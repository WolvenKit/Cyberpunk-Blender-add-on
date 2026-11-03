import math
from functools import lru_cache

from .vector3 import add3, cross3, dot3, normalized3, scale3

_CONE_SEGMENTS = 16
_CONE_CIRCLE = tuple(
    (
        math.cos(segment * 2.0 * math.pi / _CONE_SEGMENTS),
        math.sin(segment * 2.0 * math.pi / _CONE_SEGMENTS),
    )
    for segment in range(_CONE_SEGMENTS)
)


@lru_cache(maxsize=256)
def capsule_wireframe(rad: float, half_h: float):
    verts, lines = [], []
    segments, hemi_rings = 8, 4

    for r in range(hemi_rings + 1):
        theta = r * (math.pi / 2.0) / hemi_rings
        z = math.cos(theta) * rad + half_h
        xy_rad = math.sin(theta) * rad
        ring_start = len(verts)
        for s in range(segments):
            phi = s * 2 * math.pi / segments
            verts.append((math.cos(phi) * xy_rad, math.sin(phi) * xy_rad, z))
            lines.append((ring_start + s, ring_start + ((s + 1) % segments)))
            if r > 0:
                lines.append((ring_start + s, ring_start - segments + s))

    bot_equator = len(verts) - segments
    bot_start = len(verts)

    for r in range(hemi_rings + 1):
        theta = (math.pi / 2.0) + (r * (math.pi / 2.0) / hemi_rings)
        z = math.cos(theta) * rad - half_h
        xy_rad = math.sin(theta) * rad
        ring_start = len(verts)
        for s in range(segments):
            phi = s * 2 * math.pi / segments
            verts.append((math.cos(phi) * xy_rad, math.sin(phi) * xy_rad, z))
            lines.append((ring_start + s, ring_start + ((s + 1) % segments)))
            if r > 0:
                lines.append((ring_start + s, ring_start - segments + s))

    for s in range(segments):
        lines.append((bot_equator + s, bot_start + s))

    return tuple(verts), tuple(lines)


@lru_cache(maxsize=256)
def sphere_wireframe(radius: float, segments: int = 8, rings: int = 8):
    """A UV sphere about the origin"""
    verts, lines = [], []
    for r in range(rings + 1):
        theta = r * math.pi / rings
        z = math.cos(theta) * radius
        xy_rad = math.sin(theta) * radius
        ring_start = len(verts)
        for s in range(segments):
            phi = s * 2 * math.pi / segments
            verts.append((math.cos(phi) * xy_rad, math.sin(phi) * xy_rad, z))
            if r > 0:
                lines.append((ring_start + s, ring_start - segments + s))
            lines.append((ring_start + s, ring_start + ((s + 1) % segments)))
    return tuple(verts), tuple(lines)


@lru_cache(maxsize=256)
def box_wireframe(extents, radius=0.0):
    x, y, z = (max(0.0, float(value)) + radius for value in extents)
    verts = [
        (-x, -y, -z),
        (x, -y, -z),
        (x, y, -z),
        (-x, y, -z),
        (-x, -y, z),
        (x, -y, z),
        (x, y, z),
        (-x, y, z),
    ]
    lines = [
        (0, 1),
        (1, 2),
        (2, 3),
        (3, 0),
        (4, 5),
        (5, 6),
        (6, 7),
        (7, 4),
        (0, 4),
        (1, 5),
        (2, 6),
        (3, 7),
    ]
    return verts, lines


@lru_cache(maxsize=256)
def two_sided_ellipsoid_wireframe(radius, scale1, scale2):
    radius = max(0.0, float(radius))
    scale1 = max(0.01, float(scale1))
    scale2 = max(0.01, float(scale2))
    segments = 16
    rings = 8
    verts, lines = [], []

    for ring in range(rings + 1):
        theta = math.pi * ring / rings
        radial = math.sin(theta) * radius
        z_unit = math.cos(theta)
        z_scale = scale2 if z_unit >= 0.0 else scale1
        z = z_unit * radius * z_scale
        ring_start = len(verts)
        for segment in range(segments):
            phi = 2.0 * math.pi * segment / segments
            verts.append(
                (
                    math.cos(phi) * radial,
                    math.sin(phi) * radial,
                    z,
                )
            )
            lines.append(
                (
                    ring_start + segment,
                    ring_start + ((segment + 1) % segments),
                )
            )
            if ring > 0:
                lines.append(
                    (
                        ring_start + segment,
                        ring_start - segments + segment,
                    )
                )
    return tuple(verts), tuple(lines)


def cone_wireframe(origin, axis_ms, angle_rad, length=0.1):
    """Generate a bounded wire cone using ray length, not tan(angle)"""
    verts, lines = [], []
    segments = _CONE_SEGMENTS

    axis_ms = tuple(float(value) for value in axis_ms)
    if dot3(axis_ms, axis_ms) <= 1e-12:
        axis_ms = (1.0, 0.0, 0.0)
    else:
        axis_ms = normalized3(axis_ms)

    angle_rad = min(math.pi, max(0.0, float(angle_rad)))
    ray_length = max(0.001, abs(float(length)))

    up = (0.0, 0.0, 1.0) if abs(axis_ms[2]) < 0.99 else (1.0, 0.0, 0.0)
    tangent = cross3(axis_ms, up)
    if dot3(tangent, tangent) <= 1e-12:
        tangent = cross3(axis_ms, (0.0, 1.0, 0.0))
    tangent = normalized3(tangent)
    bitangent = normalized3(cross3(axis_ms, tangent))

    # Parameterize the boundary by ray length. Unlike tan(angle), this is
    # finite at 90 degrees and remains valid for inverted cones above 90.
    axial_distance = math.cos(angle_rad) * ray_length
    radius = abs(math.sin(angle_rad) * ray_length)
    origin = tuple(float(value) for value in origin)
    center = add3(origin, scale3(axis_ms, axial_distance))

    for cosine, sine in _CONE_CIRCLE:
        radial = add3(scale3(tangent, cosine), scale3(bitangent, sine))
        point = add3(center, scale3(radial, radius))
        if not all(math.isfinite(value) for value in point):
            return [], []
        verts.append(point)

    for segment in range(segments):
        lines.append((segment, (segment + 1) % segments))

    apex_idx = len(verts)
    if not all(math.isfinite(value) for value in origin):
        return [], []
    verts.append(origin)
    for segment in range(0, segments, 4):
        lines.append((apex_idx, segment))

    return verts, lines


@lru_cache(maxsize=64)
def coil_wireframe(
    radius: float, length: float, turns: float = 7.0, segments_per_turn: int = 12
):
    """A helical spring along -Z"""
    radius = max(0.0, float(radius))
    length = max(0.0, float(length))
    count = max(2, int(round(turns * segments_per_turn)))
    verts = []
    for index in range(count + 1):
        fraction = index / count
        angle = 2.0 * math.pi * turns * fraction
        verts.append(
            (math.cos(angle) * radius, math.sin(angle) * radius, -length * fraction)
        )
    lines = [(index, index + 1) for index in range(count)]
    return tuple(verts), tuple(lines)


@lru_cache(maxsize=64)
def ring_wireframe(radius: float, axis: int, segments: int = 32):
    """A circle of the given radius about the origin, in the plane normal to coordinate axis 0, 1 or 2"""
    radius = max(0.0, float(radius))
    first, second = ((1, 2), (2, 0), (0, 1))[axis]
    verts = []
    for index in range(segments):
        angle = 2.0 * math.pi * index / segments
        vertex = [0.0, 0.0, 0.0]
        vertex[first] = math.cos(angle) * radius
        vertex[second] = math.sin(angle) * radius
        verts.append(tuple(vertex))
    lines = [(index, (index + 1) % segments) for index in range(segments)]
    return tuple(verts), tuple(lines)


@lru_cache(maxsize=8)
def _wheel_template(segments: int):
    samples = tuple(
        (
            math.cos(index * 2.0 * math.pi / segments),
            math.sin(index * 2.0 * math.pi / segments),
        )
        for index in range(segments)
    )
    lines = []
    for ring_start in (0, segments):
        lines.extend(
            (ring_start + index, ring_start + ((index + 1) % segments))
            for index in range(segments)
        )
    lines.extend(
        (index, segments + index) for index in range(0, segments, max(1, segments // 8))
    )
    return samples, tuple(lines)


def wheel_wireframe(center, radius: float, width: float, segments: int = 16):
    """A wheel spinning about X"""
    samples, lines = _wheel_template(segments)
    verts = [
        (
            center[0] + side * width,
            center[1] + cosine * radius,
            center[2] + sine * radius,
        )
        for side in (-0.5, 0.5)
        for cosine, sine in samples
    ]
    return verts, lines
