from ..blender import shader_nodes
from ..materials.blender.nodes import create_node
from .decal_math import ev_to_linear
from .graph import mix_color_socket
from .interior_parallax_common import InteriorParallaxCore, atlas_depth
from .mat_common import param_float
from .normal_math import create_cp77_normal_texture


class MikoshiParallax(InteriorParallaxCore):
    texture_defaults = {
        "RoomAtlas": r"base\environment\decoration\unique\quest\q105\textures\1x1_dollhouse_paralax.xbm",
        "LayerAtlas": r"base\environment\decoration\unique\quest\q105\textures\1x1_dollhouse_paralax_curtains.xbm",
        "WindowTexture": r"base\surfaces\masks\simple_glass_transparency_m.xbm",
        "Roughness": r"base\surfaces\masks\glass_generic_01_200_r.xbm",
        "Normal": r"engine\textures\editor\normal.xbm",
    }
    atlas_depth_default = 0.0
    position_x_default = 0.5
    position_y_default = 0.5

    def create(self, Data, Mat):
        data = Data if isinstance(Data, dict) else {}
        tree = Mat.node_tree
        bsdf = shader_nodes.principled_bsdf(tree.nodes)
        room_uv, _ = self._room_grid(tree, data, tangent_position=True)
        room_map, _, room_interp = self._interior_uv(
            tree,
            room_uv,
            data,
            atlas_depth(data, self.atlas_depth_default),
            label="Room Interior",
            location=(-1660, 560),
            plane="room",
        )
        layer_depth = max(0.001, 1.0 - param_float(data, "LayerDepth", 0.3))
        layer_map, layer_mask, _ = self._interior_uv(
            tree,
            room_uv,
            data,
            layer_depth,
            label="Layer Interior",
            location=(-1660, 220),
            plane="layer",
        )

        room = self._texture(
            tree, data, "RoomAtlas", room_map, (-860, 560), extension="EXTEND"
        )
        layer = self._texture(
            tree, data, "LayerAtlas", layer_map, (-860, 260), extension="EXTEND"
        )
        window = self._texture(
            tree, data, "WindowTexture", room_uv, (-860, -40), extension="EXTEND"
        )
        color = room.outputs["Color"] if room else (0.0, 0.0, 0.0, 1.0)
        if layer is not None:
            factor = layer.outputs["Alpha"]
            if layer_mask is not None:
                layer_alpha = shader_nodes.math(
                    tree.nodes,
                    tree.links,
                    "MULTIPLY",
                    label="Layer Alpha x Geometry Mask",
                    location=(-680, 360),
                    hide=True,
                ).node
                tree.links.new(layer.outputs["Alpha"], layer_alpha.inputs["Value"])
                tree.links.new(
                    layer_mask,
                    shader_nodes.socket_by_identifier(layer_alpha.inputs, "Value_001"),
                )
                factor = layer_alpha.outputs["Value"]
            color = mix_color_socket(
                tree.nodes,
                tree.links,
                "Room / Layer",
                color,
                layer.outputs["Color"],
                factor,
                (-520, 440),
            )
        if window is not None:
            color = mix_color_socket(
                tree.nodes,
                tree.links,
                "Interior / Window",
                color,
                window.outputs["Color"],
                window.outputs["Alpha"],
                (-300, 440),
            )
        interp_rgb = create_node(
            tree.nodes, "ShaderNodeCombineColor", (-260, 500), label="RoomInterp.xxx"
        )
        for socket in ("Red", "Green", "Blue"):
            tree.links.new(room_interp, interp_rgb.inputs[socket])
        color = mix_color_socket(
            tree.nodes,
            tree.links,
            "Interior x RoomInterp",
            color,
            interp_rgb.outputs["Color"],
            1.0,
            (-80, 440),
            blend_type="MULTIPLY",
            clamp=False,
        )
        tree.links.new(color, bsdf.inputs["Base Color"])
        tree.links.new(color, bsdf.inputs["Emission Color"])
        bsdf.inputs["Emission Strength"].default_value = max(
            0.0, ev_to_linear(param_float(data, "EmissiveEV", 0.0)) - 1.0
        )
        bsdf.inputs["Metallic"].default_value = 1.0
        bsdf.inputs["Roughness"].default_value = 0.0
        normal = create_cp77_normal_texture(
            self,
            tree,
            data,
            uv=room_uv,
            location=(-820, -360),
            default_strength=0.0,
            extension="EXTEND",
        )
        if normal is not None:
            tree.links.new(normal, bsdf.inputs["Normal"])
        bsdf.inputs["Alpha"].default_value = 1.0
