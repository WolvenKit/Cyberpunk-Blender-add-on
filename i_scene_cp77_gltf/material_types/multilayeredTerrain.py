import bpy
import os
from ..main.common import *
from ..jsontool import JSONTool

class MultilayeredTerrain:
    def __init__(self, BasePath,image_format,ProjPath):
        self.BasePath = str(BasePath)
        self.ProjPath = ProjPath
        self.image_format = image_format


    def createBaseMaterial(self,matTemplateObj,name):
        print(self.BasePath + matTemplateObj["colorTexture"]["DepotPath"]["$value"])

        ct_path=matTemplateObj["colorTexture"]["DepotPath"]["$value"]
        CT = imageFromRelPath(ct_path,self.image_format, DepotPath=self.BasePath, ProjPath=self.ProjPath)

        nt_path= matTemplateObj["normalTexture"]["DepotPath"]["$value"]
        NT = imageFromRelPath(nt_path,self.image_format,isNormal = True, DepotPath=self.BasePath, ProjPath=self.ProjPath)

        rt_path=matTemplateObj["roughnessTexture"]["DepotPath"]["$value"]
        RT = imageFromRelPath(rt_path,self.image_format,isNormal = True, DepotPath=self.BasePath, ProjPath=self.ProjPath)

        mt_path=matTemplateObj["metalnessTexture"]["DepotPath"]["$value"]
        MT = imageFromRelPath(mt_path,self.image_format,isNormal = True, DepotPath=self.BasePath, ProjPath=self.ProjPath)

        TileMult = float(matTemplateObj.get("tilingMultiplier",1))

        NG = bpy.data.node_groups.new(name[:-11],"ShaderNodeTree")
        TMI = NG.inputs.new('NodeSocketVector','Tile Multiplier')
        TMI.default_value = (1,1,1)
        NG.outputs.new('NodeSocketColor','Color')
        NG.outputs.new('NodeSocketColor','Metalness')
        NG.outputs.new('NodeSocketColor','Roughness')
        NG.outputs.new('NodeSocketColor','Normal')

        CTN = NG.nodes.new("ShaderNodeTexImage")
        CTN.hide = True
        CTN.image = CT

        MTN = NG.nodes.new("ShaderNodeTexImage")
        MTN.hide = True
        MTN.image = MT
        MTN.location[1] = -50*1

        RTN = NG.nodes.new("ShaderNodeTexImage")
        RTN.hide = True
        RTN.image = RT
        RTN.location[1] = -50*2

        NTN = NG.nodes.new("ShaderNodeTexImage")
        NTN.hide = True
        NTN.image = NT
        NTN.location[1] = -50*3

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

        VecMathN = NG.nodes.new("ShaderNodeVectorMath")
        VecMathN.hide=True
        VecMathN.location = (-500,-45*3)
        VecMathN.operation = 'MULTIPLY'

        NormSepN = NG.nodes.new("ShaderNodeSeparateRGB")
        NormSepN.hide=True
        NormSepN.location = (300,-150)

        NormCombN = NG.nodes.new("ShaderNodeCombineRGB")
        NormCombN.hide=True
        NormCombN.location = (500,-150)
        NormCombN.inputs[2].default_value = 1

        GroupOutN = NG.nodes.new("NodeGroupOutput")
        GroupOutN.hide=True
        GroupOutN.location = (700,0)

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
        if os.path.exists(self.BasePath + normalimgpath[:-3]+'png'):
            GNMap = CreateShaderNodeNormalMap(CurMat,self.BasePath + normalimgpath,-600,-550,'GlobalNormal',self.image_format)
        else:
            GNMap = CreateShaderNodeNormalMap(CurMat,self.ProjPath + normalimgpath,-600,-550,'GlobalNormal',self.image_format)
        CurMat.links.new(GNGeo.outputs['Normal'],GNS.inputs[1])
        CurMat.links.new(GNMap.outputs[0],GNS.inputs[0])
        CurMat.links.new(GNS.outputs[0],GNA.inputs[1])
        CurMat.links.new(input,GNA.inputs[0])
        CurMat.links.new(GNA.outputs[0],GNN.inputs[0])
        return GNN.outputs[0]

    def createLayerMaterial(self,LayerName,LayerCount,CurMat,mlmaskpath,normalimgpath):

        for x in range(LayerCount-1):
            if os.path.exists(os.path.splitext(self.ProjPath + mlmaskpath)[0]+'_layers\\'+mlmaskpath.split('\\')[-1:][0][:-7]+"_"+str(x+1)+".png"):
                MaskTexture = imageFromPath(os.path.splitext(self.ProjPath+ mlmaskpath)[0]+'_layers\\'+mlmaskpath.split('\\')[-1:][0][:-7]+"_"+str(x+1)+".png",self.image_format,isNormal = True)
            else:
                MaskTexture = imageFromPath(os.path.splitext(self.BasePath + mlmaskpath)[0]+"_"+str(x+1)+".png",self.image_format,isNormal = True)
            NG = bpy.data.node_groups.new("Layer_Blend_"+str(x),"ShaderNodeTree")#create layer's node group
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

            GroupInN = NG.nodes.new("NodeGroupInput")
            GroupInN.location = (-700,0)

            GroupOutN = NG.nodes.new("NodeGroupOutput")
            GroupOutN.hide=True
            GroupOutN.location = (200,0)

            ColorMixN = NG.nodes.new("ShaderNodeMixRGB")
            ColorMixN.hide=True
            ColorMixN.location = (-300,100)
            ColorMixN.label = "Color Mix"

            MetalMixN = NG.nodes.new("ShaderNodeMixRGB")
            MetalMixN.hide=True
            MetalMixN.location = (-300,50)
            MetalMixN.label = "Metal Mix"

            RoughMixN = NG.nodes.new("ShaderNodeMixRGB")
            RoughMixN.hide=True
            RoughMixN.location = (-300,0)
            RoughMixN.label = "Rough Mix"

            NormalMixN = NG.nodes.new("ShaderNodeMixRGB")
            NormalMixN.hide=True
            NormalMixN.location = (-300,-50)
            NormalMixN.label = "Normal Mix"

            LayerGroupN = CurMat.nodes.new("ShaderNodeGroup")
            LayerGroupN.location = (-1400,400-100*x)
            LayerGroupN.hide = True
            LayerGroupN.node_tree = NG
            LayerGroupN.name = "Layer_"+str(x)

            MaskN = CurMat.nodes.new("ShaderNodeTexImage")
            MaskN.hide = True
            MaskN.image = MaskTexture
            MaskN.location = (-2400,400-100*x)
            #if self.flipMaskY:
            # Mask flip deprecated in WolvenKit deveolpment build 8.7+
            #MaskN.texture_mapping.scale[1] = -1 #flip mask if needed
            MaskN.label="Layer_"+str(x+1)

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
        pBSDF = CurMat.nodes[loc('Principled BSDF')]
        CurMat.links.new(CurMat.nodes["Layer_"+str(LayerCount-2)].outputs[0],pBSDF.inputs['Base Color'])
        if normalimgpath:
            yoink = self.setGlobNormal(normalimgpath,CurMat,CurMat.nodes["Layer_"+str(LayerCount-2)].outputs[3])
            CurMat.links.new(yoink,pBSDF.inputs['Normal'])
        else:
            CurMat.links.new(CurMat.nodes["Layer_"+str(LayerCount-2)].outputs[3],pBSDF.inputs['Normal'])
        CurMat.links.new(CurMat.nodes["Layer_"+str(LayerCount-2)].outputs[2],pBSDF.inputs['Roughness'])
        CurMat.links.new(CurMat.nodes["Layer_"+str(LayerCount-2)].outputs[1],pBSDF.inputs['Metallic'])
        return


    def create(self,Data,Mat):

        file = self.BasePath + Data["MultilayerSetup"] + ".json"
        mlsetup = jsonload(file)
        mlsetup = mlsetup["Data"]["RootChunk"]
        xllay = mlsetup.get("layers")
        if xllay is None:
            xllay = x.get("Layers")
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
                Microblend = x["Microblend"]["DepotPath"].get("$value")
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
                colorScale =  x["ColorScale"].get("$value")

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
                MBI = imageFromRelPath(Microblend,self.image_format,True,self.BasePath,self.ProjPath)


            file = self.BasePath + material + ".json"
            mltemplate = jsonload(file)
            mltemplate = mltemplate["Data"]["RootChunk"]
            OverrideTable = createOverrideTable(mltemplate)#get override info for colors and what not

            NG = bpy.data.node_groups.new(os.path.basename(Data["MultilayerSetup"])[:-8]+"_Layer_"+str(LayerIndex),"ShaderNodeTree")#create layer's node group
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
            NG.inputs[6].min_value = 0
            NG.inputs[6].max_value = 1

            LayerGroupN = CurMat.nodes.new("ShaderNodeGroup")
            LayerGroupN.location = (-2000,500-100*LayerIndex)
            LayerGroupN.hide = True
            LayerGroupN.width = 400
            LayerGroupN.node_tree = NG
            LayerGroupN.name = "Mat_Mod_Layer_"+str(LayerIndex)
            LayerIndex += 1

            GroupInN = NG.nodes.new("NodeGroupInput")
            GroupInN.hide=True
            GroupInN.location = (-2600,0)

            GroupOutN = NG.nodes.new("NodeGroupOutput")
            GroupOutN.hide=True
            GroupOutN.location = (200,0)

            if not bpy.data.node_groups.get(os.path.basename(material)[:-11]):
                self.createBaseMaterial(mltemplate,os.path.basename(material))

            BaseMat = bpy.data.node_groups.get(os.path.basename(material)[:-11])
            if BaseMat:
                BMN = NG.nodes.new("ShaderNodeGroup")
                BMN.location = (-2000,0)
                BMN.width = 300
                BMN.hide = True
                BMN.node_tree = BaseMat

            # SET LAYER GROUP DEFAULT VALUES

            if colorScale != None and colorScale in OverrideTable["ColorScale"].keys():
                LayerGroupN.inputs[0].default_value = OverrideTable["ColorScale"][colorScale]
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

            if colorScale != "null":
                ColorScaleMixN = NG.nodes.new("ShaderNodeMixRGB")
                ColorScaleMixN.hide=True
                ColorScaleMixN.location=(-1500,50)
                ColorScaleMixN.inputs[0].default_value=1
                ColorScaleMixN.blend_type='MULTIPLY'

            MBN = NG.nodes.new("ShaderNodeTexImage")
            MBN.hide = True
            MBN.image = MBI
            MBN.location = (-1900,-400)
            MBN.label = "Microblend"

            MBRGBCurveN = NG.nodes.new("ShaderNodeRGBCurve")
            MBRGBCurveN.hide = True
            MBRGBCurveN.location = (-1600,-350)
            MBRGBCurveN.mapping.curves[0].points[0].location = (0,1)
            MBRGBCurveN.mapping.curves[0].points[1].location = (1,0)
            MBRGBCurveN.mapping.curves[1].points[0].location = (0,1)
            MBRGBCurveN.mapping.curves[1].points[1].location = (1,0)

            MBGrtrThanN = NG.nodes.new("ShaderNodeMath")
            MBGrtrThanN.hide = True
            MBGrtrThanN.location = (-1200,-350)
            MBGrtrThanN.operation = 'GREATER_THAN'
            MBGrtrThanN.inputs[1].default_value = 0

            MBMixN = NG.nodes.new("ShaderNodeMixRGB")
            MBMixN.hide = True
            MBMixN.location =  (-1200,-400)
            MBMixN.blend_type ='MIX'

            MBMixColorRamp = NG.nodes.new("ShaderNodeValToRGB")
            MBMixColorRamp.hide = True
            MBMixColorRamp.location = (-1350,-500)
            MBMixColorRamp.color_ramp.elements.remove(MBMixColorRamp.color_ramp.elements[1])
            MBMix_colors = [(0.25,0.25,0.25,1), (1,1,1,1)]
            MBMix_positions = [0.9, 0.99608]

            elements = MBMixColorRamp.color_ramp.elements
            for i in range(len(MBMix_colors)):
                element = elements.new(MBMix_positions[i])
                element.color = MBMix_colors[i]

            MBMixNormStrength = NG.nodes.new("ShaderNodeMixRGB")
            MBMixNormStrength.hide = True
            MBMixNormStrength.location =  (-950,-350)
            MBMixNormStrength.blend_type ='MIX'
            MBMixNormStrength.inputs[2].default_value = (0.5,0.5,1.0,1.0)

            MBMapping = NG.nodes.new("ShaderNodeMapping")
            MBMapping.hide = True
            MBMapping.location = (-2100,-400)

            MBTexCord = NG.nodes.new("ShaderNodeTexCoord")
            MBTexCord.hide = True
            MBTexCord.location = (-2100,-450)

            MBNormAbsN = NG.nodes.new("ShaderNodeMath")
            MBNormAbsN.hide=True
            MBNormAbsN.location = (-750,-300)
            MBNormAbsN.operation = 'ABSOLUTE'

            MBNormalN = NG.nodes.new("ShaderNodeNormalMap")
            MBNormalN.hide = True
            MBNormalN.location = (-750,-350)

            NormalCombineN = NG.nodes.new("ShaderNodeVectorMath")
            NormalCombineN.hide = True
            NormalCombineN.location = (-550,-250)

            NormSubN = NG.nodes.new("ShaderNodeVectorMath")
            NormSubN.hide=True
            NormSubN.location = (-550, -350)
            NormSubN.operation = 'SUBTRACT'

            NormalizeN = NG.nodes.new("ShaderNodeVectorMath")
            NormalizeN.hide = True
            NormalizeN.location = (-350,-200)
            NormalizeN.operation = 'NORMALIZE'

            GeoN = NG.nodes.new("ShaderNodeNewGeometry")
            GeoN.hide=True
            GeoN.location=(-750, -450)

            NormStrengthN = NG.nodes.new("ShaderNodeNormalMap")
            NormStrengthN.hide = True
            NormStrengthN.label = ("NormalStrength")
            NormStrengthN.location = (-1200,-200)

            # Roughness
            RoughRampN = NG.nodes.new("ShaderNodeMapRange")
            RoughRampN.hide=True
            RoughRampN.location = (-1400,-100)
            if roughLevelsOut in OverrideTable["RoughLevelsOut"].keys():
                RoughRampN.inputs['To Min'].default_value = (OverrideTable["RoughLevelsOut"][roughLevelsOut][1][0])
                RoughRampN.inputs['To Max'].default_value = (OverrideTable["RoughLevelsOut"][roughLevelsOut][0][0])
            RoughRampN.label = "Roughness Ramp"

            # Metalness
            MetalRampN = NG.nodes.new("ShaderNodeValToRGB")
            MetalRampN.hide=True
            MetalRampN.location = (-1400,-50)
            if metalLevelsOut in OverrideTable["MetalLevelsOut"].keys():
                MetalRampN.color_ramp.elements[1].color = (OverrideTable["MetalLevelsOut"][metalLevelsOut][0])
                MetalRampN.color_ramp.elements[0].color = (OverrideTable["MetalLevelsOut"][metalLevelsOut][1])
            MetalRampN.label = "Metal Ramp"

			# Mask Layer
            MaskMix1 = NG.nodes.new("ShaderNodeMixRGB")
            MaskMix1.hide = True
            MaskMix1.location =  (-1600,-500)
            MaskMix1.blend_type ='OVERLAY'
            MaskMix1.inputs[0].default_value = 1

            MaskMix2 = NG.nodes.new("ShaderNodeMixRGB")
            MaskMix2.hide = True
            MaskMix2.location =  (-1600,-600)
            MaskMix2.blend_type ='MIX'
            MaskMix2.inputs[0].default_value = 1

            MaskOpReroute = NG.nodes.new("NodeReroute")
            MaskOpReroute.location = (-1600,-650)

            MaskMix3 = NG.nodes.new("ShaderNodeMixRGB")
            MaskMix3.label = "OPACITY MIX"
            MaskMix3.hide = True
            MaskMix3.location =  (-600,-550)
            MaskMix3.blend_type ='MULTIPLY'
            MaskMix3.inputs[0].default_value = 1

            MaskMBMultiply = NG.nodes.new("ShaderNodeMath")
            MaskMBMultiply.hide = True
            MaskMBMultiply.location = (-1600,-450)
            MaskMBMultiply.operation = 'MULTIPLY'
            MaskMBMultiply.inputs[1].default_value = 6.0
            NG.links.new(GroupInN.outputs[2],MaskMBMultiply.inputs[0])

            MaskMBPower = NG.nodes.new("ShaderNodeMath")
            MaskMBPower.hide = True
            MaskMBPower.location = (-1600,-550)
            MaskMBPower.operation = 'POWER'
            MaskMBPower.inputs[1].default_value = 100.0
            MaskMBPower.use_clamp = True


            # CREATE FINAL LINKS
            NG.links.new(GroupInN.outputs[0],ColorScaleMixN.inputs[2])
            NG.links.new(GroupInN.outputs[1],BMN.inputs[0])
            NG.links.new(GroupInN.outputs[2],MBMapping.inputs[3])
            NG.links.new(GroupInN.outputs[3],MBGrtrThanN.inputs[0])
            NG.links.new(GroupInN.outputs[3],MBNormAbsN.inputs[0])
            NG.links.new(GroupInN.outputs[4],MaskMix2.inputs[0])
            NG.links.new(GroupInN.outputs[5],NormStrengthN.inputs[0])
            NG.links.new(GroupInN.outputs[6],MaskOpReroute.inputs[0])
            NG.links.new(MaskOpReroute.outputs[0],MaskMix3.inputs[2])
            NG.links.new(GroupInN.outputs[7],MaskMix1.inputs[1])
            NG.links.new(GroupInN.outputs[7],MaskMix2.inputs[2])

            NG.links.new(BMN.outputs[0],ColorScaleMixN.inputs[1])
            NG.links.new(BMN.outputs[1],MetalRampN.inputs[0])
            NG.links.new(BMN.outputs[2],RoughRampN.inputs[0])
            NG.links.new(BMN.outputs[3],NormStrengthN.inputs[1])

            NG.links.new(MBTexCord.outputs[2],MBMapping.inputs[0])
            NG.links.new(MBMapping.outputs[0],MBN.inputs[0])
            NG.links.new(MBN.outputs[0],MBRGBCurveN.inputs[1])
            NG.links.new(MBN.outputs[0],MBMixN.inputs[2])
            NG.links.new(MBN.outputs[1],MaskMBMultiply.inputs[0])

            NG.links.new(MaskMBMultiply.outputs[0],MaskMix1.inputs[2])
            NG.links.new(MaskMix1.outputs[0],MaskMBPower.inputs[0])
            NG.links.new(MaskMBPower.outputs[0],MaskMix2.inputs[1])
            NG.links.new(MaskMix2.outputs[0],MaskMix3.inputs[1])
            NG.links.new(MaskMix2.outputs[0],MBMixColorRamp.inputs[0])
            NG.links.new(MBMixColorRamp.outputs[0],MBMixNormStrength.inputs[0])

            NG.links.new(NormStrengthN.outputs[0],NormalCombineN.inputs[0])

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
            NG.links.new(MaskMix3.outputs[0],GroupOutN.inputs[4]) #Mask Layer output

        self.createLayerMaterial(os.path.basename(Data["MultilayerSetup"])[:-8]+"_Layer_",LayerCount,CurMat,Data["MultilayerMask"],Data["GlobalNormal"])