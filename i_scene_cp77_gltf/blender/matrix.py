from __future__ import annotations

from mathutils import Matrix, Quaternion, Vector

from ..assetio.transform_values import quaternion_wxyz_from_ijkr


def safe_matrix_inverse(matrix):
    return (
        matrix.inverted_safe()
        if hasattr(matrix, "inverted_safe")
        else matrix.inverted()
    )


def matrix_from_flat(values):
    """Rebuild a 4x4 Matrix from 16 row-major values, or return None when they are not 16 numbers"""
    try:
        flat = [float(component) for component in values]
    except (TypeError, ValueError):
        return None
    if len(flat) != 16:
        return None
    return Matrix((flat[0:4], flat[4:8], flat[8:12], flat[12:16]))


def object_world_matrix(obj):
    """World matrix composed from the object's own and its object parents' transforms"""
    if obj.parent is None:
        return obj.matrix_basis.copy()
    if obj.parent_type != "OBJECT":
        return obj.matrix_world.copy()
    return (
        object_world_matrix(obj.parent) @ obj.matrix_parent_inverse @ obj.matrix_basis
    )


def instance_matrix(instance, scale=1):
    """The world matrix of a node data entry (a NodeInstance), its scale divided by the import's scale"""
    inst_scale = Vector(instance.scale)
    if scale != 1:
        inst_scale = Vector(
            (inst_scale.x / scale, inst_scale.y / scale, inst_scale.z / scale)
        )
    return Matrix.LocRotScale(
        Vector(instance.position),
        Quaternion(quaternion_wxyz_from_ijkr(instance.orientation)),
        inst_scale,
    )
