import bpy
import os
import math
if __name__ != "__main__":
    from ..main.common import *

def to_gam(c):
    if c < 0.0031308:
        srgb = 0.0 if c < 0.0 else c * 12.92
    else:
        srgb = 1.055 * math.pow(c, 1.0 / 2.4) - 0.055
    return max(min(int(srgb * 255 + 0.5), 255), 0)/255

class Decal:
    def __init__(self, BasePath,image_format):
        self.BasePath = BasePath
        self.image_format = image_format

    def create(self,Data,Mat):
        difftex=None
        DiffuseTextureAsMaskTexture=0
        RoughnessTexture = None
        NormalTexture = None
        DiffuseColor = None
        DiffuseAlpha = None
        MetalnessTexture = None
        
        for i in range(len(Data["values"])):
            
                if "DiffuseTexture" in Data["values"][i].keys():
                    difftex = Data["values"][i]["DiffuseTexture"]["DepotPath"]['$value'][:-3]+self.image_format
                    print("Diffuse Texture path is: ", difftex)
                elif "DiffuseTextureAsMaskTexture" in Data["values"][i].keys():
                    DiffuseTextureAsMaskTexture = Data["values"][i]["DiffuseTextureAsMaskTexture"]
                    print("DiffuseTextureAsMaskTexture  is: ",Data["values"][i]["DiffuseTextureAsMaskTexture"])
                elif "DiffuseColor" in Data["values"][i].keys():
                    DiffuseColor = Data["values"][i]["DiffuseColor"]
                    print("Diffuse Texture path is:  ",Data["values"][i]["DiffuseColor"])
                elif "DiffuseAlpha" in Data["values"][i].keys():
                    DiffuseAlpha = Data["values"][i]["DiffuseAlpha"]
                    print("DiffuseAlpha is:  ",Data["values"][i]["DiffuseAlpha"])
                elif "RoughnessTexture" in Data["values"][i].keys():
                    RoughnessTexture = Data["values"][i]["RoughnessTexture"]["DepotPath"]['$value'][:-3]+self.image_format
                    print("Roughness Texture path is:  ",Data["values"][i]["RoughnessTexture"])
                elif "NormalTexture" in Data["values"][i].keys():
                    NormalTexture = Data["values"][i]["NormalTexture"]["DepotPath"]['$value'][:-3]+self.image_format
                    print("Normal Texture path is:  ",Data["values"][i]["NormalTexture"])
                elif "MetalnessTexture" in Data["values"][i].keys():
                    MetalnessTexture = Data["values"][i]["MetalnessTexture"]["DepotPath"]['$value'][:-3]+self.image_format
                    print("Metalness Texture path is:  ",Data["values"][i]["MetalnessTexture"])
                

        CurMat = Mat.node_tree
        Prin_BSDF=CurMat.nodes['Principled BSDF']
        Prin_BSDF.inputs['Specular'].default_value = 0.5
        TexCoordinate = CurMat.nodes.new("ShaderNodeTexCoord")
        TexCoordinate.location = (-1000,300)
        if difftex and os.path.exists(os.path.join(self.BasePath ,difftex)):
            dImgNode = CreateShaderNodeTexImage(CurMat,os.path.join(self.BasePath ,difftex),-800,300,'DiffuseTexture',self.image_format)
            RGBnode = CurMat.nodes.new("ShaderNodeRGB")
            RGBnode.location = (-700,500)
            if DiffuseColor:
                Red=(DiffuseColor['Red']/255)
                Green=(DiffuseColor['Green']/255)
                Blue=(DiffuseColor['Blue']/255)
                Alpha=(DiffuseColor['Alpha']/255)
                RGBnode.outputs[0].default_value=(Red,Green,Blue,Alpha)
            else:
                RGBnode.outputs[0].default_value=(1,1,1,1)   
            mulNode = CurMat.nodes.new("ShaderNodeMixRGB")
            mulNode.blend_type = 'MULTIPLY'
            mulNode.inputs[0].default_value=1.0
            mulNode.location = (-400,300)
            CurMat.links.new(dImgNode.outputs[0],mulNode.inputs[2])
            CurMat.links.new(RGBnode.outputs[0],mulNode.inputs[1])
            CurMat.links.new(mulNode.outputs[0],Prin_BSDF.inputs['Base Color'])
            CurMat.links.new(TexCoordinate.outputs[0],dImgNode.inputs[0])
            mulNode1 = CurMat.nodes.new("ShaderNodeMath")
            mulNode1.operation = 'MULTIPLY'
            mulNode1.location = (-400,100)
            if 'alpha' in Data.keys():
                    DiffuseAlpha=float(Data["alpha"])

            if DiffuseAlpha:                
                mulNode1.inputs[0].default_value = DiffuseAlpha
            else:
                mulNode1.inputs[0].default_value = 1.0

            if 'enableMask' in Data.keys():
                if Data["enableMask"] and DiffuseTextureAsMaskTexture==None:
                    DiffuseTextureAsMaskTexture=0
                else:
                    DiffuseTextureAsMaskTexture=1
                     
            if DiffuseTextureAsMaskTexture>0:
                CurMat.links.new(dImgNode.outputs[0],mulNode1.inputs[1])
            else:
                CurMat.links.new(dImgNode.outputs[1],mulNode1.inputs[1])
            CurMat.links.new(mulNode1.outputs[0],Prin_BSDF.inputs['Alpha'])
        else:
            CurMat.nodes['Principled BSDF'].inputs['Alpha'].default_value = 0
            print(f"Texture is not found: {difftex}")
        if RoughnessTexture and os.path.exists(os.path.join(self.BasePath ,RoughnessTexture)):
            rImgNode = CreateShaderNodeTexImage(CurMat,os.path.join(self.BasePath ,RoughnessTexture),-800,0,'RoughnessTexture',self.image_format)
            rImgNode.image.colorspace_settings.name = 'Non-Color'
            reroute = CurMat.nodes.new(type="NodeReroute")
            reroute.location = (-335, -100)
            CurMat.links.new(rImgNode.outputs[0],reroute.inputs[0])
            CurMat.links.new(reroute.outputs[0],Prin_BSDF.inputs['Roughness'])
            CurMat.links.new(TexCoordinate.outputs[0],rImgNode.inputs[0])

        if NormalTexture and os.path.exists(os.path.join(self.BasePath ,NormalTexture)):
            nImgNode = CreateShaderNodeTexImage(CurMat,os.path.join(self.BasePath ,NormalTexture),-800,-300,'NormalTexture',self.image_format)
            nImgNode.image.colorspace_settings.name = 'Non-Color'
            toNormalNode = CurMat.nodes.new('ShaderNodeNormalMap')
            toNormalNode.location = (-400,-120)
            CurMat.links.new(nImgNode.outputs[0],toNormalNode.inputs[1])
            CurMat.links.new(toNormalNode.outputs[0],Prin_BSDF.inputs['Normal'])
            CurMat.links.new(TexCoordinate.outputs[0],nImgNode.inputs[0])
        
        if MetalnessTexture and os.path.exists(os.path.join(self.BasePath ,MetalnessTexture)):
            mImgNode = CreateShaderNodeTexImage(CurMat,os.path.join(self.BasePath ,MetalnessTexture),-800,150,'MetalnessTexture',self.image_format)
            mImgNode.image.colorspace_settings.name = 'Non-Color'
            reroute2 = CurMat.nodes.new(type="NodeReroute")
            reroute2.location = (-275, 115)
            CurMat.links.new(mImgNode.outputs[0],reroute2.inputs[0])
            CurMat.links.new(reroute2.outputs[0],Prin_BSDF.inputs['Metallic'])
            CurMat.links.new(TexCoordinate.outputs[0],rImgNode.inputs[0])         


# The above is  the code thats for the import plugin below is to allow testing/dev, you can run this file to import something

if __name__ == "__main__":
    import sys
    sys.path.append("F://CPmod//ImportPluginGIT//i_scene_cp77_gltf//material_types")
    sys.path.append("F://CPmod//ImportPluginGIT//i_scene_cp77_gltf//main")
    from common import *
    import os
    import json
    filepath="F:\\CPmod\\judysApt\\source\\raw\\base\\surfaces\\textures\\decals\\dirt\\oil_mark_asphalt_a.mi.json"
    #filepath="F:\\CPmod\\judysApt\\source\\raw\\base\\surfaces\\textures\\decals\\dirt\\glass_shatter_01.mi.json"
    fileBasePath = os.path.splitext(filepath)[0]
    file = open(filepath,mode='r')
    obj = json.loads(file.read())
    BasePath = "F:\\CPmod\\judysApt\\source\\raw"

    bpyMat = bpy.data.materials.new("TestMat")
    bpyMat.use_nodes = True
    bpyMat.blend_method='HASHED'
    rawMat=obj["Data"]["RootChunk"]
    vehicleLights = Decal(BasePath,"png")
    vehicleLights.create(rawMat,bpyMat)
