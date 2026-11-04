import json
import logging
import math

from ..assetio.paths import backslash_depot_key, depot_path_key
from ..bartmoss.geometry import calc_subuv_offset
from ..bartmoss.scalar import clamp01
from ..blender import shader_nodes
from ..blender.shader_nodes import replace_link
from ..core.log import get_logger, log_once
from ..materials.blender.images import image_has_alpha, image_is_placeholder
from ..materials.cache_identity import filtered_material_data_identity
from .bundles import (
    alpha_contrast_socket,
    decal_uv_transform_socket,
    emissive_scale_bundle,
    signed_fraction_socket,
)
from .decal_composite import (
    PROJECTION_COVERAGE_ATTRIBUTE,
    PROJECTOR_BITANGENT_ATTRIBUTE,
    PROJECTOR_FRAME_VALID_ATTRIBUTE,
    PROJECTOR_TANGENT_ATTRIBUTE,
    PROJECTOR_UP_ATTRIBUTE,
)
from .decal_contracts import contract_records
from .decal_math import half_texel_offset
from .decal_profiles import mesh_profile, projected_profile
from .graph import (
    cp77_bitangent_socket,
    cp77_uv_tangent_node,
    mix_color_socket,
    mix_scalar_socket,
    rgb_socket,
    value_socket,
)
from .mat_common import (
    MaterialTypeBase,
    decal_values,
    find_input,
    find_output,
    get_or_build_node_group,
    lookup_param,
    material_property_socket,
    new_labeled_node,
    param_color,
    param_float,
    param_texture_path,
    param_vector,
    populate_color_ramp,
    scene_time_socket,
    unwrap_param,
)
from .normal_math import (
    create_cp77_normal_texture,
    decode_cp77_normal,
    encode_tangent_normal,
    tangent_to_normal_map,
)
from .parallax_math import parallax_uv
from .vehicle_decal_dirt import DIRT_VERSION, build_vehicle_dirt_alpha

_LOG = get_logger(__name__)


_PLAIN_MESH_DECAL_TEMPLATE = "base\\materials\\mesh_decal.mt"
_MESH_DECAL_PARALLAX_TEMPLATE = "base\\materials\\mesh_decal_parallax.mt"
_PLAIN_VEHICLE_MESH_TEMPLATE = "base\\materials\\vehicle_mesh_decal.mt"


def material_cache_identity(raw_material):
    if not isinstance(raw_material, dict):
        return raw_material
    template = raw_material.get("MaterialTemplate", "")
    profile = mesh_profile(template) or projected_profile(template)
    if profile is None:
        return raw_material
    identity = filtered_material_data_identity(raw_material, profile.parameters)
    if "vehicle" in profile.features:
        identity = dict(identity)
        identity["cp77_vehicle_decal_dirt_version"] = DIRT_VERSION
    return identity


def _float(data, profile, name, fallback=0.0):
    return param_float(data, name, profile.defaults.get(name, fallback))


def _color(data, profile, name, fallback=(1.0, 1.0, 1.0, 1.0)):
    return param_color(data, name, profile.defaults.get(name, fallback))


def _store_profile(material, profile):
    material["cp77_decal_family"] = profile.family
    material["cp77_decal_features"] = json.dumps(
        sorted(profile.features), separators=(",", ":")
    )


def _set_transparent(material):
    for name, value in (
        ("surface_render_method", "BLENDED"),
        ("use_backface_culling", False),
        ("use_transparency_overlap", True),
    ):
        if not hasattr(material, name):
            continue
        try:
            setattr(material, name, value)
        except (AttributeError, TypeError, ValueError):
            log_once(
                _LOG,
                logging.DEBUG,
                "_set_transparent",
                "_set_transparent skipped what it could not read or write",
                exc_info=True,
            )
    material["cp77_no_shadows"] = True


def _instance_override_group():
    def build(group):
        input_node = group.nodes.new("NodeGroupInput")
        output_node = group.nodes.new("NodeGroupOutput")
        input_node.location = (-220, 0)
        output_node.location = (80, 0)
        group.links.new(
            input_node.outputs["DiffuseColorScale"],
            output_node.inputs["DiffuseColorScale"],
        )
        group.links.new(
            input_node.outputs["RoughnessScale"], output_node.inputs["RoughnessScale"]
        )
        group.links.new(
            input_node.outputs["DecalAlpha"], output_node.inputs["DecalAlpha"]
        )
        group.links.new(
            input_node.outputs["EmissiveScale"], output_node.inputs["EmissiveScale"]
        )

    return get_or_build_node_group(
        "CP77 Decal Instance Overrides v3",
        (
            ("NodeSocketColor", "DiffuseColorScale"),
            ("NodeSocketFloat", "RoughnessScale"),
            ("NodeSocketFloat", "DecalAlpha"),
            ("NodeSocketFloat", "EmissiveScale"),
        ),
        (
            ("NodeSocketColor", "DiffuseColorScale"),
            ("NodeSocketFloat", "RoughnessScale"),
            ("NodeSocketFloat", "DecalAlpha"),
            ("NodeSocketFloat", "EmissiveScale"),
        ),
        build,
    )


def _instance_overrides(nodes, location=(-1800, 1000)):
    node = new_labeled_node(
        nodes, "ShaderNodeGroup", "CP77 Decal Instance Overrides", location
    )
    node.node_tree = _instance_override_group()
    node.inputs["DiffuseColorScale"].default_value = (1.0, 1.0, 1.0, 1.0)
    node.inputs["RoughnessScale"].default_value = 1.0
    node.inputs["DecalAlpha"].default_value = 1.0
    node.inputs["EmissiveScale"].default_value = 1.0
    return (
        node.outputs["DiffuseColorScale"],
        node.outputs["RoughnessScale"],
        node.outputs["DecalAlpha"],
        node.outputs["EmissiveScale"],
    )


def _projection_coverage(nodes, location=(-1800, 820)):
    node = new_labeled_node(
        nodes,
        "ShaderNodeAttribute",
        "Conformal Projection Coverage",
        location,
    )
    node.attribute_type = "GEOMETRY"
    node.attribute_name = PROJECTION_COVERAGE_ATTRIBUTE
    return node.outputs.get("Fac") or node.outputs["Factor"]


def _projected_parallax_frame(nodes, links, location=(-1840, -1040)):
    geometry = new_labeled_node(
        nodes,
        "ShaderNodeNewGeometry",
        "Projected Parallax Geometry",
        location,
    )
    view = geometry.outputs.get("Incoming")
    components = []
    for index, (axis, attribute_name) in enumerate(
        (
            ("X", PROJECTOR_TANGENT_ATTRIBUTE),
            ("Y", PROJECTOR_BITANGENT_ATTRIBUTE),
            ("Z", PROJECTOR_UP_ATTRIBUTE),
        )
    ):
        attribute = new_labeled_node(
            nodes,
            "ShaderNodeAttribute",
            f"Projected Parallax {axis} Axis",
            (location[0] + 180, location[1] - index * 120),
        )
        attribute.attribute_type = "GEOMETRY"
        attribute.attribute_name = attribute_name
        basis = attribute.outputs["Vector"]
        dot = shader_nodes.vector_math(
            nodes,
            links,
            "DOT_PRODUCT",
            name=f"Projected Parallax View {axis}",
            location=(location[0] + 400, location[1] - index * 120),
        ).node
        links.new(view, dot.inputs["Vector"])
        links.new(basis, shader_nodes.socket_by_identifier(dot.inputs, "Vector_001"))
        components.append(dot.outputs["Value"])
    y = shader_nodes.math(
        nodes,
        links,
        "MULTIPLY",
        components[1],
        -1.0,
        name="Projected Parallax DirectX Y",
        location=(location[0] + 620, location[1] - 120),
    )
    combine = new_labeled_node(
        nodes,
        "ShaderNodeCombineXYZ",
        "Projected Parallax View",
        (location[0] + 820, location[1] - 80),
    )
    links.new(components[0], combine.inputs["X"])
    links.new(y, combine.inputs["Y"])
    links.new(components[2], combine.inputs["Z"])
    normalized = shader_nodes.vector_math(
        nodes,
        links,
        "NORMALIZE",
        combine.outputs["Vector"],
        name="Projected Parallax View Normalize",
        location=(location[0] + 1020, location[1] - 80),
    )
    up = new_labeled_node(
        nodes,
        "ShaderNodeAttribute",
        "Projected Parallax Surface Normal",
        (location[0] + 820, location[1] - 260),
    )
    up.attribute_type = "GEOMETRY"
    up.attribute_name = PROJECTOR_UP_ATTRIBUTE
    valid = new_labeled_node(
        nodes,
        "ShaderNodeAttribute",
        "Projected Parallax Frame Valid",
        (location[0] + 820, location[1] - 380),
    )
    valid.attribute_type = "GEOMETRY"
    valid.attribute_name = PROJECTOR_FRAME_VALID_ATTRIBUTE
    return (
        normalized,
        up.outputs["Vector"],
        valid.outputs.get("Fac") or valid.outputs["Factor"],
    )


def _resolved_texture_path(data, profile, name):
    path = param_texture_path(data, name)
    if not path and isinstance(profile.defaults.get(name), str):
        path = profile.defaults[name]
    return str(path) if path else None


def _texture(
    owner,
    nodes,
    links,
    data,
    profile,
    name,
    location,
    uv,
    *,
    non_color=False,
    extension="REPEAT",
):
    path = _resolved_texture_path(data, profile, name)
    if not path:
        return None
    image = owner._load_relative_image(
        path,
        non_color=non_color,
        error_label=profile.name,
    )
    if image is None or image_is_placeholder(image):
        return None
    node = new_labeled_node(nodes, "ShaderNodeTexImage", name, location)
    node.image = image
    node.extension = extension
    links.new(uv, find_input(node, "Vector"))
    return node


def _red(nodes, links, source, name, location):
    separate = new_labeled_node(nodes, "ShaderNodeSeparateColor", name, location)
    separate.mode = "RGB"
    links.new(source, find_input(separate, "Color"))
    return separate.outputs["Red"]


def _decal_texture_opacity(texture):
    image = getattr(texture, "image", None)
    if image is not None and image_has_alpha(image):
        return texture.outputs["Alpha"]
    return texture.outputs["Color"]


def _texture_alpha(texture):
    return texture.outputs["Alpha"]


def _secondary_diffuse_alpha_socket(
    nodes,
    links,
    texture,
    source_path,
    default_source_path,
    location,
):
    image = getattr(texture, "image", None)
    if image is not None and image_has_alpha(image):
        return texture.outputs["Alpha"]
    if (
        source_path
        and default_source_path
        and depot_path_key(source_path) == depot_path_key(default_source_path)
    ):
        return value_socket(
            nodes,
            "Secondary Diffuse Default Alpha",
            0.0,
            location,
        )
    return _red(
        nodes,
        links,
        texture.outputs["Color"],
        "SecondaryDiffuseAlpha.r",
        location,
    )


def _normal_detail_coverage_group():
    def build(group):
        input_node = group.nodes.new("NodeGroupInput")
        output_node = group.nodes.new("NodeGroupOutput")
        input_node.location = (-520, 0)
        output_node.location = (220, 0)

        vectorize = shader_nodes.vector_math(
            group.nodes,
            group.links,
            "MULTIPLY_ADD",
            name="Normal Detail Coverage Vector",
            label="",
        ).node
        shader_nodes.socket_by_identifier(
            vectorize.inputs, "Vector_001"
        ).default_value = (2.0, 2.0, 0.0)
        shader_nodes.socket_by_identifier(
            vectorize.inputs, "Vector_002"
        ).default_value = (-1.0, -1.0, 0.0)
        vectorize.location = (-320, 0)
        group.links.new(input_node.outputs["Normal"], vectorize.inputs["Vector"])

        magnitude = shader_nodes.vector_math(
            group.nodes,
            group.links,
            "LENGTH",
            name="Normal Detail Coverage Magnitude",
            label="",
            location=(-100, 0),
        ).node
        group.links.new(vectorize.outputs["Vector"], magnitude.inputs["Vector"])

        curve = group.nodes.new("ShaderNodeFloatCurve")
        curve.name = "Normal Detail Coverage"
        curve.location = (100, 0)
        curve.mapping.extend = "HORIZONTAL"
        points = curve.mapping.curves[0].points
        points[0].location = (0.03, 0.0)
        points[0].handle_type = "VECTOR"
        points[1].location = (0.3, 1.0)
        points[1].handle_type = "VECTOR"
        curve.mapping.update()
        group.links.new(magnitude.outputs["Value"], curve.inputs["Value"])
        group.links.new(curve.outputs["Value"], output_node.inputs["Coverage"])

    return get_or_build_node_group(
        "CP77 Normal Detail Coverage v1",
        (("NodeSocketColor", "Normal"),),
        (("NodeSocketFloat", "Coverage"),),
        build,
    )


def _normal_detail_coverage(nodes, links, normal_texture, location):
    node = new_labeled_node(
        nodes,
        "ShaderNodeGroup",
        "Normal Detail Coverage",
        location,
    )
    node.node_tree = _normal_detail_coverage_group()
    links.new(
        normal_texture.outputs["Color"],
        node.inputs["Normal"],
    )
    return node.outputs["Coverage"]


def _rnm_normal_detail_coverage(nodes, links, decoder, location):
    separate = new_labeled_node(
        nodes,
        "ShaderNodeSeparateXYZ",
        "RNM Normal Tangent",
        location,
    )
    links.new(decoder.outputs["Tangent"], separate.inputs["Vector"])
    one_minus_z = shader_nodes.math(
        nodes,
        links,
        "SUBTRACT",
        1.0,
        separate.outputs["Z"],
        name="RNM 1 - Normal Z",
        location=(location[0] + 200, location[1]),
    )
    return shader_nodes.math(
        nodes,
        links,
        "MULTIPLY",
        one_minus_z,
        50.0,
        name="RNM Normal Detail Coverage",
        location=(location[0] + 400, location[1]),
        use_clamp=True,
    )


def _mesh_uv(nodes, links, data, profile):
    uv_map = new_labeled_node(nodes, "ShaderNodeUVMap", "UV", (-2800, 220))
    uv = uv_map.outputs["UV"]
    centered = shader_nodes.vector_math(
        nodes,
        links,
        "SUBTRACT",
        uv,
        (0.5, 0.5, 0.0),
        name="UV - 0.5",
        location=(-2600, 220),
    )
    scaled = shader_nodes.vector_math(
        nodes,
        links,
        "MULTIPLY",
        centered,
        (
            _float(data, profile, "UVScaleX", 1.0),
            _float(data, profile, "UVScaleY", 1.0),
            1.0,
        ),
        name="UV Scale About Center",
        location=(-2400, 220),
    )
    rotate = new_labeled_node(
        nodes, "ShaderNodeVectorRotate", "UV Rotation x PI", (-2200, 220)
    )
    rotate.rotation_type = "Z_AXIS"
    links.new(scaled, find_input(rotate, "Vector"))
    find_input(rotate, "Center").default_value = (0.0, 0.0, 0.0)
    find_input(rotate, "Angle").default_value = (
        _float(data, profile, "UVRotation") * math.pi
    )
    translated = shader_nodes.vector_math(
        nodes,
        links,
        "ADD",
        rotate.outputs["Vector"],
        (
            0.5 + _float(data, profile, "UVOffsetX"),
            0.5 + _float(data, profile, "UVOffsetY"),
            0.0,
        ),
        name="UV Center and Offset",
        location=(-2000, 220),
    )
    wrapped = signed_fraction_socket(
        nodes.id_data,
        translated,
        (-1800, 320),
        "Signed Wrapped UV",
    )
    if "wet" in profile.features:
        time = scene_time_socket(nodes, (-1260, -620), "Wet Decal Scene Time")
        geometry = new_labeled_node(
            nodes, "ShaderNodeNewGeometry", "Wet Decal Normal", (-1640, -620)
        )
        tangent = cp77_uv_tangent_node(nodes, (-1640, -780), label="Wet Decal Tangent")
        binormal = cp77_bitangent_socket(
            nodes,
            links,
            geometry.outputs.get("Normal"),
            tangent.outputs.get("Tangent"),
            (-1420, -700),
            label="Wet Decal Binormal",
        )
        components = new_labeled_node(
            nodes, "ShaderNodeSeparateXYZ", "Wet Binormal Components", (-1200, -700)
        )
        links.new(binormal, components.inputs["Vector"])
        positive = shader_nodes.math(
            nodes,
            links,
            "GREATER_THAN",
            components.outputs["Z"],
            0.0,
            name="Wet Binormal Z Positive",
            location=(-980, -700),
        )
        signed_time = mix_scalar_socket(
            nodes,
            links,
            "Wet Scroll Direction",
            (-760, -700),
            time,
            shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                time,
                -1.0,
                name="Negative Wet Time",
                location=(-980, -840),
            ),
            positive,
        )
        wet_offset = new_labeled_node(
            nodes, "ShaderNodeCombineXYZ", "Wet Scroll Offset", (-540, -700)
        )
        links.new(signed_time, wet_offset.inputs["Y"])
        wrapped = shader_nodes.vector_math(
            nodes,
            links,
            "ADD",
            wrapped,
            wet_offset.outputs["Vector"],
            name="Wet Scrolled UV",
            location=(-320, -620),
        )
        wrapped = signed_fraction_socket(
            nodes.id_data,
            wrapped,
            (-100, -560),
            "Wet Signed Wrapped UV",
        )
    if "emissive" in profile.features:
        scroll_time = scene_time_socket(nodes, (-1420, -1020), "Emissive Scroll Time")
        scroll = param_vector(
            data,
            "ScrollSpeed",
            profile.defaults.get("ScrollSpeed", (0.0, 0.0, 0.0, 0.0)),
        )
        wrapped = shader_nodes.vector_math(
            nodes,
            links,
            "MULTIPLY_ADD",
            (scroll[0], scroll[1], 0.0),
            scroll_time,
            wrapped,
            name="Pre-Flipbook Emissive UV",
            location=(-1020, -1020),
        )
    columns = max(1, int(_float(data, profile, "AnimationFramesWidth", 1.0)))
    rows = max(1, int(_float(data, profile, "AnimationFramesHeight", 1.0)))
    if columns == 1 and rows == 1:
        return wrapped

    scaled_uv = shader_nodes.vector_math(
        nodes,
        links,
        "DIVIDE",
        wrapped,
        (columns, rows, 1.0),
        name="Flipbook UV Scale",
        location=(-820, 220),
    )
    time = scene_time_socket(nodes, (-1260, -360))
    phase = shader_nodes.math(
        nodes,
        links,
        "MULTIPLY",
        time,
        _float(data, profile, "AnimationSpeed", 1.0),
        name="Flipbook Time x Speed",
        location=(-1060, -360),
    )
    phase = shader_nodes.math(
        nodes, links, "FRACT", phase, name="Flipbook Phase", location=(-880, -360)
    )
    frame = shader_nodes.math(
        nodes,
        links,
        "MULTIPLY",
        phase,
        columns * rows,
        name="Flipbook Frame Float",
        location=(-700, -360),
    )
    tile_number = _float(data, profile, "TileNumber", 0.0)
    if tile_number:
        frame = shader_nodes.math(
            nodes,
            links,
            "ADD",
            frame,
            tile_number,
            name="Flipbook Tile Number",
            location=(-520, -500),
        )
    floored_frame = shader_nodes.math(
        nodes, links, "FLOOR", frame, name="Flipbook Frame", location=(-520, -300)
    )
    column = shader_nodes.math(
        nodes,
        links,
        "DIVIDE",
        floored_frame,
        columns,
        name="Flipbook Column Offset",
        location=(-160, -300),
    )
    row = shader_nodes.math(
        nodes,
        links,
        "DIVIDE",
        frame,
        columns,
        name="Flipbook Row Float",
        location=(-340, -440),
    )
    row = shader_nodes.math(
        nodes, links, "FLOOR", row, name="Flipbook Row", location=(-160, -440)
    )
    row = shader_nodes.math(
        nodes,
        links,
        "MULTIPLY",
        row,
        -1.0 / rows,
        name="Flipbook Row Offset",
        location=(200, -440),
    )
    offset = new_labeled_node(
        nodes, "ShaderNodeCombineXYZ", "Flipbook Offset", (380, -340)
    )
    links.new(column, offset.inputs["X"])
    links.new(row, offset.inputs["Y"])
    return shader_nodes.vector_math(
        nodes,
        links,
        "ADD",
        scaled_uv,
        offset.outputs["Vector"],
        name="Flipbook UV",
        location=(580, 220),
    )


def _projected_half_texel(owner, data, profile):
    if {"terrain", "forward", "caustics", "thermal"} & profile.features:
        return (0.0, 0.0, 0.0)
    if {"glitch", "glitch_emissive"} & profile.features:
        return (0.0, 0.0, 0.0)
    texture_key = (
        "Emissive"
        if "emissive_color" in profile.features
        else "EmissiveMask"
        if "emissive_only" in profile.features
        else "RoughnessTexture"
        if profile.name == "decal_roughness_only"
        else "DiffuseTexture"
    )
    path = _resolved_texture_path(data, profile, texture_key)
    if path:
        image = owner._load_relative_image(
            path,
            non_color=(
                texture_key in {"EmissiveMask", "RoughnessTexture"}
                or (texture_key == "DiffuseTexture" and "gradient" in profile.features)
            ),
            error_label=profile.name,
        )
        if image is not None and not image_is_placeholder(image):
            width, height = (int(value) for value in image.size[:2])
            if width > 0 and height > 0:
                return half_texel_offset(width, height)
    return half_texel_offset(0, 0)


def _projected_uv(owner, nodes, data, profile):
    """Select pixel-region or frame-based decal UV mapping"""
    uv = new_labeled_node(
        nodes, "ShaderNodeUVMap", "Projected Decal UV", (-2200, 220)
    ).outputs["UV"]
    columns = rows = 1
    offset_u = offset_v = 0.0
    atlas_scale = (1.0, 1.0, 1.0)
    atlas_offset = (0.0, 0.0, 0.0)
    if "atlas" in profile.features:
        atlas = param_vector(
            data, "AtlasSize", profile.defaults.get("AtlasSize", (1.0, 1.0, 0.0, 0.0))
        )
        region = param_vector(
            data,
            "SubRegion",
            profile.defaults.get("SubRegion", (0.0, 0.0, atlas[0], atlas[1])),
        )
        atlas_x = max(1.0e-8, atlas[0])
        atlas_y = max(1.0e-8, atlas[1])
        atlas_scale = (region[2] / atlas_x, region[3] / atlas_y, 1.0)
        atlas_offset = (region[0] / atlas_x, region[1] / atlas_y, 0.0)
    else:
        columns = max(1, int(_float(data, profile, "SubUVx", 1.0)))
        rows = max(1, int(_float(data, profile, "SubUVy", 1.0)))
        offset_u, offset_v = calc_subuv_offset(
            _float(data, profile, "Frame") + columns,
            columns,
            rows,
        )
    return decal_uv_transform_socket(
        nodes.id_data,
        uv,
        (-1940, 220),
        half_texel=_projected_half_texel(owner, data, profile),
        frame_size=(columns, rows, 1.0),
        frame_offset=(offset_u, offset_v, 0.0),
        atlas_scale=atlas_scale,
        atlas_offset=atlas_offset,
        label="Projected Decal UV Transform",
    )


def _parallax_uv(owner, nodes, links, data, profile, uv):
    if "parallax" not in profile.features:
        return uv, None
    height_path = param_texture_path(data, "HeightTexture")
    if not height_path:
        raw_default = profile.defaults.get("HeightTexture")
        height_path = unwrap_param(raw_default) if raw_default is not None else None
    if not height_path:
        return uv, None
    shifted = parallax_uv(
        owner,
        nodes.id_data,
        data,
        uv,
        height_key="HeightTexture",
        strength_key="HeightStrength",
        height_path=height_path,
        strength=_float(data, profile, "HeightStrength"),
        location=(-1280, -900),
        label="Decal Parallax",
        frame_factory=(lambda: _projected_parallax_frame(nodes, links))
        if profile.family == "projected"
        else None,
    )
    return shifted, None


def _normal(
    owner,
    nodes,
    links,
    data,
    profile,
    uv,
    location=(-700, -120),
    *,
    rnm_mode=None,
    rnm_alpha_texture=False,
):
    normal_path = param_texture_path(data, "NormalTexture")
    if not normal_path:
        raw_default = profile.defaults.get("NormalTexture")
        normal_path = unwrap_param(raw_default) if raw_default is not None else None
    if not normal_path:
        return None
    normal_data = data
    if param_texture_path(data, "NormalTexture") != normal_path:
        normal_data = dict(data)
        normal_data["NormalTexture"] = normal_path

    if rnm_mode is None:
        rnm_mode = _float(data, profile, "NormalsBlendingMode") > 0.5
    if not rnm_mode:
        return create_cp77_normal_texture(
            owner,
            nodes.id_data,
            normal_data,
            key="NormalTexture",
            uv=uv,
            strength_key="NormalStrength",
            default_strength=_float(data, profile, "NormalStrength", 1.0),
            location=(location[0] - 440, location[1]),
            label="NormalTexture",
        )

    image = owner._load_relative_image(
        normal_path,
        non_color=True,
        error_label="NormalTexture",
    )
    if image is None or image_is_placeholder(image):
        return None
    texture = new_labeled_node(
        nodes,
        "ShaderNodeTexImage",
        "NormalTexture",
        (location[0] - 440, location[1]),
    )
    texture.image = image
    texture.extension = "REPEAT"
    links.new(uv, find_input(texture, "Vector"))
    decoder = decode_cp77_normal(
        nodes.id_data,
        texture.outputs["Color"],
        strength=max(0.0, _float(data, profile, "NormalStrength", 1.0)),
        location=(location[0] - 180, location[1]),
        label="NormalTexture DirectX Decode",
    )
    rnm_tangent = shader_nodes.vector_math(
        nodes,
        links,
        "MULTIPLY",
        decoder.outputs["Tangent"],
        (-1.0, -1.0, 1.0),
        name="RNM Decal Tangent XY Orientation",
        location=(location[0] + 80, location[1]),
    )
    if rnm_alpha_texture:
        alpha_path = param_texture_path(data, "NormalsBlendingModeAlpha")
        if not alpha_path:
            raw_default = profile.defaults.get("NormalsBlendingModeAlpha")
            alpha_path = unwrap_param(raw_default) if raw_default is not None else None
        if alpha_path:
            alpha_image = owner._load_relative_image(
                alpha_path,
                non_color=True,
                error_label="NormalsBlendingModeAlpha",
            )
            if alpha_image is not None and not image_is_placeholder(alpha_image):
                alpha_texture = new_labeled_node(
                    nodes,
                    "ShaderNodeTexImage",
                    "NormalsBlendingModeAlpha",
                    (location[0] - 180, location[1] - 260),
                )
                alpha_texture.image = alpha_image
                alpha_texture.extension = "REPEAT"
                links.new(uv, find_input(alpha_texture, "Vector"))
                alpha = _red(
                    nodes,
                    links,
                    alpha_texture.outputs["Color"],
                    "NormalsBlendingModeAlpha.r",
                    (location[0] + 40, location[1] - 260),
                )
                delta = shader_nodes.vector_math(
                    nodes,
                    links,
                    "SUBTRACT",
                    decoder.outputs["Tangent"],
                    rnm_tangent,
                    name="RNM Receiver Approximation Delta",
                    location=(location[0] + 260, location[1] - 180),
                )
                rnm_tangent = shader_nodes.vector_math(
                    nodes,
                    links,
                    "MULTIPLY_ADD",
                    delta,
                    alpha,
                    rnm_tangent,
                    name="RNM Tangent Alpha Blend",
                    location=(location[0] + 660, location[1] - 100),
                )
                rnm_tangent = shader_nodes.vector_math(
                    nodes,
                    links,
                    "NORMALIZE",
                    rnm_tangent,
                    name="RNM Tangent Alpha Normalized",
                    location=(location[0] + 860, location[1] - 100),
                )
    encoded = encode_tangent_normal(
        nodes.id_data,
        rnm_tangent,
        location=(
            location[0] + 1080 if rnm_alpha_texture else location[0] + 300,
            location[1],
        ),
        label="RNM Decal Tangent Encode",
    )
    normal = tangent_to_normal_map(
        nodes.id_data,
        encoded,
        location=(
            location[0] + 1280 if rnm_alpha_texture else location[0] + 500,
            location[1],
        ),
        label="NormalTexture",
    )
    return normal


def _displacement(nodes, links, output, value):
    if abs(float(value)) <= 1.0e-12:
        return
    node = new_labeled_node(
        nodes, "ShaderNodeDisplacement", "VertexOffsetFactor", (1680, -520)
    )
    find_input(node, "Height").default_value = float(value)
    find_input(node, "Midlevel").default_value = 0.0
    find_input(node, "Scale").default_value = 1.0
    links.new(node.outputs["Displacement"], output.inputs["Displacement"])


def _new_graph(material, label):
    material.use_nodes = True
    tree = material.node_tree
    tree.nodes.clear()
    output = new_labeled_node(
        tree.nodes, "ShaderNodeOutputMaterial", "Material Output", (2100, 180)
    )
    principled = new_labeled_node(
        tree.nodes, "ShaderNodeBsdfPrincipled", label, (1800, 180)
    )
    tree.links.new(principled.outputs["BSDF"], output.inputs["Surface"])
    return tree, output, principled


def _gradient_color(owner, nodes, links, data, profile, diffuse_texture, location):
    raw_position = _red(
        nodes,
        links,
        diffuse_texture.outputs["Color"],
        "Gradient Position.r",
        (location[0] - 620, location[1]),
    )
    position = shader_nodes.clamp(
        nodes,
        links,
        raw_position,
        name="Gradient Position Saturate",
        location=(location[0] - 440, location[1]),
    )
    coordinate = new_labeled_node(
        nodes,
        "ShaderNodeCombineXYZ",
        "Gradient Coordinate",
        (location[0] - 80, location[1]),
    )
    links.new(position, coordinate.inputs["X"])
    coordinate.inputs["Y"].default_value = 0.5
    gradient = _texture(
        owner,
        nodes,
        links,
        data,
        profile,
        "GradientMap",
        location,
        coordinate.outputs["Vector"],
        extension="EXTEND",
    )
    if gradient is None and "gradient_resource" in profile.features:
        raw = unwrap_param(lookup_param(data, "Gradient"))
        entries = (
            raw.get("entries", raw.get("Entries", ())) if isinstance(raw, dict) else raw
        )
        if isinstance(entries, (list, tuple)) and entries:
            normalized = []
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                value = entry.get("value", entry.get("Value", 0.0))
                color = unwrap_param(entry.get("color", entry.get("Color", {})))
                if isinstance(color, dict):
                    normalized.append({"value": value, "color": color})
            if normalized:
                ramp = new_labeled_node(
                    nodes, "ShaderNodeValToRGB", "Gradient Resource", location
                )
                populate_color_ramp(ramp, normalized)
                links.new(position, ramp.inputs["Factor"])
                return ramp.outputs["Color"], position, ramp.outputs["Alpha"]
    if gradient is None:
        return diffuse_texture.outputs["Color"], position, 1.0
    return gradient.outputs["Color"], position, gradient.outputs["Alpha"]


def _multiply_mask(nodes, links, coverage, mask, name, location):
    if mask is None:
        return coverage
    return shader_nodes.math(
        nodes,
        links,
        "MULTIPLY",
        coverage,
        _red(
            nodes,
            links,
            mask.outputs["Color"],
            f"{name} Mask.r",
            (location[0] - 240, location[1] - 100),
        ),
        name=name,
        location=location,
    )


class ProjectedDecal(MaterialTypeBase):
    def create(self, Data, Mat):
        profile = projected_profile(Mat.get("MaterialTemplate"))
        if profile is None:
            raise ValueError(
                f"No projected decal profile for {Mat.get('MaterialTemplate', '')}"
            )
        if isinstance(Data, dict) and isinstance(Data.get("values"), list):
            data = dict(decal_values(Data))
            for key in (
                "__sectorMaterialPath",
                "normalBlendingMode",
            ):
                if key in Data:
                    data[key] = Data[key]
        else:
            data = dict(Data) if isinstance(Data, dict) else {}
        _store_profile(Mat, profile)
        normal_blending_mode = int(data.get("normalBlendingMode", 0) or 0)
        Mat["normalBlendingMode"] = normal_blending_mode
        tree, _, principled = _new_graph(Mat, profile.name)
        nodes, links = tree.nodes, tree.links
        (
            color_override,
            roughness_override,
            decal_alpha,
            emissive_scale,
        ) = _instance_overrides(nodes)
        projection_coverage = _projection_coverage(nodes)
        uv = _projected_uv(self, nodes, data, profile)
        uv, _ = _parallax_uv(self, nodes, links, data, profile, uv)

        if "forward" in profile.features:
            self._build_forward(
                data,
                Mat,
                profile,
                nodes,
                links,
                principled,
                uv,
                color_override,
                roughness_override,
                projection_coverage,
                decal_alpha,
                emissive_scale,
            )
            _set_transparent(Mat)
            return
        if "terrain" in profile.features:
            alpha = self._build_terrain(
                data,
                profile,
                nodes,
                links,
                principled,
                uv,
                color_override,
                roughness_override,
            )
            alpha = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                alpha,
                projection_coverage,
                name="Conformal Projection Coverage",
                location=(1320, -340),
            )
            links.new(alpha, find_input(principled, "Alpha"))
            _set_transparent(Mat)
            return

        colorless_pass = profile.name == "decal_roughness_only"
        diffuse = (
            None
            if colorless_pass
            else _texture(
                self,
                nodes,
                links,
                data,
                profile,
                "DiffuseTexture",
                (-1500, 620),
                uv,
                non_color="gradient" in profile.features,
            )
        )
        base_color = None
        if not colorless_pass:
            base_color = rgb_socket(
                nodes,
                "DiffuseColor",
                _color(data, profile, "DiffuseColor"),
                (-1180, 840),
            )
        texture_alpha = value_socket(
            nodes, "Diffuse Texture Alpha Fallback", 1.0, (-1180, 500)
        )
        gradient_position = None
        gradient_alpha = None
        if diffuse is not None:
            texture_alpha = _decal_texture_opacity(diffuse)
            if "gradient" in profile.features:
                base_color, gradient_position, gradient_alpha = _gradient_color(
                    self, nodes, links, data, profile, diffuse, (-900, 640)
                )
                base_color = mix_color_socket(
                    nodes,
                    links,
                    "Gradient x DiffuseColor",
                    base_color,
                    _color(data, profile, "DiffuseColor"),
                    1.0,
                    (-580, 700),
                    blend_type="MULTIPLY",
                )
            elif "tint3" in profile.features:
                base_color = diffuse.outputs["Color"]
            else:
                base_color = mix_color_socket(
                    nodes,
                    links,
                    "Diffuse Texture x Color",
                    diffuse.outputs["Color"],
                    base_color,
                    1.0,
                    (-900, 720),
                    blend_type="MULTIPLY",
                )

        if "tint3" in profile.features and diffuse is not None:
            base_color = self._tint3(data, profile, nodes, links, uv, base_color)
        if {"glitch", "glitch_emissive"} & profile.features:
            base_color = self._glitch(data, profile, nodes, links, uv, base_color)
        if "caustics" in profile.features:
            base_color, texture_alpha = self._caustics(data, profile, nodes, links, uv)
        if "thermal" in profile.features:
            texture_alpha = self._thermal(
                data, profile, nodes, links, uv, texture_alpha
            )

        mask_path = param_texture_path(data, "MaskTexture")
        mask_is_explicit = bool(mask_path)
        mask = (
            _texture(
                self,
                nodes,
                links,
                data,
                profile,
                "MaskTexture",
                (-1500, 340),
                uv,
                non_color=True,
            )
            if mask_is_explicit
            else None
        )
        if "gradient" in profile.features and diffuse is not None:
            # The gradient map's alpha cuts the background (at whichever end of the ramp it sits); the mask cuts the
            # rest, as for mesh decals.
            texture_alpha = (
                gradient_alpha if gradient_alpha is not None else texture_alpha
            )
            if mask_is_explicit:
                texture_alpha = _multiply_mask(
                    nodes,
                    links,
                    texture_alpha,
                    mask,
                    "MaskTexture x Gradient Alpha",
                    (-900, 420),
                )
        else:
            diffuse_as_mask = (
                diffuse is not None
                and _float(data, profile, "DiffuseTextureAsMaskTexture") >= 0.5
            )
            if mask_is_explicit and not diffuse_as_mask:
                texture_alpha = _multiply_mask(
                    nodes,
                    links,
                    texture_alpha,
                    mask,
                    "MaskTexture x Alpha",
                    (-900, 420),
                )
            if diffuse_as_mask:
                texture_alpha = _red(
                    nodes,
                    links,
                    diffuse.outputs["Color"],
                    "DiffuseTexture.r as Mask",
                    (-1180, 240),
                )
        texture_alpha = alpha_contrast_socket(
            nodes.id_data,
            texture_alpha,
            _float(data, profile, "AlphaMaskContrast"),
            (-620, 420),
        )
        texture_alpha = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            texture_alpha,
            projection_coverage,
            name="Conformal Projection Coverage",
            location=(-420, 320),
        )
        diffuse_alpha = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            texture_alpha,
            _float(data, profile, "DiffuseAlpha", 1.0),
            name="DiffuseAlpha",
            location=(-380, 420),
        )

        if colorless_pass:
            color = None
            find_input(principled, "Base Color").default_value = (0.18, 0.18, 0.18, 1.0)
        else:
            color = mix_color_socket(
                nodes,
                links,
                "Sector DiffuseColorScale",
                base_color,
                color_override,
                1.0,
                (680, 700),
                blend_type="MULTIPLY",
            )
            if not ({"emissive_color", "emissive_only"} & profile.features):
                links.new(color, find_input(principled, "Base Color"))

        normal_alpha = value_socket(nodes, "No Normal Influence", 0.0, (680, 80))
        if "normal" in profile.features:
            normal = _normal(
                self,
                nodes,
                links,
                data,
                profile,
                uv,
                rnm_mode=normal_blending_mode > 0,
            )
            if normal is not None:
                links.new(normal, find_input(principled, "Normal"))
                if normal_blending_mode > 0:
                    decoder = nodes.get("NormalTexture DirectX Decode")
                    tangent = (
                        decoder.outputs.get("Tangent") if decoder is not None else None
                    )
                    if tangent is not None:
                        components = new_labeled_node(
                            nodes,
                            "ShaderNodeSeparateXYZ",
                            "Projected Normal Components",
                            (280, 80),
                        )
                        links.new(tangent, components.inputs["Vector"])
                        normal_alpha = shader_nodes.math(
                            nodes,
                            links,
                            "MULTIPLY_ADD",
                            components.outputs["Z"],
                            -50.0,
                            name="Normal Influence",
                            location=(500, 80),
                        )
                        shader_nodes.socket_by_identifier(
                            normal_alpha.node.inputs, "Value_002"
                        ).default_value = 50.0
                        normal_alpha.node.use_clamp = True
                    else:
                        normal_alpha = shader_nodes.math(
                            nodes,
                            links,
                            "MULTIPLY",
                            texture_alpha,
                            1.0,
                            name="Normal Influence",
                            location=(680, 80),
                        )
                else:
                    normal_alpha = shader_nodes.math(
                        nodes,
                        links,
                        "MULTIPLY",
                        texture_alpha,
                        1.0,
                        name="Normal Influence",
                        location=(680, 80),
                    )

        material_alpha = value_socket(nodes, "Material Influence", 0.0, (680, -180))
        if "roughness_bias" in profile.features:
            final_roughness = shader_nodes.math(
                nodes,
                links,
                "ADD",
                roughness_override,
                _float(data, profile, "RoughnessBias"),
                name="Roughness Bias Amount",
                location=(520, -240),
            )
            target_roughness = shader_nodes.math(
                nodes,
                links,
                "GREATER_THAN",
                final_roughness,
                1.0,
                name="Roughness Bias Target",
                location=(720, -240),
            )
            links.new(target_roughness, find_input(principled, "Roughness"))
            influence = shader_nodes.math(
                nodes,
                links,
                "SUBTRACT",
                1.0,
                final_roughness,
                name="Roughness Bias Distance",
                location=(720, -100),
            )
            influence = shader_nodes.math(
                nodes,
                links,
                "ABSOLUTE",
                influence,
                name="Roughness Bias Absolute Distance",
                location=(900, -100),
            )
            influence = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                influence,
                _float(data, profile, "RoughnessMetalnessAlpha", 1.0),
                name="Roughness Bias Alpha",
                location=(1080, -100),
            )
            material_alpha = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                texture_alpha,
                influence,
                name="Roughness Bias Influence",
                location=(1260, -100),
            )
        elif "roughness" in profile.features:
            roughness = _texture(
                self,
                nodes,
                links,
                data,
                profile,
                "RoughnessTexture",
                (80, -240),
                uv,
                non_color=True,
            )
            sample = (
                _red(
                    nodes,
                    links,
                    roughness.outputs["Color"],
                    "RoughnessTexture.r",
                    (320, -240),
                )
                if roughness
                else 0.5
            )
            scaled = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                sample,
                _float(data, profile, "RoughnessScale", 1.0),
                name="Roughness Scale",
                location=(520, -240),
            )
            scaled = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                scaled,
                roughness_override,
                name="Sector RoughnessScale",
                location=(720, -240),
            )
            biased = shader_nodes.math(
                nodes,
                links,
                "ADD",
                scaled,
                _float(data, profile, "RoughnessBias"),
                name="Roughness Bias",
                location=(920, -240),
                use_clamp=True,
            )
            links.new(biased, find_input(principled, "Roughness"))
            material_alpha = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                texture_alpha,
                _float(data, profile, "RoughnessMetalnessAlpha", 1.0),
                name="Roughness Metalness Influence",
                location=(900, -100),
            )
            if colorless_pass:
                preview = shader_nodes.math(
                    nodes,
                    links,
                    "MULTIPLY",
                    biased,
                    0.32,
                    name="Colorless Roughness Preview Range",
                    location=(1120, -360),
                )
                preview = shader_nodes.math(
                    nodes,
                    links,
                    "ADD",
                    preview,
                    0.18,
                    name="Colorless Roughness Preview Minimum",
                    location=(1320, -360),
                    use_clamp=True,
                )
                links.new(preview, find_input(principled, "Base Color"))
        if "metalness" in profile.features:
            metalness = _texture(
                self,
                nodes,
                links,
                data,
                profile,
                "MetalnessTexture",
                (80, -500),
                uv,
                non_color=True,
            )
            sample = (
                _red(
                    nodes,
                    links,
                    metalness.outputs["Color"],
                    "MetalnessTexture.r",
                    (320, -500),
                )
                if metalness
                else 0.0
            )
            scaled = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                sample,
                _float(data, profile, "MetalnessScale", 1.0),
                name="Metalness Scale",
                location=(520, -500),
            )
            biased = shader_nodes.math(
                nodes,
                links,
                "ADD",
                scaled,
                _float(data, profile, "MetalnessBias"),
                name="Metalness Bias",
                location=(720, -500),
                use_clamp=True,
            )
            links.new(biased, find_input(principled, "Metallic"))

        emissive_alpha = self._emission(
            data,
            profile,
            nodes,
            links,
            principled,
            uv,
            diffuse,
            gradient_position,
            texture_alpha,
            base_color,
            projection_coverage,
            decal_alpha,
            emissive_scale,
        )
        if emissive_alpha is not None and (
            {"emissive_color", "emissive_only"} & profile.features
        ):
            diffuse_alpha = emissive_alpha
        preview_alpha = shader_nodes.math(
            nodes,
            links,
            "MAXIMUM",
            diffuse_alpha,
            normal_alpha,
            name="Diffuse or Normal Alpha",
            location=(1320, 260),
        )
        preview_alpha = shader_nodes.math(
            nodes,
            links,
            "MAXIMUM",
            preview_alpha,
            material_alpha,
            name="Combined Decal Preview Alpha",
            location=(1500, 260),
        )
        links.new(preview_alpha, find_input(principled, "Alpha"))
        _set_transparent(Mat)

    def _emission(
        self,
        data,
        profile,
        nodes,
        links,
        principled,
        uv,
        diffuse,
        gradient_position,
        alpha,
        base_color,
        projection_coverage,
        decal_alpha,
        emissive_scale,
    ):
        emissive = None
        strength_mask = None
        if "emissive_color" in profile.features:
            texture = _texture(
                self, nodes, links, data, profile, "Emissive", (-320, 1020), uv
            )
            if texture:
                emissive_color = _color(data, profile, "EmissiveColor")
                emissive = mix_color_socket(
                    nodes,
                    links,
                    "Emissive x Color",
                    texture.outputs["Color"],
                    emissive_color,
                    1.0,
                    (0, 1020),
                    blend_type="MULTIPLY",
                )
                strength_mask = texture.outputs["Alpha"]
                strength_mask = shader_nodes.math(
                    nodes,
                    links,
                    "MULTIPLY",
                    strength_mask,
                    emissive_color[3],
                    name="Emissive Color Alpha",
                    location=(220, 860),
                )
        elif "emissive_only" in profile.features:
            texture = _texture(
                self,
                nodes,
                links,
                data,
                profile,
                "EmissiveMask",
                (-320, 1020),
                uv,
                non_color=True,
            )
            if texture:
                emissive = rgb_socket(
                    nodes, "Emissive White", (1.0, 1.0, 1.0, 1.0), (0, 1100)
                )
                strength_mask = _red(
                    nodes, links, texture.outputs["Color"], "EmissiveMask.r", (0, 940)
                )
        elif "emissive_gradient" in profile.features and gradient_position is not None:
            coordinate = new_labeled_node(
                nodes, "ShaderNodeCombineXYZ", "Emissive Gradient Coordinate", (40, 920)
            )
            links.new(gradient_position, coordinate.inputs["X"])
            coordinate.inputs["Y"].default_value = 0.5
            gradient = _texture(
                self,
                nodes,
                links,
                data,
                profile,
                "EmissiveGradientMap",
                (260, 920),
                coordinate.outputs["Vector"],
                non_color=True,
                extension="EXTEND",
            )
            if gradient:
                emissive = base_color
                strength_mask = _red(
                    nodes,
                    links,
                    gradient.outputs["Color"],
                    "EmissiveGradientMap.r",
                    (500, 920),
                )
        elif (
            "caustics" in profile.features
            or {"glitch", "glitch_emissive"} & profile.features
        ):
            emissive = base_color
            strength_mask = alpha
        if emissive is None:
            return None
        if strength_mask is None:
            strength_mask = 1.0
        if "emissive_gradient" not in profile.features and not (
            {"caustics", "glitch", "glitch_emissive"} & profile.features
        ):
            strength_mask = alpha_contrast_socket(
                nodes.id_data,
                strength_mask,
                _float(data, profile, "AlphaMaskContrast"),
                (760, 840),
            )
        threshold = (
            0.0
            if "emissive_gradient" in profile.features
            else _float(data, profile, "EmissiveAlphaThreshold", 0.0)
        )
        if threshold > 0.0:
            visible = shader_nodes.math(
                nodes,
                links,
                "GREATER_THAN",
                strength_mask,
                threshold,
                name="Emissive Alpha Threshold",
                location=(940, 820),
            )
            strength_mask = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                strength_mask,
                visible,
                name="Thresholded Emissive Alpha",
                location=(1120, 820),
            )
        if "emissive_gradient" in profile.features:
            strength_mask = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                strength_mask,
                alpha,
                name="Projected Gradient Emissive x Surface Alpha",
                location=(1180, 760),
            )
        elif not ({"caustics", "glitch", "glitch_emissive"} & profile.features):
            strength_mask = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                strength_mask,
                projection_coverage,
                name="Projected Emissive Coverage",
                location=(1180, 760),
            )
        emission_scale = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            strength_mask,
            decal_alpha,
            name="Sector Emissive Alpha",
            location=(1360, 760),
        )
        emission_scale = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            emission_scale,
            emissive_scale,
            name="Sector Emissive Scale",
            location=(1540, 760),
        )
        if "emissive_color" in profile.features:
            links.new(emissive, find_input(principled, "Base Color"))
        elif "emissive_only" in profile.features:
            find_input(principled, "Base Color").default_value = (0.0, 0.0, 0.0, 1.0)
        links.new(emissive, find_input(principled, "Emission Color", "Emission"))
        emissive_ev = _float(data, profile, "EmissiveEV")
        if "caustics" in profile.features:
            scaled_ev = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                emission_scale,
                emissive_ev,
                name="Caustics EmissiveEV",
                location=(980, 920),
            )
            strength = emissive_scale_bundle(
                nodes.id_data,
                1.0,
                scaled_ev,
                (1180, 920),
                "Caustics Emission",
            ).outputs["Strength"]
        else:
            strength = emissive_scale_bundle(
                nodes.id_data,
                emission_scale,
                emissive_ev,
                (980, 920),
            ).outputs["Raw Strength"]
        links.new(strength, find_input(principled, "Emission Strength"))
        return strength_mask

    def _tint3(self, data, profile, nodes, links, uv, base):
        mask = _texture(
            self,
            nodes,
            links,
            data,
            profile,
            "TintMaskTexture",
            (-1180, 1120),
            uv,
            non_color=True,
        )
        if mask is None:
            return base
        separate = new_labeled_node(
            nodes, "ShaderNodeSeparateColor", "Tint Mask RGBA", (-940, 1120)
        )
        separate.mode = "RGB"
        links.new(mask.outputs["Color"], separate.inputs["Color"])
        generated = rgb_socket(
            nodes, "Generated Tint Initial", (0.0, 0.0, 0.0, 1.0), (-700, 1320)
        )
        for index, channel in enumerate(("Red", "Green", "Blue")):
            weighted = mix_color_socket(
                nodes,
                links,
                f"Tint {channel} Contribution",
                _color(data, profile, f"MaskColor{channel[0]}"),
                separate.outputs.get(channel),
                1.0,
                (-700 + index * 220, 1120),
                blend_type="MULTIPLY",
            )
            generated = mix_color_socket(
                nodes,
                links,
                f"Generated Tint + {channel}",
                generated,
                weighted,
                1.0,
                (-500 + index * 220, 1320),
                blend_type="ADD",
            )
        tint = mix_color_socket(
            nodes,
            links,
            "Tint Mask Alpha",
            _color(data, profile, "DiffuseColor"),
            generated,
            separate.outputs.get("Alpha") or mask.outputs.get("Alpha"),
            (260, 1260),
        )
        return mix_color_socket(
            nodes,
            links,
            "Tinted Diffuse",
            base,
            tint,
            1.0,
            (500, 1260),
            blend_type="MULTIPLY",
        )

    def _thermal(self, data, profile, nodes, links, uv, alpha):
        noise = new_labeled_node(
            nodes, "ShaderNodeTexNoise", "Thermal Dither", (-760, 120)
        )
        noise.inputs["Scale"].default_value = 180.0
        links.new(uv, noise.inputs["Vector"])
        threshold = shader_nodes.math(
            nodes,
            links,
            "GREATER_THAN",
            alpha,
            noise.outputs["Fac"],
            name="Thermal Dither Threshold",
            location=(-520, 120),
        )
        return mix_scalar_socket(
            nodes,
            links,
            "Thermal Dither",
            (-300, 120),
            alpha,
            threshold,
            _float(data, profile, "DitherIntensity"),
        )

    def _glitch(self, data, profile, nodes, links, uv, base):
        noise = new_labeled_node(
            nodes, "ShaderNodeTexNoise", "Glitch Noise", (-940, 1280)
        )
        noise.inputs["Scale"].default_value = max(
            0.01, _float(data, profile, "GlitchScale", 35.0)
        )
        noise.inputs["Roughness"].default_value = 0.0
        links.new(uv, noise.inputs["Vector"])
        hue = new_labeled_node(
            nodes, "ShaderNodeHueSaturation", "Glitch Color", (-680, 1280)
        )
        hue.inputs["Hue"].default_value = (
            0.5 + _float(data, profile, "ColorChangeAmount", 0.0) * 0.05
        )
        links.new(base, hue.inputs["Color"])
        links.new(noise.outputs["Fac"], hue.inputs["Fac"])
        return hue.outputs["Color"]

    def _caustics(self, data, profile, nodes, links, uv):
        noise = new_labeled_node(
            nodes, "ShaderNodeTexVoronoi", "Caustics", (-980, 1040)
        )
        noise.distance = "EUCLIDEAN"
        noise.feature = "DISTANCE_TO_EDGE"
        noise.inputs["Scale"].default_value = max(
            0.01, _float(data, profile, "UVScaling", 8.0)
        )
        links.new(uv, noise.inputs["Vector"])
        alpha = shader_nodes.math(
            nodes,
            links,
            "SUBTRACT",
            _float(data, profile, "EdgeWidth", 0.2),
            noise.outputs.get("Distance"),
            name="Caustics Edge",
            location=(-720, 980),
        )
        alpha = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            alpha,
            _float(data, profile, "EdgeMultiplier", 5.0),
            name="Caustics Edge Multiplier",
            location=(-520, 980),
            use_clamp=True,
        )
        return rgb_socket(
            nodes, "Caustics Color", _color(data, profile, "Color"), (-520, 1160)
        ), alpha

    def _build_forward(
        self,
        data,
        material,
        profile,
        nodes,
        links,
        principled,
        uv,
        color_override,
        roughness_override,
        projection_coverage,
        decal_alpha,
        emissive_scale,
    ):
        base = _texture(
            self, nodes, links, data, profile, "BaseColor", (-1260, 620), uv
        )
        color = (
            base.outputs["Color"]
            if base
            else rgb_socket(
                nodes, "BaseColor Fallback", (1.0, 1.0, 1.0, 1.0), (-980, 620)
            )
        )
        color = mix_color_socket(
            nodes,
            links,
            "BaseColorScale",
            color,
            _color(data, profile, "BaseColorScale", (0.0, 0.0, 0.0, 0.0)),
            1.0,
            (-720, 720),
            blend_type="MULTIPLY",
        )
        color = mix_color_socket(
            nodes,
            links,
            "Sector DiffuseColorScale",
            color,
            color_override,
            1.0,
            (-460, 720),
            blend_type="MULTIPLY",
        )
        links.new(color, find_input(principled, "Base Color"))
        alpha = (
            base.outputs.get("Alpha")
            if base
            else value_socket(nodes, "Base Alpha", 1.0, (-720, 420))
        )
        alpha = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            alpha,
            _float(data, profile, "Alpha", 1.0),
            name="Forward Alpha",
            location=(-460, 420),
        )
        alpha = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            alpha,
            projection_coverage,
            name="Conformal Projection Coverage",
            location=(-340, 320),
        )
        visible = shader_nodes.math(
            nodes,
            links,
            "GREATER_THAN",
            alpha,
            _float(data, profile, "AlphaThreshold", 0.01),
            name="Forward Alpha Threshold",
            location=(-240, 420),
        )
        alpha = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            alpha,
            visible,
            name="Forward Clipped Alpha",
            location=(-20, 420),
        )
        links.new(alpha, find_input(principled, "Alpha"))
        for key, socket, default in (
            ("Roughness", "Roughness", 0.5),
            ("Metalness", "Metallic", 0.0),
        ):
            texture = _texture(
                self,
                nodes,
                links,
                data,
                profile,
                key,
                (-1260, -120 if key == "Roughness" else -360),
                uv,
                non_color=True,
            )
            sample = (
                _red(
                    nodes,
                    links,
                    texture.outputs["Color"],
                    f"{key}.r",
                    (-1000, -120 if key == "Roughness" else -360),
                )
                if texture
                else default
            )
            scale = _float(data, profile, f"{key}Scale", 1.0)
            bias = _float(data, profile, f"{key}Bias", 0.0)
            value = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                sample,
                scale,
                name=f"{key} Scale",
                location=(-760, -120 if key == "Roughness" else -360),
            )
            value = shader_nodes.math(
                nodes,
                links,
                "ADD",
                value,
                bias,
                name=f"{key} Bias",
                location=(-560, -120 if key == "Roughness" else -360),
                use_clamp=True,
            )
            if key == "Roughness":
                value = shader_nodes.math(
                    nodes,
                    links,
                    "MULTIPLY",
                    value,
                    roughness_override,
                    name="Sector RoughnessScale",
                    location=(-360, -120),
                    use_clamp=True,
                )
            links.new(value, find_input(principled, socket))
        normal = _normal(
            self,
            nodes,
            links,
            {
                **data,
                "NormalTexture": lookup_param(
                    data, "Normal", profile.defaults.get("Normal")
                ),
            },
            profile,
            uv,
        )
        if normal:
            links.new(normal, find_input(principled, "Normal"))
        links.new(color, find_input(principled, "Emission Color", "Emission"))
        emission_scale = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            visible,
            projection_coverage,
            name="Forward Emissive Coverage",
            location=(220, 680),
        )
        emission_scale = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            emission_scale,
            decal_alpha,
            name="Forward Sector Emissive Alpha",
            location=(420, 680),
        )
        emission_scale = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            emission_scale,
            emissive_scale,
            name="Forward Sector Emissive Scale",
            location=(620, 580),
        )
        emission_strength = emissive_scale_bundle(
            nodes.id_data,
            emission_scale,
            _float(data, profile, "EmissiveEV"),
            (640, 680),
            "Forward Emission",
        ).outputs["Raw Strength"]
        links.new(emission_strength, find_input(principled, "Emission Strength"))

    def _build_terrain(
        self,
        data,
        profile,
        nodes,
        links,
        principled,
        uv,
        color_override,
        roughness_override,
    ):
        base_data = {**data, "DiffuseTexture": lookup_param(data, "BaseColor")}
        base = _texture(
            self, nodes, links, base_data, profile, "DiffuseTexture", (-1260, 620), uv
        )
        color = (
            base.outputs["Color"]
            if base
            else rgb_socket(nodes, "Terrain Base", (0.5, 0.5, 0.5, 1.0), (-980, 620))
        )
        scale = param_vector(data, "BaseColorScale", (0.5, 0.5, 0.5, 0.0))
        color = mix_color_socket(
            nodes,
            links,
            "Terrain BaseColorScale",
            color,
            (scale[0], scale[1], scale[2], 1.0),
            1.0,
            (-720, 720),
            blend_type="MULTIPLY",
        )
        color = mix_color_socket(
            nodes,
            links,
            "Sector DiffuseColorScale",
            color,
            color_override,
            1.0,
            (-460, 720),
            blend_type="MULTIPLY",
        )
        links.new(color, find_input(principled, "Base Color"))
        rough_data = {**data, "RoughnessTexture": lookup_param(data, "Roughness")}
        rough = _texture(
            self,
            nodes,
            links,
            rough_data,
            profile,
            "RoughnessTexture",
            (-1260, -140),
            uv,
            non_color=True,
        )
        if rough:
            value = _red(
                nodes, links, rough.outputs["Color"], "Terrain Roughness", (-1000, -140)
            )
            value = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                value,
                roughness_override,
                name="Sector RoughnessScale",
                location=(-760, -140),
                use_clamp=True,
            )
            links.new(value, find_input(principled, "Roughness"))

        mask_data = {
            **data,
            "MaskTexture": lookup_param(
                data,
                "AlphaMask",
                profile.defaults.get("AlphaMask"),
            ),
        }
        mask = _texture(
            self,
            nodes,
            links,
            mask_data,
            profile,
            "MaskTexture",
            (-1260, -420),
            uv,
            non_color=True,
        )
        if mask is None:
            return value_socket(
                nodes, "Terrain Decal Alpha Fallback", 0.0, (1260, -420)
            )

        alpha = _red(
            nodes, links, mask.outputs["Color"], "Terrain AlphaMask.r", (-1000, -420)
        )
        black = _float(data, profile, "AlphaMaskBlackPoint", 0.0)
        white = _float(data, profile, "AlphaMaskWhitePoint", 1.0)
        span = white - black
        if abs(span) <= 1.0e-8:
            return shader_nodes.math(
                nodes,
                links,
                "GREATER_THAN",
                alpha,
                black,
                name="Terrain AlphaMask Degenerate Levels",
                location=(-760, -420),
            )
        alpha = shader_nodes.math(
            nodes,
            links,
            "SUBTRACT",
            alpha,
            black,
            name="Terrain AlphaMask Black Point",
            location=(-760, -420),
        )
        return shader_nodes.math(
            nodes,
            links,
            "DIVIDE",
            alpha,
            span,
            name="Terrain AlphaMask Levels",
            location=(-540, -420),
            use_clamp=True,
        )


class MeshDecal(MaterialTypeBase):
    def create(self, Data, Mat):
        data = Data if isinstance(Data, dict) else {}
        material_template = backslash_depot_key(Mat.get("MaterialTemplate"))
        profile = mesh_profile(material_template)
        if profile is None:
            raise ValueError(
                f"No mesh decal profile for {Mat.get('MaterialTemplate', '')}"
            )
        _store_profile(Mat, profile)
        if "vehicle" in profile.features:
            Mat["cp77_vehicle_decal_dirt_version"] = DIRT_VERSION
        rnm_enabled = _float(data, profile, "NormalsBlendingMode") > 0.5
        Mat["normalBlendingMode"] = int(rnm_enabled)
        rnm_alpha_texture = (
            rnm_enabled
            and "vehicle" not in profile.features
            and "NormalsBlendingModeAlpha" in contract_records(material_template)
        )
        tree, output, principled = _new_graph(Mat, profile.name)
        nodes, links = tree.nodes, tree.links
        color_override, roughness_override, _decal_alpha, _emissive_scale = (
            _instance_overrides(nodes)
        )
        if {"emissive_subsurface", "vehicle"} & profile.features:
            uv = new_labeled_node(nodes, "ShaderNodeUVMap", "UV", (-2800, 220)).outputs[
                "UV"
            ]
        else:
            uv = _mesh_uv(nodes, links, data, profile)
        uv, _ = _parallax_uv(self, nodes, links, data, profile, uv)
        channel_uv = uv

        if "emissive_subsurface" in profile.features:
            self._emissive_subsurface(data, Mat, profile, nodes, links, principled, uv)
            _displacement(
                nodes, links, output, _float(data, profile, "VertexOffsetFactor")
            )
            _set_transparent(Mat)
            return
        if "emissive" in profile.features:
            self._emissive(
                data, Mat, profile, nodes, links, principled, uv, color_override
            )
            _displacement(
                nodes, links, output, _float(data, profile, "VertexOffsetFactor")
            )
            _set_transparent(Mat)
            return

        diffuse = _texture(
            self,
            nodes,
            links,
            data,
            profile,
            "DiffuseTexture",
            (-1180, 660),
            uv,
            non_color="gradient" in profile.features,
        )
        base = (
            diffuse.outputs["Color"]
            if diffuse
            else rgb_socket(
                nodes, "Diffuse Fallback", (0.0, 0.0, 0.0, 1.0), (-900, 660)
            )
        )
        double_diffuse_alpha_recovery = None
        if diffuse is not None and "double_diffuse" in profile.features:
            diffuse_image = getattr(diffuse, "image", None)
            if diffuse_image is not None and image_has_alpha(diffuse_image):
                texture_alpha = _texture_alpha(diffuse)
            else:
                double_diffuse_alpha_recovery = shader_nodes.math(
                    nodes,
                    links,
                    "MULTIPLY",
                    name="Double Diffuse Primary Alpha Recovery",
                    location=(-900, 460),
                ).node
                double_diffuse_alpha_recovery.inputs["Value"].default_value = 0.0
                shader_nodes.socket_by_identifier(
                    double_diffuse_alpha_recovery.inputs, "Value_001"
                ).default_value = 1.0
                texture_alpha = double_diffuse_alpha_recovery.outputs["Value"]
        else:
            texture_alpha = (
                _decal_texture_opacity(diffuse)
                if diffuse
                else value_socket(nodes, "Diffuse Alpha Fallback", 0.0, (-900, 460))
            )
        raw_diffuse_alpha = texture_alpha
        plain_mesh_decal = material_template == _PLAIN_MESH_DECAL_TEMPLATE
        mesh_decal_parallax = material_template == _MESH_DECAL_PARALLAX_TEMPLATE
        plain_vehicle_mesh = material_template == _PLAIN_VEHICLE_MESH_TEMPLATE
        diffuse_color_value = _color(data, profile, "DiffuseColor")
        diffuse_alpha_value = _float(data, profile, "DiffuseAlpha")
        material_alpha_value = _float(data, profile, "RoughnessMetalnessAlpha")
        gradient_position = None
        gradient_alpha = None
        if "gradient" in profile.features and diffuse:
            base, gradient_position, gradient_alpha = _gradient_color(
                self,
                nodes,
                links,
                data,
                profile,
                diffuse,
                (-840, 680),
            )
            texture_alpha = gradient_alpha
        if "vehicle" in profile.features and diffuse:
            raw_diffuse_alpha = _texture_alpha(diffuse)
            texture_alpha = raw_diffuse_alpha
            use_gradient = clamp01(_float(data, profile, "UseGradientMap"))
            if use_gradient > 1.0e-8:
                gradient = _texture(
                    self,
                    nodes,
                    links,
                    data,
                    profile,
                    "GradientMap",
                    (-840, 920),
                    uv,
                    extension="EXTEND",
                )
                if gradient:
                    position = _red(
                        nodes,
                        links,
                        diffuse.outputs["Color"],
                        "Vehicle Gradient Position",
                        (-1080, 1080),
                    )
                    coordinate = new_labeled_node(
                        nodes,
                        "ShaderNodeCombineXYZ",
                        "Vehicle Gradient Coordinate",
                        (-860, 1080),
                    )
                    links.new(position, coordinate.inputs["X"])
                    coordinate.inputs["Y"].default_value = 0.5
                    links.new(
                        coordinate.outputs["Vector"], find_input(gradient, "Vector")
                    )
                    base = mix_color_socket(
                        nodes,
                        links,
                        "Use Vehicle Gradient",
                        base,
                        gradient.outputs["Color"],
                        use_gradient,
                        (-120, 920),
                    )
                    gradient_coverage = gradient.outputs["Alpha"]
                    vehicle_mask = _texture(
                        self,
                        nodes,
                        links,
                        data,
                        profile,
                        "MaskTexture",
                        (-840, 700),
                        channel_uv,
                        non_color=True,
                    )
                    if vehicle_mask is not None:
                        vehicle_mask_red = _red(
                            nodes,
                            links,
                            vehicle_mask.outputs["Color"],
                            "Vehicle MaskTexture.r",
                            (-820, 600),
                        )
                        gradient_coverage = shader_nodes.math(
                            nodes,
                            links,
                            "MULTIPLY",
                            gradient_coverage,
                            vehicle_mask_red,
                            name="Vehicle Gradient Alpha x Mask",
                            location=(-600, 700),
                        )
                    texture_alpha = mix_scalar_socket(
                        nodes,
                        links,
                        "Use Vehicle Gradient Alpha",
                        (-360, 600),
                        raw_diffuse_alpha,
                        gradient_coverage,
                        use_gradient,
                    )
            texture_alpha = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                texture_alpha,
                diffuse_color_value[3],
                name="Vehicle DiffuseColor Alpha",
                location=(-120, 520),
            )
            texture_alpha = build_vehicle_dirt_alpha(
                self, nodes.id_data, data, profile.defaults, texture_alpha
            )

        mask = None
        if "vehicle" not in profile.features:
            mask = _texture(
                self,
                nodes,
                links,
                data,
                profile,
                "MaskTexture",
                (-1180, 380),
                channel_uv,
                non_color=True,
            )
        if mask is not None:
            mask_red = _red(
                nodes,
                links,
                mask.outputs["Color"],
                "MaskTexture.r",
                (-980, 300),
            )
            if "gradient" in profile.features and gradient_alpha is not None:
                texture_alpha = shader_nodes.math(
                    nodes,
                    links,
                    "MULTIPLY",
                    gradient_alpha,
                    mask_red,
                    name="MaskTexture.r x GradientMap.a",
                    location=(-760, 380),
                )
            else:
                diffuse_mask_alpha = (
                    diffuse.outputs["Alpha"]
                    if diffuse is not None
                    else value_socket(
                        nodes,
                        "Diffuse Mask Alpha Fallback",
                        1.0,
                        (-980, 240),
                    )
                )
                texture_alpha = shader_nodes.math(
                    nodes,
                    links,
                    "MULTIPLY",
                    diffuse_mask_alpha,
                    mask_red,
                    name="MaskTexture.r x Diffuse Alpha",
                    location=(-760, 380),
                )
        base = mix_color_socket(
            nodes,
            links,
            "DiffuseColor",
            base,
            diffuse_color_value,
            1.0,
            (-560, 740),
            blend_type="MULTIPLY",
        )
        if "multitint" in profile.features:
            base = self._multitint(data, profile, nodes, links, uv, base)
        alpha_precontrasted = False
        if "double_diffuse" in profile.features:
            base, texture_alpha = self._double_diffuse(
                data, profile, nodes, links, uv, base, texture_alpha
            )
            alpha_precontrasted = True

        if "gradient" in profile.features and not alpha_precontrasted:
            texture_alpha = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                texture_alpha,
                diffuse_alpha_value,
                name="Gradient DiffuseAlpha Before Contrast",
                location=(-760, 480),
            )

        if alpha_precontrasted or "vehicle" in profile.features:
            alpha = texture_alpha
        else:
            alpha = alpha_contrast_socket(
                nodes.id_data,
                texture_alpha,
                _float(data, profile, "AlphaMaskContrast"),
                (-560, 420),
            )
        secondary_influence = _float(data, profile, "SecondaryMaskInfluence")
        if abs(secondary_influence) <= 1.0e-8:
            # Vehicle decals have no secondary mask; their alpha is the diffuse alpha as sampled.
            if not {"gradient", "vehicle"} & profile.features:
                alpha = shader_nodes.math(
                    nodes,
                    links,
                    "MULTIPLY",
                    alpha,
                    alpha,
                    name="Secondary Alpha Base",
                    location=(-120, 200),
                )
        else:
            secondary_scale = _float(data, profile, "SecondaryMaskUVScale", 1.0)
            if abs(secondary_scale - 1.0) <= 1.0e-8:
                secondary_uv = channel_uv
            else:
                secondary_uv = shader_nodes.vector_math(
                    nodes,
                    links,
                    "MULTIPLY",
                    channel_uv,
                    (secondary_scale, secondary_scale, 1.0),
                    name="Secondary Mask UV Scale",
                    location=(-1420, 200),
                )
            secondary = _texture(
                self,
                nodes,
                links,
                data,
                profile,
                "SecondaryMask",
                (-1180, 200),
                secondary_uv,
                non_color=True,
            )
            if secondary:
                secondary_mask = _red(
                    nodes,
                    links,
                    secondary.outputs["Color"],
                    "SecondaryMask.r",
                    (-940, 200),
                )
                if "gradient" in profile.features:
                    multiplier = mix_scalar_socket(
                        nodes,
                        links,
                        "Gradient Secondary Mask",
                        (-520, 200),
                        1.0,
                        secondary_mask,
                        secondary_influence,
                    )
                    alpha = shader_nodes.math(
                        nodes,
                        links,
                        "MULTIPLY",
                        alpha,
                        multiplier,
                        name="Gradient Secondary Masked Alpha",
                        location=(-300, 200),
                    )
                else:
                    influenced = shader_nodes.math(
                        nodes,
                        links,
                        "MULTIPLY",
                        secondary_mask,
                        secondary_influence,
                        name="Secondary Mask Influence",
                        location=(-720, 200),
                    )
                    inverse = shader_nodes.math(
                        nodes,
                        links,
                        "SUBTRACT",
                        1.0,
                        influenced,
                        name="One Minus Secondary Mask",
                        location=(-520, 200),
                    )
                    secondary_alpha = shader_nodes.math(
                        nodes,
                        links,
                        "MULTIPLY",
                        alpha,
                        inverse,
                        name="Secondary Alpha Lerp",
                        location=(-320, 200),
                    )
                    alpha = shader_nodes.math(
                        nodes,
                        links,
                        "MULTIPLY",
                        alpha,
                        secondary_alpha,
                        name="Secondary Masked Alpha",
                        location=(-120, 200),
                    )

        growth_mask = None
        if "revealed" in profile.features:
            flow = _texture(
                self,
                nodes,
                links,
                data,
                profile,
                "FlowTexture",
                (-520, 40),
                uv,
                non_color=True,
            )
            if flow:
                flow_alpha = _red(
                    nodes, links, flow.outputs["Color"], "FlowTexture.r", (-500, -40)
                )
                growth_time = material_property_socket(
                    nodes, Mat, "cp77_MaterialParam0", 1.0, (-500, -180)
                )
                growth = shader_nodes.math(
                    nodes,
                    links,
                    "SUBTRACT",
                    growth_time,
                    flow_alpha,
                    name="Reveal Growth - Flow",
                    location=(-260, -80),
                )
                growth = shader_nodes.math(
                    nodes,
                    links,
                    "DIVIDE",
                    growth,
                    0.05,
                    name="Reveal Growth Width",
                    location=(-60, -80),
                    use_clamp=True,
                )
                growth = shader_nodes.math(
                    nodes,
                    links,
                    "SUBTRACT",
                    growth,
                    0.5,
                    name="Reveal Contrast Center",
                    location=(140, -80),
                )
                growth = shader_nodes.math(
                    nodes,
                    links,
                    "MULTIPLY",
                    growth,
                    10.0,
                    name="Reveal Contrast",
                    location=(340, -80),
                )
                growth = shader_nodes.math(
                    nodes,
                    links,
                    "ADD",
                    growth,
                    0.5,
                    name="Reveal Growth Mask",
                    location=(540, -80),
                    use_clamp=True,
                )
                alpha = shader_nodes.math(
                    nodes,
                    links,
                    "MULTIPLY",
                    alpha,
                    growth,
                    name="Revealed Flow",
                    location=(740, -80),
                )
                growth_mask = growth
        if "morph" in profile.features:
            morph_alpha = mix_scalar_socket(
                nodes,
                links,
                "Morph Alpha",
                (520, -160),
                _float(data, profile, "StartAlpha"),
                _float(data, profile, "FinalAlpha", 1.0),
                clamp01(_float(data, profile, "Morph", 1.0)),
            )
            alpha = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                alpha,
                morph_alpha,
                name="Morphed Decal Alpha",
                location=(740, -160),
            )

        color = mix_color_socket(
            nodes,
            links,
            "Sector DiffuseColorScale",
            base,
            color_override,
            1.0,
            (700, 720),
            blend_type="MULTIPLY",
        )
        links.new(color, find_input(principled, "Base Color"))
        if "gradient" in profile.features:
            diffuse_alpha = alpha
        else:
            diffuse_alpha = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                alpha,
                diffuse_alpha_value,
                name="DiffuseAlpha",
                location=(700, 440),
            )
        reveal_visible = None
        if growth_mask is not None:
            reveal_clip_alpha = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                growth_mask,
                diffuse_alpha_value,
                name="Reveal Clip Alpha",
                location=(700, 340),
            )
            reveal_visible = shader_nodes.math(
                nodes,
                links,
                "GREATER_THAN",
                reveal_clip_alpha,
                0.005,
                name="Reveal Alpha Threshold",
                location=(900, 340),
            )
            diffuse_alpha = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                diffuse_alpha,
                reveal_visible,
                name="Clipped Revealed Diffuse",
                location=(1100, 440),
            )

        normal_alpha = value_socket(nodes, "No Normal Influence", 0.0, (700, 80))
        if "normal" in profile.features:
            if "gradient" in profile.features:
                normal_alpha = alpha
            elif "vehicle" in profile.features:
                normal_alpha = texture_alpha
            else:
                normal_alpha = raw_diffuse_alpha
            if growth_mask is not None:
                normal_alpha = shader_nodes.math(
                    nodes,
                    links,
                    "MULTIPLY",
                    normal_alpha,
                    growth_mask,
                    name="Revealed Normal Growth",
                    location=(500, 180),
                )
            if "wet" in profile.features:
                diminish = material_property_socket(
                    nodes, Mat, "cp77_MaterialParam0", 0.0, (100, 140)
                )
                diminish = shader_nodes.math(
                    nodes,
                    links,
                    "SUBTRACT",
                    1.0,
                    diminish,
                    name="Wet Normal Diminish",
                    location=(300, 140),
                    use_clamp=True,
                )
                normal_alpha = shader_nodes.math(
                    nodes,
                    links,
                    "MULTIPLY",
                    normal_alpha,
                    diminish,
                    name="Wet Normal Alpha",
                    location=(500, 140),
                )
            if (
                "gradient" not in profile.features
                and "vehicle" not in profile.features
                and _float(data, profile, "UseNormalAlphaTex") >= 0.5
            ):
                normal_alpha_tex = _texture(
                    self,
                    nodes,
                    links,
                    data,
                    profile,
                    "NormalAlphaTex",
                    (80, 40),
                    channel_uv,
                    non_color=True,
                )
                if normal_alpha_tex:
                    normal_alpha = _red(
                        nodes,
                        links,
                        normal_alpha_tex.outputs["Color"],
                        "NormalAlphaTex.r",
                        (320, 40),
                    )
            normal = _normal(
                self,
                nodes,
                links,
                data,
                profile,
                channel_uv,
                (520, -40),
                rnm_alpha_texture=rnm_alpha_texture,
            )
            if normal:
                links.new(normal, find_input(principled, "Normal"))
            rnm_detail_coverage = None
            if rnm_enabled:
                decoder = nodes.get("NormalTexture DirectX Decode")
                if decoder is not None:
                    rnm_detail_coverage = _rnm_normal_detail_coverage(
                        nodes,
                        links,
                        decoder,
                        (700, -180),
                    )
                    normal_alpha = shader_nodes.math(
                        nodes,
                        links,
                        "MULTIPLY",
                        normal_alpha,
                        rnm_detail_coverage,
                        name="RNM Normal Alpha Detail",
                        location=(920, 20),
                    )
            if double_diffuse_alpha_recovery is not None:
                recovery = rnm_detail_coverage
                if recovery is None:
                    recovery_texture = nodes.get("NormalTexture")
                    if (
                        recovery_texture is not None
                        and recovery_texture.type == "TEX_IMAGE"
                    ):
                        recovery = _normal_detail_coverage(
                            nodes,
                            links,
                            recovery_texture,
                            (820, -120),
                        )
                if recovery is not None:
                    links.new(recovery, double_diffuse_alpha_recovery.inputs["Value"])
            normal_alpha = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                normal_alpha,
                _float(data, profile, "NormalAlpha"),
                name="NormalAlpha",
                location=(1140, 80),
            )
            normal_alpha.node.name = "Normal Influence"
            normal_alpha.node.label = "Normal Influence"
            if reveal_visible is not None:
                normal_alpha = shader_nodes.math(
                    nodes,
                    links,
                    "MULTIPLY",
                    normal_alpha,
                    reveal_visible,
                    name="Clipped Revealed Normal",
                    location=(900, 80),
                )
            if mesh_decal_parallax and normal is not None:
                strength_input = find_input(normal.node, "Strength")
                if strength_input is not None:
                    replace_link(links, normal_alpha, strength_input)

        material_channels_active = (
            not mesh_decal_parallax or abs(material_alpha_value) > 1.0e-8
        )
        if "roughness" in profile.features and material_channels_active:
            roughness = _texture(
                self,
                nodes,
                links,
                data,
                profile,
                "RoughnessTexture",
                (80, -280),
                channel_uv,
                non_color=True,
            )
            rough_sample = (
                _red(
                    nodes,
                    links,
                    roughness.outputs["Color"],
                    "RoughnessTexture.r",
                    (320, -280),
                )
                if roughness
                else 0.5
            )
            rough = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                rough_sample,
                _float(data, profile, "RoughnessScale", 1.0),
                name="Roughness Scale",
                location=(520, -280),
            )
            rough = shader_nodes.math(
                nodes,
                links,
                "ADD",
                rough,
                _float(data, profile, "RoughnessBias"),
                name="Roughness Bias",
                location=(720, -280),
                use_clamp=True,
            )
            rough = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                rough,
                roughness_override,
                name="Sector RoughnessScale",
                location=(920, -280),
                use_clamp=True,
            )
            links.new(rough, find_input(principled, "Roughness"))
        if "metalness" in profile.features and material_channels_active:
            metalness = _texture(
                self,
                nodes,
                links,
                data,
                profile,
                "MetalnessTexture",
                (80, -520),
                channel_uv,
                non_color=True,
            )
            metal_sample = (
                _red(
                    nodes,
                    links,
                    metalness.outputs["Color"],
                    "MetalnessTexture.r",
                    (320, -520),
                )
                if metalness
                else 0.0
            )
            metal = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                metal_sample,
                _float(data, profile, "MetalnessScale", 1.0),
                name="Metalness Scale",
                location=(520, -520),
            )
            metal = shader_nodes.math(
                nodes,
                links,
                "ADD",
                metal,
                _float(data, profile, "MetalnessBias"),
                name="Metalness Bias",
                location=(720, -520),
                use_clamp=True,
            )
            links.new(metal, find_input(principled, "Metallic"))

        material_alpha = 0.0
        if ({"roughness", "metalness"} & profile.features) and material_channels_active:
            material_alpha = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                alpha,
                material_alpha_value,
                name="Roughness Metalness Alpha",
                location=(920, 0),
            )
            if reveal_visible is not None:
                material_alpha = shader_nodes.math(
                    nodes,
                    links,
                    "MULTIPLY",
                    material_alpha,
                    reveal_visible,
                    name="Clipped Revealed Material",
                    location=(1120, 0),
                )
        if "wet" in profile.features:
            material_alpha = alpha
        preview_alpha = shader_nodes.math(
            nodes,
            links,
            "MAXIMUM",
            diffuse_alpha,
            normal_alpha,
            name="Diffuse or Normal Alpha",
            location=(1160, 260),
        )
        double_diffuse_preview = "double_diffuse" in profile.features
        conservative_preview = plain_mesh_decal or plain_vehicle_mesh
        if mesh_decal_parallax or double_diffuse_preview:
            preview_alpha = diffuse_alpha
        elif conservative_preview:
            if abs(diffuse_alpha_value) <= 1.0e-8:
                normal_texture = nodes.get("NormalTexture")
                if normal_texture is not None:
                    normal_coverage = _normal_detail_coverage(
                        nodes,
                        links,
                        normal_texture,
                        (1060, 20),
                    )
                    coverage_label = (
                        "Plain Vehicle Normal Coverage"
                        if plain_vehicle_mesh
                        else "Mesh Decal Normal Coverage"
                    )
                    preview_alpha = shader_nodes.math(
                        nodes,
                        links,
                        "MULTIPLY",
                        preview_alpha,
                        normal_coverage,
                        name=coverage_label,
                        location=(1360, 180),
                    )
        else:
            preview_alpha = shader_nodes.math(
                nodes,
                links,
                "MAXIMUM",
                preview_alpha,
                material_alpha,
                name="Combined Decal Preview Alpha",
                location=(1360, 260),
            )
        links.new(preview_alpha, find_input(principled, "Alpha"))

        if "emissive_gradient" in profile.features and gradient_position is not None:
            coordinate = new_labeled_node(
                nodes,
                "ShaderNodeCombineXYZ",
                "Emissive Gradient Coordinate",
                (480, 1040),
            )
            links.new(gradient_position, coordinate.inputs["X"])
            coordinate.inputs["Y"].default_value = 0.5
            gradient = _texture(
                self,
                nodes,
                links,
                data,
                profile,
                "EmissiveGradientMap",
                (700, 1040),
                coordinate.outputs["Vector"],
                non_color=True,
                extension="EXTEND",
            )
            if gradient:
                links.new(color, find_input(principled, "Emission Color", "Emission"))
                mask = _red(
                    nodes,
                    links,
                    gradient.outputs["Color"],
                    "EmissiveGradientMap.r",
                    (940, 1040),
                )
                emissive_contrast = max(
                    -1.0,
                    min(1.0, _float(data, profile, "AlphaMaskContrast")),
                )
                exponent = math.tan(
                    -emissive_contrast * math.pi * 0.25 + math.pi * 0.25
                )
                mask = shader_nodes.math(
                    nodes,
                    links,
                    "POWER",
                    mask,
                    exponent,
                    name="Emissive Inverse Alpha Contrast",
                    location=(1120, 940),
                )
                scaled_ev = emissive_scale_bundle(
                    nodes.id_data,
                    mask,
                    _float(data, profile, "EmissiveEV"),
                    (1180, 1040),
                    "Scaled Emissive EV",
                ).outputs["Scaled EV"]
                output_ev = shader_nodes.math(
                    nodes,
                    links,
                    "MULTIPLY",
                    scaled_ev,
                    alpha,
                    name="Emissive EV x Surface Alpha",
                    location=(1740, 1040),
                )
                strength = emissive_scale_bundle(
                    nodes.id_data,
                    1.0,
                    output_ev,
                    (1940, 1040),
                    "Mesh Gradient Emission",
                ).outputs["Strength"]
                links.new(strength, find_input(principled, "Emission Strength"))

        _displacement(nodes, links, output, _float(data, profile, "VertexOffsetFactor"))
        _set_transparent(Mat)

    def _multitint(self, data, profile, nodes, links, uv, base):
        mask = _texture(
            self,
            nodes,
            links,
            data,
            profile,
            "TintMaskTexture",
            (-980, 1260),
            uv,
            non_color=True,
        )
        if mask is None:
            return base
        tint_mask = _red(
            nodes, links, mask.outputs["Color"], "TintMaskTexture.r", (-740, 1260)
        )
        vertex = new_labeled_node(
            nodes, "ShaderNodeVertexColor", "Tint Index Vertex Color", (-980, 1480)
        )
        vertex_index = _red(
            nodes, links, vertex.outputs["Color"], "Vertex Color.r", (-740, 1480)
        )
        tint_color = _color(data, profile, "TintColor0")
        selected = rgb_socket(nodes, "TintColor0", tint_color, (-500, 1480))
        selected_alpha = value_socket(
            nodes, "TintColor0 Alpha", tint_color[3], (-500, 1360)
        )
        for index in range(1, 8):
            threshold = shader_nodes.math(
                nodes,
                links,
                "GREATER_THAN",
                vertex_index,
                index / 8.0 - 1.0e-7,
                name=f"Tint Index >= {index}",
                location=(-500 + index * 90, 1580 - index * 60),
            )
            tint_color = _color(data, profile, f"TintColor{index}")
            selected = mix_color_socket(
                nodes,
                links,
                f"TintColor{index}",
                selected,
                tint_color,
                threshold,
                (-280 + index * 120, 1480 - index * 40),
            )
            selected_alpha = mix_scalar_socket(
                nodes,
                links,
                f"TintColor{index} Alpha",
                (-280 + index * 120, 1340 - index * 40),
                selected_alpha,
                tint_color[3],
                threshold,
            )
        tint_factor = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            tint_mask,
            selected_alpha,
            name="Tint Alpha x Mask",
            location=(740, 1260),
        )
        decal_tint = mix_color_socket(
            nodes,
            links,
            "Vertex Selected Tint",
            (1.0, 1.0, 1.0, 1.0),
            selected,
            tint_factor,
            (960, 1300),
        )
        return mix_color_socket(
            nodes,
            links,
            "Diffuse x Vertex Tint",
            base,
            decal_tint,
            1.0,
            (1180, 1300),
            blend_type="MULTIPLY",
        )

    def _double_diffuse(self, data, profile, nodes, links, uv, base, alpha):
        secondary_path = _resolved_texture_path(data, profile, "SecondaryDiffuseAlpha")
        secondary = _texture(
            self,
            nodes,
            links,
            data,
            profile,
            "SecondaryDiffuseAlpha",
            (-980, 1040),
            uv,
            non_color=True,
        )
        if secondary is None:
            return base, alpha_contrast_socket(
                nodes.id_data,
                alpha,
                _float(data, profile, "AlphaMaskContrast"),
                (-520, 1040),
            )
        default_secondary_path = profile.defaults.get("SecondaryDiffuseAlpha")
        secondary_alpha = _secondary_diffuse_alpha_socket(
            nodes,
            links,
            secondary,
            secondary_path,
            default_secondary_path if isinstance(default_secondary_path, str) else None,
            (-740, 1040),
        )
        secondary_alpha = alpha_contrast_socket(
            nodes.id_data,
            secondary_alpha,
            _float(data, profile, "AlphaMaskContrast"),
            (-520, 1040),
        )
        influence = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            secondary_alpha,
            _float(data, profile, "SecondaryDiffuseAlphaIntensity"),
            name="Secondary Diffuse Influence",
            location=(-300, 1040),
        )
        remaining_color = shader_nodes.math(
            nodes,
            links,
            "SUBTRACT",
            1.0,
            alpha,
            name="One Minus Primary Texture Alpha",
            location=(-300, 900),
        )
        color_influence = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            influence,
            remaining_color,
            name="Secondary Diffuse Color Influence",
            location=(-60, 1040),
        )
        secondary_color = mix_color_socket(
            nodes,
            links,
            "Secondary Diffuse Contribution",
            _color(data, profile, "SecondaryDiffuseColor"),
            color_influence,
            1.0,
            (180, 1040),
            blend_type="MULTIPLY",
        )
        color = mix_color_socket(
            nodes,
            links,
            "Double Diffuse Color",
            base,
            secondary_color,
            1.0,
            (420, 1040),
            blend_type="ADD",
        )
        primary_alpha = alpha_contrast_socket(
            nodes.id_data,
            alpha,
            _float(data, profile, "AlphaMaskContrast"),
            (-300, 820),
        )
        remaining_alpha = shader_nodes.math(
            nodes,
            links,
            "SUBTRACT",
            1.0,
            primary_alpha,
            name="One Minus Primary Alpha",
            location=(-60, 820),
        )
        merged_alpha = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            remaining_alpha,
            influence,
            name="Secondary Alpha Remainder",
            location=(180, 820),
        )
        merged_alpha = shader_nodes.math(
            nodes,
            links,
            "ADD",
            primary_alpha,
            merged_alpha,
            name="Double Diffuse Alpha",
            location=(420, 820),
            use_clamp=True,
        )
        return color, merged_alpha

    def _emissive(
        self, data, material, profile, nodes, links, principled, uv, color_override
    ):
        time = scene_time_socket(nodes, (-1420, 1120), "Emissive Scene Time")
        emissive_uv = uv
        primary = _color(data, profile, "DiffuseColor")
        alternate = _color(data, profile, "DiffuseColor2", (0.0, 0.0, 0.0, 0.0))
        preview = _float(data, profile, "Preview2ndState")
        enabled = _float(data, profile, "EnableAlternateColor")
        material_param = material_property_socket(
            nodes, material, "cp77_MaterialParam0", 1.0, (-1060, 1020)
        )
        uv_components = new_labeled_node(
            nodes, "ShaderNodeSeparateXYZ", "Emissive UV", (-840, 1020)
        )
        transition_uv = nodes.get("Signed Wrapped UV")
        links.new(
            transition_uv.outputs["Value"] if transition_uv is not None else uv,
            uv_components.inputs["Vector"],
        )
        transition = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            material_param,
            2.0,
            name="MaterialParam0 x 2",
            location=(-620, 1080),
        )
        transition = shader_nodes.math(
            nodes,
            links,
            "SUBTRACT",
            transition,
            uv_components.outputs["X"],
            name="Transition Across U",
            location=(-420, 1080),
            use_clamp=True,
        )
        transition = shader_nodes.math(
            nodes,
            links,
            "SUBTRACT",
            transition,
            0.5,
            name="Transition Center",
            location=(-220, 1080),
        )
        transition = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            transition,
            4.5,
            name="Transition Contrast",
            location=(-20, 1080),
        )
        transition = shader_nodes.math(
            nodes,
            links,
            "ADD",
            transition,
            0.5,
            name="Transition Factor",
            location=(180, 1080),
            use_clamp=True,
        )
        if _float(data, profile, "EnableAlternateUVcoord") >= 0.99:
            alternate_row = shader_nodes.math(
                nodes,
                links,
                "GREATER_THAN",
                transition,
                0.5,
                name="Alternate UV Row",
                location=(380, 1160),
            )
            alternate_row = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                alternate_row,
                0.5,
                name="Alternate UV Offset",
                location=(580, 1160),
            )
            uv_offset = new_labeled_node(
                nodes, "ShaderNodeCombineXYZ", "Alternate UV Offset", (780, 1160)
            )
            links.new(alternate_row, uv_offset.inputs["Y"])
            emissive_uv = shader_nodes.vector_math(
                nodes,
                links,
                "ADD",
                emissive_uv,
                uv_offset.outputs["Vector"],
                name="Alternate Emissive UV",
                location=(980, 1160),
            )
        preview_offset = _float(data, profile, "Preview2ndState") * 0.5
        emissive_uv = shader_nodes.vector_math(
            nodes,
            links,
            "ADD",
            emissive_uv,
            (preview_offset, preview_offset, 0.0),
            name="Preview State UV",
            location=(1180, 1160),
        )
        emissive_uv = shader_nodes.vector_math(
            nodes,
            links,
            "MULTIPLY",
            emissive_uv,
            (_float(data, profile, "LayerTile", 1.0),) * 2 + (1.0,),
            name="Layer Tile",
            location=(1380, 1160),
        )
        texture = _texture(
            self,
            nodes,
            links,
            data,
            profile,
            "DiffuseTexture",
            (-1080, 640),
            emissive_uv,
        )
        color = (
            texture.outputs["Color"]
            if texture
            else rgb_socket(
                nodes, "Emissive Fallback", (0.0, 0.0, 0.0, 1.0), (-820, 640)
            )
        )
        selected = mix_color_socket(
            nodes,
            links,
            "Preview Alternate Color",
            primary,
            alternate,
            preview,
            (-820, 880),
        )
        runtime = mix_color_socket(
            nodes, links, "Alternate Color", selected, alternate, enabled, (-600, 880)
        )
        runtime = mix_color_socket(
            nodes,
            links,
            "Runtime Color Transition",
            selected,
            runtime,
            transition,
            (-380, 880),
        )
        color = mix_color_socket(
            nodes,
            links,
            "Emissive Texture x Color",
            color,
            runtime,
            1.0,
            (-560, 640),
            blend_type="MULTIPLY",
        )
        color = mix_color_socket(
            nodes,
            links,
            "Sector DiffuseColorScale",
            color,
            color_override,
            1.0,
            (-300, 640),
            blend_type="MULTIPLY",
        )
        links.new(color, find_input(principled, "Base Color"))
        links.new(color, find_input(principled, "Emission Color", "Emission"))
        alpha = (
            (texture.outputs["Alpha"])
            if texture
            else value_socket(nodes, "Emissive Alpha", 0.0, (-560, 420))
        )
        phase = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            time,
            _float(data, profile, "AnimationSpeed", 1.0),
            name="Emissive Animation Phase",
            location=(-820, 300),
        )
        frame_count = max(
            1, int(_float(data, profile, "AnimationFramesWidth", 1.0))
        ) * max(1, int(_float(data, profile, "AnimationFramesHeight", 1.0)))
        phase = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            phase,
            frame_count,
            name="Emissive Animation Frame Phase",
            location=(-720, 300),
        )
        phase = shader_nodes.math(
            nodes,
            links,
            "FRACT",
            phase,
            name="Emissive Animation Fraction",
            location=(-620, 300),
        )
        inverse = shader_nodes.math(
            nodes,
            links,
            "SUBTRACT",
            1.0,
            phase,
            name="One Minus Emissive Phase",
            location=(-420, 300),
        )
        visibility = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            phase,
            inverse,
            name="Emissive Triangle Wave",
            location=(-220, 300),
        )
        visibility = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            visibility,
            4.0 * _float(data, profile, "FullVisibilityFactor", 1.0),
            name="Emissive Full Visibility",
            location=(-20, 300),
            use_clamp=True,
        )
        visibility = mix_scalar_socket(
            nodes,
            links,
            "Hard or Soft Transition",
            (180, 300),
            1.0,
            visibility,
            _float(data, profile, "HardOrSoftTransition"),
        )
        animated_alpha = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            alpha,
            visibility,
            name="Animated Emissive Alpha",
            location=(380, 300),
        )
        surface_alpha = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            animated_alpha,
            _float(data, profile, "DiffuseAlpha"),
            name="DiffuseAlpha",
            location=(-300, 420),
        )
        links.new(surface_alpha, find_input(principled, "Alpha"))
        strength = emissive_scale_bundle(
            nodes.id_data,
            animated_alpha,
            _float(data, profile, "EmissiveEV"),
            (240, 760),
        ).outputs["Raw Strength"]
        links.new(strength, find_input(principled, "Emission Strength"))

    def _emissive_subsurface(
        self, data, material, profile, nodes, links, principled, uv
    ):
        emissive = _texture(
            self,
            nodes,
            links,
            data,
            profile,
            "EmissiveMask",
            (-1080, 620),
            uv,
            non_color=True,
        )
        secondary = _texture(
            self,
            nodes,
            links,
            data,
            profile,
            "SecondaryMask",
            (-1080, 340),
            uv,
            non_color=True,
        )
        if emissive is None:
            mask = value_socket(nodes, "Emissive Mask Fallback", 0.0, (-760, 620))
        else:
            channels = param_vector(data, "EmissiveMaskChannel", (1.0, 0.0, 0.0, 0.0))
            separate = new_labeled_node(
                nodes, "ShaderNodeSeparateColor", "Emissive Mask Channels", (-820, 620)
            )
            separate.mode = "RGB"
            links.new(find_output(emissive, "Color"), find_input(separate, "Color"))
            # Separate Color splits red, green and blue; the fourth weight reads the mask's alpha.
            sources = (
                *(find_output(separate, name) for name in ("Red", "Green", "Blue")),
                _texture_alpha(emissive),
            )
            mask = None
            for index, weight in enumerate(channels[:4]):
                weighted = shader_nodes.math(
                    nodes,
                    links,
                    "MULTIPLY",
                    sources[index],
                    weight,
                    name=f"Emissive Channel {index}",
                    location=(-580, 720 - index * 120),
                )
                mask = (
                    weighted
                    if mask is None
                    else shader_nodes.math(
                        nodes,
                        links,
                        "MAXIMUM",
                        mask,
                        weighted,
                        name="Emissive Channel Maximum",
                        location=(-360, 640 - index * 80),
                    )
                )
        if secondary:
            mask = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                mask,
                _red(
                    nodes,
                    links,
                    secondary.outputs["Color"],
                    "SecondaryMask.r",
                    (-580, 300),
                ),
                name="Secondary Emissive Mask",
                location=(-120, 520),
            )
        threshold = _float(data, profile, "AlphaThreshold")
        visible = shader_nodes.math(
            nodes,
            links,
            "GREATER_THAN",
            mask,
            threshold,
            name="Emissive Alpha Threshold",
            location=(160, 520),
        )
        fx_mask = material_property_socket(
            nodes, material, "cp77_MaterialParam0", 1.0, (160, 360)
        )
        alpha = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            mask,
            visible,
            name="Thresholded Emissive Mask",
            location=(380, 520),
        )
        alpha = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            alpha,
            fx_mask,
            name="Emissive FX Mask",
            location=(600, 520),
        )
        color = rgb_socket(
            nodes,
            "EmissiveColor",
            _color(data, profile, "EmissiveColor", (1.0, 0.0, 0.0, 1.0)),
            (160, 760),
        )
        links.new(color, find_input(principled, "Base Color"))
        links.new(color, find_input(principled, "Emission Color", "Emission"))
        find_input(principled, "Emission Strength").default_value = _float(
            data, profile, "EmissiveEV", 2.07620502
        )
        links.new(alpha, find_input(principled, "Alpha"))
