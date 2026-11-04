from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .files import binary_reader

MAGIC_MESH = b"MSHZ"


def npz_text(value) -> str:
    """Text from a bytes, numpy bytes or 0-d array value"""
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, (bytes, np.bytes_)):
        return value.decode("utf8", "ignore").rstrip("\x00")
    return str(value)


def npz_int(data, key, default=None) -> int:
    """An integer stored as a 0-d or single-element array"""
    if key not in data:
        if default is None:
            raise ValueError(f"NPZ archive is missing {key!r}")
        return default
    values = np.asarray(data[key]).reshape(-1)
    if values.size != 1:
        raise ValueError(f"NPZ field {key!r} must hold one value, found {values.size}")
    return int(values[0])


def require_count(values, expected, label) -> None:
    if len(values) != expected:
        raise ValueError(f"{label}: expected {expected} entries, found {len(values)}")


def require_indices(values, upper, label) -> None:
    """values are indices into a sequence of length upper"""
    if len(values) and (int(np.min(values)) < 0 or int(np.max(values)) >= upper):
        raise ValueError(
            f"{label}: indices must lie in [0, {upper}), found [{int(np.min(values))}, {int(np.max(values))}]"
        )


@dataclass(frozen=True)
class SkinnedMesh:
    points: np.ndarray
    normals: np.ndarray
    groups: tuple[str, ...]
    vertex_indices: np.ndarray
    group_indices: np.ndarray
    weights: np.ndarray


def _submesh_prefixes(data, label) -> list[str]:
    if npz_text(data["magic"]) != MAGIC_MESH.decode():
        raise ValueError(f"{label} is not a mesh NPZ")
    if npz_int(data, "version", 1) >= 2 and "submesh_count" in data:
        return [f"sub{index}_" for index in range(npz_int(data, "submesh_count"))]
    return [""]


def read_skinned_mesh(path) -> SkinnedMesh:
    """Vertex positions, unit vertex normals and skin influences of a mesh NPZ, its submeshes merged"""
    label = f"NPZ mesh {path}"
    points, normals, vertex_indices, group_indices, weights = [], [], [], [], []
    groups: dict[str, int] = {}
    with binary_reader(path) as stream, np.load(stream, allow_pickle=False) as data:
        for prefix in _submesh_prefixes(data, label):
            verts = np.asarray(data[f"{prefix}verts"], dtype=np.float64).reshape(-1, 3)
            corners = np.asarray(
                data[f"{prefix}loop_v_indices"], dtype=np.int64
            ).reshape(-1)
            require_indices(corners, len(verts), f"{label} corner vertex indices")
            corner_normals = np.asarray(
                data[f"{prefix}normals"], dtype=np.float64
            ).reshape(-1, 3)
            require_count(corner_normals, len(corners), f"{label} corner normals")
            summed = np.zeros_like(verts)
            np.add.at(summed, corners, corner_normals)
            names = [npz_text(name) for name in data.get(f"{prefix}vg_names", [])]
            local = np.asarray(
                data.get(f"{prefix}w_g_indices", []), dtype=np.int64
            ).reshape(-1)
            vertices = np.asarray(
                data.get(f"{prefix}w_v_indices", []), dtype=np.int64
            ).reshape(-1)
            values = np.asarray(
                data.get(f"{prefix}w_values", []), dtype=np.float64
            ).reshape(-1)
            require_count(local, len(vertices), f"{label} weight group indices")
            require_count(values, len(vertices), f"{label} weight values")
            require_indices(vertices, len(verts), f"{label} weight vertex indices")
            require_indices(local, len(names), f"{label} weight group indices")
            mapping = np.array(
                [groups.setdefault(name, len(groups)) for name in names], dtype=np.int64
            )
            vertex_indices.append(vertices + sum(len(block) for block in points))
            group_indices.append(mapping[local] if len(local) else local)
            weights.append(values)
            points.append(verts)
            normals.append(
                summed
                / np.maximum(np.linalg.norm(summed, axis=1, keepdims=True), 1e-12)
            )
    return SkinnedMesh(
        points=np.concatenate(points),
        normals=np.concatenate(normals),
        groups=tuple(groups),
        vertex_indices=np.concatenate(vertex_indices),
        group_indices=np.concatenate(group_indices),
        weights=np.concatenate(weights),
    )
