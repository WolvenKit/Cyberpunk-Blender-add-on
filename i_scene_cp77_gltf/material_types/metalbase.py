import bpy
import os
from ..main.common import *

class MetalBase:
    def __init__(self, BasePath,image_format):
        self.BasePath = BasePath
        self.image_format = image_format
    def create(self,Data,Mat):
        CurMat = Mat.node_tree


        CurMat.nodes['Principled BSDF'].inputs['Specular'].default_value = 0

        mixRGB = CurMat.nodes.new("ShaderNodeMixRGB")
        mixRGB.location = (-200,200)
        mixRGB.hide = True
        mixRGB.blend_type = 'MULTIPLY'
        mixRGB.inputs[0].default_value = 1
        CurMat.links.new(mixRGB.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Base Color'])

        if "BaseColor" in Data:
            bColNode = CreateShaderNodeTexImage(CurMat,self.BasePath + Data["BaseColor"],-800,-450,'BaseColor',self.image_format)
            CurMat.links.new(bColNode.outputs[0],mixRGB.inputs[2])
            CurMat.links.new(bColNode.outputs[1],CurMat.nodes['Principled BSDF'].inputs['Alpha'])


        if "BaseColorScale" in Data:
            dColScale = CreateShaderNodeRGB(CurMat, Data["BaseColorScale"],-700,500,'BaseColorScale',True)
            CurMat.links.new(dColScale.outputs[0],mixRGB.inputs[1])


        if "AlphaThreshold" in Data:
            aThreshold = CreateShaderNodeValue(CurMat,Data["AlphaThreshold"],-1000, 0,"AlphaThreshold")

        if "Normal" in Data:
            nMap = CreateShaderNodeNormalMap(CurMat,self.BasePath + Data["Normal"],-200,-300,'Normal',self.image_format)
            CurMat.links.new(nMap.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Normal'])


        mulNode = CurMat.nodes.new("ShaderNodeMixRGB")
        mulNode.inputs[0].default_value = 1
        mulNode.blend_type = 'MULTIPLY'
        mulNode.location = (-450,100)

        if "EmissiveColor" in Data:
            emColor = CreateShaderNodeRGB(CurMat, Data["EmissiveColor"],-800,-200,"EmissiveColor")
            CurMat.links.new(emColor.outputs[0],mulNode.inputs[1])

        if "Emissive" in Data:
            emTexNode = CreateShaderNodeTexImage(CurMat,self.BasePath + Data["Emissive"],-800,100,'Emissive',self.image_format)
            CurMat.links.new(emTexNode.outputs[0],mulNode.inputs[2])

        CurMat.links.new(mulNode.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Emission'])

        if "EmissiveEV" in Data:
            CurMat.nodes['Principled BSDF'].inputs['Emission Strength'].default_value =  Data["EmissiveEV"]