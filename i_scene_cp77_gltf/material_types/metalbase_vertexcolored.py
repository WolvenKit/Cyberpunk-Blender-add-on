from ..materials.blender.nodes import create_node
from .bundles import scalar_lerp_socket
from .metalbase_common import (
    COLUMN_ADJUST,
    COLUMN_COMBINE,
    COLUMN_TEXTURE,
    MetalBaseCore,
)

_METALBASE_VERTEX_RM_ATTRIBUTE = "cp77_metalbase_vertex_rm"


class MetalBaseVertexColored(MetalBaseCore):
    def create(self, Data, Mat):
        tree = Mat.node_tree
        bsdf, _ = self._bsdf(tree)

        vertex = create_node(
            tree.nodes,
            "ShaderNodeVertexColor",
            (COLUMN_TEXTURE, 620),
            label="VertexColor",
        )
        vertex.layer_name = "Color"
        decoded = create_node(
            tree.nodes,
            "ShaderNodeAttribute",
            (COLUMN_TEXTURE, 380),
            label="Decoded Vertex Roughness / Metalness",
        )
        decoded.attribute_name = _METALBASE_VERTEX_RM_ATTRIBUTE
        channels = create_node(
            tree.nodes,
            "ShaderNodeSeparateXYZ",
            (COLUMN_ADJUST, 380),
            label="Decoded RM",
        )
        tree.links.new(decoded.outputs["Vector"], channels.inputs["Vector"])

        presence = channels.outputs["Z"]
        base = self._mix_color(
            tree,
            (COLUMN_COMBINE, 620),
            presence,
            (1.0, 1.0, 1.0, 1.0),
            vertex.outputs["Color"],
            label="Vertex Color Present",
        )
        tree.links.new(base, bsdf.inputs["Base Color"])

        roughness = scalar_lerp_socket(
            tree,
            1.0,
            channels.outputs["X"],
            presence,
            (COLUMN_COMBINE, 460),
            "Decoded Roughness",
        )
        metalness = scalar_lerp_socket(
            tree,
            0.0,
            channels.outputs["Y"],
            presence,
            (COLUMN_COMBINE, 300),
            "Decoded Metalness",
        )
        tree.links.new(roughness, bsdf.inputs["Roughness"])
        tree.links.new(metalness, bsdf.inputs["Metallic"])

        self._geometry_normal(tree, bsdf)
        bsdf.inputs["Emission Strength"].default_value = 0.0
        bsdf.inputs["Alpha"].default_value = 1.0

        Mat["cp77_metal_base_vertex_rm_required"] = True
