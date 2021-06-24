import bpy
import os
from ..main.common import imageFromPath

class HumanSkin:
    def __init__(self, BasePath,image_format):
        self.BasePath = BasePath
        self.image_format = image_format
    def create(self,Skin,Mat):
        CurMat = Mat.node_tree
        CurMat.nodes['Principled BSDF'].inputs['Subsurface'].default_value = 0.012
        if Skin.get("Normal"):
            nImg = imageFromPath(self.BasePath + Skin["Normal"],self.image_format,True)
            
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
        
        if Skin.get("Albedo"):
            aImg = imageFromPath(self.BasePath + Skin["Albedo"],self.image_format)
            
            aImgNode = CurMat.nodes.new("ShaderNodeTexImage")
            aImgNode.location = (-300,200)
            aImgNode.image = aImg
            aImgNode.label = "Albedo"

            CurMat.links.new(aImgNode.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Base Color'])
            
        if Skin.get("TintColor"):
            tColor = CurMat.nodes.new("ShaderNodeRGB")
            tColor.location = (-300,200)
            tColor.hide = True
            tColor.label = "TintColor"
            tColor.outputs[0].default_value = (float(Skin["TintColor"]["Red"])/255,float(Skin["TintColor"]["Green"])/255,float(Skin["TintColor"]["Blue"])/255,float(Skin["TintColor"]["Alpha"])/255)
        
        if Skin.get("TintColorMask"):
            tmaskImg = imageFromPath(self.BasePath + Skin["TintColorMask"],self.image_format)
            
            tmaskNode = CurMat.nodes.new("ShaderNodeTexImage")
            tmaskNode.location = (-500,200)
            tmaskNode.image = tmaskImg
            tmaskNode.hide = True
            tmaskNode.label = "TintColorMask"

        if Skin.get("Roughness"):
            rImg = imageFromPath(self.BasePath + Skin["Roughness"],self.image_format,true)
            
            rImgNode = CurMat.nodes.new("ShaderNodeTexImage")
            rImgNode.location = (-600,100)
            rImgNode.image = rImg
            rImgNode.hide = True
            rImgNode.label = "Roughness"

            Sep = CurMat.nodes.new("ShaderNodeSeparateRGB")
            Sep.location = (-400,100)
            Sep.hide = True
            CurMat.links.new(rImgNode.outputs[0],Sep.inputs[0])
            CurMat.links.new(Sep.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Roughness'])

        if Skin.get("DetailNormal"):
            ndImg = imageFromPath(self.BasePath + Skin["DetailNormal"],self.image_format)
            
            ndImgNode = CurMat.nodes.new("ShaderNodeTexImage")
            ndImgNode.location = (-600,0)
            ndImgNode.image = ndImg
            ndImgNode.hide = True
            ndImgNode.label = "DetailNormal"

        if Skin.get("DetailNormalInfluence"):
            ndInfluence = CurMat.nodes.new("ShaderNodeValue")
            ndInfluence.location = (-600,0)
            ndInfluence.outputs[0].default_value = float(Skin["DetailNormalInfluence"])
            ndInfluence.hide = True
            ndInfluence.label = "DetailNormalInfluence"

        if Skin.get("Detailmap_Squash"):
            ndSqImg = imageFromPath(self.BasePath + Skin["Detailmap_Squash"],self.image_format)
            
            ndSqImgNode = CurMat.nodes.new("ShaderNodeTexImage")
            ndSqImgNode.location = (-800,-100)
            ndSqImgNode.image = ndSqImg
            ndSqImgNode.hide = True
            ndSqImgNode.label = "Detailmap_Squash"

        if Skin.get("Detailmap_Stretch"):
            ndStImg = imageFromPath(self.BasePath + Skin["Detailmap_Stretch"],self.image_format)
            
            ndStImgNode = CurMat.nodes.new("ShaderNodeTexImage")
            ndStImgNode.location = (-1100,-100)
            ndStImgNode.image = ndStImg
            ndStImgNode.hide = True
            ndStImgNode.label = "Detailmap_Stretch"