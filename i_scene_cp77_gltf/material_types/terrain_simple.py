from ..materials.cache_identity import filtered_material_data_identity
from .graph import mix_color_socket
from .mat_common import (
    MaterialTypeBase,
    create_relative_texture_node,
    find_input,
    new_labeled_node,
    param_vector,
)
from .normal_math import decode_cp77_normal

TEMPLATE = r"base\materials\terrain_simple.mt"


def _object_xy_uv(tree, scale_offset):
    nodes = tree.nodes
    links = tree.links
    texcoord = new_labeled_node(
        nodes, "ShaderNodeTexCoord", "Terrain Position", (-1120, 180)
    )
    mapping = new_labeled_node(
        nodes, "ShaderNodeMapping", "UVGenScaleOffset", (-900, 180)
    )
    mapping.vector_type = "POINT"
    sx, sy, ox, oy = scale_offset
    mapping.inputs["Location"].default_value = (float(ox), float(oy), 0.0)
    mapping.inputs["Scale"].default_value = (float(sx), float(sy), 1.0)
    links.new(texcoord.outputs["Object"], mapping.inputs["Vector"])
    return mapping.outputs["Vector"]


class TerrainSimple(MaterialTypeBase):
    def create(self, Data, Mat):
        data = Data if isinstance(Data, dict) else {}
        Mat.use_nodes = True
        tree = Mat.node_tree
        nodes = tree.nodes
        links = tree.links
        nodes.clear()

        output = new_labeled_node(
            nodes, "ShaderNodeOutputMaterial", "Material Output", (700, 80)
        )
        principled = new_labeled_node(
            nodes, "ShaderNodeBsdfPrincipled", "Terrain Simple", (420, 80)
        )
        links.new(principled.outputs["BSDF"], output.inputs["Surface"])

        scale_offset = param_vector(data, "UVGenScaleOffset", (0.0, 0.0, 0.0, 0.0))
        mask_uv = _object_xy_uv(tree, scale_offset)

        base = create_relative_texture_node(
            self,
            tree,
            data,
            "BaseColor",
            mask_uv,
            (-620, 360),
            error_label="terrain simple BaseColor",
        )
        if base is not None:
            color = mix_color_socket(
                nodes,
                links,
                "Terrain BaseColor × 0.5",
                base.outputs["Color"],
                (0.5, 0.5, 0.5, 1.0),
                1.0,
                (-260, 360),
                blend_type="MULTIPLY",
                clamp=True,
            )
            links.new(color, find_input(principled, "Base Color"))
        else:
            find_input(principled, "Base Color").default_value = (0.5, 0.5, 0.5, 1.0)

        normal = create_relative_texture_node(
            self,
            tree,
            data,
            "GlobalNormal",
            mask_uv,
            (-620, -20),
            non_color=True,
            error_label="terrain simple GlobalNormal",
        )
        if normal is not None:
            decoded = decode_cp77_normal(
                tree,
                normal.outputs["Color"],
                strength=1.0,
                location=(-260, -20),
                label="Terrain Global Normal",
            )
            links.new(decoded.outputs["Tangent"], find_input(principled, "Normal"))

        find_input(principled, "Metallic").default_value = 0.0
        find_input(principled, "Roughness").default_value = 0.8
        ior_level = find_input(principled, "IOR Level", "Specular IOR Level")
        if ior_level is not None:
            ior_level.default_value = 0.25


used_params = ["BaseColor", "GlobalNormal", "UVGenScaleOffset"]


def material_cache_identity(raw_material):
    return filtered_material_data_identity(raw_material, used_params)
