import bpy
import gpu
from gpu_extras.batch import batch_for_shader
from mathutils import Matrix, Vector

from ...bartmoss.wireframes import (
    box_wireframe,
    capsule_wireframe,
    sphere_wireframe,
    wheel_wireframe,
)
from ...blender.physics.cooked_shapes import decode_cooked_geometry
from ...blender.physics.vehicle_geometry import basis_matrix
from ...core.log import get_logger, log_once
from ..blender.vehicle_config import vehicle_live_dynamics_config, vehicle_objects
from ..blender.vehicle_validation import resolved_game_config

_LOG = get_logger(__name__)

_handle = None
_shader = None
_cooked_line_cache = {}
LINE_COLOR = (0.0, 1.0, 0.0, 1.0)


def _evaluated_object(context, obj, depsgraph=None):
    if obj is None:
        return None
    try:
        depsgraph = depsgraph or context.evaluated_depsgraph_get()
        return obj.evaluated_get(depsgraph)
    except (ReferenceError, RuntimeError, TypeError, ValueError):
        return obj


def _collect_primitive_lines(shape_type, dims):
    key = tuple(round(float(value), 7) for value in dims)
    if shape_type == "BOX":
        return box_wireframe(key)
    if shape_type == "SPHERE":
        return sphere_wireframe(key[0])
    if shape_type == "CAPSULE":
        return capsule_wireframe(key[0], key[1])
    return (), ()


def _append_transformed_lines(all_verts, all_indices, local_verts, local_lines, matrix):
    offset = len(all_verts)
    all_verts.extend(matrix @ Vector(vertex) for vertex in local_verts)
    all_indices.extend((a + offset, b + offset) for a, b in local_lines)


def _append_vehicle_visualization(context, all_verts, all_indices, depsgraph=None):
    vehicle = getattr(context.scene, "physx_vehicle", None)
    if not vehicle or not vehicle.enabled:
        return
    root = vehicle.rig if vehicle.source_mode == "RIG" else vehicle.chassis
    if root is None:
        return
    basis = basis_matrix(vehicle)
    root_eval = _evaluated_object(context, root, depsgraph)
    location = root_eval.matrix_world.to_translation()
    rotation = root_eval.matrix_world.to_quaternion().normalized()
    rigid_world = Matrix.Translation(location) @ rotation.to_matrix().to_4x4()
    frame = rigid_world @ basis
    actor_frame = frame @ Matrix.Translation(Vector(vehicle.chassis_shape_offset))
    dimensions = Vector(vehicle.chassis_dims) * 0.5
    from ...blender.physics.vehicle_chassis import vehicle_chassis_phys_objects

    if not vehicle_chassis_phys_objects(context.scene, getattr(vehicle, "rig", None)):
        local_verts, local_lines = _collect_primitive_lines("BOX", dimensions)
        _append_transformed_lines(
            all_verts, all_indices, local_verts, local_lines, actor_frame
        )

    try:
        game_config = resolved_game_config(vehicle)
    except ValueError:
        game_config = {}
    try:
        live_config = vehicle_live_dynamics_config(vehicle)
    except (AttributeError, TypeError, ValueError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_append_vehicle_visualization", type(error).__name__),
            "append vehicle visualization: fell back after %s",
            error,
            exc_info=True,
        )
        live_config = {}
    com = Vector(vehicle.chassis_cm_offset) - Vector(vehicle.chassis_shape_offset)
    marker = max(min(dimensions.x, dimensions.y, dimensions.z) * 0.12, 0.03)
    com_verts = [
        (com.x - marker, com.y, com.z),
        (com.x + marker, com.y, com.z),
        (com.x, com.y - marker, com.z),
        (com.x, com.y + marker, com.z),
        (com.x, com.y, com.z - marker),
        (com.x, com.y, com.z + marker),
    ]
    _append_transformed_lines(
        all_verts, all_indices, com_verts, [(0, 1), (2, 3), (4, 5)], actor_frame
    )

    actor_inverse = actor_frame.inverted_safe()
    wheel_names = (
        ("bike_front", "bike_rear")
        if getattr(vehicle, "vehicle_kind", "CAR") == "BIKE"
        else ("front_left", "front_right", "rear_left", "rear_right")
    )
    wheel_count = len(wheel_names)
    radii = live_config.get("wheel_radii", game_config.get("wheel_radii", ()))
    widths = live_config.get("wheel_widths", game_config.get("wheel_widths", ()))
    center_offsets = game_config.get("wheel_center_offsets", ())
    compressions = live_config.get(
        "suspension_compressions", game_config.get("suspension_compressions", ())
    )
    droops = live_config.get(
        "suspension_droops", game_config.get("suspension_droops", ())
    )
    for index, name in enumerate(wheel_names):
        if vehicle.source_mode == "RIG":
            bone_name = getattr(vehicle, f"{name}_bone", "")
            bone = root.data.bones.get(bone_name) if bone_name else None
            if bone is None:
                continue
            root_pose = getattr(root_eval, "pose", None)
            pose_bone = (
                root_pose.bones.get(bone_name) if root_pose is not None else None
            )
            center_world = (
                root_eval.matrix_world @ pose_bone.matrix
                if pose_bone is not None
                else root_eval.matrix_world @ bone.matrix_local
            ).translation
        else:
            wheel = getattr(vehicle, name, None)
            if wheel is None:
                continue
            center_world = _evaluated_object(
                context, wheel, depsgraph
            ).matrix_world.translation
        center = actor_inverse @ center_world
        if isinstance(center_offsets, list) and len(center_offsets) == wheel_count:
            offset = center_offsets[index]
            if isinstance(offset, list) and len(offset) == 3:
                center += Vector(offset)
        radius = (
            radii[index]
            if isinstance(radii, list) and len(radii) == wheel_count
            else vehicle.wheel_radius
        )
        width = (
            widths[index]
            if isinstance(widths, list) and len(widths) == wheel_count
            else vehicle.wheel_width
        )
        local_verts, local_lines = wheel_wireframe(
            center,
            max(float(radius), 0.001),
            max(float(width), 0.001),
        )
        _append_transformed_lines(
            all_verts, all_indices, local_verts, local_lines, actor_frame
        )
        droop = (
            droops[index]
            if isinstance(droops, list) and len(droops) == wheel_count
            else vehicle.suspension_max_droop
        )
        compression = (
            compressions[index]
            if isinstance(compressions, list) and len(compressions) == wheel_count
            else vehicle.suspension_max_compression
        )
        travel_verts = [
            (center.x, center.y, center.z - float(droop)),
            (center.x, center.y, center.z + float(compression)),
        ]
        _append_transformed_lines(
            all_verts, all_indices, travel_verts, [(0, 1)], actor_frame
        )


def _cooked_shape_lines(shape, context):
    heightfield_scale = None
    if shape.shape_type == "HEIGHTFIELD":
        heightfield_scale = (
            shape.heightfield_height_scale,
            shape.heightfield_row_scale,
            shape.heightfield_column_scale,
        )
    scale_key = tuple(round(float(value), 9) for value in (heightfield_scale or ()))
    key = (str(shape.shape_type), str(shape.cooked_data), scale_key)
    cached = _cooked_line_cache.get(key)
    if cached is not None:
        return cached
    data = decode_cooked_geometry(
        shape.shape_type,
        shape.cooked_data,
        context=context,
        heightfield_scale=heightfield_scale,
    )
    flat_vertices = data["vertices"]
    flat_indices = data["indices"]
    vertices = tuple(
        (flat_vertices[index], flat_vertices[index + 1], flat_vertices[index + 2])
        for index in range(0, len(flat_vertices), 3)
    )
    lines = []
    for index in range(0, len(flat_indices), 3):
        a, b, c = flat_indices[index : index + 3]
        lines.extend(((a, b), (b, c), (c, a)))
    cached = (vertices, tuple(lines))
    _cooked_line_cache[key] = cached
    return cached


def _build_visualization_data(context):
    """Build vertex/index data for drawing"""
    all_verts = []
    all_indices = []
    idx_offset = 0

    if not context.scene.physx:
        return [], []
    depsgraph = context.evaluated_depsgraph_get()

    vehicle = getattr(context.scene, "physx_vehicle", None)
    vehicle_object_set = set()
    if vehicle and vehicle.enabled:
        vehicle_object_set = vehicle_objects(context.scene)

    for item in context.scene.physx.actors:
        obj = item.obj_ref
        if not obj or not item.visualization_enabled or obj in vehicle_object_set:
            continue

        px = obj.physx
        obj_world = _evaluated_object(context, obj, depsgraph).matrix_world
        for shape in px.shapes:
            local_verts = []
            local_lines = []

            if shape.shape_type in ("BOX", "SPHERE", "CAPSULE"):
                local_verts, local_lines = _collect_primitive_lines(
                    shape.shape_type, (shape.dim_x, shape.dim_y, shape.dim_z)
                )
            elif shape.cooked_data:
                try:
                    local_verts, local_lines = _cooked_shape_lines(shape, context)
                except Exception as error:
                    _LOG.warning(
                        "Could not visualize cooked PhysX geometry %s/%s (%s): %s",
                        obj.name,
                        shape.name,
                        shape.shape_type,
                        error,
                        exc_info=True,
                    )
                    continue

            if local_verts:
                mat_shape = (
                    Matrix.Translation(shape.local_pos)
                    @ shape.local_rot.to_matrix().to_4x4()
                )
                mat_final = obj_world @ mat_shape

                for v in local_verts:
                    all_verts.append(mat_final @ Vector(v))

                for l in local_lines:
                    all_indices.append((l[0] + idx_offset, l[1] + idx_offset))

                idx_offset += len(local_verts)

    _append_vehicle_visualization(context, all_verts, all_indices, depsgraph)
    idx_offset = len(all_verts)

    return all_verts, all_indices


def _draw_lines(shader, vertices, indices, color):
    if not vertices or not indices:
        return
    batch = batch_for_shader(shader, "LINES", {"pos": vertices}, indices=indices)
    shader.bind()
    shader.uniform_float("color", color)
    shader.uniform_float(
        "ModelViewProjectionMatrix", bpy.context.region_data.perspective_matrix
    )
    batch.draw(shader)


def _draw_callback():
    scene = bpy.context.scene
    if not scene.physx.viz_enabled:
        return

    global _shader
    # World-space vertices are rebuilt on every draw so the overlay follows moving transforms.
    all_verts, all_indices = _build_visualization_data(bpy.context)
    if _shader is None:
        _shader = gpu.shader.from_builtin("UNIFORM_COLOR")
    try:
        gpu.state.blend_set("ALPHA")
        _draw_lines(_shader, all_verts, all_indices, LINE_COLOR)
    except (ReferenceError, RuntimeError, TypeError, ValueError) as error:
        log_once(
            _LOG,
            "WARNING",
            ("viewport_draw", type(error).__name__, str(error)),
            "PhysX viewport draw failed: %s",
            error,
        )
    finally:
        gpu.state.point_size_set(1.0)
        gpu.state.line_width_set(1.0)
        gpu.state.depth_test_set("NONE")
        gpu.state.blend_set("NONE")


def register_viz():
    global _handle
    if _handle is not None:
        unregister_viz()
    _handle = bpy.types.SpaceView3D.draw_handler_add(
        _draw_callback, (), "WINDOW", "POST_VIEW"
    )


def unregister_viz():
    global _handle, _shader
    if _handle is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(_handle, "WINDOW")
        except (ReferenceError, RuntimeError, TypeError, ValueError):
            pass
    _handle = None
    _shader = None
    _cooked_line_cache.clear()
