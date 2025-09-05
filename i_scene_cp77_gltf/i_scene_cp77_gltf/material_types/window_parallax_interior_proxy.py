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
        pBSDF=CurMat.nodes[loc('Principled BSDF')]
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
            roomWidth = CreateShaderNodeValue(CurMat,Data["roomWidth"],-1200, 100,"roomWidth")
        # roomHeight
        if 'roomHeight' in Data:
            roomHeight = CreateShaderNodeValue(CurMat,Data["roomHeight"],-1200, 150,"roomHeight")
        # roomDepth
        if 'roomDepth' in Data:
            roomDepth = CreateShaderNodeValue(CurMat,Data["roomDepth"],-1200, 200,"roomDepth")

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

        #Randomise Rooms
        WhiteNoiseTexture = create_node(CurMat.nodes,"ShaderNodeTexWhiteNoise",(-1077.558349609375, 946.2904052734375), label="White Noise Texture")
        WhiteNoiseTexture.noise_dimensions='1D'
        SeparateXYZ = create_node(CurMat.nodes,"ShaderNodeSeparateXYZ",(-1434.1156005859375, 899.5537719726562), label="Separate XYZ")
        Math = create_node(CurMat.nodes,"ShaderNodeMath",(-1245.8779296875, 950.3339233398438), operation='FLOOR', label="Math")
        Mathb = create_node(CurMat.nodes,"ShaderNodeMath",(-1245.8779296875, 930.3339233398438), operation='FLOOR', label="Mathb")
        Mathc = create_node(CurMat.nodes,"ShaderNodeMath",(-1205.8779296875, 930.3339233398438), operation='MULTIPLY', label="Mathc")
        Math002 = create_node(CurMat.nodes,"ShaderNodeMath",(-891.7330322265625, 936.3861694335938), operation='MULTIPLY', label="Math.002")
        Math002.inputs[1].default_value=5
        Math001 = create_node(CurMat.nodes,"ShaderNodeMath",(-715.7330322265625, 918.6345825195312), operation='FLOOR', label="Math.001")

       # Window properties
        if 'WindowTexture' in Data:
            wcolImg=imageFromRelPath(Data["WindowTexture"],self.image_format,DepotPath=self.BasePath, ProjPath=self.ProjPath)
            wColNode = create_node(CurMat.nodes,"ShaderNodeTexImage",  (-600,-150), label="WindowTexture", image=wcolImg)
            if 'Normal' in Data:
                wNormImg=imageFromRelPath(Data["Normal"],self.image_format,DepotPath=self.BasePath, ProjPath=self.ProjPath, isNormal=True)
                wNormNode = create_node(CurMat.nodes,"ShaderNodeTexImage",  (-600,-200), label="Normal", image=wNormImg)
            if 'NormalStrength' in Data:
                NormalStrength = CreateShaderNodeValue(CurMat,Data["NormalStrength"],-600, -250,"NormalStrength")
            if 'Roughness' in Data:
                wRoughImg=imageFromRelPath(Data["Roughness"],self.image_format,DepotPath=self.BasePath, ProjPath=self.ProjPath, isNormal=True)
                wRoughNode = create_node(CurMat.nodes,"ShaderNodeTexImage",  (-600,-300), label="Roughness", image=wRoughImg)


        CurMat.links.new(UV.outputs['UV'], SeparateXYZ.inputs[0])
        CurMat.links.new(SeparateXYZ.outputs['X'], Math.inputs[0])
        CurMat.links.new(SeparateXYZ.outputs['Y'], Mathb.inputs[0])
        CurMat.links.new(Math.outputs['Value'], Mathc.inputs[0])
        CurMat.links.new(Mathb.outputs['Value'], Mathc.inputs[1])
        CurMat.links.new(Mathc.outputs['Value'], WhiteNoiseTexture.inputs[1])
        CurMat.links.new(WhiteNoiseTexture.outputs['Value'], Math002.inputs[0])
        CurMat.links.new(Math002.outputs['Value'], Math001.inputs[0])
        CurMat.links.new(Math001.outputs['Value'], flipbook.inputs[1])
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


        

       # stuff in room 
        #LayerAtlas
        #LayerDepth

        


