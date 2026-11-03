from ..bartmoss.scalar import REC601_LUMA_WEIGHTS
from ..blender import shader_nodes
from ..materials.cache_identity import filtered_material_data_identity
from .graph import mix_color_socket, set_transparent
from .mat_common import (
    MaterialTypeBase,
    create_relative_texture_node,
    new_labeled_node,
    param_color,
    param_float,
    param_vector,
)
from .normal_math import create_cp77_normal_texture

TEMPLATE = r"base\fx\_shaders\hologram_v2.mt"
_WHITE = (1.0, 1.0, 1.0, 1.0)


def _map_range(tree, value, minimum, maximum, name, location):
    node = new_labeled_node(tree.nodes, "ShaderNodeMapRange", name, location)
    node.data_type = "FLOAT"
    node.interpolation_type = "LINEAR"
    node.clamp = True
    tree.links.new(value, node.inputs["Value"])
    node.inputs["From Min"].default_value = float(minimum)
    node.inputs["From Max"].default_value = (
        float(maximum) if abs(maximum - minimum) > 1.0e-6 else float(minimum) + 1.0e-6
    )
    node.inputs["To Min"].default_value = 0.0
    node.inputs["To Max"].default_value = 1.0
    return node.outputs["Result"]


def _axis_dot(tree, position, vector, name, location):
    direction = new_labeled_node(
        tree.nodes, "ShaderNodeCombineXYZ", f"{name} Vector", location
    )
    direction.inputs["X"].default_value = vector[0]
    direction.inputs["Y"].default_value = vector[1]
    direction.inputs["Z"].default_value = vector[2]
    return shader_nodes.vector_math(
        tree.nodes,
        tree.links,
        "DOT_PRODUCT",
        position,
        direction.outputs["Vector"],
        name=name,
        location=(location[0] + 190, location[1]),
    )


def _stripe_mask(tree, coordinate, density, size, steps, name, location):
    scaled = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        coordinate,
        max(0.0, density),
        name=f"{name} Density",
        location=location,
    )
    if steps > 1.0:
        scaled = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            scaled,
            max(1.0, steps),
            name=f"{name} Steps",
            location=(location[0] + 160, location[1]),
        )
        scaled = shader_nodes.math(
            tree.nodes,
            tree.links,
            "FLOOR",
            scaled,
            name=f"{name} Quantize",
            location=(location[0] + 320, location[1]),
        )
        scaled = shader_nodes.math(
            tree.nodes,
            tree.links,
            "DIVIDE",
            scaled,
            max(1.0, steps),
            name=f"{name} Step Normalize",
            location=(location[0] + 480, location[1]),
        )
    phase = shader_nodes.math(
        tree.nodes,
        tree.links,
        "FRACT",
        scaled,
        name=f"{name} Phase",
        location=(location[0] + 640, location[1]),
    )
    centered = shader_nodes.math(
        tree.nodes,
        tree.links,
        "SUBTRACT",
        phase,
        0.5,
        name=f"{name} Center",
        location=(location[0] + 800, location[1]),
    )
    centered = shader_nodes.math(
        tree.nodes,
        tree.links,
        "ABSOLUTE",
        centered,
        name=f"{name} abs",
        location=(location[0] + 960, location[1]),
    )
    half_size = max(0.0001, min(0.5, float(size) * 0.5))
    return shader_nodes.math(
        tree.nodes,
        tree.links,
        "LESS_THAN",
        centered,
        half_size,
        name=name,
        location=(location[0] + 1120, location[1]),
    )


def _point_mask(tree, position, density, size, steps, name, location):
    scaled = shader_nodes.vector_math(
        tree.nodes,
        tree.links,
        "SCALE",
        position,
        scale=max(0.0, density),
        name=f"{name} Density",
        location=location,
    )
    phase = shader_nodes.vector_math(
        tree.nodes,
        tree.links,
        "FRACTION",
        scaled,
        name=f"{name} Cell",
        location=(location[0] + 180, location[1]),
    )
    centered = shader_nodes.vector_math(
        tree.nodes,
        tree.links,
        "ADD",
        phase,
        (-0.5, -0.5, -0.5),
        name=f"{name} Center",
        location=(location[0] + 360, location[1]),
    )
    distance = shader_nodes.vector_math(
        tree.nodes,
        tree.links,
        "LENGTH",
        centered,
        name=f"{name} Radius",
        location=(location[0] + 540, location[1]),
    )
    radius = max(0.001, min(0.866, float(size) * 0.5))
    mask = shader_nodes.math(
        tree.nodes,
        tree.links,
        "LESS_THAN",
        distance,
        radius,
        name=name,
        location=(location[0] + 720, location[1]),
    )
    if steps > 1.0:
        quantized = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            mask,
            max(1.0, steps),
            name=f"{name} Step Level",
            location=(location[0] + 900, location[1]),
        )
        quantized = shader_nodes.math(
            tree.nodes,
            tree.links,
            "FLOOR",
            quantized,
            name=f"{name} Quantize",
            location=(location[0] + 1060, location[1]),
        )
        mask = shader_nodes.math(
            tree.nodes,
            tree.links,
            "DIVIDE",
            quantized,
            max(1.0, steps),
            name=f"{name} Normalize",
            location=(location[0] + 1220, location[1]),
        )
    return mask


class HologramV2(MaterialTypeBase):
    def create(self, Data, Mat):
        data = Data if isinstance(Data, dict) else {}
        Mat.use_nodes = True
        tree = Mat.node_tree
        nodes = tree.nodes
        links = tree.links
        nodes.clear()

        output = new_labeled_node(
            nodes, "ShaderNodeOutputMaterial", "Material Output", (3340, 160)
        )
        emission = new_labeled_node(
            nodes, "ShaderNodeEmission", "Hologram V2 Emission", (2860, 300)
        )
        transparent = new_labeled_node(
            nodes, "ShaderNodeBsdfTransparent", "Transparent", (2860, 40)
        )
        mix = new_labeled_node(
            nodes, "ShaderNodeMixShader", "Hologram V2 Alpha", (3100, 180)
        )
        links.new(transparent.outputs["BSDF"], mix.inputs["Shader"])
        links.new(
            emission.outputs["Emission"],
            shader_nodes.socket_by_identifier(mix.inputs, "Shader_001"),
        )
        links.new(mix.outputs["Shader"], output.inputs["Surface"])

        texcoord = new_labeled_node(
            nodes, "ShaderNodeTexCoord", "Hologram Coordinates", (-2500, 520)
        )
        geometry = new_labeled_node(
            nodes, "ShaderNodeNewGeometry", "Hologram Geometry", (-2500, 60)
        )
        uv = texcoord.outputs["UV"]
        local_position = texcoord.outputs["Object"]
        world_position = geometry.outputs["Position"]
        world_normal = geometry.outputs["Normal"]
        incoming = geometry.outputs["Incoming"]

        normal = create_cp77_normal_texture(
            self,
            tree,
            data,
            "Normal",
            uv=uv,
            strength_key="NormalStrength",
            default_strength=1.0,
            location=(-2260, -320),
            label="Hologram V2 Normal",
        )
        shading_normal = normal if normal is not None else world_normal

        diffuse_tex = create_relative_texture_node(
            self,
            tree,
            data,
            "Diffuse",
            uv,
            (-2260, 720),
            error_label="hologram v2 Diffuse",
        )
        diffuse = diffuse_tex.outputs["Color"] if diffuse_tex is not None else _WHITE
        diffuse_alpha = diffuse_tex.outputs["Alpha"] if diffuse_tex is not None else 1.0
        if (
            diffuse_tex is not None
            and param_float(data, "FullColorOrGrayscale", 0.0) > 0.0
        ):
            luminance = shader_nodes.vector_math(
                tree.nodes,
                tree.links,
                "DOT_PRODUCT",
                diffuse,
                REC601_LUMA_WEIGHTS,
                name="Diffuse Luminance",
                location=(-1980, 780),
            )
            gray = new_labeled_node(
                nodes, "ShaderNodeCombineColor", "Diffuse Grayscale", (-1400, 780)
            )
            gray.mode = "RGB"
            for socket_name in ("Red", "Green", "Blue"):
                links.new(luminance, gray.inputs[socket_name])
            diffuse = mix_color_socket(
                nodes,
                links,
                "Full Color / Grayscale",
                diffuse,
                gray.outputs["Color"],
                max(0.0, min(1.0, param_float(data, "FullColorOrGrayscale", 0.0))),
                (-1180, 720),
            )
        if param_float(data, "IsHair", 0.0) >= 0.5:
            if diffuse_tex is not None:
                hair_split = new_labeled_node(
                    nodes, "ShaderNodeSeparateColor", "Hair Coverage", (-1420, 620)
                )
                hair_split.mode = "RGB"
                links.new(diffuse_tex.outputs["Color"], hair_split.inputs["Color"])
                diffuse_alpha = hair_split.outputs["Red"]
            diffuse = (0.5, 0.5, 0.5, 1.0)

        view = shader_nodes.vector_math(
            nodes,
            links,
            "SCALE",
            incoming,
            scale=-1.0,
            name="View Direction",
            location=(-2220, 20),
        )
        view = shader_nodes.vector_math(
            nodes,
            links,
            "NORMALIZE",
            view,
            name="Normalized View",
            location=(-2040, 20),
        )
        facing = shader_nodes.vector_math(
            nodes,
            links,
            "DOT_PRODUCT",
            view,
            shading_normal,
            name="View · Normal",
            location=(-1840, 20),
        )
        facing = shader_nodes.math(
            nodes,
            links,
            "MAXIMUM",
            facing,
            0.0,
            name="Front Facing",
            location=(-1660, 20),
        )
        one_minus_facing = shader_nodes.math(
            nodes,
            links,
            "SUBTRACT",
            1.0,
            facing,
            name="Fresnel Base",
            location=(-1480, 20),
        )
        fresnel = shader_nodes.math(
            nodes,
            links,
            "POWER",
            one_minus_facing,
            max(0.001, param_float(data, "FresnelExponent", 4.0)),
            name="Fresnel Exponent",
            location=(-1300, 20),
        )
        fresnel = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            fresnel,
            max(0.0, param_float(data, "FresnelIntensity", 20.0)),
            name="Fresnel Intensity",
            location=(-1120, 20),
        )

        light_vector = param_vector(data, "LightVector", (0.0, 0.0, 1.0, 0.0))
        light_node = new_labeled_node(
            nodes, "ShaderNodeCombineXYZ", "Light Vector", (-1800, -180)
        )
        light_node.inputs["X"].default_value = light_vector[0]
        light_node.inputs["Y"].default_value = light_vector[1]
        light_node.inputs["Z"].default_value = light_vector[2]
        light = shader_nodes.vector_math(
            nodes,
            links,
            "DOT_PRODUCT",
            shading_normal,
            light_node.outputs["Vector"],
            name="Light · Normal",
            location=(-1600, -180),
        )
        bleed = max(0.0, param_float(data, "LightBleed", 0.2))
        light = shader_nodes.math(
            nodes,
            links,
            "ADD",
            light,
            bleed,
            name="Light Bleed",
            location=(-1420, -180),
        )
        light = shader_nodes.math(
            nodes,
            links,
            "DIVIDE",
            light,
            1.0 + bleed,
            name="Light Normalize",
            location=(-1240, -180),
            use_clamp=True,
        )
        lit_color = mix_color_socket(
            nodes,
            links,
            "Light / Shade",
            param_color(data, "Color_Shade", (0.15, 0.11, 0.36, 1.0)),
            param_color(data, "Color_Light", (0.87, 0.15, 0.15, 1.0)),
            light,
            (-1000, 500),
        )
        surface = mix_color_socket(
            nodes,
            links,
            "Diffuse × Lighting",
            diffuse,
            lit_color,
            1.0,
            (-760, 620),
            blend_type="MULTIPLY",
            clamp=False,
        )

        use_local = param_float(data, "ReferencePosSpaceWorldLocal", 1.0) >= 0.5
        position = local_position if use_local else world_position
        gradient_vector = param_vector(data, "GradientVector", (0.0, 0.0, -1.0, 1.0))
        gradient_coord = _axis_dot(
            tree, position, gradient_vector, "Gradient Coordinate", (-2060, -560)
        )
        gradient = _map_range(
            tree,
            gradient_coord,
            param_float(data, "GradientMin", -0.8),
            param_float(data, "GradientMax", 0.8),
            "Hologram Gradient",
            (-1640, -560),
        )

        scan = _stripe_mask(
            tree,
            gradient_coord,
            param_float(data, "ScanLineDensity", 10.0),
            param_float(data, "ScanLineSize", 0.25),
            param_float(data, "ScanLineSteps", 16.0),
            "Scan Lines",
            (-2060, -820),
        )
        scan_depth = max(0.0, param_float(data, "ScanLineDepth", 4.0))
        scan = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            scan,
            min(1.0, scan_depth / 4.0),
            name="Scanline Depth",
            location=(-560, -720),
        )
        scan_fresnel_amount = max(0.0, param_float(data, "ScanLineFresnel", 1.0))
        scan_edge = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            fresnel,
            scan_fresnel_amount,
            name="Scanline Fresnel",
            location=(-380, -720),
        )
        scan = shader_nodes.math(
            nodes,
            links,
            "MAXIMUM",
            scan,
            scan_edge,
            name="Scanline Visibility",
            location=(-200, -720),
            use_clamp=True,
        )

        point = _point_mask(
            tree,
            position,
            param_float(data, "PointCloudDensity", 10.0),
            param_float(data, "PointCloudSize", 0.5),
            param_float(data, "PointCloudSteps", 16.0),
            "Point Cloud",
            (-2060, -1080),
        )
        point_gradient = _map_range(
            tree,
            gradient_coord,
            param_float(data, "PointGradientMin", -1.5),
            param_float(data, "PointGradientMax", 0.8),
            "Point Gradient",
            (-1040, -1080),
        )
        point = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            point,
            point_gradient,
            name="Point Gradient Mask",
            location=(-820, -1080),
        )
        point_depth = min(
            1.0, max(0.0, param_float(data, "PointCloudDepth", 4.0)) / 4.0
        )
        point = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            point,
            point_depth,
            name="Point Depth",
            location=(-640, -1080),
        )
        point_fresnel = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            fresnel,
            max(0.0, param_float(data, "PointCloudFresnel", 1.0)),
            name="Point Fresnel",
            location=(-460, -1080),
        )
        point = shader_nodes.math(
            nodes,
            links,
            "MAXIMUM",
            point,
            point_fresnel,
            name="Point Visibility",
            location=(-280, -1080),
            use_clamp=True,
        )
        point_color = param_color(data, "Color_PointCloud", (0.0, 0.95, 1.0, 1.0))
        surface = mix_color_socket(
            nodes,
            links,
            "Point Cloud Color",
            surface,
            point_color,
            point,
            (-500, 560),
            blend_type="SCREEN",
        )

        falloff = max(0.0, param_float(data, "Falloff", 2.0))
        edge = shader_nodes.math(
            nodes,
            links,
            "POWER",
            one_minus_facing,
            max(0.001, falloff),
            name="Edge Falloff",
            location=(-20, 0),
        )
        alpha = shader_nodes.math(
            nodes,
            links,
            "MAXIMUM",
            scan,
            point,
            name="Pattern Alpha",
            location=(160, -580),
            use_clamp=True,
        )
        alpha = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            alpha,
            gradient,
            name="Gradient Alpha",
            location=(340, -580),
            use_clamp=True,
        )
        alpha = shader_nodes.math(
            nodes,
            links,
            "MAXIMUM",
            alpha,
            edge,
            name="Fresnel Alpha",
            location=(520, -580),
            use_clamp=True,
        )
        alpha = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            alpha,
            diffuse_alpha,
            name="Diffuse Alpha",
            location=(700, -580),
            use_clamp=True,
        )

        thickness_tex = create_relative_texture_node(
            self,
            tree,
            data,
            "ThicknessTex",
            uv,
            (40, -980),
            non_color=True,
            error_label="hologram v2 ThicknessTex",
        )
        if thickness_tex is not None:
            thickness_split = new_labeled_node(
                nodes, "ShaderNodeSeparateColor", "Thickness", (260, -980)
            )
            thickness_split.mode = "RGB"
            links.new(thickness_tex.outputs["Color"], thickness_split.inputs["Color"])
            thickness = thickness_split.outputs["Red"]
            if param_float(data, "ThicknessFresnelModulate", 1.0) > 0.0:
                thickness_fresnel = shader_nodes.math(
                    nodes,
                    links,
                    "MULTIPLY",
                    thickness,
                    fresnel,
                    name="Thickness × Fresnel",
                    location=(460, -960),
                )
                thickness = shader_nodes.math(
                    nodes,
                    links,
                    "MAXIMUM",
                    thickness,
                    thickness_fresnel,
                    name="Thickness Fresnel",
                    location=(640, -960),
                    use_clamp=True,
                )
            alpha = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                alpha,
                thickness,
                name="Thickness Alpha",
                location=(880, -580),
                use_clamp=True,
            )

        color_fresnel = mix_color_socket(
            nodes,
            links,
            "Fresnel Highlight",
            surface,
            param_color(data, "Color_Light", _WHITE),
            fresnel,
            (20, 580),
            blend_type="SCREEN",
        )
        links.new(color_fresnel, emission.inputs["Color"])
        exposure = max(-16.0, min(16.0, param_float(data, "Exposure", 4.0)))
        emission.inputs["Strength"].default_value = max((2.0**exposure) - 1.0, 0.0)
        links.new(alpha, mix.inputs["Factor"])

        set_transparent(Mat)
        Mat.diffuse_color = (*param_color(data, "Color_Light", _WHITE)[:3], 1.0)


used_params = [
    "ReferencePosSpaceWorldLocal",
    "Diffuse",
    "FullColorOrGrayscale",
    "IsHair",
    "Normal",
    "NormalStrength",
    "ThicknessTex",
    "ThicknessFresnelModulate",
    "LightVector",
    "LightBleed",
    "FresnelExponent",
    "FresnelIntensity",
    "Color_Light",
    "Color_Shade",
    "Color_PointCloud",
    "Exposure",
    "Falloff",
    "GradientVector",
    "GradientMin",
    "GradientMax",
    "ScanLineDensity",
    "ScanLineSize",
    "ScanLineSteps",
    "ScanLineDepth",
    "ScanLineFresnel",
    "PointCloudDensity",
    "PointCloudSize",
    "PointCloudSteps",
    "PointCloudDepth",
    "PointCloudFresnel",
    "PointGradientMin",
    "PointGradientMax",
]


def material_cache_identity(raw_material):
    return filtered_material_data_identity(raw_material, used_params)
