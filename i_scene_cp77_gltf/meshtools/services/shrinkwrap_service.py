import bpy

from ...blender.collections import get_collection_children
from ...blender.context import (
    get_safe_mode,
    restore_previous_context,
    safe_mode_switch,
    store_current_context,
)
from ...blender.shapekeys import has_shape_keys, shape_key_by_name
from ..model import MeshToolResult, ShrinkwrapRequest
from .mesh_cleanup_service import create_color_attributes


def add_shrinkwrap(context, request: ShrinkwrapRequest):
    targets = get_collection_children(request.target_collection_name, "MESH")
    if targets is None:
        return MeshToolResult.failure(
            f"Target collection '{request.target_collection_name}' was not found."
        )
    if not targets:
        return MeshToolResult.failure(
            f"Target collection '{request.target_collection_name}' contains no meshes."
        )

    target_mesh = targets[0]
    selected = [
        obj for obj in context.selected_objects
        if obj.type == "MESH" and obj != target_mesh
    ]
    if not selected:
        return MeshToolResult.failure(
            "No source meshes are selected, or only the target mesh is selected."
        )

    key_name = "GarmentSupport" if request.as_garment_support else "Shrinkwrap"
    warnings = []
    if len(targets) > 1:
        warnings.append(
            f"Target collection contains {len(targets)} meshes; using {target_mesh.name}."
        )

    if request.apply_immediately:
        store_current_context()
    try:
        if request.apply_immediately and get_safe_mode() != "OBJECT":
            safe_mode_switch("OBJECT")
        changed = 0
        for obj in selected:
            if request.vertex_group and request.vertex_group not in obj.vertex_groups:
                warnings.append(f"{obj.name}: vertex group '{request.vertex_group}' was not found.")
                continue

            modifier = obj.modifiers.new(name=key_name, type="SHRINKWRAP")
            if request.vertex_group:
                modifier.vertex_group = request.vertex_group
            if request.as_garment_support:
                create_color_attributes(obj)
                if has_shape_keys(obj):
                    for key in reversed(obj.data.shape_keys.key_blocks):
                        obj.shape_key_remove(key)

            modifier.target = target_mesh
            modifier.wrap_method = request.wrap_method
            modifier.wrap_mode = "ABOVE_SURFACE"
            modifier.offset = request.offset
            changed += 1
            if not request.apply_immediately:
                continue

            context.view_layer.objects.active = obj
            if not has_shape_keys(obj):
                if request.as_garment_support:
                    bpy.ops.object.modifier_apply_as_shapekey(modifier=modifier.name)
                else:
                    bpy.ops.object.modifier_apply(modifier=modifier.name)
            elif request.as_garment_support:
                existing = shape_key_by_name(obj, "GarmentSupport")
                if existing:
                    obj.shape_key_remove(existing)
                bpy.ops.object.modifier_apply_as_shapekey(modifier=modifier.name)
            elif shape_key_by_name(obj, "Basis") is None:
                bpy.ops.object.modifier_apply(modifier=modifier.name)
            else:
                modifier.name = "TEMP_MERGE"
                bpy.ops.object.modifier_apply_as_shapekey(modifier=modifier.name)
                basis = obj.data.shape_keys.key_blocks["Basis"]
                temporary = shape_key_by_name(obj, "TEMP_MERGE")
                for index, value in enumerate(basis.data):
                    value.co += temporary.data[index].co - basis.data[index].co
                obj.shape_key_remove(temporary)

        if changed == 0:
            return MeshToolResult.failure("No selected mesh could be shrinkwrapped.")
        result = MeshToolResult.success(
            f"Applied {key_name} to {changed} mesh(es).",
            payload=changed,
        )
        if warnings:
            return MeshToolResult(True, result.message, "WARNING", changed, tuple(warnings))
        return result
    except Exception as error:
        return MeshToolResult.failure(f"Shrinkwrap failed: {error}")
    finally:
        if request.apply_immediately:
            restore_previous_context()
