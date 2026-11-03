from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ...bartmoss.celestial import wrap_hour
from ..model.environment import WEATHER_LABELS, WEATHER_STATES
from ..model.solver import solve

SEASON_ITEMS = (
    ("ETOYS_Spring", "Spring", "Zero solar declination"),
    ("ETOYS_Summer", "Summer", "+23.75 degree solar declination"),
    ("ETOYS_Autumn", "Autumn", "Zero solar declination"),
    ("ETOYS_Winter", "Winter", "-23.75 degree solar declination"),
)

WEATHER_ITEMS = tuple(
    (key, WEATHER_LABELS.get(key, key), key) for key in WEATHER_STATES
)

BAKE_SAMPLES = 96


class RefreshScope(str, Enum):
    FULL = "FULL"
    EXPOSURE = "EXPOSURE"
    WEATHER_PREVIEW = "WEATHER_PREVIEW"
    CLOUD_PREVIEW = "CLOUD_PREVIEW"
    FOG_PREVIEW = "FOG_PREVIEW"


@dataclass(frozen=True, slots=True)
class SceneToolsRequest:
    time_of_day: float
    weather: str
    override_season: bool
    season: str
    override_latitude: bool
    latitude: float
    preview_exposure: float
    create_global_light: bool
    create_world: bool
    preview_volumetric_clouds: bool
    preview_high_clouds: bool
    preview_rain: bool
    preview_volumetric_fog: bool
    preview_distant_fog: bool
    weather_follow_scene_camera: bool

    @classmethod
    def from_settings(cls, settings):
        return cls(
            time_of_day=wrap_hour(float(settings.time_of_day)),
            weather=str(settings.weather),
            override_season=bool(settings.override_season),
            season=str(settings.season),
            override_latitude=bool(settings.override_latitude),
            latitude=float(settings.latitude),
            preview_exposure=float(settings.preview_exposure),
            create_global_light=bool(settings.create_global_light),
            create_world=bool(settings.create_world),
            preview_volumetric_clouds=bool(settings.preview_volumetric_clouds),
            preview_high_clouds=bool(settings.preview_high_clouds),
            preview_rain=bool(settings.preview_rain),
            preview_volumetric_fog=bool(settings.preview_volumetric_fog),
            preview_distant_fog=bool(settings.preview_distant_fog),
            weather_follow_scene_camera=bool(settings.weather_follow_scene_camera),
        )

    def sample(self, hour=None):
        return solve(
            self.time_of_day if hour is None else wrap_hour(float(hour)),
            weather=self.weather,
            latitude=self.latitude if self.override_latitude else None,
            season=self.season if self.override_season else None,
        )


def format_hour(hour):
    hour = wrap_hour(hour)
    total_minutes = int(round(hour * 60.0)) % (24 * 60)
    return f"{total_minutes // 60:02d}:{total_minutes % 60:02d}"
