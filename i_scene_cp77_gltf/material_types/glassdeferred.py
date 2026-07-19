import os

import bpy

if __name__ != "__main__":
    from ..main.common import *

from .mat_common import create_normal_map_rel


class GlassDeferred:
    def __init__(self, BasePath, image_format, ProjPath):
        self.BasePath = BasePath
        self.ProjPath = ProjPath
        self.image_format = image_format

    def create(self, Data, Mat):
        CurMat = Mat.node_tree
        pBSDF = CurMat.nodes[loc('Principled BSDF')]
        MatOutput = CurMat.nodes['Material Output']
        MatOutput.location = (780, 300)

        glassBSDF = CurMat.nodes.new('ShaderNodeBsdfGlass')
        glassBSDF.location = (370, -160)
        mixShader = CurMat.nodes.new('ShaderNodeMixShader')
        mixShader.location = (560, 130)
        CurMat.links.new(pBSDF.outputs[0], mixShader.inputs[1])
        CurMat.links.new(glassBSDF.outputs[0], mixShader.inputs[2])
        CurMat.links.new(mixShader.outputs[0], MatOutput.inputs[0])
        #
        if "GlassTint" in Data:
            gtImg = imageFromRelPath(
                    Data["GlassTint"], self.image_format, DepotPath=self.BasePath, ProjPath=self.ProjPath, isNormal=True
                    )
            gtImgNode = create_node(CurMat.nodes, "ShaderNodeTexImage", (-800, 50), label="GlassTint", image=gtImg)
            CurMat.links.new(gtImgNode.outputs[0], glassBSDF.inputs['Color'])

        if "TintColor" in Data:
            Color = CreateShaderNodeRGB(CurMat, Data["TintColor"], -400, 200, 'TintColor')
            CurMat.links.new(Color.outputs[0], glassBSDF.inputs['Color'])

        if "IOR" in Data:
            safeIOR = (Data['IOR'])
            if safeIOR == 0:
                safeIOR = 1
            else:
                safeIOR = (Data['IOR'])
            IOR = CreateShaderNodeValue(CurMat, safeIOR, -400, -50, "IOR")
            CurMat.links.new(IOR.outputs[0], pBSDF.inputs['IOR'])
        #
        if "Roughness" in Data:
            rImg = imageFromRelPath(
                    Data["Roughness"], self.image_format, DepotPath=self.BasePath, ProjPath=self.ProjPath, isNormal=True
                    )
            rImgNode = create_node(CurMat.nodes, "ShaderNodeTexImage", (-800, 150), label="Roughness", image=rImg)
            CurMat.links.new(rImgNode.outputs[0], pBSDF.inputs['Roughness'])
        #
        if "Normal" in Data:
            nMap = create_normal_map_rel(
                CurMat, Data["Normal"], -600, -500, 'Normal', self.image_format, self.BasePath, self.ProjPath
                )

            # Normal Strength
            if "NormalStrength" in Data:
                strength_val = float(Data.get("NormalStrength", 1.0))
                strength_node = CreateShaderNodeValue(CurMat, strength_val, -450, -550, "NormalStrength")
                CurMat.links.new(strength_node.outputs[0], nMap.inputs['Strength'])

            # NormalTileAndOffset
            if "NormalTileAndOffset" in Data:
                tile_offset = Data["NormalTileAndOffset"]
                # Vector4: (tileX, tileY, offsetX, offsetY)
                uv_map = create_node(CurMat.nodes, "ShaderNodeUVMap", (-200, -500), label="UV Map")
                mapping = create_node(CurMat.nodes, "ShaderNodeMapping", (-400, -500), label="Normal Mapping")

                # Tile (scale)
                mapping.inputs['Scale'].default_value[0] = float(tile_offset.get('X', 1.0))
                mapping.inputs['Scale'].default_value[1] = float(tile_offset.get('Y', 1.0))
                # Offset
                mapping.inputs['Location'].default_value[0] = float(tile_offset.get('Z', 0.0))
                mapping.inputs['Location'].default_value[1] = float(tile_offset.get('W', 0.0))

                tex_nodes = [n for n in CurMat.nodes if
                             isinstance(n, bpy.types.ShaderNodeTexImage) and n.label == 'Normal']
                if tex_nodes:
                    CurMat.links.new(uv_map.outputs[0], mapping.inputs[0])
                    CurMat.links.new(mapping.outputs[0], tex_nodes[0].inputs[0])

            CurMat.links.new(nMap.outputs[0], glassBSDF.inputs['Normal'])
        #

        #
        if "MaskTexture" in Data:
            mImg = imageFromRelPath(
                    Data["MaskTexture"], self.image_format, DepotPath=self.BasePath, ProjPath=self.ProjPath,
                    isNormal=True
                    )
            mImgNode = create_node(CurMat.nodes, "ShaderNodeTexImage", (-1200, -350), label="MaskTexture", image=mImg)
            facNode = CurMat.nodes.new("ShaderNodeMath")
            facNode.inputs[0].default_value = 1
            facNode.operation = 'MULTIPLY'
            facNode.location = (-450, -100)
            CurMat.links.new(mImgNode.outputs[0], pBSDF.inputs['Base Color'])
            CurMat.links.new(facNode.outputs[0], pBSDF.inputs['Alpha'])
            invNode = create_node(CurMat.nodes, "ShaderNodeInvert", (290, 125), hide=False)
            CurMat.links.new(mImgNode.outputs[1], invNode.inputs['Color'])
            CurMat.links.new(invNode.outputs[0], mixShader.inputs['Fac'])
            #
            if "MaskOpacity" in Data:
                maskOpacity = CreateShaderNodeValue(CurMat, Data["MaskOpacity"], -1000, 0, "MaskOpacity")

                invNode2 = CurMat.nodes.new("ShaderNodeMath")
                invNode2.inputs[0].default_value = 1
                invNode2.operation = 'SUBTRACT'
                invNode2.location = (-900, -50)

                mulNode = CurMat.nodes.new("ShaderNodeMath")
                mulNode.inputs[0].default_value = 1
                mulNode.operation = 'MULTIPLY'
                mulNode.location = (-650, -100)
                CurMat.links.new(maskOpacity.outputs[0], invNode.inputs[0])
                CurMat.links.new(maskOpacity.outputs[0], invNode2.inputs[0])
                CurMat.links.new(invNode2.outputs[0], mulNode.inputs[0])
                CurMat.links.new(mImgNode.outputs[1], mulNode.inputs[1])
                CurMat.links.new(mulNode.outputs[0], facNode.inputs[1])
            else:
                CurMat.links.new(mImgNode.outputs[1], facNode.inputs[1])

        # need to add a multiply and the Mask Opacity (assume thats what that does.)


# The above is  the code thats for the import plugin below is to allow testing/dev, you can run this file to import something

if __name__ == "__main__":
    import sys

    sys.path.append("F://CPmod//ImportPluginGIT//i_scene_cp77_gltf//material_types")
    sys.path.append("F://CPmod//ImportPluginGIT//i_scene_cp77_gltf//main")
    import json
    from common import *

    filepath = "F:\\CPmod\\bottles\\source\\raw\\base\\environment\\decoration\\food\\drinks\\drink_bottle\\drink_bottle_s_espejismo.glb"
    fileBasePath = os.path.splitext(filepath)[0]
    file = open(fileBasePath + ".Material.json", mode='r')
    obj = json.loads(file.read())
    BasePath = str(obj["MaterialRepo"]) + "\\"

    bpyMat = bpy.data.materials.new("TestMat")
    bpyMat.use_nodes = True
    rawMat = obj['Materials'][5]
    glass = GlassDeferred(BasePath, "png")
    glass.create(rawMat["Data"], bpyMat)
