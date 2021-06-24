import bpy
import os
from ..main.common import imageFromPath

class Eye:
    def __init__(self, BasePath,image_format):
        self.BasePath = BasePath
        self.image_format = image_format

    def create(self,eye,Mat):

        CurMat = Mat.node_tree
        nImg = imageFromPath(self.BasePath + eye["Normal"],self.image_format,True)
            
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


        rImg = imageFromPath(self.BasePath + eye["Roughness"],self.image_format,True)
            
        rImgNode = CurMat.nodes.new("ShaderNodeTexImage")
        rImgNode.location = (-300,0)
        rImgNode.image = rImg
        rImgNode.label = "Roughness"

        CurMat.links.new(rImgNode.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Roughness'])


        aImg = imageFromPath(self.BasePath + eye["Albedo"],self.image_format)
            
        aImgNode = CurMat.nodes.new("ShaderNodeTexImage")
        aImgNode.location = (-300,250)
        aImgNode.image = aImg
        aImgNode.label = "Albedo"

        CurMat.links.new(aImgNode.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Base Color'])