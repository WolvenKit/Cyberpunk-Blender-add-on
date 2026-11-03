from __future__ import annotations

import json

from ...assetio.values import json_array
from ...core.log import get_logger, log_once

_LOG = get_logger(__name__)

_REGISTRY_KEY = "cp77_reflection_probe_registry"
_GENERATION_KEY = "cp77_reflection_probe_generation"


def _registry_names(scene):
    return [
        str(value)
        for value in json_array(
            scene.get(_REGISTRY_KEY, "") if scene is not None else ""
        )
        if value
    ]


def _store_names(scene, names):
    if scene is None:
        return
    encoded = json.dumps(list(dict.fromkeys(names)), separators=(",", ":"))
    if str(scene.get(_REGISTRY_KEY, "") or "") != encoded:
        scene[_REGISTRY_KEY] = encoded


def is_reflection_probe(obj):
    return obj is not None and bool(obj.get("cp77_reflection_probe", False))


def register_reflection_probe(scene, obj):
    if scene is None or not is_reflection_probe(obj):
        return False
    names = _registry_names(scene)
    if obj.name not in names:
        names.append(obj.name)
        _store_names(scene, names)
    return True


def registered_reflection_probes(scene):
    names = _registry_names(scene)
    valid = []
    probes = []
    for name in names:
        obj = scene.objects.get(name) if scene is not None else None
        if not is_reflection_probe(obj):
            continue
        valid.append(name)
        probes.append(obj)
    if valid != names:
        _store_names(scene, valid)
    return tuple(probes)


def mark_registered_reflection_probes_dirty(scene):
    probes = registered_reflection_probes(scene)
    if not probes:
        return 0
    generation = int(scene.get(_GENERATION_KEY, 0) or 0) + 1
    scene[_GENERATION_KEY] = generation
    for obj in probes:
        obj["cp77_reflection_probe_generation"] = generation
        data = getattr(obj, "data", None)
        if data is not None:
            data["cp77_reflection_probe_generation"] = generation
            try:
                data.update_tag()
            except (AttributeError, ReferenceError, RuntimeError, TypeError) as error:
                log_once(
                    _LOG,
                    "DEBUG",
                    ("mark_registered_reflection_probes_dirty 1", type(error).__name__),
                    "mark registered reflection probes dirty: fell back after %s",
                    error,
                    exc_info=True,
                )
        try:
            obj.update_tag()
        except (AttributeError, ReferenceError, RuntimeError, TypeError) as error:
            log_once(
                _LOG,
                "DEBUG",
                ("mark_registered_reflection_probes_dirty 2", type(error).__name__),
                "mark registered reflection probes dirty: fell back after %s",
                error,
                exc_info=True,
            )
    return len(probes)
