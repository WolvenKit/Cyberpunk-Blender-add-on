import bpy
import os
if __name__ != "__main__":
    from ..main.common import *
class Glass:
    def __init__(self, BasePath,image_format, ProjPath):
        self.BasePath = BasePath
        self.ProjPath = ProjPath
        self.image_format = image_format

    def create(self,Data,Mat):
        CurMat = Mat.node_tree
        pBDSF=CurMat.nodes[loc('Principled BSDF')]
        sockets=bsdf_socket_names()
        pBDSF.inputs[sockets['Transmission']].default_value = 1
        # JATO: setting for blender eevee that improves transmission/refraction look
        Mat.use_raytrace_refraction = True

        isVehicleGlass = False

        # JATO: should be a safe method to test for vehicleglass.mt
        if "ShatterTexture" in Data:
            isVehicleGlass = True

        if "TintColor" in Data:
            tintColor = CreateShaderNodeRGB(CurMat, Data["TintColor"],-800,600,'TintColor')
            tintColor.hide = False

        if "IOR" in Data:
            safeIOR = (Data['IOR'])
            if safeIOR < 1:
                safeIOR = 1
            else:
                safeIOR = (Data['IOR'])
            IOR = CreateShaderNodeValue(CurMat, safeIOR,-600,-50,"IOR")
            CurMat.links.new(IOR.outputs[0],pBDSF.inputs['IOR'])

        if "Roughness" in Data:
            rImg = imageFromRelPath(Data["Roughness"],self.image_format,DepotPath=self.BasePath, ProjPath=self.ProjPath, isNormal=True)
            rImgNode = create_node(CurMat.nodes,"ShaderNodeTexImage",  (-1200,0), label="Roughness", image=rImg)
            CurMat.links.new(rImgNode.outputs[0],pBDSF.inputs['Roughness'])
            if isVehicleGlass:
                CurMat.links.new(rImgNode.outputs[1],pBDSF.inputs['Roughness'])

        if "Normal" in Data:
            nMap = CreateShaderNodeNormalMap(CurMat,self.BasePath + Data["Normal"],-800,-300,'Normal',self.image_format)
            CurMat.links.new(nMap.outputs[0],pBDSF.inputs['Normal'])

        alphaAdd = create_node(CurMat.nodes,"ShaderNodeMath", (-800,150) , operation = 'ADD')

        transmissionMultiply = create_node(CurMat.nodes,"ShaderNodeMath", (-800,300) , operation = 'MULTIPLY')

        if "MaskTexture" in Data:
            mImg = imageFromRelPath(Data["MaskTexture"],self.image_format,DepotPath=self.BasePath, ProjPath=self.ProjPath, isNormal=True)
            mImgNode = create_node(CurMat.nodes,"ShaderNodeTexImage",  (-1200,350), label="MaskTexture", image=mImg)

            CurMat.links.new(mImgNode.outputs[1],transmissionMultiply.inputs[0])

            CurMat.links.new(mImgNode.outputs[1],alphaAdd.inputs[0])
            CurMat.links.new(alphaAdd.outputs[0],pBDSF.inputs['Alpha'])

        mixRGB = create_node(CurMat.nodes,"ShaderNodeMixRGB", (-800,400) , blend_type = 'MULTIPLY')
        mixRGB.inputs[0].default_value = 1
        CurMat.links.new(tintColor.outputs[0],mixRGB.inputs[1])
        CurMat.links.new(mImgNode.outputs[0],mixRGB.inputs[2])
        CurMat.links.new(mixRGB.outputs[0],pBDSF.inputs['Base Color'])

        transmissionInvert = create_node(CurMat.nodes,"ShaderNodeMath", (-600,300) , operation = 'SUBTRACT')
        transmissionInvert.inputs[0].default_value = 1

        CurMat.links.new(transmissionMultiply.outputs[0],transmissionInvert.inputs[1])
        CurMat.links.new(transmissionInvert.outputs[0],pBDSF.inputs['Transmission Weight'])

        if "MaskOpacity" in Data:
            maskOpacity = CreateShaderNodeValue(CurMat,Data["MaskOpacity"],-800,250,"MaskOpacity")
            CurMat.links.new(maskOpacity.outputs[0],mixRGB.inputs[0])
            CurMat.links.new(maskOpacity.outputs[0],transmissionMultiply.inputs[1])

        if "Opacity" in Data:
            opacity = CreateShaderNodeValue(CurMat,Data["Opacity"],-800,100,"Opacity")
            CurMat.links.new(opacity.outputs[0],alphaAdd.inputs[1])

# The above is the code thats for the import plugin below is to allow testing/dev, you can run this file to import something

if __name__ == "__main__":
    import sys
    sys.path.append("F://CPmod//ImportPluginGIT//i_scene_cp77_gltf//material_types")
    sys.path.append("F://CPmod//ImportPluginGIT//i_scene_cp77_gltf//main")
    import json
    from common import *
    filepath="F:\\CPmod\\porsche\\source\\raw\\base\\vehicles\\sport\\v_sport2_porsche_911turbo\\entities\\meshes\\v_sport2_porsche_911turbo__ext01_body_01.glb"
    fileBasePath = os.path.splitext(filepath)[0]
    file = open(fileBasePath + ".Material.json",mode='r')
    obj = json.loads(file.read())
    BasePath = str(obj["MaterialRepo"])  + "\\"

    bpyMat = bpy.data.materials.new("TestMat")
    bpyMat.use_nodes = True
    rawMat=obj['Materials'][9]
    glass = Glass(BasePath,"png")
    glass.create(rawMat["Data"],bpyMat)