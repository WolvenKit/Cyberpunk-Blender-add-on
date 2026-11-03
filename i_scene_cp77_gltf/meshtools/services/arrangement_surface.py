import numpy as np


def limb_surface_support(coordinates, triangles, origin, axis, normal, length):
    """Return a conservative support distance across the finite limb span"""
    points = np.asarray(coordinates, dtype=np.float64).reshape((-1, 3))
    faces = np.asarray(triangles, dtype=np.int64).reshape((-1, 3))
    if not len(points) or not len(faces) or length <= 0.0:
        raise ValueError(
            "Limb arrangement requires a nonempty body surface and joint span"
        )
    if not np.isfinite(points).all():
        raise ValueError("Limb arrangement body surface contains nonfinite coordinates")
    relative = points - np.asarray(origin, dtype=np.float64)
    axial = relative @ np.asarray(axis, dtype=np.float64)
    spans = axial[faces]
    crossing = (spans.max(axis=1) >= 0.0) & (spans.min(axis=1) <= length)
    vertices = np.unique(faces[crossing])
    if not len(vertices):
        raise ValueError("No body surface intersects the limb arrangement span")
    return max(
        0.0, float((relative[vertices] @ np.asarray(normal, dtype=np.float64)).max())
    )
