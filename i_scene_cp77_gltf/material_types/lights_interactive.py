from .bundles import light_zone_emission, light_zone_index
from .metalbase_common import (
    COLUMN_COMBINE,
    COLUMN_OUTPUT,
    COLUMN_TEXTURE,
    MetalBaseCore,
)

_DEBUG_ZONE_COLORS = (
    (1.0, 0.0, 0.0, 1.0),
    (0.0, 1.0, 0.0, 1.0),
    (0.0, 0.2, 1.0, 1.0),
    (1.0, 0.0, 1.0, 1.0),
)


class LightsInteractive(MetalBaseCore):
    """Build the static Eevee representation for interactive lights"""

    normal_strength_param = None
    alpha_threshold_default = 0.0

    def create(self, Data, Mat):
        data = Data if isinstance(Data, dict) else {}
        tree = Mat.node_tree
        bsdf, sockets = self._bsdf(tree)
        uv = self._uv_source(tree, data)

        base = self._texture(tree, data, "BaseColor", (COLUMN_TEXTURE, 620), uv)
        surface, _ = self._scaled_base_color(tree, data, base, clamp=True)
        self._pbr_channel(
            tree, data, "Metalness", bsdf.inputs["Metallic"], uv, 260, clamp=True
        )
        self._pbr_channel(
            tree, data, "Roughness", bsdf.inputs["Roughness"], uv, 80, clamp=True
        )
        self._normal(tree, data, bsdf, uv)

        mask = self._emissive_mask(tree, data, uv, y=-560)
        zone_color, blend, emission_strength = light_zone_emission(
            tree,
            light_zone_index(tree, (COLUMN_TEXTURE, -980)),
            data,
            _DEBUG_ZONE_COLORS,
            0.0 if mask is None else mask,
            (COLUMN_COMBINE, -1080),
        )

        base_color = base.outputs["Color"] if base is not None else surface
        emissive_surface = self._mix_color(
            tree,
            (COLUMN_OUTPUT, 520),
            blend,
            surface,
            self._mix_color(
                tree,
                (COLUMN_COMBINE + 120, 420),
                1.0,
                base_color,
                zone_color,
                blend_type="MULTIPLY",
                label="Base x Zone Color",
                clamp_result=True,
            ),
            label="lights_interactive Color",
        )
        tree.links.new(emissive_surface, bsdf.inputs["Base Color"])
        tree.links.new(emissive_surface, bsdf.inputs[sockets["Emission"]])
        tree.links.new(emission_strength, bsdf.inputs["Emission Strength"])

        alpha = base.outputs["Alpha"] if base is not None else None
        self._alpha_mask(
            tree, data, bsdf, alpha, base.image if base is not None else None
        )
