import math
from typing import NamedTuple

import numpy as np

from ....bartmoss import single
from ....bartmoss.geometry import project_ellipsoid_offset, ray_sphere_point_nearest
from .collision import respond_to_cone_collision_at

CONSTRAINT_LINK = 0
CONSTRAINT_ELLIPSOID = 1
CONSTRAINT_CONE = 2

LINK_TYPES = {
    "FIXED": 0,
    "VARIABLE": 1,
    "GREATER": 2,
    "CLOSER": 3,
}
CONE_TYPES = {
    "CONE": 0,
    "HINGE_PLANE": 1,
    "HALF_CONE": 2,
}
CONE_PROJECTION_TYPES = {
    "DISABLED": 0,
    "SHORTEST_PATH_ROTATIONAL": 1,
    "DIRECTED_ROTATIONAL": 2,
}


class LinkRow(NamedTuple):
    first: int
    second: int
    link_type: int
    lower_length: np.float32
    upper_length: np.float32
    first_factor: np.float32
    second_factor: np.float32


class EllipsoidRow(NamedTuple):
    particle: int
    radius: float
    lower_scale: float
    upper_scale: float


class ConeRow(NamedTuple):
    particle: int
    attachment: int
    cone_type: int
    cosine: float
    half_sine: float
    half_cosine: float


class ConeCollisionRow(NamedTuple):
    particle: int
    attachment: int
    projection_type: int
    cone_type: int
    capsule_length: float
    capsule_radius: float


def _is_free(system, index):
    return bool(system.is_free[index] and system.active_mask[index])


def compile_rows(system):
    """Per-constraint static data, with None for constraints whose particles can never move"""
    system.link_rows = []
    if system.link_idx_a is not None:
        for ci in range(len(system.link_idx_a)):
            first = int(system.link_idx_a[ci])
            second = int(system.link_idx_b[ci])
            free1 = _is_free(system, first)
            free2 = _is_free(system, second)
            if not free1 and not free2:
                system.link_rows.append(None)
                continue
            if free1 and free2:
                mass1 = system.mass[first]
                mass2 = system.mass[second]
                total_mass = mass1 + mass2
                factor1 = np.float32(1.0) - mass1 / total_mass
                factor2 = np.float32(1.0) - mass2 / total_mass
            else:
                factor1 = np.float32(1.0 if free1 else 0.0)
                factor2 = np.float32(1.0 if free2 else 0.0)
            rest_length = system.link_rest[ci]
            system.link_rows.append(
                LinkRow(
                    first,
                    second,
                    int(system.link_types[ci]),
                    system.link_lower[ci] * rest_length,
                    system.link_upper[ci] * rest_length,
                    factor1,
                    factor2,
                )
            )

    system.ellipsoid_rows = []
    if system.ell_idx is not None:
        for ci in range(len(system.ell_idx)):
            particle = int(system.ell_idx[ci])
            system.ellipsoid_rows.append(
                EllipsoidRow(
                    particle,
                    float(system.ell_radii[ci]),
                    float(system.ell_s1[ci]),
                    float(system.ell_s2[ci]),
                )
                if _is_free(system, particle)
                else None
            )

    system.cone_rows = []
    system.cone_collision_rows = []
    if system.cone_idx is not None:
        for ci in range(len(system.cone_idx)):
            particle = int(system.cone_idx[ci])
            attachment = int(system.cone_attach[ci])
            free = _is_free(system, particle)
            system.cone_rows.append(
                ConeRow(
                    particle,
                    attachment,
                    int(system.cone_type[ci]),
                    float(system.cone_cos[ci]),
                    float(system.cone_sin_hh[ci]),
                    float(system.cone_cos_hh[ci]),
                )
                if free
                else None
            )
            projection_type = int(system.cone_proj_type[ci])
            system.cone_collision_rows.append(
                ConeCollisionRow(
                    particle,
                    attachment,
                    projection_type,
                    int(system.cone_type[ci]),
                    max(0.0, float(system.cone_col_height[ci]) * 2.0),
                    max(0.0, float(system.cone_col_radius[ci])),
                )
                if free and projection_type != 0
                else None
            )


_MIN_LINK_LENGTH = np.float32(1e-6)
_MIN_LINK_ERROR = np.float32(1e-7)
_UNIT_X = np.array((1.0, 0.0, 0.0), dtype=np.float32)


def satisfy_link_at(system, constraint_index):
    row = system.link_rows[constraint_index]
    if row is None:
        return
    pos = system.pos_ms
    # float32 throughout, component by component.
    delta = pos[row.second] - pos[row.first]
    dx, dy, dz = delta
    current_length = np.float32(math.sqrt(float(dx * dx + dy * dy + dz * dz)))
    if current_length < _MIN_LINK_LENGTH:
        normal = _UNIT_X
    else:
        normal = delta * (np.float32(1.0) / current_length)

    link_type = row.link_type
    if link_type == 0:
        desired_length = row.lower_length
    elif link_type == 1:
        desired_length = min(max(current_length, row.lower_length), row.upper_length)
    elif link_type == 2:
        desired_length = max(current_length, row.lower_length)
    else:
        desired_length = min(current_length, row.upper_length)

    error = current_length - desired_length
    if abs(error) <= _MIN_LINK_ERROR:
        return
    correction1 = error * row.first_factor
    correction2 = error * row.second_factor
    if correction1 != 0.0:
        pos[row.first] += normal * correction1
    if correction2 != 0.0:
        pos[row.second] -= normal * correction2


def satisfy_ellipsoid_at(system, constraint_index, ellipsoid_frame):
    row = system.ellipsoid_rows[constraint_index]
    if row is None:
        return

    center, rotation, inverse = ellipsoid_frame
    offset = single.sub(system.pos_ms[row.particle].tolist(), center)
    offset_es = single.rotate(inverse, offset)
    direction_es = (
        single.normalized(offset_es) if single.length(offset_es) > 1e-4 else offset_es
    )
    z_scale = row.lower_scale if direction_es[2] < 0.0 else row.upper_scale
    corrected_es = project_ellipsoid_offset(offset_es, row.radius, z_scale)
    system.pos_ms[row.particle] = single.add(
        center, single.rotate(rotation, single.vec3(*corrected_es))
    )


def satisfy_cone_at(system, constraint_index, cone_frame):
    row = system.cone_rows[constraint_index]
    initial_axis = cone_frame.initial_axis
    if row is None or initial_axis is None:
        return

    constrained_position = system.pos_ms[row.particle].tolist()
    attachment_position = system.pos_ms[row.attachment].tolist()
    cone_to_particle = single.sub(constrained_position, cone_frame.origin)
    constraint_type = row.cone_type
    orthogonal_axis = cone_frame.orthogonal_axis
    if constraint_type != 0 and orthogonal_axis is not None:
        orthogonal_component = single.dot(cone_to_particle, orthogonal_axis)
        if constraint_type == 1 or orthogonal_component > 0.0:
            cone_to_particle = single.sub(
                cone_to_particle, single.scale(orthogonal_axis, orthogonal_component)
            )

    if single.length_squared(cone_to_particle) < 1e-12:
        return
    cone_to_particle = single.normalized(cone_to_particle)
    if single.dot(initial_axis, cone_to_particle) < row.cosine:
        perpendicular = single.cross(initial_axis, cone_to_particle)
        if single.length(perpendicular) > 1e-6:
            perpendicular = single.normalized(perpendicular)
            half_sine = row.half_sine
            rotation = single.quat(
                row.half_cosine,
                perpendicular[0] * half_sine,
                perpendicular[1] * half_sine,
                perpendicular[2] * half_sine,
            )
            cone_to_particle = single.normalized(single.rotate(rotation, initial_axis))

    original_distance = single.length(
        single.sub(attachment_position, constrained_position)
    )
    if original_distance < 1e-6:
        return
    system.pos_ms[row.particle] = ray_sphere_point_nearest(
        cone_frame.origin,
        cone_to_particle,
        attachment_position,
        original_distance,
        constrained_position,
    )


def satisfy_in_authored_order(system, node_index, frame):
    for kind, constraint_index in system.node_constraint_order[node_index]:
        if kind == CONSTRAINT_LINK:
            satisfy_link_at(system, constraint_index)
        elif kind == CONSTRAINT_ELLIPSOID:
            satisfy_ellipsoid_at(
                system, constraint_index, frame.ellipsoids[constraint_index]
            )
        elif kind == CONSTRAINT_CONE:
            satisfy_cone_at(system, constraint_index, frame.cones[constraint_index])


def respond_cone_collisions_in_authored_order(system, node_index, shapes, frame):
    if system.cone_idx is None or not shapes:
        return
    for kind, constraint_index in system.node_constraint_order[node_index]:
        if kind == CONSTRAINT_CONE:
            respond_to_cone_collision_at(
                system, constraint_index, shapes, frame.cones[constraint_index]
            )
