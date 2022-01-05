import bpy
import os
from ..main.common import *

class Skin:
    def __init__(self, BasePath,image_format):
        self.BasePath = BasePath
        self.image_format = image_format
    def create(self,Data,Mat):
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
        if "Normal" in Data:
            nMap = CreateShaderNodeNormalMap(CurMat, self.BasePath + Data["Normal"], -200,-250, "Normal",self.image_format)
            CurMat.links.new(nMap.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Normal'])
        
#Albedo/a
        mixRGB = CurMat.nodes.new("ShaderNodeMixRGB")
        mixRGB.location = (-200,300)
        mixRGB.hide = True
        mixRGB.blend_type = 'MULTIPLY'

        if "Albedo" in Data:
            aImgNode = CreateShaderNodeTexImage(CurMat,self.BasePath + Data["Albedo"], -800,550, "Albedo",self.image_format)
            CurMat.links.new(aImgNode.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Base Color'])
            CurMat.links.new(aImgNode.outputs[0],mixRGB.inputs[1])

        if "TintColor" in Data:
            tColor = CreateShaderNodeRGB(CurMat, Data["TintColor"],-400,500,"TintColor")
            CurMat.links.new(tColor.outputs[0],mixRGB.inputs[2])
        
        if "TintColorMask" in Data:
            tmaskNode = CreateShaderNodeTexImage(CurMat,self.BasePath + Data["TintColorMask"], -500,550, "TintColorMask",self.image_format,True)
            CurMat.links.new(tmaskNode.outputs[0],mixRGB.inputs[0])

        CurMat.links.new(mixRGB.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Base Color'])


        Sep = CurMat.nodes.new("ShaderNodeSeparateRGB")
        Sep.location = (-500,50)
        Sep.hide = True
        if "Roughness" in Data:
            rImgNode = CreateShaderNodeTexImage(CurMat,self.BasePath + Data["Roughness"], -800,50, "Roughness",self.image_format,True)
            CurMat.links.new(rImgNode.outputs[0],Sep.inputs[0])
            CurMat.links.new(Sep.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Roughness'])

        if "DetailNormal" in Data:
            ndMap = CreateShaderNodeNormalMap(CurMat, self.BasePath + Data["DetailNormal"], -550,-250, "DetailNormal",self.image_format)
            if "DetailNormalInfluence" in Data:
                ndInfluence = CreateShaderNodeValue(CurMat, Data["DetailNormalInfluence"],-1200,-550,"DetailNormalInfluence")
                CurMat.links.new(ndInfluence.outputs[0],ndMap.inputs[0])

        if "Detailmap_Squash" in Data:
            ndSqImgNode = CreateShaderNodeNormalMap(CurMat, self.BasePath + Data["Detailmap_Squash"], -1500,50, "Detailmap_Squash",self.image_format)

        if "Detailmap_Stretch" in Data:
            ndStImg = CreateShaderNodeNormalMap(CurMat, self.BasePath + Data["Detailmap_Stretch"], -1500,0, "Detailmap_Stretch",self.image_format)

        if "MicroDetail" in Data:
            mdMap = CreateShaderNodeNormalMap(CurMat, self.BasePath + Data["MicroDetail"], -1200,-700, "MicroDetail",self.image_format)

        mdMappingNode = CurMat.nodes.new("ShaderNodeMapping")
        mdMappingNode.label = "MicroDetailUVMapping"
        mdMappingNode.location = (-1400,-700)
        if "MicroDetailUVScale01" in Data:
            mdMappingNode.inputs[3].default_value[0] = float(Data["MicroDetailUVScale01"])
        if "MicroDetailUVScale02" in Data:
            mdMappingNode.inputs[3].default_value[1] = float(Data["MicroDetailUVScale02"])

        if "MicroDetailInfluence" in Data:
            mdInfluence = CreateShaderNodeValue(CurMat, Data["MicroDetailInfluence"],-1200,-650,"MicroDetailInfluence")

        if "BloodColor" in Data:
            bfColor = CreateShaderNodeRGB(CurMat, Data["BloodColor"],-1500,300,"BloodColor")

        if "Bloodflow" in Data:
            bfImgNode = CreateShaderNodeTexImage(CurMat,self.BasePath + Data["Bloodflow"], -1500,350, "Bloodflow",self.image_format)