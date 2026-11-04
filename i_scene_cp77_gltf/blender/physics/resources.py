import json

from mathutils import Matrix, Vector

from ...assetio.documents import DocumentSession
from ...assetio.transform_values import vector3_from_data
from ...assetio.values import cname_value, resolve_handle_reference
from ...core.log import get_logger, operation
from ...physics.domain.mass import positive_mass
from ...physics.model.resource import PhysicsResource
from ...physics.services.repository import PhysicsRepository
from ..naming import fit_id_name
from ..red_transforms import red_quaternion
from .actors import (
    add_red_collider_to_actor,
    create_actor_object,
    register_actor,
    remove_actor_object,
    supports_collider_type,
)

_LOG = get_logger(__name__)


def _vector3(value, default=(0.0, 0.0, 0.0)):
    return Vector(vector3_from_data(value, default))


def _quaternion(value):
    return red_quaternion(value).normalized()


def _transform_matrix(value):
    if not isinstance(value, dict):
        return Matrix.Identity(4)
    position = (
        value.get("position") or value.get("Position") or value.get("Translation")
    )
    orientation = (
        value.get("orientation") or value.get("Orientation") or value.get("Rotation")
    )
    return Matrix.LocRotScale(
        _vector3(position), _quaternion(orientation), Vector((1.0, 1.0, 1.0))
    )


def _actor_type(body, params):
    simulation_type = cname_value(params.get("simulationType")) or cname_value(
        body.get("simulationType")
    )
    actor_type = str(simulation_type).rsplit("::", 1)[-1].upper()
    return actor_type if actor_type in {"STATIC", "DYNAMIC", "KINEMATIC"} else "STATIC"


def _body_source_metadata(body, params):
    metadata = {}
    for key in ("isQueryBodyOnly", "mappedBoneName", "mappedBoneToBody", "name"):
        if key in body:
            metadata[key] = body[key]
    local_to_model = body.get("localToModel")
    if isinstance(local_to_model, dict):
        position = local_to_model.get("position")
        if isinstance(position, dict) and "W" in position:
            metadata["localPositionW"] = position["W"]
    if isinstance(params, dict):
        preserved_params = {}
        for key in (
            "angularDamping",
            "linearDamping",
            "maxAngularVelocity",
            "maxContactImpulse",
            "maxDepenetrationVelocity",
            "solverIterationsCountPosition",
            "solverIterationsCountVelocity",
        ):
            if key in params:
                preserved_params[key] = params[key]
        com_offset = params.get("comOffset")
        if isinstance(com_offset, dict):
            orientation = com_offset.get("orientation")
            if isinstance(orientation, dict):
                preserved_params["comOffsetOrientation"] = orientation
            position = com_offset.get("position")
            if isinstance(position, dict) and "W" in position:
                preserved_params["comOffsetPositionW"] = position["W"]
        if preserved_params:
            metadata["params"] = preserved_params
    return metadata


def import_phys_resource(
    resource,
    rig=None,
    chassis_z=None,
    target_collection=None,
    actor_matrix=None,
    context=None,
):
    if context is None:
        raise ValueError("Physics resource import requires an explicit Blender context")
    target_collection = (
        target_collection or context.collection or context.scene.collection
    )
    if not isinstance(resource, PhysicsResource):
        raise TypeError("resource must be a PhysicsResource")
    with operation(_LOG, "physics body registration", source=resource.source_path):
        bodies = resource.bodies
        handle_lookup = resource.handles
        base_matrix = (
            actor_matrix.copy()
            if isinstance(actor_matrix, Matrix)
            else Matrix.Identity(4)
        )
        actor_count = 0
        shape_count = 0

        for body_index, body_ref in enumerate(bodies):
            body = resolve_handle_reference(body_ref, handle_lookup)
            if not isinstance(body, dict):
                continue

            params = resolve_handle_reference(body.get("params"), handle_lookup)
            if not isinstance(params, dict):
                params = (
                    body.get("params") if isinstance(body.get("params"), dict) else {}
                )
            collision_shapes = body.get("collisionShapes") or ()
            body_name = cname_value(body.get("name"), f"PhysicsBody_{body_index}")
            body_matrix = base_matrix @ _transform_matrix(body.get("localToModel"))
            actor_type = _actor_type(body, params)
            mass = positive_mass(params, body)
            inertia = params.get("inertia") or body.get("inertia")
            com_offset = params.get("comOffset") or body.get("comOffset")
            body_filter = resolve_handle_reference(
                body.get("filterData"), handle_lookup
            ) or resolve_handle_reference(body.get("filter"), handle_lookup)
            resolved_shapes = []
            for shape_index, shape_ref in enumerate(collision_shapes):
                collider_data = resolve_handle_reference(shape_ref, handle_lookup)
                if not isinstance(collider_data, dict):
                    continue
                collider_type = collider_data.get("$type", "")
                if not supports_collider_type(collider_type):
                    _LOG.warning(
                        "Unsupported .phys collider type %s for %s",
                        collider_type,
                        body_name,
                    )
                    continue
                resolved_shapes.append((shape_index, collider_data))

            if not resolved_shapes:
                continue

            actor_obj = create_actor_object(
                body_name,
                target_collection,
                context=context,
                actor_type=actor_type,
                mass=mass,
                inertia=inertia,
                com_offset=com_offset,
            )
            actor_obj.matrix_world = body_matrix
            actor_physx = getattr(actor_obj, "physx", None)
            if actor_physx is not None and hasattr(
                actor_physx, "source_phys_resource_path"
            ):
                actor_physx.source_phys_resource_path = str(resource.source_path or "")
            body_metadata = _body_source_metadata(body, params)
            if base_matrix != Matrix.Identity(4):
                # The frame localToModel was placed under, such as a vehicle's chassis component; the export writes
                # localToModel back relative to it.
                body_metadata["modelFrame"] = [
                    value for row in base_matrix for value in row
                ]
            if (
                body_metadata
                and actor_physx is not None
                and hasattr(actor_physx, "source_phys_body_metadata_json")
            ):
                actor_physx.source_phys_body_metadata_json = json.dumps(
                    body_metadata, separators=(",", ":"), sort_keys=True
                )
            if rig is not None and actor_matrix is None:
                constraint = actor_obj.constraints.new("CHILD_OF")
                constraint.target = rig
                constraint.subtarget = "Base"
                constraint.set_inverse_pending = True
                if chassis_z is not None:
                    actor_obj.delta_location[2] = chassis_z

            body_shape_count = 0
            for shape_index, collider_data in resolved_shapes:
                collider_type = collider_data.get("$type", "")
                try:
                    shape_filter = resolve_handle_reference(
                        collider_data.get("filterData"), handle_lookup
                    )
                    shape_item = add_red_collider_to_actor(
                        actor_obj,
                        collider_data,
                        context=context,
                        filter_data=shape_filter or body_filter,
                    )
                except Exception as exc:
                    _LOG.warning(
                        "Unable to import %s for %s: %s",
                        collider_type,
                        body_name,
                        exc,
                        exc_info=True,
                    )
                    continue

                shape_item.name = fit_id_name(
                    body_name, f"_{shape_index}_{shape_item.name}"
                )
                body_shape_count += 1

            if not body_shape_count:
                remove_actor_object(actor_obj, context)
                continue

            actor_count += 1
            shape_count += body_shape_count

        scene_physx = getattr(context.scene, "physx", None)
        if scene_physx is not None and actor_count:
            if hasattr(scene_physx, "scene_built"):
                scene_physx.scene_built = False
            if hasattr(scene_physx, "active_actor_count"):
                scene_physx.active_actor_count = len(scene_physx.actors)

    _LOG.info(
        "Registered %d physics body actors with %d shapes", actor_count, shape_count
    )
    return actor_count, shape_count


def import_phys(
    filepath,
    rig=None,
    chassis_z=None,
    target_collection=None,
    actor_matrix=None,
    context=None,
):
    with DocumentSession() as documents:
        resource = PhysicsRepository(documents).load(filepath, required=True)
    return import_phys_resource(
        resource,
        rig=rig,
        chassis_z=chassis_z,
        target_collection=target_collection,
        actor_matrix=actor_matrix,
        context=context,
    )


def import_phys_to_actor(filepath, target_obj, context):
    try:
        with DocumentSession() as documents:
            resource = PhysicsRepository(documents).load(filepath, required=True)
    except Exception as error:
        _LOG.error("Unable to read physics resource: %s", error, exc_info=True)
        return False

    if not resource.bodies:
        _LOG.error("Physics resource contains no bodies")
        return False

    body = resolve_handle_reference(resource.bodies[0], resource.handles)
    if not isinstance(body, dict):
        _LOG.error("The first .phys body could not be resolved")
        return False

    params = resolve_handle_reference(body.get("params"), resource.handles)
    if not isinstance(params, dict):
        params = body.get("params") if isinstance(body.get("params"), dict) else {}

    px = target_obj.physx
    if px.actor_type == "NONE":
        px.actor_type = _actor_type(body, params)
        mass = positive_mass(params, body)
        if mass > 0.0:
            px.mass = mass
        inertia = params.get("inertia") or body.get("inertia")
        if isinstance(inertia, dict):
            px.inertia = _vector3(inertia, tuple(px.inertia))
        com_offset = params.get("comOffset") or body.get("comOffset")
        if isinstance(com_offset, dict):
            transform = (
                com_offset.get("position") or com_offset.get("Position") or com_offset
            )
            px.com_offset = _vector3(transform, tuple(px.com_offset))

    register_actor(target_obj, px.actor_type, context)
    body_metadata = _body_source_metadata(body, params)
    if body_metadata and hasattr(px, "source_phys_body_metadata_json"):
        px.source_phys_body_metadata_json = json.dumps(
            body_metadata, separators=(",", ":"), sort_keys=True
        )
    body_filter = resolve_handle_reference(
        body.get("filterData"), resource.handles
    ) or resolve_handle_reference(body.get("filter"), resource.handles)
    imported = 0
    for shape_ref in body.get("collisionShapes", ()) or ():
        collider_data = resolve_handle_reference(shape_ref, resource.handles)
        if not isinstance(collider_data, dict):
            continue
        collider_type = collider_data.get("$type", "")
        if not supports_collider_type(collider_type):
            _LOG.warning("Unsupported .phys collider type %s", collider_type)
            continue
        filter_data = resolve_handle_reference(
            collider_data.get("filterData"), resource.handles
        )
        try:
            add_red_collider_to_actor(
                target_obj,
                collider_data,
                context=context,
                filter_data=filter_data or body_filter,
            )
            imported += 1
        except Exception as error:
            _LOG.warning("Unable to import %s: %s", collider_type, error, exc_info=True)

    if not imported:
        _LOG.warning("No supported shapes were imported from %s", filepath)
        return False

    scene_physx = getattr(context.scene, "physx", None)
    if scene_physx is not None:
        scene_physx.scene_built = False
        scene_physx.active_actor_count = len(scene_physx.actors)
    return True
