if __name__ != "__main__":
    from ..main.common import *
    from .mat_common import coerce_color, coerce_texture_path, unwrap_param
else:
    from common import *
    from mat_common import coerce_color, coerce_texture_path, unwrap_param

HOLOGRAM_GROUP_NAME = "Cyberpunk_Hologram_Base"


def _node(nodes, node_type, location, name=None, **attrs):
    node = create_node(nodes, node_type, location)
    if name:
        node.name = name
    for attr, value in attrs.items():
        if hasattr(node, attr):
            setattr(node, attr, value)
    return node


def _socket(collection, name, fallback=None):
    socket = collection.get(name) if hasattr(collection, 'get') else None
    if socket is None and fallback is not None and fallback < len(collection):
        socket = collection[fallback]
    return socket


def _set_input(node, name, value, fallback=None):
    socket = _socket(node.inputs, name, fallback)
    if socket is not None:
        socket.default_value = value


def _link(tree, output_socket, input_socket):
    if output_socket is not None and input_socket is not None:
        tree.links.new(output_socket, input_socket)


def _hologram_texture_path(data):
    for key in ("Diffuse", "Scanline", "Texture", "MainTexture", "Albedo"):
        path = coerce_texture_path(data.get(key)) if isinstance(data, dict) else None
        if path:
            return path
    return None


def _configure_principled(node):
    sockets = bsdf_socket_names()
    if hasattr(node, 'distribution'):
        node.distribution = 'GGX'
    if hasattr(node, 'subsurface_method'):
        node.subsurface_method = 'RANDOM_WALK_SKIN'

    defaults = {
        "Metallic": 0.0,
        "Roughness": 1.0,
        "IOR": 1.4500000476837158,
        "Normal": (0.0, 0.0, 0.0),
        "Subsurface Weight": 0.0,
        "Subsurface Radius": (1.0, 0.20000000298023224, 0.10000000149011612),
        "Subsurface Scale": 0.05000000074505806,
        "Subsurface IOR": 1.399999976158142,
        "Subsurface Anisotropy": 0.0,
        "Specular IOR Level": 0.0,
        "Specular Tint": (1.0, 1.0, 1.0, 1.0),
        "Anisotropic": 0.0,
        "Anisotropic Rotation": 0.0,
        "Tangent": (0.0, 0.0, 0.0),
        "Transmission Weight": 0.0,
        "Coat Weight": 0.0,
        "Coat Roughness": 0.029999999329447746,
        "Coat IOR": 1.5,
        "Coat Tint": (1.0, 1.0, 1.0, 1.0),
        "Coat Normal": (0.0, 0.0, 0.0),
        "Sheen Weight": 0.0,
        "Sheen Roughness": 0.5,
        "Sheen Tint": (1.0, 1.0, 1.0, 1.0),
        "Emission Strength": 30.0,
        }
    for key, value in defaults.items():
        _set_input(node, sockets.get(key, key), value)


def get_or_create_hologram_group():
    group = bpy.data.node_groups.get(HOLOGRAM_GROUP_NAME)
    if group:
        return group

    group = bpy.data.node_groups.new(HOLOGRAM_GROUP_NAME, "ShaderNodeTree")
    group.interface.new_socket(name="Texture Color", socket_type='NodeSocketColor', in_out='INPUT')
    group.interface.new_socket(name="Dots Color", socket_type='NodeSocketColor', in_out='INPUT')
    group.interface.new_socket(name="Shader", socket_type='NodeSocketShader', in_out='OUTPUT')

    nodes = group.nodes
    links = group.links
    sockets = bsdf_socket_names()

    group_input = _node(nodes, "NodeGroupInput", (-1400, 50), name="Group Input")
    group_output = _node(nodes, "NodeGroupOutput", (1700, -250), name="Group Output")

    wave_texture = _node(nodes, "ShaderNodeTexWave", (-865, -250), name="Wave Texture")
    wave_texture.bands_direction = 'Z'
    wave_texture.rings_direction = 'X'
    wave_texture.wave_profile = 'SIN'
    wave_texture.wave_type = 'BANDS'
    wave_texture.inputs[1].default_value = 1.0
    wave_texture.inputs[2].default_value = 0.0
    wave_texture.inputs[3].default_value = 0.5000001192092896
    wave_texture.inputs[4].default_value = 1.0
    wave_texture.inputs[5].default_value = 0.0
    wave_texture.inputs[6].default_value = 0.0

    color_ramp = _node(nodes, "ShaderNodeValToRGB", (-605, -250), name="Color Ramp")
    color_ramp.color_ramp.color_mode = 'RGB'
    color_ramp.color_ramp.hue_interpolation = 'NEAR'
    color_ramp.color_ramp.interpolation = 'LINEAR'
    while len(color_ramp.color_ramp.elements) > 1:
        color_ramp.color_ramp.elements.remove(color_ramp.color_ramp.elements[-1])
    color_ramp.color_ramp.elements[0].position = 0.0
    color_ramp.color_ramp.elements[0].color = (0.0, 0.0, 0.0, 1.0)
    color_ramp.color_ramp.elements.new(0.04545455798506737).color = (1.0, 1.0, 1.0, 1.0)

    alpha_mul = _node(nodes, "ShaderNodeMath", (-285, -250), name="Alpha Multiply", operation='MULTIPLY')
    alpha_mul.inputs[1].default_value = 0.3399999737739563
    alpha_mul.inputs[2].default_value = 0.5

    tex_coord = _node(nodes, "ShaderNodeTexCoord", (-1405, -250), name="Texture Coordinate")
    tex_coord.from_instancer = False

    mapping = _node(nodes, "ShaderNodeMapping", (-1147, -250), name="Mapping")
    mapping.vector_type = 'POINT'
    mapping.inputs[1].default_value = (0.0, 0.0, 0.0)
    mapping.inputs[2].default_value = (0.0, 0.0, 0.0)
    mapping.inputs[3].default_value = (1.0, 1.0, 50.0)

    geometry = _node(nodes, "ShaderNodeNewGeometry", (432, 229), name="Geometry")
    mix_surface = _node(nodes, "ShaderNodeMixShader", (1520, -207), name="Outer Fade Mix")

    color_mix = _node(nodes, "ShaderNodeMix", (-478, 137), name="Color Texture Multiply")
    color_mix.blend_type = 'MULTIPLY'
    color_mix.clamp_factor = True
    color_mix.clamp_result = False
    color_mix.data_type = 'RGBA'
    color_mix.factor_mode = 'UNIFORM'
    color_mix.inputs[0].default_value = 1.0
    color_mix.inputs[1].default_value = (0.5, 0.5, 0.5)
    color_mix.inputs[2].default_value = 0.0
    color_mix.inputs[3].default_value = 0.0
    color_mix.inputs[4].default_value = (0.0, 0.0, 0.0)
    color_mix.inputs[5].default_value = (0.0, 0.0, 0.0)
    color_mix.inputs[8].default_value = (0.0, 0.0, 0.0)
    color_mix.inputs[9].default_value = (0.0, 0.0, 0.0)

    principled = _node(nodes, "ShaderNodeBsdfPrincipled", (-20, 0), name="Principled BSDF")
    _configure_principled(principled)

    backface_mix = _node(nodes, "ShaderNodeMixShader", (821, -223), name="Backface Mix")

    fresnel = _node(nodes, "ShaderNodeFresnel", (700, 100), name="Fresnel")
    fresnel.inputs[0].default_value = 0.8000001907348633
    fresnel.inputs[1].default_value = (0.0, 0.0, 0.0)

    rgb_curves = _node(nodes, "ShaderNodeRGBCurve", (1062, 217), name="Fresnel Curve")
    rgb_curves.mapping.extend = 'EXTRAPOLATED'
    rgb_curves.mapping.tone = 'STANDARD'
    rgb_curves.mapping.black_level = (0.0, 0.0, 0.0)
    rgb_curves.mapping.white_level = (1.0, 1.0, 1.0)
    rgb_curves.mapping.clip_min_x = 0.0
    rgb_curves.mapping.clip_min_y = 0.0
    rgb_curves.mapping.clip_max_x = 1.0
    rgb_curves.mapping.clip_max_y = 1.0
    rgb_curves.mapping.use_clip = True
    for index in range(3):
        curve = rgb_curves.mapping.curves[index]
        curve.points[0].location = (0.0, 0.0)
        curve.points[0].handle_type = 'AUTO'
        curve.points[1].location = (1.0, 1.0)
        curve.points[1].handle_type = 'AUTO'
    alpha_curve = rgb_curves.mapping.curves[3]
    alpha_curve.points[0].location = (0.0, 0.0)
    alpha_curve.points[0].handle_type = 'AUTO'
    alpha_curve.points[1].location = (0.2863638997077942, 0.787500262260437)
    alpha_curve.points[1].handle_type = 'AUTO'
    alpha_curve.points.new(1.0, 1.0).handle_type = 'AUTO'
    rgb_curves.mapping.update()
    rgb_curves.inputs[0].default_value = 1.0

    transparent = _node(nodes, "ShaderNodeBsdfTransparent", (559, -400), name="Transparent BSDF")
    _set_input(transparent, "Color", (1.0, 1.0, 1.0, 1.0), 0)
    _set_input(transparent, "Weight", 0.0, 1)

    _link(group, group_input.outputs.get("Texture Color"), _socket(color_mix.inputs, "B_Color", 7))
    _link(group, group_input.outputs.get("Dots Color"), _socket(color_mix.inputs, "A_Color", 6))
    _link(group, tex_coord.outputs.get('Object'), mapping.inputs.get('Vector'))
    _link(group, mapping.outputs.get('Vector'), wave_texture.inputs.get('Vector'))
    _link(group, wave_texture.outputs.get('Color'), color_ramp.inputs.get('Fac'))
    _link(group, color_ramp.outputs.get('Color'), alpha_mul.inputs[0])
    _link(group, alpha_mul.outputs[0], _socket(principled.inputs, sockets.get("Alpha", "Alpha"), 4))
    _link(
        group, color_mix.outputs.get('Result') or color_mix.outputs[2],
        _socket(principled.inputs, sockets.get("Base Color", "Base Color"), 0)
        )
    _link(
        group, color_mix.outputs.get('Result') or color_mix.outputs[2],
        _socket(principled.inputs, sockets.get("Emission", "Emission Color"), 27)
        )
    _link(group, geometry.outputs.get('Backfacing'), backface_mix.inputs[0])
    _link(group, principled.outputs.get('BSDF'), backface_mix.inputs[1])
    _link(group, transparent.outputs.get('BSDF'), backface_mix.inputs[2])
    _link(group, transparent.outputs.get('BSDF'), mix_surface.inputs[1])
    _link(group, backface_mix.outputs[0], mix_surface.inputs[2])
    _link(group, fresnel.outputs.get('Fac'), rgb_curves.inputs[1])
    _link(group, rgb_curves.outputs.get('Color'), mix_surface.inputs[0])
    _link(group, mix_surface.outputs[0], group_output.inputs[0])

    return group


class Hologram:
    def __init__(self, BasePath, image_format, ProjPath):
        self.BasePath = BasePath
        self.ProjPath = ProjPath
        self.image_format = image_format

    def _image_from_data(self, data):
        path = _hologram_texture_path(data)
        if not path:
            return None
        return imageFromRelPath(path, self.image_format, DepotPath=self.BasePath, ProjPath=self.ProjPath)

    def create(self, Data, Mat):
        Mat.use_nodes = True
        if bpy.app.version[0] == 4 and bpy.app.version[1] <= 2:
            Mat.shadow_method = 'HASHED'
        Mat.blend_method = 'HASHED'

        tree = Mat.node_tree
        tree.nodes.clear()

        output = _node(tree.nodes, "ShaderNodeOutputMaterial", (500, 0), name="Material Output")
        output.is_active_output = True
        output.target = 'ALL'

        holo = _node(tree.nodes, "ShaderNodeGroup", (100, 0), name="Cyberpunk Hologram")
        holo.node_tree = get_or_create_hologram_group()
        holo.inputs["Dots Color"].default_value = coerce_color(
            unwrap_param(Data.get("DotsColor")) if isinstance(Data, dict) else None, (0.0, 0.65, 1.0, 1.0)
            )

        image = self._image_from_data(Data if isinstance(Data, dict) else {})
        if image:
            texture = _node(tree.nodes, "ShaderNodeTexImage", (-250, 150), name="Hologram Texture")
            texture.extension = 'REPEAT'
            texture.interpolation = 'Linear'
            texture.projection = 'FLAT'
            texture.projection_blend = 0.0
            texture.image = image
            _link(tree, texture.outputs.get('Color'), holo.inputs.get("Texture Color"))
        else:
            holo.inputs["Texture Color"].default_value = (1.0, 1.0, 1.0, 1.0)

        _link(tree, holo.outputs.get("Shader") or holo.outputs[0], output.inputs.get('Surface'))
