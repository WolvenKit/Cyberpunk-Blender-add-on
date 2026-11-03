import hashlib

from ..blender import shader_nodes
from ..materials.blender.nodes import create_node
from .bundles import material_bundle_node
from .graph import cp77_bitangent_socket, cp77_uv_tangent_node
from .mat_common import find_input, get_or_build_node_group, new_labeled_node

# Node group names are versioned because get_or_build_node_group returns any existing group
# of the same name. Without the suffix a scene carrying groups built by the previous
# implementation would silently keep the old arithmetic on re-import.
_GROUP_VERSION = "v2"


def create_scroll_group(layer, *, transparent=False):
    """Create stepped scrolling with increments of 1 / ScrollStepFactor"""
    suffix = f"_ps_t_{_GROUP_VERSION}" if transparent else f"_{_GROUP_VERSION}"
    group_name = f"scroll{layer}{suffix}"
    output_name = f"scroll{layer}"
    inputs = (
        ("NodeSocketFloat", f"ScrollSpeed{layer}"),
        ("NodeSocketFloat", f"ScrollStepFactor{layer}"),
        ("NodeSocketFloat", "Time"),
    )
    outputs = (("NodeSocketFloat", output_name),)

    def build(group):
        group_in = create_node(group.nodes, "NodeGroupInput", (-1400, 0))
        group_out = create_node(group.nodes, "NodeGroupOutput", (-600, 0))

        mul = shader_nodes.math(
            group.nodes, group.links, "MULTIPLY", location=(-1250, 0), hide=True
        ).node
        mul2 = shader_nodes.math(
            group.nodes, group.links, "MULTIPLY", location=(-1100, 0), hide=True
        ).node
        floor = shader_nodes.math(
            group.nodes, group.links, "FLOOR", location=(-950, 0), hide=True
        ).node
        div = shader_nodes.math(
            group.nodes, group.links, "DIVIDE", location=(-800, 0), hide=True
        ).node

        group.links.new(group_in.outputs["Time"], mul.inputs["Value"])
        group.links.new(
            group_in.outputs[f"ScrollSpeed{layer}"],
            shader_nodes.socket_by_identifier(mul.inputs, "Value_001"),
        )
        group.links.new(mul.outputs["Value"], mul2.inputs["Value"])
        group.links.new(
            group_in.outputs[f"ScrollStepFactor{layer}"],
            shader_nodes.socket_by_identifier(mul2.inputs, "Value_001"),
        )
        group.links.new(mul2.outputs["Value"], floor.inputs["Value"])
        group.links.new(floor.outputs["Value"], div.inputs["Value"])
        group.links.new(
            group_in.outputs[f"ScrollStepFactor{layer}"],
            shader_nodes.socket_by_identifier(div.inputs, "Value_001"),
        )
        group.links.new(div.outputs["Value"], group_out.inputs[output_name])

    return get_or_build_node_group(group_name, inputs, outputs, build)


def create_scroll_uv_group(layer, horizontal, *, transparent=False):
    """Build a wrapped scrolling band while passing through the other UV axis"""
    if horizontal:
        group_name = f"scrollUV{layer}X_{_GROUP_VERSION}"
    elif transparent:
        group_name = f"scrollUV{layer}_ps_t_{_GROUP_VERSION}"
    else:
        group_name = f"scrollUV{layer}_{_GROUP_VERSION}"
    output_name = f"scrollUV{layer}X" if horizontal else f"scrollUV{layer}"

    inputs = (
        ("NodeSocketVector", "newUV"),
        ("NodeSocketFloat", f"ScrollMaskHeight{layer}"),
        ("NodeSocketFloat", f"scroll{layer}"),
        ("NodeSocketFloat", f"ScrollMaskStartPoint{layer}"),
    )
    outputs = (("NodeSocketVector", output_name),)

    def build(group):
        group_in = create_node(group.nodes, "NodeGroupInput", (-1400, 0))
        group_out = create_node(group.nodes, "NodeGroupOutput", (-200, 0))
        separate_loc = (-1250, -100) if horizontal else (-1250, 100)
        combine_loc = (-350, -100) if horizontal else (-350, 100)
        separate = create_node(group.nodes, "ShaderNodeSeparateXYZ", separate_loc)
        div = shader_nodes.math(
            group.nodes, group.links, "DIVIDE", location=(-1250, 0), hide=True
        ).node
        mul = shader_nodes.math(
            group.nodes, group.links, "MULTIPLY", location=(-1100, 0), hide=True
        ).node
        add = shader_nodes.math(
            group.nodes, group.links, "ADD", location=(-950, 0), hide=True
        ).node
        frac = shader_nodes.math(
            group.nodes, group.links, "FRACT", location=(-800, 0), hide=True
        ).node
        mul2 = shader_nodes.math(
            group.nodes, group.links, "MULTIPLY", location=(-650, 0), hide=True
        ).node
        add2 = shader_nodes.math(
            group.nodes, group.links, "ADD", location=(-500, 0), hide=True
        ).node
        combine = create_node(group.nodes, "ShaderNodeCombineXYZ", combine_loc)
        div.inputs["Value"].default_value = 1
        scroll_axis = "X" if horizontal else "Y"
        passthrough_axis = "Y" if horizontal else "X"
        group.links.new(group_in.outputs["newUV"], separate.inputs["Vector"])
        group.links.new(
            group_in.outputs[f"ScrollMaskHeight{layer}"],
            shader_nodes.socket_by_identifier(div.inputs, "Value_001"),
        )
        group.links.new(separate.outputs[scroll_axis], mul.inputs["Value"])
        group.links.new(
            div.outputs["Value"],
            shader_nodes.socket_by_identifier(mul.inputs, "Value_001"),
        )
        group.links.new(mul.outputs["Value"], add.inputs["Value"])
        group.links.new(
            group_in.outputs[f"scroll{layer}"],
            shader_nodes.socket_by_identifier(add.inputs, "Value_001"),
        )
        group.links.new(add.outputs["Value"], frac.inputs["Value"])
        group.links.new(frac.outputs["Value"], mul2.inputs["Value"])
        group.links.new(
            group_in.outputs[f"ScrollMaskHeight{layer}"],
            shader_nodes.socket_by_identifier(mul2.inputs, "Value_001"),
        )
        group.links.new(mul2.outputs["Value"], add2.inputs["Value"])
        group.links.new(
            group_in.outputs[f"ScrollMaskStartPoint{layer}"],
            shader_nodes.socket_by_identifier(add2.inputs, "Value_001"),
        )
        group.links.new(add2.outputs["Value"], combine.inputs[scroll_axis])
        group.links.new(
            separate.outputs[passthrough_axis], combine.inputs[passthrough_axis]
        )
        group.links.new(combine.outputs["Vector"], group_out.inputs[output_name])

    return get_or_build_node_group(group_name, inputs, outputs, build)


def _build_camera_forward_vector(tree, *, location=(-1850, 250)):
    """Create a frame-constant world-space camera-forward vector"""
    nodes, links = tree.nodes, tree.links

    source = new_labeled_node(nodes, "ShaderNodeCombineXYZ", "Camera -Z", location)
    source.inputs["X"].default_value = 0.0
    source.inputs["Y"].default_value = 0.0
    source.inputs["Z"].default_value = -1.0

    transform = new_labeled_node(
        nodes,
        "ShaderNodeVectorTransform",
        "Camera Forward",
        (location[0] + 200, location[1]),
    )
    transform.vector_type = "VECTOR"
    transform.convert_from = "CAMERA"
    transform.convert_to = "WORLD"
    links.new(source.outputs["Vector"], transform.inputs["Vector"])
    return transform.outputs["Vector"]


def _build_camera_forward_parallax_offset(
    tree, *, y_scale=-1.0, location=(-1600, -420)
):
    """Project the camera-forward vector onto the tangent basis"""
    nodes, links = tree.nodes, tree.links

    forward = create_camera_forward_vector(
        tree, location=(location[0] - 200, location[1])
    )

    geometry = new_labeled_node(
        nodes,
        "ShaderNodeNewGeometry",
        "Parallax Geometry",
        (location[0], location[1] - 200),
    )
    tangent = cp77_uv_tangent_node(
        nodes, (location[0], location[1] - 380), label="UV Tangent"
    )
    tangent_socket = tangent.outputs["Tangent"]

    binormal = cp77_bitangent_socket(
        nodes,
        links,
        geometry.outputs.get("Normal"),
        tangent_socket,
        (location[0] + 220, location[1] - 380),
        label="UV Binormal",
    )

    left_right = shader_nodes.vector_math(
        nodes,
        links,
        "DOT_PRODUCT",
        forward,
        tangent_socket,
        name="leftRightDot",
        location=(location[0] + 440, location[1] + 80),
    )
    top_down = shader_nodes.vector_math(
        nodes,
        links,
        "DOT_PRODUCT",
        forward,
        binormal,
        name="topDownDot",
        location=(location[0] + 440, location[1] - 100),
    )

    scaled_y = shader_nodes.math(
        nodes,
        links,
        "MULTIPLY",
        top_down,
        y_scale,
        name="topDownDot scale",
        location=(location[0] + 660, location[1] - 100),
    )

    combine = new_labeled_node(
        nodes, "ShaderNodeCombineXYZ", "modUV", (location[0] + 880, location[1])
    )
    links.new(left_right, combine.inputs["X"])
    links.new(scaled_y, combine.inputs["Y"])
    return combine.outputs["Vector"]


_TAP_GRIDS = {
    1: ((0.0, 0.0),),
    4: ((-1.0, -1.0), (1.0, -1.0), (-1.0, 1.0), (1.0, 1.0)),
    5: ((0.0, 0.0), (-1.0, 0.0), (1.0, 0.0), (0.0, -1.0), (0.0, 1.0)),
    9: (
        (-1.0, -1.0),
        (0.0, -1.0),
        (1.0, -1.0),
        (-1.0, 0.0),
        (0.0, 0.0),
        (1.0, 0.0),
        (-1.0, 1.0),
        (0.0, 1.0),
        (1.0, 1.0),
    ),
}


def _build_mip_sampled_texture_nodes(
    tree,
    image,
    uv_socket,
    mip_level,
    *,
    taps,
    location,
    label,
    interpolation,
    extension,
):
    nodes, links = tree.nodes, tree.links
    offsets = _TAP_GRIDS[taps]

    width = image.size[0] or 1
    height = image.size[1] or 1
    footprint = float(2**mip_level)
    radius = footprint * 0.5
    step_u, step_v = radius / float(width), radius / float(height)

    color_sockets, alpha_sockets = [], []
    for index, (offset_u, offset_v) in enumerate(offsets):
        column, row = index % 3, index // 3
        node_location = (location[0] + column * 40, location[1] - row * 50)

        if offset_u == 0.0 and offset_v == 0.0:
            tap_uv = uv_socket
        else:
            shifted = shader_nodes.vector_math(
                nodes,
                links,
                "ADD",
                name=f"{label} mip{mip_level} tap{index}",
                location=node_location,
            ).node
            shader_nodes.socket_by_identifier(
                shifted.inputs, "Vector_001"
            ).default_value = (offset_u * step_u, offset_v * step_v, 0.0)
            links.new(uv_socket, shifted.inputs["Vector"])
            tap_uv = shifted.outputs["Vector"]

        texture = new_labeled_node(
            nodes,
            "ShaderNodeTexImage",
            f"{label} mip{mip_level}",
            (node_location[0] + 220, node_location[1]),
        )
        texture.image = image
        texture.interpolation = interpolation
        texture.extension = extension
        links.new(tap_uv, texture.inputs["Vector"])
        color_sockets.append(texture.outputs["Color"])
        alpha_sockets.append(texture.outputs["Alpha"])

    if len(color_sockets) == 1:
        return color_sockets[0], alpha_sockets[0]

    color_sum = color_sockets[0]
    for index, socket in enumerate(color_sockets[1:], start=1):
        mix = new_labeled_node(
            nodes,
            "ShaderNodeMix",
            f"{label} mip{mip_level} sum{index}",
            (location[0] + 460 + index * 30, location[1]),
        )
        mix.data_type = "RGBA"
        mix.blend_type = "ADD"
        shader_nodes.socket_by_identifier(
            mix.inputs, "Factor_Float"
        ).default_value = 1.0
        links.new(color_sum, shader_nodes.socket_by_identifier(mix.inputs, "A_Color"))
        links.new(socket, shader_nodes.socket_by_identifier(mix.inputs, "B_Color"))
        color_sum = shader_nodes.socket_by_identifier(mix.outputs, "Result_Color")

    alpha_sum = alpha_sockets[0]
    for index, socket in enumerate(alpha_sockets[1:], start=1):
        alpha_sum = shader_nodes.math(
            nodes,
            links,
            "ADD",
            alpha_sum,
            socket,
            name=f"{label} mip{mip_level} alpha{index}",
            location=(location[0] + 460 + index * 30, location[1] - 300),
        )

    inverse = 1.0 / float(len(color_sockets))
    average = new_labeled_node(
        nodes,
        "ShaderNodeMix",
        f"{label} mip{mip_level} average",
        (location[0] + 840, location[1]),
    )
    average.data_type = "RGBA"
    average.blend_type = "MULTIPLY"
    shader_nodes.socket_by_identifier(
        average.inputs, "Factor_Float"
    ).default_value = 1.0
    shader_nodes.socket_by_identifier(average.inputs, "B_Color").default_value = (
        inverse,
        inverse,
        inverse,
        1.0,
    )
    links.new(color_sum, shader_nodes.socket_by_identifier(average.inputs, "A_Color"))

    alpha_average = shader_nodes.math(
        nodes,
        links,
        "MULTIPLY",
        alpha_sum,
        inverse,
        name=f"{label} mip{mip_level} alpha average",
        location=(location[0] + 840, location[1] - 300),
    )
    return shader_nodes.socket_by_identifier(
        average.outputs, "Result_Color"
    ), alpha_average


def _mip_sampler_group(image, mip_level, taps, interpolation, extension):
    source_key = "|".join(
        (
            str(getattr(image, "name", "")),
            str(getattr(image, "filepath_raw", "") or getattr(image, "filepath", "")),
            f"{int(image.size[0])}x{int(image.size[1])}",
            str(getattr(getattr(image, "colorspace_settings", None), "name", "")),
            str(mip_level),
            str(taps),
            str(interpolation),
            str(extension),
        )
    )
    digest = hashlib.blake2b(source_key.encode("utf-8"), digest_size=10).hexdigest()
    group_name = f"CP77 Mip Sampler {digest} v1"

    def build(group):
        group_input = create_node(group.nodes, "NodeGroupInput", (-1000, 0))
        group_output = create_node(group.nodes, "NodeGroupOutput", (300, 0))
        color, alpha = _build_mip_sampled_texture_nodes(
            group,
            image,
            group_input.outputs["UV"],
            mip_level,
            taps=taps,
            location=(-800, 150),
            label="Mip Sample",
            interpolation=interpolation,
            extension=extension,
        )
        group.links.new(color, group_output.inputs["Color"])
        group.links.new(alpha, group_output.inputs["Alpha"])

    return get_or_build_node_group(
        group_name,
        (("NodeSocketVector", "UV"),),
        (("NodeSocketColor", "Color"), ("NodeSocketFloat", "Alpha")),
        build,
    )


def mip_sampler_group(
    image, mip_level, *, taps=9, interpolation="Linear", extension="EXTEND"
):
    """The shared box-tap sampler group for image at mip_level"""
    normalized_taps = taps if taps in _TAP_GRIDS else 9
    return _mip_sampler_group(
        image, max(0, int(mip_level)), normalized_taps, interpolation, extension
    )


def create_mip_sampled_texture(
    tree,
    image,
    uv_socket,
    mip_level,
    *,
    taps=9,
    location=(-900, 0),
    label="ParalaxTexture",
    interpolation="Linear",
    extension="EXTEND",
):
    """Approximate a coarse texture footprint with a shared box-tap sampler"""
    if image is None:
        return None, None

    group = mip_sampler_group(
        image, mip_level, taps=taps, interpolation=interpolation, extension=extension
    )
    sampler = material_bundle_node(
        tree,
        group,
        location,
        f"{label} · Mip {max(0, int(mip_level))}",
        {"UV": uv_socket},
    )
    return sampler.outputs["Color"], sampler.outputs["Alpha"]


def retarget_mip_sampler(
    node, image, mip_level, *, taps=9, interpolation="Linear", extension="EXTEND"
):
    """Point a sampler node made by create_mip_sampled_texture at image"""
    group = mip_sampler_group(
        image, mip_level, taps=taps, interpolation=interpolation, extension=extension
    )
    if node.node_tree is not group:
        node.node_tree = group
    node["cp77_material_bundle"] = group.name


def create_tiled_uv(tree, tiling_x, tiling_y, offset_x, offset_y, location=(-1600, 0)):
    """Origin-anchored tiling"""
    nodes = tree.nodes
    links = tree.links
    texcoord = new_labeled_node(nodes, "ShaderNodeTexCoord", "UV", location)
    mapping = new_labeled_node(
        nodes,
        "ShaderNodeMapping",
        "Neon Parallax UV Transform",
        (location[0] + 200, location[1]),
    )
    vector_input = find_input(mapping, "Vector") or mapping.inputs["Vector"]
    links.new(texcoord.outputs["UV"], vector_input)
    location_input = find_input(mapping, "Location")
    scale_input = find_input(mapping, "Scale")
    if location_input is not None:
        location_input.default_value = (float(offset_x), float(offset_y), 0.0)
    if scale_input is not None:
        scale_input.default_value = (float(tiling_x), float(tiling_y), 1.0)
    return mapping.outputs["Vector"]


def create_camera_forward_vector(tree, *, location=(-1850, 250)):
    def build(group):
        output = group.nodes.new("NodeGroupOutput")
        forward = _build_camera_forward_vector(group, location=(0, 0))
        group.links.new(forward, output.inputs["Direction"])

    group = get_or_build_node_group(
        "CP77 Camera Forward Bundle v2",
        (),
        (("NodeSocketVector", "Direction"),),
        build,
    )
    return material_bundle_node(
        tree, group, location, "Camera Forward · World", {}
    ).outputs["Direction"]


def create_camera_forward_parallax_offset(
    tree, *, y_scale=-1.0, location=(-1600, -420)
):
    def build(group):
        source = group.nodes.new("NodeGroupInput")
        output = group.nodes.new("NodeGroupOutput")
        offset = _build_camera_forward_parallax_offset(
            group,
            y_scale=source.outputs["Binormal Sign"],
            location=(0, 0),
        )
        group.links.new(offset, output.inputs["Offset"])

    group = get_or_build_node_group(
        "CP77 Camera Tangent Projection Bundle v2",
        (("NodeSocketFloat", "Binormal Sign"),),
        (("NodeSocketVector", "Offset"),),
        build,
    )
    return material_bundle_node(
        tree,
        group,
        location,
        "Camera Tangent Projection",
        {"Binormal Sign": y_scale},
    ).outputs["Offset"]
