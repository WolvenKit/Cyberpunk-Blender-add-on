import numpy as np
from mathutils import Matrix, Vector

from .....animation.domain.dangle.collision import capsule_axis_local
from .....blender.armature_bones import resolve_bone_name
from .....blender.pose import interpolate_matrix_components
from . import spaces


def _compile_shape(sim, shape, node_index=None):
    resolved_bone_name = resolve_bone_name(sim.arm_obj, shape.bone_name)
    adjusted_ls = spaces.re_local_matrix(
        shape.rotation_ls_quat, shape.offset_ls, sim.arm_obj
    )

    bone_index = sim.resolve_bone_index(shape.bone_name, node_index=node_index)
    if bone_index is None:
        bone_index = -1
    current_ms = (
        sim._cur_bone_xform[bone_index] @ adjusted_ls
        if 0 <= bone_index < len(sim._cur_bone_xform)
        else Matrix.Identity(4)
    )
    extents = np.array(
        (shape.x_box_extent, shape.y_box_extent, shape.height_extent), dtype=np.float32
    )
    axis_local = capsule_axis_local(shape.shape_type, extents)
    current_rotation = current_ms.to_quaternion()
    current_rotation_matrix = np.array(current_ms.to_3x3(), dtype=np.float32)

    compiled = {
        "bone_name": resolved_bone_name or shape.bone_name,
        "authored_bone_name": shape.bone_name,
        "bone_index": int(bone_index),
        "shape_type": shape.shape_type,
        "is_capsule": shape.shape_type == "CAPSULE",
        "radius": shape.radius,
        "height": float(np.max(np.abs(extents))),
        "extents": extents,
        "capsule_axis_local": axis_local,
        "ls_mat": adjusted_ls,
        "prev_xform_ms": current_ms.copy(),
        "cur_xform_ms": current_ms.copy(),
        "pos_ms": np.array(current_ms.translation, dtype=np.float32),
        "rot_q": tuple(current_rotation),
        "rot_mat": current_rotation_matrix,
        "inv_rot_mat": current_rotation_matrix.T.copy(),
        "axis_ms": np.array(
            current_rotation @ Vector(axis_local),
            dtype=np.float32,
        ),
    }
    _set_current_transform(compiled, current_ms.copy())
    return compiled


def _set_current_transform(shape, transform):
    shape["cur_xform_ms"] = transform
    shape["cur_pos64"] = np.asarray(transform.translation, dtype=np.float64)
    shape["cur_rot64"] = np.asarray(transform.to_3x3(), dtype=np.float64)


def authored_shape_key(shape):
    return (
        shape.bone_name,
        shape.shape_type,
        round(float(shape.radius), 7),
        round(float(shape.x_box_extent), 7),
        round(float(shape.y_box_extent), 7),
        round(float(shape.height_extent), 7),
        *(round(float(value), 7) for value in shape.offset_ls),
        *(round(float(value), 7) for value in shape.rotation_ls_quat),
    )


def compile_collision_shapes(sim):
    system = sim.system
    node_shapes_by_node = []
    draw_shapes = []
    draw_keys = set()

    has_node_local_shapes = any(
        len(dnode.collision_shapes) > 0 for dnode in sim.state.dangle_nodes
    )

    for dnode in sim.state.dangle_nodes:
        source_shapes = (
            dnode.collision_shapes
            if has_node_local_shapes
            else sim.state.collision_shapes
        )
        node_shapes = []
        for authored_shape in source_shapes:
            compiled = _compile_shape(sim, authored_shape, len(node_shapes_by_node))
            node_shapes.append(compiled)
            key = authored_shape_key(authored_shape)
            if key not in draw_keys:
                draw_keys.add(key)
                draw_shapes.append(compiled)
        node_shapes_by_node.append(node_shapes)

    if not sim.state.dangle_nodes:
        draw_shapes = [
            _compile_shape(sim, shape) for shape in sim.state.collision_shapes
        ]
    system.node_col_shapes = node_shapes_by_node
    system.col_shapes = draw_shapes


def _set_shape_pose(shape, position, rotation):
    rotation_matrix = np.array(rotation.to_matrix(), dtype=np.float32)
    shape["pos_ms"][:] = position
    shape["rot_q"] = tuple(rotation)
    shape["rot_mat"][:] = rotation_matrix
    shape["inv_rot_mat"][:] = rotation_matrix.T
    if shape["is_capsule"]:
        shape["axis_ms"][:] = rotation @ Vector(shape["capsule_axis_local"])


def begin_shape_transforms(sim, shapes):
    for shape in shapes:
        shape["prev_xform_ms"] = shape["cur_xform_ms"].copy()
        bone_index = int(shape.get("bone_index", -1))
        if 0 <= bone_index < len(sim._cur_bone_xform):
            _set_current_transform(
                shape, sim._cur_bone_xform[bone_index] @ shape["ls_mat"]
            )


def initialize_shape_transforms(sim, shapes):
    for shape in shapes:
        bone_index = int(shape.get("bone_index", -1))
        current = (
            sim._cur_bone_xform[bone_index] @ shape["ls_mat"]
            if 0 <= bone_index < len(sim._cur_bone_xform)
            else shape["cur_xform_ms"].copy()
        )
        shape["prev_xform_ms"] = current.copy()
        _set_current_transform(shape, current.copy())
        _set_shape_pose(shape, current.translation, current.to_quaternion())


def pose_shapes(shapes, progress):
    for shape in shapes:
        position, rotation = interpolate_matrix_components(
            shape["prev_xform_ms"], shape["cur_xform_ms"], progress
        )
        _set_shape_pose(shape, position, rotation)
