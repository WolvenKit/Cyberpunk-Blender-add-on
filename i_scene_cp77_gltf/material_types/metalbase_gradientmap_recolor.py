from ..blender import shader_nodes
from ..materials.blender.nodes import create_node
from .bundles import direct_ev_strength_socket
from .mat_common import param_float
from .metalbase_common import (
    COLUMN_ADJUST,
    COLUMN_COMBINE,
    COLUMN_OUTPUT,
    COLUMN_TEXTURE,
    MetalBaseCore,
)


class MetalBaseGradient(MetalBaseCore):
    texture_defaults = {
        **MetalBaseCore.texture_defaults,
        "Mask": r"engine\textures\editor\white.xbm",
        "GradientMap": r"engine\textures\editor\grey.xbm",
        "EmissiveGradientMap": r"engine\textures\editor\black.xbm",
        "Emissive": r"engine\textures\editor\white.xbm",
    }
    colour_defaults = {
        **MetalBaseCore.colour_defaults,
        "BaseColorScale": (1.0, 1.0, 1.0, 1.0),
        "EmissiveColor": (1.0, 1.0, 1.0, 1.0),
    }
    alpha_threshold_default = 0.379999995

    def _gradient_sample(self, tree, data, key, index, location, *, non_color=False):
        path = self._texture_path(data, key)
        if not path:
            return None
        image = self._load_relative_image(path, non_color=non_color, error_label=key)
        if image is None:
            return None
        vector = create_node(
            tree.nodes, "ShaderNodeCombineXYZ", location, label=f"{key} UV"
        )
        tree.links.new(index, vector.inputs["X"])
        vector.inputs["Y"].default_value = 0.5
        texture = create_node(
            tree.nodes,
            "ShaderNodeTexImage",
            (location[0] + 180, location[1]),
            label=key,
            image=image,
        )
        texture.extension = "EXTEND"
        tree.links.new(vector.outputs["Vector"], texture.inputs["Vector"])
        return texture

    def create(self, Data, Mat):
        data = Data if isinstance(Data, dict) else {}
        tree = Mat.node_tree
        bsdf, sockets = self._bsdf(tree)
        uv = self._uv_source(tree, data)

        base = self._texture(
            tree, data, "BaseColor", (COLUMN_TEXTURE, 680), uv, non_color=True
        )
        if base is None:
            bsdf.inputs["Base Color"].default_value = (1.0, 1.0, 1.0, 1.0)
            bsdf.inputs["Emission Strength"].default_value = 0.0
            return
        split = create_node(
            tree.nodes,
            "ShaderNodeSeparateColor",
            (COLUMN_ADJUST - 120, 680),
            label="BaseColor.r Gradient Index",
        )
        tree.links.new(base.outputs["Color"], split.inputs["Color"])
        clamp = create_node(
            tree.nodes,
            "ShaderNodeClamp",
            (COLUMN_ADJUST + 40, 680),
            label="saturate(BaseColor.r)",
        )
        tree.links.new(split.outputs["Red"], clamp.inputs["Value"])
        index = clamp.outputs["Result"]

        gradient = self._gradient_sample(
            tree, data, "GradientMap", index, (COLUMN_ADJUST, 520)
        )
        if gradient is None:
            gradient_color = base.outputs["Color"]
            gradient_alpha = base.outputs["Alpha"]
        else:
            gradient_color = gradient.outputs["Color"]
            gradient_alpha = gradient.outputs["Alpha"]
        scale, _ = self._colour_scale_socket(
            tree, data, "BaseColorScale", (COLUMN_TEXTURE, 430)
        )
        surface = self._mix_color(
            tree,
            (COLUMN_COMBINE, 540),
            1.0,
            gradient_color,
            scale,
            blend_type="MULTIPLY",
            label="Gradient x BaseColorScale",
        )

        self._pbr_channel(tree, data, "Metalness", bsdf.inputs["Metallic"], uv, 260)
        self._pbr_channel(tree, data, "Roughness", bsdf.inputs["Roughness"], uv, 80)
        self._normal(tree, data, bsdf, uv)

        mask_texture = self._texture(
            tree, data, "Mask", (COLUMN_TEXTURE, 860), uv, non_color=True
        )
        mask = None
        if mask_texture is not None:
            mask_split = create_node(
                tree.nodes,
                "ShaderNodeSeparateColor",
                (COLUMN_ADJUST, 860),
                label="Mask.r",
            )
            tree.links.new(mask_texture.outputs["Color"], mask_split.inputs["Color"])
            mask = mask_split.outputs["Red"]
        alpha = self._multiplied_alpha(
            tree,
            (mask, gradient_alpha),
            None,
            (COLUMN_COMBINE, 860),
            "Mask x Gradient Alpha",
        )

        ev = max(0.0, param_float(data, "EmissiveEV", 0.0))
        emissive_mask = self._emissive_mask(tree, data, None) if ev > 0.0 else None
        if emissive_mask is not None:
            tint = self._emissive_tint(tree, data, gradient_color)
            surface = self._emissive_lerp(tree, emissive_mask, surface, tint)
            tree.links.new(surface, bsdf.inputs[sockets["Emission"]])
            emissive_gradient = self._gradient_sample(
                tree,
                data,
                "EmissiveGradientMap",
                index,
                (COLUMN_ADJUST, -820),
                non_color=True,
            )
            strength = shader_nodes.math(
                tree.nodes,
                tree.links,
                "MULTIPLY",
                label="EmissiveMask x EmissiveEV",
                location=(COLUMN_OUTPUT - 120, -660),
                hide=True,
            ).node
            shader_nodes.socket_by_identifier(
                strength.inputs, "Value_001"
            ).default_value = ev
            tree.links.new(emissive_mask, strength.inputs["Value"])
            if emissive_gradient is not None:
                eg_split = create_node(
                    tree.nodes,
                    "ShaderNodeSeparateColor",
                    (COLUMN_OUTPUT + 40, -760),
                    label="EmissiveGradientMap.r",
                )
                tree.links.new(
                    emissive_gradient.outputs["Color"], eg_split.inputs["Color"]
                )
                mod = shader_nodes.math(
                    tree.nodes,
                    tree.links,
                    "MULTIPLY",
                    label="Emissive x Gradient",
                    location=(COLUMN_OUTPUT + 200, -680),
                    hide=True,
                ).node
                tree.links.new(strength.outputs["Value"], mod.inputs["Value"])
                tree.links.new(
                    eg_split.outputs["Red"],
                    shader_nodes.socket_by_identifier(mod.inputs, "Value_001"),
                )
                strength_socket = mod.outputs["Value"]
            else:
                strength_socket = strength.outputs["Value"]
            tree.links.new(
                direct_ev_strength_socket(
                    tree,
                    strength_socket,
                    (COLUMN_OUTPUT + 380, -680),
                    "Gradient EmissiveEV",
                ),
                bsdf.inputs["Emission Strength"],
            )
        else:
            bsdf.inputs["Emission Strength"].default_value = 0.0

        tree.links.new(surface, bsdf.inputs["Base Color"])
        self._alpha_mask(tree, data, bsdf, alpha, None)
