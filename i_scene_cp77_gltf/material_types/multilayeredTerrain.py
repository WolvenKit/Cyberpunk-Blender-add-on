from ..main.common import *

_ASSET_INDEX_CACHE = {}


def _resolve_indexed_json(root, depot_path):
    if not root or not depot_path:
        return None
    direct = root + depot_path + '.json'
    if os.path.exists(direct):
        return direct
    try:
        from ..main.datakrash import DepotAssetIndex
    except Exception:
        return direct

    root = os.path.abspath(os.path.normpath(root.replace('\\', os.sep)))
    index = _ASSET_INDEX_CACHE.get(root)
    if index is None:
        try:
            index = DepotAssetIndex.cached(root, extensions=('.json',), warn_missing=False)
        except Exception:
            return direct
        _ASSET_INDEX_CACHE[root] = index

    try:
        normalized = depot_path.replace('\\', os.sep).replace('/', os.sep) + '.json'
        return index.resolve_expected(normalized, '.json', warn=False) or direct
    except Exception:
        return direct


def _add_socket(tree, name, socket_type, in_out, default=None):
    if hasattr(tree, 'interface'):
        socket = tree.interface.new_socket(name=name, socket_type=socket_type, in_out=in_out)
    else:
        collection = tree.inputs if in_out == 'INPUT' else tree.outputs
        socket = collection.new(socket_type, name)
    if default is not None and hasattr(socket, 'default_value'):
        socket.default_value = default
    return socket


def _get_cased(data, key, default=None):
    if not isinstance(data, dict) or not key:
        return default
    variants = (key, key[:1].lower() + key[1:], key[:1].upper() + key[1:])
    for variant in variants:
        if variant in data:
            return data[variant]
    return default


def _get_ref_value(data, key, default=None):
    value = _get_cased(data, key)
    if not isinstance(value, dict):
        return value if value is not None else default
    depot = value.get('DepotPath')
    if isinstance(depot, dict):
        return depot.get('$value', default)
    return value.get('$value', default)


def _as_float(value, default=1.0):
    if value in (None, 'null'):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _jsonload_cached(path, cache):
    if path not in cache:
        cache[path] = jsonload(path)
    return cache[path]


def _node(nodes, node_type, location=None, hide=True, label=None, **kwargs):
    node = create_node(nodes, node_type, location or (0, 0), label=label, **kwargs)
    node.hide = hide
    return node


def get_or_create_layer_blend_group():
    name = 'Terrain_Layer_Blend_Universal'
    group = bpy.data.node_groups.get(name)
    if group:
        return group

    group = bpy.data.node_groups.new(name, 'ShaderNodeTree')
    for socket_name in (
            'Color A', 'Metalness A', 'Roughness A', 'Normal A',
            'Color B', 'Metalness B', 'Roughness B', 'Normal B', 'Mask'
            ):
        _add_socket(group, socket_name, 'NodeSocketColor', 'INPUT')
    for socket_name in ('Color', 'Metalness', 'Roughness', 'Normal'):
        _add_socket(group, socket_name, 'NodeSocketColor', 'OUTPUT')

    group_input = _node(group.nodes, 'NodeGroupInput', (-700, 0), hide=False)
    group_output = _node(group.nodes, 'NodeGroupOutput', (200, 0))
    color_mix = _node(group.nodes, 'ShaderNodeMixRGB', (-300, 100), label='Color Mix')
    metal_mix = _node(group.nodes, 'ShaderNodeMixRGB', (-300, 50), label='Metal Mix')
    rough_mix = _node(group.nodes, 'ShaderNodeMixRGB', (-300, 0), label='Rough Mix')
    normal_mix = _node(group.nodes, 'ShaderNodeMixRGB', (-300, -50), label='Normal Mix')

    for index, mix_node in enumerate((color_mix, metal_mix, rough_mix, normal_mix)):
        group.links.new(group_input.outputs[index], mix_node.inputs[1])
        group.links.new(group_input.outputs[index + 4], mix_node.inputs[2])
        group.links.new(group_input.outputs[8], mix_node.inputs[0])
        group.links.new(mix_node.outputs[0], group_output.inputs[index])
    return group


class MultilayeredTerrain:
    def __init__(self, BasePath, image_format, ProjPath):
        self.BasePath = str(BasePath)
        self.ProjPath = ProjPath
        self.image_format = image_format

    def createBaseMaterial(self, matTemplateObj, name):
        group_name = name[:-11]
        if bpy.data.node_groups.get(group_name):
            return

        ct_path = matTemplateObj['colorTexture']['DepotPath']['$value']
        nt_path = matTemplateObj['normalTexture']['DepotPath']['$value']
        rt_path = matTemplateObj['roughnessTexture']['DepotPath']['$value']
        mt_path = matTemplateObj['metalnessTexture']['DepotPath']['$value']

        CT = imageFromRelPath(ct_path, self.image_format, DepotPath=self.BasePath, ProjPath=self.ProjPath)
        NT = imageFromRelPath(
            nt_path, self.image_format, isNormal=True, DepotPath=self.BasePath, ProjPath=self.ProjPath
            )
        RT = imageFromRelPath(
            rt_path, self.image_format, isNormal=True, DepotPath=self.BasePath, ProjPath=self.ProjPath
            )
        MT = imageFromRelPath(
            mt_path, self.image_format, isNormal=True, DepotPath=self.BasePath, ProjPath=self.ProjPath
            )
        tile_mult = float(matTemplateObj.get('tilingMultiplier', 1))

        group = bpy.data.node_groups.new(group_name, 'ShaderNodeTree')
        _add_socket(group, 'Tile Multiplier', 'NodeSocketVector', 'INPUT', (1, 1, 1))
        for socket_name in ('Color', 'Metalness', 'Roughness', 'Normal'):
            _add_socket(group, socket_name, 'NodeSocketColor', 'OUTPUT')

        color_node = _node(group.nodes, 'ShaderNodeTexImage', (0, 0));
        color_node.image = CT
        metal_node = _node(group.nodes, 'ShaderNodeTexImage', (0, -50));
        metal_node.image = MT
        rough_node = _node(group.nodes, 'ShaderNodeTexImage', (0, -100));
        rough_node.image = RT
        normal_node = _node(group.nodes, 'ShaderNodeTexImage', (0, -150));
        normal_node.image = NT
        mapping = _node(group.nodes, 'ShaderNodeMapping', (-310, -64))
        tex_coord = _node(group.nodes, 'ShaderNodeTexCoord', (-500, -64))
        tile_value = _node(group.nodes, 'ShaderNodeValue', (-700, -90));
        tile_value.outputs[0].default_value = tile_mult
        group_input = _node(group.nodes, 'NodeGroupInput', (-700, -180))
        vec_math = _node(group.nodes, 'ShaderNodeVectorMath', (-500, -135), operation='MULTIPLY')
        normal_sep = _node(group.nodes, 'ShaderNodeSeparateColor', (300, -150));
        normal_sep.mode = 'RGB'
        normal_combine = _node(group.nodes, 'ShaderNodeCombineRGB', (500, -150));
        normal_combine.inputs[2].default_value = 1
        group_output = _node(group.nodes, 'NodeGroupOutput', (700, 0))

        for image_node in (color_node, normal_node, rough_node, metal_node):
            group.links.new(mapping.outputs['Vector'], image_node.inputs['Vector'])
        group.links.new(tex_coord.outputs['UV'], mapping.inputs['Vector'])
        group.links.new(vec_math.outputs[0], mapping.inputs['Scale'])
        group.links.new(tile_value.outputs[0], vec_math.inputs[0])
        group.links.new(group_input.outputs[0], vec_math.inputs[1])
        group.links.new(color_node.outputs[0], group_output.inputs[0])
        group.links.new(metal_node.outputs[0], group_output.inputs[1])
        group.links.new(rough_node.outputs[0], group_output.inputs[2])
        group.links.new(normal_node.outputs[0], normal_sep.inputs[0])
        group.links.new(normal_sep.outputs[0], normal_combine.inputs[0])
        group.links.new(normal_sep.outputs[1], normal_combine.inputs[1])
        group.links.new(normal_combine.outputs[0], group_output.inputs[3])

    def setGlobNormal(self, normalimgpath, CurMat, input):
        GNN = _node(CurMat.nodes, 'ShaderNodeVectorMath', (-200, -250), operation='NORMALIZE')
        GNA = _node(CurMat.nodes, 'ShaderNodeVectorMath', (-400, -250), operation='ADD')
        GNS = _node(CurMat.nodes, 'ShaderNodeVectorMath', (-600, -250), operation='SUBTRACT')
        GNGeo = _node(CurMat.nodes, 'ShaderNodeNewGeometry', (-800, -250))
        path = self.BasePath + normalimgpath if os.path.exists(
            self.BasePath + normalimgpath[:-3] + 'png'
            ) else self.ProjPath + normalimgpath
        GNMap = CreateShaderNodeNormalMap(CurMat, path, -600, -550, 'GlobalNormal', self.image_format)
        CurMat.links.new(GNGeo.outputs['Normal'], GNS.inputs[1])
        CurMat.links.new(GNMap.outputs[0], GNS.inputs[0])
        CurMat.links.new(GNS.outputs[0], GNA.inputs[1])
        CurMat.links.new(input, GNA.inputs[0])
        CurMat.links.new(GNA.outputs[0], GNN.inputs[0])
        return GNN.outputs[0]

    def _mask_texture(self, mlmaskpath, index):
        mask_base = os.path.splitext(mlmaskpath)[0]
        mask_name = mlmaskpath.split('\\')[-1:][0][:-7]
        project_path = os.path.splitext(self.ProjPath + mlmaskpath)[0] + '_layers\\' + mask_name + '_' + str(
            index
            ) + '.png'
        depot_path = os.path.splitext(self.BasePath + mlmaskpath)[0] + '_' + str(index) + '.png'
        return imageFromPath(
            project_path if os.path.exists(project_path) else depot_path, self.image_format, isNormal=True
            )

    def createLayerMaterial(self, LayerName, LayerCount, CurMat, mlmaskpath, normalimgpath):
        blend_group = get_or_create_layer_blend_group()

        for x in range(LayerCount - 1):
            layer_node = _node(CurMat.nodes, 'ShaderNodeGroup', (-1400, 400 - 100 * x))
            layer_node.node_tree = blend_group
            layer_node.name = 'Layer_' + str(x)

            mask_node = _node(CurMat.nodes, 'ShaderNodeTexImage', (-2400, 400 - 100 * x), label='Layer_' + str(x + 1))
            mask_node.image = self._mask_texture(mlmaskpath, x + 1)

            source_a = CurMat.nodes['Mat_Mod_Layer_0'] if x == 0 else CurMat.nodes['Layer_' + str(x - 1)]
            source_b = CurMat.nodes['Mat_Mod_Layer_' + str(x + 1)]
            for output_index in range(4):
                CurMat.links.new(source_a.outputs[output_index], layer_node.inputs[output_index])
                CurMat.links.new(source_b.outputs[output_index], layer_node.inputs[output_index + 4])
            CurMat.links.new(mask_node.outputs[0], source_b.inputs[7])
            CurMat.links.new(source_b.outputs[4], layer_node.inputs[8])

        final_node = CurMat.nodes['Layer_' + str(LayerCount - 2)] if LayerCount > 1 else CurMat.nodes['Mat_Mod_Layer_0']
        pBSDF = CurMat.nodes[loc('Principled BSDF')]
        CurMat.links.new(final_node.outputs[0], pBSDF.inputs['Base Color'])
        if normalimgpath:
            CurMat.links.new(self.setGlobNormal(normalimgpath, CurMat, final_node.outputs[3]), pBSDF.inputs['Normal'])
        else:
            CurMat.links.new(final_node.outputs[3], pBSDF.inputs['Normal'])
        CurMat.links.new(final_node.outputs[2], pBSDF.inputs['Roughness'])
        CurMat.links.new(final_node.outputs[1], pBSDF.inputs['Metallic'])

    def _create_layer_group(self, group_name):
        group = bpy.data.node_groups.new(group_name, 'ShaderNodeTree')
        sockets = [
            _add_socket(group, 'ColorScale', 'NodeSocketColor', 'INPUT'),
            _add_socket(group, 'MatTile', 'NodeSocketFloat', 'INPUT'),
            _add_socket(group, 'MbTile', 'NodeSocketFloat', 'INPUT'),
            _add_socket(group, 'MicroblendNormalStrength', 'NodeSocketFloat', 'INPUT'),
            _add_socket(group, 'MicroblendContrast', 'NodeSocketFloat', 'INPUT'),
            _add_socket(group, 'NormalStrength', 'NodeSocketFloat', 'INPUT'),
            _add_socket(group, 'Opacity', 'NodeSocketFloat', 'INPUT'),
            _add_socket(group, 'Mask', 'NodeSocketColor', 'INPUT'),
            ]
        for socket_name in ('Color', 'Metalness', 'Roughness', 'Normal', 'Layer Mask'):
            _add_socket(group, socket_name, 'NodeSocketColor', 'OUTPUT')
        for index, minimum, maximum in ((4, 0, None), (6, 0, 1)):
            socket = sockets[index]
            if hasattr(socket, 'min_value'):
                socket.min_value = minimum
            if maximum is not None and hasattr(socket, 'max_value'):
                socket.max_value = maximum
        return group

    def _configure_layer_defaults(self, LayerGroupN, values, OverrideTable):
        color_table = OverrideTable.get('ColorScale', {})
        normal_table = OverrideTable.get('NormalStrength', {})

        color_scale = values['colorScale']
        LayerGroupN.inputs[0].default_value = color_table[color_scale] if color_scale not in (None,
                                                                                              'null') and color_scale in color_table else (
            1.0, 1.0, 1.0, 1.0)
        LayerGroupN.inputs[1].default_value = _as_float(values['MatTile'])
        LayerGroupN.inputs[2].default_value = _as_float(values['MbScale'])
        LayerGroupN.inputs[3].default_value = _as_float(values['microblendNormalStrength'])
        LayerGroupN.inputs[4].default_value = _as_float(values['MicroblendContrast'])
        LayerGroupN.inputs[5].default_value = normal_table.get(values['normalStrength'], 1)
        LayerGroupN.inputs[6].default_value = _as_float(values['opacity'])

    def _build_layer_nodes(self, group, base_group, microblend_image, values, OverrideTable):
        group_input = _node(group.nodes, 'NodeGroupInput', (-2600, 0))
        group_output = _node(group.nodes, 'NodeGroupOutput', (200, 0))

        base_node = _node(group.nodes, 'ShaderNodeGroup', (-2000, 0))
        base_node.width = 300
        base_node.node_tree = base_group

        color_mix = _node(group.nodes, 'ShaderNodeMixRGB', (-1500, 50))
        color_mix.inputs[0].default_value = 1
        color_mix.blend_type = 'MULTIPLY'

        microblend = _node(group.nodes, 'ShaderNodeTexImage', (-1900, -400), label='Microblend')
        microblend.image = microblend_image

        curve = _node(group.nodes, 'ShaderNodeRGBCurve', (-1600, -350))
        curve.mapping.curves[0].points[0].location = (0, 1)
        curve.mapping.curves[0].points[1].location = (1, 0)
        curve.mapping.curves[1].points[0].location = (0, 1)
        curve.mapping.curves[1].points[1].location = (1, 0)

        mb_greater = _node(group.nodes, 'ShaderNodeMath', (-1200, -350), operation='GREATER_THAN')
        mb_greater.inputs[1].default_value = 0
        mb_mix = _node(group.nodes, 'ShaderNodeMixRGB', (-1200, -400));
        mb_mix.blend_type = 'MIX'
        mb_ramp = _node(group.nodes, 'ShaderNodeValToRGB', (-1350, -500))
        mb_ramp.color_ramp.elements.remove(mb_ramp.color_ramp.elements[1])
        for color, position in (((0.25, 0.25, 0.25, 1), 0.9), ((1, 1, 1, 1), 0.99608)):
            element = mb_ramp.color_ramp.elements.new(position)
            element.color = color

        mb_norm_strength = _node(group.nodes, 'ShaderNodeMixRGB', (-950, -350))
        mb_norm_strength.blend_type = 'MIX'
        mb_norm_strength.inputs[2].default_value = (0.5, 0.5, 1.0, 1.0)
        mb_mapping = _node(group.nodes, 'ShaderNodeMapping', (-2100, -400))
        mb_texcoord = _node(group.nodes, 'ShaderNodeTexCoord', (-2100, -450))
        mb_abs = _node(group.nodes, 'ShaderNodeMath', (-750, -300), operation='ABSOLUTE')
        mb_normal = _node(group.nodes, 'ShaderNodeNormalMap', (-750, -350))
        normal_combine = _node(group.nodes, 'ShaderNodeVectorMath', (-550, -250))
        normal_sub = _node(group.nodes, 'ShaderNodeVectorMath', (-550, -350), operation='SUBTRACT')
        normalize = _node(group.nodes, 'ShaderNodeVectorMath', (-350, -200), operation='NORMALIZE')
        geometry = _node(group.nodes, 'ShaderNodeNewGeometry', (-750, -450))
        normal_strength = _node(group.nodes, 'ShaderNodeNormalMap', (-1200, -200), label='NormalStrength')

        rough_ramp = _node(group.nodes, 'ShaderNodeMapRange', (-1400, -100), label='Roughness Ramp')
        rough_table = OverrideTable.get('RoughLevelsOut', {})
        rough_levels = values['roughLevelsOut']
        if rough_levels in rough_table:
            rough_ramp.inputs['To Min'].default_value = rough_table[rough_levels][1][0]
            rough_ramp.inputs['To Max'].default_value = rough_table[rough_levels][0][0]

        metal_ramp = _node(group.nodes, 'ShaderNodeValToRGB', (-1400, -50), label='Metal Ramp')
        metal_table = OverrideTable.get('MetalLevelsOut', {})
        metal_levels = values['metalLevelsOut']
        if metal_levels in metal_table:
            metal_ramp.color_ramp.elements[1].color = metal_table[metal_levels][0]
            metal_ramp.color_ramp.elements[0].color = metal_table[metal_levels][1]

        mask_mix1 = _node(group.nodes, 'ShaderNodeMixRGB', (-1600, -500));
        mask_mix1.blend_type = 'OVERLAY';
        mask_mix1.inputs[0].default_value = 1
        mask_mix2 = _node(group.nodes, 'ShaderNodeMixRGB', (-1600, -600));
        mask_mix2.blend_type = 'MIX';
        mask_mix2.inputs[0].default_value = 1
        mask_op = _node(group.nodes, 'NodeReroute', (-1600, -650), hide=False)
        mask_mix3 = _node(group.nodes, 'ShaderNodeMixRGB', (-600, -550), label='OPACITY MIX');
        mask_mix3.blend_type = 'MULTIPLY';
        mask_mix3.inputs[0].default_value = 1
        mask_mb_multiply = _node(group.nodes, 'ShaderNodeMath', (-1600, -450), operation='MULTIPLY');
        mask_mb_multiply.inputs[1].default_value = 6.0
        mask_mb_power = _node(group.nodes, 'ShaderNodeMath', (-1600, -550), operation='POWER');
        mask_mb_power.inputs[1].default_value = 100.0;
        mask_mb_power.use_clamp = True

        links = group.links
        links.new(group_input.outputs[0], color_mix.inputs[2])
        links.new(group_input.outputs[1], base_node.inputs[0])
        links.new(group_input.outputs[2], mb_mapping.inputs[3])
        links.new(group_input.outputs[3], mb_greater.inputs[0])
        links.new(group_input.outputs[3], mb_abs.inputs[0])
        links.new(group_input.outputs[4], mask_mix2.inputs[0])
        links.new(group_input.outputs[5], normal_strength.inputs[0])
        links.new(group_input.outputs[6], mask_op.inputs[0])
        links.new(mask_op.outputs[0], mask_mix3.inputs[2])
        links.new(group_input.outputs[7], mask_mix1.inputs[1])
        links.new(group_input.outputs[7], mask_mix2.inputs[2])
        links.new(base_node.outputs[0], color_mix.inputs[1])
        links.new(base_node.outputs[1], metal_ramp.inputs[0])
        links.new(base_node.outputs[2], rough_ramp.inputs[0])
        links.new(base_node.outputs[3], normal_strength.inputs[1])
        links.new(mb_texcoord.outputs[2], mb_mapping.inputs[0])
        links.new(mb_mapping.outputs[0], microblend.inputs[0])
        links.new(microblend.outputs[0], curve.inputs[1])
        links.new(microblend.outputs[0], mb_mix.inputs[2])
        links.new(microblend.outputs[1], mask_mb_multiply.inputs[0])
        links.new(mask_mb_multiply.outputs[0], mask_mix1.inputs[2])
        links.new(mask_mix1.outputs[0], mask_mb_power.inputs[0])
        links.new(mask_mb_power.outputs[0], mask_mix2.inputs[1])
        links.new(mask_mix2.outputs[0], mask_mix3.inputs[1])
        links.new(mask_mix2.outputs[0], mb_ramp.inputs[0])
        links.new(mb_ramp.outputs[0], mb_norm_strength.inputs[0])
        links.new(normal_strength.outputs[0], normal_combine.inputs[0])
        links.new(mb_greater.outputs[0], mb_mix.inputs[0])
        links.new(curve.outputs[0], mb_mix.inputs[1])
        links.new(mb_mix.outputs[0], mb_norm_strength.inputs[1])
        links.new(mb_norm_strength.outputs[0], mb_normal.inputs[1])
        links.new(mb_abs.outputs[0], mb_normal.inputs[0])
        links.new(mb_normal.outputs[0], normal_sub.inputs[0])
        links.new(geometry.outputs['Normal'], normal_sub.inputs[1])
        links.new(normal_sub.outputs[0], normal_combine.inputs[1])
        links.new(normal_combine.outputs[0], normalize.inputs[0])
        links.new(color_mix.outputs[0], group_output.inputs[0])
        links.new(metal_ramp.outputs[0], group_output.inputs[1])
        links.new(rough_ramp.outputs[0], group_output.inputs[2])
        links.new(normalize.outputs[0], group_output.inputs[3])
        links.new(mask_mix3.outputs[0], group_output.inputs[4])

    def create(self, Data, Mat):
        template_cache = {}
        mlsetup_path = _resolve_indexed_json(self.BasePath, Data['MultilayerSetup'])
        mlsetup = _jsonload_cached(mlsetup_path, template_cache)['Data']['RootChunk']
        layers = mlsetup.get('layers') or mlsetup.get('Layers') or []
        layer_count = len(layers)
        CurMat = Mat.node_tree

        for layer_index, layer in enumerate(layers):
            mat_tile = _get_cased(layer, 'MatTile')
            mb_tile = _get_cased(layer, 'MbTile')
            mb_scale = _as_float(mb_tile, _as_float(mat_tile, 1.0))
            microblend = _get_ref_value(layer, 'Microblend', 'null')
            microblend_contrast = _get_cased(layer, 'MicroblendContrast', 1)
            microblend_normal_strength = _get_cased(layer, 'MicroblendNormalStrength')
            opacity = _get_cased(layer, 'Opacity')
            material = _get_ref_value(layer, 'Material')
            color_scale = _get_ref_value(layer, 'ColorScale')
            normal_strength = _get_ref_value(layer, 'NormalStrength')
            rough_levels_out = _get_ref_value(layer, 'RoughLevelsOut')
            metal_levels_out = _get_ref_value(layer, 'MetalLevelsOut')
            microblend_image = imageFromRelPath(
                microblend, self.image_format, True, self.BasePath, self.ProjPath
                ) if microblend != 'null' else None

            template_path = _resolve_indexed_json(self.BasePath, material)
            mltemplate = _jsonload_cached(template_path, template_cache)['Data']['RootChunk']
            override_table = createOverrideTable(mltemplate)

            group_name = os.path.basename(Data['MultilayerSetup'])[:-8] + '_Layer_' + str(layer_index)
            group = self._create_layer_group(group_name)
            layer_node = _node(CurMat.nodes, 'ShaderNodeGroup', (-2000, 500 - 100 * layer_index))
            layer_node.width = 400
            layer_node.node_tree = group
            layer_node.name = 'Mat_Mod_Layer_' + str(layer_index)

            base_group_name = os.path.basename(material)[:-11]
            if not bpy.data.node_groups.get(base_group_name):
                self.createBaseMaterial(mltemplate, os.path.basename(material))
            base_group = bpy.data.node_groups.get(base_group_name)
            if not base_group:
                continue

            values = {
                'MatTile': mat_tile,
                'MbScale': mb_scale,
                'MicroblendContrast': microblend_contrast,
                'microblendNormalStrength': microblend_normal_strength,
                'opacity': opacity,
                'colorScale': color_scale,
                'normalStrength': normal_strength,
                'roughLevelsOut': rough_levels_out,
                'metalLevelsOut': metal_levels_out,
                }
            self._configure_layer_defaults(layer_node, values, override_table)
            self._build_layer_nodes(group, base_group, microblend_image, values, override_table)

        self.createLayerMaterial(
                os.path.basename(Data['MultilayerSetup'])[:-8] + '_Layer_',
                layer_count,
                CurMat,
                Data['MultilayerMask'],
                Data.get('GlobalNormal')
                )
