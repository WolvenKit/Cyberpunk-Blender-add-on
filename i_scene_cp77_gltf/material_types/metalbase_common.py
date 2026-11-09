from ..bartmoss.scalar import clamp01
from ..blender import shader_nodes
from ..blender.shader_nodes import assign_socket, mix_color_sockets
from ..materials.blender.images import image_is_placeholder
from ..materials.blender.nodes import (
    CreateCullBackfaceGroup,
    CreateShaderNodeValue,
    bsdf_socket_names,
    create_node,
)
from .bundles import (
    alpha_mask_socket,
    emissive_scale_bundle,
)
from .mat_common import (
    MaterialTypeBase,
    create_scene_time_value,
    lookup_param,
    param_color,
    param_float,
    param_vector,
    unwrap_param,
)
from .normal_math import (
    combine_cp77_tangent_normals,
    decode_cp77_normal,
    encode_tangent_normal,
    tangent_to_normal_map,
)


def scale_components(data, key, default=(1.0, 1.0, 1.0, 1.0)):
    """Read a colour-scale parameter without conflating PT_Color and PT_Vector"""
    raw = unwrap_param(lookup_param(data, key, None))
    if isinstance(raw, dict) and any(axis in raw for axis in ("X", "Y", "Z", "W")):
        return param_vector(data, key, default)
    if isinstance(raw, (list, tuple)):
        return tuple(
            float(raw[index]) if index < len(raw) else float(default[index])
            for index in range(4)
        )
    if raw is None:
        return tuple(float(component) for component in default)
    return param_color(data, key, default)


COLUMN_TEXTURE = -1500
COLUMN_ADJUST = -1150
COLUMN_COMBINE = -820
COLUMN_OUTPUT = -420


class MetalBaseCore(MaterialTypeBase):
    texture_defaults = {
        "BaseColor": r"engine\textures\editor\grey.xbm",
        "Metalness": r"engine\textures\editor\black.xbm",
        "Roughness": r"engine\textures\editor\white.xbm",
        "Normal": r"engine\textures\editor\normal.xbm",
        "Emissive": r"engine\textures\editor\black.xbm",
    }
    colour_defaults = {
        "BaseColorScale": (1.0, 1.0, 1.0, 0.0),
        "EmissiveColor": (0.0, 0.0, 0.0, 1.0),
    }
    layer_tile_default = 1.0
    normal_strength_default = 1.0
    alpha_threshold_default = 1.0
    metalness_scale_default = 1.0
    metalness_bias_default = 0.0
    roughness_scale_default = 1.0
    roughness_bias_default = 0.0
    uv_panning_speed_x_default = 0.0
    uv_panning_speed_y_default = 0.0
    normal_strength_param = "NormalStrength"
    emissive_lift_param = "EmissiveLift"

    def __init__(self, BasePath, image_format, ProjPath, enableMask=False):
        super().__init__(BasePath, image_format, ProjPath)
        self.enableMask = enableMask

    def _mix_color(
        self,
        CurMat,
        location,
        factor,
        first,
        second,
        *,
        blend_type="MIX",
        label=None,
        clamp_result=False,
    ):
        """Colour mix node, wired and returned as its result socket"""
        node = create_node(CurMat.nodes, "ShaderNodeMix", location, label=label)
        node.data_type = "RGBA"
        node.blend_type = blend_type
        node.clamp_factor = False
        node.clamp_result = clamp_result
        factor_input, first_input, second_input, result = mix_color_sockets(node)
        assign_socket(CurMat.links, factor, factor_input)
        assign_socket(CurMat.links, first, first_input)
        assign_socket(CurMat.links, second, second_input)
        return result

    def _bsdf(self, CurMat):
        return shader_nodes.principled_bsdf(CurMat.nodes), bsdf_socket_names()

    def _uv_source(self, CurMat, data, *, tile_key="LayerTile", location=(-2100, 400)):
        tile = param_float(data, tile_key, self.layer_tile_default) if tile_key else 1.0
        if abs(tile - 1.0) <= 1.0e-6:
            return None
        coord = create_node(
            CurMat.nodes, "ShaderNodeTexCoord", (location[0] - 200, location[1])
        )
        mapping = create_node(
            CurMat.nodes, "ShaderNodeMapping", location, label=tile_key
        )
        mapping.inputs["Scale"].default_value = (tile, tile, 1.0)
        CurMat.links.new(coord.outputs["UV"], mapping.inputs["Vector"])
        return mapping.outputs["Vector"]

    def _uv_scale_offset(self, CurMat, scale, offset, location, label):
        """Explicit UV mapping node"""
        coord = create_node(
            CurMat.nodes, "ShaderNodeTexCoord", (location[0] - 200, location[1])
        )
        mapping = create_node(CurMat.nodes, "ShaderNodeMapping", location, label=label)
        CurMat.links.new(coord.outputs["UV"], mapping.inputs["Vector"])
        if isinstance(scale, tuple):
            mapping.inputs["Scale"].default_value = (scale[0], scale[1], 1.0)
        elif scale is not None:
            CurMat.links.new(scale, mapping.inputs["Scale"])
        if isinstance(offset, tuple):
            mapping.inputs["Location"].default_value = (offset[0], offset[1], 0.0)
        elif offset is not None:
            CurMat.links.new(offset, mapping.inputs["Location"])
        return mapping

    def _time(self, CurMat, location, label="Time"):
        return create_scene_time_value(CurMat, location[0], location[1], label=label)

    def _texture(
        self, CurMat, data, key, location, uv=None, *, non_color=False, label=None
    ):
        path = self._texture_path(data, key)
        if not path:
            return None
        image = self._image_from_rel_path(path, is_normal=non_color)
        node = create_node(
            CurMat.nodes,
            "ShaderNodeTexImage",
            location,
            label=label or key,
            image=image,
        )
        if uv is not None:
            CurMat.links.new(uv, node.inputs["Vector"])
        return node

    def _colour_scale_socket(self, CurMat, data, key, location):
        """Colour-scale constant as a socket, gamma-decoded only when required"""
        components = scale_components(
            data, key, self.colour_defaults.get(key, (1.0, 1.0, 1.0, 1.0))
        )
        node = create_node(CurMat.nodes, "ShaderNodeRGB", location, label=key)
        node.outputs["Color"].default_value = components
        return node.outputs["Color"], components

    def _scaled_base_color(
        self, CurMat, data, base_node, y=520, *, clamp=True, scale_key="BaseColorScale"
    ):
        """BaseColor.rgb multiplied by the material colour scale"""
        scale_socket, components = self._colour_scale_socket(
            CurMat, data, scale_key, (COLUMN_TEXTURE, y - 120)
        )
        scaled = self._mix_color(
            CurMat,
            (COLUMN_COMBINE, y),
            1.0,
            base_node.outputs["Color"]
            if base_node is not None
            else (1.0, 1.0, 1.0, 1.0),
            scale_socket,
            blend_type="MULTIPLY",
            label="ScaledBaseColor",
            clamp_result=clamp,
        )
        return scaled, components

    def _pbr_channel(self, CurMat, data, key, target, uv, y, *, clamp=True):
        node = self._texture(CurMat, data, key, (COLUMN_TEXTURE, y), uv, non_color=True)
        if node is None:
            scalar = unwrap_param(lookup_param(data, key, None))
            if isinstance(scalar, (int, float)) and not isinstance(scalar, bool):
                target.default_value = clamp01(float(scalar))
            return None

        adjust = shader_nodes.math(
            CurMat.nodes,
            CurMat.links,
            "MULTIPLY_ADD",
            label=f"{key}Scale / {key}Bias",
            location=(COLUMN_ADJUST, y),
            hide=True,
        ).node
        prefix = key.lower()
        shader_nodes.socket_by_identifier(
            adjust.inputs, "Value_001"
        ).default_value = param_float(
            data,
            f"{key}Scale",
            getattr(self, f"{prefix}_scale_default", 1.0),
        )
        shader_nodes.socket_by_identifier(
            adjust.inputs, "Value_002"
        ).default_value = param_float(
            data,
            f"{key}Bias",
            getattr(self, f"{prefix}_bias_default", 0.0),
        )
        adjust.use_clamp = clamp
        channels = create_node(
            CurMat.nodes,
            "ShaderNodeSeparateColor",
            (COLUMN_ADJUST - 160, y),
            label=f"{key}.r",
        )
        CurMat.links.new(node.outputs["Color"], channels.inputs["Color"])
        CurMat.links.new(channels.outputs["Red"], adjust.inputs["Value"])
        CurMat.links.new(adjust.outputs["Value"], target)
        return adjust.outputs["Value"]

    def _packed_pbr(
        self, CurMat, data, key, uv, rough_target, metal_target, y, *, clamp=True
    ):
        """Single texture carrying roughness in R and metalness in G"""
        node = self._texture(CurMat, data, key, (COLUMN_TEXTURE, y), uv, non_color=True)
        if node is None:
            return None, None
        channels = create_node(
            CurMat.nodes,
            "ShaderNodeSeparateColor",
            (COLUMN_ADJUST - 150, y),
            label=f"{key} R=rough G=metal",
        )
        CurMat.links.new(node.outputs["Color"], channels.inputs["Color"])
        sources = []
        for (
            source,
            target,
            scale_key,
            bias_key,
            scale_default,
            bias_default,
            offset,
        ) in (
            (
                channels.outputs["Red"],
                rough_target,
                "RoughnessScale",
                "RoughnessBias",
                self.roughness_scale_default,
                self.roughness_bias_default,
                0,
            ),
            (
                channels.outputs["Green"],
                metal_target,
                "MetalnessScale",
                "MetalnessBias",
                self.metalness_scale_default,
                self.metalness_bias_default,
                120,
            ),
        ):
            adjust = shader_nodes.math(
                CurMat.nodes,
                CurMat.links,
                "MULTIPLY_ADD",
                label=f"{scale_key} / {bias_key}",
                location=(COLUMN_ADJUST + 120, y + offset),
                hide=True,
            ).node
            shader_nodes.socket_by_identifier(
                adjust.inputs, "Value_001"
            ).default_value = param_float(data, scale_key, scale_default)
            shader_nodes.socket_by_identifier(
                adjust.inputs, "Value_002"
            ).default_value = param_float(data, bias_key, bias_default)
            adjust.use_clamp = clamp
            CurMat.links.new(source, adjust.inputs["Value"])
            CurMat.links.new(adjust.outputs["Value"], target)
            sources.append(adjust.outputs["Value"])
        return tuple(sources)

    def _normal(self, CurMat, data, bsdf, uv, *, detail_uv=None, y=-260):
        path = self._texture_path(data, "Normal")
        if not path:
            return None
        base = self._texture(
            CurMat,
            data,
            "Normal",
            (COLUMN_TEXTURE, y),
            uv,
            non_color=True,
        )
        if base is None:
            return None
        strength = self.normal_strength_default
        if self.normal_strength_param:
            strength = param_float(data, self.normal_strength_param, strength)
        base_decode = decode_cp77_normal(
            CurMat,
            base.outputs["Color"],
            strength=max(0.0, strength),
            location=(COLUMN_ADJUST, y),
            label="Normal DirectX Decode",
        )
        tangent = base_decode.outputs["Tangent"]
        encoded = base_decode.outputs["Color"]

        detail_path = self._texture_path(data, "DetailNormal")
        if detail_path:
            detail = self._texture(
                CurMat,
                data,
                "DetailNormal",
                (COLUMN_TEXTURE, y - 240),
                detail_uv,
                non_color=True,
            )
            if detail is not None:
                detail_decode = decode_cp77_normal(
                    CurMat,
                    detail.outputs["Color"],
                    strength=1.0,
                    location=(COLUMN_ADJUST, y - 240),
                    label="DetailNormal DirectX Decode",
                )
                tangent = combine_cp77_tangent_normals(
                    CurMat,
                    tangent,
                    detail_decode.outputs["Tangent"],
                    location=(COLUMN_COMBINE, y - 100),
                    label="MetalBase Detail Normal",
                )

                encoded = encode_tangent_normal(
                    CurMat,
                    tangent,
                    location=(COLUMN_OUTPUT - 220, y - 100),
                    label="MetalBase Normal Encode",
                )
        normal = tangent_to_normal_map(
            CurMat,
            encoded,
            location=(COLUMN_OUTPUT, y - 100),
            label="MetalBase Normal",
        )
        CurMat.links.new(normal, bsdf.inputs["Normal"])
        return normal

    def _geometry_normal(self, CurMat, bsdf, location=(COLUMN_OUTPUT, -260)):
        geometry = create_node(
            CurMat.nodes, "ShaderNodeNewGeometry", location, label="World Normal"
        )
        CurMat.links.new(geometry.outputs["Normal"], bsdf.inputs["Normal"])
        return geometry

    def _emissive_mask(self, CurMat, data, uv=None, y=-560, key="Emissive"):
        """Red channel of the emissive mask. Deliberately untiled by default"""
        path = self._texture_path(data, key)
        if not path:
            return None
        image = self._image_from_rel_path(path, is_normal=True)
        if image is None or image_is_placeholder(image):
            return None
        node = create_node(
            CurMat.nodes,
            "ShaderNodeTexImage",
            (COLUMN_TEXTURE, y),
            label=f"{key} Mask",
            image=image,
        )
        if uv is not None:
            CurMat.links.new(uv, node.inputs["Vector"])
        channels = create_node(
            CurMat.nodes,
            "ShaderNodeSeparateColor",
            (COLUMN_ADJUST, y),
            label=f"{key}.r",
        )
        CurMat.links.new(node.outputs["Color"], channels.inputs["Color"])
        return channels.outputs["Red"]

    def _lift_mask(self, CurMat, data, mask, y=-640):
        if not self.emissive_lift_param:
            return mask
        lift = max(-1.0, min(1.0, param_float(data, self.emissive_lift_param, 0.0)))
        if lift == 0.0:
            return mask
        lifted = shader_nodes.math(
            CurMat.nodes,
            CurMat.links,
            "MULTIPLY_ADD",
            label="EmissiveLift",
            location=(COLUMN_COMBINE, y),
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(lifted.inputs, "Value_001").default_value = (
            1.0 - lift
        )
        shader_nodes.socket_by_identifier(
            lifted.inputs, "Value_002"
        ).default_value = lift
        lifted.use_clamp = True
        CurMat.links.new(mask, lifted.inputs["Value"])
        return lifted.outputs["Value"]

    def _emissive_tint(self, CurMat, data, base_socket, y=-760):
        colour = create_node(
            CurMat.nodes, "ShaderNodeRGB", (COLUMN_ADJUST, y), label="EmissiveColor"
        )
        colour.outputs["Color"].default_value = param_color(
            data,
            "EmissiveColor",
            self.colour_defaults.get("EmissiveColor", (0.0, 0.0, 0.0, 1.0)),
        )
        return self._mix_color(
            CurMat,
            (COLUMN_COMBINE, y),
            1.0,
            base_socket if base_socket is not None else (1.0, 1.0, 1.0, 1.0),
            colour.outputs["Color"],
            blend_type="MULTIPLY",
            label="Emissive Tint",
        )

    def _emissive_lerp(self, CurMat, mask, surface, tinted, y=520):
        return self._mix_color(
            CurMat,
            (COLUMN_OUTPUT, y),
            mask,
            surface,
            tinted,
            label="Emissive Colour Lerp",
        )

    def _ev_strength(self, CurMat, scale, ev, y=-640, label="Emissive Strength"):
        bundle = emissive_scale_bundle(
            CurMat,
            scale,
            ev,
            (COLUMN_OUTPUT - 320, y),
            label,
        )
        return bundle.outputs["Strength"]

    def _emissive_block(
        self, CurMat, data, bsdf, sockets, surface, base_socket, uv=None
    ):
        """Standard emissive branch. Returns the surface colour socket to use"""
        ev = max(0.0, param_float(data, "EmissiveEV", 0.0))
        mask = self._emissive_mask(CurMat, data, uv) if ev > 0.0 else None
        if mask is None:
            bsdf.inputs["Emission Strength"].default_value = 0.0
            return surface

        lifted = self._lift_mask(CurMat, data, mask)
        tinted = self._emissive_tint(CurMat, data, base_socket)
        surface = self._emissive_lerp(CurMat, lifted, surface, tinted)
        CurMat.links.new(surface, bsdf.inputs[sockets["Emission"]])
        CurMat.links.new(
            self._ev_strength(CurMat, lifted, ev), bsdf.inputs["Emission Strength"]
        )
        return surface

    def _alpha_mask(self, CurMat, data, bsdf, alpha_socket, _base_image, y=380):
        threshold_value = param_float(
            data, "AlphaThreshold", self.alpha_threshold_default
        )
        threshold = CreateShaderNodeValue(
            CurMat, threshold_value, COLUMN_TEXTURE, y, "AlphaThreshold"
        )
        toggle = create_node(
            CurMat.nodes, "ShaderNodeValue", (COLUMN_COMBINE, -180), label="EnableMask"
        )
        toggle.outputs["Value"].default_value = int(self.enableMask)
        alpha = alpha_mask_socket(
            CurMat,
            alpha_socket if alpha_socket is not None else 1.0,
            threshold.outputs["Value"],
            toggle.outputs["Value"],
            (COLUMN_COMBINE, y),
            dithered=bool(getattr(self, "dithered_alpha", False)),
        )
        cull = CreateCullBackfaceGroup(
            CurMat, x=COLUMN_OUTPUT, y=-60, name="Cull Backface"
        )
        CurMat.links.new(alpha, cull.inputs["Input"])
        CurMat.links.new(cull.outputs["Output"], bsdf.inputs["Alpha"])
        return cull

    def _multiplied_alpha(self, CurMat, sources, constant, location, label):
        """Product of several alpha sockets and an optional constant factor"""
        sockets = [s for s in sources if s is not None]
        if not sockets:
            return None
        current = sockets[0]
        for index, extra in enumerate(sockets[1:], start=1):
            node = shader_nodes.math(
                CurMat.nodes,
                CurMat.links,
                "MULTIPLY",
                label=label,
                location=(location[0], location[1] + index * 60),
                hide=True,
            ).node
            CurMat.links.new(current, node.inputs["Value"])
            CurMat.links.new(
                extra, shader_nodes.socket_by_identifier(node.inputs, "Value_001")
            )
            current = node.outputs["Value"]
        if constant is not None and abs(constant - 1.0) > 1.0e-6:
            node = shader_nodes.math(
                CurMat.nodes,
                CurMat.links,
                "MULTIPLY",
                label=f"{label} scale",
                location=(location[0], location[1] - 60),
                hide=True,
            ).node
            shader_nodes.socket_by_identifier(
                node.inputs, "Value_001"
            ).default_value = constant
            CurMat.links.new(current, node.inputs["Value"])
            current = node.outputs["Value"]
        return current


def uv_panning_offset(
    core, CurMat, data, location, x_key="UvPanningSpeedX", y_key="UvPanningSpeedY"
):
    """Scene-time driven UV translation shared by the panning variants"""
    speed_x = param_float(data, x_key, core.uv_panning_speed_x_default)
    speed_y = param_float(data, y_key, core.uv_panning_speed_y_default)
    if speed_x == 0.0 and speed_y == 0.0:
        return None
    time = core._time(
        CurMat, (location[0] - 200, location[1] - 120), label="UV Panning Time"
    )
    offset = shader_nodes.vector_math(
        CurMat.nodes,
        CurMat.links,
        "SCALE",
        label="UV Panning Offset",
        location=location,
        hide=True,
    ).node
    offset.inputs["Vector"].default_value = (speed_x, speed_y, 0.0)
    CurMat.links.new(time.outputs["Value"], offset.inputs["Scale"])
    return offset.outputs["Vector"]


def tiling_and_scrolling(core, CurMat, data, key, location, label):
    """Vector4 parameter carrying XY tiling and ZW scroll velocity"""
    vector = param_vector(data, key, (1.0, 1.0, 0.0, 0.0))
    time = core._time(
        CurMat, (location[0] - 400, location[1] - 120), label=f"{label} Time"
    )
    offset = shader_nodes.vector_math(
        CurMat.nodes,
        CurMat.links,
        "SCALE",
        label=f"{label} Scroll",
        location=(location[0] - 360, location[1] - 120),
        hide=True,
    ).node
    offset.inputs["Vector"].default_value = (vector[2], vector[3], 0.0)
    CurMat.links.new(time.outputs["Value"], offset.inputs["Scale"])
    return core._uv_scale_offset(
        CurMat, (vector[0], vector[1]), offset.outputs["Vector"], location, label
    )
