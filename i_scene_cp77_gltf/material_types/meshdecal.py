import bpy
import os
from ..main.common import *

class MeshDecal:
    def __init__(self, BasePath,image_format, ProjPath, enableMask):
        self.BasePath = BasePath
        self.ProjPath = ProjPath
        self.enableMask = enableMask
        self.img_format = image_format

    def create(self,Data,Mat):
        CurMat = Mat.node_tree
        Ns=CurMat.nodes
        CurMat.nodes['Principled BSDF'].inputs['Specular'].default_value = 0

#Diffuse
        mixRGB = CurMat.nodes.new("ShaderNodeMixRGB")
        mixRGB.location = (-500,500)
        mixRGB.hide = True
        mixRGB.blend_type = 'MULTIPLY'
        mixRGB.inputs[0].default_value = 1
        CurMat.links.new(mixRGB.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Base Color'])

        mulNode =create_node(Ns, "ShaderNodeMath", (-500,450), operation = 'MULTIPLY')
        if "DiffuseAlpha" in Data:
            mulNode.inputs[0].default_value = float(Data["DiffuseAlpha"])
        else:
            mulNode.inputs[0].default_value = 1


        dTexMapping = CurMat.nodes.new("ShaderNodeMapping")
        dTexMapping.label = "UVMapping"
        dTexMapping.location = (-1000,300)

        if "DiffuseTexture" in Data:
            dImg=imageFromRelPath(Data["DiffuseTexture"],DepotPath=self.BasePath, ProjPath=self.ProjPath, image_format=self.img_format)
            
            dImgNode = create_node(Ns,"ShaderNodeTexImage",  (-800,500), label="DiffuseTexture", image=dImg)
            CurMat.links.new(dTexMapping.outputs[0],dImgNode.inputs[0])
            CurMat.links.new(dImgNode.outputs[0],mixRGB.inputs[2])
            CurMat.links.new(dImgNode.outputs[1],mulNode.inputs[0])

        if "UVOffsetX" in Data:
            dTexMapping.inputs[1].default_value[0] = Data["UVOffsetX"]
        if "UVOffsetY" in Data:
            dTexMapping.inputs[1].default_value[1] = Data["UVOffsetY"]
        if "UVRotation" in Data:
            dTexMapping.inputs[2].default_value[0] = Data["UVRotation"]
            dTexMapping.inputs[2].default_value[1] = Data["UVRotation"]
        if "UVScaleX" in Data:
            dTexMapping.inputs[3].default_value[0] = Data["UVScaleX"]
        if "UVScaleY" in Data:
            dTexMapping.inputs[3].default_value[1] = Data["UVScaleY"]

        UVNode = create_node(Ns,"ShaderNodeTexCoord", (-1200,300))
        CurMat.links.new(UVNode.outputs[2],dTexMapping.inputs[0])

        CurMat.links.new(mulNode.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Alpha'])

        if "DiffuseColor" in Data:
            dColor = CreateShaderNodeRGB(CurMat, Data["DiffuseColor"], -800, 650, "DiffuseColor")
            Gamma = create_node(Ns,"ShaderNodeGamma",  (-600,600), label="Gamma")
            Gamma.inputs[1].default_value = 2.2
            
            CurMat.links.new(dColor.outputs[0],Gamma.inputs[0])
            CurMat.links.new(Gamma.outputs[0],mixRGB.inputs[1])

        if "NormalTexture" in Data:
            nMap = CreateShaderNodeNormalMap(CurMat,self.BasePath + Data["NormalTexture"],-200,-250,'NormalTexture',self.img_format)
            CurMat.links.new(nMap.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Normal'])

        if "NormalAlpha" in Data:
            norAlphaVal = CreateShaderNodeValue(CurMat, Data["NormalAlpha"], -1200,-450, "NormalAlpha")

        if "NormalAlphaTex" in Data:
            nAImg=imageFromRelPath(Data["NormalAlphaTex"],DepotPath=self.BasePath, ProjPath=self.ProjPath, image_format=self.img_format)            
            nAImgNode = create_node(Ns,"ShaderNodeTexImage",  (-1200,-500), label="NormalAlphaTex", image=nAImg)

        mulNode1 =  create_node(Ns,"ShaderNodeMath", (-500,-100), operation = 'MULTIPLY')
        if "RoughnessScale" in Data:
            mulNode1.inputs[0].default_value = float(Data["RoughnessScale"])
        else:
            mulNode1.inputs[0].default_value = 1
      
        CurMat.links.new(mulNode1.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Roughness'])
        if "RoughnessTexture" in Data:
            rImg=imageFromRelPath(Data["RoughnessTexture"],DepotPath=self.BasePath, ProjPath=self.ProjPath, image_format=self.img_format)            
            rImgNode = create_node(Ns,"ShaderNodeTexImage",  (-800,-100), label="RoughnessTexture", image=rImg)
            CurMat.links.new(rImgNode.outputs[0],mulNode1.inputs[1])


        mulNode2 = create_node(Ns,"ShaderNodeMath",(-500,200),operation = 'MULTIPLY')
        if "MetalnessScale" in Data:
            mulNode2.inputs[0].default_value = float(Data["MetalnessScale"])
        else:
            mulNode2.inputs[0].default_value = 1
        
        CurMat.links.new(mulNode2.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Metallic'])
        if "MetalnessTexture" in Data:
            mImg=imageFromRelPath(Data["MetalnessTexture"],DepotPath=self.BasePath, ProjPath=self.ProjPath, image_format=self.img_format)            
            mImgNode = create_node(Ns,"ShaderNodeTexImage",  (-800,200), label="MetalnessTexture", image=mImg)
            CurMat.links.new(mImgNode.outputs[0],mulNode2.inputs[1])