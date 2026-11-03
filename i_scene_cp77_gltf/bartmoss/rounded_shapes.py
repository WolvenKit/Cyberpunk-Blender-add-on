import math

import numpy as np

from .geometry import segment_aabb_distance_squared, segment_aabb_distances_squared

_AXIS_X_64 = np.array((1.0, 0.0, 0.0), dtype=np.float64)
_AXIS_Y_64 = np.array((0.0, 1.0, 0.0), dtype=np.float64)
_AXIS_Z_64 = np.array((0.0, 0.0, 1.0), dtype=np.float64)
_PROJECTION_PERMUTATIONS = (
    np.array(((0.0, 1.0, 0.0), (-1.0, 0.0, 0.0), (0.0, 0.0, 1.0))),
    np.identity(3),
    np.array(((1.0, 0.0, 0.0), (0.0, 0.0, -1.0), (0.0, 1.0, 0.0))),
)


def rounded_box_correction(extents, radius, points_ss, particle_radius):
    points = np.asarray(points_ss, dtype=np.float32)
    scalar_input = points.ndim == 1
    if scalar_input:
        points = points[np.newaxis, :]

    extents = np.abs(extents)
    total_radius = float(radius) + np.asarray(particle_radius, dtype=np.float32)
    if total_radius.ndim == 0:
        total_radius = np.full(len(points), float(total_radius), dtype=np.float32)

    closest = np.clip(points, -extents, extents)
    delta = points - closest
    distance = np.linalg.norm(delta, axis=1)
    correction = np.zeros_like(points)

    outside_core = distance >= 1e-6
    penetrating_outside = outside_core & (distance < total_radius)
    if np.any(penetrating_outside):
        direction = (
            delta[penetrating_outside] / distance[penetrating_outside, np.newaxis]
        )
        correction[penetrating_outside] = (
            direction
            * (total_radius[penetrating_outside] - distance[penetrating_outside])[
                :, np.newaxis
            ]
        )

    inside_core = ~outside_core
    if np.any(inside_core):
        inside_points = points[inside_core]
        face_gap = extents - np.abs(inside_points)
        axis = np.argmin(face_gap, axis=1)
        row = np.arange(len(inside_points))
        sign = np.where(inside_points[row, axis] < 0.0, -1.0, 1.0)
        target = sign * (extents[axis] + total_radius[inside_core])
        local_correction = np.zeros_like(inside_points)
        local_correction[row, axis] = target - inside_points[row, axis]
        correction[inside_core] = local_correction

    return correction[0] if scalar_input else correction


def rounded_box_signed_distance(extents, radius, point_ss, particle_radius):
    point = np.asarray(point_ss, dtype=np.float32)
    q = np.abs(point) - np.abs(extents)
    outside = np.linalg.norm(np.maximum(q, 0.0))
    inside = min(float(np.max(q)), 0.0)
    return outside + inside - float(radius) - float(particle_radius)


def rounded_box_signed_distances(extents, radii, points_ss, particle_radius):
    """Row-wise rounded_box_signed_distance"""
    points = np.asarray(points_ss, dtype=np.float32)
    q = np.abs(points) - np.abs(np.asarray(extents, dtype=np.float32))
    outside_q = np.maximum(q, np.float32(0.0))
    outside = np.sqrt(np.einsum("ij,ij->i", outside_q, outside_q))
    inside = np.minimum(q.max(axis=1), np.float32(0.0))
    return (
        outside
        + inside
        - np.asarray(radii, dtype=np.float32)
        - np.float32(particle_radius)
    )


def _directed_check_corner(position, direction, radius):
    b = float(np.dot(position, direction))
    discriminant = b * b + radius * radius - float(np.dot(position, position))
    if discriminant < 0.0:
        return 0.0
    return -b - float(np.sqrt(discriminant))


def _directed_check_edge(position, direction, half_extent, radius):
    negative_sphere = np.asarray(position, dtype=np.float64).copy()
    positive_sphere = negative_sphere.copy()
    negative_sphere[0] += half_extent
    positive_sphere[0] -= half_extent

    a = half_extent + half_extent
    b = a * a
    c = a * negative_sphere[0]
    d = a * direction[0]
    e = float(np.dot(direction, direction))
    f = float(np.dot(negative_sphere, direction))
    sphere_distance = float(np.dot(negative_sphere, negative_sphere))
    g = (sphere_distance - radius * radius) * b - c * c
    h = b * e - d * d

    if h != 0.0:
        x = b * f - d * c
        discriminant = x * x - h * g
        if discriminant < 0.0:
            return 0.0
        root = float(np.sqrt(discriminant))
        result = (-x - root) / h
        location = c + result * d
        if location > b:
            return _directed_check_corner(positive_sphere, direction, radius)
        if location < 0.0:
            return _directed_check_corner(negative_sphere, direction, radius)
        return result if result - ((root - x) / h) < 0.0 else 0.0

    if g > 0.0:
        return 0.0
    result = 0.0
    if direction[0] < 0.0:
        result += _directed_check_corner(positive_sphere, direction, radius)
    if direction[0] > 0.0:
        result += _directed_check_corner(negative_sphere, direction, radius)
    return result


def directed_box_projection(
    extents, radius, position_ss, direction_ss, height_extent, particle_radius
):
    """Project a directed point against the rounded collision shape"""
    position = np.asarray(position_ss, dtype=np.float64)
    direction = np.asarray(direction_ss, dtype=np.float64)
    extent = np.abs(np.asarray(extents, dtype=np.float64))
    radius = max(0.0, float(radius) + float(particle_radius))
    segment_length = max(0.0, float(height_extent)) * 2.0

    signs = np.where(direction < 0.0, -1.0, 1.0)
    reflected_position = position * signs
    reflected_direction = direction * signs

    def result_from_t(value):
        if value != 0.0 and value < segment_length:
            return segment_length - value
        return 0.0

    if float(np.sum(extent)) == 0.0:
        t = _directed_check_corner(position, direction, radius)
        return result_from_t(t)
    if extent[1] + extent[2] == 0.0:
        t = _directed_check_edge(position, direction, extent[0], radius)
        return result_from_t(t)
    if extent[0] + extent[2] == 0.0:
        t = _directed_check_edge(
            np.array((position[1], -position[0], position[2])),
            np.array((direction[1], -direction[0], direction[2])),
            extent[1],
            radius,
        )
        return result_from_t(t)
    if extent[0] + extent[1] == 0.0:
        t = _directed_check_edge(
            np.array((position[2], position[1], -position[0])),
            np.array((direction[2], direction[1], -direction[0])),
            extent[2],
            radius,
        )
        return result_from_t(t)

    for axis in range(3):
        if axis == 0:
            local_extent = np.array((extent[1], extent[0], extent[2]))
        elif axis == 1:
            local_extent = np.array((extent[0], extent[1], extent[2]))
        else:
            local_extent = np.array((extent[0], extent[2], extent[1]))

        matrix = _PROJECTION_PERMUTATIONS[axis]
        p = reflected_position @ matrix
        d = reflected_direction @ matrix
        if d[1] == 0.0:
            continue

        max_x = local_extent[0] + radius
        max_y = local_extent[1] + radius
        max_z = local_extent[2] + radius
        crossing = (-p[1] - max_y) / d[1]
        surface_point = np.array(
            (
                d[0] * crossing + p[0],
                -max_y,
                d[2] * crossing + p[2],
            )
        )

        if (
            abs(surface_point[2]) < local_extent[2]
            and abs(surface_point[0]) < local_extent[0]
        ):
            delta = surface_point - p
            distance = float(np.linalg.norm(delta))
            dot = float(np.dot(d, delta))
            if dot >= 0.0 and segment_length > distance:
                return segment_length - distance
            if dot < 0.0:
                return segment_length + distance

        if local_extent[2] != 0.0 and surface_point[0] >= local_extent[0]:
            t = _directed_check_edge(
                np.array(
                    (
                        p[2],
                        p[1] + local_extent[1],
                        -p[0] + local_extent[0],
                    )
                ),
                np.array((d[2], d[1], -d[0])),
                local_extent[2],
                radius,
            )
            if t != 0.0:
                value = d * t + p
                if (
                    abs(value[2]) <= max_z
                    and (local_extent[0] == 0.0 or value[0] >= local_extent[0])
                    and (local_extent[1] == 0.0 or value[1] <= -local_extent[1])
                ):
                    return result_from_t(t)

        if local_extent[0] != 0.0 and surface_point[2] >= local_extent[2]:
            t = _directed_check_edge(
                np.array(
                    (
                        p[0],
                        p[1] + local_extent[1],
                        p[2] - local_extent[2],
                    )
                ),
                d,
                local_extent[0],
                radius,
            )
            if t != 0.0:
                value = d * t + p
                if (
                    abs(value[0]) <= max_x
                    and (local_extent[2] == 0.0 or value[2] >= local_extent[2])
                    and (local_extent[1] == 0.0 or value[1] <= -local_extent[1])
                ):
                    return result_from_t(t)

        if local_extent[2] != 0.0 and surface_point[0] <= -local_extent[0]:
            t = _directed_check_edge(
                np.array(
                    (
                        p[2],
                        p[1] + local_extent[1],
                        -p[0] - local_extent[0],
                    )
                ),
                np.array((d[2], d[1], -d[0])),
                local_extent[2],
                radius,
            )
            if t != 0.0:
                value = d * t + p
                if (
                    abs(value[2]) <= max_z
                    and (local_extent[1] == 0.0 or value[1] <= -local_extent[1])
                    and (local_extent[0] == 0.0 or value[0] <= -local_extent[0])
                ):
                    return result_from_t(t)

        if local_extent[0] != 0.0 and surface_point[2] <= -local_extent[2]:
            t = _directed_check_edge(
                np.array(
                    (
                        p[0],
                        p[1] + local_extent[1],
                        p[2] + local_extent[2],
                    )
                ),
                d,
                local_extent[0],
                radius,
            )
            if t != 0.0:
                value = d * t + p
                if (
                    abs(value[0]) <= max_x
                    and (local_extent[1] == 0.0 or value[1] <= -local_extent[1])
                    and (local_extent[2] == 0.0 or value[2] <= -local_extent[2])
                ):
                    return result_from_t(t)

    return 0.0


def swept_capsule_box_overlap(
    extents,
    radius,
    position_ss,
    direction_ss,
    segment_length,
    capsule_radius,
):
    """Return signed swept-capsule overlap in shape space"""
    combined_radius = max(0.0, float(radius) + float(capsule_radius))
    distance_squared = segment_aabb_distance_squared(
        position_ss, direction_ss, segment_length, extents
    )
    return distance_squared - combined_radius * combined_radius


def swept_capsule_box_overlaps(
    extents, radii, positions_ss, directions_ss, segment_length, capsule_radius
):
    """Row-wise swept_capsule_box_overlap"""
    combined = np.maximum(
        0.0, np.asarray(radii, dtype=np.float64) + float(capsule_radius)
    )
    distances_squared = segment_aabb_distances_squared(
        positions_ss, directions_ss, segment_length, extents
    )
    return distances_squared - combined * combined


def orthogonal_unit(direction):
    direction = np.asarray(direction, dtype=np.float64)
    if abs(direction[0]) < 0.9:
        value = np.cross(direction, _AXIS_X_64)
    else:
        value = np.cross(direction, _AXIS_Y_64)
    length = float(np.linalg.norm(value))
    if length <= 1e-15:
        return _AXIS_Z_64.copy()
    return value / length


def rotated_direction(direction, axis, angle):
    direction = np.asarray(direction, dtype=np.float64)
    axis = np.asarray(axis, dtype=np.float64)
    axis_length = float(np.linalg.norm(axis))
    if axis_length <= 1e-15:
        return direction.copy()
    axis = axis / axis_length
    cosine = math.cos(angle)
    sine = math.sin(angle)
    result = (
        direction * cosine
        + np.cross(axis, direction) * sine
        + axis * float(np.dot(axis, direction)) * (1.0 - cosine)
    )
    result_length = float(np.linalg.norm(result))
    return result / result_length if result_length > 1e-15 else direction.copy()


def spherical_direction(direction, tangent, angle):
    result = direction * math.cos(angle) + tangent * math.sin(angle)
    length = float(np.linalg.norm(result))
    return result / length if length > 1e-15 else direction.copy()


def _first_clear_angle(
    extents,
    radius,
    position,
    direction,
    tangent,
    segment_length,
    capsule_radius,
    upper_angle=math.pi,
    coarse_steps=24,
):
    previous_angle = 0.0
    for step in range(1, coarse_steps + 1):
        angle = upper_angle * step / coarse_steps
        candidate = spherical_direction(direction, tangent, angle)
        if (
            swept_capsule_box_overlap(
                extents, radius, position, candidate, segment_length, capsule_radius
            )
            >= -1e-7
        ):
            lo = previous_angle
            hi = angle
            for _ in range(22):
                middle = (lo + hi) * 0.5
                candidate = spherical_direction(direction, tangent, middle)
                if (
                    swept_capsule_box_overlap(
                        extents,
                        radius,
                        position,
                        candidate,
                        segment_length,
                        capsule_radius,
                    )
                    >= -1e-7
                ):
                    hi = middle
                else:
                    lo = middle
            return hi
        previous_angle = angle
    return None


def shortest_path_rotational_projection(
    extents,
    radius,
    position_ss,
    direction_ss,
    segment_length,
    capsule_radius,
):
    """Project a swept capsule with minimum angular displacement"""
    position = np.asarray(position_ss, dtype=np.float64)
    direction = np.asarray(direction_ss, dtype=np.float64)
    segment_length = max(0.0, float(segment_length))
    length = float(np.linalg.norm(direction))
    if length <= 1e-15 or segment_length == 0.0:
        return np.zeros(3, dtype=np.float64)
    direction /= length

    if (
        swept_capsule_box_overlap(
            extents, radius, position, direction, segment_length, capsule_radius
        )
        >= -1e-7
    ):
        return direction * segment_length

    tangent_u = orthogonal_unit(direction)
    tangent_v = np.cross(direction, tangent_u)
    tangent_v /= max(float(np.linalg.norm(tangent_v)), 1e-15)

    best_angle = None
    best_azimuth = 0.0
    azimuth_steps = 48
    for azimuth_index in range(azimuth_steps):
        azimuth = math.tau * azimuth_index / azimuth_steps
        tangent = tangent_u * math.cos(azimuth) + tangent_v * math.sin(azimuth)
        angle = _first_clear_angle(
            extents,
            radius,
            position,
            direction,
            tangent,
            segment_length,
            capsule_radius,
        )
        if angle is not None and (best_angle is None or angle < best_angle):
            best_angle = angle
            best_azimuth = azimuth

    if best_angle is None:
        return direction * segment_length

    # Refine azimuth around the best candidate.
    azimuth_step = math.tau / azimuth_steps
    for _ in range(6):
        candidates = (
            best_azimuth - azimuth_step,
            best_azimuth - azimuth_step * 0.5,
            best_azimuth,
            best_azimuth + azimuth_step * 0.5,
            best_azimuth + azimuth_step,
        )
        for azimuth in candidates:
            tangent = tangent_u * math.cos(azimuth) + tangent_v * math.sin(azimuth)
            angle = _first_clear_angle(
                extents,
                radius,
                position,
                direction,
                tangent,
                segment_length,
                capsule_radius,
                upper_angle=min(math.pi, best_angle + azimuth_step),
                coarse_steps=12,
            )
            if angle is not None and angle < best_angle:
                best_angle = angle
                best_azimuth = azimuth
        azimuth_step *= 0.5

    tangent = tangent_u * math.cos(best_azimuth) + tangent_v * math.sin(best_azimuth)
    return spherical_direction(direction, tangent, best_angle) * segment_length


def directed_rotational_projection(
    extents,
    radius,
    position_ss,
    direction_ss,
    segment_length,
    capsule_radius,
    rotation_axis_ss,
):
    """Project by rotating in the authored directed plane"""
    position = np.asarray(position_ss, dtype=np.float64)
    direction = np.asarray(direction_ss, dtype=np.float64)
    axis = np.asarray(rotation_axis_ss, dtype=np.float64)
    segment_length = max(0.0, float(segment_length))

    direction_length = float(np.linalg.norm(direction))
    axis_length = float(np.linalg.norm(axis))
    if direction_length <= 1e-15 or segment_length == 0.0:
        return np.zeros(3, dtype=np.float64)
    direction /= direction_length
    if axis_length <= 1e-15:
        return shortest_path_rotational_projection(
            extents, radius, position, direction, segment_length, capsule_radius
        )
    axis /= axis_length

    if (
        swept_capsule_box_overlap(
            extents, radius, position, direction, segment_length, capsule_radius
        )
        >= -1e-7
    ):
        return direction * segment_length

    # Rotation cannot change a direction parallel to its axis.
    if float(np.linalg.norm(np.cross(axis, direction))) <= 1e-12:
        return direction * segment_length

    previous_angle = 0.0
    coarse_steps = 128
    for step in range(1, coarse_steps + 1):
        angle = math.tau * step / coarse_steps
        candidate = rotated_direction(direction, axis, angle)
        if (
            swept_capsule_box_overlap(
                extents, radius, position, candidate, segment_length, capsule_radius
            )
            >= -1e-7
        ):
            lo = previous_angle
            hi = angle
            for _ in range(24):
                middle = (lo + hi) * 0.5
                candidate = rotated_direction(direction, axis, middle)
                if (
                    swept_capsule_box_overlap(
                        extents,
                        radius,
                        position,
                        candidate,
                        segment_length,
                        capsule_radius,
                    )
                    >= -1e-7
                ):
                    hi = middle
                else:
                    lo = middle
            return rotated_direction(direction, axis, hi) * segment_length
        previous_angle = angle

    return direction * segment_length
