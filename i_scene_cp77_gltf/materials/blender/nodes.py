import math

import bpy
import numpy as np

from ...blender import shader_nodes
from ...blender.transactions import track_created_datablock
from .profiling import begin_material_phase, end_material_phase


def get_inputs(tree):
    return [
        item
        for item in tree.interface.items_tree
        if item.item_type == "SOCKET" and item.in_out == "INPUT"
    ]


_BSDF_SOCKET_NAMES = {
    "Subsurface Color": "Base Color",
    "Subsurface": "Subsurface Weight",
    "Specular": "Specular IOR Level",
    "Transmission": "Transmission Weight",
    "Coat": "Coat Weight",
    "Sheen": "Sheen Weight",
    "Emission": "Emission Color",
}


def bsdf_socket_names():
    return _BSDF_SOCKET_NAMES


def CreateCullBackfaceGroup(curMat, x=0, y=0, name="Cull Backface"):
    group = bpy.data.node_groups.get("Cull Backface")

    if group is None:
        group = track_created_datablock(
            "node_groups", bpy.data.node_groups.new("Cull Backface", "ShaderNodeTree")
        )

        GroupInN = group.nodes.new("NodeGroupInput")
        GroupInN.location = (-1000, 0)

        GroupOutN = group.nodes.new("NodeGroupOutput")
        GroupOutN.location = (0, 0)
        input_socket = group.interface.new_socket(
            name="Input", socket_type="NodeSocketFloat", in_out="INPUT"
        )
        group.interface.new_socket(
            name="Output", socket_type="NodeSocketFloat", in_out="OUTPUT"
        )

        input_socket.default_value = 1.0

        GeometryNode = group.nodes.new("ShaderNodeNewGeometry")
        GeometryNode.location = (-750, -300)

        OneMinusNode = shader_nodes.math(
            group.nodes, group.links, "SUBTRACT", location=(-500, -300)
        ).node
        OneMinusNode.inputs["Value"].default_value = 1.0

        MultiplyNode = shader_nodes.math(
            group.nodes, group.links, "MULTIPLY", location=(-250, 0)
        ).node

        group.links.new(GroupInN.outputs["Input"], MultiplyNode.inputs["Value"])
        group.links.new(
            GeometryNode.outputs["Backfacing"],
            shader_nodes.socket_by_identifier(OneMinusNode.inputs, "Value_001"),
        )
        group.links.new(
            OneMinusNode.outputs["Value"],
            shader_nodes.socket_by_identifier(MultiplyNode.inputs, "Value_001"),
        )
        group.links.new(MultiplyNode.outputs["Value"], GroupOutN.inputs["Output"])

    ShaderGroup = curMat.nodes.new("ShaderNodeGroup")
    ShaderGroup.location = (x, y)
    ShaderGroup.hide = True
    ShaderGroup.node_tree = group
    ShaderGroup.name = name

    return ShaderGroup


def CreateRebildNormalGroup(curMat, x=0, y=0, name="Rebuild Normal Z"):
    group = bpy.data.node_groups.get("Rebuild Normal Z v2")

    if group is None:
        group = track_created_datablock(
            "node_groups",
            bpy.data.node_groups.new("Rebuild Normal Z v2", "ShaderNodeTree"),
        )

        GroupInN = group.nodes.new("NodeGroupInput")
        GroupInN.location = (-1400, 0)

        GroupOutN = group.nodes.new("NodeGroupOutput")
        GroupOutN.location = (200, 0)
        group.interface.new_socket(
            name="Image", socket_type="NodeSocketColor", in_out="INPUT"
        )
        group.interface.new_socket(
            name="Image", socket_type="NodeSocketColor", in_out="OUTPUT"
        )

        VMup = shader_nodes.vector_math(
            group.nodes, group.links, "MULTIPLY", location=(-1200, -200)
        ).node
        shader_nodes.socket_by_identifier(VMup.inputs, "Vector_001").default_value[
            0
        ] = 2.0
        shader_nodes.socket_by_identifier(VMup.inputs, "Vector_001").default_value[
            1
        ] = 2.0

        VSub = shader_nodes.vector_math(
            group.nodes,
            group.links,
            "SUBTRACT",
            name="NormalSubtract",
            label="",
            location=(-1000, -200),
        ).node
        shader_nodes.socket_by_identifier(VSub.inputs, "Vector_001").default_value[
            0
        ] = 1.0
        shader_nodes.socket_by_identifier(VSub.inputs, "Vector_001").default_value[
            1
        ] = 1.0

        VDot = shader_nodes.vector_math(
            group.nodes, group.links, "DOT_PRODUCT", location=(-800, -200)
        ).node

        Sub = shader_nodes.math(
            group.nodes, group.links, "SUBTRACT", location=(-600, -200)
        ).node
        group.links.new(
            shader_nodes.socket_by_identifier(VDot.outputs, "Vector"),
            shader_nodes.socket_by_identifier(Sub.inputs, "Value_001"),
        )
        Sub.inputs["Value"].default_value = 1.0

        ClampZ = shader_nodes.math(
            group.nodes, group.links, "MAXIMUM", location=(-480, -200)
        ).node
        shader_nodes.socket_by_identifier(
            ClampZ.inputs, "Value_001"
        ).default_value = 0.0

        SQR = shader_nodes.math(
            group.nodes, group.links, "SQRT", location=(-320, -200)
        ).node

        Range = group.nodes.new("ShaderNodeMapRange")
        Range.location = (-200, -200)
        Range.clamp = True
        Range.inputs["From Min"].default_value = -1.0

        Sep = group.nodes.new("ShaderNodeSeparateColor")
        Sep.mode = "RGB"
        Sep.location = (-600, 0)
        Comb = group.nodes.new("ShaderNodeCombineColor")
        Comb.mode = "RGB"
        Comb.location = (-300, 0)

        RGBCurvesConvert = group.nodes.new("ShaderNodeRGBCurve")
        RGBCurvesConvert.label = "Convert DirectX to Blender Normal"
        RGBCurvesConvert.hide = True
        RGBCurvesConvert.location = (-100, 0)
        RGBCurvesConvert.mapping.curves[1].points[0].location = (0, 1)
        RGBCurvesConvert.mapping.curves[1].points[1].location = (1, 0)

        group.links.new(GroupInN.outputs["Image"], VMup.inputs["Vector"])
        group.links.new(VMup.outputs["Vector"], VSub.inputs["Vector"])
        group.links.new(VSub.outputs["Vector"], VDot.inputs["Vector"])
        group.links.new(
            VSub.outputs["Vector"],
            shader_nodes.socket_by_identifier(VDot.inputs, "Vector_001"),
        )
        group.links.new(
            VDot.outputs["Value"],
            shader_nodes.socket_by_identifier(Sub.inputs, "Value_001"),
        )
        group.links.new(Sub.outputs["Value"], ClampZ.inputs["Value"])
        group.links.new(ClampZ.outputs["Value"], SQR.inputs["Value"])
        group.links.new(SQR.outputs["Value"], Range.inputs["Value"])
        group.links.new(GroupInN.outputs["Image"], Sep.inputs["Color"])
        group.links.new(Sep.outputs["Red"], Comb.inputs["Red"])
        group.links.new(Sep.outputs["Green"], Comb.inputs["Green"])
        group.links.new(Range.outputs["Result"], Comb.inputs["Blue"])
        group.links.new(Comb.outputs["Color"], RGBCurvesConvert.inputs["Color"])
        group.links.new(RGBCurvesConvert.outputs["Color"], GroupOutN.inputs["Image"])

    ShaderGroup = curMat.nodes.new("ShaderNodeGroup")
    ShaderGroup.location = (x, y)
    ShaderGroup.hide = True
    ShaderGroup.node_tree = group
    ShaderGroup.name = name

    return ShaderGroup


def CreateCalculateVecNormalZ(curMat, x=0, y=0, name="Calculate Vectorized Normal Z"):
    group = bpy.data.node_groups.get("Calculate Vectorized Normal Z v2")

    if group is None:
        group = track_created_datablock(
            "node_groups",
            bpy.data.node_groups.new(
                "Calculate Vectorized Normal Z v2", "ShaderNodeTree"
            ),
        )

        GroupInN = group.nodes.new("NodeGroupInput")
        GroupInN.location = (-1400, 0)

        GroupOutN = group.nodes.new("NodeGroupOutput")
        GroupOutN.location = (300, 0)
        group.interface.new_socket(
            name="Image", socket_type="NodeSocketVector", in_out="INPUT"
        )
        group.interface.new_socket(
            name="Image", socket_type="NodeSocketColor", in_out="OUTPUT"
        )

        VDot = shader_nodes.vector_math(
            group.nodes, group.links, "DOT_PRODUCT", location=(-900, -200)
        ).node

        Sub = shader_nodes.math(
            group.nodes, group.links, "SUBTRACT", location=(-700, -200)
        ).node
        group.links.new(
            shader_nodes.socket_by_identifier(VDot.outputs, "Vector"),
            shader_nodes.socket_by_identifier(Sub.inputs, "Value_001"),
        )
        Sub.inputs["Value"].default_value = 1.0

        MaxZero = shader_nodes.math(
            group.nodes, group.links, "MAXIMUM", location=(-540, -200)
        ).node
        shader_nodes.socket_by_identifier(
            MaxZero.inputs, "Value_001"
        ).default_value = 0.0

        SQR = shader_nodes.math(
            group.nodes, group.links, "SQRT", location=(-380, -200)
        ).node

        Sep = group.nodes.new("ShaderNodeSeparateColor")
        Sep.location = (-700, 100)

        Mult = shader_nodes.math(
            group.nodes,
            group.links,
            "MULTIPLY",
            label="DirectX Y to Blender Y",
            location=(-500, 0),
        ).node
        shader_nodes.socket_by_identifier(Mult.inputs, "Value_001").default_value = -1.0

        Comb = group.nodes.new("ShaderNodeCombineColor")
        Comb.location = (-300, 100)

        MultAdd = shader_nodes.vector_math(
            group.nodes, group.links, "MULTIPLY_ADD", location=(-50, 0)
        ).node
        shader_nodes.socket_by_identifier(
            MultAdd.inputs, "Vector_001"
        ).default_value = 0.5, 0.5, 0.5
        shader_nodes.socket_by_identifier(
            MultAdd.inputs, "Vector_002"
        ).default_value = 0.5, 0.5, 0.5

        group.links.new(GroupInN.outputs["Image"], Sep.inputs["Color"])
        group.links.new(GroupInN.outputs["Image"], VDot.inputs["Vector"])
        group.links.new(
            GroupInN.outputs["Image"],
            shader_nodes.socket_by_identifier(VDot.inputs, "Vector_001"),
        )
        group.links.new(
            VDot.outputs["Value"],
            shader_nodes.socket_by_identifier(Sub.inputs, "Value_001"),
        )
        group.links.new(Sub.outputs["Value"], MaxZero.inputs["Value"])
        group.links.new(MaxZero.outputs["Value"], SQR.inputs["Value"])
        group.links.new(SQR.outputs["Value"], Comb.inputs["Blue"])
        group.links.new(Sep.outputs["Red"], Comb.inputs["Red"])
        group.links.new(Sep.outputs["Green"], Mult.inputs["Value"])
        group.links.new(Mult.outputs["Value"], Comb.inputs["Green"])
        group.links.new(Comb.outputs["Color"], MultAdd.inputs["Vector"])
        group.links.new(MultAdd.outputs["Vector"], GroupOutN.inputs["Image"])

    ShaderGroup = curMat.nodes.new("ShaderNodeGroup")
    ShaderGroup.location = (x, y)
    ShaderGroup.hide = True
    ShaderGroup.node_tree = group
    ShaderGroup.name = name

    return ShaderGroup


def CreateShaderNodeRGB(curMat, color, x=0, y=0, name=None, isVector=False):
    rgbNode = curMat.nodes.new("ShaderNodeRGB")
    rgbNode.location = (x, y)
    rgbNode.hide = True
    if name is not None:
        rgbNode.label = name

    if isVector:
        rgbNode.outputs["Color"].default_value = (
            float(color["X"]),
            float(color["Y"]),
            float(color["Z"]),
            float(color["W"]),
        )
    else:
        rgbNode.outputs["Color"].default_value = (
            float(color["Red"]) / 255,
            float(color["Green"]) / 255,
            float(color["Blue"]) / 255,
            float(color["Alpha"]) / 255,
        )

    return rgbNode


def CreateShaderNodeValue(curMat, value=0, x=0, y=0, name=None):
    valNode = curMat.nodes.new("ShaderNodeValue")
    valNode.location = (x, y)
    valNode.outputs["Value"].default_value = float(value)
    valNode.hide = True
    if name:
        valNode.label = name

    return valNode


def configure_tangent_normal_map(node, *, uv_map="UVMap"):
    node.space = "TANGENT"
    node.uv_map = uv_map
    return node


def create_node(
    NG, type, loc, hide=True, operation=None, image=None, label=None, blend_type=None
):
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
    # The colour a layer takes when it first uses the template, one of the template's own colours.
    defaults = matTemplateObj.get(
        "defaultOverrides", matTemplateObj.get("DefaultOverrides")
    )
    default_color = defaults.get("colorScale") if isinstance(defaults, dict) else None
    Output["DefaultColorScale"] = (
        default_color.get("$value") if isinstance(default_color, dict) else None
    )
    return Output


def CreateGradMapRamp(CurMat, grad_image_node, location=(-400, 250)):
    image = grad_image_node.image
    image_width = image.size[0]
    row_index = 0
    all_pixels = np.empty(len(image.pixels), dtype=np.float32)
    image.pixels.foreach_get(all_pixels)

    color_ramp_node = CurMat.nodes.new("ShaderNodeValToRGB")
    color_ramp_node.location = location

    step = math.ceil(image_width / 32) if image_width > 32 else 1
    color_ramp_node.color_ramp.elements.remove(color_ramp_node.color_ramp.elements[1])

    first = True
    for i in range(0, image_width, step):
        idx = (row_index * image_width + i) * 4
        r, g, b, a = all_pixels[idx : idx + 4]
        element = (
            color_ramp_node.color_ramp.elements[0]
            if first
            else color_ramp_node.color_ramp.elements.new(i / image_width)
        )
        element.color = (r, g, b, a)
        element.position = i / image_width
        first = False

    color_ramp_node.color_ramp.interpolation = "CONSTANT"
    return color_ramp_node


def createLerpGroup():
    CurMat = bpy.data.node_groups.get("lerp v2")
    if CurMat:
        return CurMat
    CurMat = track_created_datablock(
        "node_groups", bpy.data.node_groups.new("lerp v2", "ShaderNodeTree")
    )
    CurMat.interface.new_socket(name="A", socket_type="NodeSocketFloat", in_out="INPUT")
    CurMat.interface.new_socket(name="B", socket_type="NodeSocketFloat", in_out="INPUT")
    CurMat.interface.new_socket(name="t", socket_type="NodeSocketFloat", in_out="INPUT")
    CurMat.interface.new_socket(
        name="result", socket_type="NodeSocketFloat", in_out="OUTPUT"
    )
    GroupInput = create_node(
        CurMat.nodes, "NodeGroupInput", (0, 0), label="Group Input"
    )
    GroupOutput = create_node(
        CurMat.nodes, "NodeGroupOutput", (700, 0), label="Group Output"
    )
    result = shader_nodes.lerp(
        CurMat.nodes,
        CurMat.links,
        GroupInput.outputs["A"],
        GroupInput.outputs["B"],
        GroupInput.outputs["t"],
        name="Lerp",
        location=(250, 0),
    )
    CurMat.links.new(result, GroupOutput.inputs["result"])
    return CurMat


def createVecLerpGroup():
    CurMat = bpy.data.node_groups.get("vecLerp v2")
    if CurMat:
        return CurMat
    CurMat = track_created_datablock(
        "node_groups", bpy.data.node_groups.new("vecLerp v2", "ShaderNodeTree")
    )
    CurMat.interface.new_socket(
        name="A", socket_type="NodeSocketVector", in_out="INPUT"
    )
    CurMat.interface.new_socket(
        name="B", socket_type="NodeSocketVector", in_out="INPUT"
    )
    CurMat.interface.new_socket(
        name="t", socket_type="NodeSocketVector", in_out="INPUT"
    )
    CurMat.interface.new_socket(
        name="result", socket_type="NodeSocketVector", in_out="OUTPUT"
    )
    GroupInput = create_node(
        CurMat.nodes, "NodeGroupInput", (0, 0), label="Group Input"
    )
    GroupOutput = create_node(
        CurMat.nodes, "NodeGroupOutput", (700, 0), label="Group Output"
    )
    result = shader_nodes.vector_lerp(
        CurMat.nodes,
        CurMat.links,
        GroupInput.outputs["A"],
        GroupInput.outputs["B"],
        GroupInput.outputs["t"],
        name="Lerp",
        location=(250, 0),
    )
    CurMat.links.new(result, GroupOutput.inputs["result"])
    return CurMat


def createHash12Group():
    from ...material_types.shader_hash import HASH_OFFSET

    CurMat = bpy.data.node_groups.get("hash12")
    if CurMat:
        return CurMat
    else:
        CurMat = track_created_datablock(
            "node_groups", bpy.data.node_groups.new("hash12", "ShaderNodeTree")
        )
        CurMat.interface.new_socket(
            name="vector", socket_type="NodeSocketVector", in_out="INPUT"
        )
        CurMat.interface.new_socket(
            name="result", socket_type="NodeSocketFloat", in_out="OUTPUT"
        )
        GroupInput = create_node(
            CurMat.nodes, "NodeGroupInput", (-500, 0), label="Group Input"
        )
        GroupOutput = create_node(
            CurMat.nodes, "NodeGroupOutput", (1350, 0), label="Group Output"
        )
        separate = create_node(CurMat.nodes, "ShaderNodeSeparateXYZ", (-350, 0))
        combine = create_node(CurMat.nodes, "ShaderNodeCombineXYZ", (-200, 0))
        combine2 = create_node(CurMat.nodes, "ShaderNodeCombineXYZ", (-200, -50))
        vecMul = shader_nodes.vector_math(
            CurMat.nodes, CurMat.links, "MULTIPLY", location=(0, 0), hide=True
        ).node
        frac = shader_nodes.vector_math(
            CurMat.nodes, CurMat.links, "FRACTION", location=(150, 0), hide=True
        ).node
        shader_nodes.socket_by_identifier(vecMul.inputs, "Vector_001").default_value = (
            0.1031,
            0.1031,
            0.1031,
        )
        dot = shader_nodes.vector_math(
            CurMat.nodes, CurMat.links, "DOT_PRODUCT", location=(300, -50), hide=True
        ).node
        vecAdd = shader_nodes.vector_math(
            CurMat.nodes, CurMat.links, "ADD", location=(0, -50), hide=True
        ).node
        vecAdd2 = shader_nodes.vector_math(
            CurMat.nodes, CurMat.links, "ADD", location=(600, 0), hide=True
        ).node
        combine3 = create_node(CurMat.nodes, "ShaderNodeCombineXYZ", (450, -50))
        separate2 = create_node(CurMat.nodes, "ShaderNodeSeparateXYZ", (750, 0))
        add = shader_nodes.math(
            CurMat.nodes, CurMat.links, "ADD", location=(900, 0), hide=True
        ).node
        mul = shader_nodes.math(
            CurMat.nodes, CurMat.links, "MULTIPLY", location=(1050, 0), hide=True
        ).node
        frac2 = shader_nodes.math(
            CurMat.nodes, CurMat.links, "FRACT", location=(1200, 0), hide=True
        ).node
        CurMat.links.new(GroupInput.outputs["vector"], separate.inputs["Vector"])
        CurMat.links.new(separate.outputs["X"], combine.inputs["X"])
        CurMat.links.new(separate.outputs["Y"], combine.inputs["Y"])
        CurMat.links.new(separate.outputs["X"], combine.inputs["Z"])
        CurMat.links.new(combine.outputs["Vector"], vecMul.inputs["Vector"])
        CurMat.links.new(vecMul.outputs["Vector"], frac.inputs["Vector"])
        CurMat.links.new(separate.outputs["Y"], combine2.inputs["X"])
        CurMat.links.new(separate.outputs["Z"], combine2.inputs["Y"])
        CurMat.links.new(separate.outputs["X"], combine2.inputs["Z"])
        CurMat.links.new(combine2.outputs["Vector"], vecAdd.inputs["Vector"])
        shader_nodes.socket_by_identifier(vecAdd.inputs, "Vector_001").default_value = (
            HASH_OFFSET,
        ) * 3
        CurMat.links.new(frac.outputs["Vector"], dot.inputs["Vector"])
        CurMat.links.new(
            vecAdd.outputs["Vector"],
            shader_nodes.socket_by_identifier(dot.inputs, "Vector_001"),
        )
        CurMat.links.new(dot.outputs["Value"], combine3.inputs["X"])
        CurMat.links.new(dot.outputs["Value"], combine3.inputs["Y"])
        CurMat.links.new(dot.outputs["Value"], combine3.inputs["Z"])
        CurMat.links.new(frac.outputs["Vector"], vecAdd2.inputs["Vector"])
        CurMat.links.new(
            combine3.outputs["Vector"],
            shader_nodes.socket_by_identifier(vecAdd2.inputs, "Vector_001"),
        )
        CurMat.links.new(vecAdd2.outputs["Vector"], separate2.inputs["Vector"])
        CurMat.links.new(separate2.outputs["X"], add.inputs["Value"])
        CurMat.links.new(
            separate2.outputs["Y"],
            shader_nodes.socket_by_identifier(add.inputs, "Value_001"),
        )
        CurMat.links.new(add.outputs["Value"], mul.inputs["Value"])
        CurMat.links.new(
            separate2.outputs["Z"],
            shader_nodes.socket_by_identifier(mul.inputs, "Value_001"),
        )
        CurMat.links.new(mul.outputs["Value"], frac2.inputs["Value"])
        CurMat.links.new(frac2.outputs["Value"], GroupOutput.inputs["result"])
        return CurMat
