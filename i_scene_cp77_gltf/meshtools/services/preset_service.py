import bpy
import numpy as np

from ...blender.operator_results import OperationResult, require_finished
from ...blender.selection import selected_meshes
from ...core.log import get_logger
from ..vertex_color_presets import get_color_presets, save_presets

_LOG = get_logger(__name__)


def add_vertex_color_preset(name, color):
    name = str(name or "").strip()
    if not name:
        return OperationResult.cancelled("Preset name cannot be empty.")
    presets = get_color_presets()
    presets[name] = [float(component) for component in color[:4]]
    save_presets(presets)
    return OperationResult.finished(f"Preset '{name}' added.")


def delete_vertex_color_preset(name):
    presets = get_color_presets()
    if name not in presets:
        return OperationResult.cancelled(f"Preset '{name}' was not found.")
    del presets[name]
    save_presets(presets)
    return OperationResult.finished(f"Preset '{name}' deleted.")


def _preset_layer(mesh):
    """The colour layer a preset paints"""
    attributes = mesh.color_attributes
    candidates = (attributes.active_color, attributes.get("Color"), *attributes)
    attribute = next(
        (
            item
            for item in candidates
            if item is not None
            and not item.name.startswith("_")
            and item.domain in {"POINT", "CORNER"}
        ),
        None,
    )
    if attribute is None:
        attribute = attributes.new(name="Color", type="FLOAT_COLOR", domain="POINT")
    attributes.active_color = attribute
    return attribute


def _paint(mesh, layer, color, chosen):
    """Paint the chosen vertices (or the corners of them) and return how many elements changed"""
    # Byte layers store, and export, sRGB values; float layers export what they store.
    field = "color_srgb" if layer.data_type == "BYTE_COLOR" else "color"
    values = np.empty(len(layer.data) * 4, dtype=np.float32)
    layer.data.foreach_get(field, values)
    values = values.reshape(-1, 4)
    if layer.domain == "CORNER":
        corners = np.empty(len(mesh.loops), dtype=np.int32)
        mesh.loops.foreach_get("vertex_index", corners)
        chosen = chosen[corners]
    values[chosen] = color
    layer.data.foreach_set(field, values.reshape(-1))
    return int(np.count_nonzero(chosen))


def apply_vertex_color_preset(context, name):
    active = context.object
    if active is None:
        return OperationResult.cancelled(
            "No active object. Please select a mesh and try again.",
            "ERROR_INVALID_CONTEXT",
        )
    if active.type != "MESH":
        return OperationResult.cancelled("The active object is not a mesh.")
    if not name:
        return OperationResult.cancelled("No preset selected.")

    presets = get_color_presets()
    color = presets.get(name)
    if color is None:
        return OperationResult.cancelled(f"Preset '{name}' was not found.")

    selected = selected_meshes(context)
    if not selected:
        return OperationResult.cancelled("No mesh objects selected.")

    rgba = np.asarray((list(color) + [1.0])[:4], dtype=np.float32)
    original_mode = context.mode
    try:
        if original_mode != "OBJECT":
            require_finished(
                bpy.ops.object.mode_set(mode="OBJECT"), "The switch to Object Mode"
            )
        changed = 0
        for obj in selected:
            mesh = obj.data
            layer = _preset_layer(mesh)
            chosen = np.zeros(len(mesh.vertices), dtype=bool)
            mesh.vertices.foreach_get("select", chosen)
            if not chosen.any() and original_mode != "EDIT_MESH":
                chosen[:] = True
            changed += _paint(mesh, layer, rgba, chosen)
            mesh.update()
        return OperationResult.finished(
            f"Preset '{name}' applied to {len(selected)} mesh(es).",
            payload=changed,
        )
    except Exception as error:
        return OperationResult.cancelled(
            f"Applying preset '{name}' failed: {error}", error=error
        )
    finally:
        if original_mode != "OBJECT":
            try:
                require_finished(
                    bpy.ops.object.mode_set(
                        mode="EDIT" if original_mode == "EDIT_MESH" else original_mode
                    ),
                    f"The restoration of {original_mode} mode",
                )
            except RuntimeError as error:
                _LOG.warning(
                    "Could not restore mode after applying vertex-color preset: mode=%s error=%s",
                    original_mode,
                    error,
                    exc_info=True,
                )
