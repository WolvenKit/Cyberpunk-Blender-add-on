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
            Mat["anim_speed"] = Data["AnimationSpeed"]
            
            if mapping_node:
                # Scale: 1/X and 1/Y to zoom into one sprite
                scale_sock = mapping_node.inputs[3]
                scale_sock.default_value[0] = 1 / Mat['X_COLUMNS']
                scale_sock.default_value[1] = 1 / Mat['Y_ROWS']

                # Location: Target the specific socket at index 1
                loc_sock = mapping_node.inputs[1]
                
                # Clear existing drivers on this socket
                loc_sock.driver_remove("default_value")

                for axis in range(2): # 0 = X, 1 = Y
                    # --- 2. SCALE DRIVERS ---
                    s_fcurve = scale_sock.driver_add("default_value", axis)
                    s_drv = s_fcurve.driver
                    s_drv.type = 'SCRIPTED'
                    
                    s_var = s_drv.variables.new()
                    s_var.name = "dim"
                    s_var.type = 'SINGLE_PROP'
                    s_var.targets[0].id_type = 'MATERIAL'
                    s_var.targets[0].id = Mat
                    s_var.targets[0].data_path = f'["X_COLUMNS"]' if axis == 0 else f'["Y_ROWS"]'
                    s_drv.expression = "1 / max(1, dim)"

                    # --- 3. LOCATION DRIVERS ---
                    l_fcurve = loc_sock.driver_add("default_value", axis)
                    l_drv = l_fcurve.driver
                    l_drv.type = 'SCRIPTED'

                    vars_map = [
                        ("speed", '["anim_speed"]'), 
                        ("cols", '["X_COLUMNS"]'), 
                        ("rows", '["Y_ROWS"]'),
                        ("fps", "render.fps") # Get FPS from the Scene via the ID block
                    ]

                    for v_name, p_path in vars_map:
                        v = l_drv.variables.new()
                        v.name, v.type = v_name, 'SINGLE_PROP'
                        
                        # Use MATERIAL for speed/cols/rows, but SCENE for fps
                        if v_name == "fps":
                            v.targets[0].id_type = 'SCENE'
                            v.targets[0].id = bpy.context.scene
                            v.targets[0].data_path = "render.fps"
                        else:
                            v.targets[0].id_type = 'MATERIAL'
                            v.targets[0].id = Mat
                            v.targets[0].data_path = p_path

                    # Revised Expression (No 'depsgraph' required)
                    total_sprites = "cols * rows"
                    time_expr = "((frame - 1) / max(1, fps))"
                    sprite_index = f"floor({time_expr} * speed * {total_sprites})"  
                    if axis == 0:
                        l_drv.expression = f"({sprite_index} % max(1, cols)) * (1 / max(1, cols))"
                    else:
                        l_drv.expression = f"(1 - (1 / max(1, rows))) - (floor((floor(((frame - 1) / fps) * speed) + 0.001) / max(1, cols)) % max(1, rows)) * (1 / max(1, rows))"
                        #l_drv.expression = f"-floor({sprite_index} / max(1, cols)) * (1 / max(1, rows))"

                print("Drivers assigned to Location socket successfully.")

