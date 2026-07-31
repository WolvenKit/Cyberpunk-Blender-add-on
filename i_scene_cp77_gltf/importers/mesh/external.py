from __future__ import annotations

import os
from dataclasses import dataclass

import bpy

from ...gltf.provenance import (
    ORIGIN_EXTERNAL,
    GLBContentKind,
    GLBInspection,
    mark_origin,
)

_VALID_OBJECT_TYPES = frozenset({"MESH", "ARMATURE"})
_TRACKED_DATABLOCKS = (
    "objects",
    "collections",
    "meshes",
    "armatures",
    "materials",
    "images",
    "actions",
    "cameras",
    "lights",
    "node_groups",
    "textures",
)


class ExternalGLBImportError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ExternalImportSummary:
    filepath: str
    generator: str
    object_count: int
    mesh_count: int
    armature_count: int
    action_count: int
    removed_empty_count: int


def _context_snapshot():
    return (
        tuple(bpy.context.selected_objects),
        bpy.context.view_layer.objects.active,
        bpy.context.mode,
    )


def _restore_context(snapshot):
    selected, active, mode = snapshot
    if bpy.context.mode != "OBJECT":
        try:
            bpy.ops.object.mode_set(mode="OBJECT")
        except RuntimeError:
            pass
    for obj in tuple(bpy.context.selected_objects):
        obj.select_set(False)
    for obj in selected:
        if obj.name in bpy.data.objects:
            obj.select_set(True)
    if active is not None and active.name in bpy.data.objects:
        bpy.context.view_layer.objects.active = active
    target_mode = "EDIT" if str(mode).startswith("EDIT") else mode
    if target_mode != "OBJECT":
        try:
            bpy.ops.object.mode_set(mode=target_mode)
        except RuntimeError:
            pass


def _datablock_identity(value):
    try:
        return int(value.as_pointer())
    except (AttributeError, ReferenceError):
        return id(value)


def _snapshot_datablocks():
    return {
        name: frozenset(
            _datablock_identity(value)
            for value in getattr(bpy.data, name)
        )
        for name in _TRACKED_DATABLOCKS
        if hasattr(bpy.data, name)
    }


def _new_datablocks(snapshot, name):
    values = getattr(bpy.data, name, ())
    previous = snapshot.get(name, frozenset())
    return tuple(
        value
        for value in values
        if _datablock_identity(value) not in previous
    )


def _remove_datablock(collection, value):
    try:
        collection.remove(value, do_unlink=True)
    except TypeError:
        collection.remove(value)


def _rollback_import(snapshot):
    for name in _TRACKED_DATABLOCKS:
        collection = getattr(bpy.data, name, None)
        if collection is None:
            continue
        for value in reversed(_new_datablocks(snapshot, name)):
            try:
                _remove_datablock(collection, value)
            except (ReferenceError, RuntimeError, TypeError, ValueError):
                pass


def _nearest_valid_parent(obj, imported_object_ids):
    parent = obj.parent
    while parent is not None:
        if (
            _datablock_identity(parent) in imported_object_ids
            and parent.type in _VALID_OBJECT_TYPES
        ):
            return parent
        parent = parent.parent
    return None


def _remove_unsupported_objects(imported_objects):
    survivors = []
    for obj in tuple(imported_objects):
        if obj.type in _VALID_OBJECT_TYPES or obj.type == "EMPTY":
            survivors.append(obj)
            continue
        object_type = obj.type
        data = obj.data
        bpy.data.objects.remove(obj, do_unlink=True)
        if data is not None and data.users == 0:
            collection_name = {
                "CAMERA": "cameras",
                "LIGHT": "lights",
            }.get(object_type)
            collection = getattr(bpy.data, collection_name, None) if collection_name else None
            if collection is not None:
                _remove_datablock(collection, data)
    return tuple(survivors)


def _hierarchy_depth(obj):
    depth = 0
    parent = obj.parent
    while parent is not None:
        depth += 1
        parent = parent.parent
    return depth


def _normalize_object_transforms(objects):
    for obj in sorted(objects, key=_hierarchy_depth):
        matrix = obj.matrix_basis.copy()
        if getattr(matrix, "is_identity", False):
            continue
        data = obj.data
        if data is None or not hasattr(data, "transform"):
            raise ExternalGLBImportError(
                f"Cannot normalize transforms for imported {obj.type.lower()} {obj.name!r}."
            )
        if data.users > 1:
            obj.data = data.copy()
            data = obj.data
        data.transform(matrix)
        for child in tuple(obj.children):
            child.matrix_local = matrix @ child.matrix_local
        obj.matrix_basis.identity()
        if hasattr(data, "update"):
            data.update()


def _flatten_imported_hierarchy(imported_objects):
    imported_ids = frozenset(
        _datablock_identity(obj) for obj in imported_objects
    )
    valid_objects = tuple(
        obj for obj in imported_objects if obj.type in _VALID_OBJECT_TYPES
    )
    for obj in valid_objects:
        parent = _nearest_valid_parent(obj, imported_ids)
        if parent is obj.parent:
            continue
        world = obj.matrix_world.copy()
        obj.parent = parent
        obj.parent_type = "OBJECT"
        obj.matrix_world = world

    removed = 0
    empties = sorted(
        (obj for obj in imported_objects if obj.type == "EMPTY"),
        key=_hierarchy_depth,
        reverse=True,
    )
    for empty in empties:
        if empty.children:
            continue
        bpy.data.objects.remove(empty, do_unlink=True)
        removed += 1
    return valid_objects, removed


def _rename_imported_objects(objects):
    meshes = sorted(
        (obj for obj in objects if obj.type == "MESH"),
        key=lambda obj: obj.name.casefold(),
    )
    armatures = sorted(
        (obj for obj in objects if obj.type == "ARMATURE"),
        key=lambda obj: obj.name.casefold(),
    )
    for index, obj in enumerate(meshes):
        obj["cp77_external_original_name"] = obj.name
        obj.name = f"submesh_{index:02d}_LOD_1"
        if obj.data is not None and obj.data.users == 1:
            obj.data.name = obj.name
    for index, obj in enumerate(armatures):
        obj["cp77_external_original_name"] = obj.name
        obj.name = "Armature" if index == 0 else f"Armature_{index:02d}"
        if obj.data is not None and obj.data.users == 1:
            obj.data.name = obj.name


def _mark_imported_data(objects, collections, actions, inspection):
    for owner in (*objects, *collections, *actions):
        mark_origin(
            owner,
            ORIGIN_EXTERNAL,
            generator=inspection.generator,
            source_path=inspection.filepath,
        )


def _select_imported(objects):
    for obj in tuple(bpy.context.selected_objects):
        obj.select_set(False)
    for obj in objects:
        obj.select_set(True)
    if objects:
        bpy.context.view_layer.objects.active = objects[0]


def import_external_glb(filepath: str, inspection: GLBInspection) -> ExternalImportSummary:
    path = os.path.abspath(os.fspath(filepath))
    if inspection.claims_cp77_origin:
        raise ExternalGLBImportError(
            "The external import path cannot import WolvenKit or direct-export GLBs."
        )
    if inspection.content_kind is GLBContentKind.EMPTY:
        raise ExternalGLBImportError("The external GLB contains no mesh or animation payload.")
    if os.path.normcase(os.path.abspath(inspection.filepath)) != os.path.normcase(path):
        raise ExternalGLBImportError(
            "The GLB inspection does not belong to the requested import file."
        )
    snapshot = _snapshot_datablocks()
    context_snapshot = _context_snapshot()
    try:
        if bpy.context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        if not bpy.ops.import_scene.gltf.poll():
            raise ExternalGLBImportError(
                "Blender's glTF importer is unavailable in the current context."
            )
        result = bpy.ops.import_scene.gltf(filepath=path)
        if "FINISHED" not in result:
            raise ExternalGLBImportError("Blender's glTF importer did not finish successfully.")

        imported_objects = _new_datablocks(snapshot, "objects")
        imported_collections = _new_datablocks(snapshot, "collections")
        imported_actions = _new_datablocks(snapshot, "actions")
        imported_objects = _remove_unsupported_objects(imported_objects)
        valid_objects, removed_empty_count = _flatten_imported_hierarchy(
            imported_objects
        )
        if not valid_objects and not imported_actions:
            raise ExternalGLBImportError(
                "The external GLB did not create mesh, armature, or action data."
            )

        if valid_objects:
            _normalize_object_transforms(valid_objects)
            _rename_imported_objects(valid_objects)
            _select_imported(valid_objects)
        else:
            # Animation-only external imports do not need Blender's temporary
            # node/empty hierarchy after their actions have been created.
            for obj in tuple(_new_datablocks(snapshot, "objects")):
                try:
                    bpy.data.objects.remove(obj, do_unlink=True)
                except (ReferenceError, RuntimeError, TypeError, ValueError):
                    pass
            for collection in tuple(imported_collections):
                try:
                    _remove_datablock(bpy.data.collections, collection)
                except (ReferenceError, RuntimeError, TypeError, ValueError):
                    pass
            imported_collections = ()
            _restore_context(context_snapshot)

        _mark_imported_data(
            valid_objects,
            imported_collections,
            imported_actions,
            inspection,
        )
        return ExternalImportSummary(
            filepath=path,
            generator=inspection.generator,
            object_count=len(valid_objects),
            mesh_count=sum(obj.type == "MESH" for obj in valid_objects),
            armature_count=sum(obj.type == "ARMATURE" for obj in valid_objects),
            action_count=len(imported_actions),
            removed_empty_count=removed_empty_count,
        )
    except Exception as error:
        _rollback_import(snapshot)
        _restore_context(context_snapshot)
        if isinstance(error, ExternalGLBImportError):
            raise
        raise ExternalGLBImportError(f"External GLB import failed: {error}") from error
