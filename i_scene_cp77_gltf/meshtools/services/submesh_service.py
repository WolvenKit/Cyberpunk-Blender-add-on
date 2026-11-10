import json
import re

import bpy
import numpy as np

from ...blender.context import (
    restore_previous_context,
    safe_mode_switch,
    store_current_context,
)
from ...blender.mesh import is_mesh
from ...blender.operator_results import OperationResult, require_finished
from ...blender.selection import select_objects
from ...blender.transactions import (
    remove_datablock_on_commit,
    snapshot_datablocks,
    track_created_since,
    track_mesh_object,
    transactional,
)
from ...core.log import get_logger
from ..model import shared_mesh_refusal
from ..ownership import is_owned, owned_source, tag_owned

_LOG = get_logger(__name__)


_SAFE_JOIN_METADATA = "cp77_safe_join_materials"
_SAFE_JOIN_ROLE = "SAFE_JOIN_MARKER"
# The marker's custom properties holding the submesh's materials, by slot, and the face attribute holding each face's
# material index while the joined mesh gives every face the marker.
_SAFE_JOIN_SLOT = "cp77_safe_join_slot_"
_SAFE_JOIN_FACE_MATERIALS = "cp77_safe_join_material_index"


def _material_names(obj):
    return [slot.material.name if slot.material else "" for slot in obj.material_slots]


def is_safe_join_result(obj):
    """Whether the mesh came out of Safe Join, so Safe Split can restore its submeshes"""
    materials = getattr(getattr(obj, "data", None), "materials", ())
    return any(
        is_owned(material, _SAFE_JOIN_ROLE)
        for material in materials
        if material is not None
    )


def _temporary_submesh_material(obj):
    material = bpy.data.materials.new(name=f"CP77_SafeJoin_{obj.name}")
    tag_owned(material, _SAFE_JOIN_ROLE, source=obj.name)
    material.diffuse_color = (0.8, 0.8, 0.8, 1.0)
    material[_SAFE_JOIN_METADATA] = json.dumps(
        _material_names(obj), separators=(",", ":")
    )
    # The joined mesh no longer uses the submesh's materials; the marker holds them so a saved file keeps them.
    for index, slot in enumerate(obj.material_slots):
        if slot.material is not None:
            material[f"{_SAFE_JOIN_SLOT}{index}"] = slot.material
    return material


def _stage(obj):
    """Give the submesh one marker material that remembers its materials and each face's material index"""
    marker = _temporary_submesh_material(obj)
    mesh = obj.data
    if mesh.polygons:
        indices = np.empty(len(mesh.polygons), dtype=np.int32)
        mesh.polygons.foreach_get("material_index", indices)
        attribute = mesh.attributes.get(_SAFE_JOIN_FACE_MATERIALS)
        if attribute is None:
            attribute = mesh.attributes.new(_SAFE_JOIN_FACE_MATERIALS, "INT", "FACE")
        attribute.data.foreach_set("value", indices)
    mesh.materials.clear()
    mesh.materials.append(marker)
    if mesh.polygons:
        mesh.polygons.foreach_set(
            "material_index", np.zeros(len(mesh.polygons), dtype=np.int32)
        )
    return marker


def safe_join(context):
    selected = [
        obj
        for obj in context.selected_objects
        if obj.type == "MESH" and re.match(r"submesh_\d\d", obj.name)
    ]
    if not selected:
        return OperationResult.cancelled("No valid submeshes selected.")
    # Staging rewrites each submesh's materials, and the join writes into the active one's mesh.
    refusal = shared_mesh_refusal(selected, "join")
    if refusal is not None:
        return refusal

    store_current_context()
    warnings = []
    staged = []
    try:
        safe_mode_switch("OBJECT")
        for obj in selected:
            try:
                staged.append((obj, _stage(obj)))
            except Exception as error:
                _LOG.warning(
                    "Safe-join material staging failed: object=%s error=%s",
                    obj.name,
                    error,
                    exc_info=True,
                )
                warnings.append(f"{obj.name}: {error}")

        select_objects(selected, context=context)
        try:
            require_finished(bpy.ops.object.join(), "Join selected submeshes")
        except Exception:
            # The submeshes are still apart: each gets its materials back.
            for obj, marker in staged:
                _restore_original_materials(obj, marker)
                bpy.data.materials.remove(marker)
            raise
        result = OperationResult.finished(
            f"Joined {len(selected)} submeshes.",
            payload=context.view_layer.objects.active,
        )
        if warnings:
            return OperationResult.finished(
                result.message,
                level="WARNING",
                warnings=warnings,
                payload=result.details.get("payload"),
            )
        return result
    except Exception as error:
        return OperationResult.cancelled(f"Safe join failed: {error}", error=error)
    finally:
        restore_previous_context()


def _restore_original_materials(obj, marker_material):
    raw = marker_material.get(_SAFE_JOIN_METADATA, "[]")
    try:
        names = json.loads(raw)
    except (TypeError, ValueError):
        names = []
    obj.data.materials.clear()
    for index, name in enumerate(names):
        material = marker_material.get(f"{_SAFE_JOIN_SLOT}{index}")
        if not isinstance(material, bpy.types.Material):
            material = bpy.data.materials.get(name) if name else None
        obj.data.materials.append(material)
    _restore_face_materials(obj.data)


def _restore_face_materials(mesh):
    attribute = mesh.attributes.get(_SAFE_JOIN_FACE_MATERIALS)
    if attribute is None:
        return
    if mesh.polygons:
        indices = np.empty(len(mesh.polygons), dtype=np.int32)
        attribute.data.foreach_get("value", indices)
        mesh.polygons.foreach_set("material_index", indices)
    mesh.attributes.remove(attribute)


@transactional("Safe split")
def safe_split(context):
    obj = context.active_object
    if not obj or not is_mesh(obj):
        return OperationResult.cancelled("No mesh selected.")
    # Separating edits the mesh in place, which would change every other object that shares it.
    refusal = shared_mesh_refusal([obj], "split")
    if refusal is not None:
        return refusal

    store_current_context()
    try:
        safe_mode_switch("OBJECT")
        # The joined mesh is edited alone: separating splits every mesh in Edit Mode, and what it leaves selected are
        # the pieces.
        select_objects(obj, context=context)
        track_mesh_object(obj)
        before = snapshot_datablocks()
        safe_mode_switch("EDIT")
        # Selected in Edit Mode: Blender 5.0.0 can crash writing edge selection through the mesh data.
        require_finished(
            bpy.ops.mesh.select_all(action="SELECT"), "Select the joined mesh"
        )
        require_finished(
            bpy.ops.mesh.separate(type="MATERIAL"), "Separate mesh by material"
        )
        safe_mode_switch("OBJECT")
        track_created_since(before)
        outputs = tuple(context.selected_objects)
        restored = 0
        warnings = []
        names = []
        for new_obj in outputs:
            try:
                marker = new_obj.data.materials[0] if new_obj.data.materials else None
                if (
                    marker is None
                    or not is_owned(marker, _SAFE_JOIN_ROLE)
                    or _SAFE_JOIN_METADATA not in marker
                ):
                    continue
                original_name = owned_source(marker)
                _restore_original_materials(new_obj, marker)
                remove_datablock_on_commit("materials", marker)
                if original_name:
                    names.append((new_obj, original_name))
                restored += 1
            except Exception as error:
                _LOG.warning(
                    "Safe-split material restoration failed: object=%s error=%s",
                    new_obj.name,
                    error,
                    exc_info=True,
                )
                warnings.append(f"{new_obj.name}: {error}")
        # The joined object still holds one submesh's name, so every name is freed before any is given back.
        for new_obj, _name in names:
            new_obj.name = f"CP77_SafeSplit_{new_obj.name}"
        for new_obj, original_name in names:
            new_obj.name = original_name
        if context.mode == "OBJECT":
            select_objects(outputs, context=context)
        result = OperationResult.finished(
            f"Split and restored {restored} submeshes.", payload=outputs
        )
        if warnings:
            return OperationResult.finished(
                result.message, level="WARNING", warnings=warnings, payload=outputs
            )
        return result
    except Exception as error:
        return OperationResult.cancelled(f"Safe split failed: {error}", error=error)
    finally:
        restore_previous_context()
