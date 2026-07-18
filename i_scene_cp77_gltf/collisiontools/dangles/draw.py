"""
Dangle Physics Viewport Overlay — draws constraints, capsules, cones, velocity.

Key fixes vs. original:
  * Cone visualization uses coneTransformLS from authored data
  * Cone axis is derived from attachment bone × coneTransformLS → X-axis
  * Links draw correct direction (bone1 → bone2)
  * Global visibility toggles AND-ed with per-chain toggles
  * Body collision shapes use full shape rotation (transformLS.Rotation)
    for correct capsule axis orientation — matches engine line 239:
    shapeTransformMS = boneTransformMS × shapeLocationLS
"""

import math

import bpy
import gpu
import numpy as np
from gpu_extras.batch import batch_for_shader
from mathutils import Matrix, Quaternion, Vector

from .sim import spaces

_GLOBAL_HANDLER = None
_DRAW_CACHES = {}


# Geometry generators

def _get_capsule_geometry(rad: float, half_h: float):
    verts, lines = [], []
    segments, hemi_rings = 8, 4

    for r in range(hemi_rings + 1):
        theta = r * (math.pi / 2.0) / hemi_rings
        z = math.cos(theta) * rad + half_h
        xy_rad = math.sin(theta) * rad
        ring_start = len(verts)
        for s in range(segments):
            phi = s * 2 * math.pi / segments
            verts.append((math.cos(phi) * xy_rad, math.sin(phi) * xy_rad, z))
            lines.append((ring_start + s, ring_start + ((s + 1) % segments)))
            if r > 0:
                lines.append((ring_start + s, ring_start - segments + s))

    bot_equator = len(verts) - segments
    bot_start = len(verts)

    for r in range(hemi_rings + 1):
        theta = (math.pi / 2.0) + (r * (math.pi / 2.0) / hemi_rings)
        z = math.cos(theta) * rad - half_h
        xy_rad = math.sin(theta) * rad
        ring_start = len(verts)
        for s in range(segments):
            phi = s * 2 * math.pi / segments
            verts.append((math.cos(phi) * xy_rad, math.sin(phi) * xy_rad, z))
            lines.append((ring_start + s, ring_start + ((s + 1) % segments)))
            if r > 0:
                lines.append((ring_start + s, ring_start - segments + s))

    for s in range(segments):
        lines.append((bot_equator + s, bot_start + s))

    return verts, lines


def _get_box_geometry(extents, radius=0.0):
    x, y, z = (max(0.0, float(value)) + radius for value in extents)
    verts = [
        (-x, -y, -z), (x, -y, -z), (x, y, -z), (-x, y, -z),
        (-x, -y, z), (x, -y, z), (x, y, z), (-x, y, z),
    ]
    lines = [
        (0, 1), (1, 2), (2, 3), (3, 0),
        (4, 5), (5, 6), (6, 7), (7, 4),
        (0, 4), (1, 5), (2, 6), (3, 7),
    ]
    return verts, lines


def _get_two_sided_ellipsoid_geometry(radius, scale1, scale2):
    radius = max(0.0, float(radius))
    scale1 = max(0.01, float(scale1))
    scale2 = max(0.01, float(scale2))
    segments = 16
    rings = 8
    verts, lines = [], []

    for ring in range(rings + 1):
        theta = math.pi * ring / rings
        radial = math.sin(theta) * radius
        z_unit = math.cos(theta)
        z_scale = scale2 if z_unit >= 0.0 else scale1
        z = z_unit * radius * z_scale
        ring_start = len(verts)
        for segment in range(segments):
            phi = 2.0 * math.pi * segment / segments
            verts.append((
                math.cos(phi) * radial,
                math.sin(phi) * radial,
                z,
            ))
            lines.append((
                ring_start + segment,
                ring_start + ((segment + 1) % segments),
            ))
            if ring > 0:
                lines.append((
                    ring_start + segment,
                    ring_start - segments + segment,
                ))
    return verts, lines


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
            key = (
                shape.bone_name, shape.shape_type, round(shape.radius, 7),
                round(shape.x_box_extent, 7), round(shape.y_box_extent, 7),
                round(shape.height_extent, 7),
                *(round(value, 7) for value in shape.offset_ls),
                *(round(value, 7) for value in shape.rotation_ls_quat),
            )
            if key in seen:
                continue
            seen.add(key)
            yield shape


def _get_cone_geometry(origin, axis_ms, angle_rad, length=0.1):
    """Generate a bounded wire cone using ray length, not tan(angle)."""
    verts, lines = [], []
    segments = 16

    axis_ms = Vector(axis_ms)
    if axis_ms.length_squared <= 1e-12:
        axis_ms = Vector((1.0, 0.0, 0.0))
    else:
        axis_ms.normalize()

    angle_rad = min(math.pi, max(0.0, float(angle_rad)))
    ray_length = max(0.001, abs(float(length)))

    if abs(axis_ms.z) < 0.99:
        up = Vector((0.0, 0.0, 1.0))
    else:
        up = Vector((1.0, 0.0, 0.0))

    tangent = axis_ms.cross(up)
    if tangent.length_squared <= 1e-12:
        tangent = axis_ms.cross(Vector((0.0, 1.0, 0.0)))
    tangent.normalize()
    bitangent = axis_ms.cross(tangent).normalized()

    # Parameterize the boundary by ray length. Unlike tan(angle), this is
    # finite at 90 degrees and remains valid for inverted cones above 90.
    axial_distance = math.cos(angle_rad) * ray_length
    radius = abs(math.sin(angle_rad) * ray_length)
    center = Vector(origin) + axis_ms * axial_distance

    for segment in range(segments):
        theta = segment * 2.0 * math.pi / segments
        radial = tangent * math.cos(theta) + bitangent * math.sin(theta)
        point = center + radial * radius
        if not all(math.isfinite(value) for value in point):
            return [], []
        verts.append(tuple(point))

    for segment in range(segments):
        lines.append((segment, (segment + 1) % segments))

    apex_idx = len(verts)
    apex = Vector(origin)
    if not all(math.isfinite(value) for value in apex):
        return [], []
    verts.append(tuple(apex))
    for segment in range(0, segments, 4):
        lines.append((apex_idx, segment))

    return verts, lines


# Dynamic draw cache (used during live simulation)

class DangleDrawCache:
    def __init__(self):
        self.shader = gpu.shader.from_builtin('UNIFORM_COLOR')
        self.batches = {}
        self.matrix_world = Matrix.Identity(4)
        self.colors = {
            'links': (0.8, 0.2, 0.8, 1.0),
            'capsules': (0.2, 0.6, 1.0, 1.0),
            'body_shapes': (1.0, 0.5, 0.1, 1.0),
            'velocity': (0.9, 0.8, 0.2, 1.0),
            'cones': (0.1, 0.8, 0.5, 0.7),
            'springs': (0.9, 0.3, 0.7, 0.8),
        }

    def update(self, sim):
        self.batches.clear()
        if sim.num_particles == 0:
            return
        self.matrix_world = sim.arm_obj.matrix_world.copy()

        g = sim.state  # global toggles

        show_constraints = g.show_global_constraints
        show_velocity = g.show_global_velocity
        show_capsules = g.show_global_capsules
        show_body_shapes = g.show_global_body_shapes
        show_cones = g.show_global_cones

        #  Constraint links 
        if show_constraints and sim.link_idx_a is not None:
            verts = []
            p1 = sim.pos_ms[sim.link_idx_a]
            p2 = sim.pos_ms[sim.link_idx_b]
            for i in range(len(p1)):
                verts.extend([tuple(p1[i]), tuple(p2[i])])
            if verts:
                self.batches['links'] = batch_for_shader(
                    self.shader, 'LINES', {"pos": verts}
                )

        #  Velocity vectors 
        if show_velocity:
            verts = []
            idx = np.where(sim.is_free & sim.active_mask)[0]
            for i in idx:
                verts.extend([
                    tuple(sim.pos_ms[i]),
                    tuple(sim.pos_ms[i] + sim.vel_ms[i] * 0.05),
                ])
            if verts:
                self.batches['velocity'] = batch_for_shader(
                    self.shader, 'LINES', {"pos": verts}
                )

        #  Particle collision capsules 
        if show_capsules:
            p_verts, p_indices, offset = [], [], 0
            for i in np.where((sim.proj_type > 0) & sim.active_mask)[0]:
                v_loc, i_loc = _get_capsule_geometry(
                    float(sim.col_radius[i]), float(sim.col_height[i])
                )
                pb = sim.arm_obj.pose.bones.get(sim.bone_names[i])
                if not pb:
                    continue
                mat_ms = pb.matrix
                rot_to_axis = Vector((0, 0, 1)).rotation_difference(
                    Vector(sim.col_axis_ls[i]).normalized()
                ).to_matrix().to_4x4()
                final_mat = (
                    Matrix.Translation(sim.pos_ms[i])
                    @ mat_ms.to_quaternion().to_matrix().to_4x4()
                    @ rot_to_axis
                )
                for v in v_loc:
                    p_verts.append(tuple(final_mat @ Vector(v)))
                for l in i_loc:
                    p_indices.append((l[0] + offset, l[1] + offset))
                offset += len(v_loc)

            if p_verts:
                self.batches['capsules'] = batch_for_shader(
                    self.shader, 'LINES', {"pos": p_verts}, indices=p_indices
                )

        #  Body collision shapes 
        if show_body_shapes and sim.col_shapes:
            from .sim import collision
            collision.update_collision_transforms(sim, 1.0)
            b_verts, b_indices, b_offset = [], [], 0
            for shape in sim.col_shapes:
                if shape['shape_type'] == 'ROUNDED_BOX':
                    v_loc, i_loc = _get_box_geometry(
                        shape['extents'], float(shape['radius'])
                    )
                    final_mat = (
                        Matrix.Translation(Vector(shape['pos_ms']))
                        @ shape['rot_ms'].to_matrix().to_4x4()
                    )
                else:
                    v_loc, i_loc = _get_capsule_geometry(
                        float(shape['radius']), float(shape['height'])
                    )
                    axis_ms = Vector(shape['axis_ms']).normalized()
                    axis_rotation = Vector((0, 0, 1)).rotation_difference(
                        axis_ms
                    )
                    final_mat = (
                        Matrix.Translation(Vector(shape['pos_ms']))
                        @ axis_rotation.to_matrix().to_4x4()
                    )
                for v in v_loc:
                    b_verts.append(tuple(final_mat @ Vector(v)))
                for l in i_loc:
                    b_indices.append((l[0] + b_offset, l[1] + b_offset))
                b_offset += len(v_loc)
            if b_verts:
                self.batches['body_shapes'] = batch_for_shader(
                    self.shader, 'LINES', {"pos": b_verts}, indices=b_indices
                )

        #  Standalone Spring constraints
        if show_constraints and getattr(sim, '_spring_nodes', None):
            from .sim import spring
            s_verts, s_indices, s_offset = [], [], 0
            for node_index, runtime in sim._spring_nodes.items():
                particle_index = int(runtime['particle_index'])
                parent_index = int(runtime['parent_index'])
                if parent_index < 0 or not sim.active_mask[particle_index]:
                    continue
                particle = sim.particles[particle_index]
                parent_xform = runtime['previous_parent_xform']
                ellipsoid_xform = spring.constraint_ellipsoid_transform(
                    sim, particle, parent_xform
                )
                v_loc, i_loc = _get_two_sided_ellipsoid_geometry(
                    particle.spring_constraint_radius,
                    particle.spring_constraint_scale1,
                    particle.spring_constraint_scale2,
                )
                for vertex in v_loc:
                    s_verts.append(tuple(ellipsoid_xform @ Vector(vertex)))
                for line in i_loc:
                    s_indices.append((
                        line[0] + s_offset,
                        line[1] + s_offset,
                    ))
                s_offset += len(v_loc)

                pull_origin = spring.pull_force_origin_ms(
                    sim, particle, parent_xform
                )
                start = len(s_verts)
                s_verts.extend((
                    tuple(pull_origin),
                    tuple(sim.pos_ms[particle_index]),
                ))
                s_indices.append((start, start + 1))

            if s_verts:
                self.batches['springs'] = batch_for_shader(
                    self.shader, 'LINES', {"pos": s_verts}, indices=s_indices
                )

        #  Cone constraints (dynamic: uses compiled sim arrays) 
        if show_cones and hasattr(sim, 'cone_idx') and sim.cone_idx is not None:
            c_verts, c_indices, c_offset = [], [], 0
            for ci in range(len(sim.cone_idx)):
                p_idx = sim.cone_idx[ci]
                a_idx = sim.cone_attach[ci]

                attach_xform = sim._interp_bone_xform[a_idx]
                cone_xform_ls = sim.cone_xform_ls[ci]
                cone_xform_ms = attach_xform @ cone_xform_ls

                cone_origin = Vector(cone_xform_ms.translation)
                cone_rot = cone_xform_ms.to_quaternion()
                cone_axis = (cone_rot @ Vector((1, 0, 0))).normalized()

                constrained_pos = Vector(sim.pos_ms[p_idx])
                length = (constrained_pos - cone_origin).length
                if length < 0.001:
                    length = 0.1

                p_cfg = sim.particles[p_idx]
                half_angle = 45.0
                for pen in p_cfg.pendulum_constraints:
                    tgt_idx = sim.resolve_bone_index(pen.target_bone, particle_index=p_idx)
                    if tgt_idx == a_idx:
                        half_angle = pen.half_aperture_angle
                        break

                v_loc, i_loc = _get_cone_geometry(
                    cone_origin, cone_axis,
                    math.radians(half_angle), length,
                )
                for v in v_loc:
                    c_verts.append(v)
                for l in i_loc:
                    c_indices.append((l[0] + c_offset, l[1] + c_offset))
                c_offset += len(v_loc)

            if c_verts:
                self.batches['cones'] = batch_for_shader(
                    self.shader, 'LINES', {"pos": c_verts}, indices=c_indices
                )

    def draw(self):
        if not self.batches:
            return
        gpu.state.blend_set('ALPHA')
        gpu.state.depth_test_set('LESS_EQUAL')
        gpu.matrix.push()
        gpu.matrix.multiply_matrix(self.matrix_world)

        self.shader.bind()
        for name, batch in self.batches.items():
            self.shader.uniform_float("color", self.colors[name])
            batch.draw(self.shader)

        gpu.matrix.pop()
        gpu.state.depth_test_set('NONE')
        gpu.state.blend_set('NONE')


# Static rig visualization (when simulation is NOT playing)

def _draw_static_rig(arm, st):
    shader = gpu.shader.from_builtin('UNIFORM_COLOR')
    gpu.state.blend_set('ALPHA')
    gpu.state.depth_test_set('LESS_EQUAL')
    mw = arm.matrix_world

    # Global visibility toggles
    show_body_shapes = st.show_global_body_shapes
    show_capsules = st.show_global_capsules
    show_constraints = st.show_global_constraints
    show_cones = st.show_global_cones

    #  Body collision shapes 
    if show_body_shapes:
        b_verts, b_indices, offset = [], [], 0
        for s in _iter_authored_shapes(st):
            pb = spaces.resolve_pose_bone(arm, s.bone_name)
            if not pb:
                continue
            # Convert the authored REDengine local transform into the
            # generated Blender bone-local basis before composing it.
            q = s.rotation_ls_quat
            if q is not None and len(q) == 4:
                shape_rot = Quaternion(q)  # already wxyz
            else:
                shape_rot = Quaternion()
            shape_mat_ls = shape_rot.to_matrix().to_4x4()
            shape_mat_ls.translation = Vector(s.offset_ls)
            shape_mat_ms = pb.matrix @ spaces.re_local_transform_to_blender_bone(
                shape_mat_ls, arm
            )

            pos_ms = shape_mat_ms.translation
            extents = (s.x_box_extent, s.y_box_extent, s.height_extent)
            if s.shape_type == 'ROUNDED_BOX':
                v_loc, i_loc = _get_box_geometry(extents, s.radius)
                final_mat = mw @ shape_mat_ms
            else:
                axis_index = max(
                    range(3), key=lambda index: abs(extents[index])
                ) if s.shape_type == 'CAPSULE' else 2
                local_axis = Vector((
                    1.0 if axis_index == 0 else 0.0,
                    1.0 if axis_index == 1 else 0.0,
                    1.0 if axis_index == 2 else 0.0,
                ))
                axis_ms = (shape_mat_ms.to_quaternion() @ local_axis).normalized()
                v_loc, i_loc = _get_capsule_geometry(
                    s.radius, max(abs(value) for value in extents)
                )
                rot_to_axis = (
                    Vector((0, 0, 1))
                    .rotation_difference(axis_ms)
                    .to_matrix().to_4x4()
                )
                final_mat = mw @ Matrix.Translation(pos_ms) @ rot_to_axis
            for v in v_loc:
                b_verts.append(tuple(final_mat @ Vector(v)))
            for l in i_loc:
                b_indices.append((l[0] + offset, l[1] + offset))
            offset += len(v_loc)

        if b_verts:
            batch = batch_for_shader(
                shader, 'LINES', {"pos": b_verts}, indices=b_indices
            )
            shader.bind()
            shader.uniform_float("color", (1.0, 0.5, 0.1, 1.0))
            batch.draw(shader)

    #  Particle capsules 
    if show_capsules:
        p_verts, p_indices, offset = [], [], 0
        for dnode in st.dangle_nodes:
          for ch in dnode.chains:
            for p in ch.particles:
                if ch.solver == 'SPRING':
                    if p.spring_projection_type == 'DISABLED':
                        continue
                    collision_radius = p.spring_collision_radius
                    collision_height = 0.0
                    authored_axis = (1.0, 0.0, 0.0)
                else:
                    if (
                        p.dyng_projection_type == 'DISABLED'
                        and p.pos_projection_type == 'DISABLED'
                    ):
                        continue
                    collision_radius = p.capsule_radius
                    collision_height = p.capsule_height
                    authored_axis = p.capsule_axis_ls
                pb = spaces.resolve_pose_bone(arm, p.bone_name)
                if not pb:
                    continue

                v_loc, i_loc = _get_capsule_geometry(
                    collision_radius, collision_height
                )
                bl_axis = spaces.re_axis_to_blender_bone(
                    authored_axis, arm
                ).normalized()
                rot_to_axis = (
                    Vector((0, 0, 1))
                    .rotation_difference(bl_axis)
                    .to_matrix().to_4x4()
                )
                final_mat = (
                    mw
                    @ Matrix.Translation(pb.matrix.translation)
                    @ pb.matrix.to_quaternion().to_matrix().to_4x4()
                    @ rot_to_axis
                )
                for v in v_loc:
                    p_verts.append(tuple(final_mat @ Vector(v)))
                for l in i_loc:
                    p_indices.append((l[0] + offset, l[1] + offset))
                offset += len(v_loc)

        if p_verts:
            batch = batch_for_shader(
                shader, 'LINES', {"pos": p_verts}, indices=p_indices
            )
            shader.bind()
            shader.uniform_float("color", (0.2, 0.6, 1.0, 1.0))
            batch.draw(shader)

    #  Constraint links 
    if show_constraints:
        l_verts = []
        for dnode in st.dangle_nodes:
          for ch in dnode.chains:
            for p in ch.particles:
                pb1 = spaces.resolve_pose_bone(arm, p.bone_name)
                if not pb1:
                    continue
                for lnk in p.link_constraints:
                    pb2 = spaces.resolve_pose_bone(arm, lnk.target_bone)
                    if not pb2:
                        continue
                    l_verts.extend([
                        tuple(mw @ pb1.matrix.translation),
                        tuple(mw @ pb2.matrix.translation),
                    ])
        if l_verts:
            batch = batch_for_shader(shader, 'LINES', {"pos": l_verts})
            shader.bind()
            shader.uniform_float("color", (0.8, 0.2, 0.8, 1.0))
            batch.draw(shader)

    #  Standalone Spring constraints
    if show_constraints:
        from .sim import spring
        s_verts, s_indices, s_offset = [], [], 0
        for dnode in st.dangle_nodes:
            for ch in dnode.chains:
                if ch.solver != 'SPRING' or len(ch.particles) != 1:
                    continue
                particle = ch.particles[0]
                pose_bone = spaces.resolve_pose_bone(arm, particle.bone_name)
                if pose_bone is None or pose_bone.parent is None:
                    continue
                fake_sim = type('_SpringDrawContext', (), {'arm_obj': arm})()
                parent_xform = pose_bone.parent.matrix.copy()
                ellipsoid_xform = spring.constraint_ellipsoid_transform(
                    fake_sim, particle, parent_xform
                )
                final_xform = mw @ ellipsoid_xform
                v_loc, i_loc = _get_two_sided_ellipsoid_geometry(
                    particle.spring_constraint_radius,
                    particle.spring_constraint_scale1,
                    particle.spring_constraint_scale2,
                )
                for vertex in v_loc:
                    s_verts.append(tuple(final_xform @ Vector(vertex)))
                for line in i_loc:
                    s_indices.append((
                        line[0] + s_offset,
                        line[1] + s_offset,
                    ))
                s_offset += len(v_loc)

                pull_origin = mw @ spring.pull_force_origin_ms(
                    fake_sim, particle, parent_xform
                )
                dangle_position = mw @ pose_bone.matrix.translation
                start = len(s_verts)
                s_verts.extend((tuple(pull_origin), tuple(dangle_position)))
                s_indices.append((start, start + 1))

        if s_verts:
            batch = batch_for_shader(
                shader, 'LINES', {"pos": s_verts}, indices=s_indices
            )
            shader.bind()
            shader.uniform_float("color", (0.9, 0.3, 0.7, 0.8))
            batch.draw(shader)

    #  Cone constraints 
    if show_cones:
        c_verts, c_indices, offset = [], [], 0
        for dnode in st.dangle_nodes:
          for ch in dnode.chains:
            for p in ch.particles:
                for pen in p.pendulum_constraints:
                    pb_attach = spaces.resolve_pose_bone(arm, pen.target_bone)
                    pb_constrained = spaces.resolve_pose_bone(arm, p.bone_name)
                    if not pb_attach or not pb_constrained:
                        continue

                    attach_mat_ms = pb_attach.matrix.copy()
                    xf = pen.cone_transform_ls_quat
                    cone_q = Quaternion(xf)  # already wxyz
                    cone_xform_ls = cone_q.to_matrix().to_4x4()
                    cone_xform_ls.translation = Vector(
                        pen.cone_transform_ls_offset
                    )
                    cone_xform_ms = attach_mat_ms @ spaces.re_local_transform_to_blender_bone(
                        cone_xform_ls, arm
                    )

                    cone_origin = cone_xform_ms.translation
                    cone_rot = cone_xform_ms.to_quaternion()
                    cone_axis = (
                        cone_rot @ Vector((1, 0, 0))
                    ).normalized()

                    constrained_pos_ms = pb_constrained.matrix.translation
                    length = (constrained_pos_ms - cone_origin).length
                    if length < 0.001:
                        length = 0.1

                    v_loc, i_loc = _get_cone_geometry(
                        cone_origin, cone_axis,
                        math.radians(pen.half_aperture_angle), length,
                    )
                    for v in v_loc:
                        c_verts.append(tuple(mw @ Vector(v)))
                    for l in i_loc:
                        c_indices.append((l[0] + offset, l[1] + offset))
                    offset += len(v_loc)

        if c_verts:
            batch = batch_for_shader(
                shader, 'LINES', {"pos": c_verts}, indices=c_indices
            )
            shader.bind()
            shader.uniform_float("color", (0.1, 0.8, 0.5, 0.7))
            batch.draw(shader)

    gpu.state.depth_test_set('NONE')
    gpu.state.blend_set('NONE')


# Global draw handler

def _master_draw_callback():
    physx_scene = getattr(bpy.context.scene, "physx", None)
    if physx_scene and not physx_scene.viz_enabled:
        return

    for cache in _DRAW_CACHES.values():
        cache.draw()
    arm = bpy.context.object
    if arm and arm.type == 'ARMATURE' and arm.dangle_state.is_dangle_rig:
        if not arm.dangle_state.is_playing and not spaces.armature_space_errors(arm):
            _draw_static_rig(arm, arm.dangle_state)


def update_draw_cache(rig_id: str, sim):
    if rig_id not in _DRAW_CACHES:
        _DRAW_CACHES[rig_id] = DangleDrawCache()
    _DRAW_CACHES[rig_id].update(sim)


def register_global_handler():
    global _GLOBAL_HANDLER
    if _GLOBAL_HANDLER is None:
        _GLOBAL_HANDLER = bpy.types.SpaceView3D.draw_handler_add(
            _master_draw_callback, (), 'WINDOW', 'POST_VIEW'
        )


def unregister_all():
    global _GLOBAL_HANDLER
    if _GLOBAL_HANDLER:
        bpy.types.SpaceView3D.draw_handler_remove(_GLOBAL_HANDLER, 'WINDOW')
        _GLOBAL_HANDLER = None
    _DRAW_CACHES.clear()
