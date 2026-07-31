from __future__ import annotations

from typing import Optional, Tuple

import bpy

from ....animation.rigify.mapping import DIRECTION_FORWARD

def find_pair(obj) -> Tuple[Optional[object], Optional[object]]:
    if obj is None or getattr(obj, "type", None) != "ARMATURE":
        return None, None
    source_name = obj.data.get("cp77_source_rig")
    if source_name:
        source = bpy.data.objects.get(source_name)
        if source is not None and source.type == "ARMATURE":
            rig_name = source.data.get("cp77_rigify_rig")
            rig = bpy.data.objects.get(rig_name) if rig_name else None
            return source, rig if rig is not None and rig.type == "ARMATURE" else None
    rig_name = obj.data.get("cp77_rigify_rig")
    if rig_name:
        rig = bpy.data.objects.get(rig_name)
        if rig is not None and rig.type == "ARMATURE":
            return obj, rig
    return None, None

def find_metarig(source):
    name = source.data.get("cp77_metarig") if source is not None else None
    obj = bpy.data.objects.get(name) if name else None
    return obj if obj is not None and obj.type == "ARMATURE" else None

def get_constraint_direction(source) -> str:
    if source is None or source.data is None:
        return DIRECTION_FORWARD
    return source.data.get("cp77_constraint_direction", DIRECTION_FORWARD)
