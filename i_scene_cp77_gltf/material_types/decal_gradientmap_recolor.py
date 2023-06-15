import bpy
import os
from ..main.common import *

class DecalGradientmapRecolor:
    def __init__(self, BasePath,image_format):
        self.BasePath = BasePath
        self.image_format = image_format


    def found(self,tex):
        result = os.path.exists(self.BasePath + tex)
        if not result:
            print(f"Texture not found: {tex}")
        return result

    def create(self,Data,Mat):
        masktex=''
        diffAsMask = 0

        for i in range(len(Data["values"])):
            for value in Data["values"][i]:
                #print(value)
                if value == "DiffuseTexture":
                    difftex = Data["values"][i]["DiffuseTexture"]["DepotPath"]
                   # print(f"Diffuse Texture path is:  {difftex}")
                if value == "GradientMap":
                    gradmap = Data["values"][i]["GradientMap"]["DepotPath"]
                if value == "MaskTexture":
                    masktex = Data["values"][i]["MaskTexture"]["DepotPath"]
                if value == "DiffuseTextureAsMaskTexture":
                    diffAsMask = Data["values"][i]["DiffuseTextureAsMaskTexture"]

        CurMat = Mat.node_tree
        if self.found(difftex) and self.found(gradmap):
            dImgNode = CreateShaderNodeTexImage(CurMat,self.BasePath + difftex,-800,500,'DiffuseTexture',self.image_format)
            gImgNode = CreateShaderNodeTexImage(CurMat,self.BasePath + gradmap,-800,400,'GradientMap',self.image_format)  
            CurMat.links.new(dImgNode.outputs[0],gImgNode.inputs[0])
            CurMat.links.new(gImgNode.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Base Color'])
            mulNode1 = CurMat.nodes.new("ShaderNodeMath")
            mulNode1.operation = 'MULTIPLY'
            mulNode1.location = (-600,500)
            mulNode1.inputs[0].default_value = float(Data["alpha"])
            if diffAsMask:
                CurMat.links.new(dImgNode.outputs[0],mulNode1.inputs[1])
                CurMat.links.new(mulNode1.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Alpha'])
                #CurMat.links.new(dImgNode.outputs[1],CurMat.nodes['Principled BSDF'].inputs['Alpha'])
            else:
                if self.found(masktex):
                    aImgNode = CreateShaderNodeTexImage(CurMat,self.BasePath + masktex,-800,300,'MaskTexture',self.image_format)
                    #CurMat.links.new(aImgNode.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Alpha'])
                    CurMat.links.new(aImgNode.outputs[0],mulNode1.inputs[1])
                    CurMat.links.new(mulNode1.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Alpha'])
                else:
                    colorRamp = CurMat.nodes.new(type="ShaderNodeValToRGB")
                    colorRamp.location = (-600,500)
                    colorRamp.color_ramp.elements[1].position = (0.001)
                    invert = CurMat.nodes.new(type="ShaderNodeInvert")
                    invert.location = (-400, 500)
                    invert.inputs[0].default_value = 0
                    CurMat.links.new(colorRamp.outputs[0],invert.inputs[1])
                    #CurMat.links.new(invert.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Alpha'])
                    CurMat.links.new(invert.outputs[0],mulNode1.inputs[1])
                    CurMat.links.new(mulNode1.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Alpha'])
                    CurMat.links.new(dImgNode.outputs[1],colorRamp.inputs[0])


                   #CurMat.links.new(dImgNode.outputs[1],CurMat.nodes['Principled BSDF'].inputs['Alpha'])
        else:
            CurMat.nodes['Principled BSDF'].inputs['Alpha'].default_value = 0



