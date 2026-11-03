from __future__ import annotations

import numpy as np

from ..core.log import get_logger

_LOG = get_logger(__name__)
CUSTOM_NORMAL_ATTRIBUTE = "custom_normal"
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


def _ensure_attribute(mesh, domain: str, label: str):
    attributes = getattr(mesh, "attributes", None)
    if attributes is None:
        _LOG.warning(
            "Skipping custom normals for %s: mesh attributes are unavailable", label
        )
        return None

    attribute = attributes.get(CUSTOM_NORMAL_ATTRIBUTE)
    if attribute is not None:
        if (
            getattr(attribute, "data_type", None) == "FLOAT_VECTOR"
            and getattr(attribute, "domain", None) == domain
        ):
            return attribute
        attributes.remove(attribute)

    try:
        return attributes.new(
            name=CUSTOM_NORMAL_ATTRIBUTE,
            type="FLOAT_VECTOR",
            domain=domain,
        )
    except (AttributeError, RuntimeError, TypeError, ValueError) as error:
        _LOG.warning(
            "Unable to create custom normals for %s: %s", label, error, exc_info=True
        )
        return None


def _set_custom_normal_attribute(
    mesh, normals, *, domain: str, expected_count: int, label: str
) -> bool:
    values = _normalized_values(normals, expected_count, label)
    if values is None:
        return False

    attribute = _ensure_attribute(mesh, domain, label)
    if attribute is None:
        return False
    if len(attribute.data) != expected_count:
        _LOG.warning(
            "Skipping custom normals for %s: attribute has %d elements, expected %d",
            label,
            len(attribute.data),
            expected_count,
        )
        return False

    attribute.data.foreach_set("vector", values.reshape(-1))
    return True


def set_custom_normals_from_vertices(mesh, normals, *, label: str = "mesh") -> bool:
    """Store free custom normals on Blender's point domain"""
    return _set_custom_normal_attribute(
        mesh,
        normals,
        domain="POINT",
        expected_count=len(mesh.vertices),
        label=label,
    )


def set_custom_normals_from_corners(mesh, normals, *, label: str = "mesh") -> bool:
    """Store free custom normals on Blender's corner domain"""
    return _set_custom_normal_attribute(
        mesh,
        normals,
        domain="CORNER",
        expected_count=len(mesh.loops),
        label=label,
    )
