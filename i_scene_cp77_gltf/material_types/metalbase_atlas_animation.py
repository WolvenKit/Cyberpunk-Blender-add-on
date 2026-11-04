from ..blender import shader_nodes
from ..materials.blender.nodes import create_node
from .mat_common import param_float
from .metalbase_common import COLUMN_TEXTURE, MetalBaseCore


class MetalBaseAtlasAnimation(MetalBaseCore):
    normal_strength_param = None
    texture_defaults = {
        **MetalBaseCore.texture_defaults,
        "BaseColor": r"base\fx\_textures\animals\cockroach_2x1_anim_d.xbm",
        "Metalness": r"base\materials\placeholder\black.xbm",
        "Roughness": r"base\fx\_textures\animals\cockroach_2x1_anim_r.xbm",
        "Normal": r"base\fx\_textures\animals\cockroach_2x1_anim_n.xbm",
    }
    colour_defaults = {
        **MetalBaseCore.colour_defaults,
        "BaseColorScale": (0.6, 0.6, 0.6, 1.0),
    }
    alpha_threshold_default = 0.0299999993
    metalness_scale_default = 0.0
    roughness_scale_default = 0.200000003
    roughness_bias_default = 0.200000003

    def _frame_uv(self, CurMat, data):
        columns = max(1.0, param_float(data, "SubUVWidth", 2.0))
        rows = max(1.0, param_float(data, "SubUVHeight", 1.0))
        speed = param_float(data, "LoopedAnimationSpeed", 10.0)
        cells = columns * rows

        mapping = self._uv_scale_offset(
            CurMat, (1.0 / columns, 1.0 / rows), None, (-1900, 400), "SubUV Cell"
        )
        if cells <= 1.0:
            return mapping.outputs["Vector"]
        if speed == 0.0:
            mapping.inputs["Location"].default_value = (0.0, 0.0, 0.0)
            return mapping.outputs["Vector"]

        time = self._time(CurMat, (-2500, 240), label="Flipbook Time")
        frame = shader_nodes.math(
            CurMat.nodes,
            CurMat.links,
            "WRAP",
            label="Frame Index",
            location=(-2300, 240),
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(
            frame.inputs, "Value_001"
        ).default_value = cells
        shader_nodes.socket_by_identifier(frame.inputs, "Value_002").default_value = 0.0
        scaled_time = shader_nodes.math(
            CurMat.nodes,
            CurMat.links,
            "MULTIPLY",
            label="time x speed",
            location=(-2400, 180),
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(
            scaled_time.inputs, "Value_001"
        ).default_value = speed
        CurMat.links.new(time.outputs["Value"], scaled_time.inputs["Value"])
        CurMat.links.new(scaled_time.outputs["Value"], frame.inputs["Value"])

        floored = shader_nodes.math(
            CurMat.nodes,
            CurMat.links,
            "FLOOR",
            label="Cell",
            location=(-2200, 240),
            hide=True,
        ).node
        CurMat.links.new(frame.outputs["Value"], floored.inputs["Value"])

        # Frame addressing uses the floored frame index divided by atlas width directly.
        # The texture sampler owns repeat behavior; the UV math must not pre-wrap the column.
        divided = shader_nodes.math(
            CurMat.nodes,
            CurMat.links,
            "DIVIDE",
            label="Row Index",
            location=(-2200, 180),
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(
            divided.inputs, "Value_001"
        ).default_value = columns
        CurMat.links.new(floored.outputs["Value"], divided.inputs["Value"])
        row = shader_nodes.math(
            CurMat.nodes,
            CurMat.links,
            "FLOOR",
            label="Cell Row",
            location=(-2100, 180),
            hide=True,
        ).node
        CurMat.links.new(divided.outputs["Value"], row.inputs["Value"])

        offset = create_node(
            CurMat.nodes, "ShaderNodeCombineXYZ", (-2000, 240), label="Cell Offset"
        )
        row_uv = shader_nodes.math(
            CurMat.nodes,
            CurMat.links,
            "MULTIPLY",
            label="Row UV",
            location=(-2050, 180),
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(row_uv.inputs, "Value_001").default_value = (
            -1.0 / rows
        )
        CurMat.links.new(row.outputs["Value"], row_uv.inputs["Value"])
        CurMat.links.new(divided.outputs["Value"], offset.inputs["X"])
        CurMat.links.new(row_uv.outputs["Value"], offset.inputs["Y"])
        CurMat.links.new(offset.outputs["Vector"], mapping.inputs["Location"])
        return mapping.outputs["Vector"]

    def create(self, Data, Mat):
        data = Data if isinstance(Data, dict) else {}
        CurMat = Mat.node_tree
        bsdf, _sockets = self._bsdf(CurMat)

        uv = self._frame_uv(CurMat, data)
        base = self._texture(CurMat, data, "BaseColor", (COLUMN_TEXTURE, 640), uv)
        surface, _scale = self._scaled_base_color(CurMat, data, base, clamp=False)

        self._pbr_channel(
            CurMat, data, "Metalness", bsdf.inputs["Metallic"], uv, 260, clamp=False
        )
        self._pbr_channel(
            CurMat, data, "Roughness", bsdf.inputs["Roughness"], uv, 80, clamp=False
        )
        self._normal(CurMat, data, bsdf, uv)

        bsdf.inputs["Emission Strength"].default_value = 0.0
        CurMat.links.new(surface, bsdf.inputs["Base Color"])
        self._alpha_mask(
            CurMat,
            data,
            bsdf,
            base.outputs["Alpha"] if base is not None else None,
            base.image if base is not None else None,
        )
