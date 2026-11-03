from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache

from ...bartmoss.celestial import (
    DAY_HOURS,
    body_horizon_coordinates,
    direction_from,
    pole_direction,
    wrap_hour,
)
from ...bartmoss.scalar import clamp_scalar, luminance
from ..resources.environment import layered_block
from .color import hdr_rgb
from .curves import curve_color, curve_scalar, curve_text, first_curve_value
from .environment import (
    MOON_COLOR_SCALE,
    SEASON_DECLINATION_DEGREES,
    SKY_COLOR_SCALE,
    SUN_COLOR_SCALE,
)

DEFAULT_SEASON = "ETOYS_Spring"
MOON_HOUR_OFFSET = 12.0


def season_declination(season) -> float:
    """Solar declination in degrees for a REDengine season name"""
    return SEASON_DECLINATION_DEGREES.get(
        str(season),
        SEASON_DECLINATION_DEGREES[DEFAULT_SEASON],
    )


def _resolve_season(light_table):
    return str(
        first_curve_value(light_table.get("season", DEFAULT_SEASON), DEFAULT_SEASON)
    )


def _resolve_textures(atmosphere):
    return {
        "galaxyTexture": curve_text(atmosphere, "galaxyTexture", 0.0),
        "moonTexture": curve_text(atmosphere, "moonTexture", 0.0),
        "starMapTexture": curve_text(atmosphere, "starMapTexture", 0.0),
    }


@dataclass(slots=True, frozen=True)
class EnvironmentSample:
    hour: float
    weather: str | None
    latitude: float
    season: str
    sun_rotation_offset: float
    sun_direction: tuple[float, float, float]
    moon_direction: tuple[float, float, float]
    up_direction: tuple[float, float, float]
    sun_rgba: tuple[float, float, float, float]
    moon_rgba: tuple[float, float, float, float]
    atmosphere_sun_rgba: tuple[float, float, float, float]
    atmosphere_moon_rgba: tuple[float, float, float, float]
    skydome_rgba: tuple[float, float, float, float]
    skylight_rgba: tuple[float, float, float, float]
    specular_tint_rgba: tuple[float, float, float, float]
    ground_reflectance_rgba: tuple[float, float, float, float]
    artistic_darkening_rgba: tuple[float, float, float, float]
    sun_source_rgb: tuple[float, float, float]
    moon_source_rgb: tuple[float, float, float]
    atmosphere_sun_source_rgb: tuple[float, float, float]
    atmosphere_moon_source_rgb: tuple[float, float, float]
    skydome_source_rgb: tuple[float, float, float]
    skylight_source_rgb: tuple[float, float, float]
    dominant: str
    dominant_direction: tuple[float, float, float]
    dominant_source_rgb: tuple[float, float, float]
    sun_angle: float
    moon_angle: float
    turbidity: float
    lut_turbidity: float
    sun_min_z: float
    horizon_min_z: float
    horizon_falloff: float
    sun_falloff: float
    moon_falloff: float
    ray_traced_sun_shadow_range: float
    moon_glow_intensity: float
    moon_glow_falloff: float
    galaxy_intensity: float
    star_map_intensity: float
    star_map_bright_scale: float
    star_map_dim_scale: float
    star_map_constellation_scale: float
    star_corner_luminance_fix: float
    artistic_darkening_start: float
    artistic_darkening_end: float
    artistic_darkening_exponent: float
    probe_color_override_horizon_rgba: tuple[float, float, float, float]
    probe_alpha_override_horizon: float
    probe_color_override_zenith_rgba: tuple[float, float, float, float]
    probe_alpha_override_zenith: float
    textures: dict[str, str]

    @property
    def ground_albedo(self):
        return clamp_scalar(luminance(hdr_rgb(self.ground_reflectance_rgba)), 0.0, 1.0)


@lru_cache(maxsize=2048)
def solve(hour, weather=None, latitude=None, season=None):
    hour = wrap_hour(hour)
    light = layered_block("LightAreaSettings", weather)
    atmosphere = layered_block("AtmosphereAreaSettings", weather)

    if latitude is None:
        latitude = curve_scalar(light, "latitude", hour, 0.0)
    if season is None:
        season = _resolve_season(light)

    sun_yaw = curve_scalar(light, "sunRotationOffset", hour, 0.0)
    moon_yaw = curve_scalar(light, "moonRotationOffset", hour, 0.0)
    sun_direction = direction_from(
        *body_horizon_coordinates(hour, latitude, season_declination(season)),
        sun_yaw,
    )
    moon_direction = direction_from(
        *body_horizon_coordinates(
            hour + MOON_HOUR_OFFSET, latitude, season_declination(DEFAULT_SEASON)
        ),
        moon_yaw,
    )

    sun_rgba = curve_color(light, "sunColor", hour, (1.0, 1.0, 1.0, 1.0))
    moon_rgba = curve_color(light, "moonColor", hour, (1.0, 1.0, 1.0, 1.0))
    atmosphere_sun_rgba = curve_color(
        atmosphere, "sunColor", hour, (1.0, 1.0, 1.0, 100.0)
    )
    atmosphere_moon_rgba = curve_color(
        atmosphere, "moonColor", hour, (1.0, 1.0, 1.0, 1.0)
    )
    skydome_rgba = curve_color(atmosphere, "skydomeColor", hour, (1.0, 1.0, 1.0, 100.0))
    skylight_rgba = curve_color(
        atmosphere, "skylightColor", hour, (1.0, 1.0, 1.0, 100.0)
    )
    specular_tint_rgba = curve_color(light, "specularTint", hour, (1.0, 1.0, 1.0, 1.0))
    ground_reflectance_rgba = curve_color(
        atmosphere, "groundReflectance", hour, (1.0, 1.0, 1.0, 0.1)
    )
    artistic_darkening_rgba = curve_color(
        atmosphere, "artisticDarkeningColor", hour, (1.0, 1.0, 1.0, 1.0)
    )

    sun_source_rgb = hdr_rgb(sun_rgba, SUN_COLOR_SCALE)
    moon_source_rgb = hdr_rgb(moon_rgba, MOON_COLOR_SCALE)
    atmosphere_sun_source_rgb = hdr_rgb(atmosphere_sun_rgba)
    atmosphere_moon_source_rgb = hdr_rgb(atmosphere_moon_rgba)
    skydome_source_rgb = hdr_rgb(skydome_rgba, SKY_COLOR_SCALE)
    skylight_source_rgb = hdr_rgb(skylight_rgba, SKY_COLOR_SCALE)

    sun_luma = luminance(sun_source_rgb)
    moon_luma = luminance(moon_source_rgb)
    if sun_luma > moon_luma:
        dominant = "SUN"
        dominant_direction = sun_direction
        dominant_source_rgb = sun_source_rgb
    else:
        dominant = "MOON"
        dominant_direction = moon_direction
        dominant_source_rgb = moon_source_rgb

    return EnvironmentSample(
        hour=hour,
        weather=str(weather) if weather else None,
        latitude=float(latitude),
        season=str(season),
        sun_rotation_offset=float(sun_yaw),
        sun_direction=sun_direction,
        moon_direction=moon_direction,
        up_direction=pole_direction(hour, latitude),
        sun_rgba=sun_rgba,
        moon_rgba=moon_rgba,
        atmosphere_sun_rgba=atmosphere_sun_rgba,
        atmosphere_moon_rgba=atmosphere_moon_rgba,
        skydome_rgba=skydome_rgba,
        skylight_rgba=skylight_rgba,
        specular_tint_rgba=specular_tint_rgba,
        ground_reflectance_rgba=ground_reflectance_rgba,
        artistic_darkening_rgba=artistic_darkening_rgba,
        sun_source_rgb=sun_source_rgb,
        moon_source_rgb=moon_source_rgb,
        atmosphere_sun_source_rgb=atmosphere_sun_source_rgb,
        atmosphere_moon_source_rgb=atmosphere_moon_source_rgb,
        skydome_source_rgb=skydome_source_rgb,
        skylight_source_rgb=skylight_source_rgb,
        dominant=dominant,
        dominant_direction=dominant_direction,
        dominant_source_rgb=dominant_source_rgb,
        sun_angle=max(0.0, curve_scalar(light, "sunSize", hour)),
        moon_angle=max(0.0, curve_scalar(light, "moonSize", hour)),
        turbidity=clamp_scalar(curve_scalar(atmosphere, "turbidity", hour), 1.0, 10.0),
        lut_turbidity=clamp_scalar(
            curve_scalar(atmosphere, "lutTurbidity", hour), 1.0, 10.0
        ),
        sun_min_z=curve_scalar(atmosphere, "sunMinZ", hour),
        horizon_min_z=curve_scalar(atmosphere, "horizonMinZ", hour),
        horizon_falloff=curve_scalar(atmosphere, "horizonFalloff", hour),
        sun_falloff=curve_scalar(atmosphere, "sunFalloff", hour),
        moon_falloff=curve_scalar(atmosphere, "moonFalloff", hour),
        ray_traced_sun_shadow_range=curve_scalar(
            atmosphere,
            "rayTracedSunShadowRange",
            hour,
        ),
        moon_glow_intensity=curve_scalar(atmosphere, "moonGlowIntensity", hour),
        moon_glow_falloff=max(
            0.0,
            curve_scalar(atmosphere, "moonGlowFalloff", hour),
        ),
        galaxy_intensity=curve_scalar(atmosphere, "galaxyIntensity", hour),
        star_map_intensity=curve_scalar(atmosphere, "starMapIntensity", hour),
        star_map_bright_scale=curve_scalar(atmosphere, "starMapBrightScale", hour),
        star_map_dim_scale=curve_scalar(atmosphere, "starMapDimScale", hour),
        star_map_constellation_scale=curve_scalar(
            atmosphere,
            "starMapConstelationsScale",
            hour,
        ),
        star_corner_luminance_fix=curve_scalar(
            atmosphere,
            "starCornerLuminanceFix",
            hour,
        ),
        artistic_darkening_start=curve_scalar(
            atmosphere,
            "artisticDarkeningStartPoint",
            hour,
        ),
        artistic_darkening_end=curve_scalar(
            atmosphere,
            "artisticDarkeningEndPoint",
            hour,
        ),
        artistic_darkening_exponent=curve_scalar(
            atmosphere,
            "artisticDarkeningExponent",
            hour,
        ),
        probe_color_override_horizon_rgba=curve_color(
            atmosphere, "probeColorOverrideHorizon", hour, (0.0, 0.0, 0.0, 0.0)
        ),
        probe_alpha_override_horizon=curve_scalar(
            atmosphere, "probeAlphaOverrideHorizon", hour, 0.0
        ),
        probe_color_override_zenith_rgba=curve_color(
            atmosphere, "probeColorOverrideZenith", hour, (0.0, 0.0, 0.0, 0.0)
        ),
        probe_alpha_override_zenith=curve_scalar(
            atmosphere, "probeAlphaOverrideZenith", hour, 0.0
        ),
        textures=_resolve_textures(atmosphere),
    )


@lru_cache(maxsize=64)
def sunrise_sunset(weather=None, latitude=None, season=None, step=1.0 / 60.0):
    """First and last sampled hours with the sun above the horizon"""
    light = layered_block("LightAreaSettings", weather)
    declination = season_declination(
        _resolve_season(light) if season is None else season
    )
    first = None
    last = None
    hour = 0.0
    while hour < DAY_HOURS:
        sample_hour = wrap_hour(hour)
        sample_latitude = (
            curve_scalar(light, "latitude", sample_hour, 0.0)
            if latitude is None
            else latitude
        )
        elevation, _ = body_horizon_coordinates(
            sample_hour, sample_latitude, declination
        )
        if math.sin(elevation) > 0.0:
            if first is None:
                first = hour
            last = hour
        hour += step
    return first, last
