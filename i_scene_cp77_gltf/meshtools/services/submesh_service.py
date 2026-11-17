import json
import re

import bpy
import numpy as np

from ...blender.context import (
    restore_previous_context,
    safe_mode_switch,
    store_current_context,
)
from ...blender.identity import rna_identity, rna_is_live
from ...blender.mesh import is_mesh
from ...blender.mesh_appearances import (
    restore_appearance_materials,
    stash_appearance_materials,
)
from ...blender.mesh_validation import weighted_group_names
from ...blender.naming import fit_id_name
from ...blender.operator_results import OperationResult, require_finished
from ...blender.outliner import outliner_object_order
from ...blender.selection import select_objects
from ...blender.transactions import (
    remove_datablock_on_commit,
    snapshot_datablocks,
    track_collection_state,
    track_created_since,
    track_mesh_object,
    track_mutation,
    track_object_state,
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
_SAFE_JOIN_SUBMESH_INDEX = "cp77_safe_join_submesh_index"
# Safe Join joins copies; each submesh object waits on its marker, out of every collection, for Safe Split to give it
# its edited geometry back with its own modifiers, rig, transform and properties.
_SAFE_JOIN_OBJECT = "cp77_safe_join_object"
_SAFE_JOIN_COLLECTIONS = "cp77_safe_join_collections"


def _submesh_positions(context, objects):
    """Each object's submesh index, its Outliner position among the meshes of its collection, by object"""
    orders = {}
    positions = {}
    for obj in objects:
        collection = (
            obj.users_collection[0]
            if obj.users_collection
            else context.scene.collection
        )
        order = orders.get(collection.as_pointer())
        if order is None:
            meshes = [other for other in collection.objects if other.type == "MESH"]
            order = orders[collection.as_pointer()] = outliner_object_order(
                context, meshes
            )
        positions[obj.as_pointer()] = order.index(obj)
    return positions


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


def _temporary_submesh_material(obj, submesh_index, source_name):
    material = bpy.data.materials.new(name=f"CP77_SafeJoin_{source_name}")
    tag_owned(material, _SAFE_JOIN_ROLE, source=source_name)
    material.diffuse_color = (0.8, 0.8, 0.8, 1.0)
    material[_SAFE_JOIN_SUBMESH_INDEX] = int(submesh_index)
    material[_SAFE_JOIN_METADATA] = json.dumps(
        _material_names(obj), separators=(",", ":")
    )
    # The joined mesh no longer uses the submesh's materials; the marker holds them so a saved file keeps them.
    for index, slot in enumerate(obj.material_slots):
        if slot.material is not None:
            material[f"{_SAFE_JOIN_SLOT}{index}"] = slot.material
    return material


def _property_value(value):
    for convert in ("to_dict", "to_list"):
        if hasattr(value, convert):
            return getattr(value, convert)()
    return value


def _stage(obj, submesh_index, source_name):
    """Give the submesh copy one marker material that remembers its submesh index, materials, appearances and face material indices"""
    marker = _temporary_submesh_material(obj, submesh_index, source_name)
    mesh = obj.data
    # The joined mesh is for sculpting; the marker keeps the submesh's appearances until Safe Split gives them back.
    stash_appearance_materials(mesh, marker)
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


def _working_copy(obj):
    """A copy of the submesh with a mesh of its own, linked where the submesh is, for the join to consume"""
    copy = obj.copy()
    copy.data = obj.data.copy()
    for collection in obj.users_collection:
        collection.objects.link(copy)
    return copy


def _set_aside(obj, marker):
    """Keep the submesh on its marker and out of every collection while the joined copy stands in for it"""
    marker[_SAFE_JOIN_OBJECT] = obj
    marker[_SAFE_JOIN_COLLECTIONS] = json.dumps(
        [collection.name for collection in obj.users_collection],
        separators=(",", ":"),
    )
    for collection in tuple(obj.users_collection):
        collection.objects.unlink(obj)


def _collection_named(name):
    collection = bpy.data.collections.get(name)
    if collection is not None:
        return collection
    return next(
        (
            scene.collection
            for scene in bpy.data.scenes
            if scene.collection.name == name
        ),
        None,
    )


def _marker_collections(marker, fallback=()):
    try:
        names = json.loads(marker[_SAFE_JOIN_COLLECTIONS])
    except (KeyError, TypeError, ValueError):
        names = ()
    collections = [
        collection
        for collection in (_collection_named(name) for name in names)
        if collection is not None
    ]
    return collections or list(fallback)


def _link(obj, collections):
    for collection in collections:
        if collection.objects.get(obj.name) is not obj:
            collection.objects.link(obj)


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
    active = context.view_layer.objects.active
    if active not in selected:
        active = selected[0]
    ordered = [active, *(obj for obj in selected if obj != active)]

    store_current_context()
    restored = False
    try:
        safe_mode_switch("OBJECT")
        positions = _submesh_positions(context, ordered)
        copies, staged = [], []
        try:
            for obj in ordered:
                copy = _working_copy(obj)
                copies.append((copy, copy.data))
                staged.append(
                    (obj, _stage(copy, positions[obj.as_pointer()], obj.name))
                )
            for obj, marker in staged:
                _set_aside(obj, marker)
            select_objects([copy for copy, _mesh in copies], context=context)
            require_finished(bpy.ops.object.join(), "Join selected submeshes")
        except Exception:
            # Nothing was joined: the copies go, and each submesh is back where it was.
            for obj, marker in staged:
                _link(obj, _marker_collections(marker))
            for copy, mesh in copies:
                if rna_is_live(copy):
                    bpy.data.objects.remove(copy)
                if rna_is_live(mesh) and not mesh.users:
                    bpy.data.meshes.remove(mesh)
            for _obj, marker in staged:
                bpy.data.materials.remove(marker)
            raise
        joined = context.view_layer.objects.active
        joined.name = fit_id_name(active.name, "_joined")
        # The join leaves the other copies' meshes without users.
        for _copy, mesh in copies:
            if rna_is_live(mesh) and not mesh.users:
                bpy.data.meshes.remove(mesh)
        restore_previous_context()
        restored = True
        # The submeshes the selection held are set aside, so the joined mesh takes their place in it.
        select_objects(joined, context=context)
        return OperationResult.finished(
            f"Joined {len(selected)} submeshes.", payload=joined
        )
    except Exception as error:
        return OperationResult.cancelled(f"Safe join failed: {error}", error=error)
    finally:
        if not restored:
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
    restore_appearance_materials(obj.data, marker_material)


def _restore_face_materials(mesh):
    attribute = mesh.attributes.get(_SAFE_JOIN_FACE_MATERIALS)
    if attribute is None:
        return
    if mesh.polygons:
        indices = np.empty(len(mesh.polygons), dtype=np.int32)
        attribute.data.foreach_get("value", indices)
        mesh.polygons.foreach_set("material_index", indices)
    mesh.attributes.remove(attribute)


def _moves_nothing(block):
    count = len(block.data)
    if block.relative_key == block or not count:
        return True
    positions = np.empty(count * 3, dtype=np.float32)
    reference = np.empty(count * 3, dtype=np.float32)
    block.data.foreach_get("co", positions)
    block.relative_key.data.foreach_get("co", reference)
    return np.allclose(positions, reference, rtol=0.0, atol=1e-6)


def _keep_own_mesh_data(piece, original):
    """Leave the piece only the vertex groups, shape keys, attributes and properties of the original's mesh, keeping any edited while joined"""
    mesh = original.data
    groups = {group.name for group in original.vertex_groups}
    weighted = weighted_group_names(piece)
    for group in tuple(piece.vertex_groups):
        if group.name not in groups and group.name not in weighted:
            piece.vertex_groups.remove(group)
    keys = piece.data.shape_keys
    if keys is not None:
        own = (
            {block.name for block in mesh.shape_keys.key_blocks}
            if mesh.shape_keys
            else set()
        )
        for block in reversed(tuple(keys.key_blocks)[1:]):
            if block.name not in own and _moves_nothing(block):
                piece.shape_key_remove(block)
        if not own and len(keys.key_blocks) == 1:
            piece.shape_key_remove(keys.key_blocks[0])
    data = piece.data
    for attribute in tuple(data.attributes):
        if (
            attribute.name not in mesh.attributes
            and not attribute.is_internal
            and not attribute.is_required
        ):
            data.attributes.remove(attribute)
    for key in tuple(data.keys()):
        del data[key]
    for key, value in mesh.items():
        data[key] = _property_value(value)


def _return_to_original(piece, original, marker):
    """Give the original submesh object the piece's edited geometry, in its own space, under its own mesh name"""
    old = original.data
    _keep_own_mesh_data(piece, original)
    mesh = piece.data
    # The join moved the vertices into the joined object's space; the original keeps its own transform.
    matrix = original.matrix_world.inverted_safe() @ piece.matrix_world
    if not np.allclose(np.array(matrix), np.eye(4), rtol=0.0, atol=1e-7):
        mesh.transform(matrix)
    collections = _marker_collections(marker, piece.users_collection)
    for collection in (*collections, *piece.users_collection):
        track_collection_state(collection)
    track_object_state(original)
    name = old.name

    def restore_names(old=old, mesh=mesh, name=name):
        if rna_is_live(mesh) and mesh.name == name:
            mesh.name = fit_id_name("CP77_SafeSplit_", name)
        if rna_is_live(old):
            old.name = name

    track_mutation(("safe_split_mesh_name", rna_identity(old)), restore_names)
    original.data = mesh
    old.name = fit_id_name("CP77_SafeSplit_", name)
    mesh.name = name
    remove_datablock_on_commit("meshes", old)
    for collection in tuple(piece.users_collection):
        collection.objects.unlink(piece)
    _link(original, collections)
    remove_datablock_on_commit("objects", piece)


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
    restored = False
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
        submeshes = []
        warnings = []
        names = []
        indexed = []
        for new_obj in outputs:
            try:
                marker = new_obj.data.materials[0] if new_obj.data.materials else None
                if (
                    marker is None
                    or not is_owned(marker, _SAFE_JOIN_ROLE)
                    or _SAFE_JOIN_METADATA not in marker
                ):
                    continue
                _restore_original_materials(new_obj, marker)
                original = marker.get(_SAFE_JOIN_OBJECT)
                if isinstance(original, bpy.types.Object):
                    _return_to_original(new_obj, original, marker)
                    submesh = original
                else:
                    submesh = new_obj
                    if owned_source(marker):
                        names.append((new_obj, owned_source(marker)))
                if _SAFE_JOIN_SUBMESH_INDEX in marker:
                    indexed.append((int(marker[_SAFE_JOIN_SUBMESH_INDEX]), submesh))
                remove_datablock_on_commit("materials", marker)
                submeshes.append(submesh)
            except Exception as error:
                _LOG.warning(
                    "Safe-split material restoration failed: object=%s error=%s",
                    new_obj.name,
                    error,
                    exc_info=True,
                )
                warnings.append(f"{new_obj.name}: {error}")
        # A piece without a submesh object to return to takes its submesh's name, every name freed before any is given.
        for new_obj, _name in names:
            new_obj.name = f"CP77_SafeSplit_{new_obj.name}"
        for new_obj, original_name in names:
            new_obj.name = original_name
        # Relinked in submesh order, the submeshes keep their indices in an Outliner that lists objects as linked.
        for _index, submesh in sorted(indexed, key=lambda item: item[0]):
            for collection in tuple(submesh.users_collection):
                collection.objects.unlink(submesh)
                collection.objects.link(submesh)
        restore_previous_context()
        restored = True
        select_objects(submeshes, context=context)
        result = OperationResult.finished(
            f"Split and restored {len(submeshes)} submeshes.",
            payload=tuple(submeshes),
        )
        if warnings:
            return OperationResult.finished(
                result.message,
                level="WARNING",
                warnings=warnings,
                payload=tuple(submeshes),
            )
        return result
    except Exception as error:
        return OperationResult.cancelled(f"Safe split failed: {error}", error=error)
    finally:
        if not restored:
            restore_previous_context()
