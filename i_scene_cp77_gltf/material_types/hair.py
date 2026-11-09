import os

from ..assetio.catalog import ResourceKind
from ..assetio.resolver import resolve_asset_path
from ..blender import shader_nodes
from ..materials.hair_profile_contract import store_source_profile
from ..materials.resources import load_material_document
from .bundles import smoothstep_socket
from .graph import (
    color_channel_socket,
    cp77_bitangent_socket,
    cp77_uv_tangent_node,
    mix_color_socket,
    mix_scalar_socket,
)
from .mat_common import (
    MaterialTypeBase,
    create_relative_texture_node,
    find_input,
    new_labeled_node,
    param_float,
    populate_color_ramp,
)

# The rounded luma weights.
_HAIR_LUMA_WEIGHTS = (0.3, 0.59, 0.11)


def _overlay(tree, base, blend, location):
    nodes = tree.nodes
    links = tree.links
    lum = shader_nodes.vector_math(
        nodes,
        links,
        "DOT_PRODUCT",
        blend,
        _HAIR_LUMA_WEIGHTS,
        name="Luminance",
        location=(location[0] + 180, location[1] + 50),
    )

    low = mix_color_socket(
        nodes,
        links,
        "Overlay Low",
        base,
        blend,
        1.0,
        (location[0] + 360, location[1] + 250),
        blend_type="MULTIPLY",
        clamp=False,
    )
    low = mix_color_socket(
        nodes,
        links,
        "Overlay Low ×2",
        low,
        (2.0, 2.0, 2.0, 1.0),
        1.0,
        (location[0] + 560, location[1] + 250),
        blend_type="MULTIPLY",
        clamp=False,
    )

    inv_base_node = new_labeled_node(
        nodes, "ShaderNodeInvert", "1 - Base", (location[0] + 360, location[1] - 250)
    )
    inv_base_node.inputs["Factor"].default_value = 1.0
    links.new(base, inv_base_node.inputs["Color"])
    inv_base = inv_base_node.outputs["Color"]
    inv_blend_node = new_labeled_node(
        nodes, "ShaderNodeInvert", "1 - RootTip", (location[0] + 360, location[1] - 370)
    )
    inv_blend_node.inputs["Factor"].default_value = 1.0
    links.new(blend, inv_blend_node.inputs["Color"])
    inv_blend = inv_blend_node.outputs["Color"]
    product = mix_color_socket(
        nodes,
        links,
        "Overlay High Product",
        inv_base,
        inv_blend,
        1.0,
        (location[0] + 560, location[1] - 300),
        blend_type="MULTIPLY",
        clamp=False,
    )
    twice = mix_color_socket(
        nodes,
        links,
        "Overlay High ×2",
        product,
        (2.0, 2.0, 2.0, 1.0),
        1.0,
        (location[0] + 740, location[1] - 300),
        blend_type="MULTIPLY",
        clamp=False,
    )
    high_node = new_labeled_node(
        nodes,
        "ShaderNodeInvert",
        "Overlay High",
        (location[0] + 900, location[1] - 300),
    )
    high_node.inputs["Factor"].default_value = 1.0
    links.new(twice, high_node.inputs["Color"])
    high = high_node.outputs["Color"]

    choose_high = shader_nodes.math(
        nodes,
        links,
        "GREATER_THAN",
        lum,
        0.499999,
        name="Root/Tip Luminance >= .5",
        location=(location[0] + 720, location[1]),
    )
    return mix_color_socket(
        nodes,
        links,
        "Overlay",
        low,
        high,
        choose_high,
        (location[0] + 1080, location[1] + 60),
        clamp=True,
    )


class Hair(MaterialTypeBase):
    def create(self, Data, Mat):
        data = Data if isinstance(Data, dict) else {}
        tree = Mat.node_tree
        nodes = tree.nodes
        links = tree.links
        principled = shader_nodes.principled_bsdf(nodes)
        if principled is None:
            return

        profile_ref = data.get("HairProfile")
        if not profile_ref:
            return
        profile_path = resolve_asset_path(
            str(profile_ref) + ".json",
            roots=(self.ProjPath, self.BasePath),
            extensions=(".hp.json",),
            warn=False,
        )
        if not profile_path:
            profile_path = os.path.normpath(
                os.path.join(
                    self.BasePath, (str(profile_ref) + ".json").replace("\\", os.sep)
                )
            )
        resource = load_material_document(
            profile_path, expected_kind=ResourceKind.HAIR_PROFILE
        )
        if resource is None:
            return
        profile = resource.root

        strand_id = create_relative_texture_node(
            self, tree, data, "Strand_ID", None, (-1500, 560), non_color=True
        )
        strand_gradient = create_relative_texture_node(
            self, tree, data, "Strand_Gradient", None, (-1500, 280), non_color=True
        )
        strand_alpha = create_relative_texture_node(
            self, tree, data, "Strand_Alpha", None, (-1500, 0), non_color=True
        )
        flow = create_relative_texture_node(
            self, tree, data, "Flow", None, (-1500, -360), non_color=True
        )
        if strand_id is None or strand_gradient is None or strand_alpha is None:
            return

        id_value = color_channel_socket(
            tree.nodes,
            tree.links,
            strand_id.outputs.get("Color") or strand_id.outputs["Color"],
            "Strand ID R",
            (-1260, 560),
        )
        root_tip_value = color_channel_socket(
            tree.nodes,
            tree.links,
            strand_gradient.outputs.get("Color") or strand_gradient.outputs["Color"],
            "Root To Tip R",
            (-1260, 280),
        )
        alpha = color_channel_socket(
            tree.nodes,
            tree.links,
            strand_alpha.outputs.get("Color") or strand_alpha.outputs["Color"],
            "Strand Alpha R",
            (-1260, 0),
        )

        id_entries = profile.get("gradientEntriesID", [])
        root_tip_entries = profile.get("gradientEntriesRootToTip", [])
        id_ramp = new_labeled_node(
            nodes, "ShaderNodeValToRGB", "Hair Profile ID", (-1000, 560)
        )
        populate_color_ramp(id_ramp, id_entries)
        links.new(id_value, id_ramp.inputs["Factor"])
        root_ramp = new_labeled_node(
            nodes, "ShaderNodeValToRGB", "Hair Profile Root To Tip", (-1000, 280)
        )
        populate_color_ramp(root_ramp, root_tip_entries)
        store_source_profile(Mat, profile)
        links.new(root_tip_value, root_ramp.inputs["Factor"])
        base_color = _overlay(
            tree,
            id_ramp.outputs.get("Color") or id_ramp.outputs["Color"],
            root_ramp.outputs.get("Color") or root_ramp.outputs["Color"],
            (-760, 400),
        )

        if param_float(data, "DebugHairColor", 0.0) >= 0.5:
            debug_white = new_labeled_node(
                nodes, "ShaderNodeRGB", "Debug Hair White", (520, 620)
            )
            debug_white.outputs["Color"].default_value = (1.0, 1.0, 1.0, 1.0)
            base_color = debug_white.outputs["Color"]

        vertex = new_labeled_node(
            nodes, "ShaderNodeVertexColor", "Hair Shadow Vertex Color", (-680, -40)
        )
        vertex_r = color_channel_socket(
            tree.nodes,
            tree.links,
            vertex.outputs.get("Color") or vertex.outputs["Color"],
            "Vertex R",
            (-480, -40),
        )
        one_minus_r = shader_nodes.math(
            nodes,
            links,
            "SUBTRACT",
            1.0,
            vertex_r,
            name="1 - Vertex R",
            location=(-300, -40),
        )
        shadow = smoothstep_socket(
            tree,
            one_minus_r,
            param_float(data, "ShadowMin", -0.5),
            param_float(data, "ShadowMax", 1.0),
            (-100, -40),
            "Hair Shadow",
        )
        shadowed = mix_color_socket(
            nodes,
            links,
            "Baked Shadow",
            base_color,
            shadow,
            1.0,
            (700, 300),
            blend_type="MULTIPLY",
            clamp=True,
        )
        final_color = mix_color_socket(
            nodes,
            links,
            "Hair Shadow Strength",
            base_color,
            shadowed,
            max(0.0, min(1.0, param_float(data, "ShadowStrength", 0.0))),
            (920, 380),
        )
        final_color = mix_color_socket(
            nodes,
            links,
            "Hair Global Albedo",
            final_color,
            (0.6, 0.6, 0.6, 1.0),
            1.0,
            (1140, 380),
            blend_type="MULTIPLY",
            clamp=True,
        )
        links.new(final_color, find_input(principled, "Base Color"))

        rough = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            id_value,
            param_float(data, "RoughnessScale", 1.0),
            name="Hair Roughness Scale",
            location=(-300, -200),
        )
        rough = shader_nodes.math(
            nodes,
            links,
            "ADD",
            rough,
            param_float(data, "RoughnessBias", 0.0),
            name="Hair Roughness Bias",
            location=(-120, -200),
            use_clamp=True,
        )
        shadow_weight = shader_nodes.math(
            nodes,
            links,
            "SUBTRACT",
            1.0,
            shadow,
            name="1 - Shadow",
            location=(520, -180),
        )
        shadow_weight = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            shadow_weight,
            max(0.0, min(1.0, param_float(data, "ShadowStrength", 0.0))),
            name="Shadow Roughness Weight",
            location=(700, -180),
        )
        final_rough = mix_scalar_socket(
            nodes,
            links,
            "Hair Shadow Roughness",
            (900, -180),
            rough,
            param_float(data, "ShadowRoughness", 1.0),
            shadow_weight,
        )
        links.new(final_rough, find_input(principled, "Roughness"))
        metallic = find_input(principled, "Metallic")
        if metallic is not None:
            metallic.default_value = 0.0

        alpha_input = find_input(principled, "Alpha")
        if alpha_input is not None:
            links.new(alpha, alpha_input)
        Mat.surface_render_method = "DITHERED"
        if hasattr(Mat, "alpha_threshold"):
            Mat.alpha_threshold = max(
                0.0, min(1.0, param_float(data, "AlphaCutoff", 0.33))
            )

        anisotropic = find_input(principled, "Anisotropic IOR Level", "Anisotropic")
        if anisotropic is not None:
            anisotropic.default_value = 1.0
        if flow is not None:
            flow_split = new_labeled_node(
                nodes, "ShaderNodeSeparateColor", "Flow RG", (-1240, -360)
            )
            flow_split.mode = "RGB"
            links.new(
                flow.outputs.get("Color") or flow.outputs["Color"],
                flow_split.inputs["Color"],
            )
            fx = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                flow_split.outputs["Red"],
                2.0,
                name="Flow R ×2",
                location=(-1040, -320),
            )
            fx = shader_nodes.math(
                nodes, links, "SUBTRACT", fx, 1.0, name="Flow X", location=(-860, -320)
            )
            fy = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                flow_split.outputs["Green"],
                2.0,
                name="Flow G ×2",
                location=(-1040, -440),
            )
            fy = shader_nodes.math(
                nodes, links, "SUBTRACT", fy, 1.0, name="Flow Y", location=(-860, -440)
            )
            strength = max(0.0, min(1.0, param_float(data, "FlowStrength", 1.0)))
            fx = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                fx,
                strength,
                name="Flow X Strength",
                location=(-680, -320),
            )
            fy = mix_scalar_socket(
                nodes, links, "Flow Y Strength", (-680, -440), 1.0, fy, strength
            )
            fx = shader_nodes.math(
                nodes,
                links,
                "MAXIMUM",
                fx,
                0.01,
                name="Flow X Min",
                location=(-500, -320),
            )
            fy = shader_nodes.math(
                nodes,
                links,
                "MAXIMUM",
                fy,
                0.01,
                name="Flow Y Min",
                location=(-500, -440),
            )

            tangent = cp77_uv_tangent_node(nodes, (-280, -500), label="Surface Tangent")
            geometry = new_labeled_node(
                nodes, "ShaderNodeNewGeometry", "Surface Geometry", (-280, -660)
            )
            binormal = cp77_bitangent_socket(
                nodes,
                links,
                geometry.outputs.get("Normal"),
                tangent.outputs.get("Tangent") or tangent.outputs["Tangent"],
                (-80, -600),
                label="Surface Binormal",
            )
            tx = shader_nodes.vector_math(
                nodes,
                links,
                "SCALE",
                tangent.outputs.get("Tangent") or tangent.outputs["Tangent"],
                scale=fx,
                name="Flow Tangent",
                location=(140, -440),
            )
            by = shader_nodes.vector_math(
                nodes,
                links,
                "SCALE",
                binormal,
                scale=fy,
                name="Flow Binormal",
                location=(140, -600),
            )
            direction = shader_nodes.vector_math(
                nodes, links, "ADD", tx, by, name="Hair Direction", location=(360, -500)
            )
            direction = shader_nodes.vector_math(
                nodes,
                links,
                "NORMALIZE",
                direction,
                name="Hair Direction Normalize",
                location=(560, -500),
            )
            tangent_input = find_input(principled, "Tangent")
            if tangent_input is not None:
                links.new(direction, tangent_input)
