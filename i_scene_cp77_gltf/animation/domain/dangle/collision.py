import numpy as np

from ....bartmoss.rounded_shapes import (
    directed_box_projection,
    directed_rotational_projection,
    rounded_box_correction,
    rounded_box_signed_distances,
    shortest_path_rotational_projection,
    swept_capsule_box_overlaps,
)

# Slack on the reach test below; far larger than the rounding in the distances it bounds.
_REACH_MARGIN = 1e-4


def capsule_axis_local(shape_type, extents):
    """Shape-space unit axis of a collision shape's capsule"""
    axis = np.zeros(3, dtype=np.float32)
    if shape_type == "CAPSULE":
        axis[int(np.argmax(np.abs(np.asarray(extents, dtype=np.float32))))] = 1.0
    else:
        axis[2] = 1.0
    return axis


def _to_shape_space(shape, points_ms):
    points = np.asarray(points_ms, dtype=np.float32)
    return (points - shape["pos_ms"]) @ shape["rot_mat"]


def _from_shape_direction(shape, vectors_ss):
    vectors = np.asarray(vectors_ss, dtype=np.float32)
    return vectors @ shape["inv_rot_mat"]


def project_shortest_path_position(shape, position_ms, particle_radius):
    position = np.asarray(position_ms, dtype=np.float32)
    position_ss = _to_shape_space(shape, position)
    correction_ss = rounded_box_correction(
        shape["extents"], shape["radius"], position_ss, particle_radius
    )
    return position + _from_shape_direction(shape, correction_ss)


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
    direction_ss = (axis @ shape["rot_mat"]).astype(np.float64)
    projection = directed_box_projection(
        shape["extents"],
        shape["radius"],
        position_ss,
        direction_ss,
        height_extent,
        particle_radius,
    )
    return position - axis.astype(np.float32) * float(projection)


def current_shape_stack(system, shapes):
    """Stacked current positions, rotations, extents, radii and extent lengths of a shape list"""
    current = tuple(shape["cur_pos64"] for shape in shapes)
    entry = system.shape_stacks.get(id(shapes))
    if (
        entry is not None
        and entry[0] is shapes
        and len(entry[1]) == len(current)
        and all(old is new for old, new in zip(entry[1], current))
    ):
        return entry[2]
    extents = np.stack(
        [np.asarray(shape["extents"], dtype=np.float32) for shape in shapes]
    )
    extents64 = extents.astype(np.float64)
    stack = (
        np.stack(current),
        np.stack([shape["cur_rot64"] for shape in shapes]),
        extents,
        np.asarray([float(shape["radius"]) for shape in shapes], dtype=np.float64),
        np.sqrt(np.einsum("ij,ij->i", extents64, extents64)),
    )
    system.shape_stacks[id(shapes)] = (shapes, current, stack)
    return stack


def respond_to_collisions(system, shapes, workspace, directed_axes):
    if not shapes:
        return
    shortest_indices = workspace["collision_shortest_indices"]
    directed_indices = workspace["collision_directed_indices"]

    for shape in shapes:
        if shortest_indices.size:
            positions_ss = _to_shape_space(shape, system.pos_ms[shortest_indices])
            correction_ss = rounded_box_correction(
                shape["extents"],
                shape["radius"],
                positions_ss,
                system.col_radius[shortest_indices],
            )
            system.pos_ms[shortest_indices] += _from_shape_direction(
                shape, correction_ss
            )

        for particle_index in directed_indices:
            particle_index = int(particle_index)
            system.pos_ms[particle_index] = project_directional_capsule_position(
                shape,
                system.pos_ms[particle_index],
                directed_axes[particle_index],
                system.col_height[particle_index],
                system.col_radius[particle_index],
            )


def respond_to_cone_collision_at(system, constraint_index, shapes, cone_frame):
    row = system.cone_collision_rows[constraint_index]
    if row is None or not shapes:
        return
    projection_type = row.projection_type
    capsule_length = row.capsule_length
    capsule_radius = row.capsule_radius

    attachment_position = system.pos_ms[row.attachment].copy()
    constrained_position = system.pos_ms[row.particle].copy()
    parent_to_bob = constrained_position - attachment_position
    distance = float(np.linalg.norm(parent_to_bob))
    if distance <= 1e-8:
        return
    direction_ms = parent_to_bob / distance

    positions, rotations, extents, radii, extent_lengths = current_shape_stack(
        system, shapes
    )
    offsets = attachment_position - positions
    # Every point of the swept capsule lies within capsule_length of the attachment and every point
    # of a box within its extents' length of its centre, so a shape farther than that plus the
    # combined radius can neither overlap the capsule nor be touched, whatever the direction.
    reachable = np.flatnonzero(
        np.sqrt(np.einsum("ij,ij->i", offsets, offsets)) - extent_lengths
        <= capsule_length + np.maximum(0.0, radii + capsule_radius) + _REACH_MARGIN
    )
    if not reachable.size:
        return
    if reachable.size < len(shapes):
        shapes = [shapes[index] for index in reachable]
        offsets, rotations, extents, radii = (
            offsets[reachable],
            rotations[reachable],
            extents[reachable],
            radii[reachable],
        )
    attachments_ss = np.matmul(offsets[:, np.newaxis, :], rotations)[:, 0, :]
    # A shape is projected against only when the swept capsule overlaps it and the
    # attachment is not already touching it. The touch test does not depend on the
    # direction, so it is evaluated once, and only for shapes the capsule overlaps.
    touching = np.zeros(len(shapes), dtype=bool)
    touch_tested = np.zeros(len(shapes), dtype=bool)

    # Shapes are handled in order and a projection changes the direction the
    # remaining shapes are tested with, so re-test only after a projection.
    first = 0
    while first < len(shapes):
        directions_ss = np.matmul(direction_ms, rotations[first:])
        overlapping = np.flatnonzero(
            swept_capsule_box_overlaps(
                extents[first:],
                radii[first:],
                attachments_ss[first:],
                directions_ss,
                capsule_length,
                capsule_radius,
            )
            < -1e-7
        )
        untested = first + overlapping[~touch_tested[first + overlapping]]
        if untested.size:
            touching[untested] = (
                rounded_box_signed_distances(
                    extents[untested],
                    radii[untested],
                    attachments_ss[untested],
                    capsule_radius,
                )
                < 0.001
            )
            touch_tested[untested] = True
        candidates = overlapping[~touching[first + overlapping]]
        if not candidates.size:
            return
        local_index = int(candidates[0])
        shape_index = first + local_index
        first = shape_index + 1
        shape = shapes[shape_index]
        current_rotation = rotations[shape_index]
        attachment_ss = attachments_ss[shape_index]
        direction_ss = directions_ss[local_index]
        if projection_type == 1:
            projected_ss = shortest_path_rotational_projection(
                shape["extents"],
                shape["radius"],
                attachment_ss,
                direction_ss,
                capsule_length,
                capsule_radius,
            )
        elif projection_type == 2 and row.cone_type == 1:
            orthogonal_ms = cone_frame.collision_orthogonal
            axis_ss = np.asarray(
                np.asarray(
                    (-orthogonal_ms[0], -orthogonal_ms[1], -orthogonal_ms[2]),
                    dtype=np.float64,
                )
                @ current_rotation,
                dtype=np.float64,
            )
            projected_ss = directed_rotational_projection(
                shape["extents"],
                shape["radius"],
                attachment_ss,
                direction_ss,
                capsule_length,
                capsule_radius,
                axis_ss,
            )
        else:
            continue
        projected_length = float(np.linalg.norm(projected_ss))
        if projected_length <= 1e-8:
            continue
        direction_ms = np.asarray(
            (projected_ss / projected_length) @ current_rotation.T,
            dtype=np.float64,
        )
        constrained_position = attachment_position + direction_ms * distance
        system.pos_ms[row.particle] = constrained_position
