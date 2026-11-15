from __future__ import annotations

import bpy

from ...blender.identity import authored_material_name
from ...blender.mesh_appearances import (
    appearance_index,
    record_slot_material,
    store_original_materials,
)
from ...gltf.submesh import submesh_index_from_name
from ..common.material_appearances import resolve_appearance_materials


def _appearance_plans(appearances, json_apps):
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
        if not any(label == existing for existing, _materials in plans):
            plans.append((label, materials))
    return plans


def create_mesh_appearance_variants(result, appearances, json_apps):
    """Warnings from showing the first requested appearance on the imported objects and recording each one"""
    plans = _appearance_plans(appearances, json_apps)
    scene = bpy.context.scene
    warnings = []
    for position, (obj, submesh) in enumerate(
        zip(result["objects"], result["mesh_data"].submeshes)
    ):
        mesh = obj.data
        submesh_index = submesh_index_from_name(submesh.name, position)
        own = submesh.material_names[0] if submesh.material_names else ""
        names = []
        for label, materials in plans:
            if not materials:
                names.append(own)
            elif submesh_index < len(materials):
                names.append(materials[submesh_index])
            else:
                names.append(own)
                warnings.append(
                    f"Appearance {label!r} has no material for submesh {submesh_index} ({obj.name}); it shows {own!r}."
                )
        obj["cp77_material_name"] = names[0]
        table = {
            authored_material_name(material): material
            for material in mesh.materials
            if material is not None
        }
        if not table:
            continue
        chosen = [table.get(name) for name in names]
        mesh.materials.clear()
        mesh.materials.append(chosen[0])
        store_original_materials(obj)
        if len(plans) < 2:
            continue
        for (label, _materials), material in zip(plans, chosen):
            if material is not None:
                record_slot_material(mesh, 0, material, appearance_index(scene, label))
    return warnings
