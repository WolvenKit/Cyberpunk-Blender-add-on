from ..blender import shader_nodes
from ..materials.blender.nodes import create_node
from .bundles import material_bundle_node
from .graph import fract_socket
from .mat_common import get_or_build_node_group

# The offset and scale of the shader hash the game's materials use.
HASH_OFFSET = 33.33
HASH_SCALE = 0.1031


def _build_hash13_nodes(tree, vector, location, label):
    x0, y0 = location
    scale = shader_nodes.vector_math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        label=f"{label} * .1031",
        location=(x0, y0),
        hide=True,
    ).node
    shader_nodes.socket_by_identifier(scale.inputs, "Vector_001").default_value = (
        HASH_SCALE,
        HASH_SCALE,
        HASH_SCALE,
    )
    tree.links.new(vector, scale.inputs["Vector"])
    frac = shader_nodes.vector_math(
        tree.nodes,
        tree.links,
        "FRACTION",
        label=f"{label} frac",
        location=(x0 + 170, y0),
        hide=True,
    ).node
    tree.links.new(scale.outputs["Vector"], frac.inputs["Vector"])
    split = create_node(
        tree.nodes, "ShaderNodeSeparateXYZ", (x0 + 340, y0), label=f"{label} p3"
    )
    tree.links.new(frac.outputs["Vector"], split.inputs["Vector"])

    permute = create_node(
        tree.nodes,
        "ShaderNodeCombineXYZ",
        (x0 + 510, y0 - 120),
        label=f"{label} p3.yzx",
    )
    tree.links.new(split.outputs["Y"], permute.inputs["X"])
    tree.links.new(split.outputs["Z"], permute.inputs["Y"])
    tree.links.new(split.outputs["X"], permute.inputs["Z"])
    plus = shader_nodes.vector_math(
        tree.nodes,
        tree.links,
        "ADD",
        label=f"{label} + 33.33",
        location=(x0 + 680, y0 - 120),
        hide=True,
    ).node
    shader_nodes.socket_by_identifier(plus.inputs, "Vector_001").default_value = (
        HASH_OFFSET,
        HASH_OFFSET,
        HASH_OFFSET,
    )
    tree.links.new(permute.outputs["Vector"], plus.inputs["Vector"])
    dot = shader_nodes.vector_math(
        tree.nodes,
        tree.links,
        "DOT_PRODUCT",
        label=f"{label} dot",
        location=(x0 + 850, y0 - 40),
        hide=True,
    ).node
    tree.links.new(frac.outputs["Vector"], dot.inputs["Vector"])
    tree.links.new(
        plus.outputs["Vector"],
        shader_nodes.socket_by_identifier(dot.inputs, "Vector_001"),
    )

    dot_vec = create_node(
        tree.nodes,
        "ShaderNodeCombineXYZ",
        (x0 + 1020, y0 - 80),
        label=f"{label} dot.xxx",
    )
    for name in ("X", "Y", "Z"):
        tree.links.new(dot.outputs["Value"], dot_vec.inputs[name])
    scrambled = shader_nodes.vector_math(
        tree.nodes,
        tree.links,
        "ADD",
        label=f"{label} scrambled",
        location=(x0 + 1190, y0),
        hide=True,
    ).node
    tree.links.new(frac.outputs["Vector"], scrambled.inputs["Vector"])
    tree.links.new(
        dot_vec.outputs["Vector"],
        shader_nodes.socket_by_identifier(scrambled.inputs, "Vector_001"),
    )
    scrambled_split = create_node(
        tree.nodes,
        "ShaderNodeSeparateXYZ",
        (x0 + 1360, y0),
        label=f"{label} scrambled XYZ",
    )
    tree.links.new(scrambled.outputs["Vector"], scrambled_split.inputs["Vector"])
    xy = shader_nodes.math(
        tree.nodes,
        tree.links,
        "ADD",
        label=f"{label} x+y",
        location=(x0 + 1530, y0 + 40),
        hide=True,
    ).node
    tree.links.new(scrambled_split.outputs["X"], xy.inputs["Value"])
    tree.links.new(
        scrambled_split.outputs["Y"],
        shader_nodes.socket_by_identifier(xy.inputs, "Value_001"),
    )
    product = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        label=f"{label} product",
        location=(x0 + 1700, y0 + 40),
        hide=True,
    ).node
    tree.links.new(xy.outputs["Value"], product.inputs["Value"])
    tree.links.new(
        scrambled_split.outputs["Z"],
        shader_nodes.socket_by_identifier(product.inputs, "Value_001"),
    )
    return fract_socket(tree, product.outputs["Value"], (x0 + 1870, y0 + 40), label)


def _build_hash43_nodes(tree, vector, location, label):
    x0, y0 = location
    split = create_node(
        tree.nodes, "ShaderNodeSeparateXYZ", (x0, y0), label=f"{label} input"
    )
    tree.links.new(vector, split.inputs["Vector"])
    sources = (
        split.outputs["X"],
        split.outputs["Y"],
        split.outputs["Z"],
        split.outputs["X"],
    )
    factors = (0.1031, 0.1030, 0.0973, 0.1099)
    names = ("x", "y", "z", "w")
    p = []
    for index, (source, factor, name) in enumerate(zip(sources, factors, names)):
        y = y0 + 180 - index * 120
        scaled = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            None,
            factor,
            label=f"{label} {name} scale",
            location=(x0 + 180, y),
            hide=True,
        ).node
        tree.links.new(source, scaled.inputs["Value"])
        p.append(
            fract_socket(
                tree, scaled.outputs["Value"], (x0 + 350, y), f"{label} {name} frac"
            )
        )

    permuted = (p[3], p[2], p[0], p[1])
    terms = []
    for index, (source, other, name) in enumerate(zip(p, permuted, names)):
        y = y0 + 180 - index * 120
        plus = shader_nodes.math(
            tree.nodes,
            tree.links,
            "ADD",
            None,
            HASH_OFFSET,
            label=f"{label} {name} + 33.33",
            location=(x0 + 520, y),
            hide=True,
        ).node
        tree.links.new(other, plus.inputs["Value"])
        term = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            label=f"{label} dot {name}",
            location=(x0 + 690, y),
            hide=True,
        ).node
        tree.links.new(source, term.inputs["Value"])
        tree.links.new(
            plus.outputs["Value"],
            shader_nodes.socket_by_identifier(term.inputs, "Value_001"),
        )
        terms.append(term.outputs["Value"])
    sum_a = shader_nodes.math(
        tree.nodes,
        tree.links,
        "ADD",
        label=f"{label} dot xy",
        location=(x0 + 860, y0 + 80),
        hide=True,
    ).node
    tree.links.new(terms[0], sum_a.inputs["Value"])
    tree.links.new(
        terms[1], shader_nodes.socket_by_identifier(sum_a.inputs, "Value_001")
    )
    sum_b = shader_nodes.math(
        tree.nodes,
        tree.links,
        "ADD",
        label=f"{label} dot zw",
        location=(x0 + 860, y0 - 160),
        hide=True,
    ).node
    tree.links.new(terms[2], sum_b.inputs["Value"])
    tree.links.new(
        terms[3], shader_nodes.socket_by_identifier(sum_b.inputs, "Value_001")
    )
    dot = shader_nodes.math(
        tree.nodes,
        tree.links,
        "ADD",
        label=f"{label} dot",
        location=(x0 + 1030, y0 - 40),
        hide=True,
    ).node
    tree.links.new(sum_a.outputs["Value"], dot.inputs["Value"])
    tree.links.new(
        sum_b.outputs["Value"],
        shader_nodes.socket_by_identifier(dot.inputs, "Value_001"),
    )

    q = []
    for index, (source, name) in enumerate(zip(p, names)):
        y = y0 + 180 - index * 120
        add = shader_nodes.math(
            tree.nodes,
            tree.links,
            "ADD",
            label=f"{label} {name} scrambled",
            location=(x0 + 1200, y),
            hide=True,
        ).node
        tree.links.new(source, add.inputs["Value"])
        tree.links.new(
            dot.outputs["Value"],
            shader_nodes.socket_by_identifier(add.inputs, "Value_001"),
        )
        q.append(add.outputs["Value"])

    output_terms = (
        (q[0], q[1], q[2]),
        (q[0], q[2], q[1]),
        (q[1], q[2], q[3]),
        (q[2], q[3], q[0]),
    )
    out = []
    for index, (first, second, multiplier) in enumerate(output_terms):
        y = y0 + 180 - index * 120
        summed = shader_nodes.math(
            tree.nodes,
            tree.links,
            "ADD",
            label=f"{label} {names[index]} sum",
            location=(x0 + 1370, y),
            hide=True,
        ).node
        tree.links.new(first, summed.inputs["Value"])
        tree.links.new(
            second, shader_nodes.socket_by_identifier(summed.inputs, "Value_001")
        )
        product = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            label=f"{label} {names[index]} product",
            location=(x0 + 1540, y),
            hide=True,
        ).node
        tree.links.new(summed.outputs["Value"], product.inputs["Value"])
        tree.links.new(
            multiplier, shader_nodes.socket_by_identifier(product.inputs, "Value_001")
        )
        out.append(
            fract_socket(
                tree,
                product.outputs["Value"],
                (x0 + 1710, y),
                f"{label}.{names[index]}",
            )
        )

    rgb = create_node(
        tree.nodes, "ShaderNodeCombineXYZ", (x0 + 1880, y0 + 60), label=f"{label}.xyz"
    )
    tree.links.new(out[0], rgb.inputs["X"])
    tree.links.new(out[1], rgb.inputs["Y"])
    tree.links.new(out[2], rgb.inputs["Z"])
    return rgb.outputs["Vector"], out[3]


def _hash13_group():
    def build(group):
        group_input = group.nodes.new("NodeGroupInput")
        group_output = group.nodes.new("NodeGroupOutput")
        result = _build_hash13_nodes(
            group,
            group_input.outputs["Vector"],
            (-900, 0),
            "Hash",
        )
        group.links.new(result, group_output.inputs["Value"])

    return get_or_build_node_group(
        "CP77 Hash 1 from 3 Bundle v1",
        (("NodeSocketVector", "Vector"),),
        (("NodeSocketFloat", "Value"),),
        build,
    )


def hash13_socket(tree, vector, location, label="Hash 1 from 3"):
    node = material_bundle_node(
        tree,
        _hash13_group(),
        location,
        label,
        {"Vector": vector},
    )
    return node.outputs["Value"]


def _hash43_group():
    def build(group):
        group_input = group.nodes.new("NodeGroupInput")
        group_output = group.nodes.new("NodeGroupOutput")
        vector, w = _build_hash43_nodes(
            group,
            group_input.outputs["Vector"],
            (-900, 0),
            "Hash",
        )
        group.links.new(vector, group_output.inputs["Vector"])
        group.links.new(w, group_output.inputs["W"])

    return get_or_build_node_group(
        "CP77 Hash 4 from 3 Bundle v1",
        (("NodeSocketVector", "Vector"),),
        (("NodeSocketVector", "Vector"), ("NodeSocketFloat", "W")),
        build,
    )


def hash43_sockets(tree, vector, location, label="Hash 4 from 3"):
    node = material_bundle_node(
        tree,
        _hash43_group(),
        location,
        label,
        {"Vector": vector},
    )
    return node.outputs["Vector"], node.outputs["W"]
