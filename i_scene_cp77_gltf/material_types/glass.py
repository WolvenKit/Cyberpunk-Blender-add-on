import bpy
import os
from ..main.common import *

class Glass:
    def __init__(self, BasePath,image_format):
        self.BasePath = BasePath
        self.image_format = image_format
    def create(self,Data,Mat):
        CurMat = Mat.node_tree

        CurMat.nodes['Principled BSDF'].inputs['Transmission'].default_value = 1

        if "TintColor" in Data:
            Color = CreateShaderNodeRGB(CurMat, Data["TintColor"],-400,200,'TintColor')
            CurMat.links.new(Color.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Base Color'])

        if "IOR" in Data:
            IOR = CreateShaderNodeValue(CurMat, Data["IOR"],-400,-150,"IOR")
            CurMat.links.new(IOR.outputs[0],CurMat.nodes['Principled BSDF'].inputs['IOR'])

        if "Roughness" in Data:
            rImgNode = CreateShaderNodeTexImage(CurMat,self.BasePath + Data["Roughness"],-800,50,'Roughness',self.image_format,True)
            CurMat.links.new(rImgNode.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Roughness'])

        if "Normal" in Data:
            nMap = CreateShaderNodeNormalMap(CurMat,self.BasePath + Data["Normal"],-200,-300,'Normal',self.image_format)
            CurMat.links.new(nMap.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Normal'])