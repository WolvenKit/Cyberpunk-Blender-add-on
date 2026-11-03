<<<<<<< Updated upstream
import bpy

from ...blender.context import safe_mode_switch
from ...blender.shapekeys import has_shape_keys, shape_key_by_name, shape_key_names


def ensure_basis(obj):
    """Ensure basis shapekey exists."""
    if has_shape_keys(obj):
        return obj.data.shape_keys.key_blocks[0]

    obj.shape_key_add(name="Basis", from_mix=False)
    return obj.data.shape_keys.key_blocks[0]


def unique_key_name(obj, base_name):
    """Generate unique shape key name."""
    existing = set(shape_key_names(obj) or [])
    if base_name not in existing:
        return base_name
    i = 1
    while f"{base_name}.{i:03d}" in existing:
        i += 1
    return f"{base_name}.{i:03d}"


def remove_key(obj, name):
    """Remove a shape key by name."""
    key = shape_key_by_name(obj, name)
    if key:
        obj.shape_key_remove(key)


def add_key_from_mix(obj, name, values=None):
    """Add shape key from mix."""
    if not has_shape_keys(obj):
        basis = ensure_basis(obj)
    else:
        basis = obj.data.shape_keys.key_blocks[0]

    kb = obj.data.shape_keys.key_blocks
    new_name = unique_key_name(obj, name)
    new_key = obj.shape_key_add(name=new_name, from_mix=False)

    src_keys = list(kb)[1:]
    val_map = {k.name: (values.get(k.name, k.value) if values else k.value) for k in src_keys}

    n = len(basis.data)
    for i in range(n):
        bco = basis.data[i].co
        out = bco.copy()
        for k in src_keys:
            v = val_map.get(k.name, 0.0)
            if v != 0.0:
                out += (k.data[i].co - bco) * v
        new_key.data[i].co = out
    return new_key


def copy_key_to_basis(obj, src_name):
    """Copy a shape key to basis."""
    if not has_shape_keys(obj):
        return False

    basis = obj.data.shape_keys.key_blocks[0]
    src = shape_key_by_name(obj, src_name)

    if not src:
        return False

    if len(basis.data) != len(src.data):
        raise RuntimeError(f"Vertex count mismatch on {obj.name}")

    for i in range(len(basis.data)):
        basis.data[i].co = src.data[i].co
    return True


def apply_modifier_as_shapekey(obj, mod_name, keep_modifier=False):
    # don't use store/restore context functions here because they'll overwrite the more important main context
    view_layer = bpy.context.view_layer
=======
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
>>>>>>> Stashed changes
    prev_active = view_layer.objects.active
    preselected = [o for o in view_layer.objects if o.select_get()]
    prev_mode = getattr(prev_active, "mode", None) if prev_active else None
    prev_hide_viewport = getattr(obj, "hide_viewport", False)
    prev_hide = obj.hide_get()

<<<<<<< Updated upstream
    # just to be extra sure we're in object mode
    safe_mode_switch('OBJECT')
=======
    safe_mode_switch("OBJECT")
>>>>>>> Stashed changes

    try:
        if prev_hide_viewport:
            obj.hide_viewport = False
        if prev_hide:
            obj.hide_set(False)

        for o in preselected:
            o.select_set(False)

        view_layer.objects.active = obj
        obj.select_set(True)

<<<<<<< Updated upstream
        result = bpy.ops.object.modifier_apply_as_shapekey(modifier=mod_name)
        if result != {'FINISHED'}:
            raise RuntimeError(f"Failed to apply '{mod_name}' on {obj.name}: {result}")
=======
        require_finished(
            bpy.ops.object.modifier_apply_as_shapekey(modifier=mod_name),
            f"Applying '{mod_name}' on {obj.name}",
        )
>>>>>>> Stashed changes

        if not keep_modifier and mod_name in obj.modifiers:
            obj.modifiers.remove(obj.modifiers[mod_name])

    finally:
        try:
            obj.hide_viewport = prev_hide_viewport
            obj.hide_set(prev_hide)
<<<<<<< Updated upstream
        except Exception:
            pass
=======
        except (ReferenceError, RuntimeError) as error:
            _LOG.warning(
                "Failed to restore object visibility after shape-key modifier application: object=%s error=%s",
                getattr(obj, "name", "<unknown>"),
                error,
                exc_info=True,
            )
>>>>>>> Stashed changes

        for o in view_layer.objects:
            o.select_set(False)
        for o in preselected:
            o.select_set(True)

        view_layer.objects.active = prev_active
<<<<<<< Updated upstream
        if prev_active and prev_mode and prev_mode != 'OBJECT':
            try:
                safe_mode_switch(prev_mode)
            except Exception:
                pass
=======
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
>>>>>>> Stashed changes
