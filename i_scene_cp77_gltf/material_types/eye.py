import bpy
import os
from ..main.common import *

class Eye:
    def __init__(self, BasePath,image_format):
        self.BasePath = BasePath
        self.image_format = image_format

    def create(self,Data,Mat):
        CurMat = Mat.node_tree

        if "Specularity" in Data:
            CurMat.nodes['Principled BSDF'].inputs["Specular"].default_value = Data["Specularity"]

        if "RefractionIndex" in Data:
            CurMat.nodes['Principled BSDF'].inputs['IOR'].default_value = Data["RefractionIndex"]

#NORMAL/n
        if "Normal" in Data:
            nMap = CreateShaderNodeNormalMap(CurMat,self.BasePath + Data["Normal"],-150,-250,'Normal',self.image_format)
            CurMat.links.new(nMap.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Normal'])

#ROUGHNESS+SCALE/rs
        if "Roughness" in Data:
            rImgNode = CreateShaderNodeTexImage(CurMat,self.BasePath + Data["Roughness"],-450,0,'Roughness',self.image_format,True)

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
            CurMat.links.new(rsVecNode.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Roughness'])

#ALBEDO/a
        if "Albedo" in Data:
            aImgNode = CreateShaderNodeTexImage(CurMat,self.BasePath + Data["Albedo"],-300,250,'Albedo',self.image_format)
            CurMat.links.new(aImgNode.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Base Color'])
