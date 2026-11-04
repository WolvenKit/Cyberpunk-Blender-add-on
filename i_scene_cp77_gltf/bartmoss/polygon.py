from __future__ import annotations

import math

_EPS = 1.0e-10


def cross_2d(a, b, c):
    return (float(b[0]) - float(a[0])) * (float(c[1]) - float(a[1])) - (
        float(b[1]) - float(a[1])
    ) * (float(c[0]) - float(a[0]))


def indexed_polygon_area(indices, coords):
    if len(indices) < 3:
        return 0.0
    total = 0.0
    for index, current in enumerate(indices):
        following = indices[(index + 1) % len(indices)]
        x0, y0 = coords[current]
        x1, y1 = coords[following]
        total += (x0 * y1) - (x1 * y0)
    return total * 0.5


def point_on_segment_2d(a, b, point, epsilon=1.0e-9):
    if abs(cross_2d(a, b, point)) > epsilon:
        return False
    return (
        min(a[0], b[0]) - epsilon <= point[0] <= max(a[0], b[0]) + epsilon
        and min(a[1], b[1]) - epsilon <= point[1] <= max(a[1], b[1]) + epsilon
    )


def orientation_2d(a, b, c, epsilon=1.0e-9):
    value = cross_2d(a, b, c)
    if value > epsilon:
        return 1
    if value < -epsilon:
        return -1
    return 0


def segments_intersect_2d(a, b, c, d, epsilon=1.0e-9):
    o1 = orientation_2d(a, b, c, epsilon)
    o2 = orientation_2d(a, b, d, epsilon)
    o3 = orientation_2d(c, d, a, epsilon)
    o4 = orientation_2d(c, d, b, epsilon)
    if o1 != o2 and o3 != o4:
        return True
    return (
        (o1 == 0 and point_on_segment_2d(a, b, c, epsilon))
        or (o2 == 0 and point_on_segment_2d(a, b, d, epsilon))
        or (o3 == 0 and point_on_segment_2d(c, d, a, epsilon))
        or (o4 == 0 and point_on_segment_2d(c, d, b, epsilon))
    )


def point_in_ring(point, ring, coords):
    x, y = float(point[0]), float(point[1])
    inside = False
    for index, first_index in enumerate(ring):
        second_index = ring[(index + 1) % len(ring)]
        first = coords[first_index]
        second = coords[second_index]
        if point_on_segment_2d(first, second, (x, y)):
            return True
        if (first[1] > y) == (second[1] > y):
            continue
        x_at_y = (
            (second[0] - first[0]) * (y - first[1]) / (second[1] - first[1])
        ) + first[0]
        if x < x_at_y:
            inside = not inside
    return inside


def point_in_domain(point, outer, holes, coords):
    if not point_in_ring(point, outer, coords):
        return False
    return not any(point_in_ring(point, hole, coords) for hole in holes)


def point_in_triangle_2d(point, a, b, c, epsilon=1.0e-10):
    c1 = cross_2d(a, b, point)
    c2 = cross_2d(b, c, point)
    c3 = cross_2d(c, a, point)
    return c1 >= -epsilon and c2 >= -epsilon and c3 >= -epsilon


def triangle_area_2d(a, b, c):
    return abs(cross_2d(a, b, c)) * 0.5


def ccw_triangle(a, b, c, coords):
    return (a, b, c) if cross_2d(coords[a], coords[b], coords[c]) > 0.0 else (a, c, b)


def triangle_min_angle(triangle, coords):
    a, b, c = (coords[index] for index in triangle)
    squared = sorted(
        (
            (float(b[0]) - float(c[0])) ** 2 + (float(b[1]) - float(c[1])) ** 2,
            (float(c[0]) - float(a[0])) ** 2 + (float(c[1]) - float(a[1])) ** 2,
            (float(a[0]) - float(b[0])) ** 2 + (float(a[1]) - float(b[1])) ** 2,
        )
    )
    if squared[0] <= _EPS * _EPS:
        return 0.0
    # The shortest edge is opposite the minimum angle.
    cosine = (squared[1] + squared[2] - squared[0]) / (
        2.0 * math.sqrt(squared[1] * squared[2])
    )
    return math.acos(max(-1.0, min(1.0, cosine)))
