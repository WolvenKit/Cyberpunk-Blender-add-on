import bpy
import os
from ..main.common import imageFromPath

class Glass:
    def __init__(self, BasePath,image_format):
        self.BasePath = BasePath
        self.image_format = image_format
    def create(self,Glass,Mat):

        CurMat = Mat.node_tree
        CurMat.nodes['Principled BSDF'].inputs['Transmission'].default_value = 1

        Color = CurMat.nodes.new("ShaderNodeRGB")
        Color.location = (-400,200)
        Color.hide = True
        Color.label = "TintColor"
        Color.outputs[0].default_value = (float(Glass["TintColor"]["Red"])/255,float(Glass["TintColor"]["Green"])/255,float(Glass["TintColor"]["Blue"])/255,float(Glass["TintColor"]["Alpha"])/255)

        CurMat.links.new(Color.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Base Color'])


        IOR = CurMat.nodes.new("ShaderNodeValue")
        IOR.location = (-400,-150)
        IOR.outputs[0].default_value = float(Glass["IOR"])
        IOR.hide = True
        IOR.label = "IOR"

        CurMat.links.new(IOR.outputs[0],CurMat.nodes['Principled BSDF'].inputs['IOR'])


        rImg = imageFromPath(self.BasePath + Glass["Roughness"],self.image_format,True)
            
        rImgNode = CurMat.nodes.new("ShaderNodeTexImage")
        rImgNode.location = (-800,50)
        rImgNode.image = rImg
        rImgNode.label = "Roughness"

        CurMat.links.new(rImgNode.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Roughness'])


        nImg = imageFromPath(self.BasePath + Glass["Normal"],self.image_format,True)
            
        nImgNode = CurMat.nodes.new("ShaderNodeTexImage")
        nImgNode.location = (-800,-300)
        nImgNode.image = nImg
        nImgNode.label = "Normal"

        nRgbCurve = CurMat.nodes.new("ShaderNodeRGBCurve")
        nRgbCurve.location = (-500,-300)
        nRgbCurve.hide = True
        nRgbCurve.mapping.curves[2].points[0].location = (0,1)
        nRgbCurve.mapping.curves[2].points[1].location = (1,1)

        nMap = CurMat.nodes.new("ShaderNodeNormalMap")
        nMap.location = (-200,-300)
        nMap.hide = True

        CurMat.links.new(nImgNode.outputs[0],nRgbCurve.inputs[1])
        CurMat.links.new(nRgbCurve.outputs[0],nMap.inputs[1])
        CurMat.links.new(nMap.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Normal'])