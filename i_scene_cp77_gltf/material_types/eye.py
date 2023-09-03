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
        pBSDF = CurMat.nodes['Principled BSDF']

        if "Specularity" in Data:
            pBSDF.inputs["Specular"].default_value = Data["Specularity"]

        if "RefractionIndex" in Data:
            pBSDF.inputs['IOR'].default_value = Data["RefractionIndex"]

#NORMAL/n
        if "Normal" in Data:
            nMap = CreateShaderNodeNormalMap(CurMat,self.BasePath + Data["Normal"],-150,-250,'Normal',self.image_format)
            CurMat.links.new(nMap.outputs[0],pBSDF.inputs['Normal'])

#ROUGHNESS+SCALE/rs
        if "Roughness" in Data:
            rImg=imageFromRelPath(Data["Roughness"],self.image_format,DepotPath=self.BasePath, ProjPath=self.ProjPath, isNormal=True)
            rImgNode = create_node(CurMat.nodes,"ShaderNodeTexImage",  (-450,0), label="Roughness", image=rImg)

        if "RoughnessScale" in Data:
            rsNode = CreateShaderNodeValue(CurMat, Data["RoughnessScale"],-350,-50,"RoughnessScale")

        # if both nodes were created, scale the image according to the scale factor
        # then attach the result to the BSDF shader
        if rImgNode and rsNode:
            rsVecNode = CurMat.nodes.new("ShaderNodeVectorMath")
            rsVecNode.location = (-150, 0)
            rsVecNode.operation = "SCALE"
            rsVecNode.hide = True
            
            CurMat.links.new(rImgNode.outputs[0],rsVecNode.inputs[0])
            CurMat.links.new(rsNode.outputs[0],rsVecNode.inputs[3])
            CurMat.links.new(rsVecNode.outputs[0],pBSDF.inputs['Roughness'])

#ALBEDO/a
        if "Albedo" in Data:
            aImg = imageFromRelPath(Data["Albedo"],self.image_format,DepotPath=self.BasePath, ProjPath=self.ProjPath)
            aImgNode = create_node(CurMat.nodes,"ShaderNodeTexImage",  (-300,250), label="Albedo", image=aImg)
            CurMat.links.new(aImgNode.outputs[0],pBSDF.inputs['Base Color'])
