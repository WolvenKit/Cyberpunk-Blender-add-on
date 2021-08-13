import bpy
import os
from ..main.common import imageFromPath

class VehicleMeshDecal:
    def __init__(self, BasePath,image_format):
        self.BasePath = BasePath
        self.image_format = image_format
    def create(self,Decal,Mat):

        CurMat = Mat.node_tree
        CurMat.nodes['Principled BSDF'].inputs['Specular'].default_value = 0


#Diffuse
        dImg = imageFromPath(self.BasePath + Decal["DiffuseTexture"],self.image_format)
            
        dImgNode = CurMat.nodes.new("ShaderNodeTexImage")
        dImgNode.location = (-800,500)
        dImgNode.image = dImg
        dImgNode.label = "DiffuseTexture"


        mulNode = CurMat.nodes.new("ShaderNodeMath")
        mulNode.inputs[0].default_value = float(Decal["DiffuseAlpha"])
        if(mulNode.inputs[0].default_value == 0):
            mulNode.inputs[0].default_value = 1
        mulNode.operation = 'MULTIPLY'
        mulNode.location = (-500,450)

        CurMat.links.new(dImgNode.outputs[1],mulNode.inputs[1])
        CurMat.links.new(mulNode.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Alpha'])


        dColor = CurMat.nodes.new("ShaderNodeRGB")
        dColor.location = (-700,550)
        dColor.hide = True
        dColor.label = "DiffuseColor"
        dColor.outputs[0].default_value = (float(Decal["DiffuseColor"]["Red"])/255,float(Decal["DiffuseColor"]["Green"])/255,float(Decal["DiffuseColor"]["Blue"])/255,float(Decal["DiffuseColor"]["Alpha"])/255)

        mixRGB = CurMat.nodes.new("ShaderNodeMixRGB")
        mixRGB.location = (-500,500)
        mixRGB.hide = True
        mixRGB.blend_type = 'MULTIPLY'
        mixRGB.inputs[0].default_value = 1

        CurMat.links.new(dImgNode.outputs[0],mixRGB.inputs[2])
        CurMat.links.new(dColor.outputs[0],mixRGB.inputs[1])
        CurMat.links.new(mixRGB.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Base Color'])


#Normal
        nImg = imageFromPath(self.BasePath + Decal["NormalTexture"],self.image_format,True)
            
        nImgNode = CurMat.nodes.new("ShaderNodeTexImage")
        nImgNode.location = (-800,-400)
        nImgNode.image = nImg
        nImgNode.label = "NormalTexture"

        nRgbCurve = CurMat.nodes.new("ShaderNodeRGBCurve")
        nRgbCurve.location = (-500,-400)
        nRgbCurve.hide = True
        nRgbCurve.mapping.curves[2].points[0].location = (0,1)
        nRgbCurve.mapping.curves[2].points[1].location = (1,1)
            
        CurMat.links.new(nImgNode.outputs[0],nRgbCurve.inputs[0])

            
        nMap = CurMat.nodes.new("ShaderNodeNormalMap")
        nMap.location = (-200,-250)
        nMap.hide = True

        CurMat.links.new(nRgbCurve.outputs[0],nMap.inputs[1])
        CurMat.links.new(nMap.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Normal'])


#Roughness
        rImg = imageFromPath(self.BasePath + Decal["RoughnessTexture"],self.image_format,True)
            
        rImgNode = CurMat.nodes.new("ShaderNodeTexImage")
        rImgNode.location = (-800,-100)
        rImgNode.image = rImg
        rImgNode.label = "RoughnessTexture"

        CurMat.links.new(rImgNode.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Roughness'])


#Metalness
        mImg = imageFromPath(self.BasePath + Decal["MetalnessTexture"],self.image_format,True)
            
        mImgNode = CurMat.nodes.new("ShaderNodeTexImage")
        mImgNode.location = (-800,200)
        mImgNode.image = mImg
        mImgNode.label = "MetalnessTexture"

        CurMat.links.new(mImgNode.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Metallic'])


#Unknown Values
        norAlphaVal = CurMat.nodes.new("ShaderNodeValue")
        norAlphaVal.location = (-1200,-450)
        norAlphaVal.outputs[0].default_value = float(Decal["NormalAlpha"])
        norAlphaVal.hide = True
        norAlphaVal.label = "NormalAlpha"


        norBlendVal = CurMat.nodes.new("ShaderNodeValue")
        norBlendVal.location = (-1200,-250)
        norBlendVal.outputs[0].default_value = float(Decal["NormalsBlendingMode"])
        norBlendVal.hide = True
        norBlendVal.label = "NormalsBlendingMode"

        rmAlphaVal = CurMat.nodes.new("ShaderNodeValue")
        rmAlphaVal.location = (-1200,-50)
        rmAlphaVal.outputs[0].default_value = float(Decal["RoughnessMetalnessAlpha"])
        rmAlphaVal.hide = True
        rmAlphaVal.label = "RoughnessMetalnessAlpha"

        depThreshVal = CurMat.nodes.new("ShaderNodeValue")
        depThreshVal.location = (-1200,150)
        depThreshVal.outputs[0].default_value = float(Decal["DepthThreshold"])
        depThreshVal.hide = True
        depThreshVal.label = "DepthThreshold"

        dirtOpacVal = CurMat.nodes.new("ShaderNodeValue")
        dirtOpacVal.location = (-1200,350)
        dirtOpacVal.outputs[0].default_value = float(Decal["DirtOpacity"])
        dirtOpacVal.hide = True
        dirtOpacVal.label = "DirtOpacity"

        dmgInfVal = CurMat.nodes.new("ShaderNodeValue")
        dmgInfVal.location = (-1200,550)
        dmgInfVal.outputs[0].default_value = float(Decal["DamageInfluence"])
        dmgInfVal.hide = True
        dmgInfVal.label = "DamageInfluence"

        gradMapVal = CurMat.nodes.new("ShaderNodeValue")
        gradMapVal.location = (-1200,750)
        gradMapVal.outputs[0].default_value = float(Decal["UseGradientMap"])
        gradMapVal.hide = True
        gradMapVal.label = "UseGradientMap"