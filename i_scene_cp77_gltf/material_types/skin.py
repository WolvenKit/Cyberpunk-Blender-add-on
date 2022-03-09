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
        sVcol.location = (-1400,250)

        sSepRGB = CurMat.nodes.new("ShaderNodeSeparateRGB")
        sSepRGB.location = (-1200,250)

        sMultiply = CurMat.nodes.new("ShaderNodeMath")
        sMultiply.location = (-800,250)
        sMultiply.operation = 'MULTIPLY'
        sMultiply.inputs[1].default_value = (0.05)

        CurMat.links.new(sVcol.outputs[0],sSepRGB.inputs[0])
        CurMat.links.new(sSepRGB.outputs[1],sMultiply.inputs[0])
        CurMat.links.new(sMultiply.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Subsurface'])
        CurMat.nodes['Principled BSDF'].inputs['Subsurface Color'].default_value = (0.8, 0.14908, 0.0825199, 1)
        
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

#ROUGHNES+MASK/rm

        if "Roughness" in Data:
            rImgNode = CreateShaderNodeTexImage(CurMat,self.BasePath + Data["Roughness"], -1600,50, "Roughness",self.image_format,True)

        rmSep = CurMat.nodes.new("ShaderNodeSeparateRGB")
        rmSep.location = (-1300,50)
        rmSep.hide = True
		
        rmSub = CurMat.nodes.new("ShaderNodeMath")
        rmSub.location = (-1100,0)
        rmSub.hide = True
        rmSub.operation = 'SUBTRACT'
        rmSub.inputs[1].default_value = (0.5)

        rmMul = CurMat.nodes.new("ShaderNodeMath")
        rmMul.location = (-900,-100)
        rmMul.hide = True
        rmMul.operation = 'MULTIPLY'
		
#NORMAL/n
        nMDCoordinates = CurMat.nodes.new("ShaderNodeTexCoord")
        nMDCoordinates.hide = True
        nMDCoordinates.location =  (-2000,-850)

        nVecMulAspectA = CurMat.nodes.new("ShaderNodeVectorMath")
        nVecMulAspectA.hide = True
        nVecMulAspectA.location =  (-1800,-1000)
        nVecMulAspectA.operation = "MULTIPLY"
        nVecMulAspectA.inputs[1].default_value = (1, 2, 1)
		
        nVecMulAspectB = CurMat.nodes.new("ShaderNodeVectorMath")
        nVecMulAspectB.hide = True
        nVecMulAspectB.location =  (-1800,-1150)
        nVecMulAspectB.operation = "MULTIPLY"
        nVecMulAspectB.inputs[1].default_value = (1, 2, 1)

        nVecMulA = CurMat.nodes.new("ShaderNodeVectorMath")
        nVecMulA.hide = True
        nVecMulA.location =  (-1600,-850)
        nVecMulA.operation = "MULTIPLY"
		
        nVecMulB = CurMat.nodes.new("ShaderNodeVectorMath")
        nVecMulB.hide = True
        nVecMulB.location =  (-1600,-1150)
        nVecMulB.operation = "MULTIPLY"
		
        nVecModA = CurMat.nodes.new("ShaderNodeVectorMath")
        nVecModA.hide = True
        nVecModA.location =  (-1400,-850)
        nVecModA.operation = "MODULO"
        nVecModA.inputs[1].default_value = (0.5, 1, 1)
		
        nVecModB = CurMat.nodes.new("ShaderNodeVectorMath")
        nVecModB.hide = True
        nVecModB.location =  (-1400,-1150)
        nVecModB.operation = "MODULO"
        nVecModB.inputs[1].default_value = (0.5, 1, 1)

        nVecAdd = CurMat.nodes.new("ShaderNodeVectorMath")
        nVecAdd.hide = True
        nVecAdd.location =  (-1200,-1150)
        nVecAdd.operation = "ADD"
        nVecAdd.inputs[1].default_value = (0.5, 0, 0)

        nOverlay1 = CurMat.nodes.new("ShaderNodeMixRGB")
        nOverlay1.hide = True
        nOverlay1.location =  (-1000,-300)
        nOverlay1.blend_type ='OVERLAY'
		
        nOverlay2 = CurMat.nodes.new("ShaderNodeMixRGB")
        nOverlay2.hide = True
        nOverlay2.location =  (-700,-300)
        nOverlay2.blend_type ='OVERLAY'
		
        mdOverlay = CurMat.nodes.new("ShaderNodeMixRGB")
        mdOverlay.hide = True
        mdOverlay.location =  (-700,-450)
        mdOverlay.blend_type ='OVERLAY'
        mdOverlay.inputs[0].default_value = (1)

        nNormalMap = CurMat.nodes.new("ShaderNodeNormalMap")
        nNormalMap.location = (-300, -300)
        nNormalMap.hide = True
		
        nRebuildNormal = CreateRebildNormalGroup(CurMat)
        nRebuildNormal.hide = True
        nRebuildNormal.location =  (-500,-300)

        if "Normal" in Data:
            nMap = CreateShaderNodeTexImage(CurMat, self.BasePath + Data["Normal"], -1800,-300, "Normal",self.image_format,True)
	
        if "DetailNormal" in Data:
            dnMap = CreateShaderNodeTexImage(CurMat, self.BasePath + Data["DetailNormal"], -1800,-450, "DetailNormal",self.image_format,True)
			
        if "DetailNormalInfluence" in Data:
            nDNInfluence = CreateShaderNodeValue(CurMat, Data["DetailNormalInfluence"],-1250,-200,"DetailNormalInfluence")

        if "MicroDetail" in Data:
            mdMapA = CreateShaderNodeTexImage(CurMat, self.BasePath + Data["MicroDetail"], -1100,-450, "MicroDetail",self.image_format,True)
            mdMapB = CreateShaderNodeTexImage(CurMat, self.BasePath + Data["MicroDetail"], -1100,-650, "MicroDetail",self.image_format,True)

        if "MicroDetailUVScale01" in Data:
            mdScale01 = CreateShaderNodeValue(CurMat, Data["MicroDetailUVScale01"],-2000,-1000,"MicroDetailUVScale01")

        if "MicroDetailUVScale02" in Data:
            mdScale02 = CreateShaderNodeValue(CurMat, Data["MicroDetailUVScale02"],-2000,-1150,"MicroDetailUVScale02")

        if "MicroDetailInfluence" in Data:
            mdInfluence = CreateShaderNodeValue(CurMat, Data["MicroDetailInfluence"],-1250,-100,"MicroDetailInfluence")

        if "Detailmap_Squash" in Data:
            ndSqImgNode = CreateShaderNodeTexImage(CurMat, self.BasePath + Data["Detailmap_Squash"], -2000,50, "Detailmap_Squash",self.image_format,True)

        if "Detailmap_Stretch" in Data:
            ndStImg = CreateShaderNodeTexImage(CurMat, self.BasePath + Data["Detailmap_Stretch"], -2000,0, "Detailmap_Stretch",self.image_format,True)

        CurMat.links.new(rImgNode.outputs[0],rmSep.inputs[0])
        CurMat.links.new(rmSep.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Roughness'])
        CurMat.links.new(rmSep.outputs[2],rmSub.inputs[0])
        CurMat.links.new(rmSub.outputs[0],rmMul.inputs[0])
        CurMat.links.new(rmMul.outputs[0],nOverlay2.inputs[0])
        CurMat.links.new(mdInfluence.outputs[0],rmMul.inputs[1])

        CurMat.links.new(nMap.outputs[0],nOverlay1.inputs[1])
        CurMat.links.new(dnMap.outputs[0],nOverlay1.inputs[2])
        CurMat.links.new(nDNInfluence.outputs[0],nOverlay1.inputs[0])

        CurMat.links.new(nMDCoordinates.outputs["UV"],nVecMulA.inputs[0])
        CurMat.links.new(nMDCoordinates.outputs["UV"],nVecMulB.inputs[0])
        CurMat.links.new(mdScale01.outputs[0],nVecMulAspectA.inputs[0])
        CurMat.links.new(mdScale02.outputs[0],nVecMulAspectB.inputs[0])
        CurMat.links.new(nVecMulAspectA.outputs[0],nVecMulA.inputs[1])
        CurMat.links.new(nVecMulAspectB.outputs[0],nVecMulB.inputs[1])
        CurMat.links.new(nVecMulA.outputs[0],nVecModA.inputs[0])
        CurMat.links.new(nVecMulB.outputs[0],nVecModB.inputs[0])
        CurMat.links.new(nVecModA.outputs[0],mdMapA.inputs[0])
        CurMat.links.new(nVecModB.outputs[0],nVecAdd.inputs[0])
        CurMat.links.new(nVecAdd.outputs[0],mdMapB.inputs[0])
        CurMat.links.new(mdMapA.outputs[0],mdOverlay.inputs[1])
        CurMat.links.new(mdMapB.outputs[0],mdOverlay.inputs[2])
		
        CurMat.links.new(nOverlay1.outputs[0],nOverlay2.inputs[1])
        CurMat.links.new(mdOverlay.outputs[0],nOverlay2.inputs[2])

        CurMat.links.new(nOverlay2.outputs[0],nRebuildNormal.inputs[0])
        CurMat.links.new(nRebuildNormal.outputs[0],nNormalMap.inputs[1])

        CurMat.links.new(nNormalMap.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Normal'])

#OTHER
        if "BloodColor" in Data:
            bfColor = CreateShaderNodeRGB(CurMat, Data["BloodColor"],-2000,300,"BloodColor")

        if "Bloodflow" in Data:
            bfImgNode = CreateShaderNodeTexImage(CurMat,self.BasePath + Data["Bloodflow"], -2000,350, "Bloodflow",self.image_format)