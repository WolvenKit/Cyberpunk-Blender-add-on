import numpy as np

from ..blender import shader_nodes
from ..blender.mesh import SOURCE_NORMAL_ATTRIBUTE
from ..materials.blender.images import image_is_placeholder
from .bundles import vector_lerp_socket
from .decal_profiles import mesh_profile
from .graph import grid_location
from .mat_common import (
    get_or_build_node_group,
    new_labeled_node,
    param_float,
    param_texture_path,
    param_vector,
)

LOCAL_NORMAL_ATTRIBUTE = "CP77_VehicleDirtNormal"
DIRT_VERSION = 2


def vehicle_dirt_material_needs_rebuild(material):
    """Invalidate saved vehicle graphs without invalidating other material families"""
    if material is None:
        return False
    profile = mesh_profile(material.get("MaterialTemplate", ""))
    return bool(
        profile
        and "vehicle" in profile.features
        and material.get("cp77_vehicle_decal_dirt_version") != DIRT_VERSION
    )


def prepare_vehicle_dirt_mesh(obj, materials):
    """Prepare source normals for dirt sampling in the mesh coordinate frame"""
    if not any(
        material is not None and material.get("cp77_vehicle_decal_dirt_version")
        for material in materials
    ):
        return
    mesh = obj.data
    source = mesh.attributes.get(SOURCE_NORMAL_ATTRIBUTE)
    if (
        source is not None
        and source.domain == "POINT"
        and source.data_type == "FLOAT_VECTOR"
        and len(source.data) == len(mesh.vertices)
    ):
        values = np.empty((len(mesh.vertices), 3), dtype=np.float32)
        source.data.foreach_get("vector", values.reshape(-1))
        indices = np.empty(len(mesh.loops), dtype=np.int32)
        mesh.loops.foreach_get("vertex_index", indices)
        values = values[indices]
    else:
        values = np.empty((len(mesh.loops), 3), dtype=np.float32)
        mesh.corner_normals.foreach_get("vector", values.reshape(-1))
    attribute = mesh.attributes.get(LOCAL_NORMAL_ATTRIBUTE)
    if attribute is not None and (
        attribute.domain != "CORNER" or attribute.data_type != "FLOAT_VECTOR"
    ):
        mesh.attributes.remove(attribute)
        attribute = None
    if attribute is None:
        attribute = mesh.attributes.new(
            LOCAL_NORMAL_ATTRIBUTE, "FLOAT_VECTOR", "CORNER"
        )
    attribute.data.foreach_set("vector", np.ascontiguousarray(values).reshape(-1))


def _coordinate_group():
    def build(tree):
        source = tree.nodes.new("NodeGroupInput")
        output = tree.nodes.new("NodeGroupOutput")
        position = new_labeled_node(
            tree.nodes, "ShaderNodeSeparateXYZ", "Vehicle Local Position", (-600, 200)
        )
        normal = new_labeled_node(
            tree.nodes, "ShaderNodeSeparateXYZ", "Vehicle Local Normal", (-600, -200)
        )
        scaled = shader_nodes.vector_math(
            tree.nodes,
            tree.links,
            "SCALE",
            source.outputs["Position"],
            scale=source.outputs["Tiling"],
            name="Dirt Tiling",
            location=(-800, 200),
        )
        tree.links.new(scaled, position.inputs["Vector"])
        tree.links.new(source.outputs["Normal"], normal.inputs["Vector"])
        negative_x = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            position.outputs["X"],
            -1.0,
            name="Negative Local X",
            location=grid_location(tree),
        )
        for plane, u, v in (
            ("X", position.outputs["Y"], position.outputs["Z"]),
            ("Y", negative_x, position.outputs["Z"]),
            ("Z", position.outputs["Y"], negative_x),
        ):
            uv = new_labeled_node(
                tree.nodes,
                "ShaderNodeCombineXYZ",
                f"Dirt {plane} UV",
                (100, 400 - 160 * "XYZ".index(plane)),
            )
            tree.links.new(u, uv.inputs["X"])
            tree.links.new(v, uv.inputs["Y"])
            tree.links.new(uv.outputs["Vector"], output.inputs[f"UV {plane}"])
        weights = []
        for axis in "XYZ":
            absolute = shader_nodes.math(
                tree.nodes,
                tree.links,
                "ABSOLUTE",
                normal.outputs[axis],
                name=f"Absolute Normal {axis}",
                location=grid_location(tree),
            )
            weights.append(
                shader_nodes.math(
                    tree.nodes,
                    tree.links,
                    "POWER",
                    absolute,
                    16.0,
                    name=f"Normal {axis} Power 16",
                    location=grid_location(tree),
                )
            )
        total = shader_nodes.math(
            tree.nodes,
            tree.links,
            "ADD",
            weights[0],
            weights[1],
            name="Normal XY Weight",
            location=grid_location(tree),
        )
        total = shader_nodes.math(
            tree.nodes,
            tree.links,
            "ADD",
            total,
            weights[2],
            name="Normal Weight Sum",
            location=grid_location(tree),
        )
        combined = new_labeled_node(
            tree.nodes, "ShaderNodeCombineXYZ", "Normalized Dirt Weights", (600, -200)
        )
        for axis, weight in zip("XYZ", weights):
            normalized = shader_nodes.math(
                tree.nodes,
                tree.links,
                "DIVIDE",
                weight,
                total,
                name=f"Normalized Weight {axis}",
                location=grid_location(tree),
            )
            tree.links.new(normalized, combined.inputs[axis])
        tree.links.new(combined.outputs["Vector"], output.inputs["Weights"])

    return get_or_build_node_group(
        "CP77 Vehicle Dirt Coordinates v2",
        (
            ("NodeSocketVector", "Position"),
            ("NodeSocketVector", "Normal"),
            ("NodeSocketFloat", "Tiling"),
        ),
        tuple(
            ("NodeSocketVector", name) for name in ("UV X", "UV Y", "UV Z", "Weights")
        ),
        build,
    )


def build_vehicle_dirt_alpha(owner, tree, data, defaults, coverage):
    """Build the vehicle mesh decal's dirt coverage in the source mesh frame"""
    opacity = param_float(data, "DirtOpacity", defaults.get("DirtOpacity", 0.0))
    if opacity <= 0.0:
        return coverage
    path = param_texture_path(data, "DirtMap") or defaults.get("DirtMap", "")
    image = owner._load_relative_image(path, non_color=True, error_label="vehicle dirt")
    if image is None or image_is_placeholder(image):
        return coverage
    offsets = param_vector(
        data, "DirtMaskOffsets", defaults.get("DirtMaskOffsets", (1.5, 1.0, 0.5, 3.0))
    )
    nodes, links = tree.nodes, tree.links
    coordinates = new_labeled_node(
        nodes, "ShaderNodeTexCoord", "Vehicle Dirt Mesh Coordinates", (-1800, -900)
    )
    position = coordinates.outputs["Object"]
    geometry = new_labeled_node(
        nodes, "ShaderNodeNewGeometry", "Vehicle Dirt Geometry", (-1800, -1400)
    )
    normal = new_labeled_node(
        nodes, "ShaderNodeVectorTransform", "Vehicle Dirt Local Normal", (-1560, -1400)
    )
    normal.vector_type = "NORMAL"
    normal.convert_from = "WORLD"
    normal.convert_to = "OBJECT"
    links.new(geometry.outputs["Normal"], normal.inputs["Vector"])
    source_normal = new_labeled_node(
        nodes, "ShaderNodeAttribute", "Vehicle Dirt Source Normal", (-1800, -1660)
    )
    source_normal.attribute_type = "GEOMETRY"
    source_normal.attribute_name = LOCAL_NORMAL_ATTRIBUTE
    magnitude = shader_nodes.vector_math(
        nodes,
        links,
        "LENGTH",
        source_normal.outputs["Vector"],
        name="Vehicle Dirt Source Normal Length",
        location=(-1560, -1660),
    )
    present = shader_nodes.math(
        tree.nodes,
        tree.links,
        "GREATER_THAN",
        magnitude,
        1.0e-8,
        name="Vehicle Dirt Source Normal Present",
        location=grid_location(tree),
    )
    local_normal = vector_lerp_socket(
        tree,
        normal.outputs["Vector"],
        source_normal.outputs["Vector"],
        present,
        location=(-1340, -1400),
        label="Vehicle Dirt Source Normal Selection",
    )
    normalized = shader_nodes.vector_math(
        nodes,
        links,
        "NORMALIZE",
        local_normal,
        name="Vehicle Dirt Unit Normal",
        location=(-1120, -1400),
    )
    projection = new_labeled_node(
        nodes, "ShaderNodeGroup", "Vehicle Dirt Projection", (-1120, -900)
    )
    projection.node_tree = _coordinate_group()
    links.new(position, projection.inputs["Position"])
    links.new(normalized, projection.inputs["Normal"])
    projection.inputs["Tiling"].default_value = offsets[2]
    samples = new_labeled_node(
        nodes, "ShaderNodeCombineXYZ", "Vehicle Dirt Alpha Samples", (-620, -900)
    )
    for index, axis in enumerate("XYZ"):
        texture = new_labeled_node(
            nodes,
            "ShaderNodeTexImage",
            f"Vehicle Dirt {axis}",
            (-880, -900 - index * 240),
        )
        texture.image = image
        texture.extension = "REPEAT"
        texture.interpolation = "Linear"
        links.new(projection.outputs[f"UV {axis}"], texture.inputs["Vector"])
        links.new(texture.outputs["Alpha"], samples.inputs[axis])
    sampled = shader_nodes.vector_math(
        nodes,
        links,
        "DOT_PRODUCT",
        samples.outputs["Vector"],
        projection.outputs["Weights"],
        name="Vehicle Dirt Weighted Alpha",
        location=(-400, -900),
    )
    components = new_labeled_node(
        nodes,
        "ShaderNodeSeparateXYZ",
        "Vehicle Local Position Components",
        (-1120, -1680),
    )
    links.new(position, components.inputs["Vector"])
    height = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        components.outputs["Z"],
        offsets[0],
        name="Vehicle Dirt Height Scale",
        location=grid_location(tree),
    )
    height = shader_nodes.math(
        tree.nodes,
        tree.links,
        "SUBTRACT",
        0.5,
        height,
        name="Vehicle Dirt Height Mask",
        location=grid_location(tree),
        use_clamp=True,
    )
    amount = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        sampled,
        height,
        name="Vehicle Dirt Sample x Height",
        location=grid_location(tree),
    )
    amount = shader_nodes.math(
        tree.nodes,
        tree.links,
        "ADD",
        amount,
        opacity - offsets[1],
        name="Vehicle Dirt Opacity Offset",
        location=grid_location(tree),
    )
    amount = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        amount,
        offsets[3] + 2.2,
        name="Vehicle Dirt Contrast",
        location=grid_location(tree),
        use_clamp=True,
    )
    dirt_alpha = shader_nodes.math(
        tree.nodes,
        tree.links,
        "SUBTRACT",
        1.0,
        amount,
        name="Vehicle Dirt Alpha",
        location=grid_location(tree),
    )
    return shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        coverage,
        dirt_alpha,
        name="Vehicle Decal x Dirt Alpha",
        location=grid_location(tree),
    )
