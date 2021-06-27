import bpy
import os
from ..main.common import imageFromPath

class HumanSkin:
    def __init__(self, BasePath,image_format):
        self.BasePath = BasePath
        self.image_format = image_format
    def create(self,Skin,Mat):

        CurMat = Mat.node_tree
        CurMat.nodes['Principled BSDF'].inputs['Subsurface'].default_value = 0.01

        
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
        

        aImg = imageFromPath(self.BasePath + Skin["Albedo"],self.image_format)
            
        aImgNode = CurMat.nodes.new("ShaderNodeTexImage")
        aImgNode.location = (-400,250)
        aImgNode.image = aImg
        aImgNode.label = "Albedo"

        CurMat.links.new(aImgNode.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Base Color'])
            
        tColor = CurMat.nodes.new("ShaderNodeRGB")
        tColor.location = (-300,300)
        tColor.hide = True
        tColor.label = "TintColor"
        tColor.outputs[0].default_value = (float(Skin["TintColor"]["Red"])/255,float(Skin["TintColor"]["Green"])/255,float(Skin["TintColor"]["Blue"])/255,float(Skin["TintColor"]["Alpha"])/255)
        
        tmaskImg = imageFromPath(self.BasePath + Skin["TintColorMask"],self.image_format,True)
            
        tmaskNode = CurMat.nodes.new("ShaderNodeTexImage")
        tmaskNode.location = (-400,350)
        tmaskNode.image = tmaskImg
        tmaskNode.hide = True
        tmaskNode.label = "TintColorMask"

        mixRGB = CurMat.nodes.new("ShaderNodeMixRGB")
        mixRGB.location = (-150,200)
        mixRGB.hide = True
        mixRGB.blend_type = 'MULTIPLY'

        CurMat.links.new(tmaskNode.outputs[0],mixRGB.inputs[0])
        CurMat.links.new(tColor.outputs[0],mixRGB.inputs[2])
        CurMat.links.new(aImgNode.outputs[0],mixRGB.inputs[1])
        CurMat.links.new(mixRGB.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Base Color'])


        rImg = imageFromPath(self.BasePath + Skin["Roughness"],self.image_format,True)
            
        rImgNode = CurMat.nodes.new("ShaderNodeTexImage")
        rImgNode.location = (-600,-50)
        rImgNode.image = rImg
        rImgNode.hide = True
        rImgNode.label = "Roughness"

        Sep = CurMat.nodes.new("ShaderNodeSeparateRGB")
        Sep.location = (-200,0)
        Sep.hide = True
        CurMat.links.new(rImgNode.outputs[0],Sep.inputs[0])
        CurMat.links.new(Sep.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Roughness'])
        CurMat.links.new(Sep.outputs[2],CurMat.nodes['Principled BSDF'].inputs['Specular'])


        ndImg = imageFromPath(self.BasePath + Skin["DetailNormal"],self.image_format)
            
        ndImgNode = CurMat.nodes.new("ShaderNodeTexImage")
        ndImgNode.location = (-600,-150)
        ndImgNode.image = ndImg
        ndImgNode.hide = True
        ndImgNode.label = "DetailNormal"

        ndInfluence = CurMat.nodes.new("ShaderNodeValue")
        ndInfluence.location = (-400,-150)
        ndInfluence.outputs[0].default_value = float(Skin["DetailNormalInfluence"])
        ndInfluence.hide = True
        ndInfluence.label = "DetailNormalInfluence"


        ndSqImg = imageFromPath(self.BasePath + Skin["Detailmap_Squash"],self.image_format)
            
        ndSqImgNode = CurMat.nodes.new("ShaderNodeTexImage")
        ndSqImgNode.location = (-1100,0)
        ndSqImgNode.image = ndSqImg
        ndSqImgNode.hide = True
        ndSqImgNode.label = "Detailmap_Squash"


        ndStImg = imageFromPath(self.BasePath + Skin["Detailmap_Stretch"],self.image_format)
            
        ndStImgNode = CurMat.nodes.new("ShaderNodeTexImage")
        ndStImgNode.location = (-1100,-100)
        ndStImgNode.image = ndStImg
        ndStImgNode.hide = True
        ndStImgNode.label = "Detailmap_Stretch"


        mdImg = imageFromPath(self.BasePath + Skin["MicroDetail"],self.image_format, True)
            
        mdImgNode = CurMat.nodes.new("ShaderNodeTexImage")
        mdImgNode.location = (-800,-450)
        mdImgNode.image = mdImg
        mdImgNode.hide = True
        mdImgNode.label = "MicroDetail"

        mdMappingNode = CurMat.nodes.new("ShaderNodeMapping")
        mdMappingNode.label = "MicroDetailUVMapping"
        mdMappingNode.location = (-1000,-450)
        mdMappingNode.inputs[3].default_value[0] = Skin["MicroDetailUVScale01"]
        mdMappingNode.inputs[3].default_value[1] = Skin["MicroDetailUVScale02"]

        mdInfluence = CurMat.nodes.new("ShaderNodeValue")
        mdInfluence.location = (-900,-450)
        mdInfluence.outputs[0].default_value = float(Skin["MicroDetailInfluence"])
        mdInfluence.hide = True
        mdInfluence.label = "MicroDetailInfluence"


        bfColor = CurMat.nodes.new("ShaderNodeRGB")
        bfColor.location = (-900,300)
        bfColor.hide = True
        bfColor.label = "BloodColor"
        bfColor.outputs[0].default_value = (float(Skin["BloodColor"]["Red"])/255,float(Skin["BloodColor"]["Green"])/255,float(Skin["BloodColor"]["Blue"])/255,float(Skin["BloodColor"]["Alpha"])/255)

        bfImg = imageFromPath(self.BasePath + Skin["Bloodflow"],self.image_format)

        bfImgNode = CurMat.nodes.new("ShaderNodeTexImage")
        bfImgNode.location = (-800,450)
        bfImgNode.image = bfImg
        bfImgNode.hide = True
        bfImgNode.label = "Bloodflow"