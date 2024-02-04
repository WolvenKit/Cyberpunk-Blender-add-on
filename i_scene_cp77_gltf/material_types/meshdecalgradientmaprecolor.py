import bpy
import os
from ..main.common import *


class MeshDecalGradientMapReColor:
    def __init__(self, BasePath, image_format, ProjPath):
        self.BasePath = BasePath
        self.ProjPath = ProjPath
        self.image_format = image_format

    def create(self, Data, Mat):
        Mat.blend_method = "HASHED"
        Mat.shadow_method = "HASHED"
        CurMat = Mat.node_tree
        pBSDF = CurMat.nodes["Principled BSDF"]
        sockets = bsdf_socket_names()
        pBSDF.inputs[sockets["Specular"]].default_value = 0

        if "MaskTexture" in Data:
            aImg = imageFromRelPath(
                Data["MaskTexture"], self.image_format, DepotPath=self.BasePath, ProjPath=self.ProjPath
            )
            aImgNode = create_node(CurMat.nodes, "ShaderNodeTexImage", (-300, -100), label="MaskTexture", image=aImg)
            CurMat.links.new(aImgNode.outputs[0], pBSDF.inputs["Alpha"])

        if "NormalTexture" in Data:
            nMap = CreateShaderNodeNormalMap(
                CurMat, self.BasePath + Data["NormalTexture"], -800, -250, "NormalTexture", self.image_format
            )
            CurMat.links.new(nMap.outputs[0], pBSDF.inputs["Normal"])

        if "DiffuseTexture" in Data:
            dImg = imageFromRelPath(
                Data["DiffuseTexture"], self.image_format, DepotPath=self.BasePath, ProjPath=self.ProjPath
            )
            dImgNode = create_node(CurMat.nodes, "ShaderNodeTexImage", (-600, 250), label="DiffuseTexture", image=dImg)

        if "GradientMap" in Data:
            gImg = imageFromRelPath(
                Data["GradientMap"], self.image_format, DepotPath=self.BasePath, ProjPath=self.ProjPath
            )
            gImgNode = create_node(CurMat.nodes, "ShaderNodeTexImage", (-300, 250), label="GradientMap", image=gImg)

        CurMat.links.new(dImgNode.outputs[0], gImgNode.inputs[0])
        CurMat.links.new(gImgNode.outputs[0], pBSDF.inputs["Base Color"])
