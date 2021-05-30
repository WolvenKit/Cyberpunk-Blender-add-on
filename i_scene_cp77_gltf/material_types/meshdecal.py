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
            dImgNode.location = (-300,200)
            dImgNode.image = dImg
            
            CurMat.links.new(dImgNode.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Base Color'])
            CurMat.links.new(dImgNode.outputs[1],CurMat.nodes['Principled BSDF'].inputs['Alpha'])

        if Decal.get("diffuseColor"):
            dColor = CurMat.nodes.new("ShaderNodeRGB")
            dColor.location = (-300,200)
            dColor.hide = True
            dColor.outputs[0].default_value = (float(Decal["diffuseColor"]["r"]),float(Decal["diffuseColor"]["g"]),float(Decal["diffuseColor"]["b"]),float(Decal["diffuseColor"]["a"]))

        if Decal.get("diffuseAlpha"):
            dAlpha = CurMat.nodes.new("ShaderNodeValue")
            dAlpha.location = (-300,0)
            dAlpha.outputs[0].default_value = float(Decal["diffuseAlpha"])
            dAlpha.hide = True