from __future__ import annotations

from ....assetio.values import cname_or_empty
from .topology import has_link


def sk_anim_data(node, *, one_shot: bool):
    data = {
        "animation": cname_or_empty(node.get("animation")),
        "convertToAdditive": bool(node.get("convertToAdditive", False)),
        "clipFront": float(node.get("clipFront", 0.0) or 0.0),
        "clipEnd": float(node.get("clipEnd", 0.0) or 0.0),
        "isLooped": bool(node.get("isLooped", False)),
        "phase": cname_or_empty(node.get("phase")),
        "animLoopEventName": cname_or_empty(node.get("animLoopEventName")),
        "fireAnimLoopEvent": bool(node.get("fireAnimLoopEvent", False)),
        "collectEvents": bool(node.get("collectEvents", True)),
        "hasSpeedLink": has_link(node, "speedLink"),
        "hasDurationLink": has_link(node, "durationLink"),
        "pushDataByTag": cname_or_empty(node.get("pushDataByTag")),
    }
    if one_shot:
        data = {
            **data,
            "isLooped": False,
            "oneShot": True,
            "blendIn": max(0.0, float(node.get("blendIn", 0.0) or 0.0)),
            "blendOut": max(0.0, float(node.get("blendOut", 0.0) or 0.0)),
        }
    return data
