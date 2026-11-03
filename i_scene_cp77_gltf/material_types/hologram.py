<<<<<<< Updated upstream
import bpy
from ..blender.transactions import new_tracked_datablock
from ..materials.blender.images import imageFromRelPath
from ..materials.blender.nodes import bsdf_socket_names, create_node
from .graph import find_socket as _socket, link_tree as _link, set_node_input as _set_input
from .mat_common import MaterialTypeBase, coerce_color, coerce_texture_path, unwrap_param

HOLOGRAM_GROUP_NAME = "Cyberpunk_Hologram_Base"


def _node(nodes, node_type, location, name=None, **attrs):
    node = create_node(nodes, node_type, location)
    if name:
        node.name = name
    for attr, value in attrs.items():
        if hasattr(node, attr):
            setattr(node, attr, value)
    return node


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

    group = new_tracked_datablock("node_groups", HOLOGRAM_GROUP_NAME, "ShaderNodeTree")
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


class Hologram(MaterialTypeBase):
    def _image_from_data(self, data):
        path = _hologram_texture_path(data)
        if not path:
            return None
        return imageFromRelPath(path, self.image_format, DepotPath=self.BasePath, ProjPath=self.ProjPath)

    def create(self, Data, Mat):
        Mat.use_nodes = True
        if bpy.app.version[0] == 4 and bpy.app.version[1] <= 2:
            Mat.shadow_method = 'HASHED'
        if hasattr(Mat, "surface_render_method"):
            Mat.surface_render_method = "DITHERED"
        elif hasattr(Mat, "blend_method"):
            Mat.blend_method = "HASHED"

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
=======
from ..bartmoss.scalar import REC601_LUMA_WEIGHTS, clamp01
from ..blender import shader_nodes
from .graph import mix_color_socket, mix_scalar_socket
from .mat_common import (
    MaterialTypeBase,
    create_relative_texture_node,
    new_labeled_node,
    param_color,
    param_float,
    param_vector,
)
from .normal_math import create_cp77_normal_texture

_WHITE = (1.0, 1.0, 1.0, 1.0)
_BLACK = (0.0, 0.0, 0.0, 1.0)
# Colour defaults of the hologram material template (sRGB bytes), for materials that leave them out.
_SURFACE_COLOR_DEFAULT = (73.0, 168.0, 246.0, 255.0)
_FALLOF_COLOR_DEFAULT = (0.0, 136.0, 163.0, 255.0)


def _split_xyz(tree, source, name, location):
    node = new_labeled_node(tree.nodes, "ShaderNodeSeparateXYZ", name, location)
    tree.links.new(source, node.inputs["Vector"])
    return node


def _split_color(tree, source, name, location):
    node = new_labeled_node(tree.nodes, "ShaderNodeSeparateColor", name, location)
    node.mode = "RGB"
    tree.links.new(source, node.inputs["Color"])
    return node


def _combine_xyz(tree, x, y, z, name, location):
    node = new_labeled_node(tree.nodes, "ShaderNodeCombineXYZ", name, location)
    for source, socket in (
        (x, node.inputs["X"]),
        (y, node.inputs["Y"]),
        (z, node.inputs["Z"]),
    ):
        if hasattr(source, "is_output"):
            tree.links.new(source, socket)
        else:
            socket.default_value = float(source)
    return node.outputs["Vector"]


def _scale_saturation(tree, color, factor, name, location):
    hsv = new_labeled_node(
        tree.nodes, "ShaderNodeSeparateColor", f"{name} HSV", location
    )
    hsv.mode = "HSV"
    tree.links.new(color, hsv.inputs["Color"])
    saturation = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        hsv.outputs["Green"],
        factor,
        name=f"{name} ×{factor:g}",
        location=(location[0] + 180, location[1] - 60),
    )
    rgb = new_labeled_node(
        tree.nodes, "ShaderNodeCombineColor", name, (location[0] + 360, location[1])
    )
    rgb.mode = "HSV"
    tree.links.new(hsv.outputs["Red"], rgb.inputs["Red"])
    tree.links.new(saturation, rgb.inputs["Green"])
    tree.links.new(hsv.outputs["Blue"], rgb.inputs["Blue"])
    return rgb.outputs["Color"]


def _lerp_to_average(tree, color, factor, name, location):
    split = _split_color(tree, color, f"{name} RGB", location)
    total = shader_nodes.math(
        tree.nodes,
        tree.links,
        "ADD",
        split.outputs["Red"],
        split.outputs["Green"],
        name=f"{name} R+G",
        location=(location[0] + 180, location[1]),
    )
    total = shader_nodes.math(
        tree.nodes,
        tree.links,
        "ADD",
        total,
        split.outputs["Blue"],
        name=f"{name} R+G+B",
        location=(location[0] + 340, location[1]),
    )
    average = shader_nodes.math(
        tree.nodes,
        tree.links,
        "DIVIDE",
        total,
        3.0,
        name=f"{name} Average",
        location=(location[0] + 500, location[1]),
    )
    return mix_color_socket(
        tree.nodes,
        tree.links,
        name,
        color,
        _combine_xyz(
            tree,
            average,
            average,
            average,
            f"{name} Grey",
            (location[0] + 520, location[1] - 160),
        ),
        factor,
        (location[0] + 680, location[1]),
    )


class Hologram(MaterialTypeBase):
    def create(self, Data, Mat):
        data = Data if isinstance(Data, dict) else {}
        Mat.use_nodes = True
        Mat.surface_render_method = "DITHERED"
        Mat.use_transparency_overlap = False
        tree = Mat.node_tree
        nodes = tree.nodes
        links = tree.links
        nodes.clear()

        texcoord = new_labeled_node(
            nodes, "ShaderNodeTexCoord", "Coordinates", (-2400, 440)
        )
        uv = texcoord.outputs["UV"]
        local = texcoord.outputs["Object"]
        local_split = _split_xyz(tree, local, "Local Position", (-2200, 160))
        geometry = new_labeled_node(
            nodes, "ShaderNodeNewGeometry", "Geometry", (-2400, -140)
        )
        world_normal = geometry.outputs["Normal"]
        incoming = geometry.outputs["Incoming"]

        normal = create_cp77_normal_texture(
            self,
            tree,
            data,
            "Normal",
            uv=uv,
            strength_key="NormalStrength",
            default_strength=1.0,
            location=(-2180, -500),
            label="Hologram Normal",
        )
        shading_normal = normal if normal is not None else world_normal

        diffuse_tex = create_relative_texture_node(
            self, tree, data, "Diffuse", uv, (-2160, 720)
        )
        diffuse = _WHITE
        diffuse_alpha = 1.0
        coverage = None
        if diffuse_tex is not None:
            full_color_or_grayscale = clamp01(
                param_float(data, "FullColorOrGrayscale", 0.0)
            )
            diffuse_split = _split_color(
                tree, diffuse_tex.outputs["Color"], "Diffuse RGB", (-1920, 720)
            )
            red = diffuse_split.outputs["Red"]
            grayscale = _combine_xyz(
                tree, red, red, red, "Diffuse Grayscale", (-1740, 760)
            )
            # The grayscale switch replaces all four channels with red, alpha included.
            diffuse = mix_color_socket(
                nodes,
                links,
                "Full Color / Grayscale",
                diffuse_tex.outputs["Color"],
                grayscale,
                full_color_or_grayscale,
                (-1540, 720),
            )
            diffuse_alpha = mix_scalar_socket(
                nodes,
                links,
                "Full Color / Grayscale Alpha",
                (-1540, 560),
                diffuse_tex.outputs["Alpha"],
                red,
                full_color_or_grayscale,
            )
            # Texels whose alpha is below 0.01 are discarded.
            coverage = shader_nodes.math(
                nodes,
                links,
                "GREATER_THAN",
                diffuse_alpha,
                0.01,
                name="Diffuse Coverage",
                location=(-1360, 560),
            )
        if param_float(data, "IsHair", 0.0) >= 0.5:
            # Hair keeps its alpha, is discarded where red is below 0.01, and takes a flat grey. The grey feeds the
            # vector sum with the surface colour, so it is an RGB triple.
            diffuse = (0.5, 0.5, 0.5)
            if diffuse_tex is not None:
                hair_coverage = shader_nodes.math(
                    nodes,
                    links,
                    "GREATER_THAN",
                    red,
                    0.01,
                    name="Hair Coverage",
                    location=(-1360, 460),
                )
                coverage = shader_nodes.math(
                    nodes,
                    links,
                    "MULTIPLY",
                    coverage,
                    hair_coverage,
                    name="Hair × Diffuse Coverage",
                    location=(-1180, 500),
                )

        view_dir = shader_nodes.vector_math(
            nodes,
            links,
            "SCALE",
            incoming,
            scale=-1.0,
            name="View Direction",
            location=(-2140, -140),
        )
        view_dir = shader_nodes.vector_math(
            nodes,
            links,
            "NORMALIZE",
            view_dir,
            name="Normalize View",
            location=(-1960, -140),
        )
        view_dot = shader_nodes.vector_math(
            nodes,
            links,
            "DOT_PRODUCT",
            view_dir,
            shading_normal,
            name="View · Normal",
            location=(-1760, -140),
        )
        view_dot = shader_nodes.math(
            nodes,
            links,
            "MAXIMUM",
            view_dot,
            0.0,
            name="max(View·N, 0)",
            location=(-1580, -140),
        )

        fresnel_power = max(0.0, param_float(data, "FresnelStrength", 3.07393003))
        fresnel_pow = shader_nodes.math(
            nodes,
            links,
            "POWER",
            view_dot,
            fresnel_power,
            name="Fresnel Power",
            location=(-1400, -140),
        )
        fresnel = shader_nodes.math(
            nodes,
            links,
            "SUBTRACT",
            1.0,
            fresnel_pow,
            name="1 - Fresnel",
            location=(-1220, -140),
        )
        fresnel = shader_nodes.math(
            nodes,
            links,
            "ADD",
            fresnel,
            max(7.0, fresnel_power) - 7.0,
            name="Fresnel Strength Offset",
            location=(-1040, -140),
        )
        falloff = mix_color_socket(
            nodes,
            links,
            "Falloff Color",
            param_color(data, "FallofColor", _FALLOF_COLOR_DEFAULT),
            (1.0, 1.0, 1.0, 1.0),
            1.0,
            (-820, -140),
            blend_type="MULTIPLY",
            clamp=False,
        )
        falloff = mix_color_socket(
            nodes, links, "Falloff × Fresnel", _BLACK, falloff, fresnel, (-620, -140)
        )

        # Projector1Position is used directly as the light vector.
        projector = param_vector(data, "Projector1Position", (0.0, 0.0, 1.0, 0.0))
        projector_vec = _combine_xyz(
            tree,
            projector[0],
            projector[1],
            projector[2],
            "Projector Direction",
            (-1760, -360),
        )
        projector_dot = shader_nodes.vector_math(
            nodes,
            links,
            "DOT_PRODUCT",
            projector_vec,
            shading_normal,
            name="Projector · Normal",
            location=(-1560, -360),
        )
        bleed = param_float(data, "LightBleed", 0.291498005)
        projector_dot = shader_nodes.math(
            nodes,
            links,
            "ADD",
            projector_dot,
            bleed,
            name="Projector + LightBleed",
            location=(-1380, -360),
        )
        projector_dot = shader_nodes.math(
            nodes,
            links,
            "DIVIDE",
            projector_dot,
            1.0 + bleed,
            name="Projector / (1+Bleed)",
            location=(-1200, -360),
        )
        up_light = shader_nodes.clamp(
            tree.nodes,
            tree.links,
            projector_dot,
            name="Projector Light",
            location=(-1020, -360),
        )
        surface_color = mix_color_socket(
            nodes,
            links,
            "Surface Light",
            param_color(data, "SurfaceShadows", _BLACK),
            param_color(data, "SurfaceColor", _SURFACE_COLOR_DEFAULT),
            up_light,
            (-820, -360),
        )

        # Evaluate gradients in local position space.
        gradient_length = max(1.0e-5, param_float(data, "GradientLength", 1.0))
        gradient_offset = param_float(data, "GradientOffset", -100.0)
        top_delta = shader_nodes.math(
            nodes,
            links,
            "SUBTRACT",
            gradient_offset + 3.0 * gradient_length,
            local_split.outputs["Z"],
            name="Top Gradient Numerator",
            location=(-1560, 80),
        )
        top_delta = shader_nodes.math(
            nodes,
            links,
            "DIVIDE",
            top_delta,
            3.0 * gradient_length,
            name="Top Gradient / Length",
            location=(-1380, 80),
        )
        top_delta = shader_nodes.math(
            tree.nodes,
            tree.links,
            "ABSOLUTE",
            top_delta,
            name="abs Top Gradient",
            location=(-1200, 80),
        )
        top_delta = shader_nodes.clamp(
            tree.nodes,
            tree.links,
            top_delta,
            name="Top Gradient Saturate",
            location=(-1020, 80),
        )
        top_gradient = shader_nodes.math(
            nodes,
            links,
            "SUBTRACT",
            1.0,
            top_delta,
            name="Top/Bottom Gradient",
            location=(-840, 80),
        )
        top_gradient = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            top_gradient,
            1.0 - clamp01(param_float(data, "UseMovingDots", 0.0)),
            name="Moving Dots Gradient Gate",
            location=(-660, 80),
        )

        final_delta = shader_nodes.math(
            nodes,
            links,
            "SUBTRACT",
            gradient_offset + 1.45 + 1.4 * gradient_length,
            local_split.outputs["Z"],
            name="Final Gradient Numerator",
            location=(-1560, -20),
        )
        final_delta = shader_nodes.math(
            nodes,
            links,
            "DIVIDE",
            final_delta,
            1.4 * gradient_length,
            name="Final Gradient / Length",
            location=(-1380, -20),
        )
        final_delta = shader_nodes.math(
            tree.nodes,
            tree.links,
            "ABSOLUTE",
            final_delta,
            name="abs Final Gradient",
            location=(-1200, -20),
        )
        final_delta = shader_nodes.clamp(
            tree.nodes,
            tree.links,
            final_delta,
            name="Final Gradient Saturate",
            location=(-1020, -20),
        )
        final_gradient = shader_nodes.math(
            nodes,
            links,
            "SUBTRACT",
            1.0,
            final_delta,
            name="Final Gradient",
            location=(-840, -20),
        )

        # Scanlines use the fractional local X/Z coordinates after density scaling and axis sign adjustment.
        density = param_float(data, "OpaqueScanlineDensity", 400.0)
        scan_uv = _combine_xyz(
            tree,
            local_split.outputs["X"],
            local_split.outputs["Z"],
            0.0,
            "Local XZ",
            (-1800, -640),
        )
        scan_uv = shader_nodes.vector_math(
            nodes,
            links,
            "MULTIPLY",
            scan_uv,
            (-density, density, 1.0),
            name="Scanline Density",
            location=(-1600, -640),
        )
        scan_uv = shader_nodes.vector_math(
            nodes,
            links,
            "FRACTION",
            scan_uv,
            name="Scanline frac",
            location=(-1420, -640),
        )
        scan_split = _split_xyz(tree, scan_uv, "Scanline UV", (-1240, -640))
        thickness = max(
            -4.0, min(1.0, param_float(data, "ScanlineThickness", -0.578947008))
        )
        stretch = 1.0 - thickness
        scan_y = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            scan_split.outputs["Y"],
            stretch,
            name="Scanline Y Stretch",
            location=(-1060, -700),
        )
        scan_y = shader_nodes.math(
            nodes,
            links,
            "ADD",
            scan_y,
            0.5 - stretch * 0.5,
            name="Scanline Y Center",
            location=(-880, -700),
        )
        scan_uv = _combine_xyz(
            tree,
            scan_split.outputs["X"],
            scan_y,
            0.0,
            "Scanline UV Final",
            (-700, -640),
        )
        scan_tex = create_relative_texture_node(
            self, tree, data, "Scanline", scan_uv, (-500, -640), non_color=True
        )
        opaque_scanlines = 1.0
        if scan_tex is not None:
            opaque_scanlines = _split_color(
                tree, scan_tex.outputs["Color"], "Scanline", (-260, -640)
            ).outputs["Red"]
        moving_gate = mix_scalar_socket(
            nodes,
            links,
            "Gradient / Moving Dots",
            (-40, -640),
            final_gradient,
            0.0,
            clamp01(param_float(data, "UseMovingDots", 0.0)),
        )
        moving_gate = shader_nodes.math(
            nodes,
            links,
            "SUBTRACT",
            1.0,
            moving_gate,
            name="1 - Moving Gradient",
            location=(140, -640),
        )
        opaque_scanlines = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            opaque_scanlines,
            moving_gate,
            name="Opaque Scanlines",
            location=(320, -640),
        )
        use_isobars = param_float(data, "UseIsobars", 0.0)
        if use_isobars != 0.0:
            sharpened = new_labeled_node(
                nodes, "ShaderNodeMapRange", "Isobar Scanlines", (500, -720)
            )
            sharpened.interpolation_type = "SMOOTHSTEP"
            links.new(opaque_scanlines, sharpened.inputs["Value"])
            sharpened.inputs["From Min"].default_value = 0.0
            sharpened.inputs["From Max"].default_value = 0.3
            opaque_scanlines = shader_nodes.lerp(
                nodes,
                links,
                opaque_scanlines,
                sharpened.outputs["Result"],
                use_isobars,
                name="Scanlines / Isobars",
                location=(680, -640),
            )

        contrast = shader_nodes.vector_math(
            nodes,
            links,
            "ADD",
            surface_color,
            (-0.5, -0.5, -0.5),
            name="Surface Contrast - .5",
            location=(-180, 520),
        )
        contrast = shader_nodes.vector_math(
            nodes,
            links,
            "SCALE",
            contrast,
            scale=6.493,
            name="Surface Contrast ×6.493",
            location=(20, 520),
        )
        contrast = shader_nodes.vector_math(
            nodes,
            links,
            "ADD",
            contrast,
            (0.5, 0.5, 0.5),
            name="Surface Contrast + .5",
            location=(220, 520),
        )
        contrast = shader_nodes.vector_math(
            nodes,
            links,
            "MAXIMUM",
            contrast,
            (0.0, 0.0, 0.0),
            name="Surface Contrast max 0",
            location=(320, 600),
        )
        contrast = shader_nodes.vector_math(
            nodes,
            links,
            "SCALE",
            contrast,
            scale=0.2,
            name="Surface Contrast ×0.2",
            location=(420, 520),
        )
        final_color = shader_nodes.vector_math(
            nodes,
            links,
            "ADD",
            diffuse,
            contrast,
            name="Diffuse + Surface",
            location=(620, 520),
        )

        one_minus_top = shader_nodes.math(
            nodes,
            links,
            "SUBTRACT",
            1.0,
            top_gradient,
            name="1 - Top Gradient",
            location=(520, 80),
        )
        falloff_scaled = mix_color_socket(
            nodes, links, "Falloff ×1.2", _BLACK, falloff, 1.2, (720, -100)
        )
        falloff_scaled = mix_color_socket(
            nodes,
            links,
            "Falloff Gradient",
            _BLACK,
            falloff_scaled,
            one_minus_top,
            (920, -100),
        )
        screen_layer = mix_color_socket(
            nodes,
            links,
            "Screen Falloff",
            final_color,
            falloff_scaled,
            1.0,
            (900, 460),
            blend_type="SCREEN",
        )
        final_color = mix_color_socket(
            nodes,
            links,
            "Global Tint Blend",
            screen_layer,
            final_color,
            clamp01(param_float(data, "GlobalTint", 0.0)),
            (1120, 460),
        )
        up_falloff = mix_color_socket(
            nodes,
            links,
            "Projector Falloff",
            _BLACK,
            param_color(data, "FallofColor", _FALLOF_COLOR_DEFAULT),
            up_light,
            (900, 260),
        )
        final_color = mix_color_socket(
            nodes, links, "Projector Blend", final_color, up_falloff, 0.2, (1320, 420)
        )

        final_color = _scale_saturation(
            tree, final_color, 2.0, "Saturation", (1320, 620)
        )

        # Apply sepia/desaturation after color projection.
        luminance = shader_nodes.vector_math(
            nodes,
            links,
            "DOT_PRODUCT",
            final_color,
            REC601_LUMA_WEIGHTS,
            name="Luminance",
            location=(1500, 120),
        )
        sepia = _combine_xyz(
            tree,
            shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                luminance,
                1.2,
                name="Sepia R",
                location=(2020, 200),
            ),
            luminance,
            shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                luminance,
                0.8,
                name="Sepia B",
                location=(2020, 40),
            ),
            "Sepia",
            (2200, 120),
        )
        desat = clamp01(param_float(data, "DesaturationStrength", 0.0))
        final_color = mix_color_socket(
            nodes, links, "Sepia / Desaturation", final_color, sepia, desat, (2400, 360)
        )

        entropy = max(0.0, param_float(data, "EntropyThreshold", 0.0) + 1.0)
        final_color = shader_nodes.vector_math(
            nodes,
            links,
            "ADD",
            final_color,
            (-1.0, -1.0, -1.0),
            name="Entropy -1",
            location=(2600, 360),
        )
        final_color = shader_nodes.vector_math(
            nodes,
            links,
            "SCALE",
            final_color,
            scale=entropy,
            name="Entropy Scale",
            location=(2780, 360),
        )
        final_color = shader_nodes.vector_math(
            nodes,
            links,
            "ADD",
            final_color,
            (1.0, 1.0, 1.0),
            name="Entropy +1",
            location=(2960, 360),
        )
        final_color = shader_nodes.vector_math(
            nodes,
            links,
            "MAXIMUM",
            final_color,
            (0.0, 0.0, 0.0),
            name="Entropy Clamp",
            location=(3140, 360),
        )
        if desat > 0.0:
            # The desaturation strength then pulls the colour twice towards its channel average.
            for index in range(2):
                final_color = _lerp_to_average(
                    tree,
                    final_color,
                    desat,
                    f"Average Desaturation {index + 1}",
                    (3140 + 900 * index, 620),
                )

        # Alpha follows the authored scanline and diffuse/opacity branches.
        opacity = clamp01(param_float(data, "Opacity", 1.0))
        if abs(opacity - 1.0) <= 1.0e-6:
            alpha = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                opaque_scanlines,
                diffuse_alpha,
                name="Scanline × Diffuse Alpha",
                location=(1320, -620),
            )
        else:
            alpha = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                opaque_scanlines,
                opaque_scanlines,
                name="Scanline²",
                location=(1320, -620),
            )
            alpha = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                alpha,
                opacity,
                name="Hologram Opacity",
                location=(1500, -620),
            )
        alpha = shader_nodes.clamp(
            tree.nodes, tree.links, alpha, name="Final Alpha", location=(1680, -620)
        )
        if coverage is not None:
            alpha = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                alpha,
                coverage,
                name="Alpha × Coverage",
                location=(1860, -620),
            )

        emission = new_labeled_node(
            nodes, "ShaderNodeEmission", "Hologram Emission", (3360, 360)
        )
        links.new(final_color, emission.inputs["Color"])
        emission.inputs["Strength"].default_value = 1.0
        transparent = new_labeled_node(
            nodes, "ShaderNodeBsdfTransparent", "Transparent", (3360, 100)
        )
        mix = new_labeled_node(
            nodes, "ShaderNodeMixShader", "Hologram Alpha", (3580, 280)
        )
        links.new(alpha, mix.inputs["Factor"])
        links.new(transparent.outputs["BSDF"], mix.inputs["Shader"])
        links.new(
            emission.outputs["Emission"],
            shader_nodes.socket_by_identifier(mix.inputs, "Shader_001"),
        )
        output = new_labeled_node(
            nodes, "ShaderNodeOutputMaterial", "Material Output", (3820, 280)
        )
        links.new(mix.outputs["Shader"], output.inputs["Surface"])

        Mat.diffuse_color = (*param_color(data, "SurfaceColor", _WHITE)[:3], 1.0)
>>>>>>> Stashed changes
