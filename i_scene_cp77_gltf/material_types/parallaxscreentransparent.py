from ..main.common import *

from .mat_common import add_group_node, create_param_value_nodes, get_or_build_node_group, set_scene_fps_driver

from .scalar_params import scalar_parameter_data, scalar_value


def _create_scroll_group(layer):
    group_name = f"scroll{layer}_ps_t"
    inputs = (
        ('NodeSocketFloat', f'ScrollSpeed{layer}'),
        ('NodeSocketFloat', f'ScrollStepFactor{layer}'),
        ('NodeSocketFloat', 'Time'),
        )
    outputs = (('NodeSocketFloat', f'scroll{layer}'),)

    def build(group):
        group_in = create_node(group.nodes, "NodeGroupInput", (-1400, 0))
        group_out = create_node(group.nodes, "NodeGroupOutput", (-600, 0))
        mul = create_node(group.nodes, "ShaderNodeMath", (-1250, 0), operation="MULTIPLY")
        mul2 = create_node(group.nodes, "ShaderNodeMath", (-1100, 0), operation="MULTIPLY")
        div = create_node(group.nodes, "ShaderNodeMath", (-950, 0), operation="DIVIDE")
        floor = create_node(group.nodes, "ShaderNodeMath", (-800, 0), operation="FLOOR")
        group.links.new(group_in.outputs[2], mul.inputs[0])
        group.links.new(group_in.outputs[0], mul.inputs[1])
        group.links.new(mul.outputs[0], mul2.inputs[0])
        group.links.new(group_in.outputs[1], mul2.inputs[1])
        group.links.new(mul2.outputs[0], div.inputs[0])
        group.links.new(group_in.outputs[1], div.inputs[1])
        group.links.new(div.outputs[0], floor.inputs[0])
        group.links.new(floor.outputs[0], group_out.inputs[0])

    return get_or_build_node_group(group_name, inputs, outputs, build)


def _create_scroll_uv_group(layer, horizontal):
    group_name = f"scrollUV{layer}X" if horizontal else f"scrollUV{layer}_ps_t"
    output_name = f"scrollUV{layer}X" if horizontal else f"scrollUV{layer}"
    inputs = (
        ('NodeSocketVector', 'newUV'),
        ('NodeSocketFloat', f'ScrollMaskHeight{layer}'),
        ('NodeSocketFloat', f'scroll{layer}'),
        ('NodeSocketFloat', f'ScrollMaskStartPoint{layer}'),
        )
    outputs = (('NodeSocketVector', output_name),)

    def build(group):
        group_in = create_node(group.nodes, "NodeGroupInput", (-1400, 0))
        group_out = create_node(group.nodes, "NodeGroupOutput", (-200, 0))
        separate_loc = (-1250, -100) if horizontal else (-1250, 100)
        combine_loc = (-350, -100) if horizontal else (-350, 100)
        separate = create_node(group.nodes, "ShaderNodeSeparateXYZ", separate_loc)
        div = create_node(group.nodes, "ShaderNodeMath", (-1250, 0), operation="DIVIDE")
        mul = create_node(group.nodes, "ShaderNodeMath", (-1100, 0), operation="MULTIPLY")
        add = create_node(group.nodes, "ShaderNodeMath", (-950, 0), operation="ADD")
        frac = create_node(group.nodes, "ShaderNodeMath", (-800, 0), operation="FRACT")
        mul2 = create_node(group.nodes, "ShaderNodeMath", (-650, 0), operation="MULTIPLY")
        add2 = create_node(group.nodes, "ShaderNodeMath", (-500, 0), operation="ADD")
        combine = create_node(group.nodes, "ShaderNodeCombineXYZ", combine_loc)
        div.inputs[0].default_value = 1
        scroll_axis = 0 if horizontal else 1
        passthrough_axis = 1 if horizontal else 0
        group.links.new(group_in.outputs[0], separate.inputs[0])
        group.links.new(group_in.outputs[1], div.inputs[1])
        group.links.new(separate.outputs[scroll_axis], mul.inputs[0])
        group.links.new(div.outputs[0], mul.inputs[1])
        group.links.new(mul.outputs[0], add.inputs[0])
        group.links.new(group_in.outputs[2], add.inputs[1])
        group.links.new(add.outputs[0], frac.inputs[0])
        group.links.new(frac.outputs[0], mul2.inputs[0])
        group.links.new(group_in.outputs[1], mul2.inputs[1])
        group.links.new(mul2.outputs[0], add2.inputs[0])
        group.links.new(group_in.outputs[3], add2.inputs[1])
        group.links.new(add2.outputs[0], combine.inputs[scroll_axis])
        group.links.new(separate.outputs[passthrough_axis], combine.inputs[passthrough_axis])
        group.links.new(combine.outputs[0], group_out.inputs[0])

    return get_or_build_node_group(group_name, inputs, outputs, build)


def _create_final_scroll_delta_group(layer):
    group_name = f"finalScrollUV{layer}"
    inputs = (
        ('NodeSocketVector', 'finalScrollUV1'),
        ('NodeSocketVector', 'l1'),
        ('NodeSocketVector', f'l{layer}'),
        )
    outputs = (('NodeSocketVector', group_name),)

    def build(group):
        group_in = create_node(group.nodes, "NodeGroupInput", (-1050, 0))
        group_out = create_node(group.nodes, "NodeGroupOutput", (-150, 0))
        vec_delta = create_node(group.nodes, "ShaderNodeVectorMath", (-900, -25))
        vec_add = create_node(group.nodes, "ShaderNodeVectorMath", (-750, 0))
        group.links.new(group_in.outputs[2], vec_delta.inputs[0])
        group.links.new(group_in.outputs[1], vec_delta.inputs[1])
        group.links.new(group_in.outputs[0], vec_add.inputs[0])
        group.links.new(vec_delta.outputs[0], vec_add.inputs[1])
        group.links.new(vec_add.outputs[0], group_out.inputs[0])

    return get_or_build_node_group(group_name, inputs, outputs, build)


def _create_layer_intensity_group(layer, component, scanline_group, lerp_group):
    group_name = f"i{layer}_ps_t"
    sampled = f'l{layer}Sampled'
    layer_uv = f'l{layer}'
    final_uv = f'finalScrollUV{layer}'
    intensity = f'IntensityPerLayer.{component}'
    inputs = (
        ('NodeSocketVector', sampled),
        ('NodeSocketFloat', 'Alpha'),
        ('NodeSocketVector', layer_uv),
        ('NodeSocketVector', final_uv),
        ('NodeSocketFloat', intensity),
        ('NodeSocketFloat', 'ScanlinesIntensity'),
        ('NodeSocketFloat', 'ScanlinesDensity'),
        ('NodeSocketFloat', 'scanlineSpeed'),
        ('NodeSocketFloat', 'scrollMaskMask'),
        )
    outputs = (
        ('NodeSocketVector', f'i{layer}'),
        ('NodeSocketFloat', 'Alpha'),
        )

    def build(group):
        group_in = create_node(group.nodes, "NodeGroupInput", (-1050, 0))
        group_out = create_node(group.nodes, "NodeGroupOutput", (200, 0))
        vec_mul = create_node(group.nodes, "ShaderNodeVectorMath", (-900, 0), operation="MULTIPLY")
        separate = create_node(group.nodes, "ShaderNodeSeparateXYZ", (-750, -50))
        add = create_node(group.nodes, "ShaderNodeMath", (-600, -50))
        scanline = create_node(group.nodes, "ShaderNodeGroup", (-450, -50), label="scanline")
        scanline.node_tree = scanline_group
        separate2 = create_node(group.nodes, "ShaderNodeSeparateXYZ", (-750, 0))
        add2 = create_node(group.nodes, "ShaderNodeMath", (-600, 0))
        scanline2 = create_node(group.nodes, "ShaderNodeGroup", (-450, 0), label="scanline")
        scanline2.node_tree = scanline_group
        lerp = create_node(group.nodes, "ShaderNodeGroup", (-300, -25), label="lerp")
        lerp.node_tree = lerp_group
        lerp2 = create_node(group.nodes, "ShaderNodeGroup", (-150, 0), label="lerp")
        lerp2.node_tree = lerp_group
        lerp2.inputs[1].default_value = 1
        vec_mul2 = create_node(group.nodes, "ShaderNodeVectorMath", (0, 0), operation="MULTIPLY")
        mul = create_node(group.nodes, "ShaderNodeMath", (-900, -150), operation="MULTIPLY")
        mul2 = create_node(group.nodes, "ShaderNodeMath", (0, -150), operation="MULTIPLY")

        group.links.new(group_in.outputs[sampled], vec_mul.inputs[0])
        group.links.new(group_in.outputs[intensity], vec_mul.inputs[1])
        group.links.new(group_in.outputs[final_uv], separate.inputs[0])
        group.links.new(separate.outputs[1], add.inputs[0])
        group.links.new(group_in.outputs['scanlineSpeed'], add.inputs[1])
        group.links.new(group_in.outputs['ScanlinesDensity'], scanline.inputs[0])
        group.links.new(add.outputs[0], scanline.inputs[1])
        group.links.new(group_in.outputs[layer_uv], separate2.inputs[0])
        group.links.new(separate2.outputs[1], add2.inputs[0])
        group.links.new(group_in.outputs['scanlineSpeed'], add2.inputs[1])
        group.links.new(group_in.outputs['ScanlinesDensity'], scanline2.inputs[0])
        group.links.new(scanline.outputs[0], lerp.inputs[0])
        group.links.new(scanline2.outputs[0], lerp.inputs[1])
        group.links.new(group_in.outputs['scrollMaskMask'], lerp.inputs[2])
        group.links.new(group_in.outputs['ScanlinesIntensity'], lerp2.inputs[0])
        group.links.new(lerp.outputs[0], lerp2.inputs[2])
        group.links.new(vec_mul.outputs[0], vec_mul2.inputs[0])
        group.links.new(lerp2.outputs[0], vec_mul2.inputs[1])
        group.links.new(vec_mul2.outputs[0], group_out.inputs[0])
        group.links.new(group_in.outputs['Alpha'], mul.inputs[0])
        group.links.new(group_in.outputs[intensity], mul.inputs[1])
        group.links.new(mul.outputs[0], mul2.inputs[0])
        group.links.new(lerp2.outputs[0], mul2.inputs[1])
        group.links.new(mul2.outputs[0], group_out.inputs[1])

    return get_or_build_node_group(group_name, inputs, outputs, build)


def _create_m_group(group_name, output_name, input_a, input_b):
    inputs = (
        ('NodeSocketVector', input_a),
        ('NodeSocketVector', input_b),
        ('NodeSocketFloat', f'{input_a}.a'),
        ('NodeSocketFloat', f'{input_b}.a'),
        )
    outputs = (
        ('NodeSocketVector', output_name),
        ('NodeSocketFloat', 'Alpha'),
        )

    def build(group):
        group_in = create_node(group.nodes, "NodeGroupInput", (-1050, 0))
        group_out = create_node(group.nodes, "NodeGroupOutput", (300, 0))
        vec_sub = create_node(group.nodes, "ShaderNodeVectorMath", (-900, 25), operation="SUBTRACT")
        vec_sub.inputs[0].default_value = (1, 1, 1)
        vec_sub2 = create_node(group.nodes, "ShaderNodeVectorMath", (-900, -25), operation="SUBTRACT")
        vec_sub2.inputs[0].default_value = (1, 1, 1)
        vec_mul = create_node(group.nodes, "ShaderNodeVectorMath", (-750, 0), operation="MULTIPLY")
        vec_out = create_node(group.nodes, "ShaderNodeVectorMath", (-600, 0), operation="SUBTRACT")
        vec_out.inputs[0].default_value = (1, 1, 1)
        group.links.new(group_in.outputs[0], vec_sub.inputs[1])
        group.links.new(group_in.outputs[1], vec_sub2.inputs[1])
        group.links.new(vec_sub.outputs[0], vec_mul.inputs[0])
        group.links.new(vec_sub2.outputs[0], vec_mul.inputs[1])
        group.links.new(vec_mul.outputs[0], vec_out.inputs[1])
        group.links.new(vec_out.outputs[0], group_out.inputs[0])

        sub = create_node(group.nodes, "ShaderNodeMath", (-900, -150), operation="SUBTRACT")
        sub.inputs[0].default_value = 1
        sub2 = create_node(group.nodes, "ShaderNodeMath", (-900, -200), operation="SUBTRACT")
        sub2.inputs[0].default_value = 1
        mul = create_node(group.nodes, "ShaderNodeMath", (-750, -150), operation="MULTIPLY")
        sub3 = create_node(group.nodes, "ShaderNodeMath", (-600, -150), operation="SUBTRACT")
        sub3.inputs[0].default_value = 1
        group.links.new(group_in.outputs[2], sub.inputs[0])
        group.links.new(group_in.outputs[3], sub2.inputs[0])
        group.links.new(sub.outputs[0], mul.inputs[0])
        group.links.new(sub2.outputs[0], mul.inputs[1])
        group.links.new(mul.outputs[0], sub3.inputs[1])
        group.links.new(sub3.outputs[0], group_out.inputs[1])

    return get_or_build_node_group(group_name, inputs, outputs, build)


class ParallaxScreenTransparent:
    def __init__(self, BasePath, image_format, ProjPath):
        self.BasePath = BasePath
        self.ProjPath = ProjPath
        self.image_format = image_format

    def _image_from_rel_path(self, reference):
        if not reference:
            return None
        return imageFromRelPath(reference, self.image_format, DepotPath=self.BasePath, ProjPath=self.ProjPath)

    def createScanlinesGroup(self):

        def build(group):
            group_in = create_node(group.nodes, "NodeGroupInput", (-1400, 0))
            group_out = create_node(group.nodes, "NodeGroupOutput", (-200, 0))
            mul = create_node(group.nodes, "ShaderNodeMath", (-1200, 0), operation="MULTIPLY")
            cos = create_node(group.nodes, "ShaderNodeMath", (-1000, 0), operation="COSINE")
            div = create_node(group.nodes, "ShaderNodeMath", (-800, 0), operation="DIVIDE")
            div.inputs[1].default_value = 2
            add = create_node(group.nodes, "ShaderNodeMath", (-800, 0))
            add.inputs[1].default_value = 1
            group.links.new(group_in.outputs[0], mul.inputs[1])
            group.links.new(group_in.outputs[1], mul.inputs[0])
            group.links.new(mul.outputs[0], cos.inputs[0])
            group.links.new(cos.outputs[0], add.inputs[0])
            group.links.new(add.outputs[0], div.inputs[0])
            group.links.new(div.outputs[0], group_out.inputs[0])

        return get_or_build_node_group(
                "scanlines",
                (('NodeSocketFloat', 'density'), ('NodeSocketFloat', 'uv')),
                (('NodeSocketFloat', 'result'),),
                build,
                )

    def create(self, Data, Mat):
        CurMat = Mat.node_tree
        pBSDF = CurMat.nodes[loc('Principled BSDF')]
        sockets = bsdf_socket_names()
        pBSDF.inputs[sockets['Specular']].default_value = 0

        value_specs = (
            ('SeparateLayersFromTexture', 'SeparateLayersFromTexture', 500, 'SeparateLayersFromTexture', 0.0),
            ('LayersSeparation', 'LayersSeparation', 650, 'LayersSeparation', 0.0),
            ('ScanlinesSpeed', 'ScanlinesSpeed', 150, 'ScanlinesSpeed', 0.0),
            ('TilesWidth', 'TilesWidth', 100, 'TilesWidth', 1.0),
            ('TilesHeight', 'TilesHeight', 50, 'TilesHeight', 1.0),
            ('PlaySpeed', 'PlaySpeed', 0, 'PlaySpeed', 1.0),
            ('InterlaceLines', 'InterlaceLines', -100, 'InterlaceLines', 1.0),
            ('TextureOffsetX', 'TextureOffsetX', -150, 'TextureOffsetX', 0.0),
            ('TextureOffsetY', 'TextureOffsetY', -200, 'TextureOffsetY', 0.0),
            ('ScrollSpeed1', 'ScrollSpeed1', -350, 'ScrollSpeed1', 0.0),
            ('ScrollStepFactor1', 'ScrollStepFactor1', -400, 'ScrollStepFactor1', 0.0),
            ('ScrollMaskHeight1', 'ScrollMaskHeight1', -450, 'ScrollMaskHeight1', 0.0),
            ('ScrollMaskStartPoint1', 'ScrollMaskStartPoint1', -500, 'ScrollMaskStartPoint1', 0.0),
            ('ScrollSpeed2', 'ScrollSpeed2', -550, 'ScrollSpeed2', 0.0),
            ('ScrollStepFactor2', 'ScrollStepFactor2', -600, 'ScrollStepFactor2', 0.0),
            ('ScrollMaskHeight2', 'ScrollMaskHeight2', -650, 'ScrollMaskHeight2', 0.0),
            ('ScrollMaskStartPoint2', 'ScrollMaskStartPoint2', -700, 'ScrollMaskStartPoint2', 0.0),
            ('ScrollVerticalOrHorizontal', 'ScrollVerticalOrHorizontal', -750, 'ScrollVerticalOrHorizontal', 0.0),
            ('ScanlinesIntensity', 'ScanlinesIntensity', -1000, 'ScanlinesIntensity', 1.0),
            ('ScanlinesDensity', 'ScanlinesDensity', -1050, 'ScanlinesDensity', 1.0),
            ('Emissive', 'Emissive', -1100, 'Emissive', 1.0),
            ('EdgesMask', 'EdgesMask', -1400, 'EdgesMask', 0.0),
            )
        value_nodes = create_param_value_nodes(
            CurMat, scalar_parameter_data(Data, value_specs), value_specs
            )
        component_specs = (
            ('LayersScrollSpeed', 0.0,
             (('X', -2000, 450), ('Y', -2000, 500), ('Z', -2000, 550), ('W', -2000, 600))),
            ('ImageScale', 1.0, (('X', -2000, -250), ('Y', -2000, -300))),
            ('IntensityPerLayer', 1.0,
             (('X', -2000, -800), ('Y', -2000, -850), ('Z', -2000, -900), ('W', -2000, -950))),
            ('TexHSVControl', 1.0, (('X', -2000, -1150), ('Y', -2000, -1200), ('Z', -2000, -1250))),
            )
        component_nodes = {}
        for key, default, components in component_specs:
            values = Data.get(key) or {}
            for component, x, y in components:
                component_nodes[(key, component)] = CreateShaderNodeValue(
                        CurMat,
                        scalar_value(values.get(component), default, component),
                        x,
                        y,
                        f'{key}.{component.lower()}',
                        )

        separateLayersFromTex = value_nodes.get('SeparateLayersFromTexture')
        layersSeparation = value_nodes.get('LayersSeparation')
        scanlinesSpeed = value_nodes.get('ScanlinesSpeed')
        tilesW = value_nodes.get('TilesWidth')
        tilesH = value_nodes.get('TilesHeight')
        playSpeed = value_nodes.get('PlaySpeed')
        iLines = value_nodes.get('InterlaceLines')
        textureOffsetX = value_nodes.get('TextureOffsetX')
        textureOffsetY = value_nodes.get('TextureOffsetY')
        scrollSpeed1 = value_nodes.get('ScrollSpeed1')
        scrollStepFactor1 = value_nodes.get('ScrollStepFactor1')
        scrollMaskHeight1 = value_nodes.get('ScrollMaskHeight1')
        scrollMaskStartPoint1 = value_nodes.get('ScrollMaskStartPoint1')
        scrollSpeed2 = value_nodes.get('ScrollSpeed2')
        scrollStepFactor2 = value_nodes.get('ScrollStepFactor2')
        scrollMaskHeight2 = value_nodes.get('ScrollMaskHeight2')
        scrollMaskStartPoint2 = value_nodes.get('ScrollMaskStartPoint2')
        scrollVerticalOrHorizontal = value_nodes.get('ScrollVerticalOrHorizontal')
        scanlinesIntensity = value_nodes.get('ScanlinesIntensity')
        scanlinesDensity = value_nodes.get('ScanlinesDensity')
        emissive = value_nodes.get('Emissive')
        edgesMaskValue = value_nodes.get('EdgesMask')
        layersScrollSpeed_x = component_nodes.get(('LayersScrollSpeed', 'X'))
        layersScrollSpeed_y = component_nodes.get(('LayersScrollSpeed', 'Y'))
        layersScrollSpeed_z = component_nodes.get(('LayersScrollSpeed', 'Z'))
        layersScrollSpeed_w = component_nodes.get(('LayersScrollSpeed', 'W'))
        imageScale_x = component_nodes.get(('ImageScale', 'X'))
        imageScale_y = component_nodes.get(('ImageScale', 'Y'))
        intensityPerLayer_x = component_nodes.get(('IntensityPerLayer', 'X'))
        intensityPerLayer_y = component_nodes.get(('IntensityPerLayer', 'Y'))
        intensityPerLayer_z = component_nodes.get(('IntensityPerLayer', 'Z'))
        intensityPerLayer_w = component_nodes.get(('IntensityPerLayer', 'W'))
        texHSVControl_x = component_nodes.get(('TexHSVControl', 'X'))
        texHSVControl_y = component_nodes.get(('TexHSVControl', 'Y'))
        texHSVControl_z = component_nodes.get(('TexHSVControl', 'Z'))

        if "Color" in Data:
            color = CreateShaderNodeRGB(CurMat, Data["Color"], -2000, -1300, "Color")
            color_a = CreateShaderNodeValue(
                CurMat,
                scalar_value(Data["Color"].get("Alpha"), 255.0, "Alpha") / 255.0,
                -2000,
                -1350,
                "Color.a",
                )
        else:
            color = create_node(CurMat.nodes, "ShaderNodeRGB", (-2000, -1300), label="Color")
            color.outputs[0].default_value = (1.0, 1.0, 1.0, 1.0)
            color_a = CreateShaderNodeValue(CurMat, 1.0, -2000, -1350, "Color.a")

        scrollMaskImg = self._image_from_rel_path(Data.get("ScrollMaskTexture"))
        parImg = self._image_from_rel_path(Data.get("ParalaxTexture"))

        # tangent, geometry node, uv
        tangent = create_node(CurMat.nodes, "ShaderNodeTangent", (-2000, 400))
        tangent.direction_type = "UV_MAP"
        geometry = create_node(CurMat.nodes, "ShaderNodeNewGeometry", (-2000, 300))
        UVMap = create_node(CurMat.nodes, "ShaderNodeUVMap", (-2000, 200))

        # binormal
        vecCross = create_node(CurMat.nodes, "ShaderNodeVectorMath", (-1850, 350), operation="CROSS_PRODUCT")
        CurMat.links.new(geometry.outputs[1], vecCross.inputs[0])
        CurMat.links.new(tangent.outputs[0], vecCross.inputs[1])

        # leftRightDot
        vecDot = create_node(CurMat.nodes, "ShaderNodeVectorMath", (-1500, 200), operation="DOT_PRODUCT")
        CurMat.links.new(geometry.outputs[4], vecDot.inputs[0])
        CurMat.links.new(tangent.outputs[0], vecDot.inputs[1])

        # topDownDot float topDownDot = -1.0f * dot(viewVector,worldBinormal);
        vecDot2 = create_node(CurMat.nodes, "ShaderNodeVectorMath", (-1500, 150), operation="DOT_PRODUCT")
        vecMul = create_node(CurMat.nodes, "ShaderNodeVectorMath", (-1350, 150), operation="MULTIPLY")
        vecMul.inputs[0].default_value = (-1, -1, -1)
        CurMat.links.new(geometry.outputs[4], vecDot2.inputs[0])
        CurMat.links.new(vecCross.outputs[0], vecDot2.inputs[1])
        CurMat.links.new(vecDot2.outputs["Value"], vecMul.inputs[1])

        # modUV
        combine = create_node(CurMat.nodes, "ShaderNodeCombineXYZ", (-1200, 175))
        CurMat.links.new(vecDot.outputs["Value"], combine.inputs[0])
        CurMat.links.new(vecMul.outputs[0], combine.inputs[1])

        # time node
        time = CreateShaderNodeValue(CurMat, 1, -2000, -50, "Time")
        timeDriver = time.outputs[0].driver_add("default_value")
        set_scene_fps_driver(timeDriver.driver)

        # vector lerp group
        vecLerpG = createVecLerpGroup()

        # gamma node to color
        gamma = create_node(CurMat.nodes, "ShaderNodeGamma", (-1800, -1300))
        gamma.inputs[1].default_value = 2
        CurMat.links.new(color.outputs[0], gamma.inputs[0])

        # n
        ngroup = bpy.data.node_groups.get('n_ps_t')
        if ngroup is None:
            ngroup = bpy.data.node_groups.new("n_ps_t", "ShaderNodeTree")
            ngroup.interface.new_socket(name="TilesWidth", socket_type='NodeSocketFloat', in_out='INPUT')
            ngroup.interface.new_socket(name="TilesHeight", socket_type='NodeSocketFloat', in_out='INPUT')
            ngroup.interface.new_socket(name="PlaySpeed", socket_type='NodeSocketFloat', in_out='INPUT')
            ngroup.interface.new_socket(name="Time", socket_type='NodeSocketFloat', in_out='INPUT')
            ngroup.interface.new_socket(name="n", socket_type='NodeSocketFloat', in_out='OUTPUT')
            GroupInput = create_node(ngroup.nodes, "NodeGroupInput", (-1400, 0))
            GroupOutput = create_node(ngroup.nodes, "NodeGroupOutput", (200, 0))
            mul = create_node(ngroup.nodes, "ShaderNodeMath", (-1000, 0), operation='MULTIPLY')
            div = create_node(ngroup.nodes, "ShaderNodeMath", (-850, 0), operation='DIVIDE')
            mul1 = create_node(ngroup.nodes, "ShaderNodeMath", (-700, 0), operation='MULTIPLY')
            frac = create_node(ngroup.nodes, "ShaderNodeMath", (-550, 0), operation='FRACT')
            mul2 = create_node(ngroup.nodes, "ShaderNodeMath", (-400, 0), operation='MULTIPLY')
            mul3 = create_node(ngroup.nodes, "ShaderNodeMath", (-250, 0), operation='MULTIPLY')

            ngroup.links.new(GroupInput.outputs['TilesWidth'], mul.inputs[0])
            ngroup.links.new(GroupInput.outputs['TilesHeight'], mul.inputs[1])
            ngroup.links.new(GroupInput.outputs['PlaySpeed'], div.inputs[0])
            ngroup.links.new(mul.outputs[0], div.inputs[1])
            ngroup.links.new(GroupInput.outputs['Time'], mul1.inputs[0])
            ngroup.links.new(div.outputs[0], mul1.inputs[1])
            ngroup.links.new(mul1.outputs[0], frac.inputs[0])
            ngroup.links.new(frac.outputs[0], mul2.inputs[0])
            ngroup.links.new(GroupInput.outputs['TilesWidth'], mul2.inputs[1])
            ngroup.links.new(mul2.outputs[0], mul3.inputs[0])
            ngroup.links.new(GroupInput.outputs['TilesHeight'], mul3.inputs[1])
            ngroup.links.new(mul3.outputs[0], GroupOutput.inputs[0])

        n = create_node(CurMat.nodes, "ShaderNodeGroup", (-1700, 75), label="n_ps_t")
        n.node_tree = ngroup

        CurMat.links.new(tilesW.outputs[0], n.inputs[0])
        CurMat.links.new(tilesH.outputs[0], n.inputs[1])
        CurMat.links.new(playSpeed.outputs[0], n.inputs[2])
        CurMat.links.new(time.outputs[0], n.inputs[3])

        # frameAdd	
        frameGroup = bpy.data.node_groups.get('frameAdd_ps_t')
        if frameGroup is None:
            frameGroup = bpy.data.node_groups.new("frameAdd_ps_t", "ShaderNodeTree")
            frameGroup.interface.new_socket(name="UV", socket_type='NodeSocketVector', in_out='INPUT')
            frameGroup.interface.new_socket(name="n", socket_type='NodeSocketFloat', in_out='INPUT')
            frameGroup.interface.new_socket(name="InterlaceLines", socket_type='NodeSocketFloat', in_out='INPUT')
            frameGroup.interface.new_socket(name="frameAdd", socket_type='NodeSocketFloat', in_out='OUTPUT')
            fGroupInput = create_node(frameGroup.nodes, "NodeGroupInput", (-1400, 0))
            fGroupOutput = create_node(frameGroup.nodes, "NodeGroupOutput", (200, 0))

            UVSeparate = create_node(frameGroup.nodes, "ShaderNodeSeparateXYZ", (-1300, 100))
            div2 = create_node(frameGroup.nodes, "ShaderNodeMath", (-900, 125), operation='DIVIDE')
            mod = create_node(frameGroup.nodes, "ShaderNodeMath", (-750, 125), operation='MODULO')
            mod.inputs[1].default_value = 1
            add = create_node(frameGroup.nodes, "ShaderNodeMath", (-600, 125), operation='ADD')
            add.inputs[1].default_value = .5
            mod2 = create_node(frameGroup.nodes, "ShaderNodeMath", (-900, 75), operation='MODULO')
            mod2.inputs[1].default_value = 1
            add2 = create_node(frameGroup.nodes, "ShaderNodeMath", (-750, 75), operation='ADD')
            add2.inputs[1].default_value = .5
            floor = create_node(frameGroup.nodes, "ShaderNodeMath", (-600, 75), operation='FLOOR')
            add3 = create_node(frameGroup.nodes, "ShaderNodeMath", (-450, 125), operation='ADD')
            add3.use_clamp = True
            floor2 = create_node(frameGroup.nodes, "ShaderNodeMath", (-300, 125), operation='FLOOR')
            # clamp = create_node(frameGroup.nodes,"ShaderNodeClamp", (-300,75))
            frameGroup.links.new(fGroupInput.outputs["InterlaceLines"], div2.inputs[1])
            frameGroup.links.new(fGroupInput.outputs['UV'], UVSeparate.inputs[0])
            frameGroup.links.new(UVSeparate.outputs[1], div2.inputs[0])
            frameGroup.links.new(div2.outputs[0], mod.inputs[0])
            frameGroup.links.new(mod.outputs[0], add.inputs[0])
            frameGroup.links.new(add.outputs[0], floor.inputs[0])
            frameGroup.links.new(fGroupInput.outputs["n"], mod2.inputs[0])
            frameGroup.links.new(mod2.outputs[0], add2.inputs[0])
            frameGroup.links.new(add2.outputs[0], floor2.inputs[0])
            frameGroup.links.new(floor.outputs[0], add3.inputs[0])
            frameGroup.links.new(floor2.outputs[0], add3.inputs[1])
            frameGroup.links.new(add3.outputs[0], fGroupOutput.inputs[0])

        frameAdd = create_node(CurMat.nodes, "ShaderNodeGroup", (-1500, 75), label="frameAdd_ps_t")
        frameAdd.node_tree = frameGroup

        CurMat.links.new(iLines.outputs[0], frameAdd.inputs["InterlaceLines"])
        CurMat.links.new(UVMap.outputs[0], frameAdd.inputs["UV"])
        CurMat.links.new(n.outputs[0], frameAdd.inputs["n"])

        # subUV
        subUVGroup = bpy.data.node_groups.get('subUV')
        if subUVGroup is None:
            subUVGroup = bpy.data.node_groups.new("subUV", "ShaderNodeTree")
            subUVGroup.interface.new_socket(name="TilesWidth", socket_type='NodeSocketFloat', in_out='INPUT')
            subUVGroup.interface.new_socket(name="TilesHeight", socket_type='NodeSocketFloat', in_out='INPUT')
            subUVGroup.interface.new_socket(name="n", socket_type='NodeSocketFloat', in_out='INPUT')
            subUVGroup.interface.new_socket(name="frameAdd", socket_type='NodeSocketFloat', in_out='INPUT')
            subUVGroup.interface.new_socket(name="UV", socket_type='NodeSocketVector', in_out='INPUT')
            subUVGroup.interface.new_socket(name="subUV", socket_type='NodeSocketVector', in_out='OUTPUT')
            subUVGroupI = create_node(subUVGroup.nodes, "NodeGroupInput", (-1400, 0))
            subUVGroupO = create_node(subUVGroup.nodes, "NodeGroupOutput", (200, 0))

            UVSeparate = create_node(subUVGroup.nodes, "ShaderNodeSeparateXYZ", (-1300, 100))
            div3 = create_node(subUVGroup.nodes, "ShaderNodeMath", (-900, 0), operation='DIVIDE')
            sub = create_node(subUVGroup.nodes, "ShaderNodeMath", (-1100, -50), operation='SUBTRACT')
            div4 = create_node(subUVGroup.nodes, "ShaderNodeMath", (-900, -50), operation='DIVIDE')
            add4 = create_node(subUVGroup.nodes, "ShaderNodeMath", (-800, -100), operation='ADD')
            mod3 = create_node(subUVGroup.nodes, "ShaderNodeMath", (-900, -150), operation='MODULO')
            floor3 = create_node(subUVGroup.nodes, "ShaderNodeMath", (-750, -150), operation='FLOOR')
            div5 = create_node(subUVGroup.nodes, "ShaderNodeMath", (-500, -150), operation='DIVIDE')
            div6 = create_node(subUVGroup.nodes, "ShaderNodeMath", (-900, -200), operation='DIVIDE')
            mod4 = create_node(subUVGroup.nodes, "ShaderNodeMath", (-750, -200), operation='MODULO')
            floor4 = create_node(subUVGroup.nodes, "ShaderNodeMath", (-600, -200), operation='FLOOR')
            div7 = create_node(subUVGroup.nodes, "ShaderNodeMath", (-450, -200), operation='DIVIDE')
            add5 = create_node(subUVGroup.nodes, "ShaderNodeMath", (-500, -250), operation='ADD')
            add6 = create_node(subUVGroup.nodes, "ShaderNodeMath", (-750, -250), operation='ADD')
            sub2 = create_node(subUVGroup.nodes, "ShaderNodeMath", (-500, -150), operation='SUBTRACT')
            combine = create_node(subUVGroup.nodes, "ShaderNodeCombineXYZ", (-200, -200), label="newUV")
            subUVGroup.links.new(subUVGroupI.outputs[4], UVSeparate.inputs[0])
            subUVGroup.links.new(UVSeparate.outputs[0], div3.inputs[0])
            subUVGroup.links.new(subUVGroupI.outputs[0], div3.inputs[1])  # sizeX
            sub.inputs[0].default_value = 1.0
            subUVGroup.links.new(UVSeparate.outputs[1], sub.inputs[1])
            subUVGroup.links.new(sub.outputs[0], div4.inputs[0])
            subUVGroup.links.new(subUVGroupI.outputs[1], div4.inputs[1])  # sizeY
            subUVGroup.links.new(subUVGroupI.outputs[2], add4.inputs[0])
            subUVGroup.links.new(subUVGroupI.outputs[3], add4.inputs[1])  # CurrentFrame
            subUVGroup.links.new(add4.outputs[0], mod3.inputs[0])
            subUVGroup.links.new(subUVGroupI.outputs[0], mod3.inputs[1])
            subUVGroup.links.new(mod3.outputs[0], floor3.inputs[0])
            subUVGroup.links.new(floor3.outputs[0], div5.inputs[0])
            subUVGroup.links.new(subUVGroupI.outputs[0], div5.inputs[1])  # blockX
            subUVGroup.links.new(add4.outputs[0], div6.inputs[0])
            subUVGroup.links.new(subUVGroupI.outputs[0], div6.inputs[1])
            subUVGroup.links.new(div6.outputs[0], mod4.inputs[0])
            subUVGroup.links.new(subUVGroupI.outputs[1], mod4.inputs[1])
            subUVGroup.links.new(mod4.outputs[0], floor4.inputs[0])
            subUVGroup.links.new(floor4.outputs[0], div7.inputs[0])
            subUVGroup.links.new(subUVGroupI.outputs[1], div7.inputs[1])  # rowY
            subUVGroup.links.new(div3.outputs[0], add5.inputs[0])
            subUVGroup.links.new(div5.outputs[0], add5.inputs[1])
            subUVGroup.links.new(div4.outputs[0], add6.inputs[0])
            subUVGroup.links.new(div7.outputs[0], add6.inputs[1])
            subUVGroup.links.new(add5.outputs[0], combine.inputs[0])
            sub2.inputs[0].default_value = 1.0
            subUVGroup.links.new(add6.outputs[0], sub2.inputs[1])
            subUVGroup.links.new(sub2.outputs[0], combine.inputs[1])
            subUVGroup.links.new(combine.outputs[0], subUVGroupO.inputs[0])

        subUV = create_node(CurMat.nodes, "ShaderNodeGroup", (-1350, 75), label="subUV")
        subUV.node_tree = subUVGroup
        subUV.name = "subUV"

        CurMat.links.new(tilesW.outputs[0], subUV.inputs[0])
        CurMat.links.new(tilesH.outputs[0], subUV.inputs[1])
        CurMat.links.new(UVMap.outputs[0], subUV.inputs[4])
        CurMat.links.new(n.outputs[0], subUV.inputs[2])
        CurMat.links.new(frameAdd.outputs[0], subUV.inputs[3])

        # newUV

        newUVGroup = bpy.data.node_groups.get('newUV_ps_t')

        if newUVGroup is None:
            newUVGroup = bpy.data.node_groups.new("newUV_ps_t", "ShaderNodeTree")
            newUVGroup.interface.new_socket(name="subUV", socket_type='NodeSocketVector', in_out='INPUT')
            newUVGroup.interface.new_socket(name="TextureOffsetX", socket_type='NodeSocketFloat', in_out='INPUT')
            newUVGroup.interface.new_socket(name="TextureOffsetY", socket_type='NodeSocketFloat', in_out='INPUT')
            newUVGroup.interface.new_socket(name="ImageScale.x", socket_type='NodeSocketFloat', in_out='INPUT')
            newUVGroup.interface.new_socket(name="ImageScale.y", socket_type='NodeSocketFloat', in_out='INPUT')
            newUVGroup.interface.new_socket(name="newUV", socket_type='NodeSocketVector', in_out='OUTPUT')
            newUVGroupI = create_node(newUVGroup.nodes, "NodeGroupInput", (-1400, 0))
            newUVGroupO = create_node(newUVGroup.nodes, "NodeGroupOutput", (-300, 0))
            vecSub = create_node(newUVGroup.nodes, "ShaderNodeVectorMath", (-1200, 25), operation='SUBTRACT')
            vecSub.inputs[1].default_value = (.5, .5, .5)
            combine2 = create_node(newUVGroup.nodes, "ShaderNodeCombineXYZ", (-1200, -25))
            vecAdd = create_node(newUVGroup.nodes, "ShaderNodeVectorMath", (-1050, 0))
            combine3 = create_node(newUVGroup.nodes, "ShaderNodeCombineXYZ", (-1050, -75))
            vecMul2 = create_node(newUVGroup.nodes, "ShaderNodeVectorMath", (-900, -50), operation='MULTIPLY')
            vecAdd2 = create_node(newUVGroup.nodes, "ShaderNodeVectorMath", (-750, 0))
            vecAdd2.inputs[1].default_value = (.5, .5, .5)
            vecFrac = create_node(newUVGroup.nodes, "ShaderNodeVectorMath", (-500, 0), operation="FRACTION")
            newUVGroup.links.new(newUVGroupI.outputs["subUV"], vecSub.inputs[0])
            newUVGroup.links.new(newUVGroupI.outputs["TextureOffsetX"], combine2.inputs[0])
            newUVGroup.links.new(newUVGroupI.outputs["TextureOffsetY"], combine2.inputs[1])
            newUVGroup.links.new(newUVGroupI.outputs["ImageScale.x"], combine3.inputs[0])
            newUVGroup.links.new(newUVGroupI.outputs["ImageScale.y"], combine3.inputs[1])
            newUVGroup.links.new(vecSub.outputs[0], vecAdd.inputs[0])
            newUVGroup.links.new(combine2.outputs[0], vecAdd.inputs[1])
            newUVGroup.links.new(vecAdd.outputs[0], vecMul2.inputs[0])
            newUVGroup.links.new(combine3.outputs[0], vecMul2.inputs[1])
            newUVGroup.links.new(vecMul2.outputs[0], vecAdd2.inputs[0])
            newUVGroup.links.new(vecAdd2.outputs[0], vecFrac.inputs[0])
            newUVGroup.links.new(vecFrac.outputs[0], newUVGroupO.inputs[0])

        newUV = create_node(CurMat.nodes, "ShaderNodeGroup", (-1200, 75), label="newUV_ps_t")
        newUV.node_tree = newUVGroup
        newUV.name = "newUV_ps_t"

        CurMat.links.new(subUV.outputs[0], newUV.inputs[0])
        CurMat.links.new(textureOffsetX.outputs[0], newUV.inputs[1])
        CurMat.links.new(textureOffsetY.outputs[0], newUV.inputs[2])
        CurMat.links.new(imageScale_x.outputs[0], newUV.inputs[3])
        CurMat.links.new(imageScale_y.outputs[0], newUV.inputs[4])

        scroll1Group = _create_scroll_group(1)
        scroll1 = add_group_node(CurMat, scroll1Group, (-1500, -200), label="scroll1_ps_t", name="scroll1_ps_t")
        CurMat.links.new(scrollSpeed1.outputs[0], scroll1.inputs[0])
        CurMat.links.new(scrollStepFactor1.outputs[0], scroll1.inputs[1])
        CurMat.links.new(time.outputs[0], scroll1.inputs[2])

        scrollUV1Group = _create_scroll_uv_group(1, False)
        scrollUV1 = add_group_node(CurMat, scrollUV1Group, (-1350, -200), label="scrollUV1_ps_t", name="scrollUV1_ps_t")
        CurMat.links.new(newUV.outputs[0], scrollUV1.inputs[0])
        CurMat.links.new(scrollMaskHeight1.outputs[0], scrollUV1.inputs[1])
        CurMat.links.new(scroll1.outputs[0], scrollUV1.inputs[2])
        CurMat.links.new(scrollMaskStartPoint1.outputs[0], scrollUV1.inputs[3])

        scrollUV1XGroup = _create_scroll_uv_group(1, True)
        scrollUV1X = add_group_node(CurMat, scrollUV1XGroup, (-1350, -250), label="scrollUV1X", name="scrollUV1X")
        CurMat.links.new(newUV.outputs[0], scrollUV1X.inputs[0])
        CurMat.links.new(scrollMaskHeight1.outputs[0], scrollUV1X.inputs[1])
        CurMat.links.new(scroll1.outputs[0], scrollUV1X.inputs[2])
        CurMat.links.new(scrollMaskStartPoint1.outputs[0], scrollUV1X.inputs[3])

        scroll2Group = _create_scroll_group(2)
        scroll2 = add_group_node(CurMat, scroll2Group, (-1500, -300), label="scroll2_ps_t", name="scroll2_ps_t")
        CurMat.links.new(scrollSpeed2.outputs[0], scroll2.inputs[0])
        CurMat.links.new(scrollStepFactor2.outputs[0], scroll2.inputs[1])
        CurMat.links.new(time.outputs[0], scroll2.inputs[2])

        scrollUV2Group = _create_scroll_uv_group(2, False)
        scrollUV2 = add_group_node(CurMat, scrollUV2Group, (-1350, -300), label="scrollUV2_ps_t", name="scrollUV2_ps_t")
        CurMat.links.new(newUV.outputs[0], scrollUV2.inputs[0])
        CurMat.links.new(scrollMaskHeight2.outputs[0], scrollUV2.inputs[1])
        CurMat.links.new(scroll2.outputs[0], scrollUV2.inputs[2])
        CurMat.links.new(scrollMaskStartPoint2.outputs[0], scrollUV2.inputs[3])

        scrollUV2XGroup = _create_scroll_uv_group(2, True)
        scrollUV2X = add_group_node(CurMat, scrollUV2XGroup, (-1350, -350), label="scrollUV2X", name="scrollUV2X")
        CurMat.links.new(newUV.outputs[0], scrollUV2X.inputs[0])
        CurMat.links.new(scrollMaskHeight2.outputs[0], scrollUV2X.inputs[1])
        CurMat.links.new(scroll2.outputs[0], scrollUV2X.inputs[2])
        CurMat.links.new(scrollMaskStartPoint2.outputs[0], scrollUV2X.inputs[3])

        # TODO ClampUV
        # l1
        l1Group = bpy.data.node_groups.get('l1_ps_t')
        if l1Group is None:
            l1Group = bpy.data.node_groups.new("l1_ps_t", "ShaderNodeTree")
            l1Group.interface.new_socket(name="newUV", socket_type='NodeSocketVector', in_out='INPUT')
            l1Group.interface.new_socket(name="l1", socket_type='NodeSocketVector', in_out='OUTPUT')

            l1GroupI = create_node(l1Group.nodes, "NodeGroupInput", (-800, 0))
            l1GroupO = create_node(l1Group.nodes, "NodeGroupOutput", (200, 0))
            vecMul3 = create_node(l1Group.nodes, "ShaderNodeVectorMath", (-650, 0), operation="MULTIPLY")
            vecMul3.inputs[1].default_value = (.5, .5, 0)
            separate3 = create_node(l1Group.nodes, "ShaderNodeSeparateXYZ", (-500, 0))
            clamp2 = create_node(l1Group.nodes, "ShaderNodeClamp", (-350, 25))
            clamp2.inputs[1].default_value = (0)
            clamp2.inputs[2].default_value = (.5)
            clamp3 = create_node(l1Group.nodes, "ShaderNodeClamp", (-350, -25))
            clamp3.inputs[1].default_value = (0)
            clamp3.inputs[2].default_value = (.5)
            combine11 = create_node(l1Group.nodes, "ShaderNodeCombineXYZ", (-200, 0))
            l1Group.links.new(l1GroupI.outputs[0], vecMul3.inputs[0])
            l1Group.links.new(vecMul3.outputs[0], separate3.inputs[0])
            l1Group.links.new(separate3.outputs[0], clamp2.inputs[0])
            l1Group.links.new(separate3.outputs[1], clamp3.inputs[0])
            l1Group.links.new(clamp2.outputs[0], combine11.inputs[0])
            l1Group.links.new(clamp3.outputs[0], combine11.inputs[1])
            l1Group.links.new(combine11.outputs[0], l1GroupO.inputs[0])

        l1 = create_node(CurMat.nodes, "ShaderNodeGroup", (-950, 500), label="l1_ps_t")
        l1.node_tree = l1Group
        CurMat.links.new(newUV.outputs[0], l1.inputs[0])

        # l2
        l2Group = bpy.data.node_groups.get('l2_ps_t')
        if l2Group is None:
            l2Group = bpy.data.node_groups.new("l2_ps_t", "ShaderNodeTree")
            l2Group.interface.new_socket(name="modUV", socket_type='NodeSocketVector', in_out='INPUT')
            l2Group.interface.new_socket(name="newUV", socket_type='NodeSocketVector', in_out='INPUT')
            l2Group.interface.new_socket(name="LayersSeparation", socket_type='NodeSocketFloat', in_out='INPUT')
            l2Group.interface.new_socket(name="l2", socket_type='NodeSocketVector', in_out='OUTPUT')

            l2GroupI = create_node(l2Group.nodes, "NodeGroupInput", (-1000, 0))
            l2GroupO = create_node(l2Group.nodes, "NodeGroupOutput", (200, 0))
            vecMul7 = create_node(l2Group.nodes, "ShaderNodeVectorMath", (-800, -25), operation="MULTIPLY")
            vecMul8 = create_node(l2Group.nodes, "ShaderNodeVectorMath", (-800, 25), operation="MULTIPLY")
            vecMul8.inputs[1].default_value = (.5, .5, 0)
            vecAdd6 = create_node(l2Group.nodes, "ShaderNodeVectorMath", (-600, 0), operation="ADD")
            vecAdd6.inputs[1].default_value = (.5, 0, 0)
            vecAdd7 = create_node(l2Group.nodes, "ShaderNodeVectorMath", (-450, 0), operation="ADD")
            separate4 = create_node(l2Group.nodes, "ShaderNodeSeparateXYZ", (-300, 0))
            clamp4 = create_node(l2Group.nodes, "ShaderNodeClamp", (-150, 25))
            clamp4.inputs[1].default_value = .5
            clamp4.inputs[2].default_value = 0
            clamp5 = create_node(l2Group.nodes, "ShaderNodeClamp", (-150, -25))
            clamp5.inputs[1].default_value = 1
            clamp5.inputs[2].default_value = .5
            combine12 = create_node(l2Group.nodes, "ShaderNodeCombineXYZ", (0, 0))
            l2Group.links.new(l2GroupI.outputs[0], vecMul7.inputs[0])
            l2Group.links.new(l2GroupI.outputs[2], vecMul7.inputs[1])
            l2Group.links.new(l2GroupI.outputs[1], vecMul8.inputs[0])
            l2Group.links.new(vecMul8.outputs[0], vecAdd6.inputs[0])
            l2Group.links.new(vecAdd6.outputs[0], vecAdd7.inputs[0])
            l2Group.links.new(vecMul7.outputs[0], vecAdd7.inputs[1])
            l2Group.links.new(vecAdd7.outputs[0], separate4.inputs[0])
            l2Group.links.new(separate4.outputs[0], clamp4.inputs[0])
            l2Group.links.new(separate4.outputs[1], clamp5.inputs[0])
            l2Group.links.new(clamp4.outputs[0], combine12.inputs[0])
            l2Group.links.new(clamp5.outputs[0], combine12.inputs[1])
            l2Group.links.new(combine12.outputs[0], l2GroupO.inputs[0])

        l2 = create_node(CurMat.nodes, "ShaderNodeGroup", (-950, 450), label="l2_ps_t")
        l2.node_tree = l2Group

        CurMat.links.new(newUV.outputs[0], l2.inputs[1])
        CurMat.links.new(combine.outputs[0], l2.inputs[0])
        CurMat.links.new(layersSeparation.outputs[0], l2.inputs[2])

        # l3

        l3Group = bpy.data.node_groups.get('l3_ps_t')

        if l3Group is None:
            l3Group = bpy.data.node_groups.new("l3_ps_t", "ShaderNodeTree")
            l3Group.interface.new_socket(name="modUV", socket_type='NodeSocketVector', in_out='INPUT')
            l3Group.interface.new_socket(name="newUV", socket_type='NodeSocketVector', in_out='INPUT')
            l3Group.interface.new_socket(name="LayersSeparation", socket_type='NodeSocketFloat', in_out='INPUT')
            l3Group.interface.new_socket(name="l3", socket_type='NodeSocketVector', in_out='OUTPUT')

            l3GroupI = create_node(l3Group.nodes, "NodeGroupInput", (-1000, 0))
            l3GroupO = create_node(l3Group.nodes, "NodeGroupOutput", (200, 0))
            vecMul7 = create_node(l3Group.nodes, "ShaderNodeVectorMath", (-800, -25), operation="MULTIPLY")
            vecMul8 = create_node(l3Group.nodes, "ShaderNodeVectorMath", (-800, 25), operation="MULTIPLY")
            vecMul8.inputs[1].default_value = (.5, .5, 0)
            vecMul9 = create_node(l3Group.nodes, "ShaderNodeVectorMath", (-600, -25), operation="MULTIPLY")
            vecMul9.inputs[1].default_value = (2, 2, 2)
            vecAdd6 = create_node(l3Group.nodes, "ShaderNodeVectorMath", (-600, 25), operation="ADD")
            vecAdd6.inputs[1].default_value = (.5, 0, 0)
            vecAdd7 = create_node(l3Group.nodes, "ShaderNodeVectorMath", (-450, 0), operation="ADD")
            separate4 = create_node(l3Group.nodes, "ShaderNodeSeparateXYZ", (-300, 0))
            clamp4 = create_node(l3Group.nodes, "ShaderNodeClamp", (-150, 25))
            clamp4.inputs[1].default_value = 0
            clamp4.inputs[2].default_value = .5
            clamp5 = create_node(l3Group.nodes, "ShaderNodeClamp", (-150, -25))
            clamp5.inputs[1].default_value = .5
            clamp5.inputs[2].default_value = 1
            combine12 = create_node(l3Group.nodes, "ShaderNodeCombineXYZ", (0, 0))
            l3Group.links.new(l3GroupI.outputs[0], vecMul7.inputs[0])
            l3Group.links.new(l3GroupI.outputs[2], vecMul7.inputs[1])
            l3Group.links.new(vecMul7.outputs[0], vecMul9.inputs[0])
            l3Group.links.new(l3GroupI.outputs[1], vecMul8.inputs[0])
            l3Group.links.new(vecMul8.outputs[0], vecAdd6.inputs[0])
            l3Group.links.new(vecAdd6.outputs[0], vecAdd7.inputs[0])
            l3Group.links.new(vecMul9.outputs[0], vecAdd7.inputs[1])
            l3Group.links.new(vecAdd7.outputs[0], separate4.inputs[0])
            l3Group.links.new(separate4.outputs[0], clamp4.inputs[0])
            l3Group.links.new(separate4.outputs[1], clamp5.inputs[0])
            l3Group.links.new(clamp4.outputs[0], combine12.inputs[0])
            l3Group.links.new(clamp5.outputs[0], combine12.inputs[1])
            l3Group.links.new(combine12.outputs[0], l3GroupO.inputs[0])

        l3 = create_node(CurMat.nodes, "ShaderNodeGroup", (-950, 400), label="l3_ps_t")
        l3.node_tree = l3Group

        CurMat.links.new(newUV.outputs[0], l3.inputs[1])
        CurMat.links.new(combine.outputs[0], l3.inputs[0])
        CurMat.links.new(layersSeparation.outputs[0], l3.inputs[2])

        # l4

        l4Group = bpy.data.node_groups.get('l4_ps_t')

        if l4Group is None:
            l4Group = bpy.data.node_groups.new("l4_ps_t", "ShaderNodeTree")
            l4Group.interface.new_socket(name="modUV", socket_type='NodeSocketVector', in_out='INPUT')
            l4Group.interface.new_socket(name="newUV", socket_type='NodeSocketVector', in_out='INPUT')
            l4Group.interface.new_socket(name="LayersSeparation", socket_type='NodeSocketFloat', in_out='INPUT')
            l4Group.interface.new_socket(name="l4", socket_type='NodeSocketVector', in_out='OUTPUT')

            l4GroupI = create_node(l4Group.nodes, "NodeGroupInput", (-1000, 0))
            l4GroupO = create_node(l4Group.nodes, "NodeGroupOutput", (200, 0))
            vecMul7 = create_node(l4Group.nodes, "ShaderNodeVectorMath", (-800, -25), operation="MULTIPLY")
            vecMul8 = create_node(l4Group.nodes, "ShaderNodeVectorMath", (-800, 25), operation="MULTIPLY")
            vecMul8.inputs[1].default_value = (.5, .5, 0)
            vecMul9 = create_node(l4Group.nodes, "ShaderNodeVectorMath", (-600, -25), operation="MULTIPLY")
            vecMul9.inputs[1].default_value = (3, 3, 3)
            vecAdd6 = create_node(l4Group.nodes, "ShaderNodeVectorMath", (-600, 25), operation="ADD")
            vecAdd6.inputs[1].default_value = (.5, 0, 0)
            vecAdd7 = create_node(l4Group.nodes, "ShaderNodeVectorMath", (-450, 0), operation="ADD")
            separate4 = create_node(l4Group.nodes, "ShaderNodeSeparateXYZ", (-300, 0))
            clamp4 = create_node(l4Group.nodes, "ShaderNodeClamp", (-150, 25))
            clamp4.inputs[1].default_value = .5
            clamp4.inputs[2].default_value = 1
            clamp5 = create_node(l4Group.nodes, "ShaderNodeClamp", (-150, -25))
            clamp5.inputs[1].default_value = .5
            clamp5.inputs[2].default_value = 1
            combine12 = create_node(l4Group.nodes, "ShaderNodeCombineXYZ", (0, 0))
            l4Group.links.new(l4GroupI.outputs[0], vecMul7.inputs[0])
            l4Group.links.new(l4GroupI.outputs[2], vecMul7.inputs[1])
            l4Group.links.new(vecMul7.outputs[0], vecMul9.inputs[0])
            l4Group.links.new(l4GroupI.outputs[1], vecMul8.inputs[0])
            l4Group.links.new(vecMul8.outputs[0], vecAdd6.inputs[0])
            l4Group.links.new(vecAdd6.outputs[0], vecAdd7.inputs[0])
            l4Group.links.new(vecMul9.outputs[0], vecAdd7.inputs[1])
            l4Group.links.new(vecAdd7.outputs[0], separate4.inputs[0])
            l4Group.links.new(separate4.outputs[0], clamp4.inputs[0])
            l4Group.links.new(separate4.outputs[1], clamp5.inputs[0])
            l4Group.links.new(clamp4.outputs[0], combine12.inputs[0])
            l4Group.links.new(clamp5.outputs[0], combine12.inputs[1])
            l4Group.links.new(combine12.outputs[0], l4GroupO.inputs[0])

        l4 = create_node(CurMat.nodes, "ShaderNodeGroup", (-950, 350), label="l4_ps_t")
        l4.node_tree = l4Group

        CurMat.links.new(newUV.outputs[0], l4.inputs[1])
        CurMat.links.new(combine.outputs[0], l4.inputs[0])
        CurMat.links.new(layersSeparation.outputs[0], l4.inputs[2])

        # l1_2
        l1_2Group = bpy.data.node_groups.get('l1_2')
        if l1_2Group is None:
            l1_2Group = bpy.data.node_groups.new("l1_2", "ShaderNodeTree")
            l1_2Group.interface.new_socket(name="newUV", socket_type='NodeSocketVector', in_out='INPUT')
            l1_2Group.interface.new_socket(name="l1_2", socket_type='NodeSocketVector', in_out='OUTPUT')

            l1_2GroupI = create_node(l1_2Group.nodes, "NodeGroupInput", (-800, 0))
            l1_2GroupO = create_node(l1_2Group.nodes, "NodeGroupOutput", (200, 0))
            separate3 = create_node(l1_2Group.nodes, "ShaderNodeSeparateXYZ", (-650, 0))
            clamp2 = create_node(l1_2Group.nodes, "ShaderNodeClamp", (-500, 25))
            clamp3 = create_node(l1_2Group.nodes, "ShaderNodeClamp", (-500, -25))
            combine11 = create_node(l1_2Group.nodes, "ShaderNodeCombineXYZ", (-350, 0))
            l1_2Group.links.new(l1_2GroupI.outputs[0], separate3.inputs[0])
            l1_2Group.links.new(separate3.outputs[0], clamp2.inputs[0])
            l1_2Group.links.new(separate3.outputs[1], clamp3.inputs[0])
            l1_2Group.links.new(clamp2.outputs[0], combine11.inputs[0])
            l1_2Group.links.new(clamp3.outputs[0], combine11.inputs[1])
            l1_2Group.links.new(combine11.outputs[0], l1_2GroupO.inputs[0])

        l1_2 = create_node(CurMat.nodes, "ShaderNodeGroup", (-950, 300), label="l1_2")
        l1_2.node_tree = l1_2Group
        CurMat.links.new(newUV.outputs[0], l1_2.inputs[0])

        # l2_2
        l2_2Group = bpy.data.node_groups.get('l2_2')
        if l2_2Group is None:
            l2_2Group = bpy.data.node_groups.new("l2_2", "ShaderNodeTree")
            l2_2Group.interface.new_socket(name="modUV", socket_type='NodeSocketVector', in_out='INPUT')
            l2_2Group.interface.new_socket(name="newUV", socket_type='NodeSocketVector', in_out='INPUT')
            l2_2Group.interface.new_socket(name="LayersSeparation", socket_type='NodeSocketFloat', in_out='INPUT')
            l2_2Group.interface.new_socket(name="l2_2", socket_type='NodeSocketVector', in_out='OUTPUT')

            l2_2GroupI = create_node(l2_2Group.nodes, "NodeGroupInput", (-800, 0))
            l2_2GroupO = create_node(l2_2Group.nodes, "NodeGroupOutput", (200, 0))
            vecMul7 = create_node(l2_2Group.nodes, "ShaderNodeVectorMath", (-600, 0), operation="MULTIPLY")
            vecAdd6 = create_node(l2_2Group.nodes, "ShaderNodeVectorMath", (-450, 0), operation="ADD")
            separate4 = create_node(l2_2Group.nodes, "ShaderNodeSeparateXYZ", (-300, 0))
            clamp4 = create_node(l2_2Group.nodes, "ShaderNodeClamp", (-150, 25))
            clamp5 = create_node(l2_2Group.nodes, "ShaderNodeClamp", (-150, -25))
            combine12 = create_node(l2_2Group.nodes, "ShaderNodeCombineXYZ", (0, 0))
            l2_2Group.links.new(l2_2GroupI.outputs[0], vecMul7.inputs[0])
            l2_2Group.links.new(l2_2GroupI.outputs[2], vecMul7.inputs[1])
            l2_2Group.links.new(l2_2GroupI.outputs[1], vecAdd6.inputs[0])
            l2_2Group.links.new(vecMul7.outputs[0], vecAdd6.inputs[1])
            l2_2Group.links.new(vecAdd6.outputs[0], separate4.inputs[0])
            l2_2Group.links.new(separate4.outputs[0], clamp4.inputs[0])
            l2_2Group.links.new(separate4.outputs[1], clamp5.inputs[0])
            l2_2Group.links.new(clamp4.outputs[0], combine12.inputs[0])
            l2_2Group.links.new(clamp5.outputs[0], combine12.inputs[1])
            l2_2Group.links.new(combine12.outputs[0], l2_2GroupO.inputs[0])

        l2_2 = create_node(CurMat.nodes, "ShaderNodeGroup", (-950, 250), label="l2_2")
        l2_2.node_tree = l2_2Group

        CurMat.links.new(newUV.outputs[0], l2_2.inputs[1])
        CurMat.links.new(combine.outputs[0], l2_2.inputs[0])
        CurMat.links.new(layersSeparation.outputs[0], l2_2.inputs[2])

        # l3_2
        l3_2Group = bpy.data.node_groups.get('l3_2')
        if l3_2Group is None:
            l3_2Group = bpy.data.node_groups.new("l3_2", "ShaderNodeTree")
            l3_2Group.interface.new_socket(name="modUV", socket_type='NodeSocketVector', in_out='INPUT')
            l3_2Group.interface.new_socket(name="newUV", socket_type='NodeSocketVector', in_out='INPUT')
            l3_2Group.interface.new_socket(name="LayersSeparation", socket_type='NodeSocketFloat', in_out='INPUT')
            l3_2Group.interface.new_socket(name="l3_2", socket_type='NodeSocketVector', in_out='OUTPUT')

            l3_2GroupI = create_node(l3_2Group.nodes, "NodeGroupInput", (-800, 0))
            l3_2GroupO = create_node(l3_2Group.nodes, "NodeGroupOutput", (300, 0))
            vecMul8 = create_node(l3_2Group.nodes, "ShaderNodeVectorMath", (-600, 0), operation="MULTIPLY")
            vecMul9 = create_node(l3_2Group.nodes, "ShaderNodeVectorMath", (-450, 0), operation="MULTIPLY")
            vecMul9.inputs[1].default_value = (2, 2, 2)
            vecAdd7 = create_node(l3_2Group.nodes, "ShaderNodeVectorMath", (-300, 0), operation="ADD")
            separate5 = create_node(l3_2Group.nodes, "ShaderNodeSeparateXYZ", (-150, 0))
            clamp6 = create_node(l3_2Group.nodes, "ShaderNodeClamp", (-0, 25))
            clamp7 = create_node(l3_2Group.nodes, "ShaderNodeClamp", (-0, -25))
            combine13 = create_node(l3_2Group.nodes, "ShaderNodeCombineXYZ", (150, 0))
            l3_2Group.links.new(l3_2GroupI.outputs[0], vecMul8.inputs[0])
            l3_2Group.links.new(l3_2GroupI.outputs[2], vecMul8.inputs[1])
            l3_2Group.links.new(vecMul8.outputs[0], vecMul9.inputs[0])
            l3_2Group.links.new(l3_2GroupI.outputs[1], vecAdd7.inputs[0])
            l3_2Group.links.new(vecMul9.outputs[0], vecAdd7.inputs[1])
            l3_2Group.links.new(vecAdd7.outputs[0], separate5.inputs[0])
            l3_2Group.links.new(separate5.outputs[0], clamp6.inputs[0])
            l3_2Group.links.new(separate5.outputs[1], clamp7.inputs[0])
            l3_2Group.links.new(clamp6.outputs[0], combine13.inputs[0])
            l3_2Group.links.new(clamp7.outputs[0], combine13.inputs[1])
            l3_2Group.links.new(combine13.outputs[0], l3_2GroupO.inputs[0])

        l3_2 = create_node(CurMat.nodes, "ShaderNodeGroup", (-950, 200), label="l3_2")
        l3_2.node_tree = l3_2Group

        CurMat.links.new(newUV.outputs[0], l3_2.inputs[1])
        CurMat.links.new(combine.outputs[0], l3_2.inputs[0])
        CurMat.links.new(layersSeparation.outputs[0], l3_2.inputs[2])

        # l4_2
        l4_2Group = bpy.data.node_groups.get('l4_2')
        if l4_2Group is None:
            l4_2Group = bpy.data.node_groups.new("l4_2", "ShaderNodeTree")
            l4_2Group.interface.new_socket(name="modUV", socket_type='NodeSocketVector', in_out='INPUT')
            l4_2Group.interface.new_socket(name="newUV", socket_type='NodeSocketVector', in_out='INPUT')
            l4_2Group.interface.new_socket(name="LayersSeparation", socket_type='NodeSocketFloat', in_out='INPUT')
            l4_2Group.interface.new_socket(name="l4_2", socket_type='NodeSocketVector', in_out='OUTPUT')
            l4_2GroupI = create_node(l4_2Group.nodes, "NodeGroupInput", (-800, 0))
            l4_2GroupO = create_node(l4_2Group.nodes, "NodeGroupOutput", (300, 0))
            vecMul8 = create_node(l4_2Group.nodes, "ShaderNodeVectorMath", (-600, 0), operation="MULTIPLY")
            vecMul9 = create_node(l4_2Group.nodes, "ShaderNodeVectorMath", (-450, 0), operation="MULTIPLY")
            vecMul9.inputs[1].default_value = (3, 3, 3)
            vecAdd7 = create_node(l4_2Group.nodes, "ShaderNodeVectorMath", (-300, 0), operation="ADD")
            separate5 = create_node(l4_2Group.nodes, "ShaderNodeSeparateXYZ", (-150, 0))
            clamp6 = create_node(l4_2Group.nodes, "ShaderNodeClamp", (-0, 25))
            clamp7 = create_node(l4_2Group.nodes, "ShaderNodeClamp", (-0, -25))
            combine13 = create_node(l4_2Group.nodes, "ShaderNodeCombineXYZ", (150, 0))
            l4_2Group.links.new(l4_2GroupI.outputs[0], vecMul8.inputs[0])
            l4_2Group.links.new(l4_2GroupI.outputs[2], vecMul8.inputs[1])
            l4_2Group.links.new(vecMul8.outputs[0], vecMul9.inputs[0])
            l4_2Group.links.new(l4_2GroupI.outputs[1], vecAdd7.inputs[0])
            l4_2Group.links.new(vecMul9.outputs[0], vecAdd7.inputs[1])
            l4_2Group.links.new(vecAdd7.outputs[0], separate5.inputs[0])
            l4_2Group.links.new(separate5.outputs[0], clamp6.inputs[0])
            l4_2Group.links.new(separate5.outputs[1], clamp7.inputs[0])
            l4_2Group.links.new(clamp6.outputs[0], combine13.inputs[0])
            l4_2Group.links.new(clamp7.outputs[0], combine13.inputs[1])
            l4_2Group.links.new(combine13.outputs[0], l4_2GroupO.inputs[0])

        l4_2 = create_node(CurMat.nodes, "ShaderNodeGroup", (-950, 150), label="l4_2")
        l4_2.node_tree = l4_2Group

        CurMat.links.new(newUV.outputs[0], l4_2.inputs[1])
        CurMat.links.new(combine.outputs[0], l4_2.inputs[0])
        CurMat.links.new(layersSeparation.outputs[0], l4_2.inputs[2])

        # SeparateLayersFromTexture
        vecMix = create_node(CurMat.nodes, "ShaderNodeMix", (-775, 425))
        vecMix.data_type = "VECTOR"
        vecMix2 = create_node(CurMat.nodes, "ShaderNodeMix", (-775, 375))
        vecMix2.data_type = "VECTOR"
        vecMix3 = create_node(CurMat.nodes, "ShaderNodeMix", (-775, 325))
        vecMix3.data_type = "VECTOR"
        vecMix4 = create_node(CurMat.nodes, "ShaderNodeMix", (-775, 275))
        vecMix4.data_type = "VECTOR"
        CurMat.links.new(separateLayersFromTex.outputs[0], vecMix.inputs[0])
        CurMat.links.new(l1.outputs[0], vecMix.inputs[5])
        CurMat.links.new(l1_2.outputs[0], vecMix.inputs[4])
        CurMat.links.new(separateLayersFromTex.outputs[0], vecMix2.inputs[0])
        CurMat.links.new(l2.outputs[0], vecMix2.inputs[5])
        CurMat.links.new(l2_2.outputs[0], vecMix2.inputs[4])
        CurMat.links.new(separateLayersFromTex.outputs[0], vecMix3.inputs[0])
        CurMat.links.new(l3.outputs[0], vecMix3.inputs[5])
        CurMat.links.new(l3_2.outputs[0], vecMix3.inputs[4])
        CurMat.links.new(separateLayersFromTex.outputs[0], vecMix4.inputs[0])
        CurMat.links.new(l4.outputs[0], vecMix4.inputs[5])
        CurMat.links.new(l4_2.outputs[0], vecMix4.inputs[4])

        l1ssGroup = bpy.data.node_groups.get('l1scrollspeed')

        if l1ssGroup is None:
            l1ssGroup = bpy.data.node_groups.new("l1scrollspeed", "ShaderNodeTree")
            l1ssGroup.interface.new_socket(name="l1", socket_type='NodeSocketVector', in_out='INPUT')
            l1ssGroup.interface.new_socket(
                name="LayersScrollSpeed.x", socket_type='NodeSocketFloat', in_out='INPUT'
                )
            l1ssGroup.interface.new_socket(name="time", socket_type='NodeSocketFloat', in_out='INPUT')
            l1ssGroup.interface.new_socket(name="l1scrollspeed", socket_type='NodeSocketVector', in_out='OUTPUT')

            l1ssGroupI = create_node(l1ssGroup.nodes, "NodeGroupInput", (-1000, 0))
            l1ssGroupO = create_node(l1ssGroup.nodes, "NodeGroupOutput", (200, 0))
            separate = create_node(l1ssGroup.nodes, "ShaderNodeSeparateXYZ", (-800, 25))
            mul = create_node(l1ssGroup.nodes, "ShaderNodeMath", (-800, -25), operation="MULTIPLY")
            add = create_node(l1ssGroup.nodes, "ShaderNodeMath", (-600, 0))
            combine = create_node(l1ssGroup.nodes, "ShaderNodeCombineXYZ", (-400, 0))
            l1ssGroup.links.new(l1ssGroupI.outputs[0], separate.inputs[0])
            l1ssGroup.links.new(l1ssGroupI.outputs[2], mul.inputs[0])
            l1ssGroup.links.new(l1ssGroupI.outputs[1], mul.inputs[1])
            l1ssGroup.links.new(separate.outputs[1], add.inputs[0])
            l1ssGroup.links.new(mul.outputs[0], add.inputs[1])
            l1ssGroup.links.new(add.outputs[0], combine.inputs[1])
            l1ssGroup.links.new(separate.outputs[0], combine.inputs[0])
            l1ssGroup.links.new(combine.outputs[0], l1ssGroupO.inputs[0])

        l1ss = create_node(CurMat.nodes, "ShaderNodeGroup", (-625, 425), label="l1scrollspeed")
        l1ss.node_tree = l1ssGroup
        CurMat.links.new(vecMix.outputs[1], l1ss.inputs[0])
        CurMat.links.new(layersScrollSpeed_x.outputs[0], l1ss.inputs[1])
        CurMat.links.new(time.outputs[0], l1ss.inputs[2])

        l2ssGroup = bpy.data.node_groups.get('l2scrollspeed')

        if l2ssGroup is None:
            l2ssGroup = bpy.data.node_groups.new("l2scrollspeed", "ShaderNodeTree")
            l2ssGroup.interface.new_socket(name="l2", socket_type='NodeSocketVector', in_out='INPUT')
            l2ssGroup.interface.new_socket(
                name="LayersScrollSpeed.y", socket_type='NodeSocketFloat', in_out='INPUT'
                )
            l2ssGroup.interface.new_socket(name="time", socket_type='NodeSocketFloat', in_out='INPUT')
            l2ssGroup.interface.new_socket(name="l2scrollspeed", socket_type='NodeSocketVector', in_out='OUTPUT')

            l2ssGroupI = create_node(l2ssGroup.nodes, "NodeGroupInput", (-1000, 0))
            l2ssGroupO = create_node(l2ssGroup.nodes, "NodeGroupOutput", (200, 0))
            separate = create_node(l2ssGroup.nodes, "ShaderNodeSeparateXYZ", (-800, 25))
            mul = create_node(l2ssGroup.nodes, "ShaderNodeMath", (-800, -25), operation="MULTIPLY")
            add = create_node(l2ssGroup.nodes, "ShaderNodeMath", (-600, 0))
            combine = create_node(l2ssGroup.nodes, "ShaderNodeCombineXYZ", (-400, 0))
            l2ssGroup.links.new(l2ssGroupI.outputs[0], separate.inputs[0])
            l2ssGroup.links.new(l2ssGroupI.outputs[2], mul.inputs[0])
            l2ssGroup.links.new(l2ssGroupI.outputs[1], mul.inputs[1])
            l2ssGroup.links.new(separate.outputs[1], add.inputs[0])
            l2ssGroup.links.new(mul.outputs[0], add.inputs[1])
            l2ssGroup.links.new(add.outputs[0], combine.inputs[1])
            l2ssGroup.links.new(separate.outputs[0], combine.inputs[0])
            l2ssGroup.links.new(combine.outputs[0], l2ssGroupO.inputs[0])

        l2ss = create_node(CurMat.nodes, "ShaderNodeGroup", (-625, 375), label="l2scrollspeed")
        l2ss.node_tree = l2ssGroup
        CurMat.links.new(vecMix2.outputs[1], l2ss.inputs[0])
        CurMat.links.new(layersScrollSpeed_y.outputs[0], l2ss.inputs[1])
        CurMat.links.new(time.outputs[0], l2ss.inputs[2])

        l3ssGroup = bpy.data.node_groups.get('l3scrollspeed')

        if l3ssGroup is None:
            l3ssGroup = bpy.data.node_groups.new("l3scrollspeed", "ShaderNodeTree")
            l3ssGroup.interface.new_socket(name="l3", socket_type='NodeSocketVector', in_out='INPUT')
            l3ssGroup.interface.new_socket(
                name="LayersScrollSpeed.z", socket_type='NodeSocketFloat', in_out='INPUT'
                )
            l3ssGroup.interface.new_socket(name="time", socket_type='NodeSocketFloat', in_out='INPUT')
            l3ssGroup.interface.new_socket(name="l3scrollspeed", socket_type='NodeSocketVector', in_out='OUTPUT')

            l3ssGroupI = create_node(l3ssGroup.nodes, "NodeGroupInput", (-1000, 0))
            l3ssGroupO = create_node(l3ssGroup.nodes, "NodeGroupOutput", (200, 0))
            separate = create_node(l3ssGroup.nodes, "ShaderNodeSeparateXYZ", (-800, 25))
            mul = create_node(l3ssGroup.nodes, "ShaderNodeMath", (-800, -25), operation="MULTIPLY")
            add = create_node(l3ssGroup.nodes, "ShaderNodeMath", (-600, 0))
            combine = create_node(l3ssGroup.nodes, "ShaderNodeCombineXYZ", (-400, 0))
            l3ssGroup.links.new(l3ssGroupI.outputs[0], separate.inputs[0])
            l3ssGroup.links.new(l3ssGroupI.outputs[2], mul.inputs[0])
            l3ssGroup.links.new(l3ssGroupI.outputs[1], mul.inputs[1])
            l3ssGroup.links.new(separate.outputs[1], add.inputs[0])
            l3ssGroup.links.new(mul.outputs[0], add.inputs[1])
            l3ssGroup.links.new(add.outputs[0], combine.inputs[1])
            l3ssGroup.links.new(separate.outputs[0], combine.inputs[0])
            l3ssGroup.links.new(combine.outputs[0], l3ssGroupO.inputs[0])

        l3ss = create_node(CurMat.nodes, "ShaderNodeGroup", (-625, 325), label="l3scrollspeed")
        l3ss.node_tree = l3ssGroup
        CurMat.links.new(vecMix3.outputs[1], l3ss.inputs[0])
        CurMat.links.new(layersScrollSpeed_z.outputs[0], l3ss.inputs[1])
        CurMat.links.new(time.outputs[0], l3ss.inputs[2])

        l4ssGroup = bpy.data.node_groups.get('l4scrollspeed')

        if l4ssGroup is None:
            l4ssGroup = bpy.data.node_groups.new("l4scrollspeed", "ShaderNodeTree")
            l4ssGroup.interface.new_socket(name="l4", socket_type='NodeSocketVector', in_out='INPUT')
            l4ssGroup.interface.new_socket(
                name="LayersScrollSpeed.w", socket_type='NodeSocketFloat', in_out='INPUT'
                )
            l4ssGroup.interface.new_socket(name="time", socket_type='NodeSocketFloat', in_out='INPUT')
            l4ssGroup.interface.new_socket(name="l4scrollspeed", socket_type='NodeSocketVector', in_out='OUTPUT')

            l4ssGroupI = create_node(l4ssGroup.nodes, "NodeGroupInput", (-1000, 0))
            l4ssGroupO = create_node(l4ssGroup.nodes, "NodeGroupOutput", (200, 0))
            separate = create_node(l4ssGroup.nodes, "ShaderNodeSeparateXYZ", (-800, 25))
            mul = create_node(l4ssGroup.nodes, "ShaderNodeMath", (-800, -25), operation="MULTIPLY")
            add = create_node(l4ssGroup.nodes, "ShaderNodeMath", (-600, 0))
            combine = create_node(l4ssGroup.nodes, "ShaderNodeCombineXYZ", (-400, 0))
            l4ssGroup.links.new(l4ssGroupI.outputs[0], separate.inputs[0])
            l4ssGroup.links.new(l4ssGroupI.outputs[2], mul.inputs[0])
            l4ssGroup.links.new(l4ssGroupI.outputs[1], mul.inputs[1])
            l4ssGroup.links.new(separate.outputs[1], add.inputs[0])
            l4ssGroup.links.new(mul.outputs[0], add.inputs[1])
            l4ssGroup.links.new(add.outputs[0], combine.inputs[1])
            l4ssGroup.links.new(separate.outputs[0], combine.inputs[0])
            l4ssGroup.links.new(combine.outputs[0], l4ssGroupO.inputs[0])

        l4ss = create_node(CurMat.nodes, "ShaderNodeGroup", (-625, 275), label="l4scrollspeed")
        l4ss.node_tree = l4ssGroup
        CurMat.links.new(vecMix4.outputs[1], l4ss.inputs[0])
        CurMat.links.new(layersScrollSpeed_w.outputs[0], l4ss.inputs[1])
        CurMat.links.new(time.outputs[0], l4ss.inputs[2])

        # scrollMask
        scrollMask = create_node(
            CurMat.nodes, "ShaderNodeTexImage", (-950, 100), label="ScrollMaskTexture",
            image=scrollMaskImg
            )
        CurMat.links.new(l1ss.outputs[0], scrollMask.inputs[0])

        # scrollMaskMask
        scrollMMGroup = bpy.data.node_groups.get('scrollMaskMask')
        if scrollMMGroup is None:
            scrollMMGroup = bpy.data.node_groups.new("scrollMaskMask", "ShaderNodeTree")
            scrollMMGroup.interface.new_socket(name="scrollMask", socket_type='NodeSocketColor', in_out='INPUT')
            scrollMMGroup.interface.new_socket(
                name="scrollMaskMask", socket_type='NodeSocketVector', in_out='OUTPUT'
                )

            scrollMMGroupI = create_node(scrollMMGroup.nodes, "NodeGroupInput", (-1000, 0))
            scrollMMGroupO = create_node(scrollMMGroup.nodes, "NodeGroupOutput", (200, 0))
            separate = create_node(scrollMMGroup.nodes, "ShaderNodeSeparateXYZ", (-800, 0))
            add = create_node(scrollMMGroup.nodes, "ShaderNodeMath", (-650, 0))
            scrollMMGroup.links.new(scrollMMGroupI.outputs[0], separate.inputs[0])
            scrollMMGroup.links.new(separate.outputs[0], add.inputs[0])
            scrollMMGroup.links.new(separate.outputs[1], add.inputs[1])
            scrollMMGroup.links.new(add.outputs[0], scrollMMGroupO.inputs[0])

        scrollMaskMask = create_node(CurMat.nodes, "ShaderNodeGroup", (-700, 100), label="scrollMaskMask")
        scrollMaskMask.node_tree = scrollMMGroup
        CurMat.links.new(scrollMask.outputs[0], scrollMaskMask.inputs[0])

        # scanlineSpeed
        mul5 = create_node(CurMat.nodes, "ShaderNodeMath", (-950, 50), operation="MULTIPLY")
        frac2 = create_node(CurMat.nodes, "ShaderNodeMath", (-800, 50), operation="FRACT")
        CurMat.links.new(time.outputs[0], mul5.inputs[0])
        CurMat.links.new(scanlinesSpeed.outputs[0], mul5.inputs[1])
        CurMat.links.new(mul5.outputs[0], frac2.inputs[0])

        # finalScrollUV
        finalScrollUVGroup = bpy.data.node_groups.get('finalScrollUV1')
        if finalScrollUVGroup is None:
            finalScrollUVGroup = bpy.data.node_groups.new("finalScrollUV1", "ShaderNodeTree")
            finalScrollUVGroup.interface.new_socket(
                name="scrollMask", socket_type='NodeSocketColor', in_out='INPUT'
                )
            finalScrollUVGroup.interface.new_socket(
                name="scrollUV1", socket_type='NodeSocketVector', in_out='INPUT'
                )
            finalScrollUVGroup.interface.new_socket(
                name="scrollUV1X", socket_type='NodeSocketVector', in_out='INPUT'
                )
            finalScrollUVGroup.interface.new_socket(
                name="scrollUV2", socket_type='NodeSocketVector', in_out='INPUT'
                )
            finalScrollUVGroup.interface.new_socket(
                name="scrollUV2X", socket_type='NodeSocketVector', in_out='INPUT'
                )
            finalScrollUVGroup.interface.new_socket(
                name="ScrollVerticalOrHorizontal", socket_type='NodeSocketVector', in_out='INPUT'
                )
            finalScrollUVGroup.interface.new_socket(
                name="finalScrollUV1", socket_type='NodeSocketVector', in_out='OUTPUT'
                )

            finalScrollUVGroupI = create_node(finalScrollUVGroup.nodes, "NodeGroupInput", (-1050, 0))
            finalScrollUVGroupO = create_node(finalScrollUVGroup.nodes, "NodeGroupOutput", (-150, 0))
            vecLerp2 = create_node(finalScrollUVGroup.nodes, "ShaderNodeGroup", (-750, 0), label="lerp")
            vecLerp2.node_tree = vecLerpG
            separate9 = create_node(finalScrollUVGroup.nodes, "ShaderNodeSeparateXYZ", (-900, -50))
            vecLerp3 = create_node(finalScrollUVGroup.nodes, "ShaderNodeGroup", (-750, -100), label="lerp")
            vecLerp3.node_tree = vecLerpG
            vecLerp4 = create_node(finalScrollUVGroup.nodes, "ShaderNodeGroup", (-600, 0), label="lerp")
            vecLerp4.node_tree = vecLerpG
            finalScrollUVGroup.links.new(finalScrollUVGroupI.outputs['scrollUV2'], vecLerp2.inputs[0])
            finalScrollUVGroup.links.new(finalScrollUVGroupI.outputs['scrollUV1'], vecLerp2.inputs[1])
            finalScrollUVGroup.links.new(separate9.outputs[0], vecLerp2.inputs[2])
            finalScrollUVGroup.links.new(finalScrollUVGroupI.outputs['scrollMask'], separate9.inputs[0])
            finalScrollUVGroup.links.new(finalScrollUVGroupI.outputs['scrollUV2X'], vecLerp3.inputs[0])
            finalScrollUVGroup.links.new(finalScrollUVGroupI.outputs['scrollUV1X'], vecLerp3.inputs[1])
            finalScrollUVGroup.links.new(separate9.outputs[0], vecLerp3.inputs[2])
            finalScrollUVGroup.links.new(vecLerp2.outputs[0], vecLerp4.inputs[0])
            finalScrollUVGroup.links.new(vecLerp3.outputs[0], vecLerp4.inputs[1])
            finalScrollUVGroup.links.new(finalScrollUVGroupI.outputs['ScrollVerticalOrHorizontal'], vecLerp4.inputs[2])
            finalScrollUVGroup.links.new(vecLerp4.outputs[0], finalScrollUVGroupO.inputs[0])

        finalScrollUV1 = create_node(CurMat.nodes, "ShaderNodeGroup", (-1200, -200), label="finalScrollUV1")
        finalScrollUV1.node_tree = finalScrollUVGroup
        CurMat.links.new(scrollUV2.outputs[0], finalScrollUV1.inputs[3])
        CurMat.links.new(scrollUV1.outputs[0], finalScrollUV1.inputs[1])
        CurMat.links.new(scrollMask.outputs[0], finalScrollUV1.inputs[0])
        CurMat.links.new(scrollUV2X.outputs[0], finalScrollUV1.inputs[4])
        CurMat.links.new(scrollUV1X.outputs[0], finalScrollUV1.inputs[2])
        CurMat.links.new(scrollVerticalOrHorizontal.outputs[0], finalScrollUV1.inputs[5])

        finalScrollUV2Group = _create_final_scroll_delta_group(2)
        finalScrollUV2 = add_group_node(CurMat, finalScrollUV2Group, (-1200, -250), label="finalScrollUV2")
        CurMat.links.new(finalScrollUV1.outputs[0], finalScrollUV2.inputs[0])
        CurMat.links.new(l1ss.outputs[0], finalScrollUV2.inputs[1])
        CurMat.links.new(l2ss.outputs[0], finalScrollUV2.inputs[2])

        finalScrollUV3Group = _create_final_scroll_delta_group(3)
        finalScrollUV3 = add_group_node(CurMat, finalScrollUV3Group, (-1200, -300), label="finalScrollUV3")
        CurMat.links.new(finalScrollUV1.outputs[0], finalScrollUV3.inputs[0])
        CurMat.links.new(l1ss.outputs[0], finalScrollUV3.inputs[1])
        CurMat.links.new(l3ss.outputs[0], finalScrollUV3.inputs[2])

        finalScrollUV4Group = _create_final_scroll_delta_group(4)
        finalScrollUV4 = add_group_node(CurMat, finalScrollUV4Group, (-1200, -350), label="finalScrollUV4")
        CurMat.links.new(finalScrollUV1.outputs[0], finalScrollUV4.inputs[0])
        CurMat.links.new(l1ss.outputs[0], finalScrollUV4.inputs[1])
        CurMat.links.new(l4ss.outputs[0], finalScrollUV4.inputs[2])

        # l1Sampled 
        parTex = create_node(CurMat.nodes, "ShaderNodeTexImage", (-1050, -100), label="ParalaxTexture", image=parImg)
        parTex2 = create_node(CurMat.nodes, "ShaderNodeTexImage", (-1050, -150), label="ParalaxTexture", image=parImg)
        vecLerp = create_node(CurMat.nodes, "ShaderNodeGroup", (-700, -200), label="lerp")
        vecLerp.node_tree = vecLerpG
        lerpG = createLerpGroup()
        lerp = create_node(CurMat.nodes, "ShaderNodeGroup", (-700, -250), label="lerp")
        lerp.node_tree = lerpG
        CurMat.links.new(finalScrollUV1.outputs[0], parTex2.inputs[0])
        CurMat.links.new(l1ss.outputs[0], parTex.inputs[0])
        CurMat.links.new(parTex.outputs[0], vecLerp.inputs[0])
        CurMat.links.new(parTex2.outputs[0], vecLerp.inputs[1])
        CurMat.links.new(scrollMaskMask.outputs[0], vecLerp.inputs[2])
        CurMat.links.new(parTex.outputs[1], lerp.inputs[0])
        CurMat.links.new(parTex2.outputs[1], lerp.inputs[1])
        CurMat.links.new(scrollMaskMask.outputs[0], lerp.inputs[2])

        # l2Sampled
        parTex = create_node(CurMat.nodes, "ShaderNodeTexImage", (-1050, -200), label="ParalaxTexture", image=parImg)
        parTex2 = create_node(CurMat.nodes, "ShaderNodeTexImage", (-1050, -250), label="ParalaxTexture", image=parImg)
        vecLerp2 = create_node(CurMat.nodes, "ShaderNodeGroup", (-700, -300), label="lerp")
        vecLerp2.node_tree = vecLerpG
        lerp2 = create_node(CurMat.nodes, "ShaderNodeGroup", (-700, -350), label="lerp")
        lerp2.node_tree = lerpG
        CurMat.links.new(finalScrollUV2.outputs[0], parTex2.inputs[0])
        CurMat.links.new(l2ss.outputs[0], parTex.inputs[0])
        CurMat.links.new(parTex.outputs[0], vecLerp2.inputs[0])
        CurMat.links.new(parTex2.outputs[0], vecLerp2.inputs[1])
        CurMat.links.new(scrollMaskMask.outputs[0], vecLerp2.inputs[2])
        CurMat.links.new(parTex.outputs[1], lerp2.inputs[0])
        CurMat.links.new(parTex2.outputs[1], lerp2.inputs[1])
        CurMat.links.new(scrollMaskMask.outputs[0], lerp2.inputs[2])

        # l3Sampled
        parTex = create_node(CurMat.nodes, "ShaderNodeTexImage", (-1050, -300), label="ParalaxTexture", image=parImg)
        parTex2 = create_node(CurMat.nodes, "ShaderNodeTexImage", (-1050, -350), label="ParalaxTexture", image=parImg)
        vecLerp3 = create_node(CurMat.nodes, "ShaderNodeGroup", (-700, -400), label="lerp")
        vecLerp3.node_tree = vecLerpG
        lerp3 = create_node(CurMat.nodes, "ShaderNodeGroup", (-700, -450), label="lerp")
        lerp3.node_tree = lerpG
        CurMat.links.new(finalScrollUV3.outputs[0], parTex2.inputs[0])
        CurMat.links.new(l3ss.outputs[0], parTex.inputs[0])
        CurMat.links.new(parTex.outputs[0], vecLerp3.inputs[0])
        CurMat.links.new(parTex2.outputs[0], vecLerp3.inputs[1])
        CurMat.links.new(scrollMaskMask.outputs[0], vecLerp3.inputs[2])
        CurMat.links.new(parTex.outputs[1], lerp3.inputs[0])
        CurMat.links.new(parTex2.outputs[1], lerp3.inputs[1])
        CurMat.links.new(scrollMaskMask.outputs[0], lerp3.inputs[2])

        # l4Sampled
        parTex = create_node(CurMat.nodes, "ShaderNodeTexImage", (-1050, -400), label="ParalaxTexture", image=parImg)
        parTex2 = create_node(CurMat.nodes, "ShaderNodeTexImage", (-1050, -450), label="ParalaxTexture", image=parImg)
        vecLerp4 = create_node(CurMat.nodes, "ShaderNodeGroup", (-700, -500), label="lerp")
        vecLerp4.node_tree = vecLerpG
        lerp4 = create_node(CurMat.nodes, "ShaderNodeGroup", (-700, -550), label="lerp")
        lerp4.node_tree = lerpG
        CurMat.links.new(finalScrollUV4.outputs[0], parTex2.inputs[0])
        CurMat.links.new(l4ss.outputs[0], parTex.inputs[0])
        CurMat.links.new(parTex.outputs[0], vecLerp4.inputs[0])
        CurMat.links.new(parTex2.outputs[0], vecLerp4.inputs[1])
        CurMat.links.new(scrollMaskMask.outputs[0], vecLerp4.inputs[2])
        CurMat.links.new(parTex.outputs[1], lerp4.inputs[0])
        CurMat.links.new(parTex2.outputs[1], lerp4.inputs[1])
        CurMat.links.new(scrollMaskMask.outputs[0], lerp4.inputs[2])

        # i1
        i1Group = bpy.data.node_groups.get('i1_ps_t')
        if i1Group is None:
            i1Group = bpy.data.node_groups.new("i1_ps_t", "ShaderNodeTree")
            i1Group.interface.new_socket(name="l1Sampled", socket_type='NodeSocketVector', in_out='INPUT')
            i1Group.interface.new_socket(name="Alpha", socket_type='NodeSocketFloat', in_out='INPUT')
            i1Group.interface.new_socket(name="IntensityPerLayer.x", socket_type='NodeSocketFloat', in_out='INPUT')
            i1Group.interface.new_socket(name="i1", socket_type='NodeSocketVector', in_out='OUTPUT')
            i1Group.interface.new_socket(name="Alpha", socket_type='NodeSocketFloat', in_out='OUTPUT')

            i1GroupI = create_node(i1Group.nodes, "NodeGroupInput", (-1050, 0))
            i1GroupO = create_node(i1Group.nodes, "NodeGroupOutput", (-150, 0))
            vecMul = create_node(i1Group.nodes, "ShaderNodeVectorMath", (-900, 0), operation="MULTIPLY")
            mul = create_node(i1Group.nodes, "ShaderNodeMath", (-900, -100), operation="MULTIPLY")
            i1Group.links.new(i1GroupI.outputs['l1Sampled'], vecMul.inputs[0])
            i1Group.links.new(i1GroupI.outputs['Alpha'], mul.inputs[0])
            i1Group.links.new(i1GroupI.outputs['IntensityPerLayer.x'], vecMul.inputs[1])
            i1Group.links.new(i1GroupI.outputs['IntensityPerLayer.x'], mul.inputs[1])
            i1Group.links.new(vecMul.outputs[0], i1GroupO.inputs[0])
            i1Group.links.new(mul.outputs[0], i1GroupO.inputs[1])

        i1 = create_node(CurMat.nodes, "ShaderNodeGroup", (-550, -200), label="i1_ps_t")
        i1.node_tree = i1Group
        CurMat.links.new(vecLerp.outputs[0], i1.inputs[0])
        CurMat.links.new(lerp.outputs[0], i1.inputs[1])
        CurMat.links.new(intensityPerLayer_x.outputs[0], i1.inputs[2])

        scanlineG = self.createScanlinesGroup()
        layerLerpG = createLerpGroup()

        i2Group = _create_layer_intensity_group(2, 'y', scanlineG, layerLerpG)
        i2 = add_group_node(CurMat, i2Group, (-550, -275), label="i2_ps_t")
        CurMat.links.new(vecLerp2.outputs[0], i2.inputs[0])
        CurMat.links.new(lerp2.outputs[0], i2.inputs[1])
        CurMat.links.new(l2ss.outputs[0], i2.inputs[2])
        CurMat.links.new(finalScrollUV2.outputs[0], i2.inputs[3])
        CurMat.links.new(intensityPerLayer_y.outputs[0], i2.inputs[4])
        CurMat.links.new(scanlinesIntensity.outputs[0], i2.inputs[5])
        CurMat.links.new(scanlinesDensity.outputs[0], i2.inputs[6])
        CurMat.links.new(frac2.outputs[0], i2.inputs[7])
        CurMat.links.new(scrollMaskMask.outputs[0], i2.inputs[8])

        i3Group = _create_layer_intensity_group(3, 'z', scanlineG, layerLerpG)
        i3 = add_group_node(CurMat, i3Group, (-550, -375), label="i3_ps_t")
        CurMat.links.new(vecLerp3.outputs[0], i3.inputs[0])
        CurMat.links.new(lerp3.outputs[0], i3.inputs[1])
        CurMat.links.new(l3ss.outputs[0], i3.inputs[2])
        CurMat.links.new(finalScrollUV3.outputs[0], i3.inputs[3])
        CurMat.links.new(intensityPerLayer_z.outputs[0], i3.inputs[4])
        CurMat.links.new(scanlinesIntensity.outputs[0], i3.inputs[5])
        CurMat.links.new(scanlinesDensity.outputs[0], i3.inputs[6])
        CurMat.links.new(frac2.outputs[0], i3.inputs[7])
        CurMat.links.new(scrollMaskMask.outputs[0], i3.inputs[8])

        i4Group = _create_layer_intensity_group(4, 'w', scanlineG, layerLerpG)
        i4 = add_group_node(CurMat, i4Group, (-550, -475), label="i4_ps_t")
        CurMat.links.new(vecLerp4.outputs[0], i4.inputs[0])
        CurMat.links.new(lerp4.outputs[0], i4.inputs[1])
        CurMat.links.new(l4ss.outputs[0], i4.inputs[2])
        CurMat.links.new(finalScrollUV4.outputs[0], i4.inputs[3])
        CurMat.links.new(intensityPerLayer_w.outputs[0], i4.inputs[4])
        CurMat.links.new(scanlinesIntensity.outputs[0], i4.inputs[5])
        CurMat.links.new(scanlinesDensity.outputs[0], i4.inputs[6])
        CurMat.links.new(frac2.outputs[0], i4.inputs[7])
        CurMat.links.new(scrollMaskMask.outputs[0], i4.inputs[8])

        # TODO AdditiveOrAlphaBlened

        m1Group = _create_m_group("m1", "m1", "i4", "i3")
        m1 = add_group_node(CurMat, m1Group, (-550, -500), label="m1")
        CurMat.links.new(i4.outputs[0], m1.inputs[0])
        CurMat.links.new(i3.outputs[0], m1.inputs[1])
        CurMat.links.new(i4.outputs[1], m1.inputs[2])
        CurMat.links.new(i3.outputs[1], m1.inputs[3])

        m2Group = _create_m_group("parallax_screen_trans_m2", "m2", "m1", "i2")
        m2 = add_group_node(CurMat, m2Group, (-550, -550), label="m2")
        CurMat.links.new(m1.outputs[0], m2.inputs[0])
        CurMat.links.new(i2.outputs[0], m2.inputs[1])
        if len(m2.outputs) > 1:
            CurMat.links.new(m1.outputs[1], m2.inputs[2])
            CurMat.links.new(i2.outputs[1], m2.inputs[3])

        m3Group = _create_m_group("parallax_screen_trans_m3", "m3", "m2", "i1")
        m3 = add_group_node(CurMat, m3Group, (-550, -600), label="m3")
        CurMat.links.new(m2.outputs[0], m3.inputs[0])
        CurMat.links.new(i1.outputs[0], m3.inputs[1])
        if len(m2.outputs) > 1:
            CurMat.links.new(m2.outputs[1], m3.inputs[2])
        CurMat.links.new(i1.outputs[1], m3.inputs[3])

        # if EdgesMask > 0
        greater_than = create_node(CurMat.nodes, "ShaderNodeMath", (-550, -800), operation="GREATER_THAN")
        greater_than.inputs[1].default_value = 0
        mix = create_node(CurMat.nodes, "ShaderNodeMix", (-400, -800))
        mix.inputs[2].default_value = 1.0
        CurMat.links.new(edgesMaskValue.outputs[0], greater_than.inputs[0])
        CurMat.links.new(greater_than.outputs[0], mix.inputs[0])

        # edgesMask
        edgesMaskGroup = bpy.data.node_groups.get('edgesMask')
        if edgesMaskGroup is None:
            edgesMaskGroup = bpy.data.node_groups.new("edgesMask", "ShaderNodeTree")
            edgesMaskGroup.interface.new_socket(name="UV", socket_type='NodeSocketVector', in_out='INPUT')
            edgesMaskGroup.interface.new_socket(name="EdgesMask", socket_type='NodeSocketFloat', in_out='INPUT')
            edgesMaskGroup.interface.new_socket(name="edgesMask", socket_type='NodeSocketFloat', in_out='OUTPUT')

            edgesMaskGroupI = create_node(edgesMaskGroup.nodes, "NodeGroupInput", (-1050, 0))
            edgesMaskGroupO = create_node(edgesMaskGroup.nodes, "NodeGroupOutput", (300, 0))
            separate = create_node(edgesMaskGroup.nodes, "ShaderNodeSeparateXYZ", (-900, 0))
            sub = create_node(edgesMaskGroup.nodes, "ShaderNodeMath", (-750, 0), operation="SUBTRACT")
            sub.inputs[1].default_value = .5
            mul = create_node(edgesMaskGroup.nodes, "ShaderNodeMath", (-600, 0), operation="MULTIPLY")
            mul.inputs[1].default_value = 2
            absolute = create_node(edgesMaskGroup.nodes, "ShaderNodeMath", (-450, 0), operation="ABSOLUTE")
            sub2 = create_node(edgesMaskGroup.nodes, "ShaderNodeMath", (-300, 0), operation="SUBTRACT")
            sub2.inputs[0].default_value = 1
            sub2.use_clamp = True
            mul2 = create_node(edgesMaskGroup.nodes, "ShaderNodeMath", (-150, 0), operation="MULTIPLY")

            edgesMaskGroup.links.new(edgesMaskGroupI.outputs[0], separate.inputs[0])
            edgesMaskGroup.links.new(separate.outputs[1], sub.inputs[0])
            edgesMaskGroup.links.new(sub.outputs[0], mul.inputs[0])
            edgesMaskGroup.links.new(mul.outputs[0], absolute.inputs[0])
            edgesMaskGroup.links.new(absolute.outputs[0], sub2.inputs[1])
            edgesMaskGroup.links.new(sub2.outputs[0], mul2.inputs[0])
            edgesMaskGroup.links.new(edgesMaskGroupI.outputs[1], mul2.inputs[1])
            edgesMaskGroup.links.new(mul2.outputs[0], edgesMaskGroupO.inputs[0])

        edgesMask = create_node(CurMat.nodes, "ShaderNodeGroup", (-550, -850), label="edgesMask")
        edgesMask.node_tree = edgesMaskGroup
        CurMat.links.new(UVMap.outputs[0], edgesMask.inputs[0])
        CurMat.links.new(edgesMaskValue.outputs[0], edgesMask.inputs[1])
        CurMat.links.new(edgesMask.outputs[0], mix.inputs[3])

        # HSV
        hsvGroup = bpy.data.node_groups.get('hsv')
        if hsvGroup is None:
            hsvGroup = bpy.data.node_groups.new("hsv", "ShaderNodeTree")
            hsvGroup.interface.new_socket(name="m3", socket_type='NodeSocketVector', in_out='INPUT')
            hsvGroup.interface.new_socket(name="scroll1", socket_type='NodeSocketVector', in_out='INPUT')
            hsvGroup.interface.new_socket(name="TexHSVControl.x", socket_type='NodeSocketFloat', in_out='INPUT')
            hsvGroup.interface.new_socket(name="TexHSVControl.y", socket_type='NodeSocketFloat', in_out='INPUT')
            hsvGroup.interface.new_socket(name="TexHSVControl.z", socket_type='NodeSocketFloat', in_out='INPUT')
            hsvGroup.interface.new_socket(name="scrollMask", socket_type='NodeSocketVector', in_out='INPUT')
            hsvGroup.interface.new_socket(name="EdgesMask", socket_type='NodeSocketFloat', in_out='INPUT')
            hsvGroup.interface.new_socket(name="color", socket_type='NodeSocketColor', in_out='OUTPUT')

            hsvGroupI = create_node(hsvGroup.nodes, "NodeGroupInput", (-1650, 0))
            hsvGroupO = create_node(hsvGroup.nodes, "NodeGroupOutput", (150, 0))
            hsv_pos_x = -1500
            vecMul10 = create_node(hsvGroup.nodes, "ShaderNodeVectorMath", (hsv_pos_x, 0), operation="MULTIPLY")
            separateHSV = create_node(hsvGroup.nodes, "ShaderNodeSeparateColor", (hsv_pos_x + 150, 0))
            separateHSV.mode = 'HSV'
            combine5 = create_node(hsvGroup.nodes, "ShaderNodeCombineXYZ", (hsv_pos_x + 150, 0))
            combine6 = create_node(hsvGroup.nodes, "ShaderNodeCombineXYZ", (hsv_pos_x + 300, 0))
            vecAdd3 = create_node(hsvGroup.nodes, "ShaderNodeVectorMath", (hsv_pos_x + 450, 0))
            combine7 = create_node(hsvGroup.nodes, "ShaderNodeCombineXYZ", (hsv_pos_x + 450, -50))
            combine7.inputs[0].default_value = 1
            vecMul11 = create_node(hsvGroup.nodes, "ShaderNodeVectorMath", (hsv_pos_x + 600, 0), operation="MULTIPLY")
            separate11 = create_node(hsvGroup.nodes, "ShaderNodeSeparateXYZ", (hsv_pos_x + 750, 0))
            combineHSV = create_node(hsvGroup.nodes, "ShaderNodeCombineColor", (hsv_pos_x + 900, 0))
            combineHSV.mode = 'HSV'
            vecMul12 = create_node(hsvGroup.nodes, "ShaderNodeVectorMath", (hsv_pos_x + 1050, 0), operation="MULTIPLY")
            combine8 = create_node(hsvGroup.nodes, "ShaderNodeCombineXYZ", (hsv_pos_x + 1200, -50))
            vecMul13 = create_node(hsvGroup.nodes, "ShaderNodeVectorMath", (hsv_pos_x + 1350, 0), operation="MULTIPLY")
            hsvGroup.links.new(hsvGroupI.outputs[0], vecMul10.inputs[0])
            hsvGroup.links.new(hsvGroupI.outputs[1], vecMul10.inputs[1])
            hsvGroup.links.new(hsvGroupI.outputs[2], combine5.inputs[0])
            hsvGroup.links.new(vecMul10.outputs[0], separateHSV.inputs[0])
            hsvGroup.links.new(separateHSV.outputs[0], combine6.inputs[0])
            hsvGroup.links.new(separateHSV.outputs[1], combine6.inputs[1])
            hsvGroup.links.new(separateHSV.outputs[2], combine6.inputs[2])
            hsvGroup.links.new(combine6.outputs[0], vecAdd3.inputs[0])
            hsvGroup.links.new(combine5.outputs[0], vecAdd3.inputs[1])
            hsvGroup.links.new(hsvGroupI.outputs[3], combine7.inputs[1])
            hsvGroup.links.new(hsvGroupI.outputs[4], combine7.inputs[2])
            hsvGroup.links.new(vecAdd3.outputs[0], vecMul11.inputs[0])
            hsvGroup.links.new(combine7.outputs[0], vecMul11.inputs[1])
            hsvGroup.links.new(vecMul11.outputs[0], separate11.inputs[0])
            hsvGroup.links.new(separate11.outputs[0], combineHSV.inputs[0])
            hsvGroup.links.new(separate11.outputs[1], combineHSV.inputs[1])
            hsvGroup.links.new(separate11.outputs[2], combineHSV.inputs[2])
            hsvGroup.links.new(combineHSV.outputs[0], vecMul12.inputs[0])
            hsvGroup.links.new(hsvGroupI.outputs[5], vecMul12.inputs[1])
            hsvGroup.links.new(hsvGroupI.outputs[6], combine8.inputs[0])
            hsvGroup.links.new(hsvGroupI.outputs[6], combine8.inputs[1])
            hsvGroup.links.new(hsvGroupI.outputs[6], combine8.inputs[2])
            hsvGroup.links.new(vecMul12.outputs[0], vecMul13.inputs[0])
            hsvGroup.links.new(combine8.outputs[0], vecMul13.inputs[1])
            hsvGroup.links.new(vecMul13.outputs[0], hsvGroupO.inputs[0])

        # TODO scroll1 = lerp(emissive, emissive*2, ?)
        #      scrollMask = lerp(color, (.98,0,.05), ?)
        hsv = create_node(CurMat.nodes, "ShaderNodeGroup", (-400, -650), label="hsv")
        hsv.node_tree = hsvGroup
        CurMat.links.new(m3.outputs[0], hsv.inputs[0])
        CurMat.links.new(emissive.outputs[0], hsv.inputs[1])
        CurMat.links.new(texHSVControl_x.outputs[0], hsv.inputs[2])
        CurMat.links.new(texHSVControl_y.outputs[0], hsv.inputs[3])
        CurMat.links.new(texHSVControl_z.outputs[0], hsv.inputs[4])
        CurMat.links.new(gamma.outputs[0], hsv.inputs[5])
        CurMat.links.new(mix.outputs[0], hsv.inputs[6])

        # cameraPos
        vecTform = create_node(CurMat.nodes, "ShaderNodeVectorTransform", (-1050, -1050))
        vecTform.inputs[0].default_value = (0, 0, 0)
        vecTform.convert_from = "CAMERA"
        vecTform.convert_to = "OBJECT"
        vecTform.vector_type = "POINT"

        # viewDir
        vecSub9 = create_node(CurMat.nodes, "ShaderNodeVectorMath", (-900, -1050), operation="SUBTRACT")
        normalize = create_node(CurMat.nodes, "ShaderNodeVectorMath", (-750, -1050), operation="NORMALIZE")
        CurMat.links.new(geometry.outputs[0], vecSub9.inputs[1])
        CurMat.links.new(vecTform.outputs[0], vecSub9.inputs[0])
        CurMat.links.new(vecSub9.outputs[0], normalize.inputs[0])

        # TODO AdditiveAlphaBlend 
        # fresnelValue
        dot = create_node(CurMat.nodes, "ShaderNodeVectorMath", (-600, -1050), operation="DOT_PRODUCT")
        subtract = create_node(CurMat.nodes, "ShaderNodeMath", (-450, -1050), operation="SUBTRACT")
        subtract.inputs[0].default_value = 1
        mix2 = create_node(CurMat.nodes, "ShaderNodeMix", (-300, -1050))
        mix2.inputs[3].default_value = 1
        mul = create_node(CurMat.nodes, "ShaderNodeMath", (-150, -1050), operation="MULTIPLY")
        mul2 = create_node(CurMat.nodes, "ShaderNodeMath", (-0, -1050), operation="MULTIPLY")
        compare = create_node(CurMat.nodes, "ShaderNodeMath", (-450, -1100), operation="COMPARE")
        compare.inputs[0].default_value = 1
        compare.inputs[2].default_value = 0

        CurMat.links.new(geometry.outputs[1], dot.inputs[0])
        CurMat.links.new(normalize.outputs[0], dot.inputs[1])
        CurMat.links.new(dot.outputs["Value"], subtract.inputs[1])
        CurMat.links.new(m3.outputs[1], mul.inputs[0])
        CurMat.links.new(color_a.outputs[0], compare.inputs[1])
        CurMat.links.new(compare.outputs[0], mix2.inputs[0])
        CurMat.links.new(subtract.outputs[0], mix2.inputs[2])
        CurMat.links.new(mix2.outputs[0], mul.inputs[1])
        CurMat.links.new(mul.outputs[0], mul2.inputs[1])
        CurMat.links.new(mix.outputs[0], mul2.inputs[0])

        # to pBSDF
        CurMat.links.new(hsv.outputs[0], pBSDF.inputs["Base Color"])
        CurMat.links.new(hsv.outputs[0], pBSDF.inputs[sockets["Emission"]])
        pBSDF.inputs["Emission Strength"].default_value = 1.0
        CurMat.links.new(mul2.outputs[0], pBSDF.inputs["Alpha"])
