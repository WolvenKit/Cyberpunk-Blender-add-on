from __future__ import annotations

import bpy

from ....animation.domain.rigify.mapping import (
    METARIG_KEY,
    RIG_ID_KEY,
    RIGIFY_RIG_ID_KEY,
    RIGIFY_RIG_KEY,
    SOURCE_RIG_KEY,
)


def _armature_named(name) -> object | None:
    obj = bpy.data.objects.get(name) if name else None
    return obj if obj is not None and obj.type == "ARMATURE" else None


def find_pair(obj) -> tuple[object | None, object | None]:
    """Resolve (source, rigify rig) from either member of a linked pair"""
    if obj is None or getattr(obj, "type", None) != "ARMATURE":
        return None, None
    source = _armature_named(obj.data.get(SOURCE_RIG_KEY))
    if source is not None:
        return source, _armature_named(source.data.get(RIGIFY_RIG_KEY))
    rig = _armature_named(obj.data.get(RIGIFY_RIG_KEY))
    if rig is not None:
        return obj, rig
    return None, None


def find_metarig(source) -> object | None:
    return _armature_named(source.data.get(METARIG_KEY)) if source is not None else None


def linked_rig_object(source) -> object | None:
    name = source.data.get(RIGIFY_RIG_KEY) if source is not None else None
    return bpy.data.objects.get(name) if name else None


def link_metadata(source, meta, rig) -> None:
    source.data[METARIG_KEY] = meta.name
    source.data[RIGIFY_RIG_KEY] = rig.name
    source.data[RIG_ID_KEY] = rig.data.get(RIGIFY_RIG_ID_KEY, "")
    meta.data[SOURCE_RIG_KEY] = source.name
    rig.data[SOURCE_RIG_KEY] = source.name


def rig_id(source, rig) -> str:
    return rig.data.get(RIGIFY_RIG_ID_KEY) or source.data.get(RIG_ID_KEY, "")


def rig_ui_operator(rig_identifier: str, suffix: str) -> str | None:
    """Return the generated rig's own pose operator id, or None when its rig UI script is not loaded"""
    attribute = f"rigify_{suffix}_{rig_identifier}"
    return f"pose.{attribute}" if hasattr(bpy.ops.pose, attribute) else None
