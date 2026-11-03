<<<<<<< Updated upstream
from ..materials.blender.images import imageFromRelPath
from ..materials.blender.nodes import CreateShaderNodeRGB, bsdf_socket_names, create_node, loc


from .mat_common import MaterialTypeBase

class EyeShadow(MaterialTypeBase):
    def create(self, Data, Mat):
        CurMat = Mat.node_tree
        pBSDF = CurMat.nodes[loc('Principled BSDF')]
        sockets = bsdf_socket_names()
        pBSDF.inputs['Roughness'].default_value = 0.01
        pBSDF.inputs['IOR'].default_value = 1.2
        pBSDF.inputs[sockets['Transmission']].default_value = 1
=======
from ..blender import shader_nodes
from .mat_common import (
    MaterialTypeBase,
    find_input,
    new_labeled_node,
    param_color,
    param_float,
    param_texture_path,
)


class EyeShadow(MaterialTypeBase):
    def create(self, Data, Mat):
        data = Data if isinstance(Data, dict) else {}
        mask_path = param_texture_path(data, "Mask")
        if not mask_path:
            return
        image = self._load_relative_image(mask_path, non_color=True, error_label="Mask")
        if image is None:
            return

        tree = Mat.node_tree
        nodes = tree.nodes
        links = tree.links
        nodes.clear()
>>>>>>> Stashed changes

        output = new_labeled_node(
            nodes, "ShaderNodeOutputMaterial", "Material Output", (900, 80)
        )
        mask = new_labeled_node(nodes, "ShaderNodeTexImage", "Mask", (-1200, 240))
        mask.image = image
        split = new_labeled_node(
            nodes, "ShaderNodeSeparateColor", "Eye Shadow Mask RGB", (-960, 240)
        )
        split.mode = "RGB"
        links.new(mask.outputs["Color"], split.inputs["Color"])

<<<<<<< Updated upstream
        # MASK+SHADOW COLOR/ms
        if "Mask" in Data:
            mImg = imageFromRelPath(
                    Data["Mask"], self.image_format, DepotPath=self.BasePath, ProjPath=self.ProjPath, isNormal=True
                    )
            mImgNode = create_node(CurMat.nodes, "ShaderNodeTexImage", (-1000, 250), label="Mask", image=mImg)

            separateColor = CurMat.nodes.new("ShaderNodeSeparateColor")
            separateColor.location = (-600, -100)

            CurMat.links.new(mImgNode.outputs[0], separateColor.inputs[0])
            CurMat.links.new(mImgNode.outputs[1], pBSDF.inputs['Coat Weight'])
            CurMat.links.new(separateColor.outputs[0], pBSDF.inputs['Alpha'])

        if "ShadowColor" in Data:
            msColorNode = CreateShaderNodeRGB(CurMat, Data["ShadowColor"], -600, 300, 'ShadowColor')
            CurMat.links.new(msColorNode.outputs[0], pBSDF.inputs['Base Color'])
=======
        exponent = max(0.0, param_float(data, "Exponent", 1.0))
        intensity = max(0.0, param_float(data, "Intensity", 1.0))
        modified = shader_nodes.math(
            nodes,
            links,
            "POWER",
            split.outputs["Red"],
            exponent,
            name="Mask^Exponent",
            location=(-720, 420),
        )
        modified = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            modified,
            intensity,
            name="Shadow Mask × Intensity",
            location=(-520, 420),
            use_clamp=True,
        )

        shadow = param_color(data, "ShadowColor", (0.0, 0.0, 0.0, 1.0))
        shadow_luminance = 0.33 * sum(channel**2.2 for channel in shadow[:3])
        shadow_opacity = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            modified,
            max(0.0, min(1.0, 1.0 - shadow_luminance)),
            name="Shadow Opacity = 1 - FinalAlpha",
            location=(-300, 420),
            use_clamp=True,
        )

        transparent_shadow = new_labeled_node(
            nodes, "ShaderNodeBsdfTransparent", "Transparent Shadow", (0, 520)
        )
        shadow_surface = new_labeled_node(
            nodes, "ShaderNodeBsdfPrincipled", "Shadow Attenuation", (0, 320)
        )
        base = find_input(shadow_surface, "Base Color")
        if base is not None:
            base.default_value = (0.0, 0.0, 0.0, 1.0)
        roughness = find_input(shadow_surface, "Roughness")
        if roughness is not None:
            roughness.default_value = 1.0
        metallic = find_input(shadow_surface, "Metallic")
        if metallic is not None:
            metallic.default_value = 0.0
        specular = find_input(shadow_surface, "Specular IOR Level")
        if specular is not None:
            specular.default_value = 0.0
        shadow_mix = new_labeled_node(
            nodes, "ShaderNodeMixShader", "Shadow Transmittance", (300, 420)
        )
        links.new(shadow_opacity, shadow_mix.inputs["Factor"])
        links.new(transparent_shadow.outputs["BSDF"], shadow_mix.inputs["Shader"])
        links.new(
            shadow_surface.outputs["BSDF"],
            shader_nodes.socket_by_identifier(shadow_mix.inputs, "Shader_001"),
        )

        wet_roughness = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            split.outputs["Green"],
            max(0.0, min(1.0, param_float(data, "WetnessRoughness", 1.0))),
            name="Wetness Roughness",
            location=(-520, 40),
            use_clamp=True,
        )
        wetness = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            split.outputs["Blue"],
            max(0.0, param_float(data, "WetnessStrength", 4.0)),
            name="Wetness Specular Weight",
            location=(-520, -120),
            use_clamp=True,
        )

        transparent_wet = new_labeled_node(
            nodes, "ShaderNodeBsdfTransparent", "Transparent Wetness", (0, 40)
        )
        wet_surface = new_labeled_node(
            nodes, "ShaderNodeBsdfPrincipled", "Wet Specular", (0, -160)
        )
        wet_base = find_input(wet_surface, "Base Color")
        if wet_base is not None:
            wet_base.default_value = (1.0, 1.0, 1.0, 1.0)
        wet_metallic = find_input(wet_surface, "Metallic")
        if wet_metallic is not None:
            wet_metallic.default_value = 1.0
        wet_rough = find_input(wet_surface, "Roughness")
        if wet_rough is not None:
            links.new(wet_roughness, wet_rough)
        wet_mix = new_labeled_node(
            nodes, "ShaderNodeMixShader", "Wetness Contribution", (300, -40)
        )
        links.new(wetness, wet_mix.inputs["Factor"])
        links.new(transparent_wet.outputs["BSDF"], wet_mix.inputs["Shader"])
        links.new(
            wet_surface.outputs["BSDF"],
            shader_nodes.socket_by_identifier(wet_mix.inputs, "Shader_001"),
        )

        combined = new_labeled_node(
            nodes, "ShaderNodeAddShader", "Eye Shadow + Wetness", (620, 160)
        )
        links.new(shadow_mix.outputs["Shader"], combined.inputs["Shader"])
        links.new(
            wet_mix.outputs["Shader"],
            shader_nodes.socket_by_identifier(combined.inputs, "Shader_001"),
        )
        links.new(combined.outputs["Shader"], output.inputs["Surface"])

        Mat.surface_render_method = "DITHERED"
        if hasattr(Mat, "use_transparency_overlap"):
            Mat.use_transparency_overlap = False
        if hasattr(Mat, "use_backface_culling"):
            Mat.use_backface_culling = False
>>>>>>> Stashed changes
