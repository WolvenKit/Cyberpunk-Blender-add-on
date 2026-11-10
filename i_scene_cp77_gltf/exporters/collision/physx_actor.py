import re

from mathutils import Vector

from ...assetio.atomic import atomic_write_json
from ...assetio.headers import cr2w_header, validate_physics_payload
from ...assetio.values import cname_value, json_object
from ...blender.matrix import matrix_from_flat, safe_matrix_inverse
from ...blender.physics.cooked_shapes import decode_cooked_geometry
from ...core.log import get_logger
from ...physics.domain.filters import filter_ui_signature, state_for_export
from ...physics.domain.resource_paths import normalize_phys_json_path
from ...physics.model.resource import cooked_data_signature

_LOG = get_logger(__name__)


_PHYSX_SHAPE_TYPES = {
    "BOX": "physicsColliderBox",
    "SPHERE": "physicsColliderSphere",
    "CAPSULE": "physicsColliderCapsule",
    "CONVEX": "physicsColliderConvex",
    "TRIANGLE": "physicsColliderMesh",
}


def _transform_payload(matrix):
    location = matrix.to_translation()
    rotation = matrix.to_quaternion()
    rotation_norm_squared = (
        float(rotation.w) * float(rotation.w)
        + float(rotation.x) * float(rotation.x)
        + float(rotation.y) * float(rotation.y)
        + float(rotation.z) * float(rotation.z)
    )
    if rotation_norm_squared > 0.0:
        rotation.normalize()
    return {
        "$type": "Transform",
        "orientation": {
            "$type": "Quaternion",
            "i": float(rotation.x),
            "j": float(rotation.y),
            "k": float(rotation.z),
            "r": float(rotation.w),
        },
        "position": {
            "$type": "Vector4",
            "W": 0,
            "X": float(location.x),
            "Y": float(location.y),
            "Z": float(location.z),
        },
    }


def _source_filter_is_unchanged_null(shape, source_shape):
    if not source_shape.get("filterDataWasNull"):
        return False
    source_signature = str(getattr(shape, "filter_source_signature", "") or "")
    if not source_signature:
        return False
    current_signature = filter_ui_signature(
        str(getattr(shape, "collision_preset", "") or "None"),
        getattr(shape, "filter_group", ()),
        getattr(shape, "filter_mask", ()),
        getattr(shape, "filter_query", ()),
    )
    return source_signature == current_signature


def _source_geometry_if_unchanged(shape, source_shape):
    geometry = source_shape.get("sourceGeometry")
    if not isinstance(geometry, dict):
        return None
    if "sourceCookedDataSignature" not in source_shape:
        return None
    if source_shape.get("sourceCookedDataSignature") != cooked_data_signature(
        getattr(shape, "cooked_data", "")
    ):
        return None
    return geometry


def _decoded_cooked_geometry(shape_type, cooked_data):
    if not cooked_data:
        return None
    try:
        return decode_cooked_geometry(shape_type, cooked_data)
    except Exception as error:
        _LOG.error(
            "Could not decode %s cooked geometry: %s", shape_type, error, exc_info=True
        )
        return None


def _vector3_array(values):
    if not values or len(values) % 3:
        return []
    return [
        {
            "$type": "Vector3",
            "X": values[index],
            "Y": values[index + 1],
            "Z": values[index + 2],
        }
        for index in range(0, len(values), 3)
    ]


def _body_name(obj, source_body):
    """The body's name"""
    source = source_body.get("name")
    name = cname_value(source, None) if isinstance(source, dict) else None
    if name and re.fullmatch(re.escape(str(name)) + r"(?:\.\d{3,})?", obj.name):
        return source
    return {"$type": "CName", "$storage": "string", "$value": obj.name}


def export_actor_item_to_phys(actor_item, filepath):
    filepath = normalize_phys_json_path(filepath)
    if not actor_item or not actor_item.obj_ref:
        raise ValueError("The actor has no object to export")

    obj_ref = actor_item.obj_ref
    if not hasattr(obj_ref, "physx"):
        raise ValueError(f"{obj_ref.name} has no PhysX properties")

    px_obj = obj_ref.physx

    total_mass = px_obj.mass
    inertia = Vector(px_obj.inertia)
    com = Vector(px_obj.com_offset)

    sim_type = "Static"
    if px_obj.actor_type == "DYNAMIC":
        sim_type = "Dynamic"
    elif px_obj.actor_type == "KINEMATIC":
        sim_type = "Kinematic"

    colliders = []
    current_handle = 1

    for shape in px_obj.shapes:
        collider_type = _PHYSX_SHAPE_TYPES.get(shape.shape_type)
        if collider_type is None:
            raise ValueError(
                f"Unsupported PhysX shape type for .phys export: {shape.shape_type}"
            )

        source_shape = json_object(
            getattr(shape, "source_phys_shape_metadata_json", "")
        )
        filter_state = state_for_export(shape)
        preset_name = filter_state.preset or "None"
        sim_group = filter_state.simulation_group
        sim_target_mask = filter_state.simulation_target
        query_mask = filter_state.query_mask

        mat_name = (
            str(getattr(shape, "physics_material_source", "") or "")
            or shape.physics_material
            or "Default"
        )
        mat_storage = str(
            getattr(shape, "physics_material_storage", "string") or "string"
        )
        if mat_storage == "uint64" and not str(mat_name).isdigit():
            mat_storage = "string"

        shape_handle_id = str(current_handle)
        if _source_filter_is_unchanged_null(shape, source_shape):
            filter_data_wrapper = None
            current_handle += 1
        else:
            filter_data_wrapper = {
                "HandleId": str(current_handle + 1),
                "Data": {
                    "$type": "physicsFilterData",
                    "customFilterData": None,
                    "preset": {
                        "$type": "CName",
                        "$storage": "string",
                        "$value": preset_name,
                    },
                    "queryFilter": {
                        "$type": "physicsQueryFilter",
                        "mask1": "0",
                        "mask2": str(query_mask),
                    },
                    "simulationFilter": {
                        "$type": "physicsSimulationFilter",
                        "mask1": str(sim_group),
                        "mask2": str(sim_target_mask),
                    },
                },
            }
            current_handle += 2

        pos = shape.local_pos
        rot = shape.local_rot
        collider_data = {
            "$type": collider_type,
            "filterData": filter_data_wrapper,
            "isImported": source_shape.get("isImported", 0),
            "isQueryShapeOnly": source_shape.get("isQueryShapeOnly", 0),
            "localToBody": {
                "$type": "Transform",
                "orientation": {
                    "$type": "Quaternion",
                    "i": rot[1],
                    "j": rot[2],
                    "k": rot[3],
                    "r": rot[0],
                },
                "position": {
                    "$type": "Vector4",
                    "W": source_shape.get("localPositionW", 0),
                    "X": pos[0],
                    "Y": pos[1],
                    "Z": pos[2],
                },
            },
            "material": {"$type": "CName", "$storage": mat_storage, "$value": mat_name},
            "materialApperanceOverrides": source_shape.get(
                "materialApperanceOverrides", []
            ),
            "tag": source_shape.get(
                "tag", {"$type": "CName", "$storage": "string", "$value": "None"}
            ),
            "volumeModifier": source_shape.get("volumeModifier", 1),
        }

        if "isObstacle" in source_shape:
            collider_data["isObstacle"] = source_shape["isObstacle"]

        if shape.shape_type == "BOX":
            collider_data.setdefault("isObstacle", 0)
            collider_data["halfExtents"] = {
                "$type": "Vector3",
                "X": shape.dim_x,
                "Y": shape.dim_y,
                "Z": shape.dim_z,
            }
        elif shape.shape_type == "SPHERE":
            collider_data["radius"] = shape.dim_x
        elif shape.shape_type == "CAPSULE":
            collider_data["radius"] = shape.dim_x
            collider_data["height"] = shape.dim_y * 2
        elif shape.shape_type == "CONVEX":
            source_geometry = _source_geometry_if_unchanged(shape, source_shape)
            if source_geometry is not None:
                collider_data.update(source_geometry)
            else:
                geometry = _decoded_cooked_geometry("CONVEX", shape.cooked_data)
                vertices = _vector3_array((geometry or {}).get("vertices", ()))
                if not vertices:
                    raise ValueError(
                        f"{obj_ref.name}: convex shape '{shape.name}' has no decodable cooked geometry"
                    )
                collider_data.update(
                    {
                        "compiledGeometryBuffer": None,
                        "indexBuffer": [],
                        "polygonVertices": [],
                        "vertices": vertices,
                    }
                )
        elif shape.shape_type == "TRIANGLE":
            source_geometry = _source_geometry_if_unchanged(shape, source_shape)
            if source_geometry is not None:
                collider_data.update(source_geometry)
            else:
                geometry = _decoded_cooked_geometry("TRIANGLE", shape.cooked_data)
                vertices = _vector3_array((geometry or {}).get("vertices", ()))
                indices = [int(value) for value in (geometry or {}).get("indices", ())]
                if not vertices or not indices or len(indices) % 3:
                    raise ValueError(
                        f"{obj_ref.name}: triangle shape '{shape.name}' has no decodable cooked geometry"
                    )
                collider_data.update(
                    {
                        "compiledGeometryBuffer": None,
                        "indexBuffer": indices,
                        "polygonVertices": [],
                        "vertices": vertices,
                    }
                )

        colliders.append({"HandleId": shape_handle_id, "Data": collider_data})

    if not colliders:
        raise ValueError(f"Actor {obj_ref.name} has no shapes.")

    source_body = json_object(getattr(px_obj, "source_phys_body_metadata_json", ""))
    source_params = (
        source_body.get("params") if isinstance(source_body.get("params"), dict) else {}
    )
    basis = obj_ref.matrix_basis
    # An actor imported under a component, such as a vehicle's chassis, keeps localToModel in that component's frame.
    frame = matrix_from_flat(source_body.get("modelFrame") or ())
    if frame is not None:
        basis = safe_matrix_inverse(frame) @ basis
    local_to_model = _transform_payload(basis)
    local_to_model["position"]["W"] = source_body.get("localPositionW", 0)
    com_orientation = source_params.get(
        "comOffsetOrientation", {"$type": "Quaternion", "i": 0, "j": 0, "k": 0, "r": 1}
    )

    output_json = {
        "Header": cr2w_header(filepath),
        "Data": {
            "Version": 195,
            "BuildVersion": 0,
            "RootChunk": {
                "$type": "physicsSystemResource",
                "bodies": [
                    {
                        "HandleId": "0",
                        "Data": {
                            "$type": "physicsSystemBody",
                            "collisionShapes": colliders,
                            "isQueryBodyOnly": source_body.get("isQueryBodyOnly", 0),
                            "localToModel": local_to_model,
                            "mappedBoneName": source_body.get(
                                "mappedBoneName",
                                {
                                    "$type": "CName",
                                    "$storage": "string",
                                    "$value": "None",
                                },
                            ),
                            "mappedBoneToBody": source_body.get(
                                "mappedBoneToBody",
                                {
                                    "$type": "Transform",
                                    "orientation": {
                                        "$type": "Quaternion",
                                        "i": 0,
                                        "j": 0,
                                        "k": 0,
                                        "r": 1,
                                    },
                                    "position": {
                                        "$type": "Vector4",
                                        "W": 0,
                                        "X": 0,
                                        "Y": 0,
                                        "Z": 0,
                                    },
                                },
                            ),
                            "name": _body_name(obj_ref, source_body),
                            "params": {
                                "$type": "physicsSystemBodyParams",
                                "angularDamping": source_params.get(
                                    "angularDamping", 0.0
                                ),
                                "linearDamping": source_params.get(
                                    "linearDamping", 0.0
                                ),
                                "comOffset": {
                                    "$type": "Transform",
                                    "orientation": com_orientation,
                                    "position": {
                                        "$type": "Vector4",
                                        "W": source_params.get("comOffsetPositionW", 0),
                                        "X": com.x,
                                        "Y": com.y,
                                        "Z": com.z,
                                    },
                                },
                                "inertia": {
                                    "$type": "Vector3",
                                    "X": inertia.x,
                                    "Y": inertia.y,
                                    "Z": inertia.z,
                                },
                                "mass": total_mass,
                                "maxAngularVelocity": source_params.get(
                                    "maxAngularVelocity", -1
                                ),
                                "maxContactImpulse": source_params.get(
                                    "maxContactImpulse", -1
                                ),
                                "maxDepenetrationVelocity": source_params.get(
                                    "maxDepenetrationVelocity", -1
                                ),
                                "simulationType": sim_type,
                                "solverIterationsCountPosition": source_params.get(
                                    "solverIterationsCountPosition", 4
                                ),
                                "solverIterationsCountVelocity": source_params.get(
                                    "solverIterationsCountVelocity", 1
                                ),
                            },
                        },
                    }
                ],
                "cookingPlatform": "PLATFORM_PC",
                "joints": [],
            },
            "EmbeddedFiles": [],
        },
    }

    validate_physics_payload(output_json, filepath)
    atomic_write_json(filepath, output_json, indent=4)
    return filepath
