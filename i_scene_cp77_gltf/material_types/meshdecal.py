import bpy
import os
from ..main.common import imageFromPath

class MeshDecal:
    def __init__(self, BasePath,image_format):
        self.BasePath = BasePath
        self.image_format = image_format
    def create(self,Decal,Mat):

        CurMat = Mat.node_tree
        CurMat.nodes['Principled BSDF'].inputs['Specular'].default_value = 0

        if Decal.get("DiffuseTexture"):
            dImg = imageFromPath(self.BasePath + Decal["DiffuseTexture"],self.image_format)
            
            dImgNode = CurMat.nodes.new("ShaderNodeTexImage")
            dImgNode.location = (-450,130)
            dImgNode.image = dImg
            dImgNode.label = "DiffuseTexture"

            CurMat.links.new(dImgNode.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Base Color'])

            mulNode = CurMat.nodes.new("ShaderNodeMath")
            mulNode.inputs[0].default_value = float(Decal["DiffuseAlpha"])
            mulNode.operation = 'MULTIPLY'
            mulNode.location = (-200,-100)

            CurMat.links.new(dImgNode.outputs[1],mulNode.inputs[1])
            CurMat.links.new(mulNode.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Alpha'])

        if Decal.get("DiffuseColor"):
            dColor = CurMat.nodes.new("ShaderNodeRGB")
            dColor.location = (-450,200)
            dColor.hide = True
            dColor.label = "DiffuseColor"
            dColor.outputs[0].default_value = (float(Decal["DiffuseColor"]["Red"])/255,float(Decal["DiffuseColor"]["Green"])/255,float(Decal["DiffuseColor"]["Blue"])/255,float(Decal["DiffuseColor"]["Alpha"])/255)

        if Decal.get("NormalTexture"):
            nImg = imageFromPath(self.BasePath + Decal["NormalTexture"],self.image_format,True)
            
            nImgNode = CurMat.nodes.new("ShaderNodeTexImage")
            nImgNode.location = (-800,-250)
            nImgNode.image = nImg
            nImgNode.label = "NormalTexture"

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

            if Decal.get("NormalAlpha"):
                nMap.inputs[0].default_value = float(Decal["NormalAlpha"])

            CurMat.links.new(Comb.outputs[0],nMap.inputs[1])
            
            CurMat.links.new(nMap.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Normal'])

        if Decal.get("DiffuseColor") and Decal.get("DiffuseTexture"):
            mixRGB = CurMat.nodes.new("ShaderNodeMixRGB")
            mixRGB.location = (-150,200)
            mixRGB.hide = True
            mixRGB.blend_type = 'MULTIPLY'
            mixRGB.inputs[0].default_value = 1

            CurMat.links.new(dImgNode.outputs[0],mixRGB.inputs[2])
            CurMat.links.new(dColor.outputs[0],mixRGB.inputs[1])
            CurMat.links.new(mixRGB.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Base Color'])