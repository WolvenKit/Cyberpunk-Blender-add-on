from ..blender import shader_nodes
from ..materials.blender.nodes import create_node
from .bundles import peak_color_socket, scalar_lerp_socket
from .mat_common import param_float
from .metalbase_common import (
    COLUMN_ADJUST,
    COLUMN_COMBINE,
    COLUMN_OUTPUT,
    COLUMN_TEXTURE,
    MetalBaseCore,
)


class MetalBaseProxy(MetalBaseCore):
    texture_defaults = {
        **MetalBaseCore.texture_defaults,
        "WorldColorMap": r"base\surfaces\textures\city_color_d.xbm",
        "WorldHeightMap": r"base\surfaces\textures\city_depth_r.xbm",
    }
    colour_defaults = {
        **MetalBaseCore.colour_defaults,
        "BaseColorScale": (1.0, 1.0, 1.0, 1.0),
        "EmissiveColor": (0.0, 0.0, 0.0, 0.0),
    }
    alpha_threshold_default = 0.381817997

    def _sharpen_uv(self, tree, base_image):
        width = max(1.0, float(base_image.size[0])) if base_image is not None else 1.0
        height = max(1.0, float(base_image.size[1])) if base_image is not None else 1.0
        coord = create_node(
            tree.nodes, "ShaderNodeTexCoord", (-2300, 500), label="Proxy UV"
        )
        split = create_node(
            tree.nodes, "ShaderNodeSeparateXYZ", (-2120, 500), label="UV"
        )
        tree.links.new(coord.outputs["UV"], split.inputs["Vector"])
        values = []
        for source, extent, label, y in (
            (split.outputs["X"], width, "U", 560),
            (split.outputs["Y"], height, "V", 420),
        ):
            scaled = shader_nodes.math(
                tree.nodes,
                tree.links,
                "MULTIPLY_ADD",
                label=f"{label} x Resolution + 0.5",
                location=(-1940, y),
                hide=True,
            ).node
            shader_nodes.socket_by_identifier(
                scaled.inputs, "Value_001"
            ).default_value = extent
            shader_nodes.socket_by_identifier(
                scaled.inputs, "Value_002"
            ).default_value = 0.5
            tree.links.new(source, scaled.inputs["Value"])
            integer = shader_nodes.math(
                tree.nodes,
                tree.links,
                "FLOOR",
                label=f"floor({label})",
                location=(-1760, y + 40),
                hide=True,
            ).node
            fraction = shader_nodes.math(
                tree.nodes,
                tree.links,
                "FRACT",
                label=f"frac({label})",
                location=(-1760, y - 40),
                hide=True,
            ).node
            tree.links.new(scaled.outputs["Value"], integer.inputs["Value"])
            tree.links.new(scaled.outputs["Value"], fraction.inputs["Value"])
            f2 = shader_nodes.math(
                tree.nodes,
                tree.links,
                "MULTIPLY",
                label=f"{label}²",
                location=(-1590, y - 40),
                hide=True,
            ).node
            tree.links.new(fraction.outputs["Value"], f2.inputs["Value"])
            tree.links.new(
                fraction.outputs["Value"],
                shader_nodes.socket_by_identifier(f2.inputs, "Value_001"),
            )
            two_f = shader_nodes.math(
                tree.nodes,
                tree.links,
                "MULTIPLY",
                label=f"2{label}",
                location=(-1590, y - 120),
                hide=True,
            ).node
            shader_nodes.socket_by_identifier(
                two_f.inputs, "Value_001"
            ).default_value = 2.0
            tree.links.new(fraction.outputs["Value"], two_f.inputs["Value"])
            three_minus = shader_nodes.math(
                tree.nodes,
                tree.links,
                "SUBTRACT",
                label=f"3 - 2{label}",
                location=(-1420, y - 120),
                hide=True,
            ).node
            three_minus.inputs["Value"].default_value = 3.0
            tree.links.new(
                two_f.outputs["Value"],
                shader_nodes.socket_by_identifier(three_minus.inputs, "Value_001"),
            )
            smooth = shader_nodes.math(
                tree.nodes,
                tree.links,
                "MULTIPLY",
                label=f"smooth({label})",
                location=(-1250, y - 40),
                hide=True,
            ).node
            tree.links.new(f2.outputs["Value"], smooth.inputs["Value"])
            tree.links.new(
                three_minus.outputs["Value"],
                shader_nodes.socket_by_identifier(smooth.inputs, "Value_001"),
            )
            summed = shader_nodes.math(
                tree.nodes,
                tree.links,
                "ADD",
                label=f"cell + smooth {label}",
                location=(-1080, y),
                hide=True,
            ).node
            tree.links.new(integer.outputs["Value"], summed.inputs["Value"])
            tree.links.new(
                smooth.outputs["Value"],
                shader_nodes.socket_by_identifier(summed.inputs, "Value_001"),
            )
            minus_half = shader_nodes.math(
                tree.nodes,
                tree.links,
                "SUBTRACT",
                label=f"{label} - 0.5",
                location=(-910, y),
                hide=True,
            ).node
            shader_nodes.socket_by_identifier(
                minus_half.inputs, "Value_001"
            ).default_value = 0.5
            tree.links.new(summed.outputs["Value"], minus_half.inputs["Value"])
            normalized = shader_nodes.math(
                tree.nodes,
                tree.links,
                "DIVIDE",
                label=f"{label} / Resolution",
                location=(-740, y),
                hide=True,
            ).node
            shader_nodes.socket_by_identifier(
                normalized.inputs, "Value_001"
            ).default_value = extent
            tree.links.new(minus_half.outputs["Value"], normalized.inputs["Value"])
            values.append(normalized.outputs["Value"])
        combine = create_node(
            tree.nodes, "ShaderNodeCombineXYZ", (-560, 500), label="Sharpened UV"
        )
        tree.links.new(values[0], combine.inputs["X"])
        tree.links.new(values[1], combine.inputs["Y"])
        return combine.outputs["Vector"]

    def _sharpened_channel(self, tree, data, key, uv, target, y):
        ordinary = self._pbr_channel(tree, data, key, target, None, y)
        if ordinary is None:
            return
        sharp = self._texture(
            tree,
            data,
            key,
            (COLUMN_TEXTURE, y - 100),
            uv,
            non_color=True,
            label=f"{key} Sharpened",
        )
        if sharp is None:
            return
        split = create_node(
            tree.nodes,
            "ShaderNodeSeparateColor",
            (COLUMN_ADJUST - 100, y - 100),
            label=f"{key} Sharp.r",
        )
        tree.links.new(sharp.outputs["Color"], split.inputs["Color"])
        adjust = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY_ADD",
            label=f"Sharpened {key}",
            location=(COLUMN_ADJUST + 80, y - 100),
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(
            adjust.inputs, "Value_001"
        ).default_value = param_float(data, f"{key}Scale", 1.0)
        shader_nodes.socket_by_identifier(
            adjust.inputs, "Value_002"
        ).default_value = param_float(data, f"{key}Bias", 0.0)
        adjust.use_clamp = True
        tree.links.new(split.outputs["Red"], adjust.inputs["Value"])
        blended = scalar_lerp_socket(
            tree,
            ordinary,
            adjust.outputs["Value"],
            1.15,
            (COLUMN_COMBINE, y),
            f"{key} Sharpen 1.15",
        )
        tree.links.new(blended, target)

    def _proxy_world_tint(self, tree, data, surface, geometry):
        split_pos = create_node(
            tree.nodes,
            "ShaderNodeSeparateXYZ",
            (100, -980),
            label="Proxy World Position",
        )
        tree.links.new(geometry.outputs["Position"], split_pos.inputs["Vector"])

        uv_values = []
        for source, offset, extent, y, label in (
            (split_pos.outputs["X"], 4100.0, 6000.0, -900, "Proxy World U"),
            (split_pos.outputs["Y"], 2960.0, 6000.0, -1040, "Proxy World V"),
        ):
            add = shader_nodes.math(
                tree.nodes,
                tree.links,
                "ADD",
                label=f"{label} Origin",
                location=(280, y),
                hide=True,
            ).node
            shader_nodes.socket_by_identifier(
                add.inputs, "Value_001"
            ).default_value = offset
            tree.links.new(source, add.inputs["Value"])
            divide = shader_nodes.math(
                tree.nodes,
                tree.links,
                "DIVIDE",
                label=f"{label} Fit",
                location=(460, y),
                hide=True,
            ).node
            shader_nodes.socket_by_identifier(
                divide.inputs, "Value_001"
            ).default_value = extent
            tree.links.new(add.outputs["Value"], divide.inputs["Value"])
            uv_values.append(divide.outputs["Value"])
        uv = create_node(
            tree.nodes, "ShaderNodeCombineXYZ", (640, -970), label="Proxy World Map UV"
        )
        tree.links.new(uv_values[0], uv.inputs["X"])
        tree.links.new(uv_values[1], uv.inputs["Y"])

        world_height = self._texture(
            tree,
            data,
            "WorldHeightMap",
            (820, -1120),
            uv.outputs["Vector"],
            non_color=True,
        )
        world_color = self._texture(
            tree, data, "WorldColorMap", (820, -860), uv.outputs["Vector"]
        )
        if world_height is None or world_color is None:
            return surface

        height_split = create_node(
            tree.nodes,
            "ShaderNodeSeparateColor",
            (1000, -1120),
            label="WorldHeightMap.r",
        )
        tree.links.new(world_height.outputs["Color"], height_split.inputs["Color"])
        max_height = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            label="World Height x625",
            location=(1180, -1120),
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(
            max_height.inputs, "Value_001"
        ).default_value = 625.0
        tree.links.new(height_split.outputs["Red"], max_height.inputs["Value"])
        max_height_safe = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MAXIMUM",
            label="World Height Safe",
            location=(1360, -1120),
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(
            max_height_safe.inputs, "Value_001"
        ).default_value = 1.0e-5
        tree.links.new(max_height.outputs["Value"], max_height_safe.inputs["Value"])
        z_minus = shader_nodes.math(
            tree.nodes,
            tree.links,
            "SUBTRACT",
            label="World Z - 10",
            location=(1000, -1260),
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(
            z_minus.inputs, "Value_001"
        ).default_value = 10.0
        tree.links.new(split_pos.outputs["Z"], z_minus.inputs["Value"])
        z_clamp = shader_nodes.clamp(
            tree.nodes,
            tree.links,
            z_minus.outputs["Value"],
            0.0,
            max_height_safe.outputs["Value"],
            label="World Z in [0, Height]",
            location=(1180, -1260),
        )
        z_ratio = shader_nodes.math(
            tree.nodes,
            tree.links,
            "DIVIDE",
            label="World Z / Height",
            location=(1540, -1260),
            hide=True,
        ).node
        tree.links.new(z_clamp, z_ratio.inputs["Value"])
        tree.links.new(
            max_height_safe.outputs["Value"],
            shader_nodes.socket_by_identifier(z_ratio.inputs, "Value_001"),
        )
        bbox = shader_nodes.math(
            tree.nodes,
            tree.links,
            "SUBTRACT",
            label="Proxy Height Mask",
            location=(1720, -1260),
            hide=True,
        ).node
        bbox.inputs["Value"].default_value = 1.0
        tree.links.new(
            z_ratio.outputs["Value"],
            shader_nodes.socket_by_identifier(bbox.inputs, "Value_001"),
        )

        dot_up = shader_nodes.vector_math(
            tree.nodes,
            tree.links,
            "DOT_PRODUCT",
            label="Normal dot World Z",
            location=(1000, -1460),
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(dot_up.inputs, "Vector_001").default_value = (
            0.0,
            0.0,
            1.0,
        )
        tree.links.new(geometry.outputs["Normal"], dot_up.inputs["Vector"])
        facing_clamp = create_node(
            tree.nodes, "ShaderNodeClamp", (1180, -1460), label="saturate(N dot Z)"
        )
        tree.links.new(dot_up.outputs["Value"], facing_clamp.inputs["Value"])
        facing = shader_nodes.math(
            tree.nodes,
            tree.links,
            "SUBTRACT",
            label="1 - N dot Z",
            location=(1360, -1460),
            hide=True,
        ).node
        facing.inputs["Value"].default_value = 1.0
        tree.links.new(
            facing_clamp.outputs["Result"],
            shader_nodes.socket_by_identifier(facing.inputs, "Value_001"),
        )

        camera = create_node(
            tree.nodes,
            "ShaderNodeCameraData",
            (1000, -1640),
            label="Proxy Camera Distance",
        )
        camera_vector = shader_nodes.vector_math(
            tree.nodes,
            tree.links,
            "SCALE",
            label="Point to Camera",
            location=(1180, -1780),
            hide=True,
        ).node
        tree.links.new(geometry.outputs["Incoming"], camera_vector.inputs["Vector"])
        tree.links.new(camera.outputs["View Distance"], camera_vector.inputs["Scale"])
        camera_split = create_node(
            tree.nodes,
            "ShaderNodeSeparateXYZ",
            (1360, -1780),
            label="Horizontal Camera Delta",
        )
        tree.links.new(camera_vector.outputs["Vector"], camera_split.inputs["Vector"])
        camera_xy = create_node(
            tree.nodes,
            "ShaderNodeCombineXYZ",
            (1540, -1780),
            label="Horizontal Camera Vector",
        )
        tree.links.new(camera_split.outputs["X"], camera_xy.inputs["X"])
        tree.links.new(camera_split.outputs["Y"], camera_xy.inputs["Y"])
        horizontal_distance = shader_nodes.vector_math(
            tree.nodes,
            tree.links,
            "LENGTH",
            label="Horizontal Camera Distance",
            location=(1720, -1780),
            hide=True,
        ).node
        tree.links.new(
            camera_xy.outputs["Vector"], horizontal_distance.inputs["Vector"]
        )

        fade_start = param_float(data, "FadeStart", 600.0)
        fade_end = param_float(data, "FadeEnd", 1200.0)
        if fade_end <= fade_start:
            fade_end = fade_start + 1.0e-4
        distance_max = shader_nodes.clamp(
            tree.nodes,
            tree.links,
            horizontal_distance.outputs["Value"],
            fade_start,
            fade_end,
            label="Fade Distance",
            location=(1180, -1640),
        )
        distance_origin = shader_nodes.math(
            tree.nodes,
            tree.links,
            "SUBTRACT",
            label="Fade Distance Origin",
            location=(1540, -1640),
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(
            distance_origin.inputs, "Value_001"
        ).default_value = fade_start
        tree.links.new(distance_max, distance_origin.inputs["Value"])
        distance_fit = shader_nodes.math(
            tree.nodes,
            tree.links,
            "DIVIDE",
            label="FadeStart..FadeEnd -> 0..1",
            location=(1720, -1640),
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(
            distance_fit.inputs, "Value_001"
        ).default_value = fade_end - fade_start
        tree.links.new(distance_origin.outputs["Value"], distance_fit.inputs["Value"])

        blend_a = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            label="Proxy bbox x facing",
            location=(1900, -1360),
            hide=True,
        ).node
        tree.links.new(bbox.outputs["Value"], blend_a.inputs["Value"])
        tree.links.new(
            facing.outputs["Value"],
            shader_nodes.socket_by_identifier(blend_a.inputs, "Value_001"),
        )
        blend_b = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            label="Proxy x distance fade",
            location=(2080, -1360),
            hide=True,
        ).node
        tree.links.new(blend_a.outputs["Value"], blend_b.inputs["Value"])
        tree.links.new(
            distance_fit.outputs["Value"],
            shader_nodes.socket_by_identifier(blend_b.inputs, "Value_001"),
        )
        blend = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            label="Proxy x height map",
            location=(2260, -1360),
            use_clamp=True,
            hide=True,
        ).node
        tree.links.new(blend_b.outputs["Value"], blend.inputs["Value"])
        tree.links.new(
            height_split.outputs["Red"],
            shader_nodes.socket_by_identifier(blend.inputs, "Value_001"),
        )

        color_split = create_node(
            tree.nodes,
            "ShaderNodeSeparateColor",
            (1180, -860),
            label="WorldColorMap RGB",
        )
        tree.links.new(world_color.outputs["Color"], color_split.inputs["Color"])
        max_rg = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MAXIMUM",
            label="WorldColor max RG",
            location=(1360, -860),
            hide=True,
        ).node
        tree.links.new(color_split.outputs["Red"], max_rg.inputs["Value"])
        tree.links.new(
            color_split.outputs["Green"],
            shader_nodes.socket_by_identifier(max_rg.inputs, "Value_001"),
        )
        max_rgb = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MAXIMUM",
            label="WorldColor max RGB",
            location=(1540, -860),
            hide=True,
        ).node
        tree.links.new(max_rg.outputs["Value"], max_rgb.inputs["Value"])
        tree.links.new(
            color_split.outputs["Blue"],
            shader_nodes.socket_by_identifier(max_rgb.inputs, "Value_001"),
        )

        night_preview = create_node(
            tree.nodes, "ShaderNodeValue", (1900, -1100), label="Time Of Day Preview"
        )
        night_preview.outputs["Value"].default_value = 1.0
        proxy_strength = create_node(
            tree.nodes,
            "ShaderNodeValue",
            (1900, -1020),
            label="SC_ProxiesEmissive.x Preview",
        )
        proxy_strength.outputs["Value"].default_value = 1.0
        factor_time = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            label="Proxy Blend x TimeOfDay",
            location=(2080, -1100),
            hide=True,
        ).node
        tree.links.new(blend.outputs["Value"], factor_time.inputs["Value"])
        tree.links.new(
            night_preview.outputs["Value"],
            shader_nodes.socket_by_identifier(factor_time.inputs, "Value_001"),
        )
        factor_max = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MINIMUM",
            label="Proxy Blend <= WorldColor",
            location=(2260, -1100),
            hide=True,
        ).node
        tree.links.new(factor_time.outputs["Value"], factor_max.inputs["Value"])
        tree.links.new(
            max_rgb.outputs["Value"],
            shader_nodes.socket_by_identifier(factor_max.inputs, "Value_001"),
        )
        factor = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            label="Proxy Blend x Runtime Strength",
            location=(2440, -1100),
            hide=True,
        ).node
        tree.links.new(factor_max.outputs["Value"], factor.inputs["Value"])
        tree.links.new(
            proxy_strength.outputs["Value"],
            shader_nodes.socket_by_identifier(factor.inputs, "Value_001"),
        )

        tinted = self._mix_color(
            tree,
            (2440, -860),
            1.0,
            surface,
            world_color.outputs["Color"],
            blend_type="MULTIPLY",
            label="Surface x WorldColorMap",
        )
        return self._mix_color(
            tree,
            (2640, -960),
            factor.outputs["Value"],
            surface,
            tinted,
            label="Proxy World Color Blend",
        )

    def create(self, Data, Mat):
        data = Data if isinstance(Data, dict) else {}
        tree = Mat.node_tree
        bsdf, sockets = self._bsdf(tree)

        base_path = self._texture_path(data, "BaseColor")
        base_image = self._image_from_rel_path(base_path) if base_path else None
        base = self._texture(tree, data, "BaseColor", (COLUMN_TEXTURE, 680))
        sharp_uv = self._sharpen_uv(tree, base_image)
        sharp_base = self._texture(
            tree,
            data,
            "BaseColor",
            (COLUMN_TEXTURE, 540),
            sharp_uv,
            label="BaseColor Sharpened",
        )
        raw_color = base.outputs["Color"] if base is not None else (1.0, 1.0, 1.0, 1.0)
        if sharp_base is not None:
            raw_color = self._mix_color(
                tree,
                (COLUMN_ADJUST, 620),
                1.15,
                raw_color,
                sharp_base.outputs["Color"],
                label="BaseColor Sharpen 1.15",
            )

        scale, _ = self._colour_scale_socket(
            tree, data, "BaseColorScale", (COLUMN_TEXTURE, 380)
        )
        surface = self._mix_color(
            tree,
            (COLUMN_COMBINE, 620),
            1.0,
            raw_color,
            scale,
            blend_type="MULTIPLY",
            label="ScaledBaseColor",
            clamp_result=True,
        )

        self._sharpened_channel(
            tree, data, "Metalness", sharp_uv, bsdf.inputs["Metallic"], 260
        )
        self._sharpened_channel(
            tree, data, "Roughness", sharp_uv, bsdf.inputs["Roughness"], 60
        )
        geometry = self._geometry_normal(tree, bsdf)

        ev = max(0.0, param_float(data, "EmissiveEV", 0.0))
        mask = self._emissive_mask(tree, data, None) if ev > 0.0 else None
        if mask is not None:
            lifted = self._lift_mask(tree, data, mask)
            tinted = self._emissive_tint(tree, data, raw_color)
            surface_before_emissive = surface
            surface = self._emissive_lerp(tree, lifted, surface, tinted)
            peak = peak_color_socket(
                tree,
                surface_before_emissive,
                (COLUMN_OUTPUT - 620, -560),
                "Scaled Base Peak",
            )
            pixel_brightness = shader_nodes.math(
                tree.nodes,
                tree.links,
                "MULTIPLY",
                label="Peak x EmissiveEV",
                location=(COLUMN_OUTPUT - 400, -560),
                hide=True,
            ).node
            shader_nodes.socket_by_identifier(
                pixel_brightness.inputs, "Value_001"
            ).default_value = ev
            tree.links.new(peak, pixel_brightness.inputs["Value"])
            factor = shader_nodes.math(
                tree.nodes,
                tree.links,
                "MULTIPLY",
                label="Brightness x Lifted Mask",
                location=(COLUMN_OUTPUT - 220, -560),
                hide=True,
            ).node
            tree.links.new(pixel_brightness.outputs["Value"], factor.inputs["Value"])
            tree.links.new(
                lifted, shader_nodes.socket_by_identifier(factor.inputs, "Value_001")
            )
            tree.links.new(
                self._ev_strength(tree, factor.outputs["Value"], ev),
                bsdf.inputs["Emission Strength"],
            )
        else:
            bsdf.inputs["Emission Strength"].default_value = 0.0

        surface = self._proxy_world_tint(tree, data, surface, geometry)
        tree.links.new(surface, bsdf.inputs["Base Color"])
        if mask is not None:
            tree.links.new(surface, bsdf.inputs[sockets["Emission"]])
        self._alpha_mask(
            tree,
            data,
            bsdf,
            base.outputs["Alpha"] if base is not None else None,
            base.image if base is not None else None,
        )
