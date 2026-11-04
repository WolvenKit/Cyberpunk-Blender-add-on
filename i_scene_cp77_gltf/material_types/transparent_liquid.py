from ..blender import shader_nodes
from ..materials.cache_identity import filtered_material_data_identity
from .graph import color_channel_socket, mix_color_socket, set_transparent
from .mat_common import (
    MaterialTypeBase,
    create_relative_texture_node,
    create_scene_time_value,
    find_input,
    new_labeled_node,
    param_color,
    param_float,
    param_vector,
)
from .normal_math import decode_cp77_normal, tangent_to_normal_map

TEMPLATE = r"base\materials\transparent_liquid.mt"


def _animated_uv(tree, transform, location, label, uv, time):
    nodes = tree.nodes
    links = tree.links
    sx, sy, scroll_x, scroll_y = transform
    scaled = shader_nodes.vector_math(
        nodes,
        links,
        "MULTIPLY",
        uv,
        (float(sx), float(sy), 1.0),
        name=f"{label} Tiling",
        location=(location[0] + 200, location[1]),
    )
    return shader_nodes.vector_math(
        nodes,
        links,
        "MULTIPLY_ADD",
        time,
        (float(scroll_x), float(scroll_y), 0.0),
        scaled,
        name=f"{label} Animated UV",
        location=(location[0] + 380, location[1]),
    )


class TransparentLiquid(MaterialTypeBase):
    def create(self, Data, Mat):
        data = Data if isinstance(Data, dict) else {}
        Mat.use_nodes = True
        tree = Mat.node_tree
        nodes = tree.nodes
        links = tree.links
        nodes.clear()

        output = new_labeled_node(
            nodes, "ShaderNodeOutputMaterial", "Material Output", (1100, 120)
        )
        principled = new_labeled_node(
            nodes, "ShaderNodeBsdfPrincipled", "Transparent Liquid", (820, 120)
        )
        links.new(principled.outputs["BSDF"], output.inputs["Surface"])

        base_uv = new_labeled_node(
            nodes, "ShaderNodeTexCoord", "Liquid UV", (-1500, 520)
        ).outputs.get("UV")
        time = create_scene_time_value(tree, -1340, -60, "Liquid Time").outputs["Value"]
        distort_uv = _animated_uv(
            tree,
            param_vector(data, "DistortTilingAndScrolling", (0.0, 0.0, 0.0, 0.0)),
            (-1500, 120),
            "Distort",
            base_uv,
            time,
        )
        distort = create_relative_texture_node(
            self,
            tree,
            data,
            "Distort",
            distort_uv,
            (-700, 40),
            non_color=True,
            error_label="transparent liquid Distort",
        )
        distortion = None
        if (
            distort is not None
            and abs(param_float(data, "DistortAmount", 0.0)) > 1.0e-8
        ):
            centered = shader_nodes.vector_math(
                nodes,
                links,
                "SUBTRACT",
                distort.outputs["Color"],
                (0.5, 0.5, 0.5),
                name="Distort - 0.5",
                location=(-440, 40),
            )
            distortion = shader_nodes.vector_math(
                nodes,
                links,
                "SCALE",
                centered,
                scale=2.0 * param_float(data, "DistortAmount", 0.0),
                name="Distort Amount",
                location=(-240, 40),
            )

        normal_uv = _animated_uv(
            tree,
            param_vector(data, "NormalTilingAndScrolling", (1.0, 1.0, 0.0, 0.0)),
            (-1500, -300),
            "Normal",
            base_uv,
            time,
        )
        if distortion is not None:
            normal_uv = shader_nodes.vector_math(
                nodes,
                links,
                "ADD",
                normal_uv,
                distortion,
                name="Normal UV + Distort",
                location=(-520, -300),
            )

        normal_tex = create_relative_texture_node(
            self,
            tree,
            data,
            "Normal",
            normal_uv,
            (-280, -300),
            non_color=True,
            error_label="transparent liquid Normal",
        )
        normal_tangent = None
        if normal_tex is not None:
            decoder = decode_cp77_normal(
                tree,
                normal_tex.outputs["Color"],
                strength=max(0.0, param_float(data, "NormalStrength", 1.0)),
                location=(0, -300),
                label="Liquid Normal Decode",
            )
            normal_tangent = decoder.outputs["Tangent"]
            mapped = tangent_to_normal_map(
                tree,
                decoder.outputs["Color"],
                location=(240, -300),
                label="Liquid Normal",
            )
            links.new(mapped, find_input(principled, "Normal"))

        mask = create_relative_texture_node(
            self,
            tree,
            data,
            "Mask",
            base_uv,
            (-640, 560),
            non_color=True,
            error_label="transparent liquid Mask",
        )
        opacity = float(max(0.0, min(1.0, param_float(data, "MaskOpacity", 1.0))))
        if mask is not None:
            alpha = color_channel_socket(
                nodes,
                links,
                mask.outputs["Color"],
                "Mask.r",
                (-400, 560),
                channel="Red",
            )
            alpha = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                alpha,
                opacity,
                name="Mask × Opacity",
                location=(-180, 560),
                use_clamp=True,
            )
        else:
            alpha = opacity

        if normal_tex is not None:
            density = color_channel_socket(
                nodes,
                links,
                normal_tex.outputs["Color"],
                "Normal.b Density",
                (0, -520),
                channel="Blue",
            )
            packed_alpha = normal_tex.outputs["Alpha"]
            alpha = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                alpha,
                density,
                name="Density × Packed Alpha",
                location=(220, -520),
                use_clamp=True,
            )
            alpha = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                alpha,
                packed_alpha,
                name="Liquid Alpha",
                location=(420, -520),
                use_clamp=True,
            )
        threshold = max(0.0, min(1.0, param_float(data, "AlphaThreshold", 0.05)))
        if hasattr(alpha, "is_output") and threshold > 0.0:
            visible = shader_nodes.math(
                nodes,
                links,
                "GREATER_THAN",
                alpha,
                threshold,
                name="Alpha Threshold",
                location=(600, -520),
            )
            alpha = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                alpha,
                visible,
                name="Thresholded Alpha",
                location=(780, -520),
                use_clamp=True,
            )
        elif not hasattr(alpha, "is_output") and float(alpha) <= threshold:
            alpha = 0.0

        thin = param_color(data, "ScatteringColorThin", (1.0, 1.0, 1.0, 1.0))
        thick = param_color(data, "ScatteringColorThick", (1.0, 1.0, 1.0, 1.0))
        thickness = max(0.0, param_float(data, "ThicknessMultiplier", 1.0))
        if normal_tangent is not None:
            nz = new_labeled_node(
                nodes, "ShaderNodeSeparateXYZ", "Liquid Normal Z", (240, -80)
            )
            links.new(normal_tangent, nz.inputs["Vector"])
            factor = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                nz.outputs["Z"],
                thickness,
                name="Thickness × Normal Z",
                location=(440, -80),
                use_clamp=True,
            )
        else:
            factor = max(0.0, min(1.0, thickness))
        scattering = mix_color_socket(
            nodes,
            links,
            "Thin/Thick Scattering",
            thin,
            thick,
            factor,
            (360, 360),
            clamp=True,
        )
        albedo = param_color(data, "Albedo", (0.0, 0.0, 0.0, 1.0))
        surface_color = mix_color_socket(
            nodes,
            links,
            "Liquid Albedo × Scattering",
            albedo,
            scattering,
            1.0,
            (580, 360),
            blend_type="MULTIPLY",
            clamp=True,
        )
        links.new(surface_color, find_input(principled, "Base Color"))

        find_input(principled, "Metallic").default_value = max(
            0.0, min(1.0, param_float(data, "SurfaceMetalness", 0.0))
        )
        find_input(principled, "Roughness").default_value = max(
            0.0, min(1.0, param_float(data, "Roughness", 0.0))
        )
        ior = find_input(principled, "IOR")
        if ior is not None:
            ior.default_value = max(1.0, param_float(data, "IOR", 1.33))
        transmission = find_input(principled, "Transmission Weight", "Transmission")
        if transmission is not None:
            transmission.default_value = 1.0
        specular = find_input(principled, "IOR Level", "Specular IOR Level")
        if specular is not None:
            specular.default_value = max(
                0.0, min(1.0, param_float(data, "SpecularStrengthMultiplier", 0.5))
            )
        find_input(principled, "Alpha").default_value = (
            1.0 if hasattr(alpha, "is_output") else float(alpha)
        )
        if hasattr(alpha, "is_output"):
            links.new(alpha, find_input(principled, "Alpha"))

        set_transparent(Mat)
        Mat.use_raytrace_refraction = True


used_params = [
    "SurfaceMetalness",
    "ScatteringColorThin",
    "ScatteringColorThick",
    "Albedo",
    "IOR",
    "Normal",
    "Roughness",
    "SpecularStrengthMultiplier",
    "NormalStrength",
    "MaskOpacity",
    "ThicknessMultiplier",
    "AlphaThreshold",
    "NormalTilingAndScrolling",
    "Distort",
    "DistortAmount",
    "DistortTilingAndScrolling",
    "Mask",
]


def material_cache_identity(raw_material):
    return filtered_material_data_identity(raw_material, used_params)
