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
    prev_active = view_layer.objects.active
    preselected = [o for o in view_layer.objects if o.select_get()]
    prev_mode = getattr(prev_active, "mode", None) if prev_active else None
    prev_hide_viewport = getattr(obj, "hide_viewport", False)
    prev_hide = obj.hide_get()

    # just to be extra sure we're in object mode
    safe_mode_switch('OBJECT')

    try:
        if prev_hide_viewport:
            obj.hide_viewport = False
        if prev_hide:
            obj.hide_set(False)

        for o in preselected:
            o.select_set(False)

        view_layer.objects.active = obj
        obj.select_set(True)

        result = bpy.ops.object.modifier_apply_as_shapekey(modifier=mod_name)
        if result != {'FINISHED'}:
            raise RuntimeError(f"Failed to apply '{mod_name}' on {obj.name}: {result}")

        if not keep_modifier and mod_name in obj.modifiers:
            obj.modifiers.remove(obj.modifiers[mod_name])

    finally:
        try:
            obj.hide_viewport = prev_hide_viewport
            obj.hide_set(prev_hide)
        except Exception:
            pass

        for o in view_layer.objects:
            o.select_set(False)
        for o in preselected:
            o.select_set(True)

        view_layer.objects.active = prev_active
        if prev_active and prev_mode and prev_mode != 'OBJECT':
            try:
                safe_mode_switch(prev_mode)
            except Exception:
                pass
