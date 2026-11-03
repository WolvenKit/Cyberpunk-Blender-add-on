from __future__ import annotations

import bpy

from ..core.log import get_logger, log_once
from .shader_nodes import link, math, new_node, socket, socket_by_identifier
from .transactions import track_created_datablock

_LOG = get_logger(__name__)

_FOG_MATERIAL_CACHE = {}


def _set_input(node, value, *names):
    target = socket(node.inputs, *names)
    if target is not None:
        target.default_value = value
    return target


def _boundary_mask(tree, generated, blend_falloff):
    separate = new_node(
        tree,
        "ShaderNodeSeparateXYZ",
        "Fog Local Coordinates",
        (-1040, 320),
    )
    link(tree, generated, socket(separate.inputs, "Vector"))

    nodes, links = tree.nodes, tree.links
    edge_outputs = []
    for index, axis in enumerate(("X", "Y", "Z")):
        coordinate = socket(separate.outputs, axis)
        invert = math(
            nodes,
            links,
            "SUBTRACT",
            1.0,
            coordinate,
            name=f"Fog {axis} Opposite Edge",
            location=(-840, 460 - index * 140),
        )
        edge_outputs.append(
            math(
                nodes,
                links,
                "MINIMUM",
                coordinate,
                invert,
                name=f"Fog {axis} Edge Distance",
                location=(-650, 460 - index * 140),
            )
        )

    minimum_xy = math(
        nodes,
        links,
        "MINIMUM",
        edge_outputs[0],
        edge_outputs[1],
        name="Fog XY Edge Distance",
        location=(-450, 390),
    )
    minimum_xyz = math(
        nodes,
        links,
        "MINIMUM",
        minimum_xy,
        edge_outputs[2],
        name="Fog Box Edge Distance",
        location=(-270, 330),
    )
    normalized = math(
        nodes,
        links,
        "MULTIPLY",
        minimum_xyz,
        2.0,
        name="Fog Normalized Edge Distance",
        location=(-80, 330),
    )
    width = max(float(blend_falloff), 1e-4)
    divide = math(
        nodes,
        links,
        "DIVIDE",
        normalized,
        width,
        name="Fog Blend Falloff",
        location=(100, 330),
    )

    clamp = new_node(
        tree,
        "ShaderNodeClamp",
        "Fog Boundary Mask",
        (290, 330),
    )
    clamp.inputs["Min"].default_value = 0.0
    clamp.inputs["Max"].default_value = 1.0
    link(tree, divide, clamp.inputs["Value"])
    return socket(clamp.outputs, "Result"), separate


def _height_mask(tree, separate, density_falloff, enabled):
    value = new_node(
        tree,
        "ShaderNodeValue",
        "Fog Height Falloff",
        (100, 90),
    )
    value.outputs["Value"].default_value = 1.0
    if not enabled or density_falloff <= 0.0:
        return value.outputs["Value"]

    nodes, links = tree.nodes, tree.links
    scaled = math(
        nodes,
        links,
        "MULTIPLY",
        socket(separate.outputs, "Z"),
        density_falloff,
        name="Fog Height Density Loss",
        location=(-270, 100),
    )
    return math(
        nodes,
        links,
        "SUBTRACT",
        1.0,
        scaled,
        name="Fog Height Density",
        location=(-80, 100),
        use_clamp=True,
    )


def _noise_field(tree, generated, signature):
    mapping = new_node(
        tree,
        "ShaderNodeMapping",
        "Fog Texture Mapping",
        (-1040, -180),
    )
    mapping.vector_type = "POINT"
    _set_input(mapping, (2.15, 2.15, 2.15), "Scale")
    link(tree, generated, socket(mapping.inputs, "Vector"))

    large = new_node(
        tree,
        "ShaderNodeTexNoise",
        "Fog Broad Noise",
        (-800, -160),
    )
    large.noise_dimensions = "4D"
    _set_input(large, 2.2, "Scale")
    _set_input(large, 4.0, "Detail")
    _set_input(large, 0.58, "Roughness")
    _set_input(large, 0.18, "Distortion")
    link(tree, socket(mapping.outputs, "Vector"), socket(large.inputs, "Vector"))

    fine = new_node(
        tree,
        "ShaderNodeTexNoise",
        "Fog Detail Noise",
        (-800, -430),
    )
    fine.noise_dimensions = "4D"
    _set_input(fine, 7.5, "Scale")
    _set_input(fine, 2.0, "Detail")
    _set_input(fine, 0.62, "Roughness")
    link(tree, socket(mapping.outputs, "Vector"), socket(fine.inputs, "Vector"))

    seed = int(signature[:8], 16) % 997
    for node, speed, offset in (
        (large, 0.035, seed * 0.013),
        (fine, -0.052, seed * 0.021),
    ):
        w_socket = socket(node.inputs, "W")
        if w_socket is None:
            continue
        w_socket.default_value = offset
        try:
            driver = w_socket.driver_add("default_value").driver
            fps = max(
                float(bpy.context.scene.render.fps)
                / max(float(bpy.context.scene.render.fps_base), 1e-8),
                1e-8,
            )
            driver.expression = f"{offset:.9g} + frame / {fps:.9g} * {speed:.9g}"
        except (AttributeError, RuntimeError, TypeError, ValueError) as error:
            log_once(
                _LOG,
                "DEBUG",
                ("_noise_field", type(error).__name__),
                "noise field: fell back after %s",
                error,
                exc_info=True,
            )

    nodes, links = tree.nodes, tree.links
    broad_weight = math(
        nodes,
        links,
        "MULTIPLY",
        socket(large.outputs, "Fac"),
        0.72,
        name="Fog Broad Noise Weight",
        location=(-540, -170),
    )
    detail_weight = math(
        nodes,
        links,
        "MULTIPLY",
        socket(fine.outputs, "Fac"),
        0.28,
        name="Fog Detail Noise Weight",
        location=(-540, -400),
    )
    combined = math(
        nodes,
        links,
        "ADD",
        broad_weight,
        detail_weight,
        name="Fog Combined Noise",
        location=(-330, -260),
    )
    return math(
        nodes,
        links,
        "MULTIPLY_ADD",
        combined,
        0.8,
        0.38,
        name="Fog Density Texture",
        location=(-120, -260),
    )


def build_fog_volume_material(parameters, signature):
    """Volume material for decoded fog parameters, shared per parameter signature"""
    cached_name = _FOG_MATERIAL_CACHE.get(signature)
    if cached_name:
        cached = bpy.data.materials.get(cached_name)
        if cached is not None:
            return cached

    name = f"CP77_FogVolume_{signature}"
    material = bpy.data.materials.get(name)
    if material is None:
        material = track_created_datablock("materials", bpy.data.materials.new(name))
    material.use_nodes = True
    material.diffuse_color = parameters["color"]

    tree = material.node_tree
    tree.nodes.clear()

    output = new_node(
        tree,
        "ShaderNodeOutputMaterial",
        "Fog Volume Output",
        (950, 100),
    )
    coordinates = new_node(
        tree,
        "ShaderNodeTexCoord",
        "Fog Volume Coordinates",
        (-1280, 120),
    )
    generated = socket(coordinates.outputs, "Generated")

    boundary, separate = _boundary_mask(
        tree,
        generated,
        parameters["blendFalloff"],
    )
    height = _height_mask(
        tree,
        separate,
        parameters["densityFalloff"],
        parameters["applyHeightFalloff"],
    )
    noise = _noise_field(tree, generated, signature)

    nodes, links = tree.nodes, tree.links
    boundary_height = math(
        nodes,
        links,
        "MULTIPLY",
        boundary,
        height,
        name="Fog Spatial Falloff",
        location=(500, 210),
    )
    textured = math(
        nodes,
        links,
        "MULTIPLY",
        boundary_height,
        noise,
        name="Fog Textured Density",
        location=(500, -30),
    )
    density = math(
        nodes,
        links,
        "MULTIPLY",
        textured,
        parameters["previewDensity"],
        name="Fog Density",
        location=(700, 10),
    )

    color = tuple(
        max(0.0, min(1.0, component * parameters["ambientScale"]))
        for component in parameters["color"][:3]
    ) + (1.0,)

    scatter = new_node(
        tree,
        "ShaderNodeVolumeScatter",
        "REDengine Fog Scattering",
        (710, 230),
    )
    _set_input(scatter, color, "Color")
    _set_input(scatter, 0.0, "Anisotropy")
    link(tree, density, socket(scatter.inputs, "Density"))

    absorption_density = math(
        nodes,
        links,
        "MULTIPLY",
        density,
        parameters["absorptionMultiplier"],
        name="Fog Absorption Density",
        location=(710, -190),
    )

    absorption = new_node(
        tree,
        "ShaderNodeVolumeAbsorption",
        "REDengine Fog Absorption",
        (710, -330),
    )
    _set_input(absorption, color, "Color")
    link(tree, absorption_density, socket(absorption.inputs, "Density"))

    add = new_node(
        tree,
        "ShaderNodeAddShader",
        "Fog Scattering and Absorption",
        (920, 80),
    )
    link(
        tree,
        socket(scatter.outputs, "Volume"),
        socket_by_identifier(add.inputs, "Shader"),
    )
    link(
        tree,
        socket(absorption.outputs, "Volume"),
        socket_by_identifier(add.inputs, "Shader_001"),
    )
    link(tree, add.outputs["Shader"], socket(output.inputs, "Volume"))

    for key, value in parameters.items():
        property_name = f"cp77_fog_{key}"
        if isinstance(value, tuple):
            material[property_name] = list(value)
        elif isinstance(value, (str, int, float, bool)):
            material[property_name] = value

    _FOG_MATERIAL_CACHE[signature] = material.name
    return material
