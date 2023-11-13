import bpy
import os
from ..main.common import *

import json

class EyeGradient:
    def __init__(self, BasePath,image_format, ProjPath):
        self.BasePath = BasePath
        self.ProjPath = ProjPath
        self.image_format = image_format

    def create(self,Data,Mat):


        # load the gradient profile from the depot
        file = openJSON(Data["IrisColorGradient"] + ".json",mode='r', DepotPath=self.BasePath, ProjPath=self.ProjPath)
        profile = json.loads(file.read())
        file.close()
        valid_json=json_ver_validate(profile)
        if not valid_json:
            self.report({'ERROR'}, "Incompatible eye gradient json file detected. This add-on version requires materials generated WolvenKit 8.9.1 or higher.")
            return
        profile= profile["Data"]["RootChunk"]
        CurMat = Mat.node_tree
        pBSDF = CurMat.nodes['Principled BSDF']
        sockets=bsdf_socket_names()

        if "RefractionIndex" in Data:
            pBSDF.inputs['IOR'].default_value = Data["RefractionIndex"]

        if "Specularity" in Data:
            pBSDF.inputs[sockets["Specular"]].default_value = Data["Specularity"]

#NORMAL/n
        if "Normal" in Data:
            nMap = CreateShaderNodeNormalMap(CurMat,self.BasePath + Data["Normal"],-150,-250,'Normal',self.image_format)
            CurMat.links.new(nMap.outputs[0],pBSDF.inputs['Normal'])

#ROUGHNESS+SCALE/rs
        if "Roughness" in Data:
            rImg=imageFromRelPath(Data["Roughness"],self.image_format,DepotPath=self.BasePath, ProjPath=self.ProjPath, isNormal=True)
            rImgNode = create_node(CurMat.nodes,"ShaderNodeTexImage",  (-450,0), label="Roughness", image=rImg)

        if "RoughnessScale" in Data:
            rsNode = CreateShaderNodeValue(CurMat, Data["RoughnessScale"],-350,-50,"RoughnessScale")

        # if both nodes were created, scale the image according to the scale factor
        # then attach the result to the BSDF shader
        if rImgNode and rsNode:
            rsVecNode = CurMat.nodes.new("ShaderNodeVectorMath")
            rsVecNode.location = (-150, 0)
            rsVecNode.operation = "SCALE"
            rsVecNode.hide = True
            
            CurMat.links.new(rImgNode.outputs[0],rsVecNode.inputs[0])
            CurMat.links.new(rsNode.outputs[0],rsVecNode.inputs[3])
            CurMat.links.new(rsVecNode.outputs[0],pBSDF.inputs['Roughness'])

#ALBEDO/a
        if "Albedo" in Data:
            aImgNode = CreateShaderNodeTexImage(CurMat,self.BasePath + Data["Albedo"],-550,150,'Albedo',self.image_format)

#IRIS+GRADIENT/igrad
        if "IrisMask" in Data:
            iMask = CreateShaderNodeTexImage(CurMat,self.BasePath + Data["IrisMask"],-900,200,'Iris Mask',self.image_format)
            iMask.image.colorspace_settings.name = 'Non-Color'

        # if we have color gradient data, add a Color Ramp node
        if "IrisColorGradient" in Data:
            igradNode = CurMat.nodes.new("ShaderNodeValToRGB")
            igradNode.location = (-550,500)
            igradNode.label = "gradientEntries"

            # delete the other nodes and loop through every gradient color entry
            # (we have to have at least one though)
            igradNode.color_ramp.elements.remove(igradNode.color_ramp.elements[0])
            counter = 0
            for Entry in profile["gradientEntries"]:
                if counter == 0:
                    igradNode.color_ramp.elements[0].position = Entry.get("value",0)
                    colr = Entry["color"]
                    igradNode.color_ramp.elements[0].color = (float(colr["Red"])/255,float(colr["Green"])/255,float(colr["Blue"])/255,float(1))
                else:
                    element = igradNode.color_ramp.elements.new(Entry.get("value",0))
                    colr = Entry["color"]
                    element.color =  (float(colr["Red"])/255,float(colr["Green"])/255,float(colr["Blue"])/255,float(1))
                counter = counter + 1

        # gradients were successfully created, now connect them together
        if iMask and igradNode:
            mixNode = CurMat.nodes.new("ShaderNodeMixRGB")
            mixNode.blend_type = 'OVERLAY'
            mixNode.location = (-200,300)

            CurMat.links.new(iMask.outputs[0],igradNode.inputs[0])
            CurMat.links.new(iMask.outputs[1], mixNode.inputs[0])
            CurMat.links.new(igradNode.outputs[0], mixNode.inputs[2])
            CurMat.links.new(aImgNode.outputs[0], mixNode.inputs[1])

            CurMat.links.new(mixNode.outputs[0],pBSDF.inputs['Base Color'])

        # fallback to image only if the gradients couldn't be generated
        else:
            CurMat.links.new(aImgNode.outputs[0],pBSDF.inputs['Base Color'])