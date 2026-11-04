from __future__ import annotations

import json
import os
from dataclasses import dataclass

from mathutils import Matrix, Quaternion, Vector

from ...assetio.streaming_sector import collision_actor_scale, collision_actor_shapes
from ...assetio.transform_values import vector3_from_data, world_position_from_data
from ...assetio.values import cname_value, coerce_int, nested_dict
from ...bartmoss.matrix import scale_in_frame
from ...core.log import debug_exception, get_logger
from ...physics.model.materials import is_known_physics_material
from ..naming import fit_id_name
from ..red_transforms import red_quaternion, transform_scale
from .actors import add_shape_to_actor, create_actor_object
from .objects import update_collision_bits

_LOG = get_logger(__name__)
_WARNED_UNKNOWN_PHYSMATS = set()
_DEFAULT_PHYSMAT = {"$type": "CName", "$storage": "string", "$value": "Default"}
# A cooked collision shape's geometry class and the shape kind it holds.
_COOKED_SHAPE_KINDS = {
    "PhysicsGeometryBoxData": "Box",
    "PhysicsGeometrySphereData": "Sphere",
    "PhysicsGeometryCapsuleData": "Capsule",
    "PhysicsGeometryConvexMeshData": "ConvexMesh",
    "PhysicsGeometryTriangleMeshData": "TriangleMesh",
}


@dataclass(frozen=True, slots=True)
class _CollisionShape:
    """One shape of a world collision actor"""

    kind: str
    size: tuple
    geometry_hash: str
    position: Vector
    rotation: Quaternion
    material: object
    preset: object


@dataclass(frozen=True, slots=True)
class _CollisionActor:
    position: Vector
    rotation: Quaternion
    scale: Vector
    shapes: tuple[_CollisionShape, ...]


def _position(value):
    """A position (WorldPosition or Vector) as a Vector, with FixedPoint components decoded"""
    return Vector(world_position_from_data(value))


def _rotation(value):
    """A quaternion as a normalized Quaternion"""
    if not isinstance(value, dict):
        return Quaternion((1.0, 0.0, 0.0, 0.0))
    return red_quaternion(value).normalized()


def _source_actor(obj, *, kind, sector, node_data_index, actor_index):
    px = obj.physx
    px.source_kind = kind
    px.source_sector = sector
    px.source_node_data_index = int(node_data_index)
    px.source_actor_index = int(actor_index)


def _material(material):
    if material is None:
        return dict(_DEFAULT_PHYSMAT)
    if isinstance(material, dict):
        token = str(cname_value(material, "Default") or "Default")
        if (
            not is_known_physics_material(token)
            and token not in _WARNED_UNKNOWN_PHYSMATS
        ):
            _WARNED_UNKNOWN_PHYSMATS.add(token)
            _LOG.warning(
                "Unresolved physics material CName %s; retaining source token and using Default PhysX coefficients",
                token,
            )
        return material
    return {"$type": "CName", "$storage": "string", "$value": str(material)}


def _collision_geometry(session, sector_hash, entry_hash):
    path = os.path.join(
        session.raw_root, "collision_meshes", f"{sector_hash}_{entry_hash}.json"
    )
    if not os.path.isfile(path):
        _LOG.warning("Collision geometry not found: %s", path)
        return None
    payload = session.documents.payload(path)
    return payload if isinstance(payload, dict) else None


def _triangle_indices(values):
    indices = []
    for item in values or ():
        if isinstance(item, dict):
            item = item.get("Elements", item.get("elements", ()))
        if isinstance(item, (list, tuple)):
            indices.extend(int(value) for value in item)
        else:
            indices.append(int(item))
    return indices


def _scaled_vertices(values, actor_scale):
    vertices = []
    for vertex in values:
        value = vector3_from_data(vertex, (0.0, 0.0, 0.0))
        vertices.append(
            {
                "X": value[0] * actor_scale.x,
                "Y": value[1] * actor_scale.y,
                "Z": value[2] * actor_scale.z,
            }
        )
    return vertices


def _mesh_shape_data(payload, actor_scale):
    if not isinstance(payload, dict):
        return None, None
    if payload.get("Vertices") and payload.get("Triangles"):
        return "physicsColliderTriangleMesh", {
            "vertices": _scaled_vertices(payload["Vertices"], actor_scale),
            "indices": _triangle_indices(payload["Triangles"]),
        }
    hull = payload.get("HullData")
    if isinstance(hull, dict) and hull.get("HullVertices"):
        return "physicsColliderConvex", _scaled_vertices(
            hull["HullVertices"], actor_scale
        )
    return None, None


def _plain_actors(data):
    """The actors of a plain worldCollisionNode (its Data), as WolvenKit reads its compiled data"""
    actors = nested_dict(data, "compiledData", "Data").get("Actors")
    for actor in actors if isinstance(actors, list) else ():
        if not isinstance(actor, dict):
            continue
        shapes = []
        for shape in actor.get("Shapes") or ():
            materials = shape.get("Materials") or ()
            shapes.append(
                _CollisionShape(
                    kind=str(shape.get("ShapeType", "") or ""),
                    size=vector3_from_data(shape.get("Size"), (0.5, 0.5, 0.5)),
                    geometry_hash=str(shape.get("Hash", "") or ""),
                    position=_position(shape.get("Position")),
                    rotation=_rotation(shape.get("Rotation")),
                    material=materials[0] if materials else None,
                    preset=shape.get("Preset"),
                )
            )
        yield _CollisionActor(
            position=_position(actor.get("Position")),
            rotation=_rotation(actor.get("Orientation")),
            scale=transform_scale(actor),
            shapes=tuple(shapes),
        )


def _item(values, index):
    """values[index] for a valid index of a list, else None"""
    if isinstance(values, list) and 0 <= index < len(values):
        return values[index]
    return None


def _cooked_actors(inner):
    """The actors of an inner node of a cooked collision or foliage-destruction node"""
    for actor in inner.get("actors") or ():
        if not isinstance(actor, dict):
            continue
        actor_shapes = []
        for shape in collision_actor_shapes(inner, actor):
            key = nested_dict(shape, "collisionSourceKey")
            material_index = _item(
                inner.get("materialIndices"), coerce_int(shape.get("index"), -1)
            )
            actor_shapes.append(
                _CollisionShape(
                    kind=_COOKED_SHAPE_KINDS.get(
                        str(key.get("$type", "")), str(key.get("$type", ""))
                    ),
                    size=vector3_from_data(key.get("size"), (0.5, 0.5, 0.5)),
                    geometry_hash=str(key.get("hash", "") or ""),
                    position=_position(
                        _item(
                            inner.get("shapePositions"),
                            coerce_int(shape.get("shapePositionIndex"), -1),
                        )
                    ),
                    rotation=_rotation(
                        _item(
                            inner.get("shapeRotations"),
                            coerce_int(shape.get("shapeRotationIndex"), -1),
                        )
                    ),
                    material=None
                    if material_index is None
                    else _item(inner.get("materials"), coerce_int(material_index, -1)),
                    preset=_item(
                        inner.get("presets"),
                        coerce_int(shape.get("shapePresetIndex"), -1),
                    ),
                )
            )
        transform = nested_dict(actor, "transform")
        yield _CollisionActor(
            position=_position(transform.get("Position")),
            rotation=_rotation(transform.get("Orientation")),
            scale=Vector(collision_actor_scale(inner, actor) or (1.0, 1.0, 1.0)),
            shapes=tuple(actor_shapes),
        )


def _bridge_shape(context, sector_hash, shape, actor_scale):
    """The bridge collider type and data of shape on an actor of actor_scale"""
    size = shape.size
    if shape.kind == "Box":
        stretched = scale_in_frame(shape.rotation.to_matrix(), actor_scale)
        return "physicsColliderBox", {
            "X": size[0] * float(stretched[0, 0]),
            "Y": size[1] * float(stretched[1, 1]),
            "Z": size[2] * float(stretched[2, 2]),
        }
    if shape.kind == "Sphere":
        return "physicsColliderSphere", {"radius": size[0] * actor_scale.x}
    if shape.kind == "Capsule":
        return "physicsColliderCapsule", {
            "radius": size[0] * actor_scale.x,
            "height": max(size[1] * actor_scale.z * 2.0, 0.0),
        }
    payload = _collision_geometry(context.session, sector_hash, shape.geometry_hash)
    return _mesh_shape_data(payload, actor_scale)


def import_world_collision_node(context):
    """Place the collision actors of each node data entry and return the shapes placed"""
    data = context.data
    actors = tuple(
        _cooked_actors(data) if context.node.inner_index >= 0 else _plain_actors(data)
    )
    sector_hash = str(data.get("sectorHash", "") or "")
    placed = 0

    for instance in context.instances:
        node_data_index = instance.index
        for actor_index, actor in enumerate(actors):
            actor_obj = None
            actor_scale = actor.scale
            for shape in actor.shapes:
                bridge_type, shape_data = _bridge_shape(
                    context, sector_hash, shape, actor_scale
                )
                if not bridge_type:
                    _LOG.warning(
                        "%s: unsupported world collision shape %s",
                        context.sector_name,
                        shape.kind,
                    )
                    continue

                if actor_obj is None:
                    actor_obj = create_actor_object(
                        f"PhysX_{context.sector_name}_{node_data_index}_{actor_index}",
                        context.collection_for_node_data(node_data_index),
                        context=context.blender_context,
                        actor_type="STATIC",
                    )
                    actor_obj.matrix_world = Matrix.LocRotScale(
                        actor.position, actor.rotation, Vector((1.0, 1.0, 1.0))
                    )

                shape_item = add_shape_to_actor(
                    actor_obj,
                    bridge_type,
                    shape_data,
                    physmat=_material(shape.material),
                    local_pos=(
                        shape.position.x * actor_scale.x,
                        shape.position.y * actor_scale.y,
                        shape.position.z * actor_scale.z,
                    ),
                    local_rot=tuple(shape.rotation),
                    context=context.blender_context,
                )
                preset = str(
                    cname_value(shape.preset, "World Static") or "World Static"
                )
                shape_item.collision_preset = preset
                try:
                    update_collision_bits(shape_item, context.blender_context)
                except Exception:
                    debug_exception(
                        _LOG,
                        "Could not update the collision bits of a world collision shape",
                    )
                placed += 1

            if actor_obj is not None:
                _source_actor(
                    actor_obj,
                    kind="WORLD_COLLISION",
                    sector=context.sector_name,
                    node_data_index=node_data_index,
                    actor_index=actor_index,
                )
                context.operations.assign_custom_properties(
                    actor_obj,
                    context.node,
                    context.sector_name,
                    cp77_node_data_index=node_data_index,
                )
    return placed


def _actor_transform_matrix(data):
    transform = data.get("actorTransform", {}) if isinstance(data, dict) else {}
    return Matrix.LocRotScale(
        _position(transform.get("Position")),
        _rotation(transform.get("Orientation")),
        Vector((1.0, 1.0, 1.0)),
    )


def _create_heightfield_actor(context, instance, instance_index):
    data = context.data
    geometry = data.get("heightfieldGeometry")
    if not isinstance(geometry, dict) or not geometry.get("Bytes"):
        raise ValueError("worldTerrainCollisionNode has no heightfield geometry")

    name = fit_id_name(
        f"PhysX_{context.sector_name}_{context.node_index}_{instance_index}"
    )
    obj = create_actor_object(
        name,
        context.collection_for_instance(instance),
        context=context.blender_context,
        actor_type="STATIC",
        visualization_enabled=False,
    )
    obj.matrix_world = _actor_transform_matrix(data)

    shape_item = add_shape_to_actor(
        obj,
        "physicsColliderHeightfield",
        geometry,
        physmat=(data.get("materials") or [dict(_DEFAULT_PHYSMAT)])[0],
        context=context.blender_context,
    )
    shape_item.heightfield_height_scale = max(
        abs(float(data.get("heightScale", 1.0))), 1.0e-9
    )
    shape_item.heightfield_row_scale = max(
        abs(float(data.get("rowScale", 1.0))), 1.0e-9
    )
    shape_item.heightfield_column_scale = max(
        abs(float(data.get("columnScale", 1.0))), 1.0e-9
    )
    extents = vector3_from_data(data.get("extents"), (1.0, 1.0, 1.0))
    shape_item.heightfield_extents = tuple(
        max(abs(float(value)), 0.0) for value in extents
    )
    shape_item.heightfield_materials_json = json.dumps(
        data.get("materials") or [], separators=(",", ":")
    )
    shape_item.heightfield_material_indices_json = json.dumps(
        data.get("materialIndices") or [], separators=(",", ":")
    )
    shape_item.heightfield_source_prefab_hash = str(data.get("sourcePrefabHash") or "0")

    _source_actor(
        obj,
        kind="WORLD_HEIGHTFIELD",
        sector=context.sector_name,
        node_data_index=instance.index,
        actor_index=instance_index,
    )
    return obj


def create_foliage_destruction_actor(context, instance):
    data = context.data
    name = fit_id_name(f"PhysX_Foliage_{context.node_index}_{instance.index}")
    obj = create_actor_object(
        name,
        context.collection_for_instance(instance),
        context=context.blender_context,
        actor_type="STATIC",
    )
    obj.matrix_world = context.operations.instance_matrix(
        instance, context.execution.scale_factor
    )
    extents = vector3_from_data(data.get("extents"), (0.5, 0.5, 0.5))
    add_shape_to_actor(
        obj,
        "physicsColliderBox",
        {"X": abs(extents[0]), "Y": abs(extents[1]), "Z": abs(extents[2])},
        context=context.blender_context,
    )
    return obj


@dataclass(frozen=True, slots=True)
class SectorCollisionPlacement:
    object: object


class SectorCollisionService:
    def __init__(self, session):
        self.session = session

    def create(self, context, instance, instance_index):
        if context.node_type == "worldTerrainCollisionNode":
            obj = _create_heightfield_actor(context, instance, instance_index)
        elif context.node_type == "worldFoliageDestructionNode":
            obj = create_foliage_destruction_actor(context, instance)
        else:
            raise ValueError(
                f"Unsupported PhysX sector collision node type: {context.node_type}"
            )
        context.operations.assign_custom_properties(
            obj,
            context.node,
            context.sector_name,
            cp77_node_data_index=instance.index,
        )
        return SectorCollisionPlacement(obj)
