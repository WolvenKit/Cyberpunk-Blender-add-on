import numpy as np


def _cluster_once(vertices, triangles, cell_size):
    vertices = np.asarray(vertices, dtype=np.float64).reshape((-1, 3))
    triangles = np.asarray(triangles, dtype=np.int64).reshape((-1, 3))
    if len(vertices) == 0 or len(triangles) == 0:
        return vertices.astype(np.float32), triangles.astype(np.int32)
    if cell_size <= 0.0:
        return vertices.astype(np.float32), triangles.astype(np.int32)

    minimum = vertices.min(axis=0)
    cells = np.floor((vertices - minimum) / float(cell_size)).astype(np.int64)
    unique_cells, inverse = np.unique(cells, axis=0, return_inverse=True)
    cluster_count = len(unique_cells)

    sums = np.zeros((cluster_count, 3), dtype=np.float64)
    counts = np.bincount(inverse, minlength=cluster_count).astype(np.float64)
    np.add.at(sums, inverse, vertices)
    clustered_vertices = sums / counts[:, None]

    remapped = inverse[triangles]
    nondegenerate = (
        (remapped[:, 0] != remapped[:, 1])
        & (remapped[:, 1] != remapped[:, 2])
        & (remapped[:, 2] != remapped[:, 0])
    )
    remapped = remapped[nondegenerate]
    if len(remapped) == 0:
        return clustered_vertices.astype(np.float32), np.empty((0, 3), dtype=np.int32)

    canonical = np.sort(remapped, axis=1)
    _, first = np.unique(canonical, axis=0, return_index=True)
    remapped = remapped[np.sort(first)]

    used = np.unique(remapped.reshape(-1))
    compact = np.full(cluster_count, -1, dtype=np.int64)
    compact[used] = np.arange(len(used), dtype=np.int64)
    return (
        clustered_vertices[used].astype(np.float32),
        compact[remapped].astype(np.int32),
    )


def reduce_triangle_collision(vertices, triangles, max_triangles):
    vertices = np.asarray(vertices, dtype=np.float64).reshape((-1, 3))
    triangles = np.asarray(triangles, dtype=np.int64).reshape((-1, 3))
    budget = max(1, int(max_triangles))
    if len(triangles) <= budget:
        return vertices.astype(np.float32), triangles.astype(np.int32)
    if len(vertices) == 0 or len(triangles) == 0:
        return vertices.astype(np.float32), triangles.astype(np.int32)

    extent = np.ptp(vertices, axis=0)
    maximum_extent = float(np.max(extent))
    if not np.isfinite(maximum_extent) or maximum_extent <= 1.0e-12:
        return vertices.astype(np.float32), triangles[:budget].astype(np.int32)

    low = 0.0
    high = maximum_extent * 2.0
    best_vertices = None
    best_triangles = None
    for _ in range(18):
        cell_size = (low + high) * 0.5
        reduced_vertices, reduced_triangles = _cluster_once(
            vertices, triangles, cell_size
        )
        if 0 < len(reduced_triangles) <= budget:
            best_vertices = reduced_vertices
            best_triangles = reduced_triangles
            high = cell_size
        elif len(reduced_triangles) == 0:
            high = cell_size
        else:
            low = cell_size

    if best_triangles is None:
        reduced_vertices, reduced_triangles = _cluster_once(vertices, triangles, high)
        if 0 < len(reduced_triangles) <= budget:
            best_vertices = reduced_vertices
            best_triangles = reduced_triangles

    if best_triangles is None:
        stride = max(1, int(np.ceil(len(triangles) / budget)))
        sampled = triangles[::stride][:budget]
        used = np.unique(sampled.reshape(-1))
        compact = np.full(len(vertices), -1, dtype=np.int64)
        compact[used] = np.arange(len(used), dtype=np.int64)
        return vertices[used].astype(np.float32), compact[sampled].astype(np.int32)

    return best_vertices, best_triangles
