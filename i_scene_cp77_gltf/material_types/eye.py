import bpy
import os
from ..main.common import *
from ..jsontool import JSONTool

class Eye:
    def __init__(self, BasePath, image_format, ProjPath):
        self.BasePath = BasePath
        self.ProjPath = ProjPath
        self.image_format = image_format

    def create(self,Data,Mat):
        CurMat = Mat.node_tree

        pBSDF = CurMat.nodes[loc('Principled BSDF')]
        pBSDF.inputs['IOR'].default_value = 1.3
        pBSDF.subsurface_method = 'RANDOM_WALK_SKIN'
        pBSDF.inputs['Subsurface Weight'].default_value = 1
        pBSDF.inputs['Subsurface Scale'].default_value = .002
        pBSDF.inputs['Subsurface Radius'].default_value[0] = 1.0
        pBSDF.inputs['Subsurface Radius'].default_value[1] = 0.35
        pBSDF.inputs['Subsurface Radius'].default_value[2] = 0.2
        pBSDF.inputs['Subsurface Anisotropy'].default_value = 0.8
        pBSDF.inputs['Transmission Weight'].default_value = 0.35
        pBSDF.inputs['Coat Weight'].default_value = 0.25
        # JATO: setting for blender eevee that improves transmission/refraction look
        Mat.use_raytrace_refraction = True
        sockets=bsdf_socket_names()

        if "Albedo" in Data:
            aImg = imageFromRelPath(Data["Albedo"],self.image_format,DepotPath=self.BasePath, ProjPath=self.ProjPath)
            aImgNode = create_node(CurMat.nodes,"ShaderNodeTexImage",  (-1000,300), label="Albedo", image=aImg)
            CurMat.links.new(aImgNode.outputs[0],pBSDF.inputs['Base Color'])

        if "Roughness" in Data:
            rImg=imageFromRelPath(Data["Roughness"],self.image_format,DepotPath=self.BasePath, ProjPath=self.ProjPath, isNormal=True)
            rImgNode = create_node(CurMat.nodes,"ShaderNodeTexImage",  (-1000,0), label="Roughness", image=rImg)

        if "RoughnessScale" in Data:
            rsNode = CreateShaderNodeValue(CurMat, Data["RoughnessScale"],-650,-200,"RoughnessScale")

        if "Normal" in Data:
            nMap = CreateShaderNodeNormalMap(CurMat,self.BasePath + Data["Normal"],-600,-300,'Normal',self.image_format)
            CurMat.links.new(nMap.outputs[0],pBSDF.inputs['Normal'])

        if "RefractionIndex" in Data:
            iorNode = CreateShaderNodeValue(CurMat, Data["RefractionIndex"],-450,-400,"RefractionIndex")
            # JATO: the IOR levels in shader don't make sense - maybe there's range mapping so 1.0 in shader is ~1.3 (or some sane value)
            # CurMat.links.new(iorNode.outputs[0],pBSDF.inputs['IOR'])

        if "Specularity" in Data:
            specNode = CreateShaderNodeValue(CurMat, Data["Specularity"],-450,-450,"Specularity")

        rSeparateColor = CurMat.nodes.new("ShaderNodeSeparateColor")
        rSeparateColor.location = (-650,0)

        rMultiply = create_node(CurMat.nodes, "ShaderNodeMath",(-450,0),operation='MULTIPLY')

        CurMat.links.new(rImgNode.outputs[0],rSeparateColor.inputs[0])
        CurMat.links.new(rSeparateColor.outputs[1],rMultiply.inputs[0])
        CurMat.links.new(rsNode.outputs[0],rMultiply.inputs[1])
        CurMat.links.new(rMultiply.outputs[0],pBSDF.inputs['Roughness'])


        # ------ eyegradient shader variant ------ #

        if "IrisMask" in Data:
            iMask = CreateShaderNodeTexImage(CurMat,self.BasePath + Data["IrisMask"],-1000,500,'Iris Mask',self.image_format)
            iMask.image.colorspace_settings.name = 'Non-Color'

        if "IrisColorGradient" in Data:
            profile = JSONTool.openJSON(Data["IrisColorGradient"] + ".json",mode='r', DepotPath=self.BasePath, ProjPath=self.ProjPath)
            profile= profile["Data"]["RootChunk"]

            igradNode = CurMat.nodes.new("ShaderNodeValToRGB")
            igradNode.location = (-600,500)
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

            if iMask and igradNode:
                mixNode = CurMat.nodes.new("ShaderNodeMixRGB")
                mixNode.blend_type = 'MULTIPLY'
                mixNode.location = (-600,250)

                CurMat.links.new(iMask.outputs[0],igradNode.inputs[0])
                CurMat.links.new(iMask.outputs[1], mixNode.inputs[0])
                CurMat.links.new(igradNode.outputs[0], mixNode.inputs[2])
                CurMat.links.new(aImgNode.outputs[0], mixNode.inputs[1])

                CurMat.links.new(mixNode.outputs[0],pBSDF.inputs['Base Color'])
            else:
                CurMat.links.new(aImgNode.outputs[0],pBSDF.inputs['Base Color'])