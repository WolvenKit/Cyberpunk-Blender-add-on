from __future__ import annotations

from ...assetio.paths import local_path_key
from ...assetio.values import json_array
from ...importers.entity.rigs import reconcile_existing_metarig_overlay


def _paths(owner, key) -> tuple[str, ...]:
    return tuple(str(value) for value in json_array(owner.get(key, "[]")) if value)


def reconcile_appearance_rig(collection, rig) -> None:
    """Make rig carry the base rig parts plus the overlays recorded for collection's appearance"""
    if rig is None:
        return
    base = _paths(collection, "cp77_rig_base_source_order") or _paths(
        rig, "cp77_metarig_base_source_order"
    )
    overlay = _paths(collection, "cp77_rig_overlay_source_order")
    if not overlay:
        source = _paths(collection, "cp77_rig_source_order") or _paths(
            collection, "cp77_rig_merge_order"
        )
        base_keys = {local_path_key(path) for path in base}
        overlay = tuple(
            path for path in source if local_path_key(path) not in base_keys
        )
    if base or overlay:
        reconcile_existing_metarig_overlay(rig, base, overlay)
