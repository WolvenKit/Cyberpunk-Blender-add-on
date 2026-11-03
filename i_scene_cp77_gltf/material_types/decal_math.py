from ..assetio.values import coerce_int


def half_texel_offset(width, height, fallback_size=4096):
    width, height = coerce_int(width, unwrap=False), coerce_int(height, unwrap=False)
    fallback = max(1, int(fallback_size))
    width = width if width > 0 else fallback
    height = height if height > 0 else fallback
    return (0.5 / width, 0.5 / height, 0.0)


def ev_to_linear(ev):
    return 2.0 ** max(-16.0, min(16.0, float(ev)))
