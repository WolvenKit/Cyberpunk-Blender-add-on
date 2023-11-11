import bpy
import os
from ..main.common import *

class windowParallaxIntProx:
    def __init__(self, BasePath,image_format, ProjPath):
        self.BasePath = BasePath
        self.ProjPath = ProjPath
        self.image_format = image_format
    def create(self,Data,Mat):
        CurMat = Mat.node_tree
        pBSDF=CurMat.nodes['Principled BSDF']


       # RoomAtlas
        if "RoomAtlas" in Data:
            bcolImg=imageFromRelPath(Data["RoomAtlas"],self.image_format,DepotPath=self.BasePath, ProjPath=self.ProjPath)
            bColNode = create_node(CurMat.nodes,"ShaderNodeTexImage",  (-600,450), label="RoomAtlas", image=bcolImg)
            CurMat.links.new(bColNode.outputs[0],pBSDF.inputs['Base Color'])
       
       # AtlasGridUvRatio
       # roomWidth
        if 'roomWidth' in Data:
            roomWidth = CreateShaderNodeValue(CurMat,Data["roomWidth"],-800, -100,"roomWidth")
       # roomHeight
        if 'roomHeight' in Data:
            mScale = CreateShaderNodeValue(CurMat,Data["roomHeight"],-8000, -200,"roomHeight")
       # roomDepth
        if 'roomDepth' in Data:
            mScale = CreateShaderNodeValue(CurMat,Data["roomDepth"],-800, -300,"roomDepth")

        par=createParallaxGroup()     
       # LightsTempVariationAtNight
       # AmountTurnOffAtNight
       # TintColorAtNight
       # EmissiveEV
       # positionXoffset
       # positionYoffset
       # AtlasDepth       
       # scaleXrandomization
       # positionXrandomization
       # EmissiveEVRaytracingBias
       # EmissiveDirectionality
       # EnableRaytracedEmissive
       # ColorOverlayTexture
       # Curtain
       # CurtainDepth
       # CurtainMaxCover
       # CurtainCoverRandomize
       # CurtainAlpha