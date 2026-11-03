from __future__ import annotations

import math
import time
from dataclasses import dataclass
from statistics import median

import numpy as np

EPSILON = 1.0e-7


def bounds_intersect(first, second, epsilon=EPSILON):
    """Whether two (minimum, maximum) boxes overlap or touch, within epsilon"""
    return all(
        first[0][axis] <= second[1][axis] + epsilon
        and first[1][axis] + epsilon >= second[0][axis]
        for axis in range(3)
    )


def triangle_box_classes_and_planes(local_positions, minimum, maximum):
    positions = np.asarray(local_positions, dtype=np.float64)
    lower = np.asarray(minimum, dtype=np.float64)
    upper = np.asarray(maximum, dtype=np.float64)
    below_vertices = positions < lower - EPSILON
    above_vertices = positions > upper + EPSILON
    below = np.all(below_vertices, axis=1)
    above = np.all(above_vertices, axis=1)
    outside = np.any(below | above, axis=1)
    inside = np.all(~below_vertices & ~above_vertices, axis=(1, 2))

    classes = np.zeros(len(positions), dtype=np.int8)
    classes[outside] = -1
    classes[inside & ~outside] = 1

    planes = np.zeros(len(positions), dtype=np.uint8)
    for axis in range(3):
        planes |= np.any(below_vertices[:, :, axis], axis=1).astype(np.uint8) << (
            axis * 2
        )
        planes |= np.any(above_vertices[:, :, axis], axis=1).astype(np.uint8) << (
            axis * 2 + 1
        )
    return classes, planes


def triangle_box_classes(local_positions, minimum, maximum):
    classes, _planes = triangle_box_classes_and_planes(
        local_positions,
        minimum,
        maximum,
    )
    return classes


class BoundsGrid:
    __slots__ = (
        "bounds",
        "cell_size",
        "cells",
        "large_indices",
        "max_query_cells",
    )

    def __init__(
        self,
        bounds,
        *,
        max_item_cells=256,
        max_query_cells=4096,
    ):
        self.bounds = tuple(bounds)
        positive_extents = [
            extent
            for item in self.bounds
            for axis in range(3)
            if (extent := float(item[1][axis]) - float(item[0][axis])) > EPSILON
        ]
        self.cell_size = max(
            0.25,
            float(median(positive_extents)) if positive_extents else 1.0,
        )
        self.cells = {}
        self.large_indices = set()
        self.max_query_cells = max(1, int(max_query_cells))

        for index, item_bounds in enumerate(self.bounds):
            limits = self._limits(item_bounds)
            if self._cell_count(limits) > max_item_cells:
                self.large_indices.add(index)
                continue
            for key in self._keys(limits):
                self.cells.setdefault(key, []).append(index)

    def _limits(self, bounds):
        minimum = tuple(
            math.floor(float(bounds[0][axis]) / self.cell_size) for axis in range(3)
        )
        maximum = tuple(
            math.floor(float(bounds[1][axis]) / self.cell_size) for axis in range(3)
        )
        return minimum, maximum

    @staticmethod
    def _cell_count(limits):
        minimum, maximum = limits
        return math.prod(maximum[axis] - minimum[axis] + 1 for axis in range(3))

    @staticmethod
    def _keys(limits):
        minimum, maximum = limits
        for x in range(minimum[0], maximum[0] + 1):
            for y in range(minimum[1], maximum[1] + 1):
                for z in range(minimum[2], maximum[2] + 1):
                    yield x, y, z

    def query_indices(self, bounds):
        if not self.bounds:
            return ()

        limits = self._limits(bounds)
        if self._cell_count(limits) > self.max_query_cells:
            candidates = range(len(self.bounds))
        else:
            candidate_set = set(self.large_indices)
            for key in self._keys(limits):
                candidate_set.update(self.cells.get(key, ()))
            candidates = candidate_set

        return tuple(
            index
            for index in candidates
            if bounds_intersect(self.bounds[index], bounds)
        )


@dataclass(slots=True, frozen=True)
class ClipVertex:
    position: tuple[float, float, float]
    weights: tuple[float, float, float]


def _interpolate(first, second, amount):
    return ClipVertex(
        tuple(
            first.position[index]
            + (second.position[index] - first.position[index]) * amount
            for index in range(3)
        ),
        tuple(
            first.weights[index]
            + (second.weights[index] - first.weights[index]) * amount
            for index in range(3)
        ),
    )


def _clip_plane(vertices, axis, limit, keep_greater):
    if not vertices:
        return []

    result = []
    previous = vertices[-1]
    previous_distance = previous.position[axis] - limit
    previous_inside = (
        previous_distance >= -EPSILON if keep_greater else previous_distance <= EPSILON
    )
    for current in vertices:
        current_distance = current.position[axis] - limit
        current_inside = (
            current_distance >= -EPSILON
            if keep_greater
            else current_distance <= EPSILON
        )
        if current_inside != previous_inside:
            denominator = previous_distance - current_distance
            amount = (
                previous_distance / denominator if abs(denominator) > EPSILON else 0.0
            )
            result.append(_interpolate(previous, current, amount))
        if current_inside:
            result.append(current)
        previous = current
        previous_distance = current_distance
        previous_inside = current_inside
    return result


def clip_vertices_by_weighted_scalar(vertices, source_values, minimum):
    if not vertices:
        return ()

    def distance(vertex):
        return sum(
            float(vertex.weights[index]) * float(source_values[index])
            for index in range(3)
        ) - float(minimum)

    result = []
    previous = vertices[-1]
    previous_distance = distance(previous)
    previous_inside = previous_distance >= -EPSILON
    for current in vertices:
        current_distance = distance(current)
        current_inside = current_distance >= -EPSILON
        if current_inside != previous_inside:
            denominator = previous_distance - current_distance
            amount = (
                previous_distance / denominator if abs(denominator) > EPSILON else 0.0
            )
            result.append(_interpolate(previous, current, amount))
        if current_inside:
            result.append(current)
        previous = current
        previous_distance = current_distance
        previous_inside = current_inside
    return tuple(result) if len(result) >= 3 else ()


def clip_triangle_to_box(positions, minimum, maximum, plane_mask=None):
    vertices = [
        ClipVertex(
            tuple(float(value) for value in positions[index]),
            tuple(1.0 if index == axis else 0.0 for axis in range(3)),
        )
        for index in range(3)
    ]
    for axis in range(3):
        lower = float(minimum[axis])
        upper = float(maximum[axis])
        lower_bit = 1 << (axis * 2)
        upper_bit = 1 << (axis * 2 + 1)
        clip_lower = (
            bool(int(plane_mask) & lower_bit)
            if plane_mask is not None
            else any(vertex.position[axis] < lower - EPSILON for vertex in vertices)
        )
        if clip_lower:
            vertices = _clip_plane(vertices, axis, lower, True)
            if len(vertices) < 3:
                return ()
        clip_upper = (
            bool(int(plane_mask) & upper_bit)
            if plane_mask is not None
            else any(vertex.position[axis] > upper + EPSILON for vertex in vertices)
        )
        if clip_upper:
            vertices = _clip_plane(vertices, axis, upper, False)
            if len(vertices) < 3:
                return ()
    return tuple(vertices)


def clip_triangle_to_unit_box(positions, padding=0.0):
    if isinstance(padding, (tuple, list)):
        axis_padding = tuple(float(value) for value in padding)
        if len(axis_padding) != 3:
            axis_padding = (0.0, 0.0, 0.0)
    else:
        amount = float(padding)
        axis_padding = (amount, amount, amount)

    minimum = tuple(-0.5 - value for value in axis_padding)
    maximum = tuple(0.5 + value for value in axis_padding)
    return clip_triangle_to_box(positions, minimum, maximum)


def _clip_triangle_batch_plane(polygon, weights, lengths, distances):
    count = len(polygon)
    slots = np.arange(polygon.shape[1])[None, :]
    valid = slots < lengths[:, None]
    inside = distances >= -EPSILON
    if not np.any(valid & ~inside):
        return polygon, weights, lengths

    row = np.arange(count)[:, None]
    previous_slots = np.where(slots == 0, lengths[:, None] - 1, slots - 1)
    previous_slots = np.maximum(previous_slots, 0)
    previous_distances = distances[row, previous_slots]
    crossing = valid & (inside != inside[row, previous_slots])
    keep = valid & inside
    increments = crossing.astype(np.int32) + keep
    ends = np.cumsum(increments, axis=1)
    next_lengths = ends[:, -1]
    next_lengths = np.where(next_lengths >= 3, next_lengths, 0)
    capacity = int(next_lengths.max(initial=0))
    if capacity < 3:
        return (
            np.zeros((count, 0, 3), dtype=np.float64),
            np.zeros((count, 0, 3), dtype=np.float64),
            next_lengths,
        )

    next_polygon = np.zeros((count, capacity, 3), dtype=np.float64)
    next_weights = np.zeros_like(next_polygon)
    rows, columns = np.nonzero(crossing)
    if len(rows):
        previous = previous_slots[rows, columns]
        first = previous_distances[rows, columns]
        denominator = first - distances[rows, columns]
        amount = np.divide(
            first,
            denominator,
            out=np.zeros_like(first),
            where=np.abs(denominator) > EPSILON,
        )[:, None]
        target = ends[rows, columns] - increments[rows, columns]
        next_polygon[rows, target] = (
            polygon[rows, previous]
            + (polygon[rows, columns] - polygon[rows, previous]) * amount
        )
        next_weights[rows, target] = (
            weights[rows, previous]
            + (weights[rows, columns] - weights[rows, previous]) * amount
        )

    rows, columns = np.nonzero(keep)
    target = ends[rows, columns] - 1
    next_polygon[rows, target] = polygon[rows, columns]
    next_weights[rows, target] = weights[rows, columns]
    return next_polygon, next_weights, next_lengths


def clip_triangles_to_box(
    positions,
    minimum,
    maximum,
    *,
    source_values=None,
    scalar_minimum=None,
    timings=None,
):
    """Clip a triangle batch while retaining barycentric interpolation weights"""
    source = np.asarray(positions, dtype=np.float64)
    count = len(source)
    if not count:
        empty = np.empty((0, 3, 3), dtype=np.float64)
        return empty, empty.copy(), np.empty(0, dtype=np.int32), 0

    scalar_values = (
        None if source_values is None else np.asarray(source_values, dtype=np.float64)
    )
    if scalar_values is not None:
        if scalar_values.shape != (count, 3):
            raise ValueError("source_values must have shape (triangle_count, 3)")
        if scalar_minimum is None:
            raise ValueError(
                "scalar_minimum is required when source_values are provided"
            )

    if count > 4096:
        chunks = []
        for start in range(0, count, 4096):
            stop = start + 4096
            result = clip_triangles_to_box(
                source[start:stop],
                minimum,
                maximum,
                source_values=(
                    None if scalar_values is None else scalar_values[start:stop]
                ),
                scalar_minimum=scalar_minimum,
                timings=timings,
            )
            chunks.append((start, result))
        merge_started = time.perf_counter() if timings is not None else 0.0
        merged = (
            np.concatenate([result[0] for _, result in chunks]),
            np.concatenate([result[1] for _, result in chunks]),
            np.concatenate([result[2] + start for start, result in chunks]),
            sum(result[3] for _, result in chunks),
        )
        if timings is not None:
            timings["chunk_merge"] = timings.get("chunk_merge", 0.0) + (
                time.perf_counter() - merge_started
            )
        return merged

    polygon = source.copy()
    weights = np.broadcast_to(np.eye(3), (count, 3, 3)).copy()
    lengths = np.full(count, 3, dtype=np.int32)
    box_started = time.perf_counter() if timings is not None else 0.0
    for axis in range(3):
        for limit, sign in ((minimum[axis], 1.0), (maximum[axis], -1.0)):
            distances = (polygon[:, :, axis] - float(limit)) * sign
            polygon, weights, lengths = _clip_triangle_batch_plane(
                polygon,
                weights,
                lengths,
                distances,
            )
            if polygon.shape[1] < 3:
                if timings is not None:
                    timings["box_clip"] = timings.get("box_clip", 0.0) + (
                        time.perf_counter() - box_started
                    )
                empty = np.empty((0, 3, 3), dtype=np.float64)
                return empty, empty.copy(), np.empty(0, dtype=np.int32), 0
    if timings is not None:
        timings["box_clip"] = timings.get("box_clip", 0.0) + (
            time.perf_counter() - box_started
        )

    if scalar_values is not None:
        scalar_started = time.perf_counter() if timings is not None else 0.0
        distances = np.einsum(
            "tvi,ti->tv",
            weights,
            scalar_values,
        ) - float(scalar_minimum)
        polygon, weights, lengths = _clip_triangle_batch_plane(
            polygon,
            weights,
            lengths,
            distances,
        )
        if timings is not None:
            timings["scalar_clip"] = timings.get("scalar_clip", 0.0) + (
                time.perf_counter() - scalar_started
            )
        if polygon.shape[1] < 3:
            empty = np.empty((0, 3, 3), dtype=np.float64)
            return empty, empty.copy(), np.empty(0, dtype=np.int32), 0

    triangulate_started = time.perf_counter() if timings is not None else 0.0
    polygon_count = int(np.count_nonzero(lengths >= 3))
    slots = np.arange(1, polygon.shape[1] - 1)[None, :]
    rows, fan_slots = np.nonzero(slots < (lengths[:, None] - 1))
    middle = fan_slots + 1
    fans = np.column_stack((np.zeros(len(rows), dtype=np.int32), middle, middle + 1))
    result = (
        weights[rows[:, None], fans],
        polygon[rows[:, None], fans],
        rows.astype(np.int32),
        polygon_count,
    )
    if timings is not None:
        timings["triangulate"] = timings.get("triangulate", 0.0) + (
            time.perf_counter() - triangulate_started
        )
    return result
