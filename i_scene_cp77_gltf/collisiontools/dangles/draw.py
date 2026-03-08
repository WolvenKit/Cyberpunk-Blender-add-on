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

import bpy
import gpu
import math
import numpy as np
from mathutils import Vector, Matrix, Quaternion
from gpu_extras.batch import batch_for_shader
from .sim.constraints import RE_BONE_CONV

_GLOBAL_HANDLER = None
_DRAW_CACHES = {}
conv_3x3 = RE_BONE_CONV.to_3x3()


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


def _get_cone_geometry(origin, axis_ms, angle_rad, length=0.1):
    """Generate wireframe cone from origin along axis_ms."""
    verts, lines = [], []
    segments = 16

    axis_ms = axis_ms.normalized()
    if abs(axis_ms.z) < 0.99:
        up = Vector((0, 0, 1))
    else:
        up = Vector((1, 0, 0))

    tangent = axis_ms.cross(up).normalized()
    bitangent = axis_ms.cross(tangent).normalized()

    radius = math.tan(angle_rad) * length
    center = origin + axis_ms * length

    start_idx = len(verts)
    for s in range(segments):
        theta = s * 2.0 * math.pi / segments
        pt = center + (tangent * math.cos(theta) + bitangent * math.sin(theta)) * radius
        verts.append(tuple(pt))
        lines.append((start_idx + s, start_idx + ((s + 1) % segments)))

    apex_idx = len(verts)
    verts.append(tuple(origin))
    for s in range(0, segments, 4):
        lines.append((apex_idx, start_idx + s))

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
                mw = sim.arm_obj.matrix_world
                mat_ms = mw.inverted() @ (mw @ pb.matrix)
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
        if show_body_shapes and getattr(sim.state, 'collision_shapes', None):
            from .sim import collision
            collision.update_collision_transforms(sim, 1.0)
            b_verts, b_indices, b_offset = [], [], 0
            for shape in sim.col_shapes:
                v_loc, i_loc = _get_capsule_geometry(
                    float(shape['radius']), float(shape['height'])
                )
                # axis_ms valid — computed from bone × RE_BONE_CONV × shape rotation
                axis_ms = Vector(shape['axis_ms']).normalized()
                rot_to_axis = (
                    Vector((0, 0, 1))
                    .rotation_difference(axis_ms)
                    .to_matrix()
                    .to_4x4()
                )
                final_mat = (
                    Matrix.Translation(Vector(shape['pos_ms']))
                    @ rot_to_axis
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
                    tgt_idx = sim.bone_idx_map.get(pen.target_bone)
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
        for s in st.collision_shapes:
            pb = arm.pose.bones.get(s.bone_name)
            if not pb:
                continue
            v_loc, i_loc = _get_capsule_geometry(s.radius, s.height_extent)

            # Build shape_mat_ms = bone_mat_ms × RE_BONE_CONV × shape_mat_ls
            # Same convention as cones/ellipsoids: RE_BONE_CONV bridges
            # engine bone space (X-forward) to Blender bone space (Y-forward).
            q = s.rotation_ls_quat
            if q is not None and len(q) == 4:
                shape_rot = Quaternion(q)  # already wxyz
            else:
                shape_rot = Quaternion()
            shape_mat_ls = shape_rot.to_matrix().to_4x4()
            shape_mat_ls.translation = Vector(s.offset_ls)
            shape_mat_ms = pb.matrix @ RE_BONE_CONV @ shape_mat_ls

            pos_ms = shape_mat_ms.translation
            axis_ms = (
                shape_mat_ms.to_quaternion() @ Vector((0, 0, 1))
            ).normalized()

            rot_to_axis = (
                Vector((0, 0, 1))
                .rotation_difference(axis_ms)
                .to_matrix()
                .to_4x4()
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
                if (
                    p.dyng_projection_type == 'DISABLED'
                    and p.pos_projection_type == 'DISABLED'
                ):
                    continue
                pb = arm.pose.bones.get(p.bone_name)
                if not pb:
                    continue

                v_loc, i_loc = _get_capsule_geometry(
                    p.capsule_radius, p.capsule_height
                )
                mat_ws = mw @ pb.matrix
                bl_axis = (conv_3x3 @ Vector(p.capsule_axis_ls)).normalized()
                rot_to_axis = (
                    Vector((0, 0, 1))
                    .rotation_difference(bl_axis)
                    .to_matrix().to_4x4()
                )
                final_mat = (
                    Matrix.Translation(mat_ws.translation)
                    @ mat_ws.to_quaternion().to_matrix().to_4x4()
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
                pb1 = arm.pose.bones.get(p.bone_name)
                if not pb1:
                    continue
                for lnk in p.link_constraints:
                    pb2 = arm.pose.bones.get(lnk.target_bone)
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

    #  Cone constraints 
    if show_cones:
        c_verts, c_indices, offset = [], [], 0
        mw_inv = mw.inverted()
        for dnode in st.dangle_nodes:
          for ch in dnode.chains:
            for p in ch.particles:
                for pen in p.pendulum_constraints:
                    pb_attach = arm.pose.bones.get(pen.target_bone)
                    pb_constrained = arm.pose.bones.get(p.bone_name)
                    if not pb_attach or not pb_constrained:
                        continue

                    attach_mat_ms = mw_inv @ (mw @ pb_attach.matrix)
                    xf = pen.cone_transform_ls_quat
                    cone_q = Quaternion(xf)  # already wxyz
                    cone_xform_ls = cone_q.to_matrix().to_4x4()
                    cone_xform_ms = attach_mat_ms @ RE_BONE_CONV @ cone_xform_ls

                    cone_origin = cone_xform_ms.translation
                    cone_rot = cone_xform_ms.to_quaternion()
                    cone_axis = (
                        cone_rot @ Vector((1, 0, 0))
                    ).normalized()

                    constrained_pos_ms = (
                        mw_inv @ (mw @ pb_constrained.head)
                    )
                    length = (constrained_pos_ms - cone_origin).length
                    if length < 0.001:
                        length = 0.1

                    cone_origin_ws = mw @ cone_origin
                    cone_axis_ws = (
                        mw.to_quaternion() @ cone_axis
                    ).normalized()

                    v_loc, i_loc = _get_cone_geometry(
                        cone_origin_ws, cone_axis_ws,
                        math.radians(pen.half_aperture_angle), length,
                    )
                    for v in v_loc:
                        c_verts.append(v)
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
    for cache in _DRAW_CACHES.values():
        cache.draw()
    arm = bpy.context.object
    if arm and arm.type == 'ARMATURE' and arm.dangle_state.is_dangle_rig:
        if not arm.dangle_state.is_playing:
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
