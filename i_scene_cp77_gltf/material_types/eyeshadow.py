import bpy
import os
from ..main.common import *


class EyeShadow:
    def __init__(self, BasePath,image_format):
        self.BasePath = BasePath
        self.image_format = image_format

    def create(self,Data,Mat):
        CurMat = Mat.node_tree

        CurMat.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.01
        CurMat.nodes['Principled BSDF'].inputs['Transmission'].default_value = 1

        if "Mask" in Data:
            aImgNode = CreateShaderNodeTexImage(CurMat,self.BasePath + Data["Mask"],-300,-250,'Mask',self.image_format)

        if "ShadowColor" in Data:
            shadowColor = CreateShaderNodeRGB(CurMat, Data["ShadowColor"],-450,200,'ShadowColor')