import bpy
import os
from ..main.common import *
import json

class Multilayered:
    def __init__(self, BasePath,image_format, ProjPath):
        self.BasePath = str(BasePath)
        self.image_format = image_format
        self.ProjPath = str(ProjPath)

    def createBaseMaterial(self,matTemplateObj,mltemplate):
        name=os.path.basename(mltemplate)
        CT = imageFromRelPath(matTemplateObj["colorTexture"]["DepotPath"]["$value"],self.image_format,DepotPath=self.BasePath, ProjPath=self.ProjPath)
        NT = imageFromRelPath(matTemplateObj["normalTexture"]["DepotPath"]["$value"],self.image_format,isNormal = True,DepotPath=self.BasePath, ProjPath=self.ProjPath)
        RT = imageFromRelPath(matTemplateObj["roughnessTexture"]["DepotPath"]["$value"],self.image_format,isNormal = True,DepotPath=self.BasePath, ProjPath=self.ProjPath)
        MT = imageFromRelPath(matTemplateObj["metalnessTexture"]["DepotPath"]["$value"],self.image_format,isNormal = True,DepotPath=self.BasePath, ProjPath=self.ProjPath)
    
        TileMult = float(matTemplateObj.get("tilingMultiplier",1))

        NG = bpy.data.node_groups.new(name[:-11],"ShaderNodeTree")
        NG['mlTemplate']=mltemplate
        TMI = NG.inputs.new('NodeSocketVector','Tile Multiplier')
        TMI.default_value = (1,1,1)
        NG.outputs.new('NodeSocketColor','Color')
        NG.outputs.new('NodeSocketColor','Metalness')
        NG.outputs.new('NodeSocketColor','Roughness')
        NG.outputs.new('NodeSocketColor','Normal')
    
        CTN = create_node( NG.nodes, "ShaderNodeTexImage",(0,0),image = CT)
    
        MTN = create_node( NG.nodes, "ShaderNodeTexImage",(0,-50*1),image = MT)
    
        RTN = create_node( NG.nodes, "ShaderNodeTexImage",(0,-50*2),image = RT)
    
        NTN = create_node( NG.nodes, "ShaderNodeTexImage",(0,-50*3),image = NT)
    
        MapN = create_node( NG.nodes, "ShaderNodeMapping",(-310,-64))
    
        TexCordN = create_node( NG.nodes, "ShaderNodeTexCoord",(-500,-64))
    
        TileMultN = create_node( NG.nodes, "ShaderNodeValue", (-700,-45*2))
        TileMultN.outputs[0].default_value = TileMult
    
        GroupInN = create_node( NG.nodes, "NodeGroupInput", (-700,-45*4))
    
        VecMathN = create_node( NG.nodes, "ShaderNodeVectorMath", (-500,-45*3), operation = 'MULTIPLY')
    
        NormSepN = create_node( NG.nodes, "ShaderNodeSeparateRGB", (300,-150))
    
        NormCombN = create_node( NG.nodes, "ShaderNodeCombineRGB", (500,-150))
        NormCombN.inputs[2].default_value = 1
    
        GroupOutN = create_node( NG.nodes, "NodeGroupOutput", (700,0))
    
        NG.links.new(TexCordN.outputs['UV'],MapN.inputs['Vector'])
        NG.links.new(VecMathN.outputs[0],MapN.inputs['Scale'])
        NG.links.new(MapN.outputs['Vector'],CTN.inputs['Vector'])
        NG.links.new(MapN.outputs['Vector'],NTN.inputs['Vector'])
        NG.links.new(MapN.outputs['Vector'],RTN.inputs['Vector'])
        NG.links.new(MapN.outputs['Vector'],MTN.inputs['Vector'])
        NG.links.new(TileMultN.outputs[0],VecMathN.inputs[0])
        NG.links.new(GroupInN.outputs[0],VecMathN.inputs[1])
        NG.links.new(CTN.outputs[0],GroupOutN.inputs[0])
        NG.links.new(MTN.outputs[0],GroupOutN.inputs[1])
        NG.links.new(RTN.outputs[0],GroupOutN.inputs[2])
        NG.links.new(NTN.outputs[0],NormSepN.inputs[0])
        NG.links.new(NormSepN.outputs[0],NormCombN.inputs[0])
        NG.links.new(NormSepN.outputs[1],NormCombN.inputs[1])
        NG.links.new(NormCombN.outputs[0],GroupOutN.inputs[3])
    
        return


    def setGlobNormal(self,normalimgpath,CurMat,input):
        GNN = create_node(CurMat.nodes, "ShaderNodeVectorMath",(-200,-250),operation='NORMALIZE')        
    
        GNA = create_node(CurMat.nodes, "ShaderNodeVectorMath",(-400,-250),operation='ADD')
    
        GNS = create_node(CurMat.nodes, "ShaderNodeVectorMath", (-600,-250),operation='SUBTRACT')
    
        GNGeo = create_node(CurMat.nodes, "ShaderNodeNewGeometry", (-800,-250))
    
        GNMap = CreateShaderNodeNormalMap(CurMat,self.BasePath + normalimgpath,-600,-550,'GlobalNormal',self.image_format)
        CurMat.links.new(GNGeo.outputs['Normal'],GNS.inputs[1])
        CurMat.links.new(GNMap.outputs[0],GNS.inputs[0])
        CurMat.links.new(GNS.outputs[0],GNA.inputs[1])
        CurMat.links.new(input,GNA.inputs[0])
        CurMat.links.new(GNA.outputs[0],GNN.inputs[0])
        return GNN.outputs[0]

    def createLayerMaterial(self,LayerName,LayerCount,CurMat,mlmaskpath,normalimgpath):
        NG = bpy.data.node_groups.new("Layer_Blend","ShaderNodeTree")#create layer's node group
        NG.inputs.new('NodeSocketColor','Color A')
        NG.inputs.new('NodeSocketColor','Metalness A')
        NG.inputs.new('NodeSocketColor','Roughness A')
        NG.inputs.new('NodeSocketColor','Normal A')
        NG.inputs.new('NodeSocketColor','Color B')
        NG.inputs.new('NodeSocketColor','Metalness B')
        NG.inputs.new('NodeSocketColor','Roughness B')
        NG.inputs.new('NodeSocketColor','Normal B')
        NG.inputs.new('NodeSocketColor','Mask')
        NG.outputs.new('NodeSocketColor','Color')
        NG.outputs.new('NodeSocketColor','Metalness')
        NG.outputs.new('NodeSocketColor','Roughness')
        NG.outputs.new('NodeSocketColor','Normal')
        GroupInN = create_node(NG.nodes,"NodeGroupInput", (-700,0), hide=False)
    
        GroupOutN = create_node(NG.nodes,"NodeGroupOutput",(200,0))
    
        ColorMixN = create_node(NG.nodes,"ShaderNodeMixRGB", (-300,100), label="Color Mix")
    
        MetalMixN = create_node(NG.nodes,"ShaderNodeMixRGB", (-300,50), label = "Metal Mix")
    
        RoughMixN = create_node(NG.nodes,"ShaderNodeMixRGB", (-300,0), label = "Rough Mix")
    
        NormalMixN = create_node(NG.nodes,"ShaderNodeMixRGB",(-300,-50), label = "Normal Mix")
        for x in range(LayerCount-1):
            if os.path.exists(os.path.splitext(self.ProjPath + mlmaskpath)[0]+'_layers\\'+mlmaskpath.split('\\')[-1:][0][:-7]+"_"+str(x+1)+".png"):
                MaskTexture = imageFromPath(os.path.splitext(self.ProjPath+ mlmaskpath)[0]+'_layers\\'+mlmaskpath.split('\\')[-1:][0][:-7]+"_"+str(x+1)+".png",self.image_format,isNormal = True)
            else:
                MaskTexture = imageFromPath(os.path.splitext(self.BasePath + mlmaskpath)[0]+"_"+str(x+1)+".png",self.image_format,isNormal = True)
         
            
        
            LayerGroupN = create_node(CurMat.nodes,"ShaderNodeGroup", (-1400,400-100*x))
            LayerGroupN.node_tree = NG
            LayerGroupN.name = "Layer_"+str(x)
        
            MaskN = create_node(CurMat.nodes,"ShaderNodeTexImage",(-2400,400-100*x), image = MaskTexture,label="Layer_"+str(x+1))
            
            #if self.flipMaskY:
            # Mask flip deprecated in WolvenKit deveolpment build 8.7+
            #MaskN.texture_mapping.scale[1] = -1 #flip mask if needed
            
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
            CurMat.links.new(MaskN.outputs[0],CurMat.nodes["Mat_Mod_Layer_"+str(x+1)].inputs[7])
            CurMat.links.new(CurMat.nodes["Mat_Mod_Layer_"+str(x+1)].outputs[4],CurMat.nodes["Layer_"+str(x)].inputs[8])
            
            NG.links.new(GroupInN.outputs[0],ColorMixN.inputs[1])
            NG.links.new(GroupInN.outputs[1],MetalMixN.inputs[1])
            NG.links.new(GroupInN.outputs[2],RoughMixN.inputs[1])
            NG.links.new(GroupInN.outputs[3],NormalMixN.inputs[1])
            NG.links.new(GroupInN.outputs[4],ColorMixN.inputs[2])
            NG.links.new(GroupInN.outputs[5],MetalMixN.inputs[2])
            NG.links.new(GroupInN.outputs[6],RoughMixN.inputs[2])
            NG.links.new(GroupInN.outputs[7],NormalMixN.inputs[2])
            NG.links.new(GroupInN.outputs[8],ColorMixN.inputs[0])
            NG.links.new(GroupInN.outputs[8],NormalMixN.inputs[0])
            NG.links.new(GroupInN.outputs[8],RoughMixN.inputs[0])
            NG.links.new(GroupInN.outputs[8],MetalMixN.inputs[0])
        
            NG.links.new(ColorMixN.outputs[0],GroupOutN.inputs[0])
            NG.links.new(NormalMixN.outputs[0],GroupOutN.inputs[3])
            NG.links.new(RoughMixN.outputs[0],GroupOutN.inputs[2])
            NG.links.new(MetalMixN.outputs[0],GroupOutN.inputs[1])
        
        CurMat.links.new(CurMat.nodes["Layer_"+str(LayerCount-2)].outputs[0],CurMat.nodes['Principled BSDF'].inputs['Base Color'])
        if normalimgpath:
            yoink = self.setGlobNormal(normalimgpath,CurMat,CurMat.nodes["Layer_"+str(LayerCount-2)].outputs[3])
            CurMat.links.new(yoink,CurMat.nodes['Principled BSDF'].inputs['Normal'])
        else:
            CurMat.links.new(CurMat.nodes["Layer_"+str(LayerCount-2)].outputs[3],CurMat.nodes['Principled BSDF'].inputs['Normal'])
        CurMat.links.new(CurMat.nodes["Layer_"+str(LayerCount-2)].outputs[2],CurMat.nodes['Principled BSDF'].inputs['Roughness'])
        CurMat.links.new(CurMat.nodes["Layer_"+str(LayerCount-2)].outputs[1],CurMat.nodes['Principled BSDF'].inputs['Metallic'])
        return


    def create(self,Data,Mat):
        Mat['MLSetup']= Data["MultilayerSetup"]
        file = openJSON( Data["MultilayerSetup"] + ".json",mode='r',DepotPath=self.BasePath, ProjPath=self.ProjPath)
        mlsetup = json.loads(file.read())
        file.close()
        valid_json=json_ver_validate(mlsetup)
        if not valid_json:
            self.report({'ERROR'}, "Incompatible mlsetup json file detected. This add-on version requires materials generated WolvenKit 8.9.1 or higher.")
            return
        mlsetup = mlsetup["Data"]["RootChunk"]
        xllay = mlsetup.get("layers")
        if xllay is None:
            xllay = mlsetup.get("Layers")
        LayerCount = len(xllay)
    
        LayerIndex = 0
        CurMat = Mat.node_tree
        for x in (xllay):            
            MatTile = x.get("matTile")
            if MatTile is None:
                MatTile = x.get("MatTile")
            MbTile = x.get("mbTile")
            if MbTile is None:
                MbTile = x.get("MbTile")

            MbScale = 1
            if MatTile != None:
                MbScale = float(MatTile)
            if MbTile != None:
                MbScale = float(MbTile)
        
            Microblend = x["microblend"]["DepotPath"].get("$value")
            if Microblend is None:
                Microblend = x["Microblend"].get("$value")

            MicroblendContrast = x.get("microblendContrast")
            if MicroblendContrast is None:
                MicroblendContrast = x.get("Microblend",1)

            microblendNormalStrength = x.get("microblendNormalStrength")
            if microblendNormalStrength is None:
                microblendNormalStrength = x.get("MicroblendNormalStrength")

            opacity = x.get("opacity")
            if opacity is None:
                opacity = x.get("Opacity")
				
            material = x["material"]["DepotPath"].get("$value")
            if material is None:
                material = x["Material"]["DepotPath"].get("$value")

            colorScale = x["colorScale"].get("$value")
            if colorScale is None:
                colorScale = x["ColorScale"].get("$value")

            normalStrength = x["normalStrength"].get("$value")
            if normalStrength is None:
                normalStrength = x["NormalStrength"].get("$value")

            #roughLevelsIn = x["roughLevelsIn"]
            roughLevelsOut = x["roughLevelsOut"].get("$value")
            if roughLevelsOut is None:
                roughLevelsOut = x["RoughLevelsOut"].get("$value")

            #metalLevelsIn = x["metalLevelsIn"]
            metalLevelsOut = x["metalLevelsOut"].get("$value")
            if metalLevelsOut is None:
                metalLevelsOut = x["MetalLevelsOut"].get("$value")

            if Microblend != "null":
                MBI = imageFromPath(self.BasePath+Microblend,self.image_format,True)
            
            file = openJSON( material + ".json",mode='r',DepotPath=self.BasePath, ProjPath=self.ProjPath)
            mltemplate = json.loads(file.read())
            file.close()
            valid_json=json_ver_validate(mltemplate)
            if not valid_json:
                self.report({'ERROR'}, "Incompatible mltemplate json file detected. This add-on version requires materials generated WolvenKit 8.9.1 or higher.")
                return
            mltemplate = mltemplate["Data"]["RootChunk"]
            OverrideTable = createOverrideTable(mltemplate)#get override info for colors and what not
           # Mat[os.path.basename(material).split('.')[0]+'_cols']=OverrideTable["ColorScale"]

            NG = bpy.data.node_groups.new(os.path.basename(Data["MultilayerSetup"])[:-8]+"_Layer_"+str(LayerIndex),"ShaderNodeTree")#crLAer's node group
            NG.inputs.new('NodeSocketColor','ColorScale')
            NG.inputs.new('NodeSocketFloat','MatTile')
            NG.inputs.new('NodeSocketFloat','MbTile')
            NG.inputs.new('NodeSocketFloat','MicroblendNormalStrength')
            NG.inputs.new('NodeSocketFloat','MicroblendContrast')
            NG.inputs.new('NodeSocketFloat','NormalStrength')
            NG.inputs.new('NodeSocketFloat','Opacity')
            NG.inputs.new('NodeSocketColor','Mask')
            NG.outputs.new('NodeSocketColor','Color')
            NG.outputs.new('NodeSocketColor','Metalness')
            NG.outputs.new('NodeSocketColor','Roughness')
            NG.outputs.new('NodeSocketColor','Normal')
            NG.outputs.new('NodeSocketColor','Layer Mask')

            NG.inputs[4].min_value = 0
            NG.inputs[4].max_value = 1
            NG.inputs[6].min_value = 0
            NG.inputs[6].max_value = 1
            
            LayerGroupN = create_node(CurMat.nodes, "ShaderNodeGroup", (-2000,500-100*LayerIndex))
            LayerGroupN.width = 400
            LayerGroupN.node_tree = NG
            LayerGroupN.name = "Mat_Mod_Layer_"+str(LayerIndex)
            LayerIndex += 1
            
            GroupInN = create_node(NG.nodes, "NodeGroupInput", (-2600,0))
            
            GroupOutN = create_node(NG.nodes, "NodeGroupOutput", (200,0))
            LayerGroupN['mlTemplate']=material
            if not bpy.data.node_groups.get(os.path.basename(material)[:-11]):
                self.createBaseMaterial(mltemplate,material)

            BaseMat = bpy.data.node_groups.get(os.path.basename(material)[:-11])
            if BaseMat:
                BMN = create_node(NG.nodes,"ShaderNodeGroup", (-2000,0))
                BMN.width = 300
                BMN.node_tree = BaseMat
            
            # SET LAYER GROUP DEFAULT VALUES
            
            if colorScale != None and colorScale in OverrideTable["ColorScale"].keys():
                LayerGroupN.inputs[0].default_value = OverrideTable["ColorScale"][colorScale]
                LayerGroupN['colorScale']=colorScale
            else:
                LayerGroupN.inputs[0].default_value = (1.0,1.0,1.0,1)
            
            if MatTile != None:
                LayerGroupN.inputs[1].default_value = float(MatTile)
            else:
                LayerGroupN.inputs[1].default_value = 1
            
            if MbScale != None:
                LayerGroupN.inputs[2].default_value = float(MbScale)
            else:
                LayerGroupN.inputs[2].default_value = 1
            
            if microblendNormalStrength != None:
                LayerGroupN.inputs[3].default_value = float(microblendNormalStrength)
            else:
                LayerGroupN.inputs[3].default_value = 1
            
            if MicroblendContrast != None:
                LayerGroupN.inputs[4].default_value = float(MicroblendContrast)
            else:
                LayerGroupN.inputs[4].default_value = 1
            
            if normalStrength != None:
                LayerGroupN.inputs[5].default_value = OverrideTable["NormalStrength"][normalStrength]
            else:
                LayerGroupN.inputs[5].default_value = 1
            
            if opacity != None:
                LayerGroupN.inputs[6].default_value = float(opacity)
            else:
                LayerGroupN.inputs[6].default_value = 1
            
            
            # DEFINES MAIN MULTILAYERED PROPERTIES
        
            # Node for blending colorscale color with diffuse texture of mltemplate
            # Changed from multiply to overlay because multiply is a darkening blend mode, and colors appear too dark. Overlay is still probably wrong - jato
            if colorScale != "null":
                ColorScaleMixN = create_node(NG.nodes,"ShaderNodeMixRGB",(-1500,50),blend_type='OVERLAY')
                ColorScaleMixN.inputs[0].default_value=1
            
            MBN = create_node(NG.nodes,"ShaderNodeTexImage",(-2050,-600),image = MBI,label = "Microblend")
            
            MBRGBCurveN = create_node(NG.nodes,"ShaderNodeRGBCurve",(-1600,-250))
            MBRGBCurveN.mapping.curves[0].points[0].location = (0,1)
            MBRGBCurveN.mapping.curves[0].points[1].location = (1,0)
            MBRGBCurveN.mapping.curves[1].points[0].location = (0,1)
            MBRGBCurveN.mapping.curves[1].points[1].location = (1,0)
            
            MBGrtrThanN = create_node(NG.nodes,"ShaderNodeMath", (-1200,-350),operation = 'GREATER_THAN')
            MBGrtrThanN.inputs[1].default_value = 0
            
            MBMixN = create_node(NG.nodes,"ShaderNodeMixRGB", (-1200,-400), blend_type ='MIX')
            
            MBMixColorRamp = create_node(NG.nodes,"ShaderNodeValToRGB", (-1350,-500))
            MBMixColorRamp.color_ramp.elements.remove(MBMixColorRamp.color_ramp.elements[1])
            MBMix_colors = [(0.25,0.25,0.25,1), (1,1,1,1)]
            MBMix_positions = [0.9, 0.99608]
            
            elements = MBMixColorRamp.color_ramp.elements
            for i in range(len(MBMix_colors)):
                element = elements.new(MBMix_positions[i])
                element.color = MBMix_colors[i]
            
            MBMixNormStrength = create_node(NG.nodes,"ShaderNodeMixRGB", (-950,-350),blend_type ='MIX')
            MBMixNormStrength.inputs[2].default_value = (0.5,0.5,1.0,1.0)
            
            MBMapping = create_node(NG.nodes,"ShaderNodeMapping", (-2300,-650))
            
            MBTexCord = create_node(NG.nodes,"ShaderNodeTexCoord", (-2300,-600))
            
            MBNormAbsN = create_node(NG.nodes,"ShaderNodeMath", (-750,-300),operation = 'ABSOLUTE')
            
            MBNormalN = create_node(NG.nodes,"ShaderNodeNormalMap", (-750,-350))
            
            NormalCombineN = create_node(NG.nodes,"ShaderNodeVectorMath", (-550,-250))
            
            NormSubN = create_node(NG.nodes,"ShaderNodeVectorMath", (-550, -350), operation = 'SUBTRACT')
            
            NormalizeN =create_node(NG.nodes,"ShaderNodeVectorMath", (-350,-200), operation = 'NORMALIZE')
            
            GeoN = create_node(NG.nodes,"ShaderNodeNewGeometry", (-750, -450))
            
            NormStrengthN = create_node(NG.nodes,"ShaderNodeNormalMap", (-1200,-200), label = "NormalStrength")
            
            # Roughness
            RoughRampN = create_node(NG.nodes,"ShaderNodeMapRange", (-1400,-100), label = "Roughness Ramp")
            if roughLevelsOut in OverrideTable["RoughLevelsOut"].keys():
                RoughRampN.inputs['To Min'].default_value = (OverrideTable["RoughLevelsOut"][roughLevelsOut][1][0])
                RoughRampN.inputs['To Max'].default_value = (OverrideTable["RoughLevelsOut"][roughLevelsOut][0][0])
            
            # Metalness
            MetalRampN = create_node(NG.nodes,"ShaderNodeValToRGB", (-1400,-50),label = "Metal Ramp")
            if metalLevelsOut in OverrideTable["MetalLevelsOut"].keys():
                MetalRampN.color_ramp.elements[1].color = (OverrideTable["MetalLevelsOut"][metalLevelsOut][0])
                MetalRampN.color_ramp.elements[0].color = (OverrideTable["MetalLevelsOut"][metalLevelsOut][1])
			
            # --- Mask Layer ---

            # MicroOffset prevents shader error when microblend contrast is exactly zero
            MBCMicroOffset = create_node(NG.nodes,"ShaderNodeMath", (-2300,-400), operation = 'ADD', label = "Micro-offset")
            MBCMicroOffset.inputs[1].default_value = 0.0001

            # Invert microblend contrast so mbcontrast value of 1 = 0, and 0 = 1
            MBCSubtract = create_node(NG.nodes,"ShaderNodeMath", (-1200,-650), operation = 'SUBTRACT')
            MBCSubtract.inputs[0].default_value = 1.0
            
            # Doubles mlmask levels as mbcontrast approaches 1
            MBCAdd = create_node(NG.nodes,"ShaderNodeMath", (-1400,-700), operation = 'ADD')
            MBCAdd.inputs[1].default_value = 1.0
            
            # Doubles mlmask levels as mbcontrast approaches 1
            MaskMultiply = create_node(NG.nodes,"ShaderNodeMath", (-1200,-700), operation = 'MULTIPLY')
            MaskMultiply.use_clamp = True
            
            # Blender doesn't support Linear Burn blend mode, so we do it manually
            MaskLinearBurnAdd = create_node(NG.nodes,"ShaderNodeMath", (-1600,-800), operation = 'ADD')

            # Blender doesn't support Linear Burn blend mode, so we do it manually
            MaskLinearBurnSubtract = create_node(NG.nodes,"ShaderNodeMath", (-1400,-800), operation = 'SUBTRACT')
            MaskLinearBurnSubtract.inputs[0].default_value = 1.0

            # Blender doesn't support Linear Burn blend mode, so we do it manually
            MaskLinearBurnInvert = create_node(NG.nodes,"ShaderNodeInvert", (-1200,-800))
            MaskLinearBurnInvert.inputs[0].default_value = 1.0

            # Mix the microblend against the original mlmask
            MaskMBMix = create_node(NG.nodes,"ShaderNodeMix", (-900,-800), label = "MICROBLEND MIXER")
            MaskMBMix.data_type ='RGBA'
            MaskMBMix.clamp_factor = False

            # Raise the contrast of the microblend as mbcontrast approaches zero by increasing `From Min` value
            # Smoother Step setting appears to disable clamp in the UI? Not sure if this matters
            MaskRange = create_node(NG.nodes,"ShaderNodeMapRange", (-600,-800))
            MaskRange.inputs['From Min'].default_value = (0)
            MaskRange.inputs['From Max'].default_value = (1)
            MaskRange.inputs['To Min'].default_value = (0)
            MaskRange.inputs['To Max'].default_value = (1)
            MaskRange.interpolation_type = 'SMOOTHERSTEP'
            MaskRange.clamp = True
            
            MaskOpReroute = create_node(NG.nodes,"NodeReroute", (-1500,-750))
            
            # Mix the complete mlmask with microblend against the opacity value
            MaskOpMix = create_node(NG.nodes,"ShaderNodeMixRGB", (-300,-750), label = "OPACITY MIX")
            MaskOpMix.blend_type ='MIX'
            MaskOpMix.inputs[1].default_value = (0,0,0,1)

            # --- End Mask Layer ---
            
            
            # CREATE FINAL LINKS
            NG.links.new(GroupInN.outputs[0],ColorScaleMixN.inputs[2])
            NG.links.new(GroupInN.outputs[1],BMN.inputs[0])
            NG.links.new(GroupInN.outputs[2],MBMapping.inputs[3])
            NG.links.new(GroupInN.outputs[3],MBGrtrThanN.inputs[0])
            NG.links.new(GroupInN.outputs[3],MBNormAbsN.inputs[0])
            NG.links.new(GroupInN.outputs[4],MBCMicroOffset.inputs[0])
            NG.links.new(GroupInN.outputs[5],NormStrengthN.inputs[0])
            NG.links.new(GroupInN.outputs[6],MaskOpReroute.inputs[0])
            NG.links.new(GroupInN.outputs[7],MaskMultiply.inputs[0])
            NG.links.new(GroupInN.outputs[7],MaskLinearBurnAdd.inputs[0])
            
            NG.links.new(MBCMicroOffset.outputs[0],MBCSubtract.inputs[1])
            NG.links.new(MBCMicroOffset.outputs[0],MBCAdd.inputs[0])

            NG.links.new(MBTexCord.outputs[2],MBMapping.inputs[0])
            NG.links.new(MBMapping.outputs[0],MBN.inputs[0])
            NG.links.new(MBN.outputs[0],MBRGBCurveN.inputs[1])
            NG.links.new(MBN.outputs[0],MBMixN.inputs[2])
            NG.links.new(MBN.outputs[1],MaskLinearBurnAdd.inputs[1])

            NG.links.new(MBCSubtract.outputs[0],MaskMBMix.inputs[0])
            NG.links.new(MBCSubtract.outputs[0],MaskRange.inputs[1])
            NG.links.new(MBCAdd.outputs[0],MaskMultiply.inputs[1])

            NG.links.new(MaskLinearBurnAdd.outputs[0],MaskLinearBurnSubtract.inputs[1])
            NG.links.new(MaskLinearBurnSubtract.outputs[0],MaskLinearBurnInvert.inputs[1])
            NG.links.new(MaskMultiply.outputs[0],MaskMBMix.inputs[6])    
            NG.links.new(MaskLinearBurnInvert.outputs[0],MaskMBMix.inputs[7])
            NG.links.new(MaskMBMix.outputs[2],MaskRange.inputs[0])
                        
            NG.links.new(BMN.outputs[0],ColorScaleMixN.inputs[1])
            NG.links.new(BMN.outputs[1],MetalRampN.inputs[0])
            NG.links.new(BMN.outputs[2],RoughRampN.inputs[0])
            NG.links.new(BMN.outputs[3],NormStrengthN.inputs[1])
            
            NG.links.new(MBMixColorRamp.outputs[0],MBMixNormStrength.inputs[0])
            NG.links.new(NormStrengthN.outputs[0],NormalCombineN.inputs[0])
            
            NG.links.new(MaskOpReroute.outputs[0],MaskOpMix.inputs[0])
            NG.links.new(MaskRange.outputs[0],MaskOpMix.inputs[2])

            NG.links.new(MBGrtrThanN.outputs[0],MBMixN.inputs[0])
            NG.links.new(MBRGBCurveN.outputs[0],MBMixN.inputs[1])
            NG.links.new(MBMixN.outputs[0],MBMixNormStrength.inputs[1])
            NG.links.new(MBMixNormStrength.outputs[0],MBNormalN.inputs[1])
            NG.links.new(MBNormAbsN.outputs[0],MBNormalN.inputs[0])
            NG.links.new(MBNormalN.outputs[0],NormSubN.inputs[0])
            NG.links.new(GeoN.outputs['Normal'],NormSubN.inputs[1])
            NG.links.new(NormSubN.outputs[0],NormalCombineN.inputs[1])			
            NG.links.new(NormalCombineN.outputs[0],NormalizeN.inputs[0])
            
            NG.links.new(ColorScaleMixN.outputs[0],GroupOutN.inputs[0]) #Color output
            NG.links.new(MetalRampN.outputs[0],GroupOutN.inputs[1]) #Metalness output
            NG.links.new(RoughRampN.outputs[0],GroupOutN.inputs[2]) #Roughness output
            NG.links.new(NormalizeN.outputs[0],GroupOutN.inputs[3]) #Normal output
            NG.links.new(MaskOpMix.outputs[0],GroupOutN.inputs[4]) #Mask Layer output
        
        self.createLayerMaterial(os.path.basename(Data["MultilayerSetup"])[:-8]+"_Layer_",LayerCount,CurMat,Data["MultilayerMask"],Data["GlobalNormal"])