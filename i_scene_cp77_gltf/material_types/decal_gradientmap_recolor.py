import bpy
import os
import math
from mathutils import Color
if __name__ != "__main__":
    from ..main.common import *

class DecalGradientmapRecolor:
    def __init__(self, BasePath,image_format, ProjPath):
        self.BasePath = BasePath
        self.ProjPath = ProjPath
        self.image_format = image_format
 
    def found(self,tex):
        result = os.path.exists(os.path.join(self.BasePath, tex)[:-3]+ self.image_format)
        if not result:
            result = os.path.exists(os.path.join(self.ProjPath, tex)[:-3]+ self.image_format)
            if not result:
                print(f"Texture not found: {tex}")
        return result

    def create(self,Data,Mat):
        masktex=''
        difftex=''
        diffAsMask = 0

        for i in range(len(Data["values"])):
            for value in Data["values"][i]:
                #print(value)
                if value == "DiffuseTexture":
                    difftex = Data["values"][i]["DiffuseTexture"]["DepotPath"]['$value']
                   # print(f"Diffuse Texture path is:  {difftex}")
                if value == "GradientMap":
                    gradmap = Data["values"][i]["GradientMap"]["DepotPath"]['$value']
                if value == "MaskTexture":
                    masktex = Data["values"][i]["MaskTexture"]["DepotPath"]['$value']
                if value == "DiffuseTextureAsMaskTexture":
                    diffAsMask = Data["values"][i]["DiffuseTextureAsMaskTexture"]

        CurMat = Mat.node_tree
        pBSDF=CurMat.nodes[loc('Principled BSDF')]

        if self.found(difftex) and self.found(gradmap):
            diffImg = imageFromRelPath(difftex,self.image_format, DepotPath=self.BasePath, ProjPath=self.ProjPath)
            diff_image_node = create_node(CurMat.nodes,"ShaderNodeTexImage",  (-800,-300), label="DiffuseTexture", image=diffImg)
            vers=bpy.app.version
            if vers[0]<4:
                diff_image_node.image.colorspace_settings.name = 'Linear'
            else:
                diff_image_node.image.colorspace_settings.name = 'Linear Rec.709'
            gradImg = imageFromRelPath(gradmap,self.image_format, DepotPath=self.BasePath, ProjPath=self.ProjPath)
            grad_image_node = create_node(CurMat.nodes,"ShaderNodeTexImage",  (-800,0), label="GradientMap", image=gradImg)
            
            
            color_ramp_node=CreateGradMapRamp(CurMat, grad_image_node)

            CurMat.links.new(diff_image_node.outputs[0], color_ramp_node.inputs[0])
            CurMat.links.new(color_ramp_node.outputs[0], pBSDF.inputs['Base Color'])

            #if 'alpha' in Data.keys():
             #   mulNode1.inputs[0].default_value = float(Data["alpha"])

            if diffAsMask:
                #CurMat.links.new(diff_image_node.outputs[0],mulNode1.inputs[1])
                
                alpha_ramp = create_node(CurMat.nodes,"ShaderNodeValToRGB", (-400,-350),label='MaskRamp')
                alpha_ramp.color_ramp.elements[0].position=0.004
                CurMat.links.new(diff_image_node.outputs[0],alpha_ramp.inputs[0])
                CurMat.links.new(alpha_ramp.outputs[0],pBSDF.inputs['Alpha'])
                #CurMat.links.new(dImgNode.outputs[1],pBSDF.inputs['Alpha'])
            else:
                if self.found(masktex):
                    maskImg = imageFromRelPath(masktex,self.image_format, DepotPath=self.BasePath, ProjPath=self.ProjPath)
                    mask_image_node = create_node(CurMat.nodes,"ShaderNodeTexImage",  (-800,-100), label="MaskTexture", image=maskImg)
                    CurMat.links.new(mask_image_node.outputs[0], pBSDF.inputs['Alpha'])
                else:
                    CurMat.links.new(diff_image_node.outputs[1], pBSDF.inputs['Alpha'])
        else:
            pBSDF.inputs['Alpha'].default_value = 0


# The above is  the code thats for the import plugin below is to allow testing/dev, you can run this file to import something

if __name__ == "__main__":
    import sys
    sys.path.append("F://CPmod//ImportPluginGIT//i_scene_cp77_gltf//material_types")
    sys.path.append("F://CPmod//ImportPluginGIT//i_scene_cp77_gltf//main")
    from common import *
    import os
    import json
    filepath="F:\\CPmod\\deleteme4\\source\\raw\\base\\surfaces\\textures\\decals\\graffiti\\tyger_claws\\tyger_claws_08.mi.json"
    fileBasePath = os.path.splitext(filepath)[0]
    file = open(filepath,mode='r')
    obj = json.loads(file.read())
    BasePath = "F:\\MaterialDepots\\source\\raw"
    ProjPath = "F:\\CPmod\\deleteme4\\source\\raw\\"

    bpyMat = bpy.data.materials.new("TestMat")
    bpyMat.use_nodes = True
    bpyMat.blend_method='HASHED'
    rawMat=obj["Data"]["RootChunk"]
    vehicleLights = DecalGradientmapRecolor(BasePath,"png",ProjPath)
    vehicleLights.create(rawMat,bpyMat)

