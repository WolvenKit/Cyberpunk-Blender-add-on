from ..blender import shader_nodes
from ..materials.blender.nodes import create_node
from .graph import mix_color_socket
from .interior_parallax_common import atlas_depth, window_day_night_factors
from .mat_common import param_color
from .window_parallax_interior import WindowParallaxInterior, _replicate
from .window_parallax_source import build_window_parallax_coordinates, color_overlay_uv


class WindowParallaxInteriorProxy(WindowParallaxInterior):
    texture_defaults = {
        "RoomAtlas": r"base\surfaces\parallax\placeholder\parallax_day.xbm",
        "Curtain": r"base\surfaces\parallax\placeholder\blinds.xbm",
        "ColorOverlayTexture": r"base\surfaces\parallax\coloroverlay.xbm",
    }
    atlas_depth_default = 0.0
    room_width_default = 6.0
    room_height_default = 4.0
    room_depth_default = 4.0

    def create(self, Data, Mat):
        data = Data if isinstance(Data, dict) else {}
        tree = Mat.node_tree
        bsdf = shader_nodes.principled_bsdf(tree.nodes)
        coords = build_window_parallax_coordinates(
            self,
            tree,
            data,
            atlas_depth(data, self.atlas_depth_default),
            include_layer=False,
        )

        room = self._texture(
            tree,
            data,
            "RoomAtlas",
            coords.room_atlas_uv,
            (-900, 620),
            extension="EXTEND",
        )
        curtain = self._texture(
            tree,
            data,
            "Curtain",
            coords.curtain_atlas_uv,
            (-900, 260),
            extension="EXTEND",
        )
        overlay_uv = color_overlay_uv(tree, coords.object_pivot, location=(-1200, -900))
        overlay_node = self._texture(
            tree,
            data,
            "ColorOverlayTexture",
            overlay_uv,
            (-80, -900),
            extension="EXTEND",
        )
        overlay = overlay_node.outputs["Color"] if overlay_node is not None else None

        room_lighting_factor, final_night_factor, time_of_day, room_on_floor = (
            window_day_night_factors(tree, data, coords.room_on_random, (-740, -620))
        )

        if room is not None:
            color, _ = self._night_lit_color(
                tree,
                room.outputs["Color"],
                room.outputs["Alpha"],
                room_lighting_factor.outputs["Value"],
                location=(-700, 700),
                label="Room",
                alpha_power=2.0,
                lighting_scale=1.5,
            )
        else:
            black = create_node(
                tree.nodes, "ShaderNodeRGB", (-700, 700), label="Missing RoomAtlas"
            )
            black.outputs["Color"].default_value = (0.0, 0.0, 0.0, 1.0)
            color = black.outputs["Color"]

        if curtain is not None:
            curtain_alpha = shader_nodes.math(
                tree.nodes,
                tree.links,
                "MULTIPLY",
                label="Curtain Alpha x Geometry Mask",
                location=(-520, 260),
                hide=True,
            ).node
            tree.links.new(curtain.outputs["Alpha"], curtain_alpha.inputs["Value"])
            tree.links.new(
                coords.curtain_mask,
                shader_nodes.socket_by_identifier(curtain_alpha.inputs, "Value_001"),
            )
            curtain_mix = create_node(
                tree.nodes, "ShaderNodeMix", (-160, 520), label="Interior / Curtain"
            )
            curtain_mix.data_type = "RGBA"
            tree.links.new(
                curtain_alpha.outputs["Value"],
                shader_nodes.socket_by_identifier(curtain_mix.inputs, "Factor_Float"),
            )
            tree.links.new(
                color, shader_nodes.socket_by_identifier(curtain_mix.inputs, "A_Color")
            )
            tree.links.new(
                curtain.outputs["Color"],
                shader_nodes.socket_by_identifier(curtain_mix.inputs, "B_Color"),
            )
            color = shader_nodes.socket_by_identifier(
                curtain_mix.outputs, "Result_Color"
            )

        interp_rgb = _replicate(tree, coords.room_interp, (20, 620), "roomInterp.xxx")
        depth_color = mix_color_socket(
            tree.nodes,
            tree.links,
            "FinalBaseColor x roomInterp",
            color,
            interp_rgb,
            1.0,
            (200, 520),
            blend_type="MULTIPLY",
            clamp=False,
        )
        tint = create_node(
            tree.nodes, "ShaderNodeRGB", (240, 180), label="TintColorAtNight"
        )
        tint.outputs["Color"].default_value = param_color(
            data, "TintColorAtNight", (1.0, 1.0, 1.0, 0.0)
        )
        temp_color = self._light_temperature(
            tree, coords.random, data, location=(240, 40)
        )
        final_color = self._source_window_color(
            tree,
            depth_color,
            overlay,
            tint.outputs["Color"],
            temp_color,
            coords.view_angle,
            final_night_factor.outputs["Value"],
            location=(520, 520),
        )
        tree.links.new(final_color, bsdf.inputs["Base Color"])
        tree.links.new(final_color, bsdf.inputs["Emission Color"])

        roughness = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            None,
            0.2,
            label="Proxy Roughness = ViewAngle x 0.2",
            location=(620, -240),
            use_clamp=True,
            hide=True,
        ).node
        tree.links.new(coords.view_angle, roughness.inputs["Value"])
        tree.links.new(roughness.outputs["Value"], bsdf.inputs["Roughness"])
        bsdf.inputs["Metallic"].default_value = 1.0
        geometry = create_node(
            tree.nodes, "ShaderNodeNewGeometry", (400, -420), label="Proxy World Normal"
        )
        tree.links.new(geometry.outputs["Normal"], bsdf.inputs["Normal"])

        if curtain is not None:
            curtain_alpha_socket = curtain.outputs["Alpha"]
        else:
            curtain_default = create_node(
                tree.nodes,
                "ShaderNodeValue",
                (700, -760),
                label="Curtain Alpha Default",
            )
            curtain_default.outputs["Value"].default_value = 0.0
            curtain_alpha_socket = curtain_default.outputs["Value"]
        if room is not None:
            room_alpha_socket = room.outputs["Alpha"]
        else:
            room_default = create_node(
                tree.nodes, "ShaderNodeValue", (700, -640), label="Room Alpha Default"
            )
            room_default.outputs["Value"].default_value = 0.0
            room_alpha_socket = room_default.outputs["Value"]

        emission_strength, _ = self._window_emission_strength(
            tree,
            data,
            room_alpha=room_alpha_socket,
            room_hit_y=coords.room_hit_y,
            room_interp=coords.room_interp,
            curtain_alpha=curtain_alpha_socket,
            curtain_mask=coords.curtain_mask,
            overlay=overlay,
            time_of_day=time_of_day.outputs["Value"],
            turned_on=room_on_floor.outputs["Value"],
            emissive_ev_default=4.0,
            location=(900, -780),
        )
        tree.links.new(emission_strength, bsdf.inputs["Emission Strength"])
        bsdf.inputs["Alpha"].default_value = 1.0
