from ..bartmoss.scalar import (
    SRGB_DECODE_THRESHOLD,
    SRGB_GAMMA,
    SRGB_LINEAR_SCALE,
    SRGB_OFFSET,
    SRGB_SCALE,
)
from ..blender import shader_nodes
from ..materials.blender.nodes import create_node
from .bundles import material_bundle_node
from .mat_common import get_or_build_node_group, param_texture_path

# BT.709 YCbCr to RGB: the (Cb, Cr) weights of each of R, G and B.
_YCBCR_TO_RGB = ((0.0, 1.5748), (-0.1873, -0.4681), (1.8556, 0.0))


def _plane(owner, tree, data, key, y, uv=None, *, extension="REPEAT"):
    path = param_texture_path(data, key)
    if not path:
        return None
    image = owner._load_relative_image(path, non_color=True, error_label=key)
    if image is None:
        return None
    texture = create_node(
        tree.nodes, "ShaderNodeTexImage", (-1500, y), label=key, image=image
    )
    texture.extension = extension
    if uv is not None:
        tree.links.new(uv, texture.inputs["Vector"])
    split = create_node(
        tree.nodes, "ShaderNodeSeparateColor", (-1260, y), label=f"{key}.r"
    )
    split.mode = "RGB"
    tree.links.new(texture.outputs["Color"], split.inputs["Color"])
    return split.outputs["Red"]


def _decode_rgb(tree, luma, cb, cr):
    """BT.709 R, G and B from the luma and chroma planes"""
    chroma = (
        shader_nodes.math(
            tree.nodes,
            tree.links,
            "SUBTRACT",
            cb,
            0.5,
            label="Cb - 0.5",
            location=(-1060, 140),
            hide=True,
        )
        if cb is not None
        else None,
        shader_nodes.math(
            tree.nodes,
            tree.links,
            "SUBTRACT",
            cr,
            0.5,
            label="Cr - 0.5",
            location=(-1060, 330),
            hide=True,
        )
        if cr is not None
        else None,
    )
    channels = []
    for weights, label, y in zip(
        _YCBCR_TO_RGB, ("Bink R", "Bink G", "Bink B"), (520, 330, 140)
    ):
        current = luma
        for index, (source, weight) in enumerate(zip(chroma, weights)):
            if source is not None and weight:
                current = shader_nodes.math(
                    tree.nodes,
                    tree.links,
                    "MULTIPLY_ADD",
                    source,
                    weight,
                    current,
                    label=label,
                    location=(-860 + index * 180, y),
                    hide=True,
                )
        channels.append(current)
    return channels


def _build_srgb_conversion(tree, color, location):
    split = create_node(
        tree.nodes, "ShaderNodeSeparateColor", location, label="Bink sRGB"
    )
    split.mode = "RGB"
    tree.links.new(color, split.inputs["Color"])
    outputs = []
    for index, name in enumerate(("Red", "Green", "Blue")):
        y = location[1] - index * 140
        source = split.outputs[name]
        low = shader_nodes.math(
            tree.nodes,
            tree.links,
            "DIVIDE",
            label=f"{name} / 12.92",
            location=(location[0] + 180, y),
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(
            low.inputs, "Value_001"
        ).default_value = SRGB_LINEAR_SCALE
        tree.links.new(source, low.inputs["Value"])
        offset = shader_nodes.math(
            tree.nodes,
            tree.links,
            "ADD",
            label=f"{name} + .055",
            location=(location[0] + 180, y - 60),
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(
            offset.inputs, "Value_001"
        ).default_value = SRGB_OFFSET
        tree.links.new(source, offset.inputs["Value"])
        scale = shader_nodes.math(
            tree.nodes,
            tree.links,
            "DIVIDE",
            label=f"{name} / 1.055",
            location=(location[0] + 340, y - 60),
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(
            scale.inputs, "Value_001"
        ).default_value = SRGB_SCALE
        tree.links.new(offset.outputs["Value"], scale.inputs["Value"])
        absolute = shader_nodes.math(
            tree.nodes,
            tree.links,
            "ABSOLUTE",
            label=f"abs({name})",
            location=(location[0] + 500, y - 60),
            hide=True,
        ).node
        tree.links.new(scale.outputs["Value"], absolute.inputs["Value"])
        high = shader_nodes.math(
            tree.nodes,
            tree.links,
            "POWER",
            label=f"{name} ^ 2.4",
            location=(location[0] + 660, y - 60),
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(
            high.inputs, "Value_001"
        ).default_value = SRGB_GAMMA
        tree.links.new(absolute.outputs["Value"], high.inputs["Value"])
        use_high = shader_nodes.math(
            tree.nodes,
            tree.links,
            "GREATER_THAN",
            label=f"{name} > .04045",
            location=(location[0] + 500, y + 40),
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(
            use_high.inputs, "Value_001"
        ).default_value = SRGB_DECODE_THRESHOLD
        tree.links.new(source, use_high.inputs["Value"])
        mix = create_node(
            tree.nodes,
            "ShaderNodeMix",
            (location[0] + 830, y),
            label=f"{name} sRGB to Linear",
        )
        mix.data_type = "FLOAT"
        mix.clamp_factor = True
        sockets = {socket.identifier: socket for socket in (*mix.inputs, *mix.outputs)}
        tree.links.new(use_high.outputs["Value"], sockets["Factor_Float"])
        tree.links.new(low.outputs["Value"], sockets["A_Float"])
        tree.links.new(high.outputs["Value"], sockets["B_Float"])
        outputs.append(sockets["Result_Float"])
    combine = create_node(
        tree.nodes,
        "ShaderNodeCombineColor",
        (location[0] + 1010, location[1] - 140),
        label="Bink Linear RGB",
    )
    combine.mode = "RGB"
    for source, name in zip(outputs, ("Red", "Green", "Blue")):
        tree.links.new(source, combine.inputs[name])
    return combine.outputs["Color"]


def _srgb_conversion_group():
    def build(group):
        group_input = group.nodes.new("NodeGroupInput")
        group_output = group.nodes.new("NodeGroupOutput")
        converted = _build_srgb_conversion(
            group,
            group_input.outputs["Color"],
            (-900, 160),
        )
        group.links.new(converted, group_output.inputs["Color"])

    return get_or_build_node_group(
        "CP77 sRGB Decode Bundle v1",
        (("NodeSocketColor", "Color"),),
        (("NodeSocketColor", "Color"),),
        build,
    )


def _srgb_to_linear(tree, color, location):
    node = material_bundle_node(
        tree,
        _srgb_conversion_group(),
        location,
        "sRGB Decode",
        {"Color": color},
    )
    return node.outputs["Color"]


def decode_bink_preview(
    owner, tree, data, *, uv=None, location=(-420, 260), extension="REPEAT"
):
    """Approximate decoded video color when runtime colorspace parameters are unavailable"""
    luma = _plane(owner, tree, data, "BinkY", 520, uv, extension=extension)
    cr = _plane(owner, tree, data, "BinkCR", 330, uv, extension=extension)
    cb = _plane(owner, tree, data, "BinkCB", 140, uv, extension=extension)
    alpha = _plane(owner, tree, data, "BinkA", -50, uv, extension=extension)
    if luma is None:
        return None, alpha

    red, green, blue = _decode_rgb(tree, luma, cb, cr)

    combine = create_node(
        tree.nodes, "ShaderNodeCombineColor", location, label="Bink RGB Preview"
    )
    combine.mode = "RGB"
    for source, name in ((red, "Red"), (green, "Green"), (blue, "Blue")):
        if source is not None:
            tree.links.new(source, combine.inputs[name])
    return _srgb_to_linear(
        tree, combine.outputs["Color"], (location[0] + 220, location[1])
    ), alpha
