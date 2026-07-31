from ..materials.blender.nodes import bsdf_socket_names, create_node, loc

from .graph import mix_scalar_socket
from .mat_common import (
    MaterialTypeBase,
    create_scene_time_value,
    param_color,
    param_float,
    param_vector,
)


LAYER_COUNT = 4


class MetalBaseUI(MaterialTypeBase):

    def __init__(self, BasePath, image_format, ProjPath, render_texture=None):
        super().__init__(BasePath, image_format, ProjPath)
        self.render_texture = render_texture

    def _create_mod_uv(self, CurMat, Data):
        geometry = create_node(CurMat.nodes, "ShaderNodeNewGeometry", (-2400, -100))
        tangent = create_node(CurMat.nodes, "ShaderNodeTangent", (-2400, -180))
        tangent.direction_type = 'UV_MAP'

        binormal = create_node(CurMat.nodes, "ShaderNodeVectorMath", (-2200, -180),
                               operation='CROSS_PRODUCT')
        CurMat.links.new(geometry.outputs['Normal'], binormal.inputs[0])
        CurMat.links.new(tangent.outputs['Tangent'], binormal.inputs[1])

        left_right = create_node(CurMat.nodes, "ShaderNodeVectorMath", (-2000, -140),
                                 operation='DOT_PRODUCT', label="leftRightDot")
        CurMat.links.new(geometry.outputs['Incoming'], left_right.inputs[0])
        CurMat.links.new(tangent.outputs['Tangent'], left_right.inputs[1])

        top_down = create_node(CurMat.nodes, "ShaderNodeVectorMath", (-2000, -200),
                               operation='DOT_PRODUCT', label="topDownDot")
        CurMat.links.new(geometry.outputs['Incoming'], top_down.inputs[0])
        CurMat.links.new(binormal.outputs['Vector'], top_down.inputs[1])

        slide = create_node(CurMat.nodes, "ShaderNodeMath", (-1820, -200),
                            operation='MULTIPLY', label="FixForVerticalSlide")
        slide.inputs[1].default_value = param_float(Data, "FixForVerticalSlide", 1.0)
        CurMat.links.new(top_down.outputs['Value'], slide.inputs[0])

        mod_uv = create_node(CurMat.nodes, "ShaderNodeCombineXYZ", (-1650, -170), label="modUV")
        CurMat.links.new(left_right.outputs['Value'], mod_uv.inputs[0])
        CurMat.links.new(slide.outputs['Value'], mod_uv.inputs[1])
        return mod_uv

    def _create_base_uv(self, CurMat, Data):
        part_uv = param_vector(Data, "TexturePartUV", (0.0, 0.0, 1.0, 1.0))
        part_size = (part_uv[2] - part_uv[0], part_uv[3] - part_uv[1])
        flip = param_float(Data, "VerticalFlipEnabled", 0.0) >= 0.5

        texCoord = create_node(CurMat.nodes, "ShaderNodeTexCoord", (-2400, 400))
        separate = create_node(CurMat.nodes, "ShaderNodeSeparateXYZ", (-2200, 400))
        CurMat.links.new(texCoord.outputs['UV'], separate.inputs[0])

        invert_v = create_node(CurMat.nodes, "ShaderNodeMath", (-2050, 360),
                               operation='SUBTRACT', label="1-v")
        invert_v.inputs[0].default_value = 1.0
        CurMat.links.new(separate.outputs['Y'], invert_v.inputs[1])

        remap_u = create_node(CurMat.nodes, "ShaderNodeMath", (-1880, 420),
                              operation='MULTIPLY_ADD', label="TexturePartUV.u")
        remap_u.inputs[1].default_value = part_size[0]
        remap_u.inputs[2].default_value = part_uv[0]
        CurMat.links.new(separate.outputs['X'], remap_u.inputs[0])

        remap_v = create_node(CurMat.nodes, "ShaderNodeMath", (-1880, 360),
                              operation='MULTIPLY_ADD', label="TexturePartUV.v")
        remap_v.inputs[1].default_value = -part_size[1] if flip else part_size[1]
        remap_v.inputs[2].default_value = (1.0 - part_uv[1]) if flip else part_uv[1]
        CurMat.links.new(invert_v.outputs['Value'], remap_v.inputs[0])

        base_uv = create_node(CurMat.nodes, "ShaderNodeCombineXYZ", (-1700, 400), label="newUV")
        CurMat.links.new(remap_u.outputs['Value'], base_uv.inputs[0])
        CurMat.links.new(remap_v.outputs['Value'], base_uv.inputs[1])
        return base_uv, part_size, texCoord

    def _create_scanlines(self, CurMat, Data, texCoord):
        image = self._load_relative_image(
            Data.get("ScanlineTexture"),
            non_color=True,
            error_label="scanline",
        )
        if image is None:
            return None

        density = param_vector(Data, "ScanlinesDensity", (1.0, 1.0, 0.0, 0.0))
        time = create_scene_time_value(CurMat, -2200, 120)
        scroll_u = create_node(CurMat.nodes, "ShaderNodeMath", (-2030, 150), operation='MULTIPLY')
        scroll_u.inputs[1].default_value = density[2]
        CurMat.links.new(time.outputs[0], scroll_u.inputs[0])
        scroll_v = create_node(CurMat.nodes, "ShaderNodeMath", (-2030, 100), operation='MULTIPLY')
        scroll_v.inputs[1].default_value = density[3]
        CurMat.links.new(time.outputs[0], scroll_v.inputs[0])

        scroll = create_node(CurMat.nodes, "ShaderNodeCombineXYZ", (-1880, 130))
        CurMat.links.new(scroll_u.outputs['Value'], scroll.inputs[0])
        CurMat.links.new(scroll_v.outputs['Value'], scroll.inputs[1])

        scaled = create_node(CurMat.nodes, "ShaderNodeVectorMath", (-1880, 200),
                             operation='MULTIPLY', label="ScanlinesDensity")
        scaled.inputs[1].default_value = (density[0], density[1], 1.0)
        CurMat.links.new(texCoord.outputs['UV'], scaled.inputs[0])

        offset = create_node(CurMat.nodes, "ShaderNodeVectorMath", (-1700, 180), operation='ADD')
        CurMat.links.new(scaled.outputs['Vector'], offset.inputs[0])
        CurMat.links.new(scroll.outputs['Vector'], offset.inputs[1])

        node = create_node(CurMat.nodes, "ShaderNodeTexImage", (-1500, 180),
                           label="ScanlineTexture", image=image)
        CurMat.links.new(offset.outputs['Vector'], node.inputs[0])

        modulation = create_node(CurMat.nodes, "ShaderNodeMapRange", (-1300, 180),
                                 label="ScanlinesIntensity")
        modulation.inputs[1].default_value = 0.0
        modulation.inputs[2].default_value = 1.0
        modulation.inputs[3].default_value = param_float(Data, "ScanlinesIntensity", 1.0)
        modulation.inputs[4].default_value = 1.0
        CurMat.links.new(node.outputs['Color'], modulation.inputs[0])
        return modulation

    def _create_layers(self, CurMat, Data, base_uv, mod_uv, part_size, scanlines, image):
        intensity = param_vector(Data, "IntensityPerLayer", (1.0, 0.0, 0.0, 0.0))
        separation = min(max(param_float(Data, "LayersSeparation", 0.0) * part_size[0], 0.0), 0.5)

        samples = []
        for index in range(LAYER_COUNT):
            y = 900 - index * 260
            if index == 0:
                uv_out = base_uv.outputs[0]
            else:
                step = create_node(CurMat.nodes, "ShaderNodeVectorMath", (-1500, y + 60),
                                   operation='SCALE', label=f"layerSeparation x{index}")
                step.inputs[3].default_value = separation * index
                CurMat.links.new(mod_uv.outputs[0], step.inputs[0])

                offset = create_node(CurMat.nodes, "ShaderNodeVectorMath", (-1340, y + 60),
                                     operation='ADD')
                CurMat.links.new(base_uv.outputs[0], offset.inputs[0])
                CurMat.links.new(step.outputs['Vector'], offset.inputs[1])
                uv_out = offset.outputs['Vector']

            texture = create_node(CurMat.nodes, "ShaderNodeTexImage", (-1150, y),
                                  label=f"UIRenderTexture L{index + 1}", image=image)
            texture.extension = 'EXTEND'
            CurMat.links.new(uv_out, texture.inputs[0])

            weighted = create_node(CurMat.nodes, "ShaderNodeMixRGB", (-900, y),
                                   blend_type='MULTIPLY')
            weighted.inputs[0].default_value = 1.0
            weighted.inputs[2].default_value = (intensity[index],) * 3 + (1.0,)
            CurMat.links.new(texture.outputs['Color'], weighted.inputs[1])

            if index > 0 and scanlines is not None:
                modulated = create_node(CurMat.nodes, "ShaderNodeMixRGB", (-730, y),
                                        blend_type='MULTIPLY')
                modulated.inputs[0].default_value = 1.0
                CurMat.links.new(weighted.outputs[0], modulated.inputs[1])
                CurMat.links.new(scanlines.outputs['Result'], modulated.inputs[2])
                samples.append(modulated.outputs[0])
            else:
                samples.append(weighted.outputs[0])

        composite = samples[LAYER_COUNT - 1]
        for index in range(LAYER_COUNT - 2, -1, -1):
            screen = create_node(CurMat.nodes, "ShaderNodeMixRGB", (-550, 200 + index * 120),
                                 blend_type='SCREEN', label=f"screen L{index + 1}")
            screen.inputs[0].default_value = 1.0
            CurMat.links.new(composite, screen.inputs[1])
            CurMat.links.new(samples[index], screen.inputs[2])
            composite = screen.outputs[0]
        return composite

    def _create_dirt_mask(self, CurMat, Data):
        if "DirtTexture" not in Data:
            return None

        contrast = param_float(Data, "DirtContrast", 1.0)
        dirt_color = param_color(Data, "DirtColor", (1.0, 1.0, 1.0, 1.0))

        image = self._load_relative_image(
            Data["DirtTexture"],
            non_color=True,
            error_label="dirt",
        )
        if image is None:
            return None
        node = create_node(CurMat.nodes, "ShaderNodeTexImage", (-1500, -500),
                           label="DirtTexture", image=image)
                           
        scaled = create_node(CurMat.nodes, "ShaderNodeMath", (-1300, -500),
                             operation='MULTIPLY', label="DirtContrast")
        scaled.inputs[1].default_value = contrast
        scaled.use_clamp = True
        CurMat.links.new(node.outputs['Alpha'], scaled.inputs[0])

        squared = create_node(CurMat.nodes, "ShaderNodeMath", (-1150, -500), operation='MULTIPLY')
        CurMat.links.new(node.outputs['Alpha'], squared.inputs[0])
        CurMat.links.new(scaled.outputs['Value'], squared.inputs[1])

        centred = create_node(CurMat.nodes, "ShaderNodeMath", (-1000, -500), operation='SUBTRACT')
        centred.inputs[1].default_value = 0.5
        CurMat.links.new(squared.outputs['Value'], centred.inputs[0])

        recontrast = create_node(CurMat.nodes, "ShaderNodeMath", (-850, -500),
                                 operation='MULTIPLY_ADD')
        recontrast.inputs[1].default_value = contrast
        recontrast.inputs[2].default_value = 0.5
        recontrast.use_clamp = True
        CurMat.links.new(centred.outputs['Value'], recontrast.inputs[0])

        masked = create_node(CurMat.nodes, "ShaderNodeMath", (-700, -500),
                             operation='MULTIPLY', label="DirtColor.w")
        masked.inputs[1].default_value = dirt_color[3]
        CurMat.links.new(recontrast.outputs['Value'], masked.inputs[0])
        return masked

    def create(self, Data, Mat):
        CurMat = Mat.node_tree
        pBSDF = CurMat.nodes[loc('Principled BSDF')]
        sockets = bsdf_socket_names()

        image = self.render_texture
        if image is None and "UIRenderTexture" in Data:
            image = self._image_from_rel_path(Data["UIRenderTexture"])

        base_uv, part_size, texCoord = self._create_base_uv(CurMat, Data)
        mod_uv = self._create_mod_uv(CurMat, Data)
        scanlines = self._create_scanlines(CurMat, Data, texCoord)
        composite = self._create_layers(CurMat, Data, base_uv, mod_uv, part_size, scanlines, image)

        desaturate = create_node(CurMat.nodes, "ShaderNodeHueSaturation", (-400, 400))
        desaturate.inputs['Saturation'].default_value = 0.96
        CurMat.links.new(composite, desaturate.inputs['Color'])
        composite = desaturate.outputs['Color']

        tint = param_color(Data, "Tint", (1.0, 1.0, 1.0, 1.0))
        tinted = create_node(CurMat.nodes, "ShaderNodeMixRGB", (-250, 400), blend_type='MULTIPLY')
        tinted.inputs[0].default_value = 1.0
        tinted.inputs[2].default_value = tint[:3] + (1.0,)
        CurMat.links.new(composite, tinted.inputs[1])
        base_color = tinted.outputs[0]

        dirt_mask = self._create_dirt_mask(CurMat, Data)
        emission_intensity = None

        if dirt_mask is not None:
            dirt_color = param_color(Data, "DirtColor", (1.0, 1.0, 1.0, 1.0))
            contrast = param_float(Data, "DirtContrast", 1.0)

            dirt_mix = create_node(CurMat.nodes, "ShaderNodeMixRGB", (-100, 400), label="DirtColor")
            dirt_mix.inputs[2].default_value = dirt_color[:3] + (1.0,)
            CurMat.links.new(dirt_mask.outputs['Value'], dirt_mix.inputs[0])
            CurMat.links.new(base_color, dirt_mix.inputs[1])
            base_color = dirt_mix.outputs[0]
            attenuation = create_node(CurMat.nodes, "ShaderNodeMath", (-400, -700),
                                      operation='SUBTRACT', label="DirtEmissiveAttenuation")
            attenuation.inputs[0].default_value = 1.0 + param_float(Data, "DirtEmissiveAttenuation", 0.0)
            attenuation.use_clamp = True
            CurMat.links.new(dirt_mask.outputs['Value'], attenuation.inputs[1])

            centred = create_node(CurMat.nodes, "ShaderNodeMath", (-250, -700), operation='SUBTRACT')
            centred.inputs[1].default_value = 0.5
            CurMat.links.new(attenuation.outputs['Value'], centred.inputs[0])

            emission_intensity = create_node(CurMat.nodes, "ShaderNodeMath", (-100, -700),
                                             operation='MULTIPLY_ADD', label="emissionIntensity")
            emission_intensity.inputs[1].default_value = contrast * 1.5
            emission_intensity.inputs[2].default_value = 0.5
            emission_intensity.use_clamp = True
            CurMat.links.new(centred.outputs['Value'], emission_intensity.inputs[0])

            metalness = create_node(CurMat.nodes, "ShaderNodeMapRange", (-100, -900),
                                    label="Metalness")
            metalness.inputs[3].default_value = param_float(Data, "Metalness", 0.9)
            metalness.inputs[4].default_value = 0.0
            CurMat.links.new(dirt_mask.outputs['Value'], metalness.inputs[0])
            CurMat.links.new(metalness.outputs['Result'], pBSDF.inputs['Metallic'])

            roughness = create_node(CurMat.nodes, "ShaderNodeMapRange", (-100, -1050),
                                    label="Roughness")
            roughness.inputs[3].default_value = param_float(Data, "RoughnessScale", 0.1)
            roughness.inputs[4].default_value = param_float(Data, "DirtRoughness", 0.1)
            CurMat.links.new(dirt_mask.outputs['Value'], roughness.inputs[0])
            CurMat.links.new(roughness.outputs['Result'], pBSDF.inputs['Roughness'])
        else:
            pBSDF.inputs['Metallic'].default_value = param_float(Data, "Metalness", 0.9)
            pBSDF.inputs['Roughness'].default_value = param_float(Data, "RoughnessScale", 0.1)

        channels = create_node(CurMat.nodes, "ShaderNodeSeparateXYZ", (60, 250))
        CurMat.links.new(base_color, channels.inputs[0])
        max_rg = create_node(CurMat.nodes, "ShaderNodeMath", (200, 250), operation='MAXIMUM')
        CurMat.links.new(channels.outputs['X'], max_rg.inputs[0])
        CurMat.links.new(channels.outputs['Y'], max_rg.inputs[1])
        max_rgb = create_node(CurMat.nodes, "ShaderNodeMath", (340, 250), operation='MAXIMUM',
                              label="bright")
        CurMat.links.new(max_rg.outputs['Value'], max_rgb.inputs[0])
        CurMat.links.new(channels.outputs['Z'], max_rgb.inputs[1])
        forced = param_color(Data, "ForcedTint", (1.0, 1.0, 1.0, 0.0))
        if forced[3] > 0.0:
            forced_scale = create_node(CurMat.nodes, "ShaderNodeMixRGB", (480, 400),
                                       blend_type='MULTIPLY', label="ForcedTint")
            forced_scale.inputs[0].default_value = 1.0
            forced_scale.inputs[2].default_value = forced[:3] + (1.0,)
            CurMat.links.new(max_rgb.outputs['Value'], forced_scale.inputs[1])

            forced_mix = create_node(CurMat.nodes, "ShaderNodeMixRGB", (640, 400))
            forced_mix.inputs[0].default_value = forced[3]
            CurMat.links.new(base_color, forced_mix.inputs[1])
            CurMat.links.new(forced_scale.outputs[0], forced_mix.inputs[2])
            base_color = forced_mix.outputs[0]
        fix_for_black = param_float(Data, "FixForBlack", 0.0)
        emissive_bright = max_rgb.outputs['Value']
        if fix_for_black > 0.0:
            doubled = create_node(CurMat.nodes, "ShaderNodeMath", (480, 250),
                                  operation='MULTIPLY', label="FixForBlack")
            doubled.inputs[1].default_value = 2.0
            doubled.use_clamp = True
            CurMat.links.new(max_rgb.outputs['Value'], doubled.inputs[0])

            emissive_bright = mix_scalar_socket(
                CurMat.nodes,
                CurMat.links,
                "FixForBlack brightness",
                (640, 250),
                1.0,
                doubled.outputs['Value'],
                min(max(fix_for_black, 0.0), 1.0),
            )

            lift_amount = create_node(CurMat.nodes, "ShaderNodeMath", (640, 120),
                                      operation='SUBTRACT')
            lift_amount.inputs[0].default_value = 1.0
            CurMat.links.new(emissive_bright, lift_amount.inputs[1])

            lift_scaled = create_node(CurMat.nodes, "ShaderNodeMath", (800, 120),
                                      operation='MULTIPLY')
            lift_scaled.inputs[1].default_value = 0.03 * fix_for_black
            CurMat.links.new(lift_amount.outputs['Value'], lift_scaled.inputs[0])

            lift_rgb = create_node(CurMat.nodes, "ShaderNodeCombineXYZ", (800, 60))
            for socket in range(3):
                CurMat.links.new(lift_scaled.outputs['Value'], lift_rgb.inputs[socket])

            lift = create_node(CurMat.nodes, "ShaderNodeMixRGB", (960, 250), blend_type='ADD',
                               label="black lift")
            lift.inputs[0].default_value = 1.0
            CurMat.links.new(base_color, lift.inputs[1])
            CurMat.links.new(lift_rgb.outputs['Vector'], lift.inputs[2])
            base_color = lift.outputs[0]

        emissive_ev = param_float(Data, "EmissiveEV", 1.0)
        floor_mix = create_node(CurMat.nodes, "ShaderNodeMixRGB", (1120, 400), label="base floor")
        floor_mix.inputs[0].default_value = min(max(emissive_ev, 0.0), 1.0)
        floor_mix.inputs[1].default_value = (0.03, 0.03, 0.03, 1.0)
        CurMat.links.new(base_color, floor_mix.inputs[2])

        CurMat.links.new(floor_mix.outputs[0], pBSDF.inputs['Base Color'])
        CurMat.links.new(base_color, pBSDF.inputs[sockets['Emission']])
        strength = create_node(CurMat.nodes, "ShaderNodeMath", (1120, 120), operation='MULTIPLY',
                               label="EmissiveEV")
        strength.inputs[1].default_value = emissive_ev
        CurMat.links.new(emissive_bright, strength.inputs[0])

        if emission_intensity is not None:
            attenuated = create_node(CurMat.nodes, "ShaderNodeMath", (1280, 120),
                                     operation='MULTIPLY')
            CurMat.links.new(strength.outputs['Value'], attenuated.inputs[0])
            CurMat.links.new(emission_intensity.outputs['Value'], attenuated.inputs[1])
            CurMat.links.new(attenuated.outputs['Value'], pBSDF.inputs['Emission Strength'])
        else:
            CurMat.links.new(strength.outputs['Value'], pBSDF.inputs['Emission Strength'])


used_params = (
    "UIRenderTexture",
    "TexturePartUV",
    "VerticalFlipEnabled",
    "ScanlineTexture",
    "ScanlinesDensity",
    "ScanlinesIntensity",
    "LayersSeparation",
    "IntensityPerLayer",
    "Metalness",
    "RoughnessScale",
    "EmissiveEV",
    "DirtTexture",
    "DirtColor",
    "DirtRoughness",
    "DirtEmissiveAttenuation",
    "DirtContrast",
    "Tint",
    "ForcedTint",
    "FixForBlack",
    "FixForVerticalSlide",
)

unsupported_params = (
    "RenderTextureScale",
    "IsBroken",
    "EmissiveEVRaytracingBias",
    "EmissiveDirectionality",
    "EnableRaytracedEmissive",
)
