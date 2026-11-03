from ..blender import shader_nodes
from ..materials.blender.nodes import create_node
from .bundles import direct_ev_strength_socket
from .mat_common import param_color, param_float
from .metalbase_common import (
    COLUMN_ADJUST,
    COLUMN_COMBINE,
    COLUMN_TEXTURE,
    MetalBaseCore,
    tiling_and_scrolling,
)


class MetalBaseScrolling(MetalBaseCore):
    normal_strength_param = None
    texture_defaults = {
        "Normal": r"base\materials\placeholder\normal.xbm",
        "Mask": r"base\fx\_textures\masks\noise\fx_digital_noise_01_d.xbm",
    }

    def create(self, Data, Mat):
        data = Data if isinstance(Data, dict) else {}
        CurMat = Mat.node_tree
        bsdf, sockets = self._bsdf(CurMat)

        mask_uv = tiling_and_scrolling(
            self, CurMat, data, "MaskTilingAndScrolling", (-1900, 640), "Mask Scroll"
        )
        mask_texture = self._texture(
            CurMat,
            data,
            "Mask",
            (COLUMN_TEXTURE, 640),
            mask_uv.outputs["Vector"],
            non_color=True,
        )

        mask_socket = None
        if mask_texture is not None:
            channels = create_node(
                CurMat.nodes,
                "ShaderNodeSeparateColor",
                (COLUMN_ADJUST, 640),
                label="Mask.r",
            )
            CurMat.links.new(mask_texture.outputs["Color"], channels.inputs["Color"])
            mask_socket = channels.outputs["Red"]

        surface = self._mix_color(
            CurMat,
            (COLUMN_COMBINE, 640),
            mask_socket if mask_socket is not None else 0.0,
            param_color(data, "Dark", (0.0, 0.0, 0.0, 1.0)),
            param_color(data, "Bright", (1.0, 1.0, 1.0, 1.0)),
            label="Dark to Bright",
        )

        bsdf.inputs["Metallic"].default_value = max(
            0.0, min(1.0, param_float(data, "Metalness", 0.0))
        )
        bsdf.inputs["Roughness"].default_value = max(
            0.0, min(1.0, param_float(data, "Roughness", 0.5))
        )
        self._normal(CurMat, data, bsdf, None)

        ev = max(0.0, param_float(data, "EmissiveEV", 10.0))
        if ev > 0.0 and mask_socket is not None:
            CurMat.links.new(surface, bsdf.inputs[sockets["Emission"]])
            emissive_ev = shader_nodes.math(
                CurMat.nodes,
                CurMat.links,
                "MULTIPLY",
                label="EmissiveEV x Mask",
                location=(COLUMN_COMBINE + 160, 420),
                hide=True,
            ).node
            shader_nodes.socket_by_identifier(
                emissive_ev.inputs, "Value_001"
            ).default_value = ev
            CurMat.links.new(mask_socket, emissive_ev.inputs["Value"])
            CurMat.links.new(
                direct_ev_strength_socket(
                    CurMat,
                    emissive_ev.outputs["Value"],
                    (COLUMN_COMBINE + 340, 420),
                    "Scrolling EmissiveEV",
                ),
                bsdf.inputs["Emission Strength"],
            )
        else:
            bsdf.inputs["Emission Strength"].default_value = 0.0

        CurMat.links.new(surface, bsdf.inputs["Base Color"])
        bsdf.inputs["Alpha"].default_value = 1.0
