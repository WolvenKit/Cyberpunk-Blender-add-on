import bpy
import os
from io_scene_gltf2.io.imp.gltf2_io_gltf import glTFImporter
from io_scene_gltf2.blender.imp.gltf2_blender_gltf import BlenderGlTF
filepath = "C:\\Users\\Abhinav\\Desktop\\w_handgun__malorian_silverhand__base1_01.glb"
gltf_importer = glTFImporter(filepath, { "files": None, "loglevel": 0, "import_pack_images" :True, "merge_vertices" :False, "import_shading" : 'NORMALS', "bone_heuristic":'TEMPERANCE', "guess_original_bind_pose" : False})
gltf_importer.read()
gltf_importer.checks()

#Index = len(bpy.data.meshes.keys())
#BlenderGlTF.create(gltf_importer)
#print(bpy.data.meshes.keys())
#print(Index)
#
#print(len(bpy.data.meshes.keys()))
#y = gltf_importer.data.meshes[0].extras
#print(y["appNames"][0])
obj = gltf_importer.data.extras
valueToIgnore = float(obj["valueToBeIgnored"])
BasePath = os.path.splitext(filepath)[0] + "_Textures\\"

def imageFromPath(Img,isNormal = False):
    Im = bpy.data.images.get(os.path.basename(Img)[:-4])
    if not Im:
        Im = bpy.data.images.new(os.path.basename(Img)[:-4],1,1)
        Im.source = "FILE"
        Im.filepath = Img[:-3]+"png"
        if isNormal:
            Im.colorspace_settings.name = 'Non-Color'
    return Im
def createBaseMaterial(matTemplateObj,BasePath):
    CT = imageFromPath(BasePath + matTemplateObj["colorTexture"])
    NT = imageFromPath(BasePath + matTemplateObj["normalTexture"],isNormal = True)
    RT = imageFromPath(BasePath + matTemplateObj["roughnessTexture"])
    MT = imageFromPath(BasePath + matTemplateObj["metalnessTexture"])
    
    TileMult = float(matTemplateObj["tilingMultiplier"])
    if TileMult == valueToIgnore:
        TileMult = 1
    NG = bpy.data.node_groups.new(matTemplateObj["name"][:-11],"ShaderNodeTree")
    TMI = NG.inputs.new('NodeSocketVector','Tile Multiplier')
    TMI.default_value = (1,1,1)
    NG.outputs.new('NodeSocketColor','Difuse')
    NG.outputs.new('NodeSocketColor','Normal')
    NG.outputs.new('NodeSocketColor','Roughness')
    NG.outputs.new('NodeSocketColor','Metallic')
    
    CTN = NG.nodes.new("ShaderNodeTexImage")
    CTN.hide = True
    CTN.image = CT
    
    NTN = NG.nodes.new("ShaderNodeTexImage")
    NTN.hide = True
    NTN.image = NT
    NTN.location[1] = -45*1
    
    RTN = NG.nodes.new("ShaderNodeTexImage")
    RTN.hide = True
    RTN.image = RT
    RTN.location[1] = -45*2
    
    MTN = NG.nodes.new("ShaderNodeTexImage")
    MTN.hide = True
    MTN.image = MT
    MTN.location[1] = -45*3
    
    MapN = NG.nodes.new("ShaderNodeMapping")
    MapN.hide = True
    MapN.location = (-310,-64)
    
    TexCordN = NG.nodes.new("ShaderNodeTexCoord")
    TexCordN.hide = True
    TexCordN.location = (-500,-64)
    
    TileMultN = NG.nodes.new("ShaderNodeValue")
    TileMultN.location = (-700,-45*2)
    TileMultN.hide = True
    TileMultN.outputs[0].default_value = TileMult
    
    GroupInN = NG.nodes.new("NodeGroupInput")
    GroupInN.location = (-700,-45*4)
    GroupInN.hide = True
    
    GroupOutN = NG.nodes.new("NodeGroupOutput")
    GroupOutN.hide=True
    GroupOutN.location = (400,0)
    
    VecMathN = NG.nodes.new("ShaderNodeVectorMath")
    VecMathN.hide=True
    VecMathN.location = (-500,-45*3)
    VecMathN.operation = 'MULTIPLY'
    
    NormSepN = NG.nodes.new("ShaderNodeSeparateRGB")
    NormSepN.hide=True
    
    NormCombN = NG.nodes.new("ShaderNodeCombineRGB")
    NormCombN.hide=True
    NormCombN.location = (100,0)
    NormCombN.inputs[2].default_value = 1
    
    NG.links.new(TexCordN.outputs['UV'],MapN.inputs['Vector'])
    NG.links.new(VecMathN.outputs[0],MapN.inputs['Scale'])
    NG.links.new(MapN.outputs['Vector'],CTN.inputs['Vector'])
    NG.links.new(MapN.outputs['Vector'],NTN.inputs['Vector'])
    NG.links.new(MapN.outputs['Vector'],RTN.inputs['Vector'])
    NG.links.new(MapN.outputs['Vector'],MTN.inputs['Vector'])
    NG.links.new(TileMultN.outputs[0],VecMathN.inputs[0])
    NG.links.new(GroupInN.outputs[0],VecMathN.inputs[1])
    NG.links.new(CTN.outputs[0],GroupOutN.inputs[0])
    NG.links.new(NTN.outputs[0],NormSepN.inputs[0])
    NG.links.new(RTN.outputs[0],GroupOutN.inputs[2])
    NG.links.new(MTN.outputs[0],GroupOutN.inputs[3])
    NG.links.new(NormSepN.outputs[0],NormCombN.inputs[0])
    NG.links.new(NormSepN.outputs[1],NormCombN.inputs[1])
    NG.links.new(NormCombN.outputs[0],GroupOutN.inputs[1])
    
    return

def createOverrideTable(matTemplateObj):
    OverList = matTemplateObj["overrides"]
    Output = {}
    Output["ColorScale"] = {}
    Output["NormalStrength"] = {}
    Output["RoughLevelsOut"] = {}
    Output["MetalLevelsOut"] = {}
    for x in OverList["colorScale"]:
        tmpName = x["n"]
        tmpR = float(x["v"][0])
        tmpG = float(x["v"][1])
        tmpB = float(x["v"][2])
        Output["ColorScale"][tmpName] = (tmpR,tmpG,tmpB,1)
    for x in OverList["normalStrength"]:
        tmpName = x["n"]
        tmpStrength = float(x["v"][0])
        Output["NormalStrength"][tmpName] = tmpStrength
    for x in OverList["roughLevelsOut"]:
        tmpName = x["n"]
        tmpStrength0 = float(x["v"][0])
        tmpStrength1 = float(x["v"][1])
        Output["RoughLevelsOut"][tmpName] = [(tmpStrength0,tmpStrength0,tmpStrength0,1),(tmpStrength1,tmpStrength1,tmpStrength1,1)]
    for x in OverList["metalLevelsOut"]:
        tmpName = x["n"]
        if float(x["v"][0]) != valueToIgnore :
            tmpStrength0 = float(x["v"][0])
            tmpStrength1 = float(x["v"][1])
        else:
            tmpStrength0 = 0
            tmpStrength1 = 1
        Output["MetalLevelsOut"][tmpName] = [(tmpStrength0,tmpStrength0,tmpStrength0,1),(tmpStrength1,tmpStrength1,tmpStrength1,1)]
    return Output

def setGlobNormal(normalimgpath,CurMat,input):
    GNN = CurMat.nodes.new("ShaderNodeVectorMath")
    GNN.location = (-200,-250)
    GNN.operation = 'NORMALIZE'
    GNN.hide = True
    
    GNA = CurMat.nodes.new("ShaderNodeVectorMath")
    GNA.location = (-400,-250)
    GNA.operation = 'ADD'
    GNA.hide = True
    
    GNS = CurMat.nodes.new("ShaderNodeVectorMath")
    GNS.location = (-600,-250)
    GNS.operation = 'SUBTRACT'
    GNS.hide = True
    
    GNGeo = CurMat.nodes.new("ShaderNodeNewGeometry")
    GNGeo.location = (-800,-250)
    GNGeo.hide = True
    
    GNMap = CurMat.nodes.new("ShaderNodeNormalMap")
    GNMap.location = (-600,-350)
    GNMap.hide = True
    
    GNComRGB = CurMat.nodes.new("ShaderNodeCombineRGB")
    GNComRGB.location = (-600,-450)
    GNComRGB.hide = True
    
    GNSepRGB = CurMat.nodes.new("ShaderNodeSeparateRGB")
    GNSepRGB.location = (-800,-450)
    GNSepRGB.hide = True
    
    GNImg = imageFromPath(normalimgpath,True)
    
    GNImgNode = CurMat.nodes.new("ShaderNodeTexImage")
    GNImgNode.image = GNImg
    GNImgNode.location = (-900,-550)
    GNImgNode.hide = True

    CurMat.links.new(GNImgNode.outputs[0],GNSepRGB.inputs[0])
    CurMat.links.new(GNSepRGB.outputs[0],GNComRGB.inputs[0])
    CurMat.links.new(GNSepRGB.outputs[1],GNComRGB.inputs[1])
    GNComRGB.inputs[2].default_value = 1
    CurMat.links.new(GNComRGB.outputs[0],GNMap.inputs[1])
    CurMat.links.new(GNGeo.outputs['Normal'],GNS.inputs[1])
    CurMat.links.new(GNMap.outputs[0],GNS.inputs[0])
    CurMat.links.new(GNS.outputs[0],GNA.inputs[1])
    CurMat.links.new(input,GNA.inputs[0])
    CurMat.links.new(GNA.outputs[0],GNN.inputs[0])
    return GNN.outputs[0]

def createLayerMaterial(LayerName,LayerCount,CurMat,mlmaskpath,normalimgpath):
    for x in range(LayerCount-1):
        MaskTexture = imageFromPath(os.path.splitext(mlmaskpath)[0]+"_"+str(x+1)+".png")
        NG = bpy.data.node_groups.new("Layer_Blend_"+str(x),"ShaderNodeTree")#create layer's node group
        NG.inputs.new('NodeSocketColor','Difuse1')
        NG.inputs.new('NodeSocketColor','Normal1')
        NG.inputs.new('NodeSocketColor','Roughness1')
        NG.inputs.new('NodeSocketColor','Metallic1')
        NG.inputs.new('NodeSocketColor','Difuse2')
        NG.inputs.new('NodeSocketColor','Normal2')
        NG.inputs.new('NodeSocketColor','Roughness2')
        NG.inputs.new('NodeSocketColor','Metallic2')
        NG.inputs.new('NodeSocketColor','Mask')
        NG.outputs.new('NodeSocketColor','Difuse')
        NG.outputs.new('NodeSocketColor','Normal')
        NG.outputs.new('NodeSocketColor','Roughness')
        NG.outputs.new('NodeSocketColor','Metallic')
        
        GroupInN = NG.nodes.new("NodeGroupInput")
        GroupInN.location = (-700,0)
        GroupInN.hide = True
        
        GroupOutN = NG.nodes.new("NodeGroupOutput")
        GroupOutN.hide=True
        GroupOutN.location = (200,0)
        
        ColorMixN = NG.nodes.new("ShaderNodeMixRGB")
        ColorMixN.hide=True
        ColorMixN.location = (-300,100)
        ColorMixN.label = "Color Mix"
        
        NormalMixN = NG.nodes.new("ShaderNodeMixRGB")
        NormalMixN.hide=True
        NormalMixN.location = (-300,50)
        NormalMixN.label = "Normal Mix"
        
        RoughMixN = NG.nodes.new("ShaderNodeMixRGB")
        RoughMixN.hide=True
        RoughMixN.location = (-300,0)
        RoughMixN.label = "Rough Mix"
        
        MetalMixN = NG.nodes.new("ShaderNodeMixRGB")
        MetalMixN.hide=True
        MetalMixN.location = (-300,-50)
        MetalMixN.label = "Metal Mix"

        LayerGroupN = CurMat.nodes.new("ShaderNodeGroup")
        LayerGroupN.location = (-1400,450-100*x)
        LayerGroupN.hide = True
        LayerGroupN.node_tree = NG
        LayerGroupN.name = "Layer_"+str(x)
        
        MaskN = CurMat.nodes.new("ShaderNodeTexImage")
        MaskN.hide = True
        MaskN.image = MaskTexture
        MaskN.location = (-2100,450-100*x)
        #if self.flipMaskY:
        MaskN.texture_mapping.scale[1] = -1 #flip mask if needed
        MaskN.label="Layer_"+str(x+1)
        
        MaskOpacN = CurMat.nodes.new("ShaderNodeMixRGB")
        MaskOpacN.hide = True
        MaskOpacN.location = (-1800,450-100*x)
        MaskOpacN.inputs[0].default_value = 1
        MaskOpacN.blend_type = "MULTIPLY"
        MaskOpacN.label = "Opacity"
        
        
        if x == 0:
            CurMat.links.new(CurMat.nodes["Mat_Mod_Layer_"+"0"].outputs[0],LayerGroupN.inputs[0])
            CurMat.links.new(CurMat.nodes["Mat_Mod_Layer_"+"0"].outputs[1],LayerGroupN.inputs[1])
            CurMat.links.new(CurMat.nodes["Mat_Mod_Layer_"+"0"].outputs[2],LayerGroupN.inputs[2])
            CurMat.links.new(CurMat.nodes["Mat_Mod_Layer_"+"0"].outputs[3],LayerGroupN.inputs[3])
            CurMat.links.new(CurMat.nodes["Mat_Mod_Layer_"+"1"].outputs[0],LayerGroupN.inputs[4])
            CurMat.links.new(CurMat.nodes["Mat_Mod_Layer_"+"1"].outputs[1],LayerGroupN.inputs[5])
            CurMat.links.new(CurMat.nodes["Mat_Mod_Layer_"+"1"].outputs[2],LayerGroupN.inputs[6])
            CurMat.links.new(CurMat.nodes["Mat_Mod_Layer_"+"1"].outputs[3],LayerGroupN.inputs[7])
        else:
            CurMat.links.new(CurMat.nodes["Layer_"+str(x-1)].outputs[0],LayerGroupN.inputs[0])
            CurMat.links.new(CurMat.nodes["Layer_"+str(x-1)].outputs[1],LayerGroupN.inputs[1])
            CurMat.links.new(CurMat.nodes["Layer_"+str(x-1)].outputs[2],LayerGroupN.inputs[2])
            CurMat.links.new(CurMat.nodes["Layer_"+str(x-1)].outputs[3],LayerGroupN.inputs[3])
            CurMat.links.new(CurMat.nodes["Mat_Mod_Layer_"+str(x+1)].outputs[0],LayerGroupN.inputs[4])
            CurMat.links.new(CurMat.nodes["Mat_Mod_Layer_"+str(x+1)].outputs[1],LayerGroupN.inputs[5])
            CurMat.links.new(CurMat.nodes["Mat_Mod_Layer_"+str(x+1)].outputs[2],LayerGroupN.inputs[6])
            CurMat.links.new(CurMat.nodes["Mat_Mod_Layer_"+str(x+1)].outputs[3],LayerGroupN.inputs[7])
        CurMat.links.new(MaskN.outputs[0],MaskOpacN.inputs[1])
        CurMat.links.new(CurMat.nodes["Mat_Mod_Layer_"+str(x+1)].outputs[4],MaskOpacN.inputs[2])
        CurMat.links.new(MaskOpacN.outputs[0],CurMat.nodes["Layer_"+str(x)].inputs[8])
            
        NG.links.new(GroupInN.outputs[0],ColorMixN.inputs[1])
        NG.links.new(GroupInN.outputs[1],NormalMixN.inputs[1])
        NG.links.new(GroupInN.outputs[2],RoughMixN.inputs[1])
        NG.links.new(GroupInN.outputs[3],MetalMixN.inputs[1])
        NG.links.new(GroupInN.outputs[4],ColorMixN.inputs[2])
        NG.links.new(GroupInN.outputs[5],NormalMixN.inputs[2])
        NG.links.new(GroupInN.outputs[6],RoughMixN.inputs[2])
        NG.links.new(GroupInN.outputs[7],MetalMixN.inputs[2])
        NG.links.new(GroupInN.outputs[8],ColorMixN.inputs[0])
        NG.links.new(GroupInN.outputs[8],NormalMixN.inputs[0])
        NG.links.new(GroupInN.outputs[8],RoughMixN.inputs[0])
        NG.links.new(GroupInN.outputs[8],MetalMixN.inputs[0])
        
        NG.links.new(ColorMixN.outputs[0],GroupOutN.inputs[0])
        NG.links.new(NormalMixN.outputs[0],GroupOutN.inputs[1])
        NG.links.new(RoughMixN.outputs[0],GroupOutN.inputs[2])
        NG.links.new(MetalMixN.outputs[0],GroupOutN.inputs[3])
        
    CurMat.links.new(CurMat.nodes["Layer_"+str(LayerCount-2)].outputs[0],CurMat.nodes['Principled BSDF'].inputs['Base Color'])
    yoink = setGlobNormal(normalimgpath,CurMat,CurMat.nodes["Layer_"+str(LayerCount-2)].outputs[1])
    CurMat.links.new(yoink,CurMat.nodes['Principled BSDF'].inputs['Normal'])
    CurMat.links.new(CurMat.nodes["Layer_"+str(LayerCount-2)].outputs[2],CurMat.nodes['Principled BSDF'].inputs['Roughness'])
    CurMat.links.new(CurMat.nodes["Layer_"+str(LayerCount-2)].outputs[3],CurMat.nodes['Principled BSDF'].inputs['Metallic'])
    return


def create(obj,mlsetup,mlmaskpath,Mat,normalimgpath):
    mltemplates = []
    xllay = mlsetup["layers"]
    LayerCount = len(xllay)
    
    LayerIndex = 0
    CurMat = Mat.node_tree
    for x in (xllay):            
        MatTile = x["matTile"]
        MbTile = x.get("mbTile")
        MbScale = float(MbTile)
        
        Microblend = x["microblend"]
        MicroblendContrast = x["microblendContrast"]
        microblendNormalStrength = x.get("microblendNormalStrength")
        opacity = x.get("opacity")
        material = x.get("material")
        colorScale = x.get("colorScale")
        normalStrength = x.get("normalStrength")
        #roughLevelsIn = x["roughLevelsIn"]
        roughLevelsOut = x.get("roughLevelsOut")
        #metalLevelsIn = x["metalLevelsIn"]
        metalLevelsOut = x.get("metalLevelsOut")
        
        if Microblend != "null":
            MBI = imageFromPath(BasePath+Microblend[:-3]+"png",True)
        
        cowunter = 0    
        for i in range(0,len(obj["materialTemplates"])):
            if os.path.basename(material) == obj["materialTemplates"][i]["name"]:
                cowunter = i
        OverrideTable = createOverrideTable(obj["materialTemplates"][cowunter])#get override info for colors and what not

        NG = bpy.data.node_groups.new(mlsetup["name"][:-8]+"_Layer_"+str(LayerIndex),"ShaderNodeTree")#create layer's node group
        NG.outputs.new('NodeSocketColor','Difuse')
        NG.outputs.new('NodeSocketColor','Normal')
        NG.outputs.new('NodeSocketColor','Roughness')
        NG.outputs.new('NodeSocketColor','Metallic')
        NG.outputs.new('NodeSocketColor','Opacity')
            
        LayerGroupN = CurMat.nodes.new("ShaderNodeGroup")
        LayerGroupN.location = (-2000,500-100*LayerIndex)
        LayerGroupN.hide = True
        LayerGroupN.width = 400
        LayerGroupN.node_tree = NG
        LayerGroupN.name = "Mat_Mod_Layer_"+str(LayerIndex)
        LayerIndex += 1
        
        GroupOutN = NG.nodes.new("NodeGroupOutput")
        GroupOutN.hide=True
        GroupOutN.location = (0,0)
        
        BaseMat = bpy.data.node_groups.get(os.path.basename(material[:-11]))
        if BaseMat:
            BMN = NG.nodes.new("ShaderNodeGroup")
            BMN.location = (-2000,0)
            BMN.hide = True
            BMN.node_tree = BaseMat
        
        OpacN = NG.nodes.new("ShaderNodeValue")
        OpacN.hide=True
        OpacN.location = (-200,-10)
        OpacN.outputs[0].default_value = 1
        if opacity != valueToIgnore:
            OpacN.outputs[0].default_value = float(opacity)
        
        TileMultN = NG.nodes.new("ShaderNodeValue")
        TileMultN.location = (-2200,0)
        TileMultN.hide = True
        if MatTile != "null":
            TileMultN.outputs[0].default_value = float(MatTile)
        else:
            TileMultN.outputs[0].default_value = 1
            
        if colorScale != "null":
            ColorScaleN = NG.nodes.new("ShaderNodeRGB")
            ColorScaleN.hide=True
            ColorScaleN.location=(-2000,-45)
            ColorScaleN.outputs[0].default_value = OverrideTable["ColorScale"][colorScale]
            #add color info shit here
               
            ColorScaleMixN = NG.nodes.new("ShaderNodeMixRGB")
            ColorScaleMixN.hide=True
            ColorScaleMixN.location=(-1800,0)
            ColorScaleMixN.inputs[0].default_value=1
            ColorScaleMixN.blend_type='MULTIPLY'

        GeoN = NG.nodes.new("ShaderNodeNewGeometry")
        GeoN.hide=True
        GeoN.location=(-1960.0, -200.0)
        
        NormSubN = NG.nodes.new("ShaderNodeVectorMath")
        NormSubN.hide=True
        NormSubN.location = (-1780.0, -200.0)
        NormSubN.operation = 'SUBTRACT'
                
        MBN = NG.nodes.new("ShaderNodeTexImage")
        MBN.hide = True
        MBN.image = MBI
        MBN.location = (-1800,-100)
        MBN.label = "Microblend"
        MBN.texture_mapping.scale = (MbScale,MbScale,MbScale)
        
        MBNormStrengthN = NG.nodes.new("ShaderNodeNormalMap")
        MBNormStrengthN.hide = True
        MBNormStrengthN.location = (-1500,-100)
        if microblendNormalStrength:
            MBNormStrengthN.inputs[0].default_value = float(microblendNormalStrength)
            
        NormStrengthN = NG.nodes.new("ShaderNodeNormalMap")
        NormStrengthN.hide = True
        NormStrengthN.location = (-1800,-150)
        NormStrengthN.inputs[0].default_value = OverrideTable["NormalStrength"][normalStrength]
        
        RoughRampN = NG.nodes.new("ShaderNodeMapRange")
        RoughRampN.hide=True
        RoughRampN.location = (-1800,-250)
        RoughRampN.inputs['To Min'].default_value = (OverrideTable["RoughLevelsOut"][roughLevelsOut][1][0])
        RoughRampN.inputs['To Max'].default_value = (OverrideTable["RoughLevelsOut"][roughLevelsOut][0][0])
        RoughRampN.label = "Roughness Ramp"
            
        RoughRamp2N = NG.nodes.new("ShaderNodeMapRange")
        RoughRamp2N.hide=True
        RoughRamp2N.location = (-1500,-250)
        RoughRamp2N.inputs['From Max'].default_value = 0.5
        RoughRamp2N.label = "Roughness Ramp 2"
                
        MetalRampN = NG.nodes.new("ShaderNodeValToRGB")
        MetalRampN.hide=True
        MetalRampN.location = (-1800,-300)
        MetalRampN.color_ramp.elements[1].color = (OverrideTable["MetalLevelsOut"][metalLevelsOut][0])
        MetalRampN.color_ramp.elements[0].color = (OverrideTable["MetalLevelsOut"][metalLevelsOut][1])
        MetalRampN.label = "Metal Ramp"
        
        NormalCombineN = NG.nodes.new("ShaderNodeVectorMath")
        NormalCombineN.hide = True
        NormalCombineN.location = (-1500,-150)
            
        NormalizeN = NG.nodes.new("ShaderNodeVectorMath")
        NormalizeN.hide = True
        NormalizeN.location = (-1300,-150)
        NormalizeN.operation = 'NORMALIZE'
        
            
        NG.links.new(TileMultN.outputs[0],BMN.inputs[0])
        NG.links.new(BMN.outputs[0],ColorScaleMixN.inputs[1])
        NG.links.new(ColorScaleN.outputs[0],ColorScaleMixN.inputs[2])
        NG.links.new(BMN.outputs[1],NormStrengthN.inputs[1])
        NG.links.new(MBN.outputs[0],MBNormStrengthN.inputs[1])
        NG.links.new(BMN.outputs[2],RoughRampN.inputs[0])
        NG.links.new(BMN.outputs[3],MetalRampN.inputs[0])
        NG.links.new(RoughRampN.outputs[0],RoughRamp2N.inputs[0])
        NG.links.new(RoughRamp2N.outputs[0],GroupOutN.inputs[2])
        NG.links.new(MetalRampN.outputs[0],GroupOutN.inputs[3])
        NG.links.new(NormStrengthN.outputs[0],NormalCombineN.inputs[0])
        NG.links.new(MBNormStrengthN.outputs[0],NormSubN.inputs[0])
        NG.links.new(GeoN.outputs['Normal'],NormSubN.inputs[1])
        NG.links.new(NormSubN.outputs[0],NormalCombineN.inputs[1])
        NG.links.new(NormalCombineN.outputs[0],NormalizeN.inputs[0])
        NG.links.new(NormalizeN.outputs[0],GroupOutN.inputs[1])
        NG.links.new(ColorScaleMixN.outputs[0],GroupOutN.inputs[0])
        NG.links.new(OpacN.outputs[0],GroupOutN.inputs[4])
        
    createLayerMaterial(mlsetup["name"][:-8]+"_Layer_",LayerCount,CurMat,mlmaskpath,normalimgpath)
    
for x in obj["materialTemplates"]:
    if not bpy.data.node_groups.get(x["name"][:-11]):
        createBaseMaterial(x,BasePath)
        continue
counter = len(bpy.data.materials.keys())
mat = obj["rawMaterials"][0]
bpy.data.materials.new(mat["name"])
bpy.data.materials[counter].use_nodes = True
create(obj,obj["materialSetups"][0],BasePath + mat["multiLayered"]["multilayerMask"],bpy.data.materials[counter],BasePath + obj["rawMaterials"][7]["multiLayered"]["globalNormal"])
counter += 1