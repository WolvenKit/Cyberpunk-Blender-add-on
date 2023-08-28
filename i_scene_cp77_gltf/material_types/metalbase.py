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
        pBSDF = CurMat.nodes['Principled BSDF']
        mixRGB = create_node(CurMat.nodes,"ShaderNodeMixRGB", (-450,400) , blend_type = 'MULTIPLY')
        mixRGB.inputs[0].default_value = 1
        CurMat.links.new(mixRGB.outputs[0],pBSDF.inputs['Base Color'])

        if "BaseColor" in Data:
            bcolImg=imageFromRelPath(Data["BaseColor"],self.image_format,DepotPath=self.BasePath, ProjPath=self.ProjPath)
            bColNode = create_node(CurMat.nodes,"ShaderNodeTexImage",  (-800,-450), label="BaseColor", image=bcolImg)
            CurMat.links.new(bColNode.outputs[0],mixRGB.inputs[2])
        
        if "BaseColorScale" in Data:
            dColScale = CreateShaderNodeRGB(CurMat, Data["BaseColorScale"],-700,500,'BaseColorScale',True)
            CurMat.links.new(dColScale.outputs[0],mixRGB.inputs[1])    

        if "Metalness" in Data:
            mImg=imageFromRelPath(Data["Metalness"],self.image_format,DepotPath=self.BasePath, ProjPath=self.ProjPath)
            metNode = create_node(CurMat.nodes,"ShaderNodeTexImage",  (-800,-550), label="Metalness", image=mImg)
            CurMat.links.new(metNode.outputs[0],pBSDF.inputs['Metallic'])

        if 'MetalnessScale' in Data:
            mScale = CreateShaderNodeValue(CurMat,Data["MetalnessScale"],-1000, -100,"MetalnessScale")

        if 'MetalnessBias' in Data:
            mBias = CreateShaderNodeValue(CurMat,Data["MetalnessBias"],-1000, -200,"MetalnessBias")

        if "Roughness" in Data:
            rImg=imageFromRelPath(Data["Roughness"],self.image_format,DepotPath=self.BasePath, ProjPath=self.ProjPath)
            rNode = create_node(CurMat.nodes,"ShaderNodeTexImage",  (-800,-650), label="Roughness", image=rImg)
            CurMat.links.new(rNode.outputs[0],pBSDF.inputs['Roughness'])
            invr = create_node(CurMat.nodes,"ShaderNodeInvert",(-280., 90.))
            CurMat.links.new(rNode.outputs[0],invr.inputs['Color'])
            CurMat.links.new(invr.outputs[0],pBSDF.inputs['Specular'])
        
        if 'RoughnessScale' in Data:
            rScale = CreateShaderNodeValue(CurMat,Data["RoughnessScale"],-1000, -300,"RoughnessScale")

        if 'RoughnesssBias' in Data:
            rBias = CreateShaderNodeValue(CurMat,Data["RoughnesssBias"],-1000, -400,"RoughnesssBias")

        if "AlphaThreshold" in Data:
            aThreshold = CreateShaderNodeValue(CurMat,Data["AlphaThreshold"],-1000, 280,"AlphaThreshold")
        else:
            aThreshold = CreateShaderNodeValue(CurMat,1.0,-1000, 280,"AlphaThreshold")

        alphclamp = create_node(CurMat.nodes,"ShaderNodeClamp",(-740, 330))
        CurMat.links.new(aThreshold.outputs[0],alphclamp.inputs['Max'])
        CurMat.links.new(bColNode.outputs[1],alphclamp.inputs['Value'])
        
        Clamp2 = create_node(CurMat.nodes,"ShaderNodeClamp",(-538., 476.))
        CurMat.links.new(alphclamp.outputs[0],Clamp2.inputs['Value'])
        CurMat.links.new(dColScale.outputs[0],Clamp2.inputs['Min'])
        CurMat.links.new(Clamp2.outputs[0],mixRGB.inputs['Fac'])
        

        if "Normal" in Data:
            nMap = CreateShaderNodeNormalMap(CurMat,self.BasePath + Data["Normal"],-200,-300,'Normal',self.image_format)
            CurMat.links.new(nMap.outputs[0],pBSDF.inputs['Normal'])


        mulNode = CurMat.nodes.new("ShaderNodeMixRGB")
        mulNode.inputs[0].default_value = 1
        mulNode.blend_type = 'MULTIPLY'
        mulNode.location = (-450,0)

        if "EmissiveColor" in Data:
            emColor = CreateShaderNodeRGB(CurMat, Data["EmissiveColor"],-700,50,"EmissiveColor")
            CurMat.links.new(emColor.outputs[0],mulNode.inputs[1])

        if "Emissive" in Data:
            EmImg=imageFromRelPath(Data["Emissive"],self.image_format, DepotPath=self.BasePath, ProjPath=self.ProjPath)
            emTexNode =create_node(CurMat.nodes,"ShaderNodeTexImage",  (-800,0), label="Emissive", image=EmImg)
            CurMat.links.new(emTexNode.outputs[0],mulNode.inputs[2])

        CurMat.links.new(mulNode.outputs[0],pBSDF.inputs['Emission'])

        if "EmissiveEV" in Data:
            pBSDF.inputs['Emission Strength'].default_value =  Data["EmissiveEV"]-1 # everything is blown out and emmisive otherwise.

        #Setup a value node for the enableMask flag that turns off the alpha when 0 (false) and on when 1
        EnableMask = create_node(CurMat.nodes,"ShaderNodeValue",(-800., -800.), label="EnableMask")
        EnableMask.outputs[0].default_value=1

        Math = create_node(CurMat.nodes,"ShaderNodeMath",(-500., -750.), operation='SUBTRACT', label="Math")
        Math.inputs[0].default_value=1
        
        Clamp001 = create_node(CurMat.nodes,"ShaderNodeClamp",(-200., -450.), label="Clamp.001")
        
        CurMat.links.new(EnableMask.outputs['Value'], Math.inputs[1]) # Enablemask value into math which inverts it
        CurMat.links.new(Math.outputs['Value'], Clamp001.inputs[1]) # Inverted value into clamp min, so if 1 its always solic, if 0 will use BaseColor alpha
        CurMat.links.new(bColNode.outputs['Alpha'], Clamp001.inputs[0]) # alpha into one thats clamped by enableMask value        
        CurMat.links.new(Clamp001.outputs['Result'], pBSDF.inputs['Alpha'])

        



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