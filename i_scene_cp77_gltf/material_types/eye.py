import bpy
import os
from ..main.common import *

class Eye:
    def __init__(self, BasePath, image_format, ProjPath):
        self.BasePath = BasePath
        self.ProjPath = ProjPath
        self.image_format = image_format

    def create(self,Data,Mat):
        CurMat = Mat.node_tree
        pBSDF = CurMat.nodes[loc('Principled BSDF')]
        sockets=bsdf_socket_names()

        if "Albedo" in Data:
            aImg = imageFromRelPath(Data["Albedo"],self.image_format,DepotPath=self.BasePath, ProjPath=self.ProjPath)
            aImgNode = create_node(CurMat.nodes,"ShaderNodeTexImage",  (-300,250), label="Albedo", image=aImg)
            CurMat.links.new(aImgNode.outputs[0],pBSDF.inputs['Base Color'])

        if "Roughness" in Data:
            rImg=imageFromRelPath(Data["Roughness"],self.image_format,DepotPath=self.BasePath, ProjPath=self.ProjPath, isNormal=True)
            rImgNode = create_node(CurMat.nodes,"ShaderNodeTexImage",  (-450,0), label="Roughness", image=rImg)

        if "RoughnessScale" in Data:
            rsNode = CreateShaderNodeValue(CurMat, Data["RoughnessScale"],-350,-50,"RoughnessScale")

        if "Normal" in Data:
            nMap = CreateShaderNodeNormalMap(CurMat,self.BasePath + Data["Normal"],-150,-250,'Normal',self.image_format)
            CurMat.links.new(nMap.outputs[0],pBSDF.inputs['Normal'])

        if "Specularity" in Data:
            pBSDF.inputs[sockets["Specular"]].default_value = Data["Specularity"]

        if "RefractionIndex" in Data:
            pBSDF.inputs['IOR'].default_value = Data["RefractionIndex"]

        rSeparateColor = CurMat.nodes.new("ShaderNodeSeparateColor")
        rSeparateColor.location = (-300, 0)

        mathMultiply = CurMat.nodes.new("ShaderNodeMath")
        mathMultiply.location = (-150,0)
        mathMultiply.operation = 'MULTIPLY'

        CurMat.links.new(rImgNode.outputs[0],rSeparateColor.inputs[0])
        CurMat.links.new(rSeparateColor.outputs[1],mathMultiply.inputs[0])
        CurMat.links.new(rsNode.outputs[0],mathMultiply.inputs[1])
        CurMat.links.new(mathMultiply.outputs[0],pBSDF.inputs['Roughness'])

