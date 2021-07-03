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
            bColNode.location = (-800,450)
            bColNode.image = bColImg
            bColNode.label = "BaseColor"

            CurMat.links.new(bColNode.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Base Color'])
            CurMat.links.new(bColNode.outputs[1],CurMat.nodes['Principled BSDF'].inputs['Alpha'])

        if MetalBase.get("BaseColorScale"):
            dColScale = CurMat.nodes.new("ShaderNodeRGB")
            dColScale.location = (-700,500)
            dColScale.hide = True
            dColScale.label = "BaseColorScale"
            dColScale.outputs[0].default_value = (float(MetalBase["BaseColorScale"]["X"]),float(MetalBase["BaseColorScale"]["Y"]),float(MetalBase["BaseColorScale"]["Z"]),float(MetalBase["BaseColorScale"]["W"]))

        if MetalBase.get("BaseColor") and MetalBase.get("BaseColorScale"):
            mixRGB = CurMat.nodes.new("ShaderNodeMixRGB")
            mixRGB.location = (-200,200)
            mixRGB.hide = True
            mixRGB.blend_type = 'MULTIPLY'
            mixRGB.inputs[0].default_value = 1

            CurMat.links.new(bColNode.outputs[0],mixRGB.inputs[2])
            CurMat.links.new(dColScale.outputs[0],mixRGB.inputs[1])
            CurMat.links.new(mixRGB.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Base Color'])

        if MetalBase.get("AlphaThreshold"):
            aThreshold = CurMat.nodes.new("ShaderNodeValue")
            aThreshold.location = (-1000,0)
            aThreshold.outputs[0].default_value = float(MetalBase["AlphaThreshold"])
            aThreshold.hide = True
            aThreshold.label = "AlphaThreshold"

        if MetalBase.get("Normal"):
            nImg = imageFromPath(self.BasePath + MetalBase["Normal"],self.image_format,True)
            
            nImgNode = CurMat.nodes.new("ShaderNodeTexImage")
            nImgNode.location = (-800,-300)
            nImgNode.image = nImg
            nImgNode.label = "Normal"

            nRgbCurve = CurMat.nodes.new("ShaderNodeRGBCurve")
            nRgbCurve.location = (-500,-300)
            nRgbCurve.hide = True
            nRgbCurve.mapping.curves[2].points[0].location = (0,1)
            nRgbCurve.mapping.curves[2].points[1].location = (1,1)
            
            CurMat.links.new(nImgNode.outputs[0],nRgbCurve.inputs[1])
            
            nMap = CurMat.nodes.new("ShaderNodeNormalMap")
            nMap.location = (-200,-300)
            nMap.hide = True

            CurMat.links.new(nRgbCurve.outputs[0],nMap.inputs[1])
            CurMat.links.new(nMap.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Normal'])


        if MetalBase.get("EmissiveColor"):
            emColor = CurMat.nodes.new("ShaderNodeRGB")
            emColor.location = (-800,-200)
            emColor.hide = True
            emColor.label = "EmissiveColor"
            emColor.outputs[0].default_value = (float(MetalBase["EmissiveColor"]["Red"])/255,float(MetalBase["EmissiveColor"]["Green"])/255,float(MetalBase["EmissiveColor"]["Blue"])/255,float(MetalBase["EmissiveColor"]["Alpha"])/255)

        if MetalBase.get("Emissive"):
            emTeximg = imageFromPath(self.BasePath + MetalBase["Emissive"],self.image_format)
            
            emTexNode = CurMat.nodes.new("ShaderNodeTexImage")
            emTexNode.location = (-800,100)
            emTexNode.image = emTeximg
            emTexNode.label = "Emissive"

        mulNode = CurMat.nodes.new("ShaderNodeMixRGB")
        mulNode.inputs[0].default_value = 1
        mulNode.blend_type = 'MULTIPLY'
        mulNode.location = (-450,100)

        CurMat.links.new(emColor.outputs[0],mulNode.inputs[1])
        CurMat.links.new(emTexNode.outputs[0],mulNode.inputs[2])
        CurMat.links.new(mulNode.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Emission'])

        CurMat.nodes['Principled BSDF'].inputs['Emission Strength'].default_value =  MetalBase["EmissiveEV"]