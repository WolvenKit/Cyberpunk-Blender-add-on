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
    
    #mask_mixer interface
    #Socket Normal Map
    normal_map_socket = mask_mixer.interface.new_socket(name = "Normal Map", in_out='OUTPUT', socket_type = 'NodeSocketVector')
    normal_map_socket.subtype = 'NONE'
    normal_map_socket.default_value = (0.0, 0.0, 0.0)
    normal_map_socket.min_value = -3.4028234663852886e+38
    normal_map_socket.max_value = 3.4028234663852886e+38
    normal_map_socket.attribute_domain = 'POINT'
    
    #Socket Layer Mask
    layer_mask_socket = mask_mixer.interface.new_socket(name = "Layer Mask", in_out='OUTPUT', socket_type = 'NodeSocketFloat')
    layer_mask_socket.subtype = 'NONE'
    layer_mask_socket.default_value = 0.0
    layer_mask_socket.min_value = -3.4028234663852886e+38
    layer_mask_socket.max_value = 3.4028234663852886e+38
    layer_mask_socket.attribute_domain = 'POINT'
    
    #Socket MicroblendNormalStrength
    microblendnormalstrength_socket = mask_mixer.interface.new_socket(name = "MicroblendNormalStrength", in_out='INPUT', socket_type = 'NodeSocketFloat')
    microblendnormalstrength_socket.subtype = 'NONE'
    microblendnormalstrength_socket.default_value = 0.0
    microblendnormalstrength_socket.min_value = -3.4028234663852886e+38
    microblendnormalstrength_socket.max_value = 3.4028234663852886e+38
    microblendnormalstrength_socket.attribute_domain = 'POINT'
    
    #Socket MicroblendContrast
    microblendcontrast_socket = mask_mixer.interface.new_socket(name = "MicroblendContrast", in_out='INPUT', socket_type = 'NodeSocketFloat')
    microblendcontrast_socket.subtype = 'NONE'
    microblendcontrast_socket.default_value = 0.5
    microblendcontrast_socket.min_value = 0.0
    microblendcontrast_socket.max_value = 1.0
    microblendcontrast_socket.attribute_domain = 'POINT'
    
    #Socket Opacity
    opacity_socket = mask_mixer.interface.new_socket(name = "Opacity", in_out='INPUT', socket_type = 'NodeSocketFloat')
    opacity_socket.subtype = 'NONE'
    opacity_socket.default_value = 1.0
    opacity_socket.min_value = -10000.0
    opacity_socket.max_value = 10000.0
    opacity_socket.attribute_domain = 'POINT'
    
    #Socket Mask
    mask_socket = mask_mixer.interface.new_socket(name = "Mask", in_out='INPUT', socket_type = 'NodeSocketColor')
    mask_socket.attribute_domain = 'POINT'
    
    #Socket Microblend
    microblend_socket = mask_mixer.interface.new_socket(name = "Microblend", in_out='INPUT', socket_type = 'NodeSocketColor')
    microblend_socket.attribute_domain = 'POINT'
    
    #Socket Microblend Alpha
    microblend_alpha_socket = mask_mixer.interface.new_socket(name = "Microblend Alpha", in_out='INPUT', socket_type = 'NodeSocketColor')
    microblend_alpha_socket.attribute_domain = 'POINT'
    
    
    #initialize mask_mixer nodes
    #node Group Output.001
    group_output_001 = mask_mixer.nodes.new("NodeGroupOutput")
    group_output_001.name = "Group Output.001"
    group_output_001.is_active_output = True
    
    #node RGB Curves.002
    rgb_curves_002 = mask_mixer.nodes.new("ShaderNodeRGBCurve")
    rgb_curves_002.name = "RGB Curves.002"
    #mapping settings
    rgb_curves_002.mapping.extend = 'EXTRAPOLATED'
    rgb_curves_002.mapping.tone = 'STANDARD'
    rgb_curves_002.mapping.black_level = (0.0, 0.0, 0.0)
    rgb_curves_002.mapping.white_level = (1.0, 1.0, 1.0)
    rgb_curves_002.mapping.clip_min_x = 0.0
    rgb_curves_002.mapping.clip_min_y = 0.0
    rgb_curves_002.mapping.clip_max_x = 1.0
    rgb_curves_002.mapping.clip_max_y = 1.0
    rgb_curves_002.mapping.use_clip = True
    #curve 0
    rgb_curves_002_curve_0 = rgb_curves_002.mapping.curves[0]
    rgb_curves_002_curve_0_point_0 = rgb_curves_002_curve_0.points[0]
    rgb_curves_002_curve_0_point_0.location = (0.0, 1.0)
    rgb_curves_002_curve_0_point_0.handle_type = 'AUTO'
    rgb_curves_002_curve_0_point_1 = rgb_curves_002_curve_0.points[1]
    rgb_curves_002_curve_0_point_1.location = (1.0, 0.0)
    rgb_curves_002_curve_0_point_1.handle_type = 'AUTO'
    #curve 1
    rgb_curves_002_curve_1 = rgb_curves_002.mapping.curves[1]
    rgb_curves_002_curve_1_point_0 = rgb_curves_002_curve_1.points[0]
    rgb_curves_002_curve_1_point_0.location = (0.0, 1.0)
    rgb_curves_002_curve_1_point_0.handle_type = 'AUTO'
    rgb_curves_002_curve_1_point_1 = rgb_curves_002_curve_1.points[1]
    rgb_curves_002_curve_1_point_1.location = (1.0, 0.0)
    rgb_curves_002_curve_1_point_1.handle_type = 'AUTO'
    #curve 2
    rgb_curves_002_curve_2 = rgb_curves_002.mapping.curves[2]
    rgb_curves_002_curve_2_point_0 = rgb_curves_002_curve_2.points[0]
    rgb_curves_002_curve_2_point_0.location = (0.0, 0.0)
    rgb_curves_002_curve_2_point_0.handle_type = 'AUTO'
    rgb_curves_002_curve_2_point_1 = rgb_curves_002_curve_2.points[1]
    rgb_curves_002_curve_2_point_1.location = (1.0, 1.0)
    rgb_curves_002_curve_2_point_1.handle_type = 'AUTO'
    #curve 3
    rgb_curves_002_curve_3 = rgb_curves_002.mapping.curves[3]
    rgb_curves_002_curve_3_point_0 = rgb_curves_002_curve_3.points[0]
    rgb_curves_002_curve_3_point_0.location = (0.0, 0.0)
    rgb_curves_002_curve_3_point_0.handle_type = 'AUTO'
    rgb_curves_002_curve_3_point_1 = rgb_curves_002_curve_3.points[1]
    rgb_curves_002_curve_3_point_1.location = (1.0, 1.0)
    rgb_curves_002_curve_3_point_1.handle_type = 'AUTO'
    #update curve after changes
    rgb_curves_002.mapping.update()
    #Fac
    rgb_curves_002.inputs[0].default_value = 1.0
    
    #node Math.003
    math_003_1 = mask_mixer.nodes.new("ShaderNodeMath")
    math_003_1.name = "Math.003"
    math_003_1.operation = 'GREATER_THAN'
    math_003_1.use_clamp = False
    #Value_001
    math_003_1.inputs[1].default_value = 0.0
    #Value_002
    math_003_1.inputs[2].default_value = 0.5
    
    #node Mix (Legacy).002
    mix__legacy__002 = mask_mixer.nodes.new("ShaderNodeMixRGB")
    mix__legacy__002.name = "Mix (Legacy).002"
    mix__legacy__002.blend_type = 'MIX'
    mix__legacy__002.use_alpha = False
    mix__legacy__002.use_clamp = False
    
    #node Math.004
    math_004_1 = mask_mixer.nodes.new("ShaderNodeMath")
    math_004_1.name = "Math.004"
    math_004_1.operation = 'ABSOLUTE'
    math_004_1.use_clamp = False
    #Value_001
    math_004_1.inputs[1].default_value = 0.5
    #Value_002
    math_004_1.inputs[2].default_value = 0.5
    
    #node Normal Map.001
    normal_map_001 = mask_mixer.nodes.new("ShaderNodeNormalMap")
    normal_map_001.name = "Normal Map.001"
    normal_map_001.space = 'TANGENT'
    normal_map_001.uv_map = ""
    
    #node Math.005
    math_005_1 = mask_mixer.nodes.new("ShaderNodeMath")
    math_005_1.name = "Math.005"
    math_005_1.operation = 'MULTIPLY'
    math_005_1.use_clamp = False
    #Value_002
    math_005_1.inputs[2].default_value = 0.5
    
    #node RGB Curves.003
    rgb_curves_003 = mask_mixer.nodes.new("ShaderNodeRGBCurve")
    rgb_curves_003.name = "RGB Curves.003"
    #mapping settings
    rgb_curves_003.mapping.extend = 'EXTRAPOLATED'
    rgb_curves_003.mapping.tone = 'STANDARD'
    rgb_curves_003.mapping.black_level = (0.0, 0.0, 0.0)
    rgb_curves_003.mapping.white_level = (1.0, 1.0, 1.0)
    rgb_curves_003.mapping.clip_min_x = 0.0
    rgb_curves_003.mapping.clip_min_y = 0.0
    rgb_curves_003.mapping.clip_max_x = 1.0
    rgb_curves_003.mapping.clip_max_y = 1.0
    rgb_curves_003.mapping.use_clip = True
    #curve 0
    rgb_curves_003_curve_0 = rgb_curves_003.mapping.curves[0]
    rgb_curves_003_curve_0_point_0 = rgb_curves_003_curve_0.points[0]
    rgb_curves_003_curve_0_point_0.location = (0.0, 0.0)
    rgb_curves_003_curve_0_point_0.handle_type = 'AUTO'
    rgb_curves_003_curve_0_point_1 = rgb_curves_003_curve_0.points[1]
    rgb_curves_003_curve_0_point_1.location = (1.0, 1.0)
    rgb_curves_003_curve_0_point_1.handle_type = 'AUTO'
    #curve 1
    rgb_curves_003_curve_1 = rgb_curves_003.mapping.curves[1]
    rgb_curves_003_curve_1_point_0 = rgb_curves_003_curve_1.points[0]
    rgb_curves_003_curve_1_point_0.location = (0.0, 1.0)
    rgb_curves_003_curve_1_point_0.handle_type = 'AUTO'
    rgb_curves_003_curve_1_point_1 = rgb_curves_003_curve_1.points[1]
    rgb_curves_003_curve_1_point_1.location = (1.0, 0.0)
    rgb_curves_003_curve_1_point_1.handle_type = 'AUTO'
    #curve 2
    rgb_curves_003_curve_2 = rgb_curves_003.mapping.curves[2]
    rgb_curves_003_curve_2_point_0 = rgb_curves_003_curve_2.points[0]
    rgb_curves_003_curve_2_point_0.location = (0.0, 0.0)
    rgb_curves_003_curve_2_point_0.handle_type = 'AUTO'
    rgb_curves_003_curve_2_point_1 = rgb_curves_003_curve_2.points[1]
    rgb_curves_003_curve_2_point_1.location = (1.0, 1.0)
    rgb_curves_003_curve_2_point_1.handle_type = 'AUTO'
    #curve 3
    rgb_curves_003_curve_3 = rgb_curves_003.mapping.curves[3]
    rgb_curves_003_curve_3_point_0 = rgb_curves_003_curve_3.points[0]
    rgb_curves_003_curve_3_point_0.location = (0.0, 0.0)
    rgb_curves_003_curve_3_point_0.handle_type = 'AUTO'
    rgb_curves_003_curve_3_point_1 = rgb_curves_003_curve_3.points[1]
    rgb_curves_003_curve_3_point_1.location = (1.0, 1.0)
    rgb_curves_003_curve_3_point_1.handle_type = 'AUTO'
    #update curve after changes
    rgb_curves_003.mapping.update()
    #Fac
    rgb_curves_003.inputs[0].default_value = 1.0
    
    #node Float Curve.002
    float_curve_002 = mask_mixer.nodes.new("ShaderNodeFloatCurve")
    float_curve_002.name = "Float Curve.002"
    #mapping settings
    float_curve_002.mapping.extend = 'EXTRAPOLATED'
    float_curve_002.mapping.tone = 'STANDARD'
    float_curve_002.mapping.black_level = (0.0, 0.0, 0.0)
    float_curve_002.mapping.white_level = (1.0, 1.0, 1.0)
    float_curve_002.mapping.clip_min_x = 0.0
    float_curve_002.mapping.clip_min_y = 0.0
    float_curve_002.mapping.clip_max_x = 1.0
    float_curve_002.mapping.clip_max_y = 1.0
    float_curve_002.mapping.use_clip = True
    #curve 0
    float_curve_002_curve_0 = float_curve_002.mapping.curves[0]
    float_curve_002_curve_0_point_0 = float_curve_002_curve_0.points[0]
    float_curve_002_curve_0_point_0.location = (0.0, 0.0)
    float_curve_002_curve_0_point_0.handle_type = 'AUTO_CLAMPED'
    float_curve_002_curve_0_point_1 = float_curve_002_curve_0.points[1]
    float_curve_002_curve_0_point_1.location = (0.5045454502105713, 1.0)
    float_curve_002_curve_0_point_1.handle_type = 'AUTO_CLAMPED'
    float_curve_002_curve_0_point_2 = float_curve_002_curve_0.points.new(1.0, 0.0)
    float_curve_002_curve_0_point_2.handle_type = 'AUTO_CLAMPED'
    #update curve after changes
    float_curve_002.mapping.update()
    #Factor
    float_curve_002.inputs[0].default_value = 1.0
    
    #node Reroute
    reroute = mask_mixer.nodes.new("NodeReroute")
    reroute.name = "Reroute"
    #node Math.011
    math_011 = mask_mixer.nodes.new("ShaderNodeMath")
    math_011.label = "opacity"
    math_011.name = "Math.011"
    math_011.operation = 'MULTIPLY'
    math_011.use_clamp = False
    #Value_002
    math_011.inputs[2].default_value = 0.5

    inverted_overlay = inverted_overlay_node_group()
    inverted_gamma = inverted_gamma_node_group()

    #node Group
    group = mask_mixer.nodes.new("ShaderNodeGroup")
    group.name = "Group"
    group.node_tree = inverted_overlay
    
    #node Group.001
    group_001 = mask_mixer.nodes.new("ShaderNodeGroup")
    group_001.name = "Group.001"
    group_001.node_tree = inverted_gamma
    
    #node Group Input.001
    group_input_001 = mask_mixer.nodes.new("NodeGroupInput")
    group_input_001.name = "Group Input.001"
    
    
    #Set locations
    group_output_001.location = (1220.0, -1360.0)
    rgb_curves_002.location = (-260.0, -1320.0)
    math_003_1.location = (-240.0, -1280.0)
    mix__legacy__002.location = (0.0, -1380.0)
    math_004_1.location = (640.0, -1120.0)
    normal_map_001.location = (900.0, -1380.0)
    math_005_1.location = (640.0, -1160.0)
    rgb_curves_003.location = (-540.0, -1380.0)
    float_curve_002.location = (540.0, -1200.0)
    reroute.location = (-580.0, -1740.0)
    math_011.location = (280.0, -1620.0)
    group.location = (-460.0, -1580.0)
    group_001.location = (-60.0, -1460.0)
    group_input_001.location = (-1000.0, -1280.0)
    
    #Set dimensions
    group_output_001.width, group_output_001.height = 140.0, 100.0
    rgb_curves_002.width, rgb_curves_002.height = 166.4442138671875, 100.0
    math_003_1.width, math_003_1.height = 140.0, 100.0
    mix__legacy__002.width, mix__legacy__002.height = 140.0, 100.0
    math_004_1.width, math_004_1.height = 140.0, 100.0
    normal_map_001.width, normal_map_001.height = 150.0, 100.0
    math_005_1.width, math_005_1.height = 140.0, 100.0
    rgb_curves_003.width, rgb_curves_003.height = 192.269775390625, 100.0
    float_curve_002.width, float_curve_002.height = 240.0, 100.0
    reroute.width, reroute.height = 16.0, 100.0
    math_011.width, math_011.height = 140.0, 100.0
    group.width, group.height = 180.0, 100.0
    group_001.width, group_001.height = 200.0, 100.0
    group_input_001.width, group_input_001.height = 140.0, 100.0
    
    #initialize mask_mixer links
    #rgb_curves_003.Color -> rgb_curves_002.Color
    mask_mixer.links.new(rgb_curves_003.outputs[0], rgb_curves_002.inputs[1])
    #math_003_1.Value -> mix__legacy__002.Fac
    mask_mixer.links.new(math_003_1.outputs[0], mix__legacy__002.inputs[0])
    #rgb_curves_002.Color -> mix__legacy__002.Color1
    mask_mixer.links.new(rgb_curves_002.outputs[0], mix__legacy__002.inputs[1])
    #mix__legacy__002.Color -> normal_map_001.Color
    mask_mixer.links.new(mix__legacy__002.outputs[0], normal_map_001.inputs[1])
    #float_curve_002.Value -> math_005_1.Value
    mask_mixer.links.new(float_curve_002.outputs[0], math_005_1.inputs[1])
    #math_004_1.Value -> math_005_1.Value
    mask_mixer.links.new(math_004_1.outputs[0], math_005_1.inputs[0])
    #math_005_1.Value -> normal_map_001.Strength
    mask_mixer.links.new(math_005_1.outputs[0], normal_map_001.inputs[0])
    #rgb_curves_003.Color -> mix__legacy__002.Color2
    mask_mixer.links.new(rgb_curves_003.outputs[0], mix__legacy__002.inputs[2])
    #normal_map_001.Normal -> group_output_001.Normal Map
    mask_mixer.links.new(normal_map_001.outputs[0], group_output_001.inputs[0])
    #group_input_001.Microblend -> rgb_curves_003.Color
    mask_mixer.links.new(group_input_001.outputs[4], rgb_curves_003.inputs[1])
    #group_input_001.MicroblendNormalStrength -> math_003_1.Value
    mask_mixer.links.new(group_input_001.outputs[0], math_003_1.inputs[0])
    #group_input_001.MicroblendNormalStrength -> math_004_1.Value
    mask_mixer.links.new(group_input_001.outputs[0], math_004_1.inputs[0])
    #group_input_001.MicroblendContrast -> group.Factor
    mask_mixer.links.new(group_input_001.outputs[1], group.inputs[0])
    #group_input_001.Opacity -> reroute.Input
    mask_mixer.links.new(group_input_001.outputs[2], reroute.inputs[0])
    #group_input_001.Mask -> group.A
    mask_mixer.links.new(group_input_001.outputs[3], group.inputs[1])
    #group_input_001.Microblend Alpha -> group.B
    mask_mixer.links.new(group_input_001.outputs[5], group.inputs[2])
    #group.Value -> group_001.Input
    mask_mixer.links.new(group.outputs[0], group_001.inputs[0])
    #group_input_001.MicroblendContrast -> group_001.Gamma
    mask_mixer.links.new(group_input_001.outputs[1], group_001.inputs[1])
    #group_input_001.Mask -> group_001.Middle
    mask_mixer.links.new(group_input_001.outputs[3], group_001.inputs[2])
    #group_001.Value -> math_011.Value
    mask_mixer.links.new(group_001.outputs[0], math_011.inputs[0])
    #math_011.Value -> group_output_001.Layer Mask
    mask_mixer.links.new(math_011.outputs[0], group_output_001.inputs[1])
    #reroute.Output -> math_011.Value
    mask_mixer.links.new(reroute.outputs[0], math_011.inputs[1])
    #math_011.Value -> float_curve_002.Value
    mask_mixer.links.new(math_011.outputs[0], float_curve_002.inputs[1])
    return mask_mixer
    
def inverted_overlay_node_group():
    if "Inverted Overlay" in bpy.data.node_groups:
        return bpy.data.node_groups["Inverted Overlay"]

    inverted_overlay = bpy.data.node_groups.new(type = 'ShaderNodeTree', name = "Inverted Overlay")
    
    #inverted_overlay interface
    #Socket Value
    value_socket = inverted_overlay.interface.new_socket(name = "Value", in_out='OUTPUT', socket_type = 'NodeSocketFloat')
    value_socket.subtype = 'NONE'
    value_socket.default_value = 0.0
    value_socket.min_value = -3.4028234663852886e+38
    value_socket.max_value = 3.4028234663852886e+38
    value_socket.attribute_domain = 'POINT'
    
    #Socket Factor
    factor_socket = inverted_overlay.interface.new_socket(name = "Factor", in_out='INPUT', socket_type = 'NodeSocketFloat')
    factor_socket.subtype = 'FACTOR'
    factor_socket.default_value = 0.5
    factor_socket.min_value = 0.0
    factor_socket.max_value = 1.0
    factor_socket.attribute_domain = 'POINT'
    
    #Socket A
    a_socket = inverted_overlay.interface.new_socket(name = "A", in_out='INPUT', socket_type = 'NodeSocketFloat')
    a_socket.subtype = 'NONE'
    a_socket.default_value = 0.0
    a_socket.min_value = -3.4028234663852886e+38
    a_socket.max_value = 3.4028234663852886e+38
    a_socket.attribute_domain = 'POINT'
    
    #Socket B
    b_socket = inverted_overlay.interface.new_socket(name = "B", in_out='INPUT', socket_type = 'NodeSocketFloat')
    b_socket.subtype = 'NONE'
    b_socket.default_value = 0.0
    b_socket.min_value = -3.4028234663852886e+38
    b_socket.max_value = 3.4028234663852886e+38
    b_socket.attribute_domain = 'POINT'
    
    
    #initialize inverted_overlay nodes
    #node Group Output
    group_output = inverted_overlay.nodes.new("NodeGroupOutput")
    group_output.name = "Group Output"
    group_output.is_active_output = True
    
    #node Group Input
    group_input = inverted_overlay.nodes.new("NodeGroupInput")
    group_input.name = "Group Input"
    
    #node Math.003
    math_003 = inverted_overlay.nodes.new("ShaderNodeMath")
    math_003.name = "Math.003"
    math_003.operation = 'MULTIPLY'
    math_003.use_clamp = False
    #Value_002
    math_003.inputs[2].default_value = 0.5
    
    #node Math.004
    math_004 = inverted_overlay.nodes.new("ShaderNodeMath")
    math_004.name = "Math.004"
    math_004.operation = 'MULTIPLY'
    math_004.use_clamp = False
    #Value_001
    math_004.inputs[1].default_value = 2.0
    #Value_002
    math_004.inputs[2].default_value = 0.5
    
    #node Math
    math = inverted_overlay.nodes.new("ShaderNodeMath")
    math.name = "Math"
    math.operation = 'SUBTRACT'
    math.use_clamp = False
    #Value
    math.inputs[0].default_value = 1.0
    #Value_002
    math.inputs[2].default_value = 0.5
    
    #node Math.001
    math_001 = inverted_overlay.nodes.new("ShaderNodeMath")
    math_001.name = "Math.001"
    math_001.operation = 'SUBTRACT'
    math_001.use_clamp = False
    #Value
    math_001.inputs[0].default_value = 1.0
    #Value_002
    math_001.inputs[2].default_value = 0.5
    
    #node Math.002
    math_002 = inverted_overlay.nodes.new("ShaderNodeMath")
    math_002.name = "Math.002"
    math_002.operation = 'MULTIPLY'
    math_002.use_clamp = False
    #Value_002
    math_002.inputs[2].default_value = 0.5
    
    #node Math.005
    math_005 = inverted_overlay.nodes.new("ShaderNodeMath")
    math_005.name = "Math.005"
    math_005.operation = 'MULTIPLY'
    math_005.use_clamp = False
    #Value_001
    math_005.inputs[1].default_value = 2.0
    #Value_002
    math_005.inputs[2].default_value = 0.5
    
    #node Math.006
    math_006 = inverted_overlay.nodes.new("ShaderNodeMath")
    math_006.name = "Math.006"
    math_006.operation = 'SUBTRACT'
    math_006.use_clamp = False
    #Value
    math_006.inputs[0].default_value = 1.0
    #Value_002
    math_006.inputs[2].default_value = 0.5
    
    #node Mix.001
    mix_001 = inverted_overlay.nodes.new("ShaderNodeMix")
    mix_001.name = "Mix.001"
    mix_001.blend_type = 'MIX'
    mix_001.clamp_factor = True
    mix_001.clamp_result = False
    mix_001.data_type = 'FLOAT'
    mix_001.factor_mode = 'UNIFORM'
    #Factor_Vector
    mix_001.inputs[1].default_value = (0.5, 0.5, 0.5)
    #A_Vector
    mix_001.inputs[4].default_value = (0.0, 0.0, 0.0)
    #B_Vector
    mix_001.inputs[5].default_value = (0.0, 0.0, 0.0)
    #A_Color
    mix_001.inputs[6].default_value = (0.5, 0.5, 0.5, 1.0)
    #B_Color
    mix_001.inputs[7].default_value = (0.5, 0.5, 0.5, 1.0)
    #A_Rotation
    mix_001.inputs[8].default_value = (0.0, 0.0, 0.0)
    #B_Rotation
    mix_001.inputs[9].default_value = (0.0, 0.0, 0.0)
    
    #node Math.007
    math_007 = inverted_overlay.nodes.new("ShaderNodeMath")
    math_007.name = "Math.007"
    math_007.operation = 'GREATER_THAN'
    math_007.use_clamp = False
    #Value_001
    math_007.inputs[1].default_value = 0.5
    #Value_002
    math_007.inputs[2].default_value = 0.5
    
    #node Mix
    mix = inverted_overlay.nodes.new("ShaderNodeMix")
    mix.name = "Mix"
    mix.blend_type = 'MIX'
    mix.clamp_factor = True
    mix.clamp_result = False
    mix.data_type = 'FLOAT'
    mix.factor_mode = 'UNIFORM'
    #Factor_Vector
    mix.inputs[1].default_value = (0.5, 0.5, 0.5)
    #A_Vector
    mix.inputs[4].default_value = (0.0, 0.0, 0.0)
    #B_Vector
    mix.inputs[5].default_value = (0.0, 0.0, 0.0)
    #A_Color
    mix.inputs[6].default_value = (0.5, 0.5, 0.5, 1.0)
    #B_Color
    mix.inputs[7].default_value = (0.5, 0.5, 0.5, 1.0)
    #A_Rotation
    mix.inputs[8].default_value = (0.0, 0.0, 0.0)
    #B_Rotation
    mix.inputs[9].default_value = (0.0, 0.0, 0.0)
    
    #node Float Curve.004
    float_curve_004 = inverted_overlay.nodes.new("ShaderNodeFloatCurve")
    float_curve_004.name = "Float Curve.004"
    #mapping settings
    float_curve_004.mapping.extend = 'EXTRAPOLATED'
    float_curve_004.mapping.tone = 'STANDARD'
    float_curve_004.mapping.black_level = (0.0, 0.0, 0.0)
    float_curve_004.mapping.white_level = (1.0, 1.0, 1.0)
    float_curve_004.mapping.clip_min_x = 0.0
    float_curve_004.mapping.clip_min_y = 0.0
    float_curve_004.mapping.clip_max_x = 1.0
    float_curve_004.mapping.clip_max_y = 1.0
    float_curve_004.mapping.use_clip = True
    #curve 0
    float_curve_004_curve_0 = float_curve_004.mapping.curves[0]
    float_curve_004_curve_0_point_0 = float_curve_004_curve_0.points[0]
    float_curve_004_curve_0_point_0.location = (0.0, 0.0)
    float_curve_004_curve_0_point_0.handle_type = 'AUTO'
    float_curve_004_curve_0_point_1 = float_curve_004_curve_0.points[1]
    float_curve_004_curve_0_point_1.location = (0.27000001072883606, 0.23000000417232513)
    float_curve_004_curve_0_point_1.handle_type = 'AUTO'
    float_curve_004_curve_0_point_2 = float_curve_004_curve_0.points.new(0.5, 0.5)
    float_curve_004_curve_0_point_2.handle_type = 'VECTOR'
    float_curve_004_curve_0_point_3 = float_curve_004_curve_0.points.new(1.0, 1.0)
    float_curve_004_curve_0_point_3.handle_type = 'AUTO'
    #update curve after changes
    float_curve_004.mapping.update()
    #Factor
    float_curve_004.inputs[0].default_value = 1.0
    
    #node Math.008
    math_008 = inverted_overlay.nodes.new("ShaderNodeMath")
    math_008.name = "Math.008"
    math_008.operation = 'SUBTRACT'
    math_008.use_clamp = False
    #Value
    math_008.inputs[0].default_value = 1.0
    #Value_002
    math_008.inputs[2].default_value = 0.5
    
    
    #Set locations
    group_output.location = (2020.0, 40.0)
    group_input.location = (-1080.0, 0.0)
    math_003.location = (-100.0, 280.0)
    math_004.location = (80.0, 280.0)
    math.location = (-200.0, -460.0)
    math_001.location = (-200.0, -300.0)
    math_002.location = (40.0, -320.0)
    math_005.location = (240.0, -320.0)
    math_006.location = (440.0, -320.0)
    mix_001.location = (880.0, 60.0)
    math_007.location = (80.0, -40.0)
    mix.location = (1300.0, 320.0)
    float_curve_004.location = (-660.0, -60.0)
    math_008.location = (1020.0, 340.0)
    
    #Set dimensions
    group_output.width, group_output.height = 140.0, 100.0
    group_input.width, group_input.height = 140.0, 100.0
    math_003.width, math_003.height = 140.0, 100.0
    math_004.width, math_004.height = 140.0, 100.0
    math.width, math.height = 140.0, 100.0
    math_001.width, math_001.height = 140.0, 100.0
    math_002.width, math_002.height = 140.0, 100.0
    math_005.width, math_005.height = 140.0, 100.0
    math_006.width, math_006.height = 140.0, 100.0
    mix_001.width, mix_001.height = 140.0, 100.0
    math_007.width, math_007.height = 140.0, 100.0
    mix.width, mix.height = 140.0, 100.0
    float_curve_004.width, float_curve_004.height = 240.0, 100.0
    math_008.width, math_008.height = 140.0, 100.0
    
    #initialize inverted_overlay links
    #math_003.Value -> math_004.Value
    inverted_overlay.links.new(math_003.outputs[0], math_004.inputs[0])
    #group_input.B -> math_003.Value
    inverted_overlay.links.new(group_input.outputs[2], math_003.inputs[1])
    #math_001.Value -> math_002.Value
    inverted_overlay.links.new(math_001.outputs[0], math_002.inputs[0])
    #math.Value -> math_002.Value
    inverted_overlay.links.new(math.outputs[0], math_002.inputs[1])
    #math_002.Value -> math_005.Value
    inverted_overlay.links.new(math_002.outputs[0], math_005.inputs[0])
    #math_005.Value -> math_006.Value
    inverted_overlay.links.new(math_005.outputs[0], math_006.inputs[1])
    #group_input.B -> math.Value
    inverted_overlay.links.new(group_input.outputs[2], math.inputs[1])
    #group_input.A -> math_007.Value
    inverted_overlay.links.new(group_input.outputs[1], math_007.inputs[0])
    #mix_001.Result -> mix.B
    inverted_overlay.links.new(mix_001.outputs[0], mix.inputs[3])
    #group_input.A -> mix.A
    inverted_overlay.links.new(group_input.outputs[1], mix.inputs[2])
    #math_008.Value -> mix.Factor
    inverted_overlay.links.new(math_008.outputs[0], mix.inputs[0])
    #math_006.Value -> mix_001.B
    inverted_overlay.links.new(math_006.outputs[0], mix_001.inputs[3])
    #math_004.Value -> mix_001.A
    inverted_overlay.links.new(math_004.outputs[0], mix_001.inputs[2])
    #mix.Result -> group_output.Value
    inverted_overlay.links.new(mix.outputs[0], group_output.inputs[0])
    #math_007.Value -> mix_001.Factor
    inverted_overlay.links.new(math_007.outputs[0], mix_001.inputs[0])
    #group_input.A -> float_curve_004.Value
    inverted_overlay.links.new(group_input.outputs[1], float_curve_004.inputs[1])
    #float_curve_004.Value -> math_003.Value
    inverted_overlay.links.new(float_curve_004.outputs[0], math_003.inputs[0])
    #float_curve_004.Value -> math_001.Value
    inverted_overlay.links.new(float_curve_004.outputs[0], math_001.inputs[1])
    #group_input.Factor -> math_008.Value
    inverted_overlay.links.new(group_input.outputs[0], math_008.inputs[1])
    return inverted_overlay

#initialize Inverted Gamma node group
def inverted_gamma_node_group():
    if "Inverted Gamma" in bpy.data.node_groups:
        return bpy.data.node_groups["Inverted Gamma"]

    inverted_gamma = bpy.data.node_groups.new(type = 'ShaderNodeTree', name = "Inverted Gamma")
    
    #inverted_gamma interface
    #Socket Value
    value_socket_1 = inverted_gamma.interface.new_socket(name = "Value", in_out='OUTPUT', socket_type = 'NodeSocketFloat')
    value_socket_1.subtype = 'NONE'
    value_socket_1.default_value = 0.0
    value_socket_1.min_value = -3.4028234663852886e+38
    value_socket_1.max_value = 3.4028234663852886e+38
    value_socket_1.attribute_domain = 'POINT'
    
    #Socket Input
    input_socket = inverted_gamma.interface.new_socket(name = "Input", in_out='INPUT', socket_type = 'NodeSocketFloat')
    input_socket.subtype = 'NONE'
    input_socket.default_value = 0.0
    input_socket.min_value = -3.4028234663852886e+38
    input_socket.max_value = 3.4028234663852886e+38
    input_socket.attribute_domain = 'POINT'
    
    #Socket Gamma
    gamma_socket = inverted_gamma.interface.new_socket(name = "Gamma", in_out='INPUT', socket_type = 'NodeSocketFloat')
    gamma_socket.subtype = 'NONE'
    gamma_socket.default_value = 0.0
    gamma_socket.min_value = -3.4028234663852886e+38
    gamma_socket.max_value = 3.4028234663852886e+38
    gamma_socket.attribute_domain = 'POINT'
    
    #Socket Middle
    middle_socket = inverted_gamma.interface.new_socket(name = "Middle", in_out='INPUT', socket_type = 'NodeSocketFloat')
    middle_socket.subtype = 'NONE'
    middle_socket.default_value = 0.18000000715255737
    middle_socket.min_value = 0.0
    middle_socket.max_value = 1.0
    middle_socket.attribute_domain = 'POINT'
    
    
    #initialize inverted_gamma nodes
    #node Group Output
    group_output_1 = inverted_gamma.nodes.new("NodeGroupOutput")
    group_output_1.name = "Group Output"
    group_output_1.is_active_output = True
    
    #node Group Input
    group_input_1 = inverted_gamma.nodes.new("NodeGroupInput")
    group_input_1.name = "Group Input"
    
    #node Math.006
    math_006_1 = inverted_gamma.nodes.new("ShaderNodeMath")
    math_006_1.name = "Math.006"
    math_006_1.operation = 'DIVIDE'
    math_006_1.use_clamp = False
    #Value_002
    math_006_1.inputs[2].default_value = 0.5
    
    #node Math.007
    math_007_1 = inverted_gamma.nodes.new("ShaderNodeMath")
    math_007_1.label = "gamma"
    math_007_1.name = "Math.007"
    math_007_1.operation = 'POWER'
    math_007_1.use_clamp = False
    #Value_002
    math_007_1.inputs[2].default_value = 0.5
    
    #node Math.008
    math_008_1 = inverted_gamma.nodes.new("ShaderNodeMath")
    math_008_1.name = "Math.008"
    math_008_1.operation = 'MULTIPLY'
    math_008_1.use_clamp = True
    #Value_002
    math_008_1.inputs[2].default_value = 0.5
    
    #node Math.009
    math_009 = inverted_gamma.nodes.new("ShaderNodeMath")
    math_009.label = "1/gamma"
    math_009.name = "Math.009"
    math_009.operation = 'DIVIDE'
    math_009.use_clamp = False
    #Value
    math_009.inputs[0].default_value = 1.0
    #Value_002
    math_009.inputs[2].default_value = 0.5
    
    
    #Set locations
    group_output_1.location = (1240.0, 0.0)
    group_input_1.location = (-490.0, 0.0)
    math_006_1.location = (-40.0, 320.0)
    math_007_1.location = (160.0, 180.0)
    math_008_1.location = (360.0, 60.0)
    math_009.location = (-40.0, 100.0)
    
    #Set dimensions
    group_output_1.width, group_output_1.height = 140.0, 100.0
    group_input_1.width, group_input_1.height = 140.0, 100.0
    math_006_1.width, math_006_1.height = 140.0, 100.0
    math_007_1.width, math_007_1.height = 140.0, 100.0
    math_008_1.width, math_008_1.height = 140.0, 100.0
    math_009.width, math_009.height = 140.0, 100.0
    
    #initialize inverted_gamma links
    #math_006_1.Value -> math_007_1.Value
    inverted_gamma.links.new(math_006_1.outputs[0], math_007_1.inputs[0])
    #math_009.Value -> math_007_1.Value
    inverted_gamma.links.new(math_009.outputs[0], math_007_1.inputs[1])
    #math_007_1.Value -> math_008_1.Value
    inverted_gamma.links.new(math_007_1.outputs[0], math_008_1.inputs[0])
    #group_input_1.Input -> math_006_1.Value
    inverted_gamma.links.new(group_input_1.outputs[0], math_006_1.inputs[0])
    #group_input_1.Gamma -> math_009.Value
    inverted_gamma.links.new(group_input_1.outputs[1], math_009.inputs[1])
    #group_input_1.Middle -> math_006_1.Value
    inverted_gamma.links.new(group_input_1.outputs[2], math_006_1.inputs[1])
    #group_input_1.Middle -> math_008_1.Value
    inverted_gamma.links.new(group_input_1.outputs[2], math_008_1.inputs[1])
    #math_008_1.Value -> group_output_1.Value
    inverted_gamma.links.new(math_008_1.outputs[0], group_output_1.inputs[0])
    return inverted_gamma

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
                ColorScaleMixN = create_node(NG.nodes,"ShaderNodeMixRGB",(-1400,100),blend_type='MULTIPLY')
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
            #NG.links.new(GroupInN.outputs[3],MBNormMultiply.inputs[0])
            #NG.links.new(GroupInN.outputs[4],MBCMicroOffset.inputs[0])
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
            #NG.links.new(MBN.outputs[0],MBRGBCurveN.inputs[1])
            #NG.links.new(MBN.outputs[0],MBMixN.inputs[2])            
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
            
            # Mask Mixer group links
            NG.links.new(GroupInN.outputs[3], mask_mixergroup.inputs[0])
            NG.links.new(GroupInN.outputs[4], mask_mixergroup.inputs[1])
            NG.links.new(GroupInN.outputs[8], mask_mixergroup.inputs[2])
            NG.links.new(GroupInN.outputs[9], mask_mixergroup.inputs[3])
            NG.links.new(MBN.outputs[0], mask_mixergroup.inputs[4])
            NG.links.new(MBN.outputs[1], mask_mixergroup.inputs[5])

            NG.links.new(mask_mixergroup.outputs[0], NormSubN.inputs[0])
            NG.links.new(mask_mixergroup.outputs[1], GroupOutN.inputs[4])
#layer group input node output names
#['ColorScale', 'MatTile', 'MbTile', 'MicroblendNormalStrength', 'MicroblendContrast', 'MicroblendOffsetU', 'MicroblendOffsetV', 'NormalStrength', 'Opacity', 'Mask', 'OffsetU', 'OffsetV', '']
        # Data for vehicledestrblendshape.mt
        # Instead of maintaining two material py files we should setup the main multilayered shader to handle variants such as the vehicle material
        if "BakedNormal" in Data.keys():
            LayerNormal=Data["BakedNormal"]
        else:
            LayerNormal=Data["GlobalNormal"]

        self.createLayerMaterial(file_name+"_Layer_", LayerCount, CurMat, Data["MultilayerMask"], LayerNormal, skip_layers)

  


    

