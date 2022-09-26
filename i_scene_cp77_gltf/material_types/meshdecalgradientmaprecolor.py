import bpy
import os
from ..main.common import *

class MeshDecalGradientMapReColor:
    def __init__(self, BasePath,image_format):
        self.BasePath = BasePath
        self.image_format = image_format

    def create(self,Data,Mat):

        Mat.blend_method = 'HASHED'
        Mat.shadow_method = 'HASHED'

        CurMat = Mat.node_tree

        if "MaskTexture" in Data:
            aImgNode =  CreateShaderNodeTexImage(CurMat,self.BasePath + Data["MaskTexture"],-300,-100,'MaskTexture',self.image_format)
            CurMat.links.new(aImgNode.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Alpha'])


        CurMat.nodes['Principled BSDF'].inputs['Specular'].default_value = 0

        if "NormalTexture" in Data:
            nMap = CreateShaderNodeNormalMap(CurMat,self.BasePath + Data["NormalTexture"],-800,-250,'NormalTexture',self.image_format)
            CurMat.links.new(nMap.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Normal'])

        if "DiffuseTexture" in Data:
            dImgNode = CreateShaderNodeTexImage(CurMat,self.BasePath + Data["DiffuseTexture"],-600,250,'DiffuseTexture',self.image_format)

        if "GradientMap" in Data:
            gImgNode = CreateShaderNodeTexImage(CurMat,self.BasePath + Data["GradientMap"],-300,250,'GradientMap',self.image_format)

        CurMat.links.new(dImgNode.outputs[0],gImgNode.inputs[0])
        CurMat.links.new(gImgNode.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Base Color'])