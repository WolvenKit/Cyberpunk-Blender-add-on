import bpy
import os
from ..main.common import imageFromPath

class MetalBase:
    def __init__(self, BasePath,image_format):
        self.BasePath = BasePath
        self.image_format = image_format
    def create(self,MetalBase,Mat):

        CurMat = Mat.node_tree
        CurMat.nodes['Principled BSDF'].inputs['Specular'].default_value = 0

        if MetalBase.get("BaseColor"):
            bColImg = imageFromPath(self.BasePath + MetalBase["BaseColor"],self.image_format)
            
            bColNode = CurMat.nodes.new("ShaderNodeTexImage")
            bColNode.location = (-450,130)
            bColNode.image = bColImg
            bColNode.label = "BaseColor"

            CurMat.links.new(bColNode.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Base Color'])
            CurMat.links.new(bColNode.outputs[1],CurMat.nodes['Principled BSDF'].inputs['Alpha'])

        if MetalBase.get("BaseColorScale"):
            dColScale = CurMat.nodes.new("ShaderNodeRGB")
            dColScale.location = (-450,200)
            dColScale.hide = True
            dColScale.label = "BaseColorScale"
            dColScale.outputs[0].default_value = (float(MetalBase["BaseColorScale"]["X"]),float(MetalBase["BaseColorScale"]["Y"]),float(MetalBase["BaseColorScale"]["Z"]),float(MetalBase["BaseColorScale"]["W"]))

        if MetalBase.get("AlphaThreshold"):
            aThreshold = CurMat.nodes.new("ShaderNodeValue")
            aThreshold.location = (-300,0)
            aThreshold.outputs[0].default_value = float(MetalBase["AlphaThreshold"])
            aThreshold.hide = True
            aThreshold.label = "AlphaThreshold"

        if MetalBase.get("Normal"):
            nImg = imageFromPath(self.BasePath + MetalBase["Normal"],self.image_format,True)
            
            nImgNode = CurMat.nodes.new("ShaderNodeTexImage")
            nImgNode.location = (-800,-250)
            nImgNode.image = nImg
            nImgNode.label = "Normal"

            Sep = CurMat.nodes.new("ShaderNodeSeparateRGB")
            Sep.location = (-500,-250)
            Sep.hide = True
            
            Comb = CurMat.nodes.new("ShaderNodeCombineRGB")
            Comb.location = (-350,-250)
            Comb.hide = True
            
            CurMat.links.new(nImgNode.outputs[0],Sep.inputs[0])
            CurMat.links.new(Sep.outputs[0],Comb.inputs[0])
            CurMat.links.new(Sep.outputs[1],Comb.inputs[1])
            Comb.inputs[2].default_value = 1
            
            nMap = CurMat.nodes.new("ShaderNodeNormalMap")
            nMap.location = (-150,-250)
            nMap.hide = True

            CurMat.links.new(Comb.outputs[0],nMap.inputs[1])
            
            CurMat.links.new(nMap.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Normal'])

        if MetalBase.get("BaseColor") and MetalBase.get("BaseColorScale"):
            mixRGB = CurMat.nodes.new("ShaderNodeMixRGB")
            mixRGB.location = (-150,200)
            mixRGB.hide = True
            mixRGB.blend_type = 'MULTIPLY'
            mixRGB.inputs[0].default_value = 1

            CurMat.links.new(bColNode.outputs[0],mixRGB.inputs[2])
            CurMat.links.new(dColScale.outputs[0],mixRGB.inputs[1])
            CurMat.links.new(mixRGB.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Base Color'])

        if MetalBase.get("EmissiveColor"):
            emColor = CurMat.nodes.new("ShaderNodeRGB")
            emColor.location = (-800,-100)
            emColor.hide = True
            emColor.label = "EmissiveColor"
            emColor.outputs[0].default_value = (float(MetalBase["EmissiveColor"]["Red"])/255,float(MetalBase["EmissiveColor"]["Green"])/255,float(MetalBase["EmissiveColor"]["Blue"])/255,float(MetalBase["EmissiveColor"]["Alpha"])/255)

        if MetalBase.get("Emissive"):
            emTeximg = imageFromPath(self.BasePath + MetalBase["Emissive"],self.image_format)
            
            emTexNode = CurMat.nodes.new("ShaderNodeTexImage")
            emTexNode.location = (-800,200)
            emTexNode.image = emTeximg
            emTexNode.label = "Emissive"

        mulNode = CurMat.nodes.new("ShaderNodeMixRGB")
        mulNode.inputs[0].default_value = 1
        mulNode.blend_type = 'MULTIPLY'
        mulNode.location = (-550,50)

        CurMat.links.new(emColor.outputs[0],mulNode.inputs[1])
        CurMat.links.new(emTexNode.outputs[0],mulNode.inputs[2])
        CurMat.links.new(mulNode.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Emission'])

        CurMat.nodes['Principled BSDF'].inputs['Emission Strength'].default_value =  MetalBase["EmissiveEV"]