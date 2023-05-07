import bpy
import os
from ..main.common import *

class Decal:
    def __init__(self, BasePath,image_format):
        self.BasePath = BasePath
        self.image_format = image_format

    def create(self,Data,Mat):
        for i in range(len(Data["values"])):
            for value in Data["values"][i]:
               # print(value)
                if value == "DiffuseTexture":
                    difftex = Data["values"][i]["DiffuseTexture"]["DepotPath"]
                    #print(f"Diffuse Texture path is:  {difftex}")

        CurMat = Mat.node_tree
        CurMat.nodes['Principled BSDF'].inputs['Specular'].default_value = 0
        if os.path.exists(self.BasePath + difftex):
            dImgNode = CreateShaderNodeTexImage(CurMat,self.BasePath + difftex,-800,500,'DiffuseTexture',self.image_format)
            CurMat.links.new(dImgNode.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Base Color'])
           # CurMat.links.new(dImgNode.outputs[1],CurMat.nodes['Principled BSDF'].inputs['Alpha'])
            mulNode1 = CurMat.nodes.new("ShaderNodeMath")
            mulNode1.operation = 'MULTIPLY'
            mulNode1.location = (-600,500)
            mulNode1.inputs[0].default_value = float(Data["alpha"])
            CurMat.links.new(dImgNode.outputs[1],mulNode1.inputs[1])
            CurMat.links.new(mulNode1.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Alpha'])

        else:
            CurMat.nodes['Principled BSDF'].inputs['Alpha'].default_value = 0
            print(f"Texture is not found: {difftex}")