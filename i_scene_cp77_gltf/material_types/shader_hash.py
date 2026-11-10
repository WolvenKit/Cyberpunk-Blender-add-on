import bpy

from ..blender import shader_nodes
from ..blender.transactions import track_created_datablock
from ..materials.blender.nodes import create_node
from .bundles import material_bundle_node
from .graph import fract_socket
from .mat_common import get_or_build_node_group

# The offset and scale of the shader hash the game's materials use.
HASH_OFFSET = 33.33
HASH_SCALE = 0.1031
HASH_SCALE3 = (0.1031, 0.1030, 0.0973)
HASH_SCALE4 = (*HASH_SCALE3, 0.1099)


def _combine(tree, x, y, z, location, label):
    node = create_node(tree.nodes, "ShaderNodeCombineXYZ", location, label=label)
    tree.links.new(x, node.inputs["X"])
    tree.links.new(y, node.inputs["Y"])
    if z is not None:
        tree.links.new(z, node.inputs["Z"])
    return node.outputs["Vector"]


def _scrambled_nodes(tree, p3, scale, location, label):
    x0, y0 = location
    scaled = shader_nodes.vector_math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        label=f"{label} scale",
        location=(x0, y0),
        hide=True,
    ).node
    shader_nodes.socket_by_identifier(scaled.inputs, "Vector_001").default_value = scale
    tree.links.new(p3, scaled.inputs["Vector"])
    frac = shader_nodes.vector_math(
        tree.nodes,
        tree.links,
        "FRACTION",
        label=f"{label} frac",
        location=(x0 + 170, y0),
        hide=True,
    ).node
    tree.links.new(scaled.outputs["Vector"], frac.inputs["Vector"])
    split = create_node(
        tree.nodes, "ShaderNodeSeparateXYZ", (x0 + 340, y0), label=f"{label} p3"
    )
    tree.links.new(frac.outputs["Vector"], split.inputs["Vector"])
    permute = _combine(
        tree,
        split.outputs["Y"],
        split.outputs["Z"],
        split.outputs["X"],
        (x0 + 510, y0 - 120),
        f"{label} p3.yzx",
    )
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
    ) * 3
    tree.links.new(permute, plus.inputs["Vector"])
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
    dot_value = dot.outputs["Value"]
    dot_vec = _combine(
        tree, dot_value, dot_value, dot_value, (x0 + 1020, y0 - 80), f"{label} dot.xxx"
    )
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
        dot_vec, shader_nodes.socket_by_identifier(scrambled.inputs, "Vector_001")
    )
    scrambled_split = create_node(
        tree.nodes,
        "ShaderNodeSeparateXYZ",
        (x0 + 1360, y0),
        label=f"{label} scrambled XYZ",
    )
    tree.links.new(scrambled.outputs["Vector"], scrambled_split.inputs["Vector"])
    return scrambled_split.outputs


def _fract_product(tree, first, second, factor, location, label):
    x0, y0 = location
    total = shader_nodes.math(
        tree.nodes,
        tree.links,
        "ADD",
        label=f"{label} sum",
        location=(x0, y0),
        hide=True,
    ).node
    tree.links.new(first, total.inputs["Value"])
    tree.links.new(second, shader_nodes.socket_by_identifier(total.inputs, "Value_001"))
    product = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        label=f"{label} product",
        location=(x0 + 170, y0),
        hide=True,
    ).node
    tree.links.new(total.outputs["Value"], product.inputs["Value"])
    tree.links.new(
        factor, shader_nodes.socket_by_identifier(product.inputs, "Value_001")
    )
    return fract_socket(tree, product.outputs["Value"], (x0 + 340, y0), label)


def _build_hash11_nodes(tree, source, location, label):
    mul = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        None,
        HASH_SCALE,
        label=f"{label} * .1031",
        location=location,
        hide=True,
    ).node
    tree.links.new(source, mul.inputs["Value"])
    p = fract_socket(
        tree, mul.outputs["Value"], (location[0] + 150, location[1]), f"{label} frac"
    )
    plus = shader_nodes.math(
        tree.nodes,
        tree.links,
        "ADD",
        None,
        HASH_OFFSET,
        label=f"{label} + 33.33",
        location=(location[0] + 300, location[1]),
        hide=True,
    ).node
    tree.links.new(p, plus.inputs["Value"])
    p2 = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        label=f"{label} scramble",
        location=(location[0] + 450, location[1]),
        hide=True,
    ).node
    tree.links.new(p, p2.inputs["Value"])
    tree.links.new(
        plus.outputs["Value"], shader_nodes.socket_by_identifier(p2.inputs, "Value_001")
    )
    doubled = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        None,
        2.0,
        label=f"{label} x2",
        location=(location[0] + 600, location[1]),
        hide=True,
    ).node
    tree.links.new(p2.outputs["Value"], doubled.inputs["Value"])
    final_mul = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        label=f"{label} final",
        location=(location[0] + 750, location[1]),
        hide=True,
    ).node
    tree.links.new(p2.outputs["Value"], final_mul.inputs["Value"])
    tree.links.new(
        doubled.outputs["Value"],
        shader_nodes.socket_by_identifier(final_mul.inputs, "Value_001"),
    )
    return fract_socket(
        tree, final_mul.outputs["Value"], (location[0] + 900, location[1]), label
    )


def _build_hash13_nodes(tree, vector, location, label):
    x0, y0 = location
    scrambled = _scrambled_nodes(tree, vector, (HASH_SCALE,) * 3, location, label)
    return _fract_product(
        tree,
        scrambled["X"],
        scrambled["Y"],
        scrambled["Z"],
        (x0 + 1530, y0 + 40),
        label,
    )


def _build_hash12_nodes(tree, vector, location, label):
    x0, y0 = location
    split = create_node(
        tree.nodes, "ShaderNodeSeparateXYZ", location, label=f"{label} input"
    )
    tree.links.new(vector, split.inputs["Vector"])
    p3 = _combine(
        tree,
        split.outputs["X"],
        split.outputs["Y"],
        split.outputs["X"],
        (x0 + 170, y0),
        f"{label} p.xyx",
    )
    return _build_hash13_nodes(tree, p3, (x0 + 340, y0), label)


def _build_hash2_nodes(tree, source, mode, location, label):
    x0, y0 = location
    if mode == "21":
        p3 = _combine(tree, source, source, source, location, f"{label} p.xxx")
    elif mode == "22":
        split = create_node(
            tree.nodes, "ShaderNodeSeparateXYZ", location, label=f"{label} input"
        )
        tree.links.new(source, split.inputs["Vector"])
        p3 = _combine(
            tree,
            split.outputs["X"],
            split.outputs["Y"],
            split.outputs["X"],
            (x0 + 170, y0),
            f"{label} p.xyx",
        )
    else:
        p3 = source
    scrambled = _scrambled_nodes(tree, p3, HASH_SCALE3, (x0 + 340, y0), label)
    out_x = _fract_product(
        tree,
        scrambled["X"],
        scrambled["Y"],
        scrambled["Z"],
        (x0 + 1870, y0 + 70),
        f"{label}.x",
    )
    out_y = _fract_product(
        tree,
        scrambled["X"],
        scrambled["Z"],
        scrambled["Y"],
        (x0 + 1870, y0 - 90),
        f"{label}.y",
    )
    return _combine(tree, out_x, out_y, None, (x0 + 2380, y0), label)


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
    factors = HASH_SCALE4
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


def _hash11_group():
    def build(group):
        group_input = group.nodes.new("NodeGroupInput")
        group_output = group.nodes.new("NodeGroupOutput")
        result = _build_hash11_nodes(
            group,
            group_input.outputs["Value"],
            (-500, 0),
            "Hash",
        )
        group.links.new(result, group_output.inputs["Value"])

    return get_or_build_node_group(
        "CP77 Hash 1 from 1 Bundle v1",
        (("NodeSocketFloat", "Value"),),
        (("NodeSocketFloat", "Value"),),
        build,
    )


def hash11_socket(tree, value, location, label="Hash 1 from 1"):
    node = material_bundle_node(
        tree, _hash11_group(), location, label, {"Value": value}
    )
    return node.outputs["Value"]


def _hash12_group():
    def build(group):
        group_input = group.nodes.new("NodeGroupInput")
        group_output = group.nodes.new("NodeGroupOutput")
        result = _build_hash12_nodes(
            group,
            group_input.outputs["Vector"],
            (-1100, 0),
            "Hash",
        )
        group.links.new(result, group_output.inputs["Value"])

    return get_or_build_node_group(
        "CP77 Hash 1 from 2 Bundle v1",
        (("NodeSocketVector", "Vector"),),
        (("NodeSocketFloat", "Value"),),
        build,
    )


def hash12_socket(tree, vector, location, label="Hash 1 from 2"):
    node = material_bundle_node(
        tree, _hash12_group(), location, label, {"Vector": vector}
    )
    return node.outputs["Value"]


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


def _hash2_group(mode):
    socket_type = "NodeSocketFloat" if mode == "21" else "NodeSocketVector"

    def build(group):
        group_input = group.nodes.new("NodeGroupInput")
        group_output = group.nodes.new("NodeGroupOutput")
        result = _build_hash2_nodes(
            group,
            group_input.outputs["Value"],
            mode,
            (-1200, 0),
            "Hash",
        )
        group.links.new(result, group_output.inputs["Vector"])

    return get_or_build_node_group(
        f"CP77 Hash 2 from {mode[1]} Bundle v1",
        ((socket_type, "Value"),),
        (("NodeSocketVector", "Vector"),),
        build,
    )


def hash2_socket(tree, source, mode, location, label="Hash 2"):
    node = material_bundle_node(
        tree, _hash2_group(mode), location, label, {"Value": source}
    )
    return node.outputs["Vector"]


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


def screen_hash12_group():
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
