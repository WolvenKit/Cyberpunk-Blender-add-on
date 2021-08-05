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
        profile = json.loads(file.read())
        file.close()

        CurMat = Mat.node_tree


        aImg = imageFromPath(self.BasePath + hair["Strand_Alpha"],self.image_format)
        aImgNode = CurMat.nodes.new("ShaderNodeTexImage")
        aImgNode.location = (-300,-250)
        aImgNode.image = aImg
        aImgNode.label = "Strand_Alpha"
        CurMat.links.new(aImgNode.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Alpha'])


        CurMat.nodes['Principled BSDF'].inputs['Specular'].default_value = 0


        gImg = imageFromPath(self.BasePath + hair["Strand_Gradient"],self.image_format)
        gImgNode = CurMat.nodes.new("ShaderNodeTexImage")
        gImgNode.location = (-1000,250)
        gImgNode.image = gImg
        gImgNode.label = "Strand_Gradient"

        RootToTip = CurMat.nodes.new("ShaderNodeValToRGB")
        RootToTip.location = (-700,250)
        RootToTip.label = "GradientEntriesRootToTip"

        RootToTip.color_ramp.elements.remove(RootToTip.color_ramp.elements[0])
        counter = 0
        for Entry in profile["GradientEntriesRootToTip"]:
            if counter is 0:
                RootToTip.color_ramp.elements[0].position = Entry["Value"]
                RootToTip.color_ramp.elements[0].color = (float(Entry["Color"]["Red"])/255,float(Entry["Color"]["Green"])/255,float(Entry["Color"]["Blue"])/255,float(Entry["Color"]["Alpha"])/255)
            else:
                element = RootToTip.color_ramp.elements.new(Entry["Value"])
                element.color = (float(Entry["Color"]["Red"])/255,float(Entry["Color"]["Green"])/255,float(Entry["Color"]["Blue"])/255,float(Entry["Color"]["Alpha"])/255)
            counter = counter + 1


        CurMat.links.new(gImgNode.outputs[0],RootToTip.inputs[0])
        gamma0 = CurMat.nodes.new("ShaderNodeGamma")
        gamma0.inputs[1].default_value = 8
        gamma0.location = (-500,250)
        CurMat.links.new(RootToTip.outputs[0],gamma0.inputs[0])


        idImg = imageFromPath(self.BasePath + hair["Strand_ID"],self.image_format)
        idImgNode = CurMat.nodes.new("ShaderNodeTexImage")
        idImgNode.location = (-1000,550)
        idImgNode.image = idImg
        idImgNode.label = "Strand_ID"

        ID = CurMat.nodes.new("ShaderNodeValToRGB")
        ID.location = (-700,550)
        ID.label = "GradientEntriesID"

        ID.color_ramp.elements.remove(ID.color_ramp.elements[0])
        counter = 0
        for Entry in profile["GradientEntriesID"]:
            if counter is 0:
                ID.color_ramp.elements[0].position = Entry["Value"]
                ID.color_ramp.elements[0].color = (float(Entry["Color"]["Red"])/255,float(Entry["Color"]["Green"])/255,float(Entry["Color"]["Blue"])/255,float(Entry["Color"]["Alpha"])/255)
            else:
                element = ID.color_ramp.elements.new(Entry["Value"])
                element.color = (float(Entry["Color"]["Red"])/255,float(Entry["Color"]["Green"])/255,float(Entry["Color"]["Blue"])/255,float(Entry["Color"]["Alpha"])/255)
            counter = counter + 1


        CurMat.links.new(idImgNode.outputs[0],ID.inputs[0])


        CurMat.links.new(gamma0.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Base Color'])