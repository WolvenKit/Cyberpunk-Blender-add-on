from __future__ import annotations

import math

from ...blender.light_preview import energy_fcurves, update_cycles_attenuation_radius
from ...entity.domain.light_representation import cosine_spot_blend


def is_vehicle_light_object(obj):
    return (
        obj is not None
        and getattr(obj, "type", None) == "LIGHT"
        and str(obj.get("cp77_type", "")) == "vehicleLightComponent"
        and not bool(obj.get("cp77_light_proxy", False))
    )


def is_vehicle_light_member(obj):
    return (
        obj is not None
        and getattr(obj, "type", None) == "LIGHT"
        and str(obj.get("cp77_type", "")) == "vehicleLightComponent"
        and (
            not bool(obj.get("cp77_light_proxy", False))
            or (obj.parent is not None and is_vehicle_light_object(obj.parent))
        )
    )


def capture_vehicle_light_base(obj):
    if not is_vehicle_light_member(obj):
        return
    light = obj.data
    if "cp77_preview_base_cutoff_distance" not in obj and hasattr(
        light, "cutoff_distance"
    ):
        obj["cp77_preview_base_cutoff_distance"] = float(light.cutoff_distance)
    if "cp77_preview_base_use_custom_distance" not in obj and hasattr(
        light, "use_custom_distance"
    ):
        obj["cp77_preview_base_use_custom_distance"] = bool(light.use_custom_distance)
    if (
        "cp77_preview_base_spot_size" not in obj
        and getattr(light, "type", "") == "SPOT"
    ):
        obj["cp77_preview_base_spot_size"] = float(light.spot_size)
        obj["cp77_preview_base_spot_blend"] = float(light.spot_blend)
    if (
        "cp77_preview_base_area_spread" not in obj
        and getattr(light, "type", "") == "AREA"
        and hasattr(light, "spread")
    ):
        obj["cp77_preview_base_area_spread"] = float(light.spread)
    if "cp77_preview_base_delta_rotation" not in obj:
        obj["cp77_preview_base_delta_rotation"] = tuple(
            float(value) for value in obj.delta_rotation_euler
        )


def set_light_energy_animation_muted(light, muted):
    changed = False
    for fcurve in energy_fcurves(light):
        if hasattr(fcurve, "mute"):
            fcurve.mute = bool(muted)
            changed = True
    return changed


def restore_base_geometry(obj):
    """Give a vehicle light back the reach, cone and aim capture_vehicle_light_base kept"""
    light = obj.data
    if (
        hasattr(light, "use_custom_distance")
        and "cp77_preview_base_use_custom_distance" in obj
    ):
        light.use_custom_distance = bool(obj["cp77_preview_base_use_custom_distance"])
    if hasattr(light, "cutoff_distance") and "cp77_preview_base_cutoff_distance" in obj:
        light.cutoff_distance = float(obj["cp77_preview_base_cutoff_distance"])
        update_cycles_attenuation_radius(light, light.cutoff_distance)
    if getattr(light, "type", "") == "SPOT":
        if "cp77_preview_base_spot_size" in obj:
            light.spot_size = float(obj["cp77_preview_base_spot_size"])
        if "cp77_preview_base_spot_blend" in obj:
            light.spot_blend = float(obj["cp77_preview_base_spot_blend"])
    if (
        getattr(light, "type", "") == "AREA"
        and hasattr(light, "spread")
        and "cp77_preview_base_area_spread" in obj
    ):
        light.spread = float(obj["cp77_preview_base_area_spread"])
    base_rotation = obj.get("cp77_preview_base_delta_rotation")
    if base_rotation is not None and len(base_rotation) >= 3:
        obj.delta_rotation_euler = tuple(
            float(base_rotation[index]) for index in range(3)
        )


def apply_high_beam_geometry(obj, *, apply_rotation=True):
    """Widen a Head light's reach and cone and raise its aim for high beam"""
    light = obj.data
    radius_multiplier = max(float(obj.get("highBeamRadiusMultiplier", 1.0) or 1.0), 0.0)
    cone_multiplier = max(float(obj.get("highBeamConeMultiplier", 1.0) or 1.0), 0.001)
    pitch = float(obj.get("highBeamPitchAngle", 0.0) or 0.0)

    base_radius = float(
        obj.get(
            "cp77_effective_radius", obj.get("cp77_preview_base_cutoff_distance", 0.0)
        )
        or 0.0
    )
    if base_radius > 0.0 and hasattr(light, "use_custom_distance"):
        light.use_custom_distance = True
        light.cutoff_distance = base_radius * radius_multiplier
        update_cycles_attenuation_radius(light, light.cutoff_distance)

    inner = float(obj.get("innerAngle", 0.0) or 0.0) * cone_multiplier
    outer = float(obj.get("outerAngle", 180.0) or 180.0) * cone_multiplier
    if getattr(light, "type", "") == "SPOT":
        proxy_outer = min(max(outer, 0.001), 179.999)
        proxy_inner = max(0.0, min(inner, proxy_outer))
        light.spot_size = math.radians(proxy_outer)
        light.spot_blend = cosine_spot_blend(proxy_inner, proxy_outer)

    base_rotation = obj.get("cp77_preview_base_delta_rotation")
    if apply_rotation and base_rotation is not None and len(base_rotation) >= 3:
        obj.delta_rotation_euler = (
            float(base_rotation[0]) + math.radians(pitch),
            float(base_rotation[1]),
            float(base_rotation[2]),
        )
