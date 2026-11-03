from ..blender import shader_nodes
from ..blender.shader_nodes import assign_socket
from .graph import grid_location, set_transparent
from .mat_common import new_labeled_node, param_float


def control(tree, data, name, default):
    node = new_labeled_node(
        tree.nodes, "ShaderNodeValue", name, (-1600, -140 * len(tree.nodes))
    )
    node.outputs["Value"].default_value = param_float(data, name, default)
    return node.outputs["Value"]


def split_vector(tree, name, value):
    node = new_labeled_node(tree.nodes, "ShaderNodeSeparateXYZ", name, (-800, 200))
    assign_socket(tree.links, value, node.inputs["Vector"])
    return node.outputs


def combine_vector(tree, name, x, y, z=0.0):
    node = new_labeled_node(tree.nodes, "ShaderNodeCombineXYZ", name, (-400, 200))
    for key, value in zip("XYZ", (x, y, z)):
        assign_socket(tree.links, value, node.inputs[key])
    return node.outputs["Vector"]


def additive_surface(material, color, coverage, additive):
    """Compose emitted color and independent background transmission with a shadow bypass"""
    tree = material.node_tree
    opacity = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        coverage,
        additive,
        name="Blend Opacity",
        location=grid_location(tree, (200, 160)),
        use_clamp=True,
    )
    transmission = shader_nodes.math(
        tree.nodes,
        tree.links,
        "SUBTRACT",
        1.0,
        opacity,
        name="Background Transmission",
        location=grid_location(tree, (200, 160)),
    )
    transmission_surface(material, color, transmission, coverage=coverage)


def transmission_surface(material, color, transmission, *, coverage=1.0):
    """Combine a local light contribution with spatially unshifted background transmission"""
    tree = material.node_tree
    transparent = new_labeled_node(
        tree.nodes, "ShaderNodeBsdfTransparent", "Overlay Background", (1600, 200)
    )
    assign_socket(tree.links, transmission, transparent.inputs["Color"])
    emission = new_labeled_node(
        tree.nodes, "ShaderNodeEmission", "Overlay Emission", (1600, 500)
    )
    assign_socket(tree.links, color, emission.inputs["Color"])
    assign_socket(tree.links, coverage, emission.inputs["Strength"])
    combined = new_labeled_node(
        tree.nodes, "ShaderNodeAddShader", "Overlay Surface", (1800, 400)
    )
    tree.links.new(transparent.outputs["BSDF"], combined.inputs["Shader"])
    tree.links.new(
        emission.outputs["Emission"],
        shader_nodes.socket_by_identifier(combined.inputs, "Shader_001"),
    )
    shadow = new_labeled_node(
        tree.nodes, "ShaderNodeBsdfTransparent", "Shadow Transparency", (1800, 100)
    )
    path = new_labeled_node(
        tree.nodes, "ShaderNodeLightPath", "Overlay Ray Type", (1800, -100)
    )
    bypass = new_labeled_node(
        tree.nodes, "ShaderNodeMixShader", "Overlay Shadow Bypass", (2000, 400)
    )
    tree.links.new(path.outputs["Is Shadow Ray"], bypass.inputs["Factor"])
    tree.links.new(combined.outputs["Shader"], bypass.inputs["Shader"])
    tree.links.new(
        shadow.outputs["BSDF"],
        shader_nodes.socket_by_identifier(bypass.inputs, "Shader_001"),
    )
    output = new_labeled_node(
        tree.nodes, "ShaderNodeOutputMaterial", "Material Output", (2200, 400)
    )
    tree.links.new(bypass.outputs["Shader"], output.inputs["Surface"])
    set_transparent(material)
    material.use_transparency_overlap = True


def material_cache_identity(raw_material):
    if not isinstance(raw_material, dict):
        return raw_material
    identity = dict(raw_material)
    identity["cp77_overlay_surface_version"] = 1
    return identity
