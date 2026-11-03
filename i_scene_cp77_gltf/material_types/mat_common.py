<<<<<<< Updated upstream
import math
from collections import OrderedDict

import bpy
from ..blender.transactions import new_tracked_datablock

from ..materials.blender.images import imageFromRelPath, resolve_relative_image_path
from ..materials.blender.nodes import CreateRebildNormalGroup, CreateShaderNodeValue, create_node
from ..materials.blender.profiling import begin_material_phase, end_material_phase
from ..materials.blender.helper_caches import register_helper_cache


class MaterialTypeBase:
=======
from collections import OrderedDict

import bpy

from ..assetio.cache import store_bounded_lru
from ..assetio.values import coerce_float
from ..bartmoss.scalar import srgb_channel_to_linear
from ..blender.shader_nodes import set_default_if_changed
from ..blender.transactions import new_tracked_datablock
from ..core.log import get_logger
from ..materials.blender.helper_caches import register_helper_cache
from ..materials.blender.images import imageFromRelPath, resolve_relative_image_path
from ..materials.blender.nodes import (
    CreateRebildNormalGroup,
    CreateShaderNodeValue,
    configure_tangent_normal_map,
    create_node,
)
from ..materials.blender.profiling import begin_material_phase, end_material_phase

_LOG = get_logger(__name__)


class MaterialTypeBase:
    # Texture parameters' paths when the material does not set them (see default_texture_path).
    texture_defaults = {}

>>>>>>> Stashed changes
    def __init__(self, BasePath, image_format, ProjPath=""):
        self.BasePath = BasePath
        self.ProjPath = ProjPath
        self.image_format = image_format
<<<<<<< Updated upstream
=======
        # Names of the nodes a full build gave each per-material value, for apply_structure_values on copies.
        self.structure_slots = {}
        # The material's template, for structure keys of handlers serving several templates.
        self.material_template = ""

    def structure_key(self, Data):
        """What fixes the graph a build makes from Data"""
        return

    def apply_structure_values(self, Data, Mat, slots):
        """Write this material's own values into Mat, a copy of a material of the same structure"""
        raise NotImplementedError

    def _texture_path(self, data, key):
        return default_texture_path(data, key, self.texture_defaults)
>>>>>>> Stashed changes

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
<<<<<<< Updated upstream
            print(f"Texture not found: {texture_path}")
=======
            _LOG.warning("Texture not found: %s", texture_path)
>>>>>>> Stashed changes
        return result

    def _load_relative_image(
        self,
        path,
        *,
        non_color=False,
        reject_suffixes=(),
        error_label="material",
    ):
<<<<<<< Updated upstream
        if not path or any(str(path).lower().endswith(suffix) for suffix in reject_suffixes):
=======
        if not path or any(
            str(path).lower().endswith(suffix) for suffix in reject_suffixes
        ):
>>>>>>> Stashed changes
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
<<<<<<< Updated upstream
            print(f"Failed to load {error_label} texture {path}: {error}")
=======
            _LOG.warning(
                "Failed to load %s texture %s: %s",
                error_label,
                path,
                error,
                exc_info=True,
            )
>>>>>>> Stashed changes
            return None
        if non_color:
            set_non_color(image)
        return image

<<<<<<< Updated upstream

def create_param_value_nodes(tree, data, specs, x=-2000):
    """Create one labelled Value node per parameter variable.

    specs rows are (data_key, var_name, y, label, default). Every var_name is
    guaranteed a node: parameters absent from the material data fall back to
    their template default, so downstream links never dereference a missing
    node. Where several data keys alias one var_name, the last key present in
    the data wins, matching the previous last-writer behaviour without leaving
    orphaned nodes in the tree.
    """
=======
    def _relative_texture_node(
        self,
        nodes,
        path,
        name,
        location,
        *,
        non_color=False,
        error_label="material",
        require_image=False,
        extension=None,
        interpolation=None,
    ):
        image = self._load_relative_image(
            path,
            non_color=non_color,
            error_label=error_label,
        )
        if require_image and image is None:
            return None
        node = new_labeled_node(nodes, "ShaderNodeTexImage", name, location)
        node.image = image
        if extension is not None:
            try:
                node.extension = extension
            except ValueError:
                pass
        if interpolation is not None:
            try:
                node.interpolation = interpolation
            except ValueError:
                pass
        return node

    def _parameter_texture_node(
        self,
        nodes,
        links,
        data,
        key,
        location,
        uv_socket=None,
        *,
        non_color=False,
        error_label="material",
        require_image=False,
        extension="REPEAT",
        interpolation=None,
    ):
        node = self._relative_texture_node(
            nodes,
            param_texture_path(data, key),
            key,
            location,
            non_color=non_color,
            error_label=error_label,
            require_image=require_image,
            extension=extension,
            interpolation=interpolation,
        )
        if node is not None and uv_socket is not None:
            links.new(uv_socket, node.inputs.get("Vector") or node.inputs["Vector"])
        return node


def create_param_value_nodes(tree, data, specs, x=-2000):
    """Create one labelled Value node per parameter variable"""
    return {
        var_name: CreateShaderNodeValue(tree, value, x, y, label)
        for var_name, y, label, value in param_value_rows(data, specs)
    }


def param_value_rows(data, specs):
    """(var_name, y, label, value) of each Value node create_param_value_nodes makes, in creation order"""
>>>>>>> Stashed changes
    chosen = {}
    for spec in specs:
        if spec[0] in data:
            chosen[spec[1]] = spec
<<<<<<< Updated upstream
    nodes = {}
    for spec in specs:
        key, var_name, y, label, default = spec
        if var_name in nodes:
=======
    rows = {}
    for spec in specs:
        key, var_name, y, label, default = spec
        if var_name in rows:
>>>>>>> Stashed changes
            continue
        active = chosen.get(var_name)
        if active is not None:
            key, var_name, y, label, default = active
<<<<<<< Updated upstream
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
=======
            rows[var_name] = (var_name, y, label, data[key])
        else:
            rows[var_name] = (var_name, y, label, default)
    return tuple(rows.values())


def write_slot_values(nodes, slots, values):
    """Set each value on the socket its slot names"""
    for slot, value in values.items():
        target = slots.get(slot)
        if target is None:
            continue
        node_name, socket = target
        node = nodes[node_name]
        if socket is None:
            socket = node.outputs["Color" if node.type == "RGB" else "Value"]
        else:
            socket = node.inputs[socket]
        set_default_if_changed(socket, value)


def set_scene_fps_driver(driver, *, expression="frame / (fps / fps_base)"):
    """Drive a Value output with scene time in seconds, honouring fps_base"""
    started = begin_material_phase()
    try:
        driver.expression = expression
        fps = driver.variables.new()
        fps.name = "fps"
        fps.targets[0].id_type = "SCENE"
>>>>>>> Stashed changes
        fps.targets[0].id = bpy.context.scene
        fps.targets[0].data_path = "render.fps"
        fps_base = driver.variables.new()
        fps_base.name = "fps_base"
<<<<<<< Updated upstream
        fps_base.targets[0].id_type = 'SCENE'
=======
        fps_base.targets[0].id_type = "SCENE"
>>>>>>> Stashed changes
        fps_base.targets[0].id = bpy.context.scene
        fps_base.targets[0].data_path = "render.fps_base"
    finally:
        if started is not None:
            end_material_phase(started, "material.driver_create", label="scene_time")


def create_scene_time_value(tree, x, y, label="Time"):
<<<<<<< Updated upstream
    """Value node driven by scene time in seconds."""
    node = CreateShaderNodeValue(tree, 1, x, y, label)
    fcurve = node.outputs[0].driver_add("default_value")
=======
    """Value node driven by scene time in seconds"""
    node = CreateShaderNodeValue(tree, 1, x, y, label)
    fcurve = node.outputs["Value"].driver_add("default_value")
>>>>>>> Stashed changes
    set_scene_fps_driver(fcurve.driver)
    return node


<<<<<<< Updated upstream
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
=======
def populate_color_ramp(ramp_node, entries, alpha=1.0):
    """Fill a ColorRamp from serialized REDengine gradient colors"""
>>>>>>> Stashed changes
    elements = ramp_node.color_ramp.elements
    while len(elements) > 1:
        elements.remove(elements[-1])
    for index, entry in enumerate(entries):
        position = entry.get("value", 0)
        element = elements[0] if index == 0 else elements.new(position)
        element.position = position
        colr = entry["color"]
<<<<<<< Updated upstream
        element.color = (
            float(colr["Red"]) / 255,
            float(colr["Green"]) / 255,
            float(colr["Blue"]) / 255,
            float(alpha),
            )


# Decal resource helpers ------------------------------------------------------

=======
        rgb = []
        for key in ("Red", "Green", "Blue"):
            rgb.append(srgb_channel_to_linear(float(colr[key]) / 255.0))
        ramp_alpha = float(colr.get("Alpha", alpha * 255.0)) / 255.0
        element.color = (*rgb, max(0.0, min(1.0, ramp_alpha)))


>>>>>>> Stashed changes
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


<<<<<<< Updated upstream
def _bounded_identity_cache(cache, key, source, value, limit):
    cache[key] = (source, value)
    cache.move_to_end(key)
    while len(cache) > limit:
        cache.popitem(last=False)
    return value


def decal_values(data, priority=()):
    """Flatten WolvenKit decal value records once per shared values list."""
=======
def decal_values(data, priority=()):
    """Flatten serialized decal value records once per shared values list"""
>>>>>>> Stashed changes
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

<<<<<<< Updated upstream
    return _bounded_identity_cache(
        _DECAL_VALUES_CACHE,
        cache_key,
        values,
        result,
        _DECAL_VALUES_CACHE_LIMIT,
    )


def resolve_depot_texture(texture_path, image_format, depot_path, proj_path=""):
    """Resolve a decal texture through the canonical indexed image boundary."""
=======
    store_bounded_lru(
        _DECAL_VALUES_CACHE,
        cache_key,
        (values, result),
        limit=_DECAL_VALUES_CACHE_LIMIT,
    )
    return result


def resolve_depot_texture(texture_path, image_format, depot_path, proj_path=""):
    """Resolve a decal texture through the canonical indexed image boundary"""
>>>>>>> Stashed changes
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
<<<<<<< Updated upstream
    _TEXTURE_RESOLUTION_CACHE[key] = resolved
    _TEXTURE_RESOLUTION_CACHE.move_to_end(key)
    while len(_TEXTURE_RESOLUTION_CACHE) > _TEXTURE_RESOLUTION_CACHE_LIMIT:
        _TEXTURE_RESOLUTION_CACHE.popitem(last=False)
    return resolved


def depot_texture_exists(texture_path, image_format, depot_path, proj_path=""):
    return resolve_depot_texture(
        texture_path, image_format, depot_path, proj_path
    ) is not None
=======
    return store_bounded_lru(
        _TEXTURE_RESOLUTION_CACHE,
        key,
        resolved,
        limit=_TEXTURE_RESOLUTION_CACHE_LIMIT,
    )


def depot_texture_exists(texture_path, image_format, depot_path, proj_path=""):
    return (
        resolve_depot_texture(texture_path, image_format, depot_path, proj_path)
        is not None
    )
>>>>>>> Stashed changes


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


<<<<<<< Updated upstream
# JSON parameter extraction ---------------------------------------------------

=======
>>>>>>> Stashed changes
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
<<<<<<< Updated upstream
    _PARAM_KEY_CACHE[cache_key] = (data, len(data), normalized)
    _PARAM_KEY_CACHE.move_to_end(cache_key)
    while len(_PARAM_KEY_CACHE) > _PARAM_KEY_CACHE_LIMIT:
        _PARAM_KEY_CACHE.popitem(last=False)
=======
    store_bounded_lru(
        _PARAM_KEY_CACHE,
        cache_key,
        (data, len(data), normalized),
        limit=_PARAM_KEY_CACHE_LIMIT,
    )
>>>>>>> Stashed changes
    return normalized


def clear_param_key_cache():
    _PARAM_KEY_CACHE.clear()
    _PARAM_CACHE_STATS.update(hits=0, misses=0)


def param_key_cache_stats():
    return {**_PARAM_CACHE_STATS, "entries": len(_PARAM_KEY_CACHE)}


<<<<<<< Updated upstream
register_helper_cache("decal", clear=clear_decal_helper_caches, stats=decal_helper_cache_stats)
register_helper_cache("material_params", clear=clear_param_key_cache, stats=param_key_cache_stats)
=======
register_helper_cache(
    "decal", clear=clear_decal_helper_caches, stats=decal_helper_cache_stats
)
register_helper_cache(
    "material_params", clear=clear_param_key_cache, stats=param_key_cache_stats
)
>>>>>>> Stashed changes


def lookup_param(data, key, default=None):
    if not isinstance(data, dict):
        return default
    if key in data:
        return data[key]
    normalized_key = str(key).casefold()
    matched = _normalized_param_keys(data).get(normalized_key)
<<<<<<< Updated upstream
    if matched is None or matched not in data:
=======
    if matched is not None and matched not in data:
>>>>>>> Stashed changes
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
<<<<<<< Updated upstream
    value = unwrap_param(lookup_param(data, key, default))
    try:
        result = float(value)
    except (TypeError, ValueError):
        return float(default)
    return result if math.isfinite(result) else float(default)
=======
    return coerce_float(
        unwrap_param(lookup_param(data, key, default)), default, unwrap=False
    )
>>>>>>> Stashed changes


def param_vector(data, key, default):
    value = unwrap_param(lookup_param(data, key, default))
    if isinstance(value, dict):
        result = []
        for index, axis in enumerate(("X", "Y", "Z", "W")):
<<<<<<< Updated upstream
            try:
                result.append(float(value.get(axis, default[index])))
            except (TypeError, ValueError):
                result.append(float(default[index]))
=======
            result.append(
                coerce_float(
                    value.get(axis, default[index]),
                    default[index],
                    unwrap=False,
                    finite=False,
                )
            )
>>>>>>> Stashed changes
        return tuple(result)
    if isinstance(value, (list, tuple)):
        result = []
        for index in range(4):
            source = value[index] if index < len(value) else default[index]
<<<<<<< Updated upstream
            try:
                result.append(float(source))
            except (TypeError, ValueError):
                result.append(float(default[index]))
=======
            result.append(
                coerce_float(source, default[index], unwrap=False, finite=False)
            )
>>>>>>> Stashed changes
        return tuple(result)
    return tuple(float(component) for component in default)


def coerce_color(value, default):
<<<<<<< Updated upstream
    if isinstance(value, dict):
        channels = (
            value.get("Red", value.get("R", default[0])),
            value.get("Green", value.get("G", default[1])),
            value.get("Blue", value.get("B", default[2])),
            value.get("Alpha", value.get("A", default[3])),
            )
    elif isinstance(value, (list, tuple)):
        channels = tuple(value[:4]) + tuple(default[len(value[:4]):])
=======
    byte_channels = (False, False, False, False)
    if isinstance(value, dict):
        long_names = ("Red", "Green", "Blue", "Alpha")
        short_names = ("R", "G", "B", "A")
        channels = []
        encoded = []
        for index, (long_name, short_name) in enumerate(zip(long_names, short_names)):
            if long_name in value:
                channels.append(value[long_name])
                encoded.append(True)
            elif short_name in value:
                channels.append(value[short_name])
                encoded.append(False)
            else:
                channels.append(default[index])
                encoded.append(False)
        channels = tuple(channels)
        byte_channels = tuple(encoded)
    elif isinstance(value, (list, tuple)):
        channels = tuple(value[:4]) + tuple(default[len(value[:4]) :])
>>>>>>> Stashed changes
    else:
        channels = default

    normalized = []
<<<<<<< Updated upstream
    for component in channels:
        try:
            component = float(component)
        except (TypeError, ValueError):
            component = 0.0
        normalized.append(component / 255.0 if abs(component) > 1.0 else component)
    return tuple(max(0.0, min(1.0, component)) for component in normalized)
=======
    for index, component in enumerate(channels):
        component = coerce_float(component, unwrap=False, finite=False)
        if byte_channels[index] or abs(component) > 1.0:
            component /= 255.0
        normalized.append(component)
    normalized = [max(0.0, min(1.0, component)) for component in normalized]
    return (
        srgb_channel_to_linear(normalized[0]),
        srgb_channel_to_linear(normalized[1]),
        srgb_channel_to_linear(normalized[2]),
        normalized[3],
    )
>>>>>>> Stashed changes


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


<<<<<<< Updated upstream
def clamp01(value, minimum=0.0, maximum=1.0):
    return max(minimum, min(maximum, float(value)))


# Node graph helpers ----------------------------------------------------------

def new_labeled_node(nodes, node_type, name, location):
    node = nodes.new(node_type)
    node.name = name
    node.label = name
    node.location = location
    return node
=======
def new_labeled_node(nodes, node_type, name, location):
    if hasattr(location, "is_output"):
        raise TypeError(
            f"{name}: node location received a shader socket; check helper argument order"
        )
    started = begin_material_phase()
    try:
        node = nodes.new(node_type)
        node.name = name
        node.label = name
        node.location = location
        return node
    finally:
        end_material_phase(
            started,
            "material.node_create",
            label=str(name or node_type or ""),
            metadata={"nodeType": str(node_type or "")},
        )


def new_link(links, output_socket, input_socket):
    started = begin_material_phase()
    try:
        return links.new(output_socket, input_socket)
    finally:
        end_material_phase(started, "material.link_create")


def create_relative_texture_node(
    owner,
    tree,
    data,
    key,
    uv,
    location,
    *,
    non_color=False,
    extension="REPEAT",
    error_label=None,
):
    return owner._parameter_texture_node(
        tree.nodes,
        tree.links,
        data,
        key,
        location,
        uv,
        non_color=non_color,
        error_label=error_label or key,
        require_image=True,
        extension=extension,
    )
>>>>>>> Stashed changes


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
<<<<<<< Updated upstream
        links.new(output_socket, input_socket)
=======
        new_link(links, output_socket, input_socket)
>>>>>>> Stashed changes


def set_non_color(image):
    if image is None:
        return
    try:
<<<<<<< Updated upstream
        image.colorspace_settings.name = "Non-Color"
    except (AttributeError, TypeError, ValueError):
        pass


# Node group construction -----------------------------------------------------

=======
        # Assigning the colourspace reloads the image, even when it is unchanged.
        if image.colorspace_settings.name != "Non-Color":
            image.colorspace_settings.name = "Non-Color"
    except ValueError:
        pass


>>>>>>> Stashed changes
_NODE_GROUP_CACHE = {}
_NODE_GROUP_CACHE_STATS = {"hits": 0, "misses": 0, "stale": 0}


def clear_node_group_cache():
    _NODE_GROUP_CACHE.clear()
    _NODE_GROUP_CACHE_STATS.update(hits=0, misses=0, stale=0)


def node_group_cache_stats():
    return {**_NODE_GROUP_CACHE_STATS, "entries": len(_NODE_GROUP_CACHE)}


<<<<<<< Updated upstream
register_helper_cache("material_node_groups", clear=clear_node_group_cache, stats=node_group_cache_stats)
=======
register_helper_cache(
    "material_node_groups", clear=clear_node_group_cache, stats=node_group_cache_stats
)
>>>>>>> Stashed changes


def add_group_io(group, inputs, outputs):
    for socket_type, name in inputs:
<<<<<<< Updated upstream
        group.interface.new_socket(name=name, socket_type=socket_type, in_out='INPUT')
    for socket_type, name in outputs:
        group.interface.new_socket(name=name, socket_type=socket_type, in_out='OUTPUT')
=======
        group.interface.new_socket(name=name, socket_type=socket_type, in_out="INPUT")
    for socket_type, name in outputs:
        group.interface.new_socket(name=name, socket_type=socket_type, in_out="OUTPUT")
>>>>>>> Stashed changes


def get_or_build_node_group(name, inputs, outputs, build):
    group = _NODE_GROUP_CACHE.get(name)
    if group is not None:
        try:
            if bpy.data.node_groups.get(name) is group:
                _NODE_GROUP_CACHE_STATS["hits"] += 1
                return group
<<<<<<< Updated upstream
        except (AttributeError, ReferenceError, RuntimeError):
=======
        except (ReferenceError, RuntimeError):
>>>>>>> Stashed changes
            pass
        _NODE_GROUP_CACHE.pop(name, None)
        _NODE_GROUP_CACHE_STATS["stale"] += 1

    group = bpy.data.node_groups.get(name)
    if group is None:
        _NODE_GROUP_CACHE_STATS["misses"] += 1
<<<<<<< Updated upstream
        group = new_tracked_datablock("node_groups", name, "ShaderNodeTree")
        add_group_io(group, inputs, outputs)
        build(group)
=======
        started = begin_material_phase()
        try:
            group = new_tracked_datablock(
                "node_groups",
                name,
                "ShaderNodeTree",
            )
            add_group_io(group, inputs, outputs)
            build(group)
        except BaseException:
            if group is not None:
                try:
                    bpy.data.node_groups.remove(group)
                except (AttributeError, ReferenceError, RuntimeError, TypeError):
                    _LOG.debug(
                        "Cannot remove incomplete material group %s",
                        name,
                        exc_info=True,
                    )
            raise
        finally:
            end_material_phase(
                started,
                "material.node_group_cold_build",
                label=name,
                metadata={"helper": "get_or_build_node_group"},
            )
>>>>>>> Stashed changes
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


<<<<<<< Updated upstream
def create_normal_map_rel(curMat, rel_path, x, y, label, image_format, depot_path, proj_path):
    """CreateShaderNodeNormalMap for depot-relative paths: same graph topology,
    but the image resolves through imageFromRelPath so project overrides and
    the asset index apply, unlike the BasePath string-concat sites this
    replaces."""
    nMap = curMat.nodes.new("ShaderNodeNormalMap")
=======
def create_normal_map_rel(
    curMat, rel_path, x, y, label, image_format, depot_path, proj_path
):
    """Create the depot-relative normal-map graph"""
    nMap = configure_tangent_normal_map(curMat.nodes.new("ShaderNodeNormalMap"))
>>>>>>> Stashed changes
    nMap.location = (x, y)
    nMap.hide = True

    if rel_path:
<<<<<<< Updated upstream
        img = imageFromRelPath(rel_path, image_format, isNormal=True, DepotPath=depot_path, ProjPath=proj_path)
        img_node = create_node(curMat.nodes, "ShaderNodeTexImage", (x - 400, y), label=label, image=img)
        rebuild = CreateRebildNormalGroup(curMat, x - 150, y, label + ' Rebuilt')
        curMat.links.new(img_node.outputs[0], rebuild.inputs[0])
        curMat.links.new(rebuild.outputs[0], nMap.inputs[1])
=======
        img = imageFromRelPath(
            rel_path,
            image_format,
            isNormal=True,
            DepotPath=depot_path,
            ProjPath=proj_path,
        )
        img_node = create_node(
            curMat.nodes, "ShaderNodeTexImage", (x - 400, y), label=label, image=img
        )
        rebuild = CreateRebildNormalGroup(curMat, x - 150, y, label + " Rebuilt")
        curMat.links.new(img_node.outputs["Color"], rebuild.inputs["Image"])
        curMat.links.new(rebuild.outputs["Image"], nMap.inputs["Color"])
>>>>>>> Stashed changes

    return nMap


<<<<<<< Updated upstream
def create_global_normal_rel(curMat, rel_path, x, y, label, image_format, depot_path, proj_path):
    """CreateShaderNodeGlobalNormalMap for depot-relative paths: a plain
    non-color image node the caller wires into its own normal chain, resolved
    through imageFromRelPath instead of a BasePath string concat."""
    img = imageFromRelPath(rel_path, image_format, isNormal=True, DepotPath=depot_path, ProjPath=proj_path)
    node = create_node(curMat.nodes, "ShaderNodeTexImage", (x - 450, y), label=label, image=img, hide=False)
    node.width = 350
    return node
=======
def material_property_socket(
    nodes,
    material,
    property_name,
    default,
    location,
    label=None,
    *,
    name=None,
    initial=None,
):
    """Expose a material-owned property through an independently driven Value node"""
    material[property_name] = float(material.get(property_name, default))
    node = new_labeled_node(
        nodes, "ShaderNodeValue", name or label or property_name, location
    )
    node.label = label or property_name
    node.outputs["Value"].default_value = (
        material[property_name] if initial is None else float(initial)
    )
    driver = node.outputs["Value"].driver_add("default_value").driver
    variable = driver.variables.new()
    variable.name = "value"
    variable.targets[0].id_type = "MATERIAL"
    variable.targets[0].id = material
    variable.targets[0].data_path = f'["{property_name}"]'
    driver.expression = "value"
    return node.outputs["Value"]


def scene_time_socket(nodes, location, name="Scene Time"):
    """Build the guarded scene-time recipe used by decal animation"""
    node = new_labeled_node(nodes, "ShaderNodeValue", name, location)
    node.outputs["Value"].default_value = 0.0
    driver = node.outputs["Value"].driver_add("default_value").driver
    set_scene_fps_driver(driver, expression="frame / max(1e-8, fps / fps_base)")
    return node.outputs["Value"]


def default_texture_path(data, key, defaults):
    """Apply authored-null semantics separately from a missing parameter default"""
    missing = object()
    raw = lookup_param(data, key, missing)
    path = defaults.get(key, "") if raw is missing else coerce_texture_path(raw)
    return (
        ""
        if not path or str(path).strip().casefold() in {"0", "null", "none"}
        else str(path)
    )
>>>>>>> Stashed changes
