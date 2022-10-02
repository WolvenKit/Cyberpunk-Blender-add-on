import bpy
import os
from ..main.common import *

class Signages:
    def __init__(self, BasePath,image_format):
        self.BasePath = BasePath
        self.image_format = image_format
    def create(self,Data,Mat):
        CurMat = Mat.node_tree
        CurMat.nodes['Principled BSDF'].inputs['Specular'].default_value = 0
        print('Creating neon sign')
        if "ColorOneStart" in Data:
            dCol = CreateShaderNodeRGB(CurMat, Data["ColorOneStart"], -800, 250, "ColorOneStart")    
        else:
            dCol = CreateShaderNodeRGB(CurMat,{'Red': 255, 'Green': 255, 'Blue': 255, 'Alpha': 255}, -800, 250, "ColorOneStart")
        CurMat.links.new(dCol.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Base Color'])
          
        alphaNode = CurMat.nodes.new("ShaderNodeMath")
        alphaNode.operation = 'MULTIPLY'
        alphaNode.location = (-300, -250)
        if "DiffuseAlpha" in Data:
            aThreshold = CreateShaderNodeValue(CurMat, Data["DiffuseAlpha"], -550, -400, "DiffuseAlpha")
            CurMat.links.new(aThreshold.outputs[0],alphaNode.inputs[1])
        else:
            alphaNode.inputs[1].default_value = 1

        mulNode = CurMat.nodes.new("ShaderNodeMixRGB")
        mulNode.inputs[0].default_value = 0.5
        mulNode.blend_type = 'MULTIPLY'
        mulNode.location = (-300, -50)
        CurMat.links.new(dCol.outputs[0],mulNode.inputs[1])

        if "MainTexture" in Data:
            emTexNode = CreateShaderNodeTexImage(CurMat, self.BasePath + Data["MainTexture"], -700, -250,'MainTexture',self.image_format)
            CurMat.links.new(emTexNode.outputs[0],mulNode.inputs[2])
            CurMat.links.new(emTexNode.outputs[1],alphaNode.inputs[0])


        CurMat.links.new(alphaNode.outputs[0], CurMat.nodes['Principled BSDF'].inputs['Alpha'])
        CurMat.links.new(mulNode.outputs[0], CurMat.nodes['Principled BSDF'].inputs['Emission'])
        
        if "EmissiveEV" in Data:
            CurMat.nodes['Principled BSDF'].inputs['Emission Strength'].default_value =  Data["EmissiveEV"]*10

        if "Roughness" in Data:
            CurMat.nodes['Principled BSDF'].inputs['Roughness'].default_value =  Data["Roughness"]

        if "FresnelAmount" in Data:   
            CurMat.nodes['Principled BSDF'].inputs['Specular'].default_value =  Data["FresnelAmount"]
        
        if "ColorOneStart" in Data:
            dCol = CreateShaderNodeRGB(CurMat, Data["ColorOneStart"], -850, 250, "ColorOneStart")    

        if "ColorTwo" in Data:
            dCol = CreateShaderNodeRGB(CurMat, Data["ColorTwo"], -900, 250, "ColorTwo")    

        if "ColorThree" in Data:
            dCol = CreateShaderNodeRGB(CurMat, Data["ColorThree"], -950, 250, "ColorThree")    

        if "ColorFour" in Data:
            dCol = CreateShaderNodeRGB(CurMat, Data["ColorFour"], -1000, 250, "ColorFour")    
                    
        if "ColorFive" in Data:
            dCol = CreateShaderNodeRGB(CurMat, Data["ColorFive"], -1050, 250, "ColorFive")  
        
        if "ColorSix" in Data:
            dCol = CreateShaderNodeRGB(CurMat, Data["ColorSix"], -1100, 250, "ColorSix")
