from ..blender import shader_nodes
from ..materials.blender.nodes import create_node
from .decal_math import ev_to_linear
from .graph import set_transparent
from .mat_common import param_float, param_vector
from .metalbase_common import (
    COLUMN_ADJUST,
    COLUMN_COMBINE,
    COLUMN_OUTPUT,
    COLUMN_TEXTURE,
    MetalBaseCore,
)

_ALPHA_FLOOR = 1.0e-4


class MetalBaseUIQ303(MetalBaseCore):
    texture_defaults = {"UIRenderTexture": r"base\fx\textures\devices\holo_ad_guns.xbm"}
    texture_part_uv_default = (1.0, 1.0, 0.0, 0.0)

    def _panel_uv(self, CurMat, data):
        part = param_vector(data, "TexturePartUV", self.texture_part_uv_default)
        width = part[2] - part[0]
        height = part[3] - part[1]
        if abs(width) <= 1.0e-6:
            width = 1.0
        if abs(height) <= 1.0e-6:
            height = 1.0
        return self._uv_scale_offset(
            CurMat, (width, height), (part[0], part[1]), (-1900, 400), "TexturePartUV"
        ).outputs["Vector"]

    def create(self, Data, Mat):
        data = Data if isinstance(Data, dict) else {}
        Mat.use_nodes = True
        CurMat = Mat.node_tree
        nodes = CurMat.nodes
        links = CurMat.links
        nodes.clear()

        output = create_node(
            nodes, "ShaderNodeOutputMaterial", (COLUMN_OUTPUT + 600, 0), hide=False
        )
        emission = create_node(
            nodes, "ShaderNodeEmission", (COLUMN_OUTPUT + 340, 120), label="Panel"
        )
        transparent = create_node(
            nodes, "ShaderNodeBsdfTransparent", (COLUMN_OUTPUT + 340, -80)
        )
        mix = create_node(
            nodes,
            "ShaderNodeMixShader",
            (COLUMN_OUTPUT + 480, 0),
            label="Panel over Background",
        )
        links.new(transparent.outputs["BSDF"], mix.inputs["Shader"])
        links.new(
            emission.outputs["Emission"],
            shader_nodes.socket_by_identifier(mix.inputs, "Shader_001"),
        )
        links.new(mix.outputs["Shader"], output.inputs["Surface"])

        uv = self._panel_uv(CurMat, data)
        panel = self._texture(
            CurMat, data, "UIRenderTexture", (COLUMN_TEXTURE, 400), uv
        )
        if panel is not None:
            panel.interpolation = "Closest"
            links.new(panel.outputs["Color"], emission.inputs["Color"])
            alpha_source = panel.outputs["Alpha"]
        else:
            emission.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1.0)
            alpha_source = None

        ev = max(0.0, param_float(data, "EmissiveEV", 15.0))

        alpha = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            label="Alpha",
            location=(COLUMN_ADJUST, 120),
            use_clamp=True,
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(alpha.inputs, "Value_001").default_value = 1.0
        if alpha_source is not None:
            links.new(alpha_source, alpha.inputs["Value"])
        else:
            alpha.inputs["Value"].default_value = 1.0
        links.new(alpha.outputs["Value"], mix.inputs["Factor"])

        floored = shader_nodes.math(
            nodes,
            links,
            "MAXIMUM",
            label="max(Alpha, eps)",
            location=(COLUMN_COMBINE, 40),
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(
            floored.inputs, "Value_001"
        ).default_value = _ALPHA_FLOOR
        links.new(alpha.outputs["Value"], floored.inputs["Value"])

        # The Mix Shader scales the emission by alpha; dividing by alpha keeps the panel at full strength.
        compensation = shader_nodes.math(
            nodes,
            links,
            "DIVIDE",
            label="Premultiplied",
            location=(COLUMN_COMBINE + 200, 40),
            hide=True,
        ).node
        compensation.inputs["Value"].default_value = 1.0
        links.new(
            floored.outputs["Value"],
            shader_nodes.socket_by_identifier(compensation.inputs, "Value_001"),
        )

        strength = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            label="Emission Strength",
            location=(COLUMN_OUTPUT + 180, 40),
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(
            strength.inputs, "Value_001"
        ).default_value = max(0.0, ev_to_linear(ev) - 1.0)
        links.new(compensation.outputs["Value"], strength.inputs["Value"])
        links.new(strength.outputs["Value"], emission.inputs["Strength"])

        set_transparent(Mat)
        Mat.use_backface_culling = False
