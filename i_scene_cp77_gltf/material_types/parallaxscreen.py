from functools import partial

import bpy

from ..blender import shader_nodes
from ..blender.transactions import new_tracked_datablock
from ..materials.blender.nodes import (
    CreateShaderNodeRGB,
    CreateShaderNodeValue,
    create_node,
    createLerpGroup,
    createVecLerpGroup,
)
from .graph import (
    combine_bundle_node,
    cp77_bitangent_socket,
    cp77_uv_tangent_node,
    separate_bundle_node,
)
from .mat_common import (
    MaterialTypeBase,
    add_group_node,
    create_param_value_nodes,
    get_or_build_node_group,
    param_float,
    param_value_rows,
    set_scene_fps_driver,
    write_slot_values,
)
from .overlay_common import additive_surface
from .parallax_common import (
    create_camera_forward_vector,
    create_scroll_group,
    create_scroll_uv_group,
)
from .scalar_params import component_value, scalar_parameter_data, scalar_value

_create_scroll_group = partial(create_scroll_group, transparent=True)
_create_scroll_uv_group = partial(create_scroll_uv_group, transparent=True)


_LAYER_SAMPLE_BUNDLE_ITEMS = (
    ("VECTOR", "Color"),
    ("FLOAT", "Alpha"),
)

_SCREEN_EFFECTS_BUNDLE_ITEMS = (
    ("FLOAT", "Scanline Intensity"),
    ("FLOAT", "Scanline Density"),
    ("FLOAT", "Scanline Phase"),
    ("FLOAT", "Scroll Mask"),
)


def _create_layer_uv_group(index, separated):
    """Keep atlas bounds and raw coordinates selectable through editable controls"""
    offset = (
        ((index % 2) * 0.5, (index // 2) * 0.5, 0.0) if separated else (0.0, 0.0, 0.0)
    )
    scale = 0.5 if separated else 1.0

    def build(group):
        nodes, links = group.nodes, group.links
        incoming = create_node(nodes, "NodeGroupInput", (-900, 0))
        outgoing = create_node(nodes, "NodeGroupOutput", (500, 0))
        tiled = shader_nodes.vector_math(
            nodes, links, "MULTIPLY", location=(-720, 180), hide=True
        ).node
        shader_nodes.socket_by_identifier(tiled.inputs, "Vector_001").default_value = (
            scale,
            scale,
            0.0,
        )
        shifted = shader_nodes.vector_math(
            nodes, links, "ADD", location=(-540, 180), hide=True
        ).node
        shader_nodes.socket_by_identifier(
            shifted.inputs, "Vector_001"
        ).default_value = offset
        separation = shader_nodes.vector_math(
            nodes, links, "SCALE", location=(-720, -100), hide=True
        ).node
        multiplier = shader_nodes.vector_math(
            nodes, links, "SCALE", location=(-540, -100), hide=True
        ).node
        multiplier.inputs["Scale"].default_value = float(index)
        raw = shader_nodes.vector_math(
            nodes, links, "ADD", location=(-360, 100), hide=True
        ).node
        axes = create_node(nodes, "ShaderNodeSeparateXYZ", (-180, 100))
        clamped = create_node(nodes, "ShaderNodeCombineXYZ", (160, 100))
        links.new(incoming.outputs["newUV"], tiled.inputs["Vector"])
        links.new(tiled.outputs["Vector"], shifted.inputs["Vector"])
        links.new(incoming.outputs["modUV"], separation.inputs["Vector"])
        links.new(incoming.outputs["LayersSeparation"], separation.inputs["Scale"])
        links.new(separation.outputs["Vector"], multiplier.inputs["Vector"])
        links.new(shifted.outputs["Vector"], raw.inputs["Vector"])
        links.new(
            multiplier.outputs["Vector"],
            shader_nodes.socket_by_identifier(raw.inputs, "Vector_001"),
        )
        links.new(raw.outputs["Vector"], axes.inputs["Vector"])
        for component, axis in enumerate("XY"):
            clamp = create_node(nodes, "ShaderNodeClamp", (0, 160 - component * 120))
            clamp.inputs["Min"].default_value = offset[component]
            clamp.inputs["Max"].default_value = offset[component] + scale
            links.new(axes.outputs[axis], clamp.inputs["Value"])
            links.new(clamp.outputs["Result"], clamped.inputs[axis])
        select = create_node(nodes, "ShaderNodeMix", (320, 0), label="ClampUV")
        select.data_type = "VECTOR"
        links.new(
            incoming.outputs["ClampUV"],
            shader_nodes.socket_by_identifier(select.inputs, "Factor_Float"),
        )
        links.new(
            raw.outputs["Vector"],
            shader_nodes.socket_by_identifier(select.inputs, "A_Vector"),
        )
        links.new(
            clamped.outputs["Vector"],
            shader_nodes.socket_by_identifier(select.inputs, "B_Vector"),
        )
        links.new(
            shader_nodes.socket_by_identifier(select.outputs, "Result_Vector"),
            outgoing.inputs["UV"],
        )

    return get_or_build_node_group(
        f"CP77 Transparent Screen {'Atlas' if separated else 'Full'} Layer {index + 1} UV v2",
        (
            ("NodeSocketVector", "modUV"),
            ("NodeSocketVector", "newUV"),
            ("NodeSocketFloat", "LayersSeparation"),
            ("NodeSocketFloat", "ClampUV"),
        ),
        (("NodeSocketVector", "UV"),),
        build,
    )


def _create_view_basis_group():
    inputs = (
        ("NodeSocketVector", "Camera Forward"),
        ("NodeSocketVector", "Tangent"),
        ("NodeSocketVector", "Bitangent"),
    )
    outputs = (("NodeSocketVector", "modUV"),)

    def build(group):
        group_in = create_node(group.nodes, "NodeGroupInput", (-700, 0))
        group_out = create_node(group.nodes, "NodeGroupOutput", (180, 0))
        tangent_dot = shader_nodes.vector_math(
            group.nodes, group.links, "DOT_PRODUCT", location=(-520, 80), hide=True
        ).node
        bitangent_dot = shader_nodes.vector_math(
            group.nodes, group.links, "DOT_PRODUCT", location=(-520, -80), hide=True
        ).node
        negate = shader_nodes.math(
            group.nodes, group.links, "MULTIPLY", location=(-320, -80), hide=True
        ).node
        shader_nodes.socket_by_identifier(
            negate.inputs, "Value_001"
        ).default_value = -1.0
        combine = create_node(group.nodes, "ShaderNodeCombineXYZ", (-100, 0))
        group.links.new(
            group_in.outputs["Camera Forward"], tangent_dot.inputs["Vector"]
        )
        group.links.new(
            group_in.outputs["Tangent"],
            shader_nodes.socket_by_identifier(tangent_dot.inputs, "Vector_001"),
        )
        group.links.new(
            group_in.outputs["Camera Forward"], bitangent_dot.inputs["Vector"]
        )
        group.links.new(
            group_in.outputs["Bitangent"],
            shader_nodes.socket_by_identifier(bitangent_dot.inputs, "Vector_001"),
        )
        group.links.new(bitangent_dot.outputs["Value"], negate.inputs["Value"])
        group.links.new(tangent_dot.outputs["Value"], combine.inputs["X"])
        group.links.new(negate.outputs["Value"], combine.inputs["Y"])
        group.links.new(combine.outputs["Vector"], group_out.inputs["modUV"])

    return get_or_build_node_group(
        "CP77 Transparent Screen View Basis v2",
        inputs,
        outputs,
        build,
    )


def _create_facing_alpha_group():
    inputs = (
        ("NodeSocketVector", "Position"),
        ("NodeSocketVector", "Normal"),
        ("NodeSocketFloat", "Layer Alpha"),
        ("NodeSocketFloat", "Color Alpha"),
        ("NodeSocketFloat", "Edge Mask"),
    )
    outputs = (("NodeSocketFloat", "Alpha"),)

    def build(group):
        group_in = create_node(group.nodes, "NodeGroupInput", (-900, 0))
        group_out = create_node(group.nodes, "NodeGroupOutput", (500, 0))
        camera_point = create_node(
            group.nodes, "ShaderNodeVectorTransform", (-720, 160)
        )
        camera_point.inputs["Vector"].default_value = (0, 0, 0)
        camera_point.convert_from = "CAMERA"
        camera_point.convert_to = "WORLD"
        camera_point.vector_type = "POINT"
        to_camera = shader_nodes.vector_math(
            group.nodes, group.links, "SUBTRACT", location=(-540, 160), hide=True
        ).node
        normalize = shader_nodes.vector_math(
            group.nodes, group.links, "NORMALIZE", location=(-360, 160), hide=True
        ).node
        dot = shader_nodes.vector_math(
            group.nodes, group.links, "DOT_PRODUCT", location=(-180, 160), hide=True
        ).node
        facing = shader_nodes.math(
            group.nodes, group.links, "SUBTRACT", location=(0, 160), hide=True
        ).node
        facing.inputs["Value"].default_value = 1.0
        compare = shader_nodes.math(
            group.nodes, group.links, "COMPARE", location=(-180, -120), hide=True
        ).node
        compare.inputs["Value"].default_value = 1.0
        shader_nodes.socket_by_identifier(
            compare.inputs, "Value_002"
        ).default_value = 0.0
        select = create_node(group.nodes, "ShaderNodeMix", (0, -40))
        select.data_type = "FLOAT"
        shader_nodes.socket_by_identifier(select.inputs, "B_Float").default_value = 1.0
        layer_mul = shader_nodes.math(
            group.nodes, group.links, "MULTIPLY", location=(190, -40), hide=True
        ).node
        edge_mul = shader_nodes.math(
            group.nodes, group.links, "MULTIPLY", location=(350, -40), hide=True
        ).node
        group.links.new(camera_point.outputs["Vector"], to_camera.inputs["Vector"])
        group.links.new(
            group_in.outputs["Position"],
            shader_nodes.socket_by_identifier(to_camera.inputs, "Vector_001"),
        )
        group.links.new(to_camera.outputs["Vector"], normalize.inputs["Vector"])
        group.links.new(group_in.outputs["Normal"], dot.inputs["Vector"])
        group.links.new(
            normalize.outputs["Vector"],
            shader_nodes.socket_by_identifier(dot.inputs, "Vector_001"),
        )
        group.links.new(
            dot.outputs["Value"],
            shader_nodes.socket_by_identifier(facing.inputs, "Value_001"),
        )
        group.links.new(
            group_in.outputs["Color Alpha"],
            shader_nodes.socket_by_identifier(compare.inputs, "Value_001"),
        )
        group.links.new(
            compare.outputs["Value"],
            shader_nodes.socket_by_identifier(select.inputs, "Factor_Float"),
        )
        group.links.new(
            facing.outputs["Value"],
            shader_nodes.socket_by_identifier(select.inputs, "A_Float"),
        )
        group.links.new(group_in.outputs["Layer Alpha"], layer_mul.inputs["Value"])
        group.links.new(
            shader_nodes.socket_by_identifier(select.outputs, "Result_Float"),
            shader_nodes.socket_by_identifier(layer_mul.inputs, "Value_001"),
        )
        group.links.new(group_in.outputs["Edge Mask"], edge_mul.inputs["Value"])
        group.links.new(
            layer_mul.outputs["Value"],
            shader_nodes.socket_by_identifier(edge_mul.inputs, "Value_001"),
        )
        group.links.new(edge_mul.outputs["Value"], group_out.inputs["Alpha"])

    return get_or_build_node_group(
        "CP77 Transparent Screen Facing Alpha v3",
        inputs,
        outputs,
        build,
    )


def _create_final_scroll_delta_group(layer):
    group_name = f"finalScrollUV{layer}_ps_t_v2"
    inputs = (
        ("NodeSocketVector", "finalScrollUV1"),
        ("NodeSocketVector", "l1"),
        ("NodeSocketVector", f"l{layer}"),
    )
    outputs = (("NodeSocketVector", group_name),)

    def build(group):
        group_in = create_node(group.nodes, "NodeGroupInput", (-1050, 0))
        group_out = create_node(group.nodes, "NodeGroupOutput", (-150, 0))
        vec_delta = shader_nodes.vector_math(
            group.nodes, group.links, "SUBTRACT", location=(-900, -25), hide=True
        ).node
        vec_add = shader_nodes.vector_math(
            group.nodes, group.links, "ADD", location=(-750, 0), hide=True
        ).node
        group.links.new(group_in.outputs[f"l{layer}"], vec_delta.inputs["Vector"])
        group.links.new(
            group_in.outputs["l1"],
            shader_nodes.socket_by_identifier(vec_delta.inputs, "Vector_001"),
        )
        group.links.new(group_in.outputs["finalScrollUV1"], vec_add.inputs["Vector"])
        group.links.new(
            vec_delta.outputs["Vector"],
            shader_nodes.socket_by_identifier(vec_add.inputs, "Vector_001"),
        )
        group.links.new(vec_add.outputs["Vector"], group_out.inputs[group_name])

    return get_or_build_node_group(group_name, inputs, outputs, build)


def _create_layer_intensity_group(layer, component, scanline_group, lerp_group):
    group_name = f"i{layer}_ps_t_v4"
    sampled = f"l{layer}Sampled"
    layer_uv = f"l{layer}"
    final_uv = f"finalScrollUV{layer}"
    intensity = f"IntensityPerLayer.{component}"
    inputs = (
        ("NodeSocketVector", sampled),
        ("NodeSocketFloat", "Alpha"),
        ("NodeSocketVector", layer_uv),
        ("NodeSocketVector", final_uv),
        ("NodeSocketFloat", intensity),
        ("NodeSocketBundle", "Effects"),
    )
    outputs = (("NodeSocketBundle", "Layer"),)

    def build(group):
        group_in = create_node(group.nodes, "NodeGroupInput", (-1050, 0))
        group_out = create_node(group.nodes, "NodeGroupOutput", (300, 0))
        vec_mul = shader_nodes.vector_math(
            group.nodes, group.links, "MULTIPLY", location=(-900, 0), hide=True
        ).node
        separate = create_node(group.nodes, "ShaderNodeSeparateXYZ", (-750, -50))
        add = shader_nodes.math(
            group.nodes, group.links, "ADD", location=(-600, -50), hide=True
        ).node
        scanline = create_node(
            group.nodes, "ShaderNodeGroup", (-450, -50), label="scanline"
        )
        scanline.node_tree = scanline_group
        separate2 = create_node(group.nodes, "ShaderNodeSeparateXYZ", (-750, 0))
        add2 = shader_nodes.math(
            group.nodes, group.links, "ADD", location=(-600, 0), hide=True
        ).node
        scanline2 = create_node(
            group.nodes, "ShaderNodeGroup", (-450, 0), label="scanline"
        )
        scanline2.node_tree = scanline_group
        lerp = create_node(group.nodes, "ShaderNodeGroup", (-300, -25), label="lerp")
        lerp.node_tree = lerp_group
        lerp2 = create_node(group.nodes, "ShaderNodeGroup", (-150, 0), label="lerp")
        lerp2.node_tree = lerp_group
        lerp2.inputs["B"].default_value = 1
        vec_mul2 = shader_nodes.vector_math(
            group.nodes, group.links, "MULTIPLY", location=(0, 0), hide=True
        ).node
        mul = shader_nodes.math(
            group.nodes, group.links, "MULTIPLY", location=(-900, -150), hide=True
        ).node
        mul2 = shader_nodes.math(
            group.nodes, group.links, "MULTIPLY", location=(0, -150), hide=True
        ).node
        bundle = combine_bundle_node(
            group,
            _LAYER_SAMPLE_BUNDLE_ITEMS,
            (160, -40),
            name=f"CP77 Layer {layer} Sample",
            label="Layer Sample",
        )

        effects = separate_bundle_node(
            group,
            _SCREEN_EFFECTS_BUNDLE_ITEMS,
            (-900, -300),
            name=f"CP77 Layer {layer} Effects",
            label="Screen Effects",
        )
        group.links.new(group_in.outputs["Effects"], effects.inputs["Bundle"])

        group.links.new(group_in.outputs[sampled], vec_mul.inputs["Vector"])
        group.links.new(
            group_in.outputs[intensity],
            shader_nodes.socket_by_identifier(vec_mul.inputs, "Vector_001"),
        )
        group.links.new(group_in.outputs[final_uv], separate.inputs["Vector"])
        group.links.new(separate.outputs["Y"], add.inputs["Value"])
        group.links.new(
            effects.outputs["Scanline Phase"],
            shader_nodes.socket_by_identifier(add.inputs, "Value_001"),
        )
        group.links.new(effects.outputs["Scanline Density"], scanline.inputs["density"])
        group.links.new(add.outputs["Value"], scanline.inputs["uv"])
        group.links.new(group_in.outputs[layer_uv], separate2.inputs["Vector"])
        group.links.new(separate2.outputs["Y"], add2.inputs["Value"])
        group.links.new(
            effects.outputs["Scanline Phase"],
            shader_nodes.socket_by_identifier(add2.inputs, "Value_001"),
        )
        group.links.new(
            effects.outputs["Scanline Density"], scanline2.inputs["density"]
        )
        group.links.new(add2.outputs["Value"], scanline2.inputs["uv"])
        group.links.new(scanline.outputs["result"], lerp.inputs["A"])
        group.links.new(scanline2.outputs["result"], lerp.inputs["B"])
        group.links.new(effects.outputs["Scroll Mask"], lerp.inputs["t"])
        group.links.new(effects.outputs["Scanline Intensity"], lerp2.inputs["A"])
        group.links.new(lerp.outputs["result"], lerp2.inputs["t"])
        group.links.new(vec_mul.outputs["Vector"], vec_mul2.inputs["Vector"])
        group.links.new(
            lerp2.outputs["result"],
            shader_nodes.socket_by_identifier(vec_mul2.inputs, "Vector_001"),
        )
        group.links.new(group_in.outputs["Alpha"], mul.inputs["Value"])
        group.links.new(
            group_in.outputs[intensity],
            shader_nodes.socket_by_identifier(mul.inputs, "Value_001"),
        )
        group.links.new(mul.outputs["Value"], mul2.inputs["Value"])
        group.links.new(
            lerp2.outputs["result"],
            shader_nodes.socket_by_identifier(mul2.inputs, "Value_001"),
        )
        group.links.new(vec_mul2.outputs["Vector"], bundle.inputs["Color"])
        group.links.new(mul2.outputs["Value"], bundle.inputs["Alpha"])
        group.links.new(bundle.outputs["Bundle"], group_out.inputs["Layer"])

    return get_or_build_node_group(group_name, inputs, outputs, build)


def _create_m_group(group_name, output_name, input_a, input_b):
    cached_group_name = f"{group_name}_bundle_v3"
    inputs = (
        ("NodeSocketBundle", "Layer A"),
        ("NodeSocketBundle", "Layer B"),
    )
    outputs = (("NodeSocketBundle", "Layer"),)

    def build(group):
        group_in = create_node(group.nodes, "NodeGroupInput", (-1050, 0))
        group_out = create_node(group.nodes, "NodeGroupOutput", (350, 0))
        layer_a = separate_bundle_node(
            group,
            _LAYER_SAMPLE_BUNDLE_ITEMS,
            (-900, 80),
            name="CP77 Layer A",
            label=input_a,
        )
        layer_b = separate_bundle_node(
            group,
            _LAYER_SAMPLE_BUNDLE_ITEMS,
            (-900, -100),
            name="CP77 Layer B",
            label=input_b,
        )
        result = combine_bundle_node(
            group,
            _LAYER_SAMPLE_BUNDLE_ITEMS,
            (180, 0),
            name="CP77 Layer Result",
            label=output_name,
        )
        group.links.new(group_in.outputs["Layer A"], layer_a.inputs["Bundle"])
        group.links.new(group_in.outputs["Layer B"], layer_b.inputs["Bundle"])

        vec_sub = shader_nodes.vector_math(
            group.nodes, group.links, "SUBTRACT", location=(-700, 80), hide=True
        ).node
        vec_sub.inputs["Vector"].default_value = (1, 1, 1)
        vec_sub2 = shader_nodes.vector_math(
            group.nodes, group.links, "SUBTRACT", location=(-700, -20), hide=True
        ).node
        vec_sub2.inputs["Vector"].default_value = (1, 1, 1)
        vec_mul = shader_nodes.vector_math(
            group.nodes, group.links, "MULTIPLY", location=(-500, 50), hide=True
        ).node
        vec_out = shader_nodes.vector_math(
            group.nodes, group.links, "SUBTRACT", location=(-300, 50), hide=True
        ).node
        vec_out.inputs["Vector"].default_value = (1, 1, 1)
        group.links.new(
            layer_a.outputs["Color"],
            shader_nodes.socket_by_identifier(vec_sub.inputs, "Vector_001"),
        )
        group.links.new(
            layer_b.outputs["Color"],
            shader_nodes.socket_by_identifier(vec_sub2.inputs, "Vector_001"),
        )
        group.links.new(vec_sub.outputs["Vector"], vec_mul.inputs["Vector"])
        group.links.new(
            vec_sub2.outputs["Vector"],
            shader_nodes.socket_by_identifier(vec_mul.inputs, "Vector_001"),
        )
        group.links.new(
            vec_mul.outputs["Vector"],
            shader_nodes.socket_by_identifier(vec_out.inputs, "Vector_001"),
        )

        sub = shader_nodes.math(
            group.nodes, group.links, "SUBTRACT", location=(-700, -180), hide=True
        ).node
        sub.inputs["Value"].default_value = 1
        sub2 = shader_nodes.math(
            group.nodes, group.links, "SUBTRACT", location=(-700, -240), hide=True
        ).node
        sub2.inputs["Value"].default_value = 1
        mul = shader_nodes.math(
            group.nodes, group.links, "MULTIPLY", location=(-500, -210), hide=True
        ).node
        sub3 = shader_nodes.math(
            group.nodes, group.links, "SUBTRACT", location=(-300, -210), hide=True
        ).node
        sub3.inputs["Value"].default_value = 1
        group.links.new(
            layer_a.outputs["Alpha"],
            shader_nodes.socket_by_identifier(sub.inputs, "Value_001"),
        )
        group.links.new(
            layer_b.outputs["Alpha"],
            shader_nodes.socket_by_identifier(sub2.inputs, "Value_001"),
        )
        group.links.new(sub.outputs["Value"], mul.inputs["Value"])
        group.links.new(
            sub2.outputs["Value"],
            shader_nodes.socket_by_identifier(mul.inputs, "Value_001"),
        )
        group.links.new(
            mul.outputs["Value"],
            shader_nodes.socket_by_identifier(sub3.inputs, "Value_001"),
        )
        group.links.new(vec_out.outputs["Vector"], result.inputs["Color"])
        group.links.new(sub3.outputs["Value"], result.inputs["Alpha"])
        group.links.new(result.outputs["Bundle"], group_out.inputs["Layer"])

    return get_or_build_node_group(cached_group_name, inputs, outputs, build)


def _create_alpha_blend_group(group_name, output_name, input_a, input_b):
    cached_group_name = f"{group_name}_alpha_bundle_v4"
    inputs = (
        ("NodeSocketBundle", "Layer A"),
        ("NodeSocketBundle", "Layer B"),
    )
    outputs = (("NodeSocketBundle", "Layer"),)

    def build(group):
        group_in = create_node(group.nodes, "NodeGroupInput", (-720, 0))
        group_out = create_node(group.nodes, "NodeGroupOutput", (260, 0))
        layer_a = separate_bundle_node(
            group,
            _LAYER_SAMPLE_BUNDLE_ITEMS,
            (-560, 100),
            name="CP77 Alpha Layer A",
            label=input_a,
        )
        layer_b = separate_bundle_node(
            group,
            _LAYER_SAMPLE_BUNDLE_ITEMS,
            (-560, -100),
            name="CP77 Alpha Layer B",
            label=input_b,
        )
        result = combine_bundle_node(
            group,
            _LAYER_SAMPLE_BUNDLE_ITEMS,
            (100, 0),
            name="CP77 Alpha Layer Result",
            label=output_name,
        )
        group.links.new(group_in.outputs["Layer A"], layer_a.inputs["Bundle"])
        group.links.new(group_in.outputs["Layer B"], layer_b.inputs["Bundle"])

        color = create_node(
            group.nodes, "ShaderNodeMix", (-360, 80), label="Alpha Layer Lerp"
        )
        color.data_type = "VECTOR"
        group.links.new(
            layer_b.outputs["Alpha"],
            shader_nodes.socket_by_identifier(color.inputs, "Factor_Float"),
        )
        group.links.new(
            layer_a.outputs["Color"],
            shader_nodes.socket_by_identifier(color.inputs, "A_Vector"),
        )
        group.links.new(
            layer_b.outputs["Color"],
            shader_nodes.socket_by_identifier(color.inputs, "B_Vector"),
        )

        delta = shader_nodes.math(
            group.nodes, group.links, "SUBTRACT", location=(-360, -120), hide=True
        ).node
        group.links.new(layer_b.outputs["Alpha"], delta.inputs["Value"])
        group.links.new(
            layer_a.outputs["Alpha"],
            shader_nodes.socket_by_identifier(delta.inputs, "Value_001"),
        )
        weighted = shader_nodes.math(
            group.nodes, group.links, "MULTIPLY", location=(-200, -120), hide=True
        ).node
        group.links.new(delta.outputs["Value"], weighted.inputs["Value"])
        group.links.new(
            layer_b.outputs["Alpha"],
            shader_nodes.socket_by_identifier(weighted.inputs, "Value_001"),
        )
        alpha = shader_nodes.math(
            group.nodes, group.links, "ADD", location=(-40, -120), hide=True
        ).node
        group.links.new(layer_a.outputs["Alpha"], alpha.inputs["Value"])
        group.links.new(
            weighted.outputs["Value"],
            shader_nodes.socket_by_identifier(alpha.inputs, "Value_001"),
        )
        group.links.new(
            shader_nodes.socket_by_identifier(color.outputs, "Result_Vector"),
            result.inputs["Color"],
        )
        group.links.new(alpha.outputs["Value"], result.inputs["Alpha"])
        group.links.new(result.outputs["Bundle"], group_out.inputs["Layer"])

    return get_or_build_node_group(cached_group_name, inputs, outputs, build)


_VALUE_SPECS = (
    (
        "SeparateLayersFromTexture",
        "SeparateLayersFromTexture",
        500,
        "SeparateLayersFromTexture",
        0.0,
    ),
    ("LayersSeparation", "LayersSeparation", 650, "LayersSeparation", 0.0199999996),
    ("ScanlinesSpeed", "ScanlinesSpeed", 150, "ScanlinesSpeed", 0.0),
    ("TilesWidth", "TilesWidth", 100, "TilesWidth", 1.0),
    ("TilesHeight", "TilesHeight", 50, "TilesHeight", 1.0),
    ("PlaySpeed", "PlaySpeed", 0, "PlaySpeed", 0.0),
    ("InterlaceLines", "InterlaceLines", -100, "InterlaceLines", 0.0),
    ("TextureOffsetX", "TextureOffsetX", -150, "TextureOffsetX", 0.0),
    ("TextureOffsetY", "TextureOffsetY", -200, "TextureOffsetY", 0.0),
    ("ScrollSpeed1", "ScrollSpeed1", -350, "ScrollSpeed1", 0.5),
    ("ScrollStepFactor1", "ScrollStepFactor1", -400, "ScrollStepFactor1", 60.0),
    ("ScrollMaskHeight1", "ScrollMaskHeight1", -450, "ScrollMaskHeight1", 0.25),
    (
        "ScrollMaskStartPoint1",
        "ScrollMaskStartPoint1",
        -500,
        "ScrollMaskStartPoint1",
        0.0,
    ),
    ("ScrollSpeed2", "ScrollSpeed2", -550, "ScrollSpeed2", 1.0),
    ("ScrollStepFactor2", "ScrollStepFactor2", -600, "ScrollStepFactor2", 60.0),
    ("ScrollMaskHeight2", "ScrollMaskHeight2", -650, "ScrollMaskHeight2", 0.100000001),
    (
        "ScrollMaskStartPoint2",
        "ScrollMaskStartPoint2",
        -700,
        "ScrollMaskStartPoint2",
        0.0,
    ),
    (
        "ScrollVerticalOrHorizontal",
        "ScrollVerticalOrHorizontal",
        -750,
        "ScrollVerticalOrHorizontal",
        1.0,
    ),
    ("ScanlinesIntensity", "ScanlinesIntensity", -1000, "ScanlinesIntensity", 0.0),
    ("ScanlinesDensity", "ScanlinesDensity", -1050, "ScanlinesDensity", 0.0),
    ("Emissive", "Emissive", -1100, "Emissive", 1.0),
    ("EdgesMask", "EdgesMask", -1400, "EdgesMask", 0.0),
)
# Vector parameters read one Value node per component: (parameter, default, ((component, x, y), ...)).
_COMPONENT_SPECS = (
    (
        "LayersScrollSpeed",
        0.0,
        (("X", -2000, 450), ("Y", -2000, 500), ("Z", -2000, 550), ("W", -2000, 600)),
    ),
    ("ImageScale", 1.0, (("X", -2000, -250), ("Y", -2000, -300))),
    (
        "IntensityPerLayer",
        (1.0, 0.349999994, 0.119999997, 0.0500000007),
        (
            ("X", -2000, -800),
            ("Y", -2000, -850),
            ("Z", -2000, -900),
            ("W", -2000, -950),
        ),
    ),
    (
        "TexHSVControl",
        (0.0, 1.0, 1.0, 0.0),
        (("X", -2000, -1150), ("Y", -2000, -1200), ("Z", -2000, -1250)),
    ),
)


def _alpha_blended(Data):
    return param_float(Data, "AdditiveOrAlphaBlened", 0.0) >= 0.5


class ParallaxScreenTransparent(MaterialTypeBase):
    texture_defaults = {
        "ScrollMaskTexture": r"engine\textures\editor\black.xbm",
        "ParalaxTexture": r"base\fx\textures\other\elevator_l1.xbm",
    }

    def _images(self, Data):
        """The scroll mask and the parallax texture"""
        return tuple(
            self._image_from_rel_path(self._texture_path(Data, key))
            for key in ("ScrollMaskTexture", "ParalaxTexture")
        )

    @staticmethod
    def _values(Data):
        """Each Value and RGB node's value, by structure slot"""
        values = {
            f"value:{var_name}": float(value)
            for var_name, _y, _label, value in param_value_rows(
                scalar_parameter_data(Data, _VALUE_SPECS), _VALUE_SPECS
            )
        }
        for key, default, components in _COMPONENT_SPECS:
            source = Data.get(key)
            for component, _x, _y in components:
                fallback = (
                    default[("X", "Y", "Z", "W").index(component)]
                    if isinstance(default, tuple)
                    else default
                )
                values[f"{key}.{component.lower()}"] = float(
                    component_value(source, component, fallback)
                )
        color = Data.get("Color")
        if "Color" in Data:
            values["Color"] = tuple(
                float(color[channel]) / 255
                for channel in ("Red", "Green", "Blue", "Alpha")
            )
            values["Color.a"] = scalar_value(color.get("Alpha"), 255.0, "Alpha") / 255.0
        else:
            values["Color"], values["Color.a"] = (1.0, 1.0, 1.0, 1.0), 1.0
        values["ClampUV"] = float(param_float(Data, "ClampUV", 1.0))
        values["AdditiveAlphaBlend"] = float(
            param_float(Data, "AdditiveAlphaBlend", 0.0)
        )
        return values

    def structure_key(self, Data):
        # Whether a colour is authored, the blend mode and which textures load shape the graph; the build reads every
        # other parameter into a Value or RGB node.
        return (
            "Color" in Data,
            _alpha_blended(Data),
            *(image is not None for image in self._images(Data)),
        )

    def apply_structure_values(self, Data, Mat, slots):
        nodes = Mat.node_tree.nodes
        write_slot_values(nodes, slots, self._values(Data))
        for slot, image in zip(("image:scroll", "image:parallax"), self._images(Data)):
            for name in slots[slot]:
                node = nodes[name]
                if node.image is not image:
                    node.image = image

    def createScanlinesGroup(self):

        def build(group):
            group_in = create_node(group.nodes, "NodeGroupInput", (-1400, 0))
            group_out = create_node(group.nodes, "NodeGroupOutput", (-200, 0))
            mul = shader_nodes.math(
                group.nodes, group.links, "MULTIPLY", location=(-1200, 0), hide=True
            ).node
            cos = shader_nodes.math(
                group.nodes, group.links, "COSINE", location=(-1000, 0), hide=True
            ).node
            div = shader_nodes.math(
                group.nodes, group.links, "DIVIDE", location=(-800, 0), hide=True
            ).node
            shader_nodes.socket_by_identifier(div.inputs, "Value_001").default_value = 2
            add = shader_nodes.math(
                group.nodes, group.links, "ADD", location=(-800, 0), hide=True
            ).node
            shader_nodes.socket_by_identifier(add.inputs, "Value_001").default_value = 1
            group.links.new(
                group_in.outputs["density"],
                shader_nodes.socket_by_identifier(mul.inputs, "Value_001"),
            )
            group.links.new(group_in.outputs["uv"], mul.inputs["Value"])
            group.links.new(mul.outputs["Value"], cos.inputs["Value"])
            group.links.new(cos.outputs["Value"], add.inputs["Value"])
            group.links.new(add.outputs["Value"], div.inputs["Value"])
            group.links.new(div.outputs["Value"], group_out.inputs["result"])

        return get_or_build_node_group(
            "CP77 Transparent Screen scanlines v1",
            (("NodeSocketFloat", "density"), ("NodeSocketFloat", "uv")),
            (("NodeSocketFloat", "result"),),
            build,
        )

    def create(self, Data, Mat):
        CurMat = Mat.node_tree
        pBSDF = shader_nodes.principled_bsdf(CurMat.nodes)
        CurMat.nodes.remove(pBSDF)

        values = self._values(Data)
        value_nodes = create_param_value_nodes(
            CurMat, scalar_parameter_data(Data, _VALUE_SPECS), _VALUE_SPECS
        )
        slots = self.structure_slots = {
            f"value:{var_name}": (node.name, None)
            for var_name, node in value_nodes.items()
        }
        component_nodes = {}
        for key, _default, components in _COMPONENT_SPECS:
            for component, x, y in components:
                slot = f"{key}.{component.lower()}"
                component_nodes[(key, component)] = node = CreateShaderNodeValue(
                    CurMat, values[slot], x, y, slot
                )
                slots[slot] = (node.name, None)

        separateLayersFromTex = value_nodes.get("SeparateLayersFromTexture")
        layersSeparation = value_nodes.get("LayersSeparation")
        scanlinesSpeed = value_nodes.get("ScanlinesSpeed")
        tilesW = value_nodes.get("TilesWidth")
        tilesH = value_nodes.get("TilesHeight")
        playSpeed = value_nodes.get("PlaySpeed")
        iLines = value_nodes.get("InterlaceLines")
        textureOffsetX = value_nodes.get("TextureOffsetX")
        textureOffsetY = value_nodes.get("TextureOffsetY")
        scrollSpeed1 = value_nodes.get("ScrollSpeed1")
        scrollStepFactor1 = value_nodes.get("ScrollStepFactor1")
        scrollMaskHeight1 = value_nodes.get("ScrollMaskHeight1")
        scrollMaskStartPoint1 = value_nodes.get("ScrollMaskStartPoint1")
        scrollSpeed2 = value_nodes.get("ScrollSpeed2")
        scrollStepFactor2 = value_nodes.get("ScrollStepFactor2")
        scrollMaskHeight2 = value_nodes.get("ScrollMaskHeight2")
        scrollMaskStartPoint2 = value_nodes.get("ScrollMaskStartPoint2")
        scrollVerticalOrHorizontal = value_nodes.get("ScrollVerticalOrHorizontal")
        scanlinesIntensity = value_nodes.get("ScanlinesIntensity")
        scanlinesDensity = value_nodes.get("ScanlinesDensity")
        emissive = value_nodes.get("Emissive")
        edgesMaskValue = value_nodes.get("EdgesMask")
        layersScrollSpeed_x = component_nodes.get(("LayersScrollSpeed", "X"))
        layersScrollSpeed_y = component_nodes.get(("LayersScrollSpeed", "Y"))
        layersScrollSpeed_z = component_nodes.get(("LayersScrollSpeed", "Z"))
        layersScrollSpeed_w = component_nodes.get(("LayersScrollSpeed", "W"))
        imageScale_x = component_nodes.get(("ImageScale", "X"))
        imageScale_y = component_nodes.get(("ImageScale", "Y"))
        intensityPerLayer_x = component_nodes.get(("IntensityPerLayer", "X"))
        intensityPerLayer_y = component_nodes.get(("IntensityPerLayer", "Y"))
        intensityPerLayer_z = component_nodes.get(("IntensityPerLayer", "Z"))
        intensityPerLayer_w = component_nodes.get(("IntensityPerLayer", "W"))
        texHSVControl_x = component_nodes.get(("TexHSVControl", "X"))
        texHSVControl_y = component_nodes.get(("TexHSVControl", "Y"))
        texHSVControl_z = component_nodes.get(("TexHSVControl", "Z"))

        if "Color" in Data:
            color = CreateShaderNodeRGB(CurMat, Data["Color"], -2000, -1300, "Color")
        else:
            color = create_node(
                CurMat.nodes, "ShaderNodeRGB", (-2000, -1300), label="Color"
            )
            color.outputs["Color"].default_value = values["Color"]
        color_a = CreateShaderNodeValue(
            CurMat, values["Color.a"], -2000, -1350, "Color.a"
        )
        slots["Color"], slots["Color.a"] = (color.name, None), (color_a.name, None)

        scrollMaskImg, parImg = self._images(Data)

        tangent = cp77_uv_tangent_node(
            CurMat.nodes, (-2000, 400), label="Parallax Screen Tangent"
        )
        geometry = create_node(CurMat.nodes, "ShaderNodeNewGeometry", (-2000, 300))
        UVMap = create_node(CurMat.nodes, "ShaderNodeUVMap", (-2000, 200))

        vecCross = cp77_bitangent_socket(
            CurMat.nodes,
            CurMat.links,
            geometry.outputs["Normal"],
            tangent.outputs["Tangent"],
            (-1850, 350),
            label="Parallax Screen Binormal",
        )

        cameraForward = create_camera_forward_vector(CurMat, location=(-1850, 250))

        view_basis_group = _create_view_basis_group()
        view_basis = add_group_node(
            CurMat,
            view_basis_group,
            (-1450, 175),
            label="Parallax View Basis",
            name="CP77 Parallax View Basis",
        )
        CurMat.links.new(cameraForward, view_basis.inputs["Camera Forward"])
        CurMat.links.new(tangent.outputs["Tangent"], view_basis.inputs["Tangent"])
        CurMat.links.new(vecCross, view_basis.inputs["Bitangent"])

        time = CreateShaderNodeValue(CurMat, 1, -2000, -50, "Time")
        timeDriver = time.outputs["Value"].driver_add("default_value")
        set_scene_fps_driver(timeDriver.driver)

        vecLerpG = createVecLerpGroup()

        gamma = create_node(CurMat.nodes, "ShaderNodeGamma", (-1800, -1300))
        gamma.inputs["Gamma"].default_value = 2
        CurMat.links.new(color.outputs["Color"], gamma.inputs["Color"])

        ngroup = bpy.data.node_groups.get("CP77 Transparent Screen n_ps_t v1")
        if ngroup is None:
            ngroup = new_tracked_datablock(
                "node_groups", "CP77 Transparent Screen n_ps_t v1", "ShaderNodeTree"
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

        n = create_node(CurMat.nodes, "ShaderNodeGroup", (-1700, 75), label="n_ps_t")
        n.node_tree = ngroup

        CurMat.links.new(tilesW.outputs["Value"], n.inputs["TilesWidth"])
        CurMat.links.new(tilesH.outputs["Value"], n.inputs["TilesHeight"])
        CurMat.links.new(playSpeed.outputs["Value"], n.inputs["PlaySpeed"])
        CurMat.links.new(time.outputs["Value"], n.inputs["Time"])

        frameGroup = bpy.data.node_groups.get(
            "CP77 Transparent Screen frameAdd_ps_t v1"
        )
        if frameGroup is None:
            frameGroup = new_tracked_datablock(
                "node_groups",
                "CP77 Transparent Screen frameAdd_ps_t v1",
                "ShaderNodeTree",
            )
            frameGroup.interface.new_socket(
                name="UV", socket_type="NodeSocketVector", in_out="INPUT"
            )
            frameGroup.interface.new_socket(
                name="n", socket_type="NodeSocketFloat", in_out="INPUT"
            )
            frameGroup.interface.new_socket(
                name="InterlaceLines", socket_type="NodeSocketFloat", in_out="INPUT"
            )
            frameGroup.interface.new_socket(
                name="frameAdd", socket_type="NodeSocketFloat", in_out="OUTPUT"
            )
            fGroupInput = create_node(frameGroup.nodes, "NodeGroupInput", (-1400, 0))
            fGroupOutput = create_node(frameGroup.nodes, "NodeGroupOutput", (200, 0))

            UVSeparate = create_node(
                frameGroup.nodes, "ShaderNodeSeparateXYZ", (-1300, 100)
            )
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
            shader_nodes.socket_by_identifier(mod.inputs, "Value_001").default_value = 1
            add = shader_nodes.math(
                frameGroup.nodes,
                frameGroup.links,
                "ADD",
                location=(-600, 125),
                hide=True,
            ).node
            shader_nodes.socket_by_identifier(
                add.inputs, "Value_001"
            ).default_value = 0.5
            mod2 = shader_nodes.math(
                frameGroup.nodes,
                frameGroup.links,
                "MODULO",
                location=(-900, 75),
                hide=True,
            ).node
            shader_nodes.socket_by_identifier(
                mod2.inputs, "Value_001"
            ).default_value = 1
            add2 = shader_nodes.math(
                frameGroup.nodes,
                frameGroup.links,
                "ADD",
                location=(-750, 75),
                hide=True,
            ).node
            shader_nodes.socket_by_identifier(
                add2.inputs, "Value_001"
            ).default_value = 0.5
            floor = shader_nodes.math(
                frameGroup.nodes,
                frameGroup.links,
                "FLOOR",
                location=(-600, 75),
                hide=True,
            ).node
            add3 = shader_nodes.math(
                frameGroup.nodes,
                frameGroup.links,
                "ADD",
                location=(-450, 125),
                use_clamp=True,
                hide=True,
            ).node
            floor2 = shader_nodes.math(
                frameGroup.nodes,
                frameGroup.links,
                "FLOOR",
                location=(-300, 125),
                hide=True,
            ).node
            frameGroup.links.new(
                fGroupInput.outputs["InterlaceLines"],
                shader_nodes.socket_by_identifier(div2.inputs, "Value_001"),
            )
            frameGroup.links.new(fGroupInput.outputs["UV"], UVSeparate.inputs["Vector"])
            frameGroup.links.new(UVSeparate.outputs["Y"], div2.inputs["Value"])
            frameGroup.links.new(div2.outputs["Value"], mod.inputs["Value"])
            frameGroup.links.new(mod.outputs["Value"], add.inputs["Value"])
            frameGroup.links.new(add.outputs["Value"], floor.inputs["Value"])
            frameGroup.links.new(fGroupInput.outputs["n"], mod2.inputs["Value"])
            frameGroup.links.new(mod2.outputs["Value"], add2.inputs["Value"])
            frameGroup.links.new(add2.outputs["Value"], floor2.inputs["Value"])
            frameGroup.links.new(floor.outputs["Value"], add3.inputs["Value"])
            frameGroup.links.new(
                floor2.outputs["Value"],
                shader_nodes.socket_by_identifier(add3.inputs, "Value_001"),
            )
            frameGroup.links.new(add3.outputs["Value"], fGroupOutput.inputs["frameAdd"])

        frameAdd = create_node(
            CurMat.nodes, "ShaderNodeGroup", (-1500, 75), label="frameAdd_ps_t"
        )
        frameAdd.node_tree = frameGroup

        CurMat.links.new(iLines.outputs["Value"], frameAdd.inputs["InterlaceLines"])
        CurMat.links.new(UVMap.outputs["UV"], frameAdd.inputs["UV"])
        CurMat.links.new(n.outputs["n"], frameAdd.inputs["n"])

        subUVGroup = bpy.data.node_groups.get("CP77 Transparent Screen subUV v1")
        if subUVGroup is None:
            subUVGroup = new_tracked_datablock(
                "node_groups", "CP77 Transparent Screen subUV v1", "ShaderNodeTree"
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
                subUVGroup.nodes,
                subUVGroup.links,
                "DIVIDE",
                location=(-900, 0),
                hide=True,
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
                subUVGroup.nodes,
                subUVGroup.links,
                "ADD",
                location=(-800, -100),
                hide=True,
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
                subUVGroup.nodes,
                subUVGroup.links,
                "ADD",
                location=(-500, -250),
                hide=True,
            ).node
            add6 = shader_nodes.math(
                subUVGroup.nodes,
                subUVGroup.links,
                "ADD",
                location=(-750, -250),
                hide=True,
            ).node
            sub2 = shader_nodes.math(
                subUVGroup.nodes,
                subUVGroup.links,
                "SUBTRACT",
                location=(-500, -150),
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
            subUVGroup.links.new(add5.outputs["Value"], combine.inputs["X"])
            sub2.inputs["Value"].default_value = 1.0
            subUVGroup.links.new(
                add6.outputs["Value"],
                shader_nodes.socket_by_identifier(sub2.inputs, "Value_001"),
            )
            subUVGroup.links.new(sub2.outputs["Value"], combine.inputs["Y"])
            subUVGroup.links.new(combine.outputs["Vector"], subUVGroupO.inputs["subUV"])

        subUV = create_node(CurMat.nodes, "ShaderNodeGroup", (-1350, 75), label="subUV")
        subUV.node_tree = subUVGroup
        subUV.name = "subUV"

        CurMat.links.new(tilesW.outputs["Value"], subUV.inputs["TilesWidth"])
        CurMat.links.new(tilesH.outputs["Value"], subUV.inputs["TilesHeight"])
        CurMat.links.new(UVMap.outputs["UV"], subUV.inputs["UV"])
        CurMat.links.new(n.outputs["n"], subUV.inputs["n"])
        CurMat.links.new(frameAdd.outputs["frameAdd"], subUV.inputs["frameAdd"])

        newUVGroup = bpy.data.node_groups.get("CP77 Transparent Screen newUV_ps_t v1")

        if newUVGroup is None:
            newUVGroup = new_tracked_datablock(
                "node_groups", "CP77 Transparent Screen newUV_ps_t v1", "ShaderNodeTree"
            )
            newUVGroup.interface.new_socket(
                name="subUV", socket_type="NodeSocketVector", in_out="INPUT"
            )
            newUVGroup.interface.new_socket(
                name="TextureOffsetX", socket_type="NodeSocketFloat", in_out="INPUT"
            )
            newUVGroup.interface.new_socket(
                name="TextureOffsetY", socket_type="NodeSocketFloat", in_out="INPUT"
            )
            newUVGroup.interface.new_socket(
                name="ImageScale.x", socket_type="NodeSocketFloat", in_out="INPUT"
            )
            newUVGroup.interface.new_socket(
                name="ImageScale.y", socket_type="NodeSocketFloat", in_out="INPUT"
            )
            newUVGroup.interface.new_socket(
                name="newUV", socket_type="NodeSocketVector", in_out="OUTPUT"
            )
            newUVGroupI = create_node(newUVGroup.nodes, "NodeGroupInput", (-1400, 0))
            newUVGroupO = create_node(newUVGroup.nodes, "NodeGroupOutput", (-300, 0))
            vecSub = shader_nodes.vector_math(
                newUVGroup.nodes,
                newUVGroup.links,
                "SUBTRACT",
                location=(-1200, 25),
                hide=True,
            ).node
            shader_nodes.socket_by_identifier(
                vecSub.inputs, "Vector_001"
            ).default_value = (0.5, 0.5, 0.5)
            combine2 = create_node(
                newUVGroup.nodes, "ShaderNodeCombineXYZ", (-1200, -25)
            )
            vecAdd = shader_nodes.vector_math(
                newUVGroup.nodes,
                newUVGroup.links,
                "ADD",
                location=(-1050, 0),
                hide=True,
            ).node
            combine3 = create_node(
                newUVGroup.nodes, "ShaderNodeCombineXYZ", (-1050, -75)
            )
            vecMul2 = shader_nodes.vector_math(
                newUVGroup.nodes,
                newUVGroup.links,
                "MULTIPLY",
                location=(-900, -50),
                hide=True,
            ).node
            vecAdd2 = shader_nodes.vector_math(
                newUVGroup.nodes, newUVGroup.links, "ADD", location=(-750, 0), hide=True
            ).node
            shader_nodes.socket_by_identifier(
                vecAdd2.inputs, "Vector_001"
            ).default_value = (0.5, 0.5, 0.5)
            vecFrac = shader_nodes.vector_math(
                newUVGroup.nodes,
                newUVGroup.links,
                "FRACTION",
                location=(-500, 0),
                hide=True,
            ).node
            newUVGroup.links.new(newUVGroupI.outputs["subUV"], vecSub.inputs["Vector"])
            newUVGroup.links.new(
                newUVGroupI.outputs["TextureOffsetX"], combine2.inputs["X"]
            )
            newUVGroup.links.new(
                newUVGroupI.outputs["TextureOffsetY"], combine2.inputs["Y"]
            )
            newUVGroup.links.new(
                newUVGroupI.outputs["ImageScale.x"], combine3.inputs["X"]
            )
            newUVGroup.links.new(
                newUVGroupI.outputs["ImageScale.y"], combine3.inputs["Y"]
            )
            newUVGroup.links.new(vecSub.outputs["Vector"], vecAdd.inputs["Vector"])
            newUVGroup.links.new(
                combine2.outputs["Vector"],
                shader_nodes.socket_by_identifier(vecAdd.inputs, "Vector_001"),
            )
            newUVGroup.links.new(vecAdd.outputs["Vector"], vecMul2.inputs["Vector"])
            newUVGroup.links.new(
                combine3.outputs["Vector"],
                shader_nodes.socket_by_identifier(vecMul2.inputs, "Vector_001"),
            )
            newUVGroup.links.new(vecMul2.outputs["Vector"], vecAdd2.inputs["Vector"])
            newUVGroup.links.new(vecAdd2.outputs["Vector"], vecFrac.inputs["Vector"])
            newUVGroup.links.new(vecFrac.outputs["Vector"], newUVGroupO.inputs["newUV"])

        newUV = create_node(
            CurMat.nodes, "ShaderNodeGroup", (-1200, 75), label="newUV_ps_t"
        )
        newUV.node_tree = newUVGroup
        newUV.name = "newUV_ps_t"

        CurMat.links.new(subUV.outputs["subUV"], newUV.inputs["subUV"])
        CurMat.links.new(
            textureOffsetX.outputs["Value"], newUV.inputs["TextureOffsetX"]
        )
        CurMat.links.new(
            textureOffsetY.outputs["Value"], newUV.inputs["TextureOffsetY"]
        )
        CurMat.links.new(imageScale_x.outputs["Value"], newUV.inputs["ImageScale.x"])
        CurMat.links.new(imageScale_y.outputs["Value"], newUV.inputs["ImageScale.y"])

        scroll1Group = _create_scroll_group(1)
        scroll1 = add_group_node(
            CurMat,
            scroll1Group,
            (-1500, -200),
            label="scroll1_ps_t",
            name="scroll1_ps_t",
        )
        CurMat.links.new(scrollSpeed1.outputs["Value"], scroll1.inputs["ScrollSpeed1"])
        CurMat.links.new(
            scrollStepFactor1.outputs["Value"], scroll1.inputs["ScrollStepFactor1"]
        )
        CurMat.links.new(time.outputs["Value"], scroll1.inputs["Time"])

        scrollUV1Group = _create_scroll_uv_group(1, False)
        scrollUV1 = add_group_node(
            CurMat,
            scrollUV1Group,
            (-1350, -200),
            label="scrollUV1_ps_t",
            name="scrollUV1_ps_t",
        )
        CurMat.links.new(newUV.outputs["newUV"], scrollUV1.inputs["newUV"])
        CurMat.links.new(
            scrollMaskHeight1.outputs["Value"], scrollUV1.inputs["ScrollMaskHeight1"]
        )
        CurMat.links.new(scroll1.outputs["scroll1"], scrollUV1.inputs["scroll1"])
        CurMat.links.new(
            scrollMaskStartPoint1.outputs["Value"],
            scrollUV1.inputs["ScrollMaskStartPoint1"],
        )

        scrollUV1XGroup = _create_scroll_uv_group(1, True)
        scrollUV1X = add_group_node(
            CurMat,
            scrollUV1XGroup,
            (-1350, -250),
            label="scrollUV1X",
            name="scrollUV1X",
        )
        CurMat.links.new(newUV.outputs["newUV"], scrollUV1X.inputs["newUV"])
        CurMat.links.new(
            scrollMaskHeight1.outputs["Value"], scrollUV1X.inputs["ScrollMaskHeight1"]
        )
        CurMat.links.new(scroll1.outputs["scroll1"], scrollUV1X.inputs["scroll1"])
        CurMat.links.new(
            scrollMaskStartPoint1.outputs["Value"],
            scrollUV1X.inputs["ScrollMaskStartPoint1"],
        )

        scroll2Group = _create_scroll_group(2)
        scroll2 = add_group_node(
            CurMat,
            scroll2Group,
            (-1500, -300),
            label="scroll2_ps_t",
            name="scroll2_ps_t",
        )
        CurMat.links.new(scrollSpeed2.outputs["Value"], scroll2.inputs["ScrollSpeed2"])
        CurMat.links.new(
            scrollStepFactor2.outputs["Value"], scroll2.inputs["ScrollStepFactor2"]
        )
        CurMat.links.new(time.outputs["Value"], scroll2.inputs["Time"])

        scrollUV2Group = _create_scroll_uv_group(2, False)
        scrollUV2 = add_group_node(
            CurMat,
            scrollUV2Group,
            (-1350, -300),
            label="scrollUV2_ps_t",
            name="scrollUV2_ps_t",
        )
        CurMat.links.new(newUV.outputs["newUV"], scrollUV2.inputs["newUV"])
        CurMat.links.new(
            scrollMaskHeight2.outputs["Value"], scrollUV2.inputs["ScrollMaskHeight2"]
        )
        CurMat.links.new(scroll2.outputs["scroll2"], scrollUV2.inputs["scroll2"])
        CurMat.links.new(
            scrollMaskStartPoint2.outputs["Value"],
            scrollUV2.inputs["ScrollMaskStartPoint2"],
        )

        scrollUV2XGroup = _create_scroll_uv_group(2, True)
        scrollUV2X = add_group_node(
            CurMat,
            scrollUV2XGroup,
            (-1350, -350),
            label="scrollUV2X",
            name="scrollUV2X",
        )
        CurMat.links.new(newUV.outputs["newUV"], scrollUV2X.inputs["newUV"])
        CurMat.links.new(
            scrollMaskHeight2.outputs["Value"], scrollUV2X.inputs["ScrollMaskHeight2"]
        )
        CurMat.links.new(scroll2.outputs["scroll2"], scrollUV2X.inputs["scroll2"])
        CurMat.links.new(
            scrollMaskStartPoint2.outputs["Value"],
            scrollUV2X.inputs["ScrollMaskStartPoint2"],
        )

        clamp_uv = CreateShaderNodeValue(
            CurMat, values["ClampUV"], -2000, -1450, "ClampUV"
        )
        slots["ClampUV"] = (clamp_uv.name, None)
        layer_nodes = {}
        for separated in (True, False):
            for index in range(4):
                label = f"l{index + 1}_ps_t" if separated else f"l{index + 1}_2"
                layer = add_group_node(
                    CurMat,
                    _create_layer_uv_group(index, separated),
                    (-950, 500 - index * 80 - (0 if separated else 400)),
                    label=label,
                )
                CurMat.links.new(newUV.outputs["newUV"], layer.inputs["newUV"])
                CurMat.links.new(view_basis.outputs["modUV"], layer.inputs["modUV"])
                CurMat.links.new(
                    layersSeparation.outputs["Value"], layer.inputs["LayersSeparation"]
                )
                CurMat.links.new(clamp_uv.outputs["Value"], layer.inputs["ClampUV"])
                layer_nodes[separated, index] = layer
        l1, l2, l3, l4 = (layer_nodes[True, index] for index in range(4))
        l1_2, l2_2, l3_2, l4_2 = (layer_nodes[False, index] for index in range(4))

        vecMix = create_node(CurMat.nodes, "ShaderNodeMix", (-775, 425))
        vecMix.data_type = "VECTOR"
        vecMix2 = create_node(CurMat.nodes, "ShaderNodeMix", (-775, 375))
        vecMix2.data_type = "VECTOR"
        vecMix3 = create_node(CurMat.nodes, "ShaderNodeMix", (-775, 325))
        vecMix3.data_type = "VECTOR"
        vecMix4 = create_node(CurMat.nodes, "ShaderNodeMix", (-775, 275))
        vecMix4.data_type = "VECTOR"
        CurMat.links.new(
            separateLayersFromTex.outputs["Value"],
            shader_nodes.socket_by_identifier(vecMix.inputs, "Factor_Float"),
        )
        CurMat.links.new(
            l1.outputs["UV"],
            shader_nodes.socket_by_identifier(vecMix.inputs, "B_Vector"),
        )
        CurMat.links.new(
            l1_2.outputs["UV"],
            shader_nodes.socket_by_identifier(vecMix.inputs, "A_Vector"),
        )
        CurMat.links.new(
            separateLayersFromTex.outputs["Value"],
            shader_nodes.socket_by_identifier(vecMix2.inputs, "Factor_Float"),
        )
        CurMat.links.new(
            l2.outputs["UV"],
            shader_nodes.socket_by_identifier(vecMix2.inputs, "B_Vector"),
        )
        CurMat.links.new(
            l2_2.outputs["UV"],
            shader_nodes.socket_by_identifier(vecMix2.inputs, "A_Vector"),
        )
        CurMat.links.new(
            separateLayersFromTex.outputs["Value"],
            shader_nodes.socket_by_identifier(vecMix3.inputs, "Factor_Float"),
        )
        CurMat.links.new(
            l3.outputs["UV"],
            shader_nodes.socket_by_identifier(vecMix3.inputs, "B_Vector"),
        )
        CurMat.links.new(
            l3_2.outputs["UV"],
            shader_nodes.socket_by_identifier(vecMix3.inputs, "A_Vector"),
        )
        CurMat.links.new(
            separateLayersFromTex.outputs["Value"],
            shader_nodes.socket_by_identifier(vecMix4.inputs, "Factor_Float"),
        )
        CurMat.links.new(
            l4.outputs["UV"],
            shader_nodes.socket_by_identifier(vecMix4.inputs, "B_Vector"),
        )
        CurMat.links.new(
            l4_2.outputs["UV"],
            shader_nodes.socket_by_identifier(vecMix4.inputs, "A_Vector"),
        )

        l1ssGroup = bpy.data.node_groups.get("CP77 Transparent Screen l1scrollspeed v1")

        if l1ssGroup is None:
            l1ssGroup = new_tracked_datablock(
                "node_groups",
                "CP77 Transparent Screen l1scrollspeed v1",
                "ShaderNodeTree",
            )
            l1ssGroup.interface.new_socket(
                name="l1", socket_type="NodeSocketVector", in_out="INPUT"
            )
            l1ssGroup.interface.new_socket(
                name="LayersScrollSpeed.x",
                socket_type="NodeSocketFloat",
                in_out="INPUT",
            )
            l1ssGroup.interface.new_socket(
                name="time", socket_type="NodeSocketFloat", in_out="INPUT"
            )
            l1ssGroup.interface.new_socket(
                name="l1scrollspeed", socket_type="NodeSocketVector", in_out="OUTPUT"
            )

            l1ssGroupI = create_node(l1ssGroup.nodes, "NodeGroupInput", (-1000, 0))
            l1ssGroupO = create_node(l1ssGroup.nodes, "NodeGroupOutput", (200, 0))
            separate = create_node(l1ssGroup.nodes, "ShaderNodeSeparateXYZ", (-800, 25))
            mul = shader_nodes.math(
                l1ssGroup.nodes,
                l1ssGroup.links,
                "MULTIPLY",
                location=(-800, -25),
                hide=True,
            ).node
            add = shader_nodes.math(
                l1ssGroup.nodes, l1ssGroup.links, "ADD", location=(-600, 0), hide=True
            ).node
            combine = create_node(l1ssGroup.nodes, "ShaderNodeCombineXYZ", (-400, 0))
            l1ssGroup.links.new(l1ssGroupI.outputs["l1"], separate.inputs["Vector"])
            l1ssGroup.links.new(l1ssGroupI.outputs["time"], mul.inputs["Value"])
            l1ssGroup.links.new(
                l1ssGroupI.outputs["LayersScrollSpeed.x"],
                shader_nodes.socket_by_identifier(mul.inputs, "Value_001"),
            )
            l1ssGroup.links.new(separate.outputs["Y"], add.inputs["Value"])
            l1ssGroup.links.new(
                mul.outputs["Value"],
                shader_nodes.socket_by_identifier(add.inputs, "Value_001"),
            )
            l1ssGroup.links.new(add.outputs["Value"], combine.inputs["Y"])
            l1ssGroup.links.new(separate.outputs["X"], combine.inputs["X"])
            l1ssGroup.links.new(
                combine.outputs["Vector"], l1ssGroupO.inputs["l1scrollspeed"]
            )

        l1ss = create_node(
            CurMat.nodes, "ShaderNodeGroup", (-625, 425), label="l1scrollspeed"
        )
        l1ss.node_tree = l1ssGroup
        CurMat.links.new(
            shader_nodes.socket_by_identifier(vecMix.outputs, "Result_Vector"),
            l1ss.inputs["l1"],
        )
        CurMat.links.new(
            layersScrollSpeed_x.outputs["Value"], l1ss.inputs["LayersScrollSpeed.x"]
        )
        CurMat.links.new(time.outputs["Value"], l1ss.inputs["time"])

        l2ssGroup = bpy.data.node_groups.get("CP77 Transparent Screen l2scrollspeed v1")

        if l2ssGroup is None:
            l2ssGroup = new_tracked_datablock(
                "node_groups",
                "CP77 Transparent Screen l2scrollspeed v1",
                "ShaderNodeTree",
            )
            l2ssGroup.interface.new_socket(
                name="l2", socket_type="NodeSocketVector", in_out="INPUT"
            )
            l2ssGroup.interface.new_socket(
                name="LayersScrollSpeed.y",
                socket_type="NodeSocketFloat",
                in_out="INPUT",
            )
            l2ssGroup.interface.new_socket(
                name="time", socket_type="NodeSocketFloat", in_out="INPUT"
            )
            l2ssGroup.interface.new_socket(
                name="l2scrollspeed", socket_type="NodeSocketVector", in_out="OUTPUT"
            )

            l2ssGroupI = create_node(l2ssGroup.nodes, "NodeGroupInput", (-1000, 0))
            l2ssGroupO = create_node(l2ssGroup.nodes, "NodeGroupOutput", (200, 0))
            separate = create_node(l2ssGroup.nodes, "ShaderNodeSeparateXYZ", (-800, 25))
            mul = shader_nodes.math(
                l2ssGroup.nodes,
                l2ssGroup.links,
                "MULTIPLY",
                location=(-800, -25),
                hide=True,
            ).node
            add = shader_nodes.math(
                l2ssGroup.nodes, l2ssGroup.links, "ADD", location=(-600, 0), hide=True
            ).node
            combine = create_node(l2ssGroup.nodes, "ShaderNodeCombineXYZ", (-400, 0))
            l2ssGroup.links.new(l2ssGroupI.outputs["l2"], separate.inputs["Vector"])
            l2ssGroup.links.new(l2ssGroupI.outputs["time"], mul.inputs["Value"])
            l2ssGroup.links.new(
                l2ssGroupI.outputs["LayersScrollSpeed.y"],
                shader_nodes.socket_by_identifier(mul.inputs, "Value_001"),
            )
            l2ssGroup.links.new(separate.outputs["Y"], add.inputs["Value"])
            l2ssGroup.links.new(
                mul.outputs["Value"],
                shader_nodes.socket_by_identifier(add.inputs, "Value_001"),
            )
            l2ssGroup.links.new(add.outputs["Value"], combine.inputs["Y"])
            l2ssGroup.links.new(separate.outputs["X"], combine.inputs["X"])
            l2ssGroup.links.new(
                combine.outputs["Vector"], l2ssGroupO.inputs["l2scrollspeed"]
            )

        l2ss = create_node(
            CurMat.nodes, "ShaderNodeGroup", (-625, 375), label="l2scrollspeed"
        )
        l2ss.node_tree = l2ssGroup
        CurMat.links.new(
            shader_nodes.socket_by_identifier(vecMix2.outputs, "Result_Vector"),
            l2ss.inputs["l2"],
        )
        CurMat.links.new(
            layersScrollSpeed_y.outputs["Value"], l2ss.inputs["LayersScrollSpeed.y"]
        )
        CurMat.links.new(time.outputs["Value"], l2ss.inputs["time"])

        l3ssGroup = bpy.data.node_groups.get("CP77 Transparent Screen l3scrollspeed v1")

        if l3ssGroup is None:
            l3ssGroup = new_tracked_datablock(
                "node_groups",
                "CP77 Transparent Screen l3scrollspeed v1",
                "ShaderNodeTree",
            )
            l3ssGroup.interface.new_socket(
                name="l3", socket_type="NodeSocketVector", in_out="INPUT"
            )
            l3ssGroup.interface.new_socket(
                name="LayersScrollSpeed.z",
                socket_type="NodeSocketFloat",
                in_out="INPUT",
            )
            l3ssGroup.interface.new_socket(
                name="time", socket_type="NodeSocketFloat", in_out="INPUT"
            )
            l3ssGroup.interface.new_socket(
                name="l3scrollspeed", socket_type="NodeSocketVector", in_out="OUTPUT"
            )

            l3ssGroupI = create_node(l3ssGroup.nodes, "NodeGroupInput", (-1000, 0))
            l3ssGroupO = create_node(l3ssGroup.nodes, "NodeGroupOutput", (200, 0))
            separate = create_node(l3ssGroup.nodes, "ShaderNodeSeparateXYZ", (-800, 25))
            mul = shader_nodes.math(
                l3ssGroup.nodes,
                l3ssGroup.links,
                "MULTIPLY",
                location=(-800, -25),
                hide=True,
            ).node
            add = shader_nodes.math(
                l3ssGroup.nodes, l3ssGroup.links, "ADD", location=(-600, 0), hide=True
            ).node
            combine = create_node(l3ssGroup.nodes, "ShaderNodeCombineXYZ", (-400, 0))
            l3ssGroup.links.new(l3ssGroupI.outputs["l3"], separate.inputs["Vector"])
            l3ssGroup.links.new(l3ssGroupI.outputs["time"], mul.inputs["Value"])
            l3ssGroup.links.new(
                l3ssGroupI.outputs["LayersScrollSpeed.z"],
                shader_nodes.socket_by_identifier(mul.inputs, "Value_001"),
            )
            l3ssGroup.links.new(separate.outputs["Y"], add.inputs["Value"])
            l3ssGroup.links.new(
                mul.outputs["Value"],
                shader_nodes.socket_by_identifier(add.inputs, "Value_001"),
            )
            l3ssGroup.links.new(add.outputs["Value"], combine.inputs["Y"])
            l3ssGroup.links.new(separate.outputs["X"], combine.inputs["X"])
            l3ssGroup.links.new(
                combine.outputs["Vector"], l3ssGroupO.inputs["l3scrollspeed"]
            )

        l3ss = create_node(
            CurMat.nodes, "ShaderNodeGroup", (-625, 325), label="l3scrollspeed"
        )
        l3ss.node_tree = l3ssGroup
        CurMat.links.new(
            shader_nodes.socket_by_identifier(vecMix3.outputs, "Result_Vector"),
            l3ss.inputs["l3"],
        )
        CurMat.links.new(
            layersScrollSpeed_z.outputs["Value"], l3ss.inputs["LayersScrollSpeed.z"]
        )
        CurMat.links.new(time.outputs["Value"], l3ss.inputs["time"])

        l4ssGroup = bpy.data.node_groups.get("CP77 Transparent Screen l4scrollspeed v1")

        if l4ssGroup is None:
            l4ssGroup = new_tracked_datablock(
                "node_groups",
                "CP77 Transparent Screen l4scrollspeed v1",
                "ShaderNodeTree",
            )
            l4ssGroup.interface.new_socket(
                name="l4", socket_type="NodeSocketVector", in_out="INPUT"
            )
            l4ssGroup.interface.new_socket(
                name="LayersScrollSpeed.w",
                socket_type="NodeSocketFloat",
                in_out="INPUT",
            )
            l4ssGroup.interface.new_socket(
                name="time", socket_type="NodeSocketFloat", in_out="INPUT"
            )
            l4ssGroup.interface.new_socket(
                name="l4scrollspeed", socket_type="NodeSocketVector", in_out="OUTPUT"
            )

            l4ssGroupI = create_node(l4ssGroup.nodes, "NodeGroupInput", (-1000, 0))
            l4ssGroupO = create_node(l4ssGroup.nodes, "NodeGroupOutput", (200, 0))
            separate = create_node(l4ssGroup.nodes, "ShaderNodeSeparateXYZ", (-800, 25))
            mul = shader_nodes.math(
                l4ssGroup.nodes,
                l4ssGroup.links,
                "MULTIPLY",
                location=(-800, -25),
                hide=True,
            ).node
            add = shader_nodes.math(
                l4ssGroup.nodes, l4ssGroup.links, "ADD", location=(-600, 0), hide=True
            ).node
            combine = create_node(l4ssGroup.nodes, "ShaderNodeCombineXYZ", (-400, 0))
            l4ssGroup.links.new(l4ssGroupI.outputs["l4"], separate.inputs["Vector"])
            l4ssGroup.links.new(l4ssGroupI.outputs["time"], mul.inputs["Value"])
            l4ssGroup.links.new(
                l4ssGroupI.outputs["LayersScrollSpeed.w"],
                shader_nodes.socket_by_identifier(mul.inputs, "Value_001"),
            )
            l4ssGroup.links.new(separate.outputs["Y"], add.inputs["Value"])
            l4ssGroup.links.new(
                mul.outputs["Value"],
                shader_nodes.socket_by_identifier(add.inputs, "Value_001"),
            )
            l4ssGroup.links.new(add.outputs["Value"], combine.inputs["Y"])
            l4ssGroup.links.new(separate.outputs["X"], combine.inputs["X"])
            l4ssGroup.links.new(
                combine.outputs["Vector"], l4ssGroupO.inputs["l4scrollspeed"]
            )

        l4ss = create_node(
            CurMat.nodes, "ShaderNodeGroup", (-625, 275), label="l4scrollspeed"
        )
        l4ss.node_tree = l4ssGroup
        CurMat.links.new(
            shader_nodes.socket_by_identifier(vecMix4.outputs, "Result_Vector"),
            l4ss.inputs["l4"],
        )
        CurMat.links.new(
            layersScrollSpeed_w.outputs["Value"], l4ss.inputs["LayersScrollSpeed.w"]
        )
        CurMat.links.new(time.outputs["Value"], l4ss.inputs["time"])

        scrollMask = create_node(
            CurMat.nodes,
            "ShaderNodeTexImage",
            (-950, 100),
            label="ScrollMaskTexture",
            image=scrollMaskImg,
        )
        slots["image:scroll"] = [scrollMask.name]
        CurMat.links.new(l1ss.outputs["l1scrollspeed"], scrollMask.inputs["Vector"])

        scrollMMGroup = bpy.data.node_groups.get(
            "CP77 Transparent Screen scrollMaskMask v1"
        )
        if scrollMMGroup is None:
            scrollMMGroup = new_tracked_datablock(
                "node_groups",
                "CP77 Transparent Screen scrollMaskMask v1",
                "ShaderNodeTree",
            )
            scrollMMGroup.interface.new_socket(
                name="scrollMask", socket_type="NodeSocketColor", in_out="INPUT"
            )
            scrollMMGroup.interface.new_socket(
                name="scrollMaskMask", socket_type="NodeSocketVector", in_out="OUTPUT"
            )

            scrollMMGroupI = create_node(
                scrollMMGroup.nodes, "NodeGroupInput", (-1000, 0)
            )
            scrollMMGroupO = create_node(
                scrollMMGroup.nodes, "NodeGroupOutput", (200, 0)
            )
            separate = create_node(
                scrollMMGroup.nodes, "ShaderNodeSeparateXYZ", (-800, 0)
            )
            add = shader_nodes.math(
                scrollMMGroup.nodes,
                scrollMMGroup.links,
                "ADD",
                location=(-650, 0),
                hide=True,
            ).node
            scrollMMGroup.links.new(
                scrollMMGroupI.outputs["scrollMask"], separate.inputs["Vector"]
            )
            scrollMMGroup.links.new(separate.outputs["X"], add.inputs["Value"])
            scrollMMGroup.links.new(
                separate.outputs["Y"],
                shader_nodes.socket_by_identifier(add.inputs, "Value_001"),
            )
            scrollMMGroup.links.new(
                add.outputs["Value"], scrollMMGroupO.inputs["scrollMaskMask"]
            )

        scrollMaskMask = create_node(
            CurMat.nodes, "ShaderNodeGroup", (-700, 100), label="scrollMaskMask"
        )
        scrollMaskMask.node_tree = scrollMMGroup
        CurMat.links.new(
            scrollMask.outputs["Color"], scrollMaskMask.inputs["scrollMask"]
        )

        mul5 = shader_nodes.math(
            CurMat.nodes, CurMat.links, "MULTIPLY", location=(-950, 50), hide=True
        ).node
        frac2 = shader_nodes.math(
            CurMat.nodes, CurMat.links, "FRACT", location=(-800, 50), hide=True
        ).node
        CurMat.links.new(time.outputs["Value"], mul5.inputs["Value"])
        CurMat.links.new(
            scanlinesSpeed.outputs["Value"],
            shader_nodes.socket_by_identifier(mul5.inputs, "Value_001"),
        )
        CurMat.links.new(mul5.outputs["Value"], frac2.inputs["Value"])

        finalScrollUVGroup = bpy.data.node_groups.get(
            "CP77 Transparent Screen finalScrollUV1 v2"
        )
        if finalScrollUVGroup is None:
            finalScrollUVGroup = new_tracked_datablock(
                "node_groups",
                "CP77 Transparent Screen finalScrollUV1 v2",
                "ShaderNodeTree",
            )
            finalScrollUVGroup.interface.new_socket(
                name="scrollMask", socket_type="NodeSocketColor", in_out="INPUT"
            )
            finalScrollUVGroup.interface.new_socket(
                name="scrollUV1", socket_type="NodeSocketVector", in_out="INPUT"
            )
            finalScrollUVGroup.interface.new_socket(
                name="scrollUV1X", socket_type="NodeSocketVector", in_out="INPUT"
            )
            finalScrollUVGroup.interface.new_socket(
                name="scrollUV2", socket_type="NodeSocketVector", in_out="INPUT"
            )
            finalScrollUVGroup.interface.new_socket(
                name="scrollUV2X", socket_type="NodeSocketVector", in_out="INPUT"
            )
            finalScrollUVGroup.interface.new_socket(
                name="ScrollVerticalOrHorizontal",
                socket_type="NodeSocketVector",
                in_out="INPUT",
            )
            finalScrollUVGroup.interface.new_socket(
                name="finalScrollUV1", socket_type="NodeSocketVector", in_out="OUTPUT"
            )

            finalScrollUVGroupI = create_node(
                finalScrollUVGroup.nodes, "NodeGroupInput", (-1050, 0)
            )
            finalScrollUVGroupO = create_node(
                finalScrollUVGroup.nodes, "NodeGroupOutput", (-150, 0)
            )
            vecLerp2 = create_node(
                finalScrollUVGroup.nodes, "ShaderNodeGroup", (-750, 0), label="lerp"
            )
            vecLerp2.node_tree = vecLerpG
            separate9 = create_node(
                finalScrollUVGroup.nodes, "ShaderNodeSeparateXYZ", (-900, -50)
            )
            vecLerp3 = create_node(
                finalScrollUVGroup.nodes, "ShaderNodeGroup", (-750, -100), label="lerp"
            )
            vecLerp3.node_tree = vecLerpG
            vecLerp4 = create_node(
                finalScrollUVGroup.nodes, "ShaderNodeGroup", (-600, 0), label="lerp"
            )
            vecLerp4.node_tree = vecLerpG
            finalScrollUVGroup.links.new(
                finalScrollUVGroupI.outputs["scrollUV2"], vecLerp2.inputs["A"]
            )
            finalScrollUVGroup.links.new(
                finalScrollUVGroupI.outputs["scrollUV1"], vecLerp2.inputs["B"]
            )
            finalScrollUVGroup.links.new(separate9.outputs["X"], vecLerp2.inputs["t"])
            finalScrollUVGroup.links.new(
                finalScrollUVGroupI.outputs["scrollMask"], separate9.inputs["Vector"]
            )
            finalScrollUVGroup.links.new(
                finalScrollUVGroupI.outputs["scrollUV2X"], vecLerp3.inputs["A"]
            )
            finalScrollUVGroup.links.new(
                finalScrollUVGroupI.outputs["scrollUV1X"], vecLerp3.inputs["B"]
            )
            finalScrollUVGroup.links.new(separate9.outputs["X"], vecLerp3.inputs["t"])
            finalScrollUVGroup.links.new(
                vecLerp2.outputs["result"], vecLerp4.inputs["A"]
            )
            finalScrollUVGroup.links.new(
                vecLerp3.outputs["result"], vecLerp4.inputs["B"]
            )
            finalScrollUVGroup.links.new(
                finalScrollUVGroupI.outputs["ScrollVerticalOrHorizontal"],
                vecLerp4.inputs["t"],
            )
            finalScrollUVGroup.links.new(
                vecLerp4.outputs["result"], finalScrollUVGroupO.inputs["finalScrollUV1"]
            )

        finalScrollUV1 = create_node(
            CurMat.nodes, "ShaderNodeGroup", (-1200, -200), label="finalScrollUV1"
        )
        finalScrollUV1.node_tree = finalScrollUVGroup
        CurMat.links.new(
            scrollUV2.outputs["scrollUV2"], finalScrollUV1.inputs["scrollUV2"]
        )
        CurMat.links.new(
            scrollUV1.outputs["scrollUV1"], finalScrollUV1.inputs["scrollUV1"]
        )
        CurMat.links.new(
            scrollMask.outputs["Color"], finalScrollUV1.inputs["scrollMask"]
        )
        CurMat.links.new(
            scrollUV2X.outputs["scrollUV2X"], finalScrollUV1.inputs["scrollUV2X"]
        )
        CurMat.links.new(
            scrollUV1X.outputs["scrollUV1X"], finalScrollUV1.inputs["scrollUV1X"]
        )
        CurMat.links.new(
            scrollVerticalOrHorizontal.outputs["Value"],
            finalScrollUV1.inputs["ScrollVerticalOrHorizontal"],
        )

        finalScrollUV2Group = _create_final_scroll_delta_group(2)
        finalScrollUV2 = add_group_node(
            CurMat, finalScrollUV2Group, (-1200, -250), label="finalScrollUV2"
        )
        CurMat.links.new(
            finalScrollUV1.outputs["finalScrollUV1"],
            finalScrollUV2.inputs["finalScrollUV1"],
        )
        CurMat.links.new(l1ss.outputs["l1scrollspeed"], finalScrollUV2.inputs["l1"])
        CurMat.links.new(l2ss.outputs["l2scrollspeed"], finalScrollUV2.inputs["l2"])

        finalScrollUV3Group = _create_final_scroll_delta_group(3)
        finalScrollUV3 = add_group_node(
            CurMat, finalScrollUV3Group, (-1200, -300), label="finalScrollUV3"
        )
        CurMat.links.new(
            finalScrollUV1.outputs["finalScrollUV1"],
            finalScrollUV3.inputs["finalScrollUV1"],
        )
        CurMat.links.new(l1ss.outputs["l1scrollspeed"], finalScrollUV3.inputs["l1"])
        CurMat.links.new(l3ss.outputs["l3scrollspeed"], finalScrollUV3.inputs["l3"])

        finalScrollUV4Group = _create_final_scroll_delta_group(4)
        finalScrollUV4 = add_group_node(
            CurMat, finalScrollUV4Group, (-1200, -350), label="finalScrollUV4"
        )
        CurMat.links.new(
            finalScrollUV1.outputs["finalScrollUV1"],
            finalScrollUV4.inputs["finalScrollUV1"],
        )
        CurMat.links.new(l1ss.outputs["l1scrollspeed"], finalScrollUV4.inputs["l1"])
        CurMat.links.new(l4ss.outputs["l4scrollspeed"], finalScrollUV4.inputs["l4"])

        parTex = create_node(
            CurMat.nodes,
            "ShaderNodeTexImage",
            (-1050, -100),
            label="ParalaxTexture",
            image=parImg,
        )
        parTex2 = create_node(
            CurMat.nodes,
            "ShaderNodeTexImage",
            (-1050, -150),
            label="ParalaxTexture",
            image=parImg,
        )
        slots.setdefault("image:parallax", []).extend((parTex.name, parTex2.name))
        vecLerp = create_node(
            CurMat.nodes, "ShaderNodeGroup", (-700, -200), label="lerp"
        )
        vecLerp.node_tree = vecLerpG
        lerpG = createLerpGroup()
        lerp = create_node(CurMat.nodes, "ShaderNodeGroup", (-700, -250), label="lerp")
        lerp.node_tree = lerpG
        CurMat.links.new(
            finalScrollUV1.outputs["finalScrollUV1"], parTex2.inputs["Vector"]
        )
        CurMat.links.new(l1ss.outputs["l1scrollspeed"], parTex.inputs["Vector"])
        CurMat.links.new(parTex.outputs["Color"], vecLerp.inputs["A"])
        CurMat.links.new(parTex2.outputs["Color"], vecLerp.inputs["B"])
        CurMat.links.new(scrollMaskMask.outputs["scrollMaskMask"], vecLerp.inputs["t"])
        CurMat.links.new(parTex.outputs["Alpha"], lerp.inputs["A"])
        CurMat.links.new(parTex2.outputs["Alpha"], lerp.inputs["B"])
        CurMat.links.new(scrollMaskMask.outputs["scrollMaskMask"], lerp.inputs["t"])

        parTex = create_node(
            CurMat.nodes,
            "ShaderNodeTexImage",
            (-1050, -200),
            label="ParalaxTexture",
            image=parImg,
        )
        parTex2 = create_node(
            CurMat.nodes,
            "ShaderNodeTexImage",
            (-1050, -250),
            label="ParalaxTexture",
            image=parImg,
        )
        slots.setdefault("image:parallax", []).extend((parTex.name, parTex2.name))
        vecLerp2 = create_node(
            CurMat.nodes, "ShaderNodeGroup", (-700, -300), label="lerp"
        )
        vecLerp2.node_tree = vecLerpG
        lerp2 = create_node(CurMat.nodes, "ShaderNodeGroup", (-700, -350), label="lerp")
        lerp2.node_tree = lerpG
        CurMat.links.new(
            finalScrollUV2.outputs["finalScrollUV2_ps_t_v2"], parTex2.inputs["Vector"]
        )
        CurMat.links.new(l2ss.outputs["l2scrollspeed"], parTex.inputs["Vector"])
        CurMat.links.new(parTex.outputs["Color"], vecLerp2.inputs["A"])
        CurMat.links.new(parTex2.outputs["Color"], vecLerp2.inputs["B"])
        CurMat.links.new(scrollMaskMask.outputs["scrollMaskMask"], vecLerp2.inputs["t"])
        CurMat.links.new(parTex.outputs["Alpha"], lerp2.inputs["A"])
        CurMat.links.new(parTex2.outputs["Alpha"], lerp2.inputs["B"])
        CurMat.links.new(scrollMaskMask.outputs["scrollMaskMask"], lerp2.inputs["t"])

        parTex = create_node(
            CurMat.nodes,
            "ShaderNodeTexImage",
            (-1050, -300),
            label="ParalaxTexture",
            image=parImg,
        )
        parTex2 = create_node(
            CurMat.nodes,
            "ShaderNodeTexImage",
            (-1050, -350),
            label="ParalaxTexture",
            image=parImg,
        )
        slots.setdefault("image:parallax", []).extend((parTex.name, parTex2.name))
        vecLerp3 = create_node(
            CurMat.nodes, "ShaderNodeGroup", (-700, -400), label="lerp"
        )
        vecLerp3.node_tree = vecLerpG
        lerp3 = create_node(CurMat.nodes, "ShaderNodeGroup", (-700, -450), label="lerp")
        lerp3.node_tree = lerpG
        CurMat.links.new(
            finalScrollUV3.outputs["finalScrollUV3_ps_t_v2"], parTex2.inputs["Vector"]
        )
        CurMat.links.new(l3ss.outputs["l3scrollspeed"], parTex.inputs["Vector"])
        CurMat.links.new(parTex.outputs["Color"], vecLerp3.inputs["A"])
        CurMat.links.new(parTex2.outputs["Color"], vecLerp3.inputs["B"])
        CurMat.links.new(scrollMaskMask.outputs["scrollMaskMask"], vecLerp3.inputs["t"])
        CurMat.links.new(parTex.outputs["Alpha"], lerp3.inputs["A"])
        CurMat.links.new(parTex2.outputs["Alpha"], lerp3.inputs["B"])
        CurMat.links.new(scrollMaskMask.outputs["scrollMaskMask"], lerp3.inputs["t"])

        parTex = create_node(
            CurMat.nodes,
            "ShaderNodeTexImage",
            (-1050, -400),
            label="ParalaxTexture",
            image=parImg,
        )
        parTex2 = create_node(
            CurMat.nodes,
            "ShaderNodeTexImage",
            (-1050, -450),
            label="ParalaxTexture",
            image=parImg,
        )
        slots.setdefault("image:parallax", []).extend((parTex.name, parTex2.name))
        vecLerp4 = create_node(
            CurMat.nodes, "ShaderNodeGroup", (-700, -500), label="lerp"
        )
        vecLerp4.node_tree = vecLerpG
        lerp4 = create_node(CurMat.nodes, "ShaderNodeGroup", (-700, -550), label="lerp")
        lerp4.node_tree = lerpG
        CurMat.links.new(
            finalScrollUV4.outputs["finalScrollUV4_ps_t_v2"], parTex2.inputs["Vector"]
        )
        CurMat.links.new(l4ss.outputs["l4scrollspeed"], parTex.inputs["Vector"])
        CurMat.links.new(parTex.outputs["Color"], vecLerp4.inputs["A"])
        CurMat.links.new(parTex2.outputs["Color"], vecLerp4.inputs["B"])
        CurMat.links.new(scrollMaskMask.outputs["scrollMaskMask"], vecLerp4.inputs["t"])
        CurMat.links.new(parTex.outputs["Alpha"], lerp4.inputs["A"])
        CurMat.links.new(parTex2.outputs["Alpha"], lerp4.inputs["B"])
        CurMat.links.new(scrollMaskMask.outputs["scrollMaskMask"], lerp4.inputs["t"])

        i1Group = bpy.data.node_groups.get("CP77 Transparent Screen i1_ps_t_v3 v1")
        if i1Group is None:
            i1Group = new_tracked_datablock(
                "node_groups", "CP77 Transparent Screen i1_ps_t_v3 v1", "ShaderNodeTree"
            )
            i1Group.interface.new_socket(
                name="l1Sampled", socket_type="NodeSocketVector", in_out="INPUT"
            )
            i1Group.interface.new_socket(
                name="Alpha", socket_type="NodeSocketFloat", in_out="INPUT"
            )
            i1Group.interface.new_socket(
                name="IntensityPerLayer.x",
                socket_type="NodeSocketFloat",
                in_out="INPUT",
            )
            i1Group.interface.new_socket(
                name="Layer", socket_type="NodeSocketBundle", in_out="OUTPUT"
            )

            i1GroupI = create_node(i1Group.nodes, "NodeGroupInput", (-1050, 0))
            i1GroupO = create_node(i1Group.nodes, "NodeGroupOutput", (-150, 0))
            vecMul = shader_nodes.vector_math(
                i1Group.nodes, i1Group.links, "MULTIPLY", location=(-900, 0), hide=True
            ).node
            mul = shader_nodes.math(
                i1Group.nodes,
                i1Group.links,
                "MULTIPLY",
                location=(-900, -100),
                hide=True,
            ).node
            i1Group.links.new(i1GroupI.outputs["l1Sampled"], vecMul.inputs["Vector"])
            i1Group.links.new(i1GroupI.outputs["Alpha"], mul.inputs["Value"])
            i1Group.links.new(
                i1GroupI.outputs["IntensityPerLayer.x"],
                shader_nodes.socket_by_identifier(vecMul.inputs, "Vector_001"),
            )
            i1Group.links.new(
                i1GroupI.outputs["IntensityPerLayer.x"],
                shader_nodes.socket_by_identifier(mul.inputs, "Value_001"),
            )
            i1Bundle = combine_bundle_node(
                i1Group,
                _LAYER_SAMPLE_BUNDLE_ITEMS,
                (-300, -25),
                name="CP77 Layer 1 Sample",
                label="Layer Sample",
            )
            i1Group.links.new(vecMul.outputs["Vector"], i1Bundle.inputs["Color"])
            i1Group.links.new(mul.outputs["Value"], i1Bundle.inputs["Alpha"])
            i1Group.links.new(i1Bundle.outputs["Bundle"], i1GroupO.inputs["Layer"])

        i1 = create_node(CurMat.nodes, "ShaderNodeGroup", (-550, -200), label="i1_ps_t")
        i1.node_tree = i1Group
        CurMat.links.new(vecLerp.outputs["result"], i1.inputs["l1Sampled"])
        CurMat.links.new(lerp.outputs["result"], i1.inputs["Alpha"])
        CurMat.links.new(
            intensityPerLayer_x.outputs["Value"], i1.inputs["IntensityPerLayer.x"]
        )

        scanlineG = self.createScanlinesGroup()
        layerLerpG = createLerpGroup()

        screen_effects = combine_bundle_node(
            CurMat,
            _SCREEN_EFFECTS_BUNDLE_ITEMS,
            (-725, -700),
            name="CP77 Parallax Screen Effects",
            label="Screen Effects",
        )
        CurMat.links.new(
            scanlinesIntensity.outputs["Value"],
            screen_effects.inputs["Scanline Intensity"],
        )
        CurMat.links.new(
            scanlinesDensity.outputs["Value"], screen_effects.inputs["Scanline Density"]
        )
        CurMat.links.new(
            frac2.outputs["Value"], screen_effects.inputs["Scanline Phase"]
        )
        CurMat.links.new(
            scrollMaskMask.outputs["scrollMaskMask"],
            screen_effects.inputs["Scroll Mask"],
        )

        i2Group = _create_layer_intensity_group(2, "y", scanlineG, layerLerpG)
        i2 = add_group_node(CurMat, i2Group, (-550, -275), label="i2_ps_t")
        CurMat.links.new(vecLerp2.outputs["result"], i2.inputs["l2Sampled"])
        CurMat.links.new(lerp2.outputs["result"], i2.inputs["Alpha"])
        CurMat.links.new(l2ss.outputs["l2scrollspeed"], i2.inputs["l2"])
        CurMat.links.new(
            finalScrollUV2.outputs["finalScrollUV2_ps_t_v2"],
            i2.inputs["finalScrollUV2"],
        )
        CurMat.links.new(
            intensityPerLayer_y.outputs["Value"], i2.inputs["IntensityPerLayer.y"]
        )
        CurMat.links.new(screen_effects.outputs["Bundle"], i2.inputs["Effects"])

        i3Group = _create_layer_intensity_group(3, "z", scanlineG, layerLerpG)
        i3 = add_group_node(CurMat, i3Group, (-550, -375), label="i3_ps_t")
        CurMat.links.new(vecLerp3.outputs["result"], i3.inputs["l3Sampled"])
        CurMat.links.new(lerp3.outputs["result"], i3.inputs["Alpha"])
        CurMat.links.new(l3ss.outputs["l3scrollspeed"], i3.inputs["l3"])
        CurMat.links.new(
            finalScrollUV3.outputs["finalScrollUV3_ps_t_v2"],
            i3.inputs["finalScrollUV3"],
        )
        CurMat.links.new(
            intensityPerLayer_z.outputs["Value"], i3.inputs["IntensityPerLayer.z"]
        )
        CurMat.links.new(screen_effects.outputs["Bundle"], i3.inputs["Effects"])

        i4Group = _create_layer_intensity_group(4, "w", scanlineG, layerLerpG)
        i4 = add_group_node(CurMat, i4Group, (-550, -475), label="i4_ps_t")
        CurMat.links.new(vecLerp4.outputs["result"], i4.inputs["l4Sampled"])
        CurMat.links.new(lerp4.outputs["result"], i4.inputs["Alpha"])
        CurMat.links.new(l4ss.outputs["l4scrollspeed"], i4.inputs["l4"])
        CurMat.links.new(
            finalScrollUV4.outputs["finalScrollUV4_ps_t_v2"],
            i4.inputs["finalScrollUV4"],
        )
        CurMat.links.new(
            intensityPerLayer_w.outputs["Value"], i4.inputs["IntensityPerLayer.w"]
        )
        CurMat.links.new(screen_effects.outputs["Bundle"], i4.inputs["Effects"])

        blend_factory = (
            _create_alpha_blend_group if _alpha_blended(Data) else _create_m_group
        )
        m1Group = blend_factory("m1", "m1", "i4", "i3")
        m1 = add_group_node(CurMat, m1Group, (-550, -500), label="m1")
        CurMat.links.new(i4.outputs["Layer"], m1.inputs["Layer A"])
        CurMat.links.new(i3.outputs["Layer"], m1.inputs["Layer B"])

        m2Group = blend_factory("parallax_screen_trans_m2", "m2", "m1", "i2")
        m2 = add_group_node(CurMat, m2Group, (-550, -550), label="m2")
        CurMat.links.new(m1.outputs["Layer"], m2.inputs["Layer A"])
        CurMat.links.new(i2.outputs["Layer"], m2.inputs["Layer B"])

        m3Group = blend_factory("parallax_screen_trans_m3", "m3", "m2", "i1")
        m3 = add_group_node(CurMat, m3Group, (-550, -600), label="m3")
        CurMat.links.new(m2.outputs["Layer"], m3.inputs["Layer A"])
        CurMat.links.new(i1.outputs["Layer"], m3.inputs["Layer B"])

        layer_result = separate_bundle_node(
            CurMat,
            _LAYER_SAMPLE_BUNDLE_ITEMS,
            (-475, -625),
            name="CP77 Parallax Layer Result",
            label="Layer Result",
        )
        CurMat.links.new(m3.outputs["Layer"], layer_result.inputs["Bundle"])

        greater_than = shader_nodes.math(
            CurMat.nodes, CurMat.links, "GREATER_THAN", location=(-550, -800), hide=True
        ).node
        shader_nodes.socket_by_identifier(
            greater_than.inputs, "Value_001"
        ).default_value = 0
        mix = create_node(CurMat.nodes, "ShaderNodeMix", (-400, -800))
        mix.data_type = "FLOAT"
        shader_nodes.socket_by_identifier(mix.inputs, "A_Float").default_value = 1.0
        CurMat.links.new(edgesMaskValue.outputs["Value"], greater_than.inputs["Value"])
        CurMat.links.new(
            greater_than.outputs["Value"],
            shader_nodes.socket_by_identifier(mix.inputs, "Factor_Float"),
        )

        edgesMaskGroup = bpy.data.node_groups.get(
            "CP77 Transparent Screen edgesMask v1"
        )
        if edgesMaskGroup is None:
            edgesMaskGroup = new_tracked_datablock(
                "node_groups", "CP77 Transparent Screen edgesMask v1", "ShaderNodeTree"
            )
            edgesMaskGroup.interface.new_socket(
                name="UV", socket_type="NodeSocketVector", in_out="INPUT"
            )
            edgesMaskGroup.interface.new_socket(
                name="EdgesMask", socket_type="NodeSocketFloat", in_out="INPUT"
            )
            edgesMaskGroup.interface.new_socket(
                name="edgesMask", socket_type="NodeSocketFloat", in_out="OUTPUT"
            )

            edgesMaskGroupI = create_node(
                edgesMaskGroup.nodes, "NodeGroupInput", (-1050, 0)
            )
            edgesMaskGroupO = create_node(
                edgesMaskGroup.nodes, "NodeGroupOutput", (300, 0)
            )
            separate = create_node(
                edgesMaskGroup.nodes, "ShaderNodeSeparateXYZ", (-900, 0)
            )
            sub = shader_nodes.math(
                edgesMaskGroup.nodes,
                edgesMaskGroup.links,
                "SUBTRACT",
                location=(-750, 0),
                hide=True,
            ).node
            shader_nodes.socket_by_identifier(
                sub.inputs, "Value_001"
            ).default_value = 0.5
            mul = shader_nodes.math(
                edgesMaskGroup.nodes,
                edgesMaskGroup.links,
                "MULTIPLY",
                location=(-600, 0),
                hide=True,
            ).node
            shader_nodes.socket_by_identifier(mul.inputs, "Value_001").default_value = 2
            absolute = shader_nodes.math(
                edgesMaskGroup.nodes,
                edgesMaskGroup.links,
                "ABSOLUTE",
                location=(-450, 0),
                hide=True,
            ).node
            sub2 = shader_nodes.math(
                edgesMaskGroup.nodes,
                edgesMaskGroup.links,
                "SUBTRACT",
                location=(-300, 0),
                hide=True,
            ).node
            sub2.inputs["Value"].default_value = 1
            sub2.use_clamp = True
            mul2 = shader_nodes.math(
                edgesMaskGroup.nodes,
                edgesMaskGroup.links,
                "MULTIPLY",
                location=(-150, 0),
                hide=True,
            ).node

            edgesMaskGroup.links.new(
                edgesMaskGroupI.outputs["UV"], separate.inputs["Vector"]
            )
            edgesMaskGroup.links.new(separate.outputs["Y"], sub.inputs["Value"])
            edgesMaskGroup.links.new(sub.outputs["Value"], mul.inputs["Value"])
            edgesMaskGroup.links.new(mul.outputs["Value"], absolute.inputs["Value"])
            edgesMaskGroup.links.new(
                absolute.outputs["Value"],
                shader_nodes.socket_by_identifier(sub2.inputs, "Value_001"),
            )
            edgesMaskGroup.links.new(sub2.outputs["Value"], mul2.inputs["Value"])
            edgesMaskGroup.links.new(
                edgesMaskGroupI.outputs["EdgesMask"],
                shader_nodes.socket_by_identifier(mul2.inputs, "Value_001"),
            )
            edgesMaskGroup.links.new(
                mul2.outputs["Value"], edgesMaskGroupO.inputs["edgesMask"]
            )

        edgesMask = create_node(
            CurMat.nodes, "ShaderNodeGroup", (-550, -850), label="edgesMask"
        )
        edgesMask.node_tree = edgesMaskGroup
        CurMat.links.new(UVMap.outputs["UV"], edgesMask.inputs["UV"])
        CurMat.links.new(edgesMaskValue.outputs["Value"], edgesMask.inputs["EdgesMask"])
        CurMat.links.new(
            edgesMask.outputs["edgesMask"],
            shader_nodes.socket_by_identifier(mix.inputs, "B_Float"),
        )

        hsvGroup = bpy.data.node_groups.get("CP77 Transparent Screen hsv v1")
        if hsvGroup is None:
            hsvGroup = new_tracked_datablock(
                "node_groups", "CP77 Transparent Screen hsv v1", "ShaderNodeTree"
            )
            hsvGroup.interface.new_socket(
                name="m3", socket_type="NodeSocketVector", in_out="INPUT"
            )
            hsvGroup.interface.new_socket(
                name="scroll1", socket_type="NodeSocketVector", in_out="INPUT"
            )
            hsvGroup.interface.new_socket(
                name="TexHSVControl.x", socket_type="NodeSocketFloat", in_out="INPUT"
            )
            hsvGroup.interface.new_socket(
                name="TexHSVControl.y", socket_type="NodeSocketFloat", in_out="INPUT"
            )
            hsvGroup.interface.new_socket(
                name="TexHSVControl.z", socket_type="NodeSocketFloat", in_out="INPUT"
            )
            hsvGroup.interface.new_socket(
                name="scrollMask", socket_type="NodeSocketVector", in_out="INPUT"
            )
            hsvGroup.interface.new_socket(
                name="EdgesMask", socket_type="NodeSocketFloat", in_out="INPUT"
            )
            hsvGroup.interface.new_socket(
                name="color", socket_type="NodeSocketColor", in_out="OUTPUT"
            )

            hsvGroupI = create_node(hsvGroup.nodes, "NodeGroupInput", (-1650, 0))
            hsvGroupO = create_node(hsvGroup.nodes, "NodeGroupOutput", (150, 0))
            hsv_pos_x = -1500
            vecMul10 = shader_nodes.vector_math(
                hsvGroup.nodes,
                hsvGroup.links,
                "MULTIPLY",
                location=(hsv_pos_x, 0),
                hide=True,
            ).node
            separateHSV = create_node(
                hsvGroup.nodes, "ShaderNodeSeparateColor", (hsv_pos_x + 150, 0)
            )
            separateHSV.mode = "HSV"
            combine5 = create_node(
                hsvGroup.nodes, "ShaderNodeCombineXYZ", (hsv_pos_x + 150, 0)
            )
            combine6 = create_node(
                hsvGroup.nodes, "ShaderNodeCombineXYZ", (hsv_pos_x + 300, 0)
            )
            vecAdd3 = shader_nodes.vector_math(
                hsvGroup.nodes,
                hsvGroup.links,
                "ADD",
                location=(hsv_pos_x + 450, 0),
                hide=True,
            ).node
            combine7 = create_node(
                hsvGroup.nodes, "ShaderNodeCombineXYZ", (hsv_pos_x + 450, -50)
            )
            combine7.inputs["X"].default_value = 1
            vecMul11 = shader_nodes.vector_math(
                hsvGroup.nodes,
                hsvGroup.links,
                "MULTIPLY",
                location=(hsv_pos_x + 600, 0),
                hide=True,
            ).node
            separate11 = create_node(
                hsvGroup.nodes, "ShaderNodeSeparateXYZ", (hsv_pos_x + 750, 0)
            )
            combineHSV = create_node(
                hsvGroup.nodes, "ShaderNodeCombineColor", (hsv_pos_x + 900, 0)
            )
            combineHSV.mode = "HSV"
            vecMul12 = shader_nodes.vector_math(
                hsvGroup.nodes,
                hsvGroup.links,
                "MULTIPLY",
                location=(hsv_pos_x + 1050, 0),
                hide=True,
            ).node
            combine8 = create_node(
                hsvGroup.nodes, "ShaderNodeCombineXYZ", (hsv_pos_x + 1200, -50)
            )
            vecMul13 = shader_nodes.vector_math(
                hsvGroup.nodes,
                hsvGroup.links,
                "MULTIPLY",
                location=(hsv_pos_x + 1350, 0),
                hide=True,
            ).node
            hsvGroup.links.new(hsvGroupI.outputs["m3"], vecMul10.inputs["Vector"])
            hsvGroup.links.new(
                hsvGroupI.outputs["scroll1"],
                shader_nodes.socket_by_identifier(vecMul10.inputs, "Vector_001"),
            )
            hsvGroup.links.new(
                hsvGroupI.outputs["TexHSVControl.x"], combine5.inputs["X"]
            )
            hsvGroup.links.new(vecMul10.outputs["Vector"], separateHSV.inputs["Color"])
            hsvGroup.links.new(separateHSV.outputs["Red"], combine6.inputs["X"])
            hsvGroup.links.new(separateHSV.outputs["Green"], combine6.inputs["Y"])
            hsvGroup.links.new(separateHSV.outputs["Blue"], combine6.inputs["Z"])
            hsvGroup.links.new(combine6.outputs["Vector"], vecAdd3.inputs["Vector"])
            hsvGroup.links.new(
                combine5.outputs["Vector"],
                shader_nodes.socket_by_identifier(vecAdd3.inputs, "Vector_001"),
            )
            hsvGroup.links.new(
                hsvGroupI.outputs["TexHSVControl.y"], combine7.inputs["Y"]
            )
            hsvGroup.links.new(
                hsvGroupI.outputs["TexHSVControl.z"], combine7.inputs["Z"]
            )
            hsvGroup.links.new(vecAdd3.outputs["Vector"], vecMul11.inputs["Vector"])
            hsvGroup.links.new(
                combine7.outputs["Vector"],
                shader_nodes.socket_by_identifier(vecMul11.inputs, "Vector_001"),
            )
            hsvGroup.links.new(vecMul11.outputs["Vector"], separate11.inputs["Vector"])
            hsvGroup.links.new(separate11.outputs["X"], combineHSV.inputs["Red"])
            hsvGroup.links.new(separate11.outputs["Y"], combineHSV.inputs["Green"])
            hsvGroup.links.new(separate11.outputs["Z"], combineHSV.inputs["Blue"])
            hsvGroup.links.new(combineHSV.outputs["Color"], vecMul12.inputs["Vector"])
            hsvGroup.links.new(
                hsvGroupI.outputs["scrollMask"],
                shader_nodes.socket_by_identifier(vecMul12.inputs, "Vector_001"),
            )
            hsvGroup.links.new(hsvGroupI.outputs["EdgesMask"], combine8.inputs["X"])
            hsvGroup.links.new(hsvGroupI.outputs["EdgesMask"], combine8.inputs["Y"])
            hsvGroup.links.new(hsvGroupI.outputs["EdgesMask"], combine8.inputs["Z"])
            hsvGroup.links.new(vecMul12.outputs["Vector"], vecMul13.inputs["Vector"])
            hsvGroup.links.new(
                combine8.outputs["Vector"],
                shader_nodes.socket_by_identifier(vecMul13.inputs, "Vector_001"),
            )
            hsvGroup.links.new(vecMul13.outputs["Vector"], hsvGroupO.inputs["color"])

        hsv = create_node(CurMat.nodes, "ShaderNodeGroup", (-400, -650), label="hsv")
        hsv.node_tree = hsvGroup
        CurMat.links.new(layer_result.outputs["Color"], hsv.inputs["m3"])
        CurMat.links.new(emissive.outputs["Value"], hsv.inputs["scroll1"])
        CurMat.links.new(
            texHSVControl_x.outputs["Value"], hsv.inputs["TexHSVControl.x"]
        )
        CurMat.links.new(
            texHSVControl_y.outputs["Value"], hsv.inputs["TexHSVControl.y"]
        )
        CurMat.links.new(
            texHSVControl_z.outputs["Value"], hsv.inputs["TexHSVControl.z"]
        )
        CurMat.links.new(gamma.outputs["Color"], hsv.inputs["scrollMask"])
        CurMat.links.new(
            shader_nodes.socket_by_identifier(mix.outputs, "Result_Float"),
            hsv.inputs["EdgesMask"],
        )

        facing_alpha_group = _create_facing_alpha_group()
        mul2 = add_group_node(
            CurMat,
            facing_alpha_group,
            (-650, -1050),
            label="Facing Alpha",
            name="CP77 Parallax Facing Alpha",
        )
        CurMat.links.new(geometry.outputs["Position"], mul2.inputs["Position"])
        CurMat.links.new(geometry.outputs["Normal"], mul2.inputs["Normal"])
        CurMat.links.new(layer_result.outputs["Alpha"], mul2.inputs["Layer Alpha"])
        CurMat.links.new(color_a.outputs["Value"], mul2.inputs["Color Alpha"])
        # The edge mask scales the colour only; the alpha is the layers' alpha and the facing term.
        mul2.inputs["Edge Mask"].default_value = 1.0

        # The forward blend adds colour × alpha and occludes the background by alpha × AdditiveAlphaBlend, so the
        # texture's colour where its alpha is zero does not show.
        additive = CreateShaderNodeValue(
            CurMat, values["AdditiveAlphaBlend"], -2000, -1450, "AdditiveAlphaBlend"
        )
        slots["AdditiveAlphaBlend"] = (additive.name, None)
        CurMat.nodes.remove(shader_nodes.material_output(CurMat.nodes))
        additive_surface(
            Mat, hsv.outputs["color"], mul2.outputs["Alpha"], additive.outputs["Value"]
        )
        # Back faces are culled; two-sided screens come with doubled geometry.
        Mat.use_backface_culling = True
