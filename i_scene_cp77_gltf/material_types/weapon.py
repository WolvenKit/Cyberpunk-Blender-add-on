from ..blender import shader_nodes
from ..materials.cache_identity import filtered_material_data_identity
from .graph import mix_color_socket, separate_color_sockets
from .mat_common import (
    MaterialTypeBase,
    create_relative_texture_node,
    find_input,
    new_labeled_node,
    param_float,
)
from .normal_math import create_cp77_normal_texture

TEMPLATE = r"base\materials\weapon.mt"


class Weapon(MaterialTypeBase):
    def create(self, Data, Mat):
        data = Data if isinstance(Data, dict) else {}
        Mat.use_nodes = True
        tree = Mat.node_tree
        nodes = tree.nodes
        links = tree.links
        nodes.clear()

        output = new_labeled_node(
            nodes, "ShaderNodeOutputMaterial", "Material Output", (780, 100)
        )
        principled = new_labeled_node(
            nodes, "ShaderNodeBsdfPrincipled", "Weapon", (500, 100)
        )
        links.new(principled.outputs["BSDF"], output.inputs["Surface"])
        uv = new_labeled_node(
            nodes, "ShaderNodeTexCoord", "Weapon UV", (-1280, 260)
        ).outputs.get("UV")

        base = create_relative_texture_node(
            self,
            tree,
            data,
            "GlobalBaseColor",
            uv,
            (-980, 520),
            error_label="weapon GlobalBaseColor",
        )
        if base is not None:
            links.new(base.outputs["Color"], find_input(principled, "Base Color"))

        normal = create_cp77_normal_texture(
            self,
            tree,
            data,
            key="GlobalNormal",
            uv=uv,
            strength_key=None,
            default_strength=1.0,
            location=(-980, 160),
            label="Weapon Global Normal",
        )
        if normal is not None:
            links.new(normal, find_input(principled, "Normal"))

        mrm = create_relative_texture_node(
            self,
            tree,
            data,
            "GlobalMRM",
            uv,
            (-980, -180),
            non_color=True,
            error_label="weapon GlobalMRM",
        )
        if mrm is not None:
            metal, rough, _ = separate_color_sockets(
                nodes, links, mrm.outputs["Color"], "GlobalMRM RGB", (-700, -120)
            )
            links.new(metal, find_input(principled, "Metallic"))
            links.new(rough, find_input(principled, "Roughness"))
        else:
            find_input(principled, "Metallic").default_value = 0.0
            find_input(principled, "Roughness").default_value = 0.5

        pattern_tiling = max(0.0001, param_float(data, "PatternTiling", 2.0))
        pattern_map = create_relative_texture_node(
            self,
            tree,
            data,
            "PatternBaseColor",
            None,
            (-980, -500),
            error_label="weapon PatternBaseColor",
        )
        global_id = create_relative_texture_node(
            self,
            tree,
            data,
            "GlobalID",
            uv,
            (-980, -760),
            non_color=True,
            error_label="weapon GlobalID",
        )
        if pattern_map is not None:
            mapping = new_labeled_node(
                nodes, "ShaderNodeMapping", "Pattern Tiling", (-1220, -500)
            )
            mapping.inputs["Scale"].default_value = (
                pattern_tiling,
                pattern_tiling,
                1.0,
            )
            links.new(uv, mapping.inputs["Vector"])
            links.new(mapping.outputs["Vector"], pattern_map.inputs["Vector"])
        if pattern_map is not None and global_id is not None and base is not None:
            id_r, id_g, id_b = separate_color_sockets(
                nodes, links, global_id.outputs["Color"], "GlobalID RGB", (-700, -700)
            )
            rg = shader_nodes.math(
                nodes,
                links,
                "MAXIMUM",
                id_r,
                id_g,
                name="Weapon ID max RG",
                location=(-480, -760),
            )
            pattern_mask = shader_nodes.math(
                nodes,
                links,
                "MAXIMUM",
                rg,
                id_b,
                name="Weapon ID Coverage",
                location=(-260, -760),
                use_clamp=True,
            )
            preview = mix_color_socket(
                nodes,
                links,
                "Weapon Pattern Contract Preview",
                base.outputs["Color"],
                pattern_map.outputs["Color"],
                pattern_mask,
                (-40, 420),
                clamp=True,
            )
            links.new(preview, find_input(principled, "Base Color"))


used_params = [
    "GlobalBaseColor",
    "GlobalNormal",
    "GlobalMRM",
    "GlobalID",
    "PatternBaseColor",
    "PatternTiling",
]


def material_cache_identity(raw_material):
    return filtered_material_data_identity(raw_material, used_params)
