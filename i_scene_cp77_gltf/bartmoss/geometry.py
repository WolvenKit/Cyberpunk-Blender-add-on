from __future__ import annotations

import math

import numpy as np


def transform_normalized_direction_deltas(base, deltas, matrix):
    """Transform a morph's complete direction vectors before differencing normalized results"""
    linear = np.asarray(matrix, dtype=np.float64)
    base = np.asarray(base, dtype=np.float64)

    def transformed(values):
        values = values @ linear.T
        lengths = np.linalg.norm(values, axis=1, keepdims=True)
        if not np.all(np.isfinite(values)) or np.any(lengths <= 1.0e-12):
            raise ValueError(
                "A transformed morph direction is non-finite or has zero length."
            )
        return values / lengths

    reference = transformed(base)
    return [
        (
            name,
            np.ascontiguousarray(
                (transformed(base + delta) - reference).astype(np.float32)
            ),
        )
        for name, delta in deltas
    ]


def isolate_repeated_triangle_faces(triangles, vertex_count):
    """Detach repeated faces while retaining each corner's original vertex identity"""
    triangles = np.asarray(triangles)
    if (
        triangles.ndim != 2
        or triangles.shape[1] != 3
        or triangles.dtype.kind not in "iu"
    ):
        raise ValueError("Triangle topology requires integral triples.")
    if len(triangles) < 2:
        return None, triangles
    ordered = np.sort(triangles, axis=1)
    if vertex_count <= 1 << 21:
        keys = ordered[:, 0].astype(np.uint64) << 42
        keys |= ordered[:, 1].astype(np.uint64) << 21
        keys |= ordered[:, 2].astype(np.uint64)
    else:
        keys = (
            np.ascontiguousarray(ordered)
            .view(np.dtype((np.void, 3 * ordered.dtype.itemsize)))
            .reshape(-1)
        )
    _, first = np.unique(keys, return_index=True)
    if len(first) == len(triangles):
        return None, triangles
    repeated = np.ones(len(triangles), dtype=bool)
    repeated[first] = False
    faces = np.flatnonzero(repeated)
    count = vertex_count + 3 * len(faces)
    if count > np.iinfo(np.int32).max:
        raise ValueError(
            "Detached triangle topology exceeds the supported vertex range."
        )
    sources = np.concatenate(
        (
            np.arange(vertex_count, dtype=np.int32),
            triangles[faces].reshape(-1).astype(np.int32),
        )
    )
    detached = triangles.astype(np.int32, copy=True)
    detached[faces] = np.arange(vertex_count, count, dtype=np.int32).reshape(-1, 3)
    return sources, detached


def float32_direction_length(origin, tolerance: float) -> float:
    """The shortest segment from origin whose direction survives float32 rounding of both endpoints"""
    magnitude = max(
        abs(float(origin[0])), abs(float(origin[1])), abs(float(origin[2])), 1.0e-6
    )
    return 2.0 * float(np.spacing(np.float32(magnitude))) / tolerance


def closest_point_on_segment(points, start, end, epsilon: float = 1e-6):
    segment = end - start
    relative = points - start
    length_squared = np.sum(segment * segment, axis=-1)
    safe = np.where(length_squared < epsilon, 1.0, length_squared)
    factor = np.clip(np.sum(relative * segment, axis=-1) / safe, 0.0, 1.0)
    return start + factor[..., None] * segment


def closest_point_on_segment_single(point, start, end, epsilon: float = 1e-6):
    segment = end - start
    length_squared = np.dot(segment, segment)
    if length_squared < epsilon:
        return start.copy()
    factor = max(0.0, min(1.0, np.dot(point - start, segment) / length_squared))
    return start + segment * factor


def orthogonal_vector(vector):
    value = np.asarray(vector)
    x, y, z = value
    if 0.81 * np.dot(value, value) - x * x < 0.0:
        return np.asarray((-z, 0.0, x), dtype=value.dtype)
    return np.asarray((0.0, z, -y), dtype=value.dtype)


def unit_vectors(vectors) -> np.ndarray:
    """Vectors scaled to unit length along the last axis, zero vectors left at zero"""
    vectors = np.asarray(vectors, dtype=np.float64)
    return vectors / np.maximum(np.linalg.norm(vectors, axis=-1, keepdims=True), 1e-12)


def vector_angles(first, second) -> np.ndarray:
    """Angles in radians between vectors along the last axis"""
    return np.arccos(
        np.clip(np.sum(unit_vectors(first) * unit_vectors(second), axis=-1), -1.0, 1.0)
    )


def signed_angles(start, end, axes) -> np.ndarray:
    """Angles in radians turning start onto end about unit axes, both taken square to the axes"""
    start = start - np.sum(start * axes, axis=-1, keepdims=True) * axes
    end = end - np.sum(end * axes, axis=-1, keepdims=True) * axes
    return np.arctan2(
        np.sum(np.cross(start, end) * axes, axis=-1), np.sum(start * end, axis=-1)
    )


def project_ellipsoid_offset(offset, radius: float, z_scale: float) -> np.ndarray:
    """Constrain an offset to an ellipsoid of radius with Z scaled by z_scale"""
    corrected = np.asarray(offset, dtype=np.float64).copy()
    radius = float(radius)
    if radius == 0.0:
        return np.zeros(3, dtype=np.float64)

    distance = float(np.linalg.norm(corrected))
    if distance <= 1e-4:
        return corrected

    direction = corrected / distance
    z_extent = radius * float(z_scale)
    if abs(z_extent) <= 1e-12:
        return corrected

    scaled = direction / np.asarray((radius, radius, z_extent))
    scaled_length = float(np.linalg.norm(scaled))
    if scaled_length <= 1e-12:
        return corrected
    maximum_distance = 1.0 / scaled_length

    if distance > maximum_distance:
        normal = direction / np.asarray(
            (
                radius * radius,
                radius * radius,
                z_extent * z_extent,
            )
        )
        normal_length = float(np.linalg.norm(normal))
        if normal_length > 1e-12:
            normal /= normal_length
            surface = direction * maximum_distance
            corrected -= normal * (
                float(np.dot(normal, corrected)) - float(np.dot(normal, surface))
            )

    corrected_length = float(np.linalg.norm(corrected))
    biggest_extent = max(radius, z_extent)
    if corrected_length > biggest_extent and corrected_length > 0.0:
        corrected *= biggest_extent / corrected_length
    return corrected


def orthonormal_axes(forward, up, epsilon: float = 1e-12):
    forward = np.asarray(forward, dtype=np.float64).copy()
    up = np.asarray(up, dtype=np.float64).copy()
    forward_length = float(np.linalg.norm(forward))
    up_length = float(np.linalg.norm(up))
    if forward_length <= epsilon or up_length <= epsilon:
        raise ValueError("Axes must be nonzero")
    forward /= forward_length
    up /= up_length
    right = np.cross(forward, up)
    right_length = float(np.linalg.norm(right))
    if right_length <= epsilon:
        raise ValueError("Axes are parallel")
    right /= right_length
    up = np.cross(right, forward)
    up /= max(float(np.linalg.norm(up)), epsilon)
    return forward, up, right


def distance_2d(first, second) -> float:
    first = np.asarray(first, dtype=np.float64)
    second = np.asarray(second, dtype=np.float64)
    return float(np.linalg.norm(second[:2] - first[:2]))


def point_line_distance_2d(point, start, end, epsilon: float = 1e-12) -> float:
    point = np.asarray(point, dtype=np.float64)
    start = np.asarray(start, dtype=np.float64)
    end = np.asarray(end, dtype=np.float64)
    chord = end[:2] - start[:2]
    length = float(np.linalg.norm(chord))
    if length <= epsilon:
        return distance_2d(point, start)
    offset = point[:2] - start[:2]
    return abs(float(chord[0] * offset[1] - chord[1] * offset[0])) / length


def segment_projection(point, start, end, epsilon: float = 1e-12) -> float:
    point = np.asarray(point, dtype=np.float64)
    start = np.asarray(start, dtype=np.float64)
    end = np.asarray(end, dtype=np.float64)
    segment = end - start
    length_squared = float(np.dot(segment, segment))
    if length_squared <= epsilon:
        return 0.0
    return float(np.dot(point - start, segment) / length_squared)


def point_segment_distance(point, start, end, epsilon: float = 1e-12) -> float:
    point = np.asarray(point, dtype=np.float64)
    start = np.asarray(start, dtype=np.float64)
    end = np.asarray(end, dtype=np.float64)
    factor = max(0.0, min(1.0, segment_projection(point, start, end, epsilon)))
    closest = start + (end - start) * factor
    return float(np.linalg.norm(point - closest))


def calc_subuv_offset(frame, columns, rows):
    columns = float(columns)
    rows = float(rows)
    if columns <= 0.0 or rows <= 0.0:
        raise ValueError("SubUV grid dimensions must be positive.")
    frame_value = float(frame)
    inv_columns = 1.0 / columns
    inv_rows = 1.0 / rows
    return (
        math.floor(frame_value) * inv_columns,
        -math.floor(frame_value * inv_columns) * inv_rows,
    )


def triangle_area_squared(a, b, c) -> float:
    abx = float(b[0]) - float(a[0])
    aby = float(b[1]) - float(a[1])
    abz = float(b[2]) - float(a[2])
    acx = float(c[0]) - float(a[0])
    acy = float(c[1]) - float(a[1])
    acz = float(c[2]) - float(a[2])
    x = aby * acz - abz * acy
    y = abz * acx - abx * acz
    z = abx * acy - aby * acx
    return x * x + y * y + z * z


def mirror_xy(coordinate, axes):
    x = float(coordinate[0])
    y = float(coordinate[1])
    for axis in axes:
        if axis == "X":
            x = -x
        else:
            y = -y
    return x, y


def box_intersects_any_padded(box, boxes, pad: float = 0.0) -> bool:
    owner, ax1, ax2, ay1, ay2 = box
    padding = float(pad)
    ax1 -= padding
    ax2 += padding
    ay1 -= padding
    ay2 += padding
    for other, bx1, bx2, by1, by2 in boxes:
        if other is owner:
            continue
        if ax1 < bx2 and bx1 < ax2 and ay1 < by2 and by1 < ay2:
            return True
    return False


def sphere_aabb(center, radius):
    """The (minimum, maximum) box around a sphere"""
    radius = max(0.0, float(radius))
    return (
        tuple(float(center[axis]) - radius for axis in range(3)),
        tuple(float(center[axis]) + radius for axis in range(3)),
    )


def aabb_sample_points(bounds):
    """The centre and the eight corners of a (minimum, maximum) box"""
    minimum, maximum = bounds
    center = tuple(
        (float(minimum[axis]) + float(maximum[axis])) * 0.5 for axis in range(3)
    )
    corners = tuple(
        (x, y, z)
        for x in (float(minimum[0]), float(maximum[0]))
        for y in (float(minimum[1]), float(maximum[1]))
        for z in (float(minimum[2]), float(maximum[2]))
    )
    return (center, *corners)


def point_in_aabb(point, bounds):
    """Whether point lies in or on a (minimum, maximum) box"""
    return all(
        float(bounds[0][axis]) <= float(point[axis]) <= float(bounds[1][axis])
        for axis in range(3)
    )


def segment_aabb_distance_squared(start, direction, length, extents):
    """Return squared distance from a finite segment to an AABB"""
    start = np.asarray(start, dtype=np.float64)
    direction = np.asarray(direction, dtype=np.float64)
    extents = np.abs(np.asarray(extents, dtype=np.float64))
    length = max(0.0, float(length))

    direction_length = float(np.linalg.norm(direction))
    if direction_length <= 1e-15 or length == 0.0:
        q = np.maximum(np.abs(start) - extents, 0.0)
        return float(np.dot(q, q))
    direction = direction / direction_length

    def objective(distance):
        point = start + direction * distance
        q = np.maximum(np.abs(point) - extents, 0.0)
        return float(np.dot(q, q))

    lo = 0.0
    hi = length
    for _ in range(36):
        third = (hi - lo) / 3.0
        left = lo + third
        right = hi - third
        if objective(left) <= objective(right):
            hi = right
        else:
            lo = left
    middle = (lo + hi) * 0.5
    return min(objective(0.0), objective(length), objective(middle))


def segment_aabb_distances_squared(starts, directions, length, extents):
    """Row-wise segment_aabb_distance_squared for many segments, each against its own AABB"""
    starts = np.asarray(starts, dtype=np.float64)
    directions = np.asarray(directions, dtype=np.float64)
    extents = np.abs(np.asarray(extents, dtype=np.float64))
    length = max(0.0, float(length))

    def objective(distances):
        q = np.maximum(np.abs(starts + directions * distances[:, None]) - extents, 0.0)
        return np.einsum("ij,ij->i", q, q)

    direction_lengths = np.sqrt(np.einsum("ij,ij->i", directions, directions))
    degenerate = (direction_lengths <= 1e-15) | (length == 0.0)
    if np.all(degenerate):
        q = np.maximum(np.abs(starts) - extents, 0.0)
        return np.einsum("ij,ij->i", q, q)
    directions = directions / np.where(degenerate, 1.0, direction_lengths)[:, None]
    lo = np.zeros(len(starts))
    hi = np.full(len(starts), length)
    for _ in range(36):
        third = (hi - lo) / 3.0
        left = lo + third
        right = hi - third
        closer_left = objective(left) <= objective(right)
        hi = np.where(closer_left, right, hi)
        lo = np.where(closer_left, lo, left)
    result = np.minimum(
        np.minimum(
            objective(np.zeros(len(starts))), objective(np.full(len(starts), length))
        ),
        objective((lo + hi) * 0.5),
    )
    if np.any(degenerate):
        q = np.maximum(np.abs(starts[degenerate]) - extents[degenerate], 0.0)
        result[degenerate] = np.einsum("ij,ij->i", q, q)
    return result


def ray_sphere_point_nearest(
    line_start, line_direction, sphere_center, sphere_radius, previous_position
):
    """Where the ray from line_start along line_direction meets the sphere"""
    sx, sy, sz = (float(value) for value in line_start)
    dx, dy, dz = (float(value) for value in line_direction)
    cx, cy, cz = (float(value) for value in sphere_center)
    px, py, pz = (float(value) for value in previous_position)

    direction_length = math.sqrt(dx * dx + dy * dy + dz * dz)
    if direction_length <= 1e-12:
        return (px, py, pz)
    dx /= direction_length
    dy /= direction_length
    dz /= direction_length

    ox, oy, oz = sx - cx, sy - cy, sz - cz
    b_coeff = 2.0 * (ox * dx + oy * dy + oz * dz)
    c_coeff = (ox * ox + oy * oy + oz * oz) - float(sphere_radius) ** 2
    discriminant = b_coeff * b_coeff - 4.0 * c_coeff

    candidates = []
    if discriminant >= -1e-12:
        sqrt_disc = math.sqrt(max(0.0, discriminant))
        far_alpha = (-b_coeff + sqrt_disc) * 0.5
        near_alpha = (-b_coeff - sqrt_disc) * 0.5
        if near_alpha >= 0.0:
            candidates.append(
                (sx + dx * near_alpha, sy + dy * near_alpha, sz + dz * near_alpha)
            )
        if far_alpha >= 0.0 and (not candidates or abs(far_alpha - near_alpha) > 1e-10):
            candidates.append(
                (sx + dx * far_alpha, sy + dy * far_alpha, sz + dz * far_alpha)
            )

    if candidates:

        def distance_squared(point):
            qx, qy, qz = point[0] - px, point[1] - py, point[2] - pz
            return qx * qx + qy * qy + qz * qz

        return min(candidates, key=distance_squared)

    alpha = max(0.0, dx * (px - sx) + dy * (py - sy) + dz * (pz - sz))
    return (sx + dx * alpha, sy + dy * alpha, sz + dz * alpha)
