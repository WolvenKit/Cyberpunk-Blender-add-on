from mathutils import Vector

from ...blender.operator_results import OperationResult
from ...blender.physics.actors import add_shape_to_actor, create_actor_object
from ...blender.physics.bridge_session import require_initialized_bridge
from ...blender.physics.vehicle_geometry import vehicle_actor_world, vehicle_root
from ...core.log import debug_exception, get_logger
from ...physics.runtime.bridge import reset_native_scene
from ...physics.runtime.cloth_provider import (
    mark_all_cloths_error,
    prepare_scene_cloths,
    refresh_cloth_object_cache,
    release_scene_cloths,
    reset_scene_cloths,
    restart_nvcloth_runtime,
    restore_scene_cloths_for_rebuild,
    set_active_cloth_state,
)
from ..blender.vehicle_authoring_state import authored_wheel_dimensions
from ..blender.vehicle_config import vehicle_simulation_excluded_objects, wheel_centers
from ..runtime.simulation import begin_runtime_session
from ..runtime.vehicle_preview import build_vehicle_if_enabled, reset_vehicle_preview
from .actors import build_authored_actors, validate_scene_actors
from .vehicle import setup_vehicle_from_rig

_LOG = get_logger(__name__)


def _vehicle_ground_height(context):
    """Height of the lowest tire bottom of the enabled vehicle at its rest pose"""
    vehicle = getattr(context.scene, "physx_vehicle", None)
    if vehicle is None or not vehicle.enabled or vehicle_root(vehicle) is None:
        return None
    try:
        centers = wheel_centers(vehicle)
        radii, _widths = authored_wheel_dimensions(vehicle)
    except (AttributeError, TypeError, ValueError) as error:
        _LOG.debug("Vehicle ground height unavailable: %s", error)
        return None
    if (
        not centers
        or any(center is None for center in centers)
        or len(radii) < len(centers)
    ):
        return None
    actor_world = vehicle_actor_world(vehicle)
    return min(
        (actor_world @ Vector(center)).z - float(radius)
        for center, radius in zip(centers, radii)
    )


def _ensure_preview_ground(context):
    px_scene = context.scene.physx
    for item in px_scene.actors:
        obj = item.obj_ref
        if (
            obj is not None
            and getattr(obj.physx, "source_kind", "") == "PREVIEW_GROUND"
        ):
            _LOG.debug("PhysX preview ground reused: %s", obj.name)
            return obj

    minimum_z = _vehicle_ground_height(context)
    if minimum_z is None:
        minimum_z = 0.0
        found_bounds = False
        for obj in context.scene.objects:
            if (
                obj.type != "MESH"
                or not getattr(obj, "bound_box", None)
                or not obj.visible_get()
            ):
                continue
            matrix = obj.matrix_world
            for corner in obj.bound_box:
                z = (matrix @ Vector(corner)).z
                minimum_z = z if not found_bounds else min(minimum_z, z)
                found_bounds = True

    size_xy = 100000.0
    thickness = 0.01
    obj = create_actor_object(
        "PhysX_PreviewGround",
        context.collection or context.scene.collection,
        context=context,
        actor_type="STATIC",
        visualization_enabled=False,
    )
    obj.location = (0.0, 0.0, minimum_z - 0.05 - thickness * 0.5)
    obj.physx.source_kind = "PREVIEW_GROUND"
    add_shape_to_actor(
        obj,
        "physicsColliderBox",
        {"X": size_xy * 0.5, "Y": size_xy * 0.5, "Z": thickness * 0.5},
        context=context,
    )
    _LOG.debug(
        "PhysX preview ground created: %s z=%.4f size=%.1f",
        obj.name,
        obj.location.z,
        size_xy,
    )
    return obj


def initialize_scene(context, add_ground=True):
    try:
        require_initialized_bridge(context)
        if add_ground:
            _ensure_preview_ground(context)
    except ImportError as error:
        return OperationResult.cancelled(
            f"PxBridge is unavailable: {error}", error=error
        )
    except Exception as error:
        return OperationResult.cancelled(
            f"PhysX initialization failed: {error}", error=error
        )
    return OperationResult.finished("PhysX Initialized")


def validate_scene(context):
    vehicle = getattr(context.scene, "physx_vehicle", None)
    if (
        vehicle is not None
        and vehicle.enabled
        and vehicle.source_mode == "RIG"
        and getattr(vehicle, "rig", None) is not None
    ):
        from ...blender.physics.vehicle_phys import adopt_loaded_vehicle_phys

        adopt_loaded_vehicle_phys(context, vehicle.rig)
    return validate_scene_actors(
        context, vehicle_simulation_excluded_objects(context.scene)
    )


def build_scene(context):
    px_scene = context.scene.physx
    if px_scene.sim_running:
        return OperationResult.cancelled(
            "Stop the simulation before rebuilding the PhysX scene"
        )
    px_scene.scene_built = False
    px_scene.active_actor_count = 0

    validation = validate_scene(context)
    if not validation.ok:
        return validation

    bridge = None
    try:
        bridge = require_initialized_bridge(context)
        reset_vehicle_preview(context, restore=True)
        refresh_cloth_object_cache(context)
        restore_scene_cloths_for_rebuild(context)
        release_scene_cloths(context, bridge)
        reset_native_scene(bridge)
        restart_nvcloth_runtime(bridge)
        gravity = px_scene.gravity
        bridge.set_gravity(gravity[0], gravity[1], gravity[2])

        count = build_authored_actors(
            context, bridge, vehicle_simulation_excluded_objects(context.scene)
        )
        prepare_scene_cloths(context, bridge)
        vehicle_handle, vehicle_warnings = build_vehicle_if_enabled(context, bridge)
        if vehicle_handle:
            count += 1

        px_scene.active_actor_count = bridge.get_actor_count()
        px_scene.scene_built = True
        message = f"Built {count} actors"
        if vehicle_warnings:
            return OperationResult.finished(
                message + "; " + "; ".join(vehicle_warnings), "WARNING"
            )
        return OperationResult.finished(message)
    except Exception as error:
        if bridge is not None:
            try:
                reset_native_scene(bridge)
                restart_nvcloth_runtime(bridge)
            except Exception:
                debug_exception(
                    _LOG, "Could not reset the native scene before rebuilding it"
                )
        px_scene.scene_built = False
        px_scene.active_actor_count = 0
        reset_vehicle_preview(context, restore=True)
        mark_all_cloths_error(context, str(error))
        return OperationResult.cancelled(str(error), error=error)


def update_gravity(context):
    try:
        bridge = require_initialized_bridge(context)
        gravity = context.scene.physx.gravity
        bridge.set_gravity(gravity[0], gravity[1], gravity[2])
    except Exception as error:
        return OperationResult.cancelled(
            f"Unable to update gravity: {error}", error=error
        )
    return OperationResult.finished()


def reset_session(context):
    px_scene = context.scene.physx
    if px_scene.sim_running:
        return OperationResult.cancelled(
            "Stop the active simulation before resetting the PhysX session"
        )
    cleanup_error = None
    try:
        bridge = require_initialized_bridge(context)
    except Exception as error:
        return OperationResult.cancelled(
            f"Unable to reset PhysX session: {error}", error=error
        )
    try:
        release_scene_cloths(context, bridge)
    except Exception as error:
        debug_exception(
            _LOG, "Could not release the scene's cloths while resetting the session"
        )
        cleanup_error = error
    try:
        reset_native_scene(bridge)
    except Exception as error:
        return OperationResult.cancelled(
            f"Unable to reset PhysX session: {error}", error=error
        )
    reset_vehicle_preview(context, restore=True)
    px_scene.active_actor_count = 0
    px_scene.scene_built = False
    reset_scene_cloths(context)
    if cleanup_error:
        return OperationResult.finished(
            f"PhysX session reset; native cloth cleanup reported: {cleanup_error}",
            "WARNING",
        )
    return OperationResult.finished()


def build_vehicle_preview(context):
    px_scene = context.scene.physx
    if px_scene.sim_running:
        return OperationResult.cancelled(
            "Pause the simulation before rebuilding the vehicle"
        )
    try:
        vehicle = context.scene.physx_vehicle
        if vehicle.source_mode == "RIG" and vehicle.refresh_rig_on_build:
            setup_vehicle_from_rig(context, vehicle.rig)
        if not px_scene.is_initialized:
            result = initialize_scene(context, False)
            if not result.ok or not px_scene.is_initialized:
                return (
                    result
                    if not result.ok
                    else OperationResult.cancelled("PhysX initialization failed")
                )
        if vehicle.preview_auto_ground:
            _ensure_preview_ground(context)
        result = build_scene(context)
        if not result.ok:
            return result
        if not vehicle.preview_built:
            return OperationResult.cancelled("Vehicle preview was not built")
    except Exception as error:
        return OperationResult.cancelled(str(error), error=error)
    return OperationResult.finished(vehicle.preview_message or "Vehicle preview built")


def reset_vehicle_session(context):
    result = reset_session(context)
    if not result.ok:
        return result
    context.view_layer.update()
    if result.level == "WARNING":
        return OperationResult.finished(
            f"Vehicle preview reset; {result.message}", "WARNING"
        )
    return OperationResult.finished("Vehicle preview reset")


def start_simulation(context):
    from .scene import build_scene

    if not context.scene.physx.scene_built:
        result = build_scene(context)
        if not result.ok:
            return result
    result = begin_runtime_session(context)
    if not result.ok:
        return result
    set_active_cloth_state(context, "RUNNING", "Simulation running")
    return OperationResult.finished()
