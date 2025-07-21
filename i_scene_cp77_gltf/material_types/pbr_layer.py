import bpy
import os
from ..main.common import *

class pbr_layer:
    def __init__(self, BasePath,image_format, ProjPath):
        self.BasePath = BasePath
        self.ProjPath = ProjPath
        self.image_format = image_format
    def create(self,Data,Mat):
        CurMat = Mat.node_tree
        pBSDF = CurMat.nodes[loc('Principled BSDF')]

        # TEXTURES
        if "Diffuse" in Data:
            diffImg=imageFromRelPath(Data["Diffuse"],self.image_format,DepotPath=self.BasePath, ProjPath=self.ProjPath)
            diffNode = create_node(CurMat.nodes,"ShaderNodeTexImage",  (-900,100), label="BaseColor", image=diffImg)

        if "Mask" in Data:
            MaskImg=imageFromRelPath(Data["Mask"],self.image_format,DepotPath=self.BasePath, ProjPath=self.ProjPath)
            MaskNode = create_node(CurMat.nodes,"ShaderNodeTexImage",  (-900,0), label="Mask", image=MaskImg) 

        if "RoughMetalBlend" in Data:
            rmbImg=imageFromRelPath(Data["RoughMetalBlend"],self.image_format,DepotPath=self.BasePath, ProjPath=self.ProjPath)
            rmbNode = create_node(CurMat.nodes,"ShaderNodeTexImage",  (-900,-250), label="RoughnessMetalBlend", image=rmbImg)

        if "Normal" in Data:
            nImg = imageFromPath(self.BasePath + Data["Normal"],self.image_format, True)
            nNode = create_node(CurMat.nodes,"ShaderNodeTexImage",  (-900,-400), label="Normal", image=nImg)            

        


        nMap = create_node(CurMat.nodes,"ShaderNodeNormalMap",  (-200,-250))   
        NRG = CreateRebildNormalGroup(CurMat, -350, -250, "DetailNormal Rebuilt")
        CurMat.links.new(nNode.outputs[0],NRG.inputs[0])
        CurMat.links.new(NRG.outputs[0],nMap.inputs[1])
        

        
        # final links
        CurMat.links.new(diffNode.outputs[0],pBSDF.inputs['Base Color'])
        if "RoughMetalBlend" in Data:
            CurMat.links.new(rmbNode.outputs[0],pBSDF.inputs['Roughness'])
            CurMat.links.new(rmbNode.outputs[0],pBSDF.inputs['Metallic'])
        CurMat.links.new(nMap.outputs[0],pBSDF.inputs['Normal'])
