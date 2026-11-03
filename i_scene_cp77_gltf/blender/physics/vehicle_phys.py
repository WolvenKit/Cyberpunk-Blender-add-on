from __future__ import annotations

import os

import bpy

from ...assetio.documents import DocumentSession
from ...assetio.index import IndexPolicy, build_asset_index
from ...assetio.paths import normalize_local_path, split_source_raw_root
from ...physics.domain.resource_paths import phys_resource_matches
from ...physics.domain.vehicle.game_data import entity_vehicle_data
from ..collections import collection_parent_map
from ..red_transforms import transform_matrix
from .resources import import_phys
from .vehicle_chassis import VEHICLE_CHASSIS_SOURCE_KIND, vehicle_chassis_phys_objects
from .vehicle_geometry import entity_collection_for_object, object_targets_rig


def _entity_collection_for_rig(rig):
    parent_map = collection_parent_map()
    for obj in bpy.data.objects:
        if obj.type == "MESH" and object_targets_rig(obj, rig):
            collection = entity_collection_for_object(obj, parent_map)
            if collection is not None:
                return collection
    return None


def _matching_loaded_actors(context, depot_path, local_path, collection=None):
    expected = tuple(value for value in (local_path, depot_path) if value)
    allowed = (
        {obj.as_pointer() for obj in collection.all_objects}
        if collection is not None
        else None
    )
    matches = []
    for actor in context.scene.physx.actors:
        obj = actor.obj_ref
        if obj is None or (allowed is not None and obj.as_pointer() not in allowed):
            continue
        source = str(getattr(obj.physx, "source_phys_resource_path", "") or "")
        if source and any(phys_resource_matches(source, value) for value in expected):
            matches.append(obj)
    return matches


def _adopt_vehicle_phys_actors(rig, actors):
    if rig is None:
        return ()
    adopted = []
    for obj in actors:
        if obj is None:
            continue
        world = obj.matrix_world.copy()
        for constraint in tuple(obj.constraints):
            if constraint.type == "CHILD_OF" and constraint.target == rig:
                obj.constraints.remove(constraint)
        obj.physx.source_kind = VEHICLE_CHASSIS_SOURCE_KIND
        obj["cp77_vehicle_chassis_rig"] = rig.name
        if obj.parent != rig:
            obj.parent = rig
            obj.matrix_parent_inverse = rig.matrix_world.inverted_safe()
        obj.matrix_world = world
        adopted.append(obj)
    return tuple(adopted)


def adopt_vehicle_phys_objects(rig, actors):
    return _adopt_vehicle_phys_actors(rig, tuple(actors or ()))


def adopt_loaded_vehicle_phys(context, rig):
    if rig is None or rig.type != "ARMATURE":
        return ()
    existing = vehicle_chassis_phys_objects(context.scene, rig)
    if existing:
        return existing
    collection = _entity_collection_for_rig(rig)
    if collection is None:
        return ()
    entity_source = str(collection.get("cp77_entity_source", "") or "")
    if not entity_source or not os.path.isfile(entity_source):
        return ()
    with DocumentSession() as documents:
        data = entity_vehicle_data(
            documents.payload(entity_source),
            str(collection.get("depotPath", "") or ""),
        )
    if not data.chassis_collision_path:
        return ()
    loaded = _matching_loaded_actors(
        context, data.chassis_collision_path, "", collection
    )
    return _adopt_vehicle_phys_actors(rig, loaded)


def vehicle_phys_preflight(context, rig):
    if rig is None or rig.type != "ARMATURE":
        return None
    collection = _entity_collection_for_rig(rig)
    if collection is None:
        return None
    entity_source = str(collection.get("cp77_entity_source", "") or "")
    if not entity_source or not os.path.isfile(entity_source):
        return None
    with DocumentSession() as documents:
        data = entity_vehicle_data(
            documents.payload(entity_source), str(collection.get("depotPath", "") or "")
        )
    if not data.chassis_collision_path:
        return None
    vehicle = context.scene.physx_vehicle
    source_root, _relative = split_source_raw_root(entity_source)
    root = normalize_local_path(vehicle.vehicle_resource_root or source_root)
    local_path = ""
    if root and os.path.isdir(root):
        index = build_asset_index(root, (".phys.json",), policy=IndexPolicy.REUSE)
        local_path = (
            index.resolve_expected(data.chassis_collision_path, ".phys.json") or ""
        )
    loaded = _matching_loaded_actors(
        context, data.chassis_collision_path, local_path, collection
    )
    if loaded:
        _adopt_vehicle_phys_actors(rig, loaded)
        return None
    return {
        "depot_path": data.chassis_collision_path,
        "local_path": local_path,
        "collection": collection,
        "entity_source": entity_source,
        "chassis_local_transform": data.chassis_local_transform,
    }


def load_vehicle_phys(context, rig, filepath, target_collection=None):
    before = {
        item.obj_ref.as_pointer()
        for item in context.scene.physx.actors
        if item.obj_ref is not None
    }
    actor_matrix = None
    collection = _entity_collection_for_rig(rig) if rig is not None else None
    entity_source = (
        str(collection.get("cp77_entity_source", "") or "") if collection else ""
    )
    if entity_source and os.path.isfile(entity_source):
        with DocumentSession() as documents:
            data = entity_vehicle_data(
                documents.payload(entity_source),
                str(collection.get("depotPath", "") or ""),
            )
        component_matrix = transform_matrix(data.chassis_local_transform)
        rig_component_matrix = transform_matrix(data.vehicle_rig_local_transform)
        entity_world = (
            rig.matrix_world @ rig_component_matrix.inverted_safe()
            if rig is not None
            else None
        )
        actor_matrix = (
            entity_world @ component_matrix
            if entity_world is not None
            else component_matrix
        )
        if target_collection is None:
            target_collection = collection
    actor_count, shape_count = import_phys(
        filepath,
        rig=rig,
        target_collection=target_collection,
        actor_matrix=actor_matrix,
        context=context,
    )
    if not actor_count or not shape_count:
        raise ValueError("The chassis .phys did not contain supported actors")
    created = [
        item.obj_ref
        for item in context.scene.physx.actors
        if item.obj_ref is not None and item.obj_ref.as_pointer() not in before
    ]
    _adopt_vehicle_phys_actors(rig, created)
    return actor_count, shape_count
