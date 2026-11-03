from __future__ import annotations

import math

from ...assetio.values import color_bytes, field_float
from ...bartmoss.scalar import clamp01, srgb_channel_to_linear

WIDE_SPOT_THRESHOLD_DEGREES = 180.0
# Representations whose preview lights never cast shadows.
SHADOWLESS_REPRESENTATIONS = frozenset(
    {
        "PUNCTUAL_POINT",
        "SPHERICAL_POINT",
        "CAPSULE_POINT_CHAIN",
        "WIDE_SPOT_POINT_APPROX",
        "CAPSULE_WIDE_SPOT_POINT_CHAIN",
        "NON_NATIVE_AREA_FALLBACK",
    }
)


def temperature_linear_rgb(kelvin):
    kelvin = float(kelvin)
    if kelvin <= 0.0:
        return 1.0, 1.0, 1.0
    k2 = kelvin * kelvin
    u = (0.860117757 + 0.000154118254 * kelvin + 0.000000128641212 * k2) / (
        1.0 + 0.000842420235 * kelvin + 0.000000708145163 * k2
    )
    v = (0.317398726 + 0.0000422806245 * kelvin + 0.0000000420481691 * k2) / (
        1.0 - 0.0000289741816 * kelvin + 0.000000161456053 * k2
    )
    denominator = 2.0 * u - 8.0 * v + 4.0
    if abs(denominator) <= 1e-12:
        return 1.0, 1.0, 1.0
    x = 3.0 * u / denominator
    y = 2.0 * v / denominator
    if abs(y) <= 1e-12:
        return 1.0, 1.0, 1.0
    z = 1.0 - x - y
    luminance = 1.0
    X = luminance / y * x
    Z = luminance / y * z
    return (
        max(0.0, 3.2404542 * X - 1.5371385 * luminance - 0.4985314 * Z),
        max(0.0, -0.9692660 * X + 1.8760108 * luminance + 0.0415560 * Z),
        max(0.0, 0.0556434 * X - 0.2040259 * luminance + 1.0572252 * Z),
    )


def linear_color(data):
    color = data.get("color") if isinstance(data, dict) else None
    linear = tuple(
        srgb_channel_to_linear(clamp01(value / 255.0)) for value in color_bytes(color)
    )
    temperature = field_float(data, "temperature", -1.0)
    if temperature > 0.0:
        tint = temperature_linear_rgb(temperature)
        linear = tuple(linear[index] * tint[index] for index in range(3))
    return tuple(max(0.0, value) for value in linear)


def numeric_energy(data):
    return max(0.0, field_float(data, "intensity", 0.0)) * max(
        0.0,
        field_float(data, "onStrength", 1.0),
    )


def cosine_spot_blend(inner_degrees, outer_degrees):
    outer = max(0.001, min(float(outer_degrees), WIDE_SPOT_THRESHOLD_DEGREES))
    inner = max(0.0, min(float(inner_degrees), outer))
    outer_cos = math.cos(math.radians(outer) * 0.5)
    inner_cos = math.cos(math.radians(inner) * 0.5)
    denominator = max(1.0 - outer_cos, 1e-8)
    return max(0.0, min(1.0, (inner_cos - outer_cos) / denominator))


def softened_cosine_spot_blend(inner_degrees, outer_degrees, softness):
    outer = max(0.001, min(float(outer_degrees), WIDE_SPOT_THRESHOLD_DEGREES))
    inner = max(0.0, min(float(inner_degrees), outer))
    softness = max(float(softness), 0.001)
    outer_cos = math.cos(math.radians(outer) * 0.5)
    inner_cos = math.cos(math.radians(inner) * 0.5)
    half_x = 0.5 ** (1.0 / softness)
    effective_inner_cos = outer_cos + 2.0 * half_x * (inner_cos - outer_cos)
    effective_inner_cos = max(outer_cos, min(1.0, effective_inner_cos))
    denominator = max(1.0 - outer_cos, 1e-8)
    return max(0.0, min(1.0, (effective_inner_cos - outer_cos) / denominator))


def capsule_sample_offsets(length, count=None):
    length = max(0.0, float(length))
    if count is None:
        count = 3 if length <= 1.0 else (5 if length <= 8.0 else 7)
    count = max(1, int(count))
    if count == 1 or length <= 1e-8:
        return (0.0,)
    step = length / float(count - 1)
    offsets = [-0.5 * length + step * index for index in range(count)]
    offsets.sort(key=lambda value: (abs(value), value))
    return tuple(offsets)


def light_representation(data):
    cp77_type = str(data.get("type", "LT_Point"))
    if cp77_type == "LT_Spot":
        outer = field_float(data, "outerAngle", 90.0)
        if outer > WIDE_SPOT_THRESHOLD_DEGREES:
            return "POINT", "WIDE_SPOT_POINT_APPROX"
        return "SPOT", "PUNCTUAL_SPOT"
    if cp77_type != "LT_Area":
        return "POINT", "PUNCTUAL_POINT"

    shape = str(data.get("areaShape", "ALS_Capsule"))
    if shape == "ALS_Sphere":
        return "POINT", "SPHERICAL_POINT"
    if shape == "ALS_Capsule":
        if bool(data.get("spotCapsule", 0)):
            if field_float(data, "outerAngle", 90.0) > WIDE_SPOT_THRESHOLD_DEGREES:
                return "POINT", "CAPSULE_WIDE_SPOT_POINT_CHAIN"
            return "SPOT", "CAPSULE_SPOT_CHAIN"
        return "POINT", "CAPSULE_POINT_CHAIN"
    return "POINT", "NON_NATIVE_AREA_FALLBACK"


def proxy_offsets(data, representation):
    if representation not in {
        "CAPSULE_SPOT_CHAIN",
        "CAPSULE_POINT_CHAIN",
        "CAPSULE_WIDE_SPOT_POINT_CHAIN",
    }:
        return (0.0,)
    return capsule_sample_offsets(field_float(data, "capsuleLength", 0.0))


def uses_direction_axis(representation):
    return representation in {
        "PUNCTUAL_SPOT",
        "CAPSULE_SPOT_CHAIN",
        "WIDE_SPOT_POINT_APPROX",
        "CAPSULE_WIDE_SPOT_POINT_CHAIN",
    }
