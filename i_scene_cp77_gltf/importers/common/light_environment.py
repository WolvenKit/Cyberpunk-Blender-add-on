from __future__ import annotations

import json
import math

from mathutils import Vector

from ...assetio.values import json_array
from ...bartmoss.scalar import luminance

_REGISTRY_KEY = "cp77_environment_light_registry"
_SCENE_LIGHT_REGISTRY_KEY = "cp77_scene_light_registry"
_EPSILON = 1e-8


def _registry_names(scene, key):
    return [
        str(value)
        for value in json_array(scene.get(key, "") if scene is not None else "")
        if value
    ]


def _store_registry_names(scene, key, names):
    if scene is None:
        return
    encoded = json.dumps(
        list(dict.fromkeys(str(name) for name in names if name)),
        separators=(",", ":"),
    )
    if str(scene.get(key, "") or "") != encoded:
        scene[key] = encoded


def _base_color(obj):
    stored = obj.get("cp77_environment_base_color")
    if stored is not None and len(stored) >= 3:
        return tuple(float(stored[index]) for index in range(3))
    color = tuple(float(value) for value in obj.data.color[:3])
    obj["cp77_environment_base_color"] = color
    return color


def _base_exposure(obj):
    if "cp77_environment_base_exposure" in obj:
        return float(obj["cp77_environment_base_exposure"])
    value = float(getattr(obj.data, "exposure", 0.0))
    obj["cp77_environment_base_exposure"] = value
    return value


def _base_volume_factor(obj):
    if "cp77_environment_base_volume_factor" in obj:
        return float(obj["cp77_environment_base_volume_factor"])
    value = float(getattr(obj.data, "volume_factor", 1.0))
    obj["cp77_environment_base_volume_factor"] = value
    return value


def _group_name(obj):
    return str(obj.get("group", "LG_Group0") or "LG_Group0")


def _group_index(obj):
    group = _group_name(obj)
    if group.startswith("LG_Group"):
        try:
            return max(0, min(7, int(group.removeprefix("LG_Group"))))
        except ValueError:
            pass
    return 0


def is_environment_light(obj):
    if obj is None or getattr(obj, "type", None) != "LIGHT":
        return False
    group = str(obj.get("envColorGroup", "") or "")
    return group not in {"", "ECG_Default"}


def is_scene_light(obj):
    if obj is None or getattr(obj, "type", None) != "LIGHT":
        return False
    return any(
        key in obj for key in ("group", "envColorGroup", "cp77_type", "cp77_node_type")
    )


def register_environment_lights(scene, objects):
    if scene is None:
        return 0

    scene_names = _registry_names(scene, _SCENE_LIGHT_REGISTRY_KEY)
    env_names = _registry_names(scene, _REGISTRY_KEY)
    scene_seen = set(scene_names)
    env_seen = set(env_names)
    environment_count = 0

    for obj in objects:
        if obj is None or getattr(obj, "type", None) != "LIGHT":
            continue
        if is_scene_light(obj):
            _base_color(obj)
            _base_exposure(obj)
            _base_volume_factor(obj)
            if obj.name not in scene_seen:
                scene_seen.add(obj.name)
                scene_names.append(obj.name)
        if not is_environment_light(obj):
            continue
        environment_count += 1
        if obj.name not in env_seen:
            env_seen.add(obj.name)
            env_names.append(obj.name)

    _store_registry_names(scene, _SCENE_LIGHT_REGISTRY_KEY, scene_names)
    _store_registry_names(scene, _REGISTRY_KEY, env_names)
    return environment_count


def rebuild_environment_light_registry(scene):
    env_names = []
    scene_names = []
    for obj in scene.objects:
        if not is_scene_light(obj):
            continue
        _base_color(obj)
        _base_exposure(obj)
        _base_volume_factor(obj)
        scene_names.append(obj.name)
        if is_environment_light(obj):
            env_names.append(obj.name)
    _store_registry_names(scene, _SCENE_LIGHT_REGISTRY_KEY, scene_names)
    _store_registry_names(scene, _REGISTRY_KEY, env_names)
    return len(scene_names)


def _registered(scene, key, predicate):
    names = _registry_names(scene, key)
    valid = []
    objects = []
    for name in names:
        obj = scene.objects.get(name) if scene is not None else None
        if obj is None or not predicate(obj):
            continue
        valid.append(name)
        objects.append(obj)
    if valid != names:
        _store_registry_names(scene, key, valid)
    return tuple(objects)


def _source_forward(obj):
    matrix = obj.matrix_world.to_3x3()
    if getattr(obj.data, "type", "") in {"SPOT", "AREA", "SUN"}:
        forward = -(matrix @ Vector((0.0, 0.0, 1.0)))
    else:
        forward = -(matrix @ Vector((0.0, 1.0, 0.0)))
    if forward.length_squared <= _EPSILON:
        return Vector((0.0, 0.0, 1.0))
    return forward.normalized()


def _saturation(rgb, percent):
    factor = float(percent) * 0.01
    luma = luminance(rgb)
    return tuple(luma + (float(rgb[index]) - luma) * factor for index in range(3))


def _sky_group_color(sample, obj):
    rgba = sample.skylight_rgba
    magnitude = float(rgba[3])
    color = tuple(float(rgba[index]) * magnitude for index in range(3))

    forward = _source_forward(obj)
    cutoff = max(float(obj.get("portalAngleCutoff", 0.0) or 0.0), 0.0)
    if cutoff > 0.0:
        limit = math.sin(math.radians(cutoff))
        forward.z = max(forward.z, limit)
        if forward.length_squared > _EPSILON:
            forward.normalize()

    direction_weight = max(float(forward.z), 0.01)
    return tuple(value * direction_weight for value in color)


def _group_color(sample, obj):
    group = str(obj.get("envColorGroup", "ECG_Default") or "ECG_Default")
    if group == "ECG_Sky":
        return _sky_group_color(sample, obj)
    return (1.0, 1.0, 1.0)


def _normalize_rgb(rgb):
    peak = max(float(value) for value in rgb)
    if peak <= _EPSILON:
        return (0.0, 0.0, 0.0), 0.0
    if peak > 1.0:
        return tuple(max(0.0, float(value) / peak) for value in rgb), peak
    return tuple(max(0.0, float(value)) for value in rgb), 1.0


def _light_group_fade(obj, weather_sample):
    fades = getattr(getattr(weather_sample, "overrides", None), "light_group_fades", ())
    index = _group_index(obj)
    if index < len(fades):
        return max(0.0, min(1.0, float(fades[index])))
    return 1.0


def apply_environment_to_light(obj, sample, weather_sample=None):
    if not is_scene_light(obj):
        return False

    base = _base_color(obj)
    group_rgb = _group_color(sample, obj)
    combined = tuple(base[index] * group_rgb[index] for index in range(3))
    saturation = float(obj.get("colorGroupSaturation", 100.0) or 100.0)
    combined = _saturation(combined, saturation)
    normalized, hdr_scale = _normalize_rgb(combined)
    fade = _light_group_fade(obj, weather_sample)

    light = obj.data
    base_exposure = _base_exposure(obj)
    light.color = normalized
    effective_scale = hdr_scale * fade
    if hasattr(light, "exposure"):
        if effective_scale > _EPSILON:
            light.exposure = base_exposure + math.log2(effective_scale)
        else:
            light.exposure = base_exposure
            light.color = (0.0, 0.0, 0.0)

    if hasattr(light, "volume_factor"):
        fog = getattr(weather_sample, "fog", None)
        local_fog_scale = max(0.0, float(getattr(fog, "local_light_scale", 1.0)))
        light.volume_factor = _base_volume_factor(obj) * local_fog_scale
    return True


def apply_environment_to_registered_lights(scene, sample, weather_sample=None):
    updated = 0
    for obj in _registered(scene, _SCENE_LIGHT_REGISTRY_KEY, is_scene_light):
        if apply_environment_to_light(obj, sample, weather_sample):
            updated += 1
    return updated
