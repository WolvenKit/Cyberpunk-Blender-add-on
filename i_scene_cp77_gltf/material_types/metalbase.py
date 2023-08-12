import bpy
import os
from ..main.common import *

class MetalBase:
    def __init__(self, BasePath,image_format, ProjPath):
        self.BasePath = BasePath
        self.ProjPath = ProjPath
        self.image_format = image_format
    def create(self,Data,Mat):
        CurMat = Mat.node_tree

        CurMat.nodes['Principled BSDF'].inputs['Specular'].default_value = 0

        mixRGB = create_node(CurMat.nodes,"ShaderNodeMixRGB", (-200,200) , blend_type = 'MULTIPLY')
        mixRGB.inputs[0].default_value = 1
        CurMat.links.new(mixRGB.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Base Color'])

        if "BaseColor" in Data:
            bcolImg=imageFromRelPath(Data["BaseColor"],self.image_format,DepotPath=self.BasePath, ProjPath=self.ProjPath)
            bColNode = create_node(CurMat.nodes,"ShaderNodeTexImage",  (-800,-450), label="BaseColor", image=bcolImg)
            CurMat.links.new(bColNode.outputs[0],mixRGB.inputs[2])
            CurMat.links.new(bColNode.outputs[1],CurMat.nodes['Principled BSDF'].inputs['Alpha'])

        if "Metalness" in Data:
            mImg=imageFromRelPath(Data["Metalness"],self.image_format,DepotPath=self.BasePath, ProjPath=self.ProjPath)
            metNode = create_node(CurMat.nodes,"ShaderNodeTexImage",  (-800,-550), label="Metalness", image=mImg)
            CurMat.links.new(metNode.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Metallic'])

        if 'MetalnessScale' in Data:
            mScale = CreateShaderNodeValue(CurMat,Data["MetalnessScale"],-1000, -100,"MetalnessScale")

        if 'MetalnessBias' in Data:
            mBias = CreateShaderNodeValue(CurMat,Data["MetalnessBias"],-1000, -200,"MetalnessBias")

        if "Roughness" in Data:
            rImg=imageFromRelPath(Data["Roughness"],self.image_format,DepotPath=self.BasePath, ProjPath=self.ProjPath)
            rNode = create_node(CurMat.nodes,"ShaderNodeTexImage",  (-800,-650), label="Roughness", image=rImg)
            CurMat.links.new(rNode.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Roughness'])
        
        if 'RoughnessScale' in Data:
            rScale = CreateShaderNodeValue(CurMat,Data["RoughnessScale"],-1000, -300,"RoughnessScale")

        if 'RoughnesssBias' in Data:
            rBias = CreateShaderNodeValue(CurMat,Data["RoughnesssBias"],-1000, -400,"MetalnessBias")

        if "BaseColorScale" in Data:
            dColScale = CreateShaderNodeRGB(CurMat, Data["BaseColorScale"],-700,500,'BaseColorScale',True)
            CurMat.links.new(dColScale.outputs[0],mixRGB.inputs[1])


        if "AlphaThreshold" in Data:
            aThreshold = CreateShaderNodeValue(CurMat,Data["AlphaThreshold"],-1000, 280,"AlphaThreshold")
            CurMat.links.new(aThreshold.outputs[0],mixRGB.inputs[0])

        if "Normal" in Data:
            nMap = CreateShaderNodeNormalMap(CurMat,self.BasePath + Data["Normal"],-200,-300,'Normal',self.image_format)
            CurMat.links.new(nMap.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Normal'])


        mulNode = CurMat.nodes.new("ShaderNodeMixRGB")
        mulNode.inputs[0].default_value = 1
        mulNode.blend_type = 'MULTIPLY'
        mulNode.location = (-450,100)

        if "EmissiveColor" in Data:
            emColor = CreateShaderNodeRGB(CurMat, Data["EmissiveColor"],-700,150,"EmissiveColor")
            CurMat.links.new(emColor.outputs[0],mulNode.inputs[1])

        if "Emissive" in Data:
            EmImg=imageFromRelPath(Data["Emissive"],self.image_format, DepotPath=self.BasePath, ProjPath=self.ProjPath)
            emTexNode =create_node(CurMat.nodes,"ShaderNodeTexImage",  (-800,100), label="Emissive", image=EmImg)
            CurMat.links.new(emTexNode.outputs[0],mulNode.inputs[2])

        CurMat.links.new(mulNode.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Emission'])

        if "EmissiveEV" in Data:
            CurMat.nodes['Principled BSDF'].inputs['Emission Strength'].default_value =  Data["EmissiveEV"]-1 # everything is blown out and emmisive otherwise.

used_params=['BaseColor',
 'BaseColorScale',
 'Metalness',
 'Roughness',
 'Normal',
 'AlphaThreshold',
 'MetalnessScale',
 'MetalnessBias',
 'RoughnessScale',
 'RoughnessBias',
 'NormalStrength',
 'Emissive',
 'EmissiveLift',
 'EmissiveEV',
 'EmissiveEVRaytracingBias',
 'EmissiveDirectionality',
 'EnableRaytracedEmissive',
 'EmissiveColor',
 'LayerTile',
 'VehicleDamageInfluence']