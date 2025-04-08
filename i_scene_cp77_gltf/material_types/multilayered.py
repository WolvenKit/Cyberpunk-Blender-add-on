import bpy
import os
from ..main.common import *
from ..jsontool import JSONTool
import numpy as np

def np_array_from_image(img_name):
    img = bpy.data.images[img_name]
    return np.array(img.pixels[:])

#initialize Mask Mixer node group
def mask_mixer_node_group():
    if "Mask Mixer" in bpy.data.node_groups:
        return bpy.data.node_groups["Mask Mixer"]

    #create layer's node group
    mask_mixer = bpy.data.node_groups.new(type = 'ShaderNodeTree', name = "Mask Mixer")

    mask_mixer.color_tag = 'NONE'
    mask_mixer.description = ""
    mask_mixer.default_group_node_width = 140
    

    #mask_mixer interface
    #Socket Layer Mask
    layer_mask_socket = mask_mixer.interface.new_socket(name = "Layer Mask", in_out='OUTPUT', socket_type = 'NodeSocketFloat')
    layer_mask_socket.default_value = 0.0
    layer_mask_socket.min_value = -3.4028234663852886e+38
    layer_mask_socket.max_value = 3.4028234663852886e+38
    layer_mask_socket.subtype = 'NONE'
    layer_mask_socket.attribute_domain = 'POINT'

    #Socket Mask
    mask_socket = mask_mixer.interface.new_socket(name = "Mask", in_out='INPUT', socket_type = 'NodeSocketColor')
    mask_socket.default_value = (0.5, 0.5, 0.5, 1.0)
    mask_socket.attribute_domain = 'POINT'

    #Socket Microblend Alpha
    microblend_alpha_socket = mask_mixer.interface.new_socket(name = "Microblend Alpha", in_out='INPUT', socket_type = 'NodeSocketColor')
    microblend_alpha_socket.default_value = (0.5, 0.5, 0.5, 1.0)
    microblend_alpha_socket.attribute_domain = 'POINT'

    #Socket Microblend Contrast
    microblend_contrast_socket = mask_mixer.interface.new_socket(name = "Microblend Contrast", in_out='INPUT', socket_type = 'NodeSocketFloat')
    microblend_contrast_socket.default_value = 0.5
    microblend_contrast_socket.min_value = -10000.0
    microblend_contrast_socket.max_value = 10000.0
    microblend_contrast_socket.subtype = 'NONE'
    microblend_contrast_socket.attribute_domain = 'POINT'

    #Socket Opacity
    opacity_socket = mask_mixer.interface.new_socket(name = "Opacity", in_out='INPUT', socket_type = 'NodeSocketFloat')
    opacity_socket.default_value = 1.0
    opacity_socket.min_value = -10000.0
    opacity_socket.max_value = 10000.0
    opacity_socket.subtype = 'NONE'
    opacity_socket.attribute_domain = 'POINT'


    #initialize mask_mixer nodes
    #node Group Output
    group_output = mask_mixer.nodes.new("NodeGroupOutput")
    group_output.name = "Group Output"
    group_output.is_active_output = True

    #node Group Input
    group_input = mask_mixer.nodes.new("NodeGroupInput")
    group_input.name = "Group Input"

    #node Mix.001
    mix_001 = mask_mixer.nodes.new("ShaderNodeMix")
    mix_001.name = "Mix.001"
    mix_001.blend_type = 'OVERLAY'
    mix_001.clamp_factor = True
    mix_001.clamp_result = False
    mix_001.data_type = 'RGBA'
    mix_001.factor_mode = 'UNIFORM'

    #node Math.006
    math_006 = mask_mixer.nodes.new("ShaderNodeMath")
    math_006.name = "Math.006"
    math_006.operation = 'SUBTRACT'
    math_006.use_clamp = False
    #Value
    math_006.inputs[0].default_value = 1.0    

    #node Map Range.001
    map_range_001 = mask_mixer.nodes.new("ShaderNodeMapRange")
    map_range_001.name = "Map Range.001"
    map_range_001.clamp = True
    map_range_001.data_type = 'FLOAT'
    map_range_001.interpolation_type = 'LINEAR'
    #To Min
    map_range_001.inputs[3].default_value = 0.0

    #node Math.008
    math_008 = mask_mixer.nodes.new("ShaderNodeMath")
    math_008.name = "Math.008"
    math_008.operation = 'DIVIDE'
    math_008.use_clamp = False
    #Value_001
    math_008.inputs[1].default_value = 2.0

    #node Math.009
    math_009 = mask_mixer.nodes.new("ShaderNodeMath")
    math_009.name = "Math.009"
    math_009.operation = 'SUBTRACT'
    math_009.use_clamp = False
    #Value
    math_009.inputs[0].default_value = 1.0

    #node Math.010
    math_010 = mask_mixer.nodes.new("ShaderNodeMath")
    math_010.name = "Math.010"
    math_010.operation = 'ADD'
    math_010.use_clamp = False
    #Value
    math_010.inputs[0].default_value = 0.0


    #Set locations
    group_output.location = (762.4629516601562, -85.77066802978516)
    group_input.location = (-599.7591552734375, 0.0)
    mix_001.location = (-93.963623046875, 170.34710693359375)
    math_006.location = (-358.4058532714844, -142.66656494140625)
    map_range_001.location = (385.4674072265625, 135.95416259765625)
    math_008.location = (-116.00799560546875, -147.20404052734375)
    math_009.location = (56.01458740234375, -272.09808349609375)
    math_010.location = (54.735107421875, -116.58660888671875)

    #Set dimensions
    group_output.width, group_output.height = 140.0, 100.0
    group_input.width, group_input.height = 140.0, 100.0
    mix_001.width, mix_001.height = 140.0, 100.0
    math_006.width, math_006.height = 140.0, 100.0
    map_range_001.width, map_range_001.height = 140.0, 100.0
    math_008.width, math_008.height = 140.0, 100.0
    math_009.width, math_009.height = 140.0, 100.0
    math_010.width, math_010.height = 140.0, 100.0

    #initialize mask_mixer links
    #math_009.Value -> map_range_001.From Max
    mask_mixer.links.new(math_009.outputs[0], map_range_001.inputs[2])
    #math_006.Value -> math_008.Value
    mask_mixer.links.new(math_006.outputs[0], math_008.inputs[0])
    #mix_001.Result -> map_range_001.Value
    mask_mixer.links.new(mix_001.outputs[2], map_range_001.inputs[0])
    #math_010.Value -> map_range_001.From Min
    mask_mixer.links.new(math_010.outputs[0], map_range_001.inputs[1])
    #math_006.Value -> mix_001.Factor
    mask_mixer.links.new(math_006.outputs[0], mix_001.inputs[0])
    #math_008.Value -> math_009.Value
    mask_mixer.links.new(math_008.outputs[0], math_009.inputs[1])
    #math_008.Value -> math_010.Value
    mask_mixer.links.new(math_008.outputs[0], math_010.inputs[1])
    #group_input.Opacity -> map_range_001.To Max
    mask_mixer.links.new(group_input.outputs[3], map_range_001.inputs[4])
    #group_input.Mask -> mix_001.A
    mask_mixer.links.new(group_input.outputs[0], mix_001.inputs[6])
    #group_input.Microblend Alpha -> mix_001.B
    mask_mixer.links.new(group_input.outputs[1], mix_001.inputs[7])
    #group_input.Microblend Contrast -> math_006.Value
    mask_mixer.links.new(group_input.outputs[2], math_006.inputs[1])
    #map_range_001.Result -> group_output.Layer Mask
    mask_mixer.links.new(map_range_001.outputs[0], group_output.inputs[0])
    return mask_mixer
    

def _getOrCreateLayerBlend():
    if "Layer_Blend" in bpy.data.node_groups:
        return bpy.data.node_groups["Layer_Blend"]

    NG = bpy.data.node_groups.new("Layer_Blend","ShaderNodeTree")#create layer's node group
    vers=bpy.app.version
    if vers[0]<4:
        NG.inputs.new('NodeSocketColor','Color A')
        NG.inputs.new('NodeSocketFloat','Metalness A')
        NG.inputs.new('NodeSocketFloat','Roughness A')
        NG.inputs.new('NodeSocketVector','Normal A')
        NG.inputs.new('NodeSocketColor','Color B')
        NG.inputs.new('NodeSocketFloat','Metalness B')
        NG.inputs.new('NodeSocketFloat','Roughness B')
        NG.inputs.new('NodeSocketVector','Normal B')
        NG.inputs.new('NodeSocketFloat','Mask')
        NG.outputs.new('NodeSocketColor','Color')
        NG.outputs.new('NodeSocketFloat','Metalness')
        NG.outputs.new('NodeSocketFloat','Roughness')
        NG.outputs.new('NodeSocketVector','Normal')
    else:
        NG.interface.new_socket(name="Color A", socket_type='NodeSocketColor', in_out='INPUT')
        NG.interface.new_socket(name="Metalness A", socket_type='NodeSocketFloat', in_out='INPUT')
        NG.interface.new_socket(name="Roughness A", socket_type='NodeSocketFloat', in_out='INPUT')
        NG.interface.new_socket(name="Normal A", socket_type='NodeSocketVector', in_out='INPUT')
        NG.interface.new_socket(name="Color B", socket_type='NodeSocketColor', in_out='INPUT')
        NG.interface.new_socket(name="Metalness B", socket_type='NodeSocketFloat', in_out='INPUT')
        NG.interface.new_socket(name="Roughness B", socket_type='NodeSocketFloat', in_out='INPUT')
        NG.interface.new_socket(name="Normal B", socket_type='NodeSocketVector', in_out='INPUT')
        NG.interface.new_socket(name="Mask", socket_type='NodeSocketFloat', in_out='INPUT')
        NG.interface.new_socket(name="Color", socket_type='NodeSocketColor', in_out='OUTPUT')
        NG.interface.new_socket(name="Metalness", socket_type='NodeSocketFloat', in_out='OUTPUT')
        NG.interface.new_socket(name="Roughness", socket_type='NodeSocketFloat', in_out='OUTPUT')
        NG.interface.new_socket(name="Normal", socket_type='NodeSocketVector', in_out='OUTPUT')

    GroupInN = create_node(NG.nodes,"NodeGroupInput", (-700,0), hide=False)

    GroupOutN = create_node(NG.nodes,"NodeGroupOutput",(200,0), hide=False)

    ColorMixN = create_node(NG.nodes,"ShaderNodeMix", (-300,100), label="Color Mix")
    ColorMixN.data_type='RGBA'

    MetalMixN = create_node(NG.nodes,"ShaderNodeMix", (-300,0), label = "Metal Mix")
    MetalMixN.data_type='FLOAT'

    RoughMixN = create_node(NG.nodes,"ShaderNodeMix", (-300,-100), label = "Rough Mix")
    RoughMixN.data_type='FLOAT'

    NormalMixN = create_node(NG.nodes,"ShaderNodeMix",(-300,-200), label = "Normal Mix")
    NormalMixN.data_type='VECTOR'
    NormalMixN.clamp_factor=False

    NG.links.new(GroupInN.outputs[0],ColorMixN.inputs[6])
    NG.links.new(GroupInN.outputs[1],MetalMixN.inputs[2])
    NG.links.new(GroupInN.outputs[2],RoughMixN.inputs[2])
    NG.links.new(GroupInN.outputs['Normal A'],NormalMixN.inputs[4])
    NG.links.new(GroupInN.outputs[4],ColorMixN.inputs[7])
    NG.links.new(GroupInN.outputs[5],MetalMixN.inputs[3])
    NG.links.new(GroupInN.outputs[6],RoughMixN.inputs[3])
    NG.links.new(GroupInN.outputs['Normal B'],NormalMixN.inputs[5])
    NG.links.new(GroupInN.outputs[8],ColorMixN.inputs[0])
    NG.links.new(GroupInN.outputs['Mask'],NormalMixN.inputs['Factor'])
    NG.links.new(GroupInN.outputs[8],RoughMixN.inputs[0])
    NG.links.new(GroupInN.outputs[8],MetalMixN.inputs[0])

    NG.links.new(ColorMixN.outputs[2],GroupOutN.inputs[0])
    NG.links.new(MetalMixN.outputs[0],GroupOutN.inputs[1])
    NG.links.new(RoughMixN.outputs[0],GroupOutN.inputs[2])
    NG.links.new(NormalMixN.outputs[1],GroupOutN.inputs[3])

    return NG


class Multilayered:
    def __init__(self, BasePath,image_format, ProjPath):
        self.BasePath = str(BasePath)
        self.image_format = image_format
        self.ProjPath = str(ProjPath)

    

    def createBaseMaterial(self,matTemplateObj,mltemplate):
        name=os.path.basename(mltemplate.replace('\\',os.sep))
        CT = imageFromRelPath(matTemplateObj["colorTexture"]["DepotPath"]["$value"],self.image_format,DepotPath=self.BasePath, ProjPath=self.ProjPath)
        NT = imageFromRelPath(matTemplateObj["normalTexture"]["DepotPath"]["$value"],self.image_format,isNormal = True,DepotPath=self.BasePath, ProjPath=self.ProjPath)
        RT = imageFromRelPath(matTemplateObj["roughnessTexture"]["DepotPath"]["$value"],self.image_format,isNormal = True,DepotPath=self.BasePath, ProjPath=self.ProjPath)
        MT = imageFromRelPath(matTemplateObj["metalnessTexture"]["DepotPath"]["$value"],self.image_format,isNormal = True,DepotPath=self.BasePath, ProjPath=self.ProjPath)

        TileMult = float(matTemplateObj.get("tilingMultiplier",1))

        NG = bpy.data.node_groups.new(name.split('.')[0],"ShaderNodeTree")
        NG['mlTemplate']=mltemplate
        vers=bpy.app.version
        if vers[0]<4:
            TMI = NG.inputs.new('NodeSocketVector','Tile Multiplier')
            OffU = NG.inputs.new('NodeSocketFloat','OffsetU')
            OffV = NG.inputs.new('NodeSocketFloat','OffsetV')
            NG.outputs.new('NodeSocketColor','Color')
            NG.outputs.new('NodeSocketFloat','Metalness')
            NG.outputs.new('NodeSocketFloat','Roughness')
            NG.outputs.new('NodeSocketColor','Normal')
        else:
            TMI = NG.interface.new_socket(name="Tile Multiplier",socket_type='NodeSocketVector', in_out='INPUT')
            OffU = NG.interface.new_socket(name="OffsetU",socket_type='NodeSocketFloat', in_out='INPUT')
            OffV = NG.interface.new_socket(name="OffsetV",socket_type='NodeSocketFloat', in_out='INPUT')
            NG.interface.new_socket(name="Color", socket_type='NodeSocketColor', in_out='OUTPUT')
            NG.interface.new_socket(name="Metalness", socket_type='NodeSocketFloat', in_out='OUTPUT')
            NG.interface.new_socket(name="Roughness", socket_type='NodeSocketFloat', in_out='OUTPUT')
            NG.interface.new_socket(name="Normal", socket_type='NodeSocketColor', in_out='OUTPUT')

        TMI.default_value = (1,1,1)
        CTN = create_node( NG.nodes, "ShaderNodeTexImage",(0,0),image = CT)

        MTN = create_node( NG.nodes, "ShaderNodeTexImage",(0,-50*1),image = MT)

        RTN = create_node( NG.nodes, "ShaderNodeTexImage",(0,-50*2),image = RT)

        NTN = create_node( NG.nodes, "ShaderNodeTexImage",(0,-50*3),image = NT)

        MapN = create_node( NG.nodes, "ShaderNodeMapping",(-310,-64))

        TexCordN = create_node( NG.nodes, "ShaderNodeTexCoord",(-500,-64))


        combine = create_node(NG.nodes,"ShaderNodeCombineXYZ",  (-600,-60))


        TileMultN = create_node( NG.nodes, "ShaderNodeValue", (-700,-45*2))
        TileMultN.outputs[0].default_value = TileMult

        GroupInN = create_node( NG.nodes, "NodeGroupInput", (-700,-45*4))

        VecMathN = create_node( NG.nodes, "ShaderNodeVectorMath", (-500,-45*3), operation = 'MULTIPLY')

        RGBCurvesConvert = create_node( NG.nodes, "ShaderNodeRGBCurve", (400,-150))
        RGBCurvesConvert.label = "Convert DX to OpenGL Normal"
        RGBCurvesConvert.hide = True
        RGBCurvesConvert.mapping.curves[1].points[0].location = (0,1)
        RGBCurvesConvert.mapping.curves[1].points[1].location = (1,0)
        RGBCurvesConvert.mapping.curves[2].points[0].location = (0,1)
        RGBCurvesConvert.mapping.curves[2].points[1].location = (1,1)

        GroupOutN = create_node( NG.nodes, "NodeGroupOutput", (700,0))

        NG.links.new(TexCordN.outputs['UV'],MapN.inputs['Vector'])
        NG.links.new(VecMathN.outputs[0],MapN.inputs['Scale'])
        NG.links.new(MapN.outputs['Vector'],CTN.inputs['Vector'])
        NG.links.new(MapN.outputs['Vector'],NTN.inputs['Vector'])
        NG.links.new(MapN.outputs['Vector'],RTN.inputs['Vector'])
        NG.links.new(MapN.outputs['Vector'],MTN.inputs['Vector'])
        NG.links.new(TileMultN.outputs[0],VecMathN.inputs[0])
        NG.links.new(GroupInN.outputs[0],VecMathN.inputs[1])
        NG.links.new(GroupInN.outputs[1],combine.inputs[0])
        NG.links.new(GroupInN.outputs[2],combine.inputs[1])
        NG.links.new(CTN.outputs[0],GroupOutN.inputs[0])
        NG.links.new(MTN.outputs[0],GroupOutN.inputs[1])
        NG.links.new(RTN.outputs[0],GroupOutN.inputs[2])
        NG.links.new(NTN.outputs[0],RGBCurvesConvert.inputs[1])
        NG.links.new(RGBCurvesConvert.outputs[0],GroupOutN.inputs[3])
        NG.links.new(combine.outputs[0],MapN.inputs[1])

        return


    def setGlobNormal(self,normalimgpath,CurMat,input):
        GNN = create_node(CurMat.nodes, "ShaderNodeVectorMath",(-200,-250),operation='NORMALIZE')

        GNA = create_node(CurMat.nodes, "ShaderNodeVectorMath",(-400,-250),operation='ADD')

        GNS = create_node(CurMat.nodes, "ShaderNodeVectorMath", (-600,-250),operation='SUBTRACT')
        GNS.name="NormalSubtract"

        GNGeo = create_node(CurMat.nodes, "ShaderNodeNewGeometry", (-800,-250))

        GNMap = CreateShaderNodeNormalMap(CurMat,self.BasePath + normalimgpath,-600,-550,'GlobalNormal',self.image_format)
        CurMat.links.new(GNGeo.outputs['Normal'],GNS.inputs[1])
        CurMat.links.new(GNMap.outputs[0],GNS.inputs[0])
        CurMat.links.new(GNS.outputs[0],GNA.inputs[1])
        CurMat.links.new(input,GNA.inputs[0])
        CurMat.links.new(GNA.outputs[0],GNN.inputs[0])
        return GNN.outputs[0]


    def createLayerMaterial(self,LayerName,LayerCount,CurMat,mlmaskpath,normalimgpath, skip_layers):
        NG = _getOrCreateLayerBlend()
        for x in range(LayerCount-1):
            if x > 0 and x+1 in skip_layers:
                continue
            MaskTexture=None
            projpath = os.path.join(os.path.splitext(os.path.join(self.ProjPath, mlmaskpath))[0] + '_layers', os.path.split(mlmaskpath)[-1:][0][:-7] + "_" + str(x + 1) + ".png")
            basepath = os.path.join(os.path.splitext(os.path.join(self.BasePath, mlmaskpath))[0] + '_layers', os.path.split(mlmaskpath)[-1:][0][:-7] + "_" + str(x + 1) + ".png")
            if os.path.exists(projpath):
                MaskTexture = imageFromPath(projpath, self.image_format, isNormal = True)
            elif os.path.exists(basepath):
                MaskTexture = imageFromPath(basepath, self.image_format, isNormal = True)
            else:
                print('Mask image not found for layer ',x+1)

            LayerGroupN = create_node(CurMat.nodes,"ShaderNodeGroup", (-1400,400-100*x))
            LayerGroupN.node_tree = NG
            LayerGroupN.name = "Layer_"+str(x)
            MaskN=None
            if MaskTexture:
                MaskN = create_node(CurMat.nodes,"ShaderNodeTexImage",(-2400,400-100*x), image = MaskTexture,label="Layer_"+str(x+1))

            #if self.flipMaskY:
            # Mask flip deprecated in WolvenKit deveolpment build 8.7+
            #MaskN.texture_mapping.scale[1] = -1 #flip mask if needed

            predecessorName = "Mat_Mod_Layer_0"
            successorName = "Mat_Mod_Layer_1"
            previousNode = None
            nextNode = None

            # since we are skipping the import for layers with an opacity of 0, we can no longer be certain
            # that everything is directly adjacent to each other.
            if x > 0:
                previousNodeIndex = x-1
                predecessorName = f"Layer_{previousNodeIndex}"
                while previousNodeIndex > 0 and predecessorName not in CurMat.nodes.keys():
                    previousNodeIndex -= 1
                    predecessorName = f"Layer_{previousNodeIndex}"

                nextNodeIndex = x+1
                successorName = f"Mat_Mod_Layer_{nextNodeIndex}"
                while nextNodeIndex < 20 and successorName not in CurMat.nodes.keys():
                    nextNodeIndex += 1
                    successorName = f"Mat_Mod_Layer_{nextNodeIndex}"

            nextNode = CurMat.nodes[successorName] if successorName in CurMat.nodes.keys() else None
            previousNode = CurMat.nodes[predecessorName] if predecessorName in CurMat.nodes.keys() else None

            if previousNode is not None:
                CurMat.links.new(previousNode.outputs[0],LayerGroupN.inputs[0])
                CurMat.links.new(previousNode.outputs[1],LayerGroupN.inputs[1])
                CurMat.links.new(previousNode.outputs[2],LayerGroupN.inputs[2])
                CurMat.links.new(previousNode.outputs[3],LayerGroupN.inputs[3])

            if nextNode is not None:

                CurMat.links.new(nextNode.outputs[0],LayerGroupN.inputs[4])
                CurMat.links.new(nextNode.outputs[1],LayerGroupN.inputs[5])
                CurMat.links.new(nextNode.outputs[2],LayerGroupN.inputs[6])
                CurMat.links.new(nextNode.outputs[3],LayerGroupN.inputs[7])

                if MaskN:
                    CurMat.links.new(MaskN.outputs[0], nextNode.inputs[9])

            if previousNode is not None and nextNode is not None:
                CurMat.links.new(nextNode.outputs[4], LayerGroupN.inputs[8])

        targetLayer = "Mat_Mod_Layer_0"
        for idx in reversed(range(LayerCount)):
            layer_name = f"Layer_{idx}"
            if layer_name in CurMat.nodes.keys():
                targetLayer = layer_name
                break

        CurMat.links.new(CurMat.nodes[targetLayer].outputs[0],CurMat.nodes[loc('Principled BSDF')].inputs['Base Color'])
        CurMat.links.new(CurMat.nodes[targetLayer].outputs[2],CurMat.nodes[loc('Principled BSDF')].inputs['Roughness'])
        CurMat.links.new(CurMat.nodes[targetLayer].outputs[1],CurMat.nodes[loc('Principled BSDF')].inputs['Metallic'])

        if normalimgpath:
            yoink = self.setGlobNormal(normalimgpath,CurMat,CurMat.nodes[targetLayer].outputs[3])
            CurMat.links.new(yoink,CurMat.nodes[loc('Principled BSDF')].inputs['Normal'])
        else:
            CurMat.links.new(CurMat.nodes[targetLayer].outputs[3],CurMat.nodes[loc('Principled BSDF')].inputs['Normal'])


    def create(self,Data,Mat):
        Mat['MLSetup']= Data["MultilayerSetup"]
        mlsetup = JSONTool.openJSON( Data["MultilayerSetup"] + ".json",mode='r',DepotPath=self.BasePath, ProjPath=self.ProjPath)
        mlsetup = mlsetup["Data"]["RootChunk"]
        xllay = mlsetup.get("layers")
        if xllay is None:
            xllay = mlsetup.get("Layers")
        LayerCount = len(xllay)

        LayerIndex = 0
        CurMat = Mat.node_tree

        file_name = os.path.basename(Data["MultilayerSetup"].replace('\\',os.sep))[:-8]

        # clear layer opacity dictionary
        skip_layers = []
        
        for idx,x  in enumerate(xllay):
            opacity = x.get("opacity")
            if opacity is None:
                opacity = x.get("Opacity")

            # if opacity is 0, then the layer has been turned off
            if opacity == 0:
                skip_layers.append(idx)
                LayerIndex += 1
                continue

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

            MicroblendOffsetU = x.get("microblendOffsetU")
            if MicroblendOffsetU is None:
                MicroblendOffsetU = x.get("MicroblendOffsetU")

            MicroblendOffsetV = x.get("microblendOffsetV")
            if MicroblendOffsetV is None:
                MicroblendOffsetV = x.get("MicroblendOffsetV")

            OffsetU = x.get("offsetU")
            if OffsetU is None:
                OffsetU = x.get("OffsetU")

            OffsetV = x.get("offsetV")
            if OffsetV is None:
                OffsetV = x.get("OffsetV")

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

            mltemplate = JSONTool.openJSON( material + ".json",mode='r',DepotPath=self.BasePath, ProjPath=self.ProjPath)
            mltemplate = mltemplate["Data"]["RootChunk"]
            OverrideTable = createOverrideTable(mltemplate)#get override info for colors and what not
           # Mat[os.path.basename(material).split('.')[0]+'_cols']=OverrideTable["ColorScale"]

            layerName = file_name+"_Layer_"+str(LayerIndex)
            NG = bpy.data.node_groups.new(layerName,"ShaderNodeTree")#crLAer's node group
            vers=bpy.app.version
            if vers[0]<4:
                NG.inputs.new('NodeSocketColor','ColorScale')
                NG.inputs.new('NodeSocketFloat','MatTile')
                NG.inputs.new('NodeSocketFloat','MbTile')
                NG.inputs.new('NodeSocketFloat','MicroblendNormalStrength')
                NG.inputs.new('NodeSocketFloat','MicroblendContrast')
                NG.inputs.new('NodeSocketFloat','MicroblendOffsetU')
                NG.inputs.new('NodeSocketFloat','MicroblendOffsetV')
                NG.inputs.new('NodeSocketFloat','NormalStrength')
                NG.inputs.new('NodeSocketFloat','Opacity')
                NG.inputs.new('NodeSocketFloat','Mask')
                NG.outputs.new('NodeSocketColor','Color')
                NG.outputs.new('NodeSocketFloat','Metalness')
                NG.outputs.new('NodeSocketFloat','Roughness')
                NG.outputs.new('NodeSocketVector','Normal')
                NG.outputs.new('NodeSocketFloat','Layer Mask')
                NG.inputs.new('NodeSocketFloat','OffsetU')
                NG.inputs.new('NodeSocketFloat','OffsetV')
                NG_inputs=NG.inputs

            else:
                NG.interface.new_socket(name="ColorScale", socket_type='NodeSocketColor', in_out='INPUT')
                NG.interface.new_socket(name="MatTile", socket_type='NodeSocketFloat', in_out='INPUT')
                NG.interface.new_socket(name="MbTile", socket_type='NodeSocketFloat', in_out='INPUT')
                NG.interface.new_socket(name="MicroblendNormalStrength", socket_type='NodeSocketFloat', in_out='INPUT')
                NG.interface.new_socket(name="MicroblendContrast", socket_type='NodeSocketFloat', in_out='INPUT')
                NG.interface.new_socket(name="MicroblendOffsetU", socket_type='NodeSocketFloat', in_out='INPUT')
                NG.interface.new_socket(name="MicroblendOffsetV", socket_type='NodeSocketFloat', in_out='INPUT')
                NG.interface.new_socket(name="NormalStrength", socket_type='NodeSocketFloat', in_out='INPUT')
                NG.interface.new_socket(name="Opacity", socket_type='NodeSocketFloat', in_out='INPUT')
                NG.interface.new_socket(name="Mask", socket_type='NodeSocketFloat', in_out='INPUT')
                NG.interface.new_socket(name="Color", socket_type='NodeSocketColor', in_out='OUTPUT')
                NG.interface.new_socket(name="Metalness", socket_type='NodeSocketFloat', in_out='OUTPUT')
                NG.interface.new_socket(name="Roughness", socket_type='NodeSocketFloat', in_out='OUTPUT')
                NG.interface.new_socket(name="Normal", socket_type='NodeSocketVector', in_out='OUTPUT')
                NG.interface.new_socket(name="Layer Mask", socket_type='NodeSocketFloat', in_out='OUTPUT')
                NG.interface.new_socket(name="OffsetU", socket_type='NodeSocketFloat', in_out='INPUT')
                NG.interface.new_socket(name="OffsetV", socket_type='NodeSocketFloat', in_out='INPUT')
                NG_inputs=get_inputs(NG)

            NG_inputs[4].min_value = 0
            NG_inputs[4].max_value = 1
            NG_inputs[7].min_value = 0 # No reason to invert these maps, not detail maps.
            NG_inputs[7].max_value = 10 # This value is arbitrary, but more than adequate.
            NG_inputs[8].min_value = 0
            NG_inputs[8].max_value = 1

            LayerGroupN = create_node(CurMat.nodes, "ShaderNodeGroup", (-2000,500-100*idx))
            LayerGroupN.width = 400
            LayerGroupN.node_tree = NG
            LayerGroupN.name = "Mat_Mod_Layer_"+str(LayerIndex)
            LayerIndex += 1

            GroupInN = create_node(NG.nodes, "NodeGroupInput", (-2600,0))

            GroupOutN = create_node(NG.nodes, "NodeGroupOutput", (200,-100))
            LayerGroupN['mlTemplate']=material
            if not bpy.data.node_groups.get(os.path.basename(material.replace('\\',os.sep)).split('.')[0]):
                self.createBaseMaterial(mltemplate,material.replace('\\',os.sep))

            BaseMat = bpy.data.node_groups.get(os.path.basename(material.replace('\\',os.sep)).split('.')[0])
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

            if MicroblendOffsetU != None:
                LayerGroupN.inputs[5].default_value = float(MicroblendOffsetU)
            else:
                LayerGroupN.inputs[5].default_value = 0

            if MicroblendOffsetV != None:
                LayerGroupN.inputs[6].default_value = float(MicroblendOffsetV)
            else:
                LayerGroupN.inputs[6].default_value = 0

            if normalStrength != None and normalStrength in OverrideTable["NormalStrength"]:
                LayerGroupN.inputs[7].default_value = OverrideTable["NormalStrength"][normalStrength]
            else:
                LayerGroupN.inputs[7].default_value = 1

            if opacity != None:
                LayerGroupN.inputs[8].default_value = float(opacity)
            else:
                LayerGroupN.inputs[8].default_value = 1


            if OffsetU !=None:
                LayerGroupN.inputs[10].default_value=OffsetU
            else:
                LayerGroupN.inputs[10].default_value=0

            if OffsetV !=None:
                LayerGroupN.inputs[11].default_value=OffsetV
            else:
                LayerGroupN.inputs[11].default_value=0

            # DEFINES MAIN MULTILAYERED PROPERTIES

            # Node for blending colorscale color with diffuse texture of mltemplate
            # Changed from multiply to overlay because multiply is a darkening blend mode, and colors appear too dark. Overlay is still probably wrong - jato
            if colorScale != "null" and colorScale != "null_null":
                ColorScaleMixN = create_node(NG.nodes,"ShaderNodeMixRGB",(-1400,100),blend_type='MIX')
                ColorScaleMixN.inputs[0].default_value=1
                if 'logos' in BaseMat.name:
                    ColorScaleMixN.blend_type='MULTIPLY'
            else:
                ColorScaleMixN = None

            # Microblend texture node
            MBN = create_node(NG.nodes,"ShaderNodeTexImage",(-2300,-800),image = MBI,label = "Microblend")

            # Flips normal map when mb normal strength is negative - invert RG channels
            MBRGBCurveN = create_node(NG.nodes,"ShaderNodeRGBCurve",(-1700,-350))
            MBRGBCurveN.mapping.curves[0].points[0].location = (0,1)
            MBRGBCurveN.mapping.curves[0].points[1].location = (1,0)
            MBRGBCurveN.mapping.curves[1].points[0].location = (0,1)
            MBRGBCurveN.mapping.curves[1].points[1].location = (1,0)
            MBRGBCurveN.width = 150

            # Flips normal map when mb normal strength is negative - returns 0 or 1 based on positive or negative mb normal strength value
            MBGrtrThanN = create_node(NG.nodes,"ShaderNodeMath", (-1400,-300),operation = 'GREATER_THAN')
            MBGrtrThanN.inputs[1].default_value = 0

            # Flips normal map when mb normal strength is negative - mix node uses greater than node like a bool for positive/negative
            MBMixN = create_node(NG.nodes,"ShaderNodeMixRGB", (-1400,-350), blend_type ='MIX', label = "MB+- Norm Mix")

            MBMapping = create_node(NG.nodes,"ShaderNodeMapping", (-2300,-650))

            MBUVCombine = create_node(NG.nodes,"ShaderNodeCombineXYZ", (-2300,-550))

            MBTexCord = create_node(NG.nodes,"ShaderNodeTexCoord", (-2300,-500))

            # Multiply normal strength against microblend contrast
            # Results in hidden mb-normals when mbcontrast = 0. This is almost certainly wrong but it's good enough for now -jato
            MBNormMultiply = create_node(NG.nodes,"ShaderNodeMath", (-1600,-200),operation = 'MULTIPLY')

            # Absolute value is necessary because Blender does not support negative normal map values in this node
            MBNormAbsN = create_node(NG.nodes,"ShaderNodeMath", (-1400,-200),operation = 'ABSOLUTE')

            # Hides mb normal map where mask is fully opaque/white/1
            MBNormSubtractMask = create_node(NG.nodes, "ShaderNodeMath", (-1200, -250), operation = 'SUBTRACT')
            MBNormSubtractMask.use_clamp = True

            # Final microblend normal map node
            MBNormalN = create_node(NG.nodes,"ShaderNodeNormalMap", (-750,-200))

            NormSubN = create_node(NG.nodes,"ShaderNodeVectorMath", (-550, -200), operation = 'SUBTRACT')

            GeoN = create_node(NG.nodes,"ShaderNodeNewGeometry", (-550, -350))

            # Sets mltemplate normal strength
            NormStrengthN = create_node(NG.nodes,"ShaderNodeNormalMap", (-1400,-100), label = "NormalStrength")

            # Adds microblend normal map to mltemplate normal map. This works because both maps have been vectorized to -1 --> +1 range
            NormalCombineN = create_node(NG.nodes,"ShaderNodeVectorMath", (-550,-100), operation = 'ADD')

            NormalizeN =create_node(NG.nodes,"ShaderNodeVectorMath", (-350,-100), operation = 'NORMALIZE')

            # Roughness
            RoughRampN = create_node(NG.nodes,"ShaderNodeMapRange", (-1400,0), label = "Roughness Ramp")
            if roughLevelsOut in OverrideTable["RoughLevelsOut"].keys():
                RoughRampN.inputs['To Min'].default_value = (OverrideTable["RoughLevelsOut"][roughLevelsOut][1][0])
                RoughRampN.inputs['To Max'].default_value = (OverrideTable["RoughLevelsOut"][roughLevelsOut][0][0])

            # Metalness
            MetalRampN = create_node(NG.nodes,"ShaderNodeValToRGB", (-1400,50),label = "Metal Ramp")
            MetalRampN.width = 150
            if metalLevelsOut in OverrideTable["MetalLevelsOut"].keys():
                MetalRampN.color_ramp.elements[1].color = (OverrideTable["MetalLevelsOut"][metalLevelsOut][0])
                MetalRampN.color_ramp.elements[0].color = (OverrideTable["MetalLevelsOut"][metalLevelsOut][1])

            # --- Mask Layer ---

            # MicroOffset prevents shader error when microblend contrast is exactly zero
            MBCMicroOffset = create_node(NG.nodes,"ShaderNodeMath", (-2000,-200), operation = 'ADD', label = "Micro-offset")
            MBCMicroOffset.inputs[1].default_value = 0.0001


            mask_mixer=mask_mixer_node_group()
            #node Group
            mask_mixergroup = NG.nodes.new("ShaderNodeGroup")
            mask_mixergroup.name = "Group"
            mask_mixergroup.node_tree = mask_mixer
            #Socket_1
            mask_mixergroup.inputs[0].default_value = (0.5, 0.5, 0.5, 1.0)
            #Socket_2
            mask_mixergroup.inputs[1].default_value = (0.5, 0.5, 0.5, 1.0)
            #Socket_3
            mask_mixergroup.inputs[2].default_value = 0.5
            #Socket_4
            mask_mixergroup.inputs[3].default_value = 1.0
            #Set locations
            mask_mixergroup.location = (-1550, -600)
            #Set dimensions
            mask_mixergroup.width, mask_mixergroup.height = 287.65118408203125, 100.0




            # CREATE FINAL LINKS
            if ColorScaleMixN is not None:
                NG.links.new(GroupInN.outputs[0],ColorScaleMixN.inputs[2])
            NG.links.new(GroupInN.outputs[1],BMN.inputs[0])
            NG.links.new(GroupInN.outputs[2],MBMapping.inputs[3])
            NG.links.new(GroupInN.outputs[3],MBGrtrThanN.inputs[0])
            NG.links.new(GroupInN.outputs[3],MBNormMultiply.inputs[0])
            NG.links.new(GroupInN.outputs[4],MBCMicroOffset.inputs[0])
            NG.links.new(GroupInN.outputs[5],MBUVCombine.inputs[0])
            NG.links.new(GroupInN.outputs[6],MBUVCombine.inputs[1])
            NG.links.new(GroupInN.outputs[7],NormStrengthN.inputs[0])
            NG.links.new(GroupInN.outputs[9],MBNormSubtractMask.inputs[1])
            if len(BMN.inputs) > 1:
              NG.links.new(GroupInN.outputs[10],BMN.inputs[1])
              if len(BMN.inputs) > 2:
                NG.links.new(GroupInN.outputs[11],BMN.inputs[2])
            NG.links.new(MBCMicroOffset.outputs[0],MBNormMultiply.inputs[1])
            NG.links.new(MBTexCord.outputs[2],MBMapping.inputs[0])
            NG.links.new(MBUVCombine.outputs[0],MBMapping.inputs[1])
            NG.links.new(MBMapping.outputs[0],MBN.inputs[0])
            NG.links.new(MBN.outputs[0],MBRGBCurveN.inputs[1])
            NG.links.new(MBN.outputs[0],MBMixN.inputs[2])            
            if ColorScaleMixN is not None:
                NG.links.new(BMN.outputs[0],ColorScaleMixN.inputs[1])
            else:
                NG.links.new(BMN.outputs[0],GroupOutN.inputs[0])
            NG.links.new(BMN.outputs[1],MetalRampN.inputs[0])
            NG.links.new(BMN.outputs[2],RoughRampN.inputs[0])
            NG.links.new(BMN.outputs[3],NormStrengthN.inputs[1])
            NG.links.new(NormStrengthN.outputs[0],NormalCombineN.inputs[0])
            NG.links.new(MBGrtrThanN.outputs[0],MBMixN.inputs[0])
            NG.links.new(MBRGBCurveN.outputs[0],MBMixN.inputs[1])
            NG.links.new(MBMixN.outputs[0],MBNormalN.inputs[1])
            NG.links.new(MBNormMultiply.outputs[0],MBNormAbsN.inputs[0])
            NG.links.new(MBNormAbsN.outputs[0],MBNormSubtractMask.inputs[0])
            NG.links.new(MBNormSubtractMask.outputs[0],MBNormalN.inputs[0])
            NG.links.new(MBNormalN.outputs[0],NormSubN.inputs[0])
            NG.links.new(GeoN.outputs['Normal'],NormSubN.inputs[1])
            NG.links.new(NormSubN.outputs[0],NormalCombineN.inputs[1])
            NG.links.new(NormalCombineN.outputs[0],NormalizeN.inputs[0])

            if ColorScaleMixN is not None:
                NG.links.new(ColorScaleMixN.outputs[0],GroupOutN.inputs[0]) #Color output
            NG.links.new(MetalRampN.outputs[0],GroupOutN.inputs[1]) #Metalness output
            NG.links.new(RoughRampN.outputs[0],GroupOutN.inputs[2]) #Roughness output
            NG.links.new(NormalizeN.outputs[0],GroupOutN.inputs[3]) #Normal output

            NG.links.new(mask_mixergroup.outputs[0], MBNormSubtractMask.inputs[1])
            NG.links.new(mask_mixergroup.outputs[0], GroupOutN.inputs[4])
            NG.links.new(MBN.outputs[1], mask_mixergroup.inputs[1])
            NG.links.new(GroupInN.outputs[4], mask_mixergroup.inputs[2])
            NG.links.new(GroupInN.outputs[8], mask_mixergroup.inputs[3])
            NG.links.new(GroupInN.outputs[9], mask_mixergroup.inputs[0])

        # Data for vehicledestrblendshape.mt
        # Instead of maintaining two material py files we should setup the main multilayered shader to handle variants such as the vehicle material
        if "BakedNormal" in Data.keys():
            LayerNormal=Data["BakedNormal"]
        else:
            LayerNormal=Data["GlobalNormal"]

        self.createLayerMaterial(file_name+"_Layer_", LayerCount, CurMat, Data["MultilayerMask"], LayerNormal, skip_layers)

  


    


