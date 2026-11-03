from __future__ import annotations

import bpy

from ...blender.identity import authored_material_name
from ...blender.transactions import track_created_datablock
from ...gltf.submesh import submesh_index_for_object
from ..common.material_appearances import resolve_appearance_materials


def create_mesh_appearance_variants(
    result, appearances, json_apps, *, parent_collection=None
):
    """Create linked geometry variants with an independent material choice per object"""
    requested = tuple(
        dict.fromkeys(str(name) for name in (appearances or ("default",)))
    )
    if any(name.casefold() == "all" for name in requested):
        requested = tuple(json_apps) or ("default",)
    plans = []
    for name in requested:
        resolved, materials, status = resolve_appearance_materials(json_apps, name)
        if not resolved and status != "source_default":
            raise ValueError(f"Appearance {name!r} could not be resolved: {status}.")
        label = resolved or "default"
        if not any(label == existing[0] for existing in plans):
            plans.append((label, materials))

    source_collection = result["collection"]
    source_objects = tuple(result["objects"])
    source_name = source_collection.name
    parent_collection = parent_collection or bpy.context.scene.collection
    material_tables = []
    for obj in source_objects:
        material_tables.append(
            {
                authored_material_name(material): material
                for material in obj.data.materials
                if material is not None
            }
        )

    variants, all_mesh_objects = [], []
    for index, (name, materials) in enumerate(plans):
        if index == 0:
            collection, objects = source_collection, source_objects
        else:
            collection = track_created_datablock(
                "collections", bpy.data.collections.new(source_name)
            )
            for key in source_collection.keys():
                collection[key] = source_collection[key]
            parent_collection.children.link(collection)
            objects = []
            for source in source_objects:
                obj = track_created_datablock("objects", source.copy())
                collection.objects.link(obj)
                objects.append(obj)
            armature = result.get("armature")
            if armature is not None:
                collection.objects.link(armature)
        if len(plans) > 1 or name != "default":
            collection.name = f"{source_name}@{name}"
        collection["appearance"] = name
        for obj, submesh, table in zip(
            objects, result["mesh_data"].submeshes, material_tables
        ):
            submesh_index = submesh_index_for_object(obj, None)
            if materials:
                if submesh_index is None or submesh_index >= len(materials):
                    raise ValueError(
                        f"Appearance {name!r} has no material mapping for {obj.name!r}."
                    )
                material_name = materials[submesh_index]
            else:
                material_name = (
                    submesh.material_names[0] if submesh.material_names else ""
                )
            obj["cp77_linked_variant_data"] = True
            obj["cp77_material_name"] = material_name
            for slot_index, slot in enumerate(obj.material_slots):
                slot.link = "OBJECT"
                slot.material = table.get(material_name) if slot_index == 0 else None
        variants.append(collection)
        all_mesh_objects.extend(objects)
    result["appearance_collections"] = tuple(variants)
    result["all_objects"] = list(
        dict.fromkeys((*result.get("all_objects", ()), *all_mesh_objects))
    )
    return result
