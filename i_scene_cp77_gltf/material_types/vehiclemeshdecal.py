import bpy
import os
from ..main.common import *

class VehicleMeshDecal:
    def __init__(self, BasePath,image_format, ProjPath, enableMask):
        self.BasePath = BasePath
        self.ProjPath = ProjPath
        self.enableMask = enableMask
        self.image_format = image_format

    def create(self,Data,Mat):
        CurMat = Mat.node_tree
        pBSDF = CurMat.nodes[loc('Principled BSDF')]
        sockets=bsdf_socket_names()
        pBSDF.inputs[sockets['Specular']].default_value = 0
        
        #Diffuse
        mulNode = CurMat.nodes.new("ShaderNodeMath")
        mulNode.operation = 'MULTIPLY'
        mulNode.location = (-850,350)

        backfaceGroup = CreateCullBackfaceGroup(CurMat, x = -600, y = 350,name = 'Cull Backface')

        if "DiffuseTexture" in Data:
            dcolImg=imageFromRelPath(Data["DiffuseTexture"],self.image_format,DepotPath=self.BasePath, ProjPath=self.ProjPath)
            dImgNode = create_node(CurMat.nodes,"ShaderNodeTexImage",  (-1200,400), label="DiffuseTexture", image=dcolImg)
            
            if self.enableMask:
                CurMat.links.new(dImgNode.outputs[1],mulNode.inputs[1])
                CurMat.links.new(mulNode.outputs[0],backfaceGroup.inputs[0])
                CurMat.links.new(backfaceGroup.outputs[0],pBSDF.inputs['Alpha'])
            else:
                alpha_ramp = create_node(CurMat.nodes,"ShaderNodeValToRGB", (-400,-350),label='MaskRamp')
                alpha_ramp.color_ramp.elements[1].position=0.004
                CurMat.links.new(dImgNode.outputs[0],alpha_ramp.inputs[0])
                CurMat.links.new(alpha_ramp.outputs[0],pBSDF.inputs['Alpha'])

        if "DiffuseAlpha" in Data:
            mulNode.inputs[0].default_value = float(Data["DiffuseAlpha"])
        else:
            mulNode.inputs[0].default_value = 1

        mixRGB = CurMat.nodes.new("ShaderNodeMixRGB")
        mixRGB.location = (-500,500)
        mixRGB.hide = True
        mixRGB.blend_type = 'MULTIPLY'
        mixRGB.inputs[0].default_value = 1
        if "DiffuseColor" in Data:
            dColor = CreateShaderNodeRGB(CurMat, Data["DiffuseColor"], -700, 550, "DiffuseColor")
            CurMat.links.new(dColor.outputs[0],mixRGB.inputs[1])

        CurMat.links.new(dImgNode.outputs[0],mixRGB.inputs[2])
        CurMat.links.new(mixRGB.outputs[0],pBSDF.inputs['Base Color'])

        #Normal
        if "NormalTexture" in Data:
            nMap = CreateShaderNodeNormalMap(CurMat,self.BasePath + Data["NormalTexture"],-800,-250,'NormalTexture',self.image_format)
            CurMat.links.new(nMap.outputs[0],pBSDF.inputs['Normal'])

        #Roughness
        if "RoughnessTexture" in Data:
            rImg=imageFromRelPath(Data["RoughnessTexture"],self.image_format,DepotPath=self.BasePath, ProjPath=self.ProjPath)
            rImgNode = create_node(CurMat.nodes,"ShaderNodeTexImage",  (-1200,-100), label="RoughnessTexture", image=rImg)
            CurMat.links.new(rImgNode.outputs[0],pBSDF.inputs['Roughness'])

        #Metalness
        if "MetalnessTexture" in Data:
            mImg=imageFromRelPath(Data["MetalnessTexture"],self.image_format,DepotPath=self.BasePath, ProjPath=self.ProjPath)
            mImgNode = create_node(CurMat.nodes,"ShaderNodeTexImage",  (-1200,50), label="MetalnessTexture", image=mImg)
            CurMat.links.new(mImgNode.outputs[0],pBSDF.inputs['Metallic'])

        #Unhandled Values
        if "NormalAlpha" in Data:
            norAlphaVal = CreateShaderNodeValue(CurMat, Data["NormalAlpha"], -1200,-450, "NormalAlpha")

        if "NormalsBlendingMode" in Data:
            norBlendVal = CreateShaderNodeValue(CurMat, Data["NormalsBlendingMode"], -1200,-150, "NormalsBlendingMode")

        if "RoughnessMetalnessAlpha" in Data:
            rmAlphaVal = CreateShaderNodeValue(CurMat, Data["RoughnessMetalnessAlpha"], -1200,-50, "RoughnessMetalnessAlpha")

        if "DepthThreshold" in Data:
            depThreshVal = CreateShaderNodeValue(CurMat, Data["DepthThreshold"], -1200,150, "DepthThreshold")

        if "DirtOpacity" in Data:
            dirtOpacVal = CreateShaderNodeValue(CurMat, Data["DirtOpacity"], -1200,350, "DirtOpacity")

       # if "DamageInfluence" in Data:
       #     dmgInfVal = CreateShaderNodeValue(CurMat, Data["DamageInfluence"]["Value"], -1200, 550, "DamageInfluence")

        if "UseGradientMap" in Data:
            gradMapVal = CreateShaderNodeValue(CurMat, Data["UseGradientMap"], -1200, 750, "UseGradientMap")

        if "GradientMap" in Data:
            gImg=imageFromRelPath(Data["GradientMap"],self.image_format,DepotPath=self.BasePath, ProjPath=self.ProjPath)
            gImgNode = create_node(CurMat.nodes,"ShaderNodeTexImage",  (-1200,-800), label="GradientMap", image=gImg)
            color_ramp_node=CreateGradMapRamp(CurMat, gImgNode)
            color_ramp_node.location = (0,400)
            if Data["UseGradientMap"]==1 and dImgNode:
                CurMat.links.new(dImgNode.outputs[0], color_ramp_node.inputs[0])
                CurMat.links.new(color_ramp_node.outputs[0], pBSDF.inputs['Base Color'])
            