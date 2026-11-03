import colorsys
import copy
import hashlib
import math
import os

import bpy

from ...assetio.resolver import full_suffix, resolve_rooted_path
from ...blender.transactions import new_tracked_datablock, track_mutation
from ...materials.resources import load_material_document
from .nodes import createOverrideTable

def _load_rooted_json(reference, project_path, depot_path):
    extension = full_suffix(reference)
    resolved = resolve_rooted_path(
        reference,
        project_root=project_path,
        depot_root=depot_path,
        extensions=(extension,),
    )
    if not resolved:
        raise FileNotFoundError(reference)
    return load_material_document(resolved).payload

def cp77_step_sort(r, g, b, repetitions=1):
    lum = math.sqrt(.241 * r + .691 * g + .068 * b)
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    if s < .01:
        h2 = -1
    else:
        h2 = int(h * repetitions)
    lum2 = int(lum * repetitions)
    v2 = int(v * repetitions)
    if h2 % 2 == 1:
        v2 = repetitions - v2
        lum = repetitions - lum
    return (h2, lum, v2)

def _normalize_template_path(value):
    return str(value or "").strip().replace("/", "\\").lower()

def _template_palette_name(template_path):
    raw = str(template_path or "").replace("/", "\\").rsplit("\\", 1)[-1]
    lower = raw.lower()
    if lower.endswith(".mltemplate.json"):
        return raw[:-16]
    if lower.endswith(".mltemplate"):
        return raw[:-11]
    return os.path.splitext(raw)[0]

def _palette_for_template(template_path):
    normalized = _normalize_template_path(template_path)
    for palette in bpy.data.palettes:
        if _normalize_template_path(palette.get("MLTemplatePath", "")) == normalized:
            return palette
    return None

def _clear_palette_colors(palette):
    colors = getattr(palette, "colors", None)
    if colors is None:
        return
    for color in reversed(tuple(colors)):
        try:
            colors.remove(color)
        except (AttributeError, ReferenceError, RuntimeError, TypeError):
            break

def _sorted_override_colors(template_name, override_table):
    color_table = override_table.get("ColorScale", {})
    if not color_table:
        return ()
    block_len = 1
    for key in color_table:
        if key.endswith("_null"):
            break
        block_len += 1
    color_nulls = []
    for key, value in color_table.items():
        if not key.endswith("_null"):
            continue
        try:
            red, green, blue = tuple(value)[:3]
        except (TypeError, ValueError):
            continue
        color_nulls.append((key, cp77_step_sort(red, green, blue, 8)))
    color_nulls.sort(key=lambda item: item[1])
    ordered = []
    for key, _sort_key in color_nulls:
        prefix_key = key.split("_", 1)[0]
        for candidate, value in color_table.items():
            if candidate.split("_", 1)[0] == prefix_key:
                ordered.append(value)
    if not ordered:
        ordered = list(color_table.values())

    alt_sort_substrings = {
        "annodised", "cliff_", "dust_", "dirt_", "ebony_",
        "factory_floor_old", "factory_floor_rough", "factory_floor_cracked",
        "grass_", "gravel", "grime_", "mirror", "mud_", "patina",
        "pebbles", "plaster_exterior_01_300", "plaster_exterior_damp_01_300",
        "plaster_exterior_neutral_01_300", "plaster_exterior_damp_neutral_01_300",
        "plaster_exterior_patched_neutral_01_300",
        "plaster_exterior_rough_neutral_01_300_copy", "rock_", "sand_",
        "soil_", "trash_", "terrain", "water", "windows",
    }
    steel_sort_substrings = {
        "steel_dented_01_100", "steel_dented_coroded_01_100",
        "steel_dented_rusty_01_100", "steel_galvanized_corrugated_01_300",
        "steel_galvanized_corrugated_02_300",
        "steel_galvanized_corrugated_rust_01_300",
        "steel_galvanized_corrugated_rust_02_300", "iron_old",
    }
    offset_maps = {
        "alt": {0: 0, 1: 0, 2: 2, 3: 1, 4: 2},
        "concrete": {0: 0, 1: 0, 2: 2, 3: 1, 4: 2},
        "steel": {0: 0, 1: 1, 2: 1, 3: 0, 4: 2},
        "asphalt_paint": {0: 0, 1: 1, 2: 0, 3: 2},
        "default": {
            5: {0: 0, 1: 1, 2: 1, 3: 1},
            6: {0: 0, 1: 1, 2: 2, 3: 2, 4: 4},
            8: {0: 0, 1: 1, 2: 2, 3: 3, 4: 3, 5: 2, 6: 4},
            9: {0: 0, 1: 1, 2: 1, 3: 1, 4: 0, 5: 0, 6: 3, 7: 0},
        },
    }
    lower_name = template_name.lower()
    if any(token in lower_name for token in alt_sort_substrings):
        category = "alt"
    elif any(token in lower_name for token in steel_sort_substrings):
        category = "steel"
    elif "asphalt_paint_01_300" in lower_name:
        category = "asphalt_paint"
    elif "concrete" in lower_name and not any(token in lower_name for token in ("dyed", "painted")):
        category = "concrete"
    else:
        category = None

    result = []
    block_index = 0
    block_number = 0
    for color in ordered:
        block_position = block_number * block_len
        if category:
            offset = offset_maps[category].get(block_index, 0)
        else:
            offset = offset_maps["default"].get(block_len, {}).get(block_index, 0)
        insert_at = min(len(result), block_position + offset)
        result.insert(insert_at, color)
        block_index += 1
        if block_index >= block_len:
            block_index = 0
            block_number += 1
    return tuple(result)

def _palette_snapshot(palette):
    keys = (
        "MLTemplatePath",
        "NormalStrengthList",
        "MetalLevelsInList",
        "MetalLevelsOutList",
        "RoughLevelsInList",
        "RoughLevelsOutList",
    )
    properties = {}
    for key in keys:
        if key in palette:
            try:
                properties[key] = copy.deepcopy(palette[key])
            except (AttributeError, ReferenceError, TypeError):
                properties[key] = palette[key]
    colors = []
    active_index = -1
    active = getattr(getattr(palette, "colors", None), "active", None)
    for index, color in enumerate(tuple(getattr(palette, "colors", ()))):
        try:
            colors.append(tuple(float(value) for value in color.color[:3]))
            if color is active:
                active_index = index
        except (AttributeError, ReferenceError, TypeError, ValueError):
            continue
    return properties, tuple(colors), active_index

def _restore_palette(palette, snapshot):
    properties, colors, active_index = snapshot
    for key in (
        "MLTemplatePath",
        "NormalStrengthList",
        "MetalLevelsInList",
        "MetalLevelsOutList",
        "RoughLevelsInList",
        "RoughLevelsOutList",
    ):
        if key in palette:
            del palette[key]
    for key, value in properties.items():
        palette[key] = value
    _clear_palette_colors(palette)
    restored = []
    for value in colors:
        color = palette.colors.new()
        color.color = value
        restored.append(color)
    if 0 <= active_index < len(restored):
        palette.colors.active = restored[active_index]

def _palette_matches_snapshot(palette, snapshot):
    properties, colors, _active_index = snapshot
    for key, value in properties.items():
        if key not in palette or palette[key] != value:
            return False
    current = []
    for color in tuple(getattr(palette, "colors", ())):
        try:
            current.append(tuple(float(value) for value in color.color[:3]))
        except (AttributeError, ReferenceError, TypeError, ValueError):
            return False
    return tuple(current) == colors

def cp77_create_palette(MLTemplate, OverrideTable):
    template_path = str(MLTemplate)
    template_name = _template_palette_name(template_path)
    palette = _palette_for_template(template_path)
    created = palette is None
    if created:
        palette_name = template_name
        existing = bpy.data.palettes.get(palette_name)
        if (
            existing is not None
            and _normalize_template_path(existing.get("MLTemplatePath", ""))
            != _normalize_template_path(template_path)
        ):
            suffix = hashlib.sha1(
                _normalize_template_path(template_path).encode("utf-8")
            ).hexdigest()[:8]
            palette_name = f"{template_name} [{suffix}]"
        palette = new_tracked_datablock("palettes", palette_name)
        snapshot = None
    else:
        snapshot = _palette_snapshot(palette)
        track_mutation(
            ("multilayer_palette", id(palette)),
            lambda palette=palette, snapshot=snapshot: _restore_palette(palette, snapshot),
            verify=lambda palette=palette, snapshot=snapshot: _palette_matches_snapshot(
                palette, snapshot
            ),
            label=f"multilayer palette {palette.name}",
        )
    try:
        palette["MLTemplatePath"] = template_path
        for key in (
            "NormalStrength",
            "MetalLevelsIn",
            "MetalLevelsOut",
            "RoughLevelsIn",
            "RoughLevelsOut",
        ):
            palette[key + "List"] = [
                str(value) for value in OverrideTable.get(key, {}).values()
            ]
        colors = []
        for value in _sorted_override_colors(template_name, OverrideTable):
            try:
                color_value = tuple(float(component) for component in tuple(value)[:3])
            except (TypeError, ValueError):
                continue
            if len(color_value) == 3:
                colors.append(color_value)
        _clear_palette_colors(palette)
        for color_value in colors:
            color = palette.colors.new()
            color.color = color_value
        return palette
    except Exception:
        if created:
            try:
                bpy.data.palettes.remove(palette)
            except (AttributeError, ReferenceError, RuntimeError, TypeError, ValueError):
                pass
        elif snapshot is not None:
            _restore_palette(palette, snapshot)
        raise

def _report_override(owner, severity, message):
    reporter = getattr(owner, "report", None)
    if callable(reporter):
        reporter({severity}, message)
    else:
        print(f"[CP77 MLSETUP] {severity}: {message}")

def _multilayer_root(nodes):
    for node in nodes:
        try:
            if node.get("cp77MaterialToolsRole") == "multilayer_root":
                return node
        except (AttributeError, ReferenceError, TypeError):
            continue
    return nodes.get("Multilayered 1.8.0")

def _linked_source(socket):
    if socket is None or not getattr(socket, "is_linked", False):
        return None
    links = tuple(getattr(socket, "links", ()))
    return getattr(links[0], "from_node", None) if links else None

def _layer_nodes(nodes, root, layer_count, include_disconnected):
    for index in range(layer_count):
        if include_disconnected:
            layer = nodes.get(f"Mat_Mod_Layer_{index}")
        else:
            inputs = getattr(root, "inputs", None)
            socket = inputs.get(f"Layer {index + 1}") if inputs is not None else None
            layer = _linked_source(socket)
        if layer is not None:
            yield index, layer

def _role_node(nodes, role, fallback=None):
    if nodes is None:
        return None
    for node in nodes:
        try:
            if node.get("cp77MultilayerRole") == role:
                return node
        except (AttributeError, ReferenceError, TypeError):
            continue
    return nodes.get(fallback) if fallback else None

def _layer_template_path(layer):
    layer_tree = getattr(layer, "node_tree", None)
    if layer_tree is None:
        return ""
    base = _role_node(getattr(layer_tree, "nodes", None), "base_material", "Group")
    template_tree = getattr(base, "node_tree", None) if base is not None else None
    if template_tree is None:
        return str(layer.get("mlTemplate", ""))
    group_input = _role_node(getattr(template_tree, "nodes", None), "group_input", "Group Input")
    if group_input is not None:
        path = group_input.get("mlTemplate", "")
        if path:
            return str(path)
    return str(template_tree.get("mlTemplate", layer.get("mlTemplate", "")))

def cp77_mlsetup_generateoverrides(self, context, objs=None, include_disconnected=False):
    objects = tuple(objs or getattr(context, "selected_objects", ()) or ())
    if not objects:
        _report_override(self, "WARNING", "No objects selected for override generation.")
        return {"CANCELLED"}
    generated = 0
    for obj in objects:
        material = getattr(obj, "active_material", None)
        node_tree = getattr(material, "node_tree", None) if material is not None else None
        if material is None or node_tree is None:
            continue
        setup_path = material.get("MLSetup")
        if not setup_path:
            _report_override(self, "WARNING", f"Multilayer setup not found on {obj.name}.")
            continue
        root = _multilayer_root(node_tree.nodes)
        if root is None:
            _report_override(self, "WARNING", f"Multilayer root node not found on {material.name}.")
            continue
        project_path = material.get("ProjPath")
        depot_path = material.get("DepotPath")
        try:
            setup = _load_rooted_json(str(setup_path) + ".json", project_path, depot_path)
            json_layers = setup["Data"]["RootChunk"]["layers"]
        except (FileNotFoundError, KeyError, TypeError, ValueError) as error:
            _report_override(self, "WARNING", f"Could not load {setup_path}: {error}")
            continue
        layer_count = min(len(json_layers), 20)
        object_generated = 0
        for index, layer in _layer_nodes(
            node_tree.nodes,
            root,
            layer_count,
            include_disconnected,
        ):
            template_path = _layer_template_path(layer)
            if not template_path:
                _report_override(self, "WARNING", f"Layer {index + 1} has no MLTemplate metadata.")
                continue
            try:
                template_json = _load_rooted_json(
                    template_path + ".json",
                    project_path,
                    depot_path,
                )
                override_table = createOverrideTable(template_json["Data"]["RootChunk"])
            except (FileNotFoundError, KeyError, TypeError, ValueError) as error:
                _report_override(self, "WARNING", f"Layer {index + 1} template could not be loaded: {error}")
                continue
            try:
                json_layers[index]["material"]["DepotPath"]["$value"] = template_path
                cp77_create_palette(template_path, override_table)
            except (AttributeError, KeyError, RuntimeError, TypeError, ValueError) as error:
                _report_override(self, "WARNING", f"Layer {index + 1} overrides could not be created: {error}")
                continue
            object_generated += 1
        if object_generated:
            generated += object_generated
            _report_override(
                self,
                "INFO",
                f"Generated overrides for {material.name} on {obj.name} ({object_generated} layers).",
            )
    return {"FINISHED"} if generated else {"CANCELLED"}
