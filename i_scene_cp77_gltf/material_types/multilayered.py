import bpy
import os
from ..main.common import *
from ..jsontool import JSONTool
import numpy as np

def np_array_from_image(img_name):
    img = bpy.data.images[img_name]
    return np.array(img.pixels[:])

def mask_mixer_node_group(Mat):
    if "Mask Mixer 1.6.7" in bpy.data.node_groups:
        return bpy.data.node_groups["Mask Mixer 1.6.7"]
    mask_mixer = bpy.data.node_groups.new(type = 'ShaderNodeTree', name = "Mask Mixer 1.6.7")
    mask_mixer['AddonVersion'] = Mat.get('AddonVersion')

    #sockets
    normal_map_socket = mask_mixer.interface.new_socket(name = "Microblend", in_out='OUTPUT', socket_type = 'NodeSocketVector')
    layer_mask_socket = mask_mixer.interface.new_socket(name = "Layer Mask", in_out='OUTPUT', socket_type = 'NodeSocketFloat')

    mask_socket = mask_mixer.interface.new_socket(name = "Mask", in_out='INPUT', socket_type = 'NodeSocketFloat')
    microblendnormalstrength_socket = mask_mixer.interface.new_socket(name = "MicroblendNormalStrength", in_out='INPUT', socket_type = 'NodeSocketFloat')
    microblendcontrast_socket = mask_mixer.interface.new_socket(name = "MicroblendContrast", in_out='INPUT', socket_type = 'NodeSocketFloat')
    opacity_socket = mask_mixer.interface.new_socket(name = "Opacity", in_out='INPUT', socket_type = 'NodeSocketFloat')
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

    # JATO: this generates a binary mask to hide mb-normals where mask = 1
    mbLessThan = mask_mixer.nodes.new("ShaderNodeMath")
    mbLessThan.operation = 'LESS_THAN'
    mbLessThan.location = (350, -100)
    mbLessThan.use_clamp = True
    mbLessThan.inputs[1].default_value = 1.0

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
    #maskMapRange.interpolation_type = 'SMOOTHSTEP'
    maskMapRange.location = (100, -600)

    maskMultiply = mask_mixer.nodes.new("ShaderNodeMath")
    maskMultiply.label = "opacity"
    maskMultiply.operation = 'MULTIPLY'
    maskMultiply.use_clamp = False
    maskMultiply.location = (350, -450)

    #initialize mask_mixer links
    mask_mixer.links.new(maskMixerInput.outputs['Mask'], maskAdd.inputs[1])
    mask_mixer.links.new(maskMixerInput.outputs['Mask'], maskMix.inputs[3])
    mask_mixer.links.new(maskMixerInput.outputs['MicroblendNormalStrength'], mbMultiply.inputs[0])
    mask_mixer.links.new(maskMixerInput.outputs['MicroblendContrast'], mbContrastMax.inputs[0])
    mask_mixer.links.new(maskMixerInput.outputs['Opacity'], maskReroute.inputs[0])
    mask_mixer.links.new(maskMixerInput.outputs['Microblend'], mbNormalVectorize.inputs[0])
    mask_mixer.links.new(maskMixerInput.outputs['Microblend Alpha'], maskAdd.inputs[0])
    mask_mixer.links.new(mbContrastMax.outputs[0], maskMix.inputs[0])
    mask_mixer.links.new(mbContrastMax.outputs[0], maskMapRange.inputs[2])
    mask_mixer.links.new(maskReroute.outputs[0], maskMultiply.inputs[1])
    mask_mixer.links.new(maskAdd.outputs[0], maskSubtract.inputs[0])
    mask_mixer.links.new(maskSubtract.outputs[0], maskMix.inputs[2])
    mask_mixer.links.new(maskMix.outputs[0], maskMapRange.inputs[0])
    mask_mixer.links.new(maskMapRange.outputs[0], maskMultiply.inputs[0])
    mask_mixer.links.new(maskMapRange.outputs[0], mbLessThan.inputs[0])
    mask_mixer.links.new(mbLessThan.outputs[0], mbMultiply.inputs[1])
    mask_mixer.links.new(mbMultiply.outputs[0], mbNormalStr.inputs[1])
    mask_mixer.links.new(mbNormalVectorize.outputs[0], mbNormalStr.inputs[0])
    mask_mixer.links.new(maskReroute.outputs[0], maskMultiply.inputs[1])
    mask_mixer.links.new(mbNormalStr.outputs[0], maskMixerOutput.inputs['Microblend'])
    mask_mixer.links.new(maskMultiply.outputs[0], maskMixerOutput.inputs['Layer Mask'])

    return mask_mixer

def levels_node_group(Mat):
    if "Levels 2077 1.6.7" in bpy.data.node_groups:
        return bpy.data.node_groups["Levels 2077 1.6.7"]
    levels = bpy.data.node_groups.new(type = 'ShaderNodeTree', name = "Levels 2077 1.6.7")
    # Write addonversion from material where group is created
    levels['AddonVersion'] = Mat.get('AddonVersion')

    input_socket = levels.interface.new_socket(name = "Input", in_out='INPUT', socket_type = 'NodeSocketFloat')
    vec2_socket = levels.interface.new_socket(name = "Levels", in_out='INPUT', socket_type = 'NodeSocketVector')
    vec2_socket.dimensions = 2
    #b_socket = levels.interface.new_socket(name = "[0]", in_out='INPUT', socket_type = 'NodeSocketFloat')
    #c_socket = levels.interface.new_socket(name = "[1]", in_out='INPUT', socket_type = 'NodeSocketFloat')
    result_socket = levels.interface.new_socket(name = "Result", in_out='OUTPUT', socket_type = 'NodeSocketFloat')

    levelsInput = levels.nodes.new("NodeGroupInput")
    levelsInput.location = (-1200,0)

    levelsOutput = levels.nodes.new("NodeGroupOutput")
    levelsOutput.location = (100,0)

    levelsSepXYZ = levels.nodes.new("ShaderNodeSeparateXYZ")
    levelsSepXYZ.location = (-800,-150)

    levelsMultAdd = levels.nodes.new("ShaderNodeMath")
    levelsMultAdd.operation = 'MULTIPLY_ADD'
    levelsMultAdd.location = (-300,0)

    levels.links.new(levelsInput.outputs[0], levelsMultAdd.inputs[0])
    levels.links.new(levelsInput.outputs[1], levelsSepXYZ.inputs[0])
    levels.links.new(levelsSepXYZ.outputs[0], levelsMultAdd.inputs[1])
    levels.links.new(levelsSepXYZ.outputs[1], levelsMultAdd.inputs[2])
    levels.links.new(levelsMultAdd.outputs[0], levelsOutput.inputs[0])

    return levels

def _getOrCreateLayerBlend(Mat):
    if "Layer Blend 1.6.7" in bpy.data.node_groups:
        return bpy.data.node_groups["Layer Blend 1.6.7"]

    NG = bpy.data.node_groups.new("Layer Blend 1.6.7","ShaderNodeTree")#create layer's node group
    # Write addonversion from material where group is created
    NG['AddonVersion'] = Mat.get('AddonVersion')
    vers=bpy.app.version
    if vers[0]<4:
        NG.inputs.new('NodeSocketColor','Color A')
        NG.inputs.new('NodeSocketFloat','Metalness A')
        NG.inputs.new('NodeSocketFloat','Roughness A')
        NG.inputs.new('NodeSocketVector','Normal A')
        NG.inputs.new('NodeSocketVector','Microblend A')
        NG.inputs.new('NodeSocketColor','Color B')
        NG.inputs.new('NodeSocketFloat','Metalness B')
        NG.inputs.new('NodeSocketFloat','Roughness B')
        NG.inputs.new('NodeSocketVector','Normal B')
        NG.inputs.new('NodeSocketVector','Microblend B')
        NG.inputs.new('NodeSocketFloat','Layer Mask')
        NG.outputs.new('NodeSocketColor','Color')
        NG.outputs.new('NodeSocketFloat','Metalness')
        NG.outputs.new('NodeSocketFloat','Roughness')
        NG.outputs.new('NodeSocketVector','Normal')
        NG.outputs.new('NodeSocketVector','Microblend')
    else:
        NG.interface.new_socket(name="Color A", socket_type='NodeSocketColor', in_out='INPUT')
        NG.interface.new_socket(name="Metalness A", socket_type='NodeSocketFloat', in_out='INPUT')
        NG.interface.new_socket(name="Roughness A", socket_type='NodeSocketFloat', in_out='INPUT')
        NG.interface.new_socket(name="Normal A", socket_type='NodeSocketVector', in_out='INPUT')
        NG.interface.new_socket(name="Microblend A", socket_type='NodeSocketVector', in_out='INPUT')
        NG.interface.new_socket(name="Color B", socket_type='NodeSocketColor', in_out='INPUT')
        NG.interface.new_socket(name="Metalness B", socket_type='NodeSocketFloat', in_out='INPUT')
        NG.interface.new_socket(name="Roughness B", socket_type='NodeSocketFloat', in_out='INPUT')
        NG.interface.new_socket(name="Normal B", socket_type='NodeSocketVector', in_out='INPUT')
        NG.interface.new_socket(name="Microblend B", socket_type='NodeSocketVector', in_out='INPUT')
        NG.interface.new_socket(name="Layer Mask", socket_type='NodeSocketFloat', in_out='INPUT')
        NG.interface.new_socket(name="Color", socket_type='NodeSocketColor', in_out='OUTPUT')
        NG.interface.new_socket(name="Metalness", socket_type='NodeSocketFloat', in_out='OUTPUT')
        NG.interface.new_socket(name="Roughness", socket_type='NodeSocketFloat', in_out='OUTPUT')
        NG.interface.new_socket(name="Normal", socket_type='NodeSocketVector', in_out='OUTPUT')
        NG.interface.new_socket(name="Microblend", socket_type='NodeSocketVector', in_out='OUTPUT')

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

    MicroblendMixN = create_node(NG.nodes,"ShaderNodeMix",(-300,-300), label = "Microblend Mix")
    MicroblendMixN.data_type='VECTOR'
    MicroblendMixN.clamp_factor=False

    NG.links.new(GroupInN.outputs['Color A'],ColorMixN.inputs[6])
    NG.links.new(GroupInN.outputs['Metalness A'],MetalMixN.inputs[2])
    NG.links.new(GroupInN.outputs['Roughness A'],RoughMixN.inputs[2])
    NG.links.new(GroupInN.outputs['Normal A'],NormalMixN.inputs[4])
    NG.links.new(GroupInN.outputs['Microblend A'],MicroblendMixN.inputs[4])
    NG.links.new(GroupInN.outputs['Color B'],ColorMixN.inputs[7])
    NG.links.new(GroupInN.outputs['Metalness B'],MetalMixN.inputs[3])
    NG.links.new(GroupInN.outputs['Roughness B'],RoughMixN.inputs[3])
    NG.links.new(GroupInN.outputs['Normal B'],NormalMixN.inputs[5])
    NG.links.new(GroupInN.outputs['Microblend B'],MicroblendMixN.inputs[5])
    NG.links.new(GroupInN.outputs['Layer Mask'],ColorMixN.inputs['Factor'])
    NG.links.new(GroupInN.outputs['Layer Mask'],NormalMixN.inputs['Factor'])
    NG.links.new(GroupInN.outputs['Layer Mask'],RoughMixN.inputs['Factor'])
    NG.links.new(GroupInN.outputs['Layer Mask'],MetalMixN.inputs['Factor'])
    NG.links.new(GroupInN.outputs['Layer Mask'],MicroblendMixN.inputs['Factor'])

    NG.links.new(ColorMixN.outputs[2],GroupOutN.inputs['Color'])
    NG.links.new(MetalMixN.outputs[0],GroupOutN.inputs['Metalness'])
    NG.links.new(RoughMixN.outputs[0],GroupOutN.inputs['Roughness'])
    NG.links.new(NormalMixN.outputs[1],GroupOutN.inputs['Normal'])
    NG.links.new(MicroblendMixN.outputs[1],GroupOutN.inputs['Microblend'])

    return NG

def _getOrCreateLayerBlend5(Mat):
    ng_name = "Layer Blend 1.8.0"
    if ng_name in bpy.data.node_groups:
        return bpy.data.node_groups[ng_name]

    NG = bpy.data.node_groups.new(ng_name,"ShaderNodeTree")
    # Write addonversion from material where group is created
    NG['AddonVersion'] = Mat.get('AddonVersion')

    NG.interface.new_socket(name="Bundle A", socket_type='NodeSocketBundle', in_out='INPUT')
    NG.interface.new_socket(name="Bundle B", socket_type='NodeSocketBundle', in_out='INPUT')
    NG.interface.new_socket(name="Bundle", socket_type='NodeSocketBundle', in_out='OUTPUT')

    GroupInN = create_node(NG.nodes,"NodeGroupInput", (-900,0))
    GroupInN.hide = False

    GroupOutN = create_node(NG.nodes,"NodeGroupOutput",(0,0), hide=False)

    GroupSeparateBundle1 = create_node(NG.nodes, "NodeSeparateBundle",(-700,0))
    GroupSeparateBundle1Color = GroupSeparateBundle1.bundle_items.new(socket_type='RGBA', name='Color')
    GroupSeparateBundle1Metal = GroupSeparateBundle1.bundle_items.new(socket_type='FLOAT', name='Metalness')
    GroupSeparateBundle1Rough = GroupSeparateBundle1.bundle_items.new(socket_type='FLOAT', name='Roughness')
    GroupSeparateBundle1Normal = GroupSeparateBundle1.bundle_items.new(socket_type='VECTOR', name='Normal')
    GroupSeparateBundle1Microblend = GroupSeparateBundle1.bundle_items.new(socket_type='VECTOR', name='Microblend')
    GroupSeparateBundle1Mask = GroupSeparateBundle1.bundle_items.new(socket_type='FLOAT', name='Layer Mask')

    GroupSeparateBundle2 = create_node(NG.nodes, "NodeSeparateBundle",(-700,-200))
    GroupSeparateBundle2Color = GroupSeparateBundle2.bundle_items.new(socket_type='RGBA', name='Color')
    GroupSeparateBundle2Metal = GroupSeparateBundle2.bundle_items.new(socket_type='FLOAT', name='Metalness')
    GroupSeparateBundle2Rough = GroupSeparateBundle2.bundle_items.new(socket_type='FLOAT', name='Roughness')
    GroupSeparateBundle2Normal = GroupSeparateBundle2.bundle_items.new(socket_type='VECTOR', name='Normal')
    GroupSeparateBundle2Microblend = GroupSeparateBundle2.bundle_items.new(socket_type='VECTOR', name='Microblend')
    GroupSeparateBundle2Mask = GroupSeparateBundle2.bundle_items.new(socket_type='FLOAT', name='Layer Mask')

    GroupCombineBundle = create_node(NG.nodes, "NodeCombineBundle",(-250,0))
    GroupCombineBundleColor = GroupCombineBundle.bundle_items.new(socket_type='RGBA', name='Color')
    GroupCombineBundleMetal = GroupCombineBundle.bundle_items.new(socket_type='FLOAT', name='Metalness')
    GroupCombineBundleRough = GroupCombineBundle.bundle_items.new(socket_type='FLOAT', name='Roughness')
    GroupCombineBundleNormal = GroupCombineBundle.bundle_items.new(socket_type='VECTOR', name='Normal')
    GroupCombineBundleMicroblend = GroupCombineBundle.bundle_items.new(socket_type='VECTOR', name='Microblend')
    GroupCombineBundleMask = GroupCombineBundle.bundle_items.new(socket_type='FLOAT', name='Layer Mask')

    ColorMixN = create_node(NG.nodes,"ShaderNodeMix", (-450,100), label="Color Mix")
    ColorMixN.data_type='RGBA'

    MetalMixN = create_node(NG.nodes,"ShaderNodeMix", (-450,0), label = "Metal Mix")
    MetalMixN.data_type='FLOAT'

    RoughMixN = create_node(NG.nodes,"ShaderNodeMix", (-450,-100), label = "Rough Mix")
    RoughMixN.data_type='FLOAT'

    NormalMixN = create_node(NG.nodes,"ShaderNodeMix",(-450,-200), label = "Normal Mix")
    NormalMixN.data_type='VECTOR'
    NormalMixN.clamp_factor=False

    MicroblendMixN = create_node(NG.nodes,"ShaderNodeMix",(-450,-300), label = "Microblend Mix")
    MicroblendMixN.data_type='VECTOR'
    MicroblendMixN.clamp_factor=False

    NG.links.new(GroupInN.outputs['Bundle A'],GroupSeparateBundle1.inputs[0])
    NG.links.new(GroupInN.outputs['Bundle B'],GroupSeparateBundle2.inputs[0])

    # Is this necessary?
    GroupSeparateBundle1.update()

    NG.links.new(GroupSeparateBundle1.outputs[0],ColorMixN.inputs[6])
    NG.links.new(GroupSeparateBundle1.outputs[1],MetalMixN.inputs[2])
    NG.links.new(GroupSeparateBundle1.outputs[2],RoughMixN.inputs[2])
    NG.links.new(GroupSeparateBundle1.outputs[3],NormalMixN.inputs[4])
    NG.links.new(GroupSeparateBundle1.outputs[4],MicroblendMixN.inputs[4])
    NG.links.new(GroupSeparateBundle2.outputs[0],ColorMixN.inputs[7])
    NG.links.new(GroupSeparateBundle2.outputs[1],MetalMixN.inputs[3])
    NG.links.new(GroupSeparateBundle2.outputs[2],RoughMixN.inputs[3])
    NG.links.new(GroupSeparateBundle2.outputs[3],NormalMixN.inputs[5])
    NG.links.new(GroupSeparateBundle2.outputs[4],MicroblendMixN.inputs[5])
    NG.links.new(GroupSeparateBundle2.outputs[5],ColorMixN.inputs['Factor'])
    NG.links.new(GroupSeparateBundle2.outputs[5],NormalMixN.inputs['Factor'])
    NG.links.new(GroupSeparateBundle2.outputs[5],RoughMixN.inputs['Factor'])
    NG.links.new(GroupSeparateBundle2.outputs[5],MetalMixN.inputs['Factor'])
    NG.links.new(GroupSeparateBundle2.outputs[5],MicroblendMixN.inputs['Factor'])

    NG.links.new(ColorMixN.outputs[2],GroupCombineBundle.inputs['Color'])
    NG.links.new(MetalMixN.outputs[0],GroupCombineBundle.inputs['Metalness'])
    NG.links.new(RoughMixN.outputs[0],GroupCombineBundle.inputs['Roughness'])
    NG.links.new(NormalMixN.outputs[1],GroupCombineBundle.inputs['Normal'])
    NG.links.new(MicroblendMixN.outputs[1],GroupCombineBundle.inputs['Microblend'])

    NG.links.new(GroupCombineBundle.outputs[0],GroupOutN.inputs[0])

    return NG

# JATO: This function wraps a pbsdf node inside a nodegroup with bundle sockets for blender 5+
def ml_pbsdf_node_group(Mat):
    ng_name = "Multilayered 1.8.0"
    if ng_name in bpy.data.node_groups:
        return bpy.data.node_groups[ng_name]
    ml_bsdf = bpy.data.node_groups.new(type = 'ShaderNodeTree', name = ng_name)
    # Write addonversion from material where group is created
    ml_bsdf['AddonVersion'] = Mat.get('AddonVersion')

    input_socket0 = ml_bsdf.interface.new_socket(name = "Normal Map", in_out='INPUT', socket_type = 'NodeSocketColor')
    input_socket1 = ml_bsdf.interface.new_socket(name = "Layer 1", in_out='INPUT', socket_type = 'NodeSocketBundle')
    input_socket2 = ml_bsdf.interface.new_socket(name = "Layer 2", in_out='INPUT', socket_type = 'NodeSocketBundle')
    input_socket3 = ml_bsdf.interface.new_socket(name = "Layer 3", in_out='INPUT', socket_type = 'NodeSocketBundle')
    input_socket4 = ml_bsdf.interface.new_socket(name = "Layer 4", in_out='INPUT', socket_type = 'NodeSocketBundle')
    input_socket5 = ml_bsdf.interface.new_socket(name = "Layer 5", in_out='INPUT', socket_type = 'NodeSocketBundle')
    input_socket6 = ml_bsdf.interface.new_socket(name = "Layer 6", in_out='INPUT', socket_type = 'NodeSocketBundle')
    input_socket7 = ml_bsdf.interface.new_socket(name = "Layer 7", in_out='INPUT', socket_type = 'NodeSocketBundle')
    input_socket8 = ml_bsdf.interface.new_socket(name = "Layer 8", in_out='INPUT', socket_type = 'NodeSocketBundle')
    input_socket9 = ml_bsdf.interface.new_socket(name = "Layer 9", in_out='INPUT', socket_type = 'NodeSocketBundle')
    input_socket10 = ml_bsdf.interface.new_socket(name = "Layer 10", in_out='INPUT', socket_type = 'NodeSocketBundle')
    input_socket11 = ml_bsdf.interface.new_socket(name = "Layer 11", in_out='INPUT', socket_type = 'NodeSocketBundle')
    input_socket12 = ml_bsdf.interface.new_socket(name = "Layer 12", in_out='INPUT', socket_type = 'NodeSocketBundle')
    input_socket13 = ml_bsdf.interface.new_socket(name = "Layer 13", in_out='INPUT', socket_type = 'NodeSocketBundle')
    input_socket14 = ml_bsdf.interface.new_socket(name = "Layer 14", in_out='INPUT', socket_type = 'NodeSocketBundle')
    input_socket15 = ml_bsdf.interface.new_socket(name = "Layer 15", in_out='INPUT', socket_type = 'NodeSocketBundle')
    input_socket16 = ml_bsdf.interface.new_socket(name = "Layer 16", in_out='INPUT', socket_type = 'NodeSocketBundle')
    input_socket17 = ml_bsdf.interface.new_socket(name = "Layer 17", in_out='INPUT', socket_type = 'NodeSocketBundle')
    input_socket18 = ml_bsdf.interface.new_socket(name = "Layer 18", in_out='INPUT', socket_type = 'NodeSocketBundle')
    input_socket19 = ml_bsdf.interface.new_socket(name = "Layer 19", in_out='INPUT', socket_type = 'NodeSocketBundle')
    input_socket20 = ml_bsdf.interface.new_socket(name = "Layer 20", in_out='INPUT', socket_type = 'NodeSocketBundle')

    output_socket = ml_bsdf.interface.new_socket(name = "BSDF", in_out='OUTPUT', socket_type = 'NodeSocketShader')

    input = ml_bsdf.nodes.new("NodeGroupInput")
    input.location = (-1200,0)

    output = ml_bsdf.nodes.new("NodeGroupOutput")
    output.location = (100,0)

    bsdf = ml_bsdf.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (-200, 0)

    normalVectorize = ml_bsdf.nodes.new("ShaderNodeVectorMath")
    normalVectorize.operation='MULTIPLY_ADD'
    normalVectorize.location = (-900,0)
    normalVectorize.hide = True
    normalVectorize.inputs[1].default_value = 2, 2, 0
    normalVectorize.inputs[2].default_value = -1, -1, 0

    normalMicroBAdd = create_node(ml_bsdf.nodes, "ShaderNodeVectorMath",(-700,-75),operation='ADD')

    normalAdd = create_node(ml_bsdf.nodes, "ShaderNodeVectorMath",(-700,0),operation='ADD')

    normalCreateVecZGroup = CreateCalculateVecNormalZ(ml_bsdf,-500,0)
    normalMap = create_node(ml_bsdf.nodes, "ShaderNodeNormalMap",(-500,-300))

    BLNDB = _getOrCreateLayerBlend5(Mat)
    count = 1
    for i in range(19):
        LayerGroupBLNDB = ml_bsdf.nodes.new("ShaderNodeGroup")
        LayerGroupBLNDB.name = "Layer_Blend_"+str(count)
        LayerGroupBLNDB.location = (-900, -150*count)
        LayerGroupBLNDB.node_tree = BLNDB
        if count == 1:
            ml_bsdf.links.new(input.outputs[count], LayerGroupBLNDB.inputs['Bundle A'])
        ml_bsdf.links.new(input.outputs[count + 1], LayerGroupBLNDB.inputs['Bundle B'])
        count += 1

    groupSeparateBundle = create_node(ml_bsdf.nodes, "NodeSeparateBundle",(-700, -150))
    groupSeparateBundle.hide = False
    groupSeparateBundleColor = groupSeparateBundle.bundle_items.new(socket_type='RGBA', name='Color')
    groupSeparateBundleMetal = groupSeparateBundle.bundle_items.new(socket_type='FLOAT', name='Metalness')
    groupSeparateBundleRough = groupSeparateBundle.bundle_items.new(socket_type='FLOAT', name='Roughness')
    groupSeparateBundleNormal = groupSeparateBundle.bundle_items.new(socket_type='VECTOR', name='Normal')
    groupSeparateBundleMicroblend = groupSeparateBundle.bundle_items.new(socket_type='VECTOR', name='Microblend')
    groupSeparateBundleMask = groupSeparateBundle.bundle_items.new(socket_type='FLOAT', name='Layer Mask')

    ml_bsdf.links.new(input.outputs[0],normalVectorize.inputs[0])
    for i in range(18):
        ml_bsdf.links.new(ml_bsdf.nodes["Layer_Blend_"+str(i+1)].outputs[0], ml_bsdf.nodes["Layer_Blend_"+str(i+2)].inputs[0])
    ml_bsdf.links.new(ml_bsdf.nodes["Layer_Blend_19"].outputs[0], groupSeparateBundle.inputs[0])
    ml_bsdf.links.new(groupSeparateBundle.outputs['Color'], bsdf.inputs['Base Color'])
    ml_bsdf.links.new(groupSeparateBundle.outputs['Metalness'], bsdf.inputs['Metallic'])
    ml_bsdf.links.new(groupSeparateBundle.outputs['Roughness'], bsdf.inputs['Roughness'])

    ml_bsdf.links.new(groupSeparateBundle.outputs['Normal'], normalMicroBAdd.inputs[0])
    ml_bsdf.links.new(groupSeparateBundle.outputs['Microblend'], normalMicroBAdd.inputs[1])
    ml_bsdf.links.new(normalVectorize.outputs[0], normalAdd.inputs[0])
    ml_bsdf.links.new(normalMicroBAdd.outputs[0], normalAdd.inputs[1])
    ml_bsdf.links.new(normalAdd.outputs[0], normalCreateVecZGroup.inputs[0])
    ml_bsdf.links.new(normalCreateVecZGroup.outputs[0], normalMap.inputs[1])
    ml_bsdf.links.new(normalMap.outputs[0], bsdf.inputs['Normal'])

    #ml_bsdf.links.new(input.outputs[0], bsdf.inputs[0])
    ml_bsdf.links.new(bsdf.outputs[0], output.inputs[0])

    return ml_bsdf


class Multilayered:
    def __init__(self, BasePath,image_format, ProjPath):
        self.BasePath = str(BasePath)
        self.image_format = image_format
        self.ProjPath = str(ProjPath)


    def createMLTemplateGroup(self,matTemplateObj,mltemplate):
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


    def setupMaterial(self,LayerName,LayerCount,CurMat,mlmaskpath,normalimgpath):
        vers=bpy.app.version
        if vers[0]<5.0:
            LayerCount = LayerCount - 1

            normalVectorize = CurMat.nodes.new("ShaderNodeVectorMath")
            normalVectorize.operation='MULTIPLY_ADD'
            normalVectorize.location = (-900,0)
            normalVectorize.hide = True
            normalVectorize.inputs[1].default_value = 2, 2, 0
            normalVectorize.inputs[2].default_value = -1, -1, 0

            normalMicroBAdd = create_node(CurMat.nodes, "ShaderNodeVectorMath",(-700,-75),operation='ADD')

            normalAdd = create_node(CurMat.nodes, "ShaderNodeVectorMath",(-700,0),operation='ADD')

            normalCreateVecZGroup = CreateCalculateVecNormalZ(CurMat,-500,0)
            normalMap = create_node(CurMat.nodes, "ShaderNodeNormalMap",(-500,-75))

            CurMat.links.new(normalVectorize.outputs[0], normalAdd.inputs[0])
            CurMat.links.new(normalMicroBAdd.outputs[0], normalAdd.inputs[1])
            CurMat.links.new(normalAdd.outputs[0], normalCreateVecZGroup.inputs[0])
            CurMat.links.new(normalCreateVecZGroup.outputs[0], normalMap.inputs[1])
            CurMat.links.new(normalMap.outputs[0], CurMat.nodes[loc('Principled BSDF')].inputs['Normal'])
        else:
            orig_pbsdf = CurMat.nodes['Principled BSDF']
            if orig_pbsdf:
                CurMat.nodes.remove(orig_pbsdf)
            ml_main_ng = ml_pbsdf_node_group(CurMat)
            ml_main_ng.color_tag = 'SHADER'
            mlShaderNG = CurMat.nodes.new("ShaderNodeGroup")
            # JATO: should we be setting node name? maybe ml-editing stuff should look for node tree name instead?
            mlShaderNG.name = "Multilayered 1.8.0"
            mlShaderNG.location = (-50, 100)
            mlShaderNG.node_tree = ml_main_ng
            mlShaderNG.show_options = False
            CurMat.links.new(mlShaderNG.outputs['BSDF'],CurMat.nodes['Material Output'].inputs[0])

        for x in range(LayerCount):
            MaskTexture=None
            projpath = os.path.join(os.path.splitext(os.path.join(self.ProjPath, mlmaskpath))[0] + '_layers', os.path.split(mlmaskpath)[-1:][0][:-7] + "_" + str(x + 1) + ".png")
            basepath = os.path.join(os.path.splitext(os.path.join(self.BasePath, mlmaskpath))[0] + '_layers', os.path.split(mlmaskpath)[-1:][0][:-7] + "_" + str(x + 1) + ".png")
            if os.path.exists(projpath):
                MaskTexture = imageFromPath(projpath, self.image_format, isNormal = True)
            elif os.path.exists(basepath):
                MaskTexture = imageFromPath(basepath, self.image_format, isNormal = True)
            # else:
                # if 'AppData' in basepath:
                    # print('Mask image not found for layer ',x+1,' DepotPath appears to be in Appdata, this is known to cause issues')
                # else:
                    # print('Mask image not found for layer ',x+1)

            MaskN=None
            if MaskTexture:
                if vers[0]<5.0:
                    MaskN = create_node(CurMat.nodes,"ShaderNodeTexImage",(-2400,-400*x), hide=False, image = MaskTexture)
                else:
                    MaskN = create_node(CurMat.nodes,"ShaderNodeTexImage",(-1200,-400*x), hide=False, image = MaskTexture)
                MaskN.width = 300

            #if self.flipMaskY:
            # Mask flip deprecated in WolvenKit deveolpment build 8.7+
            #MaskN.texture_mapping.scale[1] = -1 #flip mask if needed

            if vers[0]<5.0:
                CurMat.links.new(CurMat.nodes["Mat_Mod_Layer_"+str(x)].outputs['Color'],CurMat.nodes["Mat_Mod_Layer_"+str(x+1)].inputs['Color'])
                CurMat.links.new(CurMat.nodes["Mat_Mod_Layer_"+str(x)].outputs['Metalness'],CurMat.nodes["Mat_Mod_Layer_"+str(x+1)].inputs['Metalness'])
                CurMat.links.new(CurMat.nodes["Mat_Mod_Layer_"+str(x)].outputs['Roughness'],CurMat.nodes["Mat_Mod_Layer_"+str(x+1)].inputs['Roughness'])
                CurMat.links.new(CurMat.nodes["Mat_Mod_Layer_"+str(x)].outputs['Normal'],CurMat.nodes["Mat_Mod_Layer_"+str(x+1)].inputs['Normal'])
                CurMat.links.new(CurMat.nodes["Mat_Mod_Layer_"+str(x)].outputs['Microblend'],CurMat.nodes["Mat_Mod_Layer_"+str(x+1)].inputs['Microblend'])
            else:
                # JATO: Check for mlsetup with more than 20 layers (probably only ml-resources wk-project)
                if x<=19:
                    CurMat.links.new(CurMat.nodes["Mat_Mod_Layer_"+str(x)].outputs['Layer'],mlShaderNG.inputs[x + 1])

            if MaskN:
                try:
                    CurMat.links.new(MaskN.outputs[0],CurMat.nodes["Mat_Mod_Layer_"+str(x+1)].inputs['Mask'])
                except:
                    pass

        if vers[0]<5.0:
            if LayerCount>1:
                targetLayer="Mat_Mod_Layer_"+str(LayerCount-1)
            else:
                targetLayer="Mat_Mod_Layer_0"

            targetLayer="Mat_Mod_Layer_"+str(LayerCount)
            CurMat.links.new(CurMat.nodes[targetLayer].outputs['Color'],CurMat.nodes[loc('Principled BSDF')].inputs['Base Color'])
            CurMat.links.new(CurMat.nodes[targetLayer].outputs['Metalness'],CurMat.nodes[loc('Principled BSDF')].inputs['Metallic'])
            CurMat.links.new(CurMat.nodes[targetLayer].outputs['Roughness'],CurMat.nodes[loc('Principled BSDF')].inputs['Roughness'])
            CurMat.links.new(CurMat.nodes[targetLayer].outputs['Normal'],normalMicroBAdd.inputs[0])
            CurMat.links.new(CurMat.nodes[targetLayer].outputs['Microblend'],normalMicroBAdd.inputs[1])

        if normalimgpath:
            GNMap = CreateShaderNodeGlobalNormalMap(CurMat,self.BasePath + normalimgpath,-350,800,'GlobalNormal',self.image_format)
            if vers[0]<5.0:
                CurMat.links.new(GNMap.outputs[0],normalVectorize.inputs[0])
            else:
                CurMat.links.new(GNMap.outputs[0],mlShaderNG.inputs[0])


    def create(self,Data,Mat):
        # JATO: We have to clear gpencil palette to prevent add-on from immediately changing color of layer 1 on import
        # TODO: Should probably clear palette when material-panel is drawn
        bpy.context.tool_settings.gpencil_paint.palette = None

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
                NG.inputs.new('NodeSocketColor','Color')
                NG.inputs.new('NodeSocketFloat','Metalness')
                NG.inputs.new('NodeSocketFloat','Roughness')
                NG.inputs.new('NodeSocketVector','Normal')
                NG.inputs.new('NodeSocketVector','Microblend')
                NG.inputs.new('NodeSocketFloat','Mask')
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

                NG.outputs.new('NodeSocketColor','Color')
                NG.outputs.new('NodeSocketFloat','Metalness')
                NG.outputs.new('NodeSocketFloat','Roughness')
                NG.outputs.new('NodeSocketVector','Normal')
                NG.outputs.new('NodeSocketVector','Microblend')
                NG.outputs.new('NodeSocketFloat','Layer Mask')
                NG_inputs=NG.inputs

            else:
                ioPanel = NG.interface.new_panel(name='Input/Output')
                ioPanel.default_closed = True
                overridesPanel = NG.interface.new_panel(name='Overrides')
                overridesPanel.default_closed = True
                levelsPanel = NG.interface.new_panel(name='Levels')
                levelsPanel.default_closed = True
                NG.interface.move_to_parent(item=levelsPanel, parent=overridesPanel, to_position=2)
                paramsPanel = NG.interface.new_panel(name='Parameters')
                if vers[0]<5:
                    NG.interface.new_socket(name="Color", socket_type='NodeSocketColor', parent=ioPanel, in_out='INPUT')
                    NG.interface.new_socket(name="Metalness", socket_type='NodeSocketFloat', parent=ioPanel, in_out='INPUT')
                    NG.interface.new_socket(name="Roughness", socket_type='NodeSocketFloat', parent=ioPanel, in_out='INPUT')
                    NG.interface.new_socket(name="Normal", socket_type='NodeSocketVector', parent=ioPanel, in_out='INPUT')
                    NG.interface.new_socket(name="Microblend", socket_type='NodeSocketVector', parent=ioPanel, in_out='INPUT')
                NG.interface.new_socket(name="Mask", socket_type='NodeSocketFloat', parent=ioPanel, in_out='INPUT')

                NG.interface.new_socket(name="ColorScale", socket_type='NodeSocketColor', parent=overridesPanel, in_out='INPUT')
                NG.interface.new_socket(name="NormalStrength", socket_type='NodeSocketFloat', parent=overridesPanel, in_out='INPUT')
                NG.interface.new_socket(name="MetalLevelsIn", socket_type='NodeSocketVector', parent=levelsPanel, in_out='INPUT')
                NG.interface.new_socket(name="MetalLevelsOut", socket_type='NodeSocketVector', parent=levelsPanel, in_out='INPUT')
                NG.interface.new_socket(name="RoughLevelsIn", socket_type='NodeSocketVector', parent=levelsPanel, in_out='INPUT')
                NG.interface.new_socket(name="RoughLevelsOut", socket_type='NodeSocketVector', parent=levelsPanel, in_out='INPUT')

                NG.interface.new_socket(name="MatTile", socket_type='NodeSocketFloat', parent=paramsPanel, in_out='INPUT')
                NG.interface.new_socket(name="OffsetU", socket_type='NodeSocketFloat', parent=paramsPanel, in_out='INPUT')
                NG.interface.new_socket(name="OffsetV", socket_type='NodeSocketFloat', parent=paramsPanel, in_out='INPUT')
                NG.interface.new_socket(name="MicroblendNormalStrength", socket_type='NodeSocketFloat', parent=paramsPanel, in_out='INPUT')
                NG.interface.new_socket(name="MicroblendContrast", socket_type='NodeSocketFloat', parent=paramsPanel, in_out='INPUT')
                NG.interface.new_socket(name="MbTile", socket_type='NodeSocketFloat', parent=paramsPanel, in_out='INPUT')
                NG.interface.new_socket(name="MicroblendOffsetU", socket_type='NodeSocketFloat', parent=paramsPanel, in_out='INPUT')
                NG.interface.new_socket(name="MicroblendOffsetV", socket_type='NodeSocketFloat', parent=paramsPanel, in_out='INPUT')
                NG.interface.new_socket(name="Opacity", socket_type='NodeSocketFloat', parent=paramsPanel, in_out='INPUT')

                NG.interface.new_socket(name="Color", socket_type='NodeSocketColor', parent=ioPanel, in_out='OUTPUT')
                NG.interface.new_socket(name="Metalness", socket_type='NodeSocketFloat', parent=ioPanel, in_out='OUTPUT')
                NG.interface.new_socket(name="Roughness", socket_type='NodeSocketFloat', parent=ioPanel, in_out='OUTPUT')
                NG.interface.new_socket(name="Normal", socket_type='NodeSocketVector', parent=ioPanel, in_out='OUTPUT')
                NG.interface.new_socket(name="Microblend", socket_type='NodeSocketVector', parent=ioPanel, in_out='OUTPUT')
                NG.interface.new_socket(name="Layer Mask", socket_type='NodeSocketFloat', parent=ioPanel, in_out='OUTPUT')

                if not vers[0]<5:
                    NG.interface.new_socket(name="Layer", socket_type='NodeSocketBundle', in_out='OUTPUT')

                NG_inputs=get_inputs(NG)

            if vers[0]<5:
                if LayerIndex == 0:
                    NG_inputs[5].default_value = 1

                NG_inputs[7].min_value = 0 #NormalStrength  No reason to invert these maps, not detail maps.
                NG_inputs[7].max_value = 10 #NormalStrength This value is arbitrary, but more than adequate.

                NG_inputs[8].dimensions = 2 #MetalLevelsIn  Changes from Vec3 to Vec2 TODO Can this be set on socket creation?
                NG_inputs[9].dimensions = 2 #MetalLevelsOut  Changes from Vec3 to Vec2 TODO Can this be set on socket creation?
                NG_inputs[10].dimensions = 2 #RoughLevelsIn  Changes from Vec3 to Vec2 TODO Can this be set on socket creation?
                NG_inputs[11].dimensions = 2 #RoughLevelsOut  Changes from Vec3 to Vec2 TODO Can this be set on socket creation?

                NG_inputs[16].min_value = 0 #MicroblendContrast
                NG_inputs[16].max_value = 1 #MicroblendContrast
                NG_inputs[20].min_value = 0 #Opacity
                NG_inputs[20].max_value = 1 #Opacity
            else:
                if LayerIndex == 0:
                    NG_inputs[0].default_value = 1
                NG_inputs[2].min_value = 0 #NormalStrength  No reason to invert these maps, not detail maps.
                NG_inputs[2].max_value = 10 #NormalStrength This value is arbitrary, but more than adequate.
                NG_inputs[3].dimensions = 2 #MetalLevelsIn  Changes from Vec3 to Vec2 TODO Can this be set on socket creation?
                NG_inputs[4].dimensions = 2 #MetalLevelsOut  Changes from Vec3 to Vec2 TODO Can this be set on socket creation?
                NG_inputs[5].dimensions = 2 #RoughLevelsIn  Changes from Vec3 to Vec2 TODO Can this be set on socket creation?
                NG_inputs[6].dimensions = 2 #RoughLevelsOut  Changes from Vec3 to Vec2 TODO Can this be set on socket creation?
                NG_inputs[11].min_value = 0 #MicroblendContrast
                NG_inputs[11].max_value = 1 #MicroblendContrast
                NG_inputs[15].min_value = 0 #Opacity
                NG_inputs[15].max_value = 1 #Opacity


            if vers[0]<5.0:
                LayerGroupN = create_node(CurMat.nodes, "ShaderNodeGroup", (-2000,450-400*idx), False)
            else:
                LayerGroupN = create_node(CurMat.nodes, "ShaderNodeGroup", (-800,450-400*idx), False)
            LayerGroupN.width = 400
            LayerGroupN.node_tree = NG
            LayerGroupN.name = "Mat_Mod_Layer_"+str(LayerIndex)
            LayerIndex += 1

            GroupInN = create_node(NG.nodes, "NodeGroupInput", (-2600,100))
            GroupInN.hide = False

            GroupOutN = create_node(NG.nodes, "NodeGroupOutput", (0,100))
            GroupOutN.hide = False
            LayerGroupN['mlTemplate']=material
            if not bpy.data.node_groups.get(os.path.basename(material.replace('\\',os.sep)).split('.')[0]):
                self.createMLTemplateGroup(mltemplate,material.replace('\\',os.sep))

            BaseMat = bpy.data.node_groups.get(os.path.basename(material.replace('\\',os.sep)).split('.')[0])
            if BaseMat:
                BMN = create_node(NG.nodes,"ShaderNodeGroup", (-1800,-150))
                BMN.width = 300
                BMN.hide = False
                BMN.node_tree = BaseMat

            # SET LAYER GROUP DEFAULT VALUES

            if colorScale != None and colorScale in OverrideTable["ColorScale"]:
                LayerGroupN.inputs['ColorScale'].default_value = OverrideTable["ColorScale"][colorScale]
                LayerGroupN['colorScale']=colorScale
            else:
                LayerGroupN.inputs['ColorScale'].default_value = (1.0,1.0,1.0,1)

            if MatTile != None:
                LayerGroupN.inputs['MatTile'].default_value = float(MatTile)
            else:
                LayerGroupN.inputs['MatTile'].default_value = 1

            if OffsetU !=None:
                LayerGroupN.inputs['OffsetU'].default_value= OffsetU
            else:
                LayerGroupN.inputs['OffsetU'].default_value=0

            if OffsetV !=None:
                LayerGroupN.inputs['OffsetV'].default_value= OffsetV
            else:
                LayerGroupN.inputs['OffsetV'].default_value=0

            if normalStrength != None and normalStrength in OverrideTable["NormalStrength"]:
                LayerGroupN.inputs['NormalStrength'].default_value = OverrideTable["NormalStrength"][normalStrength]
            else:
                LayerGroupN.inputs['NormalStrength'].default_value = 1

            if microblendNormalStrength != None:
                LayerGroupN.inputs['MicroblendNormalStrength'].default_value = float(microblendNormalStrength)
            else:
                LayerGroupN.inputs['MicroblendNormalStrength'].default_value = 1

            if MicroblendContrast != None:
                LayerGroupN.inputs['MicroblendContrast'].default_value = float(MicroblendContrast)
            else:
                LayerGroupN.inputs['MicroblendContrast'].default_value = 1

            if MbScale != None:
                LayerGroupN.inputs['MbTile'].default_value = float(MbScale)
            else:
                LayerGroupN.inputs['MbTile'].default_value = 1

            if MicroblendOffsetU != None:
                LayerGroupN.inputs['MicroblendOffsetU'].default_value = float(MicroblendOffsetU)
            else:
                LayerGroupN.inputs['MicroblendOffsetU'].default_value = 0

            if MicroblendOffsetV != None:
                LayerGroupN.inputs['MicroblendOffsetV'].default_value = float(MicroblendOffsetV)
            else:
                LayerGroupN.inputs['MicroblendOffsetV'].default_value = 0

            if opacity != None:
                LayerGroupN.inputs['Opacity'].default_value = float(opacity)
            else:
                LayerGroupN.inputs['Opacity'].default_value = 1

            if metalLevelsIn != None and metalLevelsIn in OverrideTable["MetalLevelsIn"]:
                LayerGroupN.inputs['MetalLevelsIn'].default_value = OverrideTable["MetalLevelsIn"][metalLevelsIn]
            else:
                LayerGroupN.inputs['MetalLevelsIn'].default_value = (1,0)

            if metalLevelsOut != None and metalLevelsOut in OverrideTable["MetalLevelsOut"]:
                LayerGroupN.inputs['MetalLevelsOut'].default_value = OverrideTable["MetalLevelsOut"][metalLevelsOut]
            else:
                LayerGroupN.inputs['MetalLevelsOut'].default_value = (1,0)

            if roughLevelsIn != None and roughLevelsIn in OverrideTable["RoughLevelsIn"]:
                LayerGroupN.inputs['RoughLevelsIn'].default_value = OverrideTable["RoughLevelsIn"][roughLevelsIn]
            else:
                LayerGroupN.inputs['RoughLevelsIn'].default_value = (1,0)

            if roughLevelsOut != None and roughLevelsOut in OverrideTable["RoughLevelsOut"]:
                LayerGroupN.inputs['RoughLevelsOut'].default_value = OverrideTable["RoughLevelsOut"][roughLevelsOut]
            else:
                LayerGroupN.inputs['RoughLevelsOut'].default_value = (1,0)


            # DEFINES MAIN MULTILAYERED PROPERTIES

            colorReroute = NG.nodes.new("NodeReroute")
            colorReroute.location = (-1100,25)

            # Microblend texture node
            MBN = create_node(NG.nodes,"ShaderNodeTexImage",(-2300,-600),image = MBI,label = "Microblend")
            MBN.hide = False
            MBMapping = create_node(NG.nodes,"ShaderNodeMapping", (-2300,-550))
            MBUVCombine = create_node(NG.nodes,"ShaderNodeCombineXYZ", (-2300,-500))
            MBTexCord = create_node(NG.nodes,"ShaderNodeTexCoord", (-2300,-450))

            # Roughness
            rLevelsIn = levels_node_group(Mat)
            rLevelsInGroup = NG.nodes.new("ShaderNodeGroup")
            rLevelsInGroup.node_tree = rLevelsIn
            rLevelsInGroup.location = (-1100,-150)
            rLevelsInGroup.label = "R Levels In"
            rLevelsInGroup.inputs[1].default_value = (1,0)

            rLevelsOut = levels_node_group(Mat)
            rLevelsOutGroup = NG.nodes.new("ShaderNodeGroup")
            rLevelsOutGroup.node_tree = rLevelsOut
            rLevelsOutGroup.location = (-850,-150)
            rLevelsOutGroup.label = "R Levels Out"
            rLevelsOutGroup.inputs[1].default_value = (1,0)

            # Metalness
            mLevelsIn = levels_node_group(Mat)
            mLevelsInGroup = NG.nodes.new("ShaderNodeGroup")
            mLevelsInGroup.node_tree = mLevelsIn
            mLevelsInGroup.location = (-1100,0)
            mLevelsInGroup.label = "M Levels In"
            mLevelsInGroup.inputs[1].default_value = (1,0)

            mLevelsOut = levels_node_group(Mat)
            mLevelsOutGroup = NG.nodes.new("ShaderNodeGroup")
            mLevelsOutGroup.node_tree = mLevelsOut
            mLevelsOutGroup.location = (-850,0)
            mLevelsOutGroup.label = "M Levels Out"
            mLevelsOutGroup.inputs[1].default_value = (1,0)


            # --- Mask Layer ---
            mask_mixer=mask_mixer_node_group(Mat)
            mask_mixergroup = NG.nodes.new("ShaderNodeGroup")
            mask_mixergroup.name = "Group"
            mask_mixergroup.node_tree = mask_mixer
            mask_mixergroup.location = (-1800, -400)
            mask_mixergroup.width = 300

            if vers[0]<5:
                BLND = _getOrCreateLayerBlend(Mat)
                LayerGroupBLND = NG.nodes.new("ShaderNodeGroup")
                LayerGroupBLND.location = (-500, 300)
                LayerGroupBLND.node_tree = BLND
            else:
                bundlecombine = create_node(NG.nodes, "NodeCombineBundle",(-500,300))
                bundlecombine.hide = False
                bundlecombineColor = bundlecombine.bundle_items.new(socket_type='RGBA', name='Color')
                bundlecombineMetal = bundlecombine.bundle_items.new(socket_type='FLOAT', name='Metalness')
                bundlecombineRough = bundlecombine.bundle_items.new(socket_type='FLOAT', name='Roughness')
                bundlecombineNormal = bundlecombine.bundle_items.new(socket_type='VECTOR', name='Normal')
                bundlecombineMicroblend = bundlecombine.bundle_items.new(socket_type='VECTOR', name='Microblend')
                bundlecombineMask = bundlecombine.bundle_items.new(socket_type='FLOAT', name='Layer Mask')

            mLevelsInReroute = NG.nodes.new("NodeReroute")
            mLevelsInReroute.location = (-1350,-10)
            mLevelsOutReroute = NG.nodes.new("NodeReroute")
            mLevelsOutReroute.location = (-1350,-35)
            rLevelsInReroute = NG.nodes.new("NodeReroute")
            rLevelsInReroute.location = (-1350,-60)
            rLevelsOutReroute = NG.nodes.new("NodeReroute")
            rLevelsOutReroute.location = (-1350,-85)

            normalReroute = NG.nodes.new("NodeReroute")
            normalReroute.location = (-700,-350)

            microblendReroute = NG.nodes.new("NodeReroute")
            microblendReroute.location = (-700,-425)

            layerMaskReroute = NG.nodes.new("NodeReroute")
            layerMaskReroute.location = (-700,-450)

            # CREATE FINAL LINKS
            if vers[0]<5:
                NG.links.new(GroupInN.outputs['Color'],LayerGroupBLND.inputs['Color A'])
                NG.links.new(GroupInN.outputs['Metalness'],LayerGroupBLND.inputs['Metalness A'])
                NG.links.new(GroupInN.outputs['Roughness'],LayerGroupBLND.inputs['Roughness A'])
                NG.links.new(GroupInN.outputs['Normal'],LayerGroupBLND.inputs['Normal A'])
                NG.links.new(GroupInN.outputs['Microblend'],LayerGroupBLND.inputs['Microblend A'])

                NG.links.new(colorReroute.outputs[0],LayerGroupBLND.inputs['Color B'])
                NG.links.new(mLevelsOutGroup.outputs[0],LayerGroupBLND.inputs['Metalness B'])
                NG.links.new(rLevelsOutGroup.outputs[0],LayerGroupBLND.inputs['Roughness B'])
                NG.links.new(BMN.outputs[3],normalReroute.inputs[0])
                NG.links.new(normalReroute.outputs[0],LayerGroupBLND.inputs['Normal B'])
                NG.links.new(mask_mixergroup.outputs[0],microblendReroute.inputs[0])
                NG.links.new(microblendReroute.outputs[0],LayerGroupBLND.inputs['Microblend B'])
                NG.links.new(mask_mixergroup.outputs[1],layerMaskReroute.inputs[0])
                NG.links.new(layerMaskReroute.outputs[0],LayerGroupBLND.inputs['Layer Mask'])

                NG.links.new(LayerGroupBLND.outputs['Color'],GroupOutN.inputs['Color'])
                NG.links.new(LayerGroupBLND.outputs['Metalness'],GroupOutN.inputs['Metalness'])
                NG.links.new(LayerGroupBLND.outputs['Roughness'],GroupOutN.inputs['Roughness'])
                NG.links.new(LayerGroupBLND.outputs['Normal'],GroupOutN.inputs['Normal'])
                NG.links.new(LayerGroupBLND.outputs['Microblend'],GroupOutN.inputs['Microblend'])
            else:
                NG.links.new(colorReroute.outputs[0],bundlecombine.inputs['Color'])
                NG.links.new(mLevelsOutGroup.outputs[0],bundlecombine.inputs['Metalness'])
                NG.links.new(rLevelsOutGroup.outputs[0],bundlecombine.inputs['Roughness'])
                NG.links.new(normalReroute.outputs[0],bundlecombine.inputs['Normal'])
                NG.links.new(mask_mixergroup.outputs[0],microblendReroute.inputs[0])
                NG.links.new(microblendReroute.outputs[0],bundlecombine.inputs['Microblend'])
                NG.links.new(layerMaskReroute.outputs[0],bundlecombine.inputs['Layer Mask'])
                NG.links.new(bundlecombine.outputs[0],GroupOutN.inputs['Layer'])

                NG.links.new(colorReroute.outputs[0],GroupOutN.inputs['Color'])
                NG.links.new(mLevelsOutGroup.outputs[0],GroupOutN.inputs['Metalness'])
                NG.links.new(rLevelsOutGroup.outputs[0],GroupOutN.inputs['Roughness'])
                NG.links.new(BMN.outputs[3],normalReroute.inputs[0])
                NG.links.new(normalReroute.outputs[0],GroupOutN.inputs['Normal'])
                NG.links.new(mask_mixergroup.outputs[0],microblendReroute.inputs[0])
                NG.links.new(microblendReroute.outputs[0],GroupOutN.inputs['Microblend'])
                NG.links.new(mask_mixergroup.outputs[1],layerMaskReroute.inputs[0])
                NG.links.new(layerMaskReroute.outputs[0],GroupOutN.inputs['Layer Mask'])

            NG.links.new(GroupInN.outputs['ColorScale'],BMN.inputs[0])
            NG.links.new(GroupInN.outputs['NormalStrength'],BMN.inputs[4])
            NG.links.new(GroupInN.outputs['MetalLevelsIn'],mLevelsInReroute.inputs[0])
            NG.links.new(mLevelsInReroute.outputs[0],mLevelsInGroup.inputs[1])
            NG.links.new(GroupInN.outputs['MetalLevelsOut'],mLevelsOutReroute.inputs[0])
            NG.links.new(mLevelsOutReroute.outputs[0],mLevelsOutGroup.inputs[1])
            NG.links.new(GroupInN.outputs['RoughLevelsIn'],rLevelsInReroute.inputs[0])
            NG.links.new(rLevelsInReroute.outputs[0],rLevelsInGroup.inputs[1])
            NG.links.new(GroupInN.outputs['RoughLevelsOut'],rLevelsOutReroute.inputs[0])
            NG.links.new(rLevelsOutReroute.outputs[0],rLevelsOutGroup.inputs[1])

            NG.links.new(GroupInN.outputs['MatTile'],BMN.inputs[1])
            if len(BMN.inputs) > 1:
              NG.links.new(GroupInN.outputs['OffsetU'],BMN.inputs[2])
              if len(BMN.inputs) > 2:
                NG.links.new(GroupInN.outputs['OffsetV'],BMN.inputs[3])
            NG.links.new(GroupInN.outputs['MicroblendNormalStrength'],mask_mixergroup.inputs['MicroblendNormalStrength'])
            NG.links.new(GroupInN.outputs['MicroblendContrast'],mask_mixergroup.inputs['MicroblendContrast'])
            NG.links.new(GroupInN.outputs['MbTile'],MBMapping.inputs[3])
            NG.links.new(GroupInN.outputs['MicroblendOffsetU'],MBUVCombine.inputs[0])
            NG.links.new(GroupInN.outputs['MicroblendOffsetV'],MBUVCombine.inputs[1])
            NG.links.new(GroupInN.outputs['Opacity'],mask_mixergroup.inputs['Opacity'])
            NG.links.new(GroupInN.outputs['Mask'],mask_mixergroup.inputs['Mask'])
            NG.links.new(MBTexCord.outputs[2],MBMapping.inputs[0])
            NG.links.new(MBUVCombine.outputs[0],MBMapping.inputs[1])
            NG.links.new(MBMapping.outputs[0],MBN.inputs[0])
            NG.links.new(BMN.outputs[0],colorReroute.inputs[0])
            NG.links.new(BMN.outputs[1],mLevelsInGroup.inputs[0])
            NG.links.new(mLevelsInGroup.outputs[0],mLevelsOutGroup.inputs[0])
            NG.links.new(BMN.outputs[2],rLevelsInGroup.inputs[0])
            NG.links.new(rLevelsInGroup.outputs[0],rLevelsOutGroup.inputs[0])
            NG.links.new(MBN.outputs[0],mask_mixergroup.inputs['Microblend'])
            NG.links.new(MBN.outputs[1],mask_mixergroup.inputs['Microblend Alpha'])


        #layer group input node output names
        #['ColorScale', 'MatTile', 'MbTile', 'MicroblendNormalStrength', 'MicroblendContrast', 'MicroblendOffsetU', 'MicroblendOffsetV', 'NormalStrength', 'Opacity', 'Mask', 'OffsetU', 'OffsetV', '']
        # Data for vehicledestrblendshape.mt
        # Instead of maintaining two material py files we should setup the main multilayered shader to handle variants such as the vehicle material
        if "BakedNormal" in Data.keys():
            LayerNormal=Data["BakedNormal"]
        else:
            LayerNormal=Data["GlobalNormal"]

        self.setupMaterial(file_name+"_Layer_", LayerCount, CurMat, Data["MultilayerMask"], LayerNormal)

