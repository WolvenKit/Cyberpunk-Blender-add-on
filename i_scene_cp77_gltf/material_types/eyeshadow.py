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

#MASK+SHADOW COLOR/ms
        if "Mask" in Data:
            mImgNode = CreateShaderNodeTexImage(CurMat,self.BasePath + Data["Mask"],-500,250,'Mask',self.image_format)
            mImgNode.image.colorspace_settings.name = 'Non-Color'

        if "ShadowColor" in Data:
            msColorNode = CreateShaderNodeRGB(CurMat, Data["ShadowColor"],-400,150,'ShadowColor')

        # if both nodes were created, use the multiply node to mask the shadow
        # then attach the result to the BSDF shader
        # since node color is black by default, just use white as the base
        if mImgNode and msColorNode:
            mixNode = CurMat.nodes.new("ShaderNodeMixRGB")
            mixNode.blend_type = 'MULTIPLY'
            mixNode.location = (-200,200)
            mixNode.inputs[1].default_value = (1,1,1,1)
            mixNode.hide = True

            CurMat.links.new(mImgNode.outputs[1],mixNode.inputs[0])
            CurMat.links.new(msColorNode.outputs[0],mixNode.inputs[2])
            
            CurMat.links.new(mixNode.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Base Color'])