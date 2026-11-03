from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from time import perf_counter
from typing import Any

import bpy
from mathutils import Matrix, Vector

from ...bartmoss.vehicle import STANDARD_GRAVITY, fixed_step_count
from ...blender.identity import rna_identity
from ...blender.physics.bridge_session import require_initialized_bridge
from ...blender.physics.vehicle_geometry import (
    WHEEL_FIELDS,
    basis_matrix,
    matrix_from_pose,
    vehicle_root,
)
from ...core.log import get_logger
from ...physics.domain.vehicle.gears import (
    PHYSX_MAX_FORWARD_GEARS,
    collection_gears,
    validate_gears,
)
from ...physics.model.vehicle.timing import VEHICLE_FIXED_TIME_STEP
from ...physics.runtime.bridge_contract import validate_vehicle_bridge_contract
from ..blender.vehicle_authoring_state import scene_gravity_magnitude
from ..blender.vehicle_config import (
    validate_vehicle,
    vehicle_config,
    vehicle_live_dynamics_config,
)
from ..blender.vehicle_rig import (
    capture_vehicle_rig,
    pose_vehicle_rig,
    restore_vehicle_rig,
)
from .vehicle_camera import snap_vehicle_camera, update_vehicle_camera

_LOG = get_logger(__name__)


@dataclass(slots=True)
class VehicleRuntimeState:
    handle: int = 0
    basis: Any = None
    basis_inverse: Any = None
    chassis_shape_offset: Any = None
    chassis_origin_translation: Any = None
    chassis_scale: Any = None
    chassis_scale_matrix: Any = None
    chassis: Any = None
    wheels: dict | None = None
    chassis_world: Any = None
    wheel_relative: dict | None = None
    rig_drive: Any = None
    max_steer: float = 0.0
    steering_input: float = 0.0
    wheel_visual_corrections: dict | None = None
    chassis_phys_objects: tuple | None = None
    source_mode: str = "MANUAL"
    last_stats: dict | None = None
    last_telemetry_log_time: float = 0.0
    telemetry_invalid_reported: bool = False
    expected_vehicle_weight: float = 0.0
    nominal_static_compressions: tuple[float, ...] = ()
    low_support_since: float = 0.0
    low_support_reported: bool = False
    telemetry_window_samples: int = 0
    telemetry_angular_sq_sum: tuple[float, float, float] = (0.0, 0.0, 0.0)
    telemetry_angular_peak: tuple[float, float, float] = (0.0, 0.0, 0.0)
    telemetry_lateral_force_peak: tuple[float, ...] = ()
    step_time_accumulator: float = 0.0


_LOGGED_BRIDGE_BUILDS = set()


_LIVE_UPDATE_TIMERS = {}


_RUNTIME = {}


def _runtime(scene, create=True):
    key = rna_identity(scene)
    state = _RUNTIME.get(key)
    if state is None and create:
        state = VehicleRuntimeState(
            wheels={},
            wheel_relative={},
            wheel_visual_corrections={},
            last_stats={},
        )
        _RUNTIME[key] = state
    return state


def clear_vehicle_runtime(scene=None, restore=False):
    if scene is None:
        states = tuple(_RUNTIME.values())
        _RUNTIME.clear()
    else:
        state = _RUNTIME.pop(rna_identity(scene), None)
        states = (state,) if state is not None else ()
    if restore:
        for state in states:
            _restore_state(state)


def invalidate_vehicle_runtime_state(scene=None, *, restore=False):
    clear_vehicle_runtime(scene, restore=restore)
    scenes = tuple(getattr(bpy.data, "scenes", ())) if scene is None else (scene,)
    for current in scenes:
        vehicle = getattr(current, "physx_vehicle", None)
        if vehicle is None:
            continue
        vehicle.vehicle_handle = "0"
        vehicle.preview_built = False
        vehicle.preview_dirty = True
        vehicle.preview_message = "PhysX runtime was reset; rebuild the vehicle preview"
        vehicle.live_update_supported = False
        vehicle.live_update_pending = False
        vehicle.live_rebuild_pending = False
        vehicle.live_update_error = ""


def _restore_state(state):
    if state is None or state.chassis_world is None or state.chassis is None:
        return
    try:
        state.chassis.matrix_world = state.chassis_world.copy()
    except ReferenceError:
        return
    if state.source_mode == "RIG":
        if state.rig_drive is not None:
            restore_vehicle_rig(state.rig_drive)
        return
    _place_wheels(state, state.chassis_world)


def _place_wheels(state, chassis_world):
    """Places manual wheel objects at their rest offsets from the given chassis matrix"""
    for field, wheel in (state.wheels or {}).items():
        relative = (state.wheel_relative or {}).get(field)
        if wheel is not None and relative is not None:
            try:
                wheel.matrix_world = chassis_world @ relative
            except ReferenceError:
                continue


def _scale_matrix(scale):
    return Matrix.Diagonal((scale.x, scale.y, scale.z, 1.0))


def _live_tuning_supported(bridge):
    return all(
        callable(getattr(bridge, name, None))
        for name in ("update_vehicle_dynamics", "get_vehicle_dynamic_state")
    )


def _bridge_build_signature(build_info):
    return (
        str(build_info.get("python", "?")),
        str(build_info.get("physx", "?")),
        int(build_info.get("vehicle_state", 0)),
        tuple(
            bool(build_info.get(name, False))
            for name in (
                "vehicle_cp77_wheel_solver",
                "vehicle_wheel_telemetry",
                "vehicle_smoothed_tire_load",
                "vehicle_isolated_cp77_forces",
                "vehicle_cp77_impulse_timing",
                "vehicle_low_speed_friction_clamp",
                "vehicle_two_phase_tire_forces",
                "vehicle_cp77_traction_curves",
                "vehicle_live_dynamics",
                "vehicle_chassis_shapes",
            )
        ),
    )


def _log_bridge_build_info(build_info):
    signature = _bridge_build_signature(build_info)
    if signature in _LOGGED_BRIDGE_BUILDS:
        return
    _LOGGED_BRIDGE_BUILDS.add(signature)
    _LOG.debug(
        "PxBridge vehicle runtime: python=%s physx=%s contract=%d "
        "cp77_wheel_solver=%s telemetry=%s smoothed_tire_load=%s isolated_cp77_forces=%s "
        "cp77_impulse_timing=%s low_speed_friction_clamp=%s two_phase_tire_forces=%s "
        "cp77_traction_curves=%s live_dynamics=%s chassis_shapes=%s",
        build_info.get("python", "?"),
        build_info.get("physx", "?"),
        int(build_info.get("vehicle_state", 0)),
        bool(build_info.get("vehicle_cp77_wheel_solver", False)),
        bool(build_info.get("vehicle_wheel_telemetry", False)),
        bool(build_info.get("vehicle_smoothed_tire_load", False)),
        bool(build_info.get("vehicle_isolated_cp77_forces", False)),
        bool(build_info.get("vehicle_cp77_impulse_timing", False)),
        bool(build_info.get("vehicle_low_speed_friction_clamp", False)),
        bool(build_info.get("vehicle_two_phase_tire_forces", False)),
        bool(build_info.get("vehicle_cp77_traction_curves", False)),
        bool(build_info.get("vehicle_live_dynamics", False)),
        bool(build_info.get("vehicle_chassis_shapes", False)),
    )


def _telemetry_values(stats, name, wheel_count):
    values = stats.get(name, ()) if isinstance(stats, dict) else ()
    result = []
    invalid = False
    if isinstance(values, (list, tuple)):
        for value in values[:wheel_count]:
            try:
                value = float(value)
            except (TypeError, ValueError):
                value = 0.0
                invalid = True
            if not math.isfinite(value):
                value = 0.0
                invalid = True
            result.append(value)
    while len(result) < wheel_count:
        result.append(0.0)
    return result, invalid


def _telemetry_summary(stats, wheel_count):
    strengths, invalid_strength = _telemetry_values(
        stats, "wheel_contact_strengths", wheel_count
    )
    compressions, invalid_compression = _telemetry_values(
        stats, "wheel_compressions", wheel_count
    )
    loads, invalid_load = _telemetry_values(stats, "wheel_normal_loads", wheel_count)
    tire_loads, invalid_tire_load = _telemetry_values(
        stats, "wheel_tire_loads", wheel_count
    )
    contacts = sum(value > 1.0e-4 for value in strengths)
    return (
        contacts,
        contacts == 0,
        compressions,
        loads,
        tire_loads,
        invalid_strength or invalid_compression or invalid_load or invalid_tire_load,
    )


def _gravity_magnitude(scene):
    magnitude = scene_gravity_magnitude(scene)
    return (
        magnitude
        if math.isfinite(magnitude) and magnitude > 1.0e-6
        else STANDARD_GRAVITY
    )


def _support_budget(config, gravity):
    wheel_count = len(config.get("wheel_centers", ()))
    chassis_mass = max(float(config.get("chassis_mass", 0.0)), 0.0)
    expected_weight = chassis_mass * float(gravity)
    spring_strengths = [
        float(value) for value in config.get("suspension_spring_strengths", ())
    ]
    nominal_load = expected_weight / wheel_count if wheel_count else 0.0
    nominal_compressions = tuple(
        nominal_load / strength if strength > 1.0e-6 else 0.0
        for strength in spring_strengths[:wheel_count]
    )
    return expected_weight, nominal_compressions


def _log_suspension_budget(scene, state, config):
    gravity = _gravity_magnitude(scene)
    expected_weight, nominal_compressions = _support_budget(config, gravity)
    state.expected_vehicle_weight = expected_weight
    state.nominal_static_compressions = nominal_compressions
    state.low_support_since = 0.0
    state.low_support_reported = False
    _LOG.debug(
        "Vehicle suspension budget: chassis_mass=%.1fkg total_mass=%.1fkg gravity=%.3fm/s^2 "
        "weight=%.1fN nominal_static_compression=%s",
        float(config.get("chassis_mass", 0.0)),
        float(config.get("total_mass", config.get("chassis_mass", 0.0))),
        gravity,
        expected_weight,
        [round(value, 4) for value in nominal_compressions],
    )
    spring_lengths = tuple(
        float(value) for value in config.get("suspension_spring_lengths", ())
    )
    if spring_lengths and len(spring_lengths) == len(nominal_compressions):
        overloaded = [
            index
            for index, (nominal, travel) in enumerate(
                zip(nominal_compressions, spring_lengths)
            )
            if travel > 1.0e-6 and nominal > travel
        ]
        if overloaded:
            _LOG.warning(
                "Vehicle nominal static spring compression exceeds available logical travel on wheel(s) %s",
                overloaded,
            )
    if _LOG.isEnabledFor(logging.DEBUG):
        _LOG.debug(
            "Vehicle suspension geometry: centers=%s target_centers=%s radii=%s compression=%s droop=%s "
            "spring_length=%s spring_strength=%s bound_damping=%s rebound_damping=%s directions=%s vertical_offsets=%s "
            "anti_roll_stiffness=%s anti_roll_limit=%s anti_roll_length=%s turning_roll_factor=%.4f",
            [
                [round(float(axis), 4) for axis in center]
                for center in config.get("wheel_centers", ())
            ],
            [
                [round(float(axis), 4) for axis in center]
                for center in config.get("wheel_target_centers", ())
            ],
            [round(float(value), 4) for value in config.get("wheel_radii", ())],
            [
                round(float(value), 4)
                for value in config.get("suspension_compressions", ())
            ],
            [round(float(value), 4) for value in config.get("suspension_droops", ())],
            [
                round(float(value), 4)
                for value in config.get("suspension_spring_lengths", ())
            ],
            [
                round(float(value), 1)
                for value in config.get("suspension_spring_strengths", ())
            ],
            [
                round(float(value), 1)
                for value in config.get("suspension_compression_damper_rates", ())
            ],
            [
                round(float(value), 1)
                for value in config.get("suspension_rebound_damper_rates", ())
            ],
            [
                [round(float(axis), 4) for axis in direction]
                for direction in config.get("suspension_directions", ())
            ],
            [
                round(float(value), 4)
                for value in config.get("wheel_vertical_offsets", ())
            ],
            [
                round(float(value), 1)
                for value in config.get("anti_roll_stiffnesses", ())
            ],
            [
                round(float(value), 4)
                for value in config.get("anti_roll_displacement_limits", ())
            ],
            [
                round(float(value), 4)
                for value in config.get("anti_roll_length_scalars", ())
            ],
            float(config.get("turning_roll_factor", 1.0)),
        )


def _update_support_diagnostic(
    state, stats, wheel_count, contacts, compressions, loads, *, initial=False
):
    expected_weight = float(getattr(state, "expected_vehicle_weight", 0.0) or 0.0)
    if initial or expected_weight <= 1.0e-6 or wheel_count <= 0:
        return None
    support_force = sum(max(float(value), 0.0) for value in loads)
    support_ratio = support_force / expected_weight
    linear_velocity, invalid_velocity = _telemetry_values(stats, "linear_velocity", 3)
    vertical_speed = linear_velocity[2] if not invalid_velocity else 0.0
    now = perf_counter()
    all_contact = contacts == wheel_count
    low_support = all_contact and support_ratio < 0.35 and abs(vertical_speed) < 0.25
    if low_support:
        if state.low_support_since <= 0.0:
            state.low_support_since = now
        elif not state.low_support_reported and now - state.low_support_since >= 2.0:
            state.low_support_reported = True
            nominal = tuple(getattr(state, "nominal_static_compressions", ()) or ())
            compression_ratio = 0.0
            if nominal and len(nominal) == len(compressions):
                ratios = [
                    value / expected if expected > 1.0e-6 else 0.0
                    for value, expected in zip(compressions, nominal)
                ]
                compression_ratio = sum(ratios) / len(ratios)
            _LOG.warning(
                "Vehicle wheel support remains low with all wheels contacting: support=%.1fN/%.1fN (%.1f%%), "
                "vertical_speed=%.3fm/s compression_vs_nominal=%.1f%%. "
                "The custom wheel solver is not carrying most of the vehicle weight; inspect hidden native support or query/force geometry.",
                support_force,
                expected_weight,
                support_ratio * 100.0,
                vertical_speed,
                compression_ratio * 100.0,
            )
    else:
        state.low_support_since = 0.0
        if support_ratio >= 0.65 or not all_contact:
            state.low_support_reported = False
    return support_ratio


def _log_wheel_telemetry(state, stats, wheel_count, *, initial=False):
    contacts, all_airborne, compressions, loads, tire_loads, invalid = (
        _telemetry_summary(stats, wheel_count)
    )
    angular_velocity, invalid_angular_velocity = _telemetry_values(
        stats, "angular_velocity", 3
    )
    lateral_forces, invalid_lateral_forces = _telemetry_values(
        stats, "wheel_lateral_forces", wheel_count
    )
    if not initial:
        state.telemetry_window_samples += 1
        state.telemetry_angular_sq_sum = tuple(
            old + value * value
            for old, value in zip(state.telemetry_angular_sq_sum, angular_velocity)
        )
        state.telemetry_angular_peak = tuple(
            max(old, abs(value))
            for old, value in zip(state.telemetry_angular_peak, angular_velocity)
        )
        peaks = tuple(state.telemetry_lateral_force_peak or (0.0,) * wheel_count)
        state.telemetry_lateral_force_peak = tuple(
            max(old, abs(value)) for old, value in zip(peaks, lateral_forces)
        )
    support_ratio = _update_support_diagnostic(
        state, stats, wheel_count, contacts, compressions, loads, initial=initial
    )
    if invalid and not state.telemetry_invalid_reported:
        state.telemetry_invalid_reported = True
        _LOG.warning(
            "Vehicle wheel telemetry contained non-finite values; invalid display values were replaced with zero"
        )
    if not _LOG.isEnabledFor(logging.DEBUG):
        return
    now = perf_counter()
    if not initial and now - state.last_telemetry_log_time < 1.0:
        return
    state.last_telemetry_log_time = now
    sdk_dv, invalid_sdk_dv = _telemetry_values(
        stats, "vehicle_sdk_linear_velocity_delta", 3
    )
    sdk_dw, invalid_sdk_dw = _telemetry_values(
        stats, "vehicle_sdk_angular_velocity_delta", 3
    )
    lateral_slips, invalid_lateral_slips = _telemetry_values(
        stats, "wheel_lateral_slips", wheel_count
    )
    samples = max(int(state.telemetry_window_samples), 1)
    angular_rms = [
        math.sqrt(value / samples) for value in state.telemetry_angular_sq_sum
    ]
    angular_peak = list(state.telemetry_angular_peak)
    lateral_force_peak = list(
        state.telemetry_lateral_force_peak or (0.0,) * wheel_count
    )
    if (
        invalid_sdk_dv
        or invalid_sdk_dw
        or invalid_angular_velocity
        or invalid_lateral_slips
        or invalid_lateral_forces
    ) and not state.telemetry_invalid_reported:
        state.telemetry_invalid_reported = True
        _LOG.warning(
            "Vehicle native SDK delta telemetry contained non-finite values; invalid display values were replaced with zero"
        )
    _LOG.debug(
        "%s: contacts=%d/%d all_airborne=%s compression=%s suspension_load=%s tire_load=%s support_ratio=%s angular_velocity=%s angular_rms=%s angular_peak=%s lateral_slip=%s lateral_force=%s lateral_force_peak=%s sdk_dv=%s sdk_dw=%s",
        "Vehicle initial wheel telemetry (pre-step)"
        if initial
        else "Vehicle wheel telemetry",
        contacts,
        wheel_count,
        all_airborne,
        [round(value, 4) for value in compressions],
        [round(value, 1) for value in loads],
        [round(value, 1) for value in tire_loads],
        "pre-step" if initial or support_ratio is None else f"{support_ratio:.3f}",
        [round(value, 5) for value in angular_velocity],
        [round(value, 5) for value in angular_rms],
        [round(value, 5) for value in angular_peak],
        [round(value, 5) for value in lateral_slips],
        [round(value, 1) for value in lateral_forces],
        [round(value, 1) for value in lateral_force_peak],
        [round(value, 5) for value in sdk_dv],
        [round(value, 5) for value in sdk_dw],
    )
    state.telemetry_window_samples = 0
    state.telemetry_angular_sq_sum = (0.0, 0.0, 0.0)
    state.telemetry_angular_peak = (0.0, 0.0, 0.0)
    state.telemetry_lateral_force_peak = ()


def _flush_vehicle_live_updates_for_scene(scene, bridge=None):
    """Applies the queued edits to the built vehicle"""
    vehicle = getattr(scene, "physx_vehicle", None)
    if vehicle is None or not vehicle.preview_built or vehicle.preview_dirty:
        return False
    rebuild = vehicle.live_rebuild_pending
    if not rebuild and not vehicle.live_update_pending:
        return False
    bridge = bridge or require_initialized_bridge()
    vehicle.live_update_supported = _live_tuning_supported(bridge)
    if not vehicle.live_update_supported:
        vehicle.live_update_pending = False
        vehicle.live_rebuild_pending = False
        vehicle.preview_dirty = True
        vehicle.preview_message = "Live vehicle tuning requires the current PxBridge source; rebuild the native bridge"
        return False
    try:
        if rebuild:
            _rebuild_vehicle_in_place(scene, bridge)
        else:
            live_config = vehicle_live_dynamics_config(vehicle)
            bridge.update_vehicle_dynamics(live_config)
            state = _runtime(scene, create=False)
            if state is not None:
                state.max_steer = max(live_config.get("steer_angles") or (0.0,))
    except Exception as error:
        vehicle.live_update_error = str(error)
        vehicle.live_update_pending = False
        vehicle.live_rebuild_pending = False
        vehicle.preview_message = f"Live vehicle update rejected: {error}"
        _LOG.warning("Vehicle live update rejected: %s", error, exc_info=True)
        return False
    vehicle.live_update_pending = False
    vehicle.live_rebuild_pending = False
    vehicle.live_update_error = ""
    vehicle.preview_message = (
        "Live collider change applied" if rebuild else "Live dynamics applied"
    )
    _LOG.debug(
        "Applied coalesced live vehicle %s", "rebuild" if rebuild else "dynamics"
    )
    return True


def _scene_from_pointer(scene_pointer):
    for scene in getattr(bpy.data, "scenes", ()):
        if scene.as_pointer() == scene_pointer:
            return scene
    return None


def _schedule_vehicle_live_update(scene):
    scene_pointer = scene.as_pointer()
    existing = _LIVE_UPDATE_TIMERS.get(scene_pointer)
    if existing is not None and bpy.app.timers.is_registered(existing):
        return True

    def flush_pending():
        _LIVE_UPDATE_TIMERS.pop(scene_pointer, None)
        target_scene = _scene_from_pointer(scene_pointer)
        if target_scene is None:
            return
        vehicle = getattr(target_scene, "physx_vehicle", None)
        physx = getattr(target_scene, "physx", None)
        if vehicle is None or not (
            vehicle.live_update_pending or vehicle.live_rebuild_pending
        ):
            return
        if physx is not None and physx.sim_running:
            return
        try:
            _flush_vehicle_live_updates_for_scene(target_scene)
        except Exception as error:
            vehicle.live_update_error = str(error)
            vehicle.preview_message = f"Live dynamics update rejected: {error}"
            _LOG.warning("Vehicle live dynamics timer failed: %s", error, exc_info=True)
        return

    _LIVE_UPDATE_TIMERS[scene_pointer] = flush_pending
    bpy.app.timers.register(flush_pending, first_interval=0.05)
    return True


def queue_vehicle_live_update(scene, *, rebuild=False):
    """Queues an edit for the built vehicle preview"""
    vehicle = getattr(scene, "physx_vehicle", None)
    if vehicle is None:
        return False
    if not vehicle.preview_built:
        vehicle.preview_dirty = True
        return False
    if vehicle.preview_dirty:
        return False
    if rebuild:
        vehicle.live_rebuild_pending = True
    else:
        vehicle.live_update_pending = True
    vehicle.live_update_error = ""
    physx = getattr(scene, "physx", None)
    if physx is not None and physx.sim_running:
        vehicle.preview_message = "Live changes queued for the next simulation step"
        return True
    vehicle.preview_message = "Live changes queued"
    return _schedule_vehicle_live_update(scene)


def build_vehicle(context, bridge=None):
    """Builds the native vehicle from the current authoring values"""
    vehicle = context.scene.physx_vehicle
    errors, warnings = validate_vehicle(vehicle)
    if errors:
        raise ValueError("; ".join(errors))
    bridge = bridge or require_initialized_bridge(context)
    if vehicle.source_mode == "RIG" and getattr(vehicle, "rig", None) is not None:
        from ...blender.physics.vehicle_phys import adopt_loaded_vehicle_phys

        adopt_loaded_vehicle_phys(context, vehicle.rig)

    state = _runtime(context.scene)
    root = vehicle_root(vehicle)
    wheel_fields = _wheel_fields(vehicle)
    state.source_mode = vehicle.source_mode
    state.chassis = root
    state.chassis_world = root.matrix_world.copy()
    if vehicle.source_mode == "RIG":
        state.wheels = {
            field: getattr(vehicle, f"{field}_bone", "")
            for field, _label in wheel_fields
        }
        state.wheel_relative = {}
        state.rig_drive = capture_vehicle_rig(
            root,
            state.wheels,
            {
                field: getattr(vehicle, f"{field}_suspension_bone", "")
                for field, _label in wheel_fields
            },
            basis_matrix(vehicle),
            {
                field
                for field in state.wheels
                if field.startswith(("front_", "bike_front"))
            },
        )
    else:
        state.wheels = {
            field: getattr(vehicle, field) for field, _label in wheel_fields
        }
        chassis_inverse = root.matrix_world.inverted_safe()
        state.wheel_relative = {
            field: chassis_inverse @ wheel.matrix_world
            for field, wheel in state.wheels.items()
        }
        state.rig_drive = None
    handle = _build_native_vehicle(context.scene, bridge, state)
    vehicle.preview_message = (
        "Vehicle preview ready"
        if not warnings
        else "Vehicle preview ready; " + "; ".join(warnings)
    )
    return handle, warnings


def _wheel_fields(vehicle):
    if getattr(vehicle, "vehicle_kind", "CAR") == "BIKE":
        return (("bike_front", "Front"), ("bike_rear", "Rear"))
    return WHEEL_FIELDS


def _rebuild_vehicle_in_place(scene, bridge):
    """Rebuilds the native vehicle where it is now, keeping its motion"""
    state = _runtime(scene, create=False)
    if state is None or state.handle <= 0 or state.chassis is None:
        raise RuntimeError("Build the vehicle preview before changing its collider")
    dynamic_state = bridge.get_vehicle_dynamic_state()
    posed_wheels = {}
    if state.source_mode != "RIG":
        # Wheel centres are read from the wheel objects, so they return to rest for the build.
        posed_wheels = {
            field: wheel.matrix_world.copy() for field, wheel in state.wheels.items()
        }
        _place_wheels(state, state.chassis.matrix_world)
    try:
        return _build_native_vehicle(scene, bridge, state, dynamic_state=dynamic_state)
    finally:
        for field, matrix in posed_wheels.items():
            state.wheels[field].matrix_world = matrix


def _build_native_vehicle(scene, bridge, state, *, dynamic_state=None):
    """Builds the native vehicle at the chassis's current placement"""
    vehicle = scene.physx_vehicle
    rebuilding = dynamic_state is not None
    build_info = validate_vehicle_bridge_contract(bridge)
    _log_bridge_build_info(build_info)
    validate_gears(
        collection_gears(vehicle),
        max_forward_gears=PHYSX_MAX_FORWARD_GEARS,
        vehicle=vehicle,
    )

    is_bike = getattr(vehicle, "vehicle_kind", "CAR") == "BIKE"
    if is_bike:
        from ..blender.vehicle_authoring_state import bike_vehicle_config

        config = bike_vehicle_config(vehicle)
    else:
        config = vehicle_config(vehicle)
    wheel_fields = _wheel_fields(vehicle)

    def _has_traction_curves(payload):
        return bool(payload.get("tire_long_traction_front")) and bool(
            payload.get("tire_lat_traction_front")
        )

    if bool(
        build_info.get("vehicle_cp77_traction_required", False)
    ) and not _has_traction_curves(config):
        raise RuntimeError(
            "Vehicle preview traction data is missing. The resolver should provide "
            "either exported REDengine curves or the bundled generic preview profile."
        )

    chassis_shapes = config.get("chassis_shapes") or ()
    if chassis_shapes and not bool(build_info.get("vehicle_chassis_shapes", False)):
        raise RuntimeError(
            "The loaded chassis .phys requires PxBridge vehicle chassis-shape support; rebuild both Blender ABI slots from the packaged native source"
        )
    _LOG.debug(
        "Vehicle preview native config: kind=%s chassis_shapes=%d live_dynamics=%s",
        config.get("vehicle_kind", "CAR"),
        len(chassis_shapes),
        bool(build_info.get("vehicle_live_dynamics", False)),
    )
    curve_counts = {
        key: len(config.get(key) or ())
        for key in (
            "tire_long_traction_front",
            "tire_long_traction_rear",
            "tire_lat_traction_front",
            "tire_lat_traction_rear",
            "tire_long_to_lat_front",
            "tire_long_to_lat_rear",
            "tire_lat_to_long_front",
            "tire_lat_to_long_rear",
        )
    }
    if not any(curve_counts.values()):
        _LOG.warning("Vehicle tire traction curves are unavailable")
    elif not rebuilding:
        _LOG.debug(
            "Vehicle tire curves (%s): long=%d/%d lat=%d/%d long_to_lat=%d/%d lat_to_long=%d/%d surface_mul=%.3f/%.3f",
            str(config.get("traction_curve_source", "unknown")),
            curve_counts["tire_long_traction_front"],
            curve_counts["tire_long_traction_rear"],
            curve_counts["tire_lat_traction_front"],
            curve_counts["tire_lat_traction_rear"],
            curve_counts["tire_long_to_lat_front"],
            curve_counts["tire_long_to_lat_rear"],
            curve_counts["tire_lat_to_long_front"],
            curve_counts["tire_lat_to_long_rear"],
            float(config.get("surface_friction_long_multiplier", 1.0)),
            float(config.get("surface_friction_lateral_multiplier", 1.0)),
        )
    root = state.chassis
    state.basis = basis_matrix(vehicle)
    state.basis_inverse = state.basis.inverted_safe()
    state.chassis_shape_offset = Vector(vehicle.chassis_shape_offset)
    state.chassis_origin_translation = Matrix.Translation(-state.chassis_shape_offset)
    state.chassis_scale = root.matrix_world.to_scale()
    state.chassis_scale_matrix = _scale_matrix(state.chassis_scale)
    from ...blender.physics.vehicle_chassis import vehicle_chassis_phys_objects

    state.chassis_phys_objects = vehicle_chassis_phys_objects(
        scene, getattr(vehicle, "rig", None)
    )
    chassis_phys_set = set(state.chassis_phys_objects or ())
    for item in scene.physx.actors:
        if item.obj_ref in chassis_phys_set:
            item.actor_handle = "0"
    actor_frame_world = matrix_from_pose(config["pose"])
    wheel_centers = config["wheel_centers"]
    steer_angles = config.get("steer_angles") or (0.0,)
    state.max_steer = max(float(value) for value in steer_angles)
    # Maps each native wheel frame onto the rest placement of the wheel it drives.
    if state.source_mode == "RIG":
        rest_world = {
            field: root.matrix_world @ state.rig_drive.rest[bone_name]
            for field, bone_name in state.wheels.items()
        }
    else:
        rest_world = {
            field: wheel.matrix_world.copy() for field, wheel in state.wheels.items()
        }
    state.wheel_visual_corrections = {
        field: (
            actor_frame_world @ Matrix.Translation(Vector(wheel_centers[index]))
        ).inverted_safe()
        @ rest_world[field]
        for index, (field, _label) in enumerate(wheel_fields)
    }
    state.last_stats = {}
    state.last_telemetry_log_time = 0.0
    state.telemetry_invalid_reported = False
    if rebuilding:
        config["dynamic_state"] = dynamic_state
    else:
        state.step_time_accumulator = 0.0
        _log_suspension_budget(scene, state, config)

    build_started = perf_counter()
    handle = int(bridge.build_vehicle(config))
    build_elapsed = perf_counter() - build_started
    if handle <= 0:
        raise RuntimeError("PxBridge did not return a valid vehicle handle")
    (_LOG.debug if rebuilding else _LOG.info)(
        "Vehicle native %s complete: handle=%d kind=%s wheels=%d chassis_shapes=%d elapsed=%.3fs",
        "rebuild" if rebuilding else "build",
        handle,
        config.get("vehicle_kind", "CAR"),
        len(wheel_centers),
        len(chassis_shapes),
        build_elapsed,
    )
    if not rebuilding:
        try:
            initial_stats = bridge.get_stats()
        except Exception as error:
            _LOG.warning(
                "Vehicle initial telemetry unavailable: %s", error, exc_info=True
            )
        else:
            if isinstance(initial_stats, dict):
                state.last_stats = initial_stats
                _log_wheel_telemetry(
                    state, initial_stats, len(wheel_centers), initial=True
                )
    state.handle = handle
    vehicle.vehicle_handle = str(handle)
    vehicle.preview_built = True
    vehicle.preview_dirty = False
    vehicle.live_update_supported = _live_tuning_supported(bridge)
    vehicle.live_update_pending = False
    vehicle.live_rebuild_pending = False
    vehicle.live_update_error = ""
    return handle


def build_vehicle_if_enabled(context, bridge):
    vehicle = getattr(context.scene, "physx_vehicle", None)
    if vehicle is None or not vehicle.enabled:
        clear_vehicle_runtime(context.scene)
        return 0, []
    return build_vehicle(context, bridge)


def vehicle_step_schedule(scene, elapsed):
    """(step count, step length) that advance a built vehicle preview by elapsed seconds"""
    vehicle = getattr(scene, "physx_vehicle", None)
    state = _runtime(scene, create=False)
    if (
        vehicle is None
        or state is None
        or not vehicle.preview_built
        or state.handle <= 0
    ):
        return None
    count, state.step_time_accumulator = fixed_step_count(
        state.step_time_accumulator, elapsed, VEHICLE_FIXED_TIME_STEP
    )
    return count, VEHICLE_FIXED_TIME_STEP


def apply_vehicle_inputs(context, bridge, dt):
    vehicle = getattr(context.scene, "physx_vehicle", None)
    if vehicle is None or not vehicle.preview_built:
        return
    # The authored steering is positive to the right; the native vehicle turns left for a positive steer.
    bridge.update_inputs(
        float(vehicle.throttle),
        float(vehicle.brake),
        -float(vehicle.steer),
        float(vehicle.handbrake),
        float(dt),
    )


def _pose_lookup(poses, handle):
    if not poses or not handle:
        return None
    return poses.get(str(handle), poses.get(handle))


def _sync_native_wheel_poses(state, actor_world, wheel_poses):
    wheel_fields = state.wheels or {}
    if not isinstance(wheel_poses, (list, tuple)) or len(wheel_poses) != len(
        wheel_fields
    ):
        return False
    corrections = state.wheel_visual_corrections or {}
    if len(corrections) != len(wheel_fields):
        return False

    targets = {}
    for index, field in enumerate(wheel_fields):
        values = wheel_poses[index]
        if not isinstance(values, (list, tuple)) or len(values) != 7:
            return False
        targets[field] = actor_world @ matrix_from_pose(values) @ corrections[field]
    if state.source_mode == "RIG":
        chassis_inverse = state.chassis.matrix_world.inverted_safe()
        state.steering_input = pose_vehicle_rig(
            state.rig_drive,
            {field: chassis_inverse @ target for field, target in targets.items()},
            state.max_steer,
        )
        return True
    for field, target in targets.items():
        wheel = wheel_fields.get(field)
        if wheel is not None:
            wheel.matrix_world = target
    return True


def sync_vehicle_preview(context, bridge, poses, _dt):
    vehicle = getattr(context.scene, "physx_vehicle", None)
    state = _runtime(context.scene, create=False)
    if (
        vehicle is None
        or state is None
        or not vehicle.preview_built
        or state.handle <= 0
    ):
        return
    stats = bridge.get_stats()
    if not isinstance(stats, dict):
        stats = {}
    pose = _pose_lookup(poses, state.handle) or stats.get("pose")
    if pose is None:
        return

    vehicle_frame_world = matrix_from_pose(pose)
    origin_frame_world = vehicle_frame_world @ state.chassis_origin_translation
    chassis_world = (
        origin_frame_world @ state.basis_inverse @ state.chassis_scale_matrix
    )
    state.chassis.matrix_world = chassis_world

    state.last_stats = stats
    vehicle.forward_speed = float(stats.get("forward_speed", 0.0))
    vehicle.sideways_speed = float(stats.get("sideways_speed", 0.0))
    vehicle.engine_omega = float(stats.get("engine_omega", 0.0))
    linear_velocity = stats.get("linear_velocity", (0.0, 0.0, 0.0))
    angular_velocity = stats.get("angular_velocity", (0.0, 0.0, 0.0))
    if isinstance(linear_velocity, (list, tuple)) and len(linear_velocity) >= 3:
        vehicle.linear_velocity = tuple(float(value) for value in linear_velocity[:3])
    if isinstance(angular_velocity, (list, tuple)) and len(angular_velocity) >= 3:
        vehicle.angular_velocity = tuple(float(value) for value in angular_velocity[:3])
    vehicle.current_gear = int(stats.get("current_gear", 0))
    vehicle.target_gear = int(stats.get("target_gear", vehicle.current_gear))
    vehicle.vehicle_in_air = bool(stats.get("vehicle_in_air", False))
    vehicle.bike_lean = float(stats.get("bike_lean", 0.0))
    vehicle.bike_target_lean = float(stats.get("bike_target_lean", 0.0))
    telemetry_fields = (
        ("wheel_contact_strength", "wheel_contact_strengths"),
        ("wheel_compression", "wheel_compressions"),
        ("wheel_suspension_velocity", "wheel_suspension_velocities"),
        ("wheel_spring_force", "wheel_spring_forces"),
        ("wheel_normal_load", "wheel_normal_loads"),
        ("wheel_longitudinal_slip", "wheel_longitudinal_slips"),
        ("wheel_lateral_slip", "wheel_lateral_slips"),
        ("wheel_longitudinal_force", "wheel_longitudinal_forces"),
        ("wheel_lateral_force", "wheel_lateral_forces"),
        ("wheel_effective_friction", "wheel_effective_frictions"),
    )
    wheel_count = 2 if vehicle.vehicle_kind == "BIKE" else 4
    telemetry_invalid = False
    for property_name, stats_name in telemetry_fields:
        values, invalid = _telemetry_values(stats, stats_name, wheel_count)
        telemetry_invalid = telemetry_invalid or invalid
        packed = values + [0.0] * (4 - wheel_count)
        setattr(vehicle, property_name, tuple(packed[:4]))
    if telemetry_invalid and not state.telemetry_invalid_reported:
        state.telemetry_invalid_reported = True
        _LOG.warning(
            "Vehicle wheel telemetry contained non-finite values; invalid display values were replaced with zero"
        )
    _log_wheel_telemetry(state, stats, wheel_count)

    if not _sync_native_wheel_poses(
        state, vehicle_frame_world, stats.get("wheel_poses")
    ):
        raise RuntimeError("PxBridge did not return authoritative vehicle wheel poses")
    update_vehicle_camera(context.scene, _dt)


def handle_vehicle_event(context, event):
    vehicle = getattr(context.scene, "physx_vehicle", None)
    if vehicle is None or not vehicle.preview_built:
        return False
    value = event.value
    pressed = value in {"PRESS", "REPEAT"}
    released = value == "RELEASE"
    if event.type == "W":
        vehicle.throttle = 1.0 if pressed else (0.0 if released else vehicle.throttle)
        return True
    if event.type == "S":
        vehicle.brake = 1.0 if pressed else (0.0 if released else vehicle.brake)
        return True
    if event.type == "A":
        vehicle.steer = (
            -1.0
            if pressed
            else (0.0 if released and vehicle.steer < 0.0 else vehicle.steer)
        )
        return True
    if event.type == "D":
        vehicle.steer = (
            1.0
            if pressed
            else (0.0 if released and vehicle.steer > 0.0 else vehicle.steer)
        )
        return True
    if event.type == "SPACE":
        vehicle.handbrake = 1.0 if pressed else (0.0 if released else vehicle.handbrake)
        return True
    return False


def clear_vehicle_inputs(context):
    vehicle = getattr(context.scene, "physx_vehicle", None)
    if vehicle is None:
        return
    vehicle.throttle = 0.0
    vehicle.brake = 0.0
    vehicle.steer = 0.0
    vehicle.handbrake = 0.0


def reset_vehicle_preview(context, restore=True):
    vehicle = context.scene.physx_vehicle
    clear_vehicle_runtime(context.scene, restore=restore)
    vehicle.vehicle_handle = "0"
    vehicle.preview_built = False
    vehicle.preview_dirty = True
    vehicle.preview_message = ""
    vehicle.live_update_supported = False
    vehicle.live_update_pending = False
    vehicle.live_rebuild_pending = False
    vehicle.live_update_error = ""
    clear_vehicle_inputs(context)
    snap_vehicle_camera(context.scene)
    vehicle.forward_speed = 0.0
    vehicle.sideways_speed = 0.0
    vehicle.engine_omega = 0.0
    vehicle.linear_velocity = (0.0, 0.0, 0.0)
    vehicle.angular_velocity = (0.0, 0.0, 0.0)
    vehicle.current_gear = 0
    vehicle.target_gear = 0
    vehicle.vehicle_in_air = False
    vehicle.bike_lean = 0.0
    vehicle.bike_target_lean = 0.0
    for property_name in (
        "wheel_contact_strength",
        "wheel_compression",
        "wheel_suspension_velocity",
        "wheel_spring_force",
        "wheel_normal_load",
        "wheel_longitudinal_slip",
        "wheel_lateral_slip",
        "wheel_longitudinal_force",
        "wheel_lateral_force",
        "wheel_effective_friction",
    ):
        setattr(vehicle, property_name, (0.0, 0.0, 0.0, 0.0))
