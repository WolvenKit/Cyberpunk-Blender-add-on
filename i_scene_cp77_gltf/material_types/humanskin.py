import bpy
import os
from ..main.common import imageFromPath

class HumanSkin:
    def __init__(self, BasePath,image_format):
        self.BasePath = BasePath
        self.image_format = image_format
    def create(self,Skin,Mat):

        CurMat = Mat.node_tree
#SSS/s
        sVcol = CurMat.nodes.new("ShaderNodeVertexColor")
        sVcol.location = (-800,250)

        sSepRGB = CurMat.nodes.new("ShaderNodeSeparateRGB")
        sSepRGB.location = (-600,250)

        CurMat.links.new(sVcol.outputs[0],sSepRGB.inputs[0])
        CurMat.links.new(sSepRGB.outputs[1],CurMat.nodes['Principled BSDF'].inputs['Subsurface'])
        CurMat.nodes['Principled BSDF'].inputs['Subsurface Color'].default_value = (0.8, 0.14908, 0.0825199, 1)

#NORMAL/n
        nImg = imageFromPath(self.BasePath + Skin["Normal"],self.image_format,True)

        nImgNode = CurMat.nodes.new("ShaderNodeTexImage")
        nImgNode.location = (-1200,-250)
        nImgNode.image = nImg
        nImgNode.label = "Normal"


        nRgbCurve = CurMat.nodes.new("ShaderNodeRGBCurve")
        nRgbCurve.location = (-900,-250)
        nRgbCurve.hide = True
        nRgbCurve.mapping.curves[2].points[0].location = (0,1)
        nRgbCurve.mapping.curves[2].points[1].location = (1,1)

        nMap = CurMat.nodes.new("ShaderNodeNormalMap")
        nMap.location = (-200,-250)
        nMap.hide = True

        CurMat.links.new(nImgNode.outputs[0],nRgbCurve.inputs[1])
        CurMat.links.new(nMap.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Normal'])
        
#Albedo/a
        aImg = imageFromPath(self.BasePath + Skin["Albedo"],self.image_format)
            
        aImgNode = CurMat.nodes.new("ShaderNodeTexImage")
        aImgNode.location = (-800,550)
        aImgNode.image = aImg
        aImgNode.label = "Albedo"

        CurMat.links.new(aImgNode.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Base Color'])
            
        tColor = CurMat.nodes.new("ShaderNodeRGB")
        tColor.location = (-400,500)
        tColor.hide = True
        tColor.label = "TintColor"
        tColor.outputs[0].default_value = (float(Skin["TintColor"]["Red"])/255,float(Skin["TintColor"]["Green"])/255,float(Skin["TintColor"]["Blue"])/255,float(Skin["TintColor"]["Alpha"])/255)
        
        tmaskImg = imageFromPath(self.BasePath + Skin["TintColorMask"],self.image_format,True)
            
        tmaskNode = CurMat.nodes.new("ShaderNodeTexImage")
        tmaskNode.location = (-500,550)
        tmaskNode.image = tmaskImg
        tmaskNode.hide = True
        tmaskNode.label = "TintColorMask"

        mixRGB = CurMat.nodes.new("ShaderNodeMixRGB")
        mixRGB.location = (-200,300)
        mixRGB.hide = True
        mixRGB.blend_type = 'MULTIPLY'

        CurMat.links.new(tmaskNode.outputs[0],mixRGB.inputs[0])
        CurMat.links.new(tColor.outputs[0],mixRGB.inputs[2])
        CurMat.links.new(aImgNode.outputs[0],mixRGB.inputs[1])
        CurMat.links.new(mixRGB.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Base Color'])


        rImg = imageFromPath(self.BasePath + Skin["Roughness"],self.image_format,True)
            
        rImgNode = CurMat.nodes.new("ShaderNodeTexImage")
        rImgNode.location = (-800,50)
        rImgNode.image = rImg
        rImgNode.label = "Roughness"

        Sep = CurMat.nodes.new("ShaderNodeSeparateRGB")
        Sep.location = (-500,50)
        Sep.hide = True
        CurMat.links.new(rImgNode.outputs[0],Sep.inputs[0])
        CurMat.links.new(Sep.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Roughness'])


        ndImg = imageFromPath(self.BasePath + Skin["DetailNormal"],self.image_format, True)
            
        ndImgNode = CurMat.nodes.new("ShaderNodeTexImage")
        ndImgNode.location = (-1200,-600)
        ndImgNode.image = ndImg
        ndImgNode.hide = True
        ndImgNode.label = "DetailNormal"

        ndInfluence = CurMat.nodes.new("ShaderNodeValue")
        ndInfluence.location = (-1200,-550)
        ndInfluence.outputs[0].default_value = float(Skin["DetailNormalInfluence"])
        ndInfluence.hide = True
        ndInfluence.label = "DetailNormalInfluence"

        ndRgbCurve = CurMat.nodes.new("ShaderNodeRGBCurve")
        ndRgbCurve.location = (-900,-600)
        ndRgbCurve.hide = True
        ndRgbCurve.mapping.curves[2].points[0].location = (0,1)
        ndRgbCurve.mapping.curves[2].points[1].location = (1,1)
        CurMat.links.new(ndImgNode.outputs[0],ndRgbCurve.inputs[1])

        ndMixRGB = CurMat.nodes.new("ShaderNodeMixRGB")
        ndMixRGB.location = (-550,-250)
        ndMixRGB.blend_type = 'OVERLAY'
        CurMat.links.new(ndRgbCurve.outputs[0],ndMixRGB.inputs[2])
        CurMat.links.new(nRgbCurve.outputs[0],ndMixRGB.inputs[1])
        CurMat.links.new(ndInfluence.outputs[0],ndMixRGB.inputs[0])
        CurMat.links.new(ndMixRGB.outputs[0],nMap.inputs[1])

        ndSqImg = imageFromPath(self.BasePath + Skin["Detailmap_Squash"],self.image_format, True)
            
        ndSqImgNode = CurMat.nodes.new("ShaderNodeTexImage")
        ndSqImgNode.location = (-1500,50)
        ndSqImgNode.image = ndSqImg
        ndSqImgNode.hide = True
        ndSqImgNode.label = "Detailmap_Squash"


        ndStImg = imageFromPath(self.BasePath + Skin["Detailmap_Stretch"],self.image_format, True)
            
        ndStImgNode = CurMat.nodes.new("ShaderNodeTexImage")
        ndStImgNode.location = (-1500,0)
        ndStImgNode.image = ndStImg
        ndStImgNode.hide = True
        ndStImgNode.label = "Detailmap_Stretch"


        mdImg = imageFromPath(self.BasePath + Skin["MicroDetail"],self.image_format, True)
        mdImgNode = CurMat.nodes.new("ShaderNodeTexImage")
        mdImgNode.location = (-1200,-700)
        mdImgNode.image = mdImg
        mdImgNode.hide = True
        mdImgNode.label = "MicroDetail"

        mdRgbCurve = CurMat.nodes.new("ShaderNodeRGBCurve")
        mdRgbCurve.location = (-900,-700)
        mdRgbCurve.hide = True
        mdRgbCurve.mapping.curves[2].points[0].location = (0,1)
        mdRgbCurve.mapping.curves[2].points[1].location = (1,1)
        CurMat.links.new(mdImgNode.outputs[0],mdRgbCurve.inputs[0])

        mdMixRGB = CurMat.nodes.new("ShaderNodeMixRGB")
        mdMixRGB.location = (-500,-700)
        mdMixRGB.hide = True

        mdMappingNode = CurMat.nodes.new("ShaderNodeMapping")
        mdMappingNode.label = "MicroDetailUVMapping"
        mdMappingNode.location = (-1400,-700)
        mdMappingNode.inputs[3].default_value[0] = Skin["MicroDetailUVScale01"]
        mdMappingNode.inputs[3].default_value[1] = Skin["MicroDetailUVScale02"]
        CurMat.links.new(mdMappingNode.outputs[0],mdImgNode.inputs[0])

        mdInfluence = CurMat.nodes.new("ShaderNodeValue")
        mdInfluence.location = (-1200,-650)
        mdInfluence.outputs[0].default_value = float(Skin["MicroDetailInfluence"])
        mdInfluence.hide = True
        mdInfluence.label = "MicroDetailInfluence"

        bfColor = CurMat.nodes.new("ShaderNodeRGB")
        bfColor.location = (-1500,300)
        bfColor.hide = True
        bfColor.label = "BloodColor"
        bfColor.outputs[0].default_value = (float(Skin["BloodColor"]["Red"])/255,float(Skin["BloodColor"]["Green"])/255,float(Skin["BloodColor"]["Blue"])/255,float(Skin["BloodColor"]["Alpha"])/255)

        bfImg = imageFromPath(self.BasePath + Skin["Bloodflow"],self.image_format)

        bfImgNode = CurMat.nodes.new("ShaderNodeTexImage")
        bfImgNode.location = (-1500,350)
        bfImgNode.image = bfImg
        bfImgNode.hide = True
        bfImgNode.label = "Bloodflow"