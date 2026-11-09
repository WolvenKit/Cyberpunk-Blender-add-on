import bpy

from ..blender import shader_nodes
from ..blender.transactions import new_tracked_datablock
from ..materials.blender.images import imageFromRelPath
from ..materials.blender.nodes import (
    bsdf_socket_names,
    create_node,
    createHash12Group,
    createLerpGroup,
    createVecLerpGroup,
)
from .mat_common import (
    MaterialTypeBase,
    create_param_value_nodes,
    create_scene_time_value,
)

_PARAM_SPECS = (
    ("TilesWidth", "TilesWidth", 400, "TilesWidth", 1.0),
    ("TilesHeight", "TilesHeight", 350, "TilesHeight", 1.0),
    ("PlaySpeed", "PlaySpeed", 300, "PlaySpeed", 1.0),
    ("InterlaceLines", "InterlaceLines", 250, "InterlaceLines", 1.0),
    ("PixelsHeight", "PixelsHeight", 200, "PixelsHeight", 1.0),
    ("BlackLinesRatio", "BlackLinesRatio", 150, "BlackLinesRatio", 1.0),
    ("BlackLinesIntensity", "BlackLinesIntensity", 100, "BlackLinesIntensity", 1.0),
    ("BlackLinesSize", "BlackLinesSize", 50, "BlackLinesSize", 1.0),
    ("LinesOrDots", "LinesOrDots", 0, "LinesOrDots", 0.0),
    ("Metalness", "Metalness", -100, "Metalness", 0.0),
    ("Roughness", "Roughness", -150, "Roughness", 0.5),
    ("IsBroken", "IsBroken", -200, "IsBroken", 0.0),
    ("AlphaThreshold", "AlphaThreshold", -300, "AlphaThreshold", 0.0),
    ("EmissiveEV", "EmissiveEV", -400, "EmissiveEV", 1.0),
    ("HUEChangeSpeed", "HUEChangeSpeed", -550, "HUEChangeSpeed", 0.0),
    ("DirtOpacityScale", "DirtOpacityScale", -600, "DirtOpacityScale", 0.0),
    ("DirtRoughness", "DirtRoughness", -650, "DirtRoughness", 0.5),
    ("DirtUvScaleU", "DirtUvScaleU", -700, "DirtUvScaleU", 1.0),
    ("DirtUvScaleV", "DirtUvScaleV", -750, "DirtUvScaleV", 1.0),
)


def get_or_create_n_group():

    ngroup = bpy.data.node_groups.get("CP77 Television Ad n v1")

    if ngroup is None:
        ngroup = new_tracked_datablock(
            "node_groups", "CP77 Television Ad n v1", "ShaderNodeTree"
        )
        ngroup.interface.new_socket(
            name="TilesWidth", socket_type="NodeSocketFloat", in_out="INPUT"
        )
        ngroup.interface.new_socket(
            name="TilesHeight", socket_type="NodeSocketFloat", in_out="INPUT"
        )
        ngroup.interface.new_socket(
            name="PlaySpeed", socket_type="NodeSocketFloat", in_out="INPUT"
        )
        ngroup.interface.new_socket(
            name="Time", socket_type="NodeSocketFloat", in_out="INPUT"
        )
        ngroup.interface.new_socket(
            name="n", socket_type="NodeSocketFloat", in_out="OUTPUT"
        )

        GroupInput = create_node(ngroup.nodes, "NodeGroupInput", (-1400, 0))
        GroupOutput = create_node(ngroup.nodes, "NodeGroupOutput", (200, 0))
        mul = shader_nodes.math(
            ngroup.nodes, ngroup.links, "MULTIPLY", location=(-1000, 0), hide=True
        ).node
        div = shader_nodes.math(
            ngroup.nodes, ngroup.links, "DIVIDE", location=(-850, 0), hide=True
        ).node
        mul1 = shader_nodes.math(
            ngroup.nodes, ngroup.links, "MULTIPLY", location=(-700, 0), hide=True
        ).node
        frac = shader_nodes.math(
            ngroup.nodes, ngroup.links, "FRACT", location=(-550, 0), hide=True
        ).node
        mul2 = shader_nodes.math(
            ngroup.nodes, ngroup.links, "MULTIPLY", location=(-400, 0), hide=True
        ).node
        mul3 = shader_nodes.math(
            ngroup.nodes, ngroup.links, "MULTIPLY", location=(-250, 0), hide=True
        ).node

        ngroup.links.new(GroupInput.outputs["TilesWidth"], mul.inputs["Value"])
        ngroup.links.new(
            GroupInput.outputs["TilesHeight"],
            shader_nodes.socket_by_identifier(mul.inputs, "Value_001"),
        )
        ngroup.links.new(GroupInput.outputs["PlaySpeed"], div.inputs["Value"])
        ngroup.links.new(
            mul.outputs["Value"],
            shader_nodes.socket_by_identifier(div.inputs, "Value_001"),
        )
        ngroup.links.new(GroupInput.outputs["Time"], mul1.inputs["Value"])
        ngroup.links.new(
            div.outputs["Value"],
            shader_nodes.socket_by_identifier(mul1.inputs, "Value_001"),
        )
        ngroup.links.new(mul1.outputs["Value"], frac.inputs["Value"])
        ngroup.links.new(frac.outputs["Value"], mul2.inputs["Value"])
        ngroup.links.new(
            GroupInput.outputs["TilesWidth"],
            shader_nodes.socket_by_identifier(mul2.inputs, "Value_001"),
        )
        ngroup.links.new(mul2.outputs["Value"], mul3.inputs["Value"])
        ngroup.links.new(
            GroupInput.outputs["TilesHeight"],
            shader_nodes.socket_by_identifier(mul3.inputs, "Value_001"),
        )
        ngroup.links.new(mul3.outputs["Value"], GroupOutput.inputs["n"])

    return ngroup


def get_or_create_frame_add_group():

    frameGroup = bpy.data.node_groups.get("CP77 Television Ad frameAdd v1")

    if frameGroup is None:
        frameGroup = new_tracked_datablock(
            "node_groups", "CP77 Television Ad frameAdd v1", "ShaderNodeTree"
        )
        frameGroup.interface.new_socket(
            name="PixelsHeight", socket_type="NodeSocketFloat", in_out="INPUT"
        )
        frameGroup.interface.new_socket(
            name="InterlaceLines", socket_type="NodeSocketFloat", in_out="INPUT"
        )
        frameGroup.interface.new_socket(
            name="UV", socket_type="NodeSocketVector", in_out="INPUT"
        )
        frameGroup.interface.new_socket(
            name="n", socket_type="NodeSocketFloat", in_out="INPUT"
        )
        frameGroup.interface.new_socket(
            name="frameAdd", socket_type="NodeSocketFloat", in_out="OUTPUT"
        )

        fGroupInput = create_node(frameGroup.nodes, "NodeGroupInput", (-1400, 0))
        fGroupOutput = create_node(frameGroup.nodes, "NodeGroupOutput", (200, 0))

        UVSeparate = create_node(
            frameGroup.nodes, "ShaderNodeSeparateXYZ", (-1300, 100)
        )
        mul4 = shader_nodes.math(
            frameGroup.nodes,
            frameGroup.links,
            "MULTIPLY",
            location=(-1100, 100),
            hide=True,
        ).node
        mul5 = shader_nodes.math(
            frameGroup.nodes,
            frameGroup.links,
            "MULTIPLY",
            location=(-1100, 150),
            hide=True,
        ).node
        div2 = shader_nodes.math(
            frameGroup.nodes,
            frameGroup.links,
            "DIVIDE",
            location=(-900, 125),
            hide=True,
        ).node
        mod = shader_nodes.math(
            frameGroup.nodes,
            frameGroup.links,
            "MODULO",
            location=(-750, 125),
            hide=True,
        ).node
        add = shader_nodes.math(
            frameGroup.nodes, frameGroup.links, "ADD", location=(-600, 125), hide=True
        ).node
        mod2 = shader_nodes.math(
            frameGroup.nodes, frameGroup.links, "MODULO", location=(-900, 75), hide=True
        ).node
        add2 = shader_nodes.math(
            frameGroup.nodes, frameGroup.links, "ADD", location=(-750, 75), hide=True
        ).node
        floor = shader_nodes.math(
            frameGroup.nodes, frameGroup.links, "FLOOR", location=(-600, 75), hide=True
        ).node
        add3 = shader_nodes.math(
            frameGroup.nodes, frameGroup.links, "ADD", location=(-450, 125), hide=True
        ).node
        floor2 = shader_nodes.math(
            frameGroup.nodes, frameGroup.links, "FLOOR", location=(-300, 125), hide=True
        ).node
        clamp = create_node(frameGroup.nodes, "ShaderNodeClamp", (-300, 75))
        frameGroup.links.new(
            fGroupInput.outputs["InterlaceLines"], mul4.inputs["Value"]
        )
        shader_nodes.socket_by_identifier(mul4.inputs, "Value_001").default_value = 8
        frameGroup.links.new(fGroupInput.outputs["UV"], UVSeparate.inputs["Vector"])
        frameGroup.links.new(UVSeparate.outputs["Y"], mul5.inputs["Value"])
        frameGroup.links.new(
            fGroupInput.outputs["PixelsHeight"],
            shader_nodes.socket_by_identifier(mul5.inputs, "Value_001"),
        )
        frameGroup.links.new(mul5.outputs["Value"], div2.inputs["Value"])
        frameGroup.links.new(
            mul4.outputs["Value"],
            shader_nodes.socket_by_identifier(div2.inputs, "Value_001"),
        )
        frameGroup.links.new(div2.outputs["Value"], mod.inputs["Value"])
        shader_nodes.socket_by_identifier(mod.inputs, "Value_001").default_value = 1
        frameGroup.links.new(mod.outputs["Value"], add.inputs["Value"])
        shader_nodes.socket_by_identifier(add.inputs, "Value_001").default_value = 0.5
        frameGroup.links.new(fGroupInput.outputs["n"], mod2.inputs["Value"])
        shader_nodes.socket_by_identifier(mod2.inputs, "Value_001").default_value = 1
        frameGroup.links.new(mod2.outputs["Value"], add2.inputs["Value"])
        shader_nodes.socket_by_identifier(add2.inputs, "Value_001").default_value = 0.5
        frameGroup.links.new(add2.outputs["Value"], floor.inputs["Value"])
        frameGroup.links.new(add.outputs["Value"], add3.inputs["Value"])
        frameGroup.links.new(
            floor.outputs["Value"],
            shader_nodes.socket_by_identifier(add3.inputs, "Value_001"),
        )
        frameGroup.links.new(add3.outputs["Value"], floor2.inputs["Value"])
        frameGroup.links.new(floor2.outputs["Value"], clamp.inputs["Value"])
        frameGroup.links.new(clamp.outputs["Result"], fGroupOutput.inputs["frameAdd"])

    return frameGroup


def get_or_create_sub_uv_group():

    subUVGroup = bpy.data.node_groups.get("CP77 Television Ad subUV v1")

    if subUVGroup is None:
        subUVGroup = new_tracked_datablock(
            "node_groups", "CP77 Television Ad subUV v1", "ShaderNodeTree"
        )
        subUVGroup.interface.new_socket(
            name="TilesWidth", socket_type="NodeSocketFloat", in_out="INPUT"
        )
        subUVGroup.interface.new_socket(
            name="TilesHeight", socket_type="NodeSocketFloat", in_out="INPUT"
        )
        subUVGroup.interface.new_socket(
            name="n", socket_type="NodeSocketFloat", in_out="INPUT"
        )
        subUVGroup.interface.new_socket(
            name="frameAdd", socket_type="NodeSocketFloat", in_out="INPUT"
        )
        subUVGroup.interface.new_socket(
            name="UV", socket_type="NodeSocketVector", in_out="INPUT"
        )
        subUVGroup.interface.new_socket(
            name="subUV", socket_type="NodeSocketVector", in_out="OUTPUT"
        )

        subUVGroupI = create_node(subUVGroup.nodes, "NodeGroupInput", (-1400, 0))
        subUVGroupO = create_node(subUVGroup.nodes, "NodeGroupOutput", (200, 0))

        UVSeparate = create_node(
            subUVGroup.nodes, "ShaderNodeSeparateXYZ", (-1300, 100)
        )
        div3 = shader_nodes.math(
            subUVGroup.nodes, subUVGroup.links, "DIVIDE", location=(-900, 0), hide=True
        ).node
        sub = shader_nodes.math(
            subUVGroup.nodes,
            subUVGroup.links,
            "SUBTRACT",
            location=(-1100, -50),
            hide=True,
        ).node
        div4 = shader_nodes.math(
            subUVGroup.nodes,
            subUVGroup.links,
            "DIVIDE",
            location=(-900, -50),
            hide=True,
        ).node
        add4 = shader_nodes.math(
            subUVGroup.nodes, subUVGroup.links, "ADD", location=(-800, -100), hide=True
        ).node
        mod3 = shader_nodes.math(
            subUVGroup.nodes,
            subUVGroup.links,
            "MODULO",
            location=(-900, -150),
            hide=True,
        ).node
        floor3 = shader_nodes.math(
            subUVGroup.nodes,
            subUVGroup.links,
            "FLOOR",
            location=(-750, -150),
            hide=True,
        ).node
        div5 = shader_nodes.math(
            subUVGroup.nodes,
            subUVGroup.links,
            "DIVIDE",
            location=(-500, -150),
            hide=True,
        ).node
        div6 = shader_nodes.math(
            subUVGroup.nodes,
            subUVGroup.links,
            "DIVIDE",
            location=(-900, -200),
            hide=True,
        ).node
        mod4 = shader_nodes.math(
            subUVGroup.nodes,
            subUVGroup.links,
            "MODULO",
            location=(-750, -200),
            hide=True,
        ).node
        floor4 = shader_nodes.math(
            subUVGroup.nodes,
            subUVGroup.links,
            "FLOOR",
            location=(-600, -200),
            hide=True,
        ).node
        div7 = shader_nodes.math(
            subUVGroup.nodes,
            subUVGroup.links,
            "DIVIDE",
            location=(-450, -200),
            hide=True,
        ).node
        add5 = shader_nodes.math(
            subUVGroup.nodes, subUVGroup.links, "ADD", location=(-500, -250), hide=True
        ).node
        add6 = shader_nodes.math(
            subUVGroup.nodes, subUVGroup.links, "ADD", location=(-750, -250), hide=True
        ).node
        sub2 = shader_nodes.math(
            subUVGroup.nodes,
            subUVGroup.links,
            "SUBTRACT",
            location=(-500, -150),
            hide=True,
        ).node
        frac4 = shader_nodes.math(
            subUVGroup.nodes,
            subUVGroup.links,
            "FRACT",
            location=(-350, -250),
            hide=True,
        ).node
        frac5 = shader_nodes.math(
            subUVGroup.nodes,
            subUVGroup.links,
            "FRACT",
            location=(-350, -150),
            hide=True,
        ).node
        combine = create_node(
            subUVGroup.nodes, "ShaderNodeCombineXYZ", (-200, -200), label="newUV"
        )
        subUVGroup.links.new(subUVGroupI.outputs["UV"], UVSeparate.inputs["Vector"])
        subUVGroup.links.new(UVSeparate.outputs["X"], div3.inputs["Value"])
        subUVGroup.links.new(
            subUVGroupI.outputs["TilesWidth"],
            shader_nodes.socket_by_identifier(div3.inputs, "Value_001"),
        )
        sub.inputs["Value"].default_value = 1.0
        subUVGroup.links.new(
            UVSeparate.outputs["Y"],
            shader_nodes.socket_by_identifier(sub.inputs, "Value_001"),
        )
        subUVGroup.links.new(sub.outputs["Value"], div4.inputs["Value"])
        subUVGroup.links.new(
            subUVGroupI.outputs["TilesHeight"],
            shader_nodes.socket_by_identifier(div4.inputs, "Value_001"),
        )
        subUVGroup.links.new(subUVGroupI.outputs["n"], add4.inputs["Value"])
        subUVGroup.links.new(
            subUVGroupI.outputs["frameAdd"],
            shader_nodes.socket_by_identifier(add4.inputs, "Value_001"),
        )
        subUVGroup.links.new(add4.outputs["Value"], mod3.inputs["Value"])
        subUVGroup.links.new(
            subUVGroupI.outputs["TilesWidth"],
            shader_nodes.socket_by_identifier(mod3.inputs, "Value_001"),
        )
        subUVGroup.links.new(mod3.outputs["Value"], floor3.inputs["Value"])
        subUVGroup.links.new(floor3.outputs["Value"], div5.inputs["Value"])
        subUVGroup.links.new(
            subUVGroupI.outputs["TilesWidth"],
            shader_nodes.socket_by_identifier(div5.inputs, "Value_001"),
        )
        subUVGroup.links.new(add4.outputs["Value"], div6.inputs["Value"])
        subUVGroup.links.new(
            subUVGroupI.outputs["TilesWidth"],
            shader_nodes.socket_by_identifier(div6.inputs, "Value_001"),
        )
        subUVGroup.links.new(div6.outputs["Value"], mod4.inputs["Value"])
        subUVGroup.links.new(
            subUVGroupI.outputs["TilesHeight"],
            shader_nodes.socket_by_identifier(mod4.inputs, "Value_001"),
        )
        subUVGroup.links.new(mod4.outputs["Value"], floor4.inputs["Value"])
        subUVGroup.links.new(floor4.outputs["Value"], div7.inputs["Value"])
        subUVGroup.links.new(
            subUVGroupI.outputs["TilesHeight"],
            shader_nodes.socket_by_identifier(div7.inputs, "Value_001"),
        )
        subUVGroup.links.new(div3.outputs["Value"], add5.inputs["Value"])
        subUVGroup.links.new(
            div5.outputs["Value"],
            shader_nodes.socket_by_identifier(add5.inputs, "Value_001"),
        )
        subUVGroup.links.new(div4.outputs["Value"], add6.inputs["Value"])
        subUVGroup.links.new(
            div7.outputs["Value"],
            shader_nodes.socket_by_identifier(add6.inputs, "Value_001"),
        )
        subUVGroup.links.new(add5.outputs["Value"], frac4.inputs["Value"])
        subUVGroup.links.new(frac4.outputs["Value"], combine.inputs["X"])
        sub2.inputs["Value"].default_value = 1.0
        subUVGroup.links.new(
            add6.outputs["Value"],
            shader_nodes.socket_by_identifier(sub2.inputs, "Value_001"),
        )
        subUVGroup.links.new(sub2.outputs["Value"], frac5.inputs["Value"])
        subUVGroup.links.new(frac5.outputs["Value"], combine.inputs["Y"])
        subUVGroup.links.new(combine.outputs["Vector"], subUVGroupO.inputs["subUV"])

    return subUVGroup


def get_or_create_broken_uv_group():

    brokenUVGroup = bpy.data.node_groups.get("CP77 Television Ad brokenUV v1")

    if brokenUVGroup is None:
        brokenUVGroup = new_tracked_datablock(
            "node_groups", "CP77 Television Ad brokenUV v1", "ShaderNodeTree"
        )
        brokenUVGroup.interface.new_socket(
            name="rndBlocks", socket_type="NodeSocketFloat", in_out="INPUT"
        )
        brokenUVGroup.interface.new_socket(
            name="Time", socket_type="NodeSocketFloat", in_out="INPUT"
        )
        brokenUVGroup.interface.new_socket(
            name="UV", socket_type="NodeSocketVector", in_out="INPUT"
        )
        brokenUVGroup.interface.new_socket(
            name="brokenUV", socket_type="NodeSocketVector", in_out="OUTPUT"
        )

        brokenUVGroupI = create_node(brokenUVGroup.nodes, "NodeGroupInput", (-1400, 0))
        brokenUVGroupO = create_node(brokenUVGroup.nodes, "NodeGroupOutput", (200, 0))
        hash12G = createHash12Group()
        hash12 = create_node(
            brokenUVGroup.nodes, "ShaderNodeGroup", (-650, -50), label="hash12"
        )
        hash12.node_tree = hash12G
        add8 = shader_nodes.math(
            brokenUVGroup.nodes,
            brokenUVGroup.links,
            "ADD",
            location=(-1250, 0),
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(
            add8.inputs, "Value_001"
        ).default_value = 0.35748
        mul6 = shader_nodes.math(
            brokenUVGroup.nodes,
            brokenUVGroup.links,
            "MULTIPLY",
            location=(-1100, 0),
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(mul6.inputs, "Value_001").default_value = 150
        floor5 = shader_nodes.math(
            brokenUVGroup.nodes,
            brokenUVGroup.links,
            "FLOOR",
            location=(-800, -50),
            hide=True,
        ).node
        separate = create_node(brokenUVGroup.nodes, "ShaderNodeSeparateXYZ", (-800, 0))
        combine2 = create_node(brokenUVGroup.nodes, "ShaderNodeCombineXYZ", (-650, 0))
        vecAdd = shader_nodes.vector_math(
            brokenUVGroup.nodes,
            brokenUVGroup.links,
            "ADD",
            location=(-350, 0),
            hide=True,
        ).node
        vecFrac = shader_nodes.vector_math(
            brokenUVGroup.nodes,
            brokenUVGroup.links,
            "FRACTION",
            location=(-200, 0),
            hide=True,
        ).node
        mul7 = shader_nodes.math(
            brokenUVGroup.nodes,
            brokenUVGroup.links,
            "MULTIPLY",
            location=(-1250, -100),
            hide=True,
        ).node
        floor6 = shader_nodes.math(
            brokenUVGroup.nodes,
            brokenUVGroup.links,
            "FLOOR",
            location=(-1100, -100),
            hide=True,
        ).node
        div8 = shader_nodes.math(
            brokenUVGroup.nodes,
            brokenUVGroup.links,
            "DIVIDE",
            location=(-950, -100),
            hide=True,
        ).node
        add9 = shader_nodes.math(
            brokenUVGroup.nodes,
            brokenUVGroup.links,
            "ADD",
            location=(-800, -100),
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(add9.inputs, "Value_001").default_value = 1
        mul8 = shader_nodes.math(
            brokenUVGroup.nodes,
            brokenUVGroup.links,
            "MULTIPLY",
            location=(-650, -100),
            hide=True,
        ).node
        frac3 = shader_nodes.math(
            brokenUVGroup.nodes,
            brokenUVGroup.links,
            "FRACT",
            location=(-500, -100),
            hide=True,
        ).node
        clamp2 = create_node(brokenUVGroup.nodes, "ShaderNodeClamp", (-350, -100))
        lerp2 = create_node(
            brokenUVGroup.nodes, "ShaderNodeGroup", (-200, -100), label="lerp"
        )
        lerp2.node_tree = createLerpGroup()
        lerp2.inputs["A"].default_value = 1
        lerp2.inputs["B"].default_value = 4
        vecDiv = shader_nodes.vector_math(
            brokenUVGroup.nodes,
            brokenUVGroup.links,
            "DIVIDE",
            location=(-50, 0),
            hide=True,
        ).node

        brokenUVGroup.links.new(brokenUVGroupI.outputs["Time"], add8.inputs["Value"])
        brokenUVGroup.links.new(add8.outputs["Value"], mul6.inputs["Value"])
        brokenUVGroup.links.new(mul6.outputs["Value"], floor5.inputs["Value"])
        brokenUVGroup.links.new(floor5.outputs["Value"], hash12.inputs["vector"])
        brokenUVGroup.links.new(brokenUVGroupI.outputs["UV"], separate.inputs["Vector"])
        brokenUVGroup.links.new(separate.outputs["X"], combine2.inputs["X"])
        brokenUVGroup.links.new(separate.outputs["X"], combine2.inputs["Y"])
        brokenUVGroup.links.new(combine2.outputs["Vector"], vecAdd.inputs["Vector"])
        brokenUVGroup.links.new(
            hash12.outputs["result"],
            shader_nodes.socket_by_identifier(vecAdd.inputs, "Vector_001"),
        )
        brokenUVGroup.links.new(vecAdd.outputs["Vector"], vecFrac.inputs["Vector"])
        brokenUVGroup.links.new(separate.outputs["X"], mul7.inputs["Value"])
        brokenUVGroup.links.new(
            brokenUVGroupI.outputs["rndBlocks"],
            shader_nodes.socket_by_identifier(mul7.inputs, "Value_001"),
        )
        brokenUVGroup.links.new(mul7.outputs["Value"], floor6.inputs["Value"])
        brokenUVGroup.links.new(floor6.outputs["Value"], div8.inputs["Value"])
        brokenUVGroup.links.new(
            brokenUVGroupI.outputs["rndBlocks"],
            shader_nodes.socket_by_identifier(div8.inputs, "Value_001"),
        )
        brokenUVGroup.links.new(div8.outputs["Value"], add9.inputs["Value"])
        brokenUVGroup.links.new(add9.outputs["Value"], mul8.inputs["Value"])
        brokenUVGroup.links.new(
            brokenUVGroupI.outputs["Time"],
            shader_nodes.socket_by_identifier(mul8.inputs, "Value_001"),
        )
        brokenUVGroup.links.new(mul8.outputs["Value"], frac3.inputs["Value"])
        brokenUVGroup.links.new(frac3.outputs["Value"], clamp2.inputs["Value"])
        brokenUVGroup.links.new(clamp2.outputs["Result"], lerp2.inputs["t"])
        brokenUVGroup.links.new(vecFrac.outputs["Vector"], vecDiv.inputs["Vector"])
        brokenUVGroup.links.new(
            lerp2.outputs["result"],
            shader_nodes.socket_by_identifier(vecDiv.inputs, "Vector_001"),
        )
        brokenUVGroup.links.new(
            vecDiv.outputs["Vector"], brokenUVGroupO.inputs["brokenUV"]
        )

    return brokenUVGroup


def get_or_create_rnd_color_index_group():

    rndColorIGroup = bpy.data.node_groups.get("CP77 Television Ad rndColorIndex v1")

    if rndColorIGroup is None:
        rndColorIGroup = new_tracked_datablock(
            "node_groups", "CP77 Television Ad rndColorIndex v1", "ShaderNodeTree"
        )
        rndColorIGroup.interface.new_socket(
            name="rndBlocks", socket_type="NodeSocketFloat", in_out="INPUT"
        )
        rndColorIGroup.interface.new_socket(
            name="Time", socket_type="NodeSocketFloat", in_out="INPUT"
        )
        rndColorIGroup.interface.new_socket(
            name="UV", socket_type="NodeSocketVector", in_out="INPUT"
        )
        rndColorIGroup.interface.new_socket(
            name="rndColorIndex", socket_type="NodeSocketFloat", in_out="OUTPUT"
        )

        rndColorIGroupI = create_node(
            rndColorIGroup.nodes, "NodeGroupInput", (-1400, 0)
        )
        rndColorIGroupO = create_node(rndColorIGroup.nodes, "NodeGroupOutput", (400, 0))
        separate2 = create_node(
            rndColorIGroup.nodes, "ShaderNodeSeparateXYZ", (-1250, 0)
        )
        combine3 = create_node(rndColorIGroup.nodes, "ShaderNodeCombineXYZ", (-1100, 0))
        vecMul = shader_nodes.vector_math(
            rndColorIGroup.nodes,
            rndColorIGroup.links,
            "MULTIPLY",
            location=(-950, 0),
            hide=True,
        ).node
        vecFloor = shader_nodes.vector_math(
            rndColorIGroup.nodes,
            rndColorIGroup.links,
            "FLOOR",
            location=(-800, 0),
            hide=True,
        ).node
        vecDiv2 = shader_nodes.vector_math(
            rndColorIGroup.nodes,
            rndColorIGroup.links,
            "DIVIDE",
            location=(-650, 0),
            hide=True,
        ).node
        frac6 = shader_nodes.math(
            rndColorIGroup.nodes,
            rndColorIGroup.links,
            "FRACT",
            location=(-500, -50),
            hide=True,
        ).node
        vecMul2 = shader_nodes.vector_math(
            rndColorIGroup.nodes,
            rndColorIGroup.links,
            "MULTIPLY",
            location=(-350, -25),
            hide=True,
        ).node
        vecSub = shader_nodes.vector_math(
            rndColorIGroup.nodes,
            rndColorIGroup.links,
            "SUBTRACT",
            location=(-200, -25),
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(vecSub.inputs, "Vector_001").default_value = (
            0.1625,
            0.1625,
            0.1625,
        )
        hash12G = createHash12Group()
        hash12_2 = create_node(
            rndColorIGroup.nodes, "ShaderNodeGroup", (-50, -25), label="hash12"
        )
        hash12_2.node_tree = hash12G
        mul9 = shader_nodes.math(
            rndColorIGroup.nodes,
            rndColorIGroup.links,
            "MULTIPLY",
            location=(100, -25),
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(mul9.inputs, "Value_001").default_value = 4
        palette_index = shader_nodes.math(
            rndColorIGroup.nodes,
            rndColorIGroup.links,
            "FLOOR",
            location=(250, -25),
            hide=True,
        ).node
        rndColorIGroup.links.new(
            rndColorIGroupI.outputs["UV"], separate2.inputs["Vector"]
        )
        rndColorIGroup.links.new(separate2.outputs["X"], combine3.inputs["X"])
        rndColorIGroup.links.new(separate2.outputs["X"], combine3.inputs["Y"])
        rndColorIGroup.links.new(combine3.outputs["Vector"], vecMul.inputs["Vector"])
        rndColorIGroup.links.new(
            rndColorIGroupI.outputs["rndBlocks"],
            shader_nodes.socket_by_identifier(vecMul.inputs, "Vector_001"),
        )
        rndColorIGroup.links.new(vecMul.outputs["Vector"], vecFloor.inputs["Vector"])
        rndColorIGroup.links.new(vecFloor.outputs["Vector"], vecDiv2.inputs["Vector"])
        rndColorIGroup.links.new(
            rndColorIGroupI.outputs["rndBlocks"],
            shader_nodes.socket_by_identifier(vecDiv2.inputs, "Vector_001"),
        )
        rndColorIGroup.links.new(rndColorIGroupI.outputs["Time"], frac6.inputs["Value"])
        rndColorIGroup.links.new(vecDiv2.outputs["Vector"], vecMul2.inputs["Vector"])
        rndColorIGroup.links.new(
            frac6.outputs["Value"],
            shader_nodes.socket_by_identifier(vecMul2.inputs, "Vector_001"),
        )
        rndColorIGroup.links.new(vecMul2.outputs["Vector"], vecSub.inputs["Vector"])
        rndColorIGroup.links.new(vecSub.outputs["Vector"], hash12_2.inputs["vector"])
        rndColorIGroup.links.new(hash12_2.outputs["result"], mul9.inputs["Value"])
        rndColorIGroup.links.new(mul9.outputs["Value"], palette_index.inputs["Value"])
        rndColorIGroup.links.new(
            palette_index.outputs["Value"], rndColorIGroupO.inputs["rndColorIndex"]
        )

    return rndColorIGroup


def get_or_create_rnd_color_group():

    rndColorGroup = bpy.data.node_groups.get("CP77 Television Ad rndColor v1")

    if rndColorGroup is None:
        rndColorGroup = new_tracked_datablock(
            "node_groups", "CP77 Television Ad rndColor v1", "ShaderNodeTree"
        )
        rndColorGroup.interface.new_socket(
            name="rndColorIndex", socket_type="NodeSocketFloat", in_out="INPUT"
        )
        rndColorGroup.interface.new_socket(
            name="rndColor", socket_type="NodeSocketColor", in_out="OUTPUT"
        )
        rndColorGroupI = create_node(rndColorGroup.nodes, "NodeGroupInput", (-1400, 0))
        rndColorGroupO = create_node(rndColorGroup.nodes, "NodeGroupOutput", (200, 0))
        compare = shader_nodes.math(
            rndColorGroup.nodes,
            rndColorGroup.links,
            "COMPARE",
            location=(-1100, 150),
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(compare.inputs, "Value_001").default_value = 0
        shader_nodes.socket_by_identifier(compare.inputs, "Value_002").default_value = 0
        compare2 = shader_nodes.math(
            rndColorGroup.nodes,
            rndColorGroup.links,
            "COMPARE",
            location=(-1100, 50),
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(
            compare2.inputs, "Value_001"
        ).default_value = 1
        shader_nodes.socket_by_identifier(
            compare2.inputs, "Value_002"
        ).default_value = 0
        compare3 = shader_nodes.math(
            rndColorGroup.nodes,
            rndColorGroup.links,
            "COMPARE",
            location=(-1100, -50),
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(
            compare3.inputs, "Value_001"
        ).default_value = 2
        shader_nodes.socket_by_identifier(
            compare3.inputs, "Value_002"
        ).default_value = 0
        compare4 = shader_nodes.math(
            rndColorGroup.nodes,
            rndColorGroup.links,
            "COMPARE",
            location=(-1100, -150),
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(
            compare4.inputs, "Value_001"
        ).default_value = 3
        shader_nodes.socket_by_identifier(
            compare4.inputs, "Value_002"
        ).default_value = 0
        combine4 = create_node(rndColorGroup.nodes, "ShaderNodeCombineXYZ", (-900, 175))
        combine4.inputs["X"].default_value = 1
        combine4.inputs["Y"].default_value = 1
        combine4.inputs["Z"].default_value = 1
        combine5 = create_node(rndColorGroup.nodes, "ShaderNodeCombineXYZ", (-900, 75))
        combine5.inputs["X"].default_value = 0.2
        combine5.inputs["Y"].default_value = 0
        combine5.inputs["Z"].default_value = 0
        combine6 = create_node(rndColorGroup.nodes, "ShaderNodeCombineXYZ", (-900, -25))
        combine6.inputs["X"].default_value = 0
        combine6.inputs["Y"].default_value = 1
        combine6.inputs["Z"].default_value = 0
        combine7 = create_node(
            rndColorGroup.nodes, "ShaderNodeCombineXYZ", (-900, -125)
        )
        combine7.inputs["X"].default_value = 0
        combine7.inputs["Y"].default_value = 0
        combine7.inputs["Z"].default_value = 1
        vecMul3 = shader_nodes.vector_math(
            rndColorGroup.nodes,
            rndColorGroup.links,
            "MULTIPLY",
            location=(-700, 150),
            hide=True,
        ).node
        vecMul4 = shader_nodes.vector_math(
            rndColorGroup.nodes,
            rndColorGroup.links,
            "MULTIPLY",
            location=(-700, 50),
            hide=True,
        ).node
        vecMul5 = shader_nodes.vector_math(
            rndColorGroup.nodes,
            rndColorGroup.links,
            "MULTIPLY",
            location=(-700, -50),
            hide=True,
        ).node
        vecMul6 = shader_nodes.vector_math(
            rndColorGroup.nodes,
            rndColorGroup.links,
            "MULTIPLY",
            location=(-700, -150),
            hide=True,
        ).node
        vecAdd2 = shader_nodes.vector_math(
            rndColorGroup.nodes,
            rndColorGroup.links,
            "ADD",
            location=(-500, 100),
            hide=True,
        ).node
        vecAdd3 = shader_nodes.vector_math(
            rndColorGroup.nodes,
            rndColorGroup.links,
            "ADD",
            location=(-500, -100),
            hide=True,
        ).node
        vecAdd4 = shader_nodes.vector_math(
            rndColorGroup.nodes,
            rndColorGroup.links,
            "ADD",
            location=(-300, 0),
            hide=True,
        ).node
        rndColorGroup.links.new(
            rndColorGroupI.outputs["rndColorIndex"], compare.inputs["Value"]
        )
        rndColorGroup.links.new(
            rndColorGroupI.outputs["rndColorIndex"], compare2.inputs["Value"]
        )
        rndColorGroup.links.new(
            rndColorGroupI.outputs["rndColorIndex"], compare3.inputs["Value"]
        )
        rndColorGroup.links.new(
            rndColorGroupI.outputs["rndColorIndex"], compare4.inputs["Value"]
        )
        rndColorGroup.links.new(
            compare.outputs["Value"],
            shader_nodes.socket_by_identifier(vecMul3.inputs, "Vector_001"),
        )
        rndColorGroup.links.new(
            compare2.outputs["Value"],
            shader_nodes.socket_by_identifier(vecMul4.inputs, "Vector_001"),
        )
        rndColorGroup.links.new(
            compare3.outputs["Value"],
            shader_nodes.socket_by_identifier(vecMul5.inputs, "Vector_001"),
        )
        rndColorGroup.links.new(
            compare4.outputs["Value"],
            shader_nodes.socket_by_identifier(vecMul6.inputs, "Vector_001"),
        )
        rndColorGroup.links.new(combine4.outputs["Vector"], vecMul3.inputs["Vector"])
        rndColorGroup.links.new(combine5.outputs["Vector"], vecMul4.inputs["Vector"])
        rndColorGroup.links.new(combine6.outputs["Vector"], vecMul5.inputs["Vector"])
        rndColorGroup.links.new(combine7.outputs["Vector"], vecMul6.inputs["Vector"])
        rndColorGroup.links.new(vecMul3.outputs["Vector"], vecAdd2.inputs["Vector"])
        rndColorGroup.links.new(
            vecMul4.outputs["Vector"],
            shader_nodes.socket_by_identifier(vecAdd2.inputs, "Vector_001"),
        )
        rndColorGroup.links.new(vecMul5.outputs["Vector"], vecAdd3.inputs["Vector"])
        rndColorGroup.links.new(
            vecMul6.outputs["Vector"],
            shader_nodes.socket_by_identifier(vecAdd3.inputs, "Vector_001"),
        )
        rndColorGroup.links.new(vecAdd2.outputs["Vector"], vecAdd4.inputs["Vector"])
        rndColorGroup.links.new(
            vecAdd3.outputs["Vector"],
            shader_nodes.socket_by_identifier(vecAdd4.inputs, "Vector_001"),
        )
        rndColorGroup.links.new(
            vecAdd4.outputs["Vector"], rndColorGroupO.inputs["rndColor"]
        )

    return rndColorGroup


def get_or_create_black_dots_group():

    blackDotsGroup = bpy.data.node_groups.get("CP77 Television Ad blackDots v1")

    if blackDotsGroup is None:
        blackDotsGroup = new_tracked_datablock(
            "node_groups", "CP77 Television Ad blackDots v1", "ShaderNodeTree"
        )
        blackDotsGroup.interface.new_socket(
            name="UV", socket_type="NodeSocketVector", in_out="INPUT"
        )
        blackDotsGroup.interface.new_socket(
            name="PixelsHeight", socket_type="NodeSocketFloat", in_out="INPUT"
        )
        blackDotsGroup.interface.new_socket(
            name="BlackLinesRatio", socket_type="NodeSocketFloat", in_out="INPUT"
        )
        blackDotsGroup.interface.new_socket(
            name="BlackLinesSize", socket_type="NodeSocketFloat", in_out="INPUT"
        )
        blackDotsGroup.interface.new_socket(
            name="TilesHeight", socket_type="NodeSocketFloat", in_out="INPUT"
        )
        blackDotsGroup.interface.new_socket(
            name="LinesOrDots", socket_type="NodeSocketFloat", in_out="INPUT"
        )
        blackDotsGroup.interface.new_socket(
            name="BlackLinesIntensity", socket_type="NodeSocketFloat", in_out="INPUT"
        )
        blackDotsGroup.interface.new_socket(
            name="blackDots", socket_type="NodeSocketFloat", in_out="OUTPUT"
        )
        blackDotsGroupI = create_node(
            blackDotsGroup.nodes, "NodeGroupInput", (-1400, 0)
        )
        blackDotsGroupO = create_node(
            blackDotsGroup.nodes, "NodeGroupOutput", (1000, 0)
        )

        separate = create_node(
            blackDotsGroup.nodes, "ShaderNodeSeparateXYZ", (-1250, 50)
        )
        add = shader_nodes.math(
            blackDotsGroup.nodes,
            blackDotsGroup.links,
            "ADD",
            location=(-1100, 50),
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(add.inputs, "Value_001").default_value = 0.5
        mul = shader_nodes.math(
            blackDotsGroup.nodes,
            blackDotsGroup.links,
            "MULTIPLY",
            location=(-950, 50),
            hide=True,
        ).node
        div = shader_nodes.math(
            blackDotsGroup.nodes,
            blackDotsGroup.links,
            "DIVIDE",
            location=(-800, 50),
            hide=True,
        ).node
        frac = shader_nodes.math(
            blackDotsGroup.nodes,
            blackDotsGroup.links,
            "FRACT",
            location=(-650, 50),
            hide=True,
        ).node
        add2 = shader_nodes.math(
            blackDotsGroup.nodes,
            blackDotsGroup.links,
            "ADD",
            location=(-500, 50),
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(add2.inputs, "Value_001").default_value = 0.4
        floor = shader_nodes.math(
            blackDotsGroup.nodes,
            blackDotsGroup.links,
            "FLOOR",
            location=(-350, 50),
            use_clamp=True,
            hide=True,
        ).node
        blackDotsGroup.links.new(
            blackDotsGroupI.outputs["UV"], separate.inputs["Vector"]
        )
        blackDotsGroup.links.new(separate.outputs["X"], add.inputs["Value"])
        blackDotsGroup.links.new(add.outputs["Value"], mul.inputs["Value"])
        blackDotsGroup.links.new(
            blackDotsGroupI.outputs["PixelsHeight"],
            shader_nodes.socket_by_identifier(mul.inputs, "Value_001"),
        )
        blackDotsGroup.links.new(mul.outputs["Value"], div.inputs["Value"])
        blackDotsGroup.links.new(
            blackDotsGroupI.outputs["BlackLinesRatio"],
            shader_nodes.socket_by_identifier(div.inputs, "Value_001"),
        )
        blackDotsGroup.links.new(div.outputs["Value"], frac.inputs["Value"])
        blackDotsGroup.links.new(frac.outputs["Value"], add2.inputs["Value"])
        blackDotsGroup.links.new(add2.outputs["Value"], floor.inputs["Value"])

        vecMul = shader_nodes.vector_math(
            blackDotsGroup.nodes,
            blackDotsGroup.links,
            "MULTIPLY",
            location=(-1250, -50),
            hide=True,
        ).node
        vecMul2 = shader_nodes.vector_math(
            blackDotsGroup.nodes,
            blackDotsGroup.links,
            "MULTIPLY",
            location=(-1100, -50),
            hide=True,
        ).node
        vecMul3 = shader_nodes.vector_math(
            blackDotsGroup.nodes,
            blackDotsGroup.links,
            "MULTIPLY",
            location=(-950, -50),
            hide=True,
        ).node
        blackDotsGroup.links.new(blackDotsGroupI.outputs["UV"], vecMul.inputs["Vector"])
        blackDotsGroup.links.new(
            blackDotsGroupI.outputs["BlackLinesSize"],
            shader_nodes.socket_by_identifier(vecMul.inputs, "Vector_001"),
        )
        blackDotsGroup.links.new(vecMul.outputs["Vector"], vecMul2.inputs["Vector"])
        blackDotsGroup.links.new(
            blackDotsGroupI.outputs["TilesHeight"],
            shader_nodes.socket_by_identifier(vecMul2.inputs, "Vector_001"),
        )
        blackDotsGroup.links.new(vecMul2.outputs["Vector"], vecMul3.inputs["Vector"])
        blackDotsGroup.links.new(
            blackDotsGroupI.outputs["BlackLinesRatio"],
            shader_nodes.socket_by_identifier(vecMul3.inputs, "Vector_001"),
        )

        separate2 = create_node(
            blackDotsGroup.nodes, "ShaderNodeSeparateXYZ", (-800, -50)
        )
        mul2 = shader_nodes.math(
            blackDotsGroup.nodes,
            blackDotsGroup.links,
            "MULTIPLY",
            location=(-650, -50),
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(
            mul2.inputs, "Value_001"
        ).default_value = 3.1415926
        add3 = shader_nodes.math(
            blackDotsGroup.nodes,
            blackDotsGroup.links,
            "ADD",
            location=(-500, -50),
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(add3.inputs, "Value_001").default_value = (
            3.1415926 / 2
        )
        cos = shader_nodes.math(
            blackDotsGroup.nodes,
            blackDotsGroup.links,
            "COSINE",
            location=(-350, -50),
            hide=True,
        ).node

        mul3 = shader_nodes.math(
            blackDotsGroup.nodes,
            blackDotsGroup.links,
            "MULTIPLY",
            location=(-650, -150),
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(
            mul3.inputs, "Value_001"
        ).default_value = 3.1415926
        add4 = shader_nodes.math(
            blackDotsGroup.nodes,
            blackDotsGroup.links,
            "ADD",
            location=(-500, -150),
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(add4.inputs, "Value_001").default_value = (
            3.1415926 / 2
        )
        cos2 = shader_nodes.math(
            blackDotsGroup.nodes,
            blackDotsGroup.links,
            "COSINE",
            location=(-350, -150),
            hide=True,
        ).node

        mul4 = shader_nodes.math(
            blackDotsGroup.nodes,
            blackDotsGroup.links,
            "MULTIPLY",
            location=(-200, -100),
            hide=True,
        ).node
        mul5 = shader_nodes.math(
            blackDotsGroup.nodes,
            blackDotsGroup.links,
            "MULTIPLY",
            location=(-50, -100),
            hide=True,
        ).node
        mul5.inputs["Value"].default_value = 1
        mul6 = shader_nodes.math(
            blackDotsGroup.nodes,
            blackDotsGroup.links,
            "MULTIPLY",
            location=(100, -100),
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(mul6.inputs, "Value_001").default_value = 0.5
        blackDotsGroup.links.new(vecMul3.outputs["Vector"], separate2.inputs["Vector"])
        blackDotsGroup.links.new(separate2.outputs["Y"], mul2.inputs["Value"])
        blackDotsGroup.links.new(mul2.outputs["Value"], add3.inputs["Value"])
        blackDotsGroup.links.new(add3.outputs["Value"], cos.inputs["Value"])
        blackDotsGroup.links.new(separate2.outputs["X"], mul3.inputs["Value"])
        blackDotsGroup.links.new(mul3.outputs["Value"], add4.inputs["Value"])
        blackDotsGroup.links.new(add4.outputs["Value"], cos2.inputs["Value"])
        blackDotsGroup.links.new(cos.outputs["Value"], mul4.inputs["Value"])
        blackDotsGroup.links.new(
            cos2.outputs["Value"],
            shader_nodes.socket_by_identifier(mul4.inputs, "Value_001"),
        )
        blackDotsGroup.links.new(
            mul4.outputs["Value"],
            shader_nodes.socket_by_identifier(mul5.inputs, "Value_001"),
        )
        blackDotsGroup.links.new(mul5.outputs["Value"], mul6.inputs["Value"])
        midpoint = shader_nodes.math(
            blackDotsGroup.nodes,
            blackDotsGroup.links,
            "ADD",
            label="Dots Midpoint",
            location=(250, -180),
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(
            midpoint.inputs, "Value_001"
        ).default_value = 0.5
        blackDotsGroup.links.new(mul6.outputs["Value"], midpoint.inputs["Value"])

        mix = create_node(blackDotsGroup.nodes, "ShaderNodeMix", (250, 0))
        mix.data_type = "FLOAT"
        blackDotsGroup.links.new(
            blackDotsGroupI.outputs["LinesOrDots"],
            shader_nodes.socket_by_identifier(mix.inputs, "Factor_Float"),
        )
        blackDotsGroup.links.new(
            floor.outputs["Value"],
            shader_nodes.socket_by_identifier(mix.inputs, "A_Float"),
        )
        blackDotsGroup.links.new(
            midpoint.outputs["Value"],
            shader_nodes.socket_by_identifier(mix.inputs, "B_Float"),
        )

        sub = shader_nodes.math(
            blackDotsGroup.nodes,
            blackDotsGroup.links,
            "SUBTRACT",
            location=(250, -50),
            hide=True,
        ).node
        sub.inputs["Value"].default_value = 1
        add5 = shader_nodes.math(
            blackDotsGroup.nodes,
            blackDotsGroup.links,
            "ADD",
            location=(400, -50),
            use_clamp=True,
            hide=True,
        ).node
        blackDotsGroup.links.new(
            blackDotsGroupI.outputs["BlackLinesIntensity"],
            shader_nodes.socket_by_identifier(sub.inputs, "Value_001"),
        )
        blackDotsGroup.links.new(
            shader_nodes.socket_by_identifier(mix.outputs, "Result_Float"),
            add5.inputs["Value"],
        )
        blackDotsGroup.links.new(
            sub.outputs["Value"],
            shader_nodes.socket_by_identifier(add5.inputs, "Value_001"),
        )
        blackDotsGroup.links.new(
            add5.outputs["Value"], blackDotsGroupO.inputs["blackDots"]
        )

    return blackDotsGroup


class TelevisionAd(MaterialTypeBase):
    texture_defaults = {}

    def create(self, Data, Mat):
        CurMat = Mat.node_tree
        pBSDF = shader_nodes.principled_bsdf(CurMat.nodes)
        sockets = bsdf_socket_names()
        pBSDF.inputs[sockets["Specular"]].default_value = 0

        params = create_param_value_nodes(CurMat, Data, _PARAM_SPECS)
        tilesW = params["TilesWidth"]
        tilesH = params["TilesHeight"]
        playSpeed = params["PlaySpeed"]
        iLines = params["InterlaceLines"]
        pixH = params["PixelsHeight"]
        blRatio = params["BlackLinesRatio"]
        blIntensity = params["BlackLinesIntensity"]
        blSize = params["BlackLinesSize"]
        lOrDots = params["LinesOrDots"]
        m = params["Metalness"]
        r = params["Roughness"]
        isBroken = params["IsBroken"]
        e = params["EmissiveEV"]
        HUEcSpeed = params["HUEChangeSpeed"]
        dirtOS = params["DirtOpacityScale"]
        dirtR = params["DirtRoughness"]
        dirtUVScaleU = params["DirtUvScaleU"]
        dirtUVScaleV = params["DirtUvScaleV"]

        time = create_scene_time_value(CurMat, -2000, 550, "Time")

        UVNode = create_node(CurMat.nodes, "ShaderNodeTexCoord", (-2000, 650))

        ad_reference = self._texture_path(Data, "AdTexture")
        dirt_reference = self._texture_path(Data, "DirtTexture")
        if dirt_reference:
            dirtImg = imageFromRelPath(
                dirt_reference,
                self.image_format,
                DepotPath=self.BasePath,
                ProjPath=self.ProjPath,
            )
            dirtNode = create_node(
                CurMat.nodes,
                "ShaderNodeTexImage",
                (-2000, 450),
                label="DirtTexture",
                image=dirtImg,
            )

            combine11 = create_node(CurMat.nodes, "ShaderNodeCombineXYZ", (-1850, -725))
            vecMul9 = shader_nodes.vector_math(
                CurMat.nodes,
                CurMat.links,
                "MULTIPLY",
                location=(-1700, -725),
                hide=True,
            ).node
            CurMat.links.new(dirtUVScaleU.outputs["Value"], combine11.inputs["X"])
            CurMat.links.new(dirtUVScaleV.outputs["Value"], combine11.inputs["Y"])
            CurMat.links.new(UVNode.outputs["UV"], vecMul9.inputs["Vector"])
            CurMat.links.new(
                combine11.outputs["Vector"],
                shader_nodes.socket_by_identifier(vecMul9.inputs, "Vector_001"),
            )

            CurMat.links.new(vecMul9.outputs["Vector"], dirtNode.inputs["Vector"])

            mul12 = shader_nodes.math(
                CurMat.nodes,
                CurMat.links,
                "MULTIPLY",
                location=(-1850, -600),
                hide=True,
            ).node
            CurMat.links.new(dirtNode.outputs["Alpha"], mul12.inputs["Value"])
            CurMat.links.new(
                dirtOS.outputs["Value"],
                shader_nodes.socket_by_identifier(mul12.inputs, "Value_001"),
            )
        else:
            dirtNode = None
            mul12 = shader_nodes.math(
                CurMat.nodes,
                CurMat.links,
                "MULTIPLY",
                location=(-1850, -600),
                hide=True,
            ).node
            mul12.inputs["Value"].default_value = 0.0
            CurMat.links.new(
                dirtOS.outputs["Value"],
                shader_nodes.socket_by_identifier(mul12.inputs, "Value_001"),
            )

        if ad_reference:
            adImg = imageFromRelPath(
                ad_reference,
                self.image_format,
                DepotPath=self.BasePath,
                ProjPath=self.ProjPath,
            )
            adNode = create_node(
                CurMat.nodes,
                "ShaderNodeTexImage",
                (-100, 1025),
                label="AdTexture",
                image=adImg,
            )
            adNode2 = create_node(
                CurMat.nodes,
                "ShaderNodeTexImage",
                (-1000, 775),
                label="AdTexture",
                image=adImg,
            )
            adNode3 = create_node(
                CurMat.nodes,
                "ShaderNodeTexImage",
                (-550, 975),
                label="AdTexture",
                image=adImg,
            )

            ngroup = get_or_create_n_group()

            n = create_node(CurMat.nodes, "ShaderNodeGroup", (-1700, 925), label="n")
            n.node_tree = ngroup

            CurMat.links.new(tilesW.outputs["Value"], n.inputs["TilesWidth"])
            CurMat.links.new(tilesH.outputs["Value"], n.inputs["TilesHeight"])
            CurMat.links.new(playSpeed.outputs["Value"], n.inputs["PlaySpeed"])
            CurMat.links.new(time.outputs["Value"], n.inputs["Time"])

            frameGroup = get_or_create_frame_add_group()

            frameAdd = create_node(
                CurMat.nodes, "ShaderNodeGroup", (-1700, 825), label="frameAdd"
            )
            frameAdd.node_tree = frameGroup

            CurMat.links.new(pixH.outputs["Value"], frameAdd.inputs["PixelsHeight"])
            CurMat.links.new(iLines.outputs["Value"], frameAdd.inputs["InterlaceLines"])
            CurMat.links.new(UVNode.outputs["UV"], frameAdd.inputs["UV"])
            CurMat.links.new(n.outputs["n"], frameAdd.inputs["n"])

            subUVGroup = get_or_create_sub_uv_group()

            subUV = create_node(
                CurMat.nodes, "ShaderNodeGroup", (-1350, 875), label="subUV"
            )
            subUV.node_tree = subUVGroup
            subUV.name = "subUV"

            CurMat.links.new(tilesW.outputs["Value"], subUV.inputs["TilesWidth"])
            CurMat.links.new(tilesH.outputs["Value"], subUV.inputs["TilesHeight"])
            CurMat.links.new(UVNode.outputs["UV"], subUV.inputs["UV"])
            CurMat.links.new(n.outputs["n"], subUV.inputs["n"])
            CurMat.links.new(frameAdd.outputs["frameAdd"], subUV.inputs["frameAdd"])

            CurMat.links.new(subUV.outputs["subUV"], adNode.inputs["Vector"])

            lerpG = createLerpGroup()
            lerp = create_node(
                CurMat.nodes, "ShaderNodeGroup", (-1400, 675), label="lerp"
            )
            lerp.node_tree = lerpG
            lerp.inputs["A"].default_value = 2
            lerp.inputs["B"].default_value = 8
            frac2 = shader_nodes.math(
                CurMat.nodes, CurMat.links, "FRACT", location=(-1550, 675), hide=True
            ).node
            add7 = shader_nodes.math(
                CurMat.nodes, CurMat.links, "ADD", location=(-1700, 675), hide=True
            ).node
            shader_nodes.socket_by_identifier(
                add7.inputs, "Value_001"
            ).default_value = 0.375
            CurMat.links.new(time.outputs["Value"], add7.inputs["Value"])
            CurMat.links.new(add7.outputs["Value"], frac2.inputs["Value"])
            CurMat.links.new(frac2.outputs["Value"], lerp.inputs["t"])

            brokenUVGroup = get_or_create_broken_uv_group()

            brokenUV = create_node(
                CurMat.nodes, "ShaderNodeGroup", (-1200, 775), label="brokenUV"
            )
            brokenUV.node_tree = brokenUVGroup

            CurMat.links.new(lerp.outputs["result"], brokenUV.inputs["rndBlocks"])
            CurMat.links.new(time.outputs["Value"], brokenUV.inputs["Time"])
            CurMat.links.new(UVNode.outputs["UV"], brokenUV.inputs["UV"])

            rndColorIGroup = get_or_create_rnd_color_index_group()

            rndColorIndex = create_node(
                CurMat.nodes, "ShaderNodeGroup", (-1200, 575), label="rndColorIndex"
            )
            rndColorIndex.node_tree = rndColorIGroup
            CurMat.links.new(lerp.outputs["result"], rndColorIndex.inputs["rndBlocks"])
            CurMat.links.new(time.outputs["Value"], rndColorIndex.inputs["Time"])
            CurMat.links.new(UVNode.outputs["UV"], rndColorIndex.inputs["UV"])

            rndColorGroup = get_or_create_rnd_color_group()

            rndColor = create_node(
                CurMat.nodes, "ShaderNodeGroup", (-1000, 575), label="rndColor"
            )
            rndColor.node_tree = rndColorGroup

            CurMat.links.new(
                rndColorIndex.outputs["rndColorIndex"], rndColor.inputs["rndColorIndex"]
            )

            separate3 = create_node(CurMat.nodes, "ShaderNodeSeparateXYZ", (-1700, 400))
            greaterThan = shader_nodes.math(
                CurMat.nodes,
                CurMat.links,
                "GREATER_THAN",
                location=(-1500, 450),
                hide=True,
            ).node
            shader_nodes.socket_by_identifier(
                greaterThan.inputs, "Value_001"
            ).default_value = 0.02
            lessThan = shader_nodes.math(
                CurMat.nodes,
                CurMat.links,
                "LESS_THAN",
                location=(-1500, 350),
                hide=True,
            ).node
            shader_nodes.socket_by_identifier(
                lessThan.inputs, "Value_001"
            ).default_value = 0.12
            minimum = shader_nodes.math(
                CurMat.nodes, CurMat.links, "MINIMUM", location=(-1300, 400), hide=True
            ).node
            greaterThan2 = shader_nodes.math(
                CurMat.nodes,
                CurMat.links,
                "GREATER_THAN",
                location=(-1500, 250),
                hide=True,
            ).node
            shader_nodes.socket_by_identifier(
                greaterThan2.inputs, "Value_001"
            ).default_value = 0.28
            lessThan2 = shader_nodes.math(
                CurMat.nodes,
                CurMat.links,
                "LESS_THAN",
                location=(-1500, 150),
                hide=True,
            ).node
            shader_nodes.socket_by_identifier(
                lessThan2.inputs, "Value_001"
            ).default_value = 0.543
            minimum2 = shader_nodes.math(
                CurMat.nodes, CurMat.links, "MINIMUM", location=(-1300, 200), hide=True
            ).node
            greaterThan3 = shader_nodes.math(
                CurMat.nodes,
                CurMat.links,
                "GREATER_THAN",
                location=(-1500, 50),
                hide=True,
            ).node
            shader_nodes.socket_by_identifier(
                greaterThan3.inputs, "Value_001"
            ).default_value = 0.78
            lessThan3 = shader_nodes.math(
                CurMat.nodes,
                CurMat.links,
                "LESS_THAN",
                location=(-1500, -50),
                hide=True,
            ).node
            shader_nodes.socket_by_identifier(
                lessThan3.inputs, "Value_001"
            ).default_value = 0.85
            minimum3 = shader_nodes.math(
                CurMat.nodes, CurMat.links, "MINIMUM", location=(-1300, 0), hide=True
            ).node
            add10 = shader_nodes.math(
                CurMat.nodes, CurMat.links, "ADD", location=(-1100, 300), hide=True
            ).node
            add11 = shader_nodes.math(
                CurMat.nodes, CurMat.links, "ADD", location=(-900, 200), hide=True
            ).node
            CurMat.links.new(UVNode.outputs["UV"], separate3.inputs["Vector"])
            CurMat.links.new(separate3.outputs["X"], greaterThan.inputs["Value"])
            CurMat.links.new(separate3.outputs["X"], lessThan.inputs["Value"])
            CurMat.links.new(greaterThan.outputs["Value"], minimum.inputs["Value"])
            CurMat.links.new(
                lessThan.outputs["Value"],
                shader_nodes.socket_by_identifier(minimum.inputs, "Value_001"),
            )
            CurMat.links.new(separate3.outputs["X"], greaterThan2.inputs["Value"])
            CurMat.links.new(separate3.outputs["X"], lessThan2.inputs["Value"])
            CurMat.links.new(greaterThan2.outputs["Value"], minimum2.inputs["Value"])
            CurMat.links.new(
                lessThan2.outputs["Value"],
                shader_nodes.socket_by_identifier(minimum2.inputs, "Value_001"),
            )
            CurMat.links.new(separate3.outputs["X"], greaterThan3.inputs["Value"])
            CurMat.links.new(separate3.outputs["X"], lessThan3.inputs["Value"])
            CurMat.links.new(greaterThan3.outputs["Value"], minimum3.inputs["Value"])
            CurMat.links.new(
                lessThan3.outputs["Value"],
                shader_nodes.socket_by_identifier(minimum3.inputs, "Value_001"),
            )
            CurMat.links.new(minimum.outputs["Value"], add10.inputs["Value"])
            CurMat.links.new(
                minimum2.outputs["Value"],
                shader_nodes.socket_by_identifier(add10.inputs, "Value_001"),
            )
            CurMat.links.new(add10.outputs["Value"], add11.inputs["Value"])
            CurMat.links.new(
                minimum3.outputs["Value"],
                shader_nodes.socket_by_identifier(add11.inputs, "Value_001"),
            )

            CurMat.links.new(brokenUV.outputs["brokenUV"], adNode2.inputs["Vector"])
            vecMul7 = shader_nodes.vector_math(
                CurMat.nodes, CurMat.links, "MULTIPLY", location=(-700, 675), hide=True
            ).node
            CurMat.links.new(adNode2.outputs["Color"], vecMul7.inputs["Vector"])
            CurMat.links.new(
                rndColor.outputs["rndColor"],
                shader_nodes.socket_by_identifier(vecMul7.inputs, "Vector_001"),
            )
            mixRGB = create_node(CurMat.nodes, "ShaderNodeMix", (-500, 487.5))
            mixRGB.data_type = "RGBA"
            CurMat.links.new(
                add11.outputs["Value"],
                shader_nodes.socket_by_identifier(mixRGB.inputs, "Factor_Float"),
            )
            shader_nodes.socket_by_identifier(
                mixRGB.inputs, "A_Color"
            ).default_value = (0, 0, 0, 0)
            CurMat.links.new(
                vecMul7.outputs["Vector"],
                shader_nodes.socket_by_identifier(mixRGB.inputs, "B_Color"),
            )

            div9 = shader_nodes.math(
                CurMat.nodes, CurMat.links, "DIVIDE", location=(-1300, 975), hide=True
            ).node
            shader_nodes.socket_by_identifier(
                div9.inputs, "Value_001"
            ).default_value = 20
            frac7 = shader_nodes.math(
                CurMat.nodes, CurMat.links, "FRACT", location=(-1150, 975), hide=True
            ).node
            mul10 = shader_nodes.math(
                CurMat.nodes, CurMat.links, "MULTIPLY", location=(-1000, 975), hide=True
            ).node
            mul10.inputs["Value"].default_value = -0.01
            combine9 = create_node(CurMat.nodes, "ShaderNodeCombineXYZ", (-850, 975))
            combine9.inputs["X"].default_value = 0.01
            vecAdd5 = shader_nodes.vector_math(
                CurMat.nodes, CurMat.links, "ADD", location=(-700, 975), hide=True
            ).node

            vecMul8 = shader_nodes.vector_math(
                CurMat.nodes, CurMat.links, "MULTIPLY", location=(-300, 975), hide=True
            ).node
            vecMul8.inputs["Vector"].default_value = (0.4, 0.4, 0.4)
            mixRGB3 = create_node(CurMat.nodes, "ShaderNodeMix", (-150, 975))
            mixRGB3.data_type = "RGBA"
            vecAdd6 = shader_nodes.vector_math(
                CurMat.nodes, CurMat.links, "ADD", location=(0, 975), hide=True
            ).node

            CurMat.links.new(time.outputs["Value"], div9.inputs["Value"])
            CurMat.links.new(div9.outputs["Value"], frac7.inputs["Value"])
            CurMat.links.new(
                frac7.outputs["Value"],
                shader_nodes.socket_by_identifier(mul10.inputs, "Value_001"),
            )
            CurMat.links.new(mul10.outputs["Value"], combine9.inputs["Y"])
            CurMat.links.new(subUV.outputs["subUV"], vecAdd5.inputs["Vector"])
            CurMat.links.new(
                combine9.outputs["Vector"],
                shader_nodes.socket_by_identifier(vecAdd5.inputs, "Vector_001"),
            )
            CurMat.links.new(vecAdd5.outputs["Vector"], adNode3.inputs["Vector"])
            CurMat.links.new(
                adNode3.outputs["Color"],
                shader_nodes.socket_by_identifier(vecMul8.inputs, "Vector_001"),
            )
            CurMat.links.new(
                add11.outputs["Value"],
                shader_nodes.socket_by_identifier(mixRGB3.inputs, "Factor_Float"),
            )
            CurMat.links.new(
                vecMul8.outputs["Vector"],
                shader_nodes.socket_by_identifier(mixRGB3.inputs, "B_Color"),
            )
            CurMat.links.new(
                adNode.outputs["Color"],
                shader_nodes.socket_by_identifier(mixRGB3.inputs, "A_Color"),
            )
            CurMat.links.new(
                shader_nodes.socket_by_identifier(mixRGB3.outputs, "Result_Color"),
                vecAdd6.inputs["Vector"],
            )
            CurMat.links.new(
                shader_nodes.socket_by_identifier(mixRGB.outputs, "Result_Color"),
                shader_nodes.socket_by_identifier(vecAdd6.inputs, "Vector_001"),
            )

            mixRGB2 = create_node(CurMat.nodes, "ShaderNodeMix", (150, 975))
            mixRGB2.data_type = "RGBA"
            CurMat.links.new(
                isBroken.outputs["Value"],
                shader_nodes.socket_by_identifier(mixRGB2.inputs, "Factor_Float"),
            )
            CurMat.links.new(
                adNode.outputs["Color"],
                shader_nodes.socket_by_identifier(mixRGB2.inputs, "A_Color"),
            )
            CurMat.links.new(
                vecAdd6.outputs["Vector"],
                shader_nodes.socket_by_identifier(mixRGB2.inputs, "B_Color"),
            )

            separate4 = create_node(CurMat.nodes, "ShaderNodeSeparateColor", (300, 975))
            separate4.mode = "HSV"
            mul11 = shader_nodes.math(
                CurMat.nodes, CurMat.links, "MULTIPLY", location=(0, 925), hide=True
            ).node
            frac8 = shader_nodes.math(
                CurMat.nodes, CurMat.links, "FRACT", location=(150, 925), hide=True
            ).node
            add12 = shader_nodes.math(
                CurMat.nodes, CurMat.links, "ADD", location=(450, 975), hide=True
            ).node
            combine10 = create_node(CurMat.nodes, "ShaderNodeCombineColor", (600, 975))
            combine10.mode = "HSV"
            CurMat.links.new(
                shader_nodes.socket_by_identifier(mixRGB2.outputs, "Result_Color"),
                separate4.inputs["Color"],
            )
            CurMat.links.new(time.outputs["Value"], mul11.inputs["Value"])
            CurMat.links.new(
                HUEcSpeed.outputs["Value"],
                shader_nodes.socket_by_identifier(mul11.inputs, "Value_001"),
            )
            CurMat.links.new(mul11.outputs["Value"], frac8.inputs["Value"])
            CurMat.links.new(separate4.outputs["Red"], add12.inputs["Value"])
            CurMat.links.new(
                frac8.outputs["Value"],
                shader_nodes.socket_by_identifier(add12.inputs, "Value_001"),
            )
            CurMat.links.new(add12.outputs["Value"], combine10.inputs["Red"])
            CurMat.links.new(separate4.outputs["Green"], combine10.inputs["Green"])
            CurMat.links.new(separate4.outputs["Blue"], combine10.inputs["Blue"])

            blackDotsGroup = get_or_create_black_dots_group()

            blackDots = create_node(
                CurMat.nodes, "ShaderNodeGroup", (-650, 200), label="blackDots"
            )
            blackDots.node_tree = blackDotsGroup
            CurMat.links.new(UVNode.outputs["UV"], blackDots.inputs["UV"])
            CurMat.links.new(pixH.outputs["Value"], blackDots.inputs["PixelsHeight"])
            CurMat.links.new(
                blRatio.outputs["Value"], blackDots.inputs["BlackLinesRatio"]
            )
            CurMat.links.new(
                blSize.outputs["Value"], blackDots.inputs["BlackLinesSize"]
            )
            CurMat.links.new(tilesH.outputs["Value"], blackDots.inputs["TilesHeight"])
            CurMat.links.new(lOrDots.outputs["Value"], blackDots.inputs["LinesOrDots"])
            CurMat.links.new(
                blIntensity.outputs["Value"], blackDots.inputs["BlackLinesIntensity"]
            )

            vecLerpG = createVecLerpGroup()
            vecLerp = create_node(
                CurMat.nodes, "ShaderNodeGroup", (-200, 200), label="vecLerp"
            )
            vecLerp.node_tree = vecLerpG
            vecMul10 = shader_nodes.vector_math(
                CurMat.nodes, CurMat.links, "MULTIPLY", location=(-350, 200), hide=True
            ).node
            CurMat.links.new(combine10.outputs["Color"], vecMul10.inputs["Vector"])
            CurMat.links.new(
                blackDots.outputs["blackDots"],
                shader_nodes.socket_by_identifier(vecMul10.inputs, "Vector_001"),
            )
            CurMat.links.new(vecMul10.outputs["Vector"], vecLerp.inputs["A"])
            if dirtNode is not None:
                CurMat.links.new(dirtNode.outputs["Color"], vecLerp.inputs["B"])
            CurMat.links.new(mul12.outputs["Value"], vecLerp.inputs["t"])
            CurMat.links.new(vecLerp.outputs["result"], pBSDF.inputs["Base Color"])
            CurMat.links.new(
                vecLerp.outputs["result"], pBSDF.inputs[sockets["Emission"]]
            )
            alpha_input = pBSDF.inputs.get("Alpha")
            if alpha_input is not None:
                below = shader_nodes.math(
                    CurMat.nodes,
                    CurMat.links,
                    "LESS_THAN",
                    label="Below AlphaThreshold",
                    location=(100, 750),
                    hide=True,
                ).node
                keep = shader_nodes.math(
                    CurMat.nodes,
                    CurMat.links,
                    "SUBTRACT",
                    label="Cutout Coverage",
                    location=(280, 750),
                    hide=True,
                ).node
                keep.inputs["Value"].default_value = 1.0
                coverage = shader_nodes.math(
                    CurMat.nodes,
                    CurMat.links,
                    "MULTIPLY",
                    label="Ad Alpha Coverage",
                    location=(460, 750),
                    hide=True,
                ).node
                CurMat.links.new(adNode.outputs["Alpha"], below.inputs["Value"])
                CurMat.links.new(
                    params["AlphaThreshold"].outputs["Value"],
                    shader_nodes.socket_by_identifier(below.inputs, "Value_001"),
                )
                CurMat.links.new(
                    below.outputs["Value"],
                    shader_nodes.socket_by_identifier(keep.inputs, "Value_001"),
                )
                CurMat.links.new(adNode.outputs["Alpha"], coverage.inputs["Value"])
                CurMat.links.new(
                    keep.outputs["Value"],
                    shader_nodes.socket_by_identifier(coverage.inputs, "Value_001"),
                )
                CurMat.links.new(coverage.outputs["Value"], alpha_input)
            Mat.surface_render_method = "DITHERED"

        CurMat.links.new(m.outputs["Value"], pBSDF.inputs["Metallic"])

        lerpG = createLerpGroup()
        lerp3 = create_node(CurMat.nodes, "ShaderNodeGroup", (-200, 0), label="lerp")
        lerp3.node_tree = lerpG
        CurMat.links.new(r.outputs["Value"], lerp3.inputs["A"])
        CurMat.links.new(dirtR.outputs["Value"], lerp3.inputs["B"])
        CurMat.links.new(mul12.outputs["Value"], lerp3.inputs["t"])
        CurMat.links.new(lerp3.outputs["result"], pBSDF.inputs["Roughness"])

        # Preserve black-dot modulation while using the established EV preview mapping.
        if ad_reference:
            ev_pow = shader_nodes.math(
                CurMat.nodes, CurMat.links, "POWER", location=(-50, -150), hide=True
            ).node
            ev_pow.inputs["Value"].default_value = 2.0
            CurMat.links.new(
                e.outputs["Value"],
                shader_nodes.socket_by_identifier(ev_pow.inputs, "Value_001"),
            )
            ev_linear = shader_nodes.math(
                CurMat.nodes, CurMat.links, "SUBTRACT", location=(100, -150), hide=True
            ).node
            shader_nodes.socket_by_identifier(
                ev_linear.inputs, "Value_001"
            ).default_value = 1.0
            ev_linear.use_clamp = True
            CurMat.links.new(ev_pow.outputs["Value"], ev_linear.inputs["Value"])
            emissive_strength = shader_nodes.math(
                CurMat.nodes, CurMat.links, "MULTIPLY", location=(250, -150), hide=True
            ).node
            CurMat.links.new(
                ev_linear.outputs["Value"], emissive_strength.inputs["Value"]
            )
            CurMat.links.new(
                blackDots.outputs["blackDots"],
                shader_nodes.socket_by_identifier(
                    emissive_strength.inputs, "Value_001"
                ),
            )
            CurMat.links.new(
                emissive_strength.outputs["Value"], pBSDF.inputs["Emission Strength"]
            )
        else:
            pBSDF.inputs["Emission Strength"].default_value = 0.0
