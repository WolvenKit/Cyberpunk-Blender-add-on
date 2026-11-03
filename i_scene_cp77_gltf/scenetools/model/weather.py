from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from ...bartmoss.celestial import wrap_hour
from ...bartmoss.scalar import clamp01
from ..resources.environment import layered_block, weather_state_meta
from .curves import (
    curve_bool,
    curve_number,
    curve_rgba,
    curve_value,
    curve_vector,
    evaluate_curve,
    optional_curve_scalar,
    resource_text,
)


def _group_fades(table, hour):
    curves = table.get("groupFade")
    if not isinstance(curves, tuple):
        return (1.0,) * 8
    values = []
    for index in range(8):
        curve = curves[index] if index < len(curves) else None
        if isinstance(curve, dict) and curve.get("p"):
            value = evaluate_curve(curve, hour)
            values.append(clamp01(float(value)))
        else:
            values.append(1.0)
    return tuple(values)


def _ambient_colors(table, hour):
    curves = table.get("color")
    if not isinstance(curves, tuple):
        return ((0.0, 0.0, 0.0, 0.0),) * 6
    result = []
    for index in range(6):
        curve = curves[index] if index < len(curves) else None
        if isinstance(curve, dict) and curve.get("p"):
            value = evaluate_curve(curve, hour)
            if isinstance(value, tuple) and len(value) >= 4:
                result.append(tuple(float(value[channel]) for channel in range(4)))
                continue
        result.append((0.0, 0.0, 0.0, 0.0))
    return tuple(result)


@dataclass(slots=True, frozen=True)
class CloudSample:
    enabled: bool
    bottom: float
    top: float
    coverage: float
    density: float
    horizon_coverage: float
    cirrus_opacity: float
    cirrus_scale: float
    cirrus_altitude: float
    ambient_intensity: float
    ambient_outscatter: float
    cloud_ambient_intensity: float
    light_intensity: float
    light_rgba: tuple[float, float, float, float]
    sun_shadow_falloff: float
    sun_scattering: float
    moon_scattering: float
    shadow_intensity: float
    world_shadow_intensity: float
    silver_lining: float
    in_scatter: float
    out_scatter: float
    in_vs_out_scatter: float
    distant_fog_opacity: float
    ray_start_offset: float
    ray_start_falloff: float
    coverage_offset: tuple[float, float]
    coverage_wind_influence: float
    noise_wind_influence: float
    detail_wind_influence: float
    reflection_probe_light_intensity: float
    cirrus_texture: str
    weather_texture: str
    noise_texture: str

    @property
    def shader_coverage(self):
        return self.coverage * 2.0

    @property
    def shader_light_scale(self):
        return self.light_intensity / 10.0


@dataclass(slots=True, frozen=True)
class FogSample:
    enabled: bool
    range: float
    local_light_range: float
    density: float
    absorption: float
    albedo_rgba: tuple[float, float, float, float]
    fog_height: float
    fog_height_falloff: float
    fog_height_max_cut: float
    ambient_scale: float
    local_ambient_scale: float
    global_light_scale: float
    local_light_scale: float
    global_light_anisotropy: float
    global_light_anisotropy_base: float
    global_light_anisotropy_scale: float
    noise_scale: float
    noise_threshold: float
    noise_velocity: tuple[float, ...]
    distant_albedo_rgba: tuple[float, float, float, float]
    distant_global_light_scale: float
    distant_ground_irradiance: float
    distant_sky_irradiance: float
    distant_ground_saturation: float
    distant_shadow_ambient_darkening: float


@dataclass(slots=True, frozen=True)
class DistantFogSample:
    enabled: bool
    near_distance: float
    far_distance: float
    range: float
    density: float
    density_second: float
    albedo_near_rgba: tuple[float, float, float, float]
    albedo_far_rgba: tuple[float, float, float, float]
    height: float
    height_second: float
    height_falloff: float
    height_falloff_second: float
    simple_density: float
    simple_color_rgba: tuple[float, float, float, float]
    sky_altitude_begin: float
    sky_altitude_end: float
    sky_opacity: float


@dataclass(slots=True, frozen=True)
class WindSample:
    enabled: bool
    strength: float
    direction: tuple[float, ...]


@dataclass(slots=True, frozen=True)
class RainSample:
    enabled: bool
    override: float
    intensity: float
    moisture_override: float
    puddles_override: float
    num_particles: int
    radius: float
    height_range: float
    global_light_response: float
    base_color_factor: float
    glossiness_factor: float
    moisture_accumulation_speed: float
    moisture_evaporation_speed: float
    puddles_accumulation_speed: float
    puddles_evaporation_speed: float
    porosity_threshold_start: float
    porosity_threshold_end: float
    water_rain_intensity: float
    raindrops_mask: str
    rainleaks_mask: str
    ripples_mask: str


@dataclass(slots=True, frozen=True)
class OverrideSample:
    global_light_enabled: bool
    global_light_rgba: tuple[float, float, float, float]
    global_light_azimuth: float
    global_light_elevation: float
    ambient_enabled: bool
    ambient_rgba: tuple[tuple[float, float, float, float], ...]
    light_group_fades: tuple[float, ...]


@dataclass(slots=True, frozen=True)
class WeatherStateSample:
    probability: float | None
    min_duration: float | None
    max_duration: float | None
    transition_duration: float | None
    environment_resource: str


@dataclass(slots=True, frozen=True)
class WeatherSample:
    hour: float
    weather: str | None
    effect: str
    state: WeatherStateSample
    cloud: CloudSample
    fog: FogSample
    distant_fog: DistantFogSample
    wind: WindSample
    rain: RainSample
    overrides: OverrideSample


@lru_cache(maxsize=2048)
def solve_weather(hour: float, weather: str | None = None) -> WeatherSample:
    hour = wrap_hour(hour)
    cloud = layered_block("CloudAreaSettings", weather)
    fog = layered_block("VolumetricFogAreaSettings", weather)
    distant = layered_block("DistantFogAreaSettings", weather)
    wind = layered_block("WindAreaSettings", weather)
    rain = layered_block("RainAreaSettings", weather)
    global_override = layered_block("GlobalLightOverrideAreaSettings", weather)
    ambient_override = layered_block("AmbientOverrideAreaSettings", weather)
    light_groups = layered_block("LightGroupsAreaSettings", weather)
    state_meta = weather_state_meta(weather)

    cloud_sample = CloudSample(
        enabled=curve_bool(cloud, "enable", hour, True),
        bottom=curve_number(cloud, "cloudsBottom", hour, 400.0),
        top=curve_number(cloud, "cloudsTop", hour, 1000.0),
        coverage=curve_number(cloud, "volCoverage", hour, 0.5),
        density=curve_number(cloud, "volDensity", hour, 1.0),
        horizon_coverage=curve_number(cloud, "volHorizonCoverage", hour, 1.0),
        cirrus_opacity=curve_number(cloud, "cloudCirrusOpacity", hour, 1.0),
        cirrus_scale=curve_number(cloud, "cloudCirrusScale", hour, 5.0),
        cirrus_altitude=curve_number(cloud, "cloudCirrusAltitude", hour, 1.0),
        ambient_intensity=curve_number(cloud, "ambientIntensity", hour, 1.0),
        ambient_outscatter=curve_number(cloud, "ambientOutscatter", hour, 0.9),
        cloud_ambient_intensity=curve_number(cloud, "cloudAmbientIntensity", hour, 1.0),
        light_intensity=curve_number(cloud, "lightIntensity", hour, 1.0),
        light_rgba=curve_rgba(cloud, "cloudLightColor", hour, (1.0, 1.0, 1.0, 0.0)),
        sun_shadow_falloff=curve_number(cloud, "cloudSunShadowFaloff", hour, 1.0),
        sun_scattering=curve_number(cloud, "cloudSunScattering", hour, 0.9),
        moon_scattering=curve_number(cloud, "cloudMoonScattering", hour, 0.85),
        shadow_intensity=curve_number(cloud, "shadowIntensity", hour, 1.0),
        world_shadow_intensity=curve_number(cloud, "worldShadowIntensity", hour, 1.0),
        silver_lining=curve_number(cloud, "silverLining", hour, 0.8),
        in_scatter=curve_number(cloud, "inScatter", hour, 0.2),
        out_scatter=curve_number(cloud, "outScatter", hour, 0.1),
        in_vs_out_scatter=curve_number(cloud, "inVsOutScatter", hour, 0.5),
        distant_fog_opacity=curve_number(cloud, "volDistantFogOpacity", hour, 1.0),
        ray_start_offset=curve_number(cloud, "rayStartOffset", hour, 25.0),
        ray_start_falloff=curve_number(cloud, "rayStartFalloff", hour, 50.0),
        coverage_offset=tuple(
            curve_value(cloud, "volCoverageOffset", hour, (0.0, 0.0))
        )[:2],
        coverage_wind_influence=curve_number(
            cloud, "volCoverageWindInfluence", hour, 0.75
        ),
        noise_wind_influence=curve_number(cloud, "volNoiseWindInfluence", hour, 1.0),
        detail_wind_influence=curve_number(cloud, "volDetailWindInfluence", hour, 1.25),
        reflection_probe_light_intensity=curve_number(
            cloud, "reflectionProbeLightIntensity", hour, 0.25
        ),
        cirrus_texture=resource_text(cloud, "cloudCirrusTexture"),
        weather_texture=resource_text(cloud, "volWeatherTexture"),
        noise_texture=resource_text(cloud, "volNoiseTexture"),
    )

    fog_sample = FogSample(
        enabled=curve_bool(fog, "enable", hour, True),
        range=curve_number(fog, "range", hour, 250.0),
        local_light_range=curve_number(fog, "localLightRange", hour, 250.0),
        density=curve_number(fog, "density", hour, 0.005),
        absorption=curve_number(fog, "absorption", hour, 1.0),
        albedo_rgba=curve_rgba(fog, "albedo", hour, (1.0, 1.0, 0.9, 1.0)),
        fog_height=curve_number(fog, "fogHeight", hour, 0.0),
        fog_height_falloff=curve_number(fog, "fogHeightFalloff", hour, 0.01),
        fog_height_max_cut=curve_number(fog, "fogHeightMaxCut", hour, 10.0),
        ambient_scale=curve_number(fog, "ambientScale", hour, 1.0),
        local_ambient_scale=curve_number(fog, "localAmbientScale", hour, 1.0),
        global_light_scale=curve_number(fog, "globalLightScale", hour, 1.0),
        local_light_scale=curve_number(fog, "localLightScale", hour, 1.0),
        global_light_anisotropy=curve_number(fog, "globalLightAnisotropy", hour, 0.9),
        global_light_anisotropy_base=curve_number(
            fog, "globalLightAnisotropyBase", hour, 0.0
        ),
        global_light_anisotropy_scale=curve_number(
            fog, "globalLightAnisotropyScale", hour, 1.0
        ),
        noise_scale=curve_number(fog, "noiseScale", hour, 1.0),
        noise_threshold=curve_number(fog, "noiseThreshold", hour, 0.0),
        noise_velocity=curve_vector(fog, "noiseVelocity", hour, (0.0, 0.0, 0.0)),
        distant_albedo_rgba=curve_rgba(
            fog, "distantAlbedo", hour, (1.0, 1.0, 0.9, 0.0)
        ),
        distant_global_light_scale=curve_number(
            fog, "distantGlobalLightScale", hour, -1.0
        ),
        distant_ground_irradiance=curve_number(
            fog, "distantGroundIrradiance", hour, 1.0
        ),
        distant_sky_irradiance=curve_number(fog, "distantSkyIrradiance", hour, 1.0),
        distant_ground_saturation=curve_number(
            fog, "distantGroundSaturation", hour, 1.0
        ),
        distant_shadow_ambient_darkening=curve_number(
            fog, "distantShadowAmbientDarkening", hour, 1.0
        ),
    )

    distant_sample = DistantFogSample(
        enabled=curve_bool(distant, "enable", hour, True),
        near_distance=curve_number(distant, "nearDistance", hour, 128.0),
        far_distance=curve_number(distant, "farDistance", hour, 2000.0),
        range=curve_number(distant, "range", hour, 0.0),
        density=curve_number(distant, "density", hour, 6.0),
        density_second=curve_number(distant, "densitySecond", hour, 1.0),
        albedo_near_rgba=curve_rgba(distant, "albedoNear", hour, (1.0, 1.0, 0.9, 1.0)),
        albedo_far_rgba=curve_rgba(distant, "albedoFar", hour, (1.0, 1.0, 0.9, 1.0)),
        height=curve_number(distant, "height", hour, 0.0),
        height_second=curve_number(distant, "heightSecond", hour, 0.0),
        height_falloff=curve_number(distant, "heightFallof", hour, 5.0),
        height_falloff_second=curve_number(distant, "heightFallofSecond", hour, 20.0),
        simple_density=curve_number(distant, "simpleDensity", hour, 0.0),
        simple_color_rgba=curve_rgba(
            distant, "simpleColor", hour, (0.5, 0.5, 0.5, 1.0)
        ),
        sky_altitude_begin=curve_number(distant, "skyAltitudeBegin", hour, 0.0),
        sky_altitude_end=curve_number(distant, "skyAltitudeEnd", hour, 0.0),
        sky_opacity=curve_number(distant, "skyOpacity", hour, 0.0),
    )

    wind_sample = WindSample(
        enabled=curve_bool(wind, "enable", hour, True),
        strength=curve_number(wind, "strength", hour, 0.1),
        direction=curve_vector(wind, "direction", hour, (1.0, 0.0, 0.0)),
    )

    rain_sample = RainSample(
        enabled=curve_bool(rain, "enable", hour, True),
        override=curve_number(rain, "rainOverride", hour, 0.0),
        intensity=curve_number(rain, "rainIntensity", hour, 0.0),
        moisture_override=curve_number(rain, "rainMoistureOverride", hour, 0.0),
        puddles_override=curve_number(rain, "rainPuddlesOverride", hour, 0.0),
        num_particles=int(curve_number(rain, "numParticles", hour, 0.0)),
        radius=curve_number(rain, "radius", hour, 45.0),
        height_range=curve_number(rain, "heightRange", hour, 40.0),
        global_light_response=curve_number(rain, "globalLightResponse", hour, 1.0),
        base_color_factor=curve_number(rain, "baseColorFactor", hour, 0.0),
        glossiness_factor=curve_number(rain, "glossinessFactor", hour, 1.0),
        moisture_accumulation_speed=curve_number(
            rain, "moistureAccumulationSpeed", hour, 5.0
        ),
        moisture_evaporation_speed=curve_number(
            rain, "moistureEvaporationSpeed", hour, 2.5
        ),
        puddles_accumulation_speed=curve_number(
            rain, "puddlesAccumulationSpeed", hour, 1.5
        ),
        puddles_evaporation_speed=curve_number(
            rain, "puddlesEvaporationSpeed", hour, 0.25
        ),
        porosity_threshold_start=curve_number(
            rain, "porosityThresholdStart", hour, 0.0
        ),
        porosity_threshold_end=curve_number(rain, "porosityThresholdEnd", hour, 1.0),
        water_rain_intensity=curve_number(rain, "waterRainIntensity", hour, 0.0),
        raindrops_mask=resource_text(rain, "raindropsMask"),
        rainleaks_mask=resource_text(rain, "rainleaksMask"),
        ripples_mask=resource_text(rain, "rainRipplesMask"),
    )

    override_sample = OverrideSample(
        global_light_enabled=curve_bool(global_override, "enable", hour, False),
        global_light_rgba=curve_rgba(
            global_override, "color", hour, (1.0, 1.0, 1.0, 1.0)
        ),
        global_light_azimuth=curve_number(global_override, "lightAzimuth", hour, 45.0),
        global_light_elevation=curve_number(
            global_override, "lightElevation", hour, 45.0
        ),
        ambient_enabled=curve_bool(ambient_override, "enable", hour, False),
        ambient_rgba=_ambient_colors(ambient_override, hour),
        light_group_fades=_group_fades(light_groups, hour),
    )

    state_sample = WeatherStateSample(
        probability=optional_curve_scalar(state_meta, "probability", hour),
        min_duration=optional_curve_scalar(state_meta, "minDuration", hour),
        max_duration=optional_curve_scalar(state_meta, "maxDuration", hour),
        transition_duration=optional_curve_scalar(
            state_meta, "transitionDuration", hour
        ),
        environment_resource=str(state_meta.get("environmentAreaParameters", "") or ""),
    )

    return WeatherSample(
        hour=float(hour),
        weather=str(weather) if weather else None,
        effect=resource_text(state_meta, "effect"),
        state=state_sample,
        cloud=cloud_sample,
        fog=fog_sample,
        distant_fog=distant_sample,
        wind=wind_sample,
        rain=rain_sample,
        overrides=override_sample,
    )
