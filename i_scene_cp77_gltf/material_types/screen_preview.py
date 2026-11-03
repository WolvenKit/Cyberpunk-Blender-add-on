from ..blender import shader_nodes
from ..materials.blender.nodes import create_node


def premultiplied_surface(tree, color, alpha, location):
    """Compose emitted radiance and background transmission without dividing by alpha"""
    x, y = location
    emission = create_node(
        tree.nodes, "ShaderNodeEmission", (x, y + 140), label="Premultiplied Color"
    )
    emission.inputs["Strength"].default_value = 1.0
    transmission = shader_nodes.math(
        tree.nodes,
        tree.links,
        "SUBTRACT",
        label="Background Transmission",
        location=(x - 200, y - 140),
        hide=True,
    ).node
    transmission.inputs["Value"].default_value = 1.0
    transmission.use_clamp = True
    transparent = create_node(tree.nodes, "ShaderNodeBsdfTransparent", (x, y - 80))
    surface = create_node(
        tree.nodes,
        "ShaderNodeAddShader",
        (x + 200, y),
        label="Premultiplied Over Preview",
    )
    tree.links.new(color, emission.inputs["Color"])
    tree.links.new(
        alpha, shader_nodes.socket_by_identifier(transmission.inputs, "Value_001")
    )
    tree.links.new(transmission.outputs["Value"], transparent.inputs["Color"])
    tree.links.new(emission.outputs["Emission"], surface.inputs["Shader"])
    tree.links.new(
        transparent.outputs["BSDF"],
        shader_nodes.socket_by_identifier(surface.inputs, "Shader_001"),
    )
    return surface.outputs["Shader"]
