from math import radians

import bpy
from mathutils import Matrix

from .context import restore_previous_context, safe_mode_switch, store_current_context
from .selection import select_objects


def apply_xform_to_object(obj, transform_matrix):
    if not obj:
        return
    obj.matrix_world = transform_matrix @ obj.matrix_world


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
    finally:
        restore_previous_context()
