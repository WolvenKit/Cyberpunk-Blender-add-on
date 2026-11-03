import copy
import json
import ntpath
import os

import bpy
import numpy as np

from ...assetio.atomic import atomic_write_many
from ...assetio.paths import strip_json_suffix
from ...assetio.resources import MULTILAYER_DEFAULT_SETUP
from ...assetio.values import cname_entry, resource_path_entry
from ...blender.operator_results import OperationResult
from ...core.log import get_logger, log_once
from ...materials.blender.multilayer import (
    _layer_template_path,
    _load_rooted_json,
    _role_node,
    layer_nodes,
    multilayer_root,
)
from ...materials.blender.nodes import createOverrideTable
from .project_paths import project_raw_file, source_raw_relative

_LOG = get_logger(__name__)

prefix = ""


_OVERRIDE_SPECS = (
    ("ColorScale", "colorScale", 3),
    ("NormalStrength", "normalStrength", 1),
    ("MetalLevelsIn", "metalLevelsIn", 2),
    ("MetalLevelsOut", "metalLevelsOut", 2),
    ("RoughLevelsIn", "roughLevelsIn", 2),
    ("RoughLevelsOut", "roughLevelsOut", 2),
)


def prefix_mat(mltemplate):
    value = str(mltemplate or "").replace("/", "\\")
    directory, name = ntpath.split(value)
    output_name = prefix + name
    return ntpath.join(directory, output_name) if directory else output_name


def make_rel(filepath):
    normalized = str(filepath or "").replace("/", "\\")
    marker = "base\\"
    index = normalized.casefold().find(marker)
    return normalized[index:] if index >= 0 else normalized


def _numeric_components(value, dimensions):
    try:
        values = np.asarray(value, dtype=float).reshape(-1)
    except (TypeError, ValueError):
        return None
    if values.size < dimensions:
        return None
    return values[:dimensions]


def _find_override_name(
    override_table, key, value, dimensions, tolerance, preferred=None
):
    """The override of key closest to value within tolerance"""
    target = _numeric_components(value, dimensions)
    if target is None:
        return None
    overrides = override_table.get(key, {})
    if preferred in overrides:
        candidate = _numeric_components(overrides[preferred], dimensions)
        if (
            candidate is not None
            and float(np.sum(np.abs(candidate - target))) <= tolerance
        ):
            return preferred
    best_name = None
    best_error = float("inf")
    for name, override_value in overrides.items():
        candidate = _numeric_components(override_value, dimensions)
        if candidate is None:
            continue
        error = float(np.sum(np.abs(candidate - target)))
        if error <= tolerance and error < best_error:
            best_name = name
            best_error = error
    return best_name


def _default_ml_layer():
    return {
        "$type": "Multilayer_Layer",
        "colorScale": cname_entry("null_null"),
        "material": resource_path_entry(
            "engine\\materials\\defaults\\multilayer_default.mltemplate"
        ),
        "matTile": 10.1,
        "mbTile": 6.0,
        "metalLevelsIn": cname_entry("null"),
        "metalLevelsOut": cname_entry("null"),
        "microblend": resource_path_entry("base\\surfaces\\microblends\\default.xbm"),
        "microblendContrast": 0.5,
        "microblendNormalStrength": 1.0,
        "microblendOffsetU": 0.0,
        "microblendOffsetV": 0.0,
        "normalStrength": cname_entry("null"),
        "offsetU": 0.0,
        "offsetV": 0.0,
        "opacity": 0.0,
        "overrides": cname_entry("None"),
        "roughLevelsIn": cname_entry("null"),
        "roughLevelsOut": cname_entry("null"),
    }


def _required_layer_socket(layer, name):
    inputs = getattr(layer, "inputs", None)
    socket = inputs.get(name) if inputs is not None else None
    if socket is None:
        raise KeyError(
            f"Layer node {getattr(layer, 'name', '<unnamed>')} is missing {name}"
        )
    return socket


def _socket_components(layer, name, dimensions):
    value = _required_layer_socket(layer, name).default_value
    components = _numeric_components(value, dimensions)
    if components is None:
        raise ValueError(f"{name} must provide {dimensions} numeric component(s)")
    if dimensions == 1:
        return float(components[0])
    return tuple(float(component) for component in components)


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


def _override_mapping(template_data):
    overrides = template_data.get("overrides")
    if overrides is None:
        overrides = template_data.get("Overrides")
    if not isinstance(overrides, dict):
        raise ValueError("MLTemplate has no override mapping")
    return overrides


def _override_entries(template_data, json_key):
    overrides = _override_mapping(template_data)
    for key in (json_key, json_key[:1].upper() + json_key[1:]):
        entries = overrides.get(key)
        if isinstance(entries, list):
            return entries
    raise ValueError(f"MLTemplate has no {json_key} override schema")


def _entry_name(entry):
    try:
        return str(entry["n"]["$value"])
    except (KeyError, TypeError):
        return ""


def _next_override_name(entries):
    existing = {_entry_name(entry) for entry in entries}
    index = 0
    while True:
        name = f"000000_{index:06d}"
        if name not in existing:
            return name
        index += 1


def _schema_entry(entries, dimensions):
    if dimensions == 1:
        for entry in entries:
            if isinstance(entry, dict) and isinstance(entry.get("n"), dict):
                return entry
    else:
        for entry in entries:
            value = entry.get("v") if isinstance(entry, dict) else None
            elements = value.get("Elements") if isinstance(value, dict) else None
            if isinstance(elements, list) and len(elements) >= dimensions:
                return entry
    return None


def _append_override(template_data, json_key, value, dimensions):
    entries = _override_entries(template_data, json_key)
    schema = _schema_entry(entries, dimensions)
    if schema is None:
        raise ValueError(
            f"MLTemplate {json_key} overrides do not contain a writable schema entry"
        )
    entry = copy.deepcopy(schema)
    name = _next_override_name(entries)
    entry["n"]["$value"] = name
    components = _numeric_components(value, dimensions)
    if components is None:
        raise ValueError(f"{json_key} override value is invalid")
    if dimensions == 1:
        entry["v"] = float(components[0])
    else:
        elements = entry["v"]["Elements"]
        for index in range(dimensions):
            elements[index] = float(components[index])
    entries.append(entry)
    return name


def _template_state(template_states, template_path, project_path, depot_path):
    state = template_states.get(template_path)
    if state is not None:
        return state
    template_json = copy.deepcopy(
        _load_rooted_json(template_path + ".json", project_path, depot_path)
    )
    template_data = template_json["Data"]["RootChunk"]
    state = {
        "json": template_json,
        "data": template_data,
        "table": createOverrideTable(template_data),
        "dirty": False,
        "output": template_path,
        "layers": [],
    }
    template_states[template_path] = state
    return state


def _resolve_layer_override(
    state,
    table_key,
    json_key,
    value,
    dimensions,
    tolerance,
    allow_create,
    preferred,
):
    match = _find_override_name(
        state["table"], table_key, value, dimensions, tolerance, preferred=preferred
    )
    if match is not None:
        return match, False
    if not allow_create:
        return None, False
    name = _append_override(state["data"], json_key, value, dimensions)
    state["table"] = createOverrideTable(state["data"])
    state["dirty"] = True
    return name, True


def cp77_mlsetup_export(context, mlsetuppath, write_mltemplate):
    """Write the active material's multilayer setup to mlsetuppath"""
    active_object = getattr(context, "active_object", None)
    active_material = (
        getattr(active_object, "active_material", None)
        if active_object is not None
        else None
    )
    node_tree = (
        getattr(active_material, "node_tree", None)
        if active_material is not None
        else None
    )
    if active_material is None or node_tree is None:
        return OperationResult.cancelled(
            "Select a mesh with an editable multilayer material."
        )
    setup_path = active_material.get("MLSetup")
    if setup_path is None:
        return OperationResult.cancelled(
            "Multilayered setup not found within selected material."
        )
    # A created material has no setup of its own until this exports one; it starts from the game's default.
    setup_path = setup_path or MULTILAYER_DEFAULT_SETUP
    project_path = active_material.get("cp77_project_path")
    depot_path = active_material.get("DepotPath")
    try:
        mlsetup = copy.deepcopy(
            _load_rooted_json(str(setup_path) + ".json", project_path, depot_path)
        )
        root_chunk = mlsetup["Data"]["RootChunk"]
        json_layers = root_chunk.get("layers")
        if json_layers is None:
            json_layers = root_chunk.get("Layers")
        if not isinstance(json_layers, list):
            raise ValueError("MLSetup has no layer list")
    except (FileNotFoundError, KeyError, TypeError, ValueError) as error:
        return OperationResult.cancelled(
            f"Could not load {setup_path}: {error}", error=error
        )
    root = multilayer_root(node_tree.nodes)
    if root is None:
        return OperationResult.cancelled(
            "Multilayered shader node not found within selected material."
        )
    linked = {
        index: layer for index, layer in layer_nodes(node_tree.nodes, root, 20, False)
    }
    if not linked:
        return OperationResult.cancelled("No linked multilayer layers were found.")
    layer_count = max(linked) + 1
    while len(json_layers) < layer_count:
        json_layers.append(_default_ml_layer())
    del json_layers[layer_count:]

    tolerance = 0.00001
    template_states = {}
    unmatched = []

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
                "matTile": _socket_components(layer, "MatTile", 1),
                "mbTile": _socket_components(layer, "MbTile", 1),
                "microblendNormalStrength": _socket_components(
                    layer, "MicroblendNormalStrength", 1
                ),
                "microblendContrast": _socket_components(
                    layer, "MicroblendContrast", 1
                ),
                "offsetU": _socket_components(layer, "OffsetU", 1),
                "offsetV": _socket_components(layer, "OffsetV", 1),
                "microblendOffsetU": _socket_components(layer, "MicroblendOffsetU", 1),
                "microblendOffsetV": _socket_components(layer, "MicroblendOffsetV", 1),
                "opacity": _socket_components(layer, "Opacity", 1),
            }
            override_values = {
                "ColorScale": _socket_components(layer, "ColorScale", 3),
                "NormalStrength": _socket_components(layer, "NormalStrength", 1),
                "MetalLevelsIn": _socket_components(layer, "MetalLevelsIn", 2),
                "MetalLevelsOut": _socket_components(layer, "MetalLevelsOut", 2),
                "RoughLevelsIn": _socket_components(layer, "RoughLevelsIn", 2),
                "RoughLevelsOut": _socket_components(layer, "RoughLevelsOut", 2),
            }
            microblend = _microblend_path(layer)
            state = _template_state(
                template_states,
                template_path,
                project_path,
                depot_path,
            )
        except (
            AttributeError,
            FileNotFoundError,
            KeyError,
            ReferenceError,
            TypeError,
            ValueError,
        ) as error:
            log_once(
                _LOG,
                "DEBUG",
                ("cp77_mlsetup_export", type(error).__name__),
                "cp77 mlsetup export: fell back after %s",
                error,
                exc_info=True,
            )
            return OperationResult.cancelled(
                f"Layer {layer_number} could not be exported: {error}", error=error
            )

        json_layer.update(values)
        if microblend:
            json_layer["microblend"]["DepotPath"]["$value"] = make_rel(microblend)
        state["layers"].append(json_layer)
        json_layer["material"]["DepotPath"]["$value"] = state["output"]

        for table_key, json_key, dimensions in _OVERRIDE_SPECS:
            value = override_values[table_key]
            try:
                name, created = _resolve_layer_override(
                    state,
                    table_key,
                    json_key,
                    value,
                    dimensions,
                    tolerance,
                    bool(write_mltemplate),
                    str((json_layer.get(json_key) or {}).get("$value", "") or ""),
                )
            except (KeyError, TypeError, ValueError) as error:
                return OperationResult.cancelled(
                    f"{table_key} in Layer {layer_number} could not be written: {error}",
                    error=error,
                )
            if name is None:
                unmatched.append((layer_number, table_key))
                continue
            json_layer[json_key]["$value"] = name
            if created:
                state["output"] = prefix_mat(template_path)
                for layer_json in state["layers"]:
                    layer_json["material"]["DepotPath"]["$value"] = state["output"]

    if unmatched:
        preview = ", ".join(f"Layer {layer}: {name}" for layer, name in unmatched[:6])
        remainder = len(unmatched) - min(len(unmatched), 6)
        if remainder:
            preview += f", and {remainder} more"
        return OperationResult.cancelled(
            "The material contains authored override values that are not present in its MLTemplate "
            f"({preview}). Enable Generate modified MLTEMPLATE and export again."
        )

    dirty_states = [state for state in template_states.values() if state["dirty"]]
    if dirty_states and not project_path:
        return OperationResult.cancelled(
            "Modified MLTemplate overrides require a WolvenKit project path."
        )

    payloads = {
        mlsetuppath: (json.dumps(mlsetup, indent=2, ensure_ascii=False) + "\n").encode(
            "utf-8"
        )
    }
    for state in dirty_states:
        try:
            # The template path comes from imported data, so it must stay inside the project.
            output_path = project_raw_file(project_path, state["output"])
        except ValueError as error:
            return OperationResult.cancelled(
                f"Modified MLTemplate {state['output']} was not written: {error}",
                error=error,
            )
        payloads[output_path] = (
            json.dumps(state["json"], indent=2, ensure_ascii=False) + "\n"
        ).encode("utf-8")
    atomic_write_many(payloads)

    message = f"Exported MLSETUP from {active_material.name} on {active_object.name}"
    if dirty_states:
        message += f" with {len(dirty_states)} modified MLTEMPLATE resource(s)"
    relative = source_raw_relative(mlsetuppath)
    if not relative:
        return OperationResult.finished(
            message + ".",
            warnings=(
                "The file is outside a WolvenKit project's source/raw folder; the material's MLSetup path was "
                "not updated.",
            ),
        )
    active_material["MLSetup"] = strip_json_suffix(relative)
    return OperationResult.finished(
        f"{message}. The material's MLSetup now points to {active_material['MLSetup']}."
    )
