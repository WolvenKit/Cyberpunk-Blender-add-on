import colorsys
import copy
import hashlib
import math
import os
import time
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps

import bpy

from ...assetio.paths import depot_path_key
from ...assetio.resolver import full_suffix, resolve_rooted_path
from ...assetio.values import coerce_float
from ...blender.transactions import new_tracked_datablock, track_mutation
from ...core.log import get_logger
from ...core.notifications import report
from ..resources import load_material_document
from .nodes import createOverrideTable

_LOG = get_logger(__name__)

_ALT_SORT_TEMPLATES = frozenset(
    {
        "annodised",
        "cliff_",
        "dust_",
        "dirt_",
        "ebony_",
        "factory_floor_old",
        "factory_floor_rough",
        "factory_floor_cracked",
        "grass_",
        "gravel",
        "grime_",
        "mirror",
        "mud_",
        "patina",
        "pebbles",
        "plaster_exterior_01_300",
        "plaster_exterior_damp_01_300",
        "plaster_exterior_neutral_01_300",
        "plaster_exterior_damp_neutral_01_300",
        "plaster_exterior_patched_neutral_01_300",
        "plaster_exterior_rough_neutral_01_300_copy",
        "rock_",
        "sand_",
        "soil_",
        "trash_",
        "terrain",
        "water",
        "windows",
    }
)
_STEEL_SORT_TEMPLATES = frozenset(
    {
        "steel_dented_01_100",
        "steel_dented_coroded_01_100",
        "steel_dented_rusty_01_100",
        "steel_galvanized_corrugated_01_300",
        "steel_galvanized_corrugated_02_300",
        "steel_galvanized_corrugated_rust_01_300",
        "steel_galvanized_corrugated_rust_02_300",
        "iron_old",
    }
)
_COLOR_BLOCK_OFFSETS = {
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

_PALETTE_PROPERTY_KEYS = (
    "MLTemplatePath",
    "ColorScaleList",
    "NormalStrengthList",
    "MetalLevelsInList",
    "MetalLevelsOutList",
    "RoughLevelsInList",
    "RoughLevelsOutList",
    "cp77_default_color_scale",
)

_OVERRIDE_BATCH_DEPTH = ContextVar("cp77_override_palette_batch_depth", default=0)
_OVERRIDE_REPORT_OWNER = ContextVar("cp77_override_palette_report_owner", default=None)
_PENDING_OVERRIDE_PALETTES = {}
_PREPARED_OVERRIDE_PALETTES = {}
_PALETTE_INDEX = {}
_PALETTE_INDEX_READY = False
_OVERRIDE_PALETTE_STATS = {
    "queued": 0,
    "queue_hits": 0,
    "generated": 0,
    "refreshed": 0,
    "unchanged": 0,
    "flushes": 0,
    "failures": 0,
    "seconds": 0.0,
}


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
    lum = math.sqrt(0.241 * r + 0.691 * g + 0.068 * b)
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    if s < 0.01:
        h2 = -1
    else:
        h2 = int(h * repetitions)
    v2 = int(v * repetitions)
    if h2 % 2 == 1:
        v2 = repetitions - v2
        lum = repetitions - lum
    return (h2, lum, v2)


def _template_palette_name(template_path):
    raw = str(template_path or "").replace("/", "\\").rsplit("\\", 1)[-1]
    lower = raw.lower()
    if lower.endswith(".mltemplate.json"):
        return raw[:-16]
    if lower.endswith(".mltemplate"):
        return raw[:-11]
    return os.path.splitext(raw)[0]


def _palette_is_live(palette):
    try:
        return bpy.data.palettes.get(palette.name) == palette
    except (ReferenceError, RuntimeError):
        return False


def _index_palette(palette):
    try:
        normalized = depot_path_key(palette.get("MLTemplatePath", ""))
    except ReferenceError:
        return
    if normalized:
        _PALETTE_INDEX[normalized] = palette


def _rebuild_palette_index():
    global _PALETTE_INDEX_READY
    _PALETTE_INDEX.clear()
    for palette in bpy.data.palettes:
        _index_palette(palette)
    _PALETTE_INDEX_READY = True


def find_override_palette(template_path):
    normalized = depot_path_key(template_path)
    if not normalized:
        return None
    if not _PALETTE_INDEX_READY:
        _rebuild_palette_index()
    palette = _PALETTE_INDEX.get(normalized)
    if palette is None:
        return None
    try:
        indexed_path = depot_path_key(palette.get("MLTemplatePath", ""))
    except ReferenceError:
        indexed_path = ""
    if indexed_path == normalized and _palette_is_live(palette):
        return palette
    _rebuild_palette_index()
    palette = _PALETTE_INDEX.get(normalized)
    return palette if palette is not None and _palette_is_live(palette) else None


def _clear_palette_colors(palette):
    colors = getattr(palette, "colors", None)
    if colors is None:
        return
    for color in reversed(tuple(colors)):
        try:
            colors.remove(color)
        except (ReferenceError, RuntimeError):
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
    color_groups = {}
    color_nulls = []
    for key, value in color_table.items():
        prefix_key = key.split("_", 1)[0]
        color_groups.setdefault(prefix_key, []).append(value)
        if not key.endswith("_null"):
            continue
        try:
            red, green, blue = tuple(value)[:3]
        except (TypeError, ValueError):
            continue
        color_nulls.append((prefix_key, cp77_step_sort(red, green, blue, 8)))
    color_nulls.sort(key=lambda item: item[1])
    ordered = []
    for prefix_key, _sort_key in color_nulls:
        ordered.extend(color_groups.get(prefix_key, ()))
    if not ordered:
        ordered = list(color_table.values())

    lower_name = template_name.lower()
    if any(token in lower_name for token in _ALT_SORT_TEMPLATES):
        category = "alt"
    elif any(token in lower_name for token in _STEEL_SORT_TEMPLATES):
        category = "steel"
    elif "asphalt_paint_01_300" in lower_name:
        category = "asphalt_paint"
    elif "concrete" in lower_name and not any(
        token in lower_name for token in ("dyed", "painted")
    ):
        category = "concrete"
    else:
        category = None

    result = []
    block_index = 0
    block_number = 0
    for color in ordered:
        block_position = block_number * block_len
        if category:
            offset = _COLOR_BLOCK_OFFSETS[category].get(block_index, 0)
        else:
            offset = (
                _COLOR_BLOCK_OFFSETS["default"].get(block_len, {}).get(block_index, 0)
            )
        insert_at = min(len(result), block_position + offset)
        result.insert(insert_at, color)
        block_index += 1
        if block_index >= block_len:
            block_index = 0
            block_number += 1
    return tuple(result)


def _palette_snapshot(palette):
    properties = {}
    for key in _PALETTE_PROPERTY_KEYS:
        if key in palette:
            try:
                properties[key] = copy.deepcopy(palette[key])
            except ReferenceError:
                properties[key] = palette[key]
    colors = []
    active_index = -1
    active = getattr(getattr(palette, "colors", None), "active", None)
    for index, color in enumerate(tuple(getattr(palette, "colors", ()))):
        try:
            colors.append(tuple(float(value) for value in color.color[:3]))
            if color is active:
                active_index = index
        except (ReferenceError, ValueError):
            continue
    return properties, tuple(colors), active_index


def _restore_palette(palette, snapshot):
    properties, colors, active_index = snapshot
    for key in _PALETTE_PROPERTY_KEYS:
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
    for key in _PALETTE_PROPERTY_KEYS:
        if key in properties:
            if key not in palette or palette[key] != properties[key]:
                return False
        elif key in palette:
            return False
    current = []
    for color in tuple(getattr(palette, "colors", ())):
        try:
            current.append(tuple(float(value) for value in color.color[:3]))
        except (ReferenceError, ValueError):
            return False
    return tuple(current) == colors


def _palette_data(template_path, override_table):
    template_name = _template_palette_name(template_path)
    properties = {
        "MLTemplatePath": str(template_path),
    }
    for key in (
        "NormalStrength",
        "MetalLevelsIn",
        "MetalLevelsOut",
        "RoughLevelsIn",
        "RoughLevelsOut",
    ):
        properties[key + "List"] = [
            str(value) for value in override_table.get(key, {}).values()
        ]
    colors = []
    for value in _sorted_override_colors(template_name, override_table):
        color = _palette_color(value)
        if color is not None:
            colors.append(color)
    properties["ColorScaleList"] = [str(color) for color in colors]
    default = _palette_color(
        override_table.get("ColorScale", {}).get(
            override_table.get("DefaultColorScale")
        )
    )
    if default is not None:
        properties["cp77_default_color_scale"] = str(default)
    return properties, tuple(colors)


def _palette_color(value):
    """The (r, g, b) of an override colour, or None when it is not one"""
    if not isinstance(value, (list, tuple)):
        return None
    color = tuple(
        coerce_float(component, math.nan, unwrap=False, finite=False)
        for component in value[:3]
    )
    return (
        color
        if len(color) == 3 and not any(math.isnan(component) for component in color)
        else None
    )


def _freeze_palette_value(value):
    if isinstance(value, dict):
        return tuple(
            (str(key), _freeze_palette_value(item))
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        )
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_palette_value(item) for item in value)
    return value


def _palette_signature(properties, colors):
    signature_properties = []
    for key, value in sorted(properties.items()):
        if key == "MLTemplatePath":
            value = depot_path_key(value)
        signature_properties.append((key, _freeze_palette_value(value)))
    return tuple(signature_properties), tuple(colors)


def _palette_matches_data(palette, properties, colors):
    for key in _PALETTE_PROPERTY_KEYS:
        try:
            if key in properties:
                if key not in palette or palette[key] != properties[key]:
                    return False
            elif key in palette:
                return False
        except ReferenceError:
            return False
    current = []
    for color in tuple(getattr(palette, "colors", ())):
        try:
            current.append(tuple(float(value) for value in color.color[:3]))
        except (ReferenceError, ValueError):
            return False
    return tuple(current) == colors


def _create_palette_from_data(template_path, properties, colors):
    template_path = str(template_path).replace("/", "\\")
    normalized = depot_path_key(template_path)
    template_name = _template_palette_name(template_path)
    palette = find_override_palette(template_path)
    created = palette is None
    if created:
        palette_name = template_name
        existing = bpy.data.palettes.get(palette_name)
        if (
            existing is not None
            and depot_path_key(existing.get("MLTemplatePath", "")) != normalized
        ):
            suffix = hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:8]
            palette_name = f"{template_name} [{suffix}]"
        palette = new_tracked_datablock("palettes", palette_name)
        snapshot = None
    else:
        if _palette_matches_data(palette, properties, colors):
            _OVERRIDE_PALETTE_STATS["unchanged"] += 1
            _PALETTE_INDEX[normalized] = palette
            return palette
        snapshot = _palette_snapshot(palette)
        track_mutation(
            ("multilayer_palette", id(palette)),
            lambda palette=palette, snapshot=snapshot: _restore_palette(
                palette, snapshot
            ),
            verify=lambda palette=palette, snapshot=snapshot: _palette_matches_snapshot(
                palette, snapshot
            ),
            label=f"multilayer palette {palette.name}",
        )
    try:
        for key in _PALETTE_PROPERTY_KEYS:
            if key in properties:
                palette[key] = properties[key]
            elif key in palette:
                del palette[key]
        _clear_palette_colors(palette)
        for color_value in colors:
            color = palette.colors.new()
            color.color = color_value
        _PALETTE_INDEX[normalized] = palette
        _OVERRIDE_PALETTE_STATS["generated" if created else "refreshed"] += 1
        return palette
    except Exception:
        _PALETTE_INDEX.pop(normalized, None)
        if created:
            try:
                bpy.data.palettes.remove(palette)
            except (ReferenceError, RuntimeError, ValueError):
                pass
        elif snapshot is not None:
            _restore_palette(palette, snapshot)
            _index_palette(palette)
        raise


def cp77_create_palette(MLTemplate, OverrideTable):
    template_path = str(MLTemplate).replace("/", "\\")
    properties, colors = _palette_data(template_path, OverrideTable)
    return _create_palette_from_data(template_path, properties, colors)


def override_palette_stats():
    return {
        **_OVERRIDE_PALETTE_STATS,
        "pending": len(_PENDING_OVERRIDE_PALETTES),
        "prepared": len(_PREPARED_OVERRIDE_PALETTES),
        "batch_depth": int(_OVERRIDE_BATCH_DEPTH.get()),
    }


def clear_override_palette_index():
    global _PALETTE_INDEX_READY
    _PALETTE_INDEX.clear()
    _PALETTE_INDEX_READY = False


def clear_override_palette_cache(*, reset_stats=True):
    _PENDING_OVERRIDE_PALETTES.clear()
    _PREPARED_OVERRIDE_PALETTES.clear()
    clear_override_palette_index()
    if reset_stats:
        for key in _OVERRIDE_PALETTE_STATS:
            _OVERRIDE_PALETTE_STATS[key] = 0.0 if key == "seconds" else 0


def _prepared_palette(template_path, signature):
    key = depot_path_key(template_path)
    if _PREPARED_OVERRIDE_PALETTES.get(key) != signature:
        return None
    return find_override_palette(template_path)


def queue_override_palette(template_path, override_table):
    template_path = str(template_path or "")
    if not template_path or not isinstance(override_table, dict):
        return None
    key = depot_path_key(template_path)
    if _OVERRIDE_BATCH_DEPTH.get() > 0 and key in _PENDING_OVERRIDE_PALETTES:
        _OVERRIDE_PALETTE_STATS["queue_hits"] += 1
        return None
    properties, colors = _palette_data(template_path, override_table)
    signature = _palette_signature(properties, colors)
    palette = _prepared_palette(template_path, signature)
    if palette is not None:
        _OVERRIDE_PALETTE_STATS["queue_hits"] += 1
        return palette
    if _OVERRIDE_BATCH_DEPTH.get() > 0:
        _OVERRIDE_PALETTE_STATS["queued"] += 1
        _PENDING_OVERRIDE_PALETTES[key] = (
            template_path,
            properties,
            colors,
            signature,
        )
        return None
    palette = _create_palette_from_data(template_path, properties, colors)
    _PREPARED_OVERRIDE_PALETTES[key] = signature
    return palette


def flush_pending_override_palettes():
    if not _PENDING_OVERRIDE_PALETTES:
        return {
            "processed": 0,
            "failures": 0,
            "failed_templates": (),
            "seconds": 0.0,
        }
    pending = tuple(_PENDING_OVERRIDE_PALETTES.items())
    _PENDING_OVERRIDE_PALETTES.clear()
    started = time.perf_counter()
    processed = 0
    failed_templates = []
    for key, (template_path, properties, colors, signature) in pending:
        try:
            _create_palette_from_data(template_path, properties, colors)
            _PREPARED_OVERRIDE_PALETTES[key] = signature
            processed += 1
        except Exception as error:
            failed_templates.append((template_path, f"{type(error).__name__}: {error}"))
            _LOG.warning(
                "Automatic multilayer override preparation failed for %s",
                template_path,
                exc_info=True,
            )
    failures = len(failed_templates)
    elapsed = time.perf_counter() - started
    _OVERRIDE_PALETTE_STATS["flushes"] += 1
    _OVERRIDE_PALETTE_STATS["failures"] += failures
    _OVERRIDE_PALETTE_STATS["seconds"] += elapsed
    if processed or failures:
        _LOG.debug(
            "Prepared %d multilayer override palette(s) in %.3fs%s",
            processed,
            elapsed,
            f"; {failures} failed" if failures else "",
        )
    return {
        "processed": processed,
        "failures": failures,
        "failed_templates": tuple(failed_templates),
        "seconds": elapsed,
    }


def _report_flush_failures(owner, result):
    failures = result.get("failed_templates", ())
    if owner is None or not failures:
        return
    preview = ", ".join(path for path, _error in failures[:3])
    if len(failures) > 3:
        preview += f", and {len(failures) - 3} more"
    report(
        owner,
        "WARNING",
        f"{len(failures)} multilayer override palette(s) could not be prepared: {preview}",
        logger=_LOG,
    )


@contextmanager
def override_palette_batch_scope(owner=None):
    depth = int(_OVERRIDE_BATCH_DEPTH.get())
    inherited_owner = _OVERRIDE_REPORT_OWNER.get()
    effective_owner = owner if owner is not None else inherited_owner
    owner_token = _OVERRIDE_REPORT_OWNER.set(effective_owner)
    depth_token = _OVERRIDE_BATCH_DEPTH.set(depth + 1)
    try:
        yield
    except Exception:
        if depth == 0:
            _PENDING_OVERRIDE_PALETTES.clear()
        raise
    else:
        if depth == 0:
            result = flush_pending_override_palettes()
            _report_flush_failures(effective_owner, result)
    finally:
        _OVERRIDE_BATCH_DEPTH.reset(depth_token)
        _OVERRIDE_REPORT_OWNER.reset(owner_token)


def override_palette_batched(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        owner = kwargs.pop("_override_palette_owner", None)
        with override_palette_batch_scope(owner):
            return function(*args, **kwargs)

    return wrapped


def multilayer_root(nodes):
    for node in nodes:
        try:
            if node.get("cp77_material_tools_role") == "multilayer_root":
                return node
        except ReferenceError:
            continue
    return nodes.get("Multilayered 1.8.0")


def linked_source(socket):
    if socket is None:
        return None
    try:
        links = tuple(socket.links) if socket.is_linked else ()
    except ReferenceError:
        return None
    return getattr(links[0], "from_node", None) if links else None


def layer_nodes(nodes, root, layer_count, include_disconnected):
    for index in range(layer_count):
        if include_disconnected:
            layer = nodes.get(f"Mat_Mod_Layer_{index}")
        else:
            inputs = getattr(root, "inputs", None)
            socket = inputs.get(f"Layer {index + 1}") if inputs is not None else None
            layer = linked_source(socket)
        if layer is not None:
            yield index, layer


# A layer above the base with zero opacity adds nothing to the surface. Blender 5.3 leaves such layers out when it
# compiles a material; earlier versions evaluate every layer, so there the link of each hidden layer into the multilayer
# surface is muted. A muted link stays in the tree, so the panel and the exporters still find the layer through it.
_MUTES_HIDDEN_LAYERS = bpy.app.version < (5, 3, 0)


def layer_hidden(layer):
    """Whether the layer's opacity input is unlinked and zero"""
    try:
        opacity = layer.inputs.get("Opacity") if layer is not None else None
        return (
            opacity is not None
            and not opacity.is_linked
            and opacity.default_value == 0.0
        )
    except ReferenceError:
        return False


def sync_hidden_layer_links(node_tree, root):
    """Mute the link into the multilayer surface of each hidden layer above the base, and unmute the others"""
    for link in tuple(node_tree.links):
        if (
            link.to_node != root
            or not link.to_socket.name.startswith("Layer ")
            or link.to_socket.name == "Layer 1"
        ):
            continue
        muted = _MUTES_HIDDEN_LAYERS and layer_hidden(link.from_node)
        if link.is_muted != muted:
            link.is_muted = muted


def _role_node(nodes, role, fallback=None):
    if nodes is None:
        return None
    for node in nodes:
        try:
            if node.get("cp77_multilayer_role") == role:
                return node
        except ReferenceError:
            continue
    return nodes.get(fallback) if fallback else None


def _layer_template_path(layer):
    layer_tree = getattr(layer, "node_tree", None)
    if layer_tree is None:
        return ""
    base = _role_node(getattr(layer_tree, "nodes", None), "base_material", "Group")
    template_tree = getattr(base, "node_tree", None) if base is not None else None
    if template_tree is None:
        return str(layer.get("cp77_ml_template", ""))
    group_input = _role_node(
        getattr(template_tree, "nodes", None), "group_input", "Group Input"
    )
    if group_input is not None:
        path = group_input.get("cp77_ml_template", "")
        if path:
            return str(path)
    return str(template_tree.get("cp77_ml_template", layer.get("cp77_ml_template", "")))


def cp77_mlsetup_generateoverrides(
    self, context, objs=None, include_disconnected=False
):
    objects = tuple(objs or getattr(context, "selected_objects", ()) or ())
    if not objects:
        report(
            self, "WARNING", "No objects selected for override rebuild.", logger=_LOG
        )
        return {"CANCELLED"}
    generated = 0
    with override_palette_batch_scope(self):
        for obj in objects:
            material = getattr(obj, "active_material", None)
            node_tree = (
                getattr(material, "node_tree", None) if material is not None else None
            )
            if material is None or node_tree is None:
                continue
            root = multilayer_root(node_tree.nodes)
            if root is None:
                report(
                    self,
                    "WARNING",
                    f"Multilayer root node not found on {material.name}.",
                    logger=_LOG,
                )
                continue
            project_path = material.get("cp77_project_path")
            depot_path = material.get("DepotPath")
            object_generated = 0
            for index, layer in layer_nodes(
                node_tree.nodes,
                root,
                20,
                include_disconnected,
            ):
                template_path = _layer_template_path(layer)
                if not template_path:
                    report(
                        self,
                        "WARNING",
                        f"Layer {index + 1} has no MLTemplate metadata.",
                        logger=_LOG,
                    )
                    continue
                try:
                    template_json = _load_rooted_json(
                        template_path + ".json",
                        project_path,
                        depot_path,
                    )
                    override_table = createOverrideTable(
                        template_json["Data"]["RootChunk"]
                    )
                    queue_override_palette(template_path, override_table)
                except (FileNotFoundError, KeyError, TypeError, ValueError) as error:
                    report(
                        self,
                        "WARNING",
                        f"Layer {index + 1} template could not be loaded: {error}",
                        logger=_LOG,
                        error=error,
                    )
                    continue
                object_generated += 1
            if object_generated:
                generated += object_generated
                report(
                    self,
                    "INFO",
                    f"Rebuilt override palettes for {material.name} on {obj.name} ({object_generated} layers).",
                    logger=_LOG,
                )
    return {"FINISHED"} if generated else {"CANCELLED"}
