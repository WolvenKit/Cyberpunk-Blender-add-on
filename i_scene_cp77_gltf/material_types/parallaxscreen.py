import bpy
import os
from ..main.common import *

class ParallaxScreen:
    def __init__(self, BasePath,image_format,ProjPath):
        self.BasePath = BasePath
        self.ProjPath = ProjPath
        self.image_format = image_format

    def create(self,Data,Mat):
        CurMat = Mat.node_tree
        pBSDF=CurMat.nodes['Principled BSDF']
        pBSDF.inputs['Specular'].default_value = 0
        Par=createParallaxGroup()
        Mix = create_node(CurMat.nodes,"ShaderNodeMix",(-100., 250.), blend_type='MIX', label="Mix")
        Mix.data_type='RGBA'
        parImg=imageFromRelPath(Data["ParalaxTexture"],DepotPath=self.BasePath, ProjPath=self.ProjPath, image_format=self.image_format)
        ImageTexture = create_node(CurMat.nodes,"ShaderNodeTexImage",(-750., 400.), label="Image Texture", image=parImg)
        ImageTexture.extension='CLIP'
        ImageTexture001 = create_node(CurMat.nodes,"ShaderNodeTexImage",(-750.,0.), label="Image Texture.001", image=parImg)
        ImageTexture001.extension='CLIP'
        Parallax = create_node(CurMat.nodes,"ShaderNodeGroup",(-1100., 400.), label="Parallax")
        Parallax.node_tree=Par
        par_val = create_node(CurMat.nodes,"ShaderNodeValue",(-1350, 400))
        par_val.outputs[0].default_value = 0.0
        Parallax001 = create_node(CurMat.nodes,"ShaderNodeGroup",(-1100., 0.), label="Parallax.001")
        Parallax001.node_tree=Par
        par_val1 = create_node(CurMat.nodes,"ShaderNodeValue",(-1350, 0))
        par_val1.outputs[0].default_value = Data['LayersSeparation']/10
        CurMat.links.new(Mix.outputs[2], pBSDF.inputs[0])
        CurMat.links.new(ImageTexture.outputs['Color'], Mix.inputs[6])
        CurMat.links.new(ImageTexture001.outputs['Color'], Mix.inputs[7])
        CurMat.links.new(Parallax.outputs['Vector'], ImageTexture.inputs[0])
        CurMat.links.new(Parallax001.outputs['Vector'], ImageTexture001.inputs[0])
        CurMat.links.new(par_val.outputs[0], Parallax.inputs[0])
        CurMat.links.new(par_val1.outputs[0], Parallax001.inputs[0])


parameters = ['ParalaxTexture', 'ScanlineTexture', 'Metalness', 'Roughness', 'Emissive', 'ImageScale', 'LayersSeparation', 
              'IntensityPerLayer', 'ScanlinesDensity', 'ScanlinesIntensity', 'BlinkingMaskTexture', 'BlinkingSpeed',
                'ScrollSpeed1', 'ScrollStepFactor1', 'ScrollSpeed2', 'ScrollStepFactor2', 'ScrollMaskTexture', 
                'ScrollMaskStartPoint1', 'ScrollMaskHeight1', 'ScrollMaskStartPoint2', 'ScrollMaskHeight2', 
                'ScrollVerticalOrHorizontal', 'EmissiveColor', 'HSV_Mod', 'IsBroken', 'EmissiveEVRaytracingBias', 
                'EmissiveDirectionality', 'EnableRaytracedEmissive', 'FixForBlack']