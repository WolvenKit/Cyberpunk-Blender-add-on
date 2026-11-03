import math

from ..blender import shader_nodes
from ..materials.blender.nodes import CreateShaderNodeValue, create_node
from .bundles import peak_color_socket, scalar_lerp_socket
from .mat_common import param_float
from .metalbase_common import (
    COLUMN_ADJUST,
    COLUMN_COMBINE,
    COLUMN_OUTPUT,
    COLUMN_TEXTURE,
    MetalBaseCore,
)
from .shader_hash import hash13_socket, hash43_sockets


class MetalBaseTrafficLightProxy(MetalBaseCore):
    texture_defaults = {
        **MetalBaseCore.texture_defaults,
        "Emissive": r"engine\textures\editor\white.xbm",
    }
    colour_defaults = {
        **MetalBaseCore.colour_defaults,
        "BaseColorScale": (1.0, 1.0, 1.0, 1.0),
        "EmissiveColor": (1.0, 1.0, 1.0, 1.0),
    }
    normal_strength_default = 5.0
    alpha_threshold_default = 0.381817997

    def _sine_light(
        self, tree, time_socket, mask, *, multiplier, phase, amplitude, bias, y, label
    ):
        scaled = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            label=f"{label} Time",
            location=(COLUMN_TEXTURE, y),
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(
            scaled.inputs, "Value_001"
        ).default_value = multiplier
        tree.links.new(time_socket, scaled.inputs["Value"])
        phase_node = shader_nodes.math(
            tree.nodes,
            tree.links,
            "ADD",
            label=f"{label} Phase",
            location=(COLUMN_ADJUST - 120, y),
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(
            phase_node.inputs, "Value_001"
        ).default_value = phase
        tree.links.new(scaled.outputs["Value"], phase_node.inputs["Value"])
        sine = shader_nodes.math(
            tree.nodes,
            tree.links,
            "SINE",
            label=label,
            location=(COLUMN_ADJUST, y),
            hide=True,
        ).node
        tree.links.new(phase_node.outputs["Value"], sine.inputs["Value"])
        gain = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY_ADD",
            label=f"{label} Window",
            location=(COLUMN_COMBINE - 120, y),
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(
            gain.inputs, "Value_001"
        ).default_value = amplitude
        shader_nodes.socket_by_identifier(gain.inputs, "Value_002").default_value = bias
        gain.use_clamp = True
        tree.links.new(sine.outputs["Value"], gain.inputs["Value"])
        masked = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            label=f"{label} Mask",
            location=(COLUMN_COMBINE + 40, y),
            hide=True,
        ).node
        tree.links.new(mask, masked.inputs["Value"])
        tree.links.new(
            gain.outputs["Value"],
            shader_nodes.socket_by_identifier(masked.inputs, "Value_001"),
        )
        return masked.outputs["Value"]

    def _traffic_masks(self, tree, vertex_color):
        channels = create_node(
            tree.nodes,
            "ShaderNodeSeparateColor",
            (COLUMN_ADJUST - 160, -960),
            label="Traffic Vertex RGB",
        )
        tree.links.new(vertex_color, channels.inputs["Color"])
        rg = shader_nodes.math(
            tree.nodes,
            tree.links,
            "ADD",
            label="R + G",
            location=(COLUMN_ADJUST, -900),
            hide=True,
        ).node
        tree.links.new(channels.outputs["Red"], rg.inputs["Value"])
        tree.links.new(
            channels.outputs["Green"],
            shader_nodes.socket_by_identifier(rg.inputs, "Value_001"),
        )
        total = shader_nodes.math(
            tree.nodes,
            tree.links,
            "ADD",
            label="Traffic Mask Sum",
            location=(COLUMN_COMBINE - 180, -900),
            hide=True,
        ).node
        tree.links.new(rg.outputs["Value"], total.inputs["Value"])
        tree.links.new(
            channels.outputs["Blue"],
            shader_nodes.socket_by_identifier(total.inputs, "Value_001"),
        )
        safe = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MAXIMUM",
            label="Safe Traffic Mask Sum",
            location=(COLUMN_COMBINE - 20, -900),
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(
            safe.inputs, "Value_001"
        ).default_value = 1.0e-5
        tree.links.new(total.outputs["Value"], safe.inputs["Value"])

        remapped = []
        for source, label, y in (
            (channels.outputs["Red"], "Red", -980),
            (channels.outputs["Green"], "Yellow", -1060),
            (channels.outputs["Blue"], "Green", -1140),
        ):
            normalized = shader_nodes.math(
                tree.nodes,
                tree.links,
                "DIVIDE",
                label=f"{label} Normalized",
                location=(COLUMN_COMBINE + 140, y),
                hide=True,
            ).node
            tree.links.new(source, normalized.inputs["Value"])
            tree.links.new(
                safe.outputs["Value"],
                shader_nodes.socket_by_identifier(normalized.inputs, "Value_001"),
            )
            remap = shader_nodes.math(
                tree.nodes,
                tree.links,
                "MULTIPLY_ADD",
                label=f"{label} Remap .95-1",
                location=(COLUMN_COMBINE + 300, y),
                hide=True,
            ).node
            shader_nodes.socket_by_identifier(
                remap.inputs, "Value_001"
            ).default_value = 20.0
            shader_nodes.socket_by_identifier(
                remap.inputs, "Value_002"
            ).default_value = -19.0
            remap.use_clamp = True
            tree.links.new(normalized.outputs["Value"], remap.inputs["Value"])
            remapped.append(remap.outputs["Value"])
        return channels, tuple(remapped)

    def _object_randoms(self, tree, data):
        obj = create_node(
            tree.nodes,
            "ShaderNodeObjectInfo",
            (COLUMN_TEXTURE, -1520),
            label="Traffic Object Position",
        )
        cell_size = max(1.0e-5, param_float(data, "TrafficCellSize", 20.0))
        divide = shader_nodes.vector_math(
            tree.nodes,
            tree.links,
            "DIVIDE",
            label="World / Traffic Cell",
            location=(COLUMN_TEXTURE + 180, -1520),
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(divide.inputs, "Vector_001").default_value = (
            cell_size,
            cell_size,
            1000.0,
        )
        tree.links.new(obj.outputs["Location"], divide.inputs["Vector"])
        subtract = shader_nodes.vector_math(
            tree.nodes,
            tree.links,
            "SUBTRACT",
            label="Traffic Cell Position",
            location=(COLUMN_TEXTURE + 360, -1520),
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(
            subtract.inputs, "Vector_001"
        ).default_value = (cell_size * 0.5, cell_size * 0.5, 500.0)
        tree.links.new(divide.outputs["Vector"], subtract.inputs["Vector"])
        cell_split = create_node(
            tree.nodes,
            "ShaderNodeSeparateXYZ",
            (COLUMN_TEXTURE + 540, -1520),
            label="Traffic Cell Position XYZ",
        )
        tree.links.new(subtract.outputs["Vector"], cell_split.inputs["Vector"])
        rounded_components = []
        for index, name in enumerate(("X", "Y", "Z")):
            rounded_axis = shader_nodes.math(
                tree.nodes,
                tree.links,
                "ROUND",
                label=f"round(Traffic Cell {name})",
                location=(COLUMN_TEXTURE + 700, -1440 - index * 100),
                hide=True,
            ).node
            tree.links.new(cell_split.outputs[name], rounded_axis.inputs["Value"])
            rounded_components.append(rounded_axis.outputs["Value"])
        rounded = create_node(
            tree.nodes,
            "ShaderNodeCombineXYZ",
            (COLUMN_TEXTURE + 860, -1520),
            label="Rounded Traffic Cell",
        )
        for source, name in zip(rounded_components, ("X", "Y", "Z")):
            tree.links.new(source, rounded.inputs[name])

        phase_hash = hash13_socket(
            tree,
            rounded.outputs["Vector"],
            (COLUMN_TEXTURE + 1040, -1520),
            "Traffic hash13",
        )
        phase4 = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            label="Hash x 4",
            location=(COLUMN_TEXTURE + 3000, -1520),
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(
            phase4.inputs, "Value_001"
        ).default_value = 4.0
        tree.links.new(phase_hash, phase4.inputs["Value"])
        phase_floor = shader_nodes.math(
            tree.nodes,
            tree.links,
            "FLOOR",
            label="4 Traffic Variants",
            location=(COLUMN_TEXTURE + 3160, -1520),
            hide=True,
        ).node
        tree.links.new(phase4.outputs["Value"], phase_floor.inputs["Value"])
        phase = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            label="Traffic Phase",
            location=(COLUMN_TEXTURE + 3320, -1520),
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(phase.inputs, "Value_001").default_value = (
            math.pi / 4.0
        )
        tree.links.new(phase_floor.outputs["Value"], phase.inputs["Value"])

        floor_location = shader_nodes.vector_math(
            tree.nodes,
            tree.links,
            "FLOOR",
            label="floor(Object Position)",
            location=(COLUMN_TEXTURE + 180, -1900),
            hide=True,
        ).node
        tree.links.new(obj.outputs["Location"], floor_location.inputs["Vector"])
        color_hash, brightness_hash = hash43_sockets(
            tree,
            floor_location.outputs["Vector"],
            (COLUMN_TEXTURE + 380, -1900),
            "Traffic hash43",
        )

        variation_scale = shader_nodes.vector_math(
            tree.nodes,
            tree.links,
            "SCALE",
            label="Color Variation x .04",
            location=(COLUMN_TEXTURE + 580, -1700),
            hide=True,
        ).node
        variation_scale.inputs["Scale"].default_value = 0.04
        tree.links.new(color_hash, variation_scale.inputs["Vector"])
        variation = shader_nodes.vector_math(
            tree.nodes,
            tree.links,
            "ADD",
            label="Color Variation ±.02",
            location=(COLUMN_TEXTURE + 760, -1700),
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(
            variation.inputs, "Vector_001"
        ).default_value = (-0.02, -0.02, -0.02)
        tree.links.new(variation_scale.outputs["Vector"], variation.inputs["Vector"])

        brightness = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY_ADD",
            label="Random Brightness .5-1",
            location=(COLUMN_TEXTURE + 580, -1800),
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(
            brightness.inputs, "Value_001"
        ).default_value = 0.5
        shader_nodes.socket_by_identifier(
            brightness.inputs, "Value_002"
        ).default_value = 0.5
        tree.links.new(brightness_hash, brightness.inputs["Value"])
        return (
            phase.outputs["Value"],
            variation.outputs["Vector"],
            brightness.outputs["Value"],
        )

    def create(self, Data, Mat):
        data = Data if isinstance(Data, dict) else {}
        tree = Mat.node_tree
        bsdf, sockets = self._bsdf(tree)

        base = self._texture(tree, data, "BaseColor", (COLUMN_TEXTURE, 680))
        surface, _ = self._scaled_base_color(tree, data, base)
        self._pbr_channel(tree, data, "Metalness", bsdf.inputs["Metallic"], None, 300)
        self._pbr_channel(tree, data, "Roughness", bsdf.inputs["Roughness"], None, 120)
        self._normal(tree, data, bsdf, None)

        emissive_sample = self._emissive_mask(tree, data, None)
        if emissive_sample is None:
            tree.links.new(surface, bsdf.inputs["Base Color"])
            bsdf.inputs["Emission Strength"].default_value = 0.0
            self._alpha_mask(
                tree,
                data,
                bsdf,
                base.outputs["Alpha"] if base else None,
                base.image if base else None,
            )
            return

        lifted = self._lift_mask(tree, data, emissive_sample)
        vertex = create_node(
            tree.nodes,
            "ShaderNodeVertexColor",
            (COLUMN_TEXTURE, -980),
            label="Traffic Vertex Masks",
        )
        raw_channels, masks = self._traffic_masks(tree, vertex.outputs["Color"])
        # ShaderNodeMix cannot take scalar sockets as an RGBA tuple. Build the
        # remapped RGB explicitly for peak testing and colour composition.
        mask_rgb = create_node(
            tree.nodes,
            "ShaderNodeCombineColor",
            (COLUMN_COMBINE + 500, -1040),
            label="Traffic Remapped RGB",
        )
        mask_rgb.mode = "RGB"
        for socket, name in zip(masks, ("Red", "Green", "Blue")):
            tree.links.new(socket, mask_rgb.inputs[name])
        peak = peak_color_socket(
            tree,
            mask_rgb.outputs["Color"],
            (COLUMN_OUTPUT - 760, -920),
            "Traffic Remapped Peak",
        )
        is_light_test = shader_nodes.math(
            tree.nodes,
            tree.links,
            "GREATER_THAN",
            label="Is Traffic Light",
            location=(COLUMN_OUTPUT - 440, -920),
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(
            is_light_test.inputs, "Value_001"
        ).default_value = 0.5
        tree.links.new(peak, is_light_test.inputs["Value"])
        is_light = is_light_test.outputs["Value"]

        time = self._time(tree, (COLUMN_TEXTURE, -1260), label="Traffic Time")
        speed = param_float(data, "TrafficSpeed", 0.5)
        speed_node = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            label="TrafficSpeed",
            location=(COLUMN_ADJUST - 160, -1260),
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(
            speed_node.inputs, "Value_001"
        ).default_value = speed
        tree.links.new(time.outputs["Value"], speed_node.inputs["Value"])
        phase, color_variation, random_brightness = self._object_randoms(tree, data)
        animated_time = shader_nodes.math(
            tree.nodes,
            tree.links,
            "ADD",
            label="Traffic Time + Quantized Offset",
            location=(COLUMN_ADJUST + 20, -1260),
            hide=True,
        ).node
        tree.links.new(speed_node.outputs["Value"], animated_time.inputs["Value"])
        tree.links.new(
            phase, shader_nodes.socket_by_identifier(animated_time.inputs, "Value_001")
        )

        red_on = self._sine_light(
            tree,
            animated_time.outputs["Value"],
            masks[0],
            multiplier=1.0,
            phase=-4.0,
            amplitude=4.0,
            bias=0.5,
            y=-1260,
            label="Red Light",
        )
        green_on = self._sine_light(
            tree,
            animated_time.outputs["Value"],
            masks[2],
            multiplier=1.0,
            phase=-0.6,
            amplitude=6.0,
            bias=-1.0,
            y=-1360,
            label="Green Light",
        )
        yellow_on = self._sine_light(
            tree,
            animated_time.outputs["Value"],
            masks[1],
            multiplier=2.0,
            phase=0.5,
            amplitude=24.0,
            bias=-22.0,
            y=-1460,
            label="Yellow Light",
        )
        max_rg = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MAXIMUM",
            label="Traffic Emission RG",
            location=(COLUMN_OUTPUT - 500, -1340),
            hide=True,
        ).node
        tree.links.new(red_on, max_rg.inputs["Value"])
        tree.links.new(
            green_on, shader_nodes.socket_by_identifier(max_rg.inputs, "Value_001")
        )
        traffic_on = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MAXIMUM",
            label="Traffic Emission",
            location=(COLUMN_OUTPUT - 340, -1340),
            hide=True,
        ).node
        tree.links.new(max_rg.outputs["Value"], traffic_on.inputs["Value"])
        tree.links.new(
            yellow_on, shader_nodes.socket_by_identifier(traffic_on.inputs, "Value_001")
        )
        traffic_emission = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            label="Traffic Emission x Random Brightness",
            location=(COLUMN_OUTPUT - 180, -1340),
            hide=True,
        ).node
        tree.links.new(traffic_on.outputs["Value"], traffic_emission.inputs["Value"])
        tree.links.new(
            random_brightness,
            shader_nodes.socket_by_identifier(traffic_emission.inputs, "Value_001"),
        )

        traffic_color = create_node(
            tree.nodes,
            "ShaderNodeCombineColor",
            (COLUMN_OUTPUT - 640, -1080),
            label="Traffic Emission Color",
        )
        traffic_color.mode = "RGB"
        weighted_colors = (
            (masks[0], (1.0, 0.006, 0.002)),
            (masks[1], (0.7, 0.25, 0.003)),
            (masks[2], (0.01, 0.7, 0.003)),
        )
        for channel_index, channel_name in enumerate(("Red", "Green", "Blue")):
            terms = []
            for index, (weight, color) in enumerate(weighted_colors):
                term = shader_nodes.math(
                    tree.nodes,
                    tree.links,
                    "MULTIPLY",
                    label=f"Traffic {channel_name} {index}",
                    location=(
                        COLUMN_OUTPUT - 980 + index * 130,
                        -1000 - channel_index * 80,
                    ),
                    hide=True,
                ).node
                shader_nodes.socket_by_identifier(
                    term.inputs, "Value_001"
                ).default_value = color[channel_index]
                tree.links.new(weight, term.inputs["Value"])
                terms.append(term.outputs["Value"])
            first = shader_nodes.math(
                tree.nodes,
                tree.links,
                "ADD",
                label=f"Traffic {channel_name} RG",
                location=(COLUMN_OUTPUT - 540, -1000 - channel_index * 80),
                hide=True,
            ).node
            tree.links.new(terms[0], first.inputs["Value"])
            tree.links.new(
                terms[1], shader_nodes.socket_by_identifier(first.inputs, "Value_001")
            )
            final = shader_nodes.math(
                tree.nodes,
                tree.links,
                "ADD",
                label=f"Traffic {channel_name}",
                location=(COLUMN_OUTPUT - 380, -1000 - channel_index * 80),
                hide=True,
            ).node
            tree.links.new(first.outputs["Value"], final.inputs["Value"])
            tree.links.new(
                terms[2], shader_nodes.socket_by_identifier(final.inputs, "Value_001")
            )
            tree.links.new(final.outputs["Value"], traffic_color.inputs[channel_name])

        randomized_color = create_node(
            tree.nodes,
            "ShaderNodeMix",
            (COLUMN_OUTPUT - 180, -1080),
            blend_type="ADD",
            label="Traffic Color + Random Variation",
        )
        randomized_color.data_type = "RGBA"
        shader_nodes.socket_by_identifier(
            randomized_color.inputs, "Factor_Float"
        ).default_value = 1.0
        randomized_color.clamp_result = True
        tree.links.new(
            traffic_color.outputs["Color"],
            shader_nodes.socket_by_identifier(randomized_color.inputs, "A_Color"),
        )
        tree.links.new(
            color_variation,
            shader_nodes.socket_by_identifier(randomized_color.inputs, "B_Color"),
        )

        traffic_brightness = scalar_lerp_socket(
            tree,
            0.1,
            1.0,
            traffic_emission.outputs["Value"],
            (COLUMN_OUTPUT, -1200),
            "Traffic Lit Brightness",
        )
        grey = create_node(
            tree.nodes,
            "ShaderNodeCombineColor",
            (COLUMN_OUTPUT + 160, -1200),
            label="Traffic Brightness.xxx",
        )
        grey.mode = "RGB"
        for name in ("Red", "Green", "Blue"):
            tree.links.new(traffic_brightness, grey.inputs[name])
        traffic_tinted = self._mix_color(
            tree,
            (COLUMN_OUTPUT + 340, -1080),
            1.0,
            shader_nodes.socket_by_identifier(randomized_color.outputs, "Result_Color"),
            grey.outputs["Color"],
            blend_type="MULTIPLY",
            label="Traffic Emissive Base",
        )

        ordinary_tint = self._emissive_tint(
            tree, data, base.outputs["Color"] if base else surface
        )
        emissive_base = self._mix_color(
            tree,
            (COLUMN_OUTPUT + 520, -900),
            is_light,
            ordinary_tint,
            traffic_tinted,
            label="Traffic / Ordinary Emissive",
        )
        final_surface = self._emissive_lerp(
            tree, emissive_sample, surface, emissive_base
        )
        tree.links.new(final_surface, bsdf.inputs["Base Color"])
        tree.links.new(final_surface, bsdf.inputs[sockets["Emission"]])

        white_r = shader_nodes.math(
            tree.nodes,
            tree.links,
            "GREATER_THAN",
            label="White R",
            location=(COLUMN_OUTPUT - 760, -720),
            hide=True,
        ).node
        white_g = shader_nodes.math(
            tree.nodes,
            tree.links,
            "GREATER_THAN",
            label="White G",
            location=(COLUMN_OUTPUT - 600, -720),
            hide=True,
        ).node
        white_b = shader_nodes.math(
            tree.nodes,
            tree.links,
            "GREATER_THAN",
            label="White B",
            location=(COLUMN_OUTPUT - 440, -720),
            hide=True,
        ).node
        for node, source in zip(
            (white_r, white_g, white_b),
            (
                raw_channels.outputs["Red"],
                raw_channels.outputs["Green"],
                raw_channels.outputs["Blue"],
            ),
        ):
            shader_nodes.socket_by_identifier(
                node.inputs, "Value_001"
            ).default_value = 0.9
            tree.links.new(source, node.inputs["Value"])
        white_rg = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            label="White RG",
            location=(COLUMN_OUTPUT - 280, -720),
            hide=True,
        ).node
        tree.links.new(white_r.outputs["Value"], white_rg.inputs["Value"])
        tree.links.new(
            white_g.outputs["Value"],
            shader_nodes.socket_by_identifier(white_rg.inputs, "Value_001"),
        )
        is_white = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            label="Is White",
            location=(COLUMN_OUTPUT - 120, -720),
            hide=True,
        ).node
        tree.links.new(white_rg.outputs["Value"], is_white.inputs["Value"])
        tree.links.new(
            white_b.outputs["Value"],
            shader_nodes.socket_by_identifier(is_white.inputs, "Value_001"),
        )
        tod = CreateShaderNodeValue(
            tree, 1.0, COLUMN_OUTPUT + 40, -720, "TimeOfDayBrightness Preview"
        )
        tod_factor = scalar_lerp_socket(
            tree,
            1.0,
            tod.outputs["Value"],
            is_white.outputs["Value"],
            (COLUMN_OUTPUT + 200, -720),
            "White Time Of Day",
        )

        traffic_factor = scalar_lerp_socket(
            tree,
            1.0,
            traffic_emission.outputs["Value"],
            is_light,
            (COLUMN_OUTPUT + 40, -1460),
            "Traffic Emission Factor",
        )
        mask_traffic = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            label="Lifted Mask x Traffic",
            location=(COLUMN_OUTPUT + 360, -1400),
            hide=True,
        ).node
        tree.links.new(lifted, mask_traffic.inputs["Value"])
        tree.links.new(
            traffic_factor,
            shader_nodes.socket_by_identifier(mask_traffic.inputs, "Value_001"),
        )
        final_mask = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            label="Emissive Mask x Time Of Day",
            location=(COLUMN_OUTPUT + 520, -1400),
            hide=True,
        ).node
        tree.links.new(mask_traffic.outputs["Value"], final_mask.inputs["Value"])
        tree.links.new(
            tod_factor,
            shader_nodes.socket_by_identifier(final_mask.inputs, "Value_001"),
        )
        ev = max(0.0, param_float(data, "EmissiveEV", 4.0))
        tree.links.new(
            self._ev_strength(tree, final_mask.outputs["Value"], ev),
            bsdf.inputs["Emission Strength"],
        )

        self._alpha_mask(
            tree,
            data,
            bsdf,
            base.outputs["Alpha"] if base else None,
            base.image if base else None,
        )
