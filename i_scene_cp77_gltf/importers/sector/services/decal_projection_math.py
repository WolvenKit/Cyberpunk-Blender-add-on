from __future__ import annotations

import math

import numpy as np

from ....assetio.values import coerce_float
from ....bartmoss.clipping import EPSILON


def normal_threshold_radians(data):
    enabled = bool(
        data.get(
            "enableNormalTreshold",
            data.get("enableNormalThreshold", False),
        )
    )
    if not enabled:
        return None
    degrees = coerce_float(data.get("normalThreshold", 0.0), 0.0, unwrap=False)
    return math.radians(max(0.0, degrees))


def projection_clip_bounds(clip_padding):
    return (
        (
            -0.5 - float(clip_padding[0]),
            -0.5 - float(clip_padding[1]),
            -0.5 - float(clip_padding[2]),
        ),
        (
            0.5 + float(clip_padding[0]),
            0.5 + float(clip_padding[1]),
            0.5 + float(clip_padding[2]),
        ),
    )


def projection_padding(projector_dimensions):
    dimensions = tuple(abs(float(value)) for value in projector_dimensions)
    width = max(dimensions[0] if len(dimensions) > 0 else 0.0, 1.0e-6)
    height = max(dimensions[1] if len(dimensions) > 1 else 0.0, 1.0e-6)
    depth = max(dimensions[2] if len(dimensions) > 2 else 0.0, 1.0e-6)
    query_padding = min(0.1, max(0.01, max(width, height) * 0.02))
    clip_padding = (
        min(0.04, max(0.0025, query_padding / width)),
        min(0.04, max(0.0025, query_padding / height)),
        min(0.08, max(0.005, (query_padding * 0.5) / depth)),
    )
    query_padding = max(
        query_padding,
        clip_padding[0] * width,
        clip_padding[1] * height,
        clip_padding[2] * depth,
    )
    return query_padding, clip_padding


# Separation between overlapping decal surfaces, enough for the viewport depth buffer to keep them apart.
STACK_SPACING = 0.002


def projection_surface_offset(projector_dimensions):
    """Distance a projected surface stands off its receiver, growing with the decal's footprint"""
    dimensions = tuple(abs(float(value)) for value in projector_dimensions)
    footprint = dimensions[:2] if len(dimensions) >= 2 else dimensions
    smallest_footprint = max(min(footprint), 1.0e-6) if footprint else 1.0e-6
    return min(0.012, max(0.004, smallest_footprint * 0.003))


def stacked_surface_offsets(base_offsets, bounds, spacing=STACK_SPACING):
    """Surface offsets that keep each decal above the earlier ones it overlaps"""
    minimums = np.asarray([minimum for minimum, _ in bounds], dtype=np.float64).reshape(
        -1, 3
    )
    maximums = np.asarray([maximum for _, maximum in bounds], dtype=np.float64).reshape(
        -1, 3
    )
    offsets = np.asarray(base_offsets, dtype=np.float64).copy()
    for index in range(1, len(offsets)):
        overlapping = np.all(
            (minimums[:index] <= maximums[index])
            & (maximums[:index] >= minimums[index]),
            axis=1,
        )
        if np.any(overlapping):
            offsets[index] = max(
                offsets[index], float(offsets[:index][overlapping].max()) + spacing
            )
    return offsets.tolist()


def projected_uv_coverage_array(
    local_positions,
    alignments,
    data,
    normal_threshold,
    flip_x,
    flip_y,
):
    positions = np.asarray(local_positions, dtype=np.float64)
    alignment_values = np.asarray(alignments, dtype=np.float64)
    uv = positions[..., :2] + 0.5

    depth = np.clip(positions[..., 2] + 0.5, 0.0, 1.0)
    depth_fade = abs(
        coerce_float(data.get("depthFade", 1.0), 1.0, unwrap=False, finite=False)
    )
    volume_fade = np.clip(
        (1.0 - np.abs((depth - 0.5) * 2.0)) * depth_fade,
        0.0,
        1.0,
    )
    edge_fade = np.where(
        depth < 0.3,
        depth / 0.3,
        np.where(depth > 0.7, (1.0 - depth) / 0.3, 1.0),
    )
    coverage = volume_fade * np.clip(edge_fade, 0.0, 1.0)

    if normal_threshold is not None:
        coverage = np.where(
            alignment_values < float(normal_threshold),
            0.0,
            coverage,
        )

    if bool(data.get("isStretchingEnabled", 0)):
        scale = 0.25 + 0.75 * alignment_values
        valid_scale = scale > EPSILON
        safe_scale = np.where(valid_scale, scale, 1.0)
        lower = (1.0 - safe_scale) * 0.5
        upper = (1.0 + safe_scale) * 0.5
        inside = np.logical_and(
            np.all(uv > lower[..., None], axis=-1),
            np.all(uv < upper[..., None], axis=-1),
        )
        coverage = np.where(valid_scale & inside, coverage, 0.0)
        uv = (uv - 0.5) / safe_scale[..., None] + 0.5

    if flip_x:
        uv[..., 0] = 1.0 - uv[..., 0]
    if flip_y:
        uv[..., 1] = 1.0 - uv[..., 1]
    return uv, coverage
