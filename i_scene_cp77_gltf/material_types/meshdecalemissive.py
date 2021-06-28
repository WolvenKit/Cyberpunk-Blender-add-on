import bpy
import os
from ..main.common import imageFromPath

class MeshDecalEmissive:
    def __init__(self, BasePath,image_format):
        self.BasePath = BasePath
        self.image_format = image_format
    def create(self,DecalEmissive,Mat):

        CurMat = Mat.node_tree
        CurMat.nodes['Principled BSDF'].inputs['Specular'].default_value = 0

        if DecalEmissive.get("DiffuseColor2"):
            dCol2 = CurMat.nodes.new("ShaderNodeRGB")
            dCol2.location = (-450,200)
            dCol2.hide = True
            dCol2.label = "DiffuseColor2"
            dCol2.outputs[0].default_value = (float(DecalEmissive["DiffuseColor2"]["Red"])/255,float(DecalEmissive["DiffuseColor2"]["Green"])/255,float(DecalEmissive["DiffuseColor2"]["Blue"])/255,float(DecalEmissive["DiffuseColor2"]["Alpha"])/255)
            
            CurMat.links.new(dCol2.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Base Color'])

        if DecalEmissive.get("DiffuseAlpha"):
            aThreshold = CurMat.nodes.new("ShaderNodeValue")
            aThreshold.location = (-300,0)
            aThreshold.outputs[0].default_value = float(DecalEmissive["DiffuseAlpha"])
            aThreshold.hide = True
            aThreshold.label = "DiffuseAlpha"

        if DecalEmissive.get("DiffuseColor"):
            emColor = CurMat.nodes.new("ShaderNodeRGB")
            emColor.location = (-800,-100)
            emColor.hide = True
            emColor.label = "DiffuseColor"
            emColor.outputs[0].default_value = (float(DecalEmissive["DiffuseColor"]["Red"])/255,float(DecalEmissive["DiffuseColor"]["Green"])/255,float(DecalEmissive["DiffuseColor"]["Blue"])/255,float(DecalEmissive["DiffuseColor"]["Alpha"])/255)

        if DecalEmissive.get("DiffuseTexture"):
            emTeximg = imageFromPath(self.BasePath + DecalEmissive["DiffuseTexture"],self.image_format)
            
            emTexNode = CurMat.nodes.new("ShaderNodeTexImage")
            emTexNode.location = (-800,200)
            emTexNode.image = emTeximg
            emTexNode.label = "DiffuseTexture"

        mulNode = CurMat.nodes.new("ShaderNodeMixRGB")
        mulNode.inputs[0].default_value = 1
        mulNode.blend_type = 'MULTIPLY'
        mulNode.location = (-550,50)

        CurMat.links.new(emColor.outputs[0],mulNode.inputs[1])
        CurMat.links.new(emTexNode.outputs[0],mulNode.inputs[2])
        CurMat.links.new(mulNode.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Emission'])

        CurMat.nodes['Principled BSDF'].inputs['Emission Strength'].default_value =  DecalEmissive["EmissiveEV"]