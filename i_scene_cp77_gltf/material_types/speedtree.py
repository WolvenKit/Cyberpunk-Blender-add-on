<<<<<<< Updated upstream
from ..materials.blender.images import imageFromRelPath
from ..materials.blender.nodes import bsdf_socket_names, create_node, loc

from .mat_common import MaterialTypeBase, create_normal_map_rel
=======
from ..bartmoss.scalar import clamp01
from ..blender.shader_nodes import socket_by_identifier
from .graph import set_alpha_clip
from .mat_common import (
    MaterialTypeBase,
    create_relative_texture_node,
    find_input,
    new_labeled_node,
    param_color,
    param_float,
    param_texture_path,
)
from .normal_math import create_cp77_normal_texture
>>>>>>> Stashed changes


class SpeedTree(MaterialTypeBase):
    def create(self, Data, Mat):
<<<<<<< Updated upstream
        CurMat = Mat.node_tree
        pBSDF = CurMat.nodes[loc('Principled BSDF')]
        sockets = bsdf_socket_names()
        pBSDF.inputs[sockets['Specular']].default_value = 0.5

        # Diffuse
        dTexMapping = CurMat.nodes.new("ShaderNodeMapping")
        dTexMapping.label = "UVMapping"
        dTexMapping.location = (-1000, 300)

        if "DiffuseMap" in Data:
            dImg = imageFromRelPath(
                    Data["DiffuseMap"], self.image_format, DepotPath=self.BasePath, ProjPath=self.ProjPath
                    )
            dImgNode = create_node(CurMat.nodes, "ShaderNodeTexImage", (-800, 400), label="DiffuseTexture", image=dImg)
            CurMat.links.new(dTexMapping.outputs[0], dImgNode.inputs[0])
            CurMat.links.new(dImgNode.outputs[0], pBSDF.inputs['Base Color'])
            CurMat.links.new(dImgNode.outputs[1], pBSDF.inputs['Alpha'])
            dImgNode.hide = False

        if "BaseColor" in Data:
            dImg = imageFromRelPath(
                    Data["BaseColor"], self.image_format, DepotPath=self.BasePath, ProjPath=self.ProjPath
                    )
            dImgNode = create_node(CurMat.nodes, "ShaderNodeTexImage", (-800, 400), label="DiffuseTexture", image=dImg)
            CurMat.links.new(dTexMapping.outputs[0], dImgNode.inputs[0])
            CurMat.links.new(dImgNode.outputs[0], pBSDF.inputs['Base Color'])
            CurMat.links.new(dImgNode.outputs[1], pBSDF.inputs['Alpha'])
            dImgNode.hide = False
=======
        data = Data if isinstance(Data, dict) else {}
        Mat.use_nodes = True
        tree = Mat.node_tree
        nodes = tree.nodes
        links = tree.links
        nodes.clear()

        output = new_labeled_node(
            nodes, "ShaderNodeOutputMaterial", "Material Output", (720, 100)
        )
        principled = new_labeled_node(
            nodes, "ShaderNodeBsdfPrincipled", "SpeedTree Source Preview", (460, 100)
        )
        links.new(principled.outputs["BSDF"], output.inputs["Surface"])
>>>>>>> Stashed changes

        is_ver_skinned = bool(param_texture_path(data, "BaseColor"))
        diffuse_key = "BaseColor" if is_ver_skinned else "DiffuseMap"
        normal_key = "Normal" if is_ver_skinned else "NormalMap"
        transgloss_key = "Roughness" if is_ver_skinned else "TransGlossMap"

<<<<<<< Updated upstream
        UVNode = create_node(CurMat.nodes, "ShaderNodeTexCoord", (-1200, 300))
        CurMat.links.new(UVNode.outputs[2], dTexMapping.inputs[0])

        if "NormalMap" in Data:
            nMap = create_normal_map_rel(
                CurMat, Data["NormalMap"], -300, -350, 'NormalMap', self.image_format, self.BasePath, self.ProjPath
                )
            CurMat.links.new(nMap.outputs[0], pBSDF.inputs['Normal'])
            nMap.inputs[1].links[0].from_node.inputs[0].links[0].from_node.hide = False
            nMap.inputs[1].links[0].from_node.inputs[0].links[0].from_node.location = (-800, -200)

        if "Normal" in Data:
            nMap = create_normal_map_rel(
                CurMat, Data["Normal"], -300, -350, 'NormalMap', self.image_format, self.BasePath, self.ProjPath
                )
            CurMat.links.new(nMap.outputs[0], pBSDF.inputs['Normal'])
            nMap.inputs[1].links[0].from_node.inputs[0].links[0].from_node.hide = False
            nMap.inputs[1].links[0].from_node.inputs[0].links[0].from_node.location = (-800, -200)

        if "TransGlossMap" in Data:
            rImg = imageFromRelPath(
                    Data["TransGlossMap"], self.image_format, DepotPath=self.BasePath, ProjPath=self.ProjPath,
                    isNormal=True
                    )
            rImgNode = create_node(
                CurMat.nodes, "ShaderNodeTexImage", (-800, 100), label="TransGlossMap", image=rImg, hide=False
                )

            mathNode = create_node(CurMat.nodes, "ShaderNodeMath", (-400, 100), operation='SUBTRACT', label="Math")
            mathNode.inputs[0].default_value = 1.0
            CurMat.links.new(rImgNode.outputs[0], mathNode.inputs[1])
            CurMat.links.new(mathNode.outputs[0], pBSDF.inputs['Roughness'])

        if "Roughness" in Data:
            rImg = imageFromRelPath(
                    Data["Roughness"], self.image_format, DepotPath=self.BasePath, ProjPath=self.ProjPath, isNormal=True
                    )
            rImgNode = create_node(
                CurMat.nodes, "ShaderNodeTexImage", (-800, 100), label="TransGlossMap", image=rImg, hide=False
                )

            mathNode = create_node(CurMat.nodes, "ShaderNodeMath", (-400, 100), operation='SUBTRACT', label="Math")
            mathNode.inputs[0].default_value = 1.0
            CurMat.links.new(rImgNode.outputs[0], mathNode.inputs[1])
            CurMat.links.new(mathNode.outputs[0], pBSDF.inputs['Roughness'])
=======
        diffuse = create_relative_texture_node(
            self,
            tree,
            data,
            diffuse_key,
            None,
            (-760, 300),
            error_label=f"speedtree {diffuse_key}",
        )
        color_socket = diffuse.outputs["Color"] if diffuse is not None else None
        if color_socket is not None and is_ver_skinned:
            scale = param_color(data, "BaseColorScale", (1.0, 1.0, 1.0, 1.0))
            tint = new_labeled_node(
                nodes, "ShaderNodeRGB", "BaseColorScale preview", (-520, 420)
            )
            tint.outputs["Color"].default_value = scale
            multiply = new_labeled_node(
                nodes, "ShaderNodeMix", "BaseColor × Scale", (-260, 300)
            )
            multiply.data_type = "RGBA"
            multiply.blend_type = "MULTIPLY"
            socket_by_identifier(multiply.inputs, "Factor_Float").default_value = 1.0
            links.new(color_socket, socket_by_identifier(multiply.inputs, "A_Color"))
            links.new(
                tint.outputs["Color"], socket_by_identifier(multiply.inputs, "B_Color")
            )
            color_socket = socket_by_identifier(multiply.outputs, "Result_Color")
        if color_socket is not None:
            links.new(color_socket, find_input(principled, "Base Color"))
        if diffuse is not None:
            links.new(diffuse.outputs["Alpha"], find_input(principled, "Alpha"))

        normal_path = param_texture_path(data, normal_key)
        if normal_path:
            normal = create_cp77_normal_texture(
                self,
                tree,
                data,
                key=normal_key,
                strength_key=None,
                default_strength=1.0,
                location=(-720, -100),
                label=normal_key,
            )
            if normal is not None:
                links.new(normal, find_input(principled, "Normal"))

        # The serialized material does not expose the TransGloss/Roughness channel packing.
        # Keep the texture visible but do not guess its interpretation.
        create_relative_texture_node(
            self,
            tree,
            data,
            transgloss_key,
            None,
            (-760, -420),
            non_color=True,
            error_label=f"speedtree {transgloss_key}",
        )
        roughness = find_input(principled, "Roughness")
        if roughness is not None:
            if is_ver_skinned:
                roughness.default_value = clamp01(
                    param_float(data, "RoughnessBias", 0.5)
                )
            else:
                roughness.default_value = 0.5
        metallic = find_input(principled, "Metallic")
        if metallic is not None:
            metallic.default_value = (
                clamp01(param_float(data, "MetalnessBias", 0.0))
                if is_ver_skinned
                else 0.0
            )

        threshold = (
            clamp01(param_float(data, "AlphaThreshold", 0.5)) if is_ver_skinned else 0.5
        )
        set_alpha_clip(Mat, threshold)
>>>>>>> Stashed changes
