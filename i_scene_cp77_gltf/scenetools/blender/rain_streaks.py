from __future__ import annotations

import bpy

from ...blender.shader_nodes import math, new_node
from ...blender.transactions import track_created_datablock

SEED_ATTRIBUTE = "cp77_rain_seed"
# Progress through the fall: 0 where a streak enters the top of the band, 1 where it leaves the bottom.
PHASE_ATTRIBUTE = "cp77_rain_phase"
MATERIAL_NODE = "CP77 Rain Material"
_HALF_WIDTH_ATTRIBUTE = "cp77_rain_half_width"
# Each streak falls at this fraction of the fall speed or faster, set by its seed.
SLOWEST_FALL = 0.3


def _typed_output(node, socket_type):
    return next(
        socket
        for socket in node.outputs
        if socket.type == socket_type
        and getattr(socket, "enabled", True)
        and not getattr(socket, "is_unavailable", False)
    )


def _random(tree, name, seed, data_type, socket_type, location):
    node = new_node(tree, "FunctionNodeRandomValue", name, location)
    node.data_type = data_type
    node.inputs["Seed"].default_value = int(seed)
    return _typed_output(node, socket_type)


def _store(tree, geometry, name, value, location):
    node = new_node(
        tree, "GeometryNodeStoreNamedAttribute", f"CP77 Store {name}", location
    )
    node.data_type = "FLOAT"
    node.domain = "POINT"
    node.inputs["Name"].default_value = name
    tree.links.new(geometry, node.inputs["Geometry"])
    tree.links.new(value, node.inputs["Value"])
    return node.outputs["Geometry"]


def rain_streak_group(name, spec, material):
    """Group drawing falling rain streaks"""
    group = track_created_datablock(
        "node_groups", bpy.data.node_groups.new(name, "GeometryNodeTree")
    )
    group.interface.new_socket(
        name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry"
    )
    group.interface.new_socket(
        name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry"
    )
    tree = group
    new_node(tree, "NodeGroupInput", "CP77 Rain Input", (-1800, 0))
    output = new_node(tree, "NodeGroupOutput", "CP77 Rain Output", (1700, 0))
    seed = int(spec["seed"])
    radius = float(spec["radius"])
    bottom = float(spec["z_min"])
    band = float(spec["z_max"]) - bottom
    fall_speed = float(spec["fall_speed"])
    length_min, length_max = (float(value) for value in spec["length_range"])
    width_min, width_max = (float(value) for value in spec["width_range"])

    placement = _random(
        tree, "CP77 Rain Placement", seed, "FLOAT_VECTOR", "VECTOR", (-1600, 300)
    )
    streak_seed = _random(
        tree, "CP77 Rain Streak Seed", seed + 1, "FLOAT", "VALUE", (-1600, 0)
    )
    width_pick = _random(
        tree, "CP77 Rain Width Pick", seed + 2, "FLOAT", "VALUE", (-1600, -300)
    )
    split = new_node(
        tree, "ShaderNodeSeparateXYZ", "CP77 Rain Placement XYZ", (-1400, 300)
    )
    tree.links.new(placement, split.inputs["Vector"])
    nodes, links = tree.nodes, tree.links
    x = math(
        nodes,
        links,
        "MULTIPLY_ADD",
        split.outputs["X"],
        2.0 * radius,
        -radius,
        name="CP77 Rain X",
        location=(-1200, 450),
    )
    y = math(
        nodes,
        links,
        "MULTIPLY_ADD",
        split.outputs["Y"],
        2.0 * radius,
        -radius,
        name="CP77 Rain Y",
        location=(-1200, 300),
    )

    speed = math(
        nodes,
        links,
        "MULTIPLY_ADD",
        streak_seed,
        (1.0 - SLOWEST_FALL) * fall_speed,
        SLOWEST_FALL * fall_speed,
        name="CP77 Rain Fall Speed",
        location=(-1400, 0),
    )
    seconds = new_node(
        tree, "GeometryNodeInputSceneTime", "CP77 Rain Time", (-1400, -150)
    ).outputs["Seconds"]
    travel = math(
        nodes,
        links,
        "MULTIPLY",
        speed,
        seconds,
        name="CP77 Rain Travel",
        location=(-1200, 0),
    )
    travel = math(
        nodes,
        links,
        "DIVIDE",
        travel,
        band,
        name="CP77 Rain Travel In Band",
        location=(-1050, 0),
    )
    progress = math(
        nodes,
        links,
        "ADD",
        split.outputs["Z"],
        travel,
        name="CP77 Rain Fall Start",
        location=(-900, 150),
    )
    progress = math(
        nodes,
        links,
        "FRACT",
        progress,
        name="CP77 Rain Fall Progress",
        location=(-750, 150),
    )
    z = math(
        nodes,
        links,
        "MULTIPLY_ADD",
        progress,
        -band,
        bottom + band,
        name="CP77 Rain Z",
        location=(-600, 150),
    )
    position = new_node(tree, "ShaderNodeCombineXYZ", "CP77 Rain Position", (-400, 300))
    tree.links.new(x, position.inputs["X"])
    tree.links.new(y, position.inputs["Y"])
    tree.links.new(z, position.inputs["Z"])
    points = new_node(tree, "GeometryNodePoints", "CP77 Rain Points", (-200, 300))
    points.inputs["Count"].default_value = int(spec["count"])
    tree.links.new(position.outputs["Vector"], points.inputs["Position"])

    length = math(
        nodes,
        links,
        "MULTIPLY_ADD",
        streak_seed,
        0.75 * (length_max - length_min),
        length_min + 0.25 * (length_max - length_min),
        name="CP77 Rain Length",
        location=(-1200, -450),
    )
    half_width = math(
        nodes,
        links,
        "MULTIPLY_ADD",
        width_pick,
        0.5 * (width_max - width_min),
        0.5 * width_min,
        name="CP77 Rain Half Width",
        location=(-1200, -300),
    )
    geometry = _store(
        tree, points.outputs["Points"], SEED_ATTRIBUTE, streak_seed, (0, 300)
    )
    geometry = _store(tree, geometry, PHASE_ATTRIBUTE, progress, (200, 300))
    geometry = _store(tree, geometry, _HALF_WIDTH_ATTRIBUTE, half_width, (400, 300))

    line = new_node(
        tree, "GeometryNodeCurvePrimitiveLine", "CP77 Rain Streak", (400, 0)
    )
    line.inputs["End"].default_value = (0.0, 0.0, 1.0)
    scale = new_node(
        tree, "ShaderNodeCombineXYZ", "CP77 Rain Streak Scale", (400, -200)
    )
    scale.inputs["X"].default_value = 1.0
    scale.inputs["Y"].default_value = 1.0
    tree.links.new(length, scale.inputs["Z"])
    streaks = new_node(
        tree, "GeometryNodeInstanceOnPoints", "CP77 Rain Streaks", (700, 200)
    )
    tree.links.new(geometry, streaks.inputs["Points"])
    tree.links.new(line.outputs["Curve"], streaks.inputs["Instance"])
    tree.links.new(scale.outputs["Vector"], streaks.inputs["Scale"])
    realize = new_node(
        tree, "GeometryNodeRealizeInstances", "CP77 Rain Realize", (900, 200)
    )
    tree.links.new(streaks.outputs["Instances"], realize.inputs["Geometry"])
    width = new_node(
        tree, "GeometryNodeInputNamedAttribute", "CP77 Rain Width", (900, -100)
    )
    width.data_type = "FLOAT"
    width.inputs["Name"].default_value = _HALF_WIDTH_ATTRIBUTE
    radius_node = new_node(
        tree, "GeometryNodeSetCurveRadius", "CP77 Rain Radius", (1100, 200)
    )
    tree.links.new(realize.outputs["Geometry"], radius_node.inputs["Curve"])
    tree.links.new(width.outputs["Attribute"], radius_node.inputs["Radius"])
    material_node = new_node(
        tree, "GeometryNodeSetMaterial", MATERIAL_NODE, (1300, 200)
    )
    material_node.inputs["Material"].default_value = material
    tree.links.new(radius_node.outputs["Curve"], material_node.inputs["Geometry"])
    tree.links.new(material_node.outputs["Geometry"], output.inputs["Geometry"])
    return group


def set_streak_material(group, material):
    """Point the group's streaks at material (after the material was rebuilt)"""
    node = group.nodes.get(MATERIAL_NODE) if group is not None else None
    if node is not None and node.inputs["Material"].default_value is not material:
        node.inputs["Material"].default_value = material
