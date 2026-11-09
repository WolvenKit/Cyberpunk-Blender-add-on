from ..blender import shader_nodes
from .graph import grid_location
from .mat_common import (
    MaterialTypeBase,
    new_labeled_node,
    param_color,
    param_texture_path,
)
from .overlay_common import (
    additive_surface,
    combine_vector,
    control,
    split_vector,
)

from .overlay_common import material_cache_identity as material_cache_identity


class HUDUIDot(MaterialTypeBase):
    """Build a mirrored texture-red overlay with independent tint and background coverage"""

    def create(self, Data, Mat):
        data = Data if isinstance(Data, dict) else {}
        Mat.use_nodes = True
        tree = Mat.node_tree
        tree.nodes.clear()
        tiling = control(tree, data, "TillingX", 1.0)
        multiplier = control(tree, data, "ColorMultiplier", 1.0)
        additive = control(tree, data, "AdditiveAlphaBlend", 0.0)
        tint = param_color(data, "Color", (4 / 255, 1.0, 193 / 255, 1.0))
        color = new_labeled_node(tree.nodes, "ShaderNodeRGB", "Color", (-1200, 500))
        color.outputs["Color"].default_value = tint
        tint_alpha = control(tree, {"Color.a": tint[3]}, "Color.a", 1.0)
        uv = new_labeled_node(
            tree.nodes, "ShaderNodeTexCoord", "Overlay Coordinates", (-1200, 800)
        )
        scaled = shader_nodes.vector_math(
            tree.nodes,
            tree.links,
            "SCALE",
            uv.outputs["UV"],
            scale=tiling,
            name="Dot Tiling",
            location=grid_location(tree, (200, 160)),
        )
        components = split_vector(tree, "Dot Coordinates", scaled)
        mirrored = [
            shader_nodes.math(
                tree.nodes,
                tree.links,
                "PINGPONG",
                components[axis],
                1.0,
                name="Mirror " + axis,
                location=grid_location(tree, (200, 160)),
            )
            for axis in "XY"
        ]
        sample_uv = combine_vector(tree, "Dot Sample UV", *mirrored)
        path = (
            param_texture_path(data, "Diffuse")
            or r"base\fx\_textures\masks\shapes\fx_nade_area.xbm"
        )
        sample = self._relative_texture_node(
            tree.nodes, path, "Diffuse", (-700, 700), extension="EXTEND"
        )
        tree.links.new(sample_uv, sample.inputs["Vector"])
        red = split_vector(tree, "Diffuse Channels", sample.outputs["Color"])["X"]
        intensity = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            red,
            multiplier,
            name="Dot Intensity",
            location=grid_location(tree, (200, 160)),
        )
        final_color = shader_nodes.vector_math(
            tree.nodes,
            tree.links,
            "SCALE",
            color.outputs["Color"],
            scale=intensity,
            name="Dot Color",
            location=grid_location(tree, (200, 160)),
        )
        coverage = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            intensity,
            tint_alpha,
            name="Dot Coverage",
            location=grid_location(tree, (200, 160)),
            use_clamp=True,
        )
        additive_surface(Mat, final_color, coverage, additive)
        Mat.diffuse_color = tint


used_params = ("Diffuse", "TillingX", "Color", "ColorMultiplier", "AdditiveAlphaBlend")
