from contextlib import contextmanager

import bpy
import numpy as np

from ...blender.context import safe_mode_switch
from ...blender.operator_results import require_finished
from ...blender.shapekeys import has_shape_keys
from ...core.log import get_logger

_LOG = get_logger(__name__)


def key_coordinates(key):
    values = np.empty(len(key.data) * 3, dtype=np.float32)
    key.data.foreach_get("co", values)
    return values.reshape(-1, 3)


@contextmanager
def rest_shape(obj):
    """Hold every shape key at zero so a modifier applied as a shape key deforms the rest shape"""
    keys = obj.data.shape_keys.key_blocks if has_shape_keys(obj) else ()
    values = {key.name: key.value for key in keys}
    for key in keys:
        key.value = 0.0
    try:
        yield
    finally:
        if has_shape_keys(obj):
            for name, value in values.items():
                key = obj.data.shape_keys.key_blocks.get(name)
                if key is not None:
                    key.value = value


def move_with_basis(obj, displacement):
    """Add one displacement to every shape key and to the mesh, so each key keeps its offset from the basis"""
    displacement = np.asarray(displacement, dtype=np.float32).reshape(-1, 3)
    shape_keys = obj.data.shape_keys
    for key in shape_keys.key_blocks:
        key.data.foreach_set("co", (key_coordinates(key) + displacement).reshape(-1))
    obj.data.vertices.foreach_set(
        "co", key_coordinates(shape_keys.reference_key).reshape(-1)
    )
    obj.data.update()


def apply_modifier_as_shapekey(context, obj, mod_name, keep_modifier=False):
    # Preserve the outer context; nested store/restore would overwrite it.
    view_layer = context.view_layer
    prev_active = view_layer.objects.active
    preselected = [o for o in view_layer.objects if o.select_get()]
    prev_mode = getattr(prev_active, "mode", None) if prev_active else None
    prev_hide_viewport = getattr(obj, "hide_viewport", False)
    prev_hide = obj.hide_get()

    safe_mode_switch("OBJECT")

    try:
        if prev_hide_viewport:
            obj.hide_viewport = False
        if prev_hide:
            obj.hide_set(False)

        for o in preselected:
            o.select_set(False)

        view_layer.objects.active = obj
        obj.select_set(True)

        require_finished(
            bpy.ops.object.modifier_apply_as_shapekey(modifier=mod_name),
            f"Applying '{mod_name}' on {obj.name}",
        )

        if not keep_modifier and mod_name in obj.modifiers:
            obj.modifiers.remove(obj.modifiers[mod_name])

    finally:
        try:
            obj.hide_viewport = prev_hide_viewport
            obj.hide_set(prev_hide)
        except (ReferenceError, RuntimeError) as error:
            _LOG.warning(
                "Failed to restore object visibility after shape-key modifier application: object=%s error=%s",
                getattr(obj, "name", "<unknown>"),
                error,
                exc_info=True,
            )

        for o in view_layer.objects:
            o.select_set(False)
        for o in preselected:
            o.select_set(True)

        view_layer.objects.active = prev_active
        if prev_active and prev_mode and prev_mode != "OBJECT":
            try:
                safe_mode_switch(prev_mode)
            except Exception as error:
                _LOG.warning(
                    "Failed to restore mode after shape-key modifier application: object=%s mode=%s error=%s",
                    getattr(obj, "name", "<unknown>"),
                    prev_mode,
                    error,
                    exc_info=True,
                )
