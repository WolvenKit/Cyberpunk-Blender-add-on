import bpy
import os
from ..main.common import *
from ..jsontool import JSONTool
import numpy as np

def np_array_from_image(img_name):
    img = bpy.data.images[img_name]
    return np.array(img.pixels[:])

def mask_mixer_node_group():
    if "Mask Mixer" in bpy.data.node_groups:
        return bpy.data.node_groups["Mask Mixer"]
    mask_mixer = bpy.data.node_groups.new(type = 'ShaderNodeTree', name = "Mask Mixer")
    
    #sockets
    normal_map_socket = mask_mixer.interface.new_socket(name = "Normal Map", in_out='OUTPUT', socket_type = 'NodeSocketVector')
    layer_mask_socket = mask_mixer.interface.new_socket(name = "Layer Mask", in_out='OUTPUT', socket_type = 'NodeSocketFloat')
    
    microblendnormalstrength_socket = mask_mixer.interface.new_socket(name = "MicroblendNormalStrength", in_out='INPUT', socket_type = 'NodeSocketFloat')
    microblendcontrast_socket = mask_mixer.interface.new_socket(name = "MicroblendContrast", in_out='INPUT', socket_type = 'NodeSocketFloat')
    opacity_socket = mask_mixer.interface.new_socket(name = "Opacity", in_out='INPUT', socket_type = 'NodeSocketFloat')
    mask_socket = mask_mixer.interface.new_socket(name = "Mask", in_out='INPUT', socket_type = 'NodeSocketFloat')
    microblend_socket = mask_mixer.interface.new_socket(name = "Microblend", in_out='INPUT', socket_type = 'NodeSocketColor')
    microblend_alpha_socket = mask_mixer.interface.new_socket(name = "Microblend Alpha", in_out='INPUT', socket_type = 'NodeSocketFloat')

    
    #initialize mask_mixer nodes
    maskMixerInput = mask_mixer.nodes.new("NodeGroupInput")
    maskMixerInput.location = (-1000.0, -280.0)
    maskMixerInput.width, maskMixerInput.height = 140.0, 100.0

    maskMixerOutput = mask_mixer.nodes.new("NodeGroupOutput")
    maskMixerOutput.location = (1220.0, -360.0)
    maskMixerOutput.width, maskMixerOutput.height = 140.0, 100.0

    mbContrastMax = mask_mixer.nodes.new("ShaderNodeMath")
    mbContrastMax.location = (-700, -350)
    mbContrastMax.operation = 'MAXIMUM'
    mbContrastMax.hide = True
    mbContrastMax.inputs[1].default_value = 0.00001

    mbNormalVectorize = mask_mixer.nodes.new("ShaderNodeVectorMath")
    mbNormalVectorize.location = (650, -350)
    mbNormalVectorize.operation = 'MULTIPLY_ADD'
    mbNormalVectorize.inputs[1].default_value = 2, 2, 0
    mbNormalVectorize.inputs[2].default_value = -1, -1, 0

    mbNormalStr = mask_mixer.nodes.new("ShaderNodeVectorMath")
    mbNormalStr.location = (900, -300)
    mbNormalStr.operation = 'MULTIPLY'

    mbMultiply = mask_mixer.nodes.new("ShaderNodeMath")
    mbMultiply.location = (350, 50)
    mbMultiply.operation = 'MULTIPLY'

    mbNorm1Minus = mask_mixer.nodes.new("ShaderNodeMath")
    mbNorm1Minus.operation = 'SUBTRACT'
    mbNorm1Minus.location = (350, -250)
    mbNorm1Minus.inputs[0].default_value = 1.0

    mbNormMultiply = mask_mixer.nodes.new("ShaderNodeMath")
    mbNormMultiply.operation = 'MULTIPLY'
    mbNormMultiply.location = (350, -100)
    mbNormMultiply.use_clamp = True
    mbNormMultiply.inputs[1].default_value = 2.0

    maskReroute = mask_mixer.nodes.new("NodeReroute")
    maskReroute.name = "Reroute"
    maskReroute.location = (-650, -550)

    maskAdd = mask_mixer.nodes.new("ShaderNodeMath")
    maskAdd.operation = 'ADD'
    maskAdd.use_clamp = False
    maskAdd.location = (-500, -900)

    maskSubtract = mask_mixer.nodes.new("ShaderNodeMath")
    maskSubtract.operation = 'SUBTRACT'
    maskSubtract.use_clamp = False
    maskSubtract.inputs[1].default_value = 1.0
    maskSubtract.location = (-300, -900)

    maskMix = mask_mixer.nodes.new("ShaderNodeMix")
    maskMix.location = (-100, -700)

    maskMapRange = mask_mixer.nodes.new("ShaderNodeMapRange")
    maskMapRange.interpolation_type = 'SMOOTHSTEP'
    maskMapRange.location = (100, -600)

    maskMultiply = mask_mixer.nodes.new("ShaderNodeMath")
    maskMultiply.label = "opacity"
    maskMultiply.operation = 'MULTIPLY'
    maskMultiply.use_clamp = False
    maskMultiply.location = (350, -450)

    #initialize mask_mixer links
    mask_mixer.links.new(maskMixerInput.outputs[0], mbMultiply.inputs[0])
    mask_mixer.links.new(maskMixerInput.outputs[1], mbContrastMax.inputs[0])
    mask_mixer.links.new(maskMixerInput.outputs[2], maskReroute.inputs[0])
    mask_mixer.links.new(maskMixerInput.outputs[3], maskMix.inputs[3])
    mask_mixer.links.new(maskMixerInput.outputs[3], maskAdd.inputs[0])
    mask_mixer.links.new(maskMixerInput.outputs[4], mbNormalVectorize.inputs[0])
    mask_mixer.links.new(maskMixerInput.outputs[5], maskAdd.inputs[1])
    mask_mixer.links.new(mbContrastMax.outputs[0], maskMix.inputs[0])
    mask_mixer.links.new(mbContrastMax.outputs[0], maskMapRange.inputs[2])
    mask_mixer.links.new(maskReroute.outputs[0], maskMultiply.inputs[1])
    mask_mixer.links.new(maskAdd.outputs[0], maskSubtract.inputs[0])
    mask_mixer.links.new(maskSubtract.outputs[0], maskMix.inputs[2])
    mask_mixer.links.new(maskMix.outputs[0], maskMapRange.inputs[0])
    mask_mixer.links.new(maskMapRange.outputs[0], maskMultiply.inputs[0])
    mask_mixer.links.new(maskMapRange.outputs[0], mbNorm1Minus.inputs[1])
    mask_mixer.links.new(mbNorm1Minus.outputs[0], mbNormMultiply.inputs[0])
    mask_mixer.links.new(mbNormMultiply.outputs[0], mbMultiply.inputs[1])
    mask_mixer.links.new(mbMultiply.outputs[0], mbNormalStr.inputs[1])
    mask_mixer.links.new(mbNormalVectorize.outputs[0], mbNormalStr.inputs[0])
    mask_mixer.links.new(maskMixerInput.outputs[2], maskReroute.inputs[0])
    mask_mixer.links.new(maskReroute.outputs[0], maskMultiply.inputs[1])
    mask_mixer.links.new(mbNormalStr.outputs[0], maskMixerOutput.inputs[0])
    mask_mixer.links.new(maskMultiply.outputs[0], maskMixerOutput.inputs[1])

    return mask_mixer

def levels_node_group():
    if "Levels 2077" in bpy.data.node_groups:
        return bpy.data.node_groups["Levels 2077"]
    levels = bpy.data.node_groups.new(type = 'ShaderNodeTree', name = "Levels 2077")

    a_socket = levels.interface.new_socket(name = "Input", in_out='INPUT', socket_type = 'NodeSocketFloat')
    b_socket = levels.interface.new_socket(name = "[0]", in_out='INPUT', socket_type = 'NodeSocketFloat')
    c_socket = levels.interface.new_socket(name = "[1]", in_out='INPUT', socket_type = 'NodeSocketFloat')
    result_socket = levels.interface.new_socket(name = "Result", in_out='OUTPUT', socket_type = 'NodeSocketFloat')

    levelsInput = levels.nodes.new("NodeGroupInput")
    levelsInput.location = (-1500, 0)
    
    levelsOutput = levels.nodes.new("NodeGroupOutput")
    levelsOutput.location = (100, 0)

    levelsMultAdd = levels.nodes.new("ShaderNodeMath")
    levelsMultAdd.operation = 'MULTIPLY_ADD'
    levelsMultAdd.location = (-1150, 0)

    levels.links.new(levelsInput.outputs[0], levelsMultAdd.inputs[0])
    levels.links.new(levelsInput.outputs[1], levelsMultAdd.inputs[1])
    levels.links.new(levelsInput.outputs[2], levelsMultAdd.inputs[2])
    levels.links.new(levelsMultAdd.outputs[0], levelsOutput.inputs[0])

    return levels

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

    GroupInN = create_node(NG.nodes,"NodeGroupInput", (-700,0))
    GroupInN.hide = False

    GroupOutN = create_node(NG.nodes,"NodeGroupOutput",(0,0), hide=False)

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
        colorMaskIn = matTemplateObj["colorMaskLevelsIn"]["Elements"]
        colorMaskOut = matTemplateObj["colorMaskLevelsOut"]["Elements"]

        NG = bpy.data.node_groups.new(name.split('.')[0],"ShaderNodeTree")
        NG['mlTemplate']=mltemplate
        vers=bpy.app.version
        if vers[0]<4:
            Color = NG.inputs.new('NodeSocketColor','ColorScale')
            TMI = NG.inputs.new('NodeSocketFloat','MatTile')
            OffU = NG.inputs.new('NodeSocketFloat','OffsetU')
            OffV = NG.inputs.new('NodeSocketFloat','OffsetV')
            NRMSTR = NG.inputs.new('NodeSocketFloat','NormalStrength')
            NG.outputs.new('NodeSocketColor','Color')
            NG.outputs.new('NodeSocketFloat','Metalness')
            NG.outputs.new('NodeSocketFloat','Roughness')
            NG.outputs.new('NodeSocketVector','Normal')
        else:
            Color = NG.interface.new_socket(name="ColorScale",socket_type='NodeSocketColor', in_out='INPUT')
            TMI = NG.interface.new_socket(name="MatTile",socket_type='NodeSocketFloat', in_out='INPUT')
            OffU = NG.interface.new_socket(name="OffsetU",socket_type='NodeSocketFloat', in_out='INPUT')
            OffV = NG.interface.new_socket(name="OffsetV",socket_type='NodeSocketFloat', in_out='INPUT')
            NRMSTR = NG.interface.new_socket(name="NormalStrength",socket_type='NodeSocketFloat', in_out='INPUT')
            NG.interface.new_socket(name="Color", socket_type='NodeSocketColor', in_out='OUTPUT')
            NG.interface.new_socket(name="Metalness", socket_type='NodeSocketFloat', in_out='OUTPUT')
            NG.interface.new_socket(name="Roughness", socket_type='NodeSocketFloat', in_out='OUTPUT')
            NG.interface.new_socket(name="Normal", socket_type='NodeSocketVector', in_out='OUTPUT')

        TMI.default_value = (1)
        CTN = create_node( NG.nodes, "ShaderNodeTexImage",(0,0),image = CT)
        CTN.width = 300
        MTN = create_node( NG.nodes, "ShaderNodeTexImage",(0,-50*1),image = MT)
        MTN.width = 300
        RTN = create_node( NG.nodes, "ShaderNodeTexImage",(0,-50*2),image = RT)
        RTN.width = 300
        NTN = create_node( NG.nodes, "ShaderNodeTexImage",(0,-50*3),image = NT)
        NTN.width = 300

        TexCordN = create_node( NG.nodes, "ShaderNodeTexCoord",(-300,50))
        combineOffUV = create_node(NG.nodes,"ShaderNodeCombineXYZ",  (-500,-100))
        VecMathN = create_node( NG.nodes, "ShaderNodeVectorMath", (-500,-50), operation = 'MULTIPLY')
        MapN = create_node( NG.nodes, "ShaderNodeMapping",(-300,-50))

        TileMultN = create_node( NG.nodes, "ShaderNodeValue", (-500,50))
        TileMultN.label = "Tile Multiplier"
        TileMultN.outputs[0].default_value = TileMult

        # JATO: As far as I can tell colormasklevelsin does nothing? Commented these out but useful for dev
        # colorMaskIn0 = create_node( NG.nodes, "ShaderNodeValue", (-300,550))
        # colorMaskIn0.label = "ColorMaskLevelsIn 0"
        # colorMaskIn0.width = 200
        # colorMaskIn0.outputs[0].default_value = colorMaskIn[0]
        # colorMaskIn1 = create_node( NG.nodes, "ShaderNodeValue", (-300,500))
        # colorMaskIn1.label = "ColorMaskLevelsIn 1"
        # colorMaskIn1.width = 200
        # colorMaskIn1.outputs[0].default_value = colorMaskIn[1]
        # colorMaskOut0 = create_node( NG.nodes, "ShaderNodeValue", (-300,450))
        # colorMaskOut0.label = "ColorMaskLevelsOut 0"
        # colorMaskOut0.width = 200
        # colorMaskOut0.outputs[0].default_value = colorMaskOut[0]
        # colorMaskOut1 = create_node( NG.nodes, "ShaderNodeValue", (-300,400))
        # colorMaskOut1.label = "ColorMaskLevelsOut 1"
        # colorMaskOut1.width = 200
        # colorMaskOut1.outputs[0].default_value = colorMaskOut[1]

        ColorRampOut = create_node(NG.nodes,"ShaderNodeValToRGB", (-300,300), label = "Color Out")
        ColorRampOut.inputs[0].default_value = 1
        # JATO: We do wacky hack here with 0.9999999 to keep element 0 position from moving past element 1 position when they are the same
        ColorRampOut.color_ramp.elements[0].position = 0.9999999 - colorMaskOut[0]
        ColorRampOut.color_ramp.elements[0].color = colorMaskOut[1], colorMaskOut[1], colorMaskOut[1], 1

        colorScaleMix = create_node(NG.nodes,"ShaderNodeMixRGB",(400,250),blend_type='MULTIPLY')
        colorScaleMix.inputs[0].default_value = colorMaskOut[1]
        colorScaleMix.hide = False

        normalVectorize = create_node( NG.nodes, "ShaderNodeVectorMath",(400,-150), operation='MULTIPLY_ADD')
        normalVectorize.inputs[1].default_value = 2, 2, 0
        normalVectorize.inputs[2].default_value = -1, -1, 0

        normalMultiply = create_node( NG.nodes, "ShaderNodeVectorMath",(650,-250), operation='MULTIPLY')

        GroupInN = create_node( NG.nodes, "NodeGroupInput", (-1000,0))
        GroupInN['mlTemplate']=mltemplate
        GroupInN.hide = False
        GroupOutN = create_node( NG.nodes, "NodeGroupOutput", (1000,0))
        GroupOutN.hide = False

        NG.links.new(GroupInN.outputs[0],colorScaleMix.inputs[2])
        NG.links.new(GroupInN.outputs[1],VecMathN.inputs[1])
        NG.links.new(GroupInN.outputs[2],combineOffUV.inputs[0])
        NG.links.new(GroupInN.outputs[3],combineOffUV.inputs[1])
        NG.links.new(GroupInN.outputs[4],normalMultiply.inputs[1])
        NG.links.new(TexCordN.outputs['UV'],MapN.inputs['Vector'])
        NG.links.new(VecMathN.outputs[0],MapN.inputs['Scale'])
        NG.links.new(MapN.outputs['Vector'],CTN.inputs['Vector'])
        NG.links.new(MapN.outputs['Vector'],NTN.inputs['Vector'])
        NG.links.new(MapN.outputs['Vector'],RTN.inputs['Vector'])
        NG.links.new(MapN.outputs['Vector'],MTN.inputs['Vector'])
        NG.links.new(TileMultN.outputs[0],VecMathN.inputs[0])
        # NG.links.new(colorMaskOut1.outputs[0],colorScaleMix.inputs[0])
        NG.links.new(ColorRampOut.outputs[0],colorScaleMix.inputs[0])
        NG.links.new(CTN.outputs[0],colorScaleMix.inputs[1])
        NG.links.new(colorScaleMix.outputs[0],GroupOutN.inputs[0])
        NG.links.new(MTN.outputs[0],GroupOutN.inputs[1])
        NG.links.new(RTN.outputs[0],GroupOutN.inputs[2])
        NG.links.new(NTN.outputs[0],normalVectorize.inputs[0])
        NG.links.new(normalVectorize.outputs[0],normalMultiply.inputs[0])
        NG.links.new(normalMultiply.outputs[0],GroupOutN.inputs[3])
        NG.links.new(combineOffUV.outputs[0],MapN.inputs[1])
        NG.links.new(ColorRampOut.outputs[0],colorScaleMix.inputs[0])

        return


    def setGlobNormal(self,normalimgpath,CurMat,input):
        GNA = create_node(CurMat.nodes, "ShaderNodeVectorMath",(-600,-250),operation='ADD')
        normalCreateVecZGroup = CreateCalculateVecNormalZ(CurMat,-400,-250)
        GNN = create_node(CurMat.nodes, "ShaderNodeNormalMap",(-200,-250))

        GNMap = CreateShaderNodeGlobalNormalMap(CurMat,self.BasePath + normalimgpath,-600,-100,'GlobalNormal',self.image_format)
        CurMat.links.new(GNMap.outputs[0],GNA.inputs[0])
        CurMat.links.new(input,GNA.inputs[1])
        CurMat.links.new(GNA.outputs[0],normalCreateVecZGroup.inputs[0])
        CurMat.links.new(normalCreateVecZGroup.outputs[0],GNN.inputs[1])
        return GNN.outputs[0]


    def createLayerMaterial(self,LayerName,LayerCount,CurMat,mlmaskpath,normalimgpath, skip_layers):
        NG = _getOrCreateLayerBlend()
        for x in range(LayerCount-1):
            # if x > 0 and x+1 in skip_layers:
            #     continue
            MaskTexture=None
            projpath = os.path.join(os.path.splitext(os.path.join(self.ProjPath, mlmaskpath))[0] + '_layers', os.path.split(mlmaskpath)[-1:][0][:-7] + "_" + str(x + 1) + ".png")
            basepath = os.path.join(os.path.splitext(os.path.join(self.BasePath, mlmaskpath))[0] + '_layers', os.path.split(mlmaskpath)[-1:][0][:-7] + "_" + str(x + 1) + ".png")
            if os.path.exists(projpath):
                MaskTexture = imageFromPath(projpath, self.image_format, isNormal = True)
            elif os.path.exists(basepath):
                MaskTexture = imageFromPath(basepath, self.image_format, isNormal = True)
            else:
                if 'AppData' in basepath:
                    print('Mask image not found for layer ',x+1,' DepotPath appears to be in Appdata, this is known to cause issues')
                else:
                    print('Mask image not found for layer ',x+1)


            LayerGroupN = create_node(CurMat.nodes,"ShaderNodeGroup", (-1400,400-100*x))
            LayerGroupN.node_tree = NG
            LayerGroupN.name = "Layer_"+str(x)
            MaskN=None
            if MaskTexture:
                # MaskN = create_node(CurMat.nodes,"ShaderNodeTexImage",(-2400,400-100*x), image = MaskTexture,label="Layer_"+str(x+1))
                MaskN = create_node(CurMat.nodes,"ShaderNodeTexImage",(-2400,400-100*x), image = MaskTexture)
                MaskN.width = 300
                if x+1 in skip_layers:
                    MaskN.mute = True

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
                    CurMat.links.new(MaskN.outputs[0], nextNode.inputs[11])

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

            roughLevelsIn = x["roughLevelsIn"].get("$value")
            if roughLevelsIn is None:
                roughLevelsIn = x["RoughLevelsIn"].get("$value")
            
            roughLevelsOut = x["roughLevelsOut"].get("$value")
            if roughLevelsOut is None:
                roughLevelsOut = x["RoughLevelsOut"].get("$value")

            metalLevelsIn = x["metalLevelsIn"].get("$value")
            if metalLevelsIn is None:
                metalLevelsIn = x["MetalLevelsIn"].get("$value")

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
                NG.inputs.new('NodeSocketFloat','OffsetU')
                NG.inputs.new('NodeSocketFloat','OffsetV')
                NG.inputs.new('NodeSocketFloat','NormalStrength')
                NG.inputs.new('NodeSocketFloat','MicroblendNormalStrength')
                NG.inputs.new('NodeSocketFloat','MicroblendContrast')
                NG.inputs.new('NodeSocketFloat','MbTile')
                NG.inputs.new('NodeSocketFloat','MicroblendOffsetU')
                NG.inputs.new('NodeSocketFloat','MicroblendOffsetV')
                NG.inputs.new('NodeSocketFloat','Opacity')
                NG.inputs.new('NodeSocketFloat','Mask')
                NG.outputs.new('NodeSocketColor','Color')
                NG.outputs.new('NodeSocketFloat','Metalness')
                NG.outputs.new('NodeSocketFloat','Roughness')
                NG.outputs.new('NodeSocketVector','Normal')
                NG.outputs.new('NodeSocketFloat','Layer Mask')
                NG_inputs=NG.inputs

            else:
                NG.interface.new_socket(name="ColorScale", socket_type='NodeSocketColor', in_out='INPUT')
                NG.interface.new_socket(name="MatTile", socket_type='NodeSocketFloat', in_out='INPUT')
                NG.interface.new_socket(name="OffsetU", socket_type='NodeSocketFloat', in_out='INPUT')
                NG.interface.new_socket(name="OffsetV", socket_type='NodeSocketFloat', in_out='INPUT')
                NG.interface.new_socket(name="NormalStrength", socket_type='NodeSocketFloat', in_out='INPUT')
                NG.interface.new_socket(name="MicroblendNormalStrength", socket_type='NodeSocketFloat', in_out='INPUT')
                NG.interface.new_socket(name="MicroblendContrast", socket_type='NodeSocketFloat', in_out='INPUT')
                NG.interface.new_socket(name="MbTile", socket_type='NodeSocketFloat', in_out='INPUT')
                NG.interface.new_socket(name="MicroblendOffsetU", socket_type='NodeSocketFloat', in_out='INPUT')
                NG.interface.new_socket(name="MicroblendOffsetV", socket_type='NodeSocketFloat', in_out='INPUT')
                NG.interface.new_socket(name="Opacity", socket_type='NodeSocketFloat', in_out='INPUT')
                NG.interface.new_socket(name="Mask", socket_type='NodeSocketFloat', in_out='INPUT')
                NG.interface.new_socket(name="Color", socket_type='NodeSocketColor', in_out='OUTPUT')
                NG.interface.new_socket(name="Metalness", socket_type='NodeSocketFloat', in_out='OUTPUT')
                NG.interface.new_socket(name="Roughness", socket_type='NodeSocketFloat', in_out='OUTPUT')
                NG.interface.new_socket(name="Normal", socket_type='NodeSocketVector', in_out='OUTPUT')
                NG.interface.new_socket(name="Layer Mask", socket_type='NodeSocketFloat', in_out='OUTPUT')
                NG_inputs=get_inputs(NG)

            NG_inputs[6].min_value = 0
            NG_inputs[6].max_value = 1
            NG_inputs[4].min_value = 0 # No reason to invert these maps, not detail maps.
            NG_inputs[4].max_value = 10 # This value is arbitrary, but more than adequate.
            NG_inputs[10].min_value = 0
            NG_inputs[10].max_value = 1

            LayerGroupN = create_node(CurMat.nodes, "ShaderNodeGroup", (-2000,500-100*idx))
            LayerGroupN.width = 400
            LayerGroupN.node_tree = NG
            LayerGroupN.name = "Mat_Mod_Layer_"+str(LayerIndex)
            LayerIndex += 1

            GroupInN = create_node(NG.nodes, "NodeGroupInput", (-2600,0))
            GroupInN.hide = False

            GroupOutN = create_node(NG.nodes, "NodeGroupOutput", (-200,0))
            GroupOutN.hide = False
            LayerGroupN['mlTemplate']=material
            if not bpy.data.node_groups.get(os.path.basename(material.replace('\\',os.sep)).split('.')[0]):
                self.createBaseMaterial(mltemplate,material.replace('\\',os.sep))

            BaseMat = bpy.data.node_groups.get(os.path.basename(material.replace('\\',os.sep)).split('.')[0])
            if BaseMat:
                BMN = create_node(NG.nodes,"ShaderNodeGroup", (-2000,0))
                BMN.width = 300
                BMN.hide = False
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

            if OffsetU !=None:
                LayerGroupN.inputs[2].default_value= OffsetU
            else:
                LayerGroupN.inputs[2].default_value=0

            if OffsetV !=None:
                LayerGroupN.inputs[3].default_value= OffsetV
            else:
                LayerGroupN.inputs[3].default_value=0

            if normalStrength != None and normalStrength in OverrideTable["NormalStrength"]:
                LayerGroupN.inputs[4].default_value = OverrideTable["NormalStrength"][normalStrength]
            else:
                LayerGroupN.inputs[4].default_value = 1

            if microblendNormalStrength != None:
                LayerGroupN.inputs[5].default_value = float(microblendNormalStrength)
            else:
                LayerGroupN.inputs[5].default_value = 1

            if MicroblendContrast != None:
                LayerGroupN.inputs[6].default_value = float(MicroblendContrast)
            else:
                LayerGroupN.inputs[6].default_value = 1

            if MbScale != None:
                LayerGroupN.inputs[7].default_value = float(MbScale)
            else:
                LayerGroupN.inputs[7].default_value = 1

            if MicroblendOffsetU != None:
                LayerGroupN.inputs[8].default_value = float(MicroblendOffsetU)
            else:
                LayerGroupN.inputs[8].default_value = 0

            if MicroblendOffsetV != None:
                LayerGroupN.inputs[9].default_value = float(MicroblendOffsetV)
            else:
                LayerGroupN.inputs[9].default_value = 0

            if opacity != None:
                LayerGroupN.inputs[10].default_value = float(opacity)
            else:
                LayerGroupN.inputs[10].default_value = 1

            # if opacity is 0, then the layer has been turned off
            if opacity == 0:
                skip_layers.append(idx)
                LayerGroupN.mute = True
                # LayerIndex += 1
                # continue

            # DEFINES MAIN MULTILAYERED PROPERTIES

            colorReroute = NG.nodes.new("NodeReroute")
            colorReroute.location = (-950,400)

            # Microblend texture node
            MBN = create_node(NG.nodes,"ShaderNodeTexImage",(-2300,-600),image = MBI,label = "Microblend")
            MBN.hide = False
            MBMapping = create_node(NG.nodes,"ShaderNodeMapping", (-2300,-550))
            MBUVCombine = create_node(NG.nodes,"ShaderNodeCombineXYZ", (-2300,-500))
            MBTexCord = create_node(NG.nodes,"ShaderNodeTexCoord", (-2300,-450))

            # Adds microblend normal map to mltemplate normal map. This works because both maps have been vectorized to -1 --> +1 range
            NormalCombineN = create_node(NG.nodes,"ShaderNodeVectorMath", (-1250,-200), operation = 'ADD')

            # Roughness
            rLevelsIn = levels_node_group()
            rLevelsInGroup = NG.nodes.new("ShaderNodeGroup")
            rLevelsInGroup.node_tree = rLevelsIn
            rLevelsInGroup.location = (-1100,50)
            rLevelsInGroup.label = "R Levels In"
            rLevelsInGroup.inputs[1].default_value = (OverrideTable["RoughLevelsIn"][roughLevelsIn][0])
            rLevelsInGroup.inputs[2].default_value = (OverrideTable["RoughLevelsIn"][roughLevelsIn][1])

            rLevelsOut = levels_node_group()
            rLevelsOutGroup = NG.nodes.new("ShaderNodeGroup")
            rLevelsOutGroup.node_tree = rLevelsOut
            rLevelsOutGroup.location = (-850,50)
            rLevelsOutGroup.label = "R Levels Out"
            rLevelsOutGroup.inputs[1].default_value = (OverrideTable["RoughLevelsOut"][roughLevelsOut][0])
            rLevelsOutGroup.inputs[2].default_value = (OverrideTable["RoughLevelsOut"][roughLevelsOut][1])

            # Metalness
            mLevelsIn = levels_node_group()
            mLevelsInGroup = NG.nodes.new("ShaderNodeGroup")
            mLevelsInGroup.node_tree = mLevelsIn
            mLevelsInGroup.location = (-1100,200)
            mLevelsInGroup.label = "M Levels In"
            mLevelsInGroup.inputs[1].default_value = (OverrideTable["MetalLevelsIn"][metalLevelsIn][0])
            mLevelsInGroup.inputs[2].default_value = (OverrideTable["MetalLevelsIn"][metalLevelsIn][1])

            mLevelsOut = levels_node_group()
            mLevelsOutGroup = NG.nodes.new("ShaderNodeGroup")
            mLevelsOutGroup.node_tree = mLevelsOut
            mLevelsOutGroup.location = (-850,200)
            mLevelsOutGroup.label = "M Levels Out"
            mLevelsOutGroup.inputs[1].default_value = (OverrideTable["MetalLevelsOut"][metalLevelsOut][0])
            mLevelsOutGroup.inputs[2].default_value = (OverrideTable["MetalLevelsOut"][metalLevelsOut][1])


            # --- Mask Layer ---
            mask_mixer=mask_mixer_node_group()
            mask_mixergroup = NG.nodes.new("ShaderNodeGroup")
            mask_mixergroup.name = "Group"
            mask_mixergroup.node_tree = mask_mixer
            mask_mixergroup.location = (-1700, -400)
            mask_mixergroup.width = 300


            # CREATE FINAL LINKS
            NG.links.new(GroupInN.outputs[0],BMN.inputs[0])
            NG.links.new(GroupInN.outputs[1],BMN.inputs[1])
            if len(BMN.inputs) > 1:
              NG.links.new(GroupInN.outputs[2],BMN.inputs[2])
              if len(BMN.inputs) > 2:
                NG.links.new(GroupInN.outputs[3],BMN.inputs[3])
            NG.links.new(GroupInN.outputs[4],BMN.inputs[4])
            NG.links.new(GroupInN.outputs[5], mask_mixergroup.inputs[0])
            NG.links.new(GroupInN.outputs[6], mask_mixergroup.inputs[1])
            NG.links.new(GroupInN.outputs[7],MBMapping.inputs[3])
            NG.links.new(GroupInN.outputs[8],MBUVCombine.inputs[0])
            NG.links.new(GroupInN.outputs[9],MBUVCombine.inputs[1])
            NG.links.new(GroupInN.outputs[10], mask_mixergroup.inputs[2])
            NG.links.new(GroupInN.outputs[11], mask_mixergroup.inputs[3])
            NG.links.new(MBTexCord.outputs[2],MBMapping.inputs[0])
            NG.links.new(MBUVCombine.outputs[0],MBMapping.inputs[1])
            NG.links.new(MBMapping.outputs[0],MBN.inputs[0])
            NG.links.new(BMN.outputs[0],colorReroute.inputs[0])
            NG.links.new(BMN.outputs[1],mLevelsInGroup.inputs[0])
            NG.links.new(mLevelsInGroup.outputs[0],mLevelsOutGroup.inputs[0])
            NG.links.new(BMN.outputs[2],rLevelsInGroup.inputs[0])
            NG.links.new(rLevelsInGroup.outputs[0],rLevelsOutGroup.inputs[0])
            NG.links.new(BMN.outputs[3],NormalCombineN.inputs[0])
            NG.links.new(MBN.outputs[0], mask_mixergroup.inputs[4])
            NG.links.new(MBN.outputs[1], mask_mixergroup.inputs[5])
            NG.links.new(mask_mixergroup.outputs[0], NormalCombineN.inputs[1])
            NG.links.new(mask_mixergroup.outputs[1], GroupOutN.inputs[4])

            NG.links.new(colorReroute.outputs[0],GroupOutN.inputs[0]) #Color output
            NG.links.new(mLevelsOutGroup.outputs[0],GroupOutN.inputs[1]) #Metalness output
            NG.links.new(rLevelsOutGroup.outputs[0],GroupOutN.inputs[2]) #Roughness output
            NG.links.new(NormalCombineN.outputs[0],GroupOutN.inputs[3]) #Normal output



#layer group input node output names
#['ColorScale', 'MatTile', 'MbTile', 'MicroblendNormalStrength', 'MicroblendContrast', 'MicroblendOffsetU', 'MicroblendOffsetV', 'NormalStrength', 'Opacity', 'Mask', 'OffsetU', 'OffsetV', '']
        # Data for vehicledestrblendshape.mt
        # Instead of maintaining two material py files we should setup the main multilayered shader to handle variants such as the vehicle material
        if "BakedNormal" in Data.keys():
            LayerNormal=Data["BakedNormal"]
        else:
            LayerNormal=Data["GlobalNormal"]

        self.createLayerMaterial(file_name+"_Layer_", LayerCount, CurMat, Data["MultilayerMask"], LayerNormal, skip_layers)

