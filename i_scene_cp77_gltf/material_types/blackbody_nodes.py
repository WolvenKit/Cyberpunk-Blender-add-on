from ..blender import shader_nodes
from .bundles import material_bundle_node
from .graph import combine_color_socket, mix_scalar_socket
from .mat_common import get_or_build_node_group, new_labeled_node


def _build_rgb_to_hsv_nodes(nodes, links, color, location, label):
    x0, y0 = location
    split = new_labeled_node(nodes, "ShaderNodeSeparateColor", f"{label} RGB", (x0, y0))
    split.mode = "RGB"
    links.new(color, split.inputs["Color"])
    r, g, b = split.outputs["Red"], split.outputs["Green"], split.outputs["Blue"]

    max_rg = shader_nodes.math(
        nodes,
        links,
        "MAXIMUM",
        r,
        g,
        name=f"{label} max RG",
        location=(x0 + 180, y0 + 120),
    )
    value = shader_nodes.math(
        nodes,
        links,
        "MAXIMUM",
        max_rg,
        b,
        name=f"{label} Value",
        location=(x0 + 360, y0 + 120),
    )
    min_rg = shader_nodes.math(
        nodes,
        links,
        "MINIMUM",
        r,
        g,
        name=f"{label} min RG",
        location=(x0 + 180, y0 - 140),
    )
    minimum = shader_nodes.math(
        nodes,
        links,
        "MINIMUM",
        min_rg,
        b,
        name=f"{label} Min",
        location=(x0 + 360, y0 - 140),
    )
    chroma = shader_nodes.math(
        nodes,
        links,
        "SUBTRACT",
        value,
        minimum,
        name=f"{label} Chroma",
        location=(x0 + 540, y0),
    )
    active = shader_nodes.math(
        nodes,
        links,
        "GREATER_THAN",
        chroma,
        0.0,
        name=f"{label} Chroma != 0",
        location=(x0 + 720, y0 - 220),
    )

    safe_chroma = shader_nodes.math(
        nodes,
        links,
        "MAXIMUM",
        chroma,
        1.0e-20,
        name=f"{label} Chroma Safe",
        location=(x0 + 720, y0),
    )
    safe_value = shader_nodes.math(
        nodes,
        links,
        "MAXIMUM",
        value,
        1.0e-20,
        name=f"{label} Value Safe",
        location=(x0 + 720, y0 + 120),
    )
    sat_raw = shader_nodes.math(
        nodes,
        links,
        "DIVIDE",
        chroma,
        safe_value,
        name=f"{label} Saturation Raw",
        location=(x0 + 900, y0 + 120),
    )
    saturation = shader_nodes.math(
        nodes,
        links,
        "MULTIPLY",
        sat_raw,
        active,
        name=f"{label} Saturation",
        location=(x0 + 1080, y0 + 120),
    )

    deltas = []
    for channel, name, y in ((r, "R", 0), (g, "G", -100), (b, "B", -200)):
        numerator = shader_nodes.math(
            nodes,
            links,
            "SUBTRACT",
            value,
            channel,
            name=f"{label} Delta {name} Num",
            location=(x0 + 900, y0 + y),
        )
        deltas.append(
            shader_nodes.math(
                nodes,
                links,
                "DIVIDE",
                numerator,
                safe_chroma,
                name=f"{label} Delta {name}",
                location=(x0 + 1080, y0 + y),
            )
        )
    dr, dg, db = deltas
    delta_r = shader_nodes.math(
        nodes,
        links,
        "SUBTRACT",
        dr,
        db,
        name=f"{label} Delta.r",
        location=(x0 + 1260, y0),
    )
    delta_g = shader_nodes.math(
        nodes,
        links,
        "SUBTRACT",
        dg,
        dr,
        name=f"{label} Delta.g",
        location=(x0 + 1260, y0 - 100),
    )
    delta_b = shader_nodes.math(
        nodes,
        links,
        "SUBTRACT",
        db,
        dg,
        name=f"{label} Delta.b",
        location=(x0 + 1260, y0 - 200),
    )
    delta_r = shader_nodes.math(
        nodes,
        links,
        "ADD",
        delta_r,
        2.0,
        name=f"{label} Delta.r + 2",
        location=(x0 + 1440, y0),
    )
    delta_g = shader_nodes.math(
        nodes,
        links,
        "ADD",
        delta_g,
        4.0,
        name=f"{label} Delta.g + 4",
        location=(x0 + 1440, y0 - 100),
    )

    r_less = shader_nodes.math(
        nodes,
        links,
        "LESS_THAN",
        r,
        value,
        name=f"{label} R < Value",
        location=(x0 + 1260, y0 + 220),
    )
    g_less = shader_nodes.math(
        nodes,
        links,
        "LESS_THAN",
        g,
        value,
        name=f"{label} G < Value",
        location=(x0 + 1440, y0 + 220),
    )
    gb = mix_scalar_socket(
        nodes,
        links,
        f"{label} G/B Hue",
        (x0 + 1620, y0 - 140),
        delta_r,
        delta_g,
        g_less,
    )
    hue6 = mix_scalar_socket(
        nodes, links, f"{label} R/(G/B) Hue", (x0 + 1800, y0 - 40), delta_b, gb, r_less
    )
    hue = shader_nodes.math(
        nodes,
        links,
        "DIVIDE",
        hue6,
        6.0,
        name=f"{label} Hue / 6",
        location=(x0 + 1980, y0 - 40),
    )
    hue = shader_nodes.math(
        nodes, links, "FRACT", hue, name=f"{label} Hue", location=(x0 + 2160, y0 - 40)
    )
    hue = shader_nodes.math(
        nodes,
        links,
        "MULTIPLY",
        hue,
        active,
        name=f"{label} Hue Active",
        location=(x0 + 2340, y0 - 40),
    )
    return hue, saturation, value


def _build_hsv_to_rgb_nodes(nodes, links, hue, saturation, value, location, label):
    x0, y0 = location
    hue = shader_nodes.math(
        nodes, links, "FRACT", hue, name=f"{label} Hue frac", location=(x0, y0)
    )
    h6 = shader_nodes.math(
        nodes,
        links,
        "MULTIPLY",
        hue,
        6.0,
        name=f"{label} Hue x6",
        location=(x0 + 180, y0),
    )

    components = []
    for name, offset, y in (("R", 3.0, 160), ("G", 2.0, 0), ("B", 4.0, -160)):
        shifted = shader_nodes.math(
            nodes,
            links,
            "SUBTRACT",
            h6,
            offset,
            name=f"{label} {name} Hue Shift",
            location=(x0 + 360, y0 + y),
        )
        absolute = shader_nodes.math(
            nodes,
            links,
            "ABSOLUTE",
            shifted,
            name=f"{label} {name} abs",
            location=(x0 + 540, y0 + y),
        )
        # use_clamp saturates the hue ramp to [0, 1].
        if name == "R":
            components.append(
                shader_nodes.math(
                    nodes,
                    links,
                    "SUBTRACT",
                    absolute,
                    1.0,
                    name=f"{label} Hue {name}",
                    location=(x0 + 720, y0 + y),
                    use_clamp=True,
                )
            )
        else:
            components.append(
                shader_nodes.math(
                    nodes,
                    links,
                    "SUBTRACT",
                    2.0,
                    absolute,
                    name=f"{label} Hue {name}",
                    location=(x0 + 720, y0 + y),
                    use_clamp=True,
                )
            )

    rgb = []
    for component, name, y in zip(components, ("R", "G", "B"), (160, 0, -160)):
        minus_one = shader_nodes.math(
            nodes,
            links,
            "SUBTRACT",
            component,
            1.0,
            name=f"{label} {name} - 1",
            location=(x0 + 1260, y0 + y),
        )
        plus_one = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY_ADD",
            minus_one,
            saturation,
            1.0,
            name=f"{label} {name} + 1",
            location=(x0 + 1440, y0 + y),
        )
        rgb.append(
            shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                plus_one,
                value,
                name=f"{label} {name} x Value",
                location=(x0 + 1800, y0 + y),
            )
        )
    return combine_color_socket(nodes, links, label, (x0 + 1980, y0), *rgb, mode="RGB")


def _build_blackbody_nodes(nodes, links, temperature, location=(380, -120)):
    x0, y0 = location

    def poly2(name, c0, c1, c2, y):
        """c0 + c1 t + c2 t² in Horner form"""
        inner = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY_ADD",
            temperature,
            c2,
            c1,
            name=f"{name} c2 t + c1",
            location=(x0, y),
        )
        return shader_nodes.math(
            nodes,
            links,
            "MULTIPLY_ADD",
            inner,
            temperature,
            c0,
            name=name,
            location=(x0 + 170, y),
        )

    u_num = poly2(
        "BlackBody u numerator", 0.860117757, 1.54118254e-4, 1.28641212e-7, y0 + 520
    )
    u_den = poly2(
        "BlackBody u denominator", 1.0, 8.42420235e-4, 7.08145163e-7, y0 + 340
    )
    u = shader_nodes.math(
        nodes,
        links,
        "DIVIDE",
        u_num,
        u_den,
        name="BlackBody u",
        location=(x0 + 520, y0 + 430),
    )

    v_num = poly2(
        "BlackBody v numerator", 0.317398726, 4.22806245e-5, 4.20481691e-8, y0 + 160
    )
    v_den = poly2(
        "BlackBody v denominator", 1.0, -2.89741816e-5, 1.61456053e-7, y0 - 20
    )
    v = shader_nodes.math(
        nodes,
        links,
        "DIVIDE",
        v_num,
        v_den,
        name="BlackBody v",
        location=(x0 + 520, y0 + 70),
    )

    denom = shader_nodes.math(
        nodes,
        links,
        "MULTIPLY_ADD",
        u,
        2.0,
        4.0,
        name="2u + 4",
        location=(x0 + 700, y0 + 340),
    )
    denom = shader_nodes.math(
        nodes,
        links,
        "MULTIPLY_ADD",
        v,
        -8.0,
        denom,
        name="2u - 8v + 4",
        location=(x0 + 870, y0 + 340),
    )

    three_u = shader_nodes.math(
        nodes, links, "MULTIPLY", u, 3.0, name="3u", location=(x0 + 870, y0 + 180)
    )
    two_v = shader_nodes.math(
        nodes, links, "MULTIPLY", v, 2.0, name="2v", location=(x0 + 870, y0 + 60)
    )
    chroma_x = shader_nodes.math(
        nodes,
        links,
        "DIVIDE",
        three_u,
        denom,
        name="BlackBody x",
        location=(x0 + 1210, y0 + 180),
    )
    chroma_y = shader_nodes.math(
        nodes,
        links,
        "DIVIDE",
        two_v,
        denom,
        name="BlackBody y",
        location=(x0 + 1210, y0 + 60),
    )
    xy = shader_nodes.math(
        nodes,
        links,
        "ADD",
        chroma_x,
        chroma_y,
        name="BlackBody x+y",
        location=(x0 + 1380, y0 + 120),
    )
    chroma_z = shader_nodes.math(
        nodes,
        links,
        "SUBTRACT",
        1.0,
        xy,
        name="BlackBody z",
        location=(x0 + 1550, y0 + 120),
    )

    X = shader_nodes.math(
        nodes,
        links,
        "DIVIDE",
        chroma_x,
        chroma_y,
        name="BlackBody X",
        location=(x0 + 1720, y0 + 220),
    )
    Z = shader_nodes.math(
        nodes,
        links,
        "DIVIDE",
        chroma_z,
        chroma_y,
        name="BlackBody Z",
        location=(x0 + 1720, y0 + 20),
    )

    def matrix_row(name, x_weight, y_weight, z_weight, y):
        xy_sum = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY_ADD",
            X,
            x_weight,
            y_weight,
            name=f"{name} X+Y",
            location=(x0 + 1900, y),
        )
        return shader_nodes.math(
            nodes,
            links,
            "MULTIPLY_ADD",
            Z,
            z_weight,
            xy_sum,
            name=name,
            location=(x0 + 2070, y),
        )

    red = matrix_row("BlackBody R", 3.2404542, -1.5371385, -0.4985314, y0 + 280)
    green = matrix_row("BlackBody G", -0.9692660, 1.8760108, 0.0415560, y0 + 80)
    blue = matrix_row("BlackBody B", 0.0556434, -0.2040259, 1.0572252, y0 - 120)

    scaled_t = shader_nodes.math(
        nodes,
        links,
        "MULTIPLY",
        temperature,
        0.0004,
        name="0.0004 x Temperature",
        location=(x0 + 1900, y0 - 320),
    )
    intensity = shader_nodes.math(
        nodes,
        links,
        "POWER",
        scaled_t,
        4.0,
        name="BlackBody Temperature Intensity",
        location=(x0 + 2070, y0 - 320),
    )
    red = shader_nodes.math(
        nodes,
        links,
        "MULTIPLY",
        red,
        intensity,
        name="BlackBody R x Intensity",
        location=(x0 + 2410, y0 + 280),
    )
    green = shader_nodes.math(
        nodes,
        links,
        "MULTIPLY",
        green,
        intensity,
        name="BlackBody G x Intensity",
        location=(x0 + 2410, y0 + 80),
    )
    blue = shader_nodes.math(
        nodes,
        links,
        "MULTIPLY",
        blue,
        intensity,
        name="BlackBody B x Intensity",
        location=(x0 + 2410, y0 - 120),
    )
    return combine_color_socket(
        nodes,
        links,
        "Blackbody Color",
        (x0 + 2600, y0 + 80),
        red,
        green,
        blue,
        mode="RGB",
    )


def _rgb_to_hsv_group():
    def build(group):
        group_input = group.nodes.new("NodeGroupInput")
        group_output = group.nodes.new("NodeGroupOutput")
        hue, saturation, value = _build_rgb_to_hsv_nodes(
            group.nodes,
            group.links,
            group_input.outputs["Color"],
            (-1100, 0),
            "RGB to HSV",
        )
        group.links.new(hue, group_output.inputs["Hue"])
        group.links.new(saturation, group_output.inputs["Saturation"])
        group.links.new(value, group_output.inputs["Value"])

    return get_or_build_node_group(
        "CP77 RGB to HSV Bundle v1",
        (("NodeSocketColor", "Color"),),
        (
            ("NodeSocketFloat", "Hue"),
            ("NodeSocketFloat", "Saturation"),
            ("NodeSocketFloat", "Value"),
        ),
        build,
    )


def rgb_to_hsv_bundle(tree, color, location, label="RGB to HSV"):
    node = material_bundle_node(
        tree,
        _rgb_to_hsv_group(),
        location,
        label,
        {"Color": color},
    )
    return node.outputs["Hue"], node.outputs["Saturation"], node.outputs["Value"]


def _hsv_to_rgb_group():
    def build(group):
        group_input = group.nodes.new("NodeGroupInput")
        group_output = group.nodes.new("NodeGroupOutput")
        color = _build_hsv_to_rgb_nodes(
            group.nodes,
            group.links,
            group_input.outputs["Hue"],
            group_input.outputs["Saturation"],
            group_input.outputs["Value"],
            (-900, 0),
            "HSV to RGB",
        )
        group.links.new(color, group_output.inputs["Color"])

    return get_or_build_node_group(
        "CP77 HSV to RGB Bundle v2",
        (
            ("NodeSocketFloat", "Hue"),
            ("NodeSocketFloat", "Saturation"),
            ("NodeSocketFloat", "Value"),
        ),
        (("NodeSocketColor", "Color"),),
        build,
    )


def hsv_to_rgb_bundle(
    tree,
    hue,
    saturation,
    value,
    location,
    label="HSV to RGB",
):
    node = material_bundle_node(
        tree,
        _hsv_to_rgb_group(),
        location,
        label,
        {"Hue": hue, "Saturation": saturation, "Value": value},
    )
    return node.outputs["Color"]


def _blackbody_group():
    def build(group):
        group_input = group.nodes.new("NodeGroupInput")
        group_output = group.nodes.new("NodeGroupOutput")
        color = _build_blackbody_nodes(
            group.nodes,
            group.links,
            group_input.outputs["Temperature"],
            (-1300, 0),
        )
        group.links.new(color, group_output.inputs["Color"])

    return get_or_build_node_group(
        "CP77 Blackbody Bundle v2",
        (("NodeSocketFloat", "Temperature"),),
        (("NodeSocketColor", "Color"),),
        build,
    )


def blackbody_bundle(tree, temperature, location, label="Blackbody"):
    node = material_bundle_node(
        tree,
        _blackbody_group(),
        location,
        label,
        {"Temperature": temperature},
    )
    return node.outputs["Color"]
