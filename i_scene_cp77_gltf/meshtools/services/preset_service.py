import bpy

from ...vertex_color_presets import get_color_presets, save_presets
from ..model import MeshToolResult


def add_vertex_color_preset(name, color):
    name = str(name or "").strip()
    if not name:
        return MeshToolResult.failure("Preset name cannot be empty.")
    presets = get_color_presets()
    presets[name] = [float(component) for component in color[:4]]
    save_presets(presets)
    return MeshToolResult.success(f"Preset '{name}' added.")


def delete_vertex_color_preset(name):
    presets = get_color_presets()
    if name not in presets:
        return MeshToolResult.failure(f"Preset '{name}' was not found.")
    del presets[name]
    save_presets(presets)
    return MeshToolResult.success(f"Preset '{name}' deleted.")


def _active_corner_color(mesh):
    attributes = mesh.color_attributes
    attribute = attributes.active_color
    if attribute is None or attribute.domain != "CORNER":
        attribute = attributes.get("Color")
    if attribute is None or attribute.domain != "CORNER":
        attribute = attributes.new(name="Color", type="BYTE_COLOR", domain="CORNER")
    attributes.active_color = attribute
    return attribute


def apply_vertex_color_preset(context, name):
    active = context.object
    if active is None:
        return MeshToolResult.failure("No active object. Please select a mesh and try again.")
    if active.type != "MESH":
        return MeshToolResult.failure("The active object is not a mesh.")
    if not name:
        return MeshToolResult.failure("No preset selected.")

    presets = get_color_presets()
    color = presets.get(name)
    if color is None:
        return MeshToolResult.failure(f"Preset '{name}' was not found.")

    selected = [obj for obj in context.selected_objects if obj.type == "MESH"]
    if not selected:
        return MeshToolResult.failure("No mesh objects selected.")

    original_mode = context.mode
    try:
        if original_mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        changed = 0
        for obj in selected:
            mesh = obj.data
            layer = _active_corner_color(mesh)
            selected_vertices = {vertex.index for vertex in mesh.vertices if vertex.select}
            if not selected_vertices and original_mode != "EDIT_MESH":
                selected_vertices = {vertex.index for vertex in mesh.vertices}
            for polygon in mesh.polygons:
                for loop_index in polygon.loop_indices:
                    vertex_index = mesh.loops[loop_index].vertex_index
                    if vertex_index in selected_vertices:
                        layer.data[loop_index].color = color
                        changed += 1
            mesh.update()
        return MeshToolResult.success(
            f"Preset '{name}' applied to {len(selected)} mesh(es).",
            payload=changed,
        )
    except Exception as error:
        return MeshToolResult.failure(f"Applying preset '{name}' failed: {error}")
    finally:
        if original_mode != "OBJECT":
            try:
                bpy.ops.object.mode_set(mode="EDIT" if original_mode == "EDIT_MESH" else original_mode)
            except RuntimeError:
                pass
