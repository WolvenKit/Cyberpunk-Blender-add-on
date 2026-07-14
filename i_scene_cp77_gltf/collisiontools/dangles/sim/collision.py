
import math
import numpy as np
import bpy
from mathutils import Vector, Quaternion, Matrix
from . import spaces


def _compile_shape(sim, shape):
    ls_quat = Quaternion(shape.rotation_ls_quat)
    ls_mat = ls_quat.to_matrix().to_4x4()
    ls_mat.translation = Vector(shape.offset_ls)
    adjusted_ls = spaces.re_local_transform_to_blender_bone(
        ls_mat, sim.arm_obj
    )

    pb = sim.arm_obj.pose.bones.get(shape.bone_name)
    current_ms = pb.matrix @ adjusted_ls if pb else Matrix.Identity(4)
    extents = np.array((
        shape.x_box_extent, shape.y_box_extent, shape.height_extent
    ), dtype=np.float32)
    capsule_axis_local = np.zeros(3, dtype=np.float32)
    if shape.shape_type == 'CAPSULE':
        capsule_axis_local[int(np.argmax(np.abs(extents)))] = 1.0
    else:
        capsule_axis_local[2] = 1.0

    return {
        'bone_name': shape.bone_name,
        'shape_type': shape.shape_type,
        'is_capsule': shape.shape_type == 'CAPSULE',
        'radius': shape.radius,
        'height': float(np.max(np.abs(extents))),
        'extents': extents,
        'capsule_axis_local': capsule_axis_local,
        'ls_mat': adjusted_ls,
        'prev_xform_ms': current_ms.copy(),
        'cur_xform_ms': current_ms.copy(),
        'pos_ms': np.array(current_ms.translation, dtype=np.float32),
        'rot_ms': current_ms.to_quaternion(),
        'axis_ms': np.array(
            current_ms.to_quaternion() @ Vector(capsule_axis_local),
            dtype=np.float32,
        ),
    }


def _authored_shape_key(shape):
    return (
        shape.bone_name, shape.shape_type, round(float(shape.radius), 7),
        round(float(shape.x_box_extent), 7),
        round(float(shape.y_box_extent), 7),
        round(float(shape.height_extent), 7),
        *(round(float(value), 7) for value in shape.offset_ls),
        *(round(float(value), 7) for value in shape.rotation_ls_quat),
    )


def compile_collision_shapes(sim):
    sim._node_col_shapes = []
    draw_shapes = []
    draw_keys = set()

    has_node_local_shapes = any(
        len(dnode.collision_shapes) > 0 for dnode in sim.state.dangle_nodes
    )

    for dnode in sim.state.dangle_nodes:
        source_shapes = (
            dnode.collision_shapes
            if has_node_local_shapes
            else sim.state.collision_shapes
        )
        node_shapes = []
        for authored_shape in source_shapes:
            compiled = _compile_shape(sim, authored_shape)
            node_shapes.append(compiled)
            key = _authored_shape_key(authored_shape)
            if key not in draw_keys:
                draw_keys.add(key)
                draw_shapes.append(compiled)
        sim._node_col_shapes.append(node_shapes)

    if not sim.state.dangle_nodes:
        draw_shapes = [
            _compile_shape(sim, shape) for shape in sim.state.collision_shapes
        ]
    sim.col_shapes = draw_shapes


def update_collision_transforms_begin(sim, shapes=None):
    shapes = sim.col_shapes if shapes is None else shapes
    for shape in shapes:
        shape['prev_xform_ms'] = shape['cur_xform_ms'].copy()
        pb = sim.arm_obj.pose.bones.get(shape['bone_name'])
        if pb:
            shape['cur_xform_ms'] = pb.matrix @ shape['ls_mat']


def initialize_collision_transforms(sim, shapes=None):
    shapes = sim.col_shapes if shapes is None else shapes
    for shape in shapes:
        pb = sim.arm_obj.pose.bones.get(shape['bone_name'])
        current = (
            pb.matrix @ shape['ls_mat']
            if pb is not None else shape['cur_xform_ms'].copy()
        )
        shape['prev_xform_ms'] = current.copy()
        shape['cur_xform_ms'] = current.copy()
        shape['pos_ms'] = np.array(current.translation, dtype=np.float32)
        shape['rot_ms'] = current.to_quaternion()
        if shape['is_capsule']:
            shape['axis_ms'] = np.array(
                shape['rot_ms'] @ Vector(shape['capsule_axis_local']),
                dtype=np.float32,
            )


def update_collision_transforms(sim, frame_progress, shapes=None):
    shapes = sim.col_shapes if shapes is None else shapes
    for shape in shapes:
        prev = shape['prev_xform_ms']
        cur = shape['cur_xform_ms']
        shape['pos_ms'] = np.array(
            prev.translation.lerp(cur.translation, frame_progress),
            dtype=np.float32,
        )
        shape['rot_ms'] = prev.to_quaternion().slerp(
            cur.to_quaternion(), frame_progress
        )
        if shape['is_capsule']:
            shape['axis_ms'] = np.array(
                shape['rot_ms'] @ Vector(shape['capsule_axis_local']),
                dtype=np.float32,
            )

def _closest_point_on_segment(p, a, b):
    """Closest point on segment a→b to each point in p (batched)."""
    ab = b - a
    ap = p - a
    ab_sq = np.sum(ab * ab, axis=-1)
    ab_sq = np.where(ab_sq < 1e-6, 1.0, ab_sq)
    t = np.clip(np.sum(ap * ab, axis=-1) / ab_sq, 0.0, 1.0)
    return a + t[:, np.newaxis] * ab


def _closest_point_on_segment_single(p, a, b):
    """Closest point on segment a→b to single point p (Vector or np)."""
    ab = b - a
    ap = p - a
    ab_sq = np.dot(ab, ab)
    if ab_sq < 1e-6:
        return a.copy()
    t = max(0.0, min(1.0, np.dot(ap, ab) / ab_sq))
    return a + ab * t


def _shape_rotation_matrix(shape):
    return np.array(shape['rot_ms'].to_matrix(), dtype=np.float32)


def _to_shape_space(shape, points_ms):
    points = np.asarray(points_ms, dtype=np.float32)
    return (points - shape['pos_ms']) @ _shape_rotation_matrix(shape)


def _from_shape_direction(shape, vectors_ss):
    vectors = np.asarray(vectors_ss, dtype=np.float32)
    return vectors @ _shape_rotation_matrix(shape).T


def _rounded_shape_correction_ss(shape, points_ss, particle_radius):
    points = np.asarray(points_ss, dtype=np.float32)
    scalar_input = points.ndim == 1
    if scalar_input:
        points = points[np.newaxis, :]

    extents = np.abs(shape['extents'])
    total_radius = float(shape['radius']) + np.asarray(
        particle_radius, dtype=np.float32
    )
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
            delta[penetrating_outside]
            / distance[penetrating_outside, np.newaxis]
        )
        correction[penetrating_outside] = direction * (
            total_radius[penetrating_outside] - distance[penetrating_outside]
        )[:, np.newaxis]

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


def _rounded_shape_signed_distance(shape, point_ss, particle_radius):
    point = np.asarray(point_ss, dtype=np.float32)
    q = np.abs(point) - np.abs(shape['extents'])
    outside = np.linalg.norm(np.maximum(q, 0.0))
    inside = min(float(np.max(q)), 0.0)
    return outside + inside - float(shape['radius']) - float(particle_radius)


def project_shortest_path_position(shape, position_ms, particle_radius):
    position = np.asarray(position_ms, dtype=np.float32)
    position_ss = _to_shape_space(shape, position)
    correction_ss = _rounded_shape_correction_ss(
        shape, position_ss, particle_radius
    )
    return position + _from_shape_direction(shape, correction_ss)


def _directed_projection_check_corner(position, direction, radius):
    b = float(np.dot(position, direction))
    discriminant = b * b + radius * radius - float(np.dot(position, position))
    if discriminant < 0.0:
        return 0.0
    return -b - float(np.sqrt(discriminant))


def _directed_projection_check_edge(position, direction, half_extent, radius):
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
            return _directed_projection_check_corner(
                positive_sphere, direction, radius
            )
        if location < 0.0:
            return _directed_projection_check_corner(
                negative_sphere, direction, radius
            )
        return result if result - ((root - x) / h) < 0.0 else 0.0

    if g > 0.0:
        return 0.0
    result = 0.0
    if direction[0] < 0.0:
        result += _directed_projection_check_corner(
            positive_sphere, direction, radius
        )
    if direction[0] > 0.0:
        result += _directed_projection_check_corner(
            negative_sphere, direction, radius
        )
    return result


def directed_position_projection_ss(
    shape, position_ss, direction_ss, height_extent, particle_radius
):
    """Direct port of CollisionRoundedShape::DirectedPositionProjection."""
    position = np.asarray(position_ss, dtype=np.float64)
    direction = np.asarray(direction_ss, dtype=np.float64)
    extent = np.abs(np.asarray(shape['extents'], dtype=np.float64))
    radius = max(0.0, float(shape['radius']) + float(particle_radius))
    segment_length = max(0.0, float(height_extent)) * 2.0

    signs = np.where(direction < 0.0, -1.0, 1.0)
    reflected_position = position * signs
    reflected_direction = direction * signs

    permutations = (
        np.array(((0.0, 1.0, 0.0), (-1.0, 0.0, 0.0), (0.0, 0.0, 1.0))),
        np.identity(3),
        np.array(((1.0, 0.0, 0.0), (0.0, 0.0, -1.0), (0.0, 1.0, 0.0))),
    )

    def result_from_t(value):
        if value != 0.0 and value < segment_length:
            return segment_length - value
        return 0.0

    if float(np.sum(extent)) == 0.0:
        t = _directed_projection_check_corner(position, direction, radius)
        return result_from_t(t)
    if extent[1] + extent[2] == 0.0:
        t = _directed_projection_check_edge(
            position, direction, extent[0], radius
        )
        return result_from_t(t)
    if extent[0] + extent[2] == 0.0:
        t = _directed_projection_check_edge(
            np.array((position[1], -position[0], position[2])),
            np.array((direction[1], -direction[0], direction[2])),
            extent[1], radius,
        )
        return result_from_t(t)
    if extent[0] + extent[1] == 0.0:
        t = _directed_projection_check_edge(
            np.array((position[2], position[1], -position[0])),
            np.array((direction[2], direction[1], -direction[0])),
            extent[2], radius,
        )
        return result_from_t(t)

    for axis in range(3):
        if axis == 0:
            local_extent = np.array((extent[1], extent[0], extent[2]))
        elif axis == 1:
            local_extent = np.array((extent[0], extent[1], extent[2]))
        else:
            local_extent = np.array((extent[0], extent[2], extent[1]))

        matrix = permutations[axis]
        p = reflected_position @ matrix
        d = reflected_direction @ matrix
        if d[1] == 0.0:
            continue

        max_x = local_extent[0] + radius
        max_y = local_extent[1] + radius
        max_z = local_extent[2] + radius
        crossing = (-p[1] - max_y) / d[1]
        surface_point = np.array((
            d[0] * crossing + p[0],
            -max_y,
            d[2] * crossing + p[2],
        ))

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
            t = _directed_projection_check_edge(
                np.array((
                    p[2], p[1] + local_extent[1],
                    -p[0] + local_extent[0],
                )),
                np.array((d[2], d[1], -d[0])),
                local_extent[2], radius,
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
            t = _directed_projection_check_edge(
                np.array((
                    p[0], p[1] + local_extent[1],
                    p[2] - local_extent[2],
                )),
                d, local_extent[0], radius,
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
            t = _directed_projection_check_edge(
                np.array((
                    p[2], p[1] + local_extent[1],
                    -p[0] - local_extent[0],
                )),
                np.array((d[2], d[1], -d[0])),
                local_extent[2], radius,
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
            t = _directed_projection_check_edge(
                np.array((
                    p[0], p[1] + local_extent[1],
                    p[2] + local_extent[2],
                )),
                d, local_extent[0], radius,
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


def project_directional_capsule_position(
    shape, position_ms, axis_ms, height_extent, particle_radius
):
    position = np.asarray(position_ms, dtype=np.float32)
    axis = np.asarray(axis_ms, dtype=np.float64)
    axis_length = float(np.linalg.norm(axis))
    if axis_length < 1e-8:
        return position
    axis /= axis_length

    position_ss = _to_shape_space(shape, position).astype(np.float64)
    direction_ss = (axis @ _shape_rotation_matrix(shape)).astype(np.float64)
    projection = directed_position_projection_ss(
        shape, position_ss, direction_ss, height_extent, particle_radius
    )
    return position - axis.astype(np.float32) * float(projection)



def _segment_aabb_distance_squared(start, direction, length, extents):
    """Squared distance between a finite segment and an axis-aligned box.

    The rounded shape is an AABB Minkowski-summed with a sphere. The capsule
    overlap test therefore reduces to the segment/AABB distance compared with
    the combined corner and capsule radii. The one-dimensional objective is
    convex, so a bounded ternary search is stable for every degenerate box.
    """
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


def rounded_shape_overlap_value_ss(
    shape, position_ss, direction_ss, segment_length, capsule_radius,
):
    """Return the REDengine-style signed overlap value for a swept capsule.

    Negative values overlap, zero is tangent, and positive values are clear.
    ``position_ss`` is the capsule start and the segment extends forward along
    ``direction_ss`` for ``segment_length``.
    """
    combined_radius = max(
        0.0, float(shape['radius']) + float(capsule_radius)
    )
    distance_squared = _segment_aabb_distance_squared(
        position_ss, direction_ss, segment_length, shape['extents']
    )
    return distance_squared - combined_radius * combined_radius


def _orthogonal_unit(direction):
    direction = np.asarray(direction, dtype=np.float64)
    if abs(direction[0]) < 0.9:
        value = np.cross(direction, np.array((1.0, 0.0, 0.0)))
    else:
        value = np.cross(direction, np.array((0.0, 1.0, 0.0)))
    length = float(np.linalg.norm(value))
    if length <= 1e-15:
        return np.array((0.0, 0.0, 1.0), dtype=np.float64)
    return value / length


def _rotated_direction(direction, axis, angle):
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


def _spherical_direction(direction, tangent, angle):
    result = direction * math.cos(angle) + tangent * math.sin(angle)
    length = float(np.linalg.norm(result))
    return result / length if length > 1e-15 else direction.copy()


def _first_clear_angle(
    shape, position, direction, tangent, segment_length, capsule_radius,
    upper_angle=math.pi, coarse_steps=24,
):
    previous_angle = 0.0
    for step in range(1, coarse_steps + 1):
        angle = upper_angle * step / coarse_steps
        candidate = _spherical_direction(direction, tangent, angle)
        if rounded_shape_overlap_value_ss(
            shape, position, candidate, segment_length, capsule_radius
        ) >= -1e-7:
            lo = previous_angle
            hi = angle
            for _ in range(22):
                middle = (lo + hi) * 0.5
                candidate = _spherical_direction(
                    direction, tangent, middle
                )
                if rounded_shape_overlap_value_ss(
                    shape, position, candidate,
                    segment_length, capsule_radius,
                ) >= -1e-7:
                    hi = middle
                else:
                    lo = middle
            return hi
        previous_angle = angle
    return None


def shortest_path_rotational_projection_ss(
    shape, position_ss, direction_ss, segment_length, capsule_radius,
):
    """Project a penetrating swept capsule with the smallest rotation.

    This evaluates the same geometric problem as
    ``CollisionRoundedShape::ShortestPathRotationalProjection`` for every
    rounded-shape extent combination. The optimized engine routine enumerates
    analytic face/edge/corner branches; this implementation minimizes the
    angular displacement directly against the exact rounded-box overlap test.
    """
    position = np.asarray(position_ss, dtype=np.float64)
    direction = np.asarray(direction_ss, dtype=np.float64)
    segment_length = max(0.0, float(segment_length))
    length = float(np.linalg.norm(direction))
    if length <= 1e-15 or segment_length == 0.0:
        return np.zeros(3, dtype=np.float64)
    direction /= length

    if rounded_shape_overlap_value_ss(
        shape, position, direction, segment_length, capsule_radius
    ) >= -1e-7:
        return direction * segment_length

    tangent_u = _orthogonal_unit(direction)
    tangent_v = np.cross(direction, tangent_u)
    tangent_v /= max(float(np.linalg.norm(tangent_v)), 1e-15)

    best_angle = None
    best_azimuth = 0.0
    azimuth_steps = 48
    for azimuth_index in range(azimuth_steps):
        azimuth = math.tau * azimuth_index / azimuth_steps
        tangent = (
            tangent_u * math.cos(azimuth)
            + tangent_v * math.sin(azimuth)
        )
        angle = _first_clear_angle(
            shape, position, direction, tangent,
            segment_length, capsule_radius,
        )
        if angle is not None and (
            best_angle is None or angle < best_angle
        ):
            best_angle = angle
            best_azimuth = azimuth

    if best_angle is None:
        return direction * segment_length

    # Refine the azimuth while resolving the boundary angle each time.
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
            tangent = (
                tangent_u * math.cos(azimuth)
                + tangent_v * math.sin(azimuth)
            )
            angle = _first_clear_angle(
                shape, position, direction, tangent,
                segment_length, capsule_radius,
                upper_angle=min(math.pi, best_angle + azimuth_step),
                coarse_steps=12,
            )
            if angle is not None and angle < best_angle:
                best_angle = angle
                best_azimuth = azimuth
        azimuth_step *= 0.5

    tangent = (
        tangent_u * math.cos(best_azimuth)
        + tangent_v * math.sin(best_azimuth)
    )
    return _spherical_direction(
        direction, tangent, best_angle
    ) * segment_length


def directed_rotational_projection_ss(
    shape, position_ss, direction_ss, segment_length, capsule_radius,
    rotation_axis_ss,
):
    """Project by rotating only in the authored directed plane.

    The sign of ``rotation_axis_ss`` selects the permitted direction, matching
    the handed directed axis passed by the Pendulum HingePlane path.
    """
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
        return shortest_path_rotational_projection_ss(
            shape, position, direction, segment_length, capsule_radius
        )
    axis /= axis_length

    if rounded_shape_overlap_value_ss(
        shape, position, direction, segment_length, capsule_radius
    ) >= -1e-7:
        return direction * segment_length

    # A direction parallel to the rotation axis cannot be changed by the
    # directed projection.
    if float(np.linalg.norm(np.cross(axis, direction))) <= 1e-12:
        return direction * segment_length

    previous_angle = 0.0
    coarse_steps = 128
    for step in range(1, coarse_steps + 1):
        angle = math.tau * step / coarse_steps
        candidate = _rotated_direction(direction, axis, angle)
        if rounded_shape_overlap_value_ss(
            shape, position, candidate, segment_length, capsule_radius
        ) >= -1e-7:
            lo = previous_angle
            hi = angle
            for _ in range(24):
                middle = (lo + hi) * 0.5
                candidate = _rotated_direction(direction, axis, middle)
                if rounded_shape_overlap_value_ss(
                    shape, position, candidate,
                    segment_length, capsule_radius,
                ) >= -1e-7:
                    hi = middle
                else:
                    lo = middle
            return _rotated_direction(direction, axis, hi) * segment_length
        previous_angle = angle

    return direction * segment_length

def respond_to_collisions_vectorized(
    sim, frame_progress, particle_indices=None, shapes=None
):
    shapes = sim.col_shapes if shapes is None else shapes
    if not shapes:
        return

    update_collision_transforms(sim, frame_progress, shapes)
    if particle_indices is None:
        particle_indices = np.arange(sim.num_particles, dtype=np.int32)
    else:
        particle_indices = np.asarray(particle_indices, dtype=np.int32)
    if particle_indices.size == 0:
        return

    active = (
        sim.is_free[particle_indices]
        & sim.active_mask[particle_indices]
        & (sim.proj_type[particle_indices] > 0)
    )
    indices = particle_indices[active]
    if indices.size == 0:
        return

    projection_types = sim.proj_type[indices]
    particle_radii = sim.col_radius[indices]

    for shape in shapes:
        shortest_mask = projection_types == 1
        if np.any(shortest_mask):
            shortest_indices = indices[shortest_mask]
            positions_ss = _to_shape_space(
                shape, sim.pos_ms[shortest_indices]
            )
            correction_ss = _rounded_shape_correction_ss(
                shape, positions_ss, particle_radii[shortest_mask]
            )
            sim.pos_ms[shortest_indices] += _from_shape_direction(
                shape, correction_ss
            )

        directed_mask = projection_types == 2
        if not np.any(directed_mask):
            continue

        directed_indices = indices[directed_mask]
        for particle_index in directed_indices:
            xform = sim._interp_bone_xform[particle_index]
            axis_ls = Vector(sim.col_axis_ls[particle_index])
            if axis_ls.length_squared < 1e-8:
                axis_ls = spaces.re_axis_to_blender_bone(
                    (1.0, 0.0, 0.0), sim.arm_obj
                )
            axis_ms = np.array(
                xform.to_quaternion() @ axis_ls.normalized(),
                dtype=np.float32,
            )
            sim.pos_ms[particle_index] = project_directional_capsule_position(
                shape,
                sim.pos_ms[particle_index],
                axis_ms,
                sim.col_height[particle_index],
                sim.col_radius[particle_index],
            )


def respond_to_cone_collisions(sim, frame_progress, shapes=None):
    """Apply REDengine rotational capsule projection to Dyng cone constraints."""
    if not hasattr(sim, 'cone_idx') or sim.cone_idx is None:
        return
    shapes = sim.col_shapes if shapes is None else shapes
    if not shapes:
        return
    update_collision_transforms(sim, frame_progress, shapes)

    for ci in range(len(sim.cone_idx)):
        constrained_index = int(sim.cone_idx[ci])
        attachment_index = int(sim.cone_attach[ci])
        projection_type = int(sim.cone_proj_type[ci])
        if projection_type == 0 or not sim.is_free[constrained_index]:
            continue
        attachment_position = sim.pos_ms[attachment_index].copy()
        constrained_position = sim.pos_ms[constrained_index].copy()
        parent_to_bob = constrained_position - attachment_position
        distance = float(np.linalg.norm(parent_to_bob))
        if distance <= 1e-8:
            continue
        direction_ms = parent_to_bob / distance
        capsule_length = max(0.0, float(sim.cone_col_height[ci]) * 2.0)
        capsule_radius = max(0.0, float(sim.cone_col_radius[ci]))

        for shape in shapes:
            inverse_rotation = shape['rot_ms'].conjugated()
            attachment_ss = np.asarray(
                inverse_rotation @ Vector(attachment_position - shape['pos_ms']),
                dtype=np.float64,
            )
            direction_ss = np.asarray(
                inverse_rotation @ Vector(direction_ms), dtype=np.float64
            )
            if _shape_distance_simplified(shape, attachment_ss, capsule_radius) < 0.001:
                continue
            if rounded_shape_overlap_value_ss(
                shape, attachment_ss, direction_ss, capsule_length, capsule_radius
            ) >= -1e-7:
                continue
            if projection_type == 1:
                projected_ss = shortest_path_rotational_projection_ss(
                    shape, attachment_ss, direction_ss, capsule_length, capsule_radius
                )
            elif projection_type == 2 and int(sim.cone_type[ci]) == 1:
                cone_transform = (
                    sim._interp_bone_xform[attachment_index]
                    @ sim.cone_xform_ls[ci]
                )
                orthogonal_ms = cone_transform.to_quaternion() @ Vector((0.0, 0.0, 1.0))
                axis_ss = np.asarray(
                    inverse_rotation @ (-orthogonal_ms), dtype=np.float64
                )
                projected_ss = directed_rotational_projection_ss(
                    shape, attachment_ss, direction_ss, capsule_length,
                    capsule_radius, axis_ss,
                )
            else:
                continue
            projected_length = float(np.linalg.norm(projected_ss))
            if projected_length <= 1e-8:
                continue
            direction_ms = np.asarray(
                shape['rot_ms'] @ Vector(projected_ss / projected_length),
                dtype=np.float64,
            )
            constrained_position = attachment_position + direction_ms * distance
            sim.pos_ms[constrained_index] = constrained_position

def _shape_distance_simplified(shape, point_ss, particle_radius):
    return _rounded_shape_signed_distance(shape, point_ss, particle_radius)


def _perpendicular(v):
    """Return a vector perpendicular to v."""
    if abs(v[0]) < 0.9:
        cross = np.cross(v, np.array([1, 0, 0], dtype=np.float32))
    else:
        cross = np.cross(v, np.array([0, 1, 0], dtype=np.float32))
    n = np.linalg.norm(cross)
    return cross / n if n > 1e-6 else np.array([0, 1, 0], dtype=np.float32)
