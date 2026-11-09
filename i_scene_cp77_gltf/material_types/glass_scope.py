from ..blender import shader_nodes
from ..blender.shader_nodes import assign_socket
from .bundles import sphere_mask_socket
from .graph import mix_color_socket
from .mat_common import (
    MaterialTypeBase,
    create_relative_texture_node,
    find_input,
    new_labeled_node,
    param_color,
    param_float,
    param_texture_path,
    param_vector,
)
from .normal_math import (
    decode_cp77_normal,
    encode_tangent_normal,
    tangent_to_normal_map,
)
from .parallax_math import tangent_view_vector

_WHITE = (1.0, 1.0, 1.0, 1.0)
_BLACK = (0.0, 0.0, 0.0, 1.0)


def _scale_uv_center(tree, uv, scale, location, label):
    scale = max(1.0e-6, float(scale))
    mapping = new_labeled_node(tree.nodes, "ShaderNodeMapping", label, location)
    mapping.vector_type = "POINT"
    inv = 1.0 / scale
    mapping.inputs["Location"].default_value = (0.5 - 0.5 * inv, 0.5 - 0.5 * inv, 0.0)
    mapping.inputs["Scale"].default_value = (inv, inv, 1.0)
    tree.links.new(uv, mapping.inputs["Vector"])
    return mapping.outputs["Vector"]


def _mask_texture_or_sphere(
    owner, tree, data, enabled, key, uv, radius, hardness, location, label
):
    if enabled:
        scaled = _scale_uv_center(tree, uv, radius, location, f"{label} Center Scale")
        tex = create_relative_texture_node(
            owner,
            tree,
            data,
            key,
            scaled,
            (location[0] + 220, location[1]),
            non_color=True,
            extension="CLIP",
        )
        if tex is not None:
            split = new_labeled_node(
                tree.nodes,
                "ShaderNodeSeparateColor",
                f"{label}.r",
                (location[0] + 440, location[1]),
            )
            tree.links.new(tex.outputs["Color"], split.inputs["Color"])
            return split.outputs["Red"]
    return sphere_mask_socket(tree, uv, radius, hardness, location, label)


class GlassScope(MaterialTypeBase):
    """Build the scope glass preview with a neutral screen-feedback fallback"""

    def create(self, Data, Mat):
        data = Data if isinstance(Data, dict) else {}
        tree = Mat.node_tree
        nodes, links = tree.nodes, tree.links
        principled = shader_nodes.principled_bsdf(nodes)
        if principled is None:
            return

        coord = new_labeled_node(nodes, "ShaderNodeTexCoord", "Scope UV", (-1900, 400))
        uv = coord.outputs["UV"]
        tiling = param_vector(data, "UvTilingOffset", (1.0, 1.0, 0.0, 0.0))
        mapping = new_labeled_node(
            nodes, "ShaderNodeMapping", "Scope TiledUV", (-1680, 400)
        )
        mapping.vector_type = "POINT"
        mapping.inputs["Location"].default_value = (tiling[2], tiling[3], 0.0)
        mapping.inputs["Scale"].default_value = (tiling[0], tiling[1], 1.0)
        links.new(uv, mapping.inputs["Vector"])
        tiled_uv = mapping.outputs["Vector"]

        diffuse = create_relative_texture_node(
            self, tree, data, "Diffuse", tiled_uv, (-1420, 620)
        )
        rough_tex = create_relative_texture_node(
            self, tree, data, "Roughness", tiled_uv, (-1420, 380), non_color=True
        )
        glass_tint = create_relative_texture_node(
            self, tree, data, "GlassTint", tiled_uv, (-1420, 120)
        )

        rough = 0.0
        if rough_tex is not None:
            split_r = new_labeled_node(
                nodes, "ShaderNodeSeparateColor", "Roughness.r", (-1200, 380)
            )
            links.new(rough_tex.outputs["Color"], split_r.inputs["Color"])
            rough = split_r.outputs["Red"]
        mask_alpha = 0.0
        if diffuse is not None:
            mask_alpha = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                diffuse.outputs["Alpha"],
                param_float(data, "MaskOpacity", 0.0),
                name="MaskOpacity × Diffuse.a",
                location=(-1180, 620),
                use_clamp=True,
            )
        rough_partial = shader_nodes.math(
            nodes,
            links,
            "ADD",
            rough,
            mask_alpha,
            name="Scope Roughness Partial",
            location=(-920, 430),
        )
        glass_rough = shader_nodes.math(
            nodes,
            links,
            "ADD",
            rough_partial,
            param_float(data, "LensRoughness", 0.0),
            name="LensRoughness + Partial",
            location=(-740, 430),
        )
        glass_rough = shader_nodes.math(
            nodes,
            links,
            "MINIMUM",
            glass_rough,
            0.8,
            name="Scope Roughness <= .8",
            location=(-560, 430),
            use_clamp=True,
        )
        assign_socket(tree.links, glass_rough, find_input(principled, "Roughness"))

        use_mask = param_vector(data, "UseMask", (0.0, 0.0, 0.0, 0.0))
        lens_radius = param_float(data, "LensBulgeRadius", 0.5)
        lens_strength = param_float(data, "LensBulgeStrength", 1.0)
        if use_mask[1] > 0.5 and param_texture_path(data, "LensBulge"):
            lens_uv = _scale_uv_center(
                tree, uv, lens_radius, (-1420, -260), "LensBulge Center Scale"
            )
            lens_tex = create_relative_texture_node(
                self,
                tree,
                data,
                "LensBulge",
                lens_uv,
                (-1180, -260),
                non_color=True,
                extension="CLIP",
            )
            normal_socket = None
            if lens_tex is not None:
                decoded = decode_cp77_normal(
                    tree,
                    lens_tex.outputs["Color"],
                    strength=max(0.0, lens_strength),
                    location=(-920, -260),
                    label="LensBulge DirectX Decode",
                )
                invert_xy = shader_nodes.vector_math(
                    nodes,
                    links,
                    "MULTIPLY",
                    name="LensBulge -XY",
                    location=(-660, -260),
                ).node
                shader_nodes.socket_by_identifier(
                    invert_xy.inputs, "Vector_001"
                ).default_value = (-1.0, -1.0, 1.0)
                links.new(decoded.outputs["Tangent"], invert_xy.inputs["Vector"])
                normalized = shader_nodes.vector_math(
                    nodes,
                    links,
                    "NORMALIZE",
                    invert_xy.outputs["Vector"],
                    name="LensBulge Normalize",
                    location=(-460, -260),
                )
                encoded = encode_tangent_normal(
                    tree, normalized, location=(-260, -260), label="LensBulge Encode"
                )
                normal_socket = tangent_to_normal_map(
                    tree, encoded, location=(-60, -260), label="Scope Lens Normal"
                )
        else:
            centered = shader_nodes.vector_math(
                nodes,
                links,
                "MULTIPLY_ADD",
                name="Lens UV Centered",
                location=(-1180, -320),
            ).node
            shader_nodes.socket_by_identifier(
                centered.inputs, "Vector_001"
            ).default_value = (2.0, 2.0, 0.0)
            shader_nodes.socket_by_identifier(
                centered.inputs, "Vector_002"
            ).default_value = (-1.0, -1.0, 0.0)
            links.new(uv, centered.inputs["Vector"])
            sphere = sphere_mask_socket(
                tree,
                uv,
                lens_radius,
                param_float(data, "LensBulgeHardness", 0.0),
                (-1420, -520),
                "Lens Distortion Radial Mask",
            )
            xy = shader_nodes.vector_math(
                nodes,
                links,
                "SCALE",
                centered.outputs["Vector"],
                scale=sphere,
                name="Lens Distortion XY",
                location=(-900, -430),
            )
            xy = shader_nodes.vector_math(
                nodes,
                links,
                "SCALE",
                xy,
                scale=lens_strength,
                name="Lens Distortion Strength",
                location=(-700, -430),
            )
            split_xy = new_labeled_node(
                nodes,
                "ShaderNodeSeparateXYZ",
                "Lens Distortion Components",
                (-500, -430),
            )
            links.new(xy, split_xy.inputs["Vector"])
            tangent = new_labeled_node(
                nodes, "ShaderNodeCombineXYZ", "LensBulge Tangent", (-300, -430)
            )
            links.new(split_xy.outputs["X"], tangent.inputs["X"])
            links.new(split_xy.outputs["Y"], tangent.inputs["Y"])
            tangent.inputs["Z"].default_value = 1.0
            normalized = shader_nodes.vector_math(
                nodes,
                links,
                "NORMALIZE",
                tangent.outputs["Vector"],
                name="LensBulge Normalize",
                location=(-100, -430),
            )
            encoded = encode_tangent_normal(
                tree, normalized, location=(100, -430), label="LensBulge Encode"
            )
            normal_socket = tangent_to_normal_map(
                tree, encoded, location=(300, -430), label="Scope Lens Normal"
            )
        if normal_socket is not None:
            links.new(normal_socket, find_input(principled, "Normal"))

        view = tangent_view_vector(
            tree, location=(-1880, -980), label="Scope Tangent View", flip_y=True
        )
        view_split = new_labeled_node(
            nodes, "ShaderNodeSeparateXYZ", "Scope View", (-720, -980)
        )
        links.new(view, view_split.inputs["Vector"])
        view_xy = new_labeled_node(
            nodes, "ShaderNodeCombineXYZ", "Scope View XY", (-520, -980)
        )
        links.new(view_split.outputs["X"], view_xy.inputs["X"])
        links.new(view_split.outputs["Y"], view_xy.inputs["Y"])
        far_offset = shader_nodes.vector_math(
            nodes,
            links,
            "SCALE",
            view_xy.outputs["Vector"],
            scale=-param_float(data, "ScopeMaskFarDistance", 2.0),
            name="Scope Far View Offset",
            location=(-320, -980),
        )
        bump_uv = shader_nodes.vector_math(
            nodes,
            links,
            "ADD",
            uv,
            far_offset,
            name="Scope Far UV",
            location=(-120, -980),
        )

        close = _mask_texture_or_sphere(
            self,
            tree,
            data,
            use_mask[0] > 0.5,
            "ScopeMaskClose",
            uv,
            param_float(data, "SphereMaskCloseRadius", 0.5),
            param_float(data, "SphereMaskCloseHardness", 0.95),
            (-1400, -1180),
            "Scope Close Mask",
        )
        far = _mask_texture_or_sphere(
            self,
            tree,
            data,
            use_mask[2] > 0.5,
            "ScopeMaskFar",
            bump_uv,
            param_float(data, "SphereMaskFarRadius", 0.5),
            param_float(data, "SphereMaskFarHardness", 0.5),
            (-1400, -1420),
            "Scope Far Mask",
        )
        eye_relief = param_vector(data, "EyeRelief", (0.5, 0.25, 1.0, 0.0))
        eye_uv = shader_nodes.vector_math(
            nodes,
            links,
            "MULTIPLY_ADD",
            view_xy.outputs["Vector"],
            eye_relief[2],
            uv,
            name="Eye Relief UV",
            location=(-120, -1120),
        )
        eye_mask = sphere_mask_socket(
            tree,
            eye_uv,
            eye_relief[0],
            eye_relief[1],
            (-1400, -1660),
            "Eye Relief Mask",
        )
        comb = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            far,
            close,
            name="Far × Close",
            location=(240, -1320),
        )
        comb = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            comb,
            eye_mask,
            name="Scope Combined Masks",
            location=(420, -1320),
        )
        close_eye = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            close,
            eye_mask,
            name="Close × Eye",
            location=(240, -1520),
        )

        scope_inside = param_color(data, "ScopeInside", (0.1, 0.2, 0.1, 1.0))
        inside = mix_color_socket(
            nodes, links, "Scope Inside", scope_inside, _BLACK, far, (620, -1280)
        )
        scope_whole = mix_color_socket(
            nodes, links, "Scope Whole", _BLACK, inside, close_eye, (820, -1280)
        )

        tint_multiplier = param_color(data, "GlassTintMultiplier", (1.0, 1.0, 1.0, 1.0))
        tint_const = (tint_multiplier[0], tint_multiplier[1], tint_multiplier[2], 1.0)
        if glass_tint is not None:
            refraction_tint = mix_color_socket(
                nodes,
                links,
                "GlassTint × Multiplier",
                glass_tint.outputs["Color"],
                tint_const,
                1.0,
                (620, 120),
                blend_type="MULTIPLY",
                clamp=False,
            )
        else:
            refraction_tint = tint_const

        neutral_feedback = refraction_tint
        masked_feedback = mix_color_socket(
            nodes,
            links,
            "Neutral Feedback Mask",
            _BLACK,
            neutral_feedback,
            comb,
            (860, -40),
        )
        final_color = mix_color_socket(
            nodes,
            links,
            "Scope Static Color",
            masked_feedback,
            scope_whole,
            1.0,
            (1060, 100),
            blend_type="ADD",
            clamp=True,
        )
        links.new(final_color, find_input(principled, "Base Color"))

        metallic = find_input(principled, "Metallic")
        if metallic is not None:
            metallic.default_value = max(
                0.0, min(1.0, param_float(data, "LensMetalness", 0.5))
            )
        transmission = find_input(principled, "Transmission Weight", "Transmission")
        if transmission is not None:
            transmission.default_value = 1.0
        specular = find_input(principled, "Specular IOR Level")
        if specular is not None:
            specular.default_value = max(
                0.0, min(1.0, 0.5 * param_float(data, "LensReflectionPower", 1.0))
            )
        specular_tint = find_input(principled, "Specular Tint")
        if specular_tint is not None:
            specular_tint.default_value = param_color(data, "LensSpecularColor", _WHITE)
        alpha = find_input(principled, "Alpha")
        if alpha is not None:
            alpha.default_value = 1.0

        Mat.surface_render_method = "DITHERED"
