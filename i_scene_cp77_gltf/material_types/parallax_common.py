<<<<<<< Updated upstream
from ..materials.blender.nodes import create_node
from .graph import math_socket, vector_math_socket
from .mat_common import find_input, get_or_build_node_group, new_labeled_node, set_scene_fps_driver
=======
import hashlib

from ..blender import shader_nodes
from ..materials.blender.nodes import create_node
from .bundles import material_bundle_node
from .graph import cp77_bitangent_socket, cp77_uv_tangent_node
from .mat_common import find_input, get_or_build_node_group, new_labeled_node
>>>>>>> Stashed changes

# Node group names are versioned because get_or_build_node_group returns any existing group
# of the same name. Without the suffix a scene carrying groups built by the previous
# implementation would silently keep the old arithmetic on re-import.
_GROUP_VERSION = "v2"


<<<<<<< Updated upstream
def param_component(data, key, component=None, default=0.0):
    """Read a parameter authored as a Scalar in one template and a Vector in another.

    ScanlinesDensity and ImageScale both change type across the parallaxscreen family:
    ScanlinesDensity is Scalar in parallaxscreen and parallaxscreen_transparent but Vector
    in parallaxscreen_transparent_ui; ImageScale is the reverse.
    """
    value = data.get(key) if isinstance(data, dict) else None
    if value is None:
        return float(default)

    if isinstance(value, dict):
        if component is not None and component in value:
            return float(value[component])
        for name in ("X", "Red"):
            if name in value:
                return float(value[name])
        return float(default)

    if isinstance(value, (list, tuple)):
        index = {"X": 0, "Y": 1, "Z": 2, "W": 3}.get(component or "X", 0)
        return float(value[index]) if index < len(value) else float(default)

    try:
        # A scalar authored where a vector component was requested broadcasts to every axis.
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def create_scroll_group(layer, *, transparent=False):
    """scrollN = floor( (Time * ScrollSpeedN) * ScrollStepFactorN ) / ScrollStepFactorN

    parallaxscreen.fx:40,43 and parallaxscreen_transparent.fx:93,96 are identical. The floor
    sits between the multiply and the divide, which is what makes ScrollStepFactor a
    quantiser: the scroll advances in steps of 1/ScrollStepFactor. Flooring after the divide
    cancels the factor and quantises to whole units instead.
    """
=======
def create_scroll_group(layer, *, transparent=False):
    """Create stepped scrolling with increments of 1 / ScrollStepFactor"""
>>>>>>> Stashed changes
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

<<<<<<< Updated upstream
        mul = create_node(group.nodes, "ShaderNodeMath", (-1250, 0), operation="MULTIPLY")
        mul2 = create_node(group.nodes, "ShaderNodeMath", (-1100, 0), operation="MULTIPLY")
        floor = create_node(group.nodes, "ShaderNodeMath", (-950, 0), operation="FLOOR")
        div = create_node(group.nodes, "ShaderNodeMath", (-800, 0), operation="DIVIDE")

        group.links.new(group_in.outputs[2], mul.inputs[0])
        group.links.new(group_in.outputs[0], mul.inputs[1])
        group.links.new(mul.outputs[0], mul2.inputs[0])
        group.links.new(group_in.outputs[1], mul2.inputs[1])
        group.links.new(mul2.outputs[0], floor.inputs[0])
        group.links.new(floor.outputs[0], div.inputs[0])
        group.links.new(group_in.outputs[1], div.inputs[1])
        group.links.new(div.outputs[0], group_out.inputs[0])
=======
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
>>>>>>> Stashed changes

    return get_or_build_node_group(group_name, inputs, outputs, build)


def create_scroll_uv_group(layer, horizontal, *, transparent=False):
<<<<<<< Updated upstream
    """scrollUVN = frac( newUV.axis / ScrollMaskHeightN + scrollN ) * ScrollMaskHeightN
                   + ScrollMaskStartPointN, with the other axis passed through.

    Matches parallaxscreen.fx:41-45. The transparent flag affects only group naming; the
    arithmetic is identical in both shaders.
    """
=======
    """Build a wrapped scrolling band while passing through the other UV axis"""
>>>>>>> Stashed changes
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
<<<<<<< Updated upstream
        div = create_node(group.nodes, "ShaderNodeMath", (-1250, 0), operation="DIVIDE")
        mul = create_node(group.nodes, "ShaderNodeMath", (-1100, 0), operation="MULTIPLY")
        add = create_node(group.nodes, "ShaderNodeMath", (-950, 0), operation="ADD")
        frac = create_node(group.nodes, "ShaderNodeMath", (-800, 0), operation="FRACT")
        mul2 = create_node(group.nodes, "ShaderNodeMath", (-650, 0), operation="MULTIPLY")
        add2 = create_node(group.nodes, "ShaderNodeMath", (-500, 0), operation="ADD")
        combine = create_node(group.nodes, "ShaderNodeCombineXYZ", combine_loc)
        div.inputs[0].default_value = 1
        scroll_axis = 0 if horizontal else 1
        passthrough_axis = 1 if horizontal else 0
        group.links.new(group_in.outputs[0], separate.inputs[0])
        group.links.new(group_in.outputs[1], div.inputs[1])
        group.links.new(separate.outputs[scroll_axis], mul.inputs[0])
        group.links.new(div.outputs[0], mul.inputs[1])
        group.links.new(mul.outputs[0], add.inputs[0])
        group.links.new(group_in.outputs[2], add.inputs[1])
        group.links.new(add.outputs[0], frac.inputs[0])
        group.links.new(frac.outputs[0], mul2.inputs[0])
        group.links.new(group_in.outputs[1], mul2.inputs[1])
        group.links.new(mul2.outputs[0], add2.inputs[0])
        group.links.new(group_in.outputs[3], add2.inputs[1])
        group.links.new(add2.outputs[0], combine.inputs[scroll_axis])
        group.links.new(separate.outputs[passthrough_axis], combine.inputs[passthrough_axis])
        group.links.new(combine.outputs[0], group_out.inputs[0])
=======
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
>>>>>>> Stashed changes

    return get_or_build_node_group(group_name, inputs, outputs, build)


<<<<<<< Updated upstream
def create_image_scale_uv(tree, scale_x, scale_y=None, *, offset_x=0.0, offset_y=0.0,
                          wrap=False, location=(-1600, 0)):
    """newUV = ((UV - 0.5 + TextureOffset) * ImageScale) + 0.5

    parallaxscreen.fx:38 scales about the UV centre rather than the origin, so ImageScale
    zooms in place. parallaxscreen_transparent.fx:89 wraps the result in frac() and carries a
    TextureOffset; wrap selects that form.
    """
    nodes, links = tree.nodes, tree.links
    scale_y = scale_x if scale_y is None else scale_y

    texcoord = new_labeled_node(nodes, "ShaderNodeTexCoord", "UV", location)
    centre = new_labeled_node(nodes, "ShaderNodeVectorMath", "Centre UV",
                              (location[0] + 200, location[1]))
    centre.operation = "ADD"
    centre.inputs[1].default_value = (-0.5 + float(offset_x), -0.5 + float(offset_y), 0.0)
    links.new(texcoord.outputs["UV"], centre.inputs[0])

    scaled = new_labeled_node(nodes, "ShaderNodeVectorMath", "ImageScale",
                              (location[0] + 380, location[1]))
    scaled.operation = "MULTIPLY"
    scaled.inputs[1].default_value = (float(scale_x), float(scale_y), 1.0)
    links.new(centre.outputs["Vector"], scaled.inputs[0])

    recentre = new_labeled_node(nodes, "ShaderNodeVectorMath", "newUV",
                                (location[0] + 560, location[1]))
    recentre.operation = "ADD"
    recentre.inputs[1].default_value = (0.5, 0.5, 0.0)
    links.new(scaled.outputs["Vector"], recentre.inputs[0])
    result = recentre.outputs["Vector"]

    if wrap:
        fract = new_labeled_node(nodes, "ShaderNodeVectorMath", "frac(newUV)",
                                 (location[0] + 740, location[1]))
        fract.operation = "FRACTION"
        links.new(result, fract.inputs[0])
        result = fract.outputs["Vector"]
    return result


def create_camera_forward_vector(tree, *, location=(-1850, 250)):
    """SC_CameraVectorForward.xyz, recovered as camera-space -Z transformed into world space.

    Constant across the surface for a given frame, unlike ShaderNodeNewGeometry's Incoming
    output. Substituting a per-pixel view direction makes the parallax layer separation fan
    out toward the screen edges where the engine shifts it rigidly.
    """
    nodes, links = tree.nodes, tree.links

    source = new_labeled_node(nodes, "ShaderNodeCombineXYZ", "Camera -Z", location)
    source.inputs[0].default_value = 0.0
    source.inputs[1].default_value = 0.0
    source.inputs[2].default_value = -1.0

    transform = new_labeled_node(nodes, "ShaderNodeVectorTransform", "SC_CameraVectorForward",
                                 (location[0] + 200, location[1]))
    transform.vector_type = "VECTOR"
    transform.convert_from = "CAMERA"
    transform.convert_to = "WORLD"
    links.new(source.outputs["Vector"], transform.inputs[0])
    return transform.outputs["Vector"]


def create_camera_forward_parallax_offset(tree, *, y_scale=-1.0, location=(-1600, -420)):
    """modUV = float2( dot(cameraForward, WorldTangent), dot(cameraForward, WorldBinormal) * y_scale )

    parallaxscreen.fx:31-34 and parallaxscreen_transparent.fx:73-78 both use
    SC_CameraVectorForward, which is constant across the surface for a given frame. It is
    recovered exactly here by transforming camera-space -Z into world space, rather than
    substituting a per-pixel view direction, which would make the layer separation fan out
    toward the screen edges instead of shifting rigidly across the surface.

    Neither shader divides by the tangent-space Z or applies a bias.

    y_scale carries HSV_Mod.w in parallaxscreen and a hardcoded -1 in
    parallaxscreen_transparent; it accepts a float or a socket.
    """
    nodes, links = tree.nodes, tree.links

    forward = create_camera_forward_vector(tree, location=(location[0] - 200, location[1]))

    geometry = new_labeled_node(nodes, "ShaderNodeNewGeometry", "Parallax Geometry",
                                (location[0], location[1] - 200))
    tangent = new_labeled_node(nodes, "ShaderNodeTangent", "UV Tangent",
                               (location[0], location[1] - 380))
    try:
        tangent.direction_type = "UV_MAP"
    except (AttributeError, TypeError, ValueError):
        pass
    tangent_socket = tangent.outputs.get("Tangent") or tangent.outputs[0]

    # The engine reads WorldBinormal from the vertex stream; Blender reconstructs it as
    # cross(N, T), which agrees for standard tangent handedness.
    binormal = vector_math_socket(
        nodes, links, "CROSS_PRODUCT", "UV Binormal",
        (location[0] + 220, location[1] - 380),
        geometry.outputs.get("Normal"), tangent_socket,
    )

    left_right = vector_math_socket(
        nodes, links, "DOT_PRODUCT", "leftRightDot",
        (location[0] + 440, location[1] + 80),
        forward, tangent_socket,
    )
    top_down = vector_math_socket(
        nodes, links, "DOT_PRODUCT", "topDownDot",
        (location[0] + 440, location[1] - 100),
        forward, binormal,
    )

    scaled_y = math_socket(
        nodes, links, "MULTIPLY", "topDownDot scale",
        (location[0] + 660, location[1] - 100),
        top_down, y_scale,
    )

    combine = new_labeled_node(nodes, "ShaderNodeCombineXYZ", "modUV",
                               (location[0] + 880, location[1]))
    links.new(left_right, combine.inputs[0])
    links.new(scaled_y, combine.inputs[1])
    return combine.outputs.get("Vector") or combine.outputs[0]


def create_layer_uv(tree, base_uv, mod_uv, separation, multiplier, *, clamp=True,
                    location=(-1200, 0), label="layer UV"):
    """lN = saturate( newUV + modUV * LayersSeparation * multiplier )

    parallaxscreen.fx:65-67. The saturate holds the edge texel where an image node set to
    CLIP would instead go transparent, so it is built explicitly rather than left to the
    texture extension mode.
    """
    nodes, links = tree.nodes, tree.links

    if multiplier == 0:
        offset_uv = base_uv
    else:
        scaled = new_labeled_node(nodes, "ShaderNodeVectorMath", f"{label} separation",
                                  location)
        scaled.operation = "SCALE"
        scale_input = scaled.inputs[3]
        if hasattr(separation, "is_output"):
            links.new(separation, scale_input)
        else:
            scale_input.default_value = float(separation) * float(multiplier)
        links.new(mod_uv, scaled.inputs[0])
        scaled_out = scaled.outputs["Vector"]

        if hasattr(separation, "is_output") and multiplier != 1:
            stepped = new_labeled_node(nodes, "ShaderNodeVectorMath", f"{label} step",
                                       (location[0] + 180, location[1]))
            stepped.operation = "SCALE"
            stepped.inputs[3].default_value = float(multiplier)
            links.new(scaled_out, stepped.inputs[0])
            scaled_out = stepped.outputs["Vector"]

        added = new_labeled_node(nodes, "ShaderNodeVectorMath", label,
                                 (location[0] + 360, location[1]))
        added.operation = "ADD"
        links.new(base_uv, added.inputs[0])
        links.new(scaled_out, added.inputs[1])
        offset_uv = added.outputs["Vector"]

    if not clamp:
        return offset_uv

    upper = new_labeled_node(nodes, "ShaderNodeVectorMath", f"{label} saturate hi",
                             (location[0] + 540, location[1]))
    upper.operation = "MINIMUM"
    upper.inputs[1].default_value = (1.0, 1.0, 1.0)
    links.new(offset_uv, upper.inputs[0])

    lower = new_labeled_node(nodes, "ShaderNodeVectorMath", f"{label} saturate lo",
                             (location[0] + 720, location[1]))
    lower.operation = "MAXIMUM"
    lower.inputs[1].default_value = (0.0, 0.0, 0.0)
    links.new(upper.outputs["Vector"], lower.inputs[0])
    return lower.outputs["Vector"]
=======
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
>>>>>>> Stashed changes


_TAP_GRIDS = {
    1: ((0.0, 0.0),),
    4: ((-1.0, -1.0), (1.0, -1.0), (-1.0, 1.0), (1.0, 1.0)),
    5: ((0.0, 0.0), (-1.0, 0.0), (1.0, 0.0), (0.0, -1.0), (0.0, 1.0)),
<<<<<<< Updated upstream
    9: ((-1.0, -1.0), (0.0, -1.0), (1.0, -1.0),
        (-1.0, 0.0), (0.0, 0.0), (1.0, 0.0),
        (-1.0, 1.0), (0.0, 1.0), (1.0, 1.0)),
}


def create_mip_sampled_texture(tree, image, uv_socket, mip_level, *, taps=9,
                               location=(-900, 0), label="ParalaxTexture",
                               interpolation="Linear", extension="EXTEND"):
    """Approximate SampleIndirectLevel(tex, uv, mip_level) with a box tap average.

    parallaxscreen.fx:73-74 forces the second and third parallax layers to mips 2 and 3, so
    the ghosting is progressively blurred rather than only offset and dimmed. Blender's
    shader graph exposes no per-sample LOD, so the footprint of mip N -- 2^N texels -- is
    approximated by averaging taps spread over that radius.

    Cost is one image sample per tap, so nine taps on two layers adds eighteen samples.
    Falling back to taps=4 gives a single box reduction; taps=1 disables the blur.

    Returns (color_socket, alpha_socket), or (None, None) when no image is bound.
    """
    if image is None:
        return None, None

    nodes, links = tree.nodes, tree.links
    offsets = _TAP_GRIDS.get(taps, _TAP_GRIDS[9])

    width = image.size[0] or 1
    height = image.size[1] or 1
    footprint = float(2 ** max(0, int(mip_level)))
=======
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
>>>>>>> Stashed changes
    radius = footprint * 0.5
    step_u, step_v = radius / float(width), radius / float(height)

    color_sockets, alpha_sockets = [], []
    for index, (offset_u, offset_v) in enumerate(offsets):
        column, row = index % 3, index // 3
        node_location = (location[0] + column * 40, location[1] - row * 50)

        if offset_u == 0.0 and offset_v == 0.0:
            tap_uv = uv_socket
        else:
<<<<<<< Updated upstream
            shifted = new_labeled_node(nodes, "ShaderNodeVectorMath",
                                       f"{label} mip{mip_level} tap{index}", node_location)
            shifted.operation = "ADD"
            shifted.inputs[1].default_value = (offset_u * step_u, offset_v * step_v, 0.0)
            links.new(uv_socket, shifted.inputs[0])
            tap_uv = shifted.outputs["Vector"]

        texture = new_labeled_node(nodes, "ShaderNodeTexImage", f"{label} mip{mip_level}",
                                   (node_location[0] + 220, node_location[1]))
=======
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
>>>>>>> Stashed changes
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
<<<<<<< Updated upstream
        mix = new_labeled_node(nodes, "ShaderNodeMixRGB",
                               f"{label} mip{mip_level} sum{index}",
                               (location[0] + 460 + index * 30, location[1]))
        mix.blend_type = "ADD"
        mix.inputs[0].default_value = 1.0
        links.new(color_sum, mix.inputs[1])
        links.new(socket, mix.inputs[2])
        color_sum = mix.outputs[0]

    alpha_sum = alpha_sockets[0]
    for index, socket in enumerate(alpha_sockets[1:], start=1):
        alpha_sum = math_socket(
            nodes, links, "ADD", f"{label} mip{mip_level} alpha{index}",
            (location[0] + 460 + index * 30, location[1] - 300),
            alpha_sum, socket,
        )

    inverse = 1.0 / float(len(color_sockets))
    average = new_labeled_node(nodes, "ShaderNodeMixRGB", f"{label} mip{mip_level} average",
                               (location[0] + 840, location[1]))
    average.blend_type = "MULTIPLY"
    average.inputs[0].default_value = 1.0
    average.inputs[2].default_value = (inverse, inverse, inverse, 1.0)
    links.new(color_sum, average.inputs[1])

    alpha_average = math_socket(
        nodes, links, "MULTIPLY", f"{label} mip{mip_level} alpha average",
        (location[0] + 840, location[1] - 300),
        alpha_sum, inverse,
    )
    return average.outputs[0], alpha_average


def create_scanline_mask(tree, image, scanlines_density, scanlines_intensity, *,
                         scroll_rate=2.0, density_on_u=False, location=(-1600, 400)):
    """lineMask = lerp( ScanlinesIntensity, 1, ScanlineTexture( UV * (1, density) + 2*Time ).x )

    parallaxscreen.fx:85-87. The scroll rate is a hardcoded 2.0 on both axes and the density
    scales V only, unlike metal_base_ui.fx where the rate came from ScanlinesDensity.zw.
    Time is exposed as a Value node because Blender has no SC_TimeVector.
    """
    nodes, links = tree.nodes, tree.links

    texcoord = new_labeled_node(nodes, "ShaderNodeTexCoord", "Scanline UV", location)
    density = new_labeled_node(nodes, "ShaderNodeVectorMath", "ScanlinesDensity",
                               (location[0] + 200, location[1]))
    density.operation = "MULTIPLY"
    density.inputs[1].default_value = (
        float(scanlines_density) if density_on_u else 1.0,
        float(scanlines_density),
        1.0,
    )
    links.new(texcoord.outputs["UV"], density.inputs[0])

    time = new_labeled_node(nodes, "ShaderNodeValue", "Time",
                            (location[0] + 200, location[1] - 180))
    time.outputs[0].default_value = 0.0
    time_driver = time.outputs[0].driver_add("default_value")
    set_scene_fps_driver(time_driver.driver)

    scroll = math_socket(
        nodes, links, "MULTIPLY", "Scanline scroll",
        (location[0] + 380, location[1] - 180),
        time.outputs[0], float(scroll_rate),
    )
    scroll_vector = new_labeled_node(nodes, "ShaderNodeCombineXYZ", "Scanline scroll UV",
                                     (location[0] + 560, location[1] - 180))
    links.new(scroll, scroll_vector.inputs[0])
    links.new(scroll, scroll_vector.inputs[1])

    offset = new_labeled_node(nodes, "ShaderNodeVectorMath", "scanlineUV",
                              (location[0] + 560, location[1]))
    offset.operation = "ADD"
    links.new(density.outputs["Vector"], offset.inputs[0])
    links.new(scroll_vector.outputs["Vector"], offset.inputs[1])

    texture = new_labeled_node(nodes, "ShaderNodeTexImage", "ScanlineTexture",
                               (location[0] + 740, location[1]))
    texture.image = image
    links.new(offset.outputs["Vector"], texture.inputs["Vector"])

    line_mask = new_labeled_node(nodes, "ShaderNodeMapRange", "lineMask",
                                 (location[0] + 960, location[1]))
    line_mask.inputs[1].default_value = 0.0
    line_mask.inputs[2].default_value = 1.0
    line_mask.inputs[3].default_value = float(scanlines_intensity)
    line_mask.inputs[4].default_value = 1.0
    links.new(texture.outputs["Color"], line_mask.inputs[0])
    return line_mask.outputs["Result"]


def create_screen_blend(tree, sockets, *, location=(-400, 0), label="screen"):
    """m2 = 1-(1-i3)*(1-i2); m3 = 1-(1-m2)*(1-i1)

    parallaxscreen.fx:92-93 composites the layers back to front with a screen blend.
    """
    nodes, links = tree.nodes, tree.links
    if not sockets:
        return None

    composite = sockets[-1]
    for index in range(len(sockets) - 2, -1, -1):
        mix = new_labeled_node(nodes, "ShaderNodeMixRGB", f"{label} {index + 1}",
                               (location[0] + (len(sockets) - index) * 180, location[1]))
        mix.blend_type = "SCREEN"
        mix.inputs[0].default_value = 1.0
        links.new(composite, mix.inputs[1])
        links.new(sockets[index], mix.inputs[2])
        composite = mix.outputs[0]
    return composite


def create_tiled_uv(tree, tiling_x, tiling_y, offset_x, offset_y, location=(-1600, 0)):
    """Origin-anchored tiling.

    Retained for callers wanting plain tiling; the shaders use the centre-anchored form in
    create_image_scale_uv.
    """
=======
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
>>>>>>> Stashed changes
    nodes = tree.nodes
    links = tree.links
    texcoord = new_labeled_node(nodes, "ShaderNodeTexCoord", "UV", location)
    mapping = new_labeled_node(
        nodes,
        "ShaderNodeMapping",
        "Neon Parallax UV Transform",
        (location[0] + 200, location[1]),
    )
<<<<<<< Updated upstream
    vector_input = find_input(mapping, "Vector") or mapping.inputs[0]
=======
    vector_input = find_input(mapping, "Vector") or mapping.inputs["Vector"]
>>>>>>> Stashed changes
    links.new(texcoord.outputs["UV"], vector_input)
    location_input = find_input(mapping, "Location")
    scale_input = find_input(mapping, "Scale")
    if location_input is not None:
        location_input.default_value = (float(offset_x), float(offset_y), 0.0)
    if scale_input is not None:
        scale_input.default_value = (float(tiling_x), float(tiling_y), 1.0)
<<<<<<< Updated upstream
    return mapping.outputs.get("Vector") or mapping.outputs[0]


def create_tangent_parallax_offset(tree, *, flipped=False, bias=None, location=(-1600, -420)):
    """Compatibility entry point for create_camera_forward_parallax_offset.

    The previous implementation built a per-pixel view vector divided by tangent-space Z and
    scaled by a bias; neither shader does either, so bias is accepted and ignored. flipped
    maps onto the sign the shaders apply to the binormal dot.
    """
    return create_camera_forward_parallax_offset(
        tree, y_scale=1.0 if flipped else -1.0, location=location
    )
=======
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
>>>>>>> Stashed changes
