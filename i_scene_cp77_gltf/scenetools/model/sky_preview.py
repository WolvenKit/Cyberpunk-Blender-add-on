from __future__ import annotations

import math
from dataclasses import dataclass

from ...bartmoss.celestial import (
    direction_from,
    disc_basis,
    raise_to_min_elevation,
    sky_to_galactic_rows,
)
from .color import hdr_rgb
from .environment import SUN_COLOR_SCALE

DIRECTIONAL_PREVIEW_SCALE = 0.001


def exposure_scale(preview_exposure) -> float:
    return math.exp2(float(preview_exposure))


@dataclass(frozen=True, slots=True)
class GlobalLightState:
    source_rgb: tuple[float, float, float]
    direction: tuple[float, float, float]
    angle: float


@dataclass(frozen=True, slots=True)
class DirectionalLightValues:
    color: tuple[float, float, float]
    energy: float


def global_light_state(sample, weather_sample) -> GlobalLightState:
    """The light the global sun lamps preview"""
    overrides = weather_sample.overrides
    if overrides.global_light_enabled:
        return GlobalLightState(
            source_rgb=tuple(
                max(0.0, float(value))
                for value in hdr_rgb(overrides.global_light_rgba, SUN_COLOR_SCALE)
            ),
            direction=direction_from(
                math.radians(float(overrides.global_light_elevation)),
                math.radians(float(overrides.global_light_azimuth)),
            ),
            angle=sample.sun_angle,
        )
    return GlobalLightState(
        source_rgb=tuple(
            max(0.0, float(value)) for value in sample.dominant_source_rgb
        ),
        direction=sample.dominant_direction,
        angle=sample.sun_angle if sample.dominant == "SUN" else sample.moon_angle,
    )


def directional_light(source_rgb, exposure) -> DirectionalLightValues:
    """Peak-normalised colour and preview energy for an HDR light source"""
    peak = max(source_rgb)
    if peak <= 1e-12:
        return DirectionalLightValues((1.0, 1.0, 1.0), 0.0)
    return DirectionalLightValues(
        tuple(value / peak for value in source_rgb),
        peak * DIRECTIONAL_PREVIEW_SCALE * exposure,
    )


def specular_source(state: GlobalLightState, sample):
    tint = hdr_rgb(sample.specular_tint_rgba)
    return tuple(
        state.source_rgb[index] * max(0.0, float(tint[index])) for index in range(3)
    )


def rgb_color(value):
    """An opaque RGBA colour from the first three components"""
    return (float(value[0]), float(value[1]), float(value[2]), 1.0)


def gray_color(value):
    """An opaque RGBA grey of the scalar"""
    scalar = float(value)
    return (scalar, scalar, scalar, 1.0)


@dataclass(frozen=True, slots=True)
class WorldValues:
    sun_direction: tuple[float, float, float]
    turbidity: float
    lut_turbidity: float
    ground_albedo: float
    visible_tint: tuple[float, float, float, float]
    visible_magnitude: tuple[float, float, float, float]
    lighting_tint: tuple[float, float, float, float]
    lighting_magnitude: tuple[float, float, float, float]
    star_corner_near: float
    star_corner_far: float
    star_dim_scale: float
    star_bright_scale: float
    star_constellation_scale: float
    star_scale: float
    galaxy_scale: float
    galactic_rows: tuple[tuple[float, float, float], ...]
    moon_tint: tuple[float, float, float, float]
    moon_direction: tuple[float, float, float]
    moon_tangent: tuple[float, float, float]
    moon_bitangent: tuple[float, float, float]
    moon_diameter_scale: float
    moon_glow_power: float
    moon_glow_scale: float
    moon_glow_tint: tuple[float, float, float, float]
    ambient_enabled: float
    ambient_faces: tuple[tuple[float, float, float, float], ...]
    exposure: float


def world_values(sample, weather_sample, exposure) -> WorldValues:
    corner_fix = float(sample.star_corner_luminance_fix)
    moon_tangent, moon_bitangent = disc_basis(
        sample.moon_direction, sample.up_direction
    )
    diameter_scale = max(2.0 * math.sin(max(sample.moon_angle, 1e-6) * 0.5), 1e-6)
    overrides = weather_sample.overrides
    return WorldValues(
        sun_direction=raise_to_min_elevation(
            sample.sun_direction, float(sample.sun_min_z)
        ),
        turbidity=float(sample.turbidity),
        lut_turbidity=float(sample.lut_turbidity),
        ground_albedo=float(sample.ground_albedo),
        visible_tint=rgb_color(sample.skydome_rgba[:3]),
        visible_magnitude=gray_color(sample.skydome_rgba[3]),
        lighting_tint=rgb_color(sample.skylight_rgba[:3]),
        lighting_magnitude=gray_color(sample.skylight_rgba[3]),
        star_corner_near=1.0 + corner_fix,
        star_corner_far=1.0 - corner_fix,
        star_dim_scale=float(sample.star_map_dim_scale),
        star_bright_scale=float(sample.star_map_bright_scale),
        star_constellation_scale=float(sample.star_map_constellation_scale),
        star_scale=float(sample.star_map_intensity) * 10.0,
        galaxy_scale=float(sample.galaxy_intensity),
        galactic_rows=sky_to_galactic_rows(
            sample.hour, sample.latitude, sample.sun_rotation_offset
        ),
        moon_tint=rgb_color(hdr_rgb(sample.atmosphere_moon_rgba)),
        moon_direction=sample.moon_direction,
        moon_tangent=moon_tangent,
        moon_bitangent=moon_bitangent,
        moon_diameter_scale=diameter_scale,
        moon_glow_power=max(float(sample.moon_glow_falloff), 1e-6),
        moon_glow_scale=float(sample.moon_glow_intensity)
        * max(sample.atmosphere_moon_rgba[3], 0.0),
        moon_glow_tint=rgb_color(sample.atmosphere_moon_rgba[:3]),
        ambient_enabled=1.0 if overrides.ambient_enabled else 0.0,
        ambient_faces=tuple((*hdr_rgb(rgba), 1.0) for rgba in overrides.ambient_rgba),
        exposure=exposure,
    )
