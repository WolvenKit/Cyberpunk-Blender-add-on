from mathutils import Matrix, Vector

from ...assetio.transform_values import quaternion_ijkr_from_wxyz
from ...bartmoss.matrix import placements_near, transfer_matrix_delta
from ...blender.matrix import matrix_from_flat, object_world_matrix


def _number(value):
    """A float32 value to the nine digits that keep it exact"""
    return float(f"{value:.9g}")


def _recorded_matrix(obj):
    """The world matrix obj recorded on import (cp77_matrix), or None"""
    return matrix_from_flat(obj["cp77_matrix"]) if "cp77_matrix" in obj else None


def moved_matrix(obj):
    """The world matrix obj has now when it moved since import, else None"""
    recorded = _recorded_matrix(obj)
    if recorded is None:
        return None
    now = object_world_matrix(obj)
    return None if placements_near(now, recorded) else now


def scales_near(left, right):
    """Whether two scales (x, y, z) agree within the tolerance placements compare by (placements_near)"""
    return placements_near(
        Matrix.Diagonal(left).to_4x4(), Matrix.Diagonal(right).to_4x4()
    )


def scale_change(obj):
    """The factor on each axis by which obj's world scale changed since import, else None"""
    recorded = _recorded_matrix(obj)
    if recorded is None:
        return None
    now, then = object_world_matrix(obj).to_scale(), recorded.to_scale()
    if scales_near(now, then):
        return None
    return Vector(
        tuple(value / before if before else value for value, before in zip(now, then))
    )


def placement_matrix(obj, placed):
    """Where the world matrix placed lands for obj"""
    recorded = _recorded_matrix(obj)
    now = object_world_matrix(obj)
    if recorded is None:
        return now
    return Matrix(transfer_matrix_delta(now, recorded, placed).tolist())


def moved_placement(obj, placed):
    """placement_matrix of obj and placed once obj moved, else None"""
    return None if moved_matrix(obj) is None else placement_matrix(obj, placed)


def transform_values(matrix):
    """(position, orientation i/j/k/r, scale) of a world matrix, as ArchiveXL writes them"""
    location, rotation, scale = matrix.decompose()
    return (
        tuple(_number(value) for value in location),
        tuple(
            _number(value) for value in quaternion_ijkr_from_wxyz(rotation.normalized())
        ),
        tuple(_number(value) for value in scale),
    )
