from collections import OrderedDict

import bpy

from ..assetio.cache import store_bounded_lru
from ..assetio.values import coerce_float
from ..bartmoss.scalar import srgb_channel_to_linear
from ..blender.shader_nodes import set_default_if_changed
from ..blender.transactions import new_tracked_datablock
from ..core.log import get_logger
from ..materials.blender.helper_caches import register_helper_cache
from ..materials.blender.images import imageFromRelPath
from ..materials.blender.nodes import (
    CreateShaderNodeValue,
    create_node,
)
from ..materials.blender.profiling import begin_material_phase, end_material_phase
from ..materials.params import (
    clear_param_key_cache,
    coerce_texture_path,
    lookup_param,
    param_key_cache_stats,
)

_LOG = get_logger(__name__)


class MaterialTypeBase:
    # Texture parameters' paths when the material does not set them (see default_texture_path).
    texture_defaults = {}

    def __init__(self, BasePath, image_format, ProjPath=""):
        self.BasePath = BasePath
        self.ProjPath = ProjPath
        self.image_format = image_format
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

    def _load_relative_image(
        self,
        path,
        *,
        non_color=False,
        reject_suffixes=(),
        error_label="material",
    ):
        if not path or any(
            str(path).lower().endswith(suffix) for suffix in reject_suffixes
        ):
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
            _LOG.warning(
                "Failed to load %s texture %s: %s",
                error_label,
                path,
                error,
                exc_info=True,
            )
            return None
        if non_color:
            set_non_color(image)
        return image

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
    chosen = {}
    for spec in specs:
        if spec[0] in data:
            chosen[spec[1]] = spec
    rows = {}
    for spec in specs:
        key, var_name, y, label, default = spec
        if var_name in rows:
            continue
        active = chosen.get(var_name)
        if active is not None:
            key, var_name, y, label, default = active
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
        fps.targets[0].id = bpy.context.scene
        fps.targets[0].data_path = "render.fps"
        fps_base = driver.variables.new()
        fps_base.name = "fps_base"
        fps_base.targets[0].id_type = "SCENE"
        fps_base.targets[0].id = bpy.context.scene
        fps_base.targets[0].data_path = "render.fps_base"
    finally:
        if started is not None:
            end_material_phase(started, "material.driver_create", label="scene_time")


def populate_color_ramp(ramp_node, entries, alpha=1.0):
    """Fill a ColorRamp from serialized REDengine gradient colors"""
    elements = ramp_node.color_ramp.elements
    while len(elements) > 1:
        elements.remove(elements[-1])
    for index, entry in enumerate(entries):
        position = entry.get("value", 0)
        element = elements[0] if index == 0 else elements.new(position)
        element.position = position
        colr = entry["color"]
        rgb = []
        for key in ("Red", "Green", "Blue"):
            rgb.append(srgb_channel_to_linear(float(colr[key]) / 255.0))
        ramp_alpha = float(colr.get("Alpha", alpha * 255.0)) / 255.0
        element.color = (*rgb, max(0.0, min(1.0, ramp_alpha)))


_DECAL_VALUES_CACHE = OrderedDict()
_DECAL_VALUES_CACHE_LIMIT = 2048
_DECAL_HELPER_STATS = {
    "value_hits": 0,
    "value_misses": 0,
}


def decal_values(data, priority=()):
    """Flatten serialized decal value records once per shared values list"""
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

    store_bounded_lru(
        _DECAL_VALUES_CACHE,
        cache_key,
        (values, result),
        limit=_DECAL_VALUES_CACHE_LIMIT,
    )
    return result


def decal_helper_cache_stats():
    return {
        **_DECAL_HELPER_STATS,
        "value_entries": len(_DECAL_VALUES_CACHE),
    }


def clear_decal_helper_caches():
    _DECAL_VALUES_CACHE.clear()
    for key in _DECAL_HELPER_STATS:
        _DECAL_HELPER_STATS[key] = 0


register_helper_cache(
    "decal", clear=clear_decal_helper_caches, stats=decal_helper_cache_stats
)
register_helper_cache(
    "material_params", clear=clear_param_key_cache, stats=param_key_cache_stats
)


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
    return coerce_float(
        unwrap_param(lookup_param(data, key, default)), default, unwrap=False
    )


def param_vector(data, key, default):
    value = unwrap_param(lookup_param(data, key, default))
    if isinstance(value, dict):
        result = []
        for index, axis in enumerate(("X", "Y", "Z", "W")):
            result.append(
                coerce_float(
                    value.get(axis, default[index]),
                    default[index],
                    unwrap=False,
                    finite=False,
                )
            )
        return tuple(result)
    if isinstance(value, (list, tuple)):
        result = []
        for index in range(4):
            source = value[index] if index < len(value) else default[index]
            result.append(
                coerce_float(source, default[index], unwrap=False, finite=False)
            )
        return tuple(result)
    return tuple(float(component) for component in default)


def coerce_color(value, default):
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
    else:
        channels = default

    normalized = []
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


def param_color(data, key, default):
    return coerce_color(unwrap_param(lookup_param(data, key, default)), default)


def param_texture_path(data, key):
    return coerce_texture_path(lookup_param(data, key))


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
        new_link(links, output_socket, input_socket)


def set_non_color(image):
    if image is None:
        return
    try:
        # Assigning the colourspace reloads the image, even when it is unchanged.
        if image.colorspace_settings.name != "Non-Color":
            image.colorspace_settings.name = "Non-Color"
    except ValueError:
        pass


_NODE_GROUP_CACHE = {}
_NODE_GROUP_CACHE_STATS = {"hits": 0, "misses": 0, "stale": 0}


def clear_node_group_cache():
    _NODE_GROUP_CACHE.clear()
    _NODE_GROUP_CACHE_STATS.update(hits=0, misses=0, stale=0)


def node_group_cache_stats():
    return {**_NODE_GROUP_CACHE_STATS, "entries": len(_NODE_GROUP_CACHE)}


register_helper_cache(
    "material_node_groups", clear=clear_node_group_cache, stats=node_group_cache_stats
)


def add_group_io(group, inputs, outputs):
    for socket_type, name in inputs:
        group.interface.new_socket(name=name, socket_type=socket_type, in_out="INPUT")
    for socket_type, name in outputs:
        group.interface.new_socket(name=name, socket_type=socket_type, in_out="OUTPUT")


def get_or_build_node_group(name, inputs, outputs, build):
    group = _NODE_GROUP_CACHE.get(name)
    if group is not None:
        try:
            if bpy.data.node_groups.get(name) is group:
                _NODE_GROUP_CACHE_STATS["hits"] += 1
                return group
        except (ReferenceError, RuntimeError):
            pass
        _NODE_GROUP_CACHE.pop(name, None)
        _NODE_GROUP_CACHE_STATS["stale"] += 1

    group = bpy.data.node_groups.get(name)
    if group is None:
        _NODE_GROUP_CACHE_STATS["misses"] += 1
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
