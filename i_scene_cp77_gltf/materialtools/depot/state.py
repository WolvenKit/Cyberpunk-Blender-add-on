import bpy

from ...assetio.catalog import (
    ResourceKind,
    resource_export_for_suffix,
    resource_spec_for_cooked_suffix,
)
from ...assetio.paths import LocalPath
from ...assetio.resolver import full_suffix
from ...core.addon_identity import get_addon_preferences
from ...core.log import get_logger, log_once

_LOG = get_logger(__name__)

_INFERRED_DEPOT_COUNT = -1
_INFERRED_DEPOT_PATH = ""


def clear_depot_state_cache():
    global _INFERRED_DEPOT_COUNT, _INFERRED_DEPOT_PATH
    _INFERRED_DEPOT_COUNT = -1
    _INFERRED_DEPOT_PATH = ""


def _material_depot_path(material):
    if material is None:
        return ""
    try:
        value = str(material.get("DepotPath", "") or "").strip()
    except (AttributeError, ReferenceError, TypeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_material_depot_path", type(error).__name__),
            "material depot path: fell back after %s",
            error,
            exc_info=True,
        )
        return ""
    return LocalPath.from_value(value).value if value else ""


def inferred_material_depot_path(context=None):
    global _INFERRED_DEPOT_COUNT, _INFERRED_DEPOT_PATH
    context = context or bpy.context
    active_object = getattr(context, "active_object", None)
    active_material = getattr(active_object, "active_material", None)
    path = _material_depot_path(active_material)
    if path:
        _INFERRED_DEPOT_COUNT = len(bpy.data.materials)
        _INFERRED_DEPOT_PATH = path
        return path

    material_count = len(bpy.data.materials)
    if material_count == _INFERRED_DEPOT_COUNT:
        return _INFERRED_DEPOT_PATH

    inferred = ""
    for material in bpy.data.materials:
        inferred = _material_depot_path(material)
        if inferred:
            break
    _INFERRED_DEPOT_COUNT = material_count
    _INFERRED_DEPOT_PATH = inferred
    return inferred


def configured_material_depot_path(context=None):
    preferences = get_addon_preferences(context, required=False)
    if preferences is None:
        return ""
    value = str(getattr(preferences, "depotfolder_path", "") or "").strip()
    return LocalPath.from_value(value).value if value else ""


def get_material_depot_path(self):
    stored = str(self.get("_material_depot_path", "") or "")
    return stored or inferred_material_depot_path() or configured_material_depot_path()


def set_material_depot_path(self, value):
    self["_material_depot_path"] = LocalPath.from_value(value).value if value else ""


def ensure_material_depot_path(context, props=None):
    props = props or context.scene.cp77_ml_props
    value = str(getattr(props, "material_depot_path", "") or "").strip()
    current = LocalPath.from_value(value).value if value else ""
    if current:
        return current
    inferred = inferred_material_depot_path(context) or configured_material_depot_path(
        context
    )
    if inferred:
        props.material_depot_path = inferred
    return inferred


def is_multilayer_template_palette(palette):
    try:
        path = str(palette.get("MLTemplatePath", "") or "").strip()
    except (AttributeError, ReferenceError, TypeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("is_multilayer_template_palette", type(error).__name__),
            "is multilayer template palette: fell back after %s",
            error,
            exc_info=True,
        )
        return False
    suffix = full_suffix(path)
    exported = resource_export_for_suffix(suffix)
    if exported is not None:
        return exported[0].kind is ResourceKind.MLTEMPLATE
    spec = resource_spec_for_cooked_suffix(suffix)
    return spec is not None and spec.kind is ResourceKind.MLTEMPLATE


def get_depot_template_index(self):
    palette = self.depot_template
    return bpy.data.palettes.find(palette.name) if palette is not None else -1


def set_depot_template_index(self, value):
    palettes = bpy.data.palettes
    self.depot_template = palettes[value] if 0 <= value < len(palettes) else None


def selected_template_palette(props):
    palette = getattr(props, "depot_template", None) if props is not None else None
    return (
        palette
        if palette is not None and is_multilayer_template_palette(palette)
        else None
    )


def sync_palette_index(props, palette):
    if props is None or palette is None or not is_multilayer_template_palette(palette):
        return False
    if props.depot_template != palette:
        props.depot_template = palette
    return True
