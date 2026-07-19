from ..jsontool import JSONTool
from ..main.common import *

from .mat_common import create_normal_map_rel, populate_color_ramp


class Eye:
    def __init__(self, BasePath, image_format, ProjPath):
        self.BasePath = BasePath
        self.ProjPath = ProjPath
        self.image_format = image_format

    def create(self, Data, Mat):
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
        sockets = bsdf_socket_names()

        if "Albedo" in Data:
            aImg = imageFromRelPath(Data["Albedo"], self.image_format, DepotPath=self.BasePath, ProjPath=self.ProjPath)
            aImgNode = create_node(CurMat.nodes, "ShaderNodeTexImage", (-1000, 300), label="Albedo", image=aImg)
            CurMat.links.new(aImgNode.outputs[0], pBSDF.inputs['Base Color'])

        if "Roughness" in Data:
            rImg = imageFromRelPath(
                    Data["Roughness"], self.image_format, DepotPath=self.BasePath, ProjPath=self.ProjPath, isNormal=True
                    )
            rImgNode = create_node(CurMat.nodes, "ShaderNodeTexImage", (-1000, 0), label="Roughness", image=rImg)

        if "RoughnessScale" in Data:
            rsNode = CreateShaderNodeValue(CurMat, Data["RoughnessScale"], -650, -200, "RoughnessScale")

        if "Normal" in Data:
            nMap = create_normal_map_rel(
                CurMat, Data["Normal"], -600, -300, 'Normal', self.image_format, self.BasePath, self.ProjPath
                )
            CurMat.links.new(nMap.outputs[0], pBSDF.inputs['Normal'])

        if "RefractionIndex" in Data:
            iorNode = CreateShaderNodeValue(CurMat, Data["RefractionIndex"], -450, -400, "RefractionIndex")
            # JATO: the IOR levels in shader don't make sense - maybe there's range mapping so 1.0 in shader is ~1.3 (or some sane value)
            # CurMat.links.new(iorNode.outputs[0],pBSDF.inputs['IOR'])

        if "Specularity" in Data:
            specNode = CreateShaderNodeValue(CurMat, Data["Specularity"], -450, -450, "Specularity")

        if "Roughness" in Data:
            rSeparateColor = CurMat.nodes.new("ShaderNodeSeparateColor")
            rSeparateColor.location = (-650, 0)

            rMultiply = create_node(CurMat.nodes, "ShaderNodeMath", (-450, 0), operation='MULTIPLY')

            CurMat.links.new(rImgNode.outputs[0], rSeparateColor.inputs[0])
            CurMat.links.new(rSeparateColor.outputs[1], rMultiply.inputs[0])
            if "RoughnessScale" in Data:
                CurMat.links.new(rsNode.outputs[0], rMultiply.inputs[1])
            else:
                rMultiply.inputs[1].default_value = 1.0
            CurMat.links.new(rMultiply.outputs[0], pBSDF.inputs['Roughness'])

        # ------ eyegradient shader variant ------ #

        iMask = None
        if "IrisMask" in Data:
            iMaskImg = imageFromRelPath(
                    Data["IrisMask"], self.image_format, DepotPath=self.BasePath, ProjPath=self.ProjPath, isNormal=True
                    )
            iMask = create_node(CurMat.nodes, "ShaderNodeTexImage", (-1000, 500), label='Iris Mask', image=iMaskImg)

        if "IrisColorGradient" in Data:
            profile = JSONTool.openJSON(
                Data["IrisColorGradient"] + ".json", mode='r', DepotPath=self.BasePath, ProjPath=self.ProjPath
                )
            profile = profile["Data"]["RootChunk"]

            igradNode = CurMat.nodes.new("ShaderNodeValToRGB")
            igradNode.location = (-600, 500)
            igradNode.label = "gradientEntries"
            populate_color_ramp(igradNode, profile["gradientEntries"])

            if iMask is not None and "Albedo" in Data:
                mixNode = CurMat.nodes.new("ShaderNodeMixRGB")
                mixNode.blend_type = 'MULTIPLY'
                mixNode.location = (-600, 250)

                CurMat.links.new(iMask.outputs[0], igradNode.inputs[0])
                CurMat.links.new(iMask.outputs[1], mixNode.inputs[0])
                CurMat.links.new(igradNode.outputs[0], mixNode.inputs[2])
                CurMat.links.new(aImgNode.outputs[0], mixNode.inputs[1])

                CurMat.links.new(mixNode.outputs[0], pBSDF.inputs['Base Color'])
            elif "Albedo" in Data:
                CurMat.links.new(aImgNode.outputs[0], pBSDF.inputs['Base Color'])
