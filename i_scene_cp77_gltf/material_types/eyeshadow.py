import bpy
import os
from ..main.common import *


class EyeShadow:
    def __init__(self, BasePath,image_format, ProjPath):
        self.BasePath = BasePath
        self.ProjPath = ProjPath
        self.image_format = image_format

    def create(self,Data,Mat):
        CurMat = Mat.node_tree
        pBSDF = CurMat.nodes[loc('Principled BSDF')]
        sockets=bsdf_socket_names()
        pBSDF.inputs['Roughness'].default_value = 0.01
        pBSDF.inputs['IOR'].default_value = 1.2
        pBSDF.inputs[sockets['Transmission']].default_value = 1

        # JATO: setting for blender eevee that improves transmission/refraction look
        Mat.use_raytrace_refraction = True

        #MASK+SHADOW COLOR/ms
        if "Mask" in Data:
            mImg = imageFromRelPath(Data["Mask"],self.image_format,DepotPath=self.BasePath, ProjPath=self.ProjPath, isNormal=True)
            mImgNode = create_node(CurMat.nodes,"ShaderNodeTexImage",  (-1000,250), label="Mask", image=mImg)

        if "ShadowColor" in Data:
            msColorNode = CreateShaderNodeRGB(CurMat, Data["ShadowColor"],-600,300,'ShadowColor')

        separateColor = CurMat.nodes.new("ShaderNodeSeparateColor")
        separateColor.location = (-600,-100)


        # mixNode = CurMat.nodes.new("ShaderNodeMixRGB")
        # mixNode.blend_type = 'MULTIPLY'
        # mixNode.location = (-600,200)
        # mixNode.inputs[1].default_value = (1,1,1,1)
        # mixNode.hide = True

        CurMat.links.new(mImgNode.outputs[0],separateColor.inputs[0])
        CurMat.links.new(mImgNode.outputs[1],pBSDF.inputs['Coat Weight'])

        CurMat.links.new(msColorNode.outputs[0],pBSDF.inputs['Base Color'])
        CurMat.links.new(separateColor.outputs[0],pBSDF.inputs['Alpha'])