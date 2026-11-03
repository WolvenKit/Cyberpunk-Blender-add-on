from ..assetio.catalog import ResourceKind
<<<<<<< Updated upstream
from ..materials.resources import load_material_document
from ..assetio.resolver import resolve_rooted_path
from ..materials.blender.images import imageFromRelPath
from ..materials.blender.nodes import CreateShaderNodeValue, bsdf_socket_names, create_node, loc

from .mat_common import MaterialTypeBase, create_normal_map_rel, populate_color_ramp


class Eye(MaterialTypeBase):
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
=======
from ..assetio.resolver import resolve_rooted_path
from ..blender import shader_nodes
from ..materials.resources import load_material_document
from .graph import mix_color_socket, mix_scalar_socket
from .mat_common import (
    MaterialTypeBase,
    create_relative_texture_node,
    find_input,
    new_labeled_node,
    param_float,
    populate_color_ramp,
)
from .normal_math import create_cp77_normal_texture
>>>>>>> Stashed changes

            CurMat.links.new(rImgNode.outputs[0], rSeparateColor.inputs[0])
            CurMat.links.new(rSeparateColor.outputs[1], rMultiply.inputs[0])
            if "RoughnessScale" in Data:
                CurMat.links.new(rsNode.outputs[0], rMultiply.inputs[1])
            else:
                rMultiply.inputs[1].default_value = 1.0
            CurMat.links.new(rMultiply.outputs[0], pBSDF.inputs['Roughness'])

def _transformed_uv(tree, uv, location=(-1200, -300)):
    nodes = tree.nodes
    links = tree.links
    split = new_labeled_node(nodes, "ShaderNodeSeparateXYZ", "Eye UV", location)
    links.new(uv, split.inputs["Vector"])
    x_minus = shader_nodes.math(
        nodes,
        links,
        "SUBTRACT",
        split.outputs["X"],
        1.0,
        name="Eye U - 1",
        location=(location[0] + 180, location[1] + 120),
    )
    x_plus = shader_nodes.math(
        nodes,
        links,
        "ADD",
        split.outputs["X"],
        1.0,
        name="Eye U + 1",
        location=(location[0] + 180, location[1]),
    )
    positive = shader_nodes.math(
        nodes,
        links,
        "GREATER_THAN",
        split.outputs["X"],
        0.0,
        name="Eye U > 0",
        location=(location[0] + 180, location[1] - 120),
    )
    out_x = mix_scalar_socket(
        nodes,
        links,
        "Transform Eye U",
        (location[0] + 380, location[1] + 70),
        x_plus,
        x_minus,
        positive,
    )
    out_y = shader_nodes.math(
        nodes,
        links,
        "SUBTRACT",
        1.0,
        split.outputs["Y"],
        name="1 - Eye V",
        location=(location[0] + 380, location[1] - 80),
    )
    combine = new_labeled_node(
        nodes,
        "ShaderNodeCombineXYZ",
        "Eye UV Transform",
        (location[0] + 580, location[1]),
    )
    links.new(out_x, combine.inputs["X"])
    links.new(out_y, combine.inputs["Y"])
    return combine.outputs["Vector"]

<<<<<<< Updated upstream
        iMask = None
        if "IrisMask" in Data:
            iMaskImg = imageFromRelPath(
                    Data["IrisMask"], self.image_format, DepotPath=self.BasePath, ProjPath=self.ProjPath, isNormal=True
                    )
            iMask = create_node(CurMat.nodes, "ShaderNodeTexImage", (-1000, 500), label='Iris Mask', image=iMaskImg)

        if "IrisColorGradient" in Data:
            profile_path = resolve_rooted_path(
                Data["IrisColorGradient"] + ".json",
                project_root=self.ProjPath,
                depot_root=self.BasePath,
                extensions=(".gradient.json",),
            )
            profile = load_material_document(profile_path, expected_kind=ResourceKind.GRADIENT).root

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
=======

class Eye(MaterialTypeBase):
    def create(self, Data, Mat):
        data = Data if isinstance(Data, dict) else {}
        tree = Mat.node_tree
        nodes = tree.nodes
        links = tree.links
        principled = nodes.get("Principled BSDF")
        if principled is None:
            return

        texcoord = new_labeled_node(nodes, "ShaderNodeTexCoord", "Eye UV", (-1500, 200))
        uv = texcoord.outputs["UV"]
        transformed_uv = _transformed_uv(tree, uv, (-1280, -300))

        albedo = create_relative_texture_node(
            self, tree, data, "Albedo", uv, (-1060, 520)
        )
        base_color = albedo.outputs.get("Color") if albedo is not None else None

        iris_mask = create_relative_texture_node(
            self, tree, data, "IrisMask", uv, (-1060, 800), non_color=True
        )
        gradient_ref = data.get("IrisColorGradient")
        if iris_mask is not None and gradient_ref:
            profile_path = resolve_rooted_path(
                str(gradient_ref) + ".json",
                project_root=self.ProjPath,
                depot_root=self.BasePath,
                extensions=(".gradient.json",),
            )
            resource = (
                load_material_document(
                    profile_path, expected_kind=ResourceKind.GRADIENT
                )
                if profile_path
                else None
            )
            if resource is not None:
                split = new_labeled_node(
                    nodes, "ShaderNodeSeparateColor", "Iris Mask", (-820, 800)
                )
                split.mode = "RGB"
                links.new(iris_mask.outputs["Color"], split.inputs["Color"])
                ramp = new_labeled_node(
                    nodes, "ShaderNodeValToRGB", "IrisColorGradient", (-580, 820)
                )
                populate_color_ramp(ramp, resource.root.get("gradientEntries", []))
                links.new(split.outputs["Red"], ramp.inputs["Factor"])
                if base_color is not None:
                    base_color = mix_color_socket(
                        nodes,
                        links,
                        "Iris Gradient",
                        base_color,
                        ramp.outputs["Color"],
                        iris_mask.outputs["Alpha"],
                        (-300, 620),
                    )

        if base_color is not None:
            links.new(base_color, find_input(principled, "Base Color"))

        roughness = create_relative_texture_node(
            self, tree, data, "Roughness", uv, (-1060, 180), non_color=True
        )
        if roughness is not None:
            split = new_labeled_node(
                nodes, "ShaderNodeSeparateColor", "Roughness R", (-820, 180)
            )
            split.mode = "RGB"
            links.new(roughness.outputs["Color"], split.inputs["Color"])
            rough = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                split.outputs["Red"],
                max(0.0, param_float(data, "RoughnessScale", 0.2)),
                name="Eye Roughness",
                location=(-580, 180),
            )
            links.new(rough, find_input(principled, "Roughness"))

        metallic = find_input(principled, "Metallic")
        if metallic is not None:
            metallic.default_value = max(
                0.0, min(1.0, param_float(data, "Specularity", 0.18))
            )

        normal = create_cp77_normal_texture(
            self,
            tree,
            data,
            "Normal",
            uv=transformed_uv,
            strength_key="__eye_normal_strength_unused",
            default_strength=1.0,
            location=(-1020, -180),
            label="Eye Normal",
        )
        if normal is not None:
            links.new(normal, find_input(principled, "Normal"))

        alpha = find_input(principled, "Alpha")
        if alpha is not None:
            alpha.default_value = 1.0
        transmission = find_input(principled, "Transmission Weight", "Transmission")
        if transmission is not None:
            transmission.default_value = 0.0
        subsurface = find_input(principled, "Subsurface Weight")
        if subsurface is not None:
            subsurface.default_value = 0.0
        coat = find_input(principled, "Coat Weight")
        if coat is not None:
            coat.default_value = 0.0

        Mat.surface_render_method = "DITHERED"
>>>>>>> Stashed changes
