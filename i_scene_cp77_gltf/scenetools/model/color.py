from __future__ import annotations


def hdr_rgb(rgba, rgb_scale=1.0):
    """Linear RGB of an HDR colour, optionally scaled by a unit convention factor"""
    magnitude = float(rgba[3])
    scale = float(rgb_scale) * magnitude
    return tuple(float(rgba[index]) * scale for index in range(3))
