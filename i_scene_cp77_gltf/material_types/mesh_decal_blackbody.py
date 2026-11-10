from ..bartmoss.scalar import clamp01
from ..blender import shader_nodes
from ..materials.blender.images import image_is_placeholder
from .blackbody_nodes import (
    blackbody_bundle,
    hsv_to_rgb_bundle,
    rgb_to_hsv_bundle,
)
from .bundles import emissive_scale_bundle
from .decal_contracts import contract_defaults
from .graph import (
    color_channel_socket,
    mix_color_socket,
    mix_scalar_socket,
    set_transparent,
    value_socket,
)
from .mat_common import (
    MaterialTypeBase,
    find_input,
    material_property_socket,
    new_labeled_node,
    param_float,
    param_vector,
)

TEMPLATE = "base\\fx\\_shaders\\mesh_decal__blackbody.mt"
_DEFAULTS = contract_defaults(TEMPLATE)


class MeshDecalBlackbody(MaterialTypeBase):
    texture_defaults = {
        key: value for key, value in _DEFAULTS.items() if isinstance(value, str)
    }

    def _texture(self, nodes, links, data, key, location, uv):
        image = self._load_relative_image(
            self._texture_path(data, key),
            non_color=True,
            error_label="mesh decal blackbody",
        )
        if image is None or image_is_placeholder(image):
            return None
        node = new_labeled_node(nodes, "ShaderNodeTexImage", key, location)
        node.image = image
        node.extension = "REPEAT"
        links.new(uv, node.inputs["Vector"])
        return node

    def create(self, Data, Mat):
        data = Data if isinstance(Data, dict) else {}
        Mat.use_nodes = True
        tree = Mat.node_tree
        nodes = tree.nodes
        links = tree.links
        nodes.clear()

        output = new_labeled_node(
            nodes, "ShaderNodeOutputMaterial", "Material Output", (7600, 160)
        )
        principled = new_labeled_node(
            nodes, "ShaderNodeBsdfPrincipled", "Mesh Decal Blackbody", (7320, 160)
        )
        links.new(principled.outputs["BSDF"], output.inputs["Surface"])

        uv = new_labeled_node(nodes, "ShaderNodeUVMap", "UV", (-2200, 420)).outputs[
            "UV"
        ]
        tiling = param_vector(data, "HeatTiling", _DEFAULTS["HeatTiling"])
        mapping = new_labeled_node(
            nodes, "ShaderNodeMapping", "Heat Tiling", (-1980, 240)
        )
        mapping.inputs.get("Scale").default_value = (tiling[0], tiling[1], 1.0)
        links.new(uv, mapping.inputs["Vector"])

        mask = self._texture(nodes, links, data, "MaskTexture", (-1740, 520), uv)
        heat = self._texture(
            nodes,
            links,
            data,
            "HeatDistribution",
            (-1740, 160),
            mapping.outputs["Vector"],
        )
        mask_value = (
            color_channel_socket(
                nodes,
                links,
                mask.outputs["Color"],
                "MaskTexture.x",
                (-1500, 520),
                channel="Red",
                mode="RGB",
            )
            if mask is not None
            else value_socket(nodes, "MaskTexture Fallback", 0.0, (-1500, 520))
        )
        heat_value = (
            color_channel_socket(
                nodes,
                links,
                heat.outputs["Color"],
                "HeatDistribution.x",
                (-1500, 160),
                channel="Red",
                mode="RGB",
            )
            if heat is not None
            else value_socket(nodes, "HeatDistribution Fallback", 0.0, (-1500, 160))
        )

        external_curve = material_property_socket(
            nodes,
            Mat,
            "cp77_MaterialParam0",
            1.0,
            (-1740, -180),
            "MaterialParam0 (external curve)",
            name="MaterialParam0",
            initial=1.0,
        )
        external = mix_scalar_socket(
            nodes,
            links,
            "Use Float Param",
            (-1320, -180),
            1.0,
            external_curve,
            clamp01(param_float(data, "UseFloatParam", _DEFAULTS["UseFloatParam"])),
        )
        heat_scale = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            heat_value,
            external,
            name="Heat x External Param",
            location=(-1120, 160),
        )
        heat_scale = shader_nodes.math(
            nodes,
            links,
            "ADD",
            heat_scale,
            param_float(data, "MaskMinimum", _DEFAULTS["MaskMinimum"]),
            name="MaskMinimum",
            location=(-920, 160),
            use_clamp=True,
        )
        heat_scale = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            heat_scale,
            mask_value,
            name="Heat x Mask",
            location=(-720, 160),
        )
        temperature = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            heat_scale,
            120.0 * param_float(data, "Temperature", _DEFAULTS["Temperature"]),
            name="BlackBody Temperature",
            location=(-520, 160),
        )

        blackbody = blackbody_bundle(tree, temperature, (-280, 160))
        hue, saturation, value = rgb_to_hsv_bundle(
            tree, blackbody, (-40, 160), "Blackbody HSV"
        )

        hsv_mod = param_vector(data, "HSV_Mod", _DEFAULTS["HSV_Mod"])
        hue = shader_nodes.math(
            nodes,
            links,
            "ADD",
            hue,
            hsv_mod[0],
            name="Hue + HSV_Mod.x",
            location=(4940, 360),
        )
        saturation = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            saturation,
            hsv_mod[1],
            name="Saturation x HSV_Mod.y",
            location=(4940, 200),
        )
        value = shader_nodes.math(
            nodes,
            links,
            "ADD",
            value,
            hsv_mod[2],
            name="Value + HSV_Mod.z",
            location=(4940, 40),
        )
        modified_heat = hsv_to_rgb_bundle(
            tree,
            hue,
            saturation,
            value,
            (5160, 200),
            "Modified Blackbody",
        )
        _, _, modified_value = rgb_to_hsv_bundle(
            tree, modified_heat, (5380, -420), "Modified Blackbody HSV"
        )

        guarded_value = shader_nodes.math(
            nodes,
            links,
            "MAXIMUM",
            modified_value,
            1.0e-20,
            name="Guard BlackBody Value",
            location=(7560, -420),
        )
        normalized_heat = mix_color_socket(
            nodes,
            links,
            "Normalize BlackBody Color",
            modified_heat,
            guarded_value,
            1.0,
            (7560, 420),
            blend_type="DIVIDE",
        )
        contrast = shader_nodes.math(
            nodes,
            links,
            "SUBTRACT",
            modified_value,
            0.5,
            name="Value - 0.5",
            location=(7760, -420),
        )
        contrast = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            contrast,
            param_float(
                data, "EmissiveAlphaContrast", _DEFAULTS["EmissiveAlphaContrast"]
            ),
            name="Emissive Alpha Contrast",
            location=(7960, -420),
        )
        emissive_alpha = shader_nodes.math(
            nodes,
            links,
            "ADD",
            contrast,
            0.5,
            name="Emissive Alpha",
            location=(8160, -420),
            use_clamp=True,
        )
        alpha = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            modified_value,
            7.0,
            name="BlackBody Surface Alpha",
            location=(8160, -220),
            use_clamp=True,
        )
        emissive_ev = max(
            -16.0, min(16.0, param_float(data, "EmissiveEV", _DEFAULTS["EmissiveEV"]))
        )
        emission_strength = emissive_scale_bundle(
            tree,
            emissive_alpha,
            emissive_ev,
            (8360, -420),
            "Blackbody Emission",
        ).outputs["Raw Strength"]

        links.new(normalized_heat, find_input(principled, "Base Color"))
        links.new(normalized_heat, find_input(principled, "Emission Color", "Emission"))
        links.new(emission_strength, find_input(principled, "Emission Strength"))
        links.new(alpha, find_input(principled, "Alpha"))
        find_input(principled, "Metallic").default_value = 1.0
        find_input(principled, "Roughness").default_value = 1.0

        vertex_offset = param_float(
            data, "VertexOffsetFactor", _DEFAULTS["VertexOffsetFactor"]
        )
        if abs(vertex_offset) > 1.0e-12:
            displacement = new_labeled_node(
                nodes, "ShaderNodeDisplacement", "VertexOffsetFactor", (7040, -620)
            )
            find_input(displacement, "Height").default_value = vertex_offset
            find_input(displacement, "Midlevel").default_value = 0.0
            find_input(displacement, "Scale").default_value = 1.0
            links.new(
                displacement.outputs["Displacement"], output.inputs["Displacement"]
            )

        set_transparent(Mat)
        if hasattr(Mat, "use_transparency_overlap"):
            Mat.use_transparency_overlap = True
        Mat["cp77_no_shadows"] = True
        Mat.diffuse_color = (1.0, 0.18, 0.03, 1.0)
