import bpy
import os
if __name__ != "__main__":
    from ..main.common import *

import json

class Hologram:
    def __init__(self, BasePath,image_format, ProjPath):
        self.BasePath = BasePath
        self.ProjPath = ProjPath
        self.image_format = image_format

    def create(self,Data,Mat):
        mat = Mat
        mat.use_nodes = True
        vers = bpy.app.version
        if vers[0] == 4 and vers[1] <= 2:
            Mat.shadow_method = 'HASHED'
        mat.blend_method = 'HASHED'
        sockets=bsdf_socket_names()

        holo_blue_002 = mat.node_tree
        #start with a clean node tree
        for node in holo_blue_002.nodes:
            holo_blue_002.nodes.remove(node)
        #holo_blue_002 interface
        
        #initialize holo_blue_002 nodes
        #node Wave Texture.001
        wave_texture_001 = holo_blue_002.nodes.new("ShaderNodeTexWave")
        wave_texture_001.name = "Wave Texture"
        wave_texture_001.bands_direction = 'Z'
        wave_texture_001.rings_direction = 'X'
        wave_texture_001.wave_profile = 'SIN'
        wave_texture_001.wave_type = 'BANDS'
        #Scale
        wave_texture_001.inputs[1].default_value = 1.0
        #Distortion
        wave_texture_001.inputs[2].default_value = 0.0
        #Detail
        wave_texture_001.inputs[3].default_value = 0.5000001192092896
        #Detail Scale
        wave_texture_001.inputs[4].default_value = 1.0
        #Detail Roughness
        wave_texture_001.inputs[5].default_value = 0.0
        #Phase Offset
        wave_texture_001.inputs[6].default_value = 0.0
        
        #node Color Ramp.001
        color_ramp_001 = holo_blue_002.nodes.new("ShaderNodeValToRGB")
        color_ramp_001.name = "Color Ramp"
        color_ramp_001.color_ramp.color_mode = 'RGB'
        color_ramp_001.color_ramp.hue_interpolation = 'NEAR'
        color_ramp_001.color_ramp.interpolation = 'LINEAR'
        
        #initialize color ramp elements
        color_ramp_001.color_ramp.elements.remove(color_ramp_001.color_ramp.elements[0])
        color_ramp_001_cre_0 = color_ramp_001.color_ramp.elements[0]
        color_ramp_001_cre_0.position = 0.0
        color_ramp_001_cre_0.alpha = 1.0
        color_ramp_001_cre_0.color = (0.0, 0.0, 0.0, 1.0)

        color_ramp_001_cre_1 = color_ramp_001.color_ramp.elements.new(0.04545455798506737)
        color_ramp_001_cre_1.alpha = 1.0
        color_ramp_001_cre_1.color = (1.0, 1.0, 1.0, 1.0)

        
        #node Math.001
        math_001 = holo_blue_002.nodes.new("ShaderNodeMath")
        math_001.name = "Math"
        math_001.operation = 'MULTIPLY'
        math_001.use_clamp = False
        #Value_001
        math_001.inputs[1].default_value = 0.3399999737739563
        #Value_002
        math_001.inputs[2].default_value = 0.5
        
        #node Texture Coordinate.001
        texture_coordinate_001 = holo_blue_002.nodes.new("ShaderNodeTexCoord")
        texture_coordinate_001.name = "Texture Coordinate"
        texture_coordinate_001.from_instancer = False
        
        #node Mapping.001
        mapping_001 = holo_blue_002.nodes.new("ShaderNodeMapping")
        mapping_001.name = "Mapping"
        mapping_001.vector_type = 'POINT'
        #Location
        mapping_001.inputs[1].default_value = (0.0, 0.0, 0.0)
        #Rotation
        mapping_001.inputs[2].default_value = (0.0, 0.0, 0.0)
        #Scale
        mapping_001.inputs[3].default_value = (1.0, 1.0, 50.0)
        
        #node Image Texture
        image_texture_001 = holo_blue_002.nodes.new("ShaderNodeTexImage")
        image_texture_001.name = "Image Texture"
        image_texture_001.extension = 'REPEAT'
        image_texture_001.image_user.frame_current = 1
        image_texture_001.image_user.frame_duration = 1
        image_texture_001.image_user.frame_offset = -1
        image_texture_001.image_user.frame_start = 1
        image_texture_001.image_user.tile = 0
        image_texture_001.image_user.use_auto_refresh = False
        image_texture_001.image_user.use_cyclic = False
        image_texture_001.interpolation = 'Linear'
        image_texture_001.projection = 'FLAT'
        image_texture_001.projection_blend = 0.0
        if "Diffuse" in Data:
            image_texture_001.image = imageFromRelPath(Data["Diffuse"],self.image_format, DepotPath=self.BasePath, ProjPath=self.ProjPath)
        
        elif "Scanline" in Data:
            image_texture_001.image = imageFromRelPath(Data["Scanline"],self.image_format, DepotPath=self.BasePath, ProjPath=self.ProjPath)
        #Vector
        image_texture_001.inputs[0].default_value = (0.0, 0.0, 0.0)
        
        #node Geometry.001
        geometry_001 = holo_blue_002.nodes.new("ShaderNodeNewGeometry")
        geometry_001.name = "Geometry.001"
        
        #node Material Output.001
        material_output_001 = holo_blue_002.nodes.new("ShaderNodeOutputMaterial")
        material_output_001.name = "Material Output.001"
        material_output_001.is_active_output = True
        material_output_001.target = 'ALL'
        #Displacement
        material_output_001.inputs[2].default_value = (0.0, 0.0, 0.0)
        #Thickness
        material_output_001.inputs[3].default_value = 0.0
        
        #node Mix Shader.002
        mix_shader_002 = holo_blue_002.nodes.new("ShaderNodeMixShader")
        mix_shader_002.name = "Mix Shader.002"
        
        #node Mix.001
        mix_001 = holo_blue_002.nodes.new("ShaderNodeMix")
        mix_001.name = "Mix.001"
        mix_001.blend_type = 'MULTIPLY'
        mix_001.clamp_factor = True
        mix_001.clamp_result = False
        mix_001.data_type = 'RGBA'
        mix_001.factor_mode = 'UNIFORM'
        #Factor_Float
        mix_001.inputs[0].default_value = 1.0
        #Factor_Vector
        mix_001.inputs[1].default_value = (0.5, 0.5, 0.5)
        #A_Float
        mix_001.inputs[2].default_value = 0.0
        #B_Float
        mix_001.inputs[3].default_value = 0.0
        #A_Vector
        mix_001.inputs[4].default_value = (0.0, 0.0, 0.0)
        #B_Vector
        mix_001.inputs[5].default_value = (0.0, 0.0, 0.0)
        #A_Rotation
        mix_001.inputs[8].default_value = (0.0, 0.0, 0.0)
        #B_Rotation
        mix_001.inputs[9].default_value = (0.0, 0.0, 0.0)
        
        #node Principled BSDF
        principled_bsdf_001 = holo_blue_002.nodes.new("ShaderNodeBsdfPrincipled")
        principled_bsdf_001.name = "Principled BSDF"
        principled_bsdf_001.distribution = 'GGX'
        principled_bsdf_001.subsurface_method = 'RANDOM_WALK_SKIN'
        #Metallic
        principled_bsdf_001.inputs[loc('Metallic')].default_value = 0.0
        #Roughness
        principled_bsdf_001.inputs[loc('Roughness')].default_value = 1.0
        #IOR
        principled_bsdf_001.inputs[loc('IOR')].default_value = 1.4500000476837158
        #Normal
        principled_bsdf_001.inputs[loc('Normal')].default_value = (0.0, 0.0, 0.0)
        #Subsurface Weight
        principled_bsdf_001.inputs[loc('Subsurface Weight')].default_value = 0.0
        #Subsurface Radius
        principled_bsdf_001.inputs[loc('Subsurface Radius')].default_value = (1.0, 0.20000000298023224, 0.10000000149011612)
        #Subsurface Scale
        principled_bsdf_001.inputs[loc('Subsurface Scale')].default_value = 0.05000000074505806
        #Subsurface IOR
        principled_bsdf_001.inputs[loc('Subsurface IOR')].default_value = 1.399999976158142
        #Subsurface Anisotropy
        principled_bsdf_001.inputs[loc('Subsurface Anisotropy')].default_value = 0.0
        #Specular IOR Level
        principled_bsdf_001.inputs[loc('Specular IOR Level')].default_value = 0.0
        #Specular Tint
        principled_bsdf_001.inputs[loc('Specular Tint')].default_value = (1.0, 1.0, 1.0, 1.0)
        #Anisotropic
        principled_bsdf_001.inputs[loc('Anisotropic')].default_value = 0.0
        #Anisotropic Rotation
        principled_bsdf_001.inputs[loc('Anisotropic Rotation')].default_value = 0.0
        #Tangent
        principled_bsdf_001.inputs[loc('Tangent')].default_value = (0.0, 0.0, 0.0)
        #Transmission Weight
        principled_bsdf_001.inputs[loc('Transmission Weight')].default_value = 0.0
        #Coat Weight
        principled_bsdf_001.inputs[loc('Coat Weight')].default_value = 0.0
        #Coat Roughness
        principled_bsdf_001.inputs[loc('Coat Roughness')].default_value = 0.029999999329447746
        #Coat IOR
        principled_bsdf_001.inputs[loc('Coat IOR')].default_value = 1.5
        #Coat Tint
        principled_bsdf_001.inputs[loc('Coat Tint')].default_value = (1.0, 1.0, 1.0, 1.0)
        #Coat Normal
        principled_bsdf_001.inputs[loc('Coat Normal')].default_value = (0.0, 0.0, 0.0)
        #Sheen Weight
        principled_bsdf_001.inputs[loc('Sheen Weight')].default_value = 0.0
        #Sheen Roughness
        principled_bsdf_001.inputs[loc('Sheen Roughness')].default_value = 0.5
        #Sheen Tint
        principled_bsdf_001.inputs[loc('Sheen Tint')].default_value = (1.0, 1.0, 1.0, 1.0)
        #Emission Strength
        principled_bsdf_001.inputs[loc('Emission Strength')].default_value = 30.0
                
        #node Mix Shader
        mix_shader_003 = holo_blue_002.nodes.new("ShaderNodeMixShader")
        mix_shader_003.name = "Mix Shader"
        
        #node Fresnel
        fresnel_001 = holo_blue_002.nodes.new("ShaderNodeFresnel")
        fresnel_001.name = "Fresnel"
        #IOR
        fresnel_001.inputs[0].default_value = 0.8000001907348633
        #Normal
        fresnel_001.inputs[1].default_value = (0.0, 0.0, 0.0)
        
        #node RGB Curves
        rgb_curves = holo_blue_002.nodes.new("ShaderNodeRGBCurve")
        rgb_curves.name = "RGB Curves"
        #mapping settings
        rgb_curves.mapping.extend = 'EXTRAPOLATED'
        rgb_curves.mapping.tone = 'STANDARD'
        rgb_curves.mapping.black_level = (0.0, 0.0, 0.0)
        rgb_curves.mapping.white_level = (1.0, 1.0, 1.0)
        rgb_curves.mapping.clip_min_x = 0.0
        rgb_curves.mapping.clip_min_y = 0.0
        rgb_curves.mapping.clip_max_x = 1.0
        rgb_curves.mapping.clip_max_y = 1.0
        rgb_curves.mapping.use_clip = True
        #curve 0
        rgb_curves_curve_0 = rgb_curves.mapping.curves[0]
        rgb_curves_curve_0_point_0 = rgb_curves_curve_0.points[0]
        rgb_curves_curve_0_point_0.location = (0.0, 0.0)
        rgb_curves_curve_0_point_0.handle_type = 'AUTO'
        rgb_curves_curve_0_point_1 = rgb_curves_curve_0.points[1]
        rgb_curves_curve_0_point_1.location = (1.0, 1.0)
        rgb_curves_curve_0_point_1.handle_type = 'AUTO'
        #curve 1
        rgb_curves_curve_1 = rgb_curves.mapping.curves[1]
        rgb_curves_curve_1_point_0 = rgb_curves_curve_1.points[0]
        rgb_curves_curve_1_point_0.location = (0.0, 0.0)
        rgb_curves_curve_1_point_0.handle_type = 'AUTO'
        rgb_curves_curve_1_point_1 = rgb_curves_curve_1.points[1]
        rgb_curves_curve_1_point_1.location = (1.0, 1.0)
        rgb_curves_curve_1_point_1.handle_type = 'AUTO'
        #curve 2
        rgb_curves_curve_2 = rgb_curves.mapping.curves[2]
        rgb_curves_curve_2_point_0 = rgb_curves_curve_2.points[0]
        rgb_curves_curve_2_point_0.location = (0.0, 0.0)
        rgb_curves_curve_2_point_0.handle_type = 'AUTO'
        rgb_curves_curve_2_point_1 = rgb_curves_curve_2.points[1]
        rgb_curves_curve_2_point_1.location = (1.0, 1.0)
        rgb_curves_curve_2_point_1.handle_type = 'AUTO'
        #curve 3
        rgb_curves_curve_3 = rgb_curves.mapping.curves[3]
        rgb_curves_curve_3_point_0 = rgb_curves_curve_3.points[0]
        rgb_curves_curve_3_point_0.location = (0.0, 0.0)
        rgb_curves_curve_3_point_0.handle_type = 'AUTO'
        rgb_curves_curve_3_point_1 = rgb_curves_curve_3.points[1]
        rgb_curves_curve_3_point_1.location = (0.2863638997077942, 0.787500262260437)
        rgb_curves_curve_3_point_1.handle_type = 'AUTO'
        rgb_curves_curve_3_point_2 = rgb_curves_curve_3.points.new(1.0, 1.0)
        rgb_curves_curve_3_point_2.handle_type = 'AUTO'
        #update curve after changes
        rgb_curves.mapping.update()
        #Fac
        rgb_curves.inputs[0].default_value = 1.0
        
        #node RGB
        rgb = holo_blue_002.nodes.new("ShaderNodeRGB")
        rgb.name = "RGB"
        if "DotsColor" in Data:
            color=Data["DotsColor"]
            rgb.outputs[0].default_value =(float(color["Red"])/255,float(color["Green"])/255,float(color["Blue"])/255,float(color["Alpha"])/255)

        
        #node Transparent BSDF.001
        transparent_bsdf_001 = holo_blue_002.nodes.new("ShaderNodeBsdfTransparent")
        transparent_bsdf_001.name = "Transparent BSDF"
        #Color
        transparent_bsdf_001.inputs[0].default_value = (1.0, 1.0, 1.0, 1.0)
        #Weight
        transparent_bsdf_001.inputs[1].default_value = 0.0
        
        
        #Set locations
        wave_texture_001.location = (-864.6965942382812, -250)
        color_ramp_001.location = (-604.9642944335938, -250)
        math_001.location = (-284.80303955078125, -250)
        texture_coordinate_001.location = (-1405.193115234375, -250)
        mapping_001.location = (-1146.6962890625, -250)
        image_texture_001.location = (-1000, 0)
        geometry_001.location = (432.47210693359375, 228.909423828125)
        material_output_001.location = (1889.980224609375,-319.284423828125)
        mix_shader_002.location = (1520.482177734375, -206.953857421875)
        mix_001.location = (-477.52105712890625, 136.946044921875)
        principled_bsdf_001.location = (-19.76519775390625, 0)
        mix_shader_003.location = (821.0979614257812, -222.9808349609375)
        fresnel_001.location = (700, 100)
        rgb_curves.location = (1061.873046875, 217.35791015625)
        rgb.location = (-1000, 263.918212890625)
        transparent_bsdf_001.location = (558.595947265625, -400.0)
        
        #Set dimensions
        wave_texture_001.width, wave_texture_001.height = 150.0, 100.0
        color_ramp_001.width, color_ramp_001.height = 240.0, 100.0
        math_001.width, math_001.height = 140.0, 100.0
        texture_coordinate_001.width, texture_coordinate_001.height = 140.0, 100.0
        mapping_001.width, mapping_001.height = 140.0, 100.0
        image_texture_001.width, image_texture_001.height = 240.0, 100.0
        geometry_001.width, geometry_001.height = 140.0, 100.0
        material_output_001.width, material_output_001.height = 140.0, 100.0
        mix_shader_002.width, mix_shader_002.height = 140.0, 100.0
        mix_001.width, mix_001.height = 151.5238037109375, 100.0
        principled_bsdf_001.width, principled_bsdf_001.height = 240.0, 100.0
        mix_shader_003.width, mix_shader_003.height = 140.0, 100.0
        fresnel_001.width, fresnel_001.height = 140.0, 100.0
        rgb_curves.width, rgb_curves.height = 240.0, 100.0
        rgb.width, rgb.height = 140.0, 100.0
        transparent_bsdf_001.width, transparent_bsdf_001.height = 140.0, 100.0
        
        #initialize holo_blue_002 links
        #mix_shader_002.Shader -> material_output_001.Surface
        holo_blue_002.links.new(mix_shader_002.outputs[0], material_output_001.inputs[0])
        #mapping_001.Vector -> wave_texture_001.Vector
        holo_blue_002.links.new(mapping_001.outputs[0], wave_texture_001.inputs[0])
        #math_001.Value -> principled_bsdf_001.Alpha
        holo_blue_002.links.new(math_001.outputs[0], principled_bsdf_001.inputs[4])
        #wave_texture_001.Color -> color_ramp_001.Fac
        holo_blue_002.links.new(wave_texture_001.outputs[0], color_ramp_001.inputs[0])
        #mix_001.Result -> principled_bsdf_001.Base Color
        holo_blue_002.links.new(mix_001.outputs[2], principled_bsdf_001.inputs[0])
        #mix_001.Result -> principled_bsdf_001.Emission Color
        holo_blue_002.links.new(mix_001.outputs[2], principled_bsdf_001.inputs[27])
        #color_ramp_001.Color -> math_001.Value
        holo_blue_002.links.new(color_ramp_001.outputs[0], math_001.inputs[0])
        #image_texture_001.Color -> mix_001.B
        holo_blue_002.links.new(image_texture_001.outputs[0], mix_001.inputs[7])
        #geometry_001.Backfacing -> mix_shader_003.Fac
        holo_blue_002.links.new(geometry_001.outputs[6], mix_shader_003.inputs[0])
        #mix_shader_003.Shader -> mix_shader_002.Shader
        holo_blue_002.links.new(mix_shader_003.outputs[0], mix_shader_002.inputs[2])
        #transparent_bsdf_001.BSDF -> mix_shader_003.Shader
        holo_blue_002.links.new(transparent_bsdf_001.outputs[0], mix_shader_003.inputs[2])
        #principled_bsdf_001.BSDF -> mix_shader_003.Shader
        holo_blue_002.links.new(principled_bsdf_001.outputs[0], mix_shader_003.inputs[1])
        #transparent_bsdf_001.BSDF -> mix_shader_002.Shader
        holo_blue_002.links.new(transparent_bsdf_001.outputs[0], mix_shader_002.inputs[1])
        #texture_coordinate_001.Object -> mapping_001.Vector
        holo_blue_002.links.new(texture_coordinate_001.outputs[3], mapping_001.inputs[0])
        #fresnel_001.Fac -> rgb_curves.Color
        holo_blue_002.links.new(fresnel_001.outputs[0], rgb_curves.inputs[1])
        #rgb_curves.Color -> mix_shader_002.Fac
        holo_blue_002.links.new(rgb_curves.outputs[0], mix_shader_002.inputs[0])
        #rgb.Color -> mix_001.A
        holo_blue_002.links.new(rgb.outputs[0], mix_001.inputs[6])
    

    
# The above is  the code thats for the import plugin below is to allow testing/dev, you can run this file to import something
# test with base\prefabs\environment\decoration\_decoration_set\building_deco\kabuki\wat_kab_market_fish.ent

if __name__ == "__main__":
    import sys
    sys.path.append("C://CPmod//Plugin_GIT//Cyberpunk-Blender-add-on//i_scene_cp77_gltf//material_types")
    sys.path.append("C://CPmod//Plugin_GIT//Cyberpunk-Blender-add-on//i_scene_cp77_gltf//main")
    print(sys.path )
    from common import *
    import os
    import json
    filepath="C:\\CPMod\\carps\\source\\raw\\base\\environment\\decoration\\misc\\sculptures\\dashi_carp\\textures\\fx_dashi_carp_holo_blue_fins.mi.json"
    #filepath="F:\\CPmod\\judysApt\\source\\raw\\base\\surfaces\\textures\\decals\\dirt\\glass_shatter_01.mi.json"
    fileBasePath = os.path.splitext(filepath)[0]
    file = open(filepath,mode='r')
    obj = json.loads(file.read())
    BasePath = "C:\\CPMod\\carps\\source\\raw"

    bpyMat = bpy.data.materials.new("TestMat")
    bpyMat.use_nodes = True
    bpyMat.blend_method='HASHED'
    rawMat=obj["Data"]["RootChunk"]
    HologramTest = Hologram(BasePath,"png",BasePath)
    HologramTest.create(rawMat,bpyMat)

