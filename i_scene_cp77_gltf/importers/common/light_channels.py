from __future__ import annotations

import json
import time

import bpy
from mathutils import Matrix, Vector
from mathutils.geometry import intersect_ray_tri

from ...assetio.paths import depot_path_key
from ...assetio.values import json_array
from ...bartmoss.clipping import bounds_intersect
from ...bartmoss.geometry import aabb_sample_points, point_in_aabb, sphere_aabb
from ...blender.naming import fit_id_name
from ...blender.transactions import track_created_datablock
from ...core.log import debug_exception, get_logger, log_once
from .light_channel_semantics import (
    LC_CHANNEL_WORLD,
    LC_CHARACTER,
    LC_PLAYER,
    assign_runtime_volume_channels,
    canonical_channel_names,
    decode_light_channel,
    effective_component_light_channel,
    mapped_light_channel,
)

_LOG = get_logger(__name__)

_RENDERABLE_TYPES = frozenset(
    {
        "MESH",
        "CURVE",
        "SURFACE",
        "FONT",
        "VOLUME",
        "POINTCLOUD",
        "CURVES",
    }
)


def _scope_objects(scope_collection, objects=None):
    if objects is not None:
        unique = {}
        for obj in objects:
            if obj is not None:
                unique[obj.as_pointer()] = obj
        return tuple(unique.values())
    try:
        return tuple(scope_collection.all_objects)
    except (AttributeError, ReferenceError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_scope_objects", type(error).__name__),
            "scope objects: fell back after %s",
            error,
            exc_info=True,
        )
        return ()


def _world_bounds(obj):
    try:
        corners = tuple(obj.bound_box)
    except (AttributeError, ReferenceError, TypeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_world_bounds", type(error).__name__),
            "world bounds: fell back after %s",
            error,
            exc_info=True,
        )
        corners = ()
    if not corners:
        point = obj.matrix_world.translation
        coords = tuple(float(point[axis]) for axis in range(3))
        return coords, coords
    matrix_world = obj.matrix_world
    world = [matrix_world @ Vector(corner) for corner in corners]
    return (
        tuple(min(float(point[axis]) for point in world) for axis in range(3)),
        tuple(max(float(point[axis]) for point in world) for axis in range(3)),
    )


def _mesh_volume_data(obj):
    mesh = getattr(obj, "data", None)
    if mesh is None or not hasattr(mesh, "calc_loop_triangles"):
        return None
    try:
        mesh.calc_loop_triangles()
        vertices = tuple(Vector(vertex.co) for vertex in mesh.vertices)
        triangles = tuple(
            (
                vertices[triangle.vertices[0]],
                vertices[triangle.vertices[1]],
                vertices[triangle.vertices[2]],
            )
            for triangle in mesh.loop_triangles
        )
        if not triangles:
            return None
        local_corners = tuple(obj.bound_box)
        local_bounds = (
            tuple(
                min(float(corner[axis]) for corner in local_corners)
                for axis in range(3)
            ),
            tuple(
                max(float(corner[axis]) for corner in local_corners)
                for axis in range(3)
            ),
        )
        return {
            "inverse": obj.matrix_world.inverted_safe(),
            "triangles": triangles,
            "local_bounds": local_bounds,
        }
    except (
        AttributeError,
        ReferenceError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_mesh_volume_data", type(error).__name__),
            "mesh volume data: fell back after %s",
            error,
            exc_info=True,
        )
        return None


def _volume_contains_point(record, world_point):
    geometry = record.get("geometry")
    if geometry is None:
        return point_in_aabb(world_point, record["bounds"])
    local_point = geometry["inverse"] @ Vector(world_point)
    if not point_in_aabb(local_point, geometry["local_bounds"]):
        return False
    direction = Vector((0.873421, 0.421337, 0.253129)).normalized()
    distances = []
    for triangle in geometry["triangles"]:
        hit = intersect_ray_tri(
            triangle[0],
            triangle[1],
            triangle[2],
            direction,
            local_point,
            True,
        )
        if hit is None:
            continue
        distance = float((hit - local_point).dot(direction))
        if distance > 1.0e-6:
            distances.append(distance)
    if not distances:
        return False
    distances.sort()
    unique_hits = 1
    previous = distances[0]
    for distance in distances[1:]:
        if abs(distance - previous) <= 1.0e-5:
            continue
        unique_hits += 1
        previous = distance
    return bool(unique_hits & 1)


def _receiver_mask(bounds, records, class_mask):
    samples = aabb_sample_points(bounds)
    best_score = 0
    spatial_masks = []
    for record in records:
        if not bounds_intersect(bounds, record["bounds"], 0.0):
            continue
        spatial_mask = int(record["effective_mask"]) & 0xFF
        if not spatial_mask:
            continue
        score = sum(_volume_contains_point(record, point) for point in samples)
        if score <= 0:
            continue
        if score > best_score:
            best_score = score
            spatial_masks = [spatial_mask]
        elif score == best_score:
            spatial_masks.append(spatial_mask)

    spatial = 0
    for spatial_mask in spatial_masks:
        spatial |= spatial_mask
    mask = spatial | (int(class_mask) & (LC_CHARACTER | LC_PLAYER))
    if best_score != len(samples):
        mask |= LC_CHANNEL_WORLD
    return mask & 0xFFFF


def is_light_channel_volume(obj):
    if obj is None or getattr(obj, "type", None) != "MESH":
        return False
    if bool(obj.get("cp77_light_channel_volume", False)):
        return True
    ntype = str(obj.get("cp77_type", "") or obj.get("cp77_node_type", ""))
    return ntype in {
        "entLightChannelComponent",
        "worldLightChannelVolumeNode",
        "worldLightChannelShapeNode",
    }


def _is_receiver(obj):
    if obj is None or is_light_channel_volume(obj):
        return False
    obj_type = str(getattr(obj, "type", ""))
    if obj_type in _RENDERABLE_TYPES:
        return True
    return obj_type == "EMPTY" and getattr(obj, "instance_collection", None) is not None


def _is_source_light(obj):
    return (
        obj is not None
        and getattr(obj, "type", None) == "LIGHT"
        and not bool(obj.get("cp77_light_proxy", False))
        and ("lightChannel" in obj or "cp77_light_channel_mask" in obj)
    )


def _component_volume(obj):
    return str(obj.get("cp77_type", "")) == "entLightChannelComponent"


def _component_light(obj):
    return str(obj.get("cp77_type", "")) in {
        "entLightComponent",
        "vehicleLightComponent",
    }


def _receiver_class_mask(scope_collection, obj):
    explicit = obj.get("cp77_light_receiver_class_mask")
    if isinstance(explicit, (int, float)):
        return int(explicit) & (LC_CHARACTER | LC_PLAYER)

    scope_explicit = scope_collection.get("cp77_light_receiver_class_mask")
    if isinstance(scope_explicit, (int, float)):
        return int(scope_explicit) & (LC_CHARACTER | LC_PLAYER)

    path = depot_path_key(scope_collection.get("depotPath", ""))
    mask = 0
    if "/characters/" in f"/{path}/":
        mask |= LC_CHARACTER
        tail = path.rsplit("/", 1)[-1]
        if "/player/" in f"/{path}/" or tail.startswith("player"):
            mask |= LC_PLAYER
    return mask


def _volume_records(volumes, stored=()):
    records = list(stored)
    for obj in volumes:
        authored, unknown = decode_light_channel(
            obj.get("lightChannels", obj.get("channels", 0))
        )
        geometry = _mesh_volume_data(obj)
        record = {
            "object": obj,
            "authored_mask": authored,
            "component": _component_volume(obj),
            "bounds": _world_bounds(obj),
            "geometry": geometry,
            "unknown": unknown,
        }
        records.append(record)

    effective = assign_runtime_volume_channels(records)
    for record, runtime_mask in zip(records, effective):
        record["effective_mask"] = runtime_mask
    return records


_RECORDS_PROPERTY = "cp77_light_channel_records"
# The rigs bound records follow, by key: an ID pointer follows a rename and reads None once the rig is deleted.
_RIGS_PROPERTY = "cp77_light_channel_rigs"


def _vectors(values):
    return [[float(value) for value in vector] for vector in values]


def _own_node(obj):
    node_index = obj.get("nodeIndex")
    if not isinstance(node_index, (int, float)):
        return None
    return str(obj.get("cp77_sector_name", "") or ""), int(node_index)


def _bone_binding(obj):
    """The armature and pose bone a volume follows through an active Child Of constraint, or None"""
    for constraint in getattr(obj, "constraints", ()):
        if (
            constraint.type != "CHILD_OF"
            or constraint.mute
            or constraint.influence <= 0.0
        ):
            continue
        target = constraint.target
        if target is None or target.type != "ARMATURE" or not constraint.subtarget:
            continue
        pose_bone = target.pose.bones.get(constraint.subtarget)
        if pose_bone is not None:
            return target, pose_bone
    return None


def _stored_record(obj, node, binding, rig_key):
    authored, unknown = decode_light_channel(
        obj.get("lightChannels", obj.get("channels", 0))
    )
    geometry = _mesh_volume_data(obj)
    record = {
        "sector_name": node[0] if node else "",
        "node_index": node[1] if node else None,
        "authored_mask": int(authored),
        "unknown": list(unknown),
        "component": _component_volume(obj),
        "enabled": bool(obj.get("cp77_component_enabled", True)),
        "bounds": _vectors(_world_bounds(obj)),
        "matrix": _vectors(obj.matrix_world),
        "triangles": None
        if geometry is None
        else [_vectors(triangle) for triangle in geometry["triangles"]],
        "local_bounds": None
        if geometry is None
        else _vectors(geometry["local_bounds"]),
    }
    if binding is not None:
        armature, pose_bone = binding
        # Where the volume sits relative to its bone, so a later relink can place it from the bone's current pose.
        bone_world = armature.matrix_world @ pose_bone.matrix
        record.update(
            rig=rig_key,
            bone=pose_bone.name,
            bone_matrix=_vectors(bone_world.inverted_safe() @ obj.matrix_world),
        )
    return record


def _read_records(collection):
    try:
        encoded = collection.get(_RECORDS_PROPERTY)
    except (AttributeError, ReferenceError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_read_records", type(error).__name__),
            "read records: fell back after %s",
            error,
            exc_info=True,
        )
        return []
    if not isinstance(encoded, str):
        return []
    return [record for record in json_array(encoded) if isinstance(record, dict)]


def _read_rigs(collection):
    try:
        rigs = collection.get(_RIGS_PROPERTY)
    except (AttributeError, ReferenceError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_read_rigs", type(error).__name__),
            "read rigs: fell back after %s",
            error,
            exc_info=True,
        )
        return {}
    return (
        {str(key): rigs[key] for key in rigs.keys()}
        if rigs is not None and hasattr(rigs, "keys")
        else {}
    )


def _write_records(collection, records, rigs):
    """Store records on collection with the rigs they still refer to"""
    collection[_RECORDS_PROPERTY] = json.dumps(records, separators=(",", ":"))
    referenced = {record.get("rig") for record in records}
    kept = {
        key: rig for key, rig in rigs.items() if key in referenced and rig is not None
    }
    if kept:
        collection[_RIGS_PROPERTY] = kept
    elif _RIGS_PROPERTY in collection:
        del collection[_RIGS_PROPERTY]


def _rig_key(rigs, armature):
    for key, rig in rigs.items():
        if rig is not None and rig == armature:
            return key
    key = str(max((int(key) for key in rigs if key.isdigit()), default=-1) + 1)
    rigs[key] = armature
    return key


def _node_key(record):
    node_index = record.get("node_index")
    return None if node_index is None else (record.get("sector_name", ""), node_index)


def retire_light_channel_volumes(owner_collection, volumes, *, node_of=None):
    """Keep each channel volume as a record on owner_collection and remove the volume objects"""
    volumes = tuple(
        {
            obj.as_pointer(): obj for obj in volumes if is_light_channel_volume(obj)
        }.values()
    )
    if not volumes:
        return 0
    node_of = node_of or _own_node
    rigs = _read_rigs(owner_collection)
    retiring = []
    for obj in volumes:
        binding = _bone_binding(obj)
        rig_key = _rig_key(rigs, binding[0]) if binding is not None else None
        retiring.append(_stored_record(obj, node_of(obj), binding, rig_key))
    replaced = {_node_key(record) for record in retiring} - {None}
    records = [
        record
        for record in _read_records(owner_collection)
        if _node_key(record) not in replaced
    ]
    records.extend(retiring)
    _write_records(owner_collection, records, rigs)
    # One batch per type: removing IDs one at a time scans the whole file each time.
    meshes = {
        obj.data.as_pointer(): obj.data for obj in volumes if obj.data is not None
    }
    bpy.data.batch_remove(volumes)
    unused = [mesh for mesh in meshes.values() if mesh.users == 0]
    if unused:
        bpy.data.batch_remove(unused)
    return len(volumes)


def clear_light_channel_records(collection, *, keep_components=False):
    """Drop the collection's records"""
    if _RECORDS_PROPERTY not in collection:
        return
    kept = (
        [record for record in _read_records(collection) if record.get("component")]
        if keep_components
        else []
    )
    if kept:
        _write_records(collection, kept, _read_rigs(collection))
    else:
        del collection[_RECORDS_PROPERTY]
        if _RIGS_PROPERTY in collection:
            del collection[_RIGS_PROPERTY]


def _record_placement(stored, rigs):
    """Where a stored volume is now, or None"""
    rig_key = stored.get("rig")
    if rig_key is None:
        return None
    armature = rigs.get(str(rig_key))
    if armature is None or armature.type != "ARMATURE":
        return None
    pose_bone = armature.pose.bones.get(str(stored.get("bone") or ""))
    if pose_bone is None:
        return None
    try:
        return armature.matrix_world @ pose_bone.matrix @ Matrix(stored["bone_matrix"])
    except (KeyError, TypeError, ValueError):
        debug_exception(
            _LOG,
            "Stored light channel volume on bone %s has no usable bone matrix",
            pose_bone.name,
        )
        return None


def _placed_bounds(matrix, local_bounds):
    corners = [
        matrix @ Vector((x, y, z))
        for x in (local_bounds[0][0], local_bounds[1][0])
        for y in (local_bounds[0][1], local_bounds[1][1])
        for z in (local_bounds[0][2], local_bounds[1][2])
    ]
    return (
        tuple(min(float(corner[axis]) for corner in corners) for axis in range(3)),
        tuple(max(float(corner[axis]) for corner in corners) for axis in range(3)),
    )


def stored_light_channel_records(collections):
    """The retired volumes of collections as volume records with no object"""
    records = []
    for collection in collections:
        rigs = _read_rigs(collection)
        for index, stored in enumerate(_read_records(collection)):
            try:
                bounds = tuple(
                    tuple(float(value) for value in corner)
                    for corner in stored["bounds"]
                )
                placement = _record_placement(stored, rigs)
                geometry = None
                if stored.get("triangles"):
                    local_bounds = tuple(
                        tuple(float(value) for value in corner)
                        for corner in stored["local_bounds"]
                    )
                    if placement is not None:
                        bounds = _placed_bounds(placement, local_bounds)
                    geometry = {
                        "inverse": (
                            placement or Matrix(stored["matrix"])
                        ).inverted_safe(),
                        "triangles": tuple(
                            tuple(Vector(point) for point in triangle)
                            for triangle in stored["triangles"]
                        ),
                        "local_bounds": local_bounds,
                    }
                records.append(
                    {
                        "object": None,
                        "authored_mask": int(stored["authored_mask"]),
                        "component": bool(stored.get("component", False)),
                        "bounds": bounds,
                        "geometry": geometry,
                        "unknown": tuple(
                            str(token) for token in stored.get("unknown", ())
                        ),
                        "enabled": bool(stored.get("enabled", True)),
                        "sector_name": str(stored.get("sector_name", "") or ""),
                        "node_index": stored.get("node_index"),
                    }
                )
            except (KeyError, TypeError, ValueError):
                debug_exception(
                    _LOG,
                    "Dropped unreadable light channel volume record %d of %s",
                    index,
                    collection.name,
                )
                continue
    return records


def _light_bounds(obj):
    radius = max(
        float(obj.get("cp77_effective_radius", obj.get("radius", 0.0)) or 0.0),
        0.0,
    )
    center = obj.matrix_world.translation
    representation = str(obj.get("cp77_proxy_representation", "") or "")
    capsule_length = max(float(obj.get("capsuleLength", 0.0) or 0.0), 0.0)
    is_capsule = (
        str(obj.get("areaShape", "") or "") == "ALS_Capsule"
        or representation.startswith("CAPSULE_")
    ) and capsule_length > 0.0
    if not is_capsule:
        return sphere_aabb(
            tuple(float(center[axis]) for axis in range(3)),
            radius,
        )

    half = capsule_length * 0.5
    start = obj.matrix_world @ Vector((-half, 0.0, 0.0))
    end = obj.matrix_world @ Vector((half, 0.0, 0.0))
    return (
        tuple(min(float(start[axis]), float(end[axis])) - radius for axis in range(3)),
        tuple(max(float(start[axis]), float(end[axis])) + radius for axis in range(3)),
    )


def _children_of(lights):
    """Each light's children by pointer, gathered in one pass"""
    wanted = {light.as_pointer() for light in lights}
    children = {}
    if wanted:
        for obj in bpy.data.objects:
            parent = obj.parent
            if parent is not None and parent.as_pointer() in wanted:
                children.setdefault(parent.as_pointer(), []).append(obj)
    return children


def _clear_old_link_collections(scope_collection, lights, children):
    encoded = scope_collection.get("cp77_light_link_collections")
    old_names = json_array(encoded) if isinstance(encoded, str) else ()
    old = [
        collection
        for name in old_names
        for collection in (bpy.data.collections.get(str(name)),)
        if collection is not None
        and str(collection.get("cp77_light_link_scope", "")) == scope_collection.name
    ]
    for light in lights:
        linking = getattr(light, "light_linking", None)
        if linking is not None and getattr(linking, "receiver_collection", None) in old:
            linking.receiver_collection = None
        for child in children.get(light.as_pointer(), ()):
            child_linking = getattr(child, "light_linking", None)
            if (
                child_linking is not None
                and getattr(child_linking, "receiver_collection", None) in old
            ):
                child_linking.receiver_collection = None
    for collection in old:
        try:
            bpy.data.collections.remove(collection, do_unlink=True)
        except (ReferenceError, RuntimeError, TypeError):
            debug_exception(
                _LOG,
                "An old light link collection of %s was not removed",
                scope_collection.name,
            )
    scope_collection["cp77_light_link_collections"] = "[]"


def _new_link_collection(scope_collection, mask, receivers, serial):
    names = canonical_channel_names(mask, map_default=True)
    label = "+".join(name.removeprefix("LC_") for name in names)
    name = fit_id_name(f"CP77_LL_{scope_collection.name}", f"_{label}_{serial}")
    collection = track_created_datablock("collections", bpy.data.collections.new(name))
    collection["cp77_light_link_scope"] = scope_collection.name
    collection["cp77_light_channel_mask"] = int(mask)
    for receiver in receivers:
        try:
            collection.objects.link(receiver)
        except (RuntimeError, TypeError, ReferenceError):
            debug_exception(
                _LOG, "A receiver was not linked into light link collection %s", name
            )
    return collection


def _assign_receiver_collection(light, collection, children):
    linking = getattr(light, "light_linking", None)
    if linking is None or not hasattr(linking, "receiver_collection"):
        return False
    linking.receiver_collection = collection
    for child in children.get(light.as_pointer(), ()):
        if not bool(child.get("cp77_light_proxy", False)):
            continue
        child_linking = getattr(child, "light_linking", None)
        if child_linking is not None and hasattr(child_linking, "receiver_collection"):
            child_linking.receiver_collection = collection
    return True


def relink_light(light, scope_collection):
    """Relink a sector light and its capsule samples after its lightChannel changed"""
    effective = mapped_light_channel(
        decode_light_channel(light.get("lightChannel", 0))[0]
    )
    encoded = scope_collection.get("cp77_light_link_collections")
    names = json_array(encoded) if isinstance(encoded, str) else []
    linked = [
        collection
        for collection in (bpy.data.collections.get(str(name)) for name in names)
        if collection is not None
        and collection.get("cp77_light_link_scope") == scope_collection.name
    ]
    target = next(
        (
            collection
            for collection in linked
            if collection.get("cp77_light_channel_mask") == effective
        ),
        None,
    )
    if target is None and effective != LC_CHANNEL_WORLD:
        receivers = [
            obj
            for obj in _scope_objects(scope_collection)
            if int(obj.get("cp77_light_receiver_mask", 0)) & effective
            and _is_receiver(obj)
        ]
        target = _new_link_collection(
            scope_collection, effective, receivers, len(linked) + 1
        )
        scope_collection["cp77_light_link_collections"] = json.dumps(
            [*names, target.name], separators=(",", ":")
        )
    _assign_receiver_collection(light, target, _children_of((light,)))


def rebuild_light_channel_links(
    scope_collection, *, objects=None, record_collections=(), mode="ENTITY"
):
    started = time.perf_counter()
    scoped = _scope_objects(scope_collection, objects)
    volumes = tuple(
        obj
        for obj in scoped
        if is_light_channel_volume(obj)
        and bool(obj.get("cp77_component_enabled", True))
    )
    lights = tuple(
        obj
        for obj in scoped
        if _is_source_light(obj) and bool(obj.get("cp77_component_enabled", True))
    )
    receivers = tuple(
        obj for obj in scoped if _is_receiver(obj) and not bool(obj.hide_render)
    )
    scope_finished = time.perf_counter()
    stored = [
        record
        for record in stored_light_channel_records(record_collections)
        if record["enabled"]
    ]
    records = _volume_records(volumes, stored)
    volumes_finished = time.perf_counter()

    receiver_records = []
    for receiver in receivers:
        class_mask = _receiver_class_mask(scope_collection, receiver)
        if class_mask:
            receiver["cp77_light_receiver_class_mask"] = int(class_mask)
        mask = _receiver_mask(
            _world_bounds(receiver),
            records,
            class_mask,
        )
        receiver_records.append((receiver, mask))
        receiver["cp77_light_receiver_mask"] = int(mask)

    receivers_finished = time.perf_counter()
    children = _children_of(lights)
    _clear_old_link_collections(scope_collection, lights, children)
    clear_finished = time.perf_counter()
    collections = {}
    collection_names = []
    linked = 0
    unresolved = 0
    world_unbounded = 0

    for light in lights:
        authored, _unknown = decode_light_channel(light.get("lightChannel", 0))
        effective = mapped_light_channel(authored)
        source = "AUTHORED"
        if _component_light(light):
            effective, source = effective_component_light_channel(
                authored,
                _light_bounds(light),
                records,
            )

        automated_unresolved = source == "AUTOMATED_UNRESOLVED"
        if automated_unresolved:
            unresolved += 1

        if str(mode).upper() == "ENTITY" and effective & LC_CHANNEL_WORLD:
            world_unbounded += 1
            continue

        if (
            not records
            and effective == LC_CHANNEL_WORLD
            and not (effective & (LC_CHARACTER | LC_PLAYER))
        ):
            world_unbounded += 1
            continue

        effective_key = int(effective)
        # Receiver masks are fixed for this rebuild. Each effective mask therefore
        # determines one ordered receiver set, including an empty set. Cache the
        # collection and its count, avoiding per-light receiver tuple construction.
        cached = collections.get(effective_key)
        if cached is None:
            matching = tuple(
                receiver
                for receiver, receiver_mask in receiver_records
                if receiver_mask & effective_key
            )
            link_collection = _new_link_collection(
                scope_collection,
                effective,
                matching,
                len(collections) + 1,
            )
            receiver_count = len(matching)
            collections[effective_key] = (link_collection, receiver_count)
            collection_names.append(link_collection.name)
        else:
            link_collection, receiver_count = cached

        if _assign_receiver_collection(light, link_collection, children):
            linked += 1
        else:
            unresolved += 1

    assignment_finished = time.perf_counter()
    scope_collection["cp77_light_link_collections"] = json.dumps(
        collection_names, separators=(",", ":")
    )
    finished = time.perf_counter()
    _LOG.debug(
        "Light-channel rebuild timing for %s: total=%.3fs, scope=%.3fs, "
        "volumes=%.3fs, receiver_masks=%.3fs, clear=%.3fs, "
        "assignment=%.3fs, metadata=%.3fs; %d receiver(s), %d light(s), "
        "%d collection(s)",
        scope_collection.name,
        finished - started,
        scope_finished - started,
        volumes_finished - scope_finished,
        receivers_finished - volumes_finished,
        clear_finished - receivers_finished,
        assignment_finished - clear_finished,
        finished - assignment_finished,
        len(receivers),
        len(lights),
        len(collections),
    )
    return {
        "volumes": len(records),
        "receivers": len(receivers),
        "lights": len(lights),
        "linked": linked,
        "unresolved": unresolved,
        "world_unbounded": world_unbounded,
    }
