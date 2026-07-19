"""Shared helpers for material_types shader builders.

Consolidates the defaulted value-node parameter tables from televisionad, the
scene-fps time driver, the decal UV transform block, and the hair
gradient-entry ramp population. Image loading stays on main.common's
imageFromRelPath, which already performs project-first DepotAssetIndex
resolution and loaded-image dedupe.
"""

import math

import bpy

from ..main.common import CreateRebildNormalGroup, CreateShaderNodeValue, create_node, imageFromRelPath


def create_param_value_nodes(tree, data, specs, x=-2000):
    """Create one labelled Value node per parameter variable.

    specs rows are (data_key, var_name, y, label, default). Every var_name is
    guaranteed a node: parameters absent from the material data fall back to
    their template default, so downstream links never dereference a missing
    node. Where several data keys alias one var_name, the last key present in
    the data wins, matching the previous last-writer behaviour without leaving
    orphaned nodes in the tree.
    """
    chosen = {}
    for spec in specs:
        if spec[0] in data:
            chosen[spec[1]] = spec
    nodes = {}
    for spec in specs:
        key, var_name, y, label, default = spec
        if var_name in nodes:
            continue
        active = chosen.get(var_name)
        if active is not None:
            key, var_name, y, label, default = active
            nodes[var_name] = CreateShaderNodeValue(tree, data[key], x, y, label)
        else:
            nodes[var_name] = CreateShaderNodeValue(tree, default, x, y, label)
    return nodes


def set_scene_fps_driver(driver):
    """Drive a Value output with scene time in seconds, honouring fps_base."""
    driver.expression = "frame / (fps / fps_base)"
    fps = driver.variables.new()
    fps.name = "fps"
    fps.targets[0].id_type = 'SCENE'
    fps.targets[0].id = bpy.context.scene
    fps.targets[0].data_path = "render.fps"
    fps_base = driver.variables.new()
    fps_base.name = "fps_base"
    fps_base.targets[0].id_type = 'SCENE'
    fps_base.targets[0].id = bpy.context.scene
    fps_base.targets[0].data_path = "render.fps_base"


def create_scene_time_value(tree, x, y, label="Time"):
    """Value node driven by scene time in seconds."""
    node = CreateShaderNodeValue(tree, 1, x, y, label)
    fcurve = node.outputs[0].driver_add("default_value")
    set_scene_fps_driver(fcurve.driver)
    return node


def set_uv_transform(mapping_node, data):
    """Apply the decal UVOffset/UVRotation/UVScale parameters to a Mapping node."""
    if "UVOffsetX" in data:
        mapping_node.inputs[1].default_value[0] = data["UVOffsetX"]
    if "UVOffsetY" in data:
        mapping_node.inputs[1].default_value[1] = data["UVOffsetY"]
    if "UVRotation" in data:
        mapping_node.inputs[2].default_value[0] = data["UVRotation"]
        mapping_node.inputs[2].default_value[1] = data["UVRotation"]
    if "UVScaleX" in data:
        mapping_node.inputs[3].default_value[0] = data["UVScaleX"]
    if "UVScaleY" in data:
        mapping_node.inputs[3].default_value[1] = data["UVScaleY"]


def populate_color_ramp(ramp_node, entries, alpha=1.0):
    """Fill a ColorRamp from REDengine gradient entries ({value, color{R,G,B}})."""
    elements = ramp_node.color_ramp.elements
    while len(elements) > 1:
        elements.remove(elements[-1])
    for index, entry in enumerate(entries):
        position = entry.get("value", 0)
        element = elements[0] if index == 0 else elements.new(position)
        element.position = position
        colr = entry["color"]
        element.color = (
            float(colr["Red"]) / 255,
            float(colr["Green"]) / 255,
            float(colr["Blue"]) / 255,
            float(alpha),
            )


# JSON parameter extraction ---------------------------------------------------
# Canonical family for WolvenKit material parameter dicts, consolidating the
# per-module _lookup/_unwrap/_float/_vector/_color/_texture_path copies from
# device_diode, global_water_patch, and hologram. Semantics follow the most
# defensive variant (device_diode): cycle-guarded unwrapping, finite-float
# coercion, and channel normalisation that is behaviourally identical to the
# global_water_patch variant once clamped.

def lookup_param(data, key, default=None):
    if not isinstance(data, dict):
        return default
    if key in data:
        return data[key]
    target = key.lower()
    for candidate, value in data.items():
        if str(candidate).lower() == target:
            return value
    return default


def unwrap_param(value):
    visited = set()
    while isinstance(value, dict) and id(value) not in visited:
        visited.add(id(value))
        for key in ("$value", "value", "scalar", "color", "vector", "texture"):
            if key in value:
                value = value[key]
                break
        else:
            return value
    return value


def param_float(data, key, default=0.0):
    value = unwrap_param(lookup_param(data, key, default))
    try:
        result = float(value)
    except (TypeError, ValueError):
        return float(default)
    return result if math.isfinite(result) else float(default)


def param_vector(data, key, default):
    value = unwrap_param(lookup_param(data, key, default))
    if isinstance(value, dict):
        result = []
        for index, axis in enumerate(("X", "Y", "Z", "W")):
            try:
                result.append(float(value.get(axis, default[index])))
            except (TypeError, ValueError):
                result.append(float(default[index]))
        return tuple(result)
    if isinstance(value, (list, tuple)):
        result = []
        for index in range(4):
            source = value[index] if index < len(value) else default[index]
            try:
                result.append(float(source))
            except (TypeError, ValueError):
                result.append(float(default[index]))
        return tuple(result)
    return tuple(float(component) for component in default)


def coerce_color(value, default):
    if isinstance(value, dict):
        channels = (
            value.get("Red", value.get("R", default[0])),
            value.get("Green", value.get("G", default[1])),
            value.get("Blue", value.get("B", default[2])),
            value.get("Alpha", value.get("A", default[3])),
            )
    elif isinstance(value, (list, tuple)):
        channels = tuple(value[:4]) + tuple(default[len(value[:4]):])
    else:
        channels = default

    normalized = []
    for component in channels:
        try:
            component = float(component)
        except (TypeError, ValueError):
            component = 0.0
        normalized.append(component / 255.0 if abs(component) > 1.0 else component)
    return tuple(max(0.0, min(1.0, component)) for component in normalized)


def param_color(data, key, default):
    return coerce_color(unwrap_param(lookup_param(data, key, default)), default)


def coerce_texture_path(value):
    visited = set()
    while isinstance(value, dict) and id(value) not in visited:
        visited.add(id(value))
        if "DepotPath" in value:
            value = value["DepotPath"]
        elif "$value" in value:
            value = value["$value"]
        elif "texture" in value:
            value = value["texture"]
        elif "value" in value:
            value = value["value"]
        else:
            return ""
    if not isinstance(value, str) or value == "null":
        return ""
    return value


def param_texture_path(data, key):
    return coerce_texture_path(lookup_param(data, key))


def clamp01(value, minimum=0.0, maximum=1.0):
    return max(minimum, min(maximum, float(value)))


# Node graph helpers ----------------------------------------------------------

def new_labeled_node(nodes, node_type, name, location):
    node = nodes.new(node_type)
    node.name = name
    node.label = name
    node.location = location
    return node


def find_input(node, *names):
    for name in names:
        socket = node.inputs.get(name)
        if socket is not None:
            return socket
    return None


def find_output(node, *names):
    for name in names:
        socket = node.outputs.get(name)
        if socket is not None:
            return socket
    return None


def set_input_value(node, value, *names):
    socket = find_input(node, *names)
    if socket is not None:
        socket.default_value = value
    return socket


def link_sockets(links, output_socket, input_socket):
    if output_socket is not None and input_socket is not None:
        links.new(output_socket, input_socket)


def set_non_color(image):
    if image is None:
        return
    try:
        image.colorspace_settings.name = "Non-Color"
    except (AttributeError, TypeError, ValueError):
        pass


# Node group construction -----------------------------------------------------

def add_group_io(group, inputs, outputs):
    for socket_type, name in inputs:
        group.interface.new_socket(name=name, socket_type=socket_type, in_out='INPUT')
    for socket_type, name in outputs:
        group.interface.new_socket(name=name, socket_type=socket_type, in_out='OUTPUT')


def get_or_build_node_group(name, inputs, outputs, build):
    group = bpy.data.node_groups.get(name)
    if group is not None:
        return group

    group = bpy.data.node_groups.new(name, "ShaderNodeTree")
    add_group_io(group, inputs, outputs)
    build(group)
    return group


def add_group_node(tree, group, loc, label=None, name=None):
    node = create_node(tree.nodes, "ShaderNodeGroup", loc, label=label or group.name)
    node.node_tree = group
    if name:
        node.name = name
    return node


def create_normal_map_rel(curMat, rel_path, x, y, label, image_format, depot_path, proj_path):
    """CreateShaderNodeNormalMap for depot-relative paths: same graph topology,
    but the image resolves through imageFromRelPath so project overrides and
    the asset index apply, unlike the BasePath string-concat sites this
    replaces."""
    nMap = curMat.nodes.new("ShaderNodeNormalMap")
    nMap.location = (x, y)
    nMap.hide = True

    if rel_path:
        img = imageFromRelPath(rel_path, image_format, isNormal=True, DepotPath=depot_path, ProjPath=proj_path)
        img_node = create_node(curMat.nodes, "ShaderNodeTexImage", (x - 400, y), label=label, image=img)
        rebuild = CreateRebildNormalGroup(curMat, x - 150, y, label + ' Rebuilt')
        curMat.links.new(img_node.outputs[0], rebuild.inputs[0])
        curMat.links.new(rebuild.outputs[0], nMap.inputs[1])

    return nMap


def create_global_normal_rel(curMat, rel_path, x, y, label, image_format, depot_path, proj_path):
    """CreateShaderNodeGlobalNormalMap for depot-relative paths: a plain
    non-color image node the caller wires into its own normal chain, resolved
    through imageFromRelPath instead of a BasePath string concat."""
    img = imageFromRelPath(rel_path, image_format, isNormal=True, DepotPath=depot_path, ProjPath=proj_path)
    node = create_node(curMat.nodes, "ShaderNodeTexImage", (x - 450, y), label=label, image=img, hide=False)
    node.width = 350
    return node
