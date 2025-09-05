# Interior mapping nodegroup using the method described by Andrew Willmott in this talk
# http://www.andrewwillmott.com/talks/from-aaa-to-indie
# Converted to Unity by bgolus in this post https://forum.unity.com/threads/interior-mapping.424676/#post-2751518
# Converted to Blender nodes by fes who was nice enough to share on the Erindale Discord
# Converted to Python with NodetoPython https://github.com/BrendanParmer/NodeToPython
# Nodes to cope with Aspect ratio added by Simarilius

import bpy
from ..main.common import *

def andrew_willmotts_plane_interior_mapping_node_group():
    if 'CP77_AW_Plane_Interior_Mapping' in bpy.data.node_groups.keys():
        return bpy.data.node_groups['CP77_AW_Plane_Interior_Mapping']
    else:            
        andrew_willmotts_interior_mapping= bpy.data.node_groups.new(type = 'ShaderNodeTree', name = "CP77_AW_Plane_Interior_Mapping")

        #initialize andrew_willmott_s_plane_interior_mapping_1 nodes
        #node Frame.002
        frame_002 = andrew_willmotts_interior_mapping.nodes.new("NodeFrame")
        frame_002.label = "i.tangentViewDir.z *= -depthScale;"

        #node Frame.003
        frame_003 = andrew_willmotts_interior_mapping.nodes.new("NodeFrame")
        frame_003.label = "float3 id = 1.0 / i.tangentViewDir;"

        #node Frame.004
        frame_004 = andrew_willmotts_interior_mapping.nodes.new("NodeFrame")
        frame_004.label = "float3 k = abs(id) - pos * id;"

        #node Frame.005
        frame_005 = andrew_willmotts_interior_mapping.nodes.new("NodeFrame")
        frame_005.label = "float kMin = min(min(k.x, k.y), k.z);"

        #node Frame.008
        frame_008 = andrew_willmotts_interior_mapping.nodes.new("NodeFrame")
        frame_008.label = "float interp = hitPosBoxSpace.z * 0.5 + 0.5;"

        #node Frame.009
        frame_009 = andrew_willmotts_interior_mapping.nodes.new("NodeFrame")
        frame_009.label = "float realZ = saturate(interp) / depthScale + 1;"

        #node Frame.010
        frame_010 = andrew_willmotts_interior_mapping.nodes.new("NodeFrame")
        frame_010.label = "interp = 1.0 - (1.0 / realZ);"

        #node Frame.006
        frame_006 = andrew_willmotts_interior_mapping.nodes.new("NodeFrame")
        frame_006.label = "pos += kMin * i.tangentViewDir;"

        #node Frame.007
        frame_007 = andrew_willmotts_interior_mapping.nodes.new("NodeFrame")
        frame_007.label = "float3 pos = float3(roomUV * 2 - 1, -1);"

        #node Frame
        frame = andrew_willmotts_interior_mapping.nodes.new("NodeFrame")
        frame.label = "depthScale"

        #node Frame.001
        frame_001 = andrew_willmotts_interior_mapping.nodes.new("NodeFrame")
        frame_001.label = "tangentViewDir"

        #node Frame.011
        frame_011 = andrew_willmotts_interior_mapping.nodes.new("NodeFrame")
        frame_011.label = "band-aid fix part 2"

        #node Frame.012
        frame_012 = andrew_willmotts_interior_mapping.nodes.new("NodeFrame")
        frame_012.label = "band-aid fix part 1"

        #node Math.003
        math_003 = andrew_willmotts_interior_mapping.nodes.new("ShaderNodeMath")
        math_003.operation = 'MULTIPLY'
        #Value_001
        math_003.inputs[1].default_value = -1.0
        #Value_002
        math_003.inputs[2].default_value = 0.5

        #node Math
        math = andrew_willmotts_interior_mapping.nodes.new("ShaderNodeMath")
        math.operation = 'MULTIPLY'
        #Value_002
        math.inputs[2].default_value = 0.5

        #node Separate XYZ.001
        separate_xyz_001 = andrew_willmotts_interior_mapping.nodes.new("ShaderNodeSeparateXYZ")

        #node Combine XYZ
        combine_xyz = andrew_willmotts_interior_mapping.nodes.new("ShaderNodeCombineXYZ")

        #node Reroute
        reroute = andrew_willmotts_interior_mapping.nodes.new("NodeReroute")
        #node Vector Math.003
        vector_math_003 = andrew_willmotts_interior_mapping.nodes.new("ShaderNodeVectorMath")
        vector_math_003.operation = 'DIVIDE'
        #Vector
        vector_math_003.inputs[0].default_value = (1.0, 1.0, 1.0)
        #Vector_002
        vector_math_003.inputs[2].default_value = (0.0, 0.0, 0.0)
        #Scale
        vector_math_003.inputs[3].default_value = 1.0

        #node Vector Math.006
        vector_math_006 = andrew_willmotts_interior_mapping.nodes.new("ShaderNodeVectorMath")
        vector_math_006.operation = 'SUBTRACT'
        #Vector_002
        vector_math_006.inputs[2].default_value = (0.0, 0.0, 0.0)
        #Scale
        vector_math_006.inputs[3].default_value = 1.0

        #node Vector Math.004
        vector_math_004 = andrew_willmotts_interior_mapping.nodes.new("ShaderNodeVectorMath")
        vector_math_004.operation = 'ABSOLUTE'
        #Vector_001
        vector_math_004.inputs[1].default_value = (0.0, 0.0, 0.0)
        #Vector_002
        vector_math_004.inputs[2].default_value = (0.0, 0.0, 0.0)
        #Scale
        vector_math_004.inputs[3].default_value = 1.0

        #node Vector Math.005
        vector_math_005 = andrew_willmotts_interior_mapping.nodes.new("ShaderNodeVectorMath")
        vector_math_005.operation = 'MULTIPLY'
        #Vector_002
        vector_math_005.inputs[2].default_value = (0.0, 0.0, 0.0)
        #Scale
        vector_math_005.inputs[3].default_value = 1.0

        #node Reroute.001
        reroute_001 = andrew_willmotts_interior_mapping.nodes.new("NodeReroute")
        #node Reroute.002
        reroute_002 = andrew_willmotts_interior_mapping.nodes.new("NodeReroute")
        #node Reroute.003
        reroute_003 = andrew_willmotts_interior_mapping.nodes.new("NodeReroute")
        #node Reroute.004
        reroute_004 = andrew_willmotts_interior_mapping.nodes.new("NodeReroute")
        #node Reroute.005
        reroute_005 = andrew_willmotts_interior_mapping.nodes.new("NodeReroute")
        #node Math.004
        math_004 = andrew_willmotts_interior_mapping.nodes.new("ShaderNodeMath")
        math_004.operation = 'MINIMUM'
        #Value_002
        math_004.inputs[2].default_value = 0.5

        #node Separate XYZ.002
        separate_xyz_002 = andrew_willmotts_interior_mapping.nodes.new("ShaderNodeSeparateXYZ")

        #node Math.005
        math_005 = andrew_willmotts_interior_mapping.nodes.new("ShaderNodeMath")
        math_005.operation = 'MINIMUM'
        #Value_002
        math_005.inputs[2].default_value = 0.5

        #node Separate XYZ.003
        separate_xyz_003 = andrew_willmotts_interior_mapping.nodes.new("ShaderNodeSeparateXYZ")

        #node Math.006
        math_006 = andrew_willmotts_interior_mapping.nodes.new("ShaderNodeMath")
        math_006.operation = 'MULTIPLY'
        #Value_001
        math_006.inputs[1].default_value = 0.5
        #Value_002
        math_006.inputs[2].default_value = 0.5

        #node Math.007
        math_007 = andrew_willmotts_interior_mapping.nodes.new("ShaderNodeMath")
        math_007.operation = 'ADD'
        #Value_001
        math_007.inputs[1].default_value = 0.5
        #Value_002
        math_007.inputs[2].default_value = 0.5

        #node Clamp
        clamp = andrew_willmotts_interior_mapping.nodes.new("ShaderNodeClamp")
        clamp.clamp_type = 'MINMAX'
        #Min
        clamp.inputs[1].default_value = 0.0
        #Max
        clamp.inputs[2].default_value = 1.0

        #node Math.008
        math_008 = andrew_willmotts_interior_mapping.nodes.new("ShaderNodeMath")
        math_008.operation = 'DIVIDE'
        #Value_002
        math_008.inputs[2].default_value = 0.5

        #node Math.009
        math_009 = andrew_willmotts_interior_mapping.nodes.new("ShaderNodeMath")
        math_009.operation = 'ADD'
        #Value_001
        math_009.inputs[1].default_value = 1.0
        #Value_002
        math_009.inputs[2].default_value = 0.5

        #node Math.010
        math_010 = andrew_willmotts_interior_mapping.nodes.new("ShaderNodeMath")
        math_010.operation = 'DIVIDE'
        #Value
        math_010.inputs[0].default_value = 1.0
        #Value_002
        math_010.inputs[2].default_value = 0.5

        #node Math.011
        math_011 = andrew_willmotts_interior_mapping.nodes.new("ShaderNodeMath")
        math_011.operation = 'SUBTRACT'
        #Value
        math_011.inputs[0].default_value = 1.0
        #Value_002
        math_011.inputs[2].default_value = 0.5

        #node Math.013
        math_013 = andrew_willmotts_interior_mapping.nodes.new("ShaderNodeMath")
        math_013.operation = 'MULTIPLY'
        #Value_002
        math_013.inputs[2].default_value = 0.5

        #node Math.012
        math_012 = andrew_willmotts_interior_mapping.nodes.new("ShaderNodeMath")
        math_012.operation = 'ADD'
        #Value_001
        math_012.inputs[1].default_value = 1.0
        #Value_002
        math_012.inputs[2].default_value = 0.5

        #node Vector Math.007
        vector_math_007 = andrew_willmotts_interior_mapping.nodes.new("ShaderNodeVectorMath")
        vector_math_007.operation = 'SCALE'
        #Vector_001
        vector_math_007.inputs[1].default_value = (0.0, 0.0, 0.0)
        #Vector_002
        vector_math_007.inputs[2].default_value = (0.0, 0.0, 0.0)

        #node Vector Math.008
        vector_math_008 = andrew_willmotts_interior_mapping.nodes.new("ShaderNodeVectorMath")
        vector_math_008.operation = 'ADD'
        #Vector_002
        vector_math_008.inputs[2].default_value = (0.0, 0.0, 0.0)
        #Scale
        vector_math_008.inputs[3].default_value = 1.0

        #node Reroute.010
        reroute_010 = andrew_willmotts_interior_mapping.nodes.new("NodeReroute")
        #node Mix
        mix = andrew_willmotts_interior_mapping.nodes.new("ShaderNodeMix")
        mix.data_type = 'VECTOR'
        mix.clamp_factor = True
        mix.factor_mode = 'UNIFORM'
        mix.blend_type = 'MIX'
        #Factor_Vector
        mix.inputs[1].default_value = (0.5, 0.5, 0.5)
        #A_Float
        mix.inputs[2].default_value = 0.0
        #B_Float
        mix.inputs[3].default_value = 0.0
        #A_Vector
        mix.inputs[4].default_value = (1.0, 1.0, 1.0)
        #A_Color
        mix.inputs[6].default_value = (0.5, 0.5, 0.5, 1.0)
        #B_Color
        mix.inputs[7].default_value = (0.5, 0.5, 0.5, 1.0)

        #node Vector Math.009
        vector_math_009 = andrew_willmotts_interior_mapping.nodes.new("ShaderNodeVectorMath")
        vector_math_009.operation = 'MULTIPLY'
        #Vector_002
        vector_math_009.inputs[2].default_value = (0.0, 0.0, 0.0)
        #Scale
        vector_math_009.inputs[3].default_value = 1.0

        #node Group Output
        group_output = andrew_willmotts_interior_mapping.nodes.new("NodeGroupOutput")
        #andrew_willmott_s_plane_interior_mapping_1 outputs
        #output Vector
        vers=bpy.app.version
        if vers[0]<4:
            andrew_willmotts_interior_mapping.outputs.new('NodeSocketVector', "Vector")
            andrew_willmotts_interior_mapping.outputs[0].default_value = (0.0, 0.0, 0.0)
            andrew_willmotts_interior_mapping.outputs[0].min_value = -3.4028234663852886e+38
            andrew_willmotts_interior_mapping.outputs[0].max_value = 3.4028234663852886e+38
            andrew_willmotts_interior_mapping.outputs[0].attribute_domain = 'POINT'
        else:
            output0 = andrew_willmotts_interior_mapping.interface.new_socket(name= "Vector", socket_type='NodeSocketVector', in_out='OUTPUT')
            output0.default_value = (0.0, 0.0, 0.0)
            output0.min_value = -3.4028234663852886e+38
            output0.max_value = 3.4028234663852886e+38
            output0.attribute_domain = 'POINT'



        #node Separate XYZ.004
        separate_xyz_004 = andrew_willmotts_interior_mapping.nodes.new("ShaderNodeSeparateXYZ")

        #node Vector Math.010
        vector_math_010 = andrew_willmotts_interior_mapping.nodes.new("ShaderNodeVectorMath")
        vector_math_010.operation = 'MULTIPLY'
        #Vector_002
        vector_math_010.inputs[2].default_value = (0.0, 0.0, 0.0)
        #Scale
        vector_math_010.inputs[3].default_value = 1.0

        #node Vector Math.011
        vector_math_011 = andrew_willmotts_interior_mapping.nodes.new("ShaderNodeVectorMath")
        vector_math_011.operation = 'ADD'
        #Vector_001
        vector_math_011.inputs[1].default_value = (0.5, 0.0, 0.5)
        #Vector_002
        vector_math_011.inputs[2].default_value = (0.0, 0.0, 0.0)
        #Scale
        vector_math_011.inputs[3].default_value = 1.0

        #node Combine XYZ.002
        combine_xyz_002 = andrew_willmotts_interior_mapping.nodes.new("ShaderNodeCombineXYZ")
        #Z
        combine_xyz_002.inputs[2].default_value = 0.0

        #node Mix.002
        mix_002 = andrew_willmotts_interior_mapping.nodes.new("ShaderNodeMix")
        mix_002.data_type = 'FLOAT'
        mix_002.clamp_factor = True
        mix_002.factor_mode = 'UNIFORM'
        mix_002.blend_type = 'MIX'
        #Factor_Vector
        mix_002.inputs[1].default_value = (0.5, 0.5, 0.5)
        #A_Float
        mix_002.inputs[2].default_value = -0.5
        #B_Float
        mix_002.inputs[3].default_value = 0.5
        #A_Vector
        mix_002.inputs[4].default_value = (0.0, 0.0, 0.0)
        #B_Vector
        mix_002.inputs[5].default_value = (0.0, 0.0, 0.0)
        #A_Color
        mix_002.inputs[6].default_value = (0.5, 0.5, 0.5, 1.0)
        #B_Color
        mix_002.inputs[7].default_value = (0.5, 0.5, 0.5, 1.0)

        #node Mix.001
        mix_001 = andrew_willmotts_interior_mapping.nodes.new("ShaderNodeMix")
        mix_001.data_type = 'FLOAT'
        mix_001.clamp_factor = True
        mix_001.factor_mode = 'UNIFORM'
        mix_001.blend_type = 'MIX'
        #Factor_Vector
        mix_001.inputs[1].default_value = (0.5, 0.5, 0.5)
        #A_Float
        mix_001.inputs[2].default_value = -0.5
        #B_Float
        mix_001.inputs[3].default_value = 0.5
        #A_Vector
        mix_001.inputs[4].default_value = (0.0, 0.0, 0.0)
        #B_Vector
        mix_001.inputs[5].default_value = (0.0, 0.0, 0.0)
        #A_Color
        mix_001.inputs[6].default_value = (0.5, 0.5, 0.5, 1.0)
        #B_Color
        mix_001.inputs[7].default_value = (0.5, 0.5, 0.5, 1.0)

        #node Combine XYZ.003
        combine_xyz_003 = andrew_willmotts_interior_mapping.nodes.new("ShaderNodeCombineXYZ")
        combine_xyz_003.inputs[1].hide = True
        #Y
        combine_xyz_003.inputs[1].default_value = 0.0

        #node Combine XYZ.001
        combine_xyz_001 = andrew_willmotts_interior_mapping.nodes.new("ShaderNodeCombineXYZ")

        #node Separate XYZ
        separate_xyz = andrew_willmotts_interior_mapping.nodes.new("ShaderNodeSeparateXYZ")

        #node Reroute.007
        reroute_007 = andrew_willmotts_interior_mapping.nodes.new("NodeReroute")
        #node Reroute.009
        reroute_009 = andrew_willmotts_interior_mapping.nodes.new("NodeReroute")
        #node Math.002
        math_002 = andrew_willmotts_interior_mapping.nodes.new("ShaderNodeMath")
        math_002.operation = 'SUBTRACT'
        #Value_001
        math_002.inputs[1].default_value = 1.0
        #Value_002
        math_002.inputs[2].default_value = 0.5

        #node Math.001
        math_001 = andrew_willmotts_interior_mapping.nodes.new("ShaderNodeMath")
        math_001.operation = 'DIVIDE'
        #Value
        math_001.inputs[0].default_value = 1.0
        #Value_002
        math_001.inputs[2].default_value = 0.5

        #node Reroute.006
        reroute_006 = andrew_willmotts_interior_mapping.nodes.new("NodeReroute")
        #node Reroute.008
        reroute_008 = andrew_willmotts_interior_mapping.nodes.new("NodeReroute")
        #node Group Input
        group_input = andrew_willmotts_interior_mapping.nodes.new("NodeGroupInput")
        #andrew_willmott_s_plane_interior_mapping_1 inputs

        # Setup all the inputs (will need B4 proofing)
        vers=bpy.app.version
        if vers[0]<4:
            andrew_willmotts_interior_mapping.inputs.new('NodeSocketVector', "UVs")
            andrew_willmotts_interior_mapping.inputs.new('NodeSocketFloat', "Interior Depth")
            andrew_willmotts_interior_mapping.inputs.new('NodeSocketFloat', "Flip X UVs?")
            andrew_willmotts_interior_mapping.inputs.new('NodeSocketFloat', "Flip Y UVs?")
            andrew_willmotts_interior_mapping.inputs.new('NodeSocketFloat', "Aspect Ratio")
            andrew_willmotts_interior_mapping_inputs=andrew_willmotts_interior_mapping.inputs
        else:
            andrew_willmotts_interior_mapping.interface.new_socket(name="UVs", socket_type='NodeSocketVector', in_out='INPUT')
            andrew_willmotts_interior_mapping.interface.new_socket(name="Interior Depth", socket_type='NodeSocketFloat', in_out='INPUT')
            andrew_willmotts_interior_mapping.interface.new_socket(name="Flip X UVs?", socket_type='NodeSocketFloat', in_out='INPUT')
            andrew_willmotts_interior_mapping.interface.new_socket(name="Flip Y UVs?", socket_type='NodeSocketFloat', in_out='INPUT')
            andrew_willmotts_interior_mapping.interface.new_socket(name="Aspect Ratio", socket_type='NodeSocketFloat', in_out='INPUT')
            andrew_willmotts_interior_mapping_inputs=get_inputs(andrew_willmotts_interior_mapping)


        #input UVs
        andrew_willmotts_interior_mapping_inputs[0].default_value = (0.0, 0.0, 0.0)
        andrew_willmotts_interior_mapping_inputs[0].min_value = -3.4028234663852886e+38
        andrew_willmotts_interior_mapping_inputs[0].max_value = 3.4028234663852886e+38
        andrew_willmotts_interior_mapping_inputs[0].attribute_domain = 'POINT'
        andrew_willmotts_interior_mapping_inputs[0].hide_value = True

        #input Interior Depth
        andrew_willmotts_interior_mapping_inputs[1].default_value = 0.5
        andrew_willmotts_interior_mapping_inputs[1].min_value = 0.009999999776482582
        andrew_willmotts_interior_mapping_inputs[1].max_value = 0.9990000128746033
        andrew_willmotts_interior_mapping_inputs[1].attribute_domain = 'POINT'

        #input Flip X UVs?
        andrew_willmotts_interior_mapping_inputs[2].default_value = 0.0
        andrew_willmotts_interior_mapping_inputs[2].min_value = 0.0
        andrew_willmotts_interior_mapping_inputs[2].max_value = 1.0
        andrew_willmotts_interior_mapping_inputs[2].attribute_domain = 'POINT'

        #input Flip Y UVs?
        andrew_willmotts_interior_mapping_inputs[3].default_value = 0.0
        andrew_willmotts_interior_mapping_inputs[3].min_value = 0.0
        andrew_willmotts_interior_mapping_inputs[3].max_value = 1.0
        andrew_willmotts_interior_mapping_inputs[3].attribute_domain = 'POINT'
 
        #Aspect Ratio
        andrew_willmotts_interior_mapping_inputs[4].default_value = 1.0
        andrew_willmotts_interior_mapping_inputs[4].min_value = 1.0
        andrew_willmotts_interior_mapping_inputs[4].max_value = 10.0
        andrew_willmotts_interior_mapping_inputs[4].attribute_domain = 'POINT'


        #node Group Input.001
        group_input_001 = andrew_willmotts_interior_mapping.nodes.new("NodeGroupInput")
        group_input_001.outputs[1].hide = True
        group_input_001.outputs[2].hide = True
        group_input_001.outputs[3].hide = True
        group_input_001.outputs[4].hide = True

        #node Vector Math.002
        vector_math_002 = andrew_willmotts_interior_mapping.nodes.new("ShaderNodeVectorMath")
        vector_math_002.operation = 'SUBTRACT'
        #Vector_002
        vector_math_002.inputs[2].default_value = (0.0, 0.0, 0.0)
        #Scale
        vector_math_002.inputs[3].default_value = 1.0

        #node Vector Math
        vector_math = andrew_willmotts_interior_mapping.nodes.new("ShaderNodeVectorMath")
        vector_math.operation = 'MULTIPLY'
        #Vector_002
        vector_math.inputs[2].default_value = (0.0, 0.0, 0.0)
        #Scale
        vector_math.inputs[3].default_value = 1.0

        #node Group Input.002
        group_input_002 = andrew_willmotts_interior_mapping.nodes.new("NodeGroupInput")
        group_input_002.outputs[0].hide = True
        group_input_002.outputs[1].hide = True
        group_input_002.outputs[4].hide = True

        #node Math.014
        math_014 = andrew_willmotts_interior_mapping.nodes.new("ShaderNodeMath")
        math_014.operation = 'GREATER_THAN'
        #Value_001
        math_014.inputs[1].default_value = 0.5
        #Value_002
        math_014.inputs[2].default_value = 0.5

        #node Vector Math.014
        vector_math_014 = andrew_willmotts_interior_mapping.nodes.new("ShaderNodeVectorMath")
        vector_math_014.operation = 'DOT_PRODUCT'
        #Vector_002
        vector_math_014.inputs[2].default_value = (0.0, 0.0, 0.0)
        #Scale
        vector_math_014.inputs[3].default_value = 1.0

        #node Vector Math.015
        vector_math_015 = andrew_willmotts_interior_mapping.nodes.new("ShaderNodeVectorMath")
        vector_math_015.operation = 'DOT_PRODUCT'
        #Vector_002
        vector_math_015.inputs[2].default_value = (0.0, 0.0, 0.0)
        #Scale
        vector_math_015.inputs[3].default_value = 1.0

        #node Combine XYZ.004
        combine_xyz_004 = andrew_willmotts_interior_mapping.nodes.new("ShaderNodeCombineXYZ")

        #node Vector Math.012
        vector_math_012 = andrew_willmotts_interior_mapping.nodes.new("ShaderNodeVectorMath")
        vector_math_012.operation = 'DOT_PRODUCT'
        #Vector_002
        vector_math_012.inputs[2].default_value = (0.0, 0.0, 0.0)
        #Scale
        vector_math_012.inputs[3].default_value = 1.0

        #node Reroute.013
        reroute_013 = andrew_willmotts_interior_mapping.nodes.new("NodeReroute")
        #node Reroute.014
        reroute_014 = andrew_willmotts_interior_mapping.nodes.new("NodeReroute")
        #node Vector Math.013
        vector_math_013 = andrew_willmotts_interior_mapping.nodes.new("ShaderNodeVectorMath")
        vector_math_013.operation = 'CROSS_PRODUCT'
        #Vector_002
        vector_math_013.inputs[2].default_value = (0.0, 0.0, 0.0)
        #Scale
        vector_math_013.inputs[3].default_value = 1.0

        #node Geometry
        geometry = andrew_willmotts_interior_mapping.nodes.new("ShaderNodeNewGeometry")
        geometry.outputs[0].hide = True
        geometry.outputs[2].hide = True
        geometry.outputs[3].hide = True
        geometry.outputs[4].hide = True
        geometry.outputs[5].hide = True
        geometry.outputs[6].hide = True
        geometry.outputs[7].hide = True
        geometry.outputs[8].hide = True

        #node Geometry.001
        geometry_001 = andrew_willmotts_interior_mapping.nodes.new("ShaderNodeNewGeometry")
        geometry_001.outputs[0].hide = True
        geometry_001.outputs[1].hide = True
        geometry_001.outputs[2].hide = True
        geometry_001.outputs[3].hide = True
        geometry_001.outputs[5].hide = True
        geometry_001.outputs[6].hide = True
        geometry_001.outputs[7].hide = True
        geometry_001.outputs[8].hide = True

        #node Vector Math.001
        vector_math_001 = andrew_willmotts_interior_mapping.nodes.new("ShaderNodeVectorMath")
        vector_math_001.operation = 'MULTIPLY'
        #Vector_001
        vector_math_001.inputs[1].default_value = (-1.0, -1.0, -1.0)
        #Vector_002
        vector_math_001.inputs[2].default_value = (0.0, 0.0, 0.0)
        #Scale
        vector_math_001.inputs[3].default_value = 1.0

        #node Math.015
        math_015 = andrew_willmotts_interior_mapping.nodes.new("ShaderNodeMath")
        math_015.operation = 'GREATER_THAN'
        #Value_001
        math_015.inputs[1].default_value = 0.5
        #Value_002
        math_015.inputs[2].default_value = 0.5

        #node Reroute.015
        reroute_015 = andrew_willmotts_interior_mapping.nodes.new("NodeReroute")
        #node Tangent
        tangent = andrew_willmotts_interior_mapping.nodes.new("ShaderNodeTangent")
        tangent.direction_type = 'UV_MAP'
        tangent.axis = 'Y'

        #node Vector Math.016
        vector_math_016 = andrew_willmotts_interior_mapping.nodes.new("ShaderNodeVectorMath")
        vector_math_016.operation = 'MULTIPLY'
        #Vector_001
        vector_math_016.inputs[1].default_value = (-1.0, -1.0, 1.0)
        #Vector_002
        vector_math_016.inputs[2].default_value = (0.0, 0.0, 0.0)
        #Scale
        vector_math_016.inputs[3].default_value = 1.0

        #node Combine XYZ.005
        combine_xyz_005 = andrew_willmotts_interior_mapping.nodes.new("ShaderNodeCombineXYZ")

        #node Separate XYZ.005
        separate_xyz_005 = andrew_willmotts_interior_mapping.nodes.new("ShaderNodeSeparateXYZ")

        #node Mix.003
        mix_003 = andrew_willmotts_interior_mapping.nodes.new("ShaderNodeMix")
        mix_003.data_type = 'VECTOR'
        mix_003.clamp_factor = True
        mix_003.factor_mode = 'UNIFORM'
        mix_003.blend_type = 'MIX'
        #Factor_Vector
        mix_003.inputs[1].default_value = (0.5, 0.5, 0.5)
        #A_Float
        mix_003.inputs[2].default_value = 0.0
        #B_Float
        mix_003.inputs[3].default_value = 0.0
        #A_Vector
        mix_003.inputs[4].default_value = (2.0, 2.0, 0.0)
        #B_Vector
        mix_003.inputs[5].default_value = (-2.0, -2.0, 0.0)
        #A_Color
        mix_003.inputs[6].default_value = (0.5, 0.5, 0.5, 1.0)
        #B_Color
        mix_003.inputs[7].default_value = (0.5, 0.5, 0.5, 1.0)

        #node Reroute.011
        reroute_011 = andrew_willmotts_interior_mapping.nodes.new("NodeReroute")
        #node Mix.004
        mix_004 = andrew_willmotts_interior_mapping.nodes.new("ShaderNodeMix")
        mix_004.data_type = 'VECTOR'
        mix_004.clamp_factor = True
        mix_004.factor_mode = 'UNIFORM'
        mix_004.blend_type = 'MIX'
        #Factor_Vector
        mix_004.inputs[1].default_value = (0.5, 0.5, 0.5)
        #A_Float
        mix_004.inputs[2].default_value = 0.0
        #B_Float
        mix_004.inputs[3].default_value = 0.0
        #A_Vector
        mix_004.inputs[4].default_value = (1.0, 1.0, 1.0)
        #B_Vector
        mix_004.inputs[5].default_value = (-1.0, -1.0, 1.0)
        #A_Color
        mix_004.inputs[6].default_value = (0.5, 0.5, 0.5, 1.0)
        #B_Color
        mix_004.inputs[7].default_value = (0.5, 0.5, 0.5, 1.0)

        #node Value
        value = andrew_willmotts_interior_mapping.nodes.new("ShaderNodeValue")

        value.outputs[0].default_value = 1.0
        #Set parents
        math_003.parent = frame_002
        math.parent = frame_002
        separate_xyz_001.parent = frame_002
        combine_xyz.parent = frame_002
        vector_math_003.parent = frame_003
        vector_math_006.parent = frame_004
        vector_math_004.parent = frame_004
        vector_math_005.parent = frame_004
        math_004.parent = frame_005
        separate_xyz_002.parent = frame_005
        math_005.parent = frame_005
        separate_xyz_003.parent = frame_008
        math_006.parent = frame_008
        math_007.parent = frame_008
        clamp.parent = frame_009
        math_008.parent = frame_009
        math_009.parent = frame_009
        math_010.parent = frame_010
        math_011.parent = frame_010
        vector_math_007.parent = frame_006
        vector_math_008.parent = frame_006
        combine_xyz_001.parent = frame_007
        separate_xyz.parent = frame_007
        math_002.parent = frame
        math_001.parent = frame
        vector_math_002.parent = frame_007
        vector_math.parent = frame_007
        vector_math_014.parent = frame_001
        vector_math_015.parent = frame_001
        combine_xyz_004.parent = frame_001
        vector_math_012.parent = frame_001
        reroute_013.parent = frame_001
        reroute_014.parent = frame_001
        vector_math_013.parent = frame_001
        geometry.parent = frame_001
        geometry_001.parent = frame_001
        vector_math_001.parent = frame_001
        reroute_015.parent = frame_001
        tangent.parent = frame_001
        vector_math_016.parent = frame_011
        combine_xyz_005.parent = frame_011
        separate_xyz_005.parent = frame_011
        mix_003.parent = frame_012
        reroute_011.parent = frame_012
        mix_004.parent = frame_012
        value.parent = frame_012

        #Set locations
        frame_002.location = (-11393.62109375, -1201.529541015625)
        frame_003.location = (-11264.2392578125, -1225.83056640625)
        frame_004.location = (-11393.62109375, -1201.529541015625)
        frame_005.location = (-11367.3291015625, -1219.5499267578125)
        frame_008.location = (-11393.62109375, -1201.529541015625)
        frame_009.location = (-11393.62109375, -1201.529541015625)
        frame_010.location = (-11393.62109375, -1201.529541015625)
        frame_006.location = (-11393.62109375, -1201.529541015625)
        frame_007.location = (-11393.62109375, -1001.5250244140625)
        frame.location = (-11105.8134765625, -1332.7579345703125)
        frame_001.location = (-11831.931640625, -1229.248779296875)
        frame_011.location = (0.0, 0.0)
        frame_012.location = (0.0, -1.38714599609375)
        math_003.location = (8574.9775390625, 1171.7548828125)
        math.location = (8783.359375, 1229.8702392578125)
        separate_xyz_001.location = (8575.033203125, 1334.010009765625)
        combine_xyz.location = (8973.759765625, 1298.9278564453125)
        reroute.location = (-1713.4150390625, 44.1063232421875)
        vector_math_003.location = (9193.599609375, 1308.735107421875)
        vector_math_006.location = (10135.2001953125, 1416.254638671875)
        vector_math_004.location = (9790.6611328125, 1255.9691162109375)
        vector_math_005.location = (9880.3115234375, 1466.1571044921875)
        reroute_001.location = (-2192.517578125, 10.7388916015625)
        reroute_002.location = (-373.6357421875, -196.30218505859375)
        reroute_003.location = (-2166.0283203125, -209.01715087890625)
        reroute_004.location = (-1917.9296875, 400.9151611328125)
        reroute_005.location = (-161.7451171875, 396.257568359375)
        math_004.location = (10576.0, 1422.6353759765625)
        separate_xyz_002.location = (10356.0, 1412.2216796875)
        math_005.location = (10796.0, 1409.5887451171875)
        separate_xyz_003.location = (11482.4521484375, 1501.727294921875)
        math_006.location = (11702.3994140625, 1475.6136474609375)
        math_007.location = (11922.400390625, 1475.6136474609375)
        clamp.location = (12215.771484375, 1488.0423583984375)
        math_008.location = (12436.0, 1495.1593017578125)
        math_009.location = (12656.0, 1487.465087890625)
        math_010.location = (12933.208984375, 1488.746337890625)
        math_011.location = (13165.6064453125, 1482.667236328125)
        math_013.location = (2192.52734375, 296.69189453125)
        math_012.location = (1979.8896484375, 176.511962890625)
        vector_math_007.location = (11042.3994140625, 1479.315673828125)
        vector_math_008.location = (11257.546875, 1516.578125)
        reroute_010.location = (54.3662109375, 404.9371337890625)
        mix.location = (2412.7783203125, 293.8433837890625)
        vector_math_009.location = (2687.64453125, 435.5938720703125)
        group_output.location = (4049.490234375, 0.0)
        separate_xyz_004.location = (3639.490234375, 414.7901306152344)
        vector_math_010.location = (3199.84765625, 448.85693359375)
        vector_math_011.location = (3419.848388671875, 448.85693359375)
        combine_xyz_002.location = (3859.490234375, 403.3603515625)
        mix_002.location = (2819.64111328125, 64.2289810180664)
        mix_001.location = (2819.64111328125, 268.3122863769531)
        combine_xyz_003.location = (3006.78271484375, 267.7255859375)
        combine_xyz_001.location = (8737.0732421875, 1606.0089111328125)
        separate_xyz.location = (8538.48828125, 1608.077392578125)
        reroute_007.location = (793.5604248046875, -392.9407653808594)
        reroute_009.location = (2260.431396484375, -472.222412109375)
        math_002.location = (7958.23828125, 984.9021606445312)
        math_001.location = (7782.41943359375, 989.8995361328125)
        reroute_006.location = (-2921.240478515625, -379.2322692871094)
        reroute_008.location = (-3383.895751953125, -563.2879638671875)
        group_input.location = (-3627.66650390625, -565.7387084960938)
        group_input_001.location = (-3796.53759765625, 493.26141357421875)
        vector_math_002.location = (8312.9267578125, 1608.318359375)
        vector_math.location = (8112.23681640625, 1607.3035888671875)
        group_input_002.location = (2414.422607421875, -83.7418441772461)
        math_014.location = (2614.357177734375, 123.44041442871094)
        vector_math_014.location = (7806.4404296875, 1205.86474609375)
        vector_math_015.location = (7806.4404296875, 1033.2490234375)
        combine_xyz_004.location = (8095.3212890625, 1268.3214111328125)
        vector_math_012.location = (7806.4404296875, 1359.8096923828125)
        reroute_013.location = (7447.8857421875, 1079.459228515625)
        reroute_014.location = (7457.41650390625, 922.1935424804688)
        vector_math_013.location = (7480.9130859375, 1068.6666259765625)
        geometry.location = (7265.09228515625, 1091.4346923828125)
        geometry_001.location = (7259.7470703125, 1289.0223388671875)
        vector_math_001.location = (7483.14453125, 1345.4296875)
        math_015.location = (2614.357177734375, -56.195213317871094)
        reroute_015.location = (7706.7568359375, 1118.2265625)
        tangent.location = (7256.7001953125, 1202.63916015625)
        vector_math_016.location = (-3479.577392578125, 60.647430419921875)
        combine_xyz_005.location = (-3044.70166015625, 27.672286987304688)
        separate_xyz_005.location = (-3249.80126953125, 18.78656005859375)
        mix_003.location = (-3522.47314453125, 369.51898193359375)
        reroute_011.location = (-3571.09228515625, 319.0013122558594)
        mix_004.location = (-3413.041748046875, 292.8710021972656)
        value.location = (-3798.04052734375, 350.9649353027344)

        #Set dimensions
        frame_002.width, frame_002.height = 598.400390625, 384.4000244140625
        frame_003.width, frame_003.height = 318.060546875, 259.5999755859375
        frame_004.width, frame_004.height = 544.7998046875, 388.4000244140625
        frame_005.width, frame_005.height = 640.0, 236.39990234375
        frame_008.width, frame_008.height = 640.0, 249.199951171875
        frame_009.width, frame_009.height = 640.0, 231.5999755859375
        frame_010.width, frame_010.height = 432.7998046875, 230.0
        frame_006.width, frame_006.height = 420.052734375, 236.39990234375
        frame_007.width, frame_007.height = 824.80029296875, 202.0
        frame.width, frame.height = 376.0, 226.7999267578125
        frame_001.width, frame_001.height = 1038.400390625, 523.6000366210938
        frame_011.width, frame_011.height = 634.39990234375, 259.6000061035156
        frame_012.width, frame_012.height = 585.599853515625, 176.8000030517578
        math_003.width, math_003.height = 140.0, 100.0
        math.width, math.height = 140.0, 100.0
        separate_xyz_001.width, separate_xyz_001.height = 140.0, 100.0
        combine_xyz.width, combine_xyz.height = 140.0, 100.0
        reroute.width, reroute.height = 16.0, 100.0
        vector_math_003.width, vector_math_003.height = 258.0609436035156, 100.0
        vector_math_006.width, vector_math_006.height = 140.0, 100.0
        vector_math_004.width, vector_math_004.height = 258.0609436035156, 100.0
        vector_math_005.width, vector_math_005.height = 140.0, 100.0
        reroute_001.width, reroute_001.height = 16.0, 100.0
        reroute_002.width, reroute_002.height = 16.0, 100.0
        reroute_003.width, reroute_003.height = 16.0, 100.0
        reroute_004.width, reroute_004.height = 16.0, 100.0
        reroute_005.width, reroute_005.height = 16.0, 100.0
        math_004.width, math_004.height = 140.0, 100.0
        separate_xyz_002.width, separate_xyz_002.height = 140.0, 100.0
        math_005.width, math_005.height = 140.0, 100.0
        separate_xyz_003.width, separate_xyz_003.height = 140.0, 100.0
        math_006.width, math_006.height = 140.0, 100.0
        math_007.width, math_007.height = 140.0, 100.0
        clamp.width, clamp.height = 140.0, 100.0
        math_008.width, math_008.height = 140.0, 100.0
        math_009.width, math_009.height = 140.0, 100.0
        math_010.width, math_010.height = 140.0, 100.0
        math_011.width, math_011.height = 140.0, 100.0
        math_013.width, math_013.height = 140.0, 100.0
        math_012.width, math_012.height = 140.0, 100.0
        vector_math_007.width, vector_math_007.height = 140.0, 100.0
        vector_math_008.width, vector_math_008.height = 144.8525390625, 100.0
        reroute_010.width, reroute_010.height = 16.0, 100.0
        mix.width, mix.height = 140.0, 100.0
        vector_math_009.width, vector_math_009.height = 140.0, 100.0
        group_output.width, group_output.height = 140.0, 100.0
        separate_xyz_004.width, separate_xyz_004.height = 140.0, 100.0
        vector_math_010.width, vector_math_010.height = 140.0, 100.0
        vector_math_011.width, vector_math_011.height = 140.0, 100.0
        combine_xyz_002.width, combine_xyz_002.height = 140.0, 100.0
        mix_002.width, mix_002.height = 140.0, 100.0
        mix_001.width, mix_001.height = 140.0, 100.0
        combine_xyz_003.width, combine_xyz_003.height = 140.0, 100.0
        combine_xyz_001.width, combine_xyz_001.height = 140.0, 100.0
        separate_xyz.width, separate_xyz.height = 140.0, 100.0
        reroute_007.width, reroute_007.height = 16.0, 100.0
        reroute_009.width, reroute_009.height = 16.0, 100.0
        math_002.width, math_002.height = 140.0, 100.0
        math_001.width, math_001.height = 140.0, 100.0
        reroute_006.width, reroute_006.height = 16.0, 100.0
        reroute_008.width, reroute_008.height = 16.0, 100.0
        group_input.width, group_input.height = 140.0, 100.0
        group_input_001.width, group_input_001.height = 140.0, 100.0
        vector_math_002.width, vector_math_002.height = 140.0, 100.0
        vector_math.width, vector_math.height = 140.0, 100.0
        group_input_002.width, group_input_002.height = 140.0, 100.0
        math_014.width, math_014.height = 140.0, 100.0
        vector_math_014.width, vector_math_014.height = 140.0, 100.0
        vector_math_015.width, vector_math_015.height = 140.0, 100.0
        combine_xyz_004.width, combine_xyz_004.height = 140.0, 100.0
        vector_math_012.width, vector_math_012.height = 140.0, 100.0
        reroute_013.width, reroute_013.height = 16.0, 100.0
        reroute_014.width, reroute_014.height = 16.0, 100.0
        vector_math_013.width, vector_math_013.height = 140.0, 100.0
        geometry.width, geometry.height = 140.0, 100.0
        geometry_001.width, geometry_001.height = 140.0, 100.0
        vector_math_001.width, vector_math_001.height = 140.0, 100.0
        math_015.width, math_015.height = 140.0, 100.0
        reroute_015.width, reroute_015.height = 16.0, 100.0
        tangent.width, tangent.height = 150.0, 100.0
        vector_math_016.width, vector_math_016.height = 140.0, 100.0
        combine_xyz_005.width, combine_xyz_005.height = 140.0, 100.0
        separate_xyz_005.width, separate_xyz_005.height = 140.0, 100.0
        mix_003.width, mix_003.height = 140.0, 100.0
        reroute_011.width, reroute_011.height = 16.0, 100.0
        mix_004.width, mix_004.height = 140.0, 100.0
        value.width, value.height = 140.0, 100.0

        #initialize andrew_willmott_s_plane_interior_mapping_1 links
        #math_008.Value -> math_009.Value
        andrew_willmotts_interior_mapping.links.new(math_008.outputs[0], math_009.inputs[0])
        #reroute_004.Output -> vector_math_005.Vector
        andrew_willmotts_interior_mapping.links.new(reroute_004.outputs[0], vector_math_005.inputs[0])
        #separate_xyz.Z -> combine_xyz_001.Y
        andrew_willmotts_interior_mapping.links.new(separate_xyz.outputs[2], combine_xyz_001.inputs[1])
        #reroute_002.Output -> vector_math_007.Vector
        andrew_willmotts_interior_mapping.links.new(reroute_002.outputs[0], vector_math_007.inputs[0])
        #math_005.Value -> vector_math_007.Scale
        andrew_willmotts_interior_mapping.links.new(math_005.outputs[0], vector_math_007.inputs[3])
        #reroute.Output -> vector_math_004.Vector
        andrew_willmotts_interior_mapping.links.new(reroute.outputs[0], vector_math_004.inputs[0])
        #vector_math_006.Vector -> separate_xyz_002.Vector
        andrew_willmotts_interior_mapping.links.new(vector_math_006.outputs[0], separate_xyz_002.inputs[0])
        #math_004.Value -> math_005.Value
        andrew_willmotts_interior_mapping.links.new(math_004.outputs[0], math_005.inputs[0])
        #reroute_004.Output -> reroute_005.Input
        andrew_willmotts_interior_mapping.links.new(reroute_004.outputs[0], reroute_005.inputs[0])
        #separate_xyz_002.Z -> math_004.Value
        andrew_willmotts_interior_mapping.links.new(separate_xyz_002.outputs[2], math_004.inputs[1])
        #separate_xyz_001.Y -> math.Value
        andrew_willmotts_interior_mapping.links.new(separate_xyz_001.outputs[1], math.inputs[0])
        #reroute_003.Output -> reroute_002.Input
        andrew_willmotts_interior_mapping.links.new(reroute_003.outputs[0], reroute_002.inputs[0])
        #math_010.Value -> math_011.Value
        andrew_willmotts_interior_mapping.links.new(math_010.outputs[0], math_011.inputs[1])
        #separate_xyz_001.X -> combine_xyz.X
        andrew_willmotts_interior_mapping.links.new(separate_xyz_001.outputs[0], combine_xyz.inputs[0])
        #reroute_009.Output -> mix.B
        andrew_willmotts_interior_mapping.links.new(reroute_009.outputs[0], mix.inputs[5])
        #separate_xyz_004.X -> combine_xyz_002.X
        andrew_willmotts_interior_mapping.links.new(separate_xyz_004.outputs[0], combine_xyz_002.inputs[0])
        #clamp.Result -> math_008.Value
        andrew_willmotts_interior_mapping.links.new(clamp.outputs[0], math_008.inputs[0])
        #separate_xyz_002.X -> math_004.Value
        andrew_willmotts_interior_mapping.links.new(separate_xyz_002.outputs[0], math_004.inputs[0])
        #separate_xyz.X -> combine_xyz_001.X
        andrew_willmotts_interior_mapping.links.new(separate_xyz.outputs[0], combine_xyz_001.inputs[0])
        #separate_xyz_001.Z -> combine_xyz.Z
        andrew_willmotts_interior_mapping.links.new(separate_xyz_001.outputs[2], combine_xyz.inputs[2])
        #math_013.Value -> mix.Factor
        andrew_willmotts_interior_mapping.links.new(math_013.outputs[0], mix.inputs[0])
        #mix.Result -> vector_math_009.Vector
        andrew_willmotts_interior_mapping.links.new(mix.outputs[1], vector_math_009.inputs[1])
        #vector_math_003.Vector -> reroute.Input
        andrew_willmotts_interior_mapping.links.new(vector_math_003.outputs[0], reroute.inputs[0])
        #vector_math_010.Vector -> vector_math_011.Vector
        andrew_willmotts_interior_mapping.links.new(vector_math_010.outputs[0], vector_math_011.inputs[0])
        #reroute_005.Output -> vector_math_008.Vector
        andrew_willmotts_interior_mapping.links.new(reroute_005.outputs[0], vector_math_008.inputs[0])
        #vector_math_002.Vector -> separate_xyz.Vector
        andrew_willmotts_interior_mapping.links.new(vector_math_002.outputs[0], separate_xyz.inputs[0])
        #separate_xyz_003.Y -> math_006.Value
        andrew_willmotts_interior_mapping.links.new(separate_xyz_003.outputs[1], math_006.inputs[0])
        #math_002.Value -> reroute_006.Input
        andrew_willmotts_interior_mapping.links.new(math_002.outputs[0], reroute_006.inputs[0])
        #vector_math_007.Vector -> vector_math_008.Vector
        andrew_willmotts_interior_mapping.links.new(vector_math_007.outputs[0], vector_math_008.inputs[1])
        #combine_xyz.Vector -> reroute_001.Input
        andrew_willmotts_interior_mapping.links.new(combine_xyz.outputs[0], reroute_001.inputs[0])
        #math_001.Value -> math_002.Value
        andrew_willmotts_interior_mapping.links.new(math_001.outputs[0], math_002.inputs[0])
        #math_009.Value -> math_010.Value
        andrew_willmotts_interior_mapping.links.new(math_009.outputs[0], math_010.inputs[1])
        #reroute_001.Output -> reroute_003.Input
        andrew_willmotts_interior_mapping.links.new(reroute_001.outputs[0], reroute_003.inputs[0])
        #separate_xyz.Y -> combine_xyz_001.Z
        andrew_willmotts_interior_mapping.links.new(separate_xyz.outputs[1], combine_xyz_001.inputs[2])
        #math.Value -> combine_xyz.Y
        andrew_willmotts_interior_mapping.links.new(math.outputs[0], combine_xyz.inputs[1])
        #reroute_001.Output -> vector_math_003.Vector
        andrew_willmotts_interior_mapping.links.new(reroute_001.outputs[0], vector_math_003.inputs[1])
        #combine_xyz_001.Vector -> reroute_004.Input
        andrew_willmotts_interior_mapping.links.new(combine_xyz_001.outputs[0], reroute_004.inputs[0])
        #reroute_010.Output -> vector_math_009.Vector
        andrew_willmotts_interior_mapping.links.new(reroute_010.outputs[0], vector_math_009.inputs[0])
        #math_006.Value -> math_007.Value
        andrew_willmotts_interior_mapping.links.new(math_006.outputs[0], math_007.inputs[0])
        #reroute_006.Output -> math_003.Value
        andrew_willmotts_interior_mapping.links.new(reroute_006.outputs[0], math_003.inputs[0])
        #math_007.Value -> clamp.Value
        andrew_willmotts_interior_mapping.links.new(math_007.outputs[0], clamp.inputs[0])
        #reroute_006.Output -> reroute_007.Input
        andrew_willmotts_interior_mapping.links.new(reroute_006.outputs[0], reroute_007.inputs[0])
        #separate_xyz_002.Y -> math_005.Value
        andrew_willmotts_interior_mapping.links.new(separate_xyz_002.outputs[1], math_005.inputs[1])
        #vector_math.Vector -> vector_math_002.Vector
        andrew_willmotts_interior_mapping.links.new(vector_math.outputs[0], vector_math_002.inputs[0])
        #reroute_008.Output -> math_001.Value
        andrew_willmotts_interior_mapping.links.new(reroute_008.outputs[0], math_001.inputs[1])
        #reroute_010.Output -> separate_xyz_003.Vector
        andrew_willmotts_interior_mapping.links.new(reroute_010.outputs[0], separate_xyz_003.inputs[0])
        #math_011.Value -> math_013.Value
        andrew_willmotts_interior_mapping.links.new(math_011.outputs[0], math_013.inputs[0])
        #vector_math_008.Vector -> reroute_010.Input
        andrew_willmotts_interior_mapping.links.new(vector_math_008.outputs[0], reroute_010.inputs[0])
        #math_003.Value -> math.Value
        andrew_willmotts_interior_mapping.links.new(math_003.outputs[0], math.inputs[1])
        #reroute.Output -> vector_math_005.Vector
        andrew_willmotts_interior_mapping.links.new(reroute.outputs[0], vector_math_005.inputs[1])
        #vector_math_004.Vector -> vector_math_006.Vector
        andrew_willmotts_interior_mapping.links.new(vector_math_004.outputs[0], vector_math_006.inputs[0])
        #vector_math_005.Vector -> vector_math_006.Vector
        andrew_willmotts_interior_mapping.links.new(vector_math_005.outputs[0], vector_math_006.inputs[1])
        #vector_math_011.Vector -> separate_xyz_004.Vector
        andrew_willmotts_interior_mapping.links.new(vector_math_011.outputs[0], separate_xyz_004.inputs[0])
        #math_012.Value -> math_013.Value
        andrew_willmotts_interior_mapping.links.new(math_012.outputs[0], math_013.inputs[1])
        #reroute_007.Output -> math_008.Value
        andrew_willmotts_interior_mapping.links.new(reroute_007.outputs[0], math_008.inputs[1])
        #separate_xyz_004.Z -> combine_xyz_002.Y
        andrew_willmotts_interior_mapping.links.new(separate_xyz_004.outputs[2], combine_xyz_002.inputs[1])
        #reroute_008.Output -> reroute_009.Input
        andrew_willmotts_interior_mapping.links.new(reroute_008.outputs[0], reroute_009.inputs[0])
        #vector_math_009.Vector -> vector_math_010.Vector
        andrew_willmotts_interior_mapping.links.new(vector_math_009.outputs[0], vector_math_010.inputs[0])
        #reroute_007.Output -> math_012.Value
        andrew_willmotts_interior_mapping.links.new(reroute_007.outputs[0], math_012.inputs[0])
        #combine_xyz_002.Vector -> group_output.Vector
        andrew_willmotts_interior_mapping.links.new(combine_xyz_002.outputs[0], group_output.inputs[0])
        #group_input.Interior Depth -> reroute_008.Input
        andrew_willmotts_interior_mapping.links.new(group_input.outputs[1], reroute_008.inputs[0])
        #group_input_001.UVs -> vector_math.Vector
        andrew_willmotts_interior_mapping.links.new(group_input_001.outputs[0], vector_math.inputs[0])
        #mix_001.Result -> combine_xyz_003.X
        andrew_willmotts_interior_mapping.links.new(mix_001.outputs[0], combine_xyz_003.inputs[0])
        #math_014.Value -> mix_001.Factor
        andrew_willmotts_interior_mapping.links.new(math_014.outputs[0], mix_001.inputs[0])
        #math_015.Value -> mix_002.Factor
        andrew_willmotts_interior_mapping.links.new(math_015.outputs[0], mix_002.inputs[0])
        #combine_xyz_003.Vector -> vector_math_010.Vector
        andrew_willmotts_interior_mapping.links.new(combine_xyz_003.outputs[0], vector_math_010.inputs[1])
        #mix_002.Result -> combine_xyz_003.Z
        andrew_willmotts_interior_mapping.links.new(mix_002.outputs[0], combine_xyz_003.inputs[2])
        #reroute_011.Output -> mix_003.Factor
        andrew_willmotts_interior_mapping.links.new(reroute_011.outputs[0], mix_003.inputs[0])
        #reroute_011.Output -> mix_004.Factor
        andrew_willmotts_interior_mapping.links.new(reroute_011.outputs[0], mix_004.inputs[0])
        #reroute_015.Output -> vector_math_012.Vector
        andrew_willmotts_interior_mapping.links.new(reroute_015.outputs[0], vector_math_012.inputs[0])
        #reroute_014.Output -> vector_math_013.Vector
        andrew_willmotts_interior_mapping.links.new(reroute_014.outputs[0], vector_math_013.inputs[0])
        #reroute_013.Output -> vector_math_013.Vector
        andrew_willmotts_interior_mapping.links.new(reroute_013.outputs[0], vector_math_013.inputs[1])
        #tangent.Tangent -> reroute_013.Input
        andrew_willmotts_interior_mapping.links.new(tangent.outputs[0], reroute_013.inputs[0])
        #reroute_013.Output -> vector_math_012.Vector
        andrew_willmotts_interior_mapping.links.new(reroute_013.outputs[0], vector_math_012.inputs[1])
        #vector_math_013.Vector -> vector_math_014.Vector
        andrew_willmotts_interior_mapping.links.new(vector_math_013.outputs[0], vector_math_014.inputs[1])
        #reroute_014.Output -> vector_math_015.Vector
        andrew_willmotts_interior_mapping.links.new(reroute_014.outputs[0], vector_math_015.inputs[1])
        #vector_math_012.Value -> combine_xyz_004.X
        andrew_willmotts_interior_mapping.links.new(vector_math_012.outputs[1], combine_xyz_004.inputs[0])
        #vector_math_014.Value -> combine_xyz_004.Y
        andrew_willmotts_interior_mapping.links.new(vector_math_014.outputs[1], combine_xyz_004.inputs[1])
        #vector_math_015.Value -> combine_xyz_004.Z
        andrew_willmotts_interior_mapping.links.new(vector_math_015.outputs[1], combine_xyz_004.inputs[2])
        #mix_003.Result -> vector_math.Vector
        andrew_willmotts_interior_mapping.links.new(mix_003.outputs[1], vector_math.inputs[1])
        #mix_004.Result -> vector_math_002.Vector
        andrew_willmotts_interior_mapping.links.new(mix_004.outputs[1], vector_math_002.inputs[1])
        #value.Value -> reroute_011.Input
        andrew_willmotts_interior_mapping.links.new(value.outputs[0], reroute_011.inputs[0])
        #vector_math_001.Vector -> reroute_015.Input
        andrew_willmotts_interior_mapping.links.new(vector_math_001.outputs[0], reroute_015.inputs[0])
        #reroute_015.Output -> vector_math_014.Vector
        andrew_willmotts_interior_mapping.links.new(reroute_015.outputs[0], vector_math_014.inputs[0])
        #geometry.Normal -> reroute_014.Input
        andrew_willmotts_interior_mapping.links.new(geometry.outputs[1], reroute_014.inputs[0])
        #reroute_015.Output -> vector_math_015.Vector
        andrew_willmotts_interior_mapping.links.new(reroute_015.outputs[0], vector_math_015.inputs[0])
        #geometry_001.Incoming -> vector_math_001.Vector
        andrew_willmotts_interior_mapping.links.new(geometry_001.outputs[4], vector_math_001.inputs[0])
        #combine_xyz_004.Vector -> vector_math_016.Vector
        andrew_willmotts_interior_mapping.links.new(combine_xyz_004.outputs[0], vector_math_016.inputs[0])
        #vector_math_016.Vector -> separate_xyz_005.Vector
        andrew_willmotts_interior_mapping.links.new(vector_math_016.outputs[0], separate_xyz_005.inputs[0])
        #separate_xyz_005.X -> combine_xyz_005.X
        andrew_willmotts_interior_mapping.links.new(separate_xyz_005.outputs[0], combine_xyz_005.inputs[0])
        #separate_xyz_005.Y -> combine_xyz_005.Z
        andrew_willmotts_interior_mapping.links.new(separate_xyz_005.outputs[1], combine_xyz_005.inputs[2])
        #separate_xyz_005.Z -> combine_xyz_005.Y
        andrew_willmotts_interior_mapping.links.new(separate_xyz_005.outputs[2], combine_xyz_005.inputs[1])
        #combine_xyz_005.Vector -> separate_xyz_001.Vector
        andrew_willmotts_interior_mapping.links.new(combine_xyz_005.outputs[0], separate_xyz_001.inputs[0])
        #group_input_002.Flip X UVs? -> math_014.Value
        andrew_willmotts_interior_mapping.links.new(group_input_002.outputs[2], math_014.inputs[0])
        #group_input_002.Flip Y UVs? -> math_015.Value
        andrew_willmotts_interior_mapping.links.new(group_input_002.outputs[3], math_015.inputs[0])

        #Sims bodges for Aspect Ratio
        AR_group_input = create_node(andrew_willmotts_interior_mapping.nodes,"NodeGroupInput",(-131.2041015625, 100.))
        AR_div = create_node(andrew_willmotts_interior_mapping.nodes,"ShaderNodeMath",(96.85089111328125, 100.), operation='DIVIDE')
        AR_div.inputs[0].default_value = 0.5
        andrew_willmotts_interior_mapping.links.new(AR_group_input.outputs[1], AR_div.inputs[0])
        andrew_willmotts_interior_mapping.links.new(AR_group_input.outputs[4], AR_div.inputs[1])
        andrew_willmotts_interior_mapping.links.new(AR_div.outputs[0], math_006.inputs[1])
        andrew_willmotts_interior_mapping.links.new(AR_div.outputs[0], math_007.inputs[1])

        AddGI = create_node(andrew_willmotts_interior_mapping.nodes,"NodeGroupInput",(10., 10.))        
        AR_div2 = create_node(andrew_willmotts_interior_mapping.nodes,"ShaderNodeMath",(10, 10.), operation='DIVIDE')
        AR_div2.inputs[0].default_value = -1
        AddCXYZ = create_node(andrew_willmotts_interior_mapping.nodes,"ShaderNodeCombineXYZ",(10., 10.))
        AddCXYZ.inputs[0].default_value=-1.0
        AddCXYZ.inputs[1].default_value=-1.0
        AddCXYZ.inputs[2].default_value=-1.0
        MultAdd = create_node(andrew_willmotts_interior_mapping.nodes,"ShaderNodeMath",(10., 10), operation='MULTIPLY_ADD')
        MultAdd.inputs[0].default_value=0.25
        MultAdd.inputs[2].default_value=-1.25
        MultAdd.parent = frame_001
        AddGI.parent = frame_001
        AR_div2.parent = frame_001
        AddCXYZ.parent = frame_001
        MultAdd.location=(7058., 1401.)
        AddGI.location=(7080., 1490.)
        AR_div2.location=(7245, 1490.)
        AddCXYZ.location= (7429., 1490.)
        andrew_willmotts_interior_mapping.links.new(AddGI.outputs[4], AR_div2.inputs[1])
        andrew_willmotts_interior_mapping.links.new(AddGI.outputs[4], MultAdd.inputs[1])
        andrew_willmotts_interior_mapping.links.new(AR_div2.outputs[0], AddCXYZ.inputs[0])
        andrew_willmotts_interior_mapping.links.new(AR_div2.outputs[0], AddCXYZ.inputs[1])
        andrew_willmotts_interior_mapping.links.new(MultAdd.outputs[0], AddCXYZ.inputs[2])
        andrew_willmotts_interior_mapping.links.new(AddCXYZ.outputs[0], vector_math_001.inputs[1])


        return andrew_willmotts_interior_mapping


#initialize flipbook_function node group
def flipbook_function_node_group():
    if 'CP77_Flipbook_Function' in bpy.data.node_groups.keys():
        return bpy.data.node_groups['CP77_Flipbook_Function']
    else:
        flipbook_function= bpy.data.node_groups.new(type = 'ShaderNodeTree', name = "CP77_Flipbook_Function")

        #initialize flipbook_function nodes
        #node Frame.001
        frame_001 = flipbook_function.nodes.new("NodeFrame")
        frame_001.label = "totalFrames"

        #node Frame.003
        frame_003 = flipbook_function.nodes.new("NodeFrame")
        frame_003.label = "indexY"

        #node Frame
        frame = flipbook_function.nodes.new("NodeFrame")
        frame.label = "size"

        #node Frame.004
        frame_004 = flipbook_function.nodes.new("NodeFrame")
        frame_004.label = "offset"

        #node Frame.002
        frame_002 = flipbook_function.nodes.new("NodeFrame")
        frame_002.label = "indexX"

        #node Frame.005
        frame_005 = flipbook_function.nodes.new("NodeFrame")
        frame_005.label = "newUV"

        #node Math
        math = flipbook_function.nodes.new("ShaderNodeMath")
        math.operation = 'MULTIPLY'
        #Value_002
        math.inputs[2].default_value = 0.5

        #node Group Input.002
        group_input_002 = flipbook_function.nodes.new("NodeGroupInput")
        #flipbook_function inputs
        
        vers=bpy.app.version
        if vers[0]<4:
            flipbook_function.inputs.new('NodeSocketVector', "UVs")
            flipbook_function.inputs.new('NodeSocketFloat', "Index")
            flipbook_function.inputs.new('NodeSocketFloat', "Index Start Point")
            flipbook_function.inputs.new('NodeSocketFloat', "Total Frames to Play")
            flipbook_function.inputs.new('NodeSocketFloat', "X / Columns")
            flipbook_function.inputs.new('NodeSocketFloat', "Y / Rows")
            flipbook_function_inputs=flipbook_function.inputs
        else:
            flipbook_function.interface.new_socket(name="UVs", socket_type='NodeSocketVector', in_out='INPUT')
            flipbook_function.interface.new_socket(name="Index", socket_type='NodeSocketFloat', in_out='INPUT')
            flipbook_function.interface.new_socket(name="Index Start Point", socket_type='NodeSocketFloat', in_out='INPUT')
            flipbook_function.interface.new_socket(name="Total Frames to Play", socket_type='NodeSocketFloat', in_out='INPUT')
            flipbook_function.interface.new_socket(name="X / Columns", socket_type='NodeSocketFloat', in_out='INPUT')
            flipbook_function.interface.new_socket(name="Y / Rows", socket_type='NodeSocketFloat', in_out='INPUT')
            flipbook_function_inputs=get_inputs(flipbook_function)

        #input UVs
        flipbook_function_inputs[0].default_value = (0.0, 0.0, 0.0)
        flipbook_function_inputs[0].min_value = -3.4028234663852886e+38
        flipbook_function_inputs[0].max_value = 3.4028234663852886e+38
        flipbook_function_inputs[0].attribute_domain = 'POINT'
        flipbook_function_inputs[0].hide_value = True

        #input Index
        flipbook_function_inputs[1].default_value = 1.0
        flipbook_function_inputs[1].min_value = 1.0
        flipbook_function_inputs[1].max_value = 3.4028234663852886e+38
        flipbook_function_inputs[1].attribute_domain = 'POINT'

        #input Index Start Point
        flipbook_function_inputs[2].default_value = 1.0
        flipbook_function_inputs[2].min_value = 1.0
        flipbook_function_inputs[2].max_value = 3.4028234663852886e+38
        flipbook_function_inputs[2].attribute_domain = 'POINT'

        #input Total Frames to Play
        flipbook_function_inputs[3].default_value = 1.0
        flipbook_function_inputs[3].min_value = 1.0
        flipbook_function_inputs[3].max_value = 3.4028234663852886e+38
        flipbook_function_inputs[3].attribute_domain = 'POINT'

        #input X / Columns
        flipbook_function_inputs[4].default_value = 1.0
        flipbook_function_inputs[4].min_value = 1.0
        flipbook_function_inputs[4].max_value = 3.4028234663852886e+38
        flipbook_function_inputs[4].attribute_domain = 'POINT'

        #input Y / Rows
        flipbook_function_inputs[5].default_value = 1.0
        flipbook_function_inputs[5].min_value = 1.0
        flipbook_function_inputs[5].max_value = 3.4028234663852886e+38
        flipbook_function_inputs[5].attribute_domain = 'POINT'



        #node Math.004
        math_004 = flipbook_function.nodes.new("ShaderNodeMath")
        math_004.operation = 'FLOOR'
        #Value_001
        math_004.inputs[1].default_value = 0.5
        #Value_002
        math_004.inputs[2].default_value = 0.5

        #node Math.006
        math_006 = flipbook_function.nodes.new("ShaderNodeMath")
        math_006.operation = 'DIVIDE'
        #Value_002
        math_006.inputs[2].default_value = 0.5

        #node Math.005
        math_005 = flipbook_function.nodes.new("ShaderNodeMath")
        math_005.operation = 'MODULO'
        #Value_002
        math_005.inputs[2].default_value = 0.5

        #node Separate XYZ
        separate_xyz = flipbook_function.nodes.new("ShaderNodeSeparateXYZ")

        #node Combine XYZ
        combine_xyz = flipbook_function.nodes.new("ShaderNodeCombineXYZ")
        #Z
        combine_xyz.inputs[2].default_value = 0.0

        #node Group Input
        group_input = flipbook_function.nodes.new("NodeGroupInput")

        #node Vector Math
        vector_math = flipbook_function.nodes.new("ShaderNodeVectorMath")
        vector_math.operation = 'DIVIDE'
        #Vector
        vector_math.inputs[0].default_value = (1.0, 1.0, 0.0)
        #Vector_002
        vector_math.inputs[2].default_value = (0.0, 0.0, 0.0)
        #Scale
        vector_math.inputs[3].default_value = 1.0

        #node Math.003
        math_003 = flipbook_function.nodes.new("ShaderNodeMath")
        math_003.operation = 'SUBTRACT'
        #Value
        math_003.inputs[0].default_value = 0.0
        #Value_002
        math_003.inputs[2].default_value = 0.5

        #node Math.008
        math_008 = flipbook_function.nodes.new("ShaderNodeMath")
        math_008.operation = 'MULTIPLY'
        #Value_002
        math_008.inputs[2].default_value = 0.5

        #node Math.007
        math_007 = flipbook_function.nodes.new("ShaderNodeMath")
        math_007.operation = 'MULTIPLY'
        #Value_002
        math_007.inputs[2].default_value = 0.5

        #node Combine XYZ.001
        combine_xyz_001 = flipbook_function.nodes.new("ShaderNodeCombineXYZ")
        #Z
        combine_xyz_001.inputs[2].default_value = 0.0

        #node Group Input.004
        group_input_004 = flipbook_function.nodes.new("NodeGroupInput")

        #node Math.002
        math_002 = flipbook_function.nodes.new("ShaderNodeMath")
        math_002.operation = 'MODULO'
        #Value_002
        math_002.inputs[2].default_value = 0.5

        #node Reroute.001
        reroute_001 = flipbook_function.nodes.new("NodeReroute")
        #node Group Input.003
        group_input_003 = flipbook_function.nodes.new("NodeGroupInput")

        #node Math.001
        math_001 = flipbook_function.nodes.new("ShaderNodeMath")
        math_001.operation = 'MODULO'
        #Value_002
        math_001.inputs[2].default_value = 0.5

        #node Math.016
        math_016 = flipbook_function.nodes.new("ShaderNodeMath")
        math_016.operation = 'FLOOR'
        #Value_001
        math_016.inputs[1].default_value = 0.5
        #Value_002
        math_016.inputs[2].default_value = 0.5

        #node Group Input.006
        group_input_006 = flipbook_function.nodes.new("NodeGroupInput")

        #node Math.014
        math_014 = flipbook_function.nodes.new("ShaderNodeMath")
        math_014.operation = 'SUBTRACT'
        #Value_001
        math_014.inputs[1].default_value = 1.0
        #Value_002
        math_014.inputs[2].default_value = 0.5

        #node Math.017
        math_017 = flipbook_function.nodes.new("ShaderNodeMath")
        math_017.operation = 'FLOOR'
        #Value_001
        math_017.inputs[1].default_value = 0.5
        #Value_002
        math_017.inputs[2].default_value = 0.5

        #node Math.015
        math_015 = flipbook_function.nodes.new("ShaderNodeMath")
        math_015.operation = 'SUBTRACT'
        #Value_001
        math_015.inputs[1].default_value = 1.0
        #Value_002
        math_015.inputs[2].default_value = 0.5

        #node Math.013
        math_013 = flipbook_function.nodes.new("ShaderNodeMath")
        math_013.operation = 'ADD'
        #Value_002
        math_013.inputs[2].default_value = 0.5

        #node Math.012
        math_012 = flipbook_function.nodes.new("ShaderNodeMath")
        math_012.operation = 'FLOOR'
        #Value_001
        math_012.inputs[1].default_value = 0.5
        #Value_002
        math_012.inputs[2].default_value = 0.5

        #node Group Output
        group_output = flipbook_function.nodes.new("NodeGroupOutput")
        #flipbook_function outputs
        #output Output
        if vers[0]<4:
            fbOut0=flipbook_function.outputs.new('NodeSocketVector', "Output")
        else:
            fbOut0=flipbook_function.interface.new_socket(name="Output", socket_type='NodeSocketVector', in_out='OUTPUT')
        fbOut0.default_value = (0.0, 0.0, 0.0)
        fbOut0.min_value = -3.4028234663852886e+38
        fbOut0.max_value = 3.4028234663852886e+38
        fbOut0.attribute_domain = 'POINT'



        #node Vector Math.002
        vector_math_002 = flipbook_function.nodes.new("ShaderNodeVectorMath")
        vector_math_002.operation = 'ADD'
        #Vector_002
        vector_math_002.inputs[2].default_value = (0.0, 0.0, 0.0)
        #Scale
        vector_math_002.inputs[3].default_value = 1.0

        #node Separate XYZ.001
        separate_xyz_001 = flipbook_function.nodes.new("ShaderNodeSeparateXYZ")

        #node Math.010
        math_010 = flipbook_function.nodes.new("ShaderNodeMath")
        math_010.operation = 'MULTIPLY'
        #Value_002
        math_010.inputs[2].default_value = 0.5

        #node Math.009
        math_009 = flipbook_function.nodes.new("ShaderNodeMath")
        math_009.operation = 'ADD'
        #Value_002
        math_009.inputs[2].default_value = 0.5

        #node Combine XYZ.002
        combine_xyz_002 = flipbook_function.nodes.new("ShaderNodeCombineXYZ")
        #Z
        combine_xyz_002.inputs[2].default_value = 0.0

        #node Math.011
        math_011 = flipbook_function.nodes.new("ShaderNodeMath")
        math_011.operation = 'SUBTRACT'
        #Value_001
        math_011.inputs[1].default_value = 1.0
        #Value_002
        math_011.inputs[2].default_value = 0.5

        #node Group Input.005
        group_input_005 = flipbook_function.nodes.new("NodeGroupInput")

        #node Reroute
        reroute = flipbook_function.nodes.new("NodeReroute")
        #node Vector Math.001
        vector_math_001 = flipbook_function.nodes.new("ShaderNodeVectorMath")
        vector_math_001.operation = 'MULTIPLY'
        #Vector_002
        vector_math_001.inputs[2].default_value = (0.0, 0.0, 0.0)
        #Scale
        vector_math_001.inputs[3].default_value = 1.0

        #node Texture Coordinate
        texture_coordinate = flipbook_function.nodes.new("ShaderNodeTexCoord")
        texture_coordinate.outputs[0].hide = True
        texture_coordinate.outputs[1].hide = True
        texture_coordinate.outputs[3].hide = True
        texture_coordinate.outputs[4].hide = True
        texture_coordinate.outputs[5].hide = True
        texture_coordinate.outputs[6].hide = True

        #node Group Input.001
        group_input_001 = flipbook_function.nodes.new("NodeGroupInput")
        group_input_001.outputs[1].hide = True
        group_input_001.outputs[2].hide = True
        group_input_001.outputs[3].hide = True
        group_input_001.outputs[4].hide = True
        group_input_001.outputs[5].hide = True
        group_input_001.outputs[6].hide = True

        #Set parents
        math.parent = frame_001
        group_input_002.parent = frame_001
        math_004.parent = frame_003
        math_006.parent = frame_003
        math_005.parent = frame_003
        combine_xyz.parent = frame
        group_input.parent = frame
        vector_math.parent = frame
        math_003.parent = frame_004
        math_008.parent = frame_004
        math_007.parent = frame_004
        combine_xyz_001.parent = frame_004
        group_input_004.parent = frame_003
        math_002.parent = frame_002
        group_input_003.parent = frame_002
        vector_math_001.parent = frame_005
        texture_coordinate.parent = frame_005
        group_input_001.parent = frame_005

        #Set locations
        frame_001.location = (-163.97775268554688, -551.3585205078125)
        frame_003.location = (166.0, 10.0)
        frame.location = (19.234130859375, -14.6524658203125)
        frame_004.location = (174.1219482421875, -10.91497802734375)
        frame_002.location = (166.0, 10.0)
        frame_005.location = (-19.878143310546875, 187.38275146484375)
        math.location = (293.75653076171875, -76.71304321289062)
        group_input_002.location = (13.3409423828125, -125.78768920898438)
        math_004.location = (1497.386474609375, -548.57470703125)
        math_006.location = (1297.9349365234375, -580.7101440429688)
        math_005.location = (1079.3350830078125, -524.4735107421875)
        separate_xyz.location = (759.4443359375, 73.30291748046875)
        combine_xyz.location = (142.95498657226562, 204.04269409179688)
        group_input.location = (-140.75509643554688, 214.04852294921875)
        vector_math.location = (343.95794677734375, 344.0719299316406)
        math_003.location = (1612.291259765625, -234.28326416015625)
        math_008.location = (1854.05322265625, -23.61822509765625)
        math_007.location = (1853.664306640625, -241.07321166992188)
        combine_xyz_001.location = (2090.266357421875, -146.97677612304688)
        group_input_004.location = (910.05224609375, -710.2528686523438)
        math_002.location = (844.6197509765625, -198.29461669921875)
        reroute_001.location = (611.066162109375, -408.55731201171875)
        group_input_003.location = (573.3001708984375, -177.94854736328125)
        math_001.location = (-428.38232421875, -25.010986328125)
        math_016.location = (-856.8076782226562, -14.62286376953125)
        group_input_006.location = (-1130.0859375, -213.24166870117188)
        math_014.location = (-850.0503540039062, -345.9706726074219)
        math_017.location = (-860.0101928710938, -190.42620849609375)
        math_015.location = (-657.93408203125, 8.1865234375)
        math_013.location = (-237.86175537109375, -208.6192626953125)
        math_012.location = (-47.527587890625, -159.346923828125)
        group_output.location = (4224.97998046875, -70.21841430664062)
        vector_math_002.location = (3983.825927734375, -131.47427368164062)
        separate_xyz_001.location = (2961.53369140625, 411.2303466796875)
        math_010.location = (2947.66845703125, 223.6722412109375)
        math_009.location = (3175.61181640625, 326.5302734375)
        combine_xyz_002.location = (3409.975341796875, 350.354736328125)
        math_011.location = (2720.36328125, 40.82421875)
        group_input_005.location = (2518.391845703125, -3.338714599609375)
        reroute.location = (2349.813720703125, 118.02578735351562)
        vector_math_001.location = (2624.24755859375, 248.04608154296875)
        texture_coordinate.location = (2402.292236328125, 348.709716796875)
        group_input_001.location = (2398.22509765625, 220.63742065429688)

        #Set dimensions
        frame_001.width, frame_001.height = 480.0, 298.0
        frame_003.width, frame_003.height = 787.199951171875, 434.8000183105469
        frame.width, frame.height = 684.800048828125, 384.3999938964844
        frame_004.width, frame_004.height = 677.599853515625, 439.6000061035156
        frame_002.width, frame_002.height = 471.20001220703125, 249.20001220703125
        frame_005.width, frame_005.height = 425.60009765625, 302.0
        math.width, math.height = 140.0, 100.0
        group_input_002.width, group_input_002.height = 140.0, 100.0
        math_004.width, math_004.height = 140.0, 100.0
        math_006.width, math_006.height = 140.0, 100.0
        math_005.width, math_005.height = 140.0, 100.0
        separate_xyz.width, separate_xyz.height = 140.0, 100.0
        combine_xyz.width, combine_xyz.height = 140.0, 100.0
        group_input.width, group_input.height = 140.0, 100.0
        vector_math.width, vector_math.height = 140.0, 100.0
        math_003.width, math_003.height = 140.0, 100.0
        math_008.width, math_008.height = 140.0, 100.0
        math_007.width, math_007.height = 140.0, 100.0
        combine_xyz_001.width, combine_xyz_001.height = 140.0, 100.0
        group_input_004.width, group_input_004.height = 194.36767578125, 100.0
        math_002.width, math_002.height = 140.0, 100.0
        reroute_001.width, reroute_001.height = 16.0, 100.0
        group_input_003.width, group_input_003.height = 140.0, 100.0
        math_001.width, math_001.height = 140.0, 100.0
        math_016.width, math_016.height = 140.0, 100.0
        group_input_006.width, group_input_006.height = 140.0, 100.0
        math_014.width, math_014.height = 140.0, 100.0
        math_017.width, math_017.height = 140.0, 100.0
        math_015.width, math_015.height = 140.0, 100.0
        math_013.width, math_013.height = 140.0, 100.0
        math_012.width, math_012.height = 140.0, 100.0
        group_output.width, group_output.height = 140.0, 100.0
        vector_math_002.width, vector_math_002.height = 140.0, 100.0
        separate_xyz_001.width, separate_xyz_001.height = 140.0, 100.0
        math_010.width, math_010.height = 140.0, 100.0
        math_009.width, math_009.height = 140.0, 100.0
        combine_xyz_002.width, combine_xyz_002.height = 140.0, 100.0
        math_011.width, math_011.height = 140.0, 100.0
        group_input_005.width, group_input_005.height = 140.0, 100.0
        reroute.width, reroute.height = 16.0, 100.0
        vector_math_001.width, vector_math_001.height = 140.0, 100.0
        texture_coordinate.width, texture_coordinate.height = 140.0, 100.0
        group_input_001.width, group_input_001.height = 140.0, 100.0

        #initialize flipbook_function links
        #combine_xyz.Vector -> vector_math.Vector
        flipbook_function.links.new(combine_xyz.outputs[0], vector_math.inputs[1])
        #group_input.X / Columns -> combine_xyz.X
        flipbook_function.links.new(group_input.outputs[4], combine_xyz.inputs[0])
        #group_input.Y / Rows -> combine_xyz.Y
        flipbook_function.links.new(group_input.outputs[5], combine_xyz.inputs[1])
        #group_input_002.X / Columns -> math.Value
        flipbook_function.links.new(group_input_002.outputs[4], math.inputs[0])
        #group_input_002.Y / Rows -> math.Value
        flipbook_function.links.new(group_input_002.outputs[5], math.inputs[1])
        #group_input_003.X / Columns -> math_002.Value
        flipbook_function.links.new(group_input_003.outputs[4], math_002.inputs[1])
        #math.Value -> math_005.Value
        flipbook_function.links.new(math.outputs[0], math_005.inputs[1])
        #math_005.Value -> math_006.Value
        flipbook_function.links.new(math_005.outputs[0], math_006.inputs[0])
        #group_input_004.X / Columns -> math_006.Value
        flipbook_function.links.new(group_input_004.outputs[4], math_006.inputs[1])
        #math_006.Value -> math_004.Value
        flipbook_function.links.new(math_006.outputs[0], math_004.inputs[0])
        #vector_math.Vector -> separate_xyz.Vector
        flipbook_function.links.new(vector_math.outputs[0], separate_xyz.inputs[0])
        #separate_xyz.Y -> math_003.Value
        flipbook_function.links.new(separate_xyz.outputs[1], math_003.inputs[1])
        #math_003.Value -> math_007.Value
        flipbook_function.links.new(math_003.outputs[0], math_007.inputs[0])
        #math_004.Value -> math_007.Value
        flipbook_function.links.new(math_004.outputs[0], math_007.inputs[1])
        #math_002.Value -> math_008.Value
        flipbook_function.links.new(math_002.outputs[0], math_008.inputs[1])
        #separate_xyz.X -> math_008.Value
        flipbook_function.links.new(separate_xyz.outputs[0], math_008.inputs[0])
        #math_008.Value -> combine_xyz_001.X
        flipbook_function.links.new(math_008.outputs[0], combine_xyz_001.inputs[0])
        #math_007.Value -> combine_xyz_001.Y
        flipbook_function.links.new(math_007.outputs[0], combine_xyz_001.inputs[1])
        #vector_math.Vector -> vector_math_001.Vector
        flipbook_function.links.new(vector_math.outputs[0], vector_math_001.inputs[1])
        #vector_math_001.Vector -> separate_xyz_001.Vector
        flipbook_function.links.new(vector_math_001.outputs[0], separate_xyz_001.inputs[0])
        #separate_xyz_001.Y -> math_009.Value
        flipbook_function.links.new(separate_xyz_001.outputs[1], math_009.inputs[0])
        #math_010.Value -> math_009.Value
        flipbook_function.links.new(math_010.outputs[0], math_009.inputs[1])
        #reroute.Output -> math_010.Value
        flipbook_function.links.new(reroute.outputs[0], math_010.inputs[0])
        #separate_xyz.Y -> reroute.Input
        flipbook_function.links.new(separate_xyz.outputs[1], reroute.inputs[0])
        #math_011.Value -> math_010.Value
        flipbook_function.links.new(math_011.outputs[0], math_010.inputs[1])
        #group_input_005.Y / Rows -> math_011.Value
        flipbook_function.links.new(group_input_005.outputs[5], math_011.inputs[0])
        #math_009.Value -> combine_xyz_002.Y
        flipbook_function.links.new(math_009.outputs[0], combine_xyz_002.inputs[1])
        #separate_xyz_001.X -> combine_xyz_002.X
        flipbook_function.links.new(separate_xyz_001.outputs[0], combine_xyz_002.inputs[0])
        #combine_xyz_002.Vector -> vector_math_002.Vector
        flipbook_function.links.new(combine_xyz_002.outputs[0], vector_math_002.inputs[0])
        #combine_xyz_001.Vector -> vector_math_002.Vector
        flipbook_function.links.new(combine_xyz_001.outputs[0], vector_math_002.inputs[1])
        #vector_math_002.Vector -> group_output.Output
        flipbook_function.links.new(vector_math_002.outputs[0], group_output.inputs[0])
        #reroute_001.Output -> math_002.Value
        flipbook_function.links.new(reroute_001.outputs[0], math_002.inputs[0])
        #reroute_001.Output -> math_005.Value
        flipbook_function.links.new(reroute_001.outputs[0], math_005.inputs[0])
        #math_012.Value -> reroute_001.Input
        flipbook_function.links.new(math_012.outputs[0], reroute_001.inputs[0])
        #group_input_006.Index Start Point -> math_014.Value
        flipbook_function.links.new(group_input_006.outputs[2], math_014.inputs[0])
        #group_input_006.Index -> math_016.Value
        flipbook_function.links.new(group_input_006.outputs[1], math_016.inputs[0])
        #math_013.Value -> math_012.Value
        flipbook_function.links.new(math_013.outputs[0], math_012.inputs[0])
        #math_014.Value -> math_013.Value
        flipbook_function.links.new(math_014.outputs[0], math_013.inputs[1])
        #math_015.Value -> math_001.Value
        flipbook_function.links.new(math_015.outputs[0], math_001.inputs[0])
        #group_input_006.Total Frames to Play -> math_017.Value
        flipbook_function.links.new(group_input_006.outputs[3], math_017.inputs[0])
        #math_001.Value -> math_013.Value
        flipbook_function.links.new(math_001.outputs[0], math_013.inputs[0])
        #math_016.Value -> math_015.Value
        flipbook_function.links.new(math_016.outputs[0], math_015.inputs[0])
        #math_017.Value -> math_001.Value
        flipbook_function.links.new(math_017.outputs[0], math_001.inputs[1])
        #group_input_001.UVs -> vector_math_001.Vector
        flipbook_function.links.new(group_input_001.outputs[0], vector_math_001.inputs[0])
        return flipbook_function





