from __future__ import annotations

SUN_COLOR_SCALE = 100000.0
MOON_COLOR_SCALE = 1.0
SKY_COLOR_SCALE = 1000.0

SEASON_DECLINATION_DEGREES = {
    "ETOYS_Spring": 0.0,
    "ETOYS_Summer": 23.75,
    "ETOYS_Autumn": 0.0,
    "ETOYS_Winter": -23.75,
}

WEATHER_STATES = (
    "24h_weather_sunny",
    "24h_weather_rain",
    "24h_weather_fog",
    "24h_weather_pollution",
    "24h_weather_toxic_rain",
    "24h_weather_sandstorm",
    "24h_weather_light_clouds",
    "24h_weather_cloudy",
    "24h_weather_heavy_clouds",
    "q302_squat_morning",
    "q302_deeb_blue",
    "sa_courier_clouds",
    "q306_epilogue_cloudy_morning",
    "q306_rainy_night",
    "q302_light_rain",
)

WEATHER_LABELS = {
    "24h_weather_sunny": "Sunny",
    "24h_weather_rain": "Rain",
    "24h_weather_fog": "Fog",
    "24h_weather_pollution": "Pollution",
    "24h_weather_toxic_rain": "Toxic Rain",
    "24h_weather_sandstorm": "Sandstorm",
    "24h_weather_light_clouds": "Light Clouds",
    "24h_weather_cloudy": "Cloudy",
    "24h_weather_heavy_clouds": "Heavy Clouds",
    "q302_squat_morning": "Squat Morning",
    "q302_deeb_blue": "Deep Blue",
    "sa_courier_clouds": "Courier Clouds",
    "q306_epilogue_cloudy_morning": "Epilogue Cloudy Morning",
    "q306_rainy_night": "Rainy Night",
    "q302_light_rain": "Light Rain",
}
