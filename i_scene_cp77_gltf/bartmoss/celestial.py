from __future__ import annotations

import math

from .scalar import clamp_scalar
from .vector3 import add3, cross3, dot3, normalized3, scale3, sub3

DAY_HOURS = 24.0
# Right ascension and declination, in degrees, of the north galactic pole the star and galaxy textures are mapped
# against.
GALACTIC_POLE = (192.75, 27.13)


def wrap_hour(value: float) -> float:
    """Hour on the cyclic [0, 24) clock"""
    value = float(value) % DAY_HOURS
    if math.isclose(value, DAY_HOURS, abs_tol=1e-9):
        return 0.0
    return value


def hour_angle(hour: float) -> float:
    """Hour angle in radians, zero at solar noon"""
    return math.radians(15.0 * (wrap_hour(hour) - 12.0))


def horizon_coordinates(latitude: float, declination: float, hour_angle_radians: float):
    """(elevation, azimuth) in radians of a body at the given declination and hour angle"""
    sin_lat = math.sin(latitude)
    cos_lat = math.cos(latitude)
    sin_dec = math.sin(declination)
    cos_dec = math.cos(declination)
    cos_ha = math.cos(hour_angle_radians)
    elevation = math.asin(
        clamp_scalar(sin_dec * sin_lat + cos_dec * cos_lat * cos_ha, -1.0, 1.0)
    )
    cos_elevation = math.cos(elevation)
    if abs(cos_elevation) < 1e-9:
        return elevation, 0.0
    azimuth = math.acos(
        clamp_scalar(
            (sin_dec * cos_lat - cos_dec * sin_lat * cos_ha) / cos_elevation,
            -1.0,
            1.0,
        )
    )
    if hour_angle_radians > 0.0:
        azimuth = math.tau - azimuth
    return elevation, azimuth


def body_horizon_coordinates(
    hour: float, latitude_degrees: float, declination_degrees: float
):
    """(elevation, azimuth) of a body with the given declination at a clock hour and latitude"""
    return horizon_coordinates(
        math.radians(float(latitude_degrees)),
        math.radians(float(declination_degrees)),
        hour_angle(hour),
    )


def direction_from(elevation: float, azimuth: float, yaw_offset_degrees: float = 0.0):
    """Unit direction for horizon coordinates, optionally yawed about +Z"""
    horizontal = math.cos(elevation)
    x = horizontal * math.sin(azimuth)
    y = horizontal * math.cos(azimuth)
    z = math.sin(elevation)
    if abs(float(yaw_offset_degrees)) > 1e-12:
        angle = math.radians(yaw_offset_degrees)
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)
        x, y = x * cos_a - y * sin_a, x * sin_a + y * cos_a
    length = math.sqrt(x * x + y * y + z * z) or 1.0
    return (x / length, y / length, z / length)


def pole_direction(hour: float, latitude_degrees: float):
    """Direction of the celestial pole (declination 90 degrees) at a clock hour and latitude"""
    latitude = math.radians(float(latitude_degrees))
    elevation, azimuth = horizon_coordinates(latitude, math.pi * 0.5, hour_angle(hour))
    return direction_from(elevation, azimuth)


def elevation_degrees(direction) -> float:
    """Elevation of a unit direction above the horizon, in degrees"""
    return math.degrees(math.asin(clamp_scalar(direction[2], -1.0, 1.0)))


def raise_to_min_elevation(direction, minimum_elevation: float):
    """Direction lifted to at least the given elevation (radians), keeping its azimuth"""
    x, y, z = normalized3(direction)
    if math.asin(clamp_scalar(z, -1.0, 1.0)) >= minimum_elevation:
        return (x, y, z)
    horizontal_x, horizontal_y = x, y
    if horizontal_x * horizontal_x + horizontal_y * horizontal_y <= 1e-12:
        horizontal_x, horizontal_y = 0.0, 1.0
    planar = math.sqrt(horizontal_x * horizontal_x + horizontal_y * horizontal_y)
    horizontal = math.cos(minimum_elevation)
    return normalized3(
        (
            horizontal_x / planar * horizontal,
            horizontal_y / planar * horizontal,
            math.sin(minimum_elevation),
        )
    )


def disc_basis(direction, up_direction):
    """(horizontal, vertical) unit axes spanning the sky disc of a body seen along direction"""
    direction = normalized3(direction)
    vertical = sub3(up_direction, scale3(direction, dot3(up_direction, direction)))
    if dot3(vertical, vertical) <= 1e-12:
        vertical = sub3((0.0, 0.0, 1.0), scale3(direction, direction[2]))
    if dot3(vertical, vertical) <= 1e-12:
        vertical = (0.0, 1.0, 0.0)
    vertical = normalized3(vertical)
    horizontal = normalized3(cross3(vertical, direction))
    return horizontal, vertical


def _pole_frame_rows(longitude_degrees: float, latitude_degrees: float):
    """Rows of the rotation into the frame whose +Z is the pole at (longitude, latitude)"""
    longitude = math.radians(float(longitude_degrees))
    latitude = math.radians(float(latitude_degrees))
    sin_lon, cos_lon = math.sin(longitude), math.cos(longitude)
    sin_lat, cos_lat = math.sin(latitude), math.cos(latitude)
    return (
        (sin_lon, -cos_lon, 0.0),
        (sin_lat * cos_lon, sin_lat * sin_lon, cos_lat),
        (-cos_lat * cos_lon, -cos_lat * sin_lon, sin_lat),
    )


def _rotated(rows, direction):
    return (
        dot3(rows[0], direction),
        dot3(rows[1], direction),
        dot3(rows[2], direction),
    )


def sky_to_galactic_rows(
    hour: float, latitude_degrees: float, longitude_degrees: float
):
    """Rows of the rotation from a sky direction to the galactic frame"""
    observer = _pole_frame_rows(longitude_degrees, latitude_degrees)
    galactic = _pole_frame_rows(*GALACTIC_POLE)
    pole = (galactic[0][2], galactic[1][2], galactic[2][2])
    angle = math.tau * wrap_hour(hour) / DAY_HOURS
    cos_a, sin_a = math.cos(angle), math.sin(angle)
    columns = []
    for axis in ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)):
        direction = _rotated(galactic, _rotated(observer, axis))
        along = scale3(pole, dot3(pole, direction) * (1.0 - cos_a))
        columns.append(
            add3(
                add3(scale3(direction, cos_a), scale3(cross3(pole, direction), sin_a)),
                along,
            )
        )
    return tuple(tuple(column[row] for column in columns) for row in range(3))
