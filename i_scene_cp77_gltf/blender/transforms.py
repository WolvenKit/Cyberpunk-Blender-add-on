from math import radians

import bpy
from mathutils import Matrix

from .context import restore_previous_context, safe_mode_switch, store_current_context
<<<<<<< Updated upstream
=======
from .identity import real_users
from .operator_results import require_finished
>>>>>>> Stashed changes
from .selection import select_objects


def apply_xform_to_object(obj, transform_matrix):
    if not obj:
        return
    obj.matrix_world = transform_matrix @ obj.matrix_world


<<<<<<< Updated upstream
def rotate_quat_180(_operator, context):
    selected = list(context.selected_objects)
    if not selected:
        return

    store_current_context()
    try:
        safe_mode_switch('OBJECT')
        select_objects(selected, make_first_active=True, clear=True, reveal=True)
        rotation = Matrix.Rotation(radians(180.0), 4, 'Z')
        for obj in selected:
            apply_xform_to_object(obj, rotation)
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
=======
def _reset_rotation(obj):
    if obj.rotation_mode == "QUATERNION":
        obj.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
    elif obj.rotation_mode == "AXIS_ANGLE":
        obj.rotation_axis_angle = (0.0, 0.0, 1.0, 0.0)
    else:
        obj.rotation_euler = (0.0, 0.0, 0.0)


def _turns_alike(users):
    """Whether the rotation of each user of a shared mesh can be applied once to the mesh"""
    data = users[0].data
    if not isinstance(data, bpy.types.Mesh) or len(users) != real_users(data):
        return False
    first = users[0].matrix_basis.to_3x3()
    if any(abs(value) < 1e-9 for value in first.to_scale()):
        return False
    return all(
        not obj.children
        and all(
            abs(a - b) <= 1e-6
            for row, other in zip(obj.matrix_basis.to_3x3(), first)
            for a, b in zip(row, other)
        )
        for obj in users
    )


def _apply_shared_rotation(users):
    """Apply the users' common rotation to their mesh once"""
    _location, rotation, scale = users[0].matrix_basis.decompose()
    stretch = Matrix.Diagonal(scale)
    users[0].data.transform(
        (stretch.inverted() @ rotation.to_matrix() @ stretch).to_4x4(), shape_keys=True
    )
    for obj in users:
        _reset_rotation(obj)


def rotate_quat_180(_operator, context):
    """Turn the selected objects half round the world Z axis and apply the turn"""
    selected = list(context.selected_objects)
    if not selected:
        return (), ()

    store_current_context()
    try:
        safe_mode_switch("OBJECT")
        select_objects(selected, make_first_active=True, clear=True, reveal=True)
        rotation = Matrix.Rotation(radians(180.0), 4, "Z")
        for obj in selected:
            apply_xform_to_object(obj, rotation)

        shared = {}
        for obj in selected:
            if obj.data is not None and real_users(obj.data) > 1:
                shared.setdefault(obj.data.as_pointer(), []).append(obj)
        kept = []
        for users in shared.values():
            if _turns_alike(users):
                _apply_shared_rotation(users)
            else:
                kept.extend(users)

        sharing = {obj.as_pointer() for users in shared.values() for obj in users}
        own = [obj for obj in selected if obj.as_pointer() not in sharing]
        if own:
            # Blender refuses to apply to an object that shares its data, so only the others are applied here.
            select_objects(own, make_first_active=True, clear=True)
            require_finished(
                bpy.ops.object.transform_apply(
                    location=False, rotation=True, scale=False
                ),
                "Applying the rotation",
            )
        return tuple(selected), tuple(kept)
>>>>>>> Stashed changes
    finally:
        restore_previous_context()
