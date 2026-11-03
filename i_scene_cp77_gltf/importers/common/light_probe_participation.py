from __future__ import annotations

from .reflection_probe_semantics import source_bool


def apply_probe_capture_participation(obj, data):
    enabled = source_bool(data, "useInEnvProbes", True)
    obj["useInEnvProbes"] = enabled
    if hasattr(obj, "hide_probe_sphere"):
        obj.hide_probe_sphere = not enabled
    return enabled
