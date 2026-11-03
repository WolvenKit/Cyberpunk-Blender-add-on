import math


def scale_emissive_ev(base_ev, scale):
    return max(
        float(base_ev) + math.log2(max(float(scale), 1.0e-7)),
        0.0,
    )


def emissive_strength_from_ev(base_ev, scale=1.0):
    scaled_ev = min(scale_emissive_ev(base_ev, scale), 16.0)
    return max((2.0**scaled_ev) - 1.0, 0.0)
