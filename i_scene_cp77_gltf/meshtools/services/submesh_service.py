import json
import re

import bpy

from ...blender.context import restore_previous_context, safe_mode_switch, store_current_context
from ...blender.mesh import is_mesh
from ...blender.selection import select_objects
from ..model import MeshToolResult


_SAFE_JOIN_METADATA = "cp77_safe_join_materials"


def _material_names(obj):
    return [slot.material.name if slot.material else "" for slot in obj.material_slots]


def _temporary_submesh_material(obj):
    material = bpy.data.materials.get(obj.name)
    if material is None:
        material = bpy.data.materials.new(name=obj.name)
        material.diffuse_color = (0.8, 0.8, 0.8, 1.0)
    material[_SAFE_JOIN_METADATA] = json.dumps(_material_names(obj), separators=(",", ":"))
    return material


def safe_join(context):
    selected = [
        obj for obj in context.selected_objects
        if obj.type == "MESH" and re.match(r"submesh_\d\d", obj.name)
    ]
    if not selected:
        return MeshToolResult.failure("No valid submeshes selected.")

    store_current_context()
    warnings = []
    try:
        safe_mode_switch("OBJECT")
        for obj in selected:
            try:
                material = _temporary_submesh_material(obj)
                obj.data.materials.clear()
                obj.data.materials.append(material)
                context.view_layer.objects.active = obj
                safe_mode_switch("EDIT")
                bpy.ops.mesh.select_all(action="SELECT")
                obj.active_material_index = 0
                bpy.ops.object.material_slot_assign()
                safe_mode_switch("OBJECT")
            except Exception as error:
                warnings.append(f"{obj.name}: {error}")

        bpy.ops.object.select_all(action="DESELECT")
        for obj in selected:
            obj.select_set(True)
        context.view_layer.objects.active = selected[0]
        bpy.ops.object.join()
        result = MeshToolResult.success(f"Joined {len(selected)} submeshes.", payload=context.view_layer.objects.active)
        if warnings:
            return MeshToolResult(True, result.message, "WARNING", result.payload, tuple(warnings))
        return result
    except Exception as error:
        return MeshToolResult.failure(f"Safe join failed: {error}")
    finally:
        restore_previous_context()


def _restore_original_materials(obj, marker_material):
    raw = marker_material.get(_SAFE_JOIN_METADATA, "[]")
    try:
        names = json.loads(raw)
    except (TypeError, ValueError):
        names = []
    obj.data.materials.clear()
    for name in names:
        obj.data.materials.append(bpy.data.materials.get(name) if name else None)


def safe_split(context):
    obj = context.active_object
    if not obj or not is_mesh(obj):
        return MeshToolResult.failure("No mesh selected.")

    store_current_context()
    try:
        safe_mode_switch("EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.separate(type="MATERIAL")
        safe_mode_switch("OBJECT")
        outputs = tuple(context.selected_objects)
        restored = 0
        warnings = []
        for new_obj in outputs:
            try:
                marker = new_obj.data.materials[0] if new_obj.data.materials else None
                if marker is None or _SAFE_JOIN_METADATA not in marker:
                    continue
                new_obj.name = marker.name
                _restore_original_materials(new_obj, marker)
                restored += 1
            except Exception as error:
                warnings.append(f"{new_obj.name}: {error}")
        if context.mode == "OBJECT":
            select_objects(outputs, context=context)
        result = MeshToolResult.success(f"Split and restored {restored} submeshes.", payload=outputs)
        if warnings:
            return MeshToolResult(True, result.message, "WARNING", outputs, tuple(warnings))
        return result
    except Exception as error:
        return MeshToolResult.failure(f"Safe split failed: {error}")
    finally:
        restore_previous_context()
