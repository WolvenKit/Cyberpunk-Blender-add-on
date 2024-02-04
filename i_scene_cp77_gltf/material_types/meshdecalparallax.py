import bpy
import os
from ..main.common import *


class MeshDecalParallax:
    def __init__(self, BasePath, image_format, ProjPath):
        self.BasePath = BasePath
        self.ProjPath = ProjPath
        self.image_format = image_format

    def create(self, Data, Mat):
        CurMat = Mat.node_tree
        pBSDF = CurMat.nodes["Principled BSDF"]
        sockets = bsdf_socket_names()
        pBSDF.inputs[sockets["Specular"]].default_value = 0
        # Diffuse
        mixRGB = create_node(CurMat.nodes, "ShaderNodeMixRGB", (-500, 500), blend_type="MULTIPLY")
        mixRGB.inputs[0].default_value = 1
        CurMat.links.new(mixRGB.outputs[0], pBSDF.inputs["Base Color"])

        mulNode = CurMat.nodes.new("ShaderNodeMath")
        mulNode.operation = "MULTIPLY"
        mulNode.location = (-500, 450)
        if "DiffuseAlpha" in Data:
            mulNode.inputs[0].default_value = float(Data["DiffuseAlpha"])
        else:
            mulNode.inputs[0].default_value = 1

        dTexMapping = CurMat.nodes.new("ShaderNodeMapping")
        dTexMapping.label = "UVMapping"
        dTexMapping.location = (-1000, 300)

        if "DiffuseTexture" in Data:
            dImg = imageFromRelPath(
                Data["DiffuseTexture"], self.image_format, DepotPath=self.BasePath, ProjPath=self.ProjPath
            )
            dImgNode = create_node(CurMat.nodes, "ShaderNodeTexImage", (-800, 500), label="DiffuseTexture", image=dImg)
            CurMat.links.new(dTexMapping.outputs[0], dImgNode.inputs[0])
            CurMat.links.new(dImgNode.outputs[0], mixRGB.inputs[2])
            CurMat.links.new(dImgNode.outputs[1], mulNode.inputs[1])

        if "UVOffsetX" in Data:
            dTexMapping.inputs[1].default_value[0] = Data["UVOffsetX"]
        if "UVOffsetY" in Data:
            dTexMapping.inputs[1].default_value[1] = Data["UVOffsetY"]
        if "UVRotation" in Data:
            dTexMapping.inputs[2].default_value[0] = Data["UVRotation"]
            dTexMapping.inputs[2].default_value[1] = Data["UVRotation"]
        if "UVScaleX" in Data:
            dTexMapping.inputs[3].default_value[0] = Data["UVScaleX"]
        if "UVScaleY" in Data:
            dTexMapping.inputs[3].default_value[1] = Data["UVScaleY"]

        UVNode = CurMat.nodes.new("ShaderNodeTexCoord")
        UVNode.location = (-1200, 300)
        CurMat.links.new(UVNode.outputs[2], dTexMapping.inputs[0])

        CurMat.links.new(mulNode.outputs[0], pBSDF.inputs["Alpha"])

        if "DiffuseColor" in Data:
            dColor = CreateShaderNodeRGB(CurMat, Data["DiffuseColor"], -700, 550, "DiffuseColor")
            CurMat.links.new(dColor.outputs[0], mixRGB.inputs[1])

        if "NormalTexture" in Data:
            nMap = CreateShaderNodeNormalMap(
                CurMat, self.BasePath + Data["NormalTexture"], -200, -250, "NormalTexture", self.image_format
            )
            CurMat.links.new(nMap.outputs[0], pBSDF.inputs["Normal"])

        if "NormalAlpha" in Data:
            norAlphaVal = CreateShaderNodeValue(CurMat, Data["NormalAlpha"], -1200, -450, "NormalAlpha")

        if "NormalAlphaTex" in Data:
            nAImgNode = CreateShaderNodeTexImage(
                CurMat, self.BasePath + Data["NormalAlphaTex"], -1200, -500, "NormalAlphaTex", self.image_format, True
            )

        mulNode1 = CurMat.nodes.new("ShaderNodeMath")
        if "RoughnessScale" in Data:
            mulNode1.inputs[0].default_value = float(Data["RoughnessScale"])
        else:
            mulNode1.inputs[0].default_value = 1

        mulNode1.operation = "MULTIPLY"
        mulNode1.location = (-500, -100)
        CurMat.links.new(mulNode1.outputs[0], pBSDF.inputs["Roughness"])
        if "RoughnessTexture" in Data:
            rImg = imageFromRelPath(
                Data["RoughnessTexture"],
                self.image_format,
                DepotPath=self.BasePath,
                ProjPath=self.ProjPath,
                isNormal=True,
            )
            rImgNode = create_node(
                CurMat.nodes, "ShaderNodeTexImage", (-800, 100), label="RoughnessTexture", image=rImg, hide=False
            )
            CurMat.links.new(rImgNode.outputs[0], mulNode1.inputs[1])

        mulNode2 = CurMat.nodes.new("ShaderNodeMath")
        if "MetalnessScale" in Data:
            mulNode2.inputs[0].default_value = float(Data["MetalnessScale"])
        else:
            mulNode2.inputs[0].default_value = 1
        mulNode2.operation = "MULTIPLY"
        mulNode2.location = (-500, 200)
        CurMat.links.new(mulNode2.outputs[0], pBSDF.inputs["Metallic"])
        if "MetalnessTexture" in Data:
            mImg = imageFromRelPath(
                Data["MetalnessTexture"],
                self.image_format,
                DepotPath=self.BasePath,
                ProjPath=self.ProjPath,
                isNormal=True,
            )
            mImgNode = create_node(
                CurMat.nodes, "ShaderNodeTexImage", (-800, 200), label="MetalnessTexture", image=mImg
            )
            CurMat.links.new(mImgNode.outputs[0], mulNode2.inputs[1])


"""     
        if "SecondaryMask"in Data:
            print('SecondaryMask detected', Data['SecondaryMask'])
            
        if "SecondaryMaskUVScale"in Data:
            print('SecondaryMaskUVScale detected - ', Data['SecondaryMaskUVScale'])
            
        if "SecondaryMaskInfluence"in Data:
            print('SecondaryMaskInfluence detected', Data['SecondaryMaskInfluence'])
            
        if "UseNormalAlphaTex"in Data:
            print('UseNormalAlphaTex detected', Data['UseNormalAlphaTex'])
        if "NormalsBlendingMode"in Data:
            print('NormalsBlendingMode detected', Data['NormalsBlendingMode'])
        
        if "AlphaMaskContrast"in Data:
            print('NormalsBlendingMode detected', Data['NormalsBlendingMode'])

        if "RoughnessMetalnessAlpha"in Data:
            print('RoughnessMetalnessAlpha detected', Data['NormalsBlendingMode'])

        if "DepthThreshold"in Data:
            print('DepthThreshold detected', Data['DepthThreshold'])

        if "HeightTexture"in Data:
            print('HeightTexture detected', Data['HeightTexture'])
        if "HeightStrength"in Data:
            print('HeightStrength detected', Data['HeightStrength'])
"""
