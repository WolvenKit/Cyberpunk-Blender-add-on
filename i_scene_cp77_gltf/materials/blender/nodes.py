from ...blender.transactions import track_created_datablock
import math

import bpy
import numpy as np

from .images import imageFromPath
from .profiling import begin_material_phase, end_material_phase

def loc(nodename):
    return bpy.app.translations.pgettext(nodename)


def get_inputs(tree):
    return [
        item for item in tree.interface.items_tree
        if item.item_type == 'SOCKET' and item.in_out == 'INPUT'
        ]


def get_outputs(tree):
    return [
        item for item in tree.interface.items_tree
        if item.item_type == 'SOCKET' and item.in_out == 'OUTPUT'
        ]


_BSDF_SOCKET_NAMES = {
    'Subsurface Color': 'Base Color',
    'Subsurface': 'Subsurface Weight',
    'Specular': 'Specular IOR Level',
    'Transmission': 'Transmission Weight',
    'Coat': 'Coat Weight',
    'Sheen': 'Sheen Weight',
    'Emission': 'Emission Color',
}


def bsdf_socket_names():
    return _BSDF_SOCKET_NAMES


def CreateShaderNodeTexImage(curMat, path=None, x=0, y=0, name=None, image_format='png', nonCol=False):
    ImgNode = curMat.nodes.new("ShaderNodeTexImage")
    ImgNode.location = (x, y)
    ImgNode.hide = True
    if name:
        ImgNode.label = name
    if path:
        Img = imageFromPath(path, image_format, nonCol)
        ImgNode.image = Img

    return ImgNode


def CreateCullBackfaceGroup(curMat, x=0, y=0, name='Cull Backface'):
    group = bpy.data.node_groups.get("Cull Backface")

    if group is None:
        group = track_created_datablock("node_groups", bpy.data.node_groups.new("Cull Backface", "ShaderNodeTree"))

        GroupInN = group.nodes.new("NodeGroupInput")
        GroupInN.location = (-1000, 0)

        GroupOutN = group.nodes.new("NodeGroupOutput")
        GroupOutN.location = (0, 0)
        input_socket = group.interface.new_socket(name="Input", socket_type='NodeSocketFloat', in_out='INPUT')
        output_socket = group.interface.new_socket(name="Output", socket_type='NodeSocketFloat', in_out='OUTPUT')

        input_socket.default_value = 1.0

        GeometryNode = group.nodes.new("ShaderNodeNewGeometry")
        GeometryNode.location = (-750, -300)

        OneMinusNode = group.nodes.new("ShaderNodeMath")
        OneMinusNode.location = (-500, -300)
        OneMinusNode.operation = 'SUBTRACT'
        OneMinusNode.inputs[0].default_value = 1.0

        MultiplyNode = group.nodes.new("ShaderNodeMath")
        MultiplyNode.operation = 'MULTIPLY'
        MultiplyNode.location = (-250, 0)

        group.links.new(GroupInN.outputs[0], MultiplyNode.inputs[0])
        group.links.new(GeometryNode.outputs[6], OneMinusNode.inputs[1])
        group.links.new(OneMinusNode.outputs[0], MultiplyNode.inputs[1])
        group.links.new(MultiplyNode.outputs[0], GroupOutN.inputs[0])

    ShaderGroup = curMat.nodes.new("ShaderNodeGroup")
    ShaderGroup.location = (x, y)
    ShaderGroup.hide = True
    ShaderGroup.node_tree = group
    ShaderGroup.name = name

    return ShaderGroup


def CreateRebildNormalGroup(curMat, x=0, y=0, name='Rebuild Normal Z'):
    group = bpy.data.node_groups.get("Rebuild Normal Z")

    if group is None:
        group = track_created_datablock("node_groups", bpy.data.node_groups.new("Rebuild Normal Z", "ShaderNodeTree"))

        GroupInN = group.nodes.new("NodeGroupInput")
        GroupInN.location = (-1400, 0)

        GroupOutN = group.nodes.new("NodeGroupOutput")
        GroupOutN.location = (200, 0)
        group.interface.new_socket(name="Image", socket_type='NodeSocketColor', in_out='INPUT')
        group.interface.new_socket(name="Image", socket_type='NodeSocketColor', in_out='OUTPUT')

        VMup = group.nodes.new("ShaderNodeVectorMath")
        VMup.location = (-1200, -200)
        VMup.operation = 'MULTIPLY'
        VMup.inputs[1].default_value[0] = 2.0
        VMup.inputs[1].default_value[1] = 2.0

        VSub = group.nodes.new("ShaderNodeVectorMath")
        VSub.location = (-1000, -200)
        VSub.operation = 'SUBTRACT'
        VSub.name = 'NormalSubtract'
        VSub.inputs[1].default_value[0] = 1.0
        VSub.inputs[1].default_value[1] = 1.0

        VDot = group.nodes.new("ShaderNodeVectorMath")
        VDot.location = (-800, -200)
        VDot.operation = 'DOT_PRODUCT'

        Sub = group.nodes.new("ShaderNodeMath")
        Sub.location = (-600, -200)
        Sub.operation = 'SUBTRACT'
        group.links.new(VDot.outputs[0], Sub.inputs[1])
        Sub.inputs[0].default_value = 1.020

        SQR = group.nodes.new("ShaderNodeMath")
        SQR.location = (-400, -200)
        SQR.operation = 'SQRT'

        Range = group.nodes.new("ShaderNodeMapRange")
        Range.location = (-200, -200)
        Range.clamp = True
        Range.inputs[1].default_value = -1.0

        Sep = group.nodes.new("ShaderNodeSeparateColor")
        Sep.mode = 'RGB'
        Sep.location = (-600, 0)
        Comb = group.nodes.new("ShaderNodeCombineColor")
        Comb.mode = 'RGB'
        Comb.location = (-300, 0)

        RGBCurvesConvert = group.nodes.new("ShaderNodeRGBCurve")
        RGBCurvesConvert.label = "Convert DX to OpenGL Normal"
        RGBCurvesConvert.hide = True
        RGBCurvesConvert.location = (-100, 0)
        RGBCurvesConvert.mapping.curves[1].points[0].location = (0, 1)
        RGBCurvesConvert.mapping.curves[1].points[1].location = (1, 0)

        group.links.new(GroupInN.outputs[0], VMup.inputs[0])
        group.links.new(VMup.outputs[0], VSub.inputs[0])
        group.links.new(VSub.outputs[0], VDot.inputs[0])
        group.links.new(VSub.outputs[0], VDot.inputs[1])
        group.links.new(VDot.outputs["Value"], Sub.inputs[1])
        group.links.new(Sub.outputs[0], SQR.inputs[0])
        group.links.new(SQR.outputs[0], Range.inputs[0])
        group.links.new(GroupInN.outputs[0], Sep.inputs[0])
        group.links.new(Sep.outputs[0], Comb.inputs[0])
        group.links.new(Sep.outputs[1], Comb.inputs[1])
        group.links.new(Range.outputs[0], Comb.inputs[2])
        group.links.new(Comb.outputs[0], RGBCurvesConvert.inputs[1])
        group.links.new(RGBCurvesConvert.outputs[0], GroupOutN.inputs[0])

    ShaderGroup = curMat.nodes.new("ShaderNodeGroup")
    ShaderGroup.location = (x, y)
    ShaderGroup.hide = True
    ShaderGroup.node_tree = group
    ShaderGroup.name = name

    return ShaderGroup


def CreateCalculateVecNormalZ(curMat, x=0, y=0, name='Calculate Vectorized Normal Z'):
    group = bpy.data.node_groups.get("Calculate Vectorized Normal Z")

    if group is None:
        group = track_created_datablock("node_groups", bpy.data.node_groups.new("Calculate Vectorized Normal Z", "ShaderNodeTree"))

        GroupInN = group.nodes.new("NodeGroupInput")
        GroupInN.location = (-1400, 0)

        GroupOutN = group.nodes.new("NodeGroupOutput")
        GroupOutN.location = (300, 0)
        group.interface.new_socket(name="Image", socket_type='NodeSocketVector', in_out='INPUT')
        group.interface.new_socket(name="Image", socket_type='NodeSocketColor', in_out='OUTPUT')

        VDot = group.nodes.new("ShaderNodeVectorMath")
        VDot.location = (-900, -200)
        VDot.operation = 'DOT_PRODUCT'

        Sub = group.nodes.new("ShaderNodeMath")
        Sub.location = (-700, -200)
        Sub.operation = 'SUBTRACT'
        group.links.new(VDot.outputs[0], Sub.inputs[1])
        Sub.inputs[0].default_value = 1.0

        SQR = group.nodes.new("ShaderNodeMath")
        SQR.location = (-500, -200)
        SQR.operation = 'SQRT'

        Sep = group.nodes.new("ShaderNodeSeparateColor")
        Sep.location = (-700, 100)

        Mult = group.nodes.new("ShaderNodeMath")
        Mult.operation = 'MULTIPLY'
        Mult.location = (-500, 0)
        Mult.label = "OpenGL to DX"
        Mult.inputs[1].default_value = -1.0

        Comb = group.nodes.new("ShaderNodeCombineColor")
        Comb.location = (-300, 100)

        MultAdd = group.nodes.new("ShaderNodeVectorMath")
        MultAdd.location = (-50, 0)
        MultAdd.operation = "MULTIPLY_ADD"
        MultAdd.inputs[1].default_value = 0.5, 0.5, 0.5
        MultAdd.inputs[2].default_value = 0.5, 0.5, 0.5

        group.links.new(GroupInN.outputs[0], Sep.inputs[0])
        group.links.new(GroupInN.outputs[0], VDot.inputs[0])
        group.links.new(GroupInN.outputs[0], VDot.inputs[1])
        group.links.new(VDot.outputs["Value"], Sub.inputs[1])
        group.links.new(Sub.outputs[0], SQR.inputs[0])
        group.links.new(SQR.outputs[0], Comb.inputs[2])
        group.links.new(Sep.outputs[0], Comb.inputs[0])
        group.links.new(Sep.outputs[1], Mult.inputs[0])
        group.links.new(Mult.outputs[0], Comb.inputs[1])
        group.links.new(Comb.outputs[0], MultAdd.inputs[0])
        group.links.new(MultAdd.outputs[0], GroupOutN.inputs[0])

    ShaderGroup = curMat.nodes.new("ShaderNodeGroup")
    ShaderGroup.location = (x, y)
    ShaderGroup.hide = True
    ShaderGroup.node_tree = group
    ShaderGroup.name = name

    return ShaderGroup


def CreateShaderNodeNormalMap(curMat, path=None, x=0, y=0, name=None, image_format='png', nonCol=True):
    nMap = curMat.nodes.new("ShaderNodeNormalMap")
    nMap.location = (x, y)
    nMap.hide = True

    if path is not None:
        ImgNode = curMat.nodes.new("ShaderNodeTexImage")
        ImgNode.location = (x - 400, y)
        ImgNode.hide = True
        if name is not None:
            ImgNode.label = name
        Img = imageFromPath(path, image_format, nonCol)
        ImgNode.image = Img

        NormalRebuildGroup = CreateRebildNormalGroup(curMat, x - 150, y, name + ' Rebuilt')

        curMat.links.new(ImgNode.outputs[0], NormalRebuildGroup.inputs[0])
        curMat.links.new(NormalRebuildGroup.outputs[0], nMap.inputs[1])

    return nMap


def CreateShaderNodeGlobalNormalMap(curMat, path=None, x=0, y=0, name=None, image_format='png', nonCol=True):
    if path is not None:
        ImgNode = curMat.nodes.new("ShaderNodeTexImage")
        ImgNode.location = (x - 450, y)
        ImgNode.width = 350
        ImgNode.hide = False
        Img = imageFromPath(path, image_format, nonCol)
        ImgNode.image = Img
    return ImgNode


def CreateShaderNodeVectorizedNormalMap(curMat, path=None, x=0, y=0, name=None, image_format='png', nonCol=True):
    normalVectorize = curMat.nodes.new("ShaderNodeVectorMath")
    normalVectorize.operation = 'MULTIPLY_ADD'
    normalVectorize.location = (x, y)
    normalVectorize.hide = True
    normalVectorize.inputs[1].default_value = 2, 2, 0
    normalVectorize.inputs[2].default_value = -1, -1, 0

    if path is not None:
        ImgNode = curMat.nodes.new("ShaderNodeTexImage")
        ImgNode.location = (x - 450, y)
        ImgNode.width = 350
        ImgNode.hide = False
        Img = imageFromPath(path, image_format, nonCol)
        ImgNode.image = Img

        curMat.links.new(ImgNode.outputs[0], normalVectorize.inputs[0])

    return normalVectorize


def CreateShaderNodeRGB(curMat, color, x=0, y=0, name=None, isVector=False):
    rgbNode = curMat.nodes.new("ShaderNodeRGB")
    rgbNode.location = (x, y)
    rgbNode.hide = True
    if name is not None:
        rgbNode.label = name

    if isVector:
        rgbNode.outputs[0].default_value = (float(color["X"]), float(color["Y"]), float(color["Z"]), float(color["W"]))
    else:
        rgbNode.outputs[0].default_value = (float(color["Red"]) / 255, float(color["Green"]) / 255,
                                            float(color["Blue"]) / 255, float(color["Alpha"]) / 255)

    return rgbNode


def CreateShaderNodeValue(curMat, value=0, x=0, y=0, name=None):
    valNode = curMat.nodes.new("ShaderNodeValue")
    valNode.location = (x, y)
    valNode.outputs[0].default_value = float(value)
    valNode.hide = True
    if name:
        valNode.label = name

    return valNode


def create_node(NG, type, loc, hide=True, operation=None, image=None, label=None, blend_type=None):
    started = begin_material_phase()
    Node = None
    try:
        Node = NG.new(type)
        Node.hide = hide
        Node.location = loc
        if operation:
            Node.operation = operation
        if image:
            Node.image = image
        if label:
            Node.label = label
        if blend_type:
            Node.blend_type = blend_type
        return Node
    finally:
        if started is not None:
            end_material_phase(
                started,
                "material.node_create",
                label=str(label or type or ""),
                metadata={"nodeType": str(type or "")},
            )


def createOverrideTable(matTemplateObj):
    if not isinstance(matTemplateObj, dict):
        raise TypeError("MLTemplate root must be a mapping")
    OverList = matTemplateObj.get("overrides")
    if OverList is None:
        OverList = matTemplateObj.get("Overrides")
    if not isinstance(OverList, dict):
        OverList = {}

    def entries(name):
        values = OverList.get(name)
        if values is None:
            values = OverList.get(name[:1].upper() + name[1:])
        return values if isinstance(values, (list, tuple)) else ()

    Output = {}
    Output["ColorScale"] = {}
    Output["NormalStrength"] = {}
    Output["RoughLevelsIn"] = {}
    Output["RoughLevelsOut"] = {}
    Output["MetalLevelsIn"] = {}
    Output["MetalLevelsOut"] = {}
    for x in entries("colorScale"):
        tmpName = x["n"]["$value"]
        tmpR = float(x["v"]["Elements"][0])
        tmpG = float(x["v"]["Elements"][1])
        tmpB = float(x["v"]["Elements"][2])
        Output["ColorScale"][tmpName] = (tmpR, tmpG, tmpB, 1)
    for x in entries("normalStrength"):
        tmpName = x["n"]["$value"]
        tmpStrength = 0
        if x.get("v") is not None:
            tmpStrength = float(x["v"])
        Output["NormalStrength"][tmpName] = tmpStrength
    for x in entries("roughLevelsIn"):
        tmpName = x["n"]["$value"]
        tmpStrength0 = float(x["v"]["Elements"][0])
        tmpStrength1 = float(x["v"]["Elements"][1])
        Output["RoughLevelsIn"][tmpName] = [(tmpStrength0), (tmpStrength1)]
    for x in entries("roughLevelsOut"):
        tmpName = x["n"]["$value"]
        tmpStrength0 = float(x["v"]["Elements"][0])
        tmpStrength1 = float(x["v"]["Elements"][1])
        Output["RoughLevelsOut"][tmpName] = [(tmpStrength0), (tmpStrength1)]
    for x in entries("metalLevelsIn"):
        tmpName = x["n"]["$value"]
        if x.get("v") is not None:
            tmpStrength0 = float(x["v"]["Elements"][0])
            tmpStrength1 = float(x["v"]["Elements"][1])
        else:
            tmpStrength0 = 0
            tmpStrength1 = 1
        Output["MetalLevelsIn"][tmpName] = [(tmpStrength0), (tmpStrength1)]
    for x in entries("metalLevelsOut"):
        tmpName = x["n"]["$value"]
        if x.get("v") is not None:
            tmpStrength0 = float(x["v"]["Elements"][0])
            tmpStrength1 = float(x["v"]["Elements"][1])
        else:
            tmpStrength0 = 0
            tmpStrength1 = 1
        Output["MetalLevelsOut"][tmpName] = [(tmpStrength0), (tmpStrength1)]
    return Output


def createParallaxGroup():
    CurMat = bpy.data.node_groups.get('CP77_Parallax')
    if CurMat:
        return CurMat
    else:
        CurMat = track_created_datablock("node_groups", bpy.data.node_groups.new('CP77_Parallax', 'ShaderNodeTree'))
        CurMat.interface.new_socket(name="Distance", socket_type='NodeSocketFloat', in_out='INPUT')
        CurMat.interface.new_socket(name="Vector", socket_type='NodeSocketVector', in_out='OUTPUT')
        GroupOutput = create_node(CurMat.nodes, "NodeGroupOutput", (771.574462890625, 0.0), label="Group Output")
        Tangent = create_node(CurMat.nodes, "ShaderNodeTangent", (-565., -136.), label="Tangent")
        Tangent.direction_type = 'UV_MAP'
        VectorMath = create_node(
            CurMat.nodes, "ShaderNodeVectorMath", (-566., -342.), operation='CROSS_PRODUCT', label="Vector Math"
            )
        VectorMath002 = create_node(
            CurMat.nodes, "ShaderNodeVectorMath", (-227., -208.), operation='DOT_PRODUCT', label="Vector Math.002"
            )
        VectorMath004 = create_node(
            CurMat.nodes, "ShaderNodeVectorMath", (361., 34.), operation='SCALE', label="Vector Math.004"
            )
        VectorMath005 = create_node(
            CurMat.nodes, "ShaderNodeVectorMath", (581., 123.), operation='SUBTRACT', label="Vector Math.005"
            )
        UVMap = create_node(CurMat.nodes, "ShaderNodeUVMap", (299., 342.), label="UV Map")
        VectorMath001 = create_node(
            CurMat.nodes, "ShaderNodeVectorMath", (-248., 37.), operation='DOT_PRODUCT', label="Vector Math.001"
            )
        VectorMath006 = create_node(
            CurMat.nodes, "ShaderNodeVectorMath", (-95., 332.), operation='DOT_PRODUCT', label="Vector Math.006"
            )
        Geometry = create_node(CurMat.nodes, "ShaderNodeNewGeometry", (-581., 222.), label="Geometry")
        Math = create_node(CurMat.nodes, "ShaderNodeMath", (159., -230.), operation='DIVIDE', label="Math")
        CombineXYZ = create_node(CurMat.nodes, "ShaderNodeCombineXYZ", (-13., 31.), label="Combine XYZ")
        GroupInput = create_node(CurMat.nodes, "NodeGroupInput", (-781., 0.0), label="Group Input")
        CurMat.links.new(VectorMath005.outputs['Vector'], GroupOutput.inputs[0])
        CurMat.links.new(Geometry.outputs['Normal'], VectorMath.inputs[0])
        CurMat.links.new(Tangent.outputs['Tangent'], VectorMath.inputs[1])
        CurMat.links.new(Geometry.outputs['Incoming'], VectorMath002.inputs[0])
        CurMat.links.new(VectorMath.outputs['Vector'], VectorMath002.inputs[1])
        CurMat.links.new(CombineXYZ.outputs['Vector'], VectorMath004.inputs[0])
        CurMat.links.new(Math.outputs['Value'], VectorMath004.inputs[3])
        CurMat.links.new(UVMap.outputs['UV'], VectorMath005.inputs[0])
        CurMat.links.new(VectorMath004.outputs['Vector'], VectorMath005.inputs[1])
        CurMat.links.new(Geometry.outputs['Incoming'], VectorMath001.inputs[0])
        CurMat.links.new(Tangent.outputs['Tangent'], VectorMath001.inputs[1])
        CurMat.links.new(Geometry.outputs['Incoming'], VectorMath006.inputs[0])
        CurMat.links.new(Geometry.outputs['Normal'], VectorMath006.inputs[1])
        CurMat.links.new(GroupInput.outputs['Distance'], Math.inputs[0])
        CurMat.links.new(VectorMath006.outputs['Value'], Math.inputs[1])
        CurMat.links.new(VectorMath001.outputs['Value'], CombineXYZ.inputs[0])
        CurMat.links.new(VectorMath002.outputs['Value'], CombineXYZ.inputs[1])
        return CurMat


def CreateGradMapRamp(CurMat, grad_image_node, location=(-400, 250)):
    image = grad_image_node.image
    image_width = image.size[0]
    row_index = 0
    all_pixels = np.empty(len(image.pixels), dtype=np.float32)
    image.pixels.foreach_get(all_pixels)

    color_ramp_node = CurMat.nodes.new('ShaderNodeValToRGB')
    color_ramp_node.location = location

    step = math.ceil(image_width / 32) if image_width > 32 else 1
    color_ramp_node.color_ramp.elements.remove(color_ramp_node.color_ramp.elements[1])

    first = True
    for i in range(0, image_width, step):
        idx = (row_index * image_width + i) * 4
        r, g, b, a = all_pixels[idx:idx + 4]
        element = color_ramp_node.color_ramp.elements[0] if first else color_ramp_node.color_ramp.elements.new(
            i / image_width
            )
        element.color = (r, g, b, a)
        element.position = i / image_width
        first = False

    color_ramp_node.color_ramp.interpolation = 'CONSTANT'
    return color_ramp_node


def createLerpGroup():
    CurMat = bpy.data.node_groups.get('lerp')
    if CurMat:
        return CurMat
    else:
        CurMat = track_created_datablock("node_groups", bpy.data.node_groups.new('lerp', 'ShaderNodeTree'))
        CurMat.interface.new_socket(name="A", socket_type='NodeSocketFloat', in_out='INPUT')
        CurMat.interface.new_socket(name="B", socket_type='NodeSocketFloat', in_out='INPUT')
        CurMat.interface.new_socket(name="t", socket_type='NodeSocketFloat', in_out='INPUT')
        CurMat.interface.new_socket(name="result", socket_type='NodeSocketFloat', in_out='OUTPUT')
        GroupInput = create_node(CurMat.nodes, "NodeGroupInput", (0, 0), label="Group Input")
        GroupOutput = create_node(CurMat.nodes, "NodeGroupOutput", (700, 0), label="Group Output")
        sub = create_node(CurMat.nodes, "ShaderNodeMath", (200, 100), operation='SUBTRACT')
        mul = create_node(CurMat.nodes, "ShaderNodeMath", (350, 50), operation='MULTIPLY')
        mul2 = create_node(CurMat.nodes, "ShaderNodeMath", (350, -50), operation='MULTIPLY')
        add = create_node(CurMat.nodes, "ShaderNodeMath", (500, 0), operation='ADD')
        sub.inputs[0].default_value = 1.0
        CurMat.links.new(GroupInput.outputs[2], sub.inputs[1])
        CurMat.links.new(sub.outputs[0], mul.inputs[0])
        CurMat.links.new(GroupInput.outputs[0], mul.inputs[1])
        CurMat.links.new(GroupInput.outputs[2], mul2.inputs[0])
        CurMat.links.new(GroupInput.outputs[1], mul2.inputs[1])
        CurMat.links.new(GroupInput.outputs[1], mul2.inputs[1])
        CurMat.links.new(mul.outputs[0], add.inputs[0])
        CurMat.links.new(mul2.outputs[0], add.inputs[1])
        CurMat.links.new(add.outputs[0], GroupOutput.inputs[0])
        return CurMat


def createVecLerpGroup():
    CurMat = bpy.data.node_groups.get('vecLerp')
    if CurMat:
        return CurMat
    else:
        CurMat = track_created_datablock("node_groups", bpy.data.node_groups.new('vecLerp', 'ShaderNodeTree'))
        CurMat.interface.new_socket(name="A", socket_type='NodeSocketVector', in_out='INPUT')
        CurMat.interface.new_socket(name="B", socket_type='NodeSocketVector', in_out='INPUT')
        CurMat.interface.new_socket(name="t", socket_type='NodeSocketVector', in_out='INPUT')
        CurMat.interface.new_socket(name="result", socket_type='NodeSocketVector', in_out='OUTPUT')
        GroupInput = create_node(CurMat.nodes, "NodeGroupInput", (0, 0), label="Group Input")
        GroupOutput = create_node(CurMat.nodes, "NodeGroupOutput", (700, 0), label="Group Output")
        sub = create_node(CurMat.nodes, "ShaderNodeVectorMath", (200, 100), operation='SUBTRACT')
        mul = create_node(CurMat.nodes, "ShaderNodeVectorMath", (350, 50), operation='MULTIPLY')
        mul2 = create_node(CurMat.nodes, "ShaderNodeVectorMath", (350, -50), operation='MULTIPLY')
        add = create_node(CurMat.nodes, "ShaderNodeVectorMath", (500, 0), operation='ADD')
        sub.inputs[0].default_value = (1, 1, 1)
        CurMat.links.new(GroupInput.outputs[2], sub.inputs[1])
        CurMat.links.new(sub.outputs[0], mul.inputs[0])
        CurMat.links.new(GroupInput.outputs[0], mul.inputs[1])
        CurMat.links.new(GroupInput.outputs[2], mul2.inputs[0])
        CurMat.links.new(GroupInput.outputs[1], mul2.inputs[1])
        CurMat.links.new(GroupInput.outputs[1], mul2.inputs[1])
        CurMat.links.new(mul.outputs[0], add.inputs[0])
        CurMat.links.new(mul2.outputs[0], add.inputs[1])
        CurMat.links.new(add.outputs[0], GroupOutput.inputs[0])
        return CurMat


def createHash12Group():
    CurMat = bpy.data.node_groups.get('hash12')
    if CurMat:
        return CurMat
    else:
        CurMat = track_created_datablock("node_groups", bpy.data.node_groups.new('hash12', 'ShaderNodeTree'))
        CurMat.interface.new_socket(name="vector", socket_type='NodeSocketVector', in_out='INPUT')
        CurMat.interface.new_socket(name="result", socket_type='NodeSocketFloat', in_out='OUTPUT')
        GroupInput = create_node(CurMat.nodes, "NodeGroupInput", (-500, 0), label="Group Input")
        GroupOutput = create_node(CurMat.nodes, "NodeGroupOutput", (1350, 0), label="Group Output")
        separate = create_node(CurMat.nodes, "ShaderNodeSeparateXYZ", (-350, 0))
        combine = create_node(CurMat.nodes, "ShaderNodeCombineXYZ", (-200, 0))
        combine2 = create_node(CurMat.nodes, "ShaderNodeCombineXYZ", (-200, -50))
        vecMul = create_node(CurMat.nodes, "ShaderNodeVectorMath", (0, 0), operation="MULTIPLY")
        frac = create_node(CurMat.nodes, "ShaderNodeVectorMath", (150, 0), operation="FRACTION")
        vecMul.inputs[1].default_value = (.1031, .1031, .1031)
        dot = create_node(CurMat.nodes, "ShaderNodeVectorMath", (300, -50), operation="DOT_PRODUCT")
        vecAdd = create_node(CurMat.nodes, "ShaderNodeVectorMath", (0, -50), operation="ADD")
        vecAdd2 = create_node(CurMat.nodes, "ShaderNodeVectorMath", (600, 0), operation="ADD")
        combine3 = create_node(CurMat.nodes, "ShaderNodeCombineXYZ", (450, -50))
        separate2 = create_node(CurMat.nodes, "ShaderNodeSeparateXYZ", (750, 0))
        add = create_node(CurMat.nodes, "ShaderNodeMath", (900, 0), operation="ADD")
        mul = create_node(CurMat.nodes, "ShaderNodeMath", (1050, 0), operation="MULTIPLY")
        frac2 = create_node(CurMat.nodes, "ShaderNodeMath", (1200, 0), operation="FRACT")
        CurMat.links.new(GroupInput.outputs[0], separate.inputs[0])
        CurMat.links.new(separate.outputs[0], combine.inputs[0])
        CurMat.links.new(separate.outputs[1], combine.inputs[1])
        CurMat.links.new(separate.outputs[0], combine.inputs[2])
        CurMat.links.new(combine.outputs[0], vecMul.inputs[0])
        CurMat.links.new(vecMul.outputs[0], frac.inputs[0])
        CurMat.links.new(separate.outputs[1], combine2.inputs[0])
        CurMat.links.new(separate.outputs[2], combine2.inputs[1])
        CurMat.links.new(separate.outputs[0], combine2.inputs[2])
        CurMat.links.new(combine2.outputs[0], vecAdd.inputs[0])
        vecAdd.inputs[1].default_value = (33.33, 33.33, 33.33)
        CurMat.links.new(frac.outputs[0], dot.inputs[0])
        CurMat.links.new(vecAdd.outputs[0], dot.inputs[1])
        CurMat.links.new(dot.outputs["Value"], combine3.inputs[0])
        CurMat.links.new(dot.outputs["Value"], combine3.inputs[1])
        CurMat.links.new(dot.outputs["Value"], combine3.inputs[2])
        CurMat.links.new(frac.outputs[0], vecAdd2.inputs[0])
        CurMat.links.new(combine3.outputs[0], vecAdd2.inputs[1])
        CurMat.links.new(vecAdd2.outputs[0], separate2.inputs[0])
        CurMat.links.new(separate2.outputs[0], add.inputs[0])
        CurMat.links.new(separate2.outputs[1], add.inputs[1])
        CurMat.links.new(add.outputs[0], mul.inputs[0])
        CurMat.links.new(separate2.outputs[2], mul.inputs[1])
        CurMat.links.new(mul.outputs[0], frac2.inputs[0])
        CurMat.links.new(frac2.outputs[0], GroupOutput.inputs[0])
        return CurMat
