import bpy
import os
if __name__ != "__main__":
    from ..main.common import *
class GlassDeferred:
    def __init__(self, BasePath,image_format):
        self.BasePath = BasePath
        self.image_format = image_format
    def create(self,Data,Mat):
        CurMat = Mat.node_tree
        pBSDF=CurMat.nodes['Principled BSDF']
        MatOutput=CurMat.nodes['Material Output']
        MatOutput.location=(780,300)
        pBSDF.inputs['Transmission'].default_value = 1
        
        glassBSDF=CurMat.nodes.new('ShaderNodeBsdfGlass')
        glassBSDF.location=(370, -160)
        mixShader=CurMat.nodes.new('ShaderNodeMixShader')
        mixShader.location = (560, 130)
        CurMat.links.new(pBSDF.outputs[0],mixShader.inputs[1])
        CurMat.links.new(glassBSDF.outputs[0],mixShader.inputs[2])
        CurMat.links.new(mixShader.outputs[0],MatOutput.inputs[0])
#
        if "GlassTint" in Data:
            gtImgNode = CreateShaderNodeTexImage(CurMat,self.BasePath + Data["GlassTint"],-800,50,'GlassTint',self.image_format,True)
            CurMat.links.new(gtImgNode.outputs[0],pBSDF.inputs['Base Color'])


        if "TintColor" in Data:
            Color = CreateShaderNodeRGB(CurMat, Data["TintColor"],-400,200,'TintColor')
            CurMat.links.new(Color.outputs[0],pBSDF.inputs['Base Color'])

        if "IOR" in Data:
            safeIOR = (Data['IOR'])
            if safeIOR == 0:
                safeIOR = 1
            else:
                safeIOR = (Data['IOR'])
            IOR = CreateShaderNodeValue(CurMat, safeIOR,-400,-50,"IOR")
            CurMat.links.new(IOR.outputs[0],pBSDF.inputs['IOR'])
#
        if "Roughness" in Data:
            rImgNode = CreateShaderNodeTexImage(CurMat,self.BasePath + Data["Roughness"],-800,50,'Roughness',self.image_format,True)
            CurMat.links.new(rImgNode.outputs[0],pBSDF.inputs['Roughness'])
#
        if "Normal" in Data:
            nMap = CreateShaderNodeNormalMap(CurMat,self.BasePath + Data["Normal"],-200,-500,'Normal',self.image_format)
            CurMat.links.new(nMap.outputs[0],glassBSDF.inputs['Normal'])
#        
        if "MaskTexture" in Data:
            mImgNode = CreateShaderNodeTexImage(CurMat,self.BasePath + Data["MaskTexture"],-1200,-350,'MaskTexture',self.image_format,True)
            facNode = CurMat.nodes.new("ShaderNodeMath")
            facNode.inputs[0].default_value = 1
            facNode.operation = 'MULTIPLY'
            facNode.location = (-450,-100)
            CurMat.links.new(facNode.outputs[0],pBSDF.inputs['Alpha'])
#
            if "MaskOpacity" in Data:
                maskOpacity = CreateShaderNodeValue(CurMat,Data["MaskOpacity"],-1000, 0,"MaskOpacity")
                
                invNode = CurMat.nodes.new("ShaderNodeMath")
                invNode.inputs[0].default_value = 1
                invNode.operation = 'SUBTRACT'
                invNode.location = (-900,-50)
                
                mulNode = CurMat.nodes.new("ShaderNodeMath")
                mulNode.inputs[0].default_value = 1
                mulNode.operation = 'MULTIPLY'
                mulNode.location = (-650,-100)
                CurMat.links.new(maskOpacity.outputs[0],invNode.inputs[1])
                CurMat.links.new(invNode.outputs[0],mulNode.inputs[0])
                CurMat.links.new(mImgNode.outputs[1],mulNode.inputs[1])
                CurMat.links.new(mulNode.outputs[0],facNode.inputs[1])
            else:
                CurMat.links.new(mImgNode.outputs[1],facNode.inputs[1])

        # need to add a multiply and the Mask Opacity (assume thats what that does.)


# The above is  the code thats for the import plugin below is to allow testing/dev, you can run this file to import something

if __name__ == "__main__":
    import sys
    sys.path.append("F://CPmod//ImportPluginGIT//i_scene_cp77_gltf//material_types")
    sys.path.append("F://CPmod//ImportPluginGIT//i_scene_cp77_gltf//main")
    import json
    from common import *
    filepath="F:\\CPmod\\bottles\\source\\raw\\base\\environment\\decoration\\food\\drinks\\drink_bottle\\drink_bottle_s_espejismo.glb"
    fileBasePath = os.path.splitext(filepath)[0]
    file = open(fileBasePath + ".Material.json",mode='r')
    obj = json.loads(file.read())
    BasePath = str(obj["MaterialRepo"])  + "\\"

    bpyMat = bpy.data.materials.new("TestMat")
    bpyMat.use_nodes = True
    rawMat=obj['Materials'][5]
    glass = GlassDeferred(BasePath,"png")
    glass.create(rawMat["Data"],bpyMat)