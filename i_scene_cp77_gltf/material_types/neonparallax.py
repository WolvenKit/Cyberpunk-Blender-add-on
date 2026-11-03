from .mat_common import (
    MaterialTypeBase,
    clamp01,
    find_input,
    new_labeled_node,
    param_color,
    param_float,
    param_texture_path,
    param_vector,
)
from .graph import (
    math_socket,
    mix_color_socket,
    mix_scalar_socket as _mix_scalar,
    multiply_color_at_socket as _multiply_color,
    red_channel_at_socket as _separate_red,
    rgb_socket as _constant_color,
    set_alpha_clip as _set_alpha_mode,
    value_socket as _constant_value,
    vector_math_socket,
)
from .parallax_common import create_tangent_parallax_offset, create_tiled_uv


_TEMPLATES = {"base\\materials\\neon_parallax.mt"}
_MAX_PARALLAX_STEPS = 24
_PARALLAX_BIAS = 0.1


def _lerp_color(first, second, factor):
    return tuple(
        float(first[index]) + (float(second[index]) - float(first[index])) * float(factor)
        for index in range(4)
    )


def _store_metadata(material, data, steps):
    material["cp77_neon_parallax_template"] = "base\\materials\\neon_parallax.mt"
    material["cp77_neon_parallax_preview"] = "FIXED_MAX_PARALLAX_SAMPLES"
    material["cp77_neon_parallax_steps"] = int(steps)
    scalar_defaults = {
        "UvTilingX": 1.0,
        "UvTilingY": 1.0,
        "UvOffsetX": 0.0,
        "UvOffsetY": 0.0,
        "UseGradientMapMode": 0.0,
        "MetalnessScale": 0.0,
        "MetalnessBias": 0.0,
        "RoughnessScale": 0.0,
        "RoughnessBias": 0.0,
        "EmissiveEV": 0.0,
        "EmissiveEVRaytracingBias": 0.0,
        "EmissiveDirectionality": 0.0,
        "EnableRaytracedEmissive": 1.0,
        "ParallaxDepth": 0.05,
        "ParallaxFlip": 0.0,
        "AlphaThreshold": 0.5,
    }
    for name, default in scalar_defaults.items():
        material[f"cp77_{name}"] = param_float(data, name, default)
    material["cp77_BaseColorScale"] = list(param_vector(data, "BaseColorScale", (1.0, 1.0, 1.0, 1.0)))
    material["cp77_BaseColorScaleEdgeStart"] = list(
        param_color(data, "BaseColorScaleEdgeStart", (0.6275, 0.6275, 0.6275, 0.0))
    )
    material["cp77_BaseColorScaleEdgeEnd"] = list(
        param_color(data, "BaseColorScaleEdgeEnd", (0.1961, 0.1961, 0.1961, 0.0))
    )
    for name in ("BaseColor", "GradientMap", "Metalness", "Roughness", "Emissive"):
        material[f"cp77_{name}"] = param_texture_path(data, name)


class NeonParallax(MaterialTypeBase):
    def _load_images(self, data):
        return {
            "BaseColor": self._load_relative_image(
                param_texture_path(data, "BaseColor"),
                error_label="neon parallax base color",
            ),
            "GradientMap": self._load_relative_image(
                param_texture_path(data, "GradientMap"),
                error_label="neon parallax gradient",
            ),
            "Metalness": self._load_relative_image(
                param_texture_path(data, "Metalness"),
                non_color=True,
                error_label="neon parallax metalness",
            ),
            "Roughness": self._load_relative_image(
                param_texture_path(data, "Roughness"),
                non_color=True,
                error_label="neon parallax roughness",
            ),
            "Emissive": self._load_relative_image(
                param_texture_path(data, "Emissive"),
                non_color=True,
                error_label="neon parallax emissive",
            ),
        }

    @staticmethod
    def _sample(nodes, links, image, vector, name, location, fallback=(1.0, 1.0, 1.0, 1.0)):
        if image is None:
            color = _constant_color(nodes, f"{name} Fallback", fallback, location)
            alpha = _constant_value(nodes, f"{name} Alpha Fallback", fallback[3], (location[0], location[1] - 80))
            return color, alpha
        node = new_labeled_node(nodes, "ShaderNodeTexImage", name, location)
        node.image = image
        try:
            node.extension = "EXTEND"
        except (AttributeError, TypeError, ValueError):
            pass
        links.new(vector, node.inputs.get("Vector") or node.inputs[0])
        return node.outputs.get("Color") or node.outputs[0], node.outputs.get("Alpha") or node.outputs[1]

    def _sample_layer(
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
            lookup = _separate_red(nodes, links, f"{label} Gradient Coordinate", (x + 180, y), base_color)
            combine = new_labeled_node(nodes, "ShaderNodeCombineXYZ", f"{label} Gradient UV", (x + 340, y))
            links.new(lookup, combine.inputs[0])
            combine.inputs[1].default_value = 0.5
            gradient_color, gradient_alpha = self._sample(
                nodes,
                links,
                images["GradientMap"],
                combine.outputs[0],
                f"{label} GradientMap",
                (x + 500, y),
                fallback=(0.5, 0.5, 0.5, 1.0),
            )
            emissive_color, _ = self._sample(
                nodes,
                links,
                images["Emissive"],
                combine.outputs[0],
                f"{label} Emissive Gradient",
                (x + 500, y - 180),
            )
            emission = _separate_red(
                nodes,
                links,
                f"{label} Emission Mask",
                (x + 680, y - 180),
                emissive_color,
            )
            alpha = math_socket(
                nodes,
                links,
                "MULTIPLY",
                f"{label} Alpha",
                (x + 680, y + 40),
                gradient_alpha,
                sampled_alpha,
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
            emission = _separate_red(
                nodes,
                links,
                f"{label} Emission Mask",
                (x + 360, y - 180),
                emissive_color,
            )
            alpha = math_socket(
                nodes,
                links,
                "MULTIPLY",
                f"{label} Alpha",
                (x + 360, y + 40),
                sampled_alpha,
                sampled_alpha,
            )
            layer_color = base_color

        color = _multiply_color(
            nodes,
            links,
            f"{label} Color Scale",
            (x + 850, y),
            layer_color,
            color_scale,
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
        metal = _separate_red(nodes, links, f"{label} Metal", (x + 360, y - 340), metal_color)
        rough = _separate_red(nodes, links, f"{label} Rough", (x + 360, y - 500), rough_color)
        return color, metal, rough, emission, alpha

    @staticmethod
    def _layer_uv(tree, tiled_uv, parallax_offset, depth, name, location):
        nodes = tree.nodes
        links = tree.links
        if abs(float(depth)) <= 1.0e-9:
            return tiled_uv
        offset = vector_math_socket(
            nodes,
            links,
            "SCALE",
            f"{name} Offset",
            location,
            parallax_offset,
            scale=float(depth),
        )
        return vector_math_socket(
            nodes,
            links,
            "ADD",
            f"{name} UV",
            (location[0] + 180, location[1]),
            tiled_uv,
            offset,
        )

    def create(self, Data, Mat):
        data = Data if isinstance(Data, dict) else {}
        depth = max(0.0, param_float(data, "ParallaxDepth", 0.05))
        steps = _MAX_PARALLAX_STEPS if depth > 1.0e-6 else 0
        _store_metadata(Mat, data, steps)

        Mat.use_nodes = True
        tree = Mat.node_tree
        nodes = tree.nodes
        links = tree.links
        nodes.clear()

        output = new_labeled_node(nodes, "ShaderNodeOutputMaterial", "Material Output", (2700, 100))
        principled = new_labeled_node(nodes, "ShaderNodeBsdfPrincipled", "Neon Parallax", (2440, 100))
        links.new(principled.outputs[0], output.inputs["Surface"])

        tiled_uv = create_tiled_uv(
            tree,
            param_float(data, "UvTilingX", 1.0),
            param_float(data, "UvTilingY", 1.0),
            param_float(data, "UvOffsetX", 0.0),
            param_float(data, "UvOffsetY", 0.0),
            location=(-2300, 500),
        )
        parallax_offset = create_tangent_parallax_offset(
            tree,
            flipped=param_float(data, "ParallaxFlip", 0.0) > 0.5,
            bias=_PARALLAX_BIAS,
            location=(-2300, 80),
        )
        images = self._load_images(data)
        use_gradient = param_float(data, "UseGradientMapMode", 0.0) > 0.5
        base_scale = param_vector(data, "BaseColorScale", (1.0, 1.0, 1.0, 1.0))
        edge_start = param_color(data, "BaseColorScaleEdgeStart", (0.6275, 0.6275, 0.6275, 0.0))
        edge_end = param_color(data, "BaseColorScaleEdgeEnd", (0.1961, 0.1961, 0.1961, 0.0))

        black = _constant_color(nodes, "Extruded Color Start", (0.0, 0.0, 0.0, 1.0), (-1980, -900))
        zero_metal = _constant_value(nodes, "Extruded Metal Start", 0.0, (-1980, -980))
        zero_rough = _constant_value(nodes, "Extruded Rough Start", 0.0, (-1980, -1060))
        zero_emission = _constant_value(nodes, "Extruded Emission Start", 0.0, (-1980, -1140))
        zero_alpha = _constant_value(nodes, "Extruded Alpha Start", 0.0, (-1980, -1220))
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
                color_scale = _lerp_color(edge_end, edge_start, normalized)
                color, metal, rough, emission, alpha = self._sample_layer(
                    tree,
                    images,
                    uv,
                    color_scale,
                    use_gradient,
                    f"Extruded Layer {index + 1}",
                    -1300 + index * 30,
                    -1100 - index * 620,
                )
                composite_x = 1050 + index * 35
                accum_color = mix_color_socket(
                    nodes,
                    links,
                    f"Extruded Color {index + 1}",
                    (composite_x, -900 - index * 20),
                    accum_color,
                    color,
                    alpha,
                )
                accum_metal = _mix_scalar(
                    nodes,
                    links,
                    f"Extruded Metal {index + 1}",
                    (composite_x, -1020 - index * 20),
                    accum_metal,
                    metal,
                    alpha,
                )
                accum_rough = _mix_scalar(
                    nodes,
                    links,
                    f"Extruded Rough {index + 1}",
                    (composite_x, -1140 - index * 20),
                    accum_rough,
                    rough,
                    alpha,
                )
                accum_emission = _mix_scalar(
                    nodes,
                    links,
                    f"Extruded Emission {index + 1}",
                    (composite_x, -1260 - index * 20),
                    accum_emission,
                    emission,
                    alpha,
                )
                accum_alpha = math_socket(
                    nodes,
                    links,
                    "MAXIMUM",
                    f"Extruded Alpha {index + 1}",
                    (composite_x, -1380 - index * 20),
                    accum_alpha,
                    alpha,
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
            images,
            top_uv,
            base_scale,
            use_gradient,
            "Top Layer",
            -1300,
            820,
        )

        final_color = mix_color_socket(
            nodes,
            links,
            "Top Over Extrusion Color",
            (1820, 520),
            accum_color,
            top_color,
            top_alpha,
        ) if steps else top_color
        final_metal = _mix_scalar(
            nodes,
            links,
            "Top Over Extrusion Metal",
            (1820, 380),
            accum_metal,
            top_metal,
            top_alpha,
        ) if steps else top_metal
        final_rough = _mix_scalar(
            nodes,
            links,
            "Top Over Extrusion Rough",
            (1820, 240),
            accum_rough,
            top_rough,
            top_alpha,
        ) if steps else top_rough
        final_emission = _mix_scalar(
            nodes,
            links,
            "Top Over Extrusion Emission",
            (1820, 100),
            accum_emission,
            top_emission,
            top_alpha,
        ) if steps else top_emission
        final_alpha = math_socket(
            nodes,
            links,
            "MAXIMUM",
            "Top Over Extrusion Alpha",
            (1820, -40),
            accum_alpha,
            top_alpha,
        ) if steps else top_alpha

        metal_scaled = math_socket(
            nodes,
            links,
            "MULTIPLY",
            "Metalness Scale",
            (2040, 380),
            final_metal,
            param_float(data, "MetalnessScale", 0.0),
        )
        metal_adjusted = math_socket(
            nodes,
            links,
            "ADD",
            "Metalness Bias",
            (2200, 380),
            metal_scaled,
            param_float(data, "MetalnessBias", 0.0),
            clamp=True,
        )
        rough_scaled = math_socket(
            nodes,
            links,
            "MULTIPLY",
            "Roughness Scale",
            (2040, 240),
            final_rough,
            param_float(data, "RoughnessScale", 0.0),
        )
        rough_adjusted = math_socket(
            nodes,
            links,
            "ADD",
            "Roughness Bias",
            (2200, 240),
            rough_scaled,
            param_float(data, "RoughnessBias", 0.0),
            clamp=True,
        )
        emission_squared = math_socket(
            nodes,
            links,
            "MULTIPLY",
            "Emission Mask Squared",
            (2040, 40),
            final_emission,
            final_emission,
        )
        metal_curve = math_socket(
            nodes,
            links,
            "MULTIPLY",
            "Emission Metalness Curve",
            (2200, 40),
            emission_squared,
            0.5,
            clamp=True,
        )
        one_minus_curve = math_socket(
            nodes,
            links,
            "SUBTRACT",
            "Emission Dielectric Blend",
            (2200, -80),
            1.0,
            metal_curve,
            clamp=True,
        )
        emissive_ev = max(0.0, param_float(data, "EmissiveEV", 0.0))
        final_metal_adjusted = (
            math_socket(
                nodes,
                links,
                "MULTIPLY",
                "Emission Reduced Metalness",
                (2360, 320),
                metal_adjusted,
                one_minus_curve,
                clamp=True,
            )
            if emissive_ev > 0.0
            else metal_adjusted
        )
        emission_strength = math_socket(
            nodes,
            links,
            "MULTIPLY",
            "Scale Emissive EV",
            (2200, 100),
            final_emission,
            emissive_ev,
        )
        alpha_threshold = clamp01(param_float(data, "AlphaThreshold", 0.5))
        alpha_gate = math_socket(
            nodes,
            links,
            "GREATER_THAN",
            "Alpha Threshold",
            (2200, -200),
            final_alpha,
            alpha_threshold,
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
        _set_alpha_mode(Mat, alpha_threshold)


used_params = [
    "UvTilingX",
    "UvTilingY",
    "UvOffsetX",
    "UvOffsetY",
    "BaseColor",
    "UseGradientMapMode",
    "BaseColorScale",
    "GradientMap",
    "BaseColorScaleEdgeStart",
    "BaseColorScaleEdgeEnd",
    "Metalness",
    "MetalnessScale",
    "MetalnessBias",
    "Roughness",
    "RoughnessScale",
    "RoughnessBias",
    "Emissive",
    "EmissiveEV",
    "EmissiveEVRaytracingBias",
    "EmissiveDirectionality",
    "EnableRaytracedEmissive",
    "ParallaxDepth",
    "ParallaxFlip",
    "AlphaThreshold",
]
