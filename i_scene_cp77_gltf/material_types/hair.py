import bpy
import os
from ..main.common import imageFromPath
import json

class Hair:
    def __init__(self, BasePath,image_format):
        self.BasePath = BasePath
        self.image_format = image_format

    def create(self,hair,Mat):

        file = open(self.BasePath + hair["HairProfile"] + ".json",mode='r')
        profile = json.loads(file.read())["Chunks"]["0"]["Properties"]
        file.close()

        CurMat = Mat.node_tree


        aImg = imageFromPath(self.BasePath + hair["Strand_Alpha"],self.image_format)
        aImgNode = CurMat.nodes.new("ShaderNodeTexImage")
        aImgNode.location = (-300,-150)
        aImgNode.image = aImg
        aImgNode.hide = True
        aImgNode.label = "Strand_Alpha"
        CurMat.links.new(aImgNode.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Alpha'])


        CurMat.nodes['Principled BSDF'].inputs['Specular'].default_value = 0


        gImg = imageFromPath(self.BasePath + hair["Strand_Gradient"],self.image_format,True)
        gImgNode = CurMat.nodes.new("ShaderNodeTexImage")
        gImgNode.location = (-1100,50)
        gImgNode.image = gImg
        gImgNode.label = "Strand_Gradient"

        RootToTip = CurMat.nodes.new("ShaderNodeValToRGB")
        RootToTip.location = (-800,50)
        RootToTip.label = "GradientEntriesRootToTip"

        RootToTip.color_ramp.elements.remove(RootToTip.color_ramp.elements[0])
        counter = 0
        for Entry in profile["gradientEntriesRootToTip"]:
            if counter is 0:
                RootToTip.color_ramp.elements[0].position = Entry.get("value",0)
                colr = Entry.get("color","255, 255, 255").split(', ')
                RootToTip.color_ramp.elements[0].color = (float(colr[0])/255,float(colr[1])/255,float(colr[2])/255,float(1))
            else:
                element = RootToTip.color_ramp.elements.new(Entry.get("value",0))
                colr = Entry.get("color","255, 255, 255").split(', ')
                element.color = (float(colr[0])/255,float(colr[1])/255,float(colr[2])/255,float(1))
            counter = counter + 1

        CurMat.links.new(gImgNode.outputs[0],RootToTip.inputs[0])


        idImg = imageFromPath(self.BasePath + hair["Strand_ID"],self.image_format,True)
        idImgNode = CurMat.nodes.new("ShaderNodeTexImage")
        idImgNode.location = (-1100,350)
        idImgNode.image = idImg
        idImgNode.label = "Strand_ID"

        ID = CurMat.nodes.new("ShaderNodeValToRGB")
        ID.location = (-800,350)
        ID.label = "GradientEntriesID"

        ID.color_ramp.elements.remove(ID.color_ramp.elements[0])
        counter = 0
        for Entry in profile["gradientEntriesID"]:
            if counter is 0:
                ID.color_ramp.elements[0].position = Entry.get("value",0)
                colr = Entry.get("color","255, 255, 255").split(', ')
                ID.color_ramp.elements[0].color = (float(colr[0])/255,float(colr[1])/255,float(colr[2])/255,float(1))
            else:
                element = ID.color_ramp.elements.new(Entry.get("value",0))
                colr = Entry.get("color","255, 255, 255").split(', ')
                element.color = (float(colr[0])/255,float(colr[1])/255,float(colr[2])/255,float(1))
            counter = counter + 1

        CurMat.links.new(idImgNode.outputs[0],ID.inputs[0])

        mulNode = CurMat.nodes.new("ShaderNodeMixRGB")
        mulNode.inputs[0].default_value = 1
        mulNode.blend_type = 'BURN'
        mulNode.location = (-400,200)

        CurMat.links.new(ID.outputs[0],mulNode.inputs[2])
        CurMat.links.new(RootToTip.outputs[0],mulNode.inputs[1])

        gamma0 = CurMat.nodes.new("ShaderNodeGamma")
        gamma0.inputs[1].default_value = 1.5
        gamma0.location = (-200,200)
        CurMat.links.new(mulNode.outputs[0],gamma0.inputs[0])

        CurMat.links.new(gamma0.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Base Color'])

        nImg = imageFromPath(self.BasePath + hair["Flow"],self.image_format,True)

        nImgNode = CurMat.nodes.new("ShaderNodeTexImage")
        nImgNode.location = (-800,-250)
        nImgNode.image = nImg
        nImgNode.label = "Flow"


        nRgbCurve = CurMat.nodes.new("ShaderNodeRGBCurve")
        nRgbCurve.location = (-500,-250)
        nRgbCurve.hide = True
        nRgbCurve.mapping.curves[2].points[0].location = (0,1)
        nRgbCurve.mapping.curves[2].points[1].location = (1,1)

        nMap = CurMat.nodes.new("ShaderNodeNormalMap")
        nMap.location = (-200,-250)
        nMap.hide = True

        CurMat.links.new(nImgNode.outputs[0],nRgbCurve.inputs[1])
        CurMat.links.new(nRgbCurve.outputs[0],nMap.inputs[1])
        CurMat.links.new(nMap.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Normal'])