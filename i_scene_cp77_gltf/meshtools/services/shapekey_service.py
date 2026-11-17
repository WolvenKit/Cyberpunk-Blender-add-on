from contextlib import ExitStack, contextmanager

import numpy as np

from ...blender.context import get_safe_mode, safe_mode_switch
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


@contextmanager
def _evaluated_alone(items):
    disabled, hidden = [], []
    for obj, modifier in items:
        for other in obj.modifiers:
            if other != modifier and other.show_viewport:
                other.show_viewport = False
                disabled.append(other)
        if obj.hide_viewport or obj.hide_get():
            hidden.append((obj, obj.hide_viewport, obj.hide_get()))
            obj.hide_viewport = False
            obj.hide_set(False)
    try:
        with ExitStack() as stack:
            for obj, _modifier in items:
                stack.enter_context(rest_shape(obj))
            yield
    finally:
        for other in disabled:
            other.show_viewport = True
        for obj, hide_viewport, hide in hidden:
            obj.hide_viewport = hide_viewport
            obj.hide_set(hide)


def modifier_positions(context, items):
    results = []
    with _evaluated_alone(items):
        depsgraph = context.evaluated_depsgraph_get()
        for obj, modifier in items:
            evaluated = obj.evaluated_get(depsgraph)
            mesh = evaluated.to_mesh()
            try:
                if len(mesh.vertices) != len(obj.data.vertices):
                    raise RuntimeError(
                        f"{modifier.name} changed the vertex count of {obj.name}"
                    )
                positions = np.empty(len(mesh.vertices) * 3, dtype=np.float32)
                mesh.vertices.foreach_get("co", positions)
            finally:
                evaluated.to_mesh_clear()
            results.append(positions.reshape(-1, 3))
    return results


def add_positions_as_shape_key(obj, name, positions):
    if not has_shape_keys(obj):
        obj.shape_key_add(name="Basis", from_mix=False)
    key = obj.shape_key_add(name=name, from_mix=False)
    key.data.foreach_set("co", np.asarray(positions, dtype=np.float32).reshape(-1))
    key.value = 0.0
    obj.data.update()
    return key


def apply_modifier_as_shapekey(context, obj, mod_name, keep_modifier=False):
    previous_mode = get_safe_mode()
    safe_mode_switch("OBJECT")
    try:
        modifier = obj.modifiers[mod_name]
        (positions,) = modifier_positions(context, ((obj, modifier),))
        add_positions_as_shape_key(obj, mod_name, positions)
        if not keep_modifier:
            obj.modifiers.remove(modifier)
    finally:
        if previous_mode != "OBJECT":
            try:
                safe_mode_switch(previous_mode)
            except Exception as error:
                _LOG.warning(
                    "Failed to restore mode after shape-key modifier application: object=%s mode=%s error=%s",
                    getattr(obj, "name", "<unknown>"),
                    previous_mode,
                    error,
                    exc_info=True,
                )
