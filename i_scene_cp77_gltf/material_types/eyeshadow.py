import bpy
import os
from ..main.common import imageFromPath


class EyeShadow:
    def __init__(self, BasePath,image_format):
        self.BasePath = BasePath
        self.image_format = image_format

    def create(self,eyeshadow,Mat):
        CurMat = Mat.node_tree
        aImg = imageFromPath(self.BasePath + eyeshadow["Mask"],self.image_format)

        aImgNode = CurMat.nodes.new("ShaderNodeTexImage")
        aImgNode.location = (-300,-250)
        aImgNode.image = aImg
        aImgNode.label = "Mask"
        CurMat.links.new(aImgNode.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Alpha'])

        dColor = CurMat.nodes.new("ShaderNodeRGB")
        dColor.location = (-450,200)
        dColor.hide = True
        dColor.label = "ShadowColor"
        dColor.outputs[0].default_value = (float(eyeshadow["ShadowColor"]["Red"])/255,float(eyeshadow["ShadowColor"]["Green"])/255,float(eyeshadow["ShadowColor"]["Blue"])/255,float(eyeshadow["ShadowColor"]["Alpha"])/255)
        CurMat.links.new(dColor.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Base Color'])