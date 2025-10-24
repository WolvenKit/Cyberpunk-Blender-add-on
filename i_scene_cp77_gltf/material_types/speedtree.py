import bpy
import os
from ..main.common import *


class SpeedTree:
    def __init__(self, BasePath,image_format, ProjPath):
        self.BasePath = BasePath
        self.ProjPath = ProjPath
        self.image_format = image_format
    def create(self,Data,Mat):
        CurMat = Mat.node_tree
        pBSDF=CurMat.nodes[loc('Principled BSDF')]
        sockets=bsdf_socket_names()
        pBSDF.inputs[sockets['Specular']].default_value = 0.5
        
        #Diffuse       
        dTexMapping = CurMat.nodes.new("ShaderNodeMapping")
        dTexMapping.label = "UVMapping"
        dTexMapping.location = (-1000,300)

        if "DiffuseMap" in Data:
            dImg = imageFromRelPath(Data["DiffuseMap"],self.image_format, DepotPath=self.BasePath, ProjPath=self.ProjPath)
            dImgNode = create_node(CurMat.nodes,"ShaderNodeTexImage",  (-800,400), label="DiffuseTexture", image=dImg)
            CurMat.links.new(dTexMapping.outputs[0],dImgNode.inputs[0])
            CurMat.links.new(dImgNode.outputs[0],pBSDF.inputs['Base Color'])
            CurMat.links.new(dImgNode.outputs[1],pBSDF.inputs['Alpha'])
            dImgNode.hide=False
        
        if "BaseColor" in Data:
            dImg = imageFromRelPath(Data["BaseColor"],self.image_format, DepotPath=self.BasePath, ProjPath=self.ProjPath)
            dImgNode = create_node(CurMat.nodes,"ShaderNodeTexImage",  (-800,400), label="DiffuseTexture", image=dImg)
            CurMat.links.new(dTexMapping.outputs[0],dImgNode.inputs[0])
            CurMat.links.new(dImgNode.outputs[0],pBSDF.inputs['Base Color'])
            CurMat.links.new(dImgNode.outputs[1],pBSDF.inputs['Alpha'])
            dImgNode.hide=False

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

        UVNode = create_node(CurMat.nodes,"ShaderNodeTexCoord",(-1200,300))
        CurMat.links.new(UVNode.outputs[2],dTexMapping.inputs[0])

        if "NormalMap" in Data:
            nMap = CreateShaderNodeNormalMap(CurMat,self.BasePath + Data["NormalMap"],-300,-350,'NormalMap',self.image_format)
            CurMat.links.new(nMap.outputs[0],pBSDF.inputs['Normal'])
            nMap.inputs[1].links[0].from_node.inputs[0].links[0].from_node.hide=False
            nMap.inputs[1].links[0].from_node.inputs[0].links[0].from_node.location = (-800,-200)
        
        if "Normal" in Data:
            nMap = CreateShaderNodeNormalMap(CurMat,self.BasePath + Data["Normal"],-300,-350,'NormalMap',self.image_format)
            CurMat.links.new(nMap.outputs[0],pBSDF.inputs['Normal'])
            nMap.inputs[1].links[0].from_node.inputs[0].links[0].from_node.hide=False
            nMap.inputs[1].links[0].from_node.inputs[0].links[0].from_node.location = (-800,-200)

        if "TransGlossMap" in Data:
            rImg = imageFromRelPath(Data["TransGlossMap"],self.image_format, DepotPath=self.BasePath, ProjPath=self.ProjPath, isNormal=True)
            rImgNode = create_node(CurMat.nodes,"ShaderNodeTexImage",  (-800,100), label="TransGlossMap", image=rImg, hide = False)
            
            mathNode = create_node(CurMat.nodes,"ShaderNodeMath",(-400,100), operation='SUBTRACT', label="Math")
            mathNode.inputs[0].default_value = 1.0
            CurMat.links.new(rImgNode.outputs[0],mathNode.inputs[1])
            CurMat.links.new(mathNode.outputs[0],pBSDF.inputs['Roughness'])
            
        if "Roughness" in Data:
            rImg = imageFromRelPath(Data["Roughness"],self.image_format, DepotPath=self.BasePath, ProjPath=self.ProjPath, isNormal=True)
            rImgNode = create_node(CurMat.nodes,"ShaderNodeTexImage",  (-800,100), label="TransGlossMap", image=rImg, hide = False)
            
            mathNode = create_node(CurMat.nodes,"ShaderNodeMath",(-400,100), operation='SUBTRACT', label="Math")
            mathNode.inputs[0].default_value = 1.0
            CurMat.links.new(rImgNode.outputs[0],mathNode.inputs[1])
            CurMat.links.new(mathNode.outputs[0],pBSDF.inputs['Roughness'])