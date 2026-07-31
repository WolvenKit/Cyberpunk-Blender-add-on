from ..materials.blender.nodes import bsdf_socket_names, create_node, loc
from .mat_common import (
    MaterialTypeBase,
    coerce_texture_path,
    decal_values,
    unwrap_param,
)


class DecalGradientmapRecolorEmissive(MaterialTypeBase):
    def create(self, Data, Mat):
        values = decal_values(Data)
        difftex = coerce_texture_path(values.get("DiffuseTexture"))
        gradmap = coerce_texture_path(values.get("GradientMap"))
        emissive_gradmap = coerce_texture_path(values.get("EmissiveGradientMap"))
        masktex = coerce_texture_path(values.get("MaskTexture"))
        try:
            emissive_ev = float(unwrap_param(values.get("EmissiveEV", 0.0)))
        except (TypeError, ValueError):
            emissive_ev = 0.0

        CurMat = Mat.node_tree
        pBSDF = CurMat.nodes[loc("Principled BSDF")]
        sockets = bsdf_socket_names()
        diff_image = self._load_relative_image(
            difftex,
            non_color=True,
            error_label="emissive decal diffuse ID map",
        )
        gradient_image = self._load_relative_image(
            gradmap,
            error_label="emissive decal gradient map",
        )
        if diff_image is None or gradient_image is None:
            pBSDF.inputs["Alpha"].default_value = 0.0
            return

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
        CurMat.links.new(gradient_node.outputs[0], pBSDF.inputs[sockets["Emission"]])

        emissive_image = self._load_relative_image(
            emissive_gradmap,
            non_color=True,
            error_label="emissive decal emission gradient",
        )
        if emissive_image is not None:
            emissive_node = create_node(
                CurMat.nodes,
                "ShaderNodeTexImage",
                (-500, -500),
                label="EmissiveGradientMap",
                image=emissive_image,
            )
            CurMat.links.new(diff_node.outputs[0], emissive_node.inputs[0])
            emissive_mult = create_node(
                CurMat.nodes,
                "ShaderNodeMath",
                (-300, -500),
                operation="MULTIPLY",
            )
            emissive_mult.inputs[1].default_value = emissive_ev
            CurMat.links.new(emissive_node.outputs[0], emissive_mult.inputs[0])
            CurMat.links.new(
                emissive_mult.outputs[0],
                pBSDF.inputs["Emission Strength"],
            )

        mask_image = self._load_relative_image(
            masktex,
            non_color=True,
            error_label="emissive decal mask",
        )
        if mask_image is None:
            CurMat.links.new(gradient_node.outputs[1], pBSDF.inputs["Alpha"])
            return
        mask_node = create_node(
            CurMat.nodes,
            "ShaderNodeTexImage",
            (-800, -600),
            label="MaskTexture",
            image=mask_image,
        )
        alpha_mult = create_node(
            CurMat.nodes,
            "ShaderNodeMath",
            (-300, -350),
            operation="MULTIPLY",
        )
        CurMat.links.new(gradient_node.outputs[1], alpha_mult.inputs[0])
        CurMat.links.new(mask_node.outputs[0], alpha_mult.inputs[1])
        CurMat.links.new(alpha_mult.outputs[0], pBSDF.inputs["Alpha"])
