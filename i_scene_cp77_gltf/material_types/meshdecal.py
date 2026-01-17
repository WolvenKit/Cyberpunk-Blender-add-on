import bpy
import os
from ..main.common import *

class MeshDecal:
    def __init__(self, BasePath,image_format, ProjPath, enableMask):
        self.BasePath = BasePath
        self.ProjPath = ProjPath
        self.enableMask = enableMask
        self.img_format = image_format

    def create(self,Data,Mat):
        CurMat = Mat.node_tree
        pBSDF = CurMat.nodes[loc('Principled BSDF')]
        Ns=CurMat.nodes
        sockets=bsdf_socket_names()
        isGradientMapRecolor = False

        # JATO: use this for hack to mask decals when diffusealpha is 0.0
        diffuseAlphaIsZero = False

        # JATO: why are we killing spec reflections? pretty wack
        # CurMat.nodes[loc('Principled BSDF')].inputs[sockets['Specular']].default_value = 0

        mixRGB = CurMat.nodes.new("ShaderNodeMixRGB")
        mixRGB.location = (-500,600)
        mixRGB.hide = True
        mixRGB.blend_type = 'MULTIPLY'
        mixRGB.inputs[0].default_value = 1
        CurMat.links.new(mixRGB.outputs[0],CurMat.nodes[loc('Principled BSDF')].inputs['Base Color'])

        if "GradientMap" in Data:
            # JATO: vehicle_mesh_decal.mt has a switch for ignoring gradient map. should probably use a mixrgb instead of not creating gradientmap like below
            isGradientMapRecolor = True
            if "UseGradientMap" in Data:
                if Data["UseGradientMap"] == 0:
                    isGradientMapRecolor = False

        # JATO: this node gets the maximum between alpha normal/alpha as a crappy hack - the game actually masks the color/normal individually but blender can't do that
        alphaMaximum =create_node(Ns, "ShaderNodeMath", (-700,300), operation = 'MAXIMUM')
        alphaMultiply =create_node(Ns, "ShaderNodeMath", (-500,450), operation = 'MULTIPLY')
        CurMat.links.new(alphaMaximum.outputs[0],alphaMultiply.inputs[1])

        backfaceGroup = CreateCullBackfaceGroup(CurMat, x = -500, y = 300,name = 'Cull Backface')
        CurMat.links.new(alphaMultiply.outputs[0],backfaceGroup.inputs[0])

        dTexMapping = CurMat.nodes.new("ShaderNodeMapping")
        dTexMapping.label = "UVMapping"
        dTexMapping.location = (-1600,300)

        # 'DiffuseTexture' is actually an ID-map in meshdecalgradientmaprecolor.mt - thanks CDPR
        if "DiffuseTexture" in Data:
            if not isGradientMapRecolor:
                dImg=imageFromRelPath(Data["DiffuseTexture"],DepotPath=self.BasePath, ProjPath=self.ProjPath, image_format=self.img_format)
            else:
                dImg=imageFromRelPath(Data["DiffuseTexture"],DepotPath=self.BasePath, ProjPath=self.ProjPath, image_format=self.img_format, isNormal=True)

            dImgNode = create_node(Ns,"ShaderNodeTexImage",  (-1200,600), label="DiffuseTexture", image=dImg)
            CurMat.links.new(dTexMapping.outputs[0],dImgNode.inputs[0])
            CurMat.links.new(dImgNode.outputs[0],mixRGB.inputs[2])
            if image_has_alpha(dImg):
                CurMat.links.new(dImgNode.outputs[1],alphaMultiply.inputs[0])
            else:
                CurMat.links.new(dImgNode.outputs[0],alphaMultiply.inputs[0])

        # 'GradientMap' from meshdecalgradientmaprecolor.mt
        # We already check for gradientmap in data above so we can rely on this bool
        if isGradientMapRecolor:
            gImg = imageFromRelPath(Data["GradientMap"],DepotPath=self.BasePath, ProjPath=self.ProjPath, image_format=self.img_format)
            gImgNode = create_node(CurMat.nodes,"ShaderNodeTexImage",  (-850,600), label="GradientMap", image=gImg)

            CurMat.links.new(dImgNode.outputs[0],gImgNode.inputs[0])
            CurMat.links.new(gImgNode.outputs[0],mixRGB.inputs[2])

        # 'MaskTexture' from meshdecalgradientmaprecolor.mt
        if "MaskTexture" in Data:
            aImg = imageFromRelPath(Data["MaskTexture"],DepotPath=self.BasePath, ProjPath=self.ProjPath, image_format=self.img_format, isNormal=True)
            aImgNode = create_node(CurMat.nodes,"ShaderNodeTexImage",  (-1200,800), label="MaskTexture", image=aImg)

            mulAlphaMaskNode =create_node(Ns, "ShaderNodeMath", (-700,350), operation = 'MULTIPLY')

            # Create this link AFTER DiffuseTexture to replace links
            CurMat.links.new(dImgNode.outputs[1],mulAlphaMaskNode.inputs[1])
            CurMat.links.new(aImgNode.outputs[0],mulAlphaMaskNode.inputs[0])
            CurMat.links.new(mulAlphaMaskNode.outputs[0],alphaMultiply.inputs[0])

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

        UVNode = create_node(Ns,"ShaderNodeTexCoord", (-1800,300))
        CurMat.links.new(UVNode.outputs[2],dTexMapping.inputs[0])

        CurMat.links.new(backfaceGroup.outputs[0],CurMat.nodes[loc('Principled BSDF')].inputs['Alpha'])

        if "DiffuseColor" in Data:
            dColor = CreateShaderNodeRGB(CurMat, Data["DiffuseColor"], -500, 850, "DiffuseColor")
            dColor.hide = False

            colorGamma = create_node(Ns,"ShaderNodeGamma",  (-500,650), label="Gamma")
            colorGamma.inputs[1].default_value = 2.2
            
            CurMat.links.new(dColor.outputs[0],colorGamma.inputs[0])
            CurMat.links.new(colorGamma.outputs[0],mixRGB.inputs[1])

        if "NormalTexture" in Data:
            nMap = CreateShaderNodeNormalMap(CurMat,self.BasePath + Data["NormalTexture"],-800,-350,'NormalTexture',self.img_format)
            CurMat.links.new(nMap.outputs[0],CurMat.nodes[loc('Principled BSDF')].inputs['Normal'])

        if "DiffuseAlpha" in Data:
            diffuseAlpha = CreateShaderNodeValue(CurMat, float(Data["DiffuseAlpha"]), -1200,300, "DiffuseAlpha")
            CurMat.links.new(diffuseAlpha.outputs[0],alphaMaximum.inputs[0])

            if float(Data["DiffuseAlpha"]) == 0:
                diffuseAlphaIsZero = True

        if "NormalAlpha" in Data:
            normalAlpha = CreateShaderNodeValue(CurMat, Data["NormalAlpha"], -1200,250, "NormalAlpha")
            CurMat.links.new(normalAlpha.outputs[0],alphaMaximum.inputs[1])

        if "NormalAlphaTex" in Data:
            nAImg=imageFromRelPath(Data["NormalAlphaTex"],DepotPath=self.BasePath, ProjPath=self.ProjPath, image_format=self.img_format)
            nAImgNode = create_node(Ns,"ShaderNodeTexImage",  (-1200,-500), label="NormalAlphaTex", image=nAImg)

        roughScale = CreateShaderNodeValue(CurMat, 1.0, -700,-100, "RoughnessScale")
        roughScaleMultiply =  create_node(Ns,"ShaderNodeMath", (-700,-50), operation = 'MULTIPLY')
        if "RoughnessScale" in Data:
            roughScale.outputs[0].default_value = float(Data["RoughnessScale"])
        CurMat.links.new(roughScale.outputs[0],roughScaleMultiply.inputs[1])
        CurMat.links.new(roughScaleMultiply.outputs[0],CurMat.nodes[loc('Principled BSDF')].inputs['Roughness'])

        if "RoughnessTexture" in Data:
            rImg=imageFromRelPath(Data["RoughnessTexture"],DepotPath=self.BasePath, ProjPath=self.ProjPath, image_format=self.img_format, isNormal=True)
            rImgNode = create_node(Ns,"ShaderNodeTexImage",  (-1200,-50), label="RoughnessTexture", image=rImg)
            rSeparateColor = CurMat.nodes.new("ShaderNodeSeparateColor")
            rSeparateColor.location = (-900,-50)
            CurMat.links.new(rImgNode.outputs[0],rSeparateColor.inputs[0])
            CurMat.links.new(rSeparateColor.outputs[0],roughScaleMultiply.inputs[0])


        metalScale = CreateShaderNodeValue(CurMat, 1.0, -700,150, "MetalnessScale")
        metalScaleMultiply = create_node(Ns,"ShaderNodeMath",(-700,200),operation = 'MULTIPLY')
        if "MetalnessScale" in Data:
            metalScale.outputs[0].default_value = float(Data["MetalnessScale"])
        CurMat.links.new(metalScale.outputs[0],metalScaleMultiply.inputs[1])
        CurMat.links.new(metalScaleMultiply.outputs[0],CurMat.nodes[loc('Principled BSDF')].inputs['Metallic'])

        if "MetalnessTexture" in Data:
            mImg=imageFromRelPath(Data["MetalnessTexture"],DepotPath=self.BasePath, ProjPath=self.ProjPath, image_format=self.img_format, isNormal=True)
            mImgNode = create_node(Ns,"ShaderNodeTexImage",  (-1200,200), label="MetalnessTexture", image=mImg)
            CurMat.links.new(mImgNode.outputs[0],metalScaleMultiply.inputs[0])

        # JATO: this is a wacky hack to hide decal where there is no normal influence. game directly hides color channel and we can't do that...
        if diffuseAlphaIsZero:
            normalVectorize = create_node(Ns,"ShaderNodeVectorMath",(-900,350),operation = 'MULTIPLY_ADD')
            normalVectorize.inputs[1].default_value = 2, 2, 0
            normalVectorize.inputs[2].default_value = -1, -1, 0

            normalAbsolute = create_node(Ns,"ShaderNodeMath",(-900,400),operation = 'ABSOLUTE')

            normalFloatCurve = create_node(Ns,"ShaderNodeFloatCurve",(-900,450))
            normalFloatCurve.mapping.curves[0].points[0]

            point1 = normalFloatCurve.mapping.curves[0].points[0]
            point1.location = (0.03, 0.0)
            point1.handle_type = 'VECTOR'
            point2 = normalFloatCurve.mapping.curves[0].points[1]
            point2.location = (0.3, 1.0)
            point2.handle_type = 'VECTOR'

            alphaMultiplyNormHack =create_node(Ns, "ShaderNodeMath", (-500,400), operation = 'MULTIPLY')

            # JATO: increase normal map str because it's getting alpha-masked. nothing special about 5, just looks alright
            nMap.inputs[0].default_value = 5.0

            # JATO: to retrieve the normal-tex node. necessary because CreateShaderNodeNormalMap returns the n-map node not the normal-tex node. maybe change this function...
            for node in Ns:
                if node.type == 'TEX_IMAGE' and node.label == 'NormalTexture':
                    normalImgNode = node
                    break

            CurMat.links.new(normalImgNode.outputs[0],normalVectorize.inputs[0])
            CurMat.links.new(normalVectorize.outputs[0],normalAbsolute.inputs[0])
            CurMat.links.new(normalAbsolute.outputs[0],normalFloatCurve.inputs[1])
            CurMat.links.new(normalFloatCurve.outputs[0],alphaMultiplyNormHack.inputs[1])

            CurMat.links.new(alphaMultiply.outputs[0],alphaMultiplyNormHack.inputs[0])
            CurMat.links.new(alphaMultiplyNormHack.outputs[0],backfaceGroup.inputs[0])
