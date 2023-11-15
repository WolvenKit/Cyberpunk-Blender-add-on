import bpy
import os
from ..main.common import *
from .interior_mapping_nodegroups import *
import re

class windowParallaxIntProx:
    def __init__(self, BasePath,image_format, ProjPath):
        self.BasePath = BasePath
        self.ProjPath = ProjPath
        self.image_format = image_format
    def create(self,Data,Mat):
        CurMat = Mat.node_tree
        pBSDF=CurMat.nodes['Principled BSDF']
        CurMat.nodes.remove(pBSDF)
        AspectRatio=1
        # Aspect ratios is in the filename
        if "RoomAtlas" in Data:
            pattern = r'_[0-9]x[0-9]_'
            matches = re.findall(pattern, Data["RoomAtlas"])[0]
            AspectRatio = int(matches[1])/int(matches[3])
            AspectRatioVal = CreateShaderNodeValue(CurMat,AspectRatio,-1300, 400,"AspectRatio")
            

        # RoomAtlas
        if "RoomAtlas" in Data:
            bcolImg=imageFromRelPath(Data["RoomAtlas"],self.image_format,DepotPath=self.BasePath, ProjPath=self.ProjPath)
            bColNode = create_node(CurMat.nodes,"ShaderNodeTexImage",  (-600,450), label="RoomAtlas", image=bcolImg)
            
       
        # AtlasGridUvRatio
        # roomWidth
        if 'roomWidth' in Data:
            roomWidth = CreateShaderNodeValue(CurMat,Data["roomWidth"],-800, -100,"roomWidth")
        # roomHeight
        if 'roomHeight' in Data:
            roomHeight = CreateShaderNodeValue(CurMat,Data["roomHeight"],-8000, -200,"roomHeight")
        # roomDepth
        if 'roomDepth' in Data:
            roomDepth = CreateShaderNodeValue(CurMat,Data["roomDepth"],-800, -300,"roomDepth")

        par=createParallaxGroup() 
        AW_Int_Map = andrew_willmotts_plane_interior_mapping_node_group()
        InteriorMapping = create_node(CurMat.nodes,"ShaderNodeGroup", (-1130,620),hide=False)
        InteriorMapping.node_tree = AW_Int_Map
        InteriorMapping.name = "Interior Mapping"
        
        # input doenst like values =>1 need to work out what the dimension of this value is
        #AW_Int_Map.inputs[1].default_value=Data["roomDepth"]

       #Just need to populate this and it works.
        #AW_Int_Map.inputs[4].default_value=AspectRatio
        CurMat.links.new(AspectRatioVal.outputs[0],InteriorMapping.inputs[4])


        flip=flipbook_function_node_group()    
        flipbook = create_node(CurMat.nodes,"ShaderNodeGroup", (-910,575),hide=False)
        flipbook.node_tree = flip
        flipbook.name = "RoomAtlas"
        
        noCols=bcolImg.size[0]/(bcolImg.size[1]*AspectRatio)
        noColsVal = CreateShaderNodeValue(CurMat,noCols,-1100, 250,"NoImages")        
        CurMat.links.new(noColsVal.outputs[0],flipbook.inputs[3])    
        CurMat.links.new(noColsVal.outputs[0],flipbook.inputs[4])

        UV=create_node(CurMat.nodes,"ShaderNodeUVMap",(-1650, 670))
        Vec_Frac=create_node(CurMat.nodes,"ShaderNodeVectorMath",(-1545, 448), operation='FRACTION')
        CurMat.links.new(UV.outputs[0],Vec_Frac.inputs[0])
        CurMat.links.new(Vec_Frac.outputs[0],InteriorMapping.inputs[0])
        CurMat.links.new(InteriorMapping.outputs[0],flipbook.inputs[0])
        CurMat.links.new(flipbook.outputs[0],bColNode.inputs[0])
        CurMat.links.new(bColNode.outputs[0],CurMat.nodes['Material Output'].inputs[0])
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
    