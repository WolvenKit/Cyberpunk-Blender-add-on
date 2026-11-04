from .bink_math import decode_bink_preview
from .mat_common import param_float
from .metalbase_common import COLUMN_TEXTURE, MetalBaseCore


class MetalBaseBink(MetalBaseCore):
    normal_strength_param = None
    emissive_lift_param = None
    texture_defaults = {
        **MetalBaseCore.texture_defaults,
        "BaseColor": r"engine\textures\editor\white.xbm",
        "Roughness": r"engine\textures\editor\grey.xbm",
        "Emissive": r"engine\textures\editor\white.xbm",
    }
    colour_defaults = {
        **MetalBaseCore.colour_defaults,
        "BaseColorScale": (1.0, 1.0, 1.0, 1.0),
        "EmissiveColor": (1.0, 1.0, 1.0, 1.0),
    }
    alpha_threshold_default = 0.0

    def create(self, Data, Mat):
        data = Data if isinstance(Data, dict) else {}
        tree = Mat.node_tree
        bsdf, sockets = self._bsdf(tree)

        base = self._texture(tree, data, "BaseColor", (COLUMN_TEXTURE, 640))
        surface, _ = self._scaled_base_color(tree, data, base, clamp=False)
        self._pbr_channel(
            tree, data, "Metalness", bsdf.inputs["Metallic"], None, 260, clamp=False
        )
        self._pbr_channel(
            tree, data, "Roughness", bsdf.inputs["Roughness"], None, 80, clamp=False
        )
        self._normal(tree, data, bsdf, None)

        video, video_alpha = decode_bink_preview(self, tree, data)
        if video is None:
            base_socket = base.outputs["Color"] if base is not None else surface
            final = self._emissive_block(
                tree, data, bsdf, sockets, surface, base_socket
            )
        else:
            final = video
            ev = max(0.0, param_float(data, "EmissiveEV", 0.0))
            emissive_mask = self._emissive_mask(tree, data, None) if ev > 0.0 else None
            if emissive_mask is not None:
                tree.links.new(final, bsdf.inputs[sockets["Emission"]])
                tree.links.new(
                    self._ev_strength(
                        tree, emissive_mask, ev, label="Bink Emissive Strength"
                    ),
                    bsdf.inputs["Emission Strength"],
                )
            else:
                bsdf.inputs["Emission Strength"].default_value = 0.0
        tree.links.new(final, bsdf.inputs["Base Color"])

        alpha = (
            video_alpha
            if video is not None and video_alpha is not None
            else (base.outputs["Alpha"] if base is not None else None)
        )
        self._alpha_mask(
            tree,
            data,
            bsdf,
            alpha,
            None if video is not None else (base.image if base is not None else None),
        )
