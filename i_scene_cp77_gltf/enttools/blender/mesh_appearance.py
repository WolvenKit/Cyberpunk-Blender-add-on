from __future__ import annotations

import json
from dataclasses import dataclass

import bpy

from ...assetio.paths import absolute_local_path_key
from ...assetio.values import json_object, json_text
from ...blender.mesh import SOURCE_MESH_EXTRAS_KEY
from ...blender.mesh_source import mesh_source
from ...importers.common.mesh_assets import ensure_appearance_variants
from .apply import Part, material_names, parts
from .scene import component_objects

MESH_APPEARANCE_NAMES_KEY = "cp77_mesh_appearance_names"
_MASTERS = "MasterInstances"


@dataclass(frozen=True, slots=True)
class ComponentView:
    """What the Component and Mesh Appearance sections show of a component"""

    objects: tuple
    modelled: bool
    mesh_appearances: tuple[str, ...]
    parts: tuple[Part, ...]


def _master(objects):
    """The imported mesh master (holding the mesh's appearance table) for a component's objects"""
    meshes = [obj for obj in objects if obj.type == "MESH"]
    source = mesh_source(meshes[0]) if meshes else None
    masters = bpy.data.collections.get(_MASTERS)
    if source is None or masters is None or not source.glb_path:
        return None, None
    key = absolute_local_path_key(source.glb_path)
    for collection in masters.children:
        if (
            collection.get("cp77_json_apps")
            and absolute_local_path_key(str(collection.get("sourcePath", ""))) == key
        ):
            return masters, collection
    return masters, None


def _holders(objects):
    """The collections the objects live in"""
    seen = {}
    for obj in objects:
        for collection in obj.users_collection:
            seen.setdefault(collection.as_pointer(), collection)
    return tuple(seen.values())


def mesh_appearance_names(objects) -> tuple[str, ...]:
    holders = _holders(objects)
    for holder in holders:
        stored = holder.get(MESH_APPEARANCE_NAMES_KEY)
        if stored:
            return tuple(json.loads(str(stored)))
    _masters, master = _master(objects)
    for owner in (master, *holders):
        if owner is not None and owner.get("cp77_json_apps"):
            return tuple(json_object(owner.get("cp77_json_apps")).keys())
    return ()


def scan_component(collection, name: str) -> ComponentView:
    """The view of the component name of the appearance collection collection"""
    objects = component_objects(collection, name)
    meshes = [obj for obj in objects if obj.type == "MESH"]
    modelled = bool(meshes) and mesh_source(meshes[0]) is None
    return ComponentView(
        objects, modelled, mesh_appearance_names(objects), parts(objects)
    )


def _store_names(objects, names) -> None:
    for holder in _holders(objects):
        holder[MESH_APPEARANCE_NAMES_KEY] = json.dumps(list(names))


def _write_material_names(obj, names) -> None:
    extras = json_object(obj.get(SOURCE_MESH_EXTRAS_KEY))
    extras["materialNames"] = list(names)
    obj[SOURCE_MESH_EXTRAS_KEY] = json_text(extras)


def set_part_material(part: Part, appearance_index: int, material_name: str) -> None:
    for obj in part.objects:
        names = material_names(obj)
        while len(names) <= appearance_index:
            names.append(names[-1] if names else material_name)
        names[appearance_index] = material_name
        _write_material_names(obj, names)


def add_mesh_appearance(objects, name: str, copy_from: str) -> None:
    names = list(mesh_appearance_names(objects))
    source_index = names.index(copy_from) if copy_from in names else 0
    for part in parts(objects):
        for obj in part.objects:
            materials = material_names(obj)
            materials.append(
                materials[source_index] if source_index < len(materials) else ""
            )
            _write_material_names(obj, materials)
    _store_names(objects, (*names, name))


def remove_mesh_appearance(objects, name: str) -> None:
    names = list(mesh_appearance_names(objects))
    if name not in names:
        return
    index = names.index(name)
    for part in parts(objects):
        for obj in part.objects:
            materials = material_names(obj)
            if index < len(materials):
                del materials[index]
                _write_material_names(obj, materials)
    names.pop(index)
    _store_names(objects, names)


def assign_material(obj, material) -> None:
    """Give the object (not its shared mesh) material in every slot"""
    if not obj.material_slots:
        obj.data.materials.append(None)
    for slot in obj.material_slots:
        slot.link = "OBJECT"
        slot.material = material


def apply_mesh_appearance(objects, appearance: str) -> None:
    """Show the objects with the materials of appearance"""
    masters, master = _master(objects)
    json_apps = json_object(master.get("cp77_json_apps")) if master is not None else {}
    if master is not None and appearance in json_apps:
        variant = ensure_appearance_variants(
            masters,
            master,
            master.get("meshPath", ""),
            master.get("sourcePath", ""),
            [appearance],
            json_apps,
        ).get(appearance)
        if variant is not None:
            by_index = {
                part.index: part.objects[0] for part in parts(variant.all_objects)
            }
            for part in parts(objects):
                source = by_index.get(part.index)
                material = (
                    source.material_slots[0].material
                    if source is not None and source.material_slots
                    else None
                )
                for obj in part.objects:
                    assign_material(obj, material)
            return
    names = list(mesh_appearance_names(objects))
    index = names.index(appearance) if appearance in names else 0
    for part in parts(objects):
        name = part.material_names[index] if index < len(part.material_names) else ""
        material = bpy.data.materials.get(name) if name else None
        for obj in part.objects:
            assign_material(obj, material)
