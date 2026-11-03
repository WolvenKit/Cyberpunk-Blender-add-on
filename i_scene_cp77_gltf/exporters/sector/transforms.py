
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

