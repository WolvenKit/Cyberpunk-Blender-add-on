from .metalbase import MetalBase


class WindowParallaxInteriorProxyBuffer(MetalBase):
    texture_defaults = {
        **MetalBase.texture_defaults,
        "BaseColor": r"engine\textures\editor\checker_d.xbm",
    }
    colour_defaults = {
        **MetalBase.colour_defaults,
        "BaseColorScale": (1.0, 1.0, 1.0, 0.0),
    }
    alpha_threshold_default = 0.0
    suppress_emissive = True
    clamp_base_color = False
    clamp_pbr = False
