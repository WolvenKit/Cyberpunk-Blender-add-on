from __future__ import annotations


def active_armature(context):
    obj = getattr(context, "active_object", None)
    return obj if obj is not None and getattr(obj, "type", None) == "ARMATURE" else None


def active_action(context, armature=None):
    obj = armature or active_armature(context)
    animation_data = getattr(obj, "animation_data", None) if obj is not None else None
    return getattr(animation_data, "action", None)
