from __future__ import annotations

import hashlib
import json
import logging
import math
import time

import bpy
from mathutils import Vector

from ..blender import shader_nodes
from ..blender.identity import rna_identity
from ..blender.naming import fit_id_name
from ..blender.shader_nodes import assign_socket, outputs_detached, replace_link
from ..blender.transactions import track_created_datablock
from ..core.log import get_logger, log_once
from .bundles import material_bundle_node
from .graph import mix_color_socket, mix_scalar_socket, set_absolute_locations
from .mat_common import find_input, get_or_build_node_group, new_labeled_node

_LOG = get_logger(__name__)

DECAL_UV_LAYER = "CP77_DecalUV"
# Decal surfaces blend in face order rather than dither: stacked decals share one object and sit millimetres apart,
# where dithered layers interfere in bands. Faces are emitted in draw order, so later decals cover earlier ones.
DECAL_RENDER_METHOD = "BLENDED"
_DECAL_UV_NODE_NAMES = frozenset({"Projected Decal UV", "UV"})
PROJECTION_COVERAGE_ATTRIBUTE = "CP77_DecalProjectionCoverage"
PROJECTOR_TANGENT_ATTRIBUTE = "CP77_DecalProjectorTangent"
PROJECTOR_BITANGENT_ATTRIBUTE = "CP77_DecalProjectorBitangent"
PROJECTOR_UP_ATTRIBUTE = "CP77_DecalProjectorUp"
PROJECTOR_FRAME_VALID_ATTRIBUTE = "CP77_DecalProjectorFrameValid"


def _mix_normal(nodes, links, first, second, factor, location):
    if first is None or (
        not hasattr(first, "is_output") and tuple(first) == (0.0, 0.0, 0.0)
    ):
        geometry = new_labeled_node(
            nodes,
            "ShaderNodeNewGeometry",
            "Receiver Geometry Normal",
            (location[0] - 220, location[1]),
        )
        first = geometry.outputs.get("Normal")
    inverse = shader_nodes.math(
        nodes,
        links,
        "SUBTRACT",
        name="One Minus Decal Normal Influence",
        location=(location[0], location[1] - 120),
    ).node
    inverse.inputs["Value"].default_value = 1.0
    assign_socket(
        links, factor, shader_nodes.socket_by_identifier(inverse.inputs, "Value_001")
    )
    first_scale = shader_nodes.vector_math(
        nodes, links, "SCALE", name="Receiver Normal Weight", location=location
    ).node
    assign_socket(links, first, first_scale.inputs["Vector"])
    links.new(inverse.outputs["Value"], find_input(first_scale, "Scale"))
    second_scale = shader_nodes.vector_math(
        nodes,
        links,
        "SCALE",
        name="Decal Normal Weight",
        location=(location[0], location[1] + 120),
    ).node
    assign_socket(links, second, second_scale.inputs["Vector"])
    assign_socket(links, factor, find_input(second_scale, "Scale"))
    add = shader_nodes.vector_math(
        nodes,
        links,
        "ADD",
        name="Conformal Decal Normal",
        location=(location[0] + 220, location[1]),
    ).node
    links.new(first_scale.outputs["Vector"], add.inputs["Vector"])
    links.new(
        second_scale.outputs["Vector"],
        shader_nodes.socket_by_identifier(add.inputs, "Vector_001"),
    )
    normalize = shader_nodes.vector_math(
        nodes,
        links,
        "NORMALIZE",
        name="Normalized Conformal Decal Normal",
        location=(location[0] + 440, location[1]),
    ).node
    links.new(add.outputs["Vector"], normalize.inputs["Vector"])
    return normalize.outputs["Vector"]


def _attribute_vector_socket(nodes, attribute_name, label, location):
    attribute = new_labeled_node(
        nodes,
        "ShaderNodeAttribute",
        label,
        location,
    )
    attribute.attribute_type = "GEOMETRY"
    attribute.attribute_name = attribute_name
    return attribute.outputs["Vector"]


def _world_vector(nodes, links, vector, vector_type, location):
    """An object-space frame vector in world space, normalized"""
    transform = new_labeled_node(
        nodes, "ShaderNodeVectorTransform", "Decal Frame to World", location
    )
    transform.vector_type = vector_type
    transform.convert_from = "OBJECT"
    transform.convert_to = "WORLD"
    links.new(vector, transform.inputs["Vector"])
    normalized = shader_nodes.vector_math(
        nodes,
        links,
        "NORMALIZE",
        name="Normalized Decal Frame",
        location=(location[0] + 80, location[1]),
    ).node
    links.new(transform.outputs["Vector"], normalized.inputs["Vector"])
    return normalized.outputs["Vector"]


def _projected_decal_normal(nodes, links, sampled_tangent, location):
    tangent_vector = _attribute_vector_socket(
        nodes,
        PROJECTOR_TANGENT_ATTRIBUTE,
        "Projected Normal Tangent",
        location,
    )
    bitangent_vector = _attribute_vector_socket(
        nodes,
        PROJECTOR_BITANGENT_ATTRIBUTE,
        "Projected Normal Bitangent",
        (location[0], location[1] - 120),
    )
    up_vector = _attribute_vector_socket(
        nodes,
        PROJECTOR_UP_ATTRIBUTE,
        "Projected Normal Up",
        (location[0], location[1] - 240),
    )
    directx_sample = shader_nodes.vector_math(
        nodes,
        links,
        "MULTIPLY",
        name="Projected Blender Tangent to Game Tangent",
        location=(location[0] + 220, location[1] - 80),
    ).node
    assign_socket(links, sampled_tangent, directx_sample.inputs["Vector"])
    shader_nodes.socket_by_identifier(
        directx_sample.inputs, "Vector_001"
    ).default_value = (1.0, -1.0, 1.0)
    components = new_labeled_node(
        nodes,
        "ShaderNodeSeparateXYZ",
        "Projected Game Tangent Components",
        (location[0] + 420, location[1] - 80),
    )
    links.new(directx_sample.outputs["Vector"], components.inputs["Vector"])
    world_terms = []
    for index, (axis, basis) in enumerate(
        (("X", tangent_vector), ("Y", bitangent_vector), ("Z", up_vector))
    ):
        term = shader_nodes.vector_math(
            nodes,
            links,
            "SCALE",
            name=f"Projected World {axis}",
            location=(location[0] + 620, location[1] + 80 - index * 110),
        ).node
        links.new(basis, term.inputs["Vector"])
        links.new(components.outputs[axis], find_input(term, "Scale"))
        world_terms.append(term.outputs["Vector"])
    add_xy = shader_nodes.vector_math(
        nodes,
        links,
        "ADD",
        name="Projected World XY",
        location=(location[0] + 820, location[1]),
    ).node
    links.new(world_terms[0], add_xy.inputs["Vector"])
    links.new(
        world_terms[1], shader_nodes.socket_by_identifier(add_xy.inputs, "Vector_001")
    )
    world = shader_nodes.vector_math(
        nodes,
        links,
        "ADD",
        name="Projected World Normal",
        location=(location[0] + 1020, location[1]),
    ).node
    links.new(add_xy.outputs["Vector"], world.inputs["Vector"])
    links.new(
        world_terms[2], shader_nodes.socket_by_identifier(world.inputs, "Vector_001")
    )
    normalize = shader_nodes.vector_math(
        nodes,
        links,
        "NORMALIZE",
        name="Normalized Projected World Normal",
        location=(location[0] + 1220, location[1]),
    ).node
    links.new(world.outputs["Vector"], normalize.inputs["Vector"])
    return normalize.outputs["Vector"]


def _reoriented_decal_normal(
    nodes,
    links,
    receiver_normal,
    sampled_tangent,
    location,
):
    if receiver_normal is None or (
        not hasattr(receiver_normal, "is_output")
        and tuple(receiver_normal) == (0.0, 0.0, 0.0)
    ):
        geometry = new_labeled_node(
            nodes,
            "ShaderNodeNewGeometry",
            "Conformal RNM Geometry",
            location,
        )
        receiver_normal = geometry.outputs.get("Normal")

    tangent_vector = _world_vector(
        nodes,
        links,
        _attribute_vector_socket(
            nodes,
            PROJECTOR_TANGENT_ATTRIBUTE,
            "Conformal Projector Tangent",
            (location[0], location[1] - 240),
        ),
        "VECTOR",
        (location[0] + 110, location[1] - 240),
    )
    bitangent_vector = _world_vector(
        nodes,
        links,
        _attribute_vector_socket(
            nodes,
            PROJECTOR_BITANGENT_ATTRIBUTE,
            "Conformal Projector Bitangent",
            (location[0], location[1] - 360),
        ),
        "VECTOR",
        (location[0] + 110, location[1] - 360),
    )
    up_vector = _world_vector(
        nodes,
        links,
        _attribute_vector_socket(
            nodes,
            PROJECTOR_UP_ATTRIBUTE,
            "Conformal Projector Up",
            (location[0], location[1] - 480),
        ),
        "NORMAL",
        (location[0] + 110, location[1] - 480),
    )

    tangent_components = []
    for index, (axis, basis) in enumerate(
        (("X", tangent_vector), ("Y", bitangent_vector), ("Z", up_vector))
    ):
        dot = shader_nodes.vector_math(
            nodes,
            links,
            "DOT_PRODUCT",
            name=f"Receiver Normal Projector {axis}",
            location=(location[0] + 220, location[1] + 120 - index * 110),
        ).node
        assign_socket(links, receiver_normal, dot.inputs["Vector"])
        links.new(basis, shader_nodes.socket_by_identifier(dot.inputs, "Vector_001"))
        tangent_components.append(dot.outputs["Value"])
    receiver_tangent = new_labeled_node(
        nodes,
        "ShaderNodeCombineXYZ",
        "Receiver Projector Normal",
        (location[0] + 420, location[1]),
    )
    for axis, value in zip(("X", "Y", "Z"), tangent_components):
        links.new(value, receiver_tangent.inputs[axis])
    receiver_plus_z = shader_nodes.vector_math(
        nodes,
        links,
        "ADD",
        name="RNM Receiver + Z",
        location=(location[0] + 620, location[1]),
    ).node
    links.new(receiver_tangent.outputs["Vector"], receiver_plus_z.inputs["Vector"])
    shader_nodes.socket_by_identifier(
        receiver_plus_z.inputs, "Vector_001"
    ).default_value = (0.0, 0.0, 1.0)

    directx_sample = shader_nodes.vector_math(
        nodes,
        links,
        "MULTIPLY",
        name="RNM Blender Tangent to Game Tangent",
        location=(location[0] + 420, location[1] - 200),
    ).node
    assign_socket(links, sampled_tangent, directx_sample.inputs["Vector"])
    shader_nodes.socket_by_identifier(
        directx_sample.inputs, "Vector_001"
    ).default_value = (1.0, -1.0, 1.0)
    flipped_sample = shader_nodes.vector_math(
        nodes,
        links,
        "MULTIPLY",
        name="RNM Flip Sample XY",
        location=(location[0] + 620, location[1] - 200),
    ).node
    links.new(directx_sample.outputs["Vector"], flipped_sample.inputs["Vector"])
    shader_nodes.socket_by_identifier(
        flipped_sample.inputs, "Vector_001"
    ).default_value = (-1.0, -1.0, 1.0)

    rnm_dot = shader_nodes.vector_math(
        nodes,
        links,
        "DOT_PRODUCT",
        name="RNM Dot",
        location=(location[0] + 820, location[1] - 80),
    ).node
    links.new(receiver_plus_z.outputs["Vector"], rnm_dot.inputs["Vector"])
    links.new(
        flipped_sample.outputs["Vector"],
        shader_nodes.socket_by_identifier(rnm_dot.inputs, "Vector_001"),
    )
    receiver_scaled = shader_nodes.vector_math(
        nodes,
        links,
        "SCALE",
        name="RNM Receiver Term",
        location=(location[0] + 1020, location[1]),
    ).node
    links.new(receiver_plus_z.outputs["Vector"], receiver_scaled.inputs["Vector"])
    links.new(
        rnm_dot.outputs["Value"],
        find_input(receiver_scaled, "Scale"),
    )
    receiver_components = new_labeled_node(
        nodes,
        "ShaderNodeSeparateXYZ",
        "RNM Receiver Components",
        (location[0] + 820, location[1] + 120),
    )
    links.new(receiver_plus_z.outputs["Vector"], receiver_components.inputs["Vector"])
    sample_scaled = shader_nodes.vector_math(
        nodes,
        links,
        "SCALE",
        name="RNM Sample Term",
        location=(location[0] + 1020, location[1] - 200),
    ).node
    links.new(flipped_sample.outputs["Vector"], sample_scaled.inputs["Vector"])
    links.new(receiver_components.outputs["Z"], find_input(sample_scaled, "Scale"))
    rnm = shader_nodes.vector_math(
        nodes,
        links,
        "SUBTRACT",
        name="Reoriented Projector Normal",
        location=(location[0] + 1220, location[1]),
    ).node
    links.new(receiver_scaled.outputs["Vector"], rnm.inputs["Vector"])
    links.new(
        sample_scaled.outputs["Vector"],
        shader_nodes.socket_by_identifier(rnm.inputs, "Vector_001"),
    )
    rnm_normalized = shader_nodes.vector_math(
        nodes,
        links,
        "NORMALIZE",
        name="Normalized Reoriented Projector Normal",
        location=(location[0] + 1420, location[1]),
    ).node
    links.new(rnm.outputs["Vector"], rnm_normalized.inputs["Vector"])

    components = new_labeled_node(
        nodes,
        "ShaderNodeSeparateXYZ",
        "Reoriented Projector Components",
        (location[0] + 1620, location[1]),
    )
    links.new(rnm_normalized.outputs["Vector"], components.inputs["Vector"])
    world_terms = []
    for index, (axis, basis) in enumerate(
        (("X", tangent_vector), ("Y", bitangent_vector), ("Z", up_vector))
    ):
        term = shader_nodes.vector_math(
            nodes,
            links,
            "SCALE",
            name=f"Reoriented World {axis}",
            location=(location[0] + 1820, location[1] + 120 - index * 120),
        ).node
        links.new(basis, term.inputs["Vector"])
        links.new(components.outputs[axis], find_input(term, "Scale"))
        world_terms.append(term.outputs["Vector"])
    add_xy = shader_nodes.vector_math(
        nodes,
        links,
        "ADD",
        name="Reoriented World XY",
        location=(location[0] + 2020, location[1] + 40),
    ).node
    links.new(world_terms[0], add_xy.inputs["Vector"])
    links.new(
        world_terms[1], shader_nodes.socket_by_identifier(add_xy.inputs, "Vector_001")
    )
    world = shader_nodes.vector_math(
        nodes,
        links,
        "ADD",
        name="Reoriented World Normal",
        location=(location[0] + 2220, location[1]),
    ).node
    links.new(add_xy.outputs["Vector"], world.inputs["Vector"])
    links.new(
        world_terms[2], shader_nodes.socket_by_identifier(world.inputs, "Vector_001")
    )
    normalize = shader_nodes.vector_math(
        nodes,
        links,
        "NORMALIZE",
        name="Normalized Reoriented World Normal",
        location=(location[0] + 2420, location[1]),
    ).node
    links.new(world.outputs["Vector"], normalize.inputs["Vector"])
    return normalize.outputs["Vector"]


def _composite_surface_coverage(nodes, links, factors, sector_alpha, projected):
    """Restrict the decal surface to its active channel masks and projection volume"""
    coverage = 0.0
    for index, factor in enumerate(factors):
        coverage = shader_nodes.math(
            nodes,
            links,
            "MAXIMUM",
            coverage,
            factor,
            name=f"Conformal Channel Coverage {index + 1}",
            location=(-1040, -980),
            use_clamp=True,
        )
    coverage = shader_nodes.math(
        nodes,
        links,
        "MINIMUM",
        coverage,
        sector_alpha,
        name="Conformal Surface Instance Coverage",
        location=(-1040, -980),
        use_clamp=True,
    )
    if not projected:
        return coverage
    projection = new_labeled_node(
        nodes,
        "ShaderNodeAttribute",
        "Conformal Surface Projection Coverage",
        (-1280, -1120),
    )
    projection.attribute_type = "GEOMETRY"
    projection.attribute_name = PROJECTION_COVERAGE_ATTRIBUTE
    return shader_nodes.math(
        nodes,
        links,
        "MINIMUM",
        coverage,
        projection.outputs["Fac"],
        name="Conformal Surface Coverage",
        location=(-1040, -980),
        use_clamp=True,
    )


def _normal_group(kind):
    inputs = [("NodeSocketVector", "Sample")]
    if kind != "Projected":
        inputs.insert(0, ("NodeSocketVector", "Receiver"))
    if kind == "Blend":
        inputs.append(("NodeSocketFloat", "Factor"))

    def build(group):
        incoming = group.nodes.new("NodeGroupInput")
        outgoing = group.nodes.new("NodeGroupOutput")
        if kind == "Blend":
            result = _mix_normal(
                group.nodes,
                group.links,
                incoming.outputs["Receiver"],
                incoming.outputs["Sample"],
                incoming.outputs["Factor"],
                (0, 0),
            )
        elif kind == "Projected":
            result = _projected_decal_normal(
                group.nodes, group.links, incoming.outputs["Sample"], (0, 0)
            )
        else:
            result = _reoriented_decal_normal(
                group.nodes,
                group.links,
                incoming.outputs["Receiver"],
                incoming.outputs["Sample"],
                (0, 0),
            )
        group.links.new(result, outgoing.inputs["Normal"])

    return get_or_build_node_group(
        f"CP77 Conformal {kind} Normal Bundle v4",
        tuple(inputs),
        (("NodeSocketVector", "Normal"),),
        build,
    )


def _receiver_normal(tree, value, location):
    if value is None or (
        not hasattr(value, "is_output") and tuple(value) == (0.0, 0.0, 0.0)
    ):
        geometry = new_labeled_node(
            tree.nodes, "ShaderNodeNewGeometry", "Receiver Geometry Normal", location
        )
        return geometry.outputs["Normal"]
    return value


def mix_normal_socket(tree, first, second, factor, location):
    first = _receiver_normal(tree, first, (location[0] - 220, location[1]))
    return material_bundle_node(
        tree,
        _normal_group("Blend"),
        location,
        "Conformal Decal Normal",
        {"Receiver": first, "Sample": second, "Factor": factor},
    ).outputs["Normal"]


def projected_normal_socket(tree, sampled_tangent, location):
    return material_bundle_node(
        tree,
        _normal_group("Projected"),
        location,
        "Projected Decal Normal",
        {"Sample": sampled_tangent},
    ).outputs["Normal"]


def reoriented_normal_socket(tree, receiver_normal, sampled_tangent, location):
    receiver_normal = _receiver_normal(
        tree, receiver_normal, (location[0] - 220, location[1])
    )
    return material_bundle_node(
        tree,
        _normal_group("Reoriented"),
        location,
        "Reoriented Decal Normal",
        {"Receiver": receiver_normal, "Sample": sampled_tangent},
    ).outputs["Normal"]


def surface_influence_sockets(
    tree, factors, sector_alpha, diffuse, normal, material, *, projected=True
):
    count = len(factors)
    factor_names = tuple(f"Coverage {index + 1}" for index in range(count))
    inputs = tuple(
        ("NodeSocketFloat", name)
        for name in (*factor_names, "Sector Alpha", "Diffuse", "Normal", "Material")
    )
    outputs = tuple(
        ("NodeSocketFloat", name)
        for name in ("Coverage", "Diffuse", "Normal", "Material")
    )

    def build(group):
        incoming = group.nodes.new("NodeGroupInput")
        outgoing = group.nodes.new("NodeGroupOutput")
        coverage = _composite_surface_coverage(
            group.nodes,
            group.links,
            [incoming.outputs[name] for name in factor_names],
            incoming.outputs["Sector Alpha"],
            projected,
        )
        group.links.new(coverage, outgoing.inputs["Coverage"])
        for name in ("Diffuse", "Normal", "Material"):
            result = shader_nodes.math(
                group.nodes,
                group.links,
                "DIVIDE",
                incoming.outputs[name],
                coverage,
                name=f"Conformal Normalized {name} Influence",
                location=(-1040, -980),
                use_clamp=True,
            )
            group.links.new(result, outgoing.inputs[name])

    kind = "Coverage" if projected else "Mesh Coverage"
    group = get_or_build_node_group(
        f"CP77 Conformal {kind} {count} Bundle v1", inputs, outputs, build
    )
    values = dict(zip(factor_names, factors))
    values.update(
        {
            "Sector Alpha": max(0.0, min(1.0, sector_alpha)),
            "Diffuse": diffuse,
            "Normal": normal,
            "Material": material,
        }
    )
    node = material_bundle_node(
        tree, group, (-1040, -980), "Conformal Surface Influences", values
    )
    return tuple(
        node.outputs[name] for name in ("Coverage", "Diffuse", "Normal", "Material")
    )


def _copy_rna_properties(source, target, property_cache):
    schema = source.bl_rna.identifier
    names = property_cache.get(schema)
    if names is None:
        # A clone has no parent frame, so its absolute location is its location, which the cloner sets itself.
        skipped = {
            "rna_type",
            "type",
            "dimensions",
            "inputs",
            "outputs",
            "internal_links",
            "select",
            "parent",
            "name",
            "label",
            "location",
            "location_absolute",
        }
        names = tuple(
            (prop.identifier, getattr(prop, "is_array", False))
            for prop in source.bl_rna.properties
            if prop.identifier not in skipped
            and not prop.is_readonly
            and prop.type not in {"POINTER", "COLLECTION"}
        )
        property_cache[schema] = names
    for name, is_array in names:
        try:
            value = getattr(source, name)
            current = getattr(target, name)
            if is_array:
                value = tuple(value)
                current = tuple(current)
            if value != current:
                setattr(target, name, value)
        except (AttributeError, TypeError, ValueError):
            log_once(
                _LOG,
                logging.DEBUG,
                "_copy_rna_properties",
                "_copy_rna_properties skipped what it could not read or write",
                exc_info=True,
            )
            continue


def _copy_socket_defaults(source, target):
    for index, source_socket in enumerate(source):
        if index >= len(target) or not hasattr(source_socket, "default_value"):
            continue
        value = source_socket.default_value
        try:
            value = tuple(value)
        except TypeError:
            pass
        try:
            current = target[index].default_value
            if isinstance(value, tuple):
                current = tuple(current)
            if value != current:
                target[index].default_value = value
        except ValueError:
            continue


def _copy_socket_driver(source_tree, target_tree, source_socket, target_socket):
    animation = getattr(source_tree, "animation_data", None)
    drivers = getattr(animation, "drivers", None)
    if drivers is None:
        return
    try:
        source_path = source_socket.path_from_id("default_value")
        source_curve = drivers.find(source_path)
    except (AttributeError, TypeError, ValueError):
        log_once(
            _LOG,
            logging.DEBUG,
            "_copy_socket_driver",
            "_copy_socket_driver skipped what it could not read or write",
            exc_info=True,
        )
        return
    if source_curve is None:
        return
    try:
        target_curve = target_socket.driver_add("default_value")
    except (AttributeError, TypeError, ValueError):
        log_once(
            _LOG,
            logging.DEBUG,
            "_copy_socket_driver",
            "_copy_socket_driver skipped what it could not read or write",
            exc_info=True,
        )
        return
    target_driver = target_curve.driver
    source_driver = source_curve.driver
    target_driver.type = source_driver.type
    target_driver.expression = source_driver.expression
    target_driver.use_self = source_driver.use_self
    for source_variable in source_driver.variables:
        target_variable = target_driver.variables.new()
        target_variable.name = source_variable.name
        target_variable.type = source_variable.type
        for source_target, target_target in zip(
            source_variable.targets, target_variable.targets
        ):
            for name in (
                "id_type",
                "data_path",
                "bone_target",
                "transform_type",
                "transform_space",
                "rotation_mode",
            ):
                if not hasattr(source_target, name) or not hasattr(target_target, name):
                    continue
                try:
                    setattr(target_target, name, getattr(source_target, name))
                except (AttributeError, TypeError, ValueError):
                    log_once(
                        _LOG,
                        logging.DEBUG,
                        "_copy_socket_driver",
                        "_copy_socket_driver skipped what it could not read or write",
                        exc_info=True,
                    )
                    continue
            target_id = getattr(source_target, "id", None)
            if target_id is source_tree.id_data:
                target_id = target_tree.id_data
            try:
                target_target.id = target_id
            except ValueError:
                continue


def _assign_if_changed(owner, name, value):
    if getattr(owner, name) != value:
        setattr(owner, name, value)


def _clone_values(source, target, property_cache):
    """What a cloned node takes from its source besides its name, sockets and links"""
    _copy_rna_properties(source, target, property_cache)
    _assign_if_changed(target, "label", source.label or source.name)
    # Compared as stored (single precision): a copied clone already sits where its source puts it.
    location = Vector((source.location.x - 2400.0, source.location.y))
    if target.location != location:
        target.location = location
    for pointer_name in ("image", "node_tree", "object"):
        if not hasattr(source, pointer_name) or not hasattr(target, pointer_name):
            continue
        try:
            _assign_if_changed(target, pointer_name, getattr(source, pointer_name))
        except (AttributeError, TypeError, ValueError):
            log_once(
                _LOG,
                logging.DEBUG,
                "_clone_values",
                "_clone_values skipped what it could not read or write",
                exc_info=True,
            )
            continue


def _clone_special_values(source, target):
    """Point cloned UV and tangent lookups at the decal UV layer and copy ramp stops"""
    if source.bl_idname == "ShaderNodeUVMap" and (
        source.name in _DECAL_UV_NODE_NAMES or source.label in _DECAL_UV_NODE_NAMES
    ):
        target.uv_map = DECAL_UV_LAYER
    if source.bl_idname == "ShaderNodeNormalMap":
        target.uv_map = DECAL_UV_LAYER
    if source.bl_idname == "ShaderNodeTangent":
        target.direction_type = "UV_MAP"
        target.uv_map = DECAL_UV_LAYER
    if source.bl_idname == "ShaderNodeValToRGB":
        source_ramp = source.color_ramp
        target_ramp = target.color_ramp
        target_ramp.color_mode = source_ramp.color_mode
        target_ramp.hue_interpolation = source_ramp.hue_interpolation
        target_ramp.interpolation = source_ramp.interpolation
        while len(target_ramp.elements) > 1:
            target_ramp.elements.remove(target_ramp.elements[-1])
        target_ramp.elements[0].position = source_ramp.elements[0].position
        target_ramp.elements[0].color = source_ramp.elements[0].color
        for element in source_ramp.elements[1:]:
            created = target_ramp.elements.new(element.position)
            created.color = element.color


class _DecalNodeCloner:
    def __init__(self, source_tree, target_tree, profile=None):
        self.profile = profile
        self._cloning = False
        self.source_tree = source_tree
        self.target_tree = target_tree
        self.nodes = {}
        self.property_cache = {}
        self.input_sources = {}
        self.output_indices = {}
        for link in source_tree.links:
            self.input_sources.setdefault(link.to_socket, link.from_socket)

    def clone_socket(self, source_socket):
        outermost = self.profile is not None and not self._cloning
        if outermost:
            started = time.perf_counter()
            self._cloning = True
        try:
            source_node = source_socket.node
            target_node = self._clone_node(source_node)
            indices = self.output_indices.get(source_node)
            if indices is None:
                indices = {
                    socket: index for index, socket in enumerate(source_node.outputs)
                }
                self.output_indices[source_node] = indices
            index = indices[source_socket]
            return target_node.outputs[index]
        finally:
            if outermost:
                self._cloning = False
                self.profile["composite_clone_seconds"] += time.perf_counter() - started

    def _clone_node(self, source):
        existing = self.nodes.get(source)
        if existing is not None:
            return existing
        profile = self.profile
        phase_started = time.perf_counter() if profile is not None else 0.0
        target = self.target_tree.nodes.new(source.bl_idname)
        self.nodes[source] = target
        if profile is not None:
            profile["composite_clone_nodes"] += 1
            profile["composite_clone_create_seconds"] += (
                time.perf_counter() - phase_started
            )
            phase_started = time.perf_counter()
        # A clone keeps Blender's own name (its label is its source's): a rename scans every data-block of the file.
        _clone_values(source, target, self.property_cache)
        if source.bl_idname in {"NodeCombineBundle", "NodeSeparateBundle"}:
            target.bundle_items.clear()
            for item in source.bundle_items:
                target.bundle_items.new(socket_type=item.socket_type, name=item.name)
        if profile is not None:
            profile["composite_clone_properties_seconds"] += (
                time.perf_counter() - phase_started
            )
            phase_started = time.perf_counter()
        _copy_socket_defaults(source.inputs, target.inputs)
        _copy_socket_defaults(source.outputs, target.outputs)
        if profile is not None:
            profile["composite_clone_defaults_seconds"] += (
                time.perf_counter() - phase_started
            )
            phase_started = time.perf_counter()
        for source_socket, target_socket in zip(source.outputs, target.outputs):
            _copy_socket_driver(
                self.source_tree,
                self.target_tree,
                source_socket,
                target_socket,
            )
        if profile is not None:
            profile["composite_clone_drivers_seconds"] += (
                time.perf_counter() - phase_started
            )
            phase_started = time.perf_counter()
        _clone_special_values(source, target)
        if profile is not None:
            profile["composite_clone_special_seconds"] += (
                time.perf_counter() - phase_started
            )
        for index, source_input in enumerate(source.inputs):
            upstream_socket = self.input_sources.get(source_input)
            if upstream_socket is None or index >= len(target.inputs):
                continue
            upstream = self.clone_socket(upstream_socket)
            self.target_tree.links.new(upstream, target.inputs[index])
            if profile is not None:
                profile["composite_clone_links"] += 1
        return target


# Receiver principled inputs a composite blends (each with its alternative socket names) and the socket type the
# shared composite group carries them with.
_CHANNELS = {
    "Base Color": (("Base Color",), "NodeSocketColor"),
    "Normal": (("Normal",), "NodeSocketVector"),
    "Roughness": (("Roughness",), "NodeSocketFloat"),
    "Metallic": (("Metallic",), "NodeSocketFloat"),
    "Emission Color": (("Emission Color", "Emission"), "NodeSocketColor"),
    "Emission Strength": (("Emission Strength",), "NodeSocketFloat"),
}
_RECEIVER_PREFIX = "Receiver "
_COVERAGE_OUTPUT = "Coverage"
_COLOR_FEATURES = frozenset(
    {
        "diffuse",
        "gradient",
        "tint3",
        "terrain",
        "caustics",
        "thermal",
        "glitch",
        "glitch_emissive",
        "emissive_color",
        "emissive_only",
        "forward",
        "base",
        "vehicle",
        "multitint",
    }
)


def _has_drivers(tree):
    animation = getattr(tree, "animation_data", None)
    return bool(getattr(animation, "drivers", None))


def _principled_input(node, channel):
    return find_input(node, *_CHANNELS[channel][0])


class _PrincipledChannels:
    """A principled node of the composite itself"""

    def __init__(self, links, target):
        self.links = links
        self.target = target
        self.location = (target.location.x, target.location.y)

    def value(self, channel):
        return socket_value(_principled_input(self.target, channel))

    def present(self, channel):
        return _principled_input(self.target, channel) is not None

    def connect(self, channel, socket):
        replace_link(self.links, socket, _principled_input(self.target, channel))


class _GroupChannels:
    """The interface of a shared composite group"""

    def __init__(self, group, incoming, outgoing):
        self.group = group
        self.incoming = incoming
        self.outgoing = outgoing
        self.location = (0.0, 0.0)
        self.declared = set()

    def _socket(self, name, in_out, socket_type):
        if (name, in_out) not in self.declared:
            self.group.interface.new_socket(
                name=name, in_out=in_out, socket_type=socket_type
            )
            self.declared.add((name, in_out))
        sockets = self.incoming.outputs if in_out == "INPUT" else self.outgoing.inputs
        return sockets[name]

    def value(self, channel):
        return self._socket(_RECEIVER_PREFIX + channel, "INPUT", _CHANNELS[channel][1])

    def present(self, channel):
        return True

    def connect(self, channel, socket):
        socket_type = (
            _CHANNELS[channel][1] if channel in _CHANNELS else "NodeSocketFloat"
        )
        self.group.links.new(socket, self._socket(channel, "OUTPUT", socket_type))


def _find_node(material, names):
    tree = getattr(material, "node_tree", None)
    if tree is None:
        return None
    for name in names:
        wanted = name.casefold()
        for node in tree.nodes:
            if node.name.casefold() == wanted or node.label.casefold() == wanted:
                return node
    return None


def _node_output(material, names):
    node = _find_node(material, names)
    if node is None or not node.outputs:
        return None
    for name in ("Result", "Value", "Color", "Vector", "Normal"):
        socket = node.outputs.get(name)
        if socket is not None:
            return socket
    return node.outputs[-1]


def _principled_nodes(material):
    tree = getattr(material, "node_tree", None)
    if tree is None:
        return ()
    return tuple(
        node for node in tree.nodes if node.bl_idname == "ShaderNodeBsdfPrincipled"
    )


def _features(material):
    try:
        return set(json.loads(material.get("cp77_decal_features", "[]")))
    except (TypeError, ValueError, json.JSONDecodeError):
        return set()


def requires_receiver_composite(material):
    if int(material.get("normalBlendingMode", 0) or 0) > 0:
        return True
    features = _features(material)
    if material.get("cp77_decal_family") == "projected" and "normal" in features:
        return True
    visible_features = {
        "diffuse",
        "gradient",
        "tint3",
        "terrain",
        "caustics",
        "thermal",
        "glitch",
        "glitch_emissive",
        "emissive_color",
        "emissive_only",
        "forward",
    }
    return not bool(features & visible_features)


def decal_surface_material(decal, cache):
    key = ("DECAL_SURFACE", decal.as_pointer())
    if key in cache:
        return cache[key]
    material = track_created_datablock("materials", decal.copy())
    material.name = fit_id_name(decal.name, "_CP77ConformalSurface")
    tree = getattr(material, "node_tree", None)
    if tree is not None:
        for node in tree.nodes:
            if (
                node.bl_idname == "ShaderNodeUVMap"
                or node.bl_idname == "ShaderNodeNormalMap"
            ):
                node.uv_map = DECAL_UV_LAYER
            elif node.bl_idname == "ShaderNodeTangent":
                node.direction_type = "UV_MAP"
                node.uv_map = DECAL_UV_LAYER
    for name, value in (
        ("surface_render_method", DECAL_RENDER_METHOD),
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
                "decal_surface_material",
                "decal_surface_material skipped what it could not read or write",
                exc_info=True,
            )
    cache[key] = material
    return material


def _scale_factor(nodes, links, name, location, factor, scale):
    if math.isclose(float(scale), 1.0, abs_tol=1.0e-8):
        return factor
    node = shader_nodes.math(
        nodes, links, "MULTIPLY", name=name, location=location
    ).node
    assign_socket(links, factor, node.inputs["Value"])
    shader_nodes.socket_by_identifier(node.inputs, "Value_001").default_value = float(
        scale
    )
    return node.outputs["Value"]


def _factor_source(
    decal,
    cloner,
    names,
    fallback_socket=None,
    fallback=0.0,
    *,
    prefer_fallback=False,
):
    if prefer_fallback and fallback_socket is not None:
        links = list(fallback_socket.links)
        if links:
            return cloner.clone_socket(links[0].from_socket)
    source = _node_output(decal, names)
    if source is None and fallback_socket is not None:
        links = list(fallback_socket.links)
        source = links[0].from_socket if links else None
        if source is None:
            return fallback_socket.default_value
    return cloner.clone_socket(source) if source is not None else fallback


def _group_node(tree, group, label, location, placed):
    """A node of tree using group"""
    node = tree.nodes.new("ShaderNodeGroup")
    node.label = label
    node.node_tree = group
    placed[rna_identity(node)] = location
    return node


def _surface_mask_group():
    """Shows Shader where Coverage is 1 and what lies behind the surface where it is 0"""

    def build(group):
        incoming = group.nodes.new("NodeGroupInput")
        incoming.location = (-680.0, 0.0)
        outgoing = group.nodes.new("NodeGroupOutput")
        transparent = new_labeled_node(
            group.nodes,
            "ShaderNodeBsdfTransparent",
            "Conformal Decal Transparent Regions",
            (-460.0, -220.0),
        )
        mix = new_labeled_node(
            group.nodes,
            "ShaderNodeMixShader",
            "Conformal Decal Surface Opacity",
            (-220.0, 0.0),
        )
        group.links.new(incoming.outputs["Coverage"], mix.inputs["Factor"])
        group.links.new(transparent.outputs["BSDF"], mix.inputs["Shader"])
        group.links.new(
            incoming.outputs["Shader"],
            shader_nodes.socket_by_identifier(mix.inputs, "Shader_001"),
        )
        group.links.new(mix.outputs["Shader"], outgoing.inputs["Shader"])

    return get_or_build_node_group(
        "CP77 Conformal Decal Surface Mask v1",
        (("NodeSocketFloat", "Coverage"), ("NodeSocketShader", "Shader")),
        (("NodeSocketShader", "Shader"),),
        build,
    )


def _linked_surfaces(tree):
    """Each material output of tree whose surface is linked, with the shader linked into it"""
    return [
        (node, node.inputs["Surface"].links[0].from_socket)
        for node in tree.nodes
        if node.bl_idname == "ShaderNodeOutputMaterial"
        and "Surface" in node.inputs
        and node.inputs["Surface"].is_linked
    ]


def _mask_composite_surface(tree, surfaces, coverage, placed):
    """Reveal underlying surfaces through empty and partially covered decal regions"""
    group = _surface_mask_group()
    for output, shader in surfaces:
        mask = _group_node(
            tree,
            group,
            "Conformal Decal Surface Mask",
            (output.location.x - 220, output.location.y),
            placed,
        )
        assign_socket(tree.links, coverage, mask.inputs["Coverage"])
        tree.links.new(shader, mask.inputs["Shader"])
        tree.links.new(mask.outputs["Shader"], output.inputs["Surface"])


def composite_material(
    receiver,
    decal,
    cache,
    *,
    receiver_pointer=None,
    decal_pointer=None,
    profile=None,
):
    cache_key = (
        (
            receiver.as_pointer()
            if receiver_pointer is None and receiver is not None
            else int(receiver_pointer or 0)
        ),
        decal.as_pointer() if decal_pointer is None else int(decal_pointer),
    )
    if cache_key in cache:
        return cache[cache_key]

    if receiver is None or not receiver.use_nodes or receiver.node_tree is None:
        cache[cache_key] = None
        return None
    if not _principled_nodes(receiver) or not _principled_nodes(decal):
        cache[cache_key] = None
        return None

    if not _has_drivers(decal.node_tree):
        group = _decal_composite_group(decal, cache, profile)
        template = cache.get(_composite_template_key(cache_key[0], group))
        material = (
            _copied_composite(template, receiver, decal, group)
            if template is not None
            else None
        )
        if material is not None:
            cache[cache_key] = material
            return material

    copy_started = time.perf_counter() if profile is not None else 0.0
    material = track_created_datablock("materials", receiver.copy())
    try:
        if profile is not None:
            profile["composite_copy_seconds"] += time.perf_counter() - copy_started
        return _build_composite_material(
            receiver, decal, cache, cache_key, material, profile
        )
    except Exception:
        if material.users == 0:
            bpy.data.materials.remove(material)
        raise


def _tag_composite(material, receiver, decal):
    """Name a receiver composite after its receiver and decal and give it the decal's properties"""
    suffix = hashlib.sha1(f"{receiver.name}|{decal.name}".encode()).hexdigest()[:10]
    material.name = fit_id_name(receiver.name, f"_CP77Decal_{suffix}")
    material["cp77_decal_features"] = decal.get("cp77_decal_features", "[]")
    for property_name in decal.keys():
        if not str(property_name).startswith("cp77"):
            continue
        if property_name in material and property_name != "cp77_MaterialParam0":
            continue
        try:
            material[property_name] = decal[property_name]
        except (TypeError, ValueError):
            continue


def _composite_template_key(receiver_pointer, group):
    """The key of composites of one receiver that differ only in their decal group"""
    interface = tuple(
        (
            item.item_type,
            item.name,
            getattr(item, "in_out", None),
            getattr(item, "socket_type", None),
            getattr(item, "identifier", None),
        )
        for item in group.interface.items_tree
    )
    return ("COMPOSITE_TEMPLATE", receiver_pointer, interface)


def _copied_composite(template, receiver, decal, group):
    """A copy of a composite built on receiver for another decal, or None"""
    built, built_group, group_nodes = template
    try:
        material = track_created_datablock("materials", built.copy())
    except ReferenceError:
        return None
    try:
        # Back to the receiver's own properties before the decal's are added, as a build from the receiver does.
        for key in tuple(material.keys()):
            if key not in receiver:
                del material[key]
            elif key in {"cp77_decal_features", "cp77_MaterialParam0"}:
                material[key] = receiver[key]
        _tag_composite(material, receiver, decal)
        nodes = material.node_tree.nodes
        for name in group_nodes:
            node = nodes[name]
            if node.node_tree is not built_group:
                raise ValueError(f"{name} does not blend the composite's decal")
            node.node_tree = group
    except (AttributeError, KeyError, ReferenceError, TypeError, ValueError):
        log_once(
            _LOG,
            logging.DEBUG,
            "_copied_composite",
            "_copied_composite skipped what it could not read or write",
            exc_info=True,
        )
        bpy.data.materials.remove(material)
        return None
    return material


def _build_composite_material(
    receiver, decal, cache, cache_key, material, profile=None
):
    """Configure a receiver copy while allowing its caller to clean up failures"""
    phase_started = time.perf_counter() if profile is not None else 0.0
    _tag_composite(material, receiver, decal)
    tree = material.node_tree
    links = tree.links
    receiver_principled = _principled_nodes(material)
    # Read before the outputs are detached; the masks link into them in place of the shaders.
    surfaces = _linked_surfaces(tree)
    placed = {}
    if profile is not None:
        profile["composite_prepare_seconds"] += time.perf_counter() - phase_started
    if _has_drivers(decal.node_tree):
        cloner = _DecalNodeCloner(decal.node_tree, tree, profile)
        targets = [_PrincipledChannels(links, target) for target in receiver_principled]
        surface_coverage = _blend_decal_channels(tree, decal, cloner, targets, profile)
        _mask_composite_surface(tree, surfaces, surface_coverage, placed)
        set_absolute_locations(tree, placed)
    else:
        group = _decal_composite_group(decal, cache, profile)
        phase_started = time.perf_counter() if profile is not None else 0.0
        surface_coverage = None
        items = tuple(group.interface.items_tree)
        inputs = [item.name for item in items if item.in_out == "INPUT"]
        outputs = [item.name for item in items if item.in_out == "OUTPUT"]
        group_nodes = []
        with outputs_detached(tree):
            for target in receiver_principled:
                node = _group_node(
                    tree,
                    group,
                    "CP77 Decal Composite",
                    (target.location.x - 520, target.location.y),
                    placed,
                )
                group_nodes.append(node.name)
                for name in inputs:
                    channel = name[len(_RECEIVER_PREFIX) :]
                    socket = _principled_input(target, channel)
                    value = socket_value(socket) if socket is not None else None
                    if channel == "Normal":
                        value = _receiver_normal(
                            tree,
                            value,
                            (target.location.x - 760, target.location.y - 200),
                        )
                    if value is not None:
                        assign_socket(links, value, node.inputs[name])
                for name in outputs:
                    if name == _COVERAGE_OUTPUT:
                        surface_coverage = surface_coverage or node.outputs[name]
                        continue
                    socket = _principled_input(target, name)
                    if socket is None:
                        continue
                    replace_link(links, node.outputs[name], socket)
            # Linked while detached, the masks leave the surfaces linked, so the shaders are not linked back.
            _mask_composite_surface(tree, surfaces, surface_coverage, placed)
            set_absolute_locations(tree, placed)
        # Other decals blending the same channels into this receiver copy this composite.
        cache[_composite_template_key(cache_key[0], group)] = (
            material,
            group,
            tuple(group_nodes),
        )
        if profile is not None:
            profile["composite_adapt_seconds"] += time.perf_counter() - phase_started
    phase_started = time.perf_counter() if profile is not None else 0.0
    material.surface_render_method = DECAL_RENDER_METHOD
    for name, value in (
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
                "_build_composite_material",
                "_build_composite_material skipped what it could not read or write",
                exc_info=True,
            )
    cache[cache_key] = material
    if profile is not None:
        profile["composite_finalize_seconds"] += time.perf_counter() - phase_started
    return material


def _decal_group_shape(decal, property_cache):
    """Everything a decal's composite group is built from except its copied values"""
    tree = decal.node_tree
    nodes = []
    for node in tree.nodes:
        schema = node.bl_rna.identifier
        settings = property_cache.get(schema)
        if settings is None:
            settings = property_cache[schema] = tuple(
                prop.identifier
                for prop in node.bl_rna.properties
                if prop.type in {"ENUM", "BOOLEAN"}
                and not prop.is_readonly
                and prop.identifier != "select"
            )
        entry = [
            node.name,
            node.bl_idname,
            node.label,
            tuple(getattr(node, name) for name in settings),
        ]
        group = getattr(node, "node_tree", None)
        entry.append(group.as_pointer() if group is not None else 0)
        if hasattr(node, "bundle_items"):
            entry.append(
                tuple((item.socket_type, item.name) for item in node.bundle_items)
            )
        if node.bl_idname == "ShaderNodeValToRGB":
            entry.append(len(node.color_ramp.elements))
        nodes.append(tuple(entry))
    links = tuple(
        (
            link.from_node.name,
            link.from_socket.identifier,
            link.to_node.name,
            link.to_socket.identifier,
        )
        for link in tree.links
    )
    principled = _principled_nodes(decal)[0]
    defaults = tuple(
        socket_value(socket) for socket in principled.inputs if not socket.is_linked
    )
    flags = (
        str(decal.get("cp77_decal_features", "[]")),
        str(decal.get("cp77_decal_family", "")),
        int(decal.get("normalBlendingMode", 0) or 0) > 0,
        float(decal.get("alpha", 1.0)),
    )
    return tuple(nodes), links, defaults, flags


def _copied_decal_group(entry, decal, name):
    """A copy of a built group of the same shape with decal's values, or None"""
    built, pairs = entry
    try:
        group = track_created_datablock("node_groups", built.copy())
    except ReferenceError:
        return None
    try:
        group.name = name
        group["cp77_decal_material"] = decal.name
        sources, targets = decal.node_tree.nodes, group.nodes
        property_cache = {}
        # Written with the outputs linked: nothing uses the new copy yet, and unlinking them would cost more edits
        # than the few writes it saves.
        for source_name, target_name in pairs:
            source, target = sources[source_name], targets[target_name]
            _clone_values(source, target, property_cache)
            _copy_socket_defaults(source.inputs, target.inputs)
            _copy_socket_defaults(source.outputs, target.outputs)
            _clone_special_values(source, target)
    except (AttributeError, KeyError, TypeError, ValueError):
        log_once(
            _LOG,
            logging.DEBUG,
            "_copied_decal_group",
            "_copied_decal_group skipped what it could not read or write",
            exc_info=True,
        )
        bpy.data.node_groups.remove(group)
        return None
    return group


def _decal_composite_group(decal, cache, profile=None):
    """The group that blends decal into any receiver"""
    key = ("COMPOSITE_GROUP", decal.as_pointer())
    group = cache.get(key)
    if group is not None:
        return group
    name = f"CP77 Decal Composite {hashlib.sha1(decal.name.encode('utf-8')).hexdigest()[:10]}"
    shape_key = (
        "COMPOSITE_GROUP_SHAPE",
        _decal_group_shape(decal, cache.setdefault("COMPOSITE_GROUP_SETTINGS", {})),
    )
    shape = cache.get(shape_key)
    group = _copied_decal_group(shape, decal, name) if shape is not None else None
    if group is None:
        group = track_created_datablock(
            "node_groups", bpy.data.node_groups.new(name, "ShaderNodeTree")
        )
        group["cp77_decal_material"] = decal.name
        incoming = group.nodes.new("NodeGroupInput")
        incoming.location = (-3200.0, 0.0)
        outgoing = group.nodes.new("NodeGroupOutput")
        outgoing.location = (400.0, 0.0)
        channels = _GroupChannels(group, incoming, outgoing)
        cloner = _DecalNodeCloner(decal.node_tree, group, profile)
        coverage = _blend_decal_channels(group, decal, cloner, [channels], profile)
        channels.connect(_COVERAGE_OUTPUT, coverage)
        cache[shape_key] = (
            group,
            tuple(
                (source.name, target.name) for source, target in cloner.nodes.items()
            ),
        )
    cache[key] = group
    return group


def _blend_decal_channels(tree, decal, cloner, targets, profile=None):
    """Blend the decal's channels into each of targets and return the surface coverage"""
    phase_started = time.perf_counter() if profile is not None else 0.0
    nodes, links = tree.nodes, tree.links
    source_principled = _principled_nodes(decal)[0]
    features = _features(decal)
    diffuse_factor = _factor_source(
        decal,
        cloner,
        (
            "DiffuseAlpha",
            "Projected Emissive Coverage",
            "Thresholded Emissive Alpha",
            "Animated Emissive Alpha",
            "Thresholded Emissive Mask",
        ),
        find_input(source_principled, "Alpha"),
        0.0,
    )
    normal_factor = _factor_source(
        decal,
        cloner,
        ("Normal Influence", "NormalAlpha", "Revealed Normal Growth"),
        None,
        0.0,
    )
    material_factor = _factor_source(
        decal,
        cloner,
        (
            "Roughness Metalness Influence",
            "Roughness Bias Influence",
            "Material Influence",
            "Wet Roughness Influence",
            "Roughness Metalness Alpha",
        ),
        None,
        0.0,
    )
    sector_alpha = float(decal.get("alpha", 1.0))
    diffuse_factor = _scale_factor(
        nodes,
        links,
        "Conformal Sector Diffuse Alpha",
        (-760, 260),
        diffuse_factor,
        sector_alpha,
    )
    projected_rnm = (
        decal.get("cp77_decal_family") == "projected"
        and int(decal.get("normalBlendingMode", 0) or 0) > 0
    )
    normal_factor = _scale_factor(
        nodes,
        links,
        "Conformal Sector Normal Alpha",
        (-760, 80),
        normal_factor,
        1.0 if projected_rnm else sector_alpha,
    )
    material_factor = _scale_factor(
        nodes,
        links,
        "Conformal Sector Material Alpha",
        (-760, -100),
        material_factor,
        sector_alpha,
    )
    if features & {"terrain", "forward"}:
        normal_factor = diffuse_factor
        material_factor = diffuse_factor

    active_factors = []
    if features & _COLOR_FEATURES:
        active_factors.append(diffuse_factor)
    if ("normal" in features or features & {"terrain", "forward"}) and find_input(
        source_principled, "Normal"
    ).is_linked:
        active_factors.append(normal_factor)
    if features & {"roughness", "roughness_bias", "metalness", "terrain", "forward"}:
        active_factors.append(material_factor)
    source_emission = find_input(source_principled, "Emission Color", "Emission")
    source_strength = find_input(source_principled, "Emission Strength")
    has_emission = (
        source_emission is not None
        and source_strength is not None
        and (
            source_emission.is_linked
            or any(float(value) != 0.0 for value in source_emission.default_value[:3])
        )
        and (source_strength.is_linked or float(source_strength.default_value) > 0.0)
    )
    if has_emission:
        emission_mask = _node_output(
            decal,
            (
                "Projected Emissive Coverage",
                "Thresholded Emissive Alpha",
                "Animated Emissive Alpha",
                "Thresholded Emissive Mask",
            ),
        )
        if emission_mask is None:
            emission_factor = _factor_source(
                decal,
                cloner,
                (),
                find_input(source_principled, "Alpha"),
                0.0,
                prefer_fallback=True,
            )
        else:
            emission_factor = _scale_factor(
                nodes,
                links,
                "Conformal Emission Coverage",
                (-1040, -840),
                cloner.clone_socket(emission_mask),
                sector_alpha,
            )
        active_factors.append(emission_factor)
    surface_coverage, diffuse_factor, normal_factor, material_factor = (
        surface_influence_sockets(
            tree,
            active_factors,
            sector_alpha,
            diffuse_factor,
            normal_factor,
            material_factor,
            projected=decal.get("cp77_decal_family") != "mesh",
        )
    )

    if profile is not None:
        profile["composite_factors_seconds"] += time.perf_counter() - phase_started
        phase_started = time.perf_counter()
    for target in targets:
        x, y = target.location
        decal_base = find_input(source_principled, "Base Color")
        if (
            target.present("Base Color")
            and decal_base is not None
            and features & _COLOR_FEATURES
        ):
            mixed = mix_color_socket(
                nodes,
                links,
                "Conformal Decal Base Color",
                target.value("Base Color"),
                cloner.clone_socket(decal_base.links[0].from_socket)
                if decal_base.is_linked
                else tuple(decal_base.default_value),
                diffuse_factor,
                (x - 420, y + 220),
            )
            target.connect("Base Color", mixed)

        decal_normal = find_input(source_principled, "Normal")
        normal_enabled = "normal" in features or bool(features & {"terrain", "forward"})
        if (
            target.present("Normal")
            and decal_normal is not None
            and decal_normal.is_linked
            and normal_enabled
        ):
            receiver_normal = target.value("Normal")
            decal_family = decal.get("cp77_decal_family")
            projected_family = decal_family == "projected"
            reoriented = int(decal.get("normalBlendingMode", 0) or 0) > 0
            decoder = _find_node(
                decal,
                ("NormalTexture DirectX Decode",),
            )
            sampled_tangent = (
                decoder.outputs.get("Tangent") if decoder is not None else None
            )
            if sampled_tangent is not None and (
                projected_family or (decal_family == "mesh" and reoriented)
            ):
                sampled_tangent = cloner.clone_socket(sampled_tangent)
                if reoriented:
                    projected_normal = reoriented_normal_socket(
                        tree,
                        receiver_normal,
                        sampled_tangent,
                        (x - 2860, y - 40),
                    )
                else:
                    projected_normal = projected_normal_socket(
                        tree,
                        sampled_tangent,
                        (x - 1820, y - 40),
                    )
            else:
                projected_normal = cloner.clone_socket(
                    decal_normal.links[0].from_socket
                )
            mixed = mix_normal_socket(
                tree,
                receiver_normal,
                projected_normal,
                normal_factor,
                (x - 520, y - 40),
            )
            target.connect("Normal", mixed)

        for socket_name, feature in (
            ("Roughness", "roughness"),
            ("Metallic", "metalness"),
        ):
            decal_socket = find_input(source_principled, socket_name)
            enabled = (
                feature in features
                or (feature == "roughness" and "roughness_bias" in features)
                or bool(features & {"terrain", "forward"})
            )
            if not target.present(socket_name) or decal_socket is None or not enabled:
                continue
            source = (
                cloner.clone_socket(decal_socket.links[0].from_socket)
                if decal_socket.is_linked
                else decal_socket.default_value
            )
            mixed = mix_scalar_socket(
                nodes,
                links,
                f"Conformal Decal {socket_name}",
                (x - 420, y - 220 if feature == "roughness" else y - 360),
                target.value(socket_name),
                source,
                material_factor,
            )
            target.connect(socket_name, mixed)

        decal_emission = find_input(source_principled, "Emission Color", "Emission")
        decal_strength = find_input(source_principled, "Emission Strength")
        if (
            target.present("Emission Color")
            and decal_emission is not None
            and target.present("Emission Strength")
            and decal_strength is not None
            and has_emission
        ):
            receiver_emission = target.value("Emission Color")
            receiver_strength = target.value("Emission Strength")
            decal_color = (
                cloner.clone_socket(decal_emission.links[0].from_socket)
                if decal_emission.is_linked
                else tuple(decal_emission.default_value)
            )
            decal_power = (
                cloner.clone_socket(decal_strength.links[0].from_socket)
                if decal_strength.is_linked
                else decal_strength.default_value
            )
            decal_power = shader_nodes.math(
                nodes,
                links,
                "DIVIDE",
                decal_power,
                surface_coverage,
                name="Conformal Normalized Emission Strength",
                location=(-1040, -980),
            )
            receiver_energy = new_labeled_node(
                nodes, "ShaderNodeMix", "Receiver Emission Energy", (x - 660, y - 520)
            )
            receiver_energy.data_type = "RGBA"
            receiver_energy.blend_type = "MULTIPLY"
            shader_nodes.socket_by_identifier(
                receiver_energy.inputs, "Factor_Float"
            ).default_value = 1.0
            assign_socket(
                links,
                receiver_emission,
                shader_nodes.socket_by_identifier(receiver_energy.inputs, "A_Color"),
            )
            assign_socket(
                links,
                receiver_strength,
                shader_nodes.socket_by_identifier(receiver_energy.inputs, "B_Color"),
            )
            decal_energy = new_labeled_node(
                nodes, "ShaderNodeMix", "Decal Emission Energy", (x - 660, y - 660)
            )
            decal_energy.data_type = "RGBA"
            decal_energy.blend_type = "MULTIPLY"
            shader_nodes.socket_by_identifier(
                decal_energy.inputs, "Factor_Float"
            ).default_value = 1.0
            assign_socket(
                links,
                decal_color,
                shader_nodes.socket_by_identifier(decal_energy.inputs, "A_Color"),
            )
            assign_socket(
                links,
                decal_power,
                shader_nodes.socket_by_identifier(decal_energy.inputs, "B_Color"),
            )
            added_color = new_labeled_node(
                nodes, "ShaderNodeMix", "Conformal Decal Emission", (x - 420, y - 520)
            )
            added_color.data_type = "RGBA"
            added_color.blend_type = "ADD"
            shader_nodes.socket_by_identifier(
                added_color.inputs, "Factor_Float"
            ).default_value = 1.0
            links.new(
                shader_nodes.socket_by_identifier(
                    receiver_energy.outputs, "Result_Color"
                ),
                shader_nodes.socket_by_identifier(added_color.inputs, "A_Color"),
            )
            links.new(
                shader_nodes.socket_by_identifier(decal_energy.outputs, "Result_Color"),
                shader_nodes.socket_by_identifier(added_color.inputs, "B_Color"),
            )
            added_strength = shader_nodes.math(
                nodes,
                links,
                "ADD",
                name="Conformal Decal Emission Strength",
                location=(x - 420, y - 660),
            ).node
            assign_socket(links, receiver_strength, added_strength.inputs["Value"])
            assign_socket(
                links,
                decal_power,
                shader_nodes.socket_by_identifier(added_strength.inputs, "Value_001"),
            )
            reciprocal = shader_nodes.math(
                nodes,
                links,
                "DIVIDE",
                name="Conformal Emission Normalization",
                location=(x - 200, y - 660),
            ).node
            reciprocal.inputs["Value"].default_value = 1.0
            links.new(
                added_strength.outputs["Value"],
                shader_nodes.socket_by_identifier(reciprocal.inputs, "Value_001"),
            )
            normalized = shader_nodes.vector_math(
                nodes,
                links,
                "SCALE",
                name="Normalized Conformal Emission",
                location=(x - 180, y - 520),
            ).node
            links.new(
                shader_nodes.socket_by_identifier(added_color.outputs, "Result_Color"),
                normalized.inputs["Vector"],
            )
            links.new(reciprocal.outputs["Value"], find_input(normalized, "Scale"))
            target.connect("Emission Color", normalized.outputs["Vector"])
            target.connect("Emission Strength", added_strength.outputs["Value"])

    if profile is not None:
        profile["composite_adapt_seconds"] += time.perf_counter() - phase_started
    return surface_coverage


def socket_value(socket):
    links = list(socket.links)
    if links:
        return links[0].from_socket
    value = getattr(socket, "default_value", None)
    try:
        return tuple(value)
    except TypeError:
        return value
