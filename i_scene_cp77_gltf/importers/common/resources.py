from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from ...datakrash import COOKED_RESOURCE_EXPORTS
from .paths import absolute_path_key

MESH_COOKED_EXTENSIONS = (".mesh", ".physicalscene", ".w2mesh")
MESH_COOKED_NAME_SUFFIXES = tuple(
    extension.lstrip(".") for extension in MESH_COOKED_EXTENSIONS
)
MESH_GLB_EXTENSIONS = tuple(
    dict.fromkeys(
        export_extension
        for cooked_extension in MESH_COOKED_EXTENSIONS
        for export_extension in COOKED_RESOURCE_EXPORTS[cooked_extension]
        if export_extension.endswith(".glb")
    )
)


def indexed_files(asset_index: Any, *extensions: str) -> tuple[str, ...]:
    """Return a stable, de-duplicated tuple from indexed extension buckets."""
    files: list[str] = []
    seen: set[str] = set()
    for extension in extensions:
        for filepath in asset_index.get_files_by_extension(extension):
            key = absolute_path_key(filepath)
            if key in seen:
                continue
            seen.add(key)
            files.append(filepath)
    return tuple(files)


def resolve_indexed_export(
    asset_index: Any,
    reference: str,
    extensions: Iterable[str],
    *,
    warn: bool = False,
) -> str:
    """Resolve one depot or exported path through ``DepotAssetIndex`` only."""
    if asset_index is None or not reference:
        return ""
    return asset_index.resolve_export(reference, tuple(extensions), warn=warn) or ""


def resolve_mesh_export(asset_index: Any, reference: str, *, warn: bool = False) -> str:
    return resolve_indexed_export(
        asset_index,
        reference,
        MESH_GLB_EXTENSIONS,
        warn=warn,
    )
