<<<<<<< Updated upstream

def get_pos(inst):
    pos = [0, 0, 0]
    if 'Position' in inst.keys():
        if 'Properties' in inst['Position'].keys():
            pos[0] = inst['Position']['Properties']['X']
            pos[1] = inst['Position']['Properties']['Y']
            pos[2] = inst['Position']['Properties']['Z']
        else:
            if 'X' in inst['Position'].keys():
                pos[0] = inst['Position']['X']
                pos[1] = inst['Position']['Y']
                pos[2] = inst['Position']['Z']
            else:
                pos[0] = inst['Position']['x']
                pos[1] = inst['Position']['y']
                pos[2] = inst['Position']['z']
    elif 'position' in inst.keys():
        if 'X' in inst['position'].keys():
            pos[0] = inst['position']['X']
            pos[1] = inst['position']['Y']
            pos[2] = inst['position']['Z']
    elif 'translation' in inst.keys():
        pos[0] = inst['translation']['X']
        pos[1] = inst['translation']['Y']
        pos[2] = inst['translation']['Z']
    return pos


def get_rot(inst):
    rot = [0, 0, 0, 0]
    if 'Orientation' in inst.keys():
        if 'Properties' in inst['Orientation'].keys():
            rot[0] = inst['Orientation']['Properties']['r']
            rot[1] = inst['Orientation']['Properties']['i']
            rot[2] = inst['Orientation']['Properties']['j']
            rot[3] = inst['Orientation']['Properties']['k']
        else:
            rot[0] = inst['Orientation']['r']
            rot[1] = inst['Orientation']['i']
            rot[2] = inst['Orientation']['j']
            rot[3] = inst['Orientation']['k']
    elif 'orientation' in inst.keys():
        rot[0] = inst['orientation']['r']
        rot[1] = inst['orientation']['i']
        rot[2] = inst['orientation']['j']
        rot[3] = inst['orientation']['k']
    elif 'Rotation' in inst.keys():
        rot[0] = inst['Rotation']['r']
        rot[1] = inst['Rotation']['i']
        rot[2] = inst['Rotation']['j']
        rot[3] = inst['Rotation']['k']
    elif 'rotation' in inst.keys():
        rot[0] = inst['rotation']['r']
        rot[1] = inst['rotation']['i']
        rot[2] = inst['rotation']['j']
        rot[3] = inst['rotation']['k']
    return rot


def set_pos(inst, obj):
    # print(inst)
    if 'Position' in inst.keys():
        if 'Properties' in inst['Position'].keys():
            inst['Position']['Properties']['X'] = float("{:.9g}".format(obj.location[0]))
            inst['Position']['Properties']['Y'] = float("{:.9g}".format(obj.location[1]))
            inst['Position']['Properties']['Z'] = float("{:.9g}".format(obj.location[2]))
        else:
            if 'X' in inst['Position'].keys():
                inst['Position']['X'] = float("{:.9g}".format(obj.location[0]))
                inst['Position']['Y'] = float("{:.9g}".format(obj.location[1]))
                inst['Position']['Z'] = float("{:.9g}".format(obj.location[2]))
            else:
                inst['Position']['x'] = float("{:.9g}".format(obj.location[0]))
                inst['Position']['y'] = float("{:.9g}".format(obj.location[1]))
                inst['Position']['z'] = float("{:.9g}".format(obj.location[2]))
    elif 'position' in inst.keys():
        inst['position']['X'] = float("{:.9g}".format(obj.location[0]))
        inst['position']['Y'] = float("{:.9g}".format(obj.location[1]))
        inst['position']['Z'] = float("{:.9g}".format(obj.location[2]))
    elif 'translation' in inst.keys():
        inst['translation']['X'] = float("{:.9g}".format(obj.location[0]))
        inst['translation']['Y'] = float("{:.9g}".format(obj.location[1]))
        inst['translation']['Z'] = float("{:.9g}".format(obj.location[2]))


def set_z_pos(inst, obj):
    # print(inst)
    if 'Position' in inst.keys():
        if 'Properties' in inst['Position'].keys():
            inst['Position']['Properties']['Z'] = float("{:.9g}".format(obj.location[2]))
        else:
            if 'X' in inst['Position'].keys():
                inst['Position']['Z'] = float("{:.9g}".format(obj.location[2]))
            else:
                inst['Position']['z'] = float("{:.9g}".format(obj.location[2]))
    elif 'position' in inst.keys():
        inst['position']['Z'] = float("{:.9g}".format(obj.location[2]))
    elif 'translation' in inst.keys():
        inst['translation']['Z'] = float("{:.9g}".format(obj.location[2]))


def set_rot(inst, obj):
    if 'Orientation' in inst.keys():
        if 'Properties' in inst['Orientation'].keys():
            inst['Orientation']['Properties']['r'] = float("{:.9g}".format(obj.rotation_quaternion[0]))
            inst['Orientation']['Properties']['i'] = float("{:.9g}".format(obj.rotation_quaternion[1]))
            inst['Orientation']['Properties']['j'] = float("{:.9g}".format(obj.rotation_quaternion[2]))
            inst['Orientation']['Properties']['k'] = float("{:.9g}".format(obj.rotation_quaternion[3]))
        else:
            inst['Orientation']['r'] = float("{:.9g}".format(obj.rotation_quaternion[0]))
            inst['Orientation']['i'] = float("{:.9g}".format(obj.rotation_quaternion[1]))
            inst['Orientation']['j'] = float("{:.9g}".format(obj.rotation_quaternion[2]))
            inst['Orientation']['k'] = float("{:.9g}".format(obj.rotation_quaternion[3]))
    elif 'Rotation' in inst.keys():
        inst['Rotation']['r'] = float("{:.9g}".format(obj.rotation_quaternion[0]))
        inst['Rotation']['i'] = float("{:.9g}".format(obj.rotation_quaternion[1]))
        inst['Rotation']['j'] = float("{:.9g}".format(obj.rotation_quaternion[2]))
        inst['Rotation']['k'] = float("{:.9g}".format(obj.rotation_quaternion[3]))
    elif 'rotation' in inst.keys():
        inst['rotation']['r'] = float("{:.9g}".format(obj.rotation_quaternion[0]))
        inst['rotation']['i'] = float("{:.9g}".format(obj.rotation_quaternion[1]))
        inst['rotation']['j'] = float("{:.9g}".format(obj.rotation_quaternion[2]))
        inst['rotation']['k'] = float("{:.9g}".format(obj.rotation_quaternion[3]))
    elif 'orientation' in inst.keys():
        inst['orientation']['r'] = float("{:.9g}".format(obj.rotation_quaternion[0]))
        inst['orientation']['i'] = float("{:.9g}".format(obj.rotation_quaternion[1]))
        inst['orientation']['j'] = float("{:.9g}".format(obj.rotation_quaternion[2]))
        inst['orientation']['k'] = float("{:.9g}".format(obj.rotation_quaternion[3]))


def set_scale(inst, obj):
    if 'Scale' in inst.keys():
        if 'Properties' in inst['Scale'].keys():
            inst['Scale']['Properties']['X'] = float("{:.9g}".format(obj.scale[0]))
            inst['Scale']['Properties']['Y'] = float("{:.9g}".format(obj.scale[1]))
            inst['Scale']['Properties']['Z'] = float("{:.9g}".format(obj.scale[2]))
        else:
            inst['Scale']['X'] = float("{:.9g}".format(obj.scale[0]))
            inst['Scale']['Y'] = float("{:.9g}".format(obj.scale[1]))
            inst['Scale']['Z'] = float("{:.9g}".format(obj.scale[2]))
    elif 'scale' in inst.keys():
        inst['scale']['X'] = float("{:.9g}".format(obj.scale[0]))
        inst['scale']['Y'] = float("{:.9g}".format(obj.scale[1]))
        inst['scale']['Z'] = float("{:.9g}".format(obj.scale[2]))


def set_bounds(node, obj):
    node["Bounds"]['Max']["X"] = float("{:.9g}".format(obj.location[0]))
    node["Bounds"]['Max']["Y"] = float("{:.9g}".format(obj.location[1]))
    node["Bounds"]['Max']["Z"] = float("{:.9g}".format(obj.location[2]))
    node["Bounds"]['Min']["X"] = float("{:.9g}".format(obj.location[0]))
    node["Bounds"]['Min']["Y"] = float("{:.9g}".format(obj.location[1]))
    node["Bounds"]['Min']["Z"] = float("{:.9g}".format(obj.location[2]))

=======
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
>>>>>>> Stashed changes
