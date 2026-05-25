import bpy
import os
from ..main.common import *

class MeshDecalEmissive:
    def __init__(self, BasePath,image_format, ProjPath):
        self.BasePath = BasePath
        self.ProjPath = ProjPath
        self.image_format = image_format

    def create(self,Data,Mat):
        CurMat = Mat.node_tree
        pBSDF = CurMat.nodes[loc('Principled BSDF')]
        sockets=bsdf_socket_names()
        #pBSDF.inputs[sockets['Specular']].default_value = 0

        if "DiffuseColor2" in Data:
            dCol2 = CreateShaderNodeRGB(CurMat, Data["DiffuseColor2"], -700, 200, "DiffuseColor2")
            CurMat.links.new(dCol2.outputs[0],pBSDF.inputs['Base Color'])

        alphaNode = CurMat.nodes.new("ShaderNodeMath")
        alphaNode.operation = 'MULTIPLY'
        alphaNode.location = (-400, -250)
        if "DiffuseAlpha" in Data:
            aThreshold = CreateShaderNodeValue(CurMat, Data["DiffuseAlpha"], -700, -400, "DiffuseAlpha")
            CurMat.links.new(aThreshold.outputs[0],alphaNode.inputs[1])
        else:
            alphaNode.inputs[1].default_value = 1

        mulNode = CurMat.nodes.new("ShaderNodeMixRGB")
        mulNode.inputs[0].default_value = 1
        mulNode.blend_type = 'MULTIPLY'
        mulNode.location = (-400, -50)
        if "DiffuseColor" in Data:
            emColor = CreateShaderNodeRGB(CurMat, Data["DiffuseColor"], -700, -100, "DiffuseColor")
            CurMat.links.new(emColor.outputs[0],mulNode.inputs[1])

        if "DiffuseTexture" in Data:
            emImg = imageFromRelPath(Data["DiffuseTexture"],self.image_format, DepotPath=self.BasePath, ProjPath=self.ProjPath)
            emTexNode = create_node(CurMat.nodes,"ShaderNodeTexImage",  (-700,-250), label="DiffuseTexture", image=emImg)
            CurMat.links.new(emTexNode.outputs[0],mulNode.inputs[2])
            CurMat.links.new(emTexNode.outputs[1],alphaNode.inputs[0])

        CurMat.links.new(mulNode.outputs[0], pBSDF.inputs[sockets['Emission']])
        CurMat.links.new(alphaNode.outputs[0], pBSDF.inputs['Alpha'])

        if "EmissiveEV" in Data:
            pBSDF.inputs['Emission Strength'].default_value =  Data["EmissiveEV"]

        if "AnimationSpeed" in Data and "AnimationFramesWidth" in Data and "AnimationFramesHeight" in Data and Data["AnimationFramesWidth"]>1 or Data["AnimationFramesHeight"]>1:
            mapping_node = create_node(CurMat.nodes,"ShaderNodeMapping",(-1075, -75))
            UVMapNode = create_node(CurMat.nodes,"ShaderNodeUVMap",(-1370, -75.))
            CurMat.links.new(UVMapNode.outputs[0],mapping_node.inputs[0])
            CurMat.links.new(mapping_node.outputs[0],emTexNode.inputs[0])
            Mat['X_COLUMNS'] = Data["AnimationFramesWidth"]
            Mat['Y_ROWS'] = Data["AnimationFramesHeight"]                        
            Mat["anim_speed"] = float(Data["AnimationSpeed"])
            UVScaleX=1.0
            UVScaleY=1.0
            if 'UVScaleX' in Data:
                Mat["UVScaleX"] = float(Data["UVScaleX"])
                UVScaleX= float(Data["UVScaleX"])
            if 'UVScaleY' in Data:
                Mat["UVScaleY"] = float(Data["UVScaleY"])
                UVScaleY= float(Data["UVScaleY"])   
            if mapping_node:
                mapping_node.vector_type = 'POINT'
                # 1. SCALE DRIVERS (Index 3)
                scale_socket = mapping_node.inputs[3]
                scale_socket.driver_remove("default_value")
                for axis in range(2):
                    s_drv = scale_socket.driver_add("default_value", axis).driver
                    s_drv.type = 'SCRIPTED'
                    uv = s_drv.variables.new()
                    uv.name, uv.type = "uvscale", 'SINGLE_PROP'
                    uv.targets[0].id_type, uv.targets[0].id = 'MATERIAL', Mat
                    uv.targets[0].data_path = '["UVScaleX"]' if axis == 0 else '["UVScaleY"]'

                    v = s_drv.variables.new()
                    v.name, v.type = "dim", 'SINGLE_PROP'
                    v.targets[0].id_type, v.targets[0].id = 'MATERIAL', Mat
                    v.targets[0].data_path = '["X_COLUMNS"]' if axis == 0 else '["Y_ROWS"]'

                    s_drv.expression = "uvscale/dim"

                # 2. LOCATION DRIVERS (Index 1)
                loc_socket = mapping_node.inputs[1]
                loc_socket.driver_remove("default_value")
                for axis in range(2):
                    l_drv = loc_socket.driver_add("default_value", axis).driver
                    l_drv.type = 'SCRIPTED'

                    # Scene Variables (f, fps)
                    for v_n, p_p in [("f", "frame_current"), ("fps", "render.fps")]:
                        v = l_drv.variables.new()
                        v.name, v.type = v_n, 'SINGLE_PROP'
                        v.targets[0].id_type, v.targets[0].id = 'SCENE', bpy.context.scene
                        v.targets[0].data_path = p_p

                    # Material Variables (sp, nx, ny)
                    for v_n, p_p in [("sp", '["anim_speed"]'), ("nx", '["X_COLUMNS"]'), ("ny", '["Y_ROWS"]')]:
                        v = l_drv.variables.new()
                        v.name, v.type = v_n, 'SINGLE_PROP'
                        v.targets[0].id_type, v.targets[0].id = 'MATERIAL', Mat
                        v.targets[0].data_path = p_p

                    # i = floor(time * (1/total_duration) * total_sprites)
                    i = "floor(max(0, f - 1) / max(1, fps) * sp * (nx * ny))"
                    
                    if axis == 0:
                        l_drv.expression = f"({i} % max(1, nx)) / max(1, nx)"
                    else:
                        l_drv.expression = f"(1.0 - (1.0 / max(1, ny))) - (floor(({i} + 0.001) / max(1, nx)) % max(1, ny)) / max(1, ny)"

                


