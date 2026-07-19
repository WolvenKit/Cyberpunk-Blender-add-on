from __future__ import annotations

import hashlib
import json
import math

import bpy
from mathutils import Matrix, Vector


FOG_COMPONENT_TYPES = frozenset({"entFogVolumeComponent"})
_FOG_MATERIAL_CACHE = {}


def _float_value(data, key, default=0.0):
    value = data.get(key, default) if isinstance(data, dict) else default
    if isinstance(value, dict):
        for nested_key in ("$value", "Value", "value"):
            if nested_key in value:
                value = value[nested_key]
                break
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _bool_value(data, key, default=False):
    value = data.get(key, default) if isinstance(data, dict) else default
    if isinstance(value, dict):
        value = value.get("$value", default)
    return bool(value)


def _axis_value(data, axis, default=0.0):
    if not isinstance(data, dict):
        return float(default)
    value = data.get(axis, data.get(axis.lower(), default))
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def fog_volume_size(data):
    size = data.get("size") if isinstance(data, dict) else None
    if not isinstance(size, dict):
        return Vector((1.0, 1.0, 1.0))
    return Vector((
        max(abs(_axis_value(size, "X", 1.0)), 1e-6),
        max(abs(_axis_value(size, "Y", 1.0)), 1e-6),
        max(abs(_axis_value(size, "Z", 1.0)), 1e-6),
    ))


def fog_volume_color(data):
    color = data.get("color") if isinstance(data, dict) else None
    if not isinstance(color, dict):
        return (1.0, 1.0, 0.9, 1.0)

    values = tuple(
        max(0.0, min(1.0, _float_value(color, channel, 0.0) / 255.0))
        for channel in ("Red", "Green", "Blue")
    )
    if max(values) <= 1e-8:
        values = (1.0, 1.0, 0.9)

    return (*values, 1.0)


def fog_volume_parameters(data, source_kind="sector"):
    density_falloff = _float_value(
        data,
        "densityFalloff",
        _float_value(data, "falloff", 0.0),
    )
    density_factor = max(_float_value(data, "densityFactor", 100.0), 0.0)
    absolute = _bool_value(data, "absolute", False)
    if source_kind == "sector" and absolute:
        preview_density = density_factor
        density_contract = "ABSOLUTE_DENSITY"
    else:
        preview_density = density_factor * 0.001
        density_contract = "RELATIVE_DENSITY_PERCENT_PREVIEW"

    absorption = _float_value(data, "absorption", -1.0)
    absorption_multiplier = 0.25 if absorption < 0.0 else max(absorption, 0.0)
    ambient_scale = max(_float_value(data, "ambientScale", 1.0), 0.0)
    color = fog_volume_color(data)

    return {
        "densityFactor": density_factor,
        "previewDensity": max(preview_density, 0.0),
        "densityContract": density_contract,
        "densityFalloff": max(0.0, min(1.0, density_falloff)),
        "blendFalloff": max(0.0, min(1.0, _float_value(data, "blendFalloff", 0.0))),
        "absorption": absorption,
        "absorptionMultiplier": absorption_multiplier,
        "ambientScale": ambient_scale,
        "color": color,
        "absolute": absolute,
        "applyHeightFalloff": _bool_value(data, "applyHeightFalloff", True),
        "enabled": _bool_value(data, "isEnabled", _bool_value(data, "isVisibleInGame", True)),
        "priority": int(_float_value(data, "priority", 0.0)),
        "applyGlobalHeightFalloff": _bool_value(data, "applyHeightFalloff", False),
    }


def _material_signature(parameters):
    payload = {
        key: parameters[key]
        for key in (
            "previewDensity",
            "densityFalloff",
            "blendFalloff",
            "absorptionMultiplier",
            "ambientScale",
            "color",
            "absolute",
            "applyHeightFalloff",
        )
    }
    return hashlib.blake2b(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8"),
        digest_size=8,
    ).hexdigest()


def _new_node(nodes, node_type, name, location):
    node = nodes.new(node_type)
    node.name = name
    node.label = name
    node.location = location
    return node


def _socket(collection, *names):
    for name in names:
        socket = collection.get(name)
        if socket is not None:
            return socket
    return None


def _set_input(node, value, *names):
    socket = _socket(node.inputs, *names)
    if socket is not None:
        socket.default_value = value
    return socket


def _link(links, output_socket, input_socket):
    if output_socket is not None and input_socket is not None:
        links.new(output_socket, input_socket)


def _math(nodes, operation, name, location, first=None, second=None, clamp=False):
    node = _new_node(nodes, "ShaderNodeMath", name, location)
    node.operation = operation
    node.use_clamp = clamp
    if first is not None:
        node.inputs[0].default_value = first
    if second is not None:
        node.inputs[1].default_value = second
    return node


def _boundary_mask(nodes, links, generated, blend_falloff):
    separate = _new_node(
        nodes,
        "ShaderNodeSeparateXYZ",
        "Fog Local Coordinates",
        (-1040, 320),
    )
    _link(links, generated, separate.inputs[0])

    edge_outputs = []
    for index, axis in enumerate(("X", "Y", "Z")):
        invert = _math(
            nodes,
            "SUBTRACT",
            f"Fog {axis} Opposite Edge",
            (-840, 460 - index * 140),
            first=1.0,
        )
        _link(links, separate.outputs[index], invert.inputs[1])

        minimum = _math(
            nodes,
            "MINIMUM",
            f"Fog {axis} Edge Distance",
            (-650, 460 - index * 140),
        )
        _link(links, separate.outputs[index], minimum.inputs[0])
        _link(links, invert.outputs[0], minimum.inputs[1])
        edge_outputs.append(minimum.outputs[0])

    minimum_xy = _math(
        nodes,
        "MINIMUM",
        "Fog XY Edge Distance",
        (-450, 390),
    )
    _link(links, edge_outputs[0], minimum_xy.inputs[0])
    _link(links, edge_outputs[1], minimum_xy.inputs[1])

    minimum_xyz = _math(
        nodes,
        "MINIMUM",
        "Fog Box Edge Distance",
        (-270, 330),
    )
    _link(links, minimum_xy.outputs[0], minimum_xyz.inputs[0])
    _link(links, edge_outputs[2], minimum_xyz.inputs[1])

    normalized = _math(
        nodes,
        "MULTIPLY",
        "Fog Normalized Edge Distance",
        (-80, 330),
        second=2.0,
    )
    _link(links, minimum_xyz.outputs[0], normalized.inputs[0])

    width = max(float(blend_falloff), 1e-4)
    divide = _math(
        nodes,
        "DIVIDE",
        "Fog Blend Falloff",
        (100, 330),
        second=width,
    )
    _link(links, normalized.outputs[0], divide.inputs[0])

    clamp = _new_node(
        nodes,
        "ShaderNodeClamp",
        "Fog Boundary Mask",
        (290, 330),
    )
    clamp.inputs["Min"].default_value = 0.0
    clamp.inputs["Max"].default_value = 1.0
    _link(links, divide.outputs[0], clamp.inputs["Value"])
    return clamp.outputs[0], separate


def _height_mask(nodes, links, separate, density_falloff, enabled):
    value = _new_node(
        nodes,
        "ShaderNodeValue",
        "Fog Height Falloff",
        (100, 90),
    )
    value.outputs[0].default_value = 1.0
    if not enabled or density_falloff <= 0.0:
        return value.outputs[0]

    scaled = _math(
        nodes,
        "MULTIPLY",
        "Fog Height Density Loss",
        (-270, 100),
        second=density_falloff,
    )
    _link(links, separate.outputs["Z"], scaled.inputs[0])

    subtract = _math(
        nodes,
        "SUBTRACT",
        "Fog Height Density",
        (-80, 100),
        first=1.0,
        clamp=True,
    )
    _link(links, scaled.outputs[0], subtract.inputs[1])
    return subtract.outputs[0]


def _noise_field(nodes, links, generated, signature):
    mapping = _new_node(
        nodes,
        "ShaderNodeMapping",
        "Fog Texture Mapping",
        (-1040, -180),
    )
    mapping.vector_type = "POINT"
    _set_input(mapping, (2.15, 2.15, 2.15), "Scale")
    _link(links, generated, _socket(mapping.inputs, "Vector"))

    large = _new_node(
        nodes,
        "ShaderNodeTexNoise",
        "Fog Broad Noise",
        (-800, -160),
    )
    large.noise_dimensions = "4D"
    _set_input(large, 2.2, "Scale")
    _set_input(large, 4.0, "Detail")
    _set_input(large, 0.58, "Roughness")
    _set_input(large, 0.18, "Distortion")
    _link(links, _socket(mapping.outputs, "Vector"), _socket(large.inputs, "Vector"))

    fine = _new_node(
        nodes,
        "ShaderNodeTexNoise",
        "Fog Detail Noise",
        (-800, -430),
    )
    fine.noise_dimensions = "4D"
    _set_input(fine, 7.5, "Scale")
    _set_input(fine, 2.0, "Detail")
    _set_input(fine, 0.62, "Roughness")
    _link(links, _socket(mapping.outputs, "Vector"), _socket(fine.inputs, "Vector"))

    seed = int(signature[:8], 16) % 997
    for node, speed, offset in (
        (large, 0.035, seed * 0.013),
        (fine, -0.052, seed * 0.021),
    ):
        w_socket = _socket(node.inputs, "W")
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
        except (AttributeError, RuntimeError, TypeError, ValueError):
            pass

    broad_weight = _math(
        nodes,
        "MULTIPLY",
        "Fog Broad Noise Weight",
        (-540, -170),
        second=0.72,
    )
    _link(links, _socket(large.outputs, "Fac"), broad_weight.inputs[0])

    detail_weight = _math(
        nodes,
        "MULTIPLY",
        "Fog Detail Noise Weight",
        (-540, -400),
        second=0.28,
    )
    _link(links, _socket(fine.outputs, "Fac"), detail_weight.inputs[0])

    combined = _math(
        nodes,
        "ADD",
        "Fog Combined Noise",
        (-330, -260),
    )
    _link(links, broad_weight.outputs[0], combined.inputs[0])
    _link(links, detail_weight.outputs[0], combined.inputs[1])

    remap = _math(
        nodes,
        "MULTIPLY_ADD",
        "Fog Density Texture",
        (-120, -260),
    )
    remap.inputs[1].default_value = 0.8
    remap.inputs[2].default_value = 0.38
    _link(links, combined.outputs[0], remap.inputs[0])
    return remap.outputs[0]


def build_fog_volume_material(data, source_kind="sector"):
    parameters = fog_volume_parameters(data, source_kind)
    signature = _material_signature(parameters)

    cached_name = _FOG_MATERIAL_CACHE.get(signature)
    if cached_name:
        cached = bpy.data.materials.get(cached_name)
        if cached is not None:
            return cached

    name = f"CP77_FogVolume_{signature}"
    material = bpy.data.materials.get(name)
    if material is None:
        material = bpy.data.materials.new(name)
    material.use_nodes = True
    material.diffuse_color = parameters["color"]

    tree = material.node_tree
    nodes = tree.nodes
    links = tree.links
    nodes.clear()

    output = _new_node(
        nodes,
        "ShaderNodeOutputMaterial",
        "Fog Volume Output",
        (950, 100),
    )
    coordinates = _new_node(
        nodes,
        "ShaderNodeTexCoord",
        "Fog Volume Coordinates",
        (-1280, 120),
    )
    generated = _socket(coordinates.outputs, "Generated")

    boundary, separate = _boundary_mask(
        nodes,
        links,
        generated,
        parameters["blendFalloff"],
    )
    height = _height_mask(
        nodes,
        links,
        separate,
        parameters["densityFalloff"],
        parameters["applyHeightFalloff"],
    )
    noise = _noise_field(nodes, links, generated, signature)

    boundary_height = _math(
        nodes,
        "MULTIPLY",
        "Fog Spatial Falloff",
        (500, 210),
    )
    _link(links, boundary, boundary_height.inputs[0])
    _link(links, height, boundary_height.inputs[1])

    textured = _math(
        nodes,
        "MULTIPLY",
        "Fog Textured Density",
        (500, -30),
    )
    _link(links, boundary_height.outputs[0], textured.inputs[0])
    _link(links, noise, textured.inputs[1])

    density = _math(
        nodes,
        "MULTIPLY",
        "Fog Density",
        (700, 10),
        second=parameters["previewDensity"],
    )
    _link(links, textured.outputs[0], density.inputs[0])

    color = tuple(
        max(0.0, min(1.0, component * parameters["ambientScale"]))
        for component in parameters["color"][:3]
    ) + (1.0,)

    scatter = _new_node(
        nodes,
        "ShaderNodeVolumeScatter",
        "REDengine Fog Scattering",
        (710, 230),
    )
    _set_input(scatter, color, "Color")
    _set_input(scatter, 0.0, "Anisotropy")
    _link(links, density.outputs[0], _socket(scatter.inputs, "Density"))

    absorption_density = _math(
        nodes,
        "MULTIPLY",
        "Fog Absorption Density",
        (710, -190),
        second=parameters["absorptionMultiplier"],
    )
    _link(links, density.outputs[0], absorption_density.inputs[0])

    absorption = _new_node(
        nodes,
        "ShaderNodeVolumeAbsorption",
        "REDengine Fog Absorption",
        (710, -330),
    )
    _set_input(absorption, color, "Color")
    _link(
        links,
        absorption_density.outputs[0],
        _socket(absorption.inputs, "Density"),
    )

    add = _new_node(
        nodes,
        "ShaderNodeAddShader",
        "Fog Scattering and Absorption",
        (920, 80),
    )
    _link(links, _socket(scatter.outputs, "Volume"), add.inputs[0])
    _link(links, _socket(absorption.outputs, "Volume"), add.inputs[1])
    _link(links, add.outputs[0], _socket(output.inputs, "Volume"))

    for key, value in parameters.items():
        property_name = f"cp77_fog_{key}"
        if isinstance(value, tuple):
            material[property_name] = list(value)
        elif isinstance(value, (str, int, float, bool)):
            material[property_name] = value
    material["cp77_fog_preview"] = "PROCEDURAL_3D_NOISE_WITH_AUTHORED_BOX_AND_HEIGHT_FALLOFF"
    material["cp77_fog_texture_source"] = "PROCEDURAL_PREVIEW_NO_COMPONENT_TEXTURE_RESOURCE"

    _FOG_MATERIAL_CACHE[signature] = material.name
    return material


def _unit_box_mesh(name):
    vertices = [
        (-1.0, -1.0, -1.0),
        (1.0, -1.0, -1.0),
        (1.0, 1.0, -1.0),
        (-1.0, 1.0, -1.0),
        (-1.0, -1.0, 1.0),
        (1.0, -1.0, 1.0),
        (1.0, 1.0, 1.0),
        (-1.0, 1.0, 1.0),
    ]
    faces = [
        (0, 3, 2, 1),
        (4, 5, 6, 7),
        (0, 1, 5, 4),
        (1, 2, 6, 5),
        (2, 3, 7, 6),
        (3, 0, 4, 7),
    ]
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    return mesh


def configure_fog_volume_object(obj, data, source_kind="sector"):
    parameters = fog_volume_parameters(data, source_kind)
    obj["fogVolumeRepresentation"] = "CP77_UNIT_BOX_MINUS_ONE_TO_ONE"
    obj["fogVolumeMaterialModel"] = "VOLUME_SCATTER_PLUS_ABSORPTION"
    obj["fogTextureSource"] = "PROCEDURAL_3D_NOISE_PREVIEW"
    obj["fogDensityFactor"] = parameters["densityFactor"]
    obj["fogPreviewDensity"] = parameters["previewDensity"]
    obj["fogDensityContract"] = parameters["densityContract"]
    obj["fogDensityFalloff"] = parameters["densityFalloff"]
    obj["fogBlendFalloff"] = parameters["blendFalloff"]
    obj["fogAbsorption"] = parameters["absorption"]
    obj["fogAmbientScale"] = parameters["ambientScale"]
    obj["fogAbsolute"] = parameters["absolute"]
    obj["fogApplyHeightFalloff"] = parameters["applyHeightFalloff"]
    obj["fogPriority"] = parameters["priority"]
    obj["fogColor"] = list(parameters["color"])
    obj["fogSourceKind"] = source_kind
    obj["fogVolumeData"] = json.dumps(data, separators=(",", ":"))

    obj.display_type = "TEXTURED"
    obj.show_wire = True
    obj.color = parameters["color"]
    obj.hide_viewport = not parameters["enabled"]
    obj.hide_render = not parameters["enabled"]
    return parameters


def create_fog_volume_object(
    name,
    data,
    collection,
    *,
    matrix=None,
    size=None,
    source_kind="sector",
):
    mesh = _unit_box_mesh(name)
    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)

    material = build_fog_volume_material(data, source_kind)
    mesh.materials.append(material)

    final_matrix = matrix.copy() if matrix is not None else Matrix.Identity(4)
    if size is not None:
        size = Vector(size)
        final_matrix = final_matrix @ Matrix.Diagonal(
            (float(size.x), float(size.y), float(size.z), 1.0)
        )
    obj.matrix_world = final_matrix
    configure_fog_volume_object(obj, data, source_kind)
    return obj
