import bpy
import os
from ..main.common import *

class Skin:
    def __init__(self, BasePath, image_format,ProjPath):
        self.BasePath = str(BasePath)
        self.ProjPath = str(ProjPath)
        self.image_format = image_format
    def create(self,Data,Mat):
        CurMat = Mat.node_tree
        pBSDF = CurMat.nodes['Principled BSDF']
#SSS/s
        sVcol = create_node(CurMat.nodes,"ShaderNodeVertexColor", (-1400,250))

        sSepRGB = create_node(CurMat.nodes,"ShaderNodeSeparateRGB", (-1200,250))

        sMultiply = create_node(CurMat.nodes,"ShaderNodeMath", (-800,250), operation = 'MULTIPLY')
        sMultiply.inputs[1].default_value = (0.05)

        CurMat.links.new(sVcol.outputs[0],sSepRGB.inputs[0])
        CurMat.links.new(sSepRGB.outputs[1],sMultiply.inputs[0])
        CurMat.links.new(sMultiply.outputs[0],pBSDF.inputs['Subsurface'])
        pBSDF.inputs['Subsurface Color'].default_value = (0.8, 0.14908, 0.0825199, 1)
        
#Albedo/a
        mixRGB = create_node(CurMat.nodes,"ShaderNodeMixRGB", (-200,300), blend_type = 'MULTIPLY')

        if "Albedo" in Data:
            aImg=imageFromRelPath(Data["Albedo"],DepotPath=self.BasePath, ProjPath=self.ProjPath)
            aImgNode = create_node(CurMat.nodes,"ShaderNodeTexImage",  (-800,550), label="Albedo", image=aImg)
            CurMat.links.new(aImgNode.outputs[0],pBSDF.inputs['Base Color'])
            CurMat.links.new(aImgNode.outputs[0],mixRGB.inputs[1])

        if "TintColor" in Data:
            tColor = CreateShaderNodeRGB(CurMat, Data["TintColor"],-400,500,"TintColor")
            CurMat.links.new(tColor.outputs[0],mixRGB.inputs[2])
        
        if "TintColorMask" in Data:
            tImg=imageFromRelPath(Data["TintColorMask"],DepotPath=self.BasePath, ProjPath=self.ProjPath, isNormal=True)
            tmaskNode = create_node(CurMat.nodes, "ShaderNodeTexImage", (-500,550), label="TintColorMask", image=tImg)
            CurMat.links.new(tmaskNode.outputs[0],mixRGB.inputs[0])

        CurMat.links.new(mixRGB.outputs[0],pBSDF.inputs['Base Color'])

#ROUGHNES+MASK/rm

        if "Roughness" in Data:
            rImg=imageFromRelPath(Data["Roughness"],DepotPath=self.BasePath, ProjPath=self.ProjPath, isNormal=True)
            rImgNode = create_node(CurMat.nodes, "ShaderNodeTexImage", (-1600,50), label="Roughness", image=tImg)

        rmSep =  create_node(CurMat.nodes, "ShaderNodeSeparateRGB", (-1300,50))
		
        rmSub =  create_node(CurMat.nodes, "ShaderNodeMath", (-1100,0), operation = 'SUBTRACT')
        rmSub.inputs[1].default_value = (0.5)

        rmMul =  create_node(CurMat.nodes, "ShaderNodeMath", (-900,-100), operation = 'MULTIPLY')
		
#NORMAL/n
        nMDCoordinates =  create_node(CurMat.nodes,"ShaderNodeTexCoord", (-2000,-850))

        nVecMulAspectA =  create_node(CurMat.nodes,"ShaderNodeVectorMath", (-1800,-1000), operation = "MULTIPLY")
        nVecMulAspectA.inputs[1].default_value = (1, 2, 1)
		
        nVecMulAspectB =  create_node(CurMat.nodes,"ShaderNodeVectorMath",  (-1800,-1150), operation = "MULTIPLY")
        nVecMulAspectB.inputs[1].default_value = (1, 2, 1)

        nVecMulA =  create_node(CurMat.nodes,"ShaderNodeVectorMath", (-1600,-850), operation = "MULTIPLY")
		
        nVecMulB =  create_node(CurMat.nodes,"ShaderNodeVectorMath", (-1600,-1150), operation = "MULTIPLY")
		
        nVecModA =  create_node(CurMat.nodes,"ShaderNodeVectorMath", (-1400,-850), operation = "MODULO")
        nVecModA.inputs[1].default_value = (0.5, 1, 1)
		
        nVecModB =  create_node(CurMat.nodes,"ShaderNodeVectorMath", (-1400,-1150), operation = "MODULO")
        nVecModB.inputs[1].default_value = (0.5, 1, 1)

        nVecAdd =  create_node(CurMat.nodes,"ShaderNodeVectorMath", (-1200,-1150), operation = "ADD")
        nVecAdd.inputs[1].default_value = (0.5, 0, 0)

        nOverlay1 =  create_node(CurMat.nodes,"ShaderNodeMixRGB", (-1000,-300), blend_type ='OVERLAY')
		
        nOverlay2 =  create_node(CurMat.nodes,"ShaderNodeMixRGB", (-700,-300), blend_type ='OVERLAY')
		
        mdOverlay =  create_node(CurMat.nodes,"ShaderNodeMixRGB", (-700,-450), blend_type ='OVERLAY')
        mdOverlay.inputs[0].default_value = (1)

        nNormalMap =  create_node(CurMat.nodes,"ShaderNodeNormalMap", (-300, -300))
		
        nRebuildNormal = CreateRebildNormalGroup(CurMat)
        nRebuildNormal.hide = True
        nRebuildNormal.location =  (-500,-300)

        if "Normal" in Data:
            nImg = imageFromRelPath(Data["Normal"],DepotPath=self.BasePath, ProjPath=self.ProjPath, isNormal=True)
            nMap = create_node(CurMat.nodes, "ShaderNodeTexImage", (-1800,-300), label="Normal", image=nImg)
            nMap.image.colorspace_settings.name='Non-Color'
	
        if "DetailNormal" in Data:
            dnImg = imageFromRelPath(Data["DetailNormal"],DepotPath=self.BasePath, ProjPath=self.ProjPath, isNormal=True)
            dnMap = create_node(CurMat.nodes, "ShaderNodeTexImage", (-1800,-450), label="DetailNormal", image=dnImg)
            dnMap.image.colorspace_settings.name='Non-Color'
			
        if "DetailNormalInfluence" in Data:
            nDNInfluence = CreateShaderNodeValue(CurMat, Data["DetailNormalInfluence"],-1250,-200,"DetailNormalInfluence")

        if "MicroDetail" in Data:
            mdMapAImg = imageFromRelPath(Data["MicroDetail"],DepotPath=self.BasePath, ProjPath=self.ProjPath, isNormal=True)
            mdMapA =  create_node(CurMat.nodes, "ShaderNodeTexImage", (-1100,-450), label="MicroDetail", image=mdMapAImg)
            mdMapB = create_node(CurMat.nodes, "ShaderNodeTexImage", (-1100,-650), label="MicroDetail", image=mdMapAImg)

        if "MicroDetailUVScale01" in Data:
            mdScale01 = CreateShaderNodeValue(CurMat, Data["MicroDetailUVScale01"],-2000,-1000,"MicroDetailUVScale01")

        if "MicroDetailUVScale02" in Data:
            mdScale02 = CreateShaderNodeValue(CurMat, Data["MicroDetailUVScale02"],-2000,-1150,"MicroDetailUVScale02")

        if "MicroDetailInfluence" in Data:
            mdInfluence = CreateShaderNodeValue(CurMat, Data["MicroDetailInfluence"],-1250,-100,"MicroDetailInfluence")

        if "Detailmap_Squash" in Data:
            sqshImg = imageFromRelPath(Data["Detailmap_Squash"],DepotPath=self.BasePath, ProjPath=self.ProjPath, isNormal=True)
            ndSqImgNode = create_node(CurMat.nodes, "ShaderNodeTexImage", (-2000,50), label="Detailmap_Squash", image=sqshImg)

        if "Detailmap_Stretch" in Data:
            strchImg =  imageFromRelPath(Data["Detailmap_Stretch"],DepotPath=self.BasePath, ProjPath=self.ProjPath, isNormal=True)
            ndStImg = create_node(CurMat.nodes, "ShaderNodeTexImage", (-2000,0), label="Detailmap_Stretch", image=strchImg)

        CurMat.links.new(rImgNode.outputs[0],rmSep.inputs[0])
        CurMat.links.new(rmSep.outputs[0],pBSDF.inputs['Roughness'])
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

        CurMat.links.new(nNormalMap.outputs[0],pBSDF.inputs['Normal'])

#OTHER
        if "BloodColor" in Data:
            bfColor = CreateShaderNodeRGB(CurMat, Data["BloodColor"],-2000,300,"BloodColor")

        if "Bloodflow" in Data:
            bldImg = imageFromRelPath(Data["Bloodflow"],DepotPath=self.BasePath, ProjPath=self.ProjPath)
            bfImgNode = create_node(CurMat.nodes, "ShaderNodeTexImage", (-2000,350), label="Bloodflow", image=bldImg)