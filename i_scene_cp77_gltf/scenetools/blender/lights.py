from __future__ import annotations

import bpy

from ...blender.keyframes import get_action_fcurves
from ...blender.light_preview import (
    BASE_ENERGY_KEY,
    animate_flicker,
    capture_base_energy,
    configure_cycles_distribution,
    configure_static_light,
    energy_fcurves,
    set_zone_on,
)
from ...entity.domain.light_representation import light_representation
from ...importers.common.light_environment import register_environment_lights
from ...importers.common.vehicle_light_preview import set_light_energy_animation_muted

_BRIGHTNESS = "CP77 Preview Brightness"
_ENVIRONMENT_BASES = (
    "cp77_environment_base_color",
    "cp77_environment_base_exposure",
    "cp77_environment_base_volume_factor",
)


def show_lights(members, preview):
    """Show the members preview shows and hide the rest"""
    changed = {}
    for member in members:
        obj, hidden = member.obj, not preview.shows(member)
        if obj.hide_viewport != hidden or obj.hide_render != hidden:
            changed[obj.as_pointer()] = hidden
    if not changed:
        return
    objects = bpy.data.objects
    targets = [
        (position, changed[obj.as_pointer()])
        for position, obj in enumerate(objects)
        if obj.as_pointer() in changed
    ]
    for name in ("hide_viewport", "hide_render"):
        flags = [False] * len(objects)
        objects.foreach_get(name, flags)
        for position, hidden in targets:
            flags[position] = hidden
        objects.foreach_set(name, flags)
    # foreach_set leaves the view layers unsynced; one ordinary write syncs them for every object.
    synced = objects[targets[0][0]]
    synced.hide_viewport = synced.hide_viewport


def _base_energy(obj):
    """A light's energy at full brightness"""
    if BASE_ENERGY_KEY not in obj:
        capture_base_energy(obj)
    return float(obj[BASE_ENERGY_KEY])


def _scale_flicker(light, factor):
    """Scale a flickering light's animated energy by factor without rewriting its keys"""
    for fcurve in energy_fcurves(light):
        modifier = next(
            (
                item
                for item in fcurve.modifiers
                if item.type == "ENVELOPE" and item.name == _BRIGHTNESS
            ),
            None,
        )
        if factor == 1.0:
            if modifier is not None:
                fcurve.modifiers.remove(modifier)
            continue
        if modifier is None:
            modifier = fcurve.modifiers.new(type="ENVELOPE")
            modifier.name = _BRIGHTNESS
            modifier.reference_value, modifier.default_min, modifier.default_max = (
                0.0,
                0.0,
                1.0,
            )
            modifier.control_points.add(0.0)
        point = modifier.control_points[0]
        point.min, point.max = 0.0, factor


def light_up(members, preview):
    """Give each member's light its preview energy"""
    for member in members:
        light = member.obj.data
        lit = preview.lit(member)
        factor = preview.factor(member)
        energy = _base_energy(member.obj) * factor if lit else 0.0
        if light.energy != energy:
            light.energy = energy
        set_light_energy_animation_muted(light, not lit)
        _scale_flicker(light, factor)


def switch_zones(zones, on):
    """Switch each light zone of (zone, objects) on or off"""
    for zone, objects in zones:
        set_zone_on(objects, zone, on)


def _remove_flicker(light):
    """Take out the energy keys a light's flicker made"""
    animation_data = light.animation_data
    fcurves = (
        get_action_fcurves(animation_data.action, light)
        if animation_data is not None
        else None
    )
    for fcurve in energy_fcurves(light):
        fcurves.remove(fcurve)


def rebuild_static_light(samples, data, seed, scene):
    """Build a sector light's Blender lights again from its node data"""
    blender_type, representation = light_representation(data)
    for obj in samples:
        if obj.data.type != blender_type:
            obj.data.type = blender_type
        light = obj.data
        _remove_flicker(light)
        radius, _source_radius = configure_static_light(
            light, data, representation, len(samples)
        )
        configure_cycles_distribution(
            light,
            data.get("attenuation", ""),
            radius,
            bool(data.get("clampAttenuation", False)),
            ies_path=obj.get("cp77_resolved_ies_profile", ""),
            projection_path=obj.get("cp77_resolved_projection_texture", ""),
        )
        obj["cp77_effective_radius"] = radius
        obj["cp77_proxy_representation"] = representation
        capture_base_energy(obj)
        animate_flicker(light, data.get("flicker"), seed)
        for key in _ENVIRONMENT_BASES:
            obj.pop(key, None)
    register_environment_lights(scene, samples)
