import bpy
import os
from ..main.common import *

class Skin:
    def __init__(self, BasePath, image_format,ProjPath):
        self.BasePath = str(BasePath)
        self.ProjPath = str(ProjPath)
        self.image_format = image_format

    def create_skin_node_group(self, microdetail_image=None):
        ng_name = "Skin 2077 1.8.0"
        if ng_name in bpy.data.node_groups:
            return bpy.data.node_groups[ng_name]
        nodegroup = bpy.data.node_groups.new(type = 'ShaderNodeTree', name = ng_name)

        nodegroup.color_tag = 'NONE'
        nodegroup.description = ""
        nodegroup.default_group_node_width = 140
        # nodegroup interface

        # Socket Image
        image_socket_2 = nodegroup.interface.new_socket(name="Image", in_out='OUTPUT', socket_type='NodeSocketColor')
        image_socket_2.default_value = (0.0, 0.0, 0.0, 1.0)
        image_socket_2.attribute_domain = 'POINT'
        image_socket_2.default_input = 'VALUE'
        image_socket_2.structure_type = 'AUTO'

        # Socket Microdetail Influence
        microdetail_influence_socket = nodegroup.interface.new_socket(name="Microdetail Influence", in_out='INPUT', socket_type='NodeSocketFloat')
        microdetail_influence_socket.default_value = 0.0
        microdetail_influence_socket.min_value = -3.4028234663852886e+38
        microdetail_influence_socket.max_value = 3.4028234663852886e+38
        microdetail_influence_socket.subtype = 'NONE'
        microdetail_influence_socket.attribute_domain = 'POINT'
        microdetail_influence_socket.default_input = 'VALUE'
        microdetail_influence_socket.structure_type = 'AUTO'

        # Socket TintColor | Green (MD Mask)
        tintcolor___green__md_mask__socket = nodegroup.interface.new_socket(name="TintColor | Green (MD Mask)", in_out='INPUT', socket_type='NodeSocketFloat')
        tintcolor___green__md_mask__socket.default_value = 0.0
        tintcolor___green__md_mask__socket.min_value = 0.0
        tintcolor___green__md_mask__socket.max_value = 1.0
        tintcolor___green__md_mask__socket.subtype = 'FACTOR'
        tintcolor___green__md_mask__socket.attribute_domain = 'POINT'
        tintcolor___green__md_mask__socket.default_input = 'VALUE'
        tintcolor___green__md_mask__socket.structure_type = 'AUTO'

        # Socket TintColor | Blue (Scale)
        tintcolor___blue__scale__socket = nodegroup.interface.new_socket(name="TintColor | Blue (Scale)", in_out='INPUT', socket_type='NodeSocketFloat')
        tintcolor___blue__scale__socket.default_value = 0.0
        tintcolor___blue__scale__socket.min_value = 0.0
        tintcolor___blue__scale__socket.max_value = 1.0
        tintcolor___blue__scale__socket.subtype = 'FACTOR'
        tintcolor___blue__scale__socket.attribute_domain = 'POINT'
        tintcolor___blue__scale__socket.default_input = 'VALUE'
        tintcolor___blue__scale__socket.structure_type = 'AUTO'

        # Socket Normal
        normal_socket = nodegroup.interface.new_socket(name="Normal", in_out='INPUT', socket_type='NodeSocketColor')
        normal_socket.default_value = (0.0, 0.0, 0.0, 1.0)
        normal_socket.attribute_domain = 'POINT'
        normal_socket.default_input = 'VALUE'
        normal_socket.structure_type = 'AUTO'

        # Socket Detail Normal
        detail_normal_socket = nodegroup.interface.new_socket(name="Detail Normal", in_out='INPUT', socket_type='NodeSocketColor')
        detail_normal_socket.default_value = (0.0, 0.0, 0.0, 1.0)
        detail_normal_socket.attribute_domain = 'POINT'
        detail_normal_socket.default_input = 'VALUE'
        detail_normal_socket.structure_type = 'AUTO'

        # Socket DetailNormalInfluence
        detailnormalinfluence_socket = nodegroup.interface.new_socket(name="DetailNormalInfluence", in_out='INPUT', socket_type='NodeSocketFloat')
        detailnormalinfluence_socket.default_value = 0.0
        detailnormalinfluence_socket.min_value = -3.4028234663852886e+38
        detailnormalinfluence_socket.max_value = 3.4028234663852886e+38
        detailnormalinfluence_socket.subtype = 'NONE'
        detailnormalinfluence_socket.attribute_domain = 'POINT'
        detailnormalinfluence_socket.default_input = 'VALUE'
        detailnormalinfluence_socket.structure_type = 'AUTO'

        # Socket MicroDetailUVScale01
        microdetailuvscale01_socket = nodegroup.interface.new_socket(name="MicroDetailUVScale01", in_out='INPUT', socket_type='NodeSocketFloat')
        microdetailuvscale01_socket.default_value = 0.0
        microdetailuvscale01_socket.min_value = -3.4028234663852886e+38
        microdetailuvscale01_socket.max_value = 3.4028234663852886e+38
        microdetailuvscale01_socket.subtype = 'NONE'
        microdetailuvscale01_socket.attribute_domain = 'POINT'
        microdetailuvscale01_socket.default_input = 'VALUE'
        microdetailuvscale01_socket.structure_type = 'AUTO'

        # Socket MicroDetailUVScale02
        microdetailuvscale02_socket = nodegroup.interface.new_socket(name="MicroDetailUVScale02", in_out='INPUT', socket_type='NodeSocketFloat')
        microdetailuvscale02_socket.default_value = 0.0
        microdetailuvscale02_socket.min_value = -3.4028234663852886e+38
        microdetailuvscale02_socket.max_value = 3.4028234663852886e+38
        microdetailuvscale02_socket.subtype = 'NONE'
        microdetailuvscale02_socket.attribute_domain = 'POINT'
        microdetailuvscale02_socket.default_input = 'VALUE'
        microdetailuvscale02_socket.structure_type = 'AUTO'

        # Initialize nodegroup nodes

        # Node Group Output
        group_output_1 = nodegroup.nodes.new("NodeGroupOutput")
        group_output_1.name = "Group Output"
        group_output_1.is_active_output = True

        # Node Group Input
        group_input_1 = nodegroup.nodes.new("NodeGroupInput")
        group_input_1.name = "Group Input"

        # Node Texture Coordinate
        texture_coordinate = nodegroup.nodes.new("ShaderNodeTexCoord")
        texture_coordinate.name = "Texture Coordinate"
        texture_coordinate.hide = True
        texture_coordinate.from_instancer = False

        # Node Vector Math
        vector_math_1 = nodegroup.nodes.new("ShaderNodeVectorMath")
        vector_math_1.name = "Vector Math"
        vector_math_1.hide = True
        vector_math_1.operation = 'MULTIPLY'
        # Vector_001
        vector_math_1.inputs[1].default_value = (1.0, 2.0, 1.0)

        # Node Vector Math.001
        vector_math_001_1 = nodegroup.nodes.new("ShaderNodeVectorMath")
        vector_math_001_1.name = "Vector Math.001"
        vector_math_001_1.hide = True
        vector_math_001_1.operation = 'MULTIPLY'
        # Vector_001
        vector_math_001_1.inputs[1].default_value = (1.0, 2.0, 1.0)

        # Node Vector Math.002
        vector_math_002 = nodegroup.nodes.new("ShaderNodeVectorMath")
        vector_math_002.name = "Vector Math.002"
        vector_math_002.hide = True
        vector_math_002.operation = 'MULTIPLY'

        # Node Vector Math.003
        vector_math_003 = nodegroup.nodes.new("ShaderNodeVectorMath")
        vector_math_003.name = "Vector Math.003"
        vector_math_003.hide = True
        vector_math_003.operation = 'MULTIPLY'

        # Node Vector Math.004
        vector_math_004 = nodegroup.nodes.new("ShaderNodeVectorMath")
        vector_math_004.name = "Vector Math.004"
        vector_math_004.hide = True
        vector_math_004.operation = 'MODULO'
        # Vector_001
        vector_math_004.inputs[1].default_value = (0.5, 1.0, 1.0)

        # Node Vector Math.005
        vector_math_005 = nodegroup.nodes.new("ShaderNodeVectorMath")
        vector_math_005.name = "Vector Math.005"
        vector_math_005.hide = True
        vector_math_005.operation = 'MODULO'
        # Vector_001
        vector_math_005.inputs[1].default_value = (0.5, 1.0, 1.0)

        # Node Vector Math.006
        vector_math_006 = nodegroup.nodes.new("ShaderNodeVectorMath")
        vector_math_006.name = "Vector Math.006"
        vector_math_006.hide = True
        vector_math_006.operation = 'ADD'
        # Vector_001
        vector_math_006.inputs[1].default_value = (0.5, 0.0, 0.0)

        # Node Image Texture.005
        image_texture_005 = nodegroup.nodes.new("ShaderNodeTexImage")
        image_texture_005.label = "MicroDetail"
        image_texture_005.name = "Image Texture.005"
        image_texture_005.extension = 'REPEAT'
        if microdetail_image:
            image_texture_005.image = microdetail_image
        image_texture_005.image_user.frame_current = 1
        image_texture_005.image_user.frame_duration = 1
        image_texture_005.image_user.frame_offset = -1
        image_texture_005.image_user.frame_start = 1
        image_texture_005.image_user.tile = 0
        image_texture_005.image_user.use_auto_refresh = False
        image_texture_005.image_user.use_cyclic = False
        image_texture_005.interpolation = 'Linear'
        image_texture_005.projection = 'FLAT'
        image_texture_005.projection_blend = 0.0

        # Node Image Texture.006
        image_texture_006 = nodegroup.nodes.new("ShaderNodeTexImage")
        image_texture_006.label = "MicroDetail"
        image_texture_006.name = "Image Texture.006"
        image_texture_006.extension = 'REPEAT'
        if microdetail_image:
            image_texture_006.image = microdetail_image
        image_texture_006.image_user.frame_current = 0
        image_texture_006.image_user.frame_duration = 100
        image_texture_006.image_user.frame_offset = 0
        image_texture_006.image_user.frame_start = 1
        image_texture_006.image_user.tile = 0
        image_texture_006.image_user.use_auto_refresh = False
        image_texture_006.image_user.use_cyclic = False
        image_texture_006.interpolation = 'Linear'
        image_texture_006.projection = 'FLAT'
        image_texture_006.projection_blend = 0.0

        # Node Vector Math.007
        vector_math_007 = nodegroup.nodes.new("ShaderNodeVectorMath")
        vector_math_007.name = "Vector Math.007"
        vector_math_007.operation = 'MULTIPLY_ADD'
        # Vector_001
        vector_math_007.inputs[1].default_value = (2.0, 2.0, 0.0)
        # Vector_002
        vector_math_007.inputs[2].default_value = (-1.0, -1.0, 0.0)

        # Node Vector Math.008
        vector_math_008 = nodegroup.nodes.new("ShaderNodeVectorMath")
        vector_math_008.name = "Vector Math.008"
        vector_math_008.operation = 'MULTIPLY_ADD'
        # Vector_001
        vector_math_008.inputs[1].default_value = (2.0, 2.0, 0.0)
        # Vector_002
        vector_math_008.inputs[2].default_value = (-1.0, -1.0, 0.0)

        # Node Vector Math.009
        vector_math_009 = nodegroup.nodes.new("ShaderNodeVectorMath")
        vector_math_009.name = "Vector Math.009"
        vector_math_009.operation = 'MULTIPLY_ADD'
        # Vector_001
        vector_math_009.inputs[1].default_value = (2.0, 2.0, 0.0)
        # Vector_002
        vector_math_009.inputs[2].default_value = (-1.0, -1.0, 0.0)

        # Node Vector Math.010
        vector_math_010 = nodegroup.nodes.new("ShaderNodeVectorMath")
        vector_math_010.name = "Vector Math.010"
        vector_math_010.operation = 'MULTIPLY_ADD'
        # Vector_001
        vector_math_010.inputs[1].default_value = (2.0, 2.0, 0.0)
        # Vector_002
        vector_math_010.inputs[2].default_value = (-1.0, -1.0, 0.0)

        # Node Vector Math.011
        vector_math_011 = nodegroup.nodes.new("ShaderNodeVectorMath")
        vector_math_011.name = "Vector Math.011"
        vector_math_011.operation = 'ADD'

        # Node Vector Math.012
        vector_math_012 = nodegroup.nodes.new("ShaderNodeVectorMath")
        vector_math_012.name = "Vector Math.012"
        vector_math_012.operation = 'MULTIPLY'

        # Node Group.001
        group_001 = CreateCalculateVecNormalZ(nodegroup)

        # Node Vector Math.013
        vector_math_013 = nodegroup.nodes.new("ShaderNodeVectorMath")
        vector_math_013.name = "Vector Math.013"
        vector_math_013.operation = 'ADD'

        # Node Vector Math.014
        vector_math_014 = nodegroup.nodes.new("ShaderNodeVectorMath")
        vector_math_014.name = "Vector Math.014"
        vector_math_014.operation = 'MULTIPLY'

        # Node Reroute
        reroute = nodegroup.nodes.new("NodeReroute")
        reroute.name = "Reroute"
        reroute.socket_idname = "NodeSocketFloat"
        # Node Mix
        mix = nodegroup.nodes.new("ShaderNodeMix")
        mix.name = "Mix"
        mix.blend_type = 'MIX'
        mix.clamp_factor = True
        mix.clamp_result = False
        mix.data_type = 'FLOAT'
        mix.factor_mode = 'UNIFORM'
        # A_Float
        mix.inputs[2].default_value = 1.0
        # B_Float
        mix.inputs[3].default_value = 0.5

        # Node Vector Math.015
        vector_math_015 = nodegroup.nodes.new("ShaderNodeVectorMath")
        vector_math_015.name = "Vector Math.015"
        vector_math_015.operation = 'MULTIPLY'

        # Node Vector Math.016
        vector_math_016 = nodegroup.nodes.new("ShaderNodeVectorMath")
        vector_math_016.name = "Vector Math.016"
        vector_math_016.operation = 'MULTIPLY'

        # Node Vector Math.017
        vector_math_017 = nodegroup.nodes.new("ShaderNodeVectorMath")
        vector_math_017.name = "Vector Math.017"
        vector_math_017.operation = 'ADD'

        # Node Vector Math.018
        vector_math_018 = nodegroup.nodes.new("ShaderNodeVectorMath")
        vector_math_018.name = "Vector Math.018"
        vector_math_018.operation = 'MULTIPLY'

        # Node Vector Math.019
        vector_math_019 = nodegroup.nodes.new("ShaderNodeVectorMath")
        vector_math_019.name = "Vector Math.019"
        vector_math_019.operation = 'MULTIPLY'

        # Node Value
        value = nodegroup.nodes.new("ShaderNodeValue")
        value.name = "Value"

        value.outputs[0].default_value = 1.0
        # Node Value.001
        value_001 = nodegroup.nodes.new("ShaderNodeValue")
        value_001.name = "Value.001"

        value_001.outputs[0].default_value = 1.0
        # Node Reroute.001
        reroute_001 = nodegroup.nodes.new("NodeReroute")
        reroute_001.name = "Reroute.001"
        reroute_001.socket_idname = "NodeSocketFloatFactor"
        # Node Node
        node_1 = nodegroup.nodes.new("NodeFrame")
        node_1.label = "cant remember which gets masked"
        node_1.name = "Node"
        node_1.label_size = 34
        node_1.shrink = False

        # Set parents
        value.parent = node_1
        value_001.parent = node_1

        # Set locations
        group_output_1.location = (1688.6412353515625, 0.0)
        group_input_1.location = (-1913.80859375, -444.4565734863281)
        texture_coordinate.location = (-1520.0, -700.0)
        vector_math_1.location = (-1320.0, -860.0)
        vector_math_001_1.location = (-1320.0, -1000.0)
        vector_math_002.location = (-1120.0, -700.0)
        vector_math_003.location = (-1120.0, -1000.0)
        vector_math_004.location = (-540.0, -700.0)
        vector_math_005.location = (-540.0, -1000.0)
        vector_math_006.location = (-340.0, -1000.0)
        image_texture_005.location = (-100.0, -400.0)
        image_texture_006.location = (-100.0, -680.0)
        vector_math_007.location = (300.0, -680.0)
        vector_math_008.location = (300.0, -400.0)
        vector_math_009.location = (-680.0, -180.0)
        vector_math_010.location = (-569.0558471679688, 125.10543060302734)
        vector_math_011.location = (-280.0, 120.0)
        vector_math_012.location = (-480.0, -180.0)
        group_001.location = (1320.0, 0.0)
        vector_math_013.location = (1040.0, 140.0)
        vector_math_014.location = (1040.0, 0.0)
        reroute.location = (-360.0, -80.0)
        mix.location = (-1100.0, -480.0)
        vector_math_015.location = (-740.0, -700.0)
        vector_math_016.location = (-740.0, -960.0)
        vector_math_017.location = (820.0, -500.0)
        vector_math_018.location = (560.0, -400.0)
        vector_math_019.location = (560.0, -680.0)
        value.location = (70.0, -400.0)
        value_001.location = (70.0, -680.0)
        reroute_001.location = (420.0, -1080.0)
        node_1.location = (490.0, -180.0)

        # Set dimensions
        group_output_1.width, group_output_1.height = 140.0, 100.0
        group_input_1.width, group_input_1.height = 220.0, 100.0
        texture_coordinate.width, texture_coordinate.height = 140.0, 100.0
        vector_math_1.width, vector_math_1.height = 140.0, 100.0
        vector_math_001_1.width, vector_math_001_1.height = 140.0, 100.0
        vector_math_002.width, vector_math_002.height = 140.0, 100.0
        vector_math_003.width, vector_math_003.height = 140.0, 100.0
        vector_math_004.width, vector_math_004.height = 140.0, 100.0
        vector_math_005.width, vector_math_005.height = 140.0, 100.0
        vector_math_006.width, vector_math_006.height = 140.0, 100.0
        image_texture_005.width, image_texture_005.height = 360.0, 100.0
        image_texture_006.width, image_texture_006.height = 360.0, 100.0
        vector_math_007.width, vector_math_007.height = 140.0, 100.0
        vector_math_008.width, vector_math_008.height = 140.0, 100.0
        vector_math_009.width, vector_math_009.height = 140.0, 100.0
        vector_math_010.width, vector_math_010.height = 140.0, 100.0
        vector_math_011.width, vector_math_011.height = 140.0, 100.0
        vector_math_012.width, vector_math_012.height = 140.0, 100.0
        group_001.width, group_001.height = 267.9640808105469, 100.0
        vector_math_013.width, vector_math_013.height = 140.0, 100.0
        vector_math_014.width, vector_math_014.height = 140.0, 100.0
        reroute.width, reroute.height = 14.5, 100.0
        mix.width, mix.height = 140.0, 100.0
        vector_math_015.width, vector_math_015.height = 140.0, 100.0
        vector_math_016.width, vector_math_016.height = 140.0, 100.0
        vector_math_017.width, vector_math_017.height = 140.0, 100.0
        vector_math_018.width, vector_math_018.height = 140.0, 100.0
        vector_math_019.width, vector_math_019.height = 140.0, 100.0
        value.width, value.height = 140.0, 100.0
        value_001.width, value_001.height = 140.0, 100.0
        reroute_001.width, reroute_001.height = 14.5, 100.0
        node_1.width, node_1.height = 300.0, 757.0

        # Initialize nodegroup links

        # vector_math_012.Vector -> vector_math_011.Vector
        nodegroup.links.new(vector_math_012.outputs[0], vector_math_011.inputs[1])
        # texture_coordinate.UV -> vector_math_003.Vector
        nodegroup.links.new(texture_coordinate.outputs[2], vector_math_003.inputs[0])
        # vector_math_010.Vector -> vector_math_011.Vector
        nodegroup.links.new(vector_math_010.outputs[0], vector_math_011.inputs[0])
        # texture_coordinate.UV -> vector_math_002.Vector
        nodegroup.links.new(texture_coordinate.outputs[2], vector_math_002.inputs[0])
        # vector_math_006.Vector -> image_texture_006.Vector
        nodegroup.links.new(vector_math_006.outputs[0], image_texture_006.inputs[0])
        # vector_math_005.Vector -> vector_math_006.Vector
        nodegroup.links.new(vector_math_005.outputs[0], vector_math_006.inputs[0])
        # vector_math_013.Vector -> group_001.Image
        nodegroup.links.new(vector_math_013.outputs[0], group_001.inputs[0])
        # vector_math_004.Vector -> image_texture_005.Vector
        nodegroup.links.new(vector_math_004.outputs[0], image_texture_005.inputs[0])
        # vector_math_016.Vector -> vector_math_005.Vector
        nodegroup.links.new(vector_math_016.outputs[0], vector_math_005.inputs[0])
        # vector_math_015.Vector -> vector_math_004.Vector
        nodegroup.links.new(vector_math_015.outputs[0], vector_math_004.inputs[0])
        # vector_math_014.Vector -> vector_math_013.Vector
        nodegroup.links.new(vector_math_014.outputs[0], vector_math_013.inputs[1])
        # vector_math_001_1.Vector -> vector_math_003.Vector
        nodegroup.links.new(vector_math_001_1.outputs[0], vector_math_003.inputs[1])
        # vector_math_011.Vector -> vector_math_013.Vector
        nodegroup.links.new(vector_math_011.outputs[0], vector_math_013.inputs[0])
        # image_texture_005.Color -> vector_math_008.Vector
        nodegroup.links.new(image_texture_005.outputs[0], vector_math_008.inputs[0])
        # vector_math_1.Vector -> vector_math_002.Vector
        nodegroup.links.new(vector_math_1.outputs[0], vector_math_002.inputs[1])
        # image_texture_006.Color -> vector_math_007.Vector
        nodegroup.links.new(image_texture_006.outputs[0], vector_math_007.inputs[0])
        # vector_math_009.Vector -> vector_math_012.Vector
        nodegroup.links.new(vector_math_009.outputs[0], vector_math_012.inputs[0])
        # group_input_1.MicroDetailUVScale01 -> vector_math_1.Vector
        nodegroup.links.new(group_input_1.outputs[6], vector_math_1.inputs[0])
        # reroute.Output -> vector_math_014.Vector
        nodegroup.links.new(reroute.outputs[0], vector_math_014.inputs[1])
        # group_input_1.Normal -> vector_math_010.Vector
        nodegroup.links.new(group_input_1.outputs[3], vector_math_010.inputs[0])
        # group_input_1.MicroDetailUVScale02 -> vector_math_001_1.Vector
        nodegroup.links.new(group_input_1.outputs[7], vector_math_001_1.inputs[0])
        # group_input_1.Detail Normal -> vector_math_009.Vector
        nodegroup.links.new(group_input_1.outputs[4], vector_math_009.inputs[0])
        # group_input_1.DetailNormalInfluence -> vector_math_012.Vector
        nodegroup.links.new(group_input_1.outputs[5], vector_math_012.inputs[1])
        # group_001.Image -> group_output_1.Image
        nodegroup.links.new(group_001.outputs[0], group_output_1.inputs[0])
        # group_input_1.Microdetail Influence -> reroute.Input
        nodegroup.links.new(group_input_1.outputs[0], reroute.inputs[0])
        # vector_math_002.Vector -> vector_math_015.Vector
        nodegroup.links.new(vector_math_002.outputs[0], vector_math_015.inputs[0])
        # vector_math_003.Vector -> vector_math_016.Vector
        nodegroup.links.new(vector_math_003.outputs[0], vector_math_016.inputs[0])
        # mix.Result -> vector_math_015.Vector
        nodegroup.links.new(mix.outputs[0], vector_math_015.inputs[1])
        # mix.Result -> vector_math_016.Vector
        nodegroup.links.new(mix.outputs[0], vector_math_016.inputs[1])
        # vector_math_018.Vector -> vector_math_017.Vector
        nodegroup.links.new(vector_math_018.outputs[0], vector_math_017.inputs[0])
        # vector_math_019.Vector -> vector_math_017.Vector
        nodegroup.links.new(vector_math_019.outputs[0], vector_math_017.inputs[1])
        # vector_math_017.Vector -> vector_math_014.Vector
        nodegroup.links.new(vector_math_017.outputs[0], vector_math_014.inputs[0])
        # group_input_1.TintColor | Blue (Scale) -> mix.Factor
        nodegroup.links.new(group_input_1.outputs[2], mix.inputs[0])
        # vector_math_008.Vector -> vector_math_018.Vector
        nodegroup.links.new(vector_math_008.outputs[0], vector_math_018.inputs[0])
        # vector_math_007.Vector -> vector_math_019.Vector
        nodegroup.links.new(vector_math_007.outputs[0], vector_math_019.inputs[0])
        # group_input_1.TintColor | Green (MD Mask) -> reroute_001.Input
        nodegroup.links.new(group_input_1.outputs[1], reroute_001.inputs[0])
        # reroute_001.Output -> vector_math_018.Vector
        nodegroup.links.new(reroute_001.outputs[0], vector_math_018.inputs[1])
        # value_001.Value -> vector_math_019.Vector
        nodegroup.links.new(value_001.outputs[0], vector_math_019.inputs[1])

        return nodegroup


    def create(self,Data,Mat):
        CurMat = Mat.node_tree
        pBSDF = CurMat.nodes[loc('Principled BSDF')]
        pBSDF.subsurface_method = 'RANDOM_WALK_SKIN'
        pBSDF.inputs['Subsurface Weight'].default_value = 1
        pBSDF.inputs['Subsurface Scale'].default_value = .005
        pBSDF.inputs['Subsurface Radius'].default_value[0] = 1.0
        pBSDF.inputs['Subsurface Radius'].default_value[1] = 0.35
        pBSDF.inputs['Subsurface Radius'].default_value[2] = 0.2
        pBSDF.inputs['Subsurface Anisotropy'].default_value = 0.8

        sockets=bsdf_socket_names()
        #SSS/s
        #sVcol = create_node(CurMat.nodes,"ShaderNodeVertexColor", (-1400,150))
        #sSepRGB = create_node(CurMat.nodes,"ShaderNodeSeparateColor", (-1200,150))
        #sSepRGB.mode = 'RGB'

        # This value is completely arbitary in Blender 3.6 and lower. However it's tied to the assets physical size in Blender. SSS is refactored completely in upcoming Blender 4.0
        #sMultiply = create_node(CurMat.nodes,"ShaderNodeMath", (-800,150), operation = 'MULTIPLY')
        #sMultiply.inputs[1].default_value = (0.025)

        #CurMat.links.new(sVcol.outputs[0],sSepRGB.inputs[0])
        #CurMat.links.new(sSepRGB.outputs[1],sMultiply.inputs[0])
        #CurMat.links.new(sMultiply.outputs[0],pBSDF.inputs[sockets['Subsurface']])
        #pBSDF.inputs[sockets['Subsurface Color']].default_value = (0.8, 0.14908, 0.0825199, 1)
        
        if "MicroDetail" in Data:
            mdMapAImg = imageFromRelPath(Data["MicroDetail"],DepotPath=self.BasePath, ProjPath=self.ProjPath, isNormal=True)

        skinnodegroup =self.create_skin_node_group(mdMapAImg if "MicroDetail" in Data else None)
        # Node Group
        skingroup = CurMat.nodes.new("ShaderNodeGroup")
        skingroup.name = "SkinGroup"
        skingroup.node_tree = skinnodegroup
        skingroup.location = (-750,-550)
        skingroup.width = 300.0

        #Albedo/a

        if "Albedo" in Data: # should always be param has a value in the skin.mt
            aImg=imageFromRelPath(Data["Albedo"],DepotPath=self.BasePath, ProjPath=self.ProjPath)
            aImgNode = create_node(CurMat.nodes,"ShaderNodeTexImage",  (-800,450), label="Albedo", image=aImg)
            aImgNode.hide = False

        if "TintColor" in Data:
            tColor = CreateShaderNodeRGB(CurMat, Data["TintColor"],-500,250,"TintColor")
            tColor.hide=False
        
        if "TintColorMask" in Data: # should always be param has a value in the skin.mt
            tImg=imageFromRelPath(Data["TintColorMask"],DepotPath=self.BasePath, ProjPath=self.ProjPath, isNormal=False)
            tmaskNode = create_node(CurMat.nodes, "ShaderNodeTexImage", (-1800,-200), label="TintColorMask", image=tImg)
            tmaskNode.hide = False
            # Jatos new sep and maprange
            tcmSep =  create_node(CurMat.nodes, "ShaderNodeSeparateColor", (-1300,-250))
            tcmSep.mode = 'RGB'
            tcmMapRange = CurMat.nodes.new("ShaderNodeMapRange")
            tcmMapRange.interpolation_type = 'STEPPED'
            tcmMapRange.location = (-1100, -300)
            tcmMapRange.inputs[5].default_value = 4.0 #steps
            CurMat.links.new(tmaskNode.outputs[0],tcmSep.inputs[0])
            CurMat.links.new(tcmSep.outputs[1],skingroup.inputs["TintColor | Green (MD Mask)"])
            CurMat.links.new(tcmSep.outputs[2],tcmMapRange.inputs[0])
            CurMat.links.new(tcmMapRange.outputs[0],skingroup.inputs["TintColor | Blue (Scale)"])


        if "TintScale" in Data:
            tintScale = CreateShaderNodeValue(CurMat, Data["TintScale"],-500,450,"TintScale")
        else:
            tintScale = CreateShaderNodeValue(CurMat, 1.0,  -500,450,"TintScale")
        tintScale.hide=False

        tintColorGamma = CurMat.nodes.new("ShaderNodeGamma")
        tintColorGamma.location = (-500,300)
        tintColorGamma.hide=True
        tintColorGamma.inputs[1].default_value = 2.2

        albedoTintMix = create_node(CurMat.nodes,"ShaderNodeMix",(-500, 350), blend_type='MULTIPLY', label="Mix")
        albedoTintMix.data_type='RGBA'
        albedoTintMix.inputs[0].default_value = 1.0
        albedoTintMix.hide=True

        CurMat.links.new(tColor.outputs[0],tintColorGamma.inputs[0])
        CurMat.links.new(tintScale.outputs[0],albedoTintMix.inputs[0])
        CurMat.links.new(aImgNode.outputs[0],albedoTintMix.inputs[6])
        CurMat.links.new(tintColorGamma.outputs[0],albedoTintMix.inputs[7])

        #Secondary Albedo/a
        if "SecondaryAlbedo" in Data and Data["SecondaryAlbedo"]!='engine\\textures\\editor\\white.xbm':
            saImg=imageFromRelPath(Data["SecondaryAlbedo"], DepotPath=self.BasePath, ProjPath=self.ProjPath)
            saImgNode = create_node(CurMat.nodes, "ShaderNodeTexImage", (-900,550), label="Secondary Albedo", image=saImg)

            overlay = create_node(CurMat.nodes, "ShaderNodeMix", (-150,500), blend_type="OVERLAY", label="Overlay")
            overlay.data_type = "RGBA"

            if "SecondaryAlbedoInfluence" in Data:
                SecondaryAlbedoInf = CreateShaderNodeValue(CurMat, Data["SecondaryAlbedoInfluence"],-250,550,"SecondaryAlbedoInf")
                
                saMul =  create_node(CurMat.nodes, "ShaderNodeMath", (-200,520), operation = 'MULTIPLY')
                CurMat.links.new(saMul.outputs[0], overlay.inputs[0])
                CurMat.links.new(SecondaryAlbedoInf.outputs[0], saMul.inputs[0])
                CurMat.links.new(saImgNode.outputs[1], saMul.inputs[1])
            else:
                CurMat.links.new(saImgNode.outputs[1], overlay.inputs[0])
            CurMat.links.new(albedoTintMix.outputs[2], overlay.inputs[6])
            CurMat.links.new(saImgNode.outputs[0], overlay.inputs[7])
            CurMat.links.new(overlay.outputs[2], pBSDF.inputs['Base Color'])
        else:
            CurMat.links.new(albedoTintMix.outputs[2], pBSDF.inputs['Base Color'])

        #ROUGHNESS+MASK/rm

        if "Roughness" in Data:
            rImg=imageFromRelPath(Data["Roughness"],DepotPath=self.BasePath, ProjPath=self.ProjPath, isNormal=True)
            rImgNode = create_node(CurMat.nodes, "ShaderNodeTexImage", (-1800,100), label="Roughness", image=rImg)
            rImgNode.hide = False

        rmSep =  create_node(CurMat.nodes, "ShaderNodeSeparateColor", (-1300,50))
        rmSep.mode = 'RGB'

        rmMul =  create_node(CurMat.nodes, "ShaderNodeMath", (-1000,-200), operation = 'MULTIPLY')
		

        #NORMAL/n

        

        nNormalMap =  create_node(CurMat.nodes,"ShaderNodeNormalMap", (-425, -300))
		
        if "Normal" in Data:
            nImg = imageFromRelPath(Data["Normal"],DepotPath=self.BasePath, ProjPath=self.ProjPath, isNormal=True)
            nMap = create_node(CurMat.nodes, "ShaderNodeTexImage", (-1800,-500), label="Normal", image=nImg)
            nMap.hide = False
            nMap.image.colorspace_settings.name='Non-Color'
	
        if "DetailNormal" in Data:
            dnImg = imageFromRelPath(Data["DetailNormal"],DepotPath=self.BasePath, ProjPath=self.ProjPath, isNormal=True)
            dnMap = create_node(CurMat.nodes, "ShaderNodeTexImage", (-1800,-800), label="DetailNormal", image=dnImg)
            dnMap.hide = False
            dnMap.image.colorspace_settings.name='Non-Color'
			
        
        if "DetailNormalInfluence" in Data:
            nDNInfluence = CreateShaderNodeValue(CurMat, Data["DetailNormalInfluence"],-950,-800,"DetailNormalInfluence")
            nDNInfluence.hide = False

        if "MicroDetailUVScale01" in Data:
            mdScale01 = CreateShaderNodeValue(CurMat, Data["MicroDetailUVScale01"],-950,-860,"MicroDetailUVScale01")
            mdScale01.hide = False

        if "MicroDetailUVScale02" in Data:
            mdScale02 = CreateShaderNodeValue(CurMat, Data["MicroDetailUVScale02"],-950,-915,"MicroDetailUVScale02")
            mdScale02.hide = False

        if "MicroDetailInfluence" in Data:
            mdInfluence = CreateShaderNodeValue(CurMat, Data["MicroDetailInfluence"],-1250,-100,"MicroDetailInfluence")
            mdInfluence.hide = False

        if "Detailmap_Squash" in Data:
            sqshImg = imageFromRelPath(Data["Detailmap_Squash"],DepotPath=self.BasePath, ProjPath=self.ProjPath, isNormal=True)
            ndSqImgNode = create_node(CurMat.nodes, "ShaderNodeTexImage", (-2200,250), label="Detailmap_Squash", image=sqshImg)

        if "Detailmap_Stretch" in Data:
            strchImg =  imageFromRelPath(Data["Detailmap_Stretch"],DepotPath=self.BasePath, ProjPath=self.ProjPath, isNormal=True)
            ndStImg = create_node(CurMat.nodes, "ShaderNodeTexImage", (-2200,200), label="Detailmap_Stretch", image=strchImg)


        CurMat.links.new(rImgNode.outputs[0],rmSep.inputs[0])
        CurMat.links.new(rmSep.outputs[0],pBSDF.inputs['Roughness'])
        CurMat.links.new(rmSep.outputs[1],pBSDF.inputs['Metallic'])
        CurMat.links.new(rmSep.outputs[2],rmMul.inputs[0])
        
        CurMat.links.new(rmMul.outputs[0],skingroup.inputs["Microdetail Influence"])
        CurMat.links.new(mdInfluence.outputs[0],rmMul.inputs[1])

        CurMat.links.new(nMap.outputs[0],skingroup.inputs["Normal"])
        CurMat.links.new(dnMap.outputs[0],skingroup.inputs["Detail Normal"])
        CurMat.links.new(nDNInfluence.outputs[0],skingroup.inputs["DetailNormalInfluence"])

        CurMat.links.new(mdScale01.outputs[0],skingroup.inputs["MicroDetailUVScale01"])
        CurMat.links.new(mdScale02.outputs[0],skingroup.inputs["MicroDetailUVScale02"])
               
        CurMat.links.new(skingroup.outputs[0],nNormalMap.inputs[1])

        CurMat.links.new(nNormalMap.outputs[0],pBSDF.inputs['Normal'])


        #OTHER
        if "BloodColor" in Data:
            bfColor = CreateShaderNodeRGB(CurMat, Data["BloodColor"],-2200,300,"BloodColor")

        if "Bloodflow" in Data:
            bldImg = imageFromRelPath(Data["Bloodflow"],DepotPath=self.BasePath, ProjPath=self.ProjPath)
            bfImgNode = create_node(CurMat.nodes, "ShaderNodeTexImage", (-2200,350), label="Bloodflow", image=bldImg)
