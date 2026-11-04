from __future__ import annotations

from dataclasses import dataclass

from ...assetio.values import json_object
from ...blender.collections import root_objects
from ...blender.mesh import SOURCE_MESH_EXTRAS_KEY
from ...entity.domain.chunks import FULL_MASK, parse_mask, part_visible
from ...gltf.submesh import submesh_index_for_object
from ...importers.entity.skinning import bind_skinned_objects_to_rig
from ...importers.entity.transforms import (
    configure_child_of_constraint,
    flush_pending_child_of_inverse_requests,
)

ENABLED_KEY = "cp77_component_enabled"
CHUNK_MASK_KEY = "cp77_chunk_mask"


@dataclass(frozen=True, slots=True)
class Part:
    """One chunk of a component's mesh as imported, with its material in each mesh appearance"""

    index: int
    objects: tuple
    material_names: tuple[str, ...]


def material_names(obj) -> list[str]:
    return list(json_object(obj.get(SOURCE_MESH_EXTRAS_KEY)).get("materialNames") or ())


def parts(objects) -> tuple[Part, ...]:
    grouped: dict[int, list] = {}
    for obj in objects:
        if obj.type != "MESH":
            continue
        index = submesh_index_for_object(obj)
        if index is not None:
            grouped.setdefault(int(index), []).append(obj)
    return tuple(
        Part(index, tuple(grouped[index]), tuple(material_names(grouped[index][0])))
        for index in sorted(grouped)
    )


def _apply_visibility(objects) -> None:
    for obj in objects:
        if obj.type != "MESH":
            continue
        enabled = bool(obj.get(ENABLED_KEY, True))
        mask = parse_mask(obj.get(CHUNK_MASK_KEY))
        index = submesh_index_for_object(obj)
        hidden = not enabled or (index is not None and not part_visible(mask, index))
        # The importer hides masked chunks and disabled components the same way.
        obj.hide_viewport = hidden
        obj.hide_render = hidden


def apply_enabled(objects, enabled: bool, mask: int = FULL_MASK) -> None:
    """Show or hide the component"""
    for obj in objects:
        obj[ENABLED_KEY] = bool(enabled)
        obj[CHUNK_MASK_KEY] = str(int(mask))
    _apply_visibility(objects)


def apply_chunk_mask(objects, mask: int) -> None:
    for obj in objects:
        obj[CHUNK_MASK_KEY] = str(int(mask) if mask is not None else FULL_MASK)
    _apply_visibility(objects)


def apply_attach(objects, target, subtarget: str = "") -> None:
    """Attach the component's root objects to target, or detach them, keeping their world placement"""
    roots = root_objects(objects) or tuple(objects[:1])
    for obj in roots:
        world = obj.matrix_world.copy()
        for constraint in [
            constraint
            for constraint in obj.constraints
            if constraint.type == "CHILD_OF"
        ]:
            obj.constraints.remove(constraint)
        obj.matrix_world = world
        if target is not None:
            configure_child_of_constraint(obj, target, subtarget)
    flush_pending_child_of_inverse_requests()


def apply_skin(objects, rig) -> None:
    """Deform the component's meshes with rig, or stop deforming them"""
    meshes = [obj for obj in objects if obj.type == "MESH"]
    for obj in meshes:
        modifiers = [
            modifier for modifier in obj.modifiers if modifier.type == "ARMATURE"
        ]
        if rig is None:
            for modifier in modifiers:
                obj.modifiers.remove(modifier)
        elif not modifiers:
            obj.modifiers.new("Armature", "ARMATURE").object = rig
        else:
            for modifier in modifiers:
                if modifier.object is None:
                    modifier.object = rig
    if rig is not None:
        bind_skinned_objects_to_rig(meshes, rig)
