from ..materials.blender.nodes import CreateShaderNodeTexImage, bsdf_socket_names, loc
from .mat_common import coerce_color, coerce_texture_path, decal_values, resolve_depot_texture, unwrap_param


class Decal:
    def __init__(self, BasePath, image_format):
        self.BasePath = BasePath
        self.image_format = image_format

    def create(self, Data, Mat):
        values = decal_values(
            Data,
            (
                "DiffuseTexture",
                "DiffuseTextureAsMaskTexture",
                "DiffuseColor",
                "DiffuseAlpha",
                "RoughnessTexture",
                "NormalTexture",
                "MetalnessTexture",
            ),
        )
        difftex = coerce_texture_path(values.get("DiffuseTexture")) or None
        DiffuseTextureAsMaskTexture = unwrap_param(
            values.get("DiffuseTextureAsMaskTexture")
        )
        RoughnessTexture = coerce_texture_path(values.get("RoughnessTexture")) or None
        NormalTexture = coerce_texture_path(values.get("NormalTexture")) or None
        DiffuseColor = values.get("DiffuseColor")
        DiffuseAlpha = unwrap_param(values.get("DiffuseAlpha"))
        MetalnessTexture = coerce_texture_path(values.get("MetalnessTexture")) or None

        resolved_diffuse = resolve_depot_texture(
            difftex, self.image_format, self.BasePath
        ) if difftex else None
        resolved_roughness = resolve_depot_texture(
            RoughnessTexture, self.image_format, self.BasePath
        ) if RoughnessTexture else None
        resolved_normal = resolve_depot_texture(
            NormalTexture, self.image_format, self.BasePath
        ) if NormalTexture else None
        resolved_metalness = resolve_depot_texture(
            MetalnessTexture, self.image_format, self.BasePath
        ) if MetalnessTexture else None

        CurMat = Mat.node_tree
        Prin_BSDF = CurMat.nodes[loc('Principled BSDF')]
        sockets = bsdf_socket_names()
        Prin_BSDF.inputs[sockets['Specular']].default_value = 0.5
        TexCoordinate = CurMat.nodes.new("ShaderNodeTexCoord")
        TexCoordinate.location = (-1000, 300)
        if resolved_diffuse:
            dImgNode = CreateShaderNodeTexImage(
                CurMat, resolved_diffuse, -800, 300, 'DiffuseTexture', self.image_format
                )
            RGBnode = CurMat.nodes.new("ShaderNodeRGB")
            RGBnode.location = (-700, 500)
            RGBnode.outputs[0].default_value = coerce_color(
                unwrap_param(DiffuseColor),
                (1.0, 1.0, 1.0, 1.0),
            )
            mulNode = CurMat.nodes.new("ShaderNodeMixRGB")
            mulNode.blend_type = 'MULTIPLY'
            mulNode.inputs[0].default_value = 1.0
            mulNode.location = (-400, 300)
            CurMat.links.new(dImgNode.outputs[0], mulNode.inputs[2])
            CurMat.links.new(RGBnode.outputs[0], mulNode.inputs[1])
            CurMat.links.new(mulNode.outputs[0], Prin_BSDF.inputs['Base Color'])
            CurMat.links.new(TexCoordinate.outputs[0], dImgNode.inputs[0])
            mulNode1 = CurMat.nodes.new("ShaderNodeMath")
            mulNode1.name = "CP77 Base Decal Alpha"
            mulNode1.label = "CP77 Base Decal Alpha"
            mulNode1.operation = 'MULTIPLY'
            mulNode1.location = (-400, 100)
            if "alpha" in Data:
                DiffuseAlpha = float(unwrap_param(Data["alpha"]))

            if DiffuseAlpha:
                mulNode1.inputs[0].default_value = DiffuseAlpha
            else:
                mulNode1.inputs[0].default_value = 1.0

            if "enableMask" in Data:
                if Data["enableMask"] and DiffuseTextureAsMaskTexture is None:
                    DiffuseTextureAsMaskTexture = 0
                else:
                    DiffuseTextureAsMaskTexture = 1

            if DiffuseTextureAsMaskTexture:
                CurMat.links.new(dImgNode.outputs[0], mulNode1.inputs[1])
            else:
                CurMat.links.new(dImgNode.outputs[1], mulNode1.inputs[1])
            CurMat.links.new(mulNode1.outputs[0], Prin_BSDF.inputs['Alpha'])
        else:
            CurMat.nodes[loc('Principled BSDF')].inputs['Alpha'].default_value = 0
            print(f"Texture is not found: {difftex}")
        Mat["cp77SectorAlphaHandled"] = True

        if resolved_roughness:
            rImgNode = CreateShaderNodeTexImage(
                CurMat, resolved_roughness, -800, 0, 'RoughnessTexture', self.image_format
                )
            rImgNode.image.colorspace_settings.name = 'Non-Color'
            reroute = CurMat.nodes.new(type="NodeReroute")
            reroute.location = (-335, -100)
            CurMat.links.new(rImgNode.outputs[0], reroute.inputs[0])
            CurMat.links.new(reroute.outputs[0], Prin_BSDF.inputs['Roughness'])
            CurMat.links.new(TexCoordinate.outputs[0], rImgNode.inputs[0])

        if resolved_normal:
            nImgNode = CreateShaderNodeTexImage(
                CurMat, resolved_normal, -800, -300, 'NormalTexture', self.image_format
                )
            nImgNode.image.colorspace_settings.name = 'Non-Color'
            toNormalNode = CurMat.nodes.new('ShaderNodeNormalMap')
            toNormalNode.location = (-400, -120)
            CurMat.links.new(nImgNode.outputs[0], toNormalNode.inputs[1])
            CurMat.links.new(toNormalNode.outputs[0], Prin_BSDF.inputs['Normal'])
            CurMat.links.new(TexCoordinate.outputs[0], nImgNode.inputs[0])

        if resolved_metalness:
            mImgNode = CreateShaderNodeTexImage(
                CurMat, resolved_metalness, -800, 150, 'MetalnessTexture', self.image_format
                )
            mImgNode.image.colorspace_settings.name = 'Non-Color'
            reroute2 = CurMat.nodes.new(type="NodeReroute")
            reroute2.location = (-275, 115)
            CurMat.links.new(mImgNode.outputs[0], reroute2.inputs[0])
            CurMat.links.new(reroute2.outputs[0], Prin_BSDF.inputs['Metallic'])
            CurMat.links.new(TexCoordinate.outputs[0], mImgNode.inputs[0])

        # The above is  the code thats for the import plugin below is to allow testing/dev, you can run this file to import something


