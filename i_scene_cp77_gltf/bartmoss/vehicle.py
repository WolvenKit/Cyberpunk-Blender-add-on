from __future__ import annotations

import math
from dataclasses import dataclass

from .scalar import all_finite

STANDARD_GRAVITY = 9.81


@dataclass(frozen=True, slots=True)
class VehicleAxleGeometry:
    wheelbase: float
    front_track: float
    rear_track: float
    front_axle: float
    rear_axle: float


def scale_vehicle_values(
    values, target: float, *, aggregate: str = "mean", preserve_zeros: bool = False
):
    source = tuple(float(value) for value in values)
    target = float(target)
    if not source:
        raise ValueError("Vehicle values cannot be empty")
    if not math.isfinite(target) or target < 0.0:
        raise ValueError("Vehicle value target must be finite and nonnegative")
    if not all_finite(source) or min(source) < 0.0:
        raise ValueError("Vehicle values must be finite and nonnegative")

    active = (
        tuple(index for index, value in enumerate(source) if value > 0.0)
        if preserve_zeros
        else tuple(range(len(source)))
    )
    if not active:
        return list(source)
    if aggregate == "mean":
        reference = sum(source[index] for index in active) / len(active)
    elif aggregate == "max":
        reference = max(source[index] for index in active)
    else:
        raise ValueError("Vehicle value aggregate must be 'mean' or 'max'")
    if reference <= 1.0e-12:
        return [target if index in active else 0.0 for index in range(len(source))]
    scale = target / reference
    return [
        value * scale if index in active else value
        for index, value in enumerate(source)
    ]


def cp77_tire_preview_friction(
    coefficient: float, longitudinal: float, lateral: float
) -> float:
    coefficient = float(coefficient)
    longitudinal = float(longitudinal)
    lateral = float(lateral)
    if not all_finite((coefficient, longitudinal, lateral)):
        raise ValueError("Vehicle tire friction values must be finite")
    if coefficient < 0.0 or longitudinal < 0.0 or lateral < 0.0:
        raise ValueError("Vehicle tire friction values must be nonnegative")
    return coefficient * math.sqrt(longitudinal * lateral)


def cp77_logical_suspension_droop(
    visual_droop: float, suspension_direction_z: float
) -> float:
    visual_droop = float(visual_droop)
    suspension_direction_z = float(suspension_direction_z)
    if not math.isfinite(visual_droop) or visual_droop < 0.0:
        raise ValueError("Visual suspension droop must be finite and nonnegative")
    if not math.isfinite(suspension_direction_z):
        raise ValueError("Suspension direction must be finite")
    if suspension_direction_z <= -0.99:
        return visual_droop
    logical_droop = visual_droop * -suspension_direction_z
    if logical_droop < 0.0:
        raise ValueError("Suspension direction must point downward in vehicle space")
    return logical_droop


def spring_rate_kg_mm_to_strength(
    spring_rate_kg_mm: float,
    logical_spring_length: float,
    gravity: float = STANDARD_GRAVITY,
) -> float:
    spring_rate_kg_mm = float(spring_rate_kg_mm)
    logical_spring_length = float(logical_spring_length)
    gravity = float(gravity)
    if not all_finite((spring_rate_kg_mm, logical_spring_length, gravity)):
        raise ValueError("Vehicle spring conversion values must be finite")
    if spring_rate_kg_mm < 0.0 or logical_spring_length <= 0.0 or gravity <= 0.0:
        raise ValueError(
            "Vehicle spring rate must be nonnegative and length/gravity must be positive"
        )
    spring_force_newtons = (spring_rate_kg_mm / 0.01) * gravity
    return spring_force_newtons / logical_spring_length


def cp77_spring_strength(
    authored_stiffness: float,
    logical_spring_length: float,
    gravity: float = STANDARD_GRAVITY,
) -> float:
    authored_stiffness = float(authored_stiffness)
    if not math.isfinite(authored_stiffness) or authored_stiffness <= 0.0:
        raise ValueError("Vehicle spring stiffness must be finite and positive")
    if authored_stiffness > 300.0:
        return authored_stiffness
    return spring_rate_kg_mm_to_strength(
        authored_stiffness, logical_spring_length, gravity
    )


def cp77_spring_rate_kg_mm(
    spring_strength: float,
    logical_spring_length: float,
    gravity: float = STANDARD_GRAVITY,
) -> float:
    spring_strength = float(spring_strength)
    logical_spring_length = float(logical_spring_length)
    gravity = float(gravity)
    if not all_finite((spring_strength, logical_spring_length, gravity)):
        raise ValueError("Vehicle spring conversion values must be finite")
    if spring_strength < 0.0 or logical_spring_length <= 0.0 or gravity <= 0.0:
        raise ValueError(
            "Vehicle spring strength must be nonnegative and length/gravity must be positive"
        )
    spring_force_newtons = spring_strength * logical_spring_length
    return (spring_force_newtons / gravity) * 0.01


def cp77_variable_damper_coefficient(
    compression: float,
    movement_speed: float,
    bound_high: float,
    rebound_high: float,
    bound_low: float,
    rebound_low: float,
    low_rate_compression: float,
    high_rate_compression: float,
) -> float:
    values = tuple(
        float(value)
        for value in (
            compression,
            movement_speed,
            bound_high,
            rebound_high,
            bound_low,
            rebound_low,
            low_rate_compression,
            high_rate_compression,
        )
    )
    if not all_finite(values):
        raise ValueError("Vehicle damper values must be finite")
    (
        compression,
        movement_speed,
        bound_high,
        rebound_high,
        bound_low,
        rebound_low,
        low_rate_compression,
        high_rate_compression,
    ) = values
    if (
        min(
            compression,
            bound_high,
            rebound_high,
            bound_low,
            rebound_low,
            low_rate_compression,
            high_rate_compression,
        )
        < 0.0
    ):
        raise ValueError("Vehicle damper values must be nonnegative")
    high = rebound_high if movement_speed > 0.0 else bound_high
    if bound_low <= 0.0:
        return high
    low = rebound_low if movement_speed > 0.0 else bound_low
    if high_rate_compression <= low_rate_compression:
        return high if compression >= high_rate_compression else low
    alpha = min(
        max(
            (compression - low_rate_compression)
            / (high_rate_compression - low_rate_compression),
            0.0,
        ),
        1.0,
    )
    return low + (high - low) * alpha


def cp77_extreme_compression(
    previous_compression: float,
    current_compression: float,
    tire_radius: float,
) -> tuple[float, bool]:
    previous_compression = float(previous_compression)
    current_compression = float(current_compression)
    tire_radius = float(tire_radius)
    if not all_finite((previous_compression, current_compression, tire_radius)):
        raise ValueError("Vehicle compression values must be finite")
    if previous_compression < 0.0 or current_compression < 0.0 or tire_radius <= 0.0:
        raise ValueError(
            "Vehicle compression values must be nonnegative and tire radius must be positive"
        )
    delta = current_compression - previous_compression
    tolerance = tire_radius * 0.2
    maximum_delta = tire_radius * 0.5
    extreme = previous_compression > 0.0 and delta > tolerance
    if delta > maximum_delta:
        current_compression = previous_compression + maximum_delta
        extreme = True
    return current_compression, extreme


def fixed_step_count(
    accumulated: float, elapsed: float, step: float
) -> tuple[int, float]:
    """Whole fixed steps that fit in the accumulated plus elapsed time, and the time carried over"""
    step = float(step)
    if not math.isfinite(step) or step <= 0.0:
        raise ValueError("The fixed step must be a positive finite time")
    total = max(float(accumulated), 0.0) + max(float(elapsed), 0.0)
    count = int(total / step)
    remainder = total - count * step
    if remainder >= step:
        count += 1
        remainder -= step
    return count, max(remainder, 0.0)


def steer_angle(rest_axle, axle, up) -> float:
    """Signed rotation about the unit up axis that turns rest_axle into axle"""
    rest_dot = rest_axle[0] * up[0] + rest_axle[1] * up[1] + rest_axle[2] * up[2]
    axle_dot = axle[0] * up[0] + axle[1] * up[1] + axle[2] * up[2]
    a = tuple(rest_axle[index] - up[index] * rest_dot for index in range(3))
    b = tuple(axle[index] - up[index] * axle_dot for index in range(3))
    cross = (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )
    sine = cross[0] * up[0] + cross[1] * up[1] + cross[2] * up[2]
    cosine = a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
    if abs(sine) <= 1.0e-12 and abs(cosine) <= 1.0e-12:
        return 0.0
    return math.atan2(sine, cosine)


def radii_of_gyration(mass: float, inertia) -> tuple[float, float, float]:
    """Distance from each principal axis at which the whole mass gives the same moment of inertia"""
    mass = float(mass)
    if not math.isfinite(mass) or mass <= 0.0:
        raise ValueError("Mass must be finite and positive")
    return tuple(math.sqrt(max(float(value), 0.0) / mass) for value in inertia)


def equivalent_inertia_box(mass: float, inertia) -> tuple[float, float, float]:
    """Half extents of the uniform box with the given mass and principal moments of inertia"""
    mass = float(mass)
    if not math.isfinite(mass) or mass <= 0.0:
        raise ValueError("Mass must be finite and positive")
    ixx, iyy, izz = (float(value) for value in inertia)
    squares = (iyy + izz - ixx, ixx + izz - iyy, ixx + iyy - izz)
    return tuple(0.5 * math.sqrt(max(6.0 * value / mass, 0.0)) for value in squares)


def box_inertia(
    mass: float, half_extents, offset=(0.0, 0.0, 0.0)
) -> tuple[float, float, float]:
    """Principal moments of a uniform box about axes through a point offset from its centre"""
    mass = float(mass)
    x, y, z = (2.0 * float(value) for value in half_extents)
    dx, dy, dz = (float(value) for value in offset)
    return (
        mass * (y * y + z * z) / 12.0 + mass * (dy * dy + dz * dz),
        mass * (x * x + z * z) / 12.0 + mass * (dx * dx + dz * dz),
        mass * (x * x + y * y) / 12.0 + mass * (dx * dx + dy * dy),
    )


def static_wheel_loads(weight: float, wheel_centers, center_of_mass) -> list[float]:
    """Share of the weight each wheel carries at rest"""
    weight = float(weight)
    cx, cy = float(center_of_mass[0]), float(center_of_mass[1])

    def share(value, low, high):
        span = high - low
        return 0.5 if abs(span) <= 1.0e-9 else min(max((value - low) / span, 0.0), 1.0)

    if len(wheel_centers) == 2:
        front = share(cy, wheel_centers[1][1], wheel_centers[0][1])
        return [weight * front, weight * (1.0 - front)]
    fl, fr, rl, rr = wheel_centers
    front = share(cy, 0.5 * (rl[1] + rr[1]), 0.5 * (fl[1] + fr[1]))
    front_right = share(cx, fl[0], fr[0])
    rear_right = share(cx, rl[0], rr[0])
    return [
        weight * front * (1.0 - front_right),
        weight * front * front_right,
        weight * (1.0 - front) * (1.0 - rear_right),
        weight * (1.0 - front) * rear_right,
    ]


def cp77_swaybar_displacements(
    left_compression: float, right_compression: float, displacement_limit: float
) -> tuple[float, float]:
    left_compression = float(left_compression)
    right_compression = float(right_compression)
    displacement_limit = float(displacement_limit)
    if not all_finite((left_compression, right_compression, displacement_limit)):
        raise ValueError("Vehicle sway-bar values must be finite")
    if left_compression < 0.0 or right_compression < 0.0 or displacement_limit < 0.0:
        raise ValueError("Vehicle sway-bar values must be nonnegative")
    delta = left_compression - right_compression
    if displacement_limit > 0.0:
        delta = min(max(delta, -displacement_limit), displacement_limit)
    return delta * 0.5, delta * -0.5


def vehicle_axle_geometry(wheel_centers, epsilon: float = 1e-4) -> VehicleAxleGeometry:
    if len(wheel_centers) != 4:
        raise ValueError(
            "Wheel centers must contain front-left, front-right, rear-left, and rear-right"
        )

    centers = []
    for center in wheel_centers:
        if len(center) != 3:
            raise ValueError("Each wheel center must contain three coordinates")
        values = tuple(float(value) for value in center)
        if not all_finite(values):
            raise ValueError("Wheel center coordinates must be finite")
        centers.append(values)

    front_left, front_right, rear_left, rear_right = centers
    front_axle = 0.5 * (front_left[1] + front_right[1])
    rear_axle = 0.5 * (rear_left[1] + rear_right[1])
    wheelbase = front_axle - rear_axle
    front_track = front_right[0] - front_left[0]
    rear_track = rear_right[0] - rear_left[0]

    threshold = max(float(epsilon), 0.0)
    if wheelbase <= threshold:
        raise ValueError(
            f"Front axle must be ahead of rear axle in vehicle space; wheelbase is {wheelbase:.6f} m"
        )
    if front_track <= threshold:
        raise ValueError(
            f"Front-left wheel must be left of front-right wheel; front track is {front_track:.6f} m"
        )
    if rear_track <= threshold:
        raise ValueError(
            f"Rear-left wheel must be left of rear-right wheel; rear track is {rear_track:.6f} m"
        )

    return VehicleAxleGeometry(
        wheelbase=wheelbase,
        front_track=front_track,
        rear_track=rear_track,
        front_axle=front_axle,
        rear_axle=rear_axle,
    )
