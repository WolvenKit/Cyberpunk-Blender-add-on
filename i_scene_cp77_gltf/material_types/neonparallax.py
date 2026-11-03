import hashlib

from ..bartmoss.scalar import clamp01, lerp
from ..blender import shader_nodes
from ..materials.cache_identity import filtered_material_data_identity
from .bundles import material_bundle_node
from .decal_math import ev_to_linear
from .graph import (
    color_channel_socket,
    mix_color_socket,
    mix_scalar_socket,
    rgb_socket,
    set_alpha_clip,
    value_socket,
)
from .mat_common import (
    MaterialTypeBase,
    find_input,
    get_or_build_node_group,
    new_labeled_node,
    param_color,
    param_float,
    param_texture_path,
    param_vector,
)
from .parallax_common import create_camera_forward_parallax_offset, create_tiled_uv

_MAX_PARALLAX_STEPS = 24

_CACHE_PARAMETERS = frozenset(
    {
        "BaseColor",
        "GradientMap",
        "Metalness",
        "Roughness",
        "Emissive",
        "ParallaxDepth",
        "UvTilingX",
        "UvTilingY",
        "UvOffsetX",
        "UvOffsetY",
        "ParallaxFlip",
        "UseGradientMapMode",
        "BaseColorScale",
        "BaseColorScaleEdgeStart",
        "BaseColorScaleEdgeEnd",
        "MetalnessScale",
        "MetalnessBias",
        "RoughnessScale",
        "RoughnessBias",
        "EmissiveEV",
        "AlphaThreshold",
    }
)


def material_cache_identity(raw_material):
    return filtered_material_data_identity(raw_material, _CACHE_PARAMETERS)


class NeonParallax(MaterialTypeBase):
    texture_defaults = {
        "BaseColor": r"engine\textures\editor\white.xbm",
        "GradientMap": r"engine\textures\editor\white.xbm",
        "Metalness": r"engine\textures\editor\black.xbm",
        "Roughness": r"engine\textures\editor\white.xbm",
        "Emissive": r"engine\textures\editor\black.xbm",
    }

    def _load_images(self, data):
        return {
            "BaseColor": self._load_relative_image(
                param_texture_path(data, "BaseColor")
                or self.texture_defaults["BaseColor"],
                error_label="neon parallax base color",
            ),
            "GradientMap": self._load_relative_image(
                param_texture_path(data, "GradientMap")
                or self.texture_defaults["GradientMap"],
                error_label="neon parallax gradient",
            ),
            "Metalness": self._load_relative_image(
                param_texture_path(data, "Metalness")
                or self.texture_defaults["Metalness"],
                non_color=True,
                error_label="neon parallax metalness",
            ),
            "Roughness": self._load_relative_image(
                param_texture_path(data, "Roughness")
                or self.texture_defaults["Roughness"],
                non_color=True,
                error_label="neon parallax roughness",
            ),
            "Emissive": self._load_relative_image(
                param_texture_path(data, "Emissive")
                or self.texture_defaults["Emissive"],
                non_color=True,
                error_label="neon parallax emissive",
            ),
        }

    @staticmethod
    def _sample(
        nodes, links, image, vector, name, location, fallback=(1.0, 1.0, 1.0, 1.0)
    ):
        if image is None:
            color = rgb_socket(nodes, f"{name} Fallback", fallback, location)
            alpha = value_socket(
                nodes,
                f"{name} Alpha Fallback",
                fallback[3],
                (location[0], location[1] - 80),
            )
            return color, alpha
        node = new_labeled_node(nodes, "ShaderNodeTexImage", name, location)
        node.image = image
        node.extension = "EXTEND"
        links.new(vector, node.inputs["Vector"])
        return node.outputs["Color"], node.outputs["Alpha"]

    def _build_sample_layer(
        self,
        tree,
        images,
        uv,
        color_scale,
        use_gradient,
        label,
        x,
        y,
    ):
        nodes = tree.nodes
        links = tree.links
        base_color, sampled_alpha = self._sample(
            nodes,
            links,
            images["BaseColor"],
            uv,
            f"{label} BaseColor",
            (x, y),
        )
        if use_gradient:
            lookup = color_channel_socket(
                nodes,
                links,
                base_color,
                f"{label} Gradient Coordinate",
                (x + 180, y),
                channel="Red",
                mode="RGB",
            )
            combine = new_labeled_node(
                nodes, "ShaderNodeCombineXYZ", f"{label} Gradient UV", (x + 340, y)
            )
            links.new(lookup, combine.inputs["X"])
            combine.inputs["Y"].default_value = 0.5
            gradient_color, gradient_alpha = self._sample(
                nodes,
                links,
                images["GradientMap"],
                combine.outputs["Vector"],
                f"{label} GradientMap",
                (x + 500, y),
                fallback=(0.5, 0.5, 0.5, 1.0),
            )
            emissive_color, _ = self._sample(
                nodes,
                links,
                images["Emissive"],
                combine.outputs["Vector"],
                f"{label} Emissive Gradient",
                (x + 500, y - 180),
            )
            emission = color_channel_socket(
                nodes,
                links,
                emissive_color,
                f"{label} Emission Mask",
                (x + 680, y - 180),
                channel="Red",
                mode="RGB",
            )
            alpha = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                gradient_alpha,
                sampled_alpha,
                name=f"{label} Alpha",
                location=(x + 680, y + 40),
            )
            layer_color = gradient_color
        else:
            emissive_color, _ = self._sample(
                nodes,
                links,
                images["Emissive"],
                uv,
                f"{label} Emissive",
                (x + 180, y - 180),
            )
            emission = color_channel_socket(
                nodes,
                links,
                emissive_color,
                f"{label} Emission Mask",
                (x + 360, y - 180),
                channel="Red",
                mode="RGB",
            )
            alpha = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                sampled_alpha,
                sampled_alpha,
                name=f"{label} Alpha",
                location=(x + 360, y + 40),
            )
            layer_color = base_color

        color = mix_color_socket(
            nodes,
            links,
            f"{label} Color Scale",
            layer_color,
            color_scale,
            1.0,
            (x + 850, y),
            blend_type="MULTIPLY",
            clamp=False,
        )
        metal_color, _ = self._sample(
            nodes,
            links,
            images["Metalness"],
            uv,
            f"{label} Metalness",
            (x + 180, y - 340),
        )
        rough_color, _ = self._sample(
            nodes,
            links,
            images["Roughness"],
            uv,
            f"{label} Roughness",
            (x + 180, y - 500),
        )
        metal = color_channel_socket(
            nodes,
            links,
            metal_color,
            f"{label} Metal",
            (x + 360, y - 340),
            channel="Red",
            mode="RGB",
        )
        rough = color_channel_socket(
            nodes,
            links,
            rough_color,
            f"{label} Rough",
            (x + 360, y - 500),
            channel="Red",
            mode="RGB",
        )
        return color, metal, rough, emission, alpha

    @staticmethod
    def _sample_layer_group_name(images, use_gradient):
        image_parts = []
        for key in sorted(images):
            image = images[key]
            if image is None:
                image_parts.append(f"{key}=none")
                continue
            image_parts.append(
                "|".join(
                    (
                        key,
                        str(getattr(image, "name", "")),
                        str(
                            getattr(image, "filepath_raw", "")
                            or getattr(image, "filepath", "")
                        ),
                        f"{int(image.size[0])}x{int(image.size[1])}",
                        str(
                            getattr(
                                getattr(image, "colorspace_settings", None), "name", ""
                            )
                        ),
                    )
                )
            )
        image_parts.append(f"gradient={int(bool(use_gradient))}")
        digest = hashlib.blake2b(
            "||".join(image_parts).encode("utf-8"), digest_size=10
        ).hexdigest()
        return f"CP77 Neon Parallax Sample {digest} v1"

    def _sample_layer_group(self, images, use_gradient):
        group_name = self._sample_layer_group_name(images, use_gradient)

        def build(group):
            group_input = new_labeled_node(
                group.nodes, "NodeGroupInput", "Inputs", (-900, 0)
            )
            group_output = new_labeled_node(
                group.nodes, "NodeGroupOutput", "Outputs", (900, 0)
            )
            color, metal, rough, emission, alpha = self._build_sample_layer(
                group,
                images,
                group_input.outputs["UV"],
                group_input.outputs["Color Scale"],
                use_gradient,
                "Sample",
                -650,
                250,
            )
            group.links.new(color, group_output.inputs["Color"])
            group.links.new(metal, group_output.inputs["Metalness"])
            group.links.new(rough, group_output.inputs["Roughness"])
            group.links.new(emission, group_output.inputs["Emission"])
            group.links.new(alpha, group_output.inputs["Alpha"])

        return get_or_build_node_group(
            group_name,
            (("NodeSocketVector", "UV"), ("NodeSocketColor", "Color Scale")),
            (
                ("NodeSocketColor", "Color"),
                ("NodeSocketFloat", "Metalness"),
                ("NodeSocketFloat", "Roughness"),
                ("NodeSocketFloat", "Emission"),
                ("NodeSocketFloat", "Alpha"),
            ),
            build,
        )

    def _sample_layer(
        self,
        tree,
        sample_group,
        uv,
        color_scale,
        label,
        x,
        y,
    ):
        sample = material_bundle_node(
            tree,
            sample_group,
            (x, y),
            label,
            {"UV": uv, "Color Scale": color_scale},
        )
        return (
            sample.outputs["Color"],
            sample.outputs["Metalness"],
            sample.outputs["Roughness"],
            sample.outputs["Emission"],
            sample.outputs["Alpha"],
        )

    @staticmethod
    def _layer_uv(tree, tiled_uv, parallax_offset, depth, name, location):
        nodes = tree.nodes
        links = tree.links
        if abs(float(depth)) <= 1.0e-9:
            return tiled_uv
        offset = shader_nodes.vector_math(
            nodes,
            links,
            "SCALE",
            parallax_offset,
            scale=float(depth),
            name=f"{name} Offset",
            location=location,
        )
        return shader_nodes.vector_math(
            nodes,
            links,
            "ADD",
            tiled_uv,
            offset,
            name=f"{name} UV",
            location=(location[0] + 180, location[1]),
        )

    def create(self, Data, Mat):
        data = Data if isinstance(Data, dict) else {}
        depth = max(0.0, param_float(data, "ParallaxDepth", 0.05))
        steps = _MAX_PARALLAX_STEPS if depth > 1.0e-6 else 0

        Mat.use_nodes = True
        tree = Mat.node_tree
        nodes = tree.nodes
        links = tree.links
        nodes.clear()

        output = new_labeled_node(
            nodes, "ShaderNodeOutputMaterial", "Material Output", (2700, 100)
        )
        principled = new_labeled_node(
            nodes, "ShaderNodeBsdfPrincipled", "Neon Parallax", (2440, 100)
        )
        links.new(principled.outputs["BSDF"], output.inputs["Surface"])

        tiled_uv = create_tiled_uv(
            tree,
            param_float(data, "UvTilingX", 1.0),
            param_float(data, "UvTilingY", 1.0),
            param_float(data, "UvOffsetX", 0.0),
            param_float(data, "UvOffsetY", 0.0),
            location=(-2300, 500),
        )
        flipped = param_float(data, "ParallaxFlip", 0.0) > 0.5
        parallax_offset = create_camera_forward_parallax_offset(
            tree,
            y_scale=1.0 if flipped else -1.0,
            location=(-2300, 80),
        )
        images = self._load_images(data)
        use_gradient = param_float(data, "UseGradientMapMode", 0.0) > 0.5
        sample_group = self._sample_layer_group(images, use_gradient)
        base_scale = param_vector(data, "BaseColorScale", (1.0, 1.0, 1.0, 1.0))
        edge_start = param_color(
            data, "BaseColorScaleEdgeStart", (0.6275, 0.6275, 0.6275, 0.0)
        )
        edge_end = param_color(
            data, "BaseColorScaleEdgeEnd", (0.1961, 0.1961, 0.1961, 0.0)
        )

        black = rgb_socket(
            nodes, "Extruded Color Start", (0.0, 0.0, 0.0, 1.0), (-1980, -900)
        )
        zero_metal = value_socket(nodes, "Extruded Metal Start", 0.0, (-1980, -980))
        zero_rough = value_socket(nodes, "Extruded Rough Start", 0.0, (-1980, -1060))
        zero_emission = value_socket(
            nodes, "Extruded Emission Start", 0.0, (-1980, -1140)
        )
        zero_alpha = value_socket(nodes, "Extruded Alpha Start", 0.0, (-1980, -1220))
        accum_color = black
        accum_metal = zero_metal
        accum_rough = zero_rough
        accum_emission = zero_emission
        accum_alpha = zero_alpha

        if steps:
            for index in range(steps + 1):
                normalized = index / float(steps)
                sample_depth = normalized * depth
                uv = self._layer_uv(
                    tree,
                    tiled_uv,
                    parallax_offset,
                    sample_depth,
                    f"Extruded Layer {index + 1}",
                    (-1800, -1500 - index * 30),
                )
                color_scale = tuple(
                    float(value) for value in lerp(edge_end, edge_start, normalized)
                )
                color, metal, rough, emission, alpha = self._sample_layer(
                    tree,
                    sample_group,
                    uv,
                    color_scale,
                    f"Extruded Layer {index + 1}",
                    -1300 + index * 30,
                    -1100 - index * 620,
                )
                composite_x = 1050 + index * 35
                accum_color = mix_color_socket(
                    nodes,
                    links,
                    f"Extruded Color {index + 1}",
                    accum_color,
                    color,
                    alpha,
                    (composite_x, -900 - index * 20),
                )
                accum_metal = mix_scalar_socket(
                    nodes,
                    links,
                    f"Extruded Metal {index + 1}",
                    (composite_x, -1020 - index * 20),
                    accum_metal,
                    metal,
                    alpha,
                )
                accum_rough = mix_scalar_socket(
                    nodes,
                    links,
                    f"Extruded Rough {index + 1}",
                    (composite_x, -1140 - index * 20),
                    accum_rough,
                    rough,
                    alpha,
                )
                accum_emission = mix_scalar_socket(
                    nodes,
                    links,
                    f"Extruded Emission {index + 1}",
                    (composite_x, -1260 - index * 20),
                    accum_emission,
                    emission,
                    alpha,
                )
                accum_alpha = shader_nodes.math(
                    nodes,
                    links,
                    "MAXIMUM",
                    accum_alpha,
                    alpha,
                    name=f"Extruded Alpha {index + 1}",
                    location=(composite_x, -1380 - index * 20),
                )

        top_uv = self._layer_uv(
            tree,
            tiled_uv,
            parallax_offset,
            depth,
            "Top Layer",
            (-1800, 760),
        )
        top_color, top_metal, top_rough, top_emission, top_alpha = self._sample_layer(
            tree,
            sample_group,
            top_uv,
            base_scale,
            "Top Layer",
            -1300,
            820,
        )

        final_color = (
            mix_color_socket(
                nodes,
                links,
                "Top Over Extrusion Color",
                accum_color,
                top_color,
                top_alpha,
                (1820, 520),
            )
            if steps
            else top_color
        )
        final_metal = (
            mix_scalar_socket(
                nodes,
                links,
                "Top Over Extrusion Metal",
                (1820, 380),
                accum_metal,
                top_metal,
                top_alpha,
            )
            if steps
            else top_metal
        )
        final_rough = (
            mix_scalar_socket(
                nodes,
                links,
                "Top Over Extrusion Rough",
                (1820, 240),
                accum_rough,
                top_rough,
                top_alpha,
            )
            if steps
            else top_rough
        )
        final_emission = (
            mix_scalar_socket(
                nodes,
                links,
                "Top Over Extrusion Emission",
                (1820, 100),
                accum_emission,
                top_emission,
                top_alpha,
            )
            if steps
            else top_emission
        )
        final_alpha = (
            shader_nodes.math(
                nodes,
                links,
                "MAXIMUM",
                accum_alpha,
                top_alpha,
                name="Top Over Extrusion Alpha",
                location=(1820, -40),
            )
            if steps
            else top_alpha
        )

        metal_scaled = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            final_metal,
            param_float(data, "MetalnessScale", 0.0),
            name="Metalness Scale",
            location=(2040, 380),
        )
        metal_adjusted = shader_nodes.math(
            nodes,
            links,
            "ADD",
            metal_scaled,
            param_float(data, "MetalnessBias", 0.0),
            name="Metalness Bias",
            location=(2200, 380),
            use_clamp=True,
        )
        rough_scaled = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            final_rough,
            param_float(data, "RoughnessScale", 0.0),
            name="Roughness Scale",
            location=(2040, 240),
        )
        rough_adjusted = shader_nodes.math(
            nodes,
            links,
            "ADD",
            rough_scaled,
            param_float(data, "RoughnessBias", 0.0),
            name="Roughness Bias",
            location=(2200, 240),
            use_clamp=True,
        )
        emission_squared = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            final_emission,
            final_emission,
            name="Emission Mask Squared",
            location=(2040, 40),
        )
        metal_curve = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            emission_squared,
            0.5,
            name="Emission Metalness Curve",
            location=(2200, 40),
            use_clamp=True,
        )
        one_minus_curve = shader_nodes.math(
            nodes,
            links,
            "SUBTRACT",
            1.0,
            metal_curve,
            name="Emission Dielectric Blend",
            location=(2200, -80),
            use_clamp=True,
        )
        emissive_ev = param_float(data, "EmissiveEV", 0.0)
        final_metal_adjusted = (
            shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                metal_adjusted,
                one_minus_curve,
                name="Emission Reduced Metalness",
                location=(2360, 320),
                use_clamp=True,
            )
            if emissive_ev > 0.0
            else metal_adjusted
        )
        emission_strength = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            final_emission,
            max(0.0, ev_to_linear(emissive_ev) - 1.0),
            name="Scale Emissive EV",
            location=(2200, 100),
        )
        alpha_threshold = clamp01(param_float(data, "AlphaThreshold", 0.5))
        alpha_gate = shader_nodes.math(
            nodes,
            links,
            "GREATER_THAN",
            final_alpha,
            alpha_threshold,
            name="Alpha Threshold",
            location=(2200, -200),
        )

        base_color_socket = find_input(principled, "Base Color")
        metallic_socket = find_input(principled, "Metallic")
        roughness_socket = find_input(principled, "Roughness")
        emission_color_socket = find_input(principled, "Emission Color", "Emission")
        emission_strength_socket = find_input(principled, "Emission Strength")
        alpha_socket = find_input(principled, "Alpha")
        if base_color_socket is not None:
            links.new(final_color, base_color_socket)
        if metallic_socket is not None:
            links.new(final_metal_adjusted, metallic_socket)
        if roughness_socket is not None:
            links.new(rough_adjusted, roughness_socket)
        if emission_color_socket is not None:
            links.new(final_color, emission_color_socket)
        if emission_strength_socket is not None:
            links.new(emission_strength, emission_strength_socket)
        if alpha_socket is not None:
            links.new(alpha_gate, alpha_socket)

        Mat.diffuse_color = (*base_scale[:3], 1.0)
        set_alpha_clip(Mat, alpha_threshold)
