import bpy
import os
from ..main.common import *

class MeshDecalGradientMapReColor:
    def __init__(self, BasePath,image_format):
        self.BasePath = BasePath
        self.image_format = image_format

    def create(self,Data,Mat):
        CurMat = Mat.node_tree

        if "MaskTexture" in Data:
            aImgNode =  CreateShaderNodeTexImage(CurMat,self.BasePath + Data["MaskTexture"],-300,-100,'MaskTexture',self.image_format)
            CurMat.links.new(aImgNode.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Alpha'])


        CurMat.nodes['Principled BSDF'].inputs['Specular'].default_value = 0

        if "NormalTexture" in Data:
            nMap = CreateShaderNodeNormalMap(CurMat,self.BasePath + Data["NormalTexture"],-800,-250,'NormalTexture',self.image_format)
            CurMat.links.new(nMap.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Normal'])

        mulNode = CurMat.nodes.new("ShaderNodeMixRGB")
        mulNode.inputs[0].default_value = 1
        mulNode.use_clamp = True
        mulNode.blend_type = 'MULTIPLY'
        mulNode.location = (-250,150)

        if "GradientMap" in Data:
            gImgNode = CreateShaderNodeTexImage(CurMat,self.BasePath + Data["GradientMap"],-600,250,'GradientMap',self.image_format)
            CurMat.links.new(gImgNode.outputs[0],mulNode.inputs[1])

        if "DiffuseTexture" in Data:
            dImgNode = CreateShaderNodeTexImage(CurMat,self.BasePath + Data["DiffuseTexture"],-600,0,'DiffuseTexture',self.image_format)
            CurMat.links.new(dImgNode.outputs[0],mulNode.inputs[2])

        CurMat.links.new(mulNode.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Base Color'])