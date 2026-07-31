import copy
import os

import bpy
import numpy as np

from ..common.atomic import atomic_write_json
from ...materials.blender.multilayer import (
    _layer_nodes,
    _layer_template_path,
    _load_rooted_json,
    _multilayer_root,
    _report_override,
    _role_node,
    createOverrideTable,
)

# JATO: prefix is never exposed in the UI but it's an interesting idea - keeping for now
# When saving a local copy of a mltemplate the prefix below will be used, use '' to get original names.


prefix = ''


def prefix_mat(MLTemplate):
    b, m, a = MLTemplate.partition(os.path.basename(MLTemplate))
    return b + prefix + m


# JATO: this function is used to get the microblend path. but it's possible to not have textures in the base folders
# TODO see if we can reliably get the relative path if it doesn't include "base\\"
def make_rel(filepath):
    before, mid, after = filepath.partition('base\\')
    return mid + after


def matchOverride(self, OverrideTable, key, layer, json_layer, jsonkey, nodevalue, matchTolerance):
    match = None
    match_error = float("inf")
    try:
        target = np.asarray(nodevalue, dtype=float)
    except (TypeError, ValueError):
        _report_override(self, "WARNING", f"{key} in Layer {layer} has an invalid node value.")
        return False
    for name, override_value in OverrideTable.get(key, {}).items():
        try:
            candidate = np.asarray(override_value, dtype=float)
        except (TypeError, ValueError):
            continue
        if candidate.shape != target.shape:
            continue
        error = float(np.sum(np.abs(candidate - target)))
        if error < matchTolerance and error < match_error:
            match = name
            match_error = error
    if match is None:
        _report_override(
            self,
            "WARNING",
            f"{key} in Layer {layer} was not exported because a matching override was not found.",
        )
        return False
    json_layer[jsonkey]["$value"] = match
    return True


def _default_ml_layer():
    return {
        "$type": "Multilayer_Layer",
        "colorScale": {"$type": "CName", "$storage": "string", "$value": "null_null"},
        "material": {
            "DepotPath": {
                "$type": "ResourcePath",
                "$storage": "string",
                "$value": "engine\\materials\\defaults\\multilayer_default.mltemplate",
            },
            "Flags": "Default",
        },
        "matTile": 10.1,
        "mbTile": 6.0,
        "metalLevelsIn": {"$type": "CName", "$storage": "string", "$value": "null"},
        "metalLevelsOut": {"$type": "CName", "$storage": "string", "$value": "null"},
        "microblend": {
            "DepotPath": {
                "$type": "ResourcePath",
                "$storage": "string",
                "$value": "base\\surfaces\\microblends\\default.xbm",
            },
            "Flags": "Default",
        },
        "microblendContrast": 0.5,
        "microblendNormalStrength": 1.0,
        "microblendOffsetU": 0.0,
        "microblendOffsetV": 0.0,
        "normalStrength": {"$type": "CName", "$storage": "string", "$value": "null"},
        "offsetU": 0.0,
        "offsetV": 0.0,
        "opacity": 0.0,
        "overrides": {"$type": "CName", "$storage": "string", "$value": "None"},
        "roughLevelsIn": {"$type": "CName", "$storage": "string", "$value": "null"},
        "roughLevelsOut": {"$type": "CName", "$storage": "string", "$value": "null"},
    }


def _required_layer_socket(layer, name):
    inputs = getattr(layer, "inputs", None)
    socket = inputs.get(name) if inputs is not None else None
    if socket is None:
        raise KeyError(f"Layer node {getattr(layer, 'name', '<unnamed>')} is missing {name}")
    return socket


def _microblend_path(layer):
    layer_tree = getattr(layer, "node_tree", None)
    if layer_tree is None:
        return ""
    node = _role_node(getattr(layer_tree, "nodes", None), "microblend", "Image Texture")
    image = getattr(node, "image", None) if node is not None else None
    filepath = getattr(image, "filepath", "") if image is not None else ""
    if not filepath:
        return ""
    absolute = bpy.path.abspath(filepath)
    return os.path.splitext(absolute)[0] + ".xbm"


def _best_color_override(override_table, color_value, tolerance):
    try:
        target = np.asarray(color_value, dtype=float)
    except (TypeError, ValueError):
        return None
    best_name = None
    best_error = float("inf")
    for name, override_value in override_table.get("ColorScale", {}).items():
        try:
            candidate = np.asarray(override_value, dtype=float)
        except (TypeError, ValueError):
            continue
        if candidate.shape != target.shape:
            continue
        error = float(np.sum(np.abs(candidate - target)))
        if error < tolerance and error < best_error:
            best_name = name
            best_error = error
    return best_name


def cp77_mlsetup_export(self, context, mlsetuppath, write_mltemplate):
    active_object = getattr(context, "active_object", None)
    active_material = getattr(active_object, "active_material", None) if active_object is not None else None
    node_tree = getattr(active_material, "node_tree", None) if active_material is not None else None
    if active_material is None or node_tree is None:
        _report_override(self, "ERROR", "Select a mesh with an editable multilayer material.")
        return {"CANCELLED"}
    setup_path = active_material.get("MLSetup")
    if not setup_path:
        _report_override(self, "ERROR", "Multilayered setup not found within selected material.")
        return {"CANCELLED"}
    project_path = active_material.get("ProjPath")
    depot_path = active_material.get("DepotPath")
    try:
        mlsetup = _load_rooted_json(str(setup_path) + ".json", project_path, depot_path)
        json_layers = mlsetup["Data"]["RootChunk"]["layers"]
    except (FileNotFoundError, KeyError, TypeError, ValueError) as error:
        _report_override(self, "ERROR", f"Could not load {setup_path}: {error}")
        return {"CANCELLED"}
    root = _multilayer_root(node_tree.nodes)
    if root is None:
        _report_override(self, "ERROR", "Multilayered shader node not found within selected material.")
        return {"CANCELLED"}
    linked = {
        index: layer
        for index, layer in _layer_nodes(node_tree.nodes, root, 20, False)
    }
    if not linked:
        _report_override(self, "ERROR", "No linked multilayer layers were found.")
        return {"CANCELLED"}
    layer_count = max(linked) + 1
    while len(json_layers) < layer_count:
        json_layers.append(_default_ml_layer())
    del json_layers[layer_count:]
    prefixed = set()
    tolerance = 0.00001

    for index in range(layer_count):
        layer_number = index + 1
        layer = linked.get(index)
        if layer is None:
            json_layers[index] = _default_ml_layer()
            continue
        json_layer = json_layers[index]
        try:
            template_path = _layer_template_path(layer)
            if not template_path:
                raise KeyError("MLTemplate metadata")
            values = {
                "matTile": _required_layer_socket(layer, "MatTile").default_value,
                "mbTile": _required_layer_socket(layer, "MbTile").default_value,
                "microblendNormalStrength": _required_layer_socket(layer, "MicroblendNormalStrength").default_value,
                "microblendContrast": _required_layer_socket(layer, "MicroblendContrast").default_value,
                "offsetU": _required_layer_socket(layer, "OffsetU").default_value,
                "offsetV": _required_layer_socket(layer, "OffsetV").default_value,
                "microblendOffsetU": _required_layer_socket(layer, "MicroblendOffsetU").default_value,
                "microblendOffsetV": _required_layer_socket(layer, "MicroblendOffsetV").default_value,
                "opacity": _required_layer_socket(layer, "Opacity").default_value,
            }
            color_scale = tuple(_required_layer_socket(layer, "ColorScale").default_value)
            normal_strength = _required_layer_socket(layer, "NormalStrength").default_value
            metal_in = tuple(_required_layer_socket(layer, "MetalLevelsIn").default_value)
            metal_out = tuple(_required_layer_socket(layer, "MetalLevelsOut").default_value)
            rough_in = tuple(_required_layer_socket(layer, "RoughLevelsIn").default_value)
            rough_out = tuple(_required_layer_socket(layer, "RoughLevelsOut").default_value)
            microblend = _microblend_path(layer)
        except (AttributeError, KeyError, ReferenceError, TypeError, ValueError) as error:
            _report_override(self, "ERROR", f"Layer {layer_number} has an incompatible node schema: {error}")
            return {"CANCELLED"}

        json_layer.update(values)
        if microblend:
            json_layer["microblend"]["DepotPath"]["$value"] = make_rel(microblend)
        export_template_path = prefix_mat(template_path) if template_path in prefixed else template_path
        json_layer["material"]["DepotPath"]["$value"] = export_template_path
        try:
            template_json = _load_rooted_json(template_path + ".json", project_path, depot_path)
            template_data = template_json["Data"]["RootChunk"]
            override_table = createOverrideTable(template_data)
        except (FileNotFoundError, KeyError, TypeError, ValueError) as error:
            _report_override(self, "ERROR", f"Layer {layer_number} template could not be loaded: {error}")
            return {"CANCELLED"}

        color_match = _best_color_override(override_table, color_scale, tolerance)
        if color_match is not None:
            json_layer["colorScale"]["$value"] = color_match
        elif write_mltemplate:
            overrides = template_data.get("overrides", {}).get("colorScale", [])
            if not overrides:
                _report_override(self, "ERROR", f"Layer {layer_number} template has no ColorScale override schema.")
                return {"CANCELLED"}
            entry = copy.deepcopy(overrides[0])
            index_value = 0
            name = f"000000_{index_value:06d}"
            while name in override_table.get("ColorScale", {}):
                index_value += 1
                name = f"000000_{index_value:06d}"
            entry["n"]["$value"] = name
            elements = entry["v"]["Elements"]
            for component in range(min(3, len(elements), len(color_scale))):
                elements[component] = color_scale[component]
            overrides.insert(0, entry)
            json_layer["colorScale"]["$value"] = name
            if os.path.basename(template_path)[:len(prefix)] == prefix:
                output_template = template_path
            else:
                output_template = prefix_mat(template_path)
                json_layer["material"]["DepotPath"]["$value"] = output_template
                prefixed.add(template_path)
            atomic_write_json(os.path.join(project_path, output_template) + ".json", template_json, indent=2)
        else:
            _report_override(self, "WARNING", f"ColorScale in Layer {layer_number} has no matching override.")

        matchOverride(self, override_table, "NormalStrength", layer_number, json_layer, "normalStrength", normal_strength, tolerance)
        matchOverride(self, override_table, "MetalLevelsIn", layer_number, json_layer, "metalLevelsIn", metal_in, tolerance)
        matchOverride(self, override_table, "MetalLevelsOut", layer_number, json_layer, "metalLevelsOut", metal_out, tolerance)
        matchOverride(self, override_table, "RoughLevelsIn", layer_number, json_layer, "roughLevelsIn", rough_in, tolerance)
        matchOverride(self, override_table, "RoughLevelsOut", layer_number, json_layer, "roughLevelsOut", rough_out, tolerance)

    atomic_write_json(mlsetuppath, mlsetup, indent=2)
    _report_override(self, "INFO", f"Exported MLSETUP from {active_material.name} on {active_object.name}")
    return {"FINISHED"}


