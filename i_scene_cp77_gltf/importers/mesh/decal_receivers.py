from __future__ import annotations

import weakref

import bpy
import numpy as np

from ...assetio.values import json_array
from ...blender.decal_receivers import (
    DECAL_SLOT_ATTRIBUTE,
    RECEIVER_ATTRIBUTE,
    bind_decal_receivers,
    ensure_receiver_preview,
    face_values,
    receiver_uv_layers,
    remove_receiver_preview,
    set_preview_slots,
    write_face_values,
)
from ...blender.transactions import current_import_transaction
from ...core.log import get_logger
from ...gltf.submesh import submesh_index_for_object
from ...material_types.decal_composite import (
    DECAL_UV_LAYER,
    PROJECTOR_BITANGENT_ATTRIBUTE,
    PROJECTOR_TANGENT_ATTRIBUTE,
    PROJECTOR_UP_ATTRIBUTE,
    composite_material,
    decal_surface_material,
)
from ...material_types.vehicle_decal_dirt import prepare_vehicle_dirt_mesh

_LOG = get_logger(__name__)
_FORWARD_FEATURES = frozenset({"emissive", "emissive_subsurface"})
_FRAME_ATTRIBUTES = (
    PROJECTOR_TANGENT_ATTRIBUTE,
    PROJECTOR_BITANGENT_ATTRIBUTE,
    PROJECTOR_UP_ATTRIBUTE,
)


def _decal_features(material):
    return set(json_array(material.get("cp77_decal_features")))


def is_deferred_mesh_decal(material):
    """A mesh decal material that writes into the surface beneath it (not a forward or emissive decal)"""
    return (
        material is not None
        and material.get("cp77_decal_family") == "mesh"
        and not (_decal_features(material) & _FORWARD_FEATURES)
    )


def _decal_material(obj):
    materials = [
        slot.material for slot in obj.material_slots if slot.material is not None
    ]
    return (
        materials[0]
        if materials and all(is_deferred_mesh_decal(material) for material in materials)
        else None
    )


def _receiver_material(obj):
    material = obj.material_slots[0].material if obj.material_slots else None
    return (
        material
        if material is not None and material.get("cp77_decal_family") is None
        else None
    )


def bind_mesh_decals(objects):
    """Bind the deferred mesh decals among objects to the submeshes they sit on"""
    meshes = [obj for obj in objects if getattr(obj, "type", "") == "MESH"]
    decals = [obj for obj in meshes if _decal_material(obj) is not None]
    receivers = [obj for obj in meshes if _receiver_material(obj) is not None]
    if not decals or not receivers:
        return 0
    receiver_ids = [submesh_index_for_object(obj, -1) for obj in receivers]
    bound, surfaces = [], {}
    for decal in decals:
        prepare_vehicle_dirt_mesh(
            decal, [slot.material for slot in decal.material_slots]
        )
        try:
            binding = bind_decal_receivers(
                decal, receivers, frame_attributes=_FRAME_ATTRIBUTES, surfaces=surfaces
            )
        except (RuntimeError, ValueError) as error:
            _LOG.warning(
                "Mesh decal %s could not be bound to its receivers: %s",
                decal.name,
                error,
                exc_info=True,
            )
            continue
        if binding is None or not np.any(binding.face_receivers >= 0):
            continue
        faces = [
            receiver_ids[index] if index >= 0 else -1
            for index in binding.face_receivers
        ]
        write_face_values(decal.data, RECEIVER_ATTRIBUTE, faces)
        bound.append(decal.data)
    if bound:
        transaction = current_import_transaction()
        if transaction is None:
            refresh_mesh_decal_materials(bound)
        else:
            _defer_refresh(transaction, bound)
    return len(bound)


# Meshes bound during an import, refreshed together by one finalizer so composites are shared across the import. Keyed
# weakly: a rolled-back transaction drops its finalizer, and its pending meshes go with it.
_PENDING_REFRESH = weakref.WeakKeyDictionary()


def _defer_refresh(transaction, meshes):
    pending = _PENDING_REFRESH.get(transaction)
    if pending is None:
        pending = _PENDING_REFRESH[transaction] = []
        transaction.defer_finalizer(
            lambda: refresh_mesh_decal_materials(
                _PENDING_REFRESH.pop(transaction, pending)
            )
        )
    pending.extend(meshes)


def _object_collections():
    """Every object's collections, gathered in one pass (Object.users_collection scans all collections)"""
    owners = {}
    for collection in (
        *bpy.data.collections,
        *(scene.collection for scene in bpy.data.scenes),
    ):
        for obj in collection.objects:
            owners.setdefault(obj.as_pointer(), []).append(collection)
    return owners


class _ReceiverSiblings:
    """The receiving submeshes of each collection by source mesh and submesh index"""

    def __init__(self):
        self._collections = {}

    def _receivers(self, collection):
        key = collection.as_pointer()
        receivers = self._collections.get(key)
        if receivers is None:
            receivers = self._collections[key] = {}
            for other in collection.objects:
                if other.type != "MESH":
                    continue
                material = _receiver_material(other)
                index = submesh_index_for_object(other, -1)
                if material is not None and index >= 0:
                    receivers.setdefault(other.get("sourcePath"), {}).setdefault(
                        index, material
                    )
        return receivers

    def find(self, obj, collections):
        """The receiving submeshes beside obj, by submesh index"""
        source = obj.get("sourcePath")
        siblings = {}
        for collection in collections:
            for index, material in self._receivers(collection).get(source, {}).items():
                siblings.setdefault(index, material)
        return siblings


def refresh_mesh_decal_materials(meshes, cache=None):
    """Build the receiver composites of every object that uses one of the bound decal meshes"""
    keys = set()
    for mesh in meshes:
        try:
            keys.add(mesh.as_pointer())
        except ReferenceError:
            continue
    if not keys:
        return 0
    cache = {} if cache is None else cache
    owners = _object_collections()
    sibling_receivers = _ReceiverSiblings()
    refreshed = 0
    for obj in bpy.data.objects:
        mesh = obj.data
        if obj.type != "MESH" or mesh.as_pointer() not in keys:
            continue
        material = _decal_material(obj)
        faces = face_values(mesh, RECEIVER_ATTRIBUTE)
        if material is None or faces is None:
            remove_receiver_preview(obj)
            continue
        # The slot layout depends only on the bound receivers, so every object sharing the mesh agrees on it.
        receivers = sorted(int(index) for index in set(faces.tolist()) if index >= 0)
        siblings = sibling_receivers.find(obj, owners.get(obj.as_pointer(), ()))
        if not any(index in siblings for index in receivers):
            remove_receiver_preview(obj)
            continue
        surface = decal_surface_material(material, cache)
        composites = []
        for index in receivers:
            receiver = siblings.get(index)
            composite = None
            if receiver is not None:
                try:
                    composite = composite_material(receiver, material, cache)
                except (RuntimeError, ValueError, KeyError) as error:
                    _LOG.warning(
                        "Mesh decal %s has no composite over %s: %s",
                        obj.name,
                        receiver.name,
                        error,
                        exc_info=True,
                    )
            composites.append(composite or surface)
        slot_of = {index: slot for slot, index in enumerate(receivers, start=1)}
        surface_slot = len(receivers) + 1
        write_face_values(
            mesh,
            DECAL_SLOT_ATTRIBUTE,
            [slot_of.get(int(index), surface_slot) for index in faces],
        )
        set_preview_slots(obj, [*composites, surface])
        ensure_receiver_preview(obj, receiver_uv_layers(mesh), DECAL_UV_LAYER)
        refreshed += 1
    return refreshed
