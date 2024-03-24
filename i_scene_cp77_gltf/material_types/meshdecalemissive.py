import bpy
import os
from ..main.common import *

class MeshDecalEmissive:
    def __init__(self, BasePath,image_format, ProjPath):
        self.BasePath = BasePath
        self.ProjPath = ProjPath
        self.image_format = image_format

    def create(self,Data,Mat):
        CurMat = Mat.node_tree
        pBSDF = CurMat.nodes[loc('Principled BSDF')]
        sockets=bsdf_socket_names()
        pBSDF.inputs[sockets['Specular']].default_value = 0

        if "DiffuseColor2" in Data:
            dCol2 = CreateShaderNodeRGB(CurMat, Data["DiffuseColor2"], -160, 200, "DiffuseColor2")
            CurMat.links.new(dCol2.outputs[0],pBSDF.inputs['Base Color'])

        alphaNode = CurMat.nodes.new("ShaderNodeMath")
        alphaNode.operation = 'MULTIPLY'
        alphaNode.location = (-300, -250)
        if "DiffuseAlpha" in Data:
            aThreshold = CreateShaderNodeValue(CurMat, Data["DiffuseAlpha"], -550, -400, "DiffuseAlpha")
            CurMat.links.new(aThreshold.outputs[0],alphaNode.inputs[1])
        else:
            alphaNode.inputs[1].default_value = 1

        mulNode = CurMat.nodes.new("ShaderNodeMixRGB")
        mulNode.inputs[0].default_value = 1
        mulNode.blend_type = 'MULTIPLY'
        mulNode.location = (-300, -50)
        if "DiffuseColor" in Data:
            emColor = CreateShaderNodeRGB(CurMat, Data["DiffuseColor"], -550, -100, "DiffuseColor")
            CurMat.links.new(emColor.outputs[0],mulNode.inputs[1])

        if "DiffuseTexture" in Data:
            emImg = imageFromRelPath(Data["DiffuseTexture"],self.image_format, DepotPath=self.BasePath, ProjPath=self.ProjPath)
            emTexNode = create_node(CurMat.nodes,"ShaderNodeTexImage",  (-700,-250), label="DiffuseTexture", image=emImg)
            CurMat.links.new(emTexNode.outputs[0],mulNode.inputs[2])
            CurMat.links.new(emTexNode.outputs[1],alphaNode.inputs[0])

        CurMat.links.new(mulNode.outputs[0], pBSDF.inputs[sockets['Emission']])
        CurMat.links.new(alphaNode.outputs[0], pBSDF.inputs['Alpha'])

        if "EmissiveEV" in Data:
            pBSDF.inputs['Emission Strength'].default_value =  Data["EmissiveEV"]