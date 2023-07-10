import bpy
import os
from mathutils import Color
if __name__ != "__main__":
    from ..main.common import *

class DecalGradientmapRecolor:
    def __init__(self, BasePath,image_format):
        self.BasePath = BasePath
        self.image_format = image_format

 
    def found(self,tex):
        result = os.path.exists(os.path.join(self.BasePath, tex))
        if not result:
            print(f"Texture not found: {tex}")
        return result

    def create(self,Data,Mat):
        masktex=''
        diffAsMask = 0

        for i in range(len(Data["values"])):
            for value in Data["values"][i]:
                #print(value)
                if value == "DiffuseTexture":
                    difftex = Data["values"][i]["DiffuseTexture"]["DepotPath"]['$value'][:-3]+self.image_format
                   # print(f"Diffuse Texture path is:  {difftex}")
                if value == "GradientMap":
                    gradmap = Data["values"][i]["GradientMap"]["DepotPath"]['$value'][:-3]+self.image_format
                if value == "MaskTexture":
                    masktex = Data["values"][i]["MaskTexture"]["DepotPath"]['$value'][:-3]+self.image_format
                if value == "DiffuseTextureAsMaskTexture":
                    diffAsMask = Data["values"][i]["DiffuseTextureAsMaskTexture"]

        CurMat = Mat.node_tree
        Prin_BSDF=CurMat.nodes['Principled BSDF']

        if self.found(difftex) and self.found(gradmap):
            diff_image_node = CreateShaderNodeTexImage(CurMat,os.path.join(self.BasePath, difftex),-800, 300,'DiffuseTexture',self.image_format)
            diff_image_node.image.colorspace_settings.name = 'Linear'
            grad_image_node = CreateShaderNodeTexImage(CurMat,os.path.join(self.BasePath , gradmap),-800, 0,'GradientMap',self.image_format)  
            
            # Get image dimensions
            image_width = grad_image_node.image.size[0]
            
            # Calculate stop positions
            stop_positions = [i / (image_width) for i in range(image_width)]
            print(len(stop_positions))
            row_index = 0
            # Get colors from the row
            colors = []
            for x in range(image_width):
                pixel_data = grad_image_node.image.pixels[(row_index * image_width + x) * 4: (row_index * image_width + x) * 4 + 3]
                color = Color()
                color.r, color.g, color.b = pixel_data
                colors.append(color)
                # Create ColorRamp node
            color_ramp_node = CurMat.nodes.new('ShaderNodeValToRGB')
            color_ramp_node.location = (-400, 250)
        
            # Set the stops
            color_ramp_node.color_ramp.elements.remove(color_ramp_node.color_ramp.elements[1])
            for i, color in enumerate(colors):
                if i>0:
                    element = color_ramp_node.color_ramp.elements.new(i / (len(colors) ))
                else:
                    element = color_ramp_node.color_ramp.elements[0]
                element.color = (color.r, color.g, color.b, 1.0)
                element.position = stop_positions[i]
                
            color_ramp_node.color_ramp.interpolation = 'CONSTANT' 

            CurMat.links.new(diff_image_node.outputs[0], color_ramp_node.inputs[0])
            CurMat.links.new(color_ramp_node.outputs[0], Prin_BSDF.inputs['Base Color'])

            #if 'alpha' in Data.keys():
             #   mulNode1.inputs[0].default_value = float(Data["alpha"])

            if diffAsMask:
                #CurMat.links.new(diff_image_node.outputs[0],mulNode1.inputs[1])
                CurMat.links.new(diff_image_node.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Alpha'])
                #CurMat.links.new(dImgNode.outputs[1],CurMat.nodes['Principled BSDF'].inputs['Alpha'])
            else:
                if self.found(masktex):
                    mask_image_node = CreateShaderNodeTexImage(CurMat,os.path.join(self.BasePath , masktex),-800, -300,'MaskTexture',self.image_format)
                    CurMat.links.new(mask_image_node.outputs[0], Prin_BSDF.inputs['Alpha'])
                else:
                    CurMat.links.new(diff_image_node.outputs[1], Prin_BSDF.inputs['Alpha'])


                   #CurMat.links.new(dImgNode.outputs[1],CurMat.nodes['Principled BSDF'].inputs['Alpha'])
        else:
            CurMat.nodes['Principled BSDF'].inputs['Alpha'].default_value = 0


# The above is  the code thats for the import plugin below is to allow testing/dev, you can run this file to import something

if __name__ == "__main__":
    import sys
    sys.path.append("F://CPmod//ImportPluginGIT//i_scene_cp77_gltf//material_types")
    sys.path.append("F://CPmod//ImportPluginGIT//i_scene_cp77_gltf//main")
    from common import *
    import os
    import json
    filepath="F:\\CPmod\\bottles\\source\\raw\\base\\surfaces\\textures\\decals\\graffiti\\tyger_claws\\tyger_claws_07.mi.json"
    fileBasePath = os.path.splitext(filepath)[0]
    file = open(filepath,mode='r')
    obj = json.loads(file.read())
    BasePath = "F:\\CPmod\\bottles\\source\\raw"

    bpyMat = bpy.data.materials.new("TestMat")
    bpyMat.use_nodes = True
    bpyMat.blend_method='HASHED'
    rawMat=obj["Data"]["RootChunk"]
    vehicleLights = DecalGradientmapRecolor(BasePath,"png")
    vehicleLights.create(rawMat,bpyMat)

