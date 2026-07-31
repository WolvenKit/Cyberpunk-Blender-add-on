from ..materials.blender.nodes import create_node, loc
from .mat_common import MaterialTypeBase, coerce_texture_path, decal_values


class DecalGradientmapRecolor(MaterialTypeBase):
    def create(self, Data, Mat):
        values = decal_values(Data)
        difftex = coerce_texture_path(values.get("DiffuseTexture"))
        gradmap = coerce_texture_path(values.get("GradientMap"))
        masktex = coerce_texture_path(values.get("MaskTexture"))
        use_diffuse_mask = not bool(Data.get("enableMask"))

        CurMat = Mat.node_tree
        pBSDF = CurMat.nodes[loc("Principled BSDF")]
        diff_image = self._load_relative_image(
            difftex,
            error_label="decal gradient diffuse",
        )
        gradient_image = self._load_relative_image(
            gradmap,
            error_label="decal gradient map",
        )
        if diff_image is None or gradient_image is None:
            pBSDF.inputs["Alpha"].default_value = 0.0
            return

        try:
            diff_image.colorspace_settings.name = "Linear Rec.709"
        except (AttributeError, TypeError, ValueError):
            pass
        diff_node = create_node(
            CurMat.nodes,
            "ShaderNodeTexImage",
            (-800, -300),
            label="DiffuseTexture",
            image=diff_image,
        )
        gradient_node = create_node(
            CurMat.nodes,
            "ShaderNodeTexImage",
            (-500, -200),
            label="GradientMap",
            image=gradient_image,
        )
        CurMat.links.new(diff_node.outputs[0], gradient_node.inputs[0])
        CurMat.links.new(gradient_node.outputs[0], pBSDF.inputs["Base Color"])

        if use_diffuse_mask:
            alpha_ramp = create_node(
                CurMat.nodes,
                "ShaderNodeValToRGB",
                (-500, -350),
                label="MaskRamp",
            )
            alpha_ramp.color_ramp.elements[0].position = 0.004
            alpha_ramp.color_ramp.elements[1].position = 0.04
            CurMat.links.new(diff_node.outputs[0], alpha_ramp.inputs[0])
            CurMat.links.new(alpha_ramp.outputs[0], pBSDF.inputs["Alpha"])
            return

        mask_image = self._load_relative_image(
            masktex,
            non_color=True,
            error_label="decal gradient mask",
        )
        if mask_image is None:
            CurMat.links.new(diff_node.outputs[1], pBSDF.inputs["Alpha"])
            return
        mask_node = create_node(
            CurMat.nodes,
            "ShaderNodeTexImage",
            (-800, -100),
            label="MaskTexture",
            image=mask_image,
        )
        CurMat.links.new(mask_node.outputs[0], pBSDF.inputs["Alpha"])
