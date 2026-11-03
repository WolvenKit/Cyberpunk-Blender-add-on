from __future__ import annotations

import math
from dataclasses import dataclass

from ...bartmoss.scalar import clamp01, clamp_scalar, luminance
from .color import hdr_rgb

CLOUD_WORLD_SIZE = 4096.0
CLOUD_PREVIEW_SIZE = 16384.0
CLOUD_COVERAGE_SCALE = 1.3
CLOUD_NOISE_SCALE = 1.1
CLOUD_DETAIL_NOISE_SCALE = 0.75
CLOUD_ALTITUDE_SCALE = 600.0
CLOUD_BASE_NOISE_WORLD_SCALE = CLOUD_ALTITUDE_SCALE * CLOUD_NOISE_SCALE * 2.0
CLOUD_DETAIL_NOISE_WORLD_SCALE = CLOUD_ALTITUDE_SCALE * CLOUD_DETAIL_NOISE_SCALE / 3.0
CLOUD_COVERAGE_WORLD_SCALE = CLOUD_COVERAGE_SCALE * 35000.0
CLOUD_SIM_SECONDS_PER_GAME_HOUR = 2.0

DISTANT_PREVIEW_RANGE_CAP = 5000.0
DISTANT_TRANSMISSION_DENSITY_SCALE = math.log(2.0) ** 2
# Gap kept between a fog box lowered under the cloud deck and the deck itself.
CLOUD_DECK_CLEARANCE = 1.0


def cloud_ceiling(enabled, weather_sample):
    """Altitude of the cloud deck when the cloud preview renders, else None"""
    cloud = weather_sample.cloud
    if not cloud_preview_active(enabled, cloud):
        return None
    return float(cloud.bottom)


# A fog box is lowered under the cloud deck only where its density there has fallen below
# this fraction of the density at the anchor, so the cap changes the preview by at most that much.
NEGLIGIBLE_DENSITY_FRACTION = 0.01


def _global_fog_density_factor(fog, z):
    """Height-dependent factor of the global fog preview density at altitude z"""
    linear = clamp01(1.0 - float(z) / 1000.0)
    exponential = math.exp(
        -max(float(z) - float(fog.fog_height), 0.0) * float(fog.fog_height_falloff)
    )
    return linear * min(exponential, max(float(fog.fog_height_max_cut), 1.0))


def global_fog_ceiling(weather_sample, anchor_z, ceiling):
    """The cloud deck as a cap for the global fog box, or None when fog there is not negligible"""
    if ceiling is None:
        return None
    fog = weather_sample.fog
    at_anchor = _global_fog_density_factor(fog, anchor_z)
    at_deck = _global_fog_density_factor(fog, ceiling)
    if at_deck <= NEGLIGIBLE_DENSITY_FRACTION * at_anchor:
        return ceiling
    return None


def distant_fog_ceiling(weather_sample, anchor_z, ceiling):
    """The cloud deck as a cap for the distant fog box, or None"""
    if ceiling is None:
        return None
    distant = weather_sample.distant_fog
    rise = float(ceiling) - float(anchor_z)
    for density, falloff in (
        (distant.density, distant.height_falloff),
        (distant.density_second, distant.height_falloff_second),
    ):
        if float(density) <= 0.0:
            continue
        exponent = 0.01 * float(falloff) * rise
        if exponent <= 0.0 or 2.0**-exponent > NEGLIGIBLE_DENSITY_FRACTION:
            return None
    return ceiling


def capped_box(half_extent, anchor_z, ceiling):
    """(centre z offset, half height) of a fog box around the weather anchor"""
    half_extent = float(half_extent)
    if ceiling is None:
        return 0.0, half_extent
    top = float(ceiling) - CLOUD_DECK_CLEARANCE - float(anchor_z)
    if top <= 0.0 or top >= half_extent:
        return 0.0, half_extent
    return 0.5 * (top - half_extent), 0.5 * (top + half_extent)


def cloud_preview_active(enabled, cloud) -> bool:
    return bool(
        enabled
        and cloud.enabled
        and float(cloud.coverage) > 1.0e-5
        and float(cloud.density) > 1.0e-5
    )


def cloud_wind_offsets(sample, weather_sample):
    """Weather-map, base-noise and detail-noise offsets after wind travel up to the sample hour"""
    cloud = weather_sample.cloud
    wind = weather_sample.wind
    direction = (
        tuple(float(v) for v in wind.direction[:2]) if wind.enabled else (0.0, 0.0)
    )
    length = math.hypot(*direction)
    if length > 1.0e-8:
        direction = (direction[0] / length, direction[1] / length)
    else:
        direction = (0.0, 0.0)
    strength = max(0.0, float(wind.strength)) if wind.enabled else 0.0
    elapsed = float(sample.hour) * CLOUD_SIM_SECONDS_PER_GAME_HOUR
    travel_x = direction[0] * strength * elapsed
    travel_y = direction[1] * strength * elapsed
    base_x, base_y = cloud.coverage_offset
    coverage = (
        (float(base_x) + travel_x * cloud.coverage_wind_influence)
        / 10.0
        / CLOUD_COVERAGE_SCALE,
        (float(base_y) + travel_y * cloud.coverage_wind_influence)
        / 10.0
        / CLOUD_COVERAGE_SCALE,
    )
    noise = (
        travel_x
        * cloud.noise_wind_influence
        / 10.0
        / CLOUD_BASE_NOISE_WORLD_SCALE
        * 35000.0,
        travel_y
        * cloud.noise_wind_influence
        / 10.0
        / CLOUD_BASE_NOISE_WORLD_SCALE
        * 35000.0,
    )
    detail = (
        travel_x
        * cloud.detail_wind_influence
        / 10.0
        / CLOUD_DETAIL_NOISE_WORLD_SCALE
        * 35000.0,
        travel_y
        * cloud.detail_wind_influence
        / 10.0
        / CLOUD_DETAIL_NOISE_WORLD_SCALE
        * 35000.0,
    )
    return coverage, noise, detail


def sky_tint(sample):
    """Peak-normalised skylight colour"""
    sky = tuple(max(0.0, float(v)) for v in sample.skylight_source_rgb)
    peak = max(sky) if sky else 0.0
    return (1.0, 1.0, 1.0) if peak <= 1.0e-8 else tuple(min(1.0, v / peak) for v in sky)


@dataclass(frozen=True, slots=True)
class CloudPreview:
    active: bool
    bottom: float
    top: float
    values: dict
    tint: tuple[float, float, float]

    @property
    def center_z(self):
        return 0.5 * (self.bottom + self.top)

    @property
    def scale(self):
        return (
            CLOUD_PREVIEW_SIZE * 0.5,
            CLOUD_PREVIEW_SIZE * 0.5,
            0.5 * (self.top - self.bottom),
        )


def cloud_preview(enabled, sample, weather_sample) -> CloudPreview:
    """Slab bounds and material inputs, keyed by the material's value-node names"""
    cloud = weather_sample.cloud
    active = cloud_preview_active(enabled, cloud)
    bottom = float(cloud.bottom)
    coverage, noise, detail = cloud_wind_offsets(sample, weather_sample)
    return CloudPreview(
        active=active,
        bottom=bottom,
        top=max(bottom + 1.0, float(cloud.top)),
        values={
            "CP77 Cloud Preview Enabled": 1.0 if active else 0.0,
            "CP77 Cloud Coverage": max(0.0, float(cloud.shader_coverage)),
            "CP77 Cloud Horizon Coverage": max(0.0, float(cloud.horizon_coverage)),
            "CP77 Cloud Density": max(0.0, float(cloud.density)),
            "CP77 Cloud Ray Start": max(0.0, float(cloud.ray_start_offset)),
            "CP77 Cloud Ray Falloff": max(1.0e-4, float(cloud.ray_start_falloff)),
            "CP77 Cloud In Scatter": clamp_scalar(float(cloud.in_scatter), -0.95, 0.95),
            "CP77 Cloud Out Scatter": clamp_scalar(float(cloud.out_scatter), 0.0, 0.95),
            "CP77 Cloud In Vs Out": clamp01(float(cloud.in_vs_out_scatter)),
            "CP77 Cloud Silver Lining": clamp_scalar(
                float(cloud.silver_lining), -0.95, 0.95
            ),
            "CP77 Cloud Coverage Offset X": coverage[0],
            "CP77 Cloud Coverage Offset Y": coverage[1],
            "CP77 Cloud Noise Offset X": noise[0],
            "CP77 Cloud Noise Offset Y": noise[1],
            "CP77 Cloud Detail Offset X": detail[0],
            "CP77 Cloud Detail Offset Y": detail[1],
        },
        # A modest sky tint keeps Blender's generic volume scattering coherent with the
        # evaluated environment lighting.
        tint=sky_tint(sample),
    )


@dataclass(frozen=True, slots=True)
class GlobalFogPreview:
    active: bool
    preview_range: float
    properties: dict
    values: dict
    albedo: tuple[float, float, float]


def global_fog_preview(enabled, has_volume, weather_sample) -> GlobalFogPreview:
    fog = weather_sample.fog
    active = bool(enabled and fog.enabled and has_volume)
    preview_range = clamp_scalar(float(fog.range), 32.0, 256.0)
    return GlobalFogPreview(
        active=active,
        preview_range=preview_range,
        properties={
            "cp77_source_range": float(fog.range),
            "cp77_preview_range": preview_range,
            "cp77_fog_global_light_scale": float(fog.global_light_scale),
            "cp77_fog_local_light_scale": float(fog.local_light_scale),
            "cp77_fog_ambient_scale": float(fog.ambient_scale),
            "cp77_fog_local_ambient_scale": float(fog.local_ambient_scale),
            "cp77_fog_noise_velocity": tuple(
                float(value) for value in fog.noise_velocity
            ),
        },
        values={
            "CP77 Fog Preview Enabled": 1.0 if active else 0.0,
            "CP77 Fog Density": fog.density,
            "CP77 Fog Height": fog.fog_height,
            "CP77 Fog Height Falloff": fog.fog_height_falloff,
            "CP77 Fog Height Max Cut": max(float(fog.fog_height_max_cut), 1.0),
            "CP77 Fog Anisotropy": clamp_scalar(
                float(fog.global_light_anisotropy), -0.99, 0.99
            ),
            "CP77 Fog Absorption": max(0.0, float(fog.absorption)),
            "CP77 Fog Noise Scale": max(0.0, float(fog.noise_scale)),
            "CP77 Fog Noise Threshold": clamp_scalar(
                float(fog.noise_threshold), 0.0, 1.0
            ),
        },
        albedo=hdr_rgb(fog.albedo_rgba),
    )


@dataclass(frozen=True, slots=True)
class DistantFogPreview:
    active: bool
    preview_far: float
    properties: dict
    values: dict
    near_color: tuple[float, float, float]
    far_color: tuple[float, float, float]


def distant_fog_preview(
    enabled, has_volume, sample, weather_sample
) -> DistantFogPreview:
    distant = weather_sample.distant_fog
    active = bool(enabled and distant.enabled and has_volume)
    actual_far = max(float(distant.far_distance), float(distant.range) + 1.0, 1.0)
    preview_far = min(actual_far, DISTANT_PREVIEW_RANGE_CAP)
    dome_scale = max(
        0.1,
        min(
            4.0,
            luminance(hdr_rgb(sample.skydome_rgba))
            / max(luminance(hdr_rgb(sample.skylight_rgba)), 1.0e-4),
        ),
    )
    return DistantFogPreview(
        active=active,
        preview_far=preview_far,
        properties={
            "cp77_source_far_distance": float(distant.far_distance),
            "cp77_preview_far_distance": preview_far,
            "cp77_preview_range_cap": DISTANT_PREVIEW_RANGE_CAP,
        },
        values={
            "CP77 Distant Fog Preview Enabled": 1.0 if active else 0.0,
            "CP77 Distant Fog Start Range": max(0.0, float(distant.range)),
            "CP77 Distant Fog Density 1": max(0.0, float(distant.density)),
            "CP77 Distant Fog Height 1": distant.height,
            "CP77 Distant Fog Falloff 1": distant.height_falloff,
            "CP77 Distant Fog Density 2": max(0.0, float(distant.density_second)),
            "CP77 Distant Fog Height 2": distant.height_second,
            "CP77 Distant Fog Falloff 2": distant.height_falloff_second,
            "CP77 Distant Fog Near Color Distance": distant.near_distance,
            "CP77 Distant Fog Far Color Distance": max(
                distant.far_distance, distant.near_distance + 1.0
            ),
        },
        near_color=tuple(
            value * dome_scale for value in hdr_rgb(distant.albedo_near_rgba)
        ),
        far_color=tuple(
            value * dome_scale for value in hdr_rgb(distant.albedo_far_rgba)
        ),
    )
