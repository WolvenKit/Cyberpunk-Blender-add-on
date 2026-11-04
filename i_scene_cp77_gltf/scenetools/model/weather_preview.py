from __future__ import annotations

import math

from ...assetio.paths import depot_path_key
from ...bartmoss.quaternion import shortest_rotation_scalar_xyzw
from ...bartmoss.scalar import clamp01, luminance, smoothstep_scalar
from .solver import solve

RAIN_EFFECT = r"base\fx\environment\weather\clear_weather\w_rain_effect.effect"


def rain_effect_active(weather_sample) -> bool:
    return (
        depot_path_key(weather_sample.effect).removesuffix(".json")
        == depot_path_key(RAIN_EFFECT).removesuffix(".json")
        and float(weather_sample.rain.intensity) > 0.001
    )


def day_factor(sample) -> float:
    """1 by day and 0 by night, blending while the sun is within about 3 degrees of the horizon"""
    return smoothstep_scalar(-0.05, 0.05, float(sample.sun_direction[2]))


def _card_light(sample):
    """The sun while it is up, the moon while it is down, and the skylight"""
    sun_up = day_factor(sample)
    return tuple(
        sun_up * float(sun) + (1.0 - sun_up) * float(moon) + float(sky)
        for sun, moon, sky in zip(
            sample.sun_source_rgb, sample.moon_source_rgb, sample.skylight_source_rgb
        )
    )


def weather_light(sample):
    """RGBA the rain and high-cloud previews glow with"""
    noon = luminance(_card_light(solve(12.0, sample.weather)))
    if noon <= 1.0e-8:
        return (1.0, 1.0, 1.0, 1.0)
    return tuple(max(0.0, value / noon) for value in _card_light(sample)) + (1.0,)


def rain_intensity(active, weather_sample) -> float:
    return clamp01(float(weather_sample.rain.intensity)) if active else 0.0


def rain_tint(sample, weather_sample):
    """Rain colour mixing fog albedo with the skylight, peak-normalised"""
    sky = tuple(max(0.0, float(value)) for value in sample.skylight_source_rgb)
    fog_rgba = weather_sample.fog.albedo_rgba
    fog = tuple(
        max(0.0, float(fog_rgba[index]) * max(float(fog_rgba[3]), 0.0))
        for index in range(3)
    )
    rgb = tuple(0.65 * fog[index] + 0.35 * sky[index] for index in range(3))
    peak = max(rgb) if rgb else 0.0
    if peak <= 1.0e-8:
        return (0.68, 0.76, 0.95, 1.0)
    return tuple(min(1.0, value / peak) for value in rgb) + (1.0,)


def rain_flow(weather_sample, wind_skew):
    """The rotation (wxyz) leaning the rain field's +Z away from the horizontal wind"""
    direction = tuple(float(value) for value in weather_sample.wind.direction[:2])
    horizontal_x, horizontal_y = direction
    length_squared = horizontal_x * horizontal_x + horizontal_y * horizontal_y
    if length_squared > 1.0e-10:
        length = math.sqrt(length_squared)
        horizontal_x, horizontal_y = horizontal_x / length, horizontal_y / length
    strength = (
        max(0.0, float(weather_sample.wind.strength))
        if weather_sample.wind.enabled
        else 0.0
    )
    tilt = min(0.45, strength * float(wind_skew))
    x, y, z, w = shortest_rotation_scalar_xyzw(
        (0.0, 0.0, 1.0),
        (-horizontal_x * tilt, -horizontal_y * tilt, 1.0),
    )
    return (w, x, y, z)
