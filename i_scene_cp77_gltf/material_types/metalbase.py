import bpy
import os
from ..main.common import imageFromPath

class MetalBase:
    def __init__(self, BasePath, valueToIgnore,image_format):
        self.BasePath = BasePath
        self.valueToIgnore = valueToIgnore
        self.image_format = image_format
    def create(self,MetalBase,Mat):
        CurMat = Mat.node_tree
        if MetalBase.get("baseColor"):
            bColImg = imageFromPath(self.BasePath + MetalBase["baseColor"],self.image_format)
            
            bColNode = CurMat.nodes.new("ShaderNodeTexImage")
            bColNode.location = (-450,130)
            bColNode.image = bColImg
            bColNode.label = "baseColor"

            CurMat.links.new(bColNode.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Base Color'])
            CurMat.links.new(bColNode.outputs[1],CurMat.nodes['Principled BSDF'].inputs['Alpha'])

        if MetalBase.get("baseColorScale"):
            dColScale = CurMat.nodes.new("ShaderNodeRGB")
            dColScale.location = (-450,200)
            dColScale.hide = True
            dColScale.label = "baseColorScale"
            dColScale.outputs[0].default_value = (float(MetalBase["baseColorScale"]["r"]),float(MetalBase["baseColorScale"]["g"]),float(MetalBase["baseColorScale"]["b"]),float(MetalBase["baseColorScale"]["a"]))

        if MetalBase.get("alphaThreshold"):
            aThreshold = CurMat.nodes.new("ShaderNodeValue")
            aThreshold.location = (-300,0)
            aThreshold.outputs[0].default_value = float(MetalBase["alphaThreshold"])
            aThreshold.hide = True
            aThreshold.label = "alphaThreshold"

        if MetalBase.get("normal"):
            nImg = imageFromPath(self.BasePath + MetalBase["normal"],self.image_format,True)
            
            nImgNode = CurMat.nodes.new("ShaderNodeTexImage")
            nImgNode.location = (-800,-250)
            nImgNode.image = nImg
            nImgNode.label = "normal"

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

        if MetalBase.get("baseColor") and MetalBase.get("baseColorScale"):
            mixRGB = CurMat.nodes.new("ShaderNodeMixRGB")
            mixRGB.location = (-150,200)
            mixRGB.hide = True
            mixRGB.blend_type = 'MULTIPLY'
            #if MetalBase.get("alphaThreshold"):
                #mixRGB.inputs[0].default_value = float(MetalBase["alphaThreshold"])
            mixRGB.inputs[0].default_value = 1

            CurMat.links.new(bColNode.outputs[0],mixRGB.inputs[2])
            CurMat.links.new(dColScale.outputs[0],mixRGB.inputs[1])
            CurMat.links.new(mixRGB.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Base Color'])