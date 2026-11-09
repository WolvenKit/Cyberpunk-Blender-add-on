from ..blender import shader_nodes
from ..materials.blender.nodes import create_node
from .graph import mix_color_socket
from .interior_parallax_common import (
    InteriorParallaxCore,
    atlas_depth,
    window_day_night_factors,
)
from .mat_common import param_color, param_float
from .normal_math import create_cp77_normal_texture
from .window_parallax_source import build_window_parallax_coordinates, color_overlay_uv


def _replicate(tree, value, location, label):
    node = create_node(tree.nodes, "ShaderNodeCombineXYZ", location, label=label)
    for name in ("X", "Y", "Z"):
        tree.links.new(value, node.inputs[name])
    return node.outputs["Vector"]


class WindowParallaxInterior(InteriorParallaxCore):
    texture_defaults = {
        "RoomAtlas": r"base\surfaces\parallax\placeholder\parallax_day.xbm",
        "LayerAtlas": r"base\surfaces\parallax\placeholder\parallax_day_layer.xbm",
        "Curtain": r"base\surfaces\parallax\placeholder\blinds.xbm",
        "ColorOverlayTexture": r"base\surfaces\parallax\coloroverlay.xbm",
        "WindowTexture": r"base\surfaces\masks\simple_glass_transparency_m.xbm",
        "Roughness": r"base\surfaces\masks\glass_generic_01_200_r.xbm",
        "Normal": r"base\surfaces\masks\glass_generic_01_200_n.xbm",
    }
    room_width_default = 6.0
    room_height_default = 4.0
    room_depth_default = 4.0

    def _light_temperature(self, tree, random, data, location=(120, 120)):
        temperature = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY_ADD",
            label="Night Temperature Preview",
            location=location,
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(
            temperature.inputs, "Value_001"
        ).default_value = 3500.0
        shader_nodes.socket_by_identifier(
            temperature.inputs, "Value_002"
        ).default_value = 2500.0
        tree.links.new(random, temperature.inputs["Value"])
        blackbody = create_node(
            tree.nodes,
            "ShaderNodeBlackbody",
            (location[0] + 180, location[1]),
            label="Night Color Approximation",
        )
        tree.links.new(temperature.outputs["Value"], blackbody.inputs["Temperature"])
        return mix_color_socket(
            tree.nodes,
            tree.links,
            "LightsTempVariationAtNight",
            (1.0, 1.0, 1.0, 1.0),
            blackbody.outputs["Color"],
            max(0.0, min(1.0, param_float(data, "LightsTempVariationAtNight", 0.0))),
            (location[0] + 360, location[1]),
        )

    def _source_window_color(
        self,
        tree,
        base_color,
        overlay,
        tint,
        temp_color,
        view_angle,
        night_factor,
        location=(300, 420),
    ):
        overlay_color = overlay if overlay is not None else None
        if overlay_color is None:
            overlay_node = create_node(
                tree.nodes,
                "ShaderNodeRGB",
                (location[0] - 180, location[1] - 80),
                label="Color Overlay Default",
            )
            overlay_node.outputs["Color"].default_value = (1.0, 1.0, 1.0, 1.0)
            overlay_color = overlay_node.outputs["Color"]

        base_overlay = mix_color_socket(
            tree.nodes,
            tree.links,
            "FinalBaseColor x ColorOverlay",
            base_color,
            overlay_color,
            1.0,
            location,
            blend_type="MULTIPLY",
            clamp=False,
        )
        one_minus = shader_nodes.math(
            tree.nodes,
            tree.links,
            "SUBTRACT",
            1.0,
            label="1 - ViewAngle",
            location=(location[0], location[1] - 180),
            hide=True,
        ).node
        tree.links.new(
            view_angle, shader_nodes.socket_by_identifier(one_minus.inputs, "Value_001")
        )
        cube = shader_nodes.math(
            tree.nodes,
            tree.links,
            "POWER",
            None,
            3.0,
            label="(1 - ViewAngle)^3",
            location=(location[0] + 170, location[1] - 180),
            hide=True,
        ).node
        tree.links.new(one_minus.outputs["Value"], cube.inputs["Value"])
        day_fresnel = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MAXIMUM",
            None,
            0.1,
            label="Day Fresnel Floor",
            location=(location[0] + 340, location[1] - 180),
            hide=True,
        ).node
        tree.links.new(cube.outputs["Value"], day_fresnel.inputs["Value"])
        day = mix_color_socket(
            tree.nodes,
            tree.links,
            "RED Window Day Color",
            base_overlay,
            (1.0, 1.0, 1.0, 1.0),
            day_fresnel.outputs["Value"],
            (location[0] + 520, location[1]),
        )

        night_base = mix_color_socket(
            tree.nodes,
            tree.links,
            "Night Base x Temperature Color",
            base_color,
            temp_color,
            1.0,
            (location[0] + 160, location[1] + 220),
            blend_type="MULTIPLY",
            clamp=False,
        )
        night_base = mix_color_socket(
            tree.nodes,
            tree.links,
            "Night Base x Tint",
            night_base,
            tint,
            1.0,
            (location[0] + 340, location[1] + 220),
            blend_type="MULTIPLY",
            clamp=False,
        )
        night_base = mix_color_socket(
            tree.nodes,
            tree.links,
            "colorAtNight",
            night_base,
            overlay_color,
            1.0,
            (location[0] + 520, location[1] + 220),
            blend_type="MULTIPLY",
            clamp=False,
        )

        white_overlay = mix_color_socket(
            tree.nodes,
            tree.links,
            "White Overlay x Temperature Color",
            overlay_color,
            temp_color,
            1.0,
            (location[0] + 340, location[1] + 380),
            blend_type="MULTIPLY",
            clamp=False,
        )
        white_overlay = mix_color_socket(
            tree.nodes,
            tree.links,
            "White Overlay x Tint",
            white_overlay,
            tint,
            1.0,
            (location[0] + 520, location[1] + 380),
            blend_type="MULTIPLY",
            clamp=False,
        )
        grazing = mix_color_socket(
            tree.nodes,
            tree.links,
            "Night Grazing Color",
            night_base,
            white_overlay,
            cube.outputs["Value"],
            (location[0] + 700, location[1] + 260),
        )
        night = mix_color_socket(
            tree.nodes,
            tree.links,
            "RED Window Night Color",
            (1.0, 1.0, 1.0, 1.0),
            grazing,
            0.95,
            (location[0] + 880, location[1] + 260),
        )
        return mix_color_socket(
            tree.nodes,
            tree.links,
            "RED Window Day / Night",
            day,
            night,
            night_factor,
            (location[0] + 1080, location[1]),
        )

    def create(self, Data, Mat):
        data = Data if isinstance(Data, dict) else {}
        tree = Mat.node_tree
        bsdf = shader_nodes.principled_bsdf(tree.nodes)
        coords = build_window_parallax_coordinates(
            self, tree, data, atlas_depth(data, self.atlas_depth_default)
        )

        room = self._texture(
            tree,
            data,
            "RoomAtlas",
            coords.room_atlas_uv,
            (-900, 720),
            extension="EXTEND",
        )
        layer = self._texture(
            tree,
            data,
            "LayerAtlas",
            coords.layer_atlas_uv,
            (-900, 440),
            extension="EXTEND",
        )
        curtain = self._texture(
            tree,
            data,
            "Curtain",
            coords.curtain_atlas_uv,
            (-900, 160),
            extension="EXTEND",
        )
        window = self._texture(
            tree,
            data,
            "WindowTexture",
            coords.room_uv,
            (-900, -120),
            extension="EXTEND",
        )
        overlay_uv = color_overlay_uv(tree, coords.object_pivot, location=(-1200, -980))
        overlay_node = self._texture(
            tree,
            data,
            "ColorOverlayTexture",
            overlay_uv,
            (-80, -980),
            extension="EXTEND",
        )
        overlay = overlay_node.outputs["Color"] if overlay_node is not None else None

        room_lighting_factor, final_night_factor, time_of_day, room_on_floor = (
            window_day_night_factors(tree, data, coords.room_on_random, (-760, -720))
        )

        if room is not None:
            color, _ = self._night_lit_color(
                tree,
                room.outputs["Color"],
                room.outputs["Alpha"],
                room_lighting_factor.outputs["Value"],
                location=(-720, 760),
                label="Room",
                alpha_power=2.0,
                lighting_scale=1.5,
            )
        else:
            black = create_node(
                tree.nodes, "ShaderNodeRGB", (-720, 760), label="Missing RoomAtlas"
            )
            black.outputs["Color"].default_value = (0.0, 0.0, 0.0, 1.0)
            color = black.outputs["Color"]

        if layer is not None:
            layer_color, _ = self._night_lit_color(
                tree,
                layer.outputs["Color"],
                layer.outputs["Alpha"],
                room_lighting_factor.outputs["Value"],
                location=(-720, 480),
                label="Layer",
            )
            layer_alpha = shader_nodes.math(
                tree.nodes,
                tree.links,
                "MULTIPLY",
                label="Layer Alpha x Geometry Mask",
                location=(-520, 380),
                hide=True,
            ).node
            tree.links.new(layer.outputs["Alpha"], layer_alpha.inputs["Value"])
            tree.links.new(
                coords.layer_mask,
                shader_nodes.socket_by_identifier(layer_alpha.inputs, "Value_001"),
            )
            color = mix_color_socket(
                tree.nodes,
                tree.links,
                "Room / Layer",
                color,
                layer_color,
                layer_alpha.outputs["Value"],
                (-340, 560),
            )

        if curtain is not None:
            curtain_alpha = shader_nodes.math(
                tree.nodes,
                tree.links,
                "MULTIPLY",
                label="Curtain Alpha x Geometry Mask",
                location=(-520, 180),
                hide=True,
            ).node
            tree.links.new(curtain.outputs["Alpha"], curtain_alpha.inputs["Value"])
            tree.links.new(
                coords.curtain_mask,
                shader_nodes.socket_by_identifier(curtain_alpha.inputs, "Value_001"),
            )
            color = mix_color_socket(
                tree.nodes,
                tree.links,
                "Interior / Curtain",
                color,
                curtain.outputs["Color"],
                curtain_alpha.outputs["Value"],
                (-160, 500),
            )

        if window is not None:
            color = mix_color_socket(
                tree.nodes,
                tree.links,
                "Interior / WindowTexture",
                color,
                window.outputs["Color"],
                window.outputs["Alpha"],
                (20, 500),
            )

        interp_rgb = _replicate(tree, coords.room_interp, (20, 620), "roomInterp.xxx")
        depth_color = mix_color_socket(
            tree.nodes,
            tree.links,
            "FinalBaseColor x roomInterp",
            color,
            interp_rgb,
            1.0,
            (200, 500),
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
            location=(520, 500),
        )
        tree.links.new(final_color, bsdf.inputs["Base Color"])
        tree.links.new(final_color, bsdf.inputs["Emission Color"])

        roughness = self._texture(
            tree,
            data,
            "Roughness",
            coords.room_uv,
            (260, -260),
            non_color=True,
            extension="EXTEND",
        )
        if roughness is not None:
            split_rough = create_node(
                tree.nodes,
                "ShaderNodeSeparateColor",
                (440, -260),
                label="SampledRoughness.r",
            )
            tree.links.new(roughness.outputs["Color"], split_rough.inputs["Color"])
            view_rough = shader_nodes.math(
                tree.nodes,
                tree.links,
                "MULTIPLY",
                label="ViewAngle x SampledRoughness",
                location=(620, -260),
                hide=True,
            ).node
            tree.links.new(coords.view_angle, view_rough.inputs["Value"])
            tree.links.new(
                split_rough.outputs["Red"],
                shader_nodes.socket_by_identifier(view_rough.inputs, "Value_001"),
            )
            rough2 = shader_nodes.math(
                tree.nodes,
                tree.links,
                "MULTIPLY",
                None,
                2.0,
                label="RED Window Roughness x2",
                location=(800, -260),
                use_clamp=True,
                hide=True,
            ).node
            tree.links.new(view_rough.outputs["Value"], rough2.inputs["Value"])
            tree.links.new(rough2.outputs["Value"], bsdf.inputs["Roughness"])
        bsdf.inputs["Metallic"].default_value = 1.0

        normal = create_cp77_normal_texture(
            self,
            tree,
            data,
            uv=coords.room_uv,
            location=(260, -500),
            default_strength=0.100000001,
            extension="EXTEND",
        )
        if normal is not None:
            tree.links.new(normal, bsdf.inputs["Normal"])

        if curtain is not None:
            curtain_alpha_socket = curtain.outputs["Alpha"]
        else:
            curtain_default = create_node(
                tree.nodes,
                "ShaderNodeValue",
                (700, -820),
                label="Curtain Alpha Default",
            )
            curtain_default.outputs["Value"].default_value = 0.0
            curtain_alpha_socket = curtain_default.outputs["Value"]
        if room is not None:
            room_alpha_socket = room.outputs["Alpha"]
        else:
            room_alpha_default = create_node(
                tree.nodes, "ShaderNodeValue", (700, -700), label="Room Alpha Default"
            )
            room_alpha_default.outputs["Value"].default_value = 0.0
            room_alpha_socket = room_alpha_default.outputs["Value"]

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
            emissive_ev_default=3.52741003,
            location=(900, -820),
        )
        tree.links.new(emission_strength, bsdf.inputs["Emission Strength"])
        bsdf.inputs["Alpha"].default_value = 1.0
