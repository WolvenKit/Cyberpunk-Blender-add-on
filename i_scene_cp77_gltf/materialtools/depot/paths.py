from __future__ import annotations

import os

from ...assetio.catalog import (
    ResourceKind,
    resource_spec_for_cooked_suffix,
)
from ...assetio.files import read_prefix
from ...assetio.index import export_candidates
from ...assetio.paths import (
    DepotPath,
    LocalPath,
    relative_local_path,
    split_source_tree_root,
    strip_json_suffix,
)
from ...assetio.resolver import full_suffix
from ...assetio.values import cname_text
from ...core.log import debug_exception, get_logger
from ..application.options import (
    MATERIAL_TEMPLATE_COOKED_EXTENSION,
    MATERIAL_TEMPLATE_EXTENSION,
    MULTILAYER_TEMPLATE_EXTENSION,
)

_LOG = get_logger(__name__)

_RESOURCE_ROOTS = frozenset({"base", "engine", "ep1"})
_MISSING = object()
_PARAMETER_VALUE_KEYS = (
    "texture",
    "scalar",
    "vector",
    "color",
    "cube",
    "gradient",
    "resource",
    "buffer",
    "value",
)
_PARAMETER_METADATA_KEYS = frozenset(
    {
        "$type",
        "parameterName",
        "register",
        "min",
        "max",
    }
)


def plain_material_value(value):
    if isinstance(value, dict):
        if "DepotPath" in value:
            return plain_material_value(value["DepotPath"])
        if "$value" in value:
            return plain_material_value(value["$value"])
        if "Elements" in value and len(value) <= 2:
            return [plain_material_value(item) for item in value["Elements"]]
        return {
            key: plain_material_value(item)
            for key, item in value.items()
            if key != "$type"
        }
    if isinstance(value, (list, tuple)):
        return [plain_material_value(item) for item in value]
    return value


def parameter_name(data):
    value = data.get("parameterName") if isinstance(data, dict) else None
    return cname_text(value).strip()


def parameter_default(data):
    for key in _PARAMETER_VALUE_KEYS:
        if key in data:
            return plain_material_value(data[key])
    remaining = {
        key: plain_material_value(value)
        for key, value in data.items()
        if key not in _PARAMETER_METADATA_KEYS
    }
    if not remaining:
        return _MISSING
    if len(remaining) == 1:
        return next(iter(remaining.values()))
    return remaining


def template_defaults(root):
    defaults = {}
    parameters = root.get("parameters", {}) if isinstance(root, dict) else {}
    elements = parameters.get("Elements", ()) if isinstance(parameters, dict) else ()

    def visit(value):
        if isinstance(value, dict):
            data = value.get("Data")
            name = parameter_name(data) if isinstance(data, dict) else ""
            if name:
                default = parameter_default(data)
                if default is not _MISSING:
                    defaults[name] = default
                return
            for child in value.values():
                visit(child)
        elif isinstance(value, (list, tuple)):
            for child in value:
                visit(child)

    visit(elements)
    return defaults


def _depot_display_path(value):
    return DepotPath.from_value(value).value.replace("/", "\\")


def relative_to_root(path, root):
    if not path or not root:
        return ""
    relative = relative_local_path(path, root)
    if not relative:
        return ""
    return _depot_display_path(strip_json_suffix(relative))


def game_path_from_local_path(path):
    local = LocalPath.from_value(path).value
    source_root, source_relative = split_source_tree_root(local, "raw")
    if source_root and source_relative:
        return _depot_display_path(strip_json_suffix(source_relative))

    _archive_root, archive_relative = split_source_tree_root(local, "archive")
    if archive_relative:
        return _depot_display_path(strip_json_suffix(archive_relative))

    value = strip_json_suffix(local).replace("\\", "/")
    parts = value.split("/")
    for index, part in enumerate(parts):
        if part.casefold() in _RESOURCE_ROOTS:
            return _depot_display_path("/".join(parts[index:]))
    return _depot_display_path(os.path.basename(value))


def template_game_path(filepath, payload, depot_root):
    relative = relative_to_root(filepath, depot_root)
    relative_root = relative.split("\\", 1)[0].casefold() if relative else ""
    if relative_root in _RESOURCE_ROOTS:
        return relative
    header = payload.get("Header", {}) if isinstance(payload, dict) else {}
    archive_path = header.get("ArchiveFileName", "") if isinstance(header, dict) else ""
    return game_path_from_local_path(archive_path or filepath)


def template_name(root, filepath):
    value = root.get("name") if isinstance(root, dict) else None
    name = cname_text(value).strip()
    if name:
        return name
    filename = os.path.basename(strip_json_suffix(filepath))
    suffix = MATERIAL_TEMPLATE_COOKED_EXTENSION
    return (
        filename[: -len(suffix)] if filename.casefold().endswith(suffix) else filename
    )


def resolve_template_json_path(filepath):
    path = LocalPath.from_value(filepath).value
    suffix = full_suffix(path)
    if suffix == MATERIAL_TEMPLATE_EXTENSION:
        return path

    spec = resource_spec_for_cooked_suffix(suffix)
    if spec is None or spec.kind is not ResourceKind.MATERIAL_TEMPLATE:
        raise ValueError("Select a WolvenKit .mt.json export or its source .mt file.")

    for candidate in export_candidates(path, (MATERIAL_TEMPLATE_EXTENSION,)):
        exported = LocalPath.from_value(candidate).value
        if os.path.isfile(exported):
            return exported
    try:
        if read_prefix(path, 64).lstrip().startswith(b"{"):
            return path
    except OSError:
        debug_exception(
            _LOG, "Could not read %s; it is not taken as template JSON", path
        )
    raise ValueError(
        "The selected .mt is a binary game resource. Export it to .mt.json with WolvenKit first."
    )


def resolve_multilayer_template_json_path(filepath):
    path = LocalPath.from_value(filepath).value
    if full_suffix(path) != MULTILAYER_TEMPLATE_EXTENSION or not os.path.isfile(path):
        raise ValueError("Select an exported .mltemplate.json file.")
    return path


def infer_depot_root(filepath):
    path = LocalPath.from_value(filepath).value
    source_root, source_relative = split_source_tree_root(path, "raw")
    if source_root and source_relative:
        return source_root

    normalized = path.replace("\\", "/")
    parts = normalized.split("/")
    for index, part in enumerate(parts):
        if part.casefold() in _RESOURCE_ROOTS:
            root = "/".join(parts[:index])
            return LocalPath.from_value(root).value if root else ""
    return ""
