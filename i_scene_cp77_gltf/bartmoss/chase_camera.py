from __future__ import annotations

import math
from dataclasses import dataclass, field

from .scalar import linear_step_scalar
from .vector3 import add3, dot3, length3, scale3, sub3

_UP = (0.0, 0.0, 1.0)


def _horizontal(a, fallback=(0.0, -1.0, 0.0)):
    length = math.hypot(a[0], a[1])
    if length <= 1.0e-6:
        return fallback
    return (a[0] / length, a[1] / length, 0.0)


def _rotate_about_up(a, degrees):
    angle = math.radians(degrees)
    cosine, sine = math.cos(angle), math.sin(angle)
    return (a[0] * cosine - a[1] * sine, a[0] * sine + a[1] * cosine, a[2])


def _normalize_degrees(angle):
    return (angle + 180.0) % 360.0 - 180.0


def _proportional(value, low, high, at_low, at_high):
    """at_low at or below low, at_high at or above high, linear between"""
    if high < low:
        return at_high if value >= high else at_low
    return at_low + (at_high - at_low) * linear_step_scalar(low, high, value)


def critical_damp(current, target, velocity, smooth_time, dt):
    """One critically damped spring step of a scalar towards target"""
    if smooth_time <= 0.0:
        return target, 0.0
    omega = 2.0 / smooth_time
    x = omega * dt
    decay = 1.0 / (1.0 + x + 0.48 * x * x + 0.235 * x * x * x)
    difference = current - target
    temp = (velocity + difference * omega) * dt
    return target + (difference + temp) * decay, (velocity - temp * omega) * decay


def _critical_damp_vector(current, target, velocity, smooth_time, dt):
    pairs = [
        critical_damp(current[i], target[i], velocity[i], smooth_time, dt)
        for i in range(3)
    ]
    return tuple(pair[0] for pair in pairs), tuple(pair[1] for pair in pairs)


@dataclass(frozen=True, slots=True)
class ChaseCameraPreset:
    look_at_offset: tuple
    pitch: float
    boom_length: float


@dataclass(slots=True)
class ChaseCameraState:
    position: tuple
    base_position: tuple
    look_at: tuple
    boom_length: float
    pitch: float
    inactive_fade: float = 0.0
    speed: float = 0.0
    speed_rate: float = 0.0
    camera_speed: float = 0.0
    camera_speed_rate: float = 0.0
    speed_delta: float = 0.0
    speed_delta_rate: float = 0.0
    last_camera_speed: float = 0.0
    linear_velocity: tuple = (0.0, 0.0, 0.0)
    linear_velocity_rate: tuple = (0.0, 0.0, 0.0)
    angular_velocity: tuple = (0.0, 0.0, 0.0)
    angular_velocity_rate: tuple = (0.0, 0.0, 0.0)
    boom_direction: tuple = field(default=(0.0, -1.0, 0.0))


def chase_camera_look_at(vehicle_position, vehicle_forward, look_at_offset):
    """The look-at point"""
    forward = _horizontal(vehicle_forward, (0.0, 1.0, 0.0))
    right = (forward[1], -forward[0], 0.0)
    return add3(
        vehicle_position,
        add3(
            add3(scale3(right, look_at_offset[0]), scale3(forward, look_at_offset[1])),
            scale3(_UP, look_at_offset[2]),
        ),
    )


def _pitched(direction_xy, pitch):
    angle = math.radians(pitch)
    return add3(scale3(direction_xy, math.cos(angle)), scale3(_UP, math.sin(angle)))


def reset_chase_camera(
    preset,
    vehicle_position,
    vehicle_forward,
    linear_velocity=(0.0, 0.0, 0.0),
    in_air=False,
):
    """A camera behind the vehicle, or in front of it while it reverses"""
    heading = _horizontal(vehicle_forward, (0.0, 1.0, 0.0))
    move_direction = 1.0
    planar_velocity = (linear_velocity[0], linear_velocity[1], 0.0)
    if not in_air and length3(planar_velocity) >= 0.5:
        move_direction = 1.0 if dot3(heading, planar_velocity) >= 0.0 else -1.0
    boom_xy = scale3(heading, -move_direction)
    look_at = chase_camera_look_at(
        vehicle_position, vehicle_forward, preset.look_at_offset
    )
    position = add3(
        look_at, scale3(_pitched(boom_xy, preset.pitch), preset.boom_length)
    )
    return ChaseCameraState(
        position=position,
        base_position=position,
        look_at=look_at,
        boom_length=preset.boom_length,
        pitch=preset.pitch,
        boom_direction=boom_xy,
    )


def _driving_direction_compensation(state, params, boom_xy, vehicle_forward):
    """Yaw, in degrees, that turns the boom back behind the direction of travel this update"""
    speed = max(state.speed - params["drivingDirectionCompensationSpeedMin"], 0.0)
    speed_range = (
        params["drivingDirectionCompensationSpeedMax"]
        - params["drivingDirectionCompensationSpeedMin"]
    )
    speed_coef = min(max(speed / speed_range, 0.0), 1.0) if speed_range > 0.0 else 1.0
    heading = _horizontal(vehicle_forward, (0.0, 1.0, 0.0))
    velocity = state.linear_velocity
    move_direction = 1.0 if dot3(velocity, heading) >= 0.0 else -1.0
    wanted = scale3(heading, -move_direction)
    correct_angle = params["drivingDirectionCompensationAngle"]
    total_angle = min(
        max(correct_angle + params["drivingDirectionCompensationAngleSmooth"], 0.0),
        360.0,
    )
    off_angle = math.degrees(
        math.acos(min(max(dot3(wanted, scale3(boom_xy, -1.0)), -1.0), 1.0))
    )
    if off_angle >= total_angle:
        return 0.0
    angle_coef = _proportional(off_angle, correct_angle, total_angle, 1.0, 0.0)
    yaw_rate = abs(math.degrees(state.angular_velocity[2]))
    angular_coef = _proportional(
        yaw_rate,
        0.0,
        max(params["drivingDirectionCompensationAngularVelocityMin"], 1.0e-6),
        1.0,
        0.0,
    )
    difference = _normalize_degrees(
        math.degrees(
            math.atan2(wanted[1], wanted[0]) - math.atan2(boom_xy[1], boom_xy[0])
        )
    )
    coef = (
        params["drivingDirectionCompensationSpeedCoef"]
        * speed_coef
        * angular_coef
        * angle_coef
        * angular_coef
        * state.inactive_fade
    )
    return min(max(difference * coef, -abs(difference)), abs(difference))


def step_chase_camera(
    state,
    preset,
    params,
    vehicle_position,
    vehicle_forward,
    linear_velocity,
    angular_velocity,
    dt,
    *,
    in_air=False,
    smooth_time=0.1,
):
    """Advances the camera by dt seconds and returns the state"""
    if dt <= 0.0:
        return state
    look_at = chase_camera_look_at(
        vehicle_position, vehicle_forward, preset.look_at_offset
    )

    camera_forward = _horizontal(sub3(look_at, state.position), (0.0, 1.0, 0.0))
    camera_speed = dot3(linear_velocity, camera_forward)
    camera_speed = 0.0 if camera_speed < 0.01 else camera_speed
    state.camera_speed, state.camera_speed_rate = critical_damp(
        state.camera_speed, camera_speed, state.camera_speed_rate, smooth_time, dt
    )
    speed = length3(linear_velocity)
    speed = 0.0 if speed < 0.1 else speed
    state.speed, state.speed_rate = critical_damp(
        state.speed, speed, state.speed_rate, smooth_time, dt
    )
    linear_target = (
        linear_velocity
        if max(abs(v) for v in linear_velocity) > 0.1
        else (0.0, 0.0, 0.0)
    )
    state.linear_velocity, state.linear_velocity_rate = _critical_damp_vector(
        state.linear_velocity,
        linear_target,
        state.linear_velocity_rate,
        smooth_time,
        dt,
    )
    angular_target = (
        angular_velocity
        if max(abs(v) for v in angular_velocity) > 0.1
        else (0.0, 0.0, 0.0)
    )
    state.angular_velocity, state.angular_velocity_rate = _critical_damp_vector(
        state.angular_velocity,
        angular_target,
        state.angular_velocity_rate,
        smooth_time,
        dt,
    )
    state.speed_delta, state.speed_delta_rate = critical_damp(
        state.speed_delta,
        state.camera_speed - state.last_camera_speed,
        state.speed_delta_rate,
        smooth_time,
        dt,
    )
    state.last_camera_speed = state.camera_speed

    # The pitch returns to the preset pitch, faster at speed; the boom then follows its own trail.
    center_coef = (
        dt
        * params["autoCenterSpeed"]
        * min(
            max(state.speed / max(params["autoCenterMaxSpeedThreshold"], 1.0e-6), 0.0),
            1.0,
        )
    )
    center_coef = min(max(center_coef, 0.0), 1.0)
    state.pitch += _normalize_degrees(preset.pitch - state.pitch) * center_coef
    if state.inactive_fade == 0.0:
        state.base_position = state.position
    state.inactive_fade = min(max(state.inactive_fade + center_coef, 0.0), 1.0)

    boom_xy = _horizontal(sub3(state.base_position, look_at), state.boom_direction)
    compensation = 0.0
    if not in_air and params["drivingDirectionCompensation"]:
        compensation = _driving_direction_compensation(
            state, params, boom_xy, vehicle_forward
        )
    boom_xy = _rotate_about_up(boom_xy, compensation)
    state.boom_direction = boom_xy
    direction = _pitched(boom_xy, state.pitch)

    target_length = preset.boom_length
    if params["elasticBoomAcceleration"]:
        delta = state.speed_delta
        if delta > 0.0:
            delta *= params["elasticBoomForwardAccelerationCoef"]
        target_length += params["elasticBoomAccelerationExpansionLength"] * min(
            max(delta, -1.0), 1.0
        )
    if (
        params["elasticBoomVelocity"]
        and state.camera_speed >= params["elasticBoomSpeedExpansionSpeedMin"]
    ):
        target_length += params["elasticBoomSpeedExpansionLength"] * _proportional(
            state.camera_speed,
            params["elasticBoomSpeedExpansionSpeedMin"],
            params["elasticBoomSpeedExpansionSpeedMax"],
            0.0,
            1.0,
        )

    state.base_position = add3(look_at, scale3(direction, state.boom_length))
    state.boom_length += (
        (target_length - state.boom_length) * params["cameraBoomExtensionSpeed"] * dt
    )
    state.position = add3(look_at, scale3(direction, state.boom_length))
    state.look_at = look_at
    return state
