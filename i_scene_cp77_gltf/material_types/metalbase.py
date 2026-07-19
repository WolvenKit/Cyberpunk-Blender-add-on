from ..main.common import *

from .mat_common import create_global_normal_rel


class MetalBase:
    def __init__(self, BasePath, image_format, ProjPath, enableMask):
        self.BasePath = BasePath
        self.ProjPath = ProjPath
        self.enableMask = enableMask
        self.image_format = image_format

    def _image_from_rel_path(self, reference, is_normal=False):
        if not reference:
            return None
        return imageFromRelPath(
                reference, self.image_format, DepotPath=self.BasePath, ProjPath=self.ProjPath, isNormal=is_normal,
                )

    def _create_layer_tile_mapping(self, CurMat, Data):
        if "LayerTile" not in Data:
            return None

        texCoord = CurMat.nodes.new("ShaderNodeTexCoord")
        texCoord.location = (-2200, 400)
        texCoord.hide = True

        mappingNode = CurMat.nodes.new("ShaderNodeMapping")
        mappingNode.location = (-2000, 400)
        mappingNode.label = "LayerTile"
        mappingNode.hide = True

        tileValue = Data["LayerTile"]
        if tileValue <= 0:
            tileValue = 1.0
        mappingNode.inputs[3].default_value = (tileValue, tileValue, 1.0)
        CurMat.links.new(texCoord.outputs[2], mappingNode.inputs[0])
        return mappingNode

    def _create_detail_mapping(self, CurMat, Data):
        texCoord = CurMat.nodes.new("ShaderNodeTexCoord")
        texCoord.location = (-2300, 0)

        mappingNode = CurMat.nodes.new("ShaderNodeMapping")
        mappingNode.location = (-2100, 0)
        if "DetailU" in Data and "DetailV" in Data:
            mappingNode.inputs[3].default_value = (Data["DetailU"], Data["DetailV"], 0)
        CurMat.links.new(texCoord.outputs[2], mappingNode.inputs[0])
        return mappingNode

    def _create_image_node(self, CurMat, Data, key, loc, label=None, is_normal=False):
        if key not in Data:
            return None, None
        image = self._image_from_rel_path(Data[key], is_normal=is_normal)
        node = create_node(CurMat.nodes, "ShaderNodeTexImage", loc, label=label or key, image=image)
        return node, image

    def _create_pbr_channel(self, Data, CurMat, channel_name, bsdf_input, layerTileMapping, y_loc):
        node, _ = self._create_image_node(CurMat, Data, channel_name, (-1400, y_loc), is_normal=True)
        if node is None:
            return None

        if layerTileMapping:
            CurMat.links.new(layerTileMapping.outputs[0], node.inputs[0])

        math_node = create_node(CurMat.nodes, "ShaderNodeMath", (-1050, y_loc), operation='MULTIPLY_ADD')
        math_node.inputs[1].default_value = 1
        math_node.inputs[2].default_value = 0

        scale_key = f"{channel_name}Scale"
        bias_key = f"{channel_name}Bias"
        if scale_key in Data:
            scale = CreateShaderNodeValue(CurMat, Data[scale_key], -1400, y_loc - 50, scale_key)
            CurMat.links.new(scale.outputs[0], math_node.inputs[1])
        if bias_key in Data:
            bias = CreateShaderNodeValue(CurMat, Data[bias_key], -1400, y_loc - 100, bias_key)
            CurMat.links.new(bias.outputs[0], math_node.inputs[2])

        CurMat.links.new(node.outputs[0], math_node.inputs[0])
        CurMat.links.new(math_node.outputs[0], bsdf_input)
        return math_node

    def _create_normal_nodes(self, CurMat, Data, pBSDF, layerTileMapping, detailMapping):
        if "Normal" not in Data:
            return None

        nMap = create_global_normal_rel(
                CurMat, Data["Normal"], -1000, -200, 'Normal', self.image_format, self.BasePath, self.ProjPath,
                )
        if layerTileMapping:
            try:
                CurMat.links.new(layerTileMapping.outputs[0], nMap.inputs[0])
            except Exception:
                pass

        normalVectorize = CurMat.nodes.new("ShaderNodeVectorMath")
        normalVectorize.operation = 'MULTIPLY_ADD'
        normalVectorize.location = (-1050, -200)
        normalVectorize.hide = True
        normalVectorize.inputs[1].default_value = 2, 2, 0
        normalVectorize.inputs[2].default_value = -1, -1, 0

        normalCreateVecZGroup = CreateCalculateVecNormalZ(CurMat, -800, -350)
        normalMap = create_node(CurMat.nodes, "ShaderNodeNormalMap", (-500, -350))

        CurMat.links.new(nMap.outputs[0], normalVectorize.inputs[0])

        detail_normal = None
        if "DetailNormal" in Data:
            dNNode = create_global_normal_rel(
                    CurMat, Data["DetailNormal"], -1000, -500, 'Normal', self.image_format, self.BasePath,
                    self.ProjPath,
                    )
            if detailMapping:
                CurMat.links.new(detailMapping.outputs[0], dNNode.inputs[0])

            normalDetVectorize = CurMat.nodes.new("ShaderNodeVectorMath")
            normalDetVectorize.operation = 'MULTIPLY_ADD'
            normalDetVectorize.location = (-1050, -500)
            normalDetVectorize.hide = True
            normalDetVectorize.inputs[1].default_value = 2, 2, 0
            normalDetVectorize.inputs[2].default_value = -1, -1, 0

            normalAdd = create_node(CurMat.nodes, "ShaderNodeVectorMath", (-1050, -350), operation='ADD')
            CurMat.links.new(dNNode.outputs[0], normalDetVectorize.inputs[0])
            CurMat.links.new(normalVectorize.outputs[0], normalAdd.inputs[0])
            CurMat.links.new(normalDetVectorize.outputs[0], normalAdd.inputs[1])
            CurMat.links.new(normalAdd.outputs[0], normalCreateVecZGroup.inputs[0])
            detail_normal = dNNode
        else:
            CurMat.links.new(normalVectorize.outputs[0], normalCreateVecZGroup.inputs[0])

        CurMat.links.new(normalCreateVecZGroup.outputs[0], normalMap.inputs[1])
        CurMat.links.new(normalMap.outputs[0], pBSDF.inputs['Normal'])
        return detail_normal

    def create(self, Data, Mat):
        CurMat = Mat.node_tree
        pBSDF = CurMat.nodes[loc('Principled BSDF')]
        sockets = bsdf_socket_names()
        has_detail = all(key in Data for key in ("BaseColor", "DetailColor", "Normal", "DetailNormal"))

        layerTileMapping = self._create_layer_tile_mapping(CurMat, Data)
        detailMapping = self._create_detail_mapping(CurMat, Data) if has_detail else None

        mixRGB = create_node(CurMat.nodes, "ShaderNodeMixRGB", (-800, 500), blend_type='MULTIPLY')
        mixRGB.inputs[0].default_value = 1
        CurMat.links.new(mixRGB.outputs[0], pBSDF.inputs['Base Color'])

        bColNode = None
        bcolImg = None
        if "BaseColor" in Data:
            bColNode, bcolImg = self._create_image_node(CurMat, Data, "BaseColor", (-1400, 650))
            if layerTileMapping:
                CurMat.links.new(layerTileMapping.outputs[0], bColNode.inputs[0])

        dColNode = None
        if "DetailColor" in Data:
            dColNode, _ = self._create_image_node(CurMat, Data, "DetailColor", (-1400, 950))
            if detailMapping:
                CurMat.links.new(detailMapping.outputs[0], dColNode.inputs[0])

        if bColNode is not None and dColNode is not None and has_detail:
            dColmul = create_node(CurMat.nodes, "ShaderNodeMixRGB", (-800, 650), blend_type='MULTIPLY')
            dColmul.inputs[0].default_value = 1
            CurMat.links.new(dColNode.outputs[0], dColmul.inputs[1])
            CurMat.links.new(bColNode.outputs[0], dColmul.inputs[2])
            CurMat.links.new(dColmul.outputs[0], mixRGB.inputs[1])
        elif bColNode is not None:
            CurMat.links.new(bColNode.outputs[0], mixRGB.inputs[1])

        self._create_pbr_channel(Data, CurMat, "Metalness", pBSDF.inputs['Metallic'], layerTileMapping, 250)
        self._create_pbr_channel(Data, CurMat, "Roughness", pBSDF.inputs['Roughness'], layerTileMapping, 50)

        dNNode = self._create_normal_nodes(CurMat, Data, pBSDF, layerTileMapping, detailMapping)

        if "BaseColorScale" in Data:
            dColScale = CreateShaderNodeRGB(CurMat, Data["BaseColorScale"], -1400, 500, 'BaseColorScale', True)
            baseColorGamma = CurMat.nodes.new("ShaderNodeGamma")
            baseColorGamma.location = (-1050, 500)
            baseColorGamma.inputs[1].default_value = 2.2
            baseColorGamma.hide = True
            CurMat.links.new(dColScale.outputs[0], baseColorGamma.inputs[0])
            CurMat.links.new(baseColorGamma.outputs[0], mixRGB.inputs[2])

        if 'GradientMap' in Data:
            gradImg = self._image_from_rel_path(Data["GradientMap"])
            grad_image_node = create_node(
                CurMat.nodes, "ShaderNodeTexImage", (-800, 0), label="GradientMap", image=gradImg
                )
            color_ramp_node = CreateGradMapRamp(CurMat, grad_image_node)
            CurMat.links.new(mixRGB.outputs[0], color_ramp_node.inputs[0])
            CurMat.links.new(color_ramp_node.outputs[0], pBSDF.inputs['Base Color'])

        if "AlphaThreshold" in Data:
            aThreshold = CreateShaderNodeValue(CurMat, Data["AlphaThreshold"], -1400, 400, "AlphaThreshold")
        else:
            aThreshold = CreateShaderNodeValue(CurMat, 1.0, -1400, 400, "AlphaThreshold")

        maskThreshold = create_node(CurMat.nodes, "ShaderNodeMath", (-1050, 400), operation='GREATER_THAN')
        if bColNode is not None:
            if dColNode is not None and has_detail:
                alphaMultiply = create_node(CurMat.nodes, "ShaderNodeMath", (-1050, 800), operation='MULTIPLY')
                CurMat.links.new(dColNode.outputs[1], alphaMultiply.inputs[0])
                CurMat.links.new(bColNode.outputs[1], alphaMultiply.inputs[1])
                CurMat.links.new(alphaMultiply.outputs[0], maskThreshold.inputs[0])
            else:
                CurMat.links.new(bColNode.outputs[1], maskThreshold.inputs[0])
        CurMat.links.new(aThreshold.outputs[0], maskThreshold.inputs[1])

        mulNode = CurMat.nodes.new("ShaderNodeMixRGB")
        mulNode.inputs[0].default_value = 1
        mulNode.blend_type = 'MULTIPLY'
        mulNode.location = (-450, -450)
        mulNode.hide = True

        if "Emissive" in Data:
            emImg = self._image_from_rel_path(Data["Emissive"])
            emTexNode = create_node(CurMat.nodes, "ShaderNodeTexImage", (-800, -500), label="Emissive", image=emImg)
            if layerTileMapping:
                CurMat.links.new(layerTileMapping.outputs[0], emTexNode.inputs[0])
            CurMat.links.new(emTexNode.outputs[0], mulNode.inputs[2])

        if "EmissiveColor" in Data:
            emColor = CreateShaderNodeRGB(CurMat, Data["EmissiveColor"], -700, -450, "EmissiveColor")
            CurMat.links.new(emColor.outputs[0], mulNode.inputs[1])

        CurMat.links.new(mulNode.outputs[0], pBSDF.inputs[sockets['Emission']])

        if "EmissiveEV" in Data:
            pBSDF.inputs['Emission Strength'].default_value = Data["EmissiveEV"]

        enableMask = create_node(CurMat.nodes, "ShaderNodeValue", (-800, -150), label="EnableMask")
        enableMask.outputs[0].default_value = int(self.enableMask)

        mathSubtract = create_node(CurMat.nodes, "ShaderNodeMath", (-800, -100), operation='SUBTRACT', label="Math")
        mathSubtract.inputs[0].default_value = 1

        enableMaskClamp = create_node(CurMat.nodes, "ShaderNodeClamp", (-800, -50))
        backfaceGroup = CreateCullBackfaceGroup(CurMat, x=-500, y=-50, name='Cull Backface')

        CurMat.links.new(enableMask.outputs['Value'], mathSubtract.inputs[1])
        CurMat.links.new(mathSubtract.outputs['Value'], enableMaskClamp.inputs[1])
        if bColNode is not None and bcolImg is not None and not image_has_alpha(bcolImg):
            CurMat.links.new(bColNode.outputs['Color'], enableMaskClamp.inputs['Value'])
        else:
            CurMat.links.new(maskThreshold.outputs[0], enableMaskClamp.inputs[0])
        CurMat.links.new(enableMaskClamp.outputs[0], backfaceGroup.inputs[0])
        CurMat.links.new(backfaceGroup.outputs[0], pBSDF.inputs['Alpha'])


used_params = [
    'BaseColor',
    'BaseColorScale',
    'Metalness',
    'Roughness',
    'Normal',
    'AlphaThreshold',
    'MetalnessScale',
    'MetalnessBias',
    'RoughnessScale',
    'RoughnessBias',
    'NormalStrength',
    'Emissive',
    'EmissiveLift',
    'EmissiveEV',
    'EmissiveEVRaytracingBias',
    'EmissiveDirectionality',
    'EnableRaytracedEmissive',
    'EmissiveColor',
    'LayerTile',
    'VehicleDamageInfluence',
    ]
