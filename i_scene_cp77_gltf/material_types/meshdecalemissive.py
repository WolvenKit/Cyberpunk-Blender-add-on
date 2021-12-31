import bpy
import os
from ..main.common import *

class MeshDecalEmissive:
    def __init__(self, BasePath,image_format):
        self.BasePath = BasePath
        self.image_format = image_format
    def create(self,Data,Mat):
        CurMat = Mat.node_tree
        CurMat.nodes['Principled BSDF'].inputs['Specular'].default_value = 0

        if "DiffuseColor2" in Data:
            dCol2 = CreateShaderNodeRGB(CurMat, Data["DiffuseColor2"], -450,200, "DiffuseColor2")
            CurMat.links.new(dCol2.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Base Color'])

        if "DiffuseAlpha" in Data:
            aThreshold = CreateShaderNodeValue(CurMat, Data["DiffuseAlpha"], -300,0, "DiffuseAlpha")

        mulNode = CurMat.nodes.new("ShaderNodeMixRGB")
        mulNode.inputs[0].default_value = 1
        mulNode.blend_type = 'MULTIPLY'
        mulNode.location = (-550,50)
        if "DiffuseColor" in Data:
            emColor = CreateShaderNodeRGB(CurMat, Data["DiffuseColor"], -800,-100, "DiffuseColor")
            CurMat.links.new(emColor.outputs[0],mulNode.inputs[1])

        if "DiffuseTexture" in Data:
            emTexNode = CreateShaderNodeTexImage(CurMat,self.BasePath + Data["DiffuseTexture"],-800,200,'DiffuseTexture',self.image_format)
            CurMat.links.new(emTexNode.outputs[0],mulNode.inputs[2])

        CurMat.links.new(mulNode.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Emission'])

        if "EmissiveEV" in Data:
            CurMat.nodes['Principled BSDF'].inputs['Emission Strength'].default_value =  Data["EmissiveEV"]