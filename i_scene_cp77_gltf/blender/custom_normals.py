from __future__ import annotations

from contextlib import contextmanager

import numpy as np

from ..core.log import get_logger

_LOG = get_logger(__name__)
CUSTOM_NORMAL_ATTRIBUTE = "custom_normal"
_CARRIED_NORMAL_ATTRIBUTE = "cp77_carried_normal"
_NORMAL_EPSILON = 1.0e-12


def _normalized_values(normals, expected_count: int, label: str):
    if normals is None or expected_count <= 0:
        return None

    values = np.asarray(normals, dtype=np.float32)
    if values.size != expected_count * 3:
        _LOG.warning(
            "Skipping custom normals for %s: %d values for %d vectors",
            label,
            values.size,
            expected_count,
        )
        return None
    values = values.reshape(expected_count, 3)
    if not np.all(np.isfinite(values)):
        _LOG.warning(
            "Skipping custom normals for %s: non-finite values detected", label
        )
        return None

    lengths_squared = np.einsum("ij,ij->i", values, values, optimize=True)
    if np.any(lengths_squared <= _NORMAL_EPSILON):
        _LOG.warning(
            "Skipping custom normals for %s: zero-length values detected", label
        )
        return None

    if not np.allclose(lengths_squared, 1.0, rtol=1.0e-4, atol=1.0e-6):
        values = values / np.sqrt(lengths_squared)[:, None]
    return np.ascontiguousarray(values, dtype=np.float32)


def _set_custom_normals(
    mesh, normals, *, domain: str, expected_count: int, label: str
) -> bool:
    values = _normalized_values(normals, expected_count, label)
    if values is None:
        return False

    # Free normals (a FLOAT_VECTOR custom_normal attribute) keep their world direction
    # when an armature or shape key moves the surface, so posed skin shades as if it
    # were still in the rest pose. Blender's standard custom normals are stored
    # relative to each corner's own frame and rotate with the deformed surface.
    attributes = getattr(mesh, "attributes", None)
    if attributes is not None:
        stale = attributes.get(CUSTOM_NORMAL_ATTRIBUTE)
        if stale is not None:
            attributes.remove(stale)

    try:
        if domain == "POINT":
            mesh.normals_split_custom_set_from_vertices(values)
        else:
            mesh.normals_split_custom_set(values)
    except (AttributeError, RuntimeError, TypeError, ValueError) as error:
        _LOG.warning(
            "Unable to set custom normals for %s: %s", label, error, exc_info=True
        )
        return False
    return True


def set_custom_normals_from_vertices(mesh, normals, *, label: str = "mesh") -> bool:
    """Store one custom normal per vertex that follows mesh deformation"""
    return _set_custom_normals(
        mesh,
        normals,
        domain="POINT",
        expected_count=len(mesh.vertices),
        label=label,
    )


def set_custom_normals_from_corners(mesh, normals, *, label: str = "mesh") -> bool:
    """Store one custom normal per face corner"""
    return _set_custom_normals(
        mesh,
        normals,
        domain="CORNER",
        expected_count=len(mesh.loops),
        label=label,
    )


def corner_normals(mesh):
    values = np.empty(len(mesh.loops) * 3, dtype=np.float32)
    mesh.corner_normals.foreach_get("vector", values)
    return values.reshape(-1, 3)


def set_custom_normals_at(mesh, normals, positions, *, label: str = "mesh") -> bool:
    """Set custom normals per face corner"""
    current = np.empty(len(mesh.vertices) * 3, dtype=np.float32)
    mesh.vertices.foreach_get("co", current)
    mesh.vertices.foreach_set(
        "co", np.ascontiguousarray(positions, dtype=np.float32).reshape(-1)
    )
    try:
        return set_custom_normals_from_corners(mesh, normals, label=label)
    finally:
        mesh.vertices.foreach_set("co", current)
        mesh.update()


@contextmanager
def normals_kept(mesh, *, label: str = "mesh"):
    """Keep mesh's custom normals through a change to its faces"""
    if not getattr(mesh, "has_custom_normals", False):
        yield
        return
    carried = mesh.attributes.new(_CARRIED_NORMAL_ATTRIBUTE, "FLOAT_VECTOR", "CORNER")
    carried.data.foreach_set("vector", corner_normals(mesh).reshape(-1))
    try:
        yield
    finally:
        carried = mesh.attributes[_CARRIED_NORMAL_ATTRIBUTE]
        values = np.empty(len(carried.data) * 3, dtype=np.float32)
        carried.data.foreach_get("vector", values)
        mesh.attributes.remove(carried)
        set_custom_normals_from_corners(mesh, values, label=label)
