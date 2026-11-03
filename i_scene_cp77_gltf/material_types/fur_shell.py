from ..blender import shader_nodes
from ..materials.cache_identity import filtered_material_data_identity
from .graph import color_channel_socket, mix_color_socket, set_alpha_clip
from .mat_common import (
    MaterialTypeBase,
    create_relative_texture_node,
    find_input,
    new_labeled_node,
    param_color,
    param_float,
)
from .normal_math import create_cp77_normal_texture

TEMPLATE = r"base\materials\fur_shell.mt"


class FurShell(MaterialTypeBase):
    def create(self, Data, Mat):
        data = Data if isinstance(Data, dict) else {}
        Mat.use_nodes = True
        tree = Mat.node_tree
        nodes = tree.nodes
        links = tree.links
        nodes.clear()

        output = new_labeled_node(
            nodes, "ShaderNodeOutputMaterial", "Material Output", (760, 100)
        )
        principled = new_labeled_node(
            nodes, "ShaderNodeBsdfPrincipled", "Fur Shell", (480, 100)
        )
        links.new(principled.outputs["BSDF"], output.inputs["Surface"])
        uv = new_labeled_node(
            nodes, "ShaderNodeTexCoord", "Fur UV", (-1280, 300)
        ).outputs.get("UV")
        fur_uv = shader_nodes.vector_math(
            nodes,
            links,
            "MULTIPLY",
            uv,
            (max(0.0001, param_float(data, "FurTiling", 10.0)),) * 2 + (1.0,),
            name="Fur Tiling",
            location=(-1120, 180),
        )
        direction_uv = shader_nodes.vector_math(
            nodes,
            links,
            "MULTIPLY",
            uv,
            (max(0.0001, param_float(data, "DirectionMapTiling", 2.0)),) * 2 + (1.0,),
            name="Direction Tiling",
            location=(-1120, -500),
        )

        base = create_relative_texture_node(
            self, tree, data, "BaseMap", uv, (-980, 500), error_label="fur BaseMap"
        )
        fur = create_relative_texture_node(
            self,
            tree,
            data,
            "FurMap",
            fur_uv,
            (-880, 220),
            non_color=True,
            error_label="fur FurMap",
        )
        alpha_map = create_relative_texture_node(
            self,
            tree,
            data,
            "AlphaMap",
            uv,
            (-980, -40),
            non_color=True,
            error_label="fur AlphaMap",
        )
        roughness = create_relative_texture_node(
            self,
            tree,
            data,
            "Roughness",
            uv,
            (-980, -300),
            non_color=True,
            error_label="fur Roughness",
        )

        base_color = base.outputs.get("Color") if base is not None else None
        if base_color is None:
            color_node = new_labeled_node(
                nodes, "ShaderNodeRGB", "Fur Base Fallback", (-720, 500)
            )
            color_node.outputs["Color"].default_value = (0.5, 0.5, 0.5, 1.0)
            base_color = color_node.outputs["Color"]

        fur_mask = None
        if fur is not None:
            fur_mask = color_channel_socket(
                nodes,
                links,
                fur.outputs["Color"],
                "FurMap.r",
                (-700, 220),
                channel="Red",
            )
            contrast = max(0.0, param_float(data, "FurContrast", 1.0))
            if abs(contrast - 1.0) > 1.0e-6:
                fur_mask = shader_nodes.math(
                    nodes,
                    links,
                    "POWER",
                    fur_mask,
                    contrast,
                    name="Fur Contrast",
                    location=(-500, 220),
                    use_clamp=True,
                )

        if fur_mask is not None:
            ao_color = param_color(data, "AOColor", (0.0, 0.0, 0.0, 1.0))
            ao_intensity = max(0.0, min(1.0, param_float(data, "FurAOIntensity", 1.0)))
            ao_factor = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                fur_mask,
                ao_intensity,
                name="Fur AO Intensity",
                location=(-300, 220),
                use_clamp=True,
            )
            base_color = mix_color_socket(
                nodes,
                links,
                "Fur AO",
                ao_color,
                base_color,
                ao_factor,
                (-60, 420),
                clamp=True,
            )
        links.new(base_color, find_input(principled, "Base Color"))

        find_input(principled, "Metallic").default_value = max(
            0.0, min(1.0, param_float(data, "Metalness", 0.0))
        )
        rough_bias = param_float(data, "RoughnessBias", 0.0)
        if roughness is not None:
            rough = color_channel_socket(
                nodes,
                links,
                roughness.outputs["Color"],
                "Roughness.r",
                (-700, -300),
                channel="Red",
            )
            rough = shader_nodes.math(
                nodes,
                links,
                "ADD",
                rough,
                rough_bias,
                name="Roughness + Bias",
                location=(-460, -300),
                use_clamp=True,
            )
            links.new(rough, find_input(principled, "Roughness"))
        else:
            find_input(principled, "Roughness").default_value = max(
                0.0, min(1.0, 0.5 + rough_bias)
            )

        direction_normal = create_cp77_normal_texture(
            self,
            tree,
            data,
            key="DirectionMap",
            uv=direction_uv,
            strength_key="FurNormalIntensity",
            default_strength=0.5,
            location=(-920, -560),
            label="Fur Direction",
        )
        if direction_normal is not None:
            links.new(direction_normal, find_input(principled, "Normal"))

        alpha = fur_mask if fur_mask is not None else 1.0
        if alpha_map is not None:
            packed_alpha = color_channel_socket(
                nodes,
                links,
                alpha_map.outputs["Color"],
                "AlphaMap.r",
                (-700, -80),
                channel="Red",
            )
            alpha = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                alpha,
                packed_alpha,
                name="Fur × Alpha",
                location=(-460, -40),
                use_clamp=True,
            )
        if base is not None:
            alpha = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                alpha,
                base.outputs["Alpha"],
                name="Fur Base Alpha",
                location=(-240, -40),
                use_clamp=True,
            )
        if hasattr(alpha, "is_output"):
            links.new(alpha, find_input(principled, "Alpha"))
        else:
            find_input(principled, "Alpha").default_value = float(alpha)

        threshold = max(0.0, min(1.0, param_float(data, "AlphaThreshold", 0.0)))
        set_alpha_clip(Mat, threshold)


used_params = [
    "BaseMap",
    "FurMap",
    "AlphaMap",
    "Roughness",
    "Metalness",
    "RoughnessBias",
    "AOColor",
    "FurAOIntensity",
    "FurContrast",
    "DirectionMap",
    "FurNormalIntensity",
    "AlphaThreshold",
    "FurTiling",
    "DirectionMapTiling",
]


def material_cache_identity(raw_material):
    return filtered_material_data_identity(raw_material, used_params)
