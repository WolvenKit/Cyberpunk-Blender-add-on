import numpy as np


def polygon_uv_areas(uvs, starts, counts):
    areas = np.zeros(len(counts), dtype=np.float64)
    valid = counts >= 3
    if not np.any(valid):
        return areas
    face_ids = np.repeat(np.flatnonzero(valid), counts[valid])
    offsets = np.arange(len(face_ids)) - np.repeat(
        np.cumsum(counts[valid]) - counts[valid], counts[valid]
    )
    loops = starts[face_ids] + offsets
    following = starts[face_ids] + (offsets + 1) % counts[face_ids]
    terms = uvs[loops, 0] * uvs[following, 1] - uvs[following, 0] * uvs[loops, 1]
    return np.abs(np.bincount(face_ids, weights=terms, minlength=len(counts))) * 0.5


def polygon_world_areas(positions, loop_vertices, starts, counts, linear_transform):
    fan_counts = np.maximum(counts - 2, 0)
    face_ids = np.repeat(np.arange(len(counts)), fan_counts)
    if not len(face_ids):
        return np.zeros(len(counts), dtype=np.float64)
    offsets = (
        np.arange(len(face_ids))
        - np.repeat(np.cumsum(fan_counts) - fan_counts, fan_counts)
        + 1
    )
    origins = positions[loop_vertices[starts[face_ids]]]
    first = (
        positions[loop_vertices[starts[face_ids] + offsets]] - origins
    ) @ linear_transform.T
    second = (
        positions[loop_vertices[starts[face_ids] + offsets + 1]] - origins
    ) @ linear_transform.T
    areas = np.linalg.norm(np.cross(first, second), axis=1) * 0.5
    return np.bincount(face_ids, weights=areas, minlength=len(counts))


def texel_densities(uv_areas, world_areas, texture_size=512.0):
    ratios = np.divide(
        uv_areas,
        world_areas,
        out=np.zeros_like(uv_areas),
        where=(world_areas > 1.0e-16) & (uv_areas > 0.0),
    )
    return float(texture_size) * np.sqrt(ratios)


def _triangle_edges(points, triangles, triangle_ids):
    corners = np.asarray(points, dtype=np.float64)[np.asarray(triangles)[triangle_ids]]
    origins = corners[:, 0]
    first = corners[:, 1] - origins
    second = corners[:, 2] - origins
    return origins, first, second, np.cross(first, second)


def triangle_uv_transfer(
    points, triangles, triangle_loops, uv_layers, triangle_ids, positions
):
    """The UVs at positions projected onto the planes of their triangles"""
    ids = np.asarray(triangle_ids, dtype=np.int64)
    origins, first, second, normals = _triangle_edges(points, triangles, ids)
    squared = np.einsum("ij,ij->i", normals, normals)
    valid = squared > 1.0e-30
    scale = np.where(valid, squared, 1.0)
    offsets = np.asarray(positions, dtype=np.float64).reshape(-1, 3) - origins
    # Signed areas against the normal give the weights of the point's projection; its height drops out.
    along_first = np.einsum("ij,ij->i", np.cross(offsets, second), normals) / scale
    along_second = np.einsum("ij,ij->i", np.cross(first, offsets), normals) / scale
    weights = np.stack(
        (1.0 - along_first - along_second, along_first, along_second), axis=1
    )
    weights[~valid] = 0.0
    loops = np.asarray(triangle_loops)[ids]
    values = {
        name: np.einsum("ij,ijk->ik", weights, np.asarray(uvs, dtype=np.float64)[loops])
        for name, uvs in uv_layers.items()
    }
    return values, valid


def triangle_uv_densities(points, triangles, triangle_loops, uvs, triangle_ids):
    """UV units per unit length on each of triangle_ids"""
    ids = np.asarray(triangle_ids, dtype=np.int64)
    _origins, _first, _second, normals = _triangle_edges(points, triangles, ids)
    areas = np.linalg.norm(normals, axis=1)
    corners = np.asarray(uvs, dtype=np.float64)[np.asarray(triangle_loops)[ids]]
    first = corners[:, 1] - corners[:, 0]
    second = corners[:, 2] - corners[:, 0]
    uv_areas = np.abs(first[:, 0] * second[:, 1] - second[:, 0] * first[:, 1])
    ratios = np.divide(uv_areas, areas, out=np.zeros_like(areas), where=areas > 1.0e-30)
    return np.sqrt(ratios)


def density_colors(densities, reference, gradient):
    palette = np.asarray(gradient, dtype=np.float64)
    ratios = np.maximum(1.0e-12, densities / max(1.0e-6, reference))
    values = np.clip(0.5 + np.log2(ratios) / 8.0, 0.0, 1.0) * (len(palette) - 1)
    indices = np.minimum(len(palette) - 2, values.astype(np.intp))
    factors = (values - indices)[:, None]
    colors = palette[indices] + (palette[indices + 1] - palette[indices]) * factors
    colors[densities <= 0.0] = palette[0]
    return colors.astype(np.float32)
