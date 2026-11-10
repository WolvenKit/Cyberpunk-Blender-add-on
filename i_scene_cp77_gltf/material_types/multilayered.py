import hashlib
import os
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from functools import lru_cache
from pathlib import Path

import bpy

from ..assetio.index import IndexPolicy, build_asset_index
from ..assetio.paths import (
    LOCAL_PATHS_IGNORE_CASE,
    absolute_local_path_key,
    local_path_key,
    normalize_local_path,
)
from ..assetio.resolver import resolve_asset_path
from ..assetio.values import coerce_float
from ..blender import shader_nodes
from ..blender.shader_nodes import set_default_if_changed
from ..blender.transactions import new_tracked_datablock, track_created_datablock
from ..core.log import debug_exception, get_logger
from ..materials.blender.helper_caches import register_helper_cache
from ..materials.blender.images import imageFromPath, imageFromRelPath
from ..materials.blender.multilayer import (
    clear_override_palette_cache,
    override_palette_stats,
    queue_override_palette,
    sync_hidden_layer_links,
)
from ..materials.blender.nodes import (
    configure_tangent_normal_map,
    create_node,
    createOverrideTable,
    get_inputs,
)
from ..materials.blender.profiling import begin_material_phase, end_material_phase
from ..materials.cache_identity import filtered_material_data_identity
from ..materials.params import coerce_texture_path
from ..materials.resources import load_material_document
from .graph import add_bundle_items, combine_bundle_node, separate_bundle_node
from .mat_common import (
    MaterialTypeBase,
    find_input,
    param_float,
    param_texture_path,
    param_vector,
)
from .normal_math import vector_normal_z_node

_LOG = get_logger(__name__)

_ML_CACHE_VERSION = 5

LAYER_BUNDLE_ITEMS = (
    ("RGBA", "Color"),
    ("FLOAT", "Metalness"),
    ("FLOAT", "Roughness"),
    ("VECTOR", "Normal"),
    ("VECTOR", "Microblend"),
    ("FLOAT", "Layer Mask"),
)
_SURFACE_BUNDLE_ITEMS = (
    ("RGBA", "Base Color"),
    ("FLOAT", "Metallic"),
    ("FLOAT", "Roughness"),
    ("VECTOR", "Normal"),
)

_TEMPLATE_CONTROL_BUNDLE_ITEMS = (
    ("RGBA", "Color Scale"),
    ("FLOAT", "Normal Strength"),
    ("FLOAT", "Tile"),
    ("FLOAT", "Offset U"),
    ("FLOAT", "Offset V"),
)
_TEMPLATE_SAMPLE_BUNDLE_ITEMS = (
    ("RGBA", "Color"),
    ("FLOAT", "Metalness"),
    ("FLOAT", "Roughness"),
    ("VECTOR", "Normal"),
)
_LEVELS_CONTROL_BUNDLE_ITEMS = (
    ("VECTOR", "Metal In"),
    ("VECTOR", "Metal Out"),
    ("VECTOR", "Rough In"),
    ("VECTOR", "Rough Out"),
)
_MICROBLEND_UV_BUNDLE_ITEMS = (
    ("FLOAT", "Tile"),
    ("FLOAT", "Offset U"),
    ("FLOAT", "Offset V"),
)
_MICROBLEND_CONTROL_BUNDLE_ITEMS = (
    ("FLOAT", "Mask"),
    ("FLOAT", "Normal Strength"),
    ("FLOAT", "Contrast"),
    ("FLOAT", "Opacity"),
)
_MICROBLEND_SAMPLE_BUNDLE_ITEMS = (
    ("RGBA", "Color"),
    ("FLOAT", "Alpha"),
)
_MASK_RESULT_BUNDLE_ITEMS = (
    ("VECTOR", "Microblend"),
    ("FLOAT", "Layer Mask"),
)


_GLOBAL_NORMAL_DECODE_GROUP = "CP77 Multilayer Global Normal Decode 1.0"


def _global_normal_decode_group():
    existing = bpy.data.node_groups.get(_GLOBAL_NORMAL_DECODE_GROUP)
    if existing is not None:
        return existing

    group = new_tracked_datablock(
        "node_groups",
        _GLOBAL_NORMAL_DECODE_GROUP,
        "ShaderNodeTree",
    )
    color_socket = group.interface.new_socket(
        name="Color",
        socket_type="NodeSocketColor",
        in_out="INPUT",
    )
    intensity_socket = group.interface.new_socket(
        name="Intensity",
        socket_type="NodeSocketFloat",
        in_out="INPUT",
    )
    intensity_socket.default_value = 1.0
    group.interface.new_socket(
        name="Encoded", socket_type="NodeSocketVector", in_out="OUTPUT"
    )
    group.interface.new_socket(
        name="Decoded", socket_type="NodeSocketVector", in_out="OUTPUT"
    )
    group.interface.new_socket(
        name="Normal", socket_type="NodeSocketVector", in_out="OUTPUT"
    )

    nodes = group.nodes
    links = group.links
    group_input = create_node(nodes, "NodeGroupInput", (-1200, 0))
    group_output = create_node(nodes, "NodeGroupOutput", (900, 0))
    split = create_node(nodes, "ShaderNodeSeparateColor", (-1000, 0))
    split.mode = "RGB"
    links.new(group_input.outputs[color_socket.name], split.inputs["Color"])

    def math(operation, x, y, label):
        node = shader_nodes.math(
            nodes, links, operation, label=label, location=(x, y), hide=True
        ).node
        return node

    x2 = math("MULTIPLY", -820, 120, "Global Normal R x2")
    shader_nodes.socket_by_identifier(x2.inputs, "Value_001").default_value = 2.0
    x = math("SUBTRACT", -650, 120, "Global Normal X")
    shader_nodes.socket_by_identifier(x.inputs, "Value_001").default_value = 1.0
    links.new(split.outputs["Red"], x2.inputs["Value"])
    links.new(x2.outputs["Value"], x.inputs["Value"])

    y2 = math("MULTIPLY", -820, -20, "Global Normal G x2")
    shader_nodes.socket_by_identifier(y2.inputs, "Value_001").default_value = 2.0
    y = math("SUBTRACT", -650, -20, "Global Normal Y (DirectX)")
    shader_nodes.socket_by_identifier(y.inputs, "Value_001").default_value = 1.0
    links.new(split.outputs["Green"], y2.inputs["Value"])
    links.new(y2.outputs["Value"], y.inputs["Value"])

    x_sq = math("MULTIPLY", -480, 140, "Global X²")
    y_sq = math("MULTIPLY", -480, 20, "Global Y²")
    links.new(x.outputs["Value"], x_sq.inputs["Value"])
    links.new(
        x.outputs["Value"], shader_nodes.socket_by_identifier(x_sq.inputs, "Value_001")
    )
    links.new(y.outputs["Value"], y_sq.inputs["Value"])
    links.new(
        y.outputs["Value"], shader_nodes.socket_by_identifier(y_sq.inputs, "Value_001")
    )
    sum_sq = math("ADD", -310, 90, "Global X²+Y²")
    links.new(x_sq.outputs["Value"], sum_sq.inputs["Value"])
    links.new(
        y_sq.outputs["Value"],
        shader_nodes.socket_by_identifier(sum_sq.inputs, "Value_001"),
    )
    z_sq = math("SUBTRACT", -140, 90, "Global 1-X²-Y²")
    z_sq.inputs["Value"].default_value = 1.0
    links.new(
        sum_sq.outputs["Value"],
        shader_nodes.socket_by_identifier(z_sq.inputs, "Value_001"),
    )
    safe_z = math("MAXIMUM", 30, 90, "Global max Z²")
    shader_nodes.socket_by_identifier(safe_z.inputs, "Value_001").default_value = 0.0
    links.new(z_sq.outputs["Value"], safe_z.inputs["Value"])
    z = math("SQRT", 200, 90, "Global Normal Z")
    links.new(safe_z.outputs["Value"], z.inputs["Value"])

    decoded = create_node(nodes, "ShaderNodeCombineXYZ", (370, 220))
    decoded.label = "Decoded Global Normal"
    links.new(x.outputs["Value"], decoded.inputs["X"])
    links.new(y.outputs["Value"], decoded.inputs["Y"])
    links.new(z.outputs["Value"], decoded.inputs["Z"])
    links.new(decoded.outputs["Vector"], group_output.inputs["Decoded"])

    x_i = math("MULTIPLY", 370, 90, "Global X × Intensity")
    y_i = math("MULTIPLY", 370, -40, "Global Y × Intensity")
    links.new(x.outputs["Value"], x_i.inputs["Value"])
    links.new(y.outputs["Value"], y_i.inputs["Value"])
    links.new(
        group_input.outputs[intensity_socket.name],
        shader_nodes.socket_by_identifier(x_i.inputs, "Value_001"),
    )
    links.new(
        group_input.outputs[intensity_socket.name],
        shader_nodes.socket_by_identifier(y_i.inputs, "Value_001"),
    )

    z_delta = math("SUBTRACT", 200, -170, "Global Z - 1")
    shader_nodes.socket_by_identifier(z_delta.inputs, "Value_001").default_value = 1.0
    links.new(z.outputs["Value"], z_delta.inputs["Value"])
    z_i = math("MULTIPLY", 370, -170, "Global (Z-1) × Intensity")
    links.new(z_delta.outputs["Value"], z_i.inputs["Value"])
    links.new(
        group_input.outputs[intensity_socket.name],
        shader_nodes.socket_by_identifier(z_i.inputs, "Value_001"),
    )
    z_lerp = math("ADD", 540, -170, "Global lerp Flat Z")
    shader_nodes.socket_by_identifier(z_lerp.inputs, "Value_001").default_value = 1.0
    links.new(z_i.outputs["Value"], z_lerp.inputs["Value"])

    combine = create_node(nodes, "ShaderNodeCombineXYZ", (540, 20))
    links.new(x_i.outputs["Value"], combine.inputs["X"])
    links.new(y_i.outputs["Value"], combine.inputs["Y"])
    links.new(z_lerp.outputs["Value"], combine.inputs["Z"])
    normalize = shader_nodes.vector_math(
        nodes, links, "NORMALIZE", location=(700, 20), hide=True
    ).node
    links.new(combine.outputs["Vector"], normalize.inputs["Vector"])
    links.new(normalize.outputs["Vector"], group_output.inputs["Normal"])
    encode = shader_nodes.vector_math(
        nodes,
        links,
        "MULTIPLY_ADD",
        label="Encode Global Normal for Multilayer Blend",
        location=(700, -100),
        hide=True,
    ).node
    shader_nodes.socket_by_identifier(encode.inputs, "Vector_001").default_value = (
        0.5,
        0.5,
        0.5,
    )
    shader_nodes.socket_by_identifier(encode.inputs, "Vector_002").default_value = (
        0.5,
        0.5,
        0.5,
    )
    links.new(normalize.outputs["Vector"], encode.inputs["Vector"])
    links.new(encode.outputs["Vector"], group_output.inputs["Encoded"])
    return group


_GLOBAL_NORMAL_PARTS = ("texture", "scale", "bias", "decode")


def _source_global_normal_image(owner, data):
    path = param_texture_path(data, "GlobalNormal") or param_texture_path(
        data, "BakedNormal"
    )
    if not path:
        return None
    return imageFromRelPath(
        path,
        owner.image_format,
        isNormal=True,
        DepotPath=owner.BasePath,
        ProjPath=owner.ProjPath,
    )


def _write_global_normal_values(parts, data, image):
    uv_scale = param_vector(data, "GlobalNormalUVScale", (1.0, 1.0, 0.0, 0.0))
    uv_bias = param_vector(data, "GlobalNormalUVBias", (0.0, 0.0, 0.0, 0.0))
    set_default_if_changed(
        shader_nodes.socket_by_identifier(parts["scale"].inputs, "Vector_001"),
        (float(uv_scale[0]), float(uv_scale[1]), 1.0),
    )
    set_default_if_changed(
        shader_nodes.socket_by_identifier(parts["bias"].inputs, "Vector_001"),
        (float(uv_bias[0]), float(uv_bias[1]), 0.0),
    )
    if parts["texture"].image is not image:
        parts["texture"].image = image
    set_default_if_changed(
        parts["decode"].inputs["Intensity"],
        param_float(data, "GlobalNormalIntensity", 1.0),
    )


def _create_source_global_normal(owner, tree, data, location=(-1250, 900)):
    image = _source_global_normal_image(owner, data)
    if image is None:
        return None

    nodes = tree.nodes
    links = tree.links
    texcoord = create_node(nodes, "ShaderNodeTexCoord", location)
    scale = shader_nodes.vector_math(
        nodes, links, "MULTIPLY", location=(location[0] + 190, location[1]), hide=True
    ).node
    bias = shader_nodes.vector_math(
        nodes, links, "ADD", location=(location[0] + 380, location[1]), hide=True
    ).node
    texture = create_node(
        nodes,
        "ShaderNodeTexImage",
        (location[0] + 580, location[1]),
        label="GlobalNormal",
        hide=False,
    )
    texture.width = 300
    links.new(texcoord.outputs["UV"], scale.inputs["Vector"])
    links.new(scale.outputs["Vector"], bias.inputs["Vector"])
    links.new(bias.outputs["Vector"], texture.inputs["Vector"])

    decode = create_node(nodes, "ShaderNodeGroup", (location[0] + 900, location[1]))
    decode.name = "CP77 Multilayer Global Normal Decode"
    decode.label = "CP77 Multilayer Global Normal Decode"
    decode.node_tree = _global_normal_decode_group()
    links.new(texture.outputs["Color"], decode.inputs["Color"])
    parts = {"texture": texture, "scale": scale, "bias": bias, "decode": decode}
    _write_global_normal_values(parts, data, image)
    return {
        "encoded": decode.outputs["Encoded"],
        "decoded": decode.outputs["Decoded"],
        "normal": decode.outputs["Normal"],
        **parts,
    }


_MLSETUP_CACHE = {}
_MLTEMPLATE_CACHE = {}
_ML_LAYER_SPEC_CACHE = {}
_ML_OVERRIDE_CACHE = {}
_ML_TEMPLATE_GROUP_CACHE = {}
_ML_TEMPLATE_BLUEPRINT_NAME = ""
_LAYER_NODE_TOPOLOGY_CACHE = {}
_LAYER_NODE_BLUEPRINT_NAME = ""
_LAYER_NODE_BLUEPRINTS_BY_BASE = {}
_PREPARED_LAYER_CACHE = {}
_MASK_SET_CACHE = {}
_MASK_LAYER_PATH_CACHE = {}
_ASSET_INDEX_CACHE = {}
_FRESH_RUNTIME_TOKEN = ContextVar("cp77_fresh_multilayer_runtime", default="")


@contextmanager
def fresh_multilayer_runtime(token=None):
    token = str(token or uuid.uuid4().hex)
    reset_token = _FRESH_RUNTIME_TOKEN.set(token)
    try:
        yield token
    finally:
        _FRESH_RUNTIME_TOKEN.reset(reset_token)


def _fresh_group_name(base_name, token, purpose):
    digest = hashlib.blake2s(
        f"{purpose}|{token}|{base_name}".encode("utf-8", "ignore"),
        digest_size=6,
    ).hexdigest()
    return f"{base_name}__fresh_{digest}"


_ML_CACHE_STATS = {
    "mlsetup_hits": 0,
    "mlsetup_misses": 0,
    "mltemplate_hits": 0,
    "mltemplate_misses": 0,
    "layer_spec_hits": 0,
    "layer_spec_misses": 0,
    "override_hits": 0,
    "override_misses": 0,
    "template_group_hits": 0,
    "template_group_builds": 0,
    "template_group_clones": 0,
    "template_group_clone_failures": 0,
    "layer_group_hits": 0,
    "layer_group_builds": 0,
    "layer_group_clones": 0,
    "layer_group_base_clones": 0,
    "layer_group_repatched_clones": 0,
    "layer_group_clone_failures": 0,
    "prepared_layer_hits": 0,
    "prepared_layer_misses": 0,
    "prepared_layer_stale": 0,
    "mask_set_hits": 0,
    "mask_set_misses": 0,
    "mask_path_hits": 0,
    "mask_path_misses": 0,
}

_ML_BUILD_PERF = {
    "builds": 0,
    "setup_load": 0.0,
    "layer_prepare": 0.0,
    "mask_resolve": 0.0,
    "mask_images": 0.0,
    "layer_nodes": 0.0,
    "surface_setup": 0.0,
    "layer_microblend": 0.0,
    "layer_template": 0.0,
    "layer_group": 0.0,
    "surface_shell": 0.0,
    "surface_masks": 0.0,
    "surface_global_normal": 0.0,
    "surface_variant": 0.0,
}


def _record_build_phase(name, started):
    _ML_BUILD_PERF[name] += max(0.0, time.perf_counter() - started)


def _cached_node_group(cache, key):
    name = cache.get(key)
    if not name:
        return None
    group = bpy.data.node_groups.get(name)
    if group is None:
        cache.pop(key, None)
    return group


def _template_path_key(path):
    return local_path_key(path) if path else ""


def _resource_extension(reference):
    lower = str(reference or "").lower()
    for extension in (
        ".mlsetup.json",
        ".mltemplate.json",
        ".mt.json",
        ".mi.json",
        ".material.json",
    ):
        if lower.endswith(extension):
            return extension
    filename = str(reference or "").replace("\\", "/").rsplit("/", 1)[-1]
    suffixes = Path(filename).suffixes
    return "".join(suffixes) if suffixes else ".json"


@lru_cache(maxsize=32768)
def _resolved_json_resource(reference, base_path, project_path):
    extension = _resource_extension(reference)
    resolved = resolve_asset_path(
        reference,
        roots=(project_path, base_path),
        extensions=(extension,),
        warn=False,
    )
    if resolved:
        return resolved
    # Preserve unresolved-path provenance without performing an
    # independent existence check. Project overrides are selected by the index.
    relative = str(reference).replace("\\", os.sep).replace("/", os.sep)
    return os.path.normpath(os.path.join(base_path, relative))


def _cached_resource_root(cache, stats_prefix, reference, base_path, project_path):
    path = _resolved_json_resource(reference, base_path, project_path)
    fresh_runtime = bool(_FRESH_RUNTIME_TOKEN.get())
    started = begin_material_phase()
    document = None
    try:
        document = load_material_document(path)
    finally:
        if started is not None:
            end_material_phase(
                started,
                "material.multilayer_json",
                label=str(path),
                metadata={"family": stats_prefix, "fresh": fresh_runtime},
            )
    if document is None:
        raise FileNotFoundError(path)

    cache_key = document.source_identity
    if not fresh_runtime:
        cached = cache.get(cache_key)
        if cached is not None:
            _ML_CACHE_STATS[f"{stats_prefix}_hits"] += 1
            return cached, cache_key

    _ML_CACHE_STATS[f"{stats_prefix}_misses"] += 1
    root = document.root
    if not fresh_runtime:
        cache[cache_key] = root
    return root, cache_key


def clear_multilayer_cache():
    global _ML_TEMPLATE_BLUEPRINT_NAME, _LAYER_NODE_BLUEPRINT_NAME
    _MLSETUP_CACHE.clear()
    _MLTEMPLATE_CACHE.clear()
    _ML_LAYER_SPEC_CACHE.clear()
    _ML_OVERRIDE_CACHE.clear()
    _ML_TEMPLATE_GROUP_CACHE.clear()
    _ML_TEMPLATE_BLUEPRINT_NAME = ""
    _LAYER_NODE_TOPOLOGY_CACHE.clear()
    _LAYER_NODE_BLUEPRINTS_BY_BASE.clear()
    _LAYER_NODE_BLUEPRINT_NAME = ""
    _PREPARED_LAYER_CACHE.clear()
    _MASK_SET_CACHE.clear()
    _MASK_LAYER_PATH_CACHE.clear()
    _ASSET_INDEX_CACHE.clear()
    _resolved_json_resource.cache_clear()
    clear_override_palette_cache()
    for key in _ML_CACHE_STATS:
        _ML_CACHE_STATS[key] = 0
    for key in _ML_BUILD_PERF:
        _ML_BUILD_PERF[key] = 0 if key == "builds" else 0.0


def multilayer_cache_stats():
    return {
        **_ML_CACHE_STATS,
        "mlsetup_entries": len(_MLSETUP_CACHE),
        "mltemplate_entries": len(_MLTEMPLATE_CACHE),
        "layer_spec_entries": len(_ML_LAYER_SPEC_CACHE),
        "override_entries": len(_ML_OVERRIDE_CACHE),
        "template_group_entries": len(_ML_TEMPLATE_GROUP_CACHE),
        "layer_group_entries": len(_LAYER_NODE_TOPOLOGY_CACHE),
        "prepared_layer_entries": len(_PREPARED_LAYER_CACHE),
        "mask_set_entries": len(_MASK_SET_CACHE),
        "mask_path_entries": len(_MASK_LAYER_PATH_CACHE),
        "asset_index_entries": len(_ASSET_INDEX_CACHE),
        "override_palettes": override_palette_stats(),
        "build_perf": dict(_ML_BUILD_PERF),
    }


def _register_template_blueprint(group):
    global _ML_TEMPLATE_BLUEPRINT_NAME
    if (
        group is None
        or group.get("cp77_ml_template_blueprint_version") != _ML_CACHE_VERSION
    ):
        return
    if not _ML_TEMPLATE_BLUEPRINT_NAME:
        _ML_TEMPLATE_BLUEPRINT_NAME = group.name


def _template_group_blueprint():
    global _ML_TEMPLATE_BLUEPRINT_NAME
    if _ML_TEMPLATE_BLUEPRINT_NAME:
        blueprint = bpy.data.node_groups.get(_ML_TEMPLATE_BLUEPRINT_NAME)
        if (
            blueprint is not None
            and blueprint.get("cp77_ml_template_blueprint_version") == _ML_CACHE_VERSION
        ):
            return blueprint
        _ML_TEMPLATE_BLUEPRINT_NAME = ""

    for group_name in _ML_TEMPLATE_GROUP_CACHE.values():
        candidate = bpy.data.node_groups.get(group_name)
        if (
            candidate is not None
            and candidate.get("cp77_ml_template_blueprint_version") == _ML_CACHE_VERSION
        ):
            _ML_TEMPLATE_BLUEPRINT_NAME = candidate.name
            return candidate

    for candidate in bpy.data.node_groups:
        if candidate.get("cp77_ml_template_blueprint_version") == _ML_CACHE_VERSION:
            _ML_TEMPLATE_BLUEPRINT_NAME = candidate.name
            return candidate
    return None


def _patch_template_group(
    group,
    *,
    mltemplate,
    color_image,
    normal_image,
    roughness_image,
    metalness_image,
    tile_multiplier,
    color_mask_out,
):
    nodes = group.nodes
    role_nodes = {}
    for node in nodes:
        role = node.get("cp77_multilayer_template_role")
        if isinstance(role, str):
            role_nodes.setdefault(role, node)
    role_values = (
        ("color_texture", color_image),
        ("normal_texture", normal_image),
        ("roughness_texture", roughness_image),
        ("metalness_texture", metalness_image),
    )
    for role, image in role_values:
        node = role_nodes.get(role)
        if node is None:
            raise RuntimeError(f"Multilayer template blueprint is missing {role}")
        node.image = image

    tile_node = role_nodes.get("tile_multiplier")
    color_ramp = role_nodes.get("color_ramp")
    color_mix = role_nodes.get("color_mix")
    group_input = role_nodes.get("group_input")
    if any(node is None for node in (tile_node, color_ramp, color_mix, group_input)):
        raise RuntimeError("Multilayer template blueprint is incomplete")

    tile_node.outputs["Value"].default_value = float(tile_multiplier)
    color_ramp.inputs["Factor"].default_value = 1
    color_ramp.color_ramp.elements[0].position = 0.9999999 - color_mask_out[0]
    color_ramp.color_ramp.elements[0].color = (
        color_mask_out[1],
        color_mask_out[1],
        color_mask_out[1],
        1,
    )
    shader_nodes.socket_by_identifier(
        color_mix.inputs, "Factor_Float"
    ).default_value = color_mask_out[1]
    group_input["cp77_ml_template"] = mltemplate
    group["cp77_ml_template"] = mltemplate
    group["cp77_ml_template_blueprint_version"] = _ML_CACHE_VERSION


def _clone_template_group(group_name, **patch_values):
    blueprint = _template_group_blueprint()
    if blueprint is None:
        return None
    clone = None
    try:
        clone = track_created_datablock("node_groups", blueprint.copy())
        clone.name = group_name
        _patch_template_group(clone, **patch_values)
        _register_template_blueprint(clone)
        _ML_CACHE_STATS["template_group_clones"] += 1
        return clone
    except Exception:
        debug_exception(
            _LOG,
            "Could not clone multilayer template group %s; building it",
            group_name,
        )
        _ML_CACHE_STATS["template_group_clone_failures"] += 1
        if clone is not None:
            try:
                bpy.data.node_groups.remove(clone)
            except (ReferenceError, RuntimeError, TypeError):
                pass
        return None


def _layer_base_key(base_material):
    return str(
        getattr(base_material, "name_full", "") or getattr(base_material, "name", "")
    )


def _register_layer_blueprint(base_material, group):
    global _LAYER_NODE_BLUEPRINT_NAME
    if (
        group is None
        or group.get("cp77_ml_layer_blueprint_version") != _ML_CACHE_VERSION
    ):
        return
    base_key = _layer_base_key(base_material)
    if base_key:
        _LAYER_NODE_BLUEPRINTS_BY_BASE[base_key] = group.name
    if not _LAYER_NODE_BLUEPRINT_NAME:
        _LAYER_NODE_BLUEPRINT_NAME = group.name


def _layer_node_blueprint(base_material=None):
    global _LAYER_NODE_BLUEPRINT_NAME
    base_key = _layer_base_key(base_material) if base_material is not None else ""
    if base_key:
        group_name = _LAYER_NODE_BLUEPRINTS_BY_BASE.get(base_key)
        if group_name:
            blueprint = bpy.data.node_groups.get(group_name)
            base_node = (
                _layer_role_node(blueprint.nodes, "base_material")
                if blueprint is not None
                else None
            )
            if (
                blueprint is not None
                and blueprint.get("cp77_ml_layer_blueprint_version")
                == _ML_CACHE_VERSION
                and getattr(base_node, "node_tree", None) is base_material
            ):
                return blueprint, True
            _LAYER_NODE_BLUEPRINTS_BY_BASE.pop(base_key, None)

    if _LAYER_NODE_BLUEPRINT_NAME:
        blueprint = bpy.data.node_groups.get(_LAYER_NODE_BLUEPRINT_NAME)
        if (
            blueprint is not None
            and blueprint.get("cp77_ml_layer_blueprint_version") == _ML_CACHE_VERSION
        ):
            return blueprint, False
        _LAYER_NODE_BLUEPRINT_NAME = ""

    for group_name in _LAYER_NODE_TOPOLOGY_CACHE.values():
        candidate = bpy.data.node_groups.get(group_name)
        if (
            candidate is not None
            and candidate.get("cp77_ml_layer_blueprint_version") == _ML_CACHE_VERSION
        ):
            _LAYER_NODE_BLUEPRINT_NAME = candidate.name
            return candidate, False
    for candidate in bpy.data.node_groups:
        if candidate.get("cp77_ml_layer_blueprint_version") == _ML_CACHE_VERSION:
            _LAYER_NODE_BLUEPRINT_NAME = candidate.name
            return candidate, False
    return None, False


def _layer_role_node(nodes, role):
    for node in nodes:
        if node.get("cp77_multilayer_role") == role:
            return node
    return None


def get_cased(data, key, default=None):
    if type(data) is not dict:
        return default
    lower_key = key[:1].lower() + key[1:]
    value = data.get(lower_key)
    if value is not None:
        return value
    upper_key = key[:1].upper() + key[1:]
    value = data.get(upper_key)
    return default if value is None else value


def get_cased_value(data, key, default=None):
    value = get_cased(data, key)
    if type(value) is dict:
        resolved = value.get("$value")
        return default if resolved is None else resolved
    return default if value is None else value


def get_cased_depot_path(data, key, default=None):
    value = get_cased(data, key)
    if type(value) is not dict:
        return default if value is None else value
    depot = value.get("DepotPath")
    if type(depot) is dict:
        resolved = depot.get("$value")
        return default if resolved is None else resolved
    if depot is not None:
        return depot
    resolved = value.get("$value")
    return default if resolved is None else resolved


def _layer_values(layer):
    mat_tile = get_cased(layer, "matTile")
    mb_tile = get_cased(layer, "mbTile")
    return {
        "opacity": get_cased(layer, "opacity"),
        "MatTile": mat_tile,
        "MbScale": float_or_default(mb_tile if mb_tile is not None else mat_tile, 1),
        "MicroblendContrast": get_cased(layer, "microblendContrast", 1),
        "microblendNormalStrength": get_cased(layer, "microblendNormalStrength"),
        "MicroblendOffsetU": get_cased(layer, "microblendOffsetU"),
        "MicroblendOffsetV": get_cased(layer, "microblendOffsetV"),
        "OffsetU": get_cased(layer, "offsetU"),
        "OffsetV": get_cased(layer, "offsetV"),
        "colorScale": get_cased_value(layer, "colorScale"),
        "normalStrength": get_cased_value(layer, "normalStrength"),
        "roughLevelsIn": get_cased_value(layer, "roughLevelsIn"),
        "roughLevelsOut": get_cased_value(layer, "roughLevelsOut"),
        "metalLevelsIn": get_cased_value(layer, "metalLevelsIn"),
        "metalLevelsOut": get_cased_value(layer, "metalLevelsOut"),
    }


def _layer_specs(cache_key, layers):
    fresh_runtime = bool(_FRESH_RUNTIME_TOKEN.get())
    if not fresh_runtime:
        cached = _ML_LAYER_SPEC_CACHE.get(cache_key)
        if cached is not None:
            _ML_CACHE_STATS["layer_spec_hits"] += 1
            return cached

    _ML_CACHE_STATS["layer_spec_misses"] += 1
    specs = tuple(
        (
            get_cased_depot_path(layer, "material"),
            get_cased_depot_path(layer, "microblend"),
            _layer_values(layer),
        )
        for layer in layers or ()
    )
    if not fresh_runtime:
        _ML_LAYER_SPEC_CACHE[cache_key] = specs
    return specs


def input_socket(inputs, socket_name):
    try:
        return inputs[socket_name]
    except (KeyError, TypeError):
        return None


def normalize_socket_default(socket, value):
    current = getattr(socket, "default_value", None)
    if isinstance(value, (list, tuple)) and hasattr(current, "__len__"):
        target_len = len(current)
        value_len = len(value)
        if value_len == target_len:
            return value
        if value_len < target_len:
            return tuple(value) + tuple(0 for _ in range(target_len - value_len))
        return tuple(value[:target_len])
    return value


def set_socket_default(inputs, socket_name, value):
    socket = input_socket(inputs, socket_name)
    if socket is not None:
        set_default_if_changed(socket, normalize_socket_default(socket, value))


def set_socket_range(inputs, socket_name, minimum=None, maximum=None):
    socket = input_socket(inputs, socket_name)
    if socket is None:
        return
    if minimum is not None:
        socket.min_value = minimum
    if maximum is not None:
        socket.max_value = maximum


def set_socket_dimensions(inputs, socket_name, dimensions):
    socket = input_socket(inputs, socket_name)
    if socket is not None:
        socket.dimensions = dimensions


def float_or_default(value, default):
    if value is None:
        return default
    return coerce_float(value, default, unwrap=False, finite=False)


def apply_override(inputs, socket_name, key_val, override_dict, default_val):
    if key_val is not None and key_val in override_dict:
        set_socket_default(inputs, socket_name, override_dict[key_val])
        return True
    set_socket_default(inputs, socket_name, default_val)
    return False


def safe_template_group_name(material_path, context_key, resource_key):
    source = f"{_ML_CACHE_VERSION}|{context_key}|{resource_key}|{material_path}"
    digest = hashlib.blake2s(
        source.encode("utf-8", "ignore"), digest_size=8
    ).hexdigest()
    prefix = os.path.basename(material_path.replace("\\", os.sep)).split(".")[0]
    return f"{prefix}_MLTemplate_{digest}"


def safe_layer_group_name(
    version_major,
    material_path,
    microblend_path,
    context_key,
    base_template_name,
):
    source = (
        f"{_ML_CACHE_VERSION}|{version_major}|{context_key}|{base_template_name}|"
        f"{material_path}|{microblend_path}"
    )
    digest = hashlib.blake2s(
        source.encode("utf-8", "ignore"), digest_size=8
    ).hexdigest()
    prefix = os.path.basename(material_path.replace("\\", os.sep)).split(".")[0]
    return f"{prefix}_LayerTemplate_{version_major}_{digest}"


def mask_mixer_node_group():
    ng_name = "Mask Mixer 2.0.0"
    existing = bpy.data.node_groups.get(ng_name)
    if existing:
        return existing
    mask_mixer = new_tracked_datablock(
        "node_groups", type="ShaderNodeTree", name=ng_name
    )

    mask_mixer.interface.new_socket(
        name="Controls", in_out="INPUT", socket_type="NodeSocketBundle"
    )
    mask_mixer.interface.new_socket(
        name="Sample", in_out="INPUT", socket_type="NodeSocketBundle"
    )
    mask_mixer.interface.new_socket(
        name="Result", in_out="OUTPUT", socket_type="NodeSocketBundle"
    )

    maskMixerInput = create_node(mask_mixer.nodes, "NodeGroupInput", (-1200, -280))
    maskMixerInput.width, maskMixerInput.height = 140.0, 100.0
    maskMixerOutput = create_node(mask_mixer.nodes, "NodeGroupOutput", (1220, -360))
    maskMixerOutput.width, maskMixerOutput.height = 140.0, 100.0

    controls = separate_bundle_node(
        mask_mixer,
        _MICROBLEND_CONTROL_BUNDLE_ITEMS,
        (-1000, -180),
        name="CP77 Microblend Controls Unpack",
        label="Controls",
    )
    sample = separate_bundle_node(
        mask_mixer,
        _MICROBLEND_SAMPLE_BUNDLE_ITEMS,
        (-1000, -480),
        name="CP77 Microblend Sample Unpack",
        label="Sample",
    )
    result = combine_bundle_node(
        mask_mixer,
        _MASK_RESULT_BUNDLE_ITEMS,
        (980, -360),
        name="CP77 Microblend Result Pack",
        label="Mask Result",
    )
    mask_mixer.links.new(maskMixerInput.outputs["Controls"], controls.inputs["Bundle"])
    mask_mixer.links.new(maskMixerInput.outputs["Sample"], sample.inputs["Bundle"])
    mask_mixer.links.new(result.outputs["Bundle"], maskMixerOutput.inputs["Result"])

    mbContrastMax = shader_nodes.math(
        mask_mixer.nodes,
        mask_mixer.links,
        "MAXIMUM",
        label="Safe Microblend Contrast",
        location=(-760, -310),
        hide=False,
    ).node
    shader_nodes.socket_by_identifier(
        mbContrastMax.inputs, "Value_001"
    ).default_value = 0.00001

    mbNormalVectorize = shader_nodes.vector_math(
        mask_mixer.nodes,
        mask_mixer.links,
        "MULTIPLY_ADD",
        label="Decode Microblend XY",
        location=(550, -350),
        hide=True,
    ).node
    shader_nodes.socket_by_identifier(
        mbNormalVectorize.inputs, "Vector_001"
    ).default_value = 2, 2, 0
    shader_nodes.socket_by_identifier(
        mbNormalVectorize.inputs, "Vector_002"
    ).default_value = -1, -1, 0

    mbNormalStr = shader_nodes.vector_math(
        mask_mixer.nodes,
        mask_mixer.links,
        "MULTIPLY",
        label="Microblend Normal Strength",
        location=(760, -300),
        hide=True,
    ).node

    mbMultiply = shader_nodes.math(
        mask_mixer.nodes,
        mask_mixer.links,
        "MULTIPLY",
        label="Active Microblend Strength",
        location=(300, 50),
        hide=True,
    ).node

    mbLessThan = shader_nodes.math(
        mask_mixer.nodes,
        mask_mixer.links,
        "LESS_THAN",
        label="Microblend Below Full Mask",
        location=(300, -100),
        use_clamp=True,
        hide=True,
    ).node
    shader_nodes.socket_by_identifier(
        mbLessThan.inputs, "Value_001"
    ).default_value = 1.0

    maskAdd = shader_nodes.math(
        mask_mixer.nodes,
        mask_mixer.links,
        "ADD",
        label="Mask + Microblend Alpha",
        location=(-550, -720),
        use_clamp=False,
        hide=True,
    ).node

    maskSubtract = shader_nodes.math(
        mask_mixer.nodes,
        mask_mixer.links,
        "SUBTRACT",
        label="Mask Threshold Offset",
        location=(-350, -720),
        use_clamp=False,
        hide=True,
    ).node
    shader_nodes.socket_by_identifier(
        maskSubtract.inputs, "Value_001"
    ).default_value = 1.0

    maskMix = create_node(mask_mixer.nodes, "ShaderNodeMix", (-150, -610))
    maskMix.label = "Microblend Mask Contrast"
    maskMix.data_type = "FLOAT"

    maskMapRange = create_node(mask_mixer.nodes, "ShaderNodeMapRange", (80, -520))
    maskMapRange.label = "Layer Mask Remap"

    maskMultiply = shader_nodes.math(
        mask_mixer.nodes,
        mask_mixer.links,
        "MULTIPLY",
        label="Layer Mask × Opacity",
        location=(330, -450),
        use_clamp=False,
        hide=True,
    ).node

    mask_mixer.links.new(
        controls.outputs["Mask"],
        shader_nodes.socket_by_identifier(maskAdd.inputs, "Value_001"),
    )
    mask_mixer.links.new(
        controls.outputs["Mask"],
        shader_nodes.socket_by_identifier(maskMix.inputs, "B_Float"),
    )
    mask_mixer.links.new(
        controls.outputs["Normal Strength"], mbMultiply.inputs["Value"]
    )
    mask_mixer.links.new(controls.outputs["Contrast"], mbContrastMax.inputs["Value"])
    mask_mixer.links.new(sample.outputs["Color"], mbNormalVectorize.inputs["Vector"])
    mask_mixer.links.new(sample.outputs["Alpha"], maskAdd.inputs["Value"])
    mask_mixer.links.new(
        mbContrastMax.outputs["Value"],
        shader_nodes.socket_by_identifier(maskMix.inputs, "Factor_Float"),
    )
    mask_mixer.links.new(
        mbContrastMax.outputs["Value"], maskMapRange.inputs["From Max"]
    )
    mask_mixer.links.new(maskAdd.outputs["Value"], maskSubtract.inputs["Value"])
    mask_mixer.links.new(
        maskSubtract.outputs["Value"],
        shader_nodes.socket_by_identifier(maskMix.inputs, "A_Float"),
    )
    mask_mixer.links.new(
        shader_nodes.socket_by_identifier(maskMix.outputs, "Result_Float"),
        maskMapRange.inputs["Value"],
    )
    mask_mixer.links.new(maskMapRange.outputs["Result"], maskMultiply.inputs["Value"])
    mask_mixer.links.new(
        controls.outputs["Opacity"],
        shader_nodes.socket_by_identifier(maskMultiply.inputs, "Value_001"),
    )
    mask_mixer.links.new(maskMapRange.outputs["Result"], mbLessThan.inputs["Value"])
    mask_mixer.links.new(
        mbLessThan.outputs["Value"],
        shader_nodes.socket_by_identifier(mbMultiply.inputs, "Value_001"),
    )
    mask_mixer.links.new(
        mbMultiply.outputs["Value"],
        shader_nodes.socket_by_identifier(mbNormalStr.inputs, "Vector_001"),
    )
    mask_mixer.links.new(
        mbNormalVectorize.outputs["Vector"], mbNormalStr.inputs["Vector"]
    )
    mask_mixer.links.new(mbNormalStr.outputs["Vector"], result.inputs["Microblend"])
    mask_mixer.links.new(maskMultiply.outputs["Value"], result.inputs["Layer Mask"])

    return mask_mixer


def levels_node_group():
    existing = bpy.data.node_groups.get("Levels 2077 1.6.7")
    if existing:
        return existing
    levels = new_tracked_datablock(
        "node_groups", type="ShaderNodeTree", name="Levels 2077 1.6.7"
    )

    levels.interface.new_socket(
        name="Input", in_out="INPUT", socket_type="NodeSocketFloat"
    )
    vec2_socket = levels.interface.new_socket(
        name="Levels", in_out="INPUT", socket_type="NodeSocketVector"
    )
    vec2_socket.dimensions = 2
    levels.interface.new_socket(
        name="Result", in_out="OUTPUT", socket_type="NodeSocketFloat"
    )

    levelsInput = levels.nodes.new("NodeGroupInput")
    levelsInput.location = (-1200, 0)

    levelsOutput = levels.nodes.new("NodeGroupOutput")
    levelsOutput.location = (100, 0)

    levelsSepXYZ = levels.nodes.new("ShaderNodeSeparateXYZ")
    levelsSepXYZ.location = (-800, -150)

    levelsMultAdd = shader_nodes.math(
        levels.nodes, levels.links, "MULTIPLY_ADD", location=(-300, 0)
    ).node

    levels.links.new(levelsInput.outputs["Input"], levelsMultAdd.inputs["Value"])
    levels.links.new(levelsInput.outputs["Levels"], levelsSepXYZ.inputs["Vector"])
    levels.links.new(
        levelsSepXYZ.outputs["X"],
        shader_nodes.socket_by_identifier(levelsMultAdd.inputs, "Value_001"),
    )
    levels.links.new(
        levelsSepXYZ.outputs["Y"],
        shader_nodes.socket_by_identifier(levelsMultAdd.inputs, "Value_002"),
    )
    levels.links.new(levelsMultAdd.outputs["Value"], levelsOutput.inputs["Result"])

    return levels


def layer_levels_node_group():
    ng_name = "CP77 Multilayer Levels 1.0.0"
    existing = bpy.data.node_groups.get(ng_name)
    if existing:
        return existing

    group = new_tracked_datablock("node_groups", type="ShaderNodeTree", name=ng_name)
    group.interface.new_socket(
        name="Sample", in_out="INPUT", socket_type="NodeSocketBundle"
    )
    group.interface.new_socket(
        name="Controls", in_out="INPUT", socket_type="NodeSocketBundle"
    )
    group.interface.new_socket(
        name="Sample", in_out="OUTPUT", socket_type="NodeSocketBundle"
    )

    group_input = create_node(group.nodes, "NodeGroupInput", (-900, 0))
    group_output = create_node(group.nodes, "NodeGroupOutput", (420, 0))
    sample = separate_bundle_node(
        group,
        _TEMPLATE_SAMPLE_BUNDLE_ITEMS,
        (-700, 140),
        name="CP77 Base Sample Unpack",
        label="Base Sample",
    )
    controls = separate_bundle_node(
        group,
        _LEVELS_CONTROL_BUNDLE_ITEMS,
        (-700, -180),
        name="CP77 Levels Controls Unpack",
        label="Levels",
    )
    result = combine_bundle_node(
        group,
        _TEMPLATE_SAMPLE_BUNDLE_ITEMS,
        (180, 80),
        name="CP77 Adjusted Sample Pack",
        label="Adjusted Sample",
    )
    group.links.new(group_input.outputs["Sample"], sample.inputs["Bundle"])
    group.links.new(group_input.outputs["Controls"], controls.inputs["Bundle"])
    group.links.new(result.outputs["Bundle"], group_output.inputs["Sample"])

    shared_levels = levels_node_group()
    metal_in = create_node(group.nodes, "ShaderNodeGroup", (-450, 40))
    metal_in.label = "Metal Levels In"
    metal_in.node_tree = shared_levels
    metal_out = create_node(group.nodes, "ShaderNodeGroup", (-220, 40))
    metal_out.label = "Metal Levels Out"
    metal_out.node_tree = shared_levels
    rough_in = create_node(group.nodes, "ShaderNodeGroup", (-450, -120))
    rough_in.label = "Rough Levels In"
    rough_in.node_tree = shared_levels
    rough_out = create_node(group.nodes, "ShaderNodeGroup", (-220, -120))
    rough_out.label = "Rough Levels Out"
    rough_out.node_tree = shared_levels

    group.links.new(sample.outputs["Metalness"], metal_in.inputs["Input"])
    group.links.new(controls.outputs["Metal In"], metal_in.inputs["Levels"])
    group.links.new(metal_in.outputs["Result"], metal_out.inputs["Input"])
    group.links.new(controls.outputs["Metal Out"], metal_out.inputs["Levels"])
    group.links.new(sample.outputs["Roughness"], rough_in.inputs["Input"])
    group.links.new(controls.outputs["Rough In"], rough_in.inputs["Levels"])
    group.links.new(rough_in.outputs["Result"], rough_out.inputs["Input"])
    group.links.new(controls.outputs["Rough Out"], rough_out.inputs["Levels"])

    group.links.new(sample.outputs["Color"], result.inputs["Color"])
    group.links.new(metal_out.outputs["Result"], result.inputs["Metalness"])
    group.links.new(rough_out.outputs["Result"], result.inputs["Roughness"])
    group.links.new(sample.outputs["Normal"], result.inputs["Normal"])
    return group


def _getOrCreateLayerBlend5():
    ng_name = "Layer Blend 2.0.0"
    existing = bpy.data.node_groups.get(ng_name)
    if existing:
        return existing

    NG = new_tracked_datablock("node_groups", ng_name, "ShaderNodeTree")
    NG.interface.new_socket(
        name="Layer A", socket_type="NodeSocketBundle", in_out="INPUT"
    )
    NG.interface.new_socket(
        name="Layer B", socket_type="NodeSocketBundle", in_out="INPUT"
    )
    NG.interface.new_socket(
        name="Layer", socket_type="NodeSocketBundle", in_out="OUTPUT"
    )

    GroupInN = create_node(NG.nodes, "NodeGroupInput", (-900, 0))
    GroupInN.hide = False
    GroupOutN = create_node(NG.nodes, "NodeGroupOutput", (100, 0), hide=False)

    layer_a = separate_bundle_node(
        NG,
        LAYER_BUNDLE_ITEMS,
        (-700, 120),
        name="CP77 Layer A Unpack",
        label="Layer A",
    )
    layer_b = separate_bundle_node(
        NG,
        LAYER_BUNDLE_ITEMS,
        (-700, -220),
        name="CP77 Layer B Unpack",
        label="Layer B",
    )
    blended = combine_bundle_node(
        NG,
        LAYER_BUNDLE_ITEMS,
        (-160, 40),
        name="CP77 Blended Layer Pack",
        label="Blended Layer",
    )
    NG.links.new(GroupInN.outputs["Layer A"], layer_a.inputs["Bundle"])
    NG.links.new(GroupInN.outputs["Layer B"], layer_b.inputs["Bundle"])
    NG.links.new(blended.outputs["Bundle"], GroupOutN.inputs["Layer"])

    blend_mask = create_node(NG.nodes, "NodeReroute", (-500, -380))
    blend_mask.label = "Blend Mask"
    NG.links.new(layer_b.outputs["Layer Mask"], blend_mask.inputs["Input"])

    ColorMixN = create_node(NG.nodes, "ShaderNodeMix", (-380, 160), label="Color")
    ColorMixN.data_type = "RGBA"
    MetalMixN = create_node(NG.nodes, "ShaderNodeMix", (-380, 60), label="Metalness")
    MetalMixN.data_type = "FLOAT"
    RoughMixN = create_node(NG.nodes, "ShaderNodeMix", (-380, -40), label="Roughness")
    RoughMixN.data_type = "FLOAT"
    NormalMixN = create_node(NG.nodes, "ShaderNodeMix", (-380, -140), label="Normal")
    NormalMixN.data_type = "VECTOR"
    NormalMixN.clamp_factor = False
    MicroblendMixN = create_node(
        NG.nodes, "ShaderNodeMix", (-380, -240), label="Microblend"
    )
    MicroblendMixN.data_type = "VECTOR"
    MicroblendMixN.clamp_factor = False

    NG.links.new(
        layer_a.outputs["Color"],
        shader_nodes.socket_by_identifier(ColorMixN.inputs, "A_Color"),
    )
    NG.links.new(
        layer_a.outputs["Metalness"],
        shader_nodes.socket_by_identifier(MetalMixN.inputs, "A_Float"),
    )
    NG.links.new(
        layer_a.outputs["Roughness"],
        shader_nodes.socket_by_identifier(RoughMixN.inputs, "A_Float"),
    )
    NG.links.new(
        layer_a.outputs["Normal"],
        shader_nodes.socket_by_identifier(NormalMixN.inputs, "A_Vector"),
    )
    NG.links.new(
        layer_a.outputs["Microblend"],
        shader_nodes.socket_by_identifier(MicroblendMixN.inputs, "A_Vector"),
    )
    NG.links.new(
        layer_b.outputs["Color"],
        shader_nodes.socket_by_identifier(ColorMixN.inputs, "B_Color"),
    )
    NG.links.new(
        layer_b.outputs["Metalness"],
        shader_nodes.socket_by_identifier(MetalMixN.inputs, "B_Float"),
    )
    NG.links.new(
        layer_b.outputs["Roughness"],
        shader_nodes.socket_by_identifier(RoughMixN.inputs, "B_Float"),
    )
    NG.links.new(
        layer_b.outputs["Normal"],
        shader_nodes.socket_by_identifier(NormalMixN.inputs, "B_Vector"),
    )
    NG.links.new(
        layer_b.outputs["Microblend"],
        shader_nodes.socket_by_identifier(MicroblendMixN.inputs, "B_Vector"),
    )
    for node in (ColorMixN, MetalMixN, RoughMixN, NormalMixN, MicroblendMixN):
        NG.links.new(blend_mask.outputs["Output"], node.inputs["Factor"])

    NG.links.new(
        shader_nodes.socket_by_identifier(ColorMixN.outputs, "Result_Color"),
        blended.inputs["Color"],
    )
    NG.links.new(
        shader_nodes.socket_by_identifier(MetalMixN.outputs, "Result_Float"),
        blended.inputs["Metalness"],
    )
    NG.links.new(
        shader_nodes.socket_by_identifier(RoughMixN.outputs, "Result_Float"),
        blended.inputs["Roughness"],
    )
    NG.links.new(
        shader_nodes.socket_by_identifier(NormalMixN.outputs, "Result_Vector"),
        blended.inputs["Normal"],
    )
    NG.links.new(
        shader_nodes.socket_by_identifier(MicroblendMixN.outputs, "Result_Vector"),
        blended.inputs["Microblend"],
    )
    NG.links.new(layer_b.outputs["Layer Mask"], blended.inputs["Layer Mask"])
    return NG


# Build the canonical multilayer surface data without terminating in a BSDF.
def ml_surface_node_group():
    ng_name = "Multilayer Surface 3.0.0"
    existing = bpy.data.node_groups.get(ng_name)
    if existing:
        return existing

    surface = new_tracked_datablock("node_groups", type="ShaderNodeTree", name=ng_name)

    normal_socket = surface.interface.new_socket(
        name="Normal Map", in_out="INPUT", socket_type="NodeSocketColor"
    )
    normal_socket.default_value = (0.5, 0.5, 1.0, 1.0)
    for index in range(20):
        surface.interface.new_socket(
            name=f"Layer {index + 1}",
            in_out="INPUT",
            socket_type="NodeSocketBundle",
        )

    surface.interface.new_socket(
        name="Surface", in_out="OUTPUT", socket_type="NodeSocketBundle"
    )

    group_input = surface.nodes.new("NodeGroupInput")
    group_input.location = (-1200, 0)
    group_output = surface.nodes.new("NodeGroupOutput")
    group_output.location = (100, 0)

    normal_vectorize = shader_nodes.vector_math(
        surface.nodes, surface.links, "MULTIPLY_ADD", location=(-900, 0), hide=True
    ).node
    shader_nodes.socket_by_identifier(
        normal_vectorize.inputs, "Vector_001"
    ).default_value = (2, 2, 0)
    shader_nodes.socket_by_identifier(
        normal_vectorize.inputs, "Vector_002"
    ).default_value = (-1, -1, 0)

    normal_microblend_add = shader_nodes.vector_math(
        surface.nodes, surface.links, "ADD", location=(-700, -75), hide=True
    ).node
    normal_add = shader_nodes.vector_math(
        surface.nodes, surface.links, "ADD", location=(-700, 0), hide=True
    ).node
    normal_rebuild = vector_normal_z_node(surface, (-500, 0))
    normal_map = configure_tangent_normal_map(
        create_node(surface.nodes, "ShaderNodeNormalMap", (-500, -300))
    )

    blend_group = _getOrCreateLayerBlend5()
    for count in range(1, 20):
        blend = surface.nodes.new("ShaderNodeGroup")
        blend.name = f"Layer_Blend_{count}"
        blend.location = (-900, -150 * count)
        blend.node_tree = blend_group
        if count == 1:
            surface.links.new(
                group_input.outputs[f"Layer {count}"], blend.inputs["Layer A"]
            )
        surface.links.new(
            group_input.outputs[f"Layer {count + 1}"], blend.inputs["Layer B"]
        )

    separate = separate_bundle_node(
        surface,
        LAYER_BUNDLE_ITEMS,
        (-700, -150),
        name="CP77 Final Layer Unpack",
        label="Final Layer",
    )

    surface.links.new(
        group_input.outputs["Normal Map"], normal_vectorize.inputs["Vector"]
    )
    for index in range(18):
        surface.links.new(
            surface.nodes[f"Layer_Blend_{index + 1}"].outputs["Layer"],
            surface.nodes[f"Layer_Blend_{index + 2}"].inputs["Layer A"],
        )
    surface.links.new(
        surface.nodes["Layer_Blend_19"].outputs["Layer"], separate.inputs["Bundle"]
    )

    surface.links.new(
        separate.outputs["Normal"], normal_microblend_add.inputs["Vector"]
    )
    surface.links.new(
        separate.outputs["Microblend"],
        shader_nodes.socket_by_identifier(normal_microblend_add.inputs, "Vector_001"),
    )
    surface.links.new(normal_vectorize.outputs["Vector"], normal_add.inputs["Vector"])
    surface.links.new(
        normal_microblend_add.outputs["Vector"],
        shader_nodes.socket_by_identifier(normal_add.inputs, "Vector_001"),
    )
    surface.links.new(normal_add.outputs["Vector"], normal_rebuild.inputs["Image"])
    surface.links.new(normal_rebuild.outputs["Image"], normal_map.inputs["Color"])

    surface_bundle = combine_bundle_node(
        surface,
        _SURFACE_BUNDLE_ITEMS,
        (-220, -150),
        name="CP77 Multilayer Surface Bundle",
        label="Surface Channels",
    )
    surface.links.new(separate.outputs["Color"], surface_bundle.inputs["Base Color"])
    surface.links.new(separate.outputs["Metalness"], surface_bundle.inputs["Metallic"])
    surface.links.new(separate.outputs["Roughness"], surface_bundle.inputs["Roughness"])
    surface.links.new(normal_map.outputs["Normal"], surface_bundle.inputs["Normal"])
    surface.links.new(surface_bundle.outputs["Bundle"], group_output.inputs["Surface"])

    return surface


register_helper_cache(
    "multilayer", clear=clear_multilayer_cache, stats=multilayer_cache_stats
)


class Multilayered(MaterialTypeBase):
    def __init__(self, BasePath, image_format, ProjPath):
        super().__init__(str(BasePath), image_format, str(ProjPath))
        self._context_key = (
            absolute_local_path_key(self.BasePath),
            absolute_local_path_key(self.ProjPath),
            str(self.image_format).lower(),
            tuple(bpy.app.version),
        )

    def createMLTemplateGroup(self, matTemplateObj, mltemplate, resource_key):
        template_path_key = _template_path_key(mltemplate)
        template_key = (self._context_key, template_path_key, resource_key)
        fresh_token = _FRESH_RUNTIME_TOKEN.get()
        if not fresh_token:
            cached = _cached_node_group(_ML_TEMPLATE_GROUP_CACHE, template_key)
            if cached is not None:
                _ML_CACHE_STATS["template_group_hits"] += 1
                return cached

        group_name = safe_template_group_name(
            mltemplate,
            self._context_key,
            resource_key,
        )
        if fresh_token:
            group_name = _fresh_group_name(group_name, fresh_token, "template")
        else:
            existing = bpy.data.node_groups.get(group_name)
            if existing is not None and existing.get("cp77_ml_template") == mltemplate:
                _ML_TEMPLATE_GROUP_CACHE[template_key] = existing.name
                _ML_CACHE_STATS["template_group_hits"] += 1
                return existing

        CT = imageFromRelPath(
            coerce_texture_path(matTemplateObj.get("colorTexture")),
            self.image_format,
            DepotPath=self.BasePath,
            ProjPath=self.ProjPath,
        )
        NT = imageFromRelPath(
            coerce_texture_path(matTemplateObj.get("normalTexture")),
            self.image_format,
            isNormal=True,
            DepotPath=self.BasePath,
            ProjPath=self.ProjPath,
        )
        RT = imageFromRelPath(
            coerce_texture_path(matTemplateObj.get("roughnessTexture")),
            self.image_format,
            isNormal=True,
            DepotPath=self.BasePath,
            ProjPath=self.ProjPath,
        )
        MT = imageFromRelPath(
            coerce_texture_path(matTemplateObj.get("metalnessTexture")),
            self.image_format,
            isNormal=True,
            DepotPath=self.BasePath,
            ProjPath=self.ProjPath,
        )

        TileMult = float(matTemplateObj.get("tilingMultiplier", 1))
        colorMaskOut = matTemplateObj["colorMaskLevelsOut"]["Elements"]

        cloned = _clone_template_group(
            group_name,
            mltemplate=mltemplate,
            color_image=CT,
            normal_image=NT,
            roughness_image=RT,
            metalness_image=MT,
            tile_multiplier=TileMult,
            color_mask_out=colorMaskOut,
        )
        if cloned is not None:
            if not fresh_token:
                _ML_TEMPLATE_GROUP_CACHE[template_key] = cloned.name
            return cloned

        _ML_CACHE_STATS["template_group_builds"] += 1
        NG = new_tracked_datablock("node_groups", group_name, "ShaderNodeTree")
        NG["cp77_ml_template"] = mltemplate
        NG["cp77_ml_template_blueprint_version"] = _ML_CACHE_VERSION
        NG.interface.new_socket(
            name="Controls", socket_type="NodeSocketBundle", in_out="INPUT"
        )
        NG.interface.new_socket(
            name="Sample", socket_type="NodeSocketBundle", in_out="OUTPUT"
        )

        CTN = create_node(NG.nodes, "ShaderNodeTexImage", (0, 0), image=CT)
        CTN["cp77_multilayer_template_role"] = "color_texture"
        CTN.width = 300
        MTN = create_node(NG.nodes, "ShaderNodeTexImage", (0, -50), image=MT)
        MTN["cp77_multilayer_template_role"] = "metalness_texture"
        MTN.width = 300
        RTN = create_node(NG.nodes, "ShaderNodeTexImage", (0, -100), image=RT)
        RTN["cp77_multilayer_template_role"] = "roughness_texture"
        RTN.width = 300
        NTN = create_node(NG.nodes, "ShaderNodeTexImage", (0, -150), image=NT)
        NTN["cp77_multilayer_template_role"] = "normal_texture"
        NTN.width = 300

        TexCordN = create_node(NG.nodes, "ShaderNodeTexCoord", (-900, 50))
        combineOffUV = create_node(NG.nodes, "ShaderNodeCombineXYZ", (-650, -100))
        VecMathN = shader_nodes.vector_math(
            NG.nodes, NG.links, "MULTIPLY", location=(-650, -50), hide=True
        ).node
        MapN = create_node(NG.nodes, "ShaderNodeMapping", (-350, -50))

        TileMultN = create_node(NG.nodes, "ShaderNodeValue", (-650, 50))
        TileMultN["cp77_multilayer_template_role"] = "tile_multiplier"
        TileMultN.label = "Tile Multiplier"
        TileMultN.outputs["Value"].default_value = TileMult

        ColorRampOut = create_node(
            NG.nodes, "ShaderNodeValToRGB", (300, 300), label="Color Out"
        )
        ColorRampOut["cp77_multilayer_template_role"] = "color_ramp"
        ColorRampOut.inputs["Factor"].default_value = 1
        ColorRampOut.color_ramp.elements[0].position = 0.9999999 - colorMaskOut[0]
        ColorRampOut.color_ramp.elements[0].color = (
            colorMaskOut[1],
            colorMaskOut[1],
            colorMaskOut[1],
            1,
        )

        colorScaleMix = create_node(
            NG.nodes, "ShaderNodeMix", (550, 250), blend_type="MULTIPLY"
        )
        colorScaleMix["cp77_multilayer_template_role"] = "color_mix"
        colorScaleMix.data_type = "RGBA"
        shader_nodes.socket_by_identifier(
            colorScaleMix.inputs, "Factor_Float"
        ).default_value = colorMaskOut[1]
        colorScaleMix.hide = False

        normalVectorize = shader_nodes.vector_math(
            NG.nodes, NG.links, "MULTIPLY_ADD", location=(400, -150), hide=True
        ).node
        shader_nodes.socket_by_identifier(
            normalVectorize.inputs, "Vector_001"
        ).default_value = 2, 2, 0
        shader_nodes.socket_by_identifier(
            normalVectorize.inputs, "Vector_002"
        ).default_value = -1, -1, 0
        normalMultiply = shader_nodes.vector_math(
            NG.nodes, NG.links, "MULTIPLY", location=(650, -250), hide=True
        ).node

        GroupInN = create_node(NG.nodes, "NodeGroupInput", (-1200, 0))
        GroupInN["cp77_multilayer_template_role"] = "group_input"
        GroupInN["cp77_ml_template"] = mltemplate
        GroupInN.hide = False
        GroupOutN = create_node(NG.nodes, "NodeGroupOutput", (1100, 0))
        GroupOutN.hide = False

        controls = separate_bundle_node(
            NG,
            _TEMPLATE_CONTROL_BUNDLE_ITEMS,
            (-1000, -20),
            name="CP77 Template Controls Unpack",
            label="Template Controls",
        )
        controls["cp77_multilayer_template_role"] = "controls"
        sample = combine_bundle_node(
            NG,
            _TEMPLATE_SAMPLE_BUNDLE_ITEMS,
            (880, 0),
            name="CP77 Template Sample Pack",
            label="Template Sample",
        )
        sample["cp77_multilayer_template_role"] = "sample"

        NG.links.new(GroupInN.outputs["Controls"], controls.inputs["Bundle"])
        NG.links.new(
            controls.outputs["Color Scale"],
            shader_nodes.socket_by_identifier(colorScaleMix.inputs, "B_Color"),
        )
        NG.links.new(
            controls.outputs["Tile"],
            shader_nodes.socket_by_identifier(VecMathN.inputs, "Vector_001"),
        )
        NG.links.new(controls.outputs["Offset U"], combineOffUV.inputs["X"])
        NG.links.new(controls.outputs["Offset V"], combineOffUV.inputs["Y"])
        NG.links.new(
            controls.outputs["Normal Strength"],
            shader_nodes.socket_by_identifier(normalMultiply.inputs, "Vector_001"),
        )
        NG.links.new(TexCordN.outputs["UV"], MapN.inputs["Vector"])
        NG.links.new(VecMathN.outputs["Vector"], MapN.inputs["Scale"])
        NG.links.new(MapN.outputs["Vector"], CTN.inputs["Vector"])
        NG.links.new(MapN.outputs["Vector"], NTN.inputs["Vector"])
        NG.links.new(MapN.outputs["Vector"], RTN.inputs["Vector"])
        NG.links.new(MapN.outputs["Vector"], MTN.inputs["Vector"])
        NG.links.new(TileMultN.outputs["Value"], VecMathN.inputs["Vector"])
        NG.links.new(
            ColorRampOut.outputs["Color"],
            shader_nodes.socket_by_identifier(colorScaleMix.inputs, "Factor_Float"),
        )
        NG.links.new(
            CTN.outputs["Color"],
            shader_nodes.socket_by_identifier(colorScaleMix.inputs, "A_Color"),
        )
        NG.links.new(MTN.outputs["Color"], sample.inputs["Metalness"])
        NG.links.new(RTN.outputs["Color"], sample.inputs["Roughness"])
        NG.links.new(NTN.outputs["Color"], normalVectorize.inputs["Vector"])
        NG.links.new(normalVectorize.outputs["Vector"], normalMultiply.inputs["Vector"])
        NG.links.new(
            shader_nodes.socket_by_identifier(colorScaleMix.outputs, "Result_Color"),
            sample.inputs["Color"],
        )
        NG.links.new(normalMultiply.outputs["Vector"], sample.inputs["Normal"])
        NG.links.new(combineOffUV.outputs["Vector"], MapN.inputs["Location"])
        NG.links.new(sample.outputs["Bundle"], GroupOutN.inputs["Sample"])

        _register_template_blueprint(NG)
        if not fresh_token:
            _ML_TEMPLATE_GROUP_CACHE[template_key] = NG.name
        # Returning NG lets callers use the freshly built group directly
        # instead of re-scanning bpy.data.node_groups for it right after creation.
        return NG

    def _asset_index(self, root, extension):
        if not root:
            return None
        root = os.path.abspath(os.path.normpath(root))
        cache_key = (root, extension.lower())
        cached = _ASSET_INDEX_CACHE.get(cache_key)
        if cached is not None:
            return cached
        cached = build_asset_index(
            root,
            (extension,),
            policy=IndexPolicy.REUSE,
        )
        _ASSET_INDEX_CACHE[cache_key] = cached
        return cached

    def _indexed_asset_path(self, root, filepath):
        if not filepath:
            return None
        extension = os.path.splitext(filepath)[1].lower()
        if not extension:
            return None
        # A file at its expected path needs no index, and where paths ignore case the index (keyed by that same path)
        # cannot find one the direct lookup missed. Indexing a whole depot root costs seconds.
        if os.path.isfile(filepath):
            return normalize_local_path(filepath)
        if LOCAL_PATHS_IGNORE_CASE:
            return None
        index = self._asset_index(root, extension)
        return (
            index.resolve_expected(filepath, extension, warn=False)
            if index is not None
            else None
        )

    def _resolve_mask_layer_path(self, mlmaskpath, layer_index):
        cache_key = (
            self._context_key,
            _template_path_key(mlmaskpath),
            int(layer_index),
        )
        if cache_key in _MASK_LAYER_PATH_CACHE:
            _ML_CACHE_STATS["mask_path_hits"] += 1
            return _MASK_LAYER_PATH_CACHE[cache_key]

        _ML_CACHE_STATS["mask_path_misses"] += 1
        mask_stem = os.path.split(mlmaskpath)[-1:][0][:-7]
        mask_filename = f"{mask_stem}_{layer_index}.png"
        resolved_path = None
        for root in (self.ProjPath, self.BasePath):
            mask_dir = os.path.splitext(os.path.join(root, mlmaskpath))[0] + "_layers"
            resolved_path = self._indexed_asset_path(
                root, os.path.join(mask_dir, mask_filename)
            )
            if resolved_path:
                break
        _MASK_LAYER_PATH_CACHE[cache_key] = resolved_path
        return resolved_path

    def _load_mlsetup(self, setup_path):
        reference = setup_path if setup_path.endswith(".json") else setup_path + ".json"
        root, resource_key = _cached_resource_root(
            _MLSETUP_CACHE,
            "mlsetup",
            reference,
            self.BasePath,
            self.ProjPath,
        )
        layers = root.get("layers")
        if layers is None:
            layers = root.get("Layers")
        return _layer_specs(resource_key, layers)

    def _load_mltemplate(self, material_path):
        reference = (
            material_path
            if material_path.endswith(".json")
            else material_path + ".json"
        )
        root, resource_key = _cached_resource_root(
            _MLTEMPLATE_CACHE,
            "mltemplate",
            reference,
            self.BasePath,
            self.ProjPath,
        )
        fresh_runtime = bool(_FRESH_RUNTIME_TOKEN.get())
        override_table = None if fresh_runtime else _ML_OVERRIDE_CACHE.get(resource_key)
        if override_table is None:
            _ML_CACHE_STATS["override_misses"] += 1
            override_table = createOverrideTable(root)
            if not fresh_runtime:
                _ML_OVERRIDE_CACHE[resource_key] = override_table
        else:
            _ML_CACHE_STATS["override_hits"] += 1
        return root, override_table, resource_key

    def ensure_template_group(self, material_path):
        material_path = str(material_path or "")
        if not material_path:
            raise ValueError("A multilayer template path is required")
        material_norm = material_path.replace("\\", os.sep)
        template, override_table, resource_key = self._load_mltemplate(material_path)
        queue_override_palette(material_path, override_table)
        return self.createMLTemplateGroup(
            template,
            material_norm,
            resource_key,
        )

    def _prepare_layer_runtime(
        self,
        Mat,
        version_major,
        material,
        microblend_path,
    ):
        material_norm = material.replace("\\", os.sep)
        cache_key = (
            self._context_key,
            int(version_major),
            _template_path_key(material_norm),
            _template_path_key(microblend_path),
        )
        fresh_token = _FRESH_RUNTIME_TOKEN.get()
        if not fresh_token:
            cached = _PREPARED_LAYER_CACHE.get(cache_key)
            if cached is not None:
                group_name, override_table = cached
                node_group = bpy.data.node_groups.get(group_name)
                if node_group is not None:
                    _ML_CACHE_STATS["prepared_layer_hits"] += 1
                    return node_group, override_table
                _PREPARED_LAYER_CACHE.pop(cache_key, None)
                _ML_CACHE_STATS["prepared_layer_stale"] += 1

        _ML_CACHE_STATS["prepared_layer_misses"] += 1
        phase_started = time.perf_counter()
        microblend_image = None
        if microblend_path:
            microblend_image = imageFromRelPath(
                microblend_path,
                self.image_format,
                isNormal=True,
                DepotPath=self.BasePath,
                ProjPath=self.ProjPath,
            )
        _record_build_phase("layer_microblend", phase_started)

        phase_started = time.perf_counter()
        mltemplate, override_table, template_resource_key = self._load_mltemplate(
            material
        )
        queue_override_palette(material, override_table)
        base_material = self.createMLTemplateGroup(
            mltemplate,
            material_norm,
            template_resource_key,
        )
        _record_build_phase("layer_template", phase_started)

        phase_started = time.perf_counter()
        group_name = safe_layer_group_name(
            version_major,
            material_norm,
            microblend_path,
            self._context_key,
            base_material.name,
        )
        if fresh_token:
            group_name = _fresh_group_name(group_name, fresh_token, "layer")
        node_group = self._get_or_create_layer_node_tree(
            Mat,
            group_name,
            base_material,
            microblend_image,
        )
        _record_build_phase("layer_group", phase_started)
        if not fresh_token:
            _PREPARED_LAYER_CACHE[cache_key] = (
                node_group.name,
                override_table,
            )
        return node_group, override_table

    def _mask_layer_paths(self, mlmaskpath, layer_count):
        cache_key = (
            self._context_key,
            _template_path_key(mlmaskpath),
            int(layer_count),
        )
        cached = _MASK_SET_CACHE.get(cache_key)
        if cached is not None:
            _ML_CACHE_STATS["mask_set_hits"] += 1
            return cached

        _ML_CACHE_STATS["mask_set_misses"] += 1
        paths = tuple(
            self._resolve_mask_layer_path(mlmaskpath, layer_index + 1)
            for layer_index in range(layer_count)
        )
        _MASK_SET_CACHE[cache_key] = paths
        return paths

    def _configure_layer_tree_sockets(self, inputs):
        set_socket_range(inputs, "NormalStrength", 0, 10)
        set_socket_dimensions(inputs, "MetalLevelsIn", 2)
        set_socket_dimensions(inputs, "MetalLevelsOut", 2)
        set_socket_dimensions(inputs, "RoughLevelsIn", 2)
        set_socket_dimensions(inputs, "RoughLevelsOut", 2)
        set_socket_range(inputs, "MicroblendContrast", 0, 1)
        set_socket_range(inputs, "Opacity", 0, 1)

    def _configure_layer_group_inputs(
        self, layer_node, layer_index, values, override_table
    ):
        inputs = layer_node.inputs
        set_socket_default(inputs, "Mask", 1 if layer_index == 0 else 0)
        if apply_override(
            inputs,
            "ColorScale",
            values["colorScale"],
            override_table["ColorScale"],
            (1.0, 1.0, 1.0, 1),
        ):
            layer_node["colorScale"] = values["colorScale"]
        elif "colorScale" in layer_node:
            # A copy of another material's layer node.
            del layer_node["colorScale"]
        set_socket_default(inputs, "MatTile", float_or_default(values["MatTile"], 1))
        set_socket_default(inputs, "OffsetU", float_or_default(values["OffsetU"], 0))
        set_socket_default(inputs, "OffsetV", float_or_default(values["OffsetV"], 0))
        apply_override(
            inputs,
            "NormalStrength",
            values["normalStrength"],
            override_table["NormalStrength"],
            1,
        )
        set_socket_default(
            inputs,
            "MicroblendNormalStrength",
            float_or_default(values["microblendNormalStrength"], 1),
        )
        set_socket_default(
            inputs,
            "MicroblendContrast",
            float_or_default(values["MicroblendContrast"], 1),
        )
        set_socket_default(inputs, "MbTile", float_or_default(values["MbScale"], 1))
        set_socket_default(
            inputs,
            "MicroblendOffsetU",
            float_or_default(values["MicroblendOffsetU"], 0),
        )
        set_socket_default(
            inputs,
            "MicroblendOffsetV",
            float_or_default(values["MicroblendOffsetV"], 0),
        )
        set_socket_default(inputs, "Opacity", float_or_default(values["opacity"], 1))
        apply_override(
            inputs,
            "MetalLevelsIn",
            values["metalLevelsIn"],
            override_table["MetalLevelsIn"],
            (1, 0),
        )
        apply_override(
            inputs,
            "MetalLevelsOut",
            values["metalLevelsOut"],
            override_table["MetalLevelsOut"],
            (1, 0),
        )
        apply_override(
            inputs,
            "RoughLevelsIn",
            values["roughLevelsIn"],
            override_table["RoughLevelsIn"],
            (1, 0),
        )
        apply_override(
            inputs,
            "RoughLevelsOut",
            values["roughLevelsOut"],
            override_table["RoughLevelsOut"],
            (1, 0),
        )

    def _patch_layer_base_material_links(self, node_tree, BaseMat, roles):
        base_node = roles.get("base_material")
        template_controls = roles.get("template_controls")
        levels_stage = roles.get("levels_stage")
        required_nodes = (base_node, template_controls, levels_stage)
        if any(node is None for node in required_nodes):
            raise RuntimeError("Multilayer blueprint is missing required bundled nodes")

        base_node.node_tree = BaseMat
        controls_input = (
            base_node.inputs.get("Controls")
            if hasattr(base_node.inputs, "get")
            else None
        )
        sample_output = (
            base_node.outputs.get("Sample")
            if hasattr(base_node.outputs, "get")
            else None
        )
        if controls_input is None or sample_output is None:
            raise RuntimeError(
                "Multilayer base template has an incompatible bundle interface"
            )

        for link in tuple(node_tree.links):
            if link.from_node is base_node or link.to_node is base_node:
                node_tree.links.remove(link)

        node_tree.links.new(template_controls.outputs["Bundle"], controls_input)
        node_tree.links.new(sample_output, levels_stage.inputs["Sample"])

    def _clone_layer_node_tree(self, group_name, BaseMat, MBI):
        blueprint, exact_base = _layer_node_blueprint(BaseMat)
        if blueprint is None:
            return None

        clone = None
        try:
            clone = track_created_datablock("node_groups", blueprint.copy())
            clone.name = group_name
            clone["cp77_ml_layer_cache_version"] = _ML_CACHE_VERSION
            clone["cp77_ml_layer_blueprint_version"] = _ML_CACHE_VERSION
            roles = {}
            for node in clone.nodes:
                role = node.get("cp77_multilayer_role")
                if role in {
                    "base_material",
                    "template_controls",
                    "levels_stage",
                    "microblend",
                }:
                    roles.setdefault(role, node)
            if exact_base:
                _ML_CACHE_STATS["layer_group_base_clones"] += 1
            else:
                self._patch_layer_base_material_links(clone, BaseMat, roles)
                _ML_CACHE_STATS["layer_group_repatched_clones"] += 1
            microblend_node = roles.get("microblend")
            if microblend_node is None:
                raise RuntimeError(
                    "Multilayer blueprint is missing its microblend node"
                )
            microblend_node.image = MBI
            _register_layer_blueprint(BaseMat, clone)
            _ML_CACHE_STATS["layer_group_clones"] += 1
            return clone
        except Exception:
            debug_exception(
                _LOG,
                "Could not clone multilayer layer group %s; building it",
                group_name,
            )
            _ML_CACHE_STATS["layer_group_clone_failures"] += 1
            if clone is not None:
                try:
                    bpy.data.node_groups.remove(clone)
                except (ReferenceError, RuntimeError, TypeError):
                    pass
            return None

    def _get_or_create_layer_node_tree(self, Mat, group_name, BaseMat, MBI):
        fresh_token = _FRESH_RUNTIME_TOKEN.get()
        if not fresh_token:
            cached = _cached_node_group(_LAYER_NODE_TOPOLOGY_CACHE, group_name)
            if cached is not None:
                _register_layer_blueprint(BaseMat, cached)
                _ML_CACHE_STATS["layer_group_hits"] += 1
                return cached

            existing = bpy.data.node_groups.get(group_name)
            if (
                existing is not None
                and existing.get("cp77_ml_layer_cache_version") == _ML_CACHE_VERSION
            ):
                _LAYER_NODE_TOPOLOGY_CACHE[group_name] = existing.name
                _register_layer_blueprint(BaseMat, existing)
                _ML_CACHE_STATS["layer_group_hits"] += 1
                return existing

            cloned = self._clone_layer_node_tree(group_name, BaseMat, MBI)
            if cloned is not None:
                _LAYER_NODE_TOPOLOGY_CACHE[group_name] = cloned.name
                return cloned

        _ML_CACHE_STATS["layer_group_builds"] += 1
        NG = new_tracked_datablock("node_groups", group_name, "ShaderNodeTree")
        NG["cp77_ml_layer_cache_version"] = _ML_CACHE_VERSION
        NG["cp77_ml_layer_blueprint_version"] = _ML_CACHE_VERSION
        ioPanel = NG.interface.new_panel(name="Input/Output")
        ioPanel.default_closed = True
        overridesPanel = NG.interface.new_panel(name="Overrides")
        overridesPanel.default_closed = True
        levelsPanel = NG.interface.new_panel(name="Levels")
        levelsPanel.default_closed = True
        NG.interface.move_to_parent(
            item=levelsPanel, parent=overridesPanel, to_position=2
        )
        paramsPanel = NG.interface.new_panel(name="Parameters")
        NG.interface.new_socket(
            name="Mask", socket_type="NodeSocketFloat", parent=ioPanel, in_out="INPUT"
        )
        NG.interface.new_socket(
            name="ColorScale",
            socket_type="NodeSocketColor",
            parent=overridesPanel,
            in_out="INPUT",
        )
        NG.interface.new_socket(
            name="NormalStrength",
            socket_type="NodeSocketFloat",
            parent=overridesPanel,
            in_out="INPUT",
        )
        NG.interface.new_socket(
            name="MetalLevelsIn",
            socket_type="NodeSocketVector",
            parent=levelsPanel,
            in_out="INPUT",
        )
        NG.interface.new_socket(
            name="MetalLevelsOut",
            socket_type="NodeSocketVector",
            parent=levelsPanel,
            in_out="INPUT",
        )
        NG.interface.new_socket(
            name="RoughLevelsIn",
            socket_type="NodeSocketVector",
            parent=levelsPanel,
            in_out="INPUT",
        )
        NG.interface.new_socket(
            name="RoughLevelsOut",
            socket_type="NodeSocketVector",
            parent=levelsPanel,
            in_out="INPUT",
        )
        NG.interface.new_socket(
            name="MatTile",
            socket_type="NodeSocketFloat",
            parent=paramsPanel,
            in_out="INPUT",
        )
        NG.interface.new_socket(
            name="OffsetU",
            socket_type="NodeSocketFloat",
            parent=paramsPanel,
            in_out="INPUT",
        )
        NG.interface.new_socket(
            name="OffsetV",
            socket_type="NodeSocketFloat",
            parent=paramsPanel,
            in_out="INPUT",
        )
        NG.interface.new_socket(
            name="MicroblendNormalStrength",
            socket_type="NodeSocketFloat",
            parent=paramsPanel,
            in_out="INPUT",
        )
        NG.interface.new_socket(
            name="MicroblendContrast",
            socket_type="NodeSocketFloat",
            parent=paramsPanel,
            in_out="INPUT",
        )
        NG.interface.new_socket(
            name="MbTile",
            socket_type="NodeSocketFloat",
            parent=paramsPanel,
            in_out="INPUT",
        )
        NG.interface.new_socket(
            name="MicroblendOffsetU",
            socket_type="NodeSocketFloat",
            parent=paramsPanel,
            in_out="INPUT",
        )
        NG.interface.new_socket(
            name="MicroblendOffsetV",
            socket_type="NodeSocketFloat",
            parent=paramsPanel,
            in_out="INPUT",
        )
        NG.interface.new_socket(
            name="Opacity",
            socket_type="NodeSocketFloat",
            parent=paramsPanel,
            in_out="INPUT",
        )
        # The layer bundle is the canonical payload. Layer Mask remains exposed for
        # clear-coat layer-range evaluation without re-expanding all six channels.
        NG.interface.new_socket(
            name="Layer Mask",
            socket_type="NodeSocketFloat",
            parent=ioPanel,
            in_out="OUTPUT",
        )
        NG.interface.new_socket(
            name="Layer", socket_type="NodeSocketBundle", in_out="OUTPUT"
        )
        NG_inputs = get_inputs(NG)
        self._configure_layer_tree_sockets(NG_inputs)

        GroupInN = create_node(NG.nodes, "NodeGroupInput", (-2800, 100))
        GroupInN["cp77_multilayer_role"] = "group_input"
        GroupInN.hide = False
        GroupOutN = create_node(NG.nodes, "NodeGroupOutput", (200, 100))
        GroupOutN.hide = False

        template_controls = combine_bundle_node(
            NG,
            _TEMPLATE_CONTROL_BUNDLE_ITEMS,
            (-2500, 300),
            name="CP77 Template Controls Pack",
            label="Template Controls",
        )
        template_controls["cp77_multilayer_role"] = "template_controls"
        levels_controls = combine_bundle_node(
            NG,
            _LEVELS_CONTROL_BUNDLE_ITEMS,
            (-2500, 80),
            name="CP77 Levels Controls Pack",
            label="Levels Controls",
        )
        microblend_uv = combine_bundle_node(
            NG,
            _MICROBLEND_UV_BUNDLE_ITEMS,
            (-2500, -360),
            name="CP77 Microblend UV Pack",
            label="Microblend UV",
        )
        microblend_controls = combine_bundle_node(
            NG,
            _MICROBLEND_CONTROL_BUNDLE_ITEMS,
            (-2500, -650),
            name="CP77 Microblend Controls Pack",
            label="Microblend Controls",
        )

        NG.links.new(
            GroupInN.outputs["ColorScale"], template_controls.inputs["Color Scale"]
        )
        NG.links.new(
            GroupInN.outputs["NormalStrength"],
            template_controls.inputs["Normal Strength"],
        )
        NG.links.new(GroupInN.outputs["MatTile"], template_controls.inputs["Tile"])
        NG.links.new(GroupInN.outputs["OffsetU"], template_controls.inputs["Offset U"])
        NG.links.new(GroupInN.outputs["OffsetV"], template_controls.inputs["Offset V"])
        NG.links.new(
            GroupInN.outputs["MetalLevelsIn"], levels_controls.inputs["Metal In"]
        )
        NG.links.new(
            GroupInN.outputs["MetalLevelsOut"], levels_controls.inputs["Metal Out"]
        )
        NG.links.new(
            GroupInN.outputs["RoughLevelsIn"], levels_controls.inputs["Rough In"]
        )
        NG.links.new(
            GroupInN.outputs["RoughLevelsOut"], levels_controls.inputs["Rough Out"]
        )
        NG.links.new(GroupInN.outputs["MbTile"], microblend_uv.inputs["Tile"])
        NG.links.new(
            GroupInN.outputs["MicroblendOffsetU"], microblend_uv.inputs["Offset U"]
        )
        NG.links.new(
            GroupInN.outputs["MicroblendOffsetV"], microblend_uv.inputs["Offset V"]
        )
        NG.links.new(GroupInN.outputs["Mask"], microblend_controls.inputs["Mask"])
        NG.links.new(
            GroupInN.outputs["MicroblendNormalStrength"],
            microblend_controls.inputs["Normal Strength"],
        )
        NG.links.new(
            GroupInN.outputs["MicroblendContrast"],
            microblend_controls.inputs["Contrast"],
        )
        NG.links.new(GroupInN.outputs["Opacity"], microblend_controls.inputs["Opacity"])

        BMN = create_node(NG.nodes, "ShaderNodeGroup", (-2050, 280))
        BMN["cp77_multilayer_role"] = "base_material"
        BMN.width = 300
        BMN.hide = False
        BMN.node_tree = BaseMat
        NG.links.new(template_controls.outputs["Bundle"], BMN.inputs["Controls"])

        levels_stage = create_node(NG.nodes, "ShaderNodeGroup", (-1550, 260))
        levels_stage["cp77_multilayer_role"] = "levels_stage"
        levels_stage.name = "CP77 Multilayer Levels"
        levels_stage.label = "Metal / Rough Levels"
        levels_stage.node_tree = layer_levels_node_group()
        NG.links.new(BMN.outputs["Sample"], levels_stage.inputs["Sample"])
        NG.links.new(levels_controls.outputs["Bundle"], levels_stage.inputs["Controls"])

        adjusted_sample = separate_bundle_node(
            NG,
            _TEMPLATE_SAMPLE_BUNDLE_ITEMS,
            (-850, 220),
            name="CP77 Adjusted Sample Unpack",
            label="Adjusted Sample",
        )
        NG.links.new(levels_stage.outputs["Sample"], adjusted_sample.inputs["Bundle"])

        MBN = create_node(
            NG.nodes, "ShaderNodeTexImage", (-1500, -650), image=MBI, label="Microblend"
        )
        MBN["cp77_multilayer_role"] = "microblend"
        MBN.hide = False
        MBN.width = 300
        MBTexCord = create_node(NG.nodes, "ShaderNodeTexCoord", (-2250, -500))
        microblend_uv_unpack = separate_bundle_node(
            NG,
            _MICROBLEND_UV_BUNDLE_ITEMS,
            (-2100, -380),
            name="CP77 Microblend UV Unpack",
            label="Microblend UV",
        )
        MBUVCombine = create_node(NG.nodes, "ShaderNodeCombineXYZ", (-1900, -480))
        MBMapping = create_node(NG.nodes, "ShaderNodeMapping", (-1725, -570))
        NG.links.new(
            microblend_uv.outputs["Bundle"], microblend_uv_unpack.inputs["Bundle"]
        )
        NG.links.new(MBTexCord.outputs["UV"], MBMapping.inputs["Vector"])
        NG.links.new(microblend_uv_unpack.outputs["Offset U"], MBUVCombine.inputs["X"])
        NG.links.new(microblend_uv_unpack.outputs["Offset V"], MBUVCombine.inputs["Y"])
        NG.links.new(MBUVCombine.outputs["Vector"], MBMapping.inputs["Location"])
        NG.links.new(microblend_uv_unpack.outputs["Tile"], MBMapping.inputs["Scale"])
        NG.links.new(MBMapping.outputs["Vector"], MBN.inputs["Vector"])

        microblend_sample = combine_bundle_node(
            NG,
            _MICROBLEND_SAMPLE_BUNDLE_ITEMS,
            (-1180, -590),
            name="CP77 Microblend Sample Pack",
            label="Microblend Sample",
        )
        NG.links.new(MBN.outputs["Color"], microblend_sample.inputs["Color"])
        NG.links.new(MBN.outputs["Alpha"], microblend_sample.inputs["Alpha"])

        mask_mixergroup = create_node(NG.nodes, "ShaderNodeGroup", (-900, -520))
        mask_mixergroup["cp77_multilayer_role"] = "mask_mixer"
        mask_mixergroup.name = "CP77 Multilayer Mask Mixer"
        mask_mixergroup.label = "Mask / Microblend"
        mask_mixergroup.node_tree = mask_mixer_node_group()
        mask_mixergroup.width = 280
        NG.links.new(
            microblend_controls.outputs["Bundle"], mask_mixergroup.inputs["Controls"]
        )
        NG.links.new(
            microblend_sample.outputs["Bundle"], mask_mixergroup.inputs["Sample"]
        )

        mask_result = separate_bundle_node(
            NG,
            _MASK_RESULT_BUNDLE_ITEMS,
            (-580, -440),
            name="CP77 Mask Result Unpack",
            label="Mask Result",
        )
        NG.links.new(mask_mixergroup.outputs["Result"], mask_result.inputs["Bundle"])

        layer_bundle = combine_bundle_node(
            NG,
            LAYER_BUNDLE_ITEMS,
            (-260, 180),
            name="CP77 Layer Payload Pack",
            label="Layer Payload",
        )
        NG.links.new(adjusted_sample.outputs["Color"], layer_bundle.inputs["Color"])
        NG.links.new(
            adjusted_sample.outputs["Metalness"], layer_bundle.inputs["Metalness"]
        )
        NG.links.new(
            adjusted_sample.outputs["Roughness"], layer_bundle.inputs["Roughness"]
        )
        NG.links.new(adjusted_sample.outputs["Normal"], layer_bundle.inputs["Normal"])
        NG.links.new(
            mask_result.outputs["Microblend"], layer_bundle.inputs["Microblend"]
        )
        NG.links.new(
            mask_result.outputs["Layer Mask"], layer_bundle.inputs["Layer Mask"]
        )
        NG.links.new(layer_bundle.outputs["Bundle"], GroupOutN.inputs["Layer"])
        NG.links.new(mask_result.outputs["Layer Mask"], GroupOutN.inputs["Layer Mask"])
        if not fresh_token:
            _LAYER_NODE_TOPOLOGY_CACHE[group_name] = NG.name
            _register_layer_blueprint(BaseMat, NG)
        return NG

    def configure_multilayer_surface(self, Mat, Data, context):
        return None

    def apply_surface_values(self, Mat, Data, slots, layer_count):
        """Write the values configure_multilayer_surface gave a material into a copy of one of the same shape"""
        return

    def surface_source_data(self, Data):
        return Data

    def surface_structure(self, Data, layer_count):
        """What the surface step's graph depends on besides the layers, their masks and the global normal"""
        return

    def _shares_structure(self):
        """Whether this class's surface step has a value pass (a subclass building its own surface may not)"""

        def owner(name):
            return next(cls for cls in type(self).__mro__ if name in cls.__dict__)

        surface = owner("configure_multilayer_surface")
        return (
            all(
                owner(name) is Multilayered
                for name in ("create", "setupMaterial", "_configure_layer_group_inputs")
            )
            and owner("apply_surface_values") is surface
            and owner("surface_structure") is surface
        )

    def _mask_images(self, mlmaskpath, layer_count):
        return tuple(
            imageFromPath(path, self.image_format, isNormal=True) if path else None
            for path in self._mask_layer_paths(mlmaskpath, max(layer_count - 1, 0))
        )

    def _global_normal_image(self, Data):
        """The image the surface's global normal samples, or None when the surface has none"""
        if not Data.get("BakedNormal", Data.get("GlobalNormal")):
            return None
        return _source_global_normal_image(self, self.surface_source_data(Data))

    def structure_key(self, Data):
        # The build reads only the setup, the mask set and the global normal (with its UV and intensity values), plus
        # whatever the surface step reads; of those, the layer count, which masks and normal load, and the surface's
        # own structure shape the graph.
        setup_path = Data.get("MultilayerSetup")
        if (
            not self._shares_structure()
            or not setup_path
            or "MultilayerMask" not in Data
        ):
            return None
        layer_count = len(self._load_mlsetup(setup_path))
        return (
            layer_count,
            tuple(
                image is not None
                for image in self._mask_images(Data["MultilayerMask"], layer_count)
            ),
            self._global_normal_image(Data) is not None,
            self.surface_structure(self.surface_source_data(Data), layer_count),
        )

    def _write_layer_node(
        self, layer_node, layer_index, material, values, node_group, override_table
    ):
        if layer_node.node_tree is not node_group:
            layer_node.node_tree = node_group
        layer_node["cp77_ml_template"] = material
        self._configure_layer_group_inputs(
            layer_node, layer_index, values, override_table
        )

    def _prepared_layers(self, Mat, layer_specs):
        version_major = bpy.app.version[0]
        prepared = []
        for material, microblend, values in layer_specs:
            microblend_path = (
                "" if not microblend or microblend == "null" else microblend
            )
            node_group, override_table = self._prepare_layer_runtime(
                Mat, version_major, material, microblend_path
            )
            prepared.append((material, values, node_group, override_table))
        return prepared

    def apply_structure_values(self, Data, Mat, slots):
        setup_path = Data["MultilayerSetup"]
        Mat["MLSetup"] = setup_path
        layer_specs = self._load_mlsetup(setup_path)
        prepared_layers = self._prepared_layers(Mat, layer_specs)
        mask_images = self._mask_images(Data["MultilayerMask"], len(layer_specs))
        nodes = Mat.node_tree.nodes
        for layer_index, (material, values, node_group, override_table) in enumerate(
            prepared_layers
        ):
            self._write_layer_node(
                nodes[slots[f"layer_{layer_index}"]],
                layer_index,
                material,
                values,
                node_group,
                override_table,
            )
        sync_hidden_layer_links(Mat.node_tree, nodes[slots["root"]])
        for layer_index, image in enumerate(mask_images):
            mask_node = (
                nodes[slots[f"mask_{layer_index}"]] if image is not None else None
            )
            if mask_node is not None and mask_node.image is not image:
                mask_node.image = image
        source_data = self.surface_source_data(Data)
        image = self._global_normal_image(Data)
        if image is not None:
            parts = {
                part: nodes[slots[f"global_normal_{part}"]]
                for part in _GLOBAL_NORMAL_PARTS
            }
            _write_global_normal_values(parts, source_data, image)
        self.apply_surface_values(Mat, source_data, slots, len(layer_specs))

    def setupMaterial(
        self,
        Mat,
        LayerName,
        LayerCount,
        mlmaskpath,
        normalimgpath,
        *,
        source_data=None,
        mask_paths=None,
        mask_images=None,
    ):
        phase_started = time.perf_counter()
        CurMat = Mat.node_tree
        node_lookup = {n.name: n for n in CurMat.nodes}

        orig_pbsdf = shader_nodes.principled_bsdf(CurMat.nodes)

        ml_surface = ml_surface_node_group()
        ml_surface.color_tag = "SHADER"
        ml_root = CurMat.nodes.new("ShaderNodeGroup")
        ml_root.name = "Multilayer Surface 3.0.0"
        ml_root["cp77_material_tools_role"] = "multilayer_root"
        ml_root.location = (-120, 120)
        ml_root.node_tree = ml_surface
        ml_root.show_options = False

        surface_channels = create_node(CurMat.nodes, "NodeSeparateBundle", (120, 120))
        surface_channels.name = "CP77 Multilayer Surface Channels"
        surface_channels.label = "Surface Channels"
        surface_channels.hide = False
        add_bundle_items(surface_channels, _SURFACE_BUNDLE_ITEMS)
        CurMat.links.new(ml_root.outputs["Surface"], surface_channels.inputs["Bundle"])

        principled = orig_pbsdf
        if principled is None:
            principled = create_node(
                CurMat.nodes,
                "ShaderNodeBsdfPrincipled",
                (360, 120),
            )
        else:
            principled.hide = True
            principled.location = (360, 120)
        principled.name = "CP77 Multilayer Principled"
        principled.label = "CP77 Multilayer Surface"
        base_color = find_input(principled, "Base Color")
        metallic = find_input(principled, "Metallic")
        roughness = find_input(principled, "Roughness")
        normal = find_input(principled, "Normal")
        if base_color is not None:
            CurMat.links.new(surface_channels.outputs["Base Color"], base_color)
        if metallic is not None:
            CurMat.links.new(surface_channels.outputs["Metallic"], metallic)
        if roughness is not None:
            CurMat.links.new(surface_channels.outputs["Roughness"], roughness)
        if normal is not None:
            CurMat.links.new(surface_channels.outputs["Normal"], normal)

        material_output = shader_nodes.material_output(CurMat.nodes)
        if material_output is None:
            material_output = create_node(
                CurMat.nodes, "ShaderNodeOutputMaterial", (600, 120)
            )
        surface_input = material_output.inputs["Surface"]
        existing_surface_link = next(
            (
                link
                for link in (getattr(surface_input, "links", ()) or ())
                if getattr(link, "from_node", None) == principled
            ),
            None,
        )
        if existing_surface_link is None:
            CurMat.links.new(principled.outputs["BSDF"], surface_input)
        _record_build_phase("surface_shell", phase_started)

        phase_started = time.perf_counter()
        if mask_paths is None:
            mask_paths = self._mask_layer_paths(mlmaskpath, max(LayerCount - 1, 0))
        if mask_images is None:
            mask_images = tuple(
                imageFromPath(path, self.image_format, isNormal=True) if path else None
                for path in mask_paths
            )

        layer_nodes = [None] * LayerCount
        mask_nodes = [None] * LayerCount
        for x in range(LayerCount):
            layer = node_lookup.get("Mat_Mod_Layer_" + str(x))
            if layer is not None:
                layer_nodes[x] = layer
                if x <= 19:
                    CurMat.links.new(
                        layer.outputs["Layer"], ml_root.inputs[f"Layer {x + 1}"]
                    )

            mask_image = mask_images[x] if x < len(mask_images) else None
            mask_node = None
            if mask_image:
                mask_node = create_node(
                    CurMat.nodes,
                    "ShaderNodeTexImage",
                    (-1200, -400 * x),
                    hide=False,
                    image=mask_image,
                )
                mask_node.width = 300
                self.structure_slots[f"mask_{x}"] = mask_node.name
            mask_nodes[x] = mask_node

            if mask_node is not None and x + 1 < LayerCount:
                next_layer = node_lookup.get("Mat_Mod_Layer_" + str(x + 1))
                if next_layer is not None:
                    CurMat.links.new(
                        mask_node.outputs["Color"], next_layer.inputs["Mask"]
                    )
        sync_hidden_layer_links(CurMat, ml_root)
        self.structure_slots["root"] = ml_root.name
        _record_build_phase("surface_masks", phase_started)

        phase_started = time.perf_counter()
        global_normal = None
        if normalimgpath:
            global_normal = _create_source_global_normal(
                self,
                CurMat,
                source_data
                if isinstance(source_data, dict)
                else {"GlobalNormal": normalimgpath},
            )
            if global_normal is not None:
                CurMat.links.new(global_normal["encoded"], ml_root.inputs["Normal Map"])
                for part in _GLOBAL_NORMAL_PARTS:
                    self.structure_slots[f"global_normal_{part}"] = global_normal[
                        part
                    ].name
        _record_build_phase("surface_global_normal", phase_started)

        phase_started = time.perf_counter()
        self.configure_multilayer_surface(
            Mat,
            source_data if isinstance(source_data, dict) else {},
            {
                "tree": CurMat,
                "root": ml_root,
                "principled": principled,
                "material_output": material_output,
                "layer_nodes": tuple(layer_nodes),
                "mask_nodes": tuple(mask_nodes),
                "layer_count": LayerCount,
                "global_normal": global_normal,
                "slots": self.structure_slots,
            },
        )
        _record_build_phase("surface_variant", phase_started)

    def create(self, Data, Mat):
        _ML_BUILD_PERF["builds"] += 1
        setup_path = Data["MultilayerSetup"]
        Mat["MLSetup"] = setup_path

        phase_started = time.perf_counter()
        layer_specs = self._load_mlsetup(setup_path)
        _record_build_phase("setup_load", phase_started)

        layer_count = len(layer_specs)
        CurMat = Mat.node_tree
        file_name = os.path.basename(setup_path.replace("\\", os.sep))[:-8]
        self.structure_slots = {}

        phase_started = time.perf_counter()
        prepared_layers = self._prepared_layers(Mat, layer_specs)
        _record_build_phase("layer_prepare", phase_started)

        layer_normal = Data.get("BakedNormal", Data.get("GlobalNormal"))
        phase_started = time.perf_counter()
        mask_paths = self._mask_layer_paths(
            Data["MultilayerMask"],
            max(layer_count - 1, 0),
        )
        _record_build_phase("mask_resolve", phase_started)

        phase_started = time.perf_counter()
        mask_images = tuple(
            imageFromPath(path, self.image_format, isNormal=True) if path else None
            for path in mask_paths
        )
        _record_build_phase("mask_images", phase_started)

        phase_started = time.perf_counter()
        for layer_index, (
            material,
            values,
            node_group,
            override_table,
        ) in enumerate(prepared_layers):
            LayerGroupN = create_node(
                CurMat.nodes,
                "ShaderNodeGroup",
                (-800, 450 - 400 * layer_index),
                False,
            )
            LayerGroupN.width = 400
            LayerGroupN.name = "Mat_Mod_Layer_" + str(layer_index)
            LayerGroupN["cp77_material_tools_role"] = "multilayer_layer"
            self._write_layer_node(
                LayerGroupN, layer_index, material, values, node_group, override_table
            )
            self.structure_slots[f"layer_{layer_index}"] = LayerGroupN.name
        _record_build_phase("layer_nodes", phase_started)

        source_data = self.surface_source_data(Data)

        phase_started = time.perf_counter()
        self.setupMaterial(
            Mat,
            file_name + "_Layer_",
            layer_count,
            Data["MultilayerMask"],
            layer_normal,
            source_data=source_data,
            mask_paths=mask_paths,
            mask_images=mask_images,
        )
        _record_build_phase("surface_setup", phase_started)


used_params = [
    "GlobalNormal",
    "MultilayerMask",
    "MultilayerSetup",
    "GlobalNormalIntensity",
    "GlobalNormalUVScale",
    "GlobalNormalUVBias",
    "UseOldVertexFormat",
    "UVGenScaleOffset",
    "MaskAtlas",
    "MaskTiles",
    "Layers",
    "LayersStartIndex",
    "SurfaceTexAspectRatio",
    "MaskToTileScale",
    "MaskTileSize",
    "MaskAtlasDims",
    "MaskBaseResolution",
    "SetupLayerMask",
    "Opacity",
    "BakedNormal",
]


_CACHE_PARAMETERS = frozenset(used_params)


def material_cache_identity(raw_material):
    return filtered_material_data_identity(raw_material, _CACHE_PARAMETERS)
