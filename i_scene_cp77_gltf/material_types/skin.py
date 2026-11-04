from ..assetio.paths import backslash_depot_key
from ..bartmoss.scalar import clamp01
from ..blender import shader_nodes
from ..blender.shader_nodes import assign_if_changed, set_default_if_changed
from .bundles import smoothstep_socket, tangent_normal_blend_socket
from .decal_math import ev_to_linear
from .graph import (
    mix_color_second_input,
    mix_color_socket,
    mix_scalar_socket,
    separate_color_node,
)
from .mat_common import (
    MaterialTypeBase,
    create_relative_texture_node,
    find_input,
    new_labeled_node,
    param_color,
    param_float,
    param_texture_path,
)
from .normal_math import (
    decode_cp77_normal,
    encode_tangent_normal,
    tangent_to_normal_map,
)
from .skin_regions import DEFAULT_FACE_REGIONSET_PATH
from .skin_wrinkles import (
    WRINKLE_REGION_COUNT,
    blend_wrinkle_normal,
    build_wrinkle_influence,
)

_WHITE = (1.0, 1.0, 1.0, 1.0)


def _source_xy(tree, color, label, location):
    split = separate_color_node(tree.nodes, tree.links, color, f"{label} RG", location)
    x2 = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        split.outputs["Red"],
        2.0,
        name=f"{label} X×2",
        location=(location[0] + 180, location[1] + 40),
    )
    x = shader_nodes.math(
        tree.nodes,
        tree.links,
        "SUBTRACT",
        x2,
        1.0,
        name=f"{label} X",
        location=(location[0] + 360, location[1] + 40),
    )
    y2 = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        split.outputs["Green"],
        2.0,
        name=f"{label} Y×2",
        location=(location[0] + 180, location[1] - 60),
    )
    y = shader_nodes.math(
        tree.nodes,
        tree.links,
        "SUBTRACT",
        y2,
        1.0,
        name=f"{label} Y",
        location=(location[0] + 360, location[1] - 60),
    )
    return x, y


def _atlas_uv(tree, uv, scale, region_scale, frame, label, location):
    nodes = tree.nodes
    links = tree.links
    scale_factor = shader_nodes.math(
        nodes,
        links,
        "ADD",
        region_scale,
        1.4 if frame == 0 else 1.0,
        name=f"{label} Region Scale",
        location=location,
    )
    total_scale = shader_nodes.math(
        nodes,
        links,
        "MULTIPLY",
        scale,
        scale_factor,
        name=f"{label} UV Scale",
        location=(location[0] + 160, location[1]),
    )
    scaled = shader_nodes.vector_math(
        nodes,
        links,
        "SCALE",
        uv,
        scale=total_scale,
        name=f"{label} Scaled UV",
        location=(location[0] + 320, location[1]),
    )
    frac = shader_nodes.vector_math(
        nodes,
        links,
        "FRACTION",
        scaled,
        name=f"{label} Repeat",
        location=(location[0] + 480, location[1]),
    )
    half = shader_nodes.vector_math(
        nodes,
        links,
        "MULTIPLY",
        frac,
        (0.5, 1.0, 1.0),
        name=f"{label} Atlas Half",
        location=(location[0] + 640, location[1]),
    )
    if frame == 0:
        return half
    return shader_nodes.vector_math(
        nodes,
        links,
        "ADD",
        half,
        (0.5, 0.0, 0.0),
        name=f"{label} Atlas Offset",
        location=(location[0] + 800, location[1]),
    )


# Texture parameters a skin samples (each named after its parameter), and whether each is non-colour data.
_TEXTURES = (
    ("Roughness", True),
    ("TintColorMask", True),
    ("Normal", True),
    ("Detailmap_Stretch", True),
    ("Detailmap_Squash", True),
    ("DetailNormal", True),
    ("Albedo", False),
    ("SecondaryAlbedo", False),
    ("Bloodflow", True),
    ("EmissiveMask", True),
)
_WRINKLE_TEXTURES = ("Detailmap_Stretch", "Detailmap_Squash", "Bloodflow")


def _is_blendable(template):
    return "blendable" in template or "blackwall" in template


def _values(data):
    """The skin's per-material values, as the build writes them into its nodes"""
    bias_min = param_float(data, "DetailRoughnessBiasMin", 0.0)
    bias_max = param_float(data, "DetailRoughnessBiasMax", 1.0)
    return {
        "detail_normal_influence": clamp01(
            param_float(data, "DetailNormalInfluence", 1.0)
        ),
        "micro_uv_01": max(0.0, param_float(data, "MicroDetailUVScale01", 1.0)),
        "micro_uv_02": max(0.0, param_float(data, "MicroDetailUVScale02", 1.0)),
        "micro_influence": clamp01(param_float(data, "MicroDetailInfluence", 0.0)),
        "rough_bias": (min(bias_min, bias_max), max(bias_min, bias_max)),
        "cavity": param_float(data, "CavityIntensity", 0.0) * 0.1,
        "tint_color": param_color(data, "TintColor", _WHITE),
        "tint_scale": param_float(data, "TintScale", 0.0),
        "secondary_tint": param_float(data, "SecondaryAlbedoTintColorInfluence", 0.0),
        "secondary_influence": param_float(data, "SecondaryAlbedoInfluence", 0.0),
        "blood_color": param_color(data, "BloodColor", (0.0, 0.0, 0.0, 1.0)),
        "emissive_ev": param_float(data, "EmissiveEV", 0.0),
    }


def _set_image(node, image):
    if node.image is not image:
        node.image = image


class Skin(MaterialTypeBase):
    def _texture_keys(self, data, blendable):
        """The texture parameters a build loads"""
        for key, non_color in _TEXTURES:
            if blendable and key in {"SecondaryAlbedo", "EmissiveMask"}:
                continue
            if key == "EmissiveMask" and param_float(data, "EmissiveEV", 0.0) == 0.0:
                continue
            yield key, non_color

    def _images(self, data, blendable):
        images = {
            key: self._load_relative_image(
                param_texture_path(data, key), non_color=non_color, error_label=key
            )
            for key, non_color in self._texture_keys(data, blendable)
        }
        micro_path = param_texture_path(data, "MicroDetail")
        images["MicroDetail"] = (
            self._load_relative_image(
                micro_path, non_color=True, error_label="MicroDetail"
            )
            if micro_path
            else None
        )
        return images

    def structure_key(self, Data):
        # Which textures load, whether wrinkle textures are named, the tint's blend mode and whether the skin emits
        # shape the graph; every other parameter is a value written into its nodes.
        data = Data if isinstance(Data, dict) else {}
        images = self._images(data, _is_blendable(self.material_template))
        return (
            tuple((key, image is not None) for key, image in images.items()),
            any(param_texture_path(data, key) for key in _WRINKLE_TEXTURES),
            param_float(data, "TintScale", 0.0) >= 0.0,
            param_float(data, "EmissiveEV", 0.0) != 0.0,
        )

    def apply_structure_values(self, Data, Mat, slots):
        data = Data if isinstance(Data, dict) else {}
        nodes = Mat.node_tree.nodes
        images = self._images(data, _is_blendable(self.material_template))
        for key, image in images.items():
            if image is None:
                continue
            for name in (
                ("MicroDetail 01", "MicroDetail 02") if key == "MicroDetail" else (key,)
            ):
                _set_image(nodes[name], image)
        values = _values(data)

        def write(name, socket, value):
            node = nodes.get(name)
            if node is not None:
                set_default_if_changed(socket(node), value)

        if "detail_normal_blend" in slots:
            write(
                slots["detail_normal_blend"],
                lambda node: node.inputs["Factor"],
                values["detail_normal_influence"],
            )
        write(
            "Microdetail 01 UV Scale",
            lambda node: node.inputs["Value"],
            values["micro_uv_01"],
        )
        write(
            "Microdetail 02 UV Scale",
            lambda node: node.inputs["Value"],
            values["micro_uv_02"],
        )
        write(
            "Microdetail Normal Influence",
            lambda node: shader_nodes.socket_by_identifier(node.inputs, "Value_001"),
            values["micro_influence"],
        )
        write(
            "Detail Roughness Bias",
            lambda node: find_input(node, "A"),
            values["rough_bias"][0],
        )
        write(
            "Detail Roughness Bias",
            lambda node: find_input(node, "B"),
            values["rough_bias"][1],
        )
        write(
            "Cavity Intensity",
            lambda node: shader_nodes.socket_by_identifier(node.inputs, "Value_001"),
            values["cavity"],
        )
        write(
            "Tint Scale × Mask",
            lambda node: node.inputs["Value"],
            abs(values["tint_scale"]),
        )
        blend_type = "MULTIPLY" if values["tint_scale"] >= 0.0 else "OVERLAY"
        write(
            f"Tint {blend_type.title()}", mix_color_second_input, values["tint_color"]
        )
        write(
            "Secondary Tint Mask",
            lambda node: shader_nodes.socket_by_identifier(node.inputs, "Value_001"),
            values["secondary_tint"],
        )
        write(
            "Secondary Influence × Alpha",
            lambda node: shader_nodes.socket_by_identifier(node.inputs, "Value_001"),
            values["secondary_influence"],
        )
        write("Blood Influenced Tint", mix_color_second_input, values["blood_color"])
        if values["emissive_ev"] != 0.0:
            emissive = max(0.0, ev_to_linear(values["emissive_ev"]) - 1.0)
            if "Skin EmissiveEV" in nodes:
                write(
                    "Skin EmissiveEV",
                    lambda node: shader_nodes.socket_by_identifier(
                        node.inputs, "Value_001"
                    ),
                    emissive,
                )
            else:
                write(
                    "Skin", lambda node: find_input(node, "Emission Strength"), emissive
                )
        assign_if_changed(Mat, "diffuse_color", (*values["tint_color"][:3], 1.0))

    def create(self, Data, Mat):
        data = Data if isinstance(Data, dict) else {}
        template = backslash_depot_key(Mat.get("MaterialTemplate", ""))
        is_blendable = _is_blendable(template)
        values = _values(data)
        self.structure_slots = {}
        Mat.use_nodes = True
        tree = Mat.node_tree
        nodes = tree.nodes
        links = tree.links
        nodes.clear()

        texcoord = new_labeled_node(nodes, "ShaderNodeTexCoord", "UV", (-2200, 400))
        uv = texcoord.outputs["UV"]
        principled = new_labeled_node(
            nodes, "ShaderNodeBsdfPrincipled", "Skin", (1700, 220)
        )
        output = new_labeled_node(
            nodes, "ShaderNodeOutputMaterial", "Material Output", (1980, 220)
        )
        links.new(principled.outputs["BSDF"], output.inputs["Surface"])

        # Roughness texture is R=roughness, G=metalness, B=detail mask.
        rough_tex = create_relative_texture_node(
            self, tree, data, "Roughness", uv, (-1900, 80), non_color=True
        )
        rough = 0.5
        metal = 0.0
        detail_mask = 0.0
        if rough_tex is not None:
            rms = separate_color_node(
                tree.nodes,
                tree.links,
                rough_tex.outputs["Color"],
                "Rough/Metal/Detail",
                (-1660, 80),
            )
            rough = rms.outputs["Red"]
            metal = rms.outputs["Green"]
            detail_mask = rms.outputs["Blue"]
            links.new(metal, find_input(principled, "Metallic"))

        tint_mask_tex = create_relative_texture_node(
            self, tree, data, "TintColorMask", uv, (-1900, -180), non_color=True
        )
        tint_mask = 1.0
        region = 0.0
        region_scale = 0.0
        if tint_mask_tex is not None:
            tint_split = separate_color_node(
                tree.nodes,
                tree.links,
                tint_mask_tex.outputs["Color"],
                "Tint/Microdetail Mask",
                (-1660, -180),
            )
            tint_mask = tint_split.outputs["Red"]
            g6 = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                tint_split.outputs["Green"],
                6.0,
                name="Microdetail Regions ×6",
                location=(-1460, -100),
            )
            g_floor = shader_nodes.math(
                nodes,
                links,
                "FLOOR",
                g6,
                name="Microdetail Regions floor",
                location=(-1300, -100),
            )
            region = shader_nodes.math(
                nodes,
                links,
                "DIVIDE",
                g_floor,
                6.0,
                name="Microdetail Regions",
                location=(-1140, -100),
            )
            b5 = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                tint_split.outputs["Blue"],
                5.0,
                name="Microdetail Scale ×5",
                location=(-1460, -260),
            )
            b_floor = shader_nodes.math(
                nodes,
                links,
                "FLOOR",
                b5,
                name="Microdetail Scale floor",
                location=(-1300, -260),
            )
            region_scale = shader_nodes.math(
                nodes,
                links,
                "DIVIDE",
                b_floor,
                5.0,
                name="Microdetail Scale",
                location=(-1140, -260),
            )
        mdr_scale = smoothstep_socket(
            tree, region, 0.0, 1.0, (-940, -100), "Microdetail Region Blend"
        )
        md_uv_lerp = smoothstep_socket(
            tree, region_scale, 0.0, 1.0, (-940, -300), "Microdetail UV Blend"
        )

        wrinkle_textures_present = any(
            param_texture_path(data, key)
            for key in ("Detailmap_Stretch", "Detailmap_Squash", "Bloodflow")
        )
        if wrinkle_textures_present:
            squash_scale, stretch_scale = build_wrinkle_influence(tree)
            Mat["cp77_skin_wrinkle_region_count"] = WRINKLE_REGION_COUNT
            Mat["cp77_skin_wrinkle_region_set"] = DEFAULT_FACE_REGIONSET_PATH
        else:
            squash_scale = 0.0
            stretch_scale = 0.0

        # Apply normals from broadest deformation to finest surface detail.
        normal_tangent = None
        normal_tex = create_relative_texture_node(
            self, tree, data, "Normal", uv, (-1900, -520), non_color=True
        )
        if normal_tex is not None:
            normal_tangent = decode_cp77_normal(
                tree,
                normal_tex.outputs["Color"],
                strength=1.0,
                location=(-1640, -520),
                label="Skin Normal DirectX Decode",
            ).outputs["Tangent"]

        stretch_tex = create_relative_texture_node(
            self, tree, data, "Detailmap_Stretch", uv, (-1900, -680), non_color=True
        )
        if stretch_tex is not None:
            stretch_tangent = decode_cp77_normal(
                tree,
                stretch_tex.outputs["Color"],
                strength=1.0,
                location=(-1640, -680),
                label="Stretch Wrinkle DirectX Decode",
            ).outputs["Tangent"]
            normal_tangent = blend_wrinkle_normal(
                tree,
                normal_tangent,
                stretch_tangent,
                stretch_scale,
                "Stretch Wrinkle Normal",
                (-1380, -640),
            )

        squash_tex = create_relative_texture_node(
            self, tree, data, "Detailmap_Squash", uv, (-1900, -840), non_color=True
        )
        if squash_tex is not None:
            squash_tangent = decode_cp77_normal(
                tree,
                squash_tex.outputs["Color"],
                strength=1.0,
                location=(-1640, -840),
                label="Squash Wrinkle DirectX Decode",
            ).outputs["Tangent"]
            normal_tangent = blend_wrinkle_normal(
                tree,
                normal_tangent,
                squash_tangent,
                squash_scale,
                "Squash Wrinkle Normal",
                (-1380, -800),
            )

        detail_tangent = None
        detail_source_x = 0.0
        detail_tex = create_relative_texture_node(
            self, tree, data, "DetailNormal", uv, (-1900, -1000), non_color=True
        )
        if detail_tex is not None:
            detail_tangent = decode_cp77_normal(
                tree,
                detail_tex.outputs["Color"],
                strength=1.0,
                location=(-1640, -1000),
                label="Detail Normal DirectX Decode",
            ).outputs["Tangent"]
        if normal_tangent is not None and detail_tangent is not None:
            normal_tangent = tangent_normal_blend_socket(
                tree,
                normal_tangent,
                detail_tangent,
                values["detail_normal_influence"],
                (-1060, -900),
                "Detail Normal Blend",
            )
            self.structure_slots["detail_normal_blend"] = normal_tangent.node.name
        elif detail_tangent is not None:
            normal_tangent = detail_tangent

        micro_tex_path = param_texture_path(data, "MicroDetail")
        micro1 = micro2 = None
        micro1_source = micro2_source = None
        if micro_tex_path:
            image = self._load_relative_image(
                micro_tex_path, non_color=True, error_label="MicroDetail"
            )
            if image is not None:
                uv1 = _atlas_uv(
                    tree,
                    uv,
                    values["micro_uv_01"],
                    md_uv_lerp,
                    0,
                    "Microdetail 01",
                    (-1800, -1080),
                )
                uv2 = _atlas_uv(
                    tree,
                    uv,
                    values["micro_uv_02"],
                    md_uv_lerp,
                    1,
                    "Microdetail 02",
                    (-1800, -1320),
                )
                tex1 = new_labeled_node(
                    nodes, "ShaderNodeTexImage", "MicroDetail 01", (-900, -1080)
                )
                tex1.image = image
                tex1.extension = "REPEAT"
                links.new(uv1, tex1.inputs["Vector"])
                tex2 = new_labeled_node(
                    nodes, "ShaderNodeTexImage", "MicroDetail 02", (-900, -1320)
                )
                tex2.image = image
                tex2.extension = "REPEAT"
                links.new(uv2, tex2.inputs["Vector"])
                micro1 = decode_cp77_normal(
                    tree,
                    tex1.outputs["Color"],
                    strength=1.0,
                    location=(-640, -1080),
                    label="Microdetail 01 DirectX Decode",
                ).outputs["Tangent"]
                micro2 = decode_cp77_normal(
                    tree,
                    tex2.outputs["Color"],
                    strength=1.0,
                    location=(-640, -1320),
                    label="Microdetail 02 DirectX Decode",
                ).outputs["Tangent"]
                micro1_source = _source_xy(
                    tree, tex1.outputs["Color"], "Microdetail 01 Source", (-360, -1080)
                )
                micro2_source = _source_xy(
                    tree, tex2.outputs["Color"], "Microdetail 02 Source", (-360, -1320)
                )

        micro_rough_blend = None
        if micro1 is not None and micro2 is not None:
            delta = shader_nodes.vector_math(
                nodes,
                links,
                "SUBTRACT",
                micro1,
                micro2,
                name="Microdetail 01-02",
                location=(80, -1180),
            )
            micro_mix = shader_nodes.vector_math(
                nodes,
                links,
                "MULTIPLY_ADD",
                delta,
                mdr_scale,
                micro2,
                name="Microdetail Blend",
                location=(440, -1180),
            )
            if normal_tangent is not None:
                influence = shader_nodes.math(
                    nodes,
                    links,
                    "MULTIPLY",
                    detail_mask,
                    values["micro_influence"],
                    name="Microdetail Normal Influence",
                    location=(620, -1040),
                )
                normal_tangent = tangent_normal_blend_socket(
                    tree,
                    normal_tangent,
                    micro_mix,
                    influence,
                    (800, -1080),
                    "Microdetail Normal Blend",
                )
            else:
                normal_tangent = micro_mix

            def detail_roughness(pair, label, y):
                x, yy = pair
                one_plus_x = shader_nodes.math(
                    nodes, links, "ADD", x, 1.0, name=f"{label} 1+x", location=(80, y)
                )
                one_plus_y = shader_nodes.math(
                    nodes,
                    links,
                    "ADD",
                    yy,
                    1.0,
                    name=f"{label} 1+y",
                    location=(80, y - 80),
                )
                y_term = shader_nodes.math(
                    nodes,
                    links,
                    "MULTIPLY",
                    yy,
                    one_plus_y,
                    name=f"{label} y(1+y)",
                    location=(240, y - 80),
                )
                total = shader_nodes.math(
                    nodes,
                    links,
                    "MULTIPLY_ADD",
                    x,
                    one_plus_x,
                    y_term,
                    name=f"{label} Sum",
                    location=(400, y - 40),
                )
                total = shader_nodes.math(
                    nodes,
                    links,
                    "MULTIPLY",
                    total,
                    2.5,
                    name=f"{label} ×2.5",
                    location=(560, y - 40),
                )
                return shader_nodes.math(
                    nodes, links, "ADD", total, 0.2, name=label, location=(720, y - 40)
                )

            dr1 = detail_roughness(micro1_source, "Detail Roughness 01", -1480)
            dr2 = detail_roughness(micro2_source, "Detail Roughness 02", -1680)
            micro_rough_blend = mix_scalar_socket(
                nodes,
                links,
                "Microdetail Roughness Blend",
                (900, -1580),
                dr1,
                dr2,
                mdr_scale,
            )

        if micro_rough_blend is not None:
            lo, hi = values["rough_bias"]
            biased = mix_scalar_socket(
                nodes,
                links,
                "Detail Roughness Bias",
                (1080, -1580),
                lo,
                hi,
                micro_rough_blend,
            )
            rough_detail = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                rough,
                biased,
                name="Roughness × Detail",
                location=(1260, -1580),
            )
            rough = mix_scalar_socket(
                nodes,
                links,
                "Final Roughness",
                (1440, -1580),
                rough,
                rough_detail,
                detail_mask,
            )
        if hasattr(rough, "is_output"):
            links.new(rough, find_input(principled, "Roughness"))
        else:
            find_input(principled, "Roughness").default_value = float(rough)

        if normal_tangent is not None:
            encoded = encode_tangent_normal(
                tree, normal_tangent, location=(1300, -760), label="Skin Normal Encode"
            )
            normal = tangent_to_normal_map(
                tree, encoded, location=(1500, -760), label="Skin Normal"
            )
            links.new(normal, find_input(principled, "Normal"))

        # Cavity modifies albedo before tinting.
        albedo_tex = create_relative_texture_node(
            self, tree, data, "Albedo", uv, (-1900, 700)
        )
        albedo = albedo_tex.outputs["Color"] if albedo_tex is not None else _WHITE
        if micro_rough_blend is not None:
            if detail_tex is not None:
                detail_split = separate_color_node(
                    nodes,
                    links,
                    detail_tex.outputs["Color"],
                    "Detail Source RG",
                    (-1400, -1060),
                )
                detail_x2 = shader_nodes.math(
                    nodes,
                    links,
                    "MULTIPLY",
                    detail_split.outputs["Red"],
                    2.0,
                    name="Detail Source X x2",
                    location=(-1220, -1020),
                )
                detail_source_x = shader_nodes.math(
                    nodes,
                    links,
                    "SUBTRACT",
                    detail_x2,
                    1.0,
                    name="Detail Source X",
                    location=(-1040, -1020),
                )
            mask_sq = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                detail_mask,
                detail_mask,
                name="Detail Mask²",
                location=(900, -1840),
            )
            cavity = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                micro_rough_blend,
                mask_sq,
                name="Cavity Microdetail",
                location=(1080, -1840),
            )
            cavity = shader_nodes.math(
                nodes,
                links,
                "ADD",
                cavity,
                detail_source_x,
                name="Cavity + DetailNormal.x",
                location=(1260, -1840),
            )
            cavity = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                cavity,
                values["cavity"],
                name="Cavity Intensity",
                location=(1440, -1840),
            )
            cavity10 = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                cavity,
                10.0,
                name="Cavity ×10",
                location=(1620, -1840),
            )
            cavity_inv = smoothstep_socket(
                tree, cavity10, 0.15, 0.0, (900, -2020), "Cavity Inverted"
            )
            cavity_inv = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                cavity_inv,
                0.01,
                name="Cavity Inverted ×0.01",
                location=(1880, -2020),
            )
            subtract = mix_color_socket(
                nodes,
                links,
                "Albedo - Cavity",
                albedo,
                (-1.0, -1.0, -1.0, 1.0),
                cavity,
                (-1320, 700),
                blend_type="ADD",
            )
            cavity_corrected = mix_color_socket(
                nodes,
                links,
                "Cavity Corrected",
                subtract,
                _WHITE,
                cavity_inv,
                (-1100, 700),
                blend_type="ADD",
            )
            albedo = mix_color_socket(
                nodes,
                links,
                "Cavity Mask",
                albedo,
                cavity_corrected,
                detail_mask,
                (-880, 700),
            )

        tint_color = values["tint_color"]
        tint_scale = values["tint_scale"]
        tint_factor = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            abs(tint_scale),
            tint_mask,
            name="Tint Scale × Mask",
            location=(-620, 620),
        )
        blend_type = "MULTIPLY" if tint_scale >= 0.0 else "OVERLAY"
        tinted_full = mix_color_socket(
            nodes,
            links,
            f"Tint {blend_type.title()}",
            albedo,
            tint_color,
            1.0,
            (-620, 760),
            blend_type=blend_type,
            clamp=True,
        )
        tinted = mix_color_socket(
            nodes, links, "Tint Mask", albedo, tinted_full, tint_factor, (-380, 700)
        )

        secondary_tinted = None
        sec_factor = None
        secondary_tex = (
            None
            if is_blendable
            else create_relative_texture_node(
                self, tree, data, "SecondaryAlbedo", uv, (-620, 980)
            )
        )
        if secondary_tex is not None:
            secondary = secondary_tex.outputs["Color"]
            secondary_tint_factor = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                tint_factor,
                values["secondary_tint"],
                name="Secondary Tint Mask",
                location=(-380, 1020),
            )
            secondary_mul = mix_color_socket(
                nodes,
                links,
                "Secondary × Tint",
                secondary,
                tinted,
                1.0,
                (-160, 1040),
                blend_type="MULTIPLY",
            )
            secondary_tinted = mix_color_socket(
                nodes,
                links,
                "Secondary Tint Influence",
                secondary,
                secondary_mul,
                secondary_tint_factor,
                (60, 1020),
            )
            sec_factor = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                secondary_tex.outputs["Alpha"],
                values["secondary_influence"],
                name="Secondary Influence × Alpha",
                location=(280, 980),
            )

        color = tinted
        bloodflow_tex = create_relative_texture_node(
            self, tree, data, "Bloodflow", uv, (-620, 1240), non_color=True
        )
        if bloodflow_tex is not None and wrinkle_textures_present:
            blood_mask = separate_color_node(
                tree.nodes,
                tree.links,
                bloodflow_tex.outputs["Color"],
                "Bloodflow Mask",
                (-380, 1240),
            )
            blood_color = values["blood_color"]
            blood_target = mix_color_socket(
                nodes,
                links,
                "Blood Influenced Tint",
                tinted,
                blood_color,
                1.0,
                (-120, 1320),
                blend_type="ADD",
                clamp=True,
            )
            squash_sq = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                squash_scale,
                squash_scale,
                name="Bloodflow Squash²",
                location=(-120, 1200),
            )
            squash_cube = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                squash_sq,
                squash_scale,
                name="Bloodflow Squash³",
                location=(60, 1200),
            )
            stretch_sq = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                stretch_scale,
                stretch_scale,
                name="Bloodflow Stretch²",
                location=(-120, 1120),
            )
            stretch_cube = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                stretch_sq,
                stretch_scale,
                name="Bloodflow Stretch³",
                location=(60, 1120),
            )
            squash_blood = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                blood_mask.outputs["Red"],
                squash_cube,
                name="Bloodflow Squash Mask",
                location=(240, 1200),
            )
            stretch_blood = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                blood_mask.outputs["Green"],
                stretch_cube,
                name="Bloodflow Stretch Mask",
                location=(240, 1120),
            )
            color = mix_color_socket(
                nodes,
                links,
                "Squash Bloodflow",
                tinted,
                blood_target,
                squash_blood,
                (460, 1280),
                clamp=True,
            )
            color = mix_color_socket(
                nodes,
                links,
                "Stretch Bloodflow",
                color,
                blood_target,
                stretch_blood,
                (680, 1280),
                clamp=True,
            )

        if secondary_tinted is not None and sec_factor is not None:
            color = mix_color_socket(
                nodes,
                links,
                "Final Skin Color",
                color,
                secondary_tinted,
                sec_factor,
                (920, 1020),
            )
        links.new(color, find_input(principled, "Base Color"))

        emissive_ev = values["emissive_ev"]
        if emissive_ev != 0.0:
            mask_tex = (
                None
                if is_blendable
                else create_relative_texture_node(
                    self, tree, data, "EmissiveMask", uv, (880, 580), non_color=True
                )
            )
            emissive_factor = max(0.0, ev_to_linear(emissive_ev) - 1.0)
            if mask_tex is not None:
                mask_split = separate_color_node(
                    tree.nodes,
                    tree.links,
                    mask_tex.outputs["Color"],
                    "Emissive Mask",
                    (1100, 580),
                )
                emissive_factor = shader_nodes.math(
                    nodes,
                    links,
                    "MULTIPLY",
                    mask_split.outputs["Red"],
                    max(0.0, ev_to_linear(emissive_ev) - 1.0),
                    name="Skin EmissiveEV",
                    location=(1300, 580),
                )
            emission = find_input(principled, "Emission Color") or find_input(
                principled, "Emission"
            )
            strength = find_input(principled, "Emission Strength")
            if emission is not None:
                links.new(color, emission)
            if strength is not None:
                if hasattr(emissive_factor, "is_output"):
                    links.new(emissive_factor, strength)
                else:
                    strength.default_value = max(0.0, float(emissive_factor))

        subsurface = find_input(principled, "Subsurface Weight")
        if subsurface is not None:
            subsurface.default_value = 1.0
        scale = find_input(principled, "Subsurface Scale")
        if scale is not None:
            scale.default_value = 0.005
        Mat.diffuse_color = (*tint_color[:3], 1.0)
