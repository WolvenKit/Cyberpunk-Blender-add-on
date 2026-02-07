import bpy
import os

if __name__ != "__main__":
    from ..main.common import *


class DecalGradientmapRecolorEmissive:
    def __init__(self, BasePath, image_format, ProjPath):
        self.BasePath = BasePath
        self.ProjPath = ProjPath
        self.image_format = image_format

    def found(self, tex):
        result = os.path.exists(
            os.path.join(self.BasePath, tex)[:-3] + self.image_format
        )
        if not result:
            result = os.path.exists(
                os.path.join(self.ProjPath, tex)[:-3] + self.image_format
            )
            if not result:
                print(f"Texture not found: {tex}")
        return result

    def create(self, Data, Mat):
        masktex = ""
        difftex = ""
        gradmap = ""
        emissive_gradmap = ""
        emissiveEV = 0
        diffAsMask = 1
        if "enableMask" in Data.keys():
            if Data["enableMask"] == True:
                diffAsMask = 0
        for i in range(len(Data["values"])):
            for value in Data["values"][i]:
                if value == "DiffuseTexture":
                    difftex = Data["values"][i]["DiffuseTexture"]["DepotPath"]["$value"]
                if value == "GradientMap":
                    gradmap = Data["values"][i]["GradientMap"]["DepotPath"]["$value"]
                if value == "EmissiveGradientMap":
                    emissive_gradmap = Data["values"][i]["EmissiveGradientMap"][
                        "DepotPath"
                    ]["$value"]
                if value == "MaskTexture":
                    masktex = Data["values"][i]["MaskTexture"]["DepotPath"]["$value"]
                if value == "EmissiveEV":
                    emissiveEV = Data["values"][i]["EmissiveEV"]
        CurMat = Mat.node_tree
        pBSDF = CurMat.nodes[loc("Principled BSDF")]
        sockets = bsdf_socket_names()

        if self.found(difftex) and self.found(gradmap):
            diffImg = imageFromRelPath(
                difftex,
                self.image_format,
                DepotPath=self.BasePath,
                ProjPath=self.ProjPath,
                isNormal=True,
            )
            diff_image_node = create_node(
                CurMat.nodes,
                "ShaderNodeTexImage",
                (-800, -300),
                label="DiffuseTexture",
                image=diffImg,
            )

            gradImg = imageFromRelPath(
                gradmap,
                self.image_format,
                DepotPath=self.BasePath,
                ProjPath=self.ProjPath,
            )
            grad_image_node = create_node(
                CurMat.nodes,
                "ShaderNodeTexImage",
                (-500, -200),
                label="GradientMap",
                image=gradImg,
            )
            CurMat.links.new(diff_image_node.outputs[0], grad_image_node.inputs[0])
            CurMat.links.new(grad_image_node.outputs[0], pBSDF.inputs["Base Color"])
            CurMat.links.new(grad_image_node.outputs[0], pBSDF.inputs[sockets["Emission"]])

            if emissive_gradmap and self.found(emissive_gradmap):
                emissiveGradImg = imageFromRelPath(
                    emissive_gradmap,
                    self.image_format,
                    DepotPath=self.BasePath,
                    ProjPath=self.ProjPath,
                    isNormal=True,
                )
                emissive_grad_node = create_node(
                    CurMat.nodes,
                    "ShaderNodeTexImage",
                    (-500, -500),
                    label="EmissiveGradientMap",
                    image=emissiveGradImg,
                )
                CurMat.links.new(diff_image_node.outputs[0], emissive_grad_node.inputs[0])
                emissive_mult = create_node(
                    CurMat.nodes, "ShaderNodeMath", (-300, -500), operation="MULTIPLY"
                )
                emissive_mult.inputs[1].default_value = emissiveEV
                CurMat.links.new(emissive_grad_node.outputs[0], emissive_mult.inputs[0])
                CurMat.links.new(emissive_mult.outputs[0], pBSDF.inputs["Emission Strength"])

            if masktex and self.found(masktex):
                maskImg = imageFromRelPath(
                    masktex,
                    self.image_format,
                    DepotPath=self.BasePath,
                    ProjPath=self.ProjPath,
                    isNormal=True,
                )
                mask_image_node = create_node(
                    CurMat.nodes,
                    "ShaderNodeTexImage",
                    (-800, -600),
                    label="MaskTexture",
                    image=maskImg,
                )
                alpha_mult = create_node(
                    CurMat.nodes, "ShaderNodeMath", (-300, -350), operation="MULTIPLY"
                )
                CurMat.links.new(grad_image_node.outputs[1], alpha_mult.inputs[0])
                CurMat.links.new(mask_image_node.outputs[0], alpha_mult.inputs[1])
                CurMat.links.new(alpha_mult.outputs[0], pBSDF.inputs["Alpha"])
            else:
                CurMat.links.new(grad_image_node.outputs[1], pBSDF.inputs["Alpha"])
        else:
            pBSDF.inputs["Alpha"].default_value = 0
