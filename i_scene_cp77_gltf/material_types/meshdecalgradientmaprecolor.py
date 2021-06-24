import bpy
import os
from ..main.common import imageFromPath

class MeshDecalGradientMapReColor:
    def __init__(self, BasePath,image_format):
        self.BasePath = BasePath
        self.image_format = image_format

    def create(self,mDecalGmap,Mat):

        CurMat = Mat.node_tree


        aImg = imageFromPath(self.BasePath + mDecalGmap["MaskTexture"],self.image_format)
        aImgNode = CurMat.nodes.new("ShaderNodeTexImage")
        aImgNode.location = (-300,-100)
        aImgNode.image = aImg
        aImgNode.label = "MaskTexture"
        CurMat.links.new(aImgNode.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Alpha'])

        CurMat.nodes['Principled BSDF'].inputs['Specular'].default_value = 0


        nImg = imageFromPath(self.BasePath + mDecalGmap["NormalTexture"],self.image_format,true)
            
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

        CurMat.links.new(Comb.outputs[0],nMap.inputs[1])
            
        CurMat.links.new(nMap.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Normal'])


        gImg = imageFromPath(self.BasePath + mDecalGmap["GradientMap"],self.image_format)
            
        gImgNode = CurMat.nodes.new("ShaderNodeTexImage")
        gImgNode.location = (-600,250)
        gImgNode.image = gImg
        gImgNode.label = "GradientMap"

        dImg = imageFromPath(self.BasePath + mDecalGmap["DiffuseTexture"],self.image_format)
            
        dImgNode = CurMat.nodes.new("ShaderNodeTexImage")
        dImgNode.location = (-600,0)
        dImgNode.image = dImg
        dImgNode.label = "DiffuseTexture"

        mulNode = CurMat.nodes.new("ShaderNodeMixRGB")
        mulNode.inputs[0].default_value = 1
        mulNode.blend_type = 'MULTIPLY'
        mulNode.location = (-250,150)

        CurMat.links.new(gImgNode.outputs[0],mulNode.inputs[1])
        CurMat.links.new(dImgNode.outputs[0],mulNode.inputs[2])
        CurMat.links.new(mulNode.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Base Color'])