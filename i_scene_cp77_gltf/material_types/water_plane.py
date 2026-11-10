from ..blender import shader_nodes
from ..materials.cache_identity import filtered_material_data_identity
from .graph import set_transparent
from .mat_common import (
    MaterialTypeBase,
    create_relative_texture_node,
    find_input,
    new_labeled_node,
    param_color,
    param_float,
    param_vector,
    scene_time_socket,
)
from .normal_math import (
    decode_cp77_normal,
    encode_tangent_normal,
    tangent_to_normal_map,
)

TEMPLATE = r"base\fx\shaders\water_plane.mt"


def _animated_uv(tree, uv, scale, speed, time, name, location):
    nodes = tree.nodes
    links = tree.links
    scaled = shader_nodes.vector_math(
        nodes,
        links,
        "MULTIPLY",
        uv,
        (scale[0], scale[1], 1.0),
        name=f"{name} Scale",
        location=location,
    )
    return shader_nodes.vector_math(
        nodes,
        links,
        "MULTIPLY_ADD",
        time,
        (speed[0], speed[1], 0.0),
        scaled,
        name=name,
        location=(location[0] + 180, location[1]),
    )


class WaterPlane(MaterialTypeBase):
    def create(self, Data, Mat):
        data = Data if isinstance(Data, dict) else {}
        Mat.use_nodes = True
        tree = Mat.node_tree
        nodes = tree.nodes
        links = tree.links
        nodes.clear()

        output = new_labeled_node(
            nodes, "ShaderNodeOutputMaterial", "Material Output", (1460, 140)
        )
        principled = new_labeled_node(
            nodes, "ShaderNodeBsdfPrincipled", "Water Plane", (1120, 220)
        )
        transparent = new_labeled_node(
            nodes, "ShaderNodeBsdfTransparent", "Transparent Backface", (1120, -100)
        )
        geometry = new_labeled_node(
            nodes, "ShaderNodeNewGeometry", "Water Geometry", (840, -180)
        )
        backface_mix = new_labeled_node(
            nodes, "ShaderNodeMixShader", "Front Face Only", (1320, 120)
        )
        links.new(geometry.outputs["Backfacing"], backface_mix.inputs["Factor"])
        links.new(principled.outputs["BSDF"], backface_mix.inputs["Shader"])
        links.new(
            transparent.outputs["BSDF"],
            shader_nodes.socket_by_identifier(backface_mix.inputs, "Shader_001"),
        )
        links.new(backface_mix.outputs["Shader"], output.inputs["Surface"])

        tint = param_color(data, "TintColor", (207 / 255, 219 / 255, 219 / 255, 1.0))
        tint_node = new_labeled_node(
            nodes, "ShaderNodeRGB", "Shallow Water Tint", (660, 420)
        )
        tint_node.outputs["Color"].default_value = tint
        links.new(tint_node.outputs["Color"], find_input(principled, "Base Color"))
        find_input(principled, "Metallic").default_value = 0.0
        find_input(principled, "Roughness").default_value = 0.0
        transmission = find_input(principled, "Transmission Weight", "Transmission")
        if transmission is not None:
            transmission.default_value = 1.0
        ior = max(1.0, min(2.0, param_float(data, "IOR", 1.2)))
        ior_socket = find_input(principled, "IOR")
        if ior_socket is not None:
            ior_socket.default_value = ior
        reflection = max(
            0.0, min(1.0, param_float(data, "ReflectionPower", 5.0) * 0.15)
        )
        specular = find_input(principled, "IOR Level", "Specular IOR Level")
        if specular is not None:
            specular.default_value = reflection

        texcoord = new_labeled_node(
            nodes, "ShaderNodeTexCoord", "Water UV", (-1600, 260)
        )
        uv = texcoord.outputs["UV"]
        time = scene_time_socket(tree.nodes, (-1600, -140), "Water Time")
        scale_speed = param_vector(
            data, "TexCoordDtortScaleSpeed", (2.0, 2.0, 0.05, 0.0)
        )
        uv_a = _animated_uv(
            tree,
            uv,
            (scale_speed[0], scale_speed[1]),
            (scale_speed[2], scale_speed[3]),
            time,
            "Water Normal UV A",
            (-1380, 260),
        )
        uv_b = _animated_uv(
            tree,
            uv,
            (scale_speed[0] * 1.2, scale_speed[1] * 1.2),
            (-scale_speed[2], -scale_speed[3]),
            time,
            "Water Normal UV B",
            (-1380, -60),
        )

        normal_a = create_relative_texture_node(
            self,
            tree,
            data,
            "Normal",
            uv_a,
            (-760, 300),
            non_color=True,
            error_label="water plane Normal",
        )
        normal_b = create_relative_texture_node(
            self,
            tree,
            data,
            "Normal",
            uv_b,
            (-760, -40),
            non_color=True,
            error_label="water plane Normal",
        )
        alpha_tex = create_relative_texture_node(
            self,
            tree,
            data,
            "Alpha",
            uv,
            (-760, -360),
            non_color=True,
            error_label="water plane Alpha",
        )
        alpha_mask = alpha_tex.outputs["Color"] if alpha_tex is not None else 1.0
        if alpha_tex is not None:
            alpha_split = new_labeled_node(
                nodes, "ShaderNodeSeparateColor", "Distortion Mask", (-540, -360)
            )
            alpha_split.mode = "RGB"
            links.new(alpha_tex.outputs["Color"], alpha_split.inputs["Color"])
            alpha_mask = alpha_split.outputs["Red"]

        if normal_a is not None and normal_b is not None:
            tangent_a = decode_cp77_normal(
                tree,
                normal_a.outputs["Color"],
                strength=1.0,
                location=(-500, 260),
                label="Water Normal A",
            )
            tangent_b = decode_cp77_normal(
                tree,
                normal_b.outputs["Color"],
                strength=1.0,
                location=(-500, -40),
                label="Water Normal B",
            )
            split_a = new_labeled_node(
                nodes, "ShaderNodeSeparateXYZ", "Water Normal A XYZ", (-220, 260)
            )
            split_b = new_labeled_node(
                nodes, "ShaderNodeSeparateXYZ", "Water Normal B XYZ", (-220, -40)
            )
            links.new(tangent_a.outputs["Tangent"], split_a.inputs["Vector"])
            links.new(tangent_b.outputs["Tangent"], split_b.inputs["Vector"])
            x = shader_nodes.math(
                nodes,
                links,
                "ADD",
                split_a.outputs["X"],
                split_b.outputs["X"],
                name="Water X Sum",
                location=(0, 260),
            )
            y = shader_nodes.math(
                nodes,
                links,
                "ADD",
                split_a.outputs["Y"],
                split_b.outputs["Y"],
                name="Water Y Sum",
                location=(0, 120),
            )
            x = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                x,
                0.5,
                name="Water X Average",
                location=(180, 260),
            )
            y = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                y,
                0.5,
                name="Water Y Average",
                location=(180, 120),
            )

            reflect = param_vector(
                data, "ReflectNormalMultiplier", (0.01, 0.01, 1.0, 0.0)
            )
            amount = max(0.0, param_float(data, "DistortAmount", 50.0)) * 0.75
            x = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                x,
                reflect[0] * amount,
                name="Water X Strength",
                location=(360, 260),
            )
            y = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                y,
                reflect[1] * amount,
                name="Water Y Strength",
                location=(360, 120),
            )
            x = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                x,
                alpha_mask,
                name="Water X Mask",
                location=(540, 260),
            )
            y = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                y,
                alpha_mask,
                name="Water Y Mask",
                location=(540, 120),
            )
            tangent = new_labeled_node(
                nodes, "ShaderNodeCombineXYZ", "Water Tangent Normal", (700, 180)
            )
            links.new(x, tangent.inputs["X"])
            links.new(y, tangent.inputs["Y"])
            tangent.inputs["Z"].default_value = 1.0
            normalize = shader_nodes.vector_math(
                nodes,
                links,
                "NORMALIZE",
                name="Water Normal Normalize",
                location=(860, 180),
            ).node
            links.new(tangent.outputs["Vector"], normalize.inputs["Vector"])
            encoded = encode_tangent_normal(
                tree,
                normalize.outputs["Vector"],
                location=(860, 20),
                label="Water Normal Encode",
            )
            normal = tangent_to_normal_map(
                tree, encoded, location=(1020, 20), label="Water Normal"
            )
            links.new(normal, find_input(principled, "Normal"))

        set_transparent(Mat)
        Mat.use_raytrace_refraction = True
        Mat.diffuse_color = tint


used_params = [
    "TintColor",
    "TintColorDeep",
    "TexCoordDtortScaleSpeed",
    "DistortAmount",
    "IOR",
    "ReflectionPower",
    "ReflectNormalMultiplier",
    "Normal",
    "Alpha",
]


def material_cache_identity(raw_material):
    return filtered_material_data_identity(raw_material, used_params)
