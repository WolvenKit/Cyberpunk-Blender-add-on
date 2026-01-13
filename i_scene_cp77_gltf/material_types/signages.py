import bpy
import os
from ..main.common import *

class Signages:
    def __init__(self, BasePath,image_format, ProjPath):
        self.BasePath = BasePath
        self.ProjPath = ProjPath
        self.image_format = image_format
    
    def create(self,Data,Mat):
        CurMat = Mat.node_tree
        pBSDF=CurMat.nodes[loc('Principled BSDF')]
        sockets=bsdf_socket_names()
        pBSDF.inputs[sockets['Specular']].default_value = 0
        print('Creating neon sign')
        if "ColorOneStart" in Data:
            dCol = CreateShaderNodeRGB(CurMat, Data["ColorOneStart"], -800, 250, "ColorOneStart")    
        else:
            dCol = CreateShaderNodeRGB(CurMat,{'Red': 255, 'Green': 255, 'Blue': 255, 'Alpha': 255}, -800, 250, "ColorOneStart")
          
        alphaNode = create_node(CurMat.nodes,"ShaderNodeMath", (-300, -250) ,operation = 'MULTIPLY')
                                
        if "DiffuseAlpha" in Data:
            aThreshold = CreateShaderNodeValue(CurMat, Data["DiffuseAlpha"], -550, -400, "DiffuseAlpha")
            CurMat.links.new(aThreshold.outputs[0],alphaNode.inputs[1])
        else:
            alphaNode.inputs[1].default_value = 1

        mulNode = CurMat.nodes.new("ShaderNodeMixRGB")
        mulNode.inputs[0].default_value = 1
        mulNode.blend_type = 'MULTIPLY'
        mulNode.location = (-300, -50)
        CurMat.links.new(dCol.outputs[0],mulNode.inputs[1])

        if "MainTexture" in Data:
            dImg = imageFromRelPath(Data["MainTexture"],self.image_format, DepotPath=self.BasePath, ProjPath=self.ProjPath)
            emTexNode = create_node(CurMat.nodes,"ShaderNodeTexImage",  (-700,-250), label="MainTexture", image=dImg)
            CurMat.links.new(emTexNode.outputs[0],mulNode.inputs[2])
            CurMat.links.new(emTexNode.outputs[1],alphaNode.inputs[0])


        CurMat.links.new(alphaNode.outputs[0], pBSDF.inputs['Alpha'])
        CurMat.links.new(mulNode.outputs[0], pBSDF.inputs['Base Color'])
        CurMat.links.new(mulNode.outputs[0], pBSDF.inputs[sockets['Emission']])
        
        if "EmissiveEV" in Data:
            pBSDF.inputs['Emission Strength'].default_value =  Data["EmissiveEV"]*10

        if "Roughness" in Data:
            pBSDF.inputs['Roughness'].default_value =  Data["Roughness"]

        if "FresnelAmount" in Data:   
            pBSDF.inputs[sockets['Specular']].default_value =  Data["FresnelAmount"]
        
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
