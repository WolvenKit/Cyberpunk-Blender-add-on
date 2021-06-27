import bpy
import os
from ..main.common import imageFromPath

class MeshDecal:
    def __init__(self, BasePath,image_format):
        self.BasePath = BasePath
        self.image_format = image_format
    def create(self,Decal,Mat):

        CurMat = Mat.node_tree
        CurMat.nodes['Principled BSDF'].inputs['Specular'].default_value = 0


        dImg = imageFromPath(self.BasePath + Decal["DiffuseTexture"],self.image_format)
            
        dImgNode = CurMat.nodes.new("ShaderNodeTexImage")
        dImgNode.location = (-450,130)
        dImgNode.image = dImg
        dImgNode.label = "DiffuseTexture"


        dTexMapping = CurMat.nodes.new("ShaderNodeMapping")
        dTexMapping.label = "UVMapping"
        dTexMapping.location = (-600,130)
        dTexMapping.inputs[1].default_value[0] = Decal["UVOffsetX"]
        dTexMapping.inputs[1].default_value[1] = Decal["UVOffsetY"]
        dTexMapping.inputs[2].default_value[0] = Decal["UVRotation"]
        dTexMapping.inputs[2].default_value[1] = Decal["UVRotation"]
        dTexMapping.inputs[3].default_value[0] = Decal["UVScaleX"]
        dTexMapping.inputs[3].default_value[1] = Decal["UVScaleY"]

        UVNode = CurMat.nodes.new("ShaderNodeTexCoord")
        UVNode.location = (-800,130)
        CurMat.links.new(UVNode.outputs[2],dTexMapping.inputs[0])
        CurMat.links.new(dTexMapping.outputs[0],dImgNode.inputs[0])


        mulNode = CurMat.nodes.new("ShaderNodeMath")
        mulNode.inputs[0].default_value = float(Decal["DiffuseAlpha"])
        if(mulNode.inputs[0].default_value == 0):
            mulNode.inputs[0].default_value = 1
        mulNode.operation = 'MULTIPLY'
        mulNode.location = (-200,-100)

        CurMat.links.new(dImgNode.outputs[1],mulNode.inputs[1])
        CurMat.links.new(mulNode.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Alpha'])


        dColor = CurMat.nodes.new("ShaderNodeRGB")
        dColor.location = (-450,200)
        dColor.hide = True
        dColor.label = "DiffuseColor"
        dColor.outputs[0].default_value = (float(Decal["DiffuseColor"]["Red"])/255,float(Decal["DiffuseColor"]["Green"])/255,float(Decal["DiffuseColor"]["Blue"])/255,float(Decal["DiffuseColor"]["Alpha"])/255)

        mixRGB = CurMat.nodes.new("ShaderNodeMixRGB")
        mixRGB.location = (-150,200)
        mixRGB.hide = True
        mixRGB.blend_type = 'MULTIPLY'
        mixRGB.inputs[0].default_value = 1

        CurMat.links.new(dImgNode.outputs[0],mixRGB.inputs[2])
        CurMat.links.new(dColor.outputs[0],mixRGB.inputs[1])
        CurMat.links.new(mixRGB.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Base Color'])


        nImg = imageFromPath(self.BasePath + Decal["NormalTexture"],self.image_format,True)
            
        nImgNode = CurMat.nodes.new("ShaderNodeTexImage")
        nImgNode.location = (-800,-250)
        nImgNode.image = nImg
        nImgNode.label = "NormalTexture"

        Sep = CurMat.nodes.new("ShaderNodeSeparateRGB")
        Sep.location = (-500,-250)
        Sep.hide = True
            
        Comb = CurMat.nodes.new("ShaderNodeCombineRGB")
        Comb.location = (-350,-250)
        Comb.hide = True
            
        CurMat.links.new(nImgNode.outputs[0],Sep.inputs[0])
        CurMat.links.new(Sep.outputs[0],Comb.inputs[0])
        CurMat.links.new(Sep.outputs[1],Comb.inputs[1])
        Comb.inputs[2].default_value = 1
            
        nMap = CurMat.nodes.new("ShaderNodeNormalMap")
        nMap.location = (-150,-250)
        nMap.hide = True

        CurMat.links.new(Comb.outputs[0],nMap.inputs[1])
        CurMat.links.new(nMap.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Normal'])


        norAlphaVal = CurMat.nodes.new("ShaderNodeValue")
        norAlphaVal.location = (-900,-450)
        norAlphaVal.outputs[0].default_value = float(Decal["NormalAlpha"])
        norAlphaVal.hide = True
        norAlphaVal.label = "NormalAlpha"


        nAImg = imageFromPath(self.BasePath + Decal["NormalAlphaTex"],self.image_format,True)
            
        nAImgNode = CurMat.nodes.new("ShaderNodeTexImage")
        nAImgNode.location = (-900,-450)
        nAImgNode.image = nAImg
        nAImgNode.label = "NormalAlphaTex"

        Sep1 = CurMat.nodes.new("ShaderNodeSeparateRGB")
        Sep1.location = (-500,-450)
        Sep1.hide = True
            
        Comb1 = CurMat.nodes.new("ShaderNodeCombineRGB")
        Comb1.location = (-350,-450)
        Comb1.hide = True
            
        CurMat.links.new(nAImgNode.outputs[0],Sep1.inputs[0])
        CurMat.links.new(Sep1.outputs[0],Comb1.inputs[0])
        CurMat.links.new(Sep1.outputs[1],Comb1.inputs[1])
        Comb1.inputs[2].default_value = 1


        rImg = imageFromPath(self.BasePath + Decal["RoughnessTexture"],self.image_format,True)
            
        rImgNode = CurMat.nodes.new("ShaderNodeTexImage")
        rImgNode.location = (-600,0)
        rImgNode.image = rImg
        rImgNode.label = "RoughnessTexture"

        mulNode1 = CurMat.nodes.new("ShaderNodeMath")
        mulNode1.inputs[0].default_value = float(Decal["RoughnessScale"])
        mulNode1.operation = 'MULTIPLY'
        mulNode1.location = (-400,0)

        CurMat.links.new(rImgNode.outputs[1],mulNode1.inputs[1])
        CurMat.links.new(mulNode1.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Roughness'])


        mImg = imageFromPath(self.BasePath + Decal["MetalnessTexture"],self.image_format,True)
            
        mImgNode = CurMat.nodes.new("ShaderNodeTexImage")
        mImgNode.location = (-600,100)
        mImgNode.image = mImg
        mImgNode.label = "MetalnessTexture"

        mulNode2 = CurMat.nodes.new("ShaderNodeMath")
        mulNode2.inputs[0].default_value = float(Decal["MetalnessScale"])
        mulNode2.operation = 'MULTIPLY'
        mulNode2.location = (-400,100)

        CurMat.links.new(mImgNode.outputs[1],mulNode2.inputs[1])
        CurMat.links.new(mulNode2.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Metallic'])