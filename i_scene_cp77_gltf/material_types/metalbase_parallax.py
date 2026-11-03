from .mat_common import param_float
from .metalbase import MetalBase
from .parallax_math import parallax_uv


class MetalBaseParallax(MetalBase):
    texture_defaults = {
        **MetalBase.texture_defaults,
        "BaseColor": r"base\vehicles\common\textures\vehicles_decals_exterior_height.xbm",
        "Metalness": r"base\materials\placeholder\black.xbm",
        "Roughness": r"base\materials\placeholder\white.xbm",
        "Normal": r"base\vehicles\common\textures\vehicles_decals_exterior_n01.xbm",
        "Emissive": r"base\materials\placeholder\black.xbm",
        "HeightTexture": r"base\vehicles\common\textures\vehicles_decals_exterior_height.xbm",
    }
    colour_defaults = {
        **MetalBase.colour_defaults,
        "BaseColorScale": (1.0, 1.0, 1.0, 1.0),
        "EmissiveColor": (0.0, 0.0, 0.0, 0.0),
    }
    alpha_threshold_default = 0.0
    metalness_scale_default = 0.0
    roughness_scale_default = 0.0

    def _surface_uv(self, tree, data, source_uv=None):
        del source_uv
        tiled = self._uv_source(tree, data)
        if tiled is None:
            mapping = self._uv_scale_offset(
                tree, (1.0, 1.0), None, (-1900, 400), "Surface UV"
            )
            tiled = mapping.outputs["Vector"]
        return parallax_uv(
            self,
            tree,
            data,
            tiled,
            height_key="HeightTexture",
            strength_key="HeightStrength",
            strength=param_float(data, "HeightStrength", 1.0),
            location=(-1700, -900),
            label="MetalBase Parallax",
        )
