import bpy
import os
from ..main.common import imageFromPath

class MeshDecal:
    def __init__(self, BasePath, valueToIgnore,image_format):
        self.BasePath = BasePath
        self.valueToIgnore = valueToIgnore
        self.image_format = image_format
    def create(self,Decal,Mat):
        CurMat = Mat.node_tree
        if Decal.get("diffuseTexture"):
            dImg = imageFromPath(self.BasePath + Decal["diffuseTexture"],self.image_format)
            
            dImgNode = CurMat.nodes.new("ShaderNodeTexImage")
            dImgNode.location = (-450,130)
            dImgNode.image = dImg
            dImgNode.label = "diffuseTexture"

            CurMat.links.new(dImgNode.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Base Color'])
            CurMat.links.new(dImgNode.outputs[1],CurMat.nodes['Principled BSDF'].inputs['Alpha'])

        if Decal.get("diffuseColor"):
            dColor = CurMat.nodes.new("ShaderNodeRGB")
            dColor.location = (-450,200)
            dColor.hide = True
            dColor.label = "diffuseColor"
            dColor.outputs[0].default_value = (float(Decal["diffuseColor"]["x"]),float(Decal["diffuseColor"]["y"]),float(Decal["diffuseColor"]["z"]),float(Decal["diffuseColor"]["w"]))

        if Decal.get("diffuseAlpha"):
            dAlpha = CurMat.nodes.new("ShaderNodeValue")
            dAlpha.location = (-300,0)
            dAlpha.outputs[0].default_value = float(Decal["diffuseAlpha"])
            dAlpha.hide = True
            dAlpha.label = "diffuseAlpha"

        if Decal.get("normalTexture"):
            nImg = imageFromPath(self.BasePath + Decal["normalTexture"],self.image_format,True)
            
            nImgNode = CurMat.nodes.new("ShaderNodeTexImage")
            nImgNode.location = (-800,-250)
            nImgNode.image = nImg
            nImgNode.label = "normalTexture"

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

            if Decal.get("normalAlpha"):
                nMap.inputs[0].default_value = float(Decal["normalAlpha"])

            CurMat.links.new(Comb.outputs[0],nMap.inputs[1])
            
            CurMat.links.new(nMap.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Normal'])

        if Decal.get("diffuseColor") and Decal.get("diffuseTexture"):
            mixRGB = CurMat.nodes.new("ShaderNodeMixRGB")
            mixRGB.location = (-150,200)
            mixRGB.hide = True
            mixRGB.blend_type = 'MULTIPLY'
            if Decal.get("diffuseAlpha"):
                mixRGB.inputs[0].default_value = float(Decal["diffuseAlpha"])

            CurMat.links.new(dImgNode.outputs[0],mixRGB.inputs[2])
            CurMat.links.new(dColor.outputs[0],mixRGB.inputs[1])
            CurMat.links.new(mixRGB.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Base Color'])