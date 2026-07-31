import math
from collections import OrderedDict

import bpy
from ..blender.transactions import new_tracked_datablock

from ..materials.blender.images import imageFromRelPath, resolve_relative_image_path
from ..materials.blender.nodes import CreateRebildNormalGroup, CreateShaderNodeValue, create_node
from ..materials.blender.profiling import begin_material_phase, end_material_phase
from ..materials.blender.helper_caches import register_helper_cache


class MaterialTypeBase:
    def __init__(self, BasePath, image_format, ProjPath=""):
        self.BasePath = BasePath
        self.ProjPath = ProjPath
        self.image_format = image_format

    def _image_from_rel_path(self, reference, is_normal=False):
        if not reference:
            return None
        options = {
            "DepotPath": self.BasePath,
            "ProjPath": self.ProjPath,
        }
        if is_normal:
            options["isNormal"] = True
        return imageFromRelPath(
            reference,
            self.image_format,
            **options,
        )

    def found(self, texture_path):
        result = depot_texture_exists(
            texture_path,
            self.image_format,
            self.BasePath,
            self.ProjPath,
        )
        if not result:
            print(f"Texture not found: {texture_path}")
        return result

    def _load_relative_image(
        self,
        path,
        *,
        non_color=False,
        reject_suffixes=(),
        error_label="material",
    ):
        if not path or any(str(path).lower().endswith(suffix) for suffix in reject_suffixes):
            return None
        try:
            image = imageFromRelPath(
                path,
                self.image_format,
                isNormal=non_color,
                DepotPath=self.BasePath,
                ProjPath=self.ProjPath,
            )
        except Exception as error:
            print(f"Failed to load {error_label} texture {path}: {error}")
            return None
        if non_color:
            set_non_color(image)
        return image


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
    started = begin_material_phase()
    try:
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
    finally:
        if started is not None:
            end_material_phase(started, "material.driver_create", label="scene_time")


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


# Decal resource helpers ------------------------------------------------------

_DECAL_VALUES_CACHE = OrderedDict()
_DECAL_VALUES_CACHE_LIMIT = 2048
_TEXTURE_RESOLUTION_CACHE = OrderedDict()
_TEXTURE_RESOLUTION_CACHE_LIMIT = 4096
_DECAL_HELPER_STATS = {
    "value_hits": 0,
    "value_misses": 0,
    "path_hits": 0,
    "path_misses": 0,
}


def _bounded_identity_cache(cache, key, source, value, limit):
    cache[key] = (source, value)
    cache.move_to_end(key)
    while len(cache) > limit:
        cache.popitem(last=False)
    return value


def decal_values(data, priority=()):
    """Flatten WolvenKit decal value records once per shared values list."""
    values = data.get("values") if isinstance(data, dict) else None
    if not isinstance(values, list):
        return {}

    priority = tuple(priority)
    cache_key = (id(values), priority)
    cached = _DECAL_VALUES_CACHE.get(cache_key)
    if cached is not None and cached[0] is values:
        _DECAL_VALUES_CACHE.move_to_end(cache_key)
        _DECAL_HELPER_STATS["value_hits"] += 1
        return cached[1]

    _DECAL_HELPER_STATS["value_misses"] += 1
    result = {}
    for entry in values:
        if not isinstance(entry, dict):
            continue
        if priority:
            for key in priority:
                if key in entry:
                    result[key] = entry[key]
                    break
        else:
            result.update(entry)

    return _bounded_identity_cache(
        _DECAL_VALUES_CACHE,
        cache_key,
        values,
        result,
        _DECAL_VALUES_CACHE_LIMIT,
    )


def resolve_depot_texture(texture_path, image_format, depot_path, proj_path=""):
    """Resolve a decal texture through the canonical indexed image boundary."""
    if not texture_path:
        return None
    key = (
        str(texture_path),
        str(image_format).lower(),
        str(depot_path),
        str(proj_path),
    )
    if key in _TEXTURE_RESOLUTION_CACHE:
        cached = _TEXTURE_RESOLUTION_CACHE[key]
        _TEXTURE_RESOLUTION_CACHE.move_to_end(key)
        _DECAL_HELPER_STATS["path_hits"] += 1
        return cached

    _DECAL_HELPER_STATS["path_misses"] += 1
    resolved = resolve_relative_image_path(
        texture_path,
        image_format=image_format,
        DepotPath=depot_path,
        ProjPath=proj_path,
    )
    _TEXTURE_RESOLUTION_CACHE[key] = resolved
    _TEXTURE_RESOLUTION_CACHE.move_to_end(key)
    while len(_TEXTURE_RESOLUTION_CACHE) > _TEXTURE_RESOLUTION_CACHE_LIMIT:
        _TEXTURE_RESOLUTION_CACHE.popitem(last=False)
    return resolved


def depot_texture_exists(texture_path, image_format, depot_path, proj_path=""):
    return resolve_depot_texture(
        texture_path, image_format, depot_path, proj_path
    ) is not None


def decal_helper_cache_stats():
    return {
        **_DECAL_HELPER_STATS,
        "value_entries": len(_DECAL_VALUES_CACHE),
        "path_entries": len(_TEXTURE_RESOLUTION_CACHE),
    }


def clear_decal_helper_caches():
    _DECAL_VALUES_CACHE.clear()
    _TEXTURE_RESOLUTION_CACHE.clear()
    for key in _DECAL_HELPER_STATS:
        _DECAL_HELPER_STATS[key] = 0


# JSON parameter extraction ---------------------------------------------------

_PARAM_KEY_CACHE = OrderedDict()
_PARAM_KEY_CACHE_LIMIT = 4096
_PARAM_CACHE_STATS = {"hits": 0, "misses": 0}


def _normalized_param_keys(data, *, refresh=False):
    cache_key = id(data)
    cached = _PARAM_KEY_CACHE.get(cache_key)
    if (
        not refresh
        and cached is not None
        and cached[0] is data
        and cached[1] == len(data)
    ):
        _PARAM_KEY_CACHE.move_to_end(cache_key)
        _PARAM_CACHE_STATS["hits"] += 1
        return cached[2]

    _PARAM_CACHE_STATS["misses"] += 1
    normalized = {str(candidate).casefold(): candidate for candidate in data}
    _PARAM_KEY_CACHE[cache_key] = (data, len(data), normalized)
    _PARAM_KEY_CACHE.move_to_end(cache_key)
    while len(_PARAM_KEY_CACHE) > _PARAM_KEY_CACHE_LIMIT:
        _PARAM_KEY_CACHE.popitem(last=False)
    return normalized


def clear_param_key_cache():
    _PARAM_KEY_CACHE.clear()
    _PARAM_CACHE_STATS.update(hits=0, misses=0)


def param_key_cache_stats():
    return {**_PARAM_CACHE_STATS, "entries": len(_PARAM_KEY_CACHE)}


register_helper_cache("decal", clear=clear_decal_helper_caches, stats=decal_helper_cache_stats)
register_helper_cache("material_params", clear=clear_param_key_cache, stats=param_key_cache_stats)


def lookup_param(data, key, default=None):
    if not isinstance(data, dict):
        return default
    if key in data:
        return data[key]
    normalized_key = str(key).casefold()
    matched = _normalized_param_keys(data).get(normalized_key)
    if matched is None or matched not in data:
        matched = _normalized_param_keys(data, refresh=True).get(normalized_key)
    return data.get(matched, default) if matched is not None else default


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

_NODE_GROUP_CACHE = {}
_NODE_GROUP_CACHE_STATS = {"hits": 0, "misses": 0, "stale": 0}


def clear_node_group_cache():
    _NODE_GROUP_CACHE.clear()
    _NODE_GROUP_CACHE_STATS.update(hits=0, misses=0, stale=0)


def node_group_cache_stats():
    return {**_NODE_GROUP_CACHE_STATS, "entries": len(_NODE_GROUP_CACHE)}


register_helper_cache("material_node_groups", clear=clear_node_group_cache, stats=node_group_cache_stats)


def add_group_io(group, inputs, outputs):
    for socket_type, name in inputs:
        group.interface.new_socket(name=name, socket_type=socket_type, in_out='INPUT')
    for socket_type, name in outputs:
        group.interface.new_socket(name=name, socket_type=socket_type, in_out='OUTPUT')


def get_or_build_node_group(name, inputs, outputs, build):
    group = _NODE_GROUP_CACHE.get(name)
    if group is not None:
        try:
            if bpy.data.node_groups.get(name) is group:
                _NODE_GROUP_CACHE_STATS["hits"] += 1
                return group
        except (AttributeError, ReferenceError, RuntimeError):
            pass
        _NODE_GROUP_CACHE.pop(name, None)
        _NODE_GROUP_CACHE_STATS["stale"] += 1

    group = bpy.data.node_groups.get(name)
    if group is None:
        _NODE_GROUP_CACHE_STATS["misses"] += 1
        group = new_tracked_datablock("node_groups", name, "ShaderNodeTree")
        add_group_io(group, inputs, outputs)
        build(group)
    else:
        _NODE_GROUP_CACHE_STATS["hits"] += 1
    _NODE_GROUP_CACHE[name] = group
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
