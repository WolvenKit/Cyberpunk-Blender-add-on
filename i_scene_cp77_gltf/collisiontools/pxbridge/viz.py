import bpy
import gpu
import math
import base64
from mathutils import Matrix, Vector
from gpu_extras.batch import batch_for_shader

_handle = None
_shader = None
_visualization_cache = {}
_cache_version = 0
LINE_COLOR = (0.0, 1.0, 0.0, 1.0)


def invalidate_visualization_cache():
    """ ensures the viewport gets updated to match where the collider is """
    global _cache_version, _visualization_cache
    _cache_version += 1
    _visualization_cache.clear()


def update_shader_visuals(self, context):
    """ Callback so property changes update the viewport """
    invalidate_visualization_cache()


def _collect_primitive_lines(shape_type, dims):
    verts = []
    lines = []

    if shape_type == 'BOX':
        x, y, z = dims
        verts = [(-x, -y, -z), (x, -y, -z), (x, y, -z), (-x, y, -z), (-x, -y, z), (x, -y, z), (x, y, z), (-x, y, z)]
        lines = [(0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4), (0, 4), (1, 5), (2, 6), (3, 7)]

    elif shape_type == 'SPHERE':
        rad = dims[0]
        segments = 8
        rings = 8


        # Start from the top pole and go down to bottom
        for r in range(rings + 1):
            theta = r * math.pi / rings  # 0 to pi
            z = math.cos(theta) * rad
            xy_rad = math.sin(theta) * rad

            start_idx = len(verts)
            for s in range(segments):
                phi = s * 2 * math.pi / segments
                x = math.cos(phi) * xy_rad
                y = math.sin(phi) * xy_rad
                verts.append((x, y, z))

                # Vertical rings
                if r > 0:
                    prev_ring_start = start_idx - segments
                    lines.append((start_idx + s, prev_ring_start + s))

                # Horizontal rings
                next_s = (s + 1) % segments
                lines.append((start_idx + s, start_idx + next_s))

    elif shape_type == 'CAPSULE':
        rad, half_h = dims[0], dims[1]

        segments = 8
        # Number of rings per hemisphere total = hemi rings x 2 + 1 (the center line)
        hemi_rings = 4

        # Top Hemisphere
        top_start_idx = 0
        for r in range(hemi_rings + 1):
            theta = r * (math.pi / 2.0) / hemi_rings  # 0 to pi/2
            z = (math.cos(theta) * rad) + half_h
            xy_rad = math.sin(theta) * rad

            ring_start = len(verts)
            for s in range(segments):
                phi = s * 2 * math.pi / segments
                x = math.cos(phi) * xy_rad
                y = math.sin(phi) * xy_rad
                verts.append((x, y, z))

                # Horizontal lines
                lines.append((ring_start + s, ring_start + ((s + 1) % segments)))

                # Vertical lines connecting to previous ring
                if r > 0:
                    prev_ring = ring_start - segments
                    lines.append((ring_start + s, prev_ring + s))

        # Bottom Hemisphere
        bottom_start_idx = len(verts)
        for r in range(hemi_rings + 1):
            theta = (math.pi / 2.0) + (r * (math.pi / 2.0) / hemi_rings)  # pi/2 to pi
            z = (math.cos(theta) * rad) - half_h
            xy_rad = math.sin(theta) * rad

            ring_start = len(verts)
            for s in range(segments):
                phi = s * 2 * math.pi / segments
                x = math.cos(phi) * xy_rad
                y = math.sin(phi) * xy_rad
                verts.append((x, y, z))

                # Horizontal lines
                lines.append((ring_start + s, ring_start + ((s + 1) % segments)))

                # Vertical lines connecting to previous ring
                if r > 0:
                    prev_ring = ring_start - segments
                    lines.append((ring_start + s, prev_ring + s))

        top_eq_start = top_start_idx + (hemi_rings * segments)
        bot_eq_start = bottom_start_idx

        for s in range(segments):
            lines.append((top_eq_start + s, bot_eq_start + s))

    elif shape_type == 'HEIGHTFIELD':
        x, y = dims[0], dims[1]
        verts = [(-x, -y, -0.1), (x, -y, -0.1), (x, y, -0.1), (-x, y, -0.1), (-x, -y, 0.1), (x, -y, 0.1), (x, y, 0.1),
                 (-x, y, 0.1)]
        lines = [(0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4), (0, 4), (1, 5), (2, 6), (3, 7)]

    return verts, lines


def _build_visualization_data(context):
    """ Build vertex/index data for drawing """
    all_verts = []
    all_indices = []
    idx_offset = 0

    if not context.scene.physx:
        return [], []

    for item in context.scene.physx.actors:
        obj = item.obj_ref
        if not obj:
            continue

        px = obj.physx
        for shape in px.shapes:
            local_verts = []
            local_lines = []

            if shape.shape_type in ('BOX', 'SPHERE', 'CAPSULE', 'HEIGHTFIELD'):
                local_verts, local_lines = _collect_primitive_lines(
                        shape.shape_type,
                        (shape.dim_x, shape.dim_y, shape.dim_z)
                        )
            elif shape.cooked_data:
                try:
                    from . import pxveh34 as _bridge
                    raw = base64.b64decode(shape.cooked_data.encode('ascii'))
                    data = _bridge.get_cooked_geometry(shape.shape_type, raw)
                    vf = data['vertices']
                    ifl = data['indices']

                    for i in range(0, len(vf), 3):
                        local_verts.append((vf[i], vf[i + 1], vf[i + 2]))

                    for i in range(0, len(ifl), 3):
                        local_lines.extend(
                                [
                                    (ifl[i], ifl[i + 1]),
                                    (ifl[i + 1], ifl[i + 2]),
                                    (ifl[i + 2], ifl[i])
                                    ]
                                )
                except Exception as e:
                    print(f"Error visualizing cooked mesh: {e}")
                    continue

            # Transform and add to batch
            if local_verts:
                mat_shape = Matrix.Translation(shape.local_pos) @ shape.local_rot.to_matrix().to_4x4()
                mat_final = obj.matrix_world @ mat_shape

                for v in local_verts:
                    all_verts.append(mat_final @ Vector(v))

                for l in local_lines:
                    all_indices.append((l[0] + idx_offset, l[1] + idx_offset))

                idx_offset += len(local_verts)

    return all_verts, all_indices


def _draw_callback():
    """ Cached draw callback """
    if not bpy.context.scene.physx.viz_enabled:
        return

    global _visualization_cache, _cache_version

    cache_key = _cache_version
    if cache_key not in _visualization_cache:
        all_verts, all_indices = _build_visualization_data(bpy.context)
        _visualization_cache.clear()
        _visualization_cache[cache_key] = (all_verts, all_indices)
    else:
        all_verts, all_indices = _visualization_cache[cache_key]

    if not all_verts:
        return

    # Draw
    global _shader
    if _shader is None:
        _shader = gpu.shader.from_builtin('UNIFORM_COLOR')

    batch = batch_for_shader(
            _shader,
            'LINES',
            {"pos": all_verts},
            indices=all_indices
            )

    gpu.state.blend_set('NONE')
    _shader.bind()
    _shader.uniform_float("color", LINE_COLOR)
    _shader.uniform_float(
            "ModelViewProjectionMatrix",
            bpy.context.region_data.perspective_matrix
            )
    batch.draw(_shader)


def register_viz():
    global _handle
    _handle = bpy.types.SpaceView3D.draw_handler_add(_draw_callback, (), 'WINDOW', 'POST_VIEW')


def unregister_viz():
    global _handle, _shader
    if _handle:
        bpy.types.SpaceView3D.draw_handler_remove(_handle, 'WINDOW')
    _handle = None
    _shader = None