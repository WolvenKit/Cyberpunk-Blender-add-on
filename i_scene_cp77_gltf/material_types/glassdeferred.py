<<<<<<< Updated upstream

import bpy

from ..materials.blender.images import imageFromRelPath
from ..materials.blender.nodes import CreateShaderNodeRGB, CreateShaderNodeValue, create_node, loc

from .mat_common import MaterialTypeBase, create_normal_map_rel


class GlassDeferred(MaterialTypeBase):
    def create(self, Data, Mat):
        CurMat = Mat.node_tree
        pBSDF = CurMat.nodes[loc('Principled BSDF')]
        MatOutput = CurMat.nodes['Material Output']
        MatOutput.location = (780, 300)
=======
from ..bartmoss.scalar import clamp01, clamp_scalar
from ..blender import shader_nodes
from ..blender.shader_nodes import assign_socket
from .graph import mix_color_socket, value_socket
from .mat_common import (
    MaterialTypeBase,
    find_input,
    new_labeled_node,
    param_color,
    param_float,
    param_texture_path,
    param_vector,
)
from .normal_math import decode_cp77_normal, tangent_to_normal_map

TEMPLATE = "base\\materials\\glass_deferred.mt"

_DEFAULTS = {
    "UvTilingX": 1.0,
    "UvTilingY": 1.0,
    "UvOffsetX": 0.0,
    "UvOffsetY": 0.0,
    "TintFromVertexPaint": 0.0,
    "TintColorAttenuation": 0.0,
    "FresnelBias": 1.0,
    "NormalStrength": 0.0,
    "SurfaceMetalness": 0.0,
    "GlassMetalness": 0.800000012,
    "MaskOpacity": 0.0,
    "MaskRoughnessBias": 0.0,
    "EmissiveEV": 0.0,
}

_TINT_COLOR = (0.862745098, 0.862745098, 0.862745098, 1.0)
_IDENTITY_TILE = (1.0, 1.0, 0.0, 0.0)
_UNIT = (1.0, 1.0, 1.0, 1.0)

# Glass-lobe roughness is fixed rather than authored.
_GLASS_ROUGHNESS = 0.1
# The fake reflection uses a fixed bias, independent of the FresnelBias parameter.
_REFLECTION_FRESNEL_BIAS = 0.25
_EMISSIVE_CLAMP = 10.0
>>>>>>> Stashed changes

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

<<<<<<< Updated upstream
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
=======
class GlassDeferred(MaterialTypeBase):
    def _texture(self, nodes, links, data, key, location, uv_source, *, non_color):
        path = param_texture_path(data, key)
        if not path:
            return None
        node = self._relative_texture_node(
            nodes,
            path,
            key,
            location,
            non_color=non_color,
            error_label="glass deferred",
            require_image=True,
            extension="REPEAT",
        )
        if node is not None and uv_source is not None:
            links.new(uv_source, node.inputs["Vector"])
        return node

    def _tiled_uv(self, nodes, links, data, location):
        uv = new_labeled_node(nodes, "ShaderNodeUVMap", "Mesh UV", location)
        mapping = new_labeled_node(
            nodes, "ShaderNodeMapping", "TiledUV", (location[0] + 200, location[1])
        )
        links.new(uv.outputs["UV"], mapping.inputs["Vector"])
        mapping.inputs["Location"].default_value = (
            param_float(data, "UvOffsetX", 0.0),
            param_float(data, "UvOffsetY", 0.0),
            0.0,
        )
        mapping.inputs["Scale"].default_value = (
            param_float(data, "UvTilingX", 1.0),
            param_float(data, "UvTilingY", 1.0),
            1.0,
        )
        return uv.outputs["UV"], mapping.outputs["Vector"]
>>>>>>> Stashed changes

    def _normal_uv(self, nodes, links, data, uv_source, location):
        tile = param_vector(data, "NormalTileAndOffset", _IDENTITY_TILE)
        mapping = new_labeled_node(nodes, "ShaderNodeMapping", "NormalUV", location)
        links.new(uv_source, mapping.inputs["Vector"])
        mapping.inputs["Location"].default_value = (float(tile[2]), float(tile[3]), 0.0)
        mapping.inputs["Scale"].default_value = (float(tile[0]), float(tile[1]), 1.0)
        return mapping.outputs["Vector"]

    def _reflection_emissive(
        self, nodes, links, data, normal_socket, geometry, location
    ):
        """Clamp reflected cubemap luminance after Fresnel and emissive scaling to 0..10"""
        reflection = self._texture(
            nodes,
            links,
            data,
            "Reflection",
            (location[0] + 360, location[1]),
            None,
            non_color=False,
        )
        if reflection is None:
            return None

        incoming = geometry.outputs["Incoming"]
        view = shader_nodes.vector_math(
            nodes, links, "SCALE", name="-V", location=(location[0], location[1])
        ).node
        links.new(incoming, view.inputs["Vector"])
        view.inputs["Scale"].default_value = -1.0

<<<<<<< Updated upstream
=======
        reflect = shader_nodes.vector_math(
            nodes,
            links,
            "REFLECT",
            name="reflect(-V, N)",
            location=(location[0] + 180, location[1]),
        ).node
        links.new(view.outputs["Vector"], reflect.inputs["Vector"])
        links.new(
            normal_socket or geometry.outputs["Normal"],
            shader_nodes.socket_by_identifier(reflect.inputs, "Vector_001"),
        )
        links.new(reflect.outputs["Vector"], reflection.inputs["Vector"])

        # Use the fixed authored Fresnel bias for tinting.
        fresnel = new_labeled_node(
            nodes,
            "ShaderNodeFresnel",
            "Reflection Fresnel",
            (location[0] + 360, location[1] - 220),
        )
        fresnel_ior = find_input(fresnel, "IOR")
        if fresnel_ior is not None:
            fresnel_ior.default_value = 1.0 + _REFLECTION_FRESNEL_BIAS * 0.5
        if normal_socket is not None:
            links.new(normal_socket, find_input(fresnel, "Normal"))

        weighted = mix_color_socket(
            nodes,
            links,
            "Reflection x Fresnel",
            reflection.outputs["Color"],
            fresnel.outputs["Factor"],
            1.0,
            (location[0] + 600, location[1]),
            blend_type="MULTIPLY",
            clamp=False,
        )
        # Use reflection luminance as the EV scalar.
        luminance = new_labeled_node(
            nodes,
            "ShaderNodeRGBToBW",
            "RGB_LUMINANCE_WEIGHTS",
            (location[0] + 780, location[1]),
        )
        links.new(weighted, luminance.inputs["Color"])
        scaled = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            luminance.outputs["Val"],
            max(0.0, param_float(data, "EmissiveEV", 0.0)),
            name="EmissiveEV",
            location=(location[0] + 960, location[1]),
        )
        return shader_nodes.math(
            nodes,
            links,
            "MINIMUM",
            scaled,
            _EMISSIVE_CLAMP,
            name="clamp(0, 10)",
            location=(location[0] + 1140, location[1]),
            use_clamp=True,
        )

    def create(self, Data, Mat):
        data = Data if isinstance(Data, dict) else {}
        Mat.use_nodes = True
        tree = Mat.node_tree
        nodes = tree.nodes
        links = tree.links
        nodes.clear()

        output = new_labeled_node(
            nodes, "ShaderNodeOutputMaterial", "Material Output", (900, 0)
        )

        needs_tiled_uv = any(
            param_texture_path(data, key)
            for key in ("GlassTint", "MaskTexture", "Roughness")
        )
        base_uv, tiled_uv = (
            self._tiled_uv(nodes, links, data, (-1900, 300))
            if needs_tiled_uv or param_texture_path(data, "Normal")
            else (None, None)
        )
        normal_uv = (
            self._normal_uv(nodes, links, data, base_uv, (-1500, -420))
            if base_uv is not None and param_texture_path(data, "Normal")
            else None
        )
        geometry = (
            new_labeled_node(nodes, "ShaderNodeNewGeometry", "Geometry", (-1500, -700))
            if param_texture_path(data, "Reflection")
            else None
        )

        glass_tint = self._texture(
            nodes, links, data, "GlassTint", (-1200, 200), tiled_uv, non_color=False
        )
        mask = self._texture(
            nodes, links, data, "MaskTexture", (-1200, 500), tiled_uv, non_color=False
        )
        roughness_texture = self._texture(
            nodes, links, data, "Roughness", (-1200, -100), tiled_uv, non_color=True
        )
        normal_texture = self._texture(
            nodes, links, data, "Normal", (-1200, -420), normal_uv, non_color=True
        )

        # Refraction tint multiplies GlassTint, TintColor, and optional vertex-color tint.
        tint_color = param_color(data, "TintColor", _TINT_COLOR)
        if glass_tint is not None:
            refraction_tint = mix_color_socket(
                nodes,
                links,
                "GlassTint x TintColor",
                glass_tint.outputs["Color"],
                tint_color,
                1.0,
                (-900, 200),
                blend_type="MULTIPLY",
                clamp=False,
            )
        else:
            refraction_tint = tint_color

        vertex_tint = clamp01(param_float(data, "TintFromVertexPaint", 0.0))
        if vertex_tint > 0.0:
            vertex = new_labeled_node(
                nodes, "ShaderNodeVertexColor", "Glass Vertex Color", (-900, 360)
            )
            vertex_factor = mix_color_socket(
                nodes,
                links,
                "TintFromVertexPaint",
                _UNIT,
                vertex.outputs["Color"],
                vertex_tint,
                (-680, 360),
            )
            refraction_tint = mix_color_socket(
                nodes,
                links,
                "Vertex Tinted Glass",
                refraction_tint,
                vertex_factor,
                1.0,
                (-480, 260),
                blend_type="MULTIPLY",
                clamp=False,
            )

        # Scale mask alpha by the authored opacity.
        mask_opacity = clamp01(param_float(data, "MaskOpacity", 0.0))
        if mask is not None and mask_opacity > 0.0:
            diffuse_opacity = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                mask.outputs["Alpha"],
                mask_opacity,
                name="diffuseOpacity",
                location=(-900, 500),
                use_clamp=True,
            )
        else:
            diffuse_opacity = value_socket(nodes, "diffuseOpacity", 0.0, (-900, 500))

        # Decode the two-channel tangent-space normal, scale XY by NormalStrength, then normalize.
        normal_socket = None
        if normal_texture is not None:
            decoder = decode_cp77_normal(
                tree,
                normal_texture.outputs["Color"],
                strength=max(0.0, param_float(data, "NormalStrength", 0.0)),
                location=(-900, -420),
                label="Glass Deferred DirectX Normal",
            )
            normal_socket = tangent_to_normal_map(
                tree,
                decoder.outputs["Color"],
                location=(-620, -420),
                label="Glass Deferred Normal",
            )

        # Surface roughness from the texture; the glass lobe is pinned at 0.1.
        if roughness_texture is not None:
            split = new_labeled_node(
                nodes, "ShaderNodeSeparateColor", "Roughness.x", (-900, -160)
            )
            split.mode = "RGB"
            links.new(
                roughness_texture.outputs["Color"],
                split.inputs["Color"],
            )
            sampled_roughness = split.outputs["Red"]
        else:
            sampled_roughness = value_socket(nodes, "Roughness", 0.0, (-900, -160))
        surface_roughness = shader_nodes.math(
            nodes,
            links,
            "ADD",
            sampled_roughness,
            clamp_scalar(param_float(data, "MaskRoughnessBias", 0.0), -1.0, 1.0),
            name="Surface Roughness",
            location=(-500, -160),
            use_clamp=True,
        )

        glass_bsdf = new_labeled_node(
            nodes, "ShaderNodeBsdfPrincipled", "Glass Lobe", (100, 240)
        )
        assign_socket(links, refraction_tint, find_input(glass_bsdf, "Base Color"))
        for name, value in (
            ("Roughness", _GLASS_ROUGHNESS),
            (
                "Metallic",
                clamp01(
                    param_float(data, "GlassMetalness", _DEFAULTS["GlassMetalness"])
                ),
            ),
            ("Transmission Weight", 0.0),
        ):
            socket = find_input(glass_bsdf, name)
            if socket is not None:
                socket.default_value = value

        # Attenuate the mask color toward the refraction tint.
        if mask is not None:
            attenuation = clamp01(param_float(data, "TintColorAttenuation", 0.0))
            attenuated = mix_color_socket(
                nodes,
                links,
                "TintColorAttenuation",
                _UNIT,
                refraction_tint,
                attenuation,
                (-500, 560),
            )
            surface_base = mix_color_socket(
                nodes,
                links,
                "Surface Base Color",
                mask.outputs["Color"],
                attenuated,
                1.0,
                (-300, 560),
                blend_type="MULTIPLY",
                clamp=False,
            )
        else:
            surface_base = refraction_tint

        surface_bsdf = new_labeled_node(
            nodes, "ShaderNodeBsdfPrincipled", "Surface Lobe", (100, -160)
        )
        assign_socket(links, surface_base, find_input(surface_bsdf, "Base Color"))
        links.new(surface_roughness, find_input(surface_bsdf, "Roughness"))
        for name, value in (
            ("Metallic", clamp01(param_float(data, "SurfaceMetalness", 0.0))),
            ("Transmission Weight", 0.0),
        ):
            socket = find_input(surface_bsdf, name)
            if socket is not None:
                socket.default_value = value

        emissive = (
            self._reflection_emissive(
                nodes, links, data, normal_socket, geometry, (-1500, -900)
            )
            if geometry is not None
            else None
        )
        for node in (glass_bsdf, surface_bsdf):
            if normal_socket is not None:
                socket = find_input(node, "Normal")
                if socket is not None:
                    links.new(normal_socket, socket)
            if emissive is not None:
                strength = find_input(node, "Emission Strength")
                colour = find_input(node, "Emission Color", "Emission")
                if strength is not None:
                    links.new(emissive, strength)
                if colour is not None:
                    colour.default_value = _UNIT

        lobe_mix = new_labeled_node(
            nodes, "ShaderNodeMixShader", "Glass and Surface Lobe Blend", (500, 40)
        )
        links.new(diffuse_opacity, lobe_mix.inputs["Factor"])
        links.new(glass_bsdf.outputs["BSDF"], lobe_mix.inputs["Shader"])
        links.new(
            surface_bsdf.outputs["BSDF"],
            shader_nodes.socket_by_identifier(lobe_mix.inputs, "Shader_001"),
        )
        links.new(lobe_mix.outputs["Shader"], output.inputs["Surface"])

        Mat.diffuse_color = (*tint_color[:3], 1.0)
>>>>>>> Stashed changes
