from __future__ import annotations

import math

from ....assetio.names import cname_hash
from ....bartmoss.quaternion import shortest_rotation_scalar_xyzw
from ....redSpace.euler import euler_from_xyzw


def float_math(operation: str, first: float, second: float) -> float:
    op = str(operation or "AGMO_Add").split("::")[-1]
    if op in {"AGMO_Add", "Add"}:
        return first + second
    if op in {"AGMO_Subtract", "Subtract"}:
        return first - second
    if op in {"AGMO_Multiply", "Multiply"}:
        return first * second
    if op in {"AGMO_Divide", "Divide"}:
        epsilon = 1.1920928955078125e-07
        denominator = float(second)
        if abs(denominator) < epsilon:
            denominator = math.copysign(epsilon, denominator)
        return first / denominator
    if op in {"AGMO_SafeDivide", "SafeDivide"}:
        epsilon = 1.1920928955078125e-07
        return first / second if abs(second) >= epsilon else 0.0
    if op in {"AGMO_ATan", "ATan"}:
        return math.atan2(first, second) / math.pi
    if op in {"AGMO_AngleDiff", "AngleDiff"}:
        value = first - second
        while value > 1.0:
            value -= 2.0
        while value < -1.0:
            value += 2.0
        return value
    if op in {"AGMO_Length", "Length"}:
        return math.sqrt(first * first + second * second)
    if op in {"AGMO_Abs", "Abs"}:
        return abs(first)
    raise ValueError(f"unsupported float math operation {operation!r}")


def float_compare(compare_func: str, first: float, second: float) -> bool:
    op = str(compare_func or "Equal").split("::")[-1]
    if op in {"Equal", "AGCF_Equal"}:
        return first == second
    if op in {"NotEqual", "AGCF_NotEqual"}:
        return first != second
    if op in {"Less", "AGCF_Less"}:
        return first < second
    if op in {"LessEqual", "AGCF_LessEqual"}:
        return first <= second
    if op in {"Greater", "AGCF_Greater"}:
        return first > second
    if op in {"GreaterEqual", "AGCF_GreaterEqual"}:
        return first >= second
    raise ValueError(f"unsupported float compare function {compare_func!r}")


def damp_step(
    current: float,
    target: float,
    dt: float,
    *,
    increase_speed: float,
    decrease_speed: float,
    range_min: float | None = None,
    range_max: float | None = None,
) -> float:
    target = float(target)
    current = float(current)
    span = None
    if range_min is not None and range_max is not None and range_max > range_min:
        span = float(range_max) - float(range_min)
        delta = target - current
        half = span * 0.5
        if delta > half:
            delta -= span
        elif delta < -half:
            delta += span
        target = current + delta
    delta = target - current
    speed = float(increase_speed if delta >= 0.0 else decrease_speed)
    if speed <= 0.0:
        result = target
    else:
        step = speed * max(0.0, float(dt))
        result = target if abs(delta) <= step else current + math.copysign(step, delta)
    if span is not None:
        lo = float(range_min)
        result = lo + ((result - lo) % span)
    return result


def critical_spring_step(
    value: float,
    velocity: float,
    target: float,
    dt: float,
    *,
    frequency: float,
) -> tuple[float, float]:
    dt = max(0.0, float(dt))
    omega = max(0.0, float(frequency)) * 2.0 * math.pi
    if dt <= 0.0:
        return float(value), float(velocity)
    if omega <= 1e-8:
        return float(target), 0.0
    displacement = float(value) - float(target)
    decay = math.exp(-omega * dt)
    c = float(velocity) + omega * displacement
    new_displacement = (displacement + c * dt) * decay
    new_velocity = (float(velocity) - omega * c * dt) * decay
    return float(target) + new_displacement, new_velocity


def slot_name_hash(name) -> int:
    """A name's 32-bit slot hash"""
    full = cname_hash(name)
    folded = ((full >> 32) ^ full) & 0xFFFFFFFF
    return folded - (1 << 32) if folded >= 1 << 31 else folded


def signal_initial(
    default_state: bool, blend_in: float, blend_out: float, cooldown: float
):
    """(signaled, blend time, cooldown timer) of a Signal node when it activates"""
    signaled = bool(default_state)
    return signaled, float(blend_in if signaled else blend_out), float(cooldown)


def signal_step(
    state,
    dt: float,
    *,
    started: bool,
    ended: bool,
    blend_in: float,
    blend_out: float,
    cooldown: float,
):
    """Advance a Signal node"""
    signaled, progress, timer = state
    if signaled:
        progress = min(max(progress + dt, 0.0), blend_in)
        use_cooldown = cooldown > 0.0
        if ended or (use_cooldown and timer <= 0.0):
            signaled = False
            progress = (
                (1.0 - progress / blend_in) * blend_out if blend_in > 0.0 else 0.0
            )
        elif use_cooldown:
            timer -= dt
    else:
        progress = min(max(progress + dt, 0.0), blend_out)
        if started:
            signaled = True
            progress = (
                (1.0 - progress / blend_out) * blend_in if blend_in > 0.0 else 0.0
            )
            timer = cooldown
    return signaled, progress, timer


def signal_value(state, blend_in: float, blend_out: float) -> float:
    signaled, progress, _timer = state
    if signaled:
        return min(max(progress / blend_in, 0.0), 1.0) if blend_in > 0.0 else 1.0
    return min(max(1.0 - progress / blend_out, 0.0), 1.0) if blend_out > 0.0 else 0.0


def wrap_to_range(value: float, range_min: float, range_max: float) -> float:
    span = float(range_max) - float(range_min)
    if span > 1.1920929e-07:
        return value - span * math.floor((value - range_min) / span)
    return float(range_min)


def spring_damp_step(
    value: float,
    speed: float,
    target: float,
    dt: float,
    *,
    mass: float,
    spring: float,
    damp: float,
    time_step: float,
    wrap: bool,
    range_min: float,
    range_max: float,
):
    """Advance a SpringDamp node in fixed time steps plus a remainder step toward target"""

    def step(value, speed, step_dt):
        distance = target - value
        if wrap:
            if abs(distance) < 1.1920929e-07:
                distance = 0.0
            else:
                span = range_max - range_min
                alternative = (
                    target - span if distance > 0.0 else target + span
                ) - value
                distance = distance if abs(distance) < abs(alternative) else alternative
        acceleration = -(damp * speed - spring * distance) / mass
        speed += acceleration * 0.5 * step_dt
        value += speed * step_dt
        return (wrap_to_range(value, range_min, range_max) if wrap else value), speed

    steps = math.floor(dt / time_step)
    for _ in range(int(steps)):
        value, speed = step(value, speed, time_step)
    return step(value, speed, dt - steps * time_step)


def clamp_degrees(value: float) -> float:
    """An angle in degrees brought into [-180, 180]"""
    wrapped = math.fmod(float(value) + 180.0, 360.0)
    if wrapped < 0.0:
        wrapped += 360.0
    return wrapped - 180.0


def time_dependent_sinus(
    time_seconds: float, minimum: float, maximum: float, frequency: float, phase: float
) -> float:
    period = 2.0 * math.pi / frequency
    middle = (minimum + maximum) / 2.0
    return (
        math.sin(time_seconds * frequency + phase * period) * (maximum - minimum) / 2.0
        + middle
    )


def direction_to_euler(direction, forward, conversion: str) -> float:
    """The pitch, yaw or roll (degrees) of the shortest rotation from forward to direction"""
    direction = tuple(float(v) for v in direction[:3])
    if all(abs(v) < 1e-6 for v in direction):
        return 0.0
    length = math.sqrt(sum(v * v for v in direction))
    direction = tuple(v / length for v in direction)
    forward = tuple(float(v) for v in forward[:3])
    forward_length = math.sqrt(sum(v * v for v in forward))
    forward = (
        tuple(v / forward_length for v in forward) if forward_length > 0.0 else forward
    )
    if all(abs(a + b) < 1e-6 for a, b in zip(direction, forward)):
        return 180.0
    pitch, roll, yaw = euler_from_xyzw(
        shortest_rotation_scalar_xyzw(forward, direction)
    )
    return {"Pitch": pitch, "Yaw": yaw, "Roll": roll}.get(
        str(conversion).split("::")[-1], pitch
    )


def map_range_clamped(
    value: float, x1: float, x2: float, y1: float, y2: float
) -> float:
    """value mapped linearly from [x1, x2] onto [y1, y2] and kept inside the y range"""
    span = float(x2) - float(x1)
    if abs(span) < 1.1920929e-07:
        return 0.0
    mapped = float(y1) + (float(value) - float(x1)) * (float(y2) - float(y1)) / span
    return min(max(mapped, min(y1, y2)), max(y1, y2))


def clamp_to_range(
    value: float, clamp_type: str, range_min: float, range_max: float
) -> float:
    """value as a ranged value keeps it"""
    if clamp_type == "None":
        return float(value)
    if clamp_type == "Clamp":
        return min(max(float(value), float(range_min)), float(range_max))
    if clamp_type == "WrappedClamp":
        return wrap_to_range(float(value), range_min, range_max)
    raise ValueError(f"unsupported clamp type {clamp_type!r}")
