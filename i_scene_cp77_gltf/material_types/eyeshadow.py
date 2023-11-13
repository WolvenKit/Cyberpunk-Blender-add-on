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
        pBSDF = CurMat.nodes['Principled BSDF']
        sockets=bsdf_socket_names()
        pBSDF.inputs['Roughness'].default_value = 0.01
        pBSDF.inputs[sockets['Transmission']].default_value = 1

#MASK+SHADOW COLOR/ms
        if "Mask" in Data:
            mImg = imageFromRelPath(Data["Mask"],self.image_format,DepotPath=self.BasePath, ProjPath=self.ProjPath, isNormal=True)
            mImgNode = create_node(CurMat.nodes,"ShaderNodeTexImage",  (-500,250), label="Mask", image=mImg)

        if "ShadowColor" in Data:
            msColorNode = CreateShaderNodeRGB(CurMat, Data["ShadowColor"],-400,150,'ShadowColor')

        # if both nodes were created, use the multiply node to mask the shadow
        # then attach the result to the BSDF shader
        # since node color is black by default, just use white as the base
        if mImgNode and msColorNode:
            mixNode = CurMat.nodes.new("ShaderNodeMixRGB")
            mixNode.blend_type = 'MULTIPLY'
            mixNode.location = (-200,200)
            mixNode.inputs[1].default_value = (1,1,1,1)
            mixNode.hide = True

            CurMat.links.new(mImgNode.outputs[1],mixNode.inputs[0])
            CurMat.links.new(msColorNode.outputs[0],mixNode.inputs[2])
            
            CurMat.links.new(mixNode.outputs[0],pBSDF.inputs['Base Color'])