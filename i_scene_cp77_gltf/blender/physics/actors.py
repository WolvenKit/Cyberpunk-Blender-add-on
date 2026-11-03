import base64
import json

import bpy

from ...assetio.transform_values import quaternion_wxyz_from_wkit, vector3_from_data
from ...assetio.values import cname_value
from ...core.log import debug_exception, get_logger
from ...physics.domain.filters import (
    decode_filter_data,
    filter_ui_signature,
    mask_bool_vector,
    query_ui_mask,
    simulation_filter_state,
    state_for_export,
)
from ...physics.model.collision_layers import COLLISION_PRESETS
from ...physics.model.materials import get_mat_data, resolve_physics_material_name
from ...physics.model.resource import cooked_data_signature
from ..transactions import track_created_datablock
from .bridge_session import require_initialized_bridge

_LOG = get_logger(__name__)


SUPPORTED_COLLIDER_TYPES = frozenset(
    {
        "physicsColliderBox",
        "physicsColliderSphere",
        "physicsColliderCapsule",
        "physicsColliderConvex",
        "physicsColliderMesh",
        "physicsColliderTriangleMesh",
        "physicsColliderHeightfield",
    }
)


def supports_collider_type(collider_type):
    return collider_type in SUPPORTED_COLLIDER_TYPES


def _position_tuple(data, default=(0.0, 0.0, 0.0)):
    if isinstance(data, dict) and isinstance(data.get("position"), dict):
        data = data.get("position")
    return vector3_from_data(data, default)


def _quat_tuple(data, default=(1.0, 0.0, 0.0, 0.0)):
    return (
        quaternion_wxyz_from_wkit(data, default) if isinstance(data, dict) else default
    )


def _collider_local_transform(cdata):
    local_to_body = cdata.get("localToBody", {}) if isinstance(cdata, dict) else {}
    return (
        vector3_from_data(local_to_body.get("position")),
        _quat_tuple(local_to_body.get("orientation")),
    )


def physmat_name(value, default="Default"):
    """The material a shape previews with"""
    name = cname_value(value, default)
    if name is None:
        return default
    name = str(name)
    return default if not name or name.lower() == "none" else name


def _material_token(value):
    """A material CName's text as written, or "" when there is none"""
    name = cname_value(value, None)
    return "" if name is None else str(name)


def _collider_shape_data(cdata):
    if not isinstance(cdata, dict):
        return {}
    ctype = cdata.get("$type")
    if ctype == "physicsColliderBox":
        return cdata.get("halfExtents", {})
    if ctype == "physicsColliderSphere":
        return cdata.get("radius", 0.5)
    if ctype == "physicsColliderCapsule":
        return {
            "radius": cdata.get("radius", 0.5),
            "height": cdata.get("height", 1.0),
        }
    if ctype == "physicsColliderConvex":
        return {
            "vertices": cdata.get("vertices", [])
            or cdata.get("polygonVertices", [])
            or [],
            "compiledGeometryBuffer": cdata.get("compiledGeometryBuffer"),
        }
    if ctype in {"physicsColliderMesh", "physicsColliderTriangleMesh"}:
        return {
            "vertices": cdata.get("vertices", [])
            or cdata.get("polygonVertices", [])
            or [],
            "indices": cdata.get("indexBuffer", []) or [],
            "compiledGeometryBuffer": cdata.get("compiledGeometryBuffer"),
        }
    return cdata


def _compiled_geometry_bytes(value):
    if isinstance(value, dict):
        value = value.get("Bytes") or value.get("bytes")
    return value if isinstance(value, str) and value else ""


def _shape_payload(shape_type, shape_data):
    if isinstance(shape_data, dict) and shape_data.get("$type") == shape_type:
        return _collider_shape_data(shape_data)
    return shape_data


def _shape_material(physmat, shape_data):
    """The material name a shape keeps for export"""
    token = _material_token(physmat)
    if (
        physmat_name(token) == "Default"
        and isinstance(shape_data, dict)
        and shape_data.get("$type")
    ):
        token = _material_token(shape_data.get("material")) or token
    return token or "Default"


def _shape_filter(filter_data, shape_data):
    if filter_data is not None:
        return filter_data
    if isinstance(shape_data, dict) and shape_data.get("$type"):
        return shape_data.get("filterData")
    return None


def _shape_local_transform(shape_data, local_pos, local_rot):
    if local_pos is not None and local_rot is not None:
        return local_pos, local_rot
    if isinstance(shape_data, dict) and shape_data.get("$type"):
        shape_pos, shape_rot = _collider_local_transform(shape_data)
        return (
            local_pos if local_pos is not None else shape_pos,
            local_rot if local_rot is not None else shape_rot,
        )
    return local_pos, local_rot


def _apply_filter_data(shape_item, filter_data):
    if not isinstance(filter_data, dict):
        return
    state = decode_filter_data(filter_data)
    visible_preset = state.preset if state.preset in COLLISION_PRESETS else "None"
    shape_item.collision_preset = visible_preset
    shape_item.filter_group = mask_bool_vector(state.simulation_group)
    shape_item.filter_mask = mask_bool_vector(state.simulation_target)
    shape_item.filter_query = mask_bool_vector(query_ui_mask(state.query_mask))
    shape_item.filter_source_preset = state.preset
    shape_item.filter_source_sim_group = str(state.simulation_group)
    shape_item.filter_source_sim_target = str(state.simulation_target)
    shape_item.filter_source_query_mask = str(state.query_mask)
    shape_item.filter_source_signature = filter_ui_signature(
        visible_preset,
        shape_item.filter_group,
        shape_item.filter_mask,
        shape_item.filter_query,
    )


def register_actor(
    obj,
    actor_type,
    context,
    mass=None,
    inertia=None,
    com_offset=None,
    visualization_enabled=None,
):
    px = obj.physx
    px.actor_type = actor_type or "STATIC"
    if mass is not None and hasattr(px, "mass"):
        px.mass = float(mass)
    if inertia is not None and hasattr(px, "inertia"):
        try:
            px.inertia = vector3_from_data(inertia, tuple(px.inertia))
        except Exception:
            debug_exception(
                _LOG, "Could not read the actor's inertia; the current value stays"
            )
    if com_offset is not None and hasattr(px, "com_offset"):
        try:
            px.com_offset = _position_tuple(com_offset, tuple(px.com_offset))
        except Exception:
            debug_exception(
                _LOG,
                "Could not read the actor's centre-of-mass offset; the current value stays",
            )

    scene_physx = getattr(context.scene, "physx", None)
    if not scene_physx:
        return
    for item in scene_physx.actors:
        if item.obj_ref == obj:
            if visualization_enabled is not None:
                item.visualization_enabled = bool(visualization_enabled)
            return
    new_item = scene_physx.actors.add()
    new_item.obj_ref = obj
    new_item.visualization_enabled = (
        True if visualization_enabled is None else bool(visualization_enabled)
    )
    scene_physx.actor_list_index = len(scene_physx.actors) - 1


def add_shape_to_actor(
    obj,
    shape_type,
    shape_data,
    physmat="Default",
    local_pos=None,
    local_rot=None,
    context=None,
    filter_data=None,
):
    if context is None:
        raise ValueError("PhysX shape authoring requires an explicit Blender context")
    local_pos, local_rot = _shape_local_transform(shape_data, local_pos, local_rot)
    if local_pos is None:
        local_pos = (0.0, 0.0, 0.0)
    if local_rot is None:
        local_rot = (1.0, 0.0, 0.0, 0.0)

    filter_data = _shape_filter(filter_data, shape_data)
    physmat_storage = "string"
    if isinstance(physmat, dict):
        physmat_storage = str(physmat.get("$storage") or "string")
    physmat_source = _shape_material(physmat, shape_data)
    physmat = resolve_physics_material_name(physmat_name(physmat_source))
    shape_data = _shape_payload(shape_type, shape_data)

    s_type_raw = str(shape_type or "")
    if not supports_collider_type(s_type_raw):
        raise ValueError(f"Unsupported PhysX collider type: {s_type_raw}")

    px = obj.physx
    shape_item = px.shapes.add()
    shape_item.name = s_type_raw.replace("physicsCollider", "")
    shape_item.local_pos = local_pos
    shape_item.local_rot = local_rot
    shape_item.physics_material = physmat
    shape_item.physics_material_source = physmat_source
    shape_item.physics_material_storage = physmat_storage
    shape_item.collision_preset = "None"
    _apply_filter_data(shape_item, filter_data)

    if s_type_raw == "physicsColliderBox":
        shape_item.shape_type = "BOX"
        extents = shape_data if isinstance(shape_data, dict) else {}
        shape_item.dim_x = float(extents.get("X", 0.5))
        shape_item.dim_y = float(extents.get("Y", 0.5))
        shape_item.dim_z = float(extents.get("Z", 0.5))

    elif s_type_raw == "physicsColliderSphere":
        shape_item.shape_type = "SPHERE"
        if isinstance(shape_data, dict):
            shape_item.dim_x = float(shape_data.get("radius", 0.5))
        else:
            shape_item.dim_x = float(shape_data)

    elif s_type_raw == "physicsColliderCapsule":
        shape_item.shape_type = "CAPSULE"
        data = shape_data if isinstance(shape_data, dict) else {}
        shape_item.dim_x = float(data.get("radius", 0.5))
        shape_item.dim_y = float(data.get("height", 1.0)) / 2.0

    elif s_type_raw == "physicsColliderConvex":
        shape_item.shape_type = "CONVEX"
        if isinstance(shape_data, dict):
            compiled = _compiled_geometry_bytes(
                shape_data.get("compiledGeometryBuffer")
            )
            raw_verts = shape_data.get("vertices", ()) or ()
        else:
            compiled = ""
            raw_verts = shape_data if isinstance(shape_data, list) else []

        if compiled:
            shape_item.cooked_data = compiled
            shape_item.is_cooked = True
            shape_item.name += " (Cooked)"
            return shape_item

        shape_points = []
        for v in raw_verts:
            shape_points.extend(
                [float(v.get("X", 0)), float(v.get("Y", 0)), float(v.get("Z", 0))]
            )

        if shape_points:
            try:
                cooked = require_initialized_bridge(context).cook_mesh(
                    "CONVEX", shape_points, [], 256
                )
                if cooked:
                    shape_item.cooked_data = base64.b64encode(cooked).decode("ascii")
                    shape_item.is_cooked = True
                    shape_item.name += " (Cooked)"
                else:
                    shape_item.name += " (Raw)"
            except Exception as exc:
                _LOG.error("Failed to cook convex collider: %s", exc, exc_info=True)
                shape_item.name += " (Failed)"
        else:
            shape_item.name += " (Raw)"

    elif s_type_raw in {"physicsColliderMesh", "physicsColliderTriangleMesh"}:
        shape_item.shape_type = "TRIANGLE"
        data = shape_data if isinstance(shape_data, dict) else {}
        compiled = _compiled_geometry_bytes(data.get("compiledGeometryBuffer"))
        if compiled:
            shape_item.cooked_data = compiled
            shape_item.is_cooked = True
        else:
            raw_vertices = (
                data.get("vertices", ()) or data.get("polygonVertices", ()) or ()
            )
            raw_indices = data.get("indices", ()) or data.get("indexBuffer", ()) or ()
            vertices = []
            for vertex in raw_vertices:
                if isinstance(vertex, dict):
                    vertices.extend(
                        (
                            float(vertex.get("X", 0.0)),
                            float(vertex.get("Y", 0.0)),
                            float(vertex.get("Z", 0.0)),
                        )
                    )
                else:
                    vertices.extend(float(value) for value in vertex[:3])
            indices = []
            for item in raw_indices:
                if isinstance(item, (list, tuple)):
                    indices.extend(int(value) for value in item)
                else:
                    indices.append(int(item))
            if vertices and indices:
                try:
                    cooked = require_initialized_bridge(context).cook_mesh(
                        "TRIANGLE", vertices, indices, 0
                    )
                    if cooked:
                        shape_item.cooked_data = base64.b64encode(cooked).decode(
                            "ascii"
                        )
                        shape_item.is_cooked = True
                except Exception as exc:
                    _LOG.error(
                        "Failed to cook triangle collider: %s", exc, exc_info=True
                    )

    elif s_type_raw == "physicsColliderHeightfield":
        shape_item.shape_type = "HEIGHTFIELD"
        if isinstance(shape_data, str) and shape_data:
            shape_item.cooked_data = shape_data
            shape_item.is_cooked = True
        elif isinstance(shape_data, dict):
            encoded = shape_data.get("Bytes") or shape_data.get("cooked_data")
            if encoded:
                shape_item.cooked_data = str(encoded)
                shape_item.is_cooked = True
            if "heightScale" in shape_data:
                shape_item.heightfield_height_scale = max(
                    float(shape_data["heightScale"]), 1.0e-9
                )
            if "rowScale" in shape_data:
                shape_item.heightfield_row_scale = max(
                    float(shape_data["rowScale"]), 1.0e-9
                )
            if "columnScale" in shape_data:
                shape_item.heightfield_column_scale = max(
                    float(shape_data["columnScale"]), 1.0e-9
                )

    return shape_item


def create_actor_object(
    name,
    collection,
    *,
    context=None,
    actor_type="STATIC",
    mass=None,
    inertia=None,
    com_offset=None,
    visualization_enabled=True,
):
    if context is None:
        raise ValueError("PhysX actor creation requires an explicit Blender context")
    obj = track_created_datablock("objects", bpy.data.objects.new(name, None))
    collection.objects.link(obj)
    register_actor(
        obj,
        actor_type,
        context,
        mass=mass,
        inertia=inertia,
        com_offset=com_offset,
        visualization_enabled=visualization_enabled,
    )
    return obj


def _actors_changed(scene_physx):
    if hasattr(scene_physx, "active_actor_count"):
        scene_physx.active_actor_count = len(scene_physx.actors)
    if hasattr(scene_physx, "scene_built"):
        scene_physx.scene_built = False
    scene_physx.actor_list_index = min(
        scene_physx.actor_list_index, max(len(scene_physx.actors) - 1, 0)
    )


def register_actors(objects, context):
    """Register the objects that carry PhysX shapes and are not registered yet"""
    scene_physx = getattr(context.scene, "physx", None)
    if not scene_physx:
        return 0
    known = {
        item.obj_ref.as_pointer()
        for item in scene_physx.actors
        if item.obj_ref is not None
    }
    added = 0
    for obj in objects:
        physx = getattr(obj, "physx", None)
        if physx is None or not len(physx.shapes) or obj.as_pointer() in known:
            continue
        item = scene_physx.actors.add()
        item.obj_ref = obj
        item.visualization_enabled = True
        known.add(obj.as_pointer())
        added += 1
    if added:
        _actors_changed(scene_physx)
    return added


def unregister_actors(objects, context):
    """Take objects out of the registry and keep their PhysX data, as for templates that are only copied"""
    scene_physx = getattr(context.scene, "physx", None)
    if not scene_physx:
        return 0
    pointers = {obj.as_pointer() for obj in objects}
    removed = 0
    for index in range(len(scene_physx.actors) - 1, -1, -1):
        obj = scene_physx.actors[index].obj_ref
        if obj is not None and obj.as_pointer() in pointers:
            scene_physx.actors.remove(index)
            removed += 1
    if removed:
        _actors_changed(scene_physx)
    return removed


def prune_actor_registry(context):
    """Drop registry entries whose object is gone, as rolled-back imports leave them"""
    scene_physx = getattr(context.scene, "physx", None)
    if not scene_physx:
        return 0
    removed = 0
    for index in range(len(scene_physx.actors) - 1, -1, -1):
        if scene_physx.actors[index].obj_ref is None:
            scene_physx.actors.remove(index)
            removed += 1
    if removed:
        _actors_changed(scene_physx)
    return removed


def remove_actor_object(obj, context=None):
    if context is None:
        raise ValueError("PhysX actor removal requires an explicit Blender context")
    scene_physx = getattr(context.scene, "physx", None)
    if scene_physx is not None:
        for index in range(len(scene_physx.actors) - 1, -1, -1):
            if scene_physx.actors[index].obj_ref == obj:
                scene_physx.actors.remove(index)
        if hasattr(scene_physx, "active_actor_count"):
            scene_physx.active_actor_count = len(scene_physx.actors)
    if obj is not None and obj.name in bpy.data.objects:
        bpy.data.objects.remove(obj, do_unlink=True)


def _shape_source_metadata(collider_data, shape_item=None):
    if not isinstance(collider_data, dict):
        return {}
    metadata = {}
    for key in (
        "isImported",
        "isObstacle",
        "isQueryShapeOnly",
        "materialApperanceOverrides",
        "tag",
        "volumeModifier",
    ):
        if key in collider_data:
            metadata[key] = collider_data[key]
    if "filterData" in collider_data and collider_data.get("filterData") is None:
        metadata["filterDataWasNull"] = True
    local_to_body = collider_data.get("localToBody")
    if isinstance(local_to_body, dict):
        position = local_to_body.get("position")
        if isinstance(position, dict) and "W" in position:
            metadata["localPositionW"] = position["W"]

    collider_type = collider_data.get("$type")
    if collider_type in {
        "physicsColliderConvex",
        "physicsColliderMesh",
        "physicsColliderTriangleMesh",
    }:
        geometry = {}
        for key in (
            "compiledGeometryBuffer",
            "indexBuffer",
            "polygonVertices",
            "vertices",
        ):
            if key in collider_data:
                geometry[key] = collider_data[key]
        if geometry:
            metadata["sourceGeometry"] = geometry
            if shape_item is not None:
                metadata["sourceCookedDataSignature"] = cooked_data_signature(
                    getattr(shape_item, "cooked_data", "")
                )
    return metadata


def add_red_collider_to_actor(
    actor_obj,
    collider_data,
    *,
    context=None,
    local_pos=None,
    local_rot=None,
    filter_data=None,
):
    if context is None:
        raise ValueError("RED collider authoring requires an explicit Blender context")
    if not isinstance(collider_data, dict):
        raise TypeError("collider_data must be a collider dictionary")
    if local_pos is None or local_rot is None:
        shape_pos, shape_rot = _collider_local_transform(collider_data)
        local_pos = shape_pos if local_pos is None else local_pos
        local_rot = shape_rot if local_rot is None else local_rot
    shape_item = add_shape_to_actor(
        actor_obj,
        collider_data.get("$type", ""),
        _collider_shape_data(collider_data),
        physmat=collider_data.get(
            "material", {"$type": "CName", "$storage": "string", "$value": "Default"}
        ),
        local_pos=local_pos,
        local_rot=local_rot,
        context=context,
        filter_data=filter_data or collider_data.get("filterData"),
    )
    metadata = _shape_source_metadata(collider_data, shape_item)
    if metadata.get("filterDataWasNull"):
        shape_item.filter_source_preset = "None"
        shape_item.filter_source_sim_group = "0"
        shape_item.filter_source_sim_target = "0"
        shape_item.filter_source_query_mask = "0"
        shape_item.filter_source_signature = filter_ui_signature(
            shape_item.collision_preset,
            shape_item.filter_group,
            shape_item.filter_mask,
            shape_item.filter_query,
        )
    if metadata and hasattr(shape_item, "source_phys_shape_metadata_json"):
        shape_item.source_phys_shape_metadata_json = json.dumps(
            metadata, separators=(",", ":"), sort_keys=True
        )
    return shape_item


def native_shape_definition(shape):
    raw = b""
    if shape.shape_type in {"CONVEX", "TRIANGLE", "HEIGHTFIELD"}:
        if not shape.cooked_data:
            return None
        raw = base64.b64decode(shape.cooked_data.encode("ascii"))
    q = shape.local_rot
    pos = shape.local_pos
    filter_state = simulation_filter_state(state_for_export(shape))
    if shape.shape_type == "BOX":
        dims = [shape.dim_x, shape.dim_y, shape.dim_z]
    elif shape.shape_type == "SPHERE":
        dims = [shape.dim_x]
    elif shape.shape_type == "CAPSULE":
        dims = [shape.dim_x, shape.dim_y]
    else:
        dims = []
    definition = {
        "type": shape.shape_type,
        "data": raw,
        "dims": dims,
        "pos": [pos[0], pos[1], pos[2]],
        "rot": [q[1], q[2], q[3], q[0]],
        "mat": get_mat_data(shape.physics_material),
        "filter": [
            filter_state.simulation_group,
            filter_state.simulation_target,
            filter_state.query_mask,
            0,
        ],
    }
    if shape.shape_type == "HEIGHTFIELD":
        definition["heightfield_scale"] = [
            float(shape.heightfield_height_scale),
            float(shape.heightfield_row_scale),
            float(shape.heightfield_column_scale),
        ]
    return definition
