import time

import numpy as np

_MAX_AGGREGATES = 320
_MIN_VERTICES = 4096


def _partition(indices, coords, groups):
    """Partition a connected material component into spatially compact aggregates"""
    pending = [(indices, int(groups))]
    while pending:
        members, count = pending.pop()
        if count <= 1 or len(members) <= 2:
            yield members
            continue
        local = coords[members]
        axis = int(np.argmax(np.ptp(local, axis=0)))
        order = np.argsort(local[:, axis], kind="stable")
        split_count = count // 2
        split = max(1, min(len(members) - 1, round(len(members) * split_count / count)))
        pending.append((members[order[split:]], count - split_count))
        pending.append((members[order[:split]], split_count))


class SeamCoarsePreconditioner:
    """An exact coarse Galerkin solve alongside projected diagonal smoothing"""

    def __init__(self, positions, components, edges_a, edges_b, edge_weights):
        self.vertex_count = len(positions)
        self.aggregation = None
        self.component_labels = None
        if self.vertex_count < _MIN_VERTICES:
            return
        _unique, remapped = np.unique(components, return_inverse=True)
        counts = np.bincount(remapped)
        if len(counts) >= _MAX_AGGREGATES:
            return
        quota = counts * (_MAX_AGGREGATES / self.vertex_count)
        counts_per_component = np.maximum(1, np.floor(quota).astype(int))
        if counts_per_component.sum() > _MAX_AGGREGATES:
            for index in np.argsort(-counts_per_component):
                if counts_per_component.sum() <= _MAX_AGGREGATES:
                    break
                counts_per_component[index] -= min(
                    counts_per_component[index] - 1,
                    counts_per_component.sum() - _MAX_AGGREGATES,
                )
        for index in np.argsort(-(quota - np.floor(quota))):
            if counts_per_component.sum() >= _MAX_AGGREGATES:
                break
            counts_per_component[index] += 1
        aggregation = np.empty(self.vertex_count, dtype=np.int64)
        owners = []
        offset = 0
        for component, count in enumerate(counts):
            indices = np.flatnonzero(remapped == component)
            for members in _partition(
                indices, positions, counts_per_component[component]
            ):
                aggregation[members] = offset
                owners.append(component)
                offset += 1
        if offset < 2 or offset >= self.vertex_count // 2:
            return
        self.aggregation = aggregation
        self.component_labels = np.asarray(owners, dtype=np.int64)
        self.count = offset
        self.dimension = 2 * offset
        self.edge_source = aggregation[edges_a]
        self.edge_target = aggregation[edges_b]
        self.edge_weights = edge_weights
        self.inverse = None
        self.build_seconds = 0.0
        self.apply_count = 0
        self.apply_seconds = 0.0
        self.condition = float("nan")

    @property
    def available(self):
        return self.aggregation is not None

    def rebuild(self, row_vertices, coefficient, weight):
        """Rebuild the exact Galerkin matrix for the current seam directions"""
        if not self.available:
            return False
        started = time.perf_counter()
        groups = self.count
        dimension = self.dimension
        first, second = self.edge_source, self.edge_target
        valid = first != second
        first, second, weights = first[valid], second[valid], self.edge_weights[valid]
        off_diagonal = np.bincount(
            np.r_[first * groups + second, second * groups + first],
            weights=np.r_[weights, weights],
            minlength=groups * groups,
        ).reshape((groups, groups))
        graph = -off_diagonal
        graph[np.diag_indices(groups)] += np.sum(off_diagonal, axis=1)
        matrix = np.zeros((dimension, dimension), dtype=float)
        matrix[::2, ::2] = graph
        matrix[1::2, 1::2] = graph
        indices = (2 * self.aggregation[row_vertices, None] + np.arange(2)).reshape(
            (-1, 12)
        )
        values = coefficient.reshape((-1, 12))

        for start in range(0, len(indices), 2048):
            stop = start + 2048
            group = indices[start:stop]
            factors = values[start:stop]
            matrix += weight * np.bincount(
                (group[:, :, None] * dimension + group[:, None, :]).ravel(),
                weights=(factors[:, :, None] * factors[:, None, :]).ravel(),
                minlength=dimension * dimension,
            ).reshape((dimension, dimension))
        diagonal = np.diag(matrix).copy()
        for component in np.unique(self.component_labels):
            member = np.flatnonzero(self.component_labels == component)
            gauge = max(
                float(diagonal[np.r_[2 * member, 2 * member + 1]].mean()), 1.0e-15
            ) / len(member)
            for axis in (0, 1):
                nodes = 2 * member + axis
                matrix[np.ix_(nodes, nodes)] += gauge
        if not np.isfinite(matrix).all():
            self.inverse = None
            return False
        try:
            chol = np.linalg.cholesky(matrix)
            inverse = np.linalg.solve(chol.T, np.linalg.solve(chol, np.eye(dimension)))
        except np.linalg.LinAlgError:
            self.inverse = None
            return False
        if not np.isfinite(inverse).all():
            self.inverse = None
            return False
        self.inverse = 0.5 * (inverse + inverse.T)
        self.build_seconds = time.perf_counter() - started
        self.apply_count = 0
        self.apply_seconds = 0.0
        return True

    def apply(self, residual, diagonal, project_means):
        started = time.perf_counter()
        fine = residual / np.maximum(diagonal, 1.0e-20)
        coarse_rhs = np.column_stack(
            [
                np.bincount(
                    self.aggregation, weights=residual[:, axis], minlength=self.count
                )
                for axis in range(2)
            ]
        )
        correction = (self.inverse @ coarse_rhs.ravel()).reshape((-1, 2))
        result = project_means(fine + correction[self.aggregation])
        self.apply_count += 1
        self.apply_seconds += time.perf_counter() - started
        return result
