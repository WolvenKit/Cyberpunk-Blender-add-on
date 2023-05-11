import bpy
import os
from ..main.common import *

class VehicleMeshDecal:
    def __init__(self, BasePath,image_format):
        self.BasePath = BasePath
        self.image_format = image_format
    def create(self,Data,Mat):
        CurMat = Mat.node_tree
        CurMat.nodes['Principled BSDF'].inputs['Specular'].default_value = 0

#Diffuse
        mulNode = CurMat.nodes.new("ShaderNodeMath")
        mulNode.operation = 'MULTIPLY'
        mulNode.location = (-500,450)
        if "DiffuseTexture" in Data:
            dImgNode = CreateShaderNodeTexImage(CurMat,self.BasePath + Data["DiffuseTexture"],-800,500,'DiffuseTexture',self.image_format)
            
            if "enableMask" in Data and Data["enableMask"==True]:
                CurMat.links.new(dImgNode.outputs[1],mulNode.inputs[1])
                CurMat.links.new(mulNode.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Alpha'])
            else:
                CurMat.links.new(dImgNode.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Alpha'])

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
        CurMat.links.new(mixRGB.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Base Color'])

#Normal
        if "NormalTexture" in Data:
            nMap = CreateShaderNodeNormalMap(CurMat,self.BasePath + Data["NormalTexture"],-200,-250,'NormalTexture',self.image_format)
            CurMat.links.new(nMap.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Normal'])

#Roughness
        if "RoughnessTexture" in Data:
            rImgNode = CreateShaderNodeTexImage(CurMat,self.BasePath + Data["RoughnessTexture"],-800,-100,'RoughnessTexture',self.image_format,True)
            CurMat.links.new(rImgNode.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Roughness'])

#Metalness
        if "MetalnessTexture" in Data:
            mImgNode = CreateShaderNodeTexImage(CurMat,self.BasePath + Data["MetalnessTexture"],-800,200,'MetalnessTexture',self.image_format,True)
            CurMat.links.new(mImgNode.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Metallic'])

#Unknown Values
        if "NormalAlpha" in Data:
            norAlphaVal = CreateShaderNodeValue(CurMat, Data["NormalAlpha"], -1200,-450, "NormalAlpha")

        if "NormalsBlendingMode" in Data:
            norBlendVal = CreateShaderNodeValue(CurMat, Data["NormalsBlendingMode"], -1200,-250, "NormalsBlendingMode")

        if "RoughnessMetalnessAlpha" in Data:
            rmAlphaVal = CreateShaderNodeValue(CurMat, Data["RoughnessMetalnessAlpha"], -1200,-50, "RoughnessMetalnessAlpha")

        if "DepthThreshold" in Data:
            depThreshVal = CreateShaderNodeValue(CurMat, Data["DepthThreshold"], -1200,150, "DepthThreshold")

        if "DirtOpacity" in Data:
            dirtOpacVal = CreateShaderNodeValue(CurMat, Data["DirtOpacity"], -1200,350, "DirtOpacity")

        if "DamageInfluence" in Data:
            dmgInfVal = CreateShaderNodeValue(CurMat, Data["DamageInfluence"]["Value"], -1200, 550, "DamageInfluence")

        if "UseGradientMap" in Data:
            gradMapVal = CreateShaderNodeValue(CurMat, Data["UseGradientMap"], -1200, 750, "UseGradientMap")