import math

import bpy
import gpu
import numpy as np
from bpy.app.handlers import persistent
from gpu_extras.batch import batch_for_shader
from mathutils import Matrix, Vector

from ....animation.domain.dangle.collision import capsule_axis_local
from ....bartmoss.wireframes import (
    box_wireframe,
    capsule_wireframe,
    cone_wireframe,
    two_sided_ellipsoid_wireframe,
)
from ....blender.armature_bones import resolve_pose_bone
from ....core.log import get_logger, log_once
from .simulation import collision, spaces, spring

_GLOBAL_HANDLER = None
_DRAW_CACHES = {}
_STATIC_DRAW_CACHE = {}
_LOG = get_logger(__name__)

_COLORS = {
    "links": (0.8, 0.2, 0.8, 1.0),
    "capsules": (0.2, 0.6, 1.0, 1.0),
    "body_shapes": (1.0, 0.5, 0.1, 1.0),
    "velocity": (0.9, 0.8, 0.2, 1.0),
    "cones": (0.1, 0.8, 0.5, 0.7),
    "springs": (0.9, 0.3, 0.7, 0.8),
}
_X_AXIS = Vector((1.0, 0.0, 0.0))
_Z_AXIS = Vector((0.0, 0.0, 1.0))


class _Lines:
    """Vertices and index pairs of one line batch"""

    __slots__ = ("indices", "verts")

    def __init__(self):
        self.verts = []
        self.indices = []

    def add_wire(self, verts, indices, matrix=None):
        offset = len(self.verts)
        if matrix is None:
            self.verts.extend(verts)
        else:
            self.verts.extend(tuple(matrix @ Vector(vertex)) for vertex in verts)
        self.indices.extend(
            (first + offset, second + offset) for first, second in indices
        )

    def add_segment(self, start, end):
        offset = len(self.verts)
        self.verts.extend((tuple(start), tuple(end)))
        self.indices.append((offset, offset + 1))

    def batch(self, shader):
        if not self.verts:
            return None
        return batch_for_shader(
            shader, "LINES", {"pos": self.verts}, indices=self.indices
        )


def _translation_then(matrix, world):
    translation = Matrix.Translation(matrix.translation)
    return translation if world is None else world @ translation


def _add_shape_wire(
    lines, shape_xform, shape_type, extents, radius, axis_local, world=None
):
    """A collision shape posed by its model-space matrix (world maps model to draw space)"""
    if shape_type == "ROUNDED_BOX":
        verts, indices = box_wireframe(tuple(extents), float(radius))
        lines.add_wire(
            verts, indices, shape_xform if world is None else world @ shape_xform
        )
        return
    verts, indices = capsule_wireframe(
        float(radius), max(abs(float(value)) for value in extents)
    )
    axis_ms = (shape_xform.to_quaternion() @ Vector(axis_local)).normalized()
    lines.add_wire(
        verts,
        indices,
        (
            _translation_then(shape_xform, world)
            @ _Z_AXIS.rotation_difference(axis_ms).to_matrix().to_4x4()
        ),
    )


def _add_particle_capsule_wire(lines, bone_matrix, radius, height, axis, world=None):
    """A particle's collision capsule along axis (bone space) at its bone"""
    verts, indices = capsule_wireframe(radius, height)
    rotation_to_axis = (
        _Z_AXIS.rotation_difference(axis.normalized()).to_matrix().to_4x4()
    )
    lines.add_wire(
        verts,
        indices,
        (
            _translation_then(bone_matrix, world)
            @ bone_matrix.to_quaternion().to_matrix().to_4x4()
            @ rotation_to_axis
        ),
    )


def _add_spring_wire(
    lines, arm_obj, particle, parent_xform, particle_position, world=None
):
    """A spring's constraint ellipsoid and the line from its pull origin to the particle"""
    ellipsoid_xform = spring.constraint_ellipsoid_transform(
        arm_obj, particle, parent_xform
    )
    verts, indices = two_sided_ellipsoid_wireframe(
        particle.spring_constraint_radius,
        particle.spring_constraint_scale1,
        particle.spring_constraint_scale2,
    )
    lines.add_wire(
        verts, indices, ellipsoid_xform if world is None else world @ ellipsoid_xform
    )
    pull_origin = spring.pull_force_origin_ms(arm_obj, particle, parent_xform)
    if world is not None:
        pull_origin = world @ pull_origin
        particle_position = world @ particle_position
    lines.add_segment(pull_origin, particle_position)


def _add_cone_wire(
    lines, attach_xform, cone_xform_ls, constrained_position, half_angle, world=None
):
    """A cone constraint opening from its attachment frame out to the constrained particle's distance"""
    cone_xform_ms = attach_xform @ cone_xform_ls
    cone_origin = cone_xform_ms.translation
    cone_axis = (cone_xform_ms.to_quaternion() @ _X_AXIS).normalized()
    length = (constrained_position - cone_origin).length
    if length < 0.001:
        length = 0.1
    verts, indices = cone_wireframe(cone_origin, cone_axis, half_angle, length)
    lines.add_wire(verts, indices, world)


def _iter_authored_shapes(state):
    seen = set()
    any_node_shapes = any(node.collision_shapes for node in state.dangle_nodes)
    collections = (
        (node.collision_shapes for node in state.dangle_nodes)
        if any_node_shapes
        else (state.collision_shapes,)
    )
    for collection in collections:
        for shape in collection:
            key = collision.authored_shape_key(shape)
            if key in seen:
                continue
            seen.add(key)
            yield shape


class DangleDrawCache:
    def __init__(self):
        self.shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        self.batches = {}
        self.matrix_world = Matrix.Identity(4)
        self.simulator = None

    def update(self, sim):
        # Keep only the live simulator reference. Dynamic GPU geometry is built
        # from the final post-solver pose in draw(), after Blender has evaluated
        # the pose-bone writes for the current simulation step.
        self.simulator = sim

    @staticmethod
    def _live_bone_matrix(sim, bone_index):
        if 0 <= int(bone_index) < len(sim._pose_bones):
            pose_bone = sim._pose_bones[int(bone_index)]
            if pose_bone is not None:
                return pose_bone.matrix.copy()
        if 0 <= int(bone_index) < len(sim._interp_bone_xform):
            return sim._interp_bone_xform[int(bone_index)].copy()
        return Matrix.Identity(4)

    def _rebuild(self, sim):
        self.batches.clear()
        if sim is None or sim.system.num_particles == 0:
            return
        system = sim.system
        # The simulator's model space follows the armature's matrix_world, not its evaluated matrix.
        self.matrix_world = sim.arm_obj.matrix_world.copy()
        live_matrices = {}

        def live_bone_matrix(bone_index):
            index = int(bone_index)
            matrix = live_matrices.get(index)
            if matrix is None:
                matrix = self._live_bone_matrix(sim, index)
                live_matrices[index] = matrix
            return matrix

        def live_bone_position(bone_index):
            return live_bone_matrix(bone_index).translation

        g = sim.state  # global toggles
        wires = {}

        if g.show_global_constraints and system.link_idx_a is not None:
            verts = []
            for source_index, target_index in zip(system.link_idx_a, system.link_idx_b):
                verts.extend(
                    (
                        tuple(live_bone_position(source_index)),
                        tuple(live_bone_position(target_index)),
                    )
                )
            if verts:
                self.batches["links"] = batch_for_shader(
                    self.shader, "LINES", {"pos": verts}
                )

        if g.show_global_velocity:
            idx = np.where(system.is_free & system.active_mask)[0]
            if idx.size:
                verts = []
                for raw_index in idx:
                    index = int(raw_index)
                    start = live_bone_position(index)
                    end = start + Vector(system.vel_ms[index]) * 0.05
                    verts.extend((tuple(start), tuple(end)))
                self.batches["velocity"] = batch_for_shader(
                    self.shader, "LINES", {"pos": verts}
                )

        if g.show_global_capsules:
            lines = wires["capsules"] = _Lines()
            for i in np.where((system.proj_type > 0) & system.active_mask)[0]:
                _add_particle_capsule_wire(
                    lines,
                    live_bone_matrix(i),
                    float(system.col_radius[i]),
                    float(system.col_height[i]),
                    Vector(system.col_axis_ls[i]),
                )

        if g.show_global_body_shapes and system.col_shapes:
            lines = wires["body_shapes"] = _Lines()
            for shape in system.col_shapes:
                bone_xform = live_bone_matrix(shape.get("bone_index", -1))
                _add_shape_wire(
                    lines,
                    bone_xform @ shape["ls_mat"],
                    shape["shape_type"],
                    shape["extents"],
                    shape["radius"],
                    shape["capsule_axis_local"],
                )

        if g.show_global_constraints and system.spring_nodes:
            lines = wires["springs"] = _Lines()
            for runtime in system.spring_nodes.values():
                particle_index = int(runtime["particle_index"])
                parent_index = int(runtime["parent_index"])
                if parent_index < 0 or not system.active_mask[particle_index]:
                    continue
                _add_spring_wire(
                    lines,
                    sim.arm_obj,
                    sim.particles[particle_index],
                    live_bone_matrix(parent_index),
                    live_bone_position(particle_index),
                )

        if g.show_global_cones and system.cone_idx is not None:
            lines = wires["cones"] = _Lines()
            for ci in range(len(system.cone_idx)):
                _add_cone_wire(
                    lines,
                    live_bone_matrix(system.cone_attach[ci]),
                    sim.cone_xform_ls[ci],
                    live_bone_position(system.cone_idx[ci]),
                    math.acos(max(-1.0, min(1.0, float(system.cone_cos[ci])))),
                )

        for name, lines in wires.items():
            batch = lines.batch(self.shader)
            if batch is not None:
                self.batches[name] = batch

    def draw(self):
        # Resolve coordinates from the live simulator immediately before draw.
        # Timer/depsgraph ordering may update pose matrices after the simulation
        # step callback, so cached world/model-space GPU batches are not stable.
        if self.simulator is not None:
            self._rebuild(self.simulator)
        if not self.batches:
            return
        pushed = False
        try:
            gpu.state.blend_set("ALPHA")
            gpu.state.depth_test_set("LESS_EQUAL")
            gpu.matrix.push()
            pushed = True
            gpu.matrix.multiply_matrix(self.matrix_world)
            self.shader.bind()
            for name, batch in self.batches.items():
                self.shader.uniform_float("color", _COLORS[name])
                batch.draw(self.shader)
        finally:
            if pushed:
                gpu.matrix.pop()
            gpu.state.depth_test_set("NONE")
            gpu.state.blend_set("NONE")
            gpu.state.line_width_set(1.0)
            gpu.state.point_size_set(1.0)


def _build_static_rig_batches(arm, st):
    shader = gpu.shader.from_builtin("UNIFORM_COLOR")
    draw_items = []
    mw = arm.matrix_world

    def add_lines(name, lines):
        batch = lines.batch(shader)
        if batch is not None:
            draw_items.append((batch, _COLORS[name]))

    particles = [
        (chain, particle)
        for dnode in st.dangle_nodes
        for chain in dnode.chains
        for particle in chain.particles
    ]

    if st.show_global_body_shapes:
        lines = _Lines()
        for shape in _iter_authored_shapes(st):
            pose_bone = resolve_pose_bone(arm, shape.bone_name)
            if not pose_bone:
                continue
            extents = (shape.x_box_extent, shape.y_box_extent, shape.height_extent)
            _add_shape_wire(
                lines,
                pose_bone.matrix
                @ spaces.re_local_matrix(shape.rotation_ls_quat, shape.offset_ls, arm),
                shape.shape_type,
                extents,
                shape.radius,
                capsule_axis_local(shape.shape_type, extents),
                world=mw,
            )
        add_lines("body_shapes", lines)

    if st.show_global_capsules:
        lines = _Lines()
        for chain, particle in particles:
            if chain.solver == "SPRING":
                if particle.spring_projection_type == "DISABLED":
                    continue
                collision_radius = particle.spring_collision_radius
                collision_height = 0.0
                authored_axis = (1.0, 0.0, 0.0)
            else:
                if (
                    particle.dyng_projection_type == "DISABLED"
                    and particle.pos_projection_type == "DISABLED"
                ):
                    continue
                collision_radius = particle.capsule_radius
                collision_height = particle.capsule_height
                authored_axis = particle.capsule_axis_ls
            pose_bone = resolve_pose_bone(arm, particle.bone_name)
            if not pose_bone:
                continue
            _add_particle_capsule_wire(
                lines,
                pose_bone.matrix,
                collision_radius,
                collision_height,
                spaces.re_axis_to_blender_bone(authored_axis, arm),
                world=mw,
            )
        add_lines("capsules", lines)

    if st.show_global_constraints:
        l_verts = []
        for _chain, particle in particles:
            pb1 = resolve_pose_bone(arm, particle.bone_name)
            if not pb1:
                continue
            for lnk in particle.link_constraints:
                pb2 = resolve_pose_bone(arm, lnk.target_bone)
                if not pb2:
                    continue
                l_verts.extend(
                    [
                        tuple(mw @ pb1.matrix.translation),
                        tuple(mw @ pb2.matrix.translation),
                    ]
                )
        if l_verts:
            batch = batch_for_shader(shader, "LINES", {"pos": l_verts})
            draw_items.append((batch, _COLORS["links"]))

        lines = _Lines()
        for dnode in st.dangle_nodes:
            for chain in dnode.chains:
                if chain.solver != "SPRING" or len(chain.particles) != 1:
                    continue
                particle = chain.particles[0]
                pose_bone = resolve_pose_bone(arm, particle.bone_name)
                if pose_bone is None or pose_bone.parent is None:
                    continue
                _add_spring_wire(
                    lines,
                    arm,
                    particle,
                    pose_bone.parent.matrix.copy(),
                    pose_bone.matrix.translation,
                    world=mw,
                )
        add_lines("springs", lines)

    if st.show_global_cones:
        lines = _Lines()
        for _chain, particle in particles:
            for pen in particle.pendulum_constraints:
                pb_attach = resolve_pose_bone(arm, pen.target_bone)
                pb_constrained = resolve_pose_bone(arm, particle.bone_name)
                if not pb_attach or not pb_constrained:
                    continue
                _add_cone_wire(
                    lines,
                    pb_attach.matrix.copy(),
                    spaces.re_local_matrix(
                        pen.cone_transform_ls_quat, pen.cone_transform_ls_offset, arm
                    ),
                    pb_constrained.matrix.translation,
                    math.radians(pen.half_aperture_angle),
                    world=mw,
                )
        add_lines("cones", lines)

    return shader, tuple(draw_items)


def _draw_static_rig(arm, st):
    key = (
        arm.as_pointer(),
        st.as_pointer(),
        bool(st.show_global_body_shapes),
        bool(st.show_global_capsules),
        bool(st.show_global_constraints),
        bool(st.show_global_cones),
    )
    cached = _STATIC_DRAW_CACHE.get(key)
    if cached is None:
        cached = _build_static_rig_batches(arm, st)
        _STATIC_DRAW_CACHE.clear()
        _STATIC_DRAW_CACHE[key] = cached
    shader, draw_items = cached
    try:
        gpu.state.blend_set("ALPHA")
        gpu.state.depth_test_set("LESS_EQUAL")
        shader.bind()
        for batch, color in draw_items:
            shader.uniform_float("color", color)
            batch.draw(shader)
    finally:
        gpu.state.depth_test_set("NONE")
        gpu.state.blend_set("NONE")
        gpu.state.line_width_set(1.0)
        gpu.state.point_size_set(1.0)


@persistent
def _invalidate_static_draw_cache(_scene=None, depsgraph=None):
    if depsgraph is None:
        _STATIC_DRAW_CACHE.clear()
        return
    if not _STATIC_DRAW_CACHE:
        return
    for update in depsgraph.updates:
        datablock = update.id
        if isinstance(datablock, (bpy.types.Object, bpy.types.Armature)):
            if isinstance(datablock, bpy.types.Armature):
                _STATIC_DRAW_CACHE.clear()
                return
            if datablock.type == "ARMATURE" and getattr(
                datablock.dangle_state, "is_dangle_rig", False
            ):
                _STATIC_DRAW_CACHE.clear()
                return


def _dangle_overlays_enabled():
    scene = getattr(bpy.context, "scene", None)
    physics = getattr(scene, "physx", None) if scene is not None else None
    return bool(physics and physics.viz_enabled)


def _master_draw_callback():
    if not _dangle_overlays_enabled():
        return
    try:
        for cache in tuple(_DRAW_CACHES.values()):
            cache.draw()
        arm = bpy.context.object
        if arm and arm.type == "ARMATURE" and arm.dangle_state.is_dangle_rig:
            if not arm.dangle_state.is_playing and not spaces.armature_space_errors(
                arm
            ):
                _draw_static_rig(arm, arm.dangle_state)
    except (ReferenceError, RuntimeError, TypeError, ValueError) as error:
        log_once(
            _LOG,
            "WARNING",
            ("viewport_draw", type(error).__name__, str(error)),
            "Dangle viewport draw failed: %s",
            error,
        )
    finally:
        gpu.state.depth_test_set("NONE")
        gpu.state.blend_set("NONE")
        gpu.state.line_width_set(1.0)
        gpu.state.point_size_set(1.0)


def update_draw_cache(rig_id: str, sim):
    if rig_id not in _DRAW_CACHES:
        _DRAW_CACHES[rig_id] = DangleDrawCache()
    _DRAW_CACHES[rig_id].update(sim)


def register_global_handler():
    global _GLOBAL_HANDLER
    if _GLOBAL_HANDLER is None:
        _GLOBAL_HANDLER = bpy.types.SpaceView3D.draw_handler_add(
            _master_draw_callback, (), "WINDOW", "POST_VIEW"
        )
    handlers = bpy.app.handlers.depsgraph_update_post
    if _invalidate_static_draw_cache not in handlers:
        handlers.append(_invalidate_static_draw_cache)
    load_handlers = bpy.app.handlers.load_pre
    if _invalidate_static_draw_cache not in load_handlers:
        load_handlers.append(_invalidate_static_draw_cache)


def unregister_all():
    global _GLOBAL_HANDLER
    if _GLOBAL_HANDLER:
        bpy.types.SpaceView3D.draw_handler_remove(_GLOBAL_HANDLER, "WINDOW")
        _GLOBAL_HANDLER = None
    handlers = bpy.app.handlers.depsgraph_update_post
    if _invalidate_static_draw_cache in handlers:
        handlers.remove(_invalidate_static_draw_cache)
    load_handlers = bpy.app.handlers.load_pre
    if _invalidate_static_draw_cache in load_handlers:
        load_handlers.remove(_invalidate_static_draw_cache)
    _DRAW_CACHES.clear()
    _STATIC_DRAW_CACHE.clear()
