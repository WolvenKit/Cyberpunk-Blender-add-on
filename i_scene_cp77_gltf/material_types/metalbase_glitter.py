from ..bartmoss.scalar import clamp01
from ..blender import shader_nodes
from .bundles import direct_ev_strength_socket, scalar_lerp_socket
from .mat_common import param_float
from .metalbase_common import (
    COLUMN_ADJUST,
    COLUMN_COMBINE,
    COLUMN_OUTPUT,
    COLUMN_TEXTURE,
    MetalBaseCore,
)


class MetalBaseGlitter(MetalBaseCore):
    normal_strength_param = None
    texture_defaults = {
        **MetalBaseCore.texture_defaults,
        "Normal": r"engine\textures\small_flat_normal.xbm",
        "EmissiveMask": r"base\fx\_textures\masks\noise\fx_digital_noise_01_d.xbm",
    }
    colour_defaults = {
        **MetalBaseCore.colour_defaults,
        "BaseColorScale": (0.898039216, 0.141176471, 0.141176471, 1.0),
        "EmissiveColor": (0.996078431, 0.454901961, 0.058823529, 1.0),
    }
    alpha_threshold_default = 0.0
    metalness_scale_default = 0.0
    roughness_scale_default = 0.0

    def _cut_range(self, CurMat, data, mask):
        speed = param_float(data, "ScrollSpeed", 0.213709995)
        looped = clamp01(param_float(data, "Looped", 0.0))
        histogram = max(1.0e-4, param_float(data, "HistogramRange", 0.491935015))

        time = self._time(CurMat, (COLUMN_TEXTURE - 200, -700), label="Glitter Time")
        swept = shader_nodes.math(
            CurMat.nodes,
            CurMat.links,
            "MULTIPLY",
            label="Sweep",
            location=(COLUMN_TEXTURE, -700),
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(
            swept.inputs, "Value_001"
        ).default_value = speed
        CurMat.links.new(time.outputs["Value"], swept.inputs["Value"])

        linear = shader_nodes.math(
            CurMat.nodes,
            CurMat.links,
            "FRACT",
            label="Linear Sweep",
            location=(COLUMN_ADJUST - 120, -760),
            hide=True,
        ).node
        CurMat.links.new(swept.outputs["Value"], linear.inputs["Value"])

        sine = shader_nodes.math(
            CurMat.nodes,
            CurMat.links,
            "SINE",
            label="Ping-Pong Sweep",
            location=(COLUMN_ADJUST - 120, -820),
            hide=True,
        ).node
        CurMat.links.new(swept.outputs["Value"], sine.inputs["Value"])
        sine_fract = shader_nodes.math(
            CurMat.nodes,
            CurMat.links,
            "FRACT",
            label="Ping-Pong Wrap",
            location=(COLUMN_ADJUST - 60, -820),
            hide=True,
        ).node
        CurMat.links.new(sine.outputs["Value"], sine_fract.inputs["Value"])

        blend_socket = scalar_lerp_socket(
            CurMat,
            linear.outputs["Value"],
            sine_fract.outputs["Value"],
            looped,
            (COLUMN_ADJUST - 40, -790),
            "Looped",
        )

        offset = shader_nodes.math(
            CurMat.nodes,
            CurMat.links,
            "SUBTRACT",
            label="Mask - Sweep",
            location=(COLUMN_COMBINE - 120, -700),
            hide=True,
        ).node
        CurMat.links.new(mask, offset.inputs["Value"])
        CurMat.links.new(
            blend_socket, shader_nodes.socket_by_identifier(offset.inputs, "Value_001")
        )

        wrapped = shader_nodes.math(
            CurMat.nodes,
            CurMat.links,
            "FRACT",
            label="Window",
            location=(COLUMN_COMBINE, -700),
            hide=True,
        ).node
        CurMat.links.new(offset.outputs["Value"], wrapped.inputs["Value"])

        widened = shader_nodes.math(
            CurMat.nodes,
            CurMat.links,
            "DIVIDE",
            label="HistogramRange",
            location=(COLUMN_COMBINE + 160, -700),
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(
            widened.inputs, "Value_001"
        ).default_value = histogram
        CurMat.links.new(wrapped.outputs["Value"], widened.inputs["Value"])

        # Texels past the top of the window are cut rather than clamped, which
        # keeps the trailing edge hard instead of smearing to full brightness.
        gate = shader_nodes.math(
            CurMat.nodes,
            CurMat.links,
            "LESS_THAN",
            label="Window Gate",
            location=(COLUMN_OUTPUT - 160, -700),
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(gate.inputs, "Value_001").default_value = 1.0
        CurMat.links.new(widened.outputs["Value"], gate.inputs["Value"])

        gated = shader_nodes.math(
            CurMat.nodes,
            CurMat.links,
            "MULTIPLY",
            label="cutRange",
            location=(COLUMN_OUTPUT, -700),
            hide=True,
        ).node
        CurMat.links.new(widened.outputs["Value"], gated.inputs["Value"])
        CurMat.links.new(
            gate.outputs["Value"],
            shader_nodes.socket_by_identifier(gated.inputs, "Value_001"),
        )
        return gated.outputs["Value"]

    def create(self, Data, Mat):
        data = Data if isinstance(Data, dict) else {}
        CurMat = Mat.node_tree
        bsdf, sockets = self._bsdf(CurMat)

        base = self._texture(CurMat, data, "BaseColor", (COLUMN_TEXTURE, 640))
        surface, _scale = self._scaled_base_color(CurMat, data, base, clamp=False)

        self._pbr_channel(
            CurMat, data, "Metalness", bsdf.inputs["Metallic"], None, 260, clamp=False
        )
        self._pbr_channel(
            CurMat, data, "Roughness", bsdf.inputs["Roughness"], None, 80, clamp=False
        )
        self._normal(CurMat, data, bsdf, None)

        tile = param_float(data, "EmissiveTile", 1.0)
        mask_uv = None
        if abs(tile - 1.0) > 1.0e-6:
            mask_uv = self._uv_scale_offset(
                CurMat, (tile, tile), (0.0, 0.0), (-1900, -560), "EmissiveTile"
            ).outputs["Vector"]
        mask = self._emissive_mask(CurMat, data, mask_uv, key="EmissiveMask")

        ev = max(0.0, param_float(data, "EmissiveEV", 6.20967817))
        cut_range = self._cut_range(CurMat, data, mask) if mask is not None else None

        if cut_range is not None and ev > 0.0:
            tinted = self._emissive_tint(
                CurMat, data, base.outputs["Color"] if base is not None else surface
            )
            surface = self._emissive_lerp(CurMat, cut_range, surface, tinted)
            CurMat.links.new(surface, bsdf.inputs[sockets["Emission"]])

            emissive_ev = shader_nodes.math(
                CurMat.nodes,
                CurMat.links,
                "MULTIPLY",
                label="EmissiveEV x cutRange",
                location=(COLUMN_OUTPUT + 120, -700),
                hide=True,
            ).node
            shader_nodes.socket_by_identifier(
                emissive_ev.inputs, "Value_001"
            ).default_value = ev
            CurMat.links.new(cut_range, emissive_ev.inputs["Value"])
            CurMat.links.new(
                direct_ev_strength_socket(
                    CurMat,
                    emissive_ev.outputs["Value"],
                    (COLUMN_OUTPUT + 300, -700),
                    "Glitter EmissiveEV",
                ),
                bsdf.inputs["Emission Strength"],
            )
        else:
            bsdf.inputs["Emission Strength"].default_value = 0.0

        CurMat.links.new(surface, bsdf.inputs["Base Color"])

        alpha = base.outputs["Alpha"] if base is not None else None
        alpha_from_emissive = clamp01(param_float(data, "AlphaFromEmissive", 1.0))
        if alpha is not None and cut_range is not None and alpha_from_emissive > 0.0:
            windowed = shader_nodes.math(
                CurMat.nodes,
                CurMat.links,
                "MULTIPLY",
                label="Mask x Window",
                location=(COLUMN_ADJUST, 760),
                hide=True,
            ).node
            CurMat.links.new(mask, windowed.inputs["Value"])
            CurMat.links.new(
                cut_range,
                shader_nodes.socket_by_identifier(windowed.inputs, "Value_001"),
            )

            factor = scalar_lerp_socket(
                CurMat,
                1.0,
                windowed.outputs["Value"],
                alpha_from_emissive,
                (COLUMN_ADJUST + 160, 760),
                "AlphaFromEmissive",
            )

            alpha_node = shader_nodes.math(
                CurMat.nodes,
                CurMat.links,
                "MULTIPLY",
                label="Alpha",
                location=(COLUMN_COMBINE, 760),
                hide=True,
            ).node
            CurMat.links.new(base.outputs["Alpha"], alpha_node.inputs["Value"])
            CurMat.links.new(
                factor,
                shader_nodes.socket_by_identifier(alpha_node.inputs, "Value_001"),
            )
            alpha = alpha_node.outputs["Value"]

        synthetic_alpha = (
            alpha is not None and cut_range is not None and alpha_from_emissive > 0.0
        )
        self._alpha_mask(
            CurMat,
            data,
            bsdf,
            alpha,
            None if synthetic_alpha else (base.image if base is not None else None),
        )
