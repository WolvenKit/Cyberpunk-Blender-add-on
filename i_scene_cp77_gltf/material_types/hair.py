import bpy
import os
from ..main.common import *

import json

class Hair:
    def __init__(self, BasePath,image_format):
        self.BasePath = BasePath
        self.image_format = image_format

    def create(self,hair,Mat):

        file = open(self.BasePath + hair["HairProfile"] + ".json",mode='r')
        profile = json.loads(file.read())["Data"]["RootChunk"]
        file.close()

        Mat.blend_method = 'HASHED'
        Mat.shadow_method = 'HASHED'

        CurMat = Mat.node_tree

        aImgNode = CreateShaderNodeTexImage(CurMat,self.BasePath + hair["Strand_Alpha"],-300,-150,'Strand_Alpha',self.image_format)
        CurMat.links.new(aImgNode.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Alpha'])

        CurMat.nodes['Principled BSDF'].inputs['Specular'].default_value = 0

        gImgNode = CreateShaderNodeTexImage(CurMat,self.BasePath + hair["Strand_Gradient"],-1100,50,'Strand_Gradient',self.image_format,True)

        RootToTip = CurMat.nodes.new("ShaderNodeValToRGB")
        RootToTip.location = (-800,50)
        RootToTip.label = "GradientEntriesRootToTip"

        RootToTip.color_ramp.elements.remove(RootToTip.color_ramp.elements[0])
        counter = 0
        for Entry in profile["gradientEntriesRootToTip"]:
            if counter == 0:
                RootToTip.color_ramp.elements[0].position = Entry.get("value",0)
                colr = Entry["color"]
                RootToTip.color_ramp.elements[0].color = (float(colr["Red"])/255,float(colr["Green"])/255,float(colr["Blue"])/255,float(1))
            else:
                element = RootToTip.color_ramp.elements.new(Entry.get("value",0))
                colr = Entry["color"]
                element.color =  (float(colr["Red"])/255,float(colr["Green"])/255,float(colr["Blue"])/255,float(1))
            counter = counter + 1

        CurMat.links.new(gImgNode.outputs[0],RootToTip.inputs[0])


        idImgNode = CreateShaderNodeTexImage(CurMat,self.BasePath + hair["Strand_ID"],-1100,350,'Strand_ID',self.image_format,True)

        ID = CurMat.nodes.new("ShaderNodeValToRGB")
        ID.location = (-800,350)
        ID.label = "GradientEntriesID"

        ID.color_ramp.elements.remove(ID.color_ramp.elements[0])
        counter = 0
        for Entry in profile["gradientEntriesID"]:
            if counter is 0:
                ID.color_ramp.elements[0].position = Entry.get("value",0)
                colr = Entry["color"]
                ID.color_ramp.elements[0].color = (float(colr["Red"])/255,float(colr["Green"])/255,float(colr["Blue"])/255,float(1))
            else:
                element = ID.color_ramp.elements.new(Entry.get("value",0))
                colr = Entry["color"]
                element.color = (float(colr["Red"])/255,float(colr["Green"])/255,float(colr["Blue"])/255,float(1))
            counter = counter + 1
			
        CurMat.links.new(idImgNode.outputs[0],ID.inputs[0])

        mulNode = CurMat.nodes.new("ShaderNodeMixRGB")
        mulNode.inputs[0].default_value = 1
        mulNode.blend_type = 'MULTIPLY'
        mulNode.location = (-400,200)

        CurMat.links.new(ID.outputs[0],mulNode.inputs[1])
        CurMat.links.new(RootToTip.outputs[0],mulNode.inputs[2])

        gamma0 = CurMat.nodes.new("ShaderNodeGamma")
        gamma0.inputs[1].default_value = 2.2
        gamma0.location = (-200,200)
        CurMat.links.new(mulNode.outputs[0],gamma0.inputs[0])

        CurMat.links.new(gamma0.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Base Color'])

        nMap = CreateShaderNodeNormalMap(CurMat,self.BasePath + hair["Flow"],-200,-250,'Flow',self.image_format)
        CurMat.links.new(nMap.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Normal'])