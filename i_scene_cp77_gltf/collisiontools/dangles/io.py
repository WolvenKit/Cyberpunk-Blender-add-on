import json
import os
import re
from json.decoder import scanstring

import bpy

from .sim import spaces

EDITOR_FORMAT = "DanglePhysicsEditor"
EDITOR_VERSION = 13

LINK_MAP = {
    "KeepFixedDistance": "FIXED",
    "KeepVariableDistance": "VARIABLE",
    "Greater": "GREATER",
    "Closer": "CLOSER",
}
PROJ_MAP = {
    "Disabled": "DISABLED",
    "ShortestPath": "SHORTEST_PATH",
    "Directed": "DIRECTED",
    "Directional": "DIRECTIONAL",
}
PEND_MAP = {
    "Cone": "CONE",
    "HingePlane": "HINGE_PLANE",
    "HalfCone": "HALF_CONE",
}
PEND_PROJ_MAP = {
    "Disabled": "DISABLED",
    "ShortestPathRotational": "SHORTEST_PATH_ROTATIONAL",
    "DirectedRotational": "DIRECTED_ROTATIONAL",
}

def _get_wk(node, key, default=None):
    if not isinstance(node, dict):
        return default
    if key in node:
        return node[key]
    if f"m_{key}" in node:
        return node[f"m_{key}"]
    return default

def _get_bone_name(node_dict, key):
    b_dict = _get_wk(node_dict, key, {})
    name_obj = _get_wk(b_dict, "name", {})
    val = name_obj.get("$value", "") if isinstance(name_obj, dict) else name_obj
    return str(val) if val else ""

def _iter_nested_values(root):
    stack = [root]
    while stack:
        value = stack.pop()
        yield value
        if isinstance(value, dict):
            for key in reversed(value):
                stack.append(value[key])
        elif isinstance(value, list):
            stack.extend(reversed(value))


def _build_handle_map(obj, node_map):
    for value in _iter_nested_values(obj):
        if isinstance(value, dict) and "HandleId" in value and "Data" in value:
            node_map[value["HandleId"]] = value["Data"]

def _resolve_handle(obj, node_map):
    if not isinstance(obj, dict):
        return obj
    if "HandleRefId" in obj:
        handle_id = obj["HandleRefId"]
        return node_map.get(handle_id, node_map.get(str(handle_id), {}))
    if "Data" in obj:
        return obj["Data"]
    return obj


def _build_handle_maps(obj):
    node_map = {}
    node_ids = {}
    for value in _iter_nested_values(obj):
        if not isinstance(value, dict):
            continue
        data = value.get("Data")
        if "HandleId" not in value or not isinstance(data, dict):
            continue
        handle_id = str(value["HandleId"])
        node_map[handle_id] = data
        node_ids[id(data)] = handle_id
    return node_map, node_ids


def _node_identity(reference, data, node_ids):
    if isinstance(reference, dict):
        if "HandleId" in reference:
            return f"handle:{reference['HandleId']}"
        if "HandleRefId" in reference:
            return f"handle:{reference['HandleRefId']}"
    handle_id = node_ids.get(id(data))
    return f"handle:{handle_id}" if handle_id is not None else f"inline:{id(data)}"


def _pose_link_target(value, node_map):
    resolved = _resolve_handle(value, node_map)
    if not isinstance(resolved, dict):
        return None
    if resolved.get("$type") != "animPoseLink":
        return None
    return _get_wk(resolved, "node", None)


def _static_switch_branch(node):
    """Return the runtime pose branch for an unevaluated StaticSwitch.

    Static switches are driven by engine-side conditions such as visual tags.
    The editor has no runtime condition context, so the engine-compatible
    neutral state is the False branch. Both branches are still imported as
    authoring data; this only controls graph evaluation order.
    """
    return _get_wk(node, "False", None)


def _iter_pose_inputs(node, node_map):
    if not isinstance(node, dict):
        return

    if node.get("$type") == "animAnimNode_StaticSwitch":
        target = _pose_link_target(_static_switch_branch(node), node_map)
        if target is not None:
            yield target
        return

    for _key, value in node.items():
        target = _pose_link_target(value, node_map)
        if target is not None:
            yield target
            continue
        if isinstance(value, list):
            for item in value:
                target = _pose_link_target(item, node_map)
                if target is not None:
                    yield target


def _collect_graph_operations(data, node_map, node_ids, nodes_by_type=None):
    nodes_by_type = nodes_by_type or {}
    roots = nodes_by_type.get("animAnimNode_Root")
    if roots is None:
        roots = _find_nodes_by_type(data, "animAnimNode_Root")
    start_nodes = []
    for root_index, root in enumerate(roots):
        for node_index, reference in enumerate(_get_wk(root, "nodes", [])):
            resolved = _resolve_handle(reference, node_map)
            if isinstance(resolved, dict) and resolved.get("$type") == "animAnimNode_Output":
                start_nodes.append((reference, f"root[{root_index}].nodes[{node_index}]"))
        output_target = _pose_link_target(_get_wk(root, "outputNode", None), node_map)
        if output_target is not None:
            start_nodes.append((output_target, f"root[{root_index}].outputNode"))

    if not start_nodes:
        outputs = nodes_by_type.get("animAnimNode_Output")
        if outputs is None:
            outputs = _find_nodes_by_type(data, "animAnimNode_Output")
        for output_index, output in enumerate(outputs):
            start_nodes.append((output, f"output[{output_index}]"))

    operations = []
    visited = set()
    visiting = set()

    for reference, path in start_nodes:
        stack = [(reference, path, False)]
        while stack:
            current_reference, current_path, expanded = stack.pop()
            node = _resolve_handle(current_reference, node_map)
            if not isinstance(node, dict):
                continue
            identity = _node_identity(current_reference, node, node_ids)

            if expanded:
                if identity not in visiting:
                    continue
                visiting.remove(identity)
                if identity in visited:
                    continue
                visited.add(identity)
                node_type = node.get("$type")
                if node_type == "animAnimNode_Dangle":
                    operations.append(("DANGLE", node, identity, current_path))
                elif node_type == "animAnimNode_Drag":
                    operations.append(("DRAG", node, identity, current_path))
                continue

            if identity in visited or identity in visiting:
                continue

            visiting.add(identity)
            stack.append((current_reference, current_path, True))
            children = list(_iter_pose_inputs(node, node_map))
            for input_index in range(len(children) - 1, -1, -1):
                stack.append((
                    children[input_index],
                    f"{current_path}.input[{input_index}]",
                    False,
                ))

    return operations

def _find_nodes_by_types(data, target_types):
    targets = set(target_types)
    results = {target_type: [] for target_type in targets}
    for value in _iter_nested_values(data):
        if not isinstance(value, dict):
            continue
        node_type = value.get("$type")
        if node_type in results:
            results[node_type].append(value)
    return results


def _find_nodes_by_type(data, target_type):
    return _find_nodes_by_types(data, (target_type,))[target_type]

def _parse_quat(q_dict):
    if not isinstance(q_dict, dict):
        return (1.0, 0.0, 0.0, 0.0)
    return (
        float(q_dict.get("r", 1.0)),
        float(q_dict.get("i", 0.0)),
        float(q_dict.get("j", 0.0)),
        float(q_dict.get("k", 0.0)),
    )

def _quat_wxyz_to_ijkr(q):
    return (q[1], q[2], q[3], q[0])

def _parse_vec3(v_dict, default=(0.0, 0.0, 0.0)):
    if not isinstance(v_dict, dict):
        return default
    return (
        float(v_dict.get("X", default[0])),
        float(v_dict.get("Y", default[1])),
        float(v_dict.get("Z", default[2])),
    )

def _quat_ijkr_to_wxyz(value, default=(1.0, 0.0, 0.0, 0.0)):
    if isinstance(value, dict):
        return (
            float(value.get("r", default[0])),
            float(value.get("i", default[1])),
            float(value.get("j", default[2])),
            float(value.get("k", default[3])),
        )
    if isinstance(value, (list, tuple)) and len(value) >= 4:
        return (float(value[3]), float(value[0]), float(value[1]), float(value[2]))
    return default


def _sequence(value, size, default):
    if not isinstance(value, (list, tuple)) or len(value) < size:
        return default
    return tuple(float(value[i]) for i in range(size))


def _shape_type_from_extents(extents):
    nonzero = sum(abs(float(value)) > 1e-8 for value in extents)
    if nonzero == 0:
        return "SPHERE"
    if nonzero == 1:
        return "CAPSULE"
    return "ROUNDED_BOX"


def _shape_key_values(bone, radius, extents, offset, rotation):
    return (
        bone,
        *(round(float(v), 7) for v in offset),
        *(round(float(v), 7) for v in rotation),
        round(float(radius), 7),
        *(round(float(v), 7) for v in extents),
    )


def _shape_key(shape):
    return _shape_key_values(
        shape.bone_name, shape.radius,
        (shape.x_box_extent, shape.y_box_extent, shape.height_extent),
        shape.offset_ls, shape.rotation_ls_quat,
    )


def _add_collision_shape(collection, values, existing=None):
    key = _shape_key_values(
        values["bone"], values["radius"], values["extents"],
        values["offset"], values["rotation"],
    )
    if existing is None:
        existing = {_shape_key(shape) for shape in collection}
    if key in existing:
        return None

    shape = collection.add()
    shape.name = values["name"]
    shape.bone_name = values["bone"]
    shape.shape_type = values["shape_type"]
    shape.radius = values["radius"]
    shape.x_box_extent, shape.y_box_extent, shape.height_extent = values["extents"]
    shape.offset_ls = values["offset"]
    shape.rotation_ls_quat = values["rotation"]
    existing.add(key)
    return shape


def _bone_prefix(name):
    return name.rsplit("_", 1)[0] if "_" in name else name

def _extract_dangle_info(dangle_node, node_map):
    constraint_ref = _get_wk(dangle_node, "dangleConstraint", {})
    sim_data = _resolve_handle(constraint_ref, node_map)
    if not sim_data:
        return None

    sim_type = sim_data.get("$type")
    if sim_type == "animDangleConstraint_SimulationDyng":
        container = _get_wk(sim_data, "particlesContainer", {})
        particles_array = _get_wk(container, "particles", [])
        bone_set = frozenset(
            _get_bone_name(p, "bone")
            for p in particles_array
            if _get_bone_name(p, "bone")
        )
    elif sim_type in {
        "animDangleConstraint_SimulationPositionProjection",
        "animDangleConstraint_SimulationSpring",
        "animDangleConstraint_SimulationPendulum",
    }:
        bone_name = _get_bone_name(sim_data, "dangleBone")
        bone_set = frozenset((bone_name,)) if bone_name else frozenset()
    else:
        return None

    return (dangle_node, sim_data, bone_set, sim_type)

def _make_node_label(sim_data, dangle_node, bone_set, index):
    sim_type = sim_data.get("$type")
    iters = int(_get_wk(sim_data, "solverIterations", 1))
    container = _get_wk(sim_data, "particlesContainer", {})
    particles = _get_wk(container, "particles", [])
    n_particles = len(particles) if particles else len(bone_set)

    rotate = bool(_get_wk(sim_data, "rotateParentToLookAtDangle", 1))

    if sim_type == "animDangleConstraint_SimulationPositionProjection":
        kind = "position_projection"
    elif sim_type == "animDangleConstraint_SimulationSpring":
        kind = "spring"
    elif sim_type == "animDangleConstraint_SimulationPendulum":
        kind = "pendulum"
    elif n_particles <= 2:
        kind = "muscle"
    elif iters >= 3 and rotate:
        kind = "structural"
    else:
        kind = "jiggle"

    if bone_set:
        stripped = sorted(
            n.lstrip("lr").lstrip("_") if n[:2] in ("l_", "r_") else n
            for n in bone_set
        )
        prefix = os.path.commonprefix(stripped)
        sep_idx = prefix.rfind("_")
        if sep_idx > 0:
            prefix = prefix[:sep_idx]
        if len(prefix) > 25:
            prefix = prefix[:25]
        if not prefix:
            prefix = stripped[0].rsplit("_", 2)[0] if stripped else "unknown"
    else:
        prefix = "unknown"

    return f"{kind}_{n_particles}p_i{iters}_{prefix}"

def _parse_dangle_as_node(dangle_node, sim_data, addon_state, node_map, node_label):
    raw_substep = float(_get_wk(sim_data, "substepTime", 0.01))
    node_substep = max(0.005, min(0.1, raw_substep))
    raw_iters = int(_get_wk(sim_data, "solverIterations", 1))
    node_iters = max(1, min(8, raw_iters))
    node_alpha = float(_get_wk(sim_data, "alpha", 1.0))
    node_rotate = bool(_get_wk(sim_data, "rotateParentToLookAtDangle", 1))

    sim_type = sim_data.get("$type")
    is_dyng = sim_type == "animDangleConstraint_SimulationDyng"
    container = _get_wk(sim_data, "particlesContainer", {}) if is_dyng else {}

    force_owner = container if is_dyng else sim_data
    grav = _get_wk(force_owner, "gravityWS", 9.81)
    grav_val = float(grav.get("Z", 9.81)) if isinstance(grav, dict) else float(grav)
    ext_force = _get_wk(force_owner, "externalForceWS", {})
    ef = _parse_vec3(ext_force) if isinstance(ext_force, dict) else (0.0, 0.0, 0.0)

    if is_dyng:
        if (
            bpy.context and bpy.context.scene
            and hasattr(bpy.context.scene, "physx")
            and abs(grav_val) > abs(bpy.context.scene.physx.gravity[2])
        ):
            bpy.context.scene.physx.gravity[2] = -abs(grav_val)
        if any(abs(v) > 0 for v in ef):
            addon_state.external_force_ws = ef
        if node_substep < addon_state.substep_time:
            addon_state.substep_time = node_substep
        if node_iters > addon_state.solver_iterations:
            addon_state.solver_iterations = node_iters

    dnode = addon_state.dangle_nodes.add()
    dnode.name = node_label
    dnode.alpha = node_alpha
    dnode.rotate_parent_to_look_at = node_rotate
    dnode.substep_time = node_substep
    dnode.solver_iterations = node_iters
    dnode.imported_solver_iterations = raw_iters
    dnode.gravity_ws = abs(grav_val)
    dnode.external_force_ws = ef
    inherited_flag_default = (
        0 if sim_data.get("$type") == "animDangleConstraint_SimulationDyng"
        else 1
    )
    dnode.parent_rotation_alters_dangle_children = bool(
        _get_wk(
            sim_data,
            "parentRotationAltersTransformsOfDangleAndItsChildren",
            inherited_flag_default,
        )
    )
    dnode.parent_rotation_alters_non_dangle_children = bool(
        _get_wk(
            sim_data,
            "parentRotationAltersTransformsOfNonDanglesAndItsChildren",
            inherited_flag_default,
        )
    )
    dnode.dangle_alters_children = bool(
        _get_wk(
            sim_data,
            "dangleAltersTransformsOfItsChildren",
            inherited_flag_default,
        )
    )

    dnode_idx = len(addon_state.dangle_nodes) - 1

    global_shape_keys = {_shape_key(shape) for shape in addon_state.collision_shapes}
    node_shape_keys = {_shape_key(shape) for shape in dnode.collision_shapes}
    shapes_raw = _get_wk(sim_data, "collisionRoundedShapes", [])
    for si, s_raw in enumerate(shapes_raw):
        bone = _get_bone_name(s_raw, "bone")
        t_ls = _get_wk(s_raw, "transformLS", {})
        x_ext = float(_get_wk(s_raw, "xBoxExtent", 0.0))
        y_ext = float(_get_wk(s_raw, "yBoxExtent", 0.0))
        z_ext = float(_get_wk(s_raw, "zBoxExtent", 0.0))
        values = {
            "name": f"Shape_{bone}_{si}",
            "bone": bone,
            "shape_type": _shape_type_from_extents((x_ext, y_ext, z_ext)),
            "radius": float(_get_wk(s_raw, "roundedCornerRadius", 0.05)),
            "extents": (x_ext, y_ext, z_ext),
            "offset": _parse_vec3(_get_wk(t_ls, "Translation", {})),
            "rotation": _parse_quat(_get_wk(t_ls, "Rotation", {})),
        }
        _add_collision_shape(dnode.collision_shapes, values, node_shape_keys)
        _add_collision_shape(addon_state.collision_shapes, values, global_shape_keys)

    if sim_data.get("$type") == "animDangleConstraint_SimulationPositionProjection":
        bone_name = _get_bone_name(sim_data, "dangleBone")
        chain = dnode.chains.add()
        chain.name = _bone_prefix(bone_name) if bone_name else "position_projection"
        chain.solver = "PBD"
        particle = chain.particles.add()
        particle.bone_name = bone_name
        particle.is_pinned = True
        particle.capsule_radius = float(
            _get_wk(sim_data, "collisionCapsuleRadius", 0.0)
        )
        particle.capsule_height = float(
            _get_wk(sim_data, "collisionCapsuleHeightExtent", 0.0)
        )
        particle.capsule_axis_ls = _parse_vec3(
            _get_wk(sim_data, "collisionCapsuleAxisLS", {}),
            default=(0.5, 0.0, 0.0),
        )
        raw_projection = str(
            _get_wk(sim_data, "projectionType", "ShortestPath")
        )
        particle.pos_projection_type = PROJ_MAP.get(
            raw_projection, "SHORTEST_PATH"
        )
        particle.direction_reference_bone = _get_bone_name(
            sim_data, "directionReferenceBone"
        )
        dnode.look_at_axis = (1.0, 0.0, 0.0)
        return dnode_idx

    if sim_type == "animDangleConstraint_SimulationSpring":
        bone_name = _get_bone_name(sim_data, "dangleBone")
        chain = dnode.chains.add()
        chain.name = _bone_prefix(bone_name) if bone_name else "spring"
        chain.solver = "SPRING"
        particle = chain.particles.add()
        particle.bone_name = bone_name
        particle.is_pinned = False
        particle.mass = float(_get_wk(sim_data, "mass", 1.0))
        particle.damping = float(_get_wk(sim_data, "damping", 1.0))
        particle.pull_force = float(_get_wk(sim_data, "pullForceFactor", 0.0))
        particle.spring_simulation_fps = float(
            _get_wk(sim_data, "simulationFps", 10.0)
        )
        particle.spring_constraint_radius = float(
            _get_wk(sim_data, "constraintSphereRadius", 0.5)
        )
        particle.spring_constraint_scale1 = float(
            _get_wk(sim_data, "constraintScale1", 1.0)
        )
        particle.spring_constraint_scale2 = float(
            _get_wk(sim_data, "constraintScale2", 1.0)
        )
        orientation = _get_wk(sim_data, "constraintOrientation", {})
        particle.spring_constraint_orientation = (
            float(_get_wk(orientation, "X", 0.0)),
            float(_get_wk(orientation, "Y", 90.0)),
        )
        particle.spring_pull_force_origin_ls = _parse_vec3(
            _get_wk(sim_data, "pullForceOriginLS", {})
        )
        raw_projection = str(
            _get_wk(sim_data, "projectionType", "ShortestPath")
        )
        particle.spring_projection_type = PROJ_MAP.get(
            raw_projection, "SHORTEST_PATH"
        )
        particle.spring_collision_radius = float(
            _get_wk(sim_data, "collisionSphereRadius", 0.0)
        )
        dnode.look_at_axis = (1.0, 0.0, 0.0)
        return dnode_idx

    if sim_type == "animDangleConstraint_SimulationPendulum":
        bone_name = _get_bone_name(sim_data, "dangleBone")
        chain = dnode.chains.add()
        chain.name = _bone_prefix(bone_name) if bone_name else "pendulum"
        chain.solver = "PENDULUM"
        particle = chain.particles.add()
        particle.bone_name = bone_name
        particle.is_pinned = False
        particle.mass = float(_get_wk(sim_data, "mass", 1.0))
        particle.damping = float(_get_wk(sim_data, "damping", 1.0))
        particle.pull_force = float(_get_wk(sim_data, "pullForceFactor", 0.0))
        particle.pendulum_simulation_fps = float(
            _get_wk(sim_data, "simulationFps", 10.0)
        )
        particle.pendulum_constraint_type = PEND_MAP.get(
            str(_get_wk(sim_data, "constraintType", "Cone")), "CONE"
        )
        particle.pendulum_half_aperture_angle = float(
            _get_wk(sim_data, "halfOfMaxApertureAngle", 45.0)
        )
        orientation = _get_wk(sim_data, "constraintOrientation", {})
        particle.pendulum_constraint_orientation = (
            float(_get_wk(orientation, "X", 90.0)),
            float(_get_wk(orientation, "Y", 0.0)),
            float(_get_wk(orientation, "Z", 0.0)),
        )
        particle.pendulum_pull_force_direction_ls = _parse_vec3(
            _get_wk(sim_data, "pullForceDirectionLS", {})
        )
        particle.pendulum_projection_type = PEND_PROJ_MAP.get(
            str(_get_wk(sim_data, "projectionType", "ShortestPathRotational")),
            "SHORTEST_PATH_ROTATIONAL",
        )
        particle.pendulum_collision_radius = float(
            _get_wk(sim_data, "collisionCapsuleRadius", 0.0)
        )
        particle.pendulum_collision_height = float(
            _get_wk(sim_data, "collisionCapsuleHeightExtent", 0.0)
        )
        dnode.look_at_axis = (1.0, 0.0, 0.0)
        return dnode_idx

    particles_array = _get_wk(container, "particles", [])

    chain_groups = {}
    chain_order = []

    for p_raw in particles_array:
        b_name = _get_bone_name(p_raw, "bone")
        if not b_name:
            continue
        pfx = _bone_prefix(b_name)
        if pfx not in chain_groups:
            chain_groups[pfx] = []
            chain_order.append(pfx)
        chain_groups[pfx].append(p_raw)

    particle_lookup = {}

    for pfx in chain_order:
        ch = dnode.chains.add()
        ch.name = pfx
        ch.solver = "DYNG"
        ch_idx = len(dnode.chains) - 1

        for p_raw in chain_groups[pfx]:
            b_name = _get_bone_name(p_raw, "bone")
            p = ch.particles.add()
            p.bone_name = b_name
            p.mass = float(_get_wk(p_raw, "mass", 1.0))
            p.damping = float(_get_wk(p_raw, "damping", 1.0))
            p.pull_force = float(_get_wk(p_raw, "pullForceFactor", 0.0))
            p.is_pinned = not bool(_get_wk(p_raw, "isFree", 1))
            p.capsule_radius = float(
                _get_wk(p_raw, "collisionCapsuleRadius", 0.0)
            )
            p.capsule_height = float(
                _get_wk(p_raw, "collisionCapsuleHeightExtent", 0.0)
            )
            axis_raw = _get_wk(p_raw, "collisionCapsuleAxisLS", {})
            p.capsule_axis_ls = _parse_vec3(axis_raw, default=(0.5, 0.0, 0.0))
            raw_proj = str(_get_wk(p_raw, "projectionType", "ShortestPath"))
            p.dyng_projection_type = PROJ_MAP.get(raw_proj, "SHORTEST_PATH")

            particle_lookup[b_name] = (ch_idx, len(ch.particles) - 1)

    dyng_ref = _get_wk(sim_data, "dyngConstraint", {})
    multi_node = _resolve_handle(dyng_ref, node_map)

    if multi_node.get("$type") == "animDyngConstraintMulti":
        inner_refs = _get_wk(multi_node, "innerConstraints", [])
        for ref in inner_refs:
            c_node = _resolve_handle(ref, node_map)
            c_type = c_node.get("$type")

            if c_type == "animDyngConstraintLink":
                b1 = _get_bone_name(c_node, "bone1")
                b2 = _get_bone_name(c_node, "bone2")
                if b1 in particle_lookup:
                    ci, pi = particle_lookup[b1]
                    target_p = dnode.chains[ci].particles[pi]
                    lnk = target_p.link_constraints.add()
                    lnk.target_bone = b2
                    lnk.link_type = LINK_MAP.get(
                        str(_get_wk(c_node, "linkType", "KeepFixedDistance")),
                        "FIXED",
                    )
                    lnk.lower_ratio = float(
                        _get_wk(c_node, "lengthLowerBoundRatioPercentage", 100.0)
                    )
                    lnk.upper_ratio = float(
                        _get_wk(c_node, "lengthUpperBoundRatioPercentage", 100.0)
                    )
                    la_raw = _get_wk(c_node, "lookAtAxis", {})
                    re_axis = _parse_vec3(la_raw, default=(1.0, 0.0, 0.0))
                    lnk.look_at_axis = re_axis
                    order = dnode.constraint_order.add()
                    order.constraint_type = "LINK"
                    order.particle_bone = b1
                    order.constraint_index = len(target_p.link_constraints) - 1

            elif c_type == "animDyngConstraintCone":
                b_attach = _get_bone_name(c_node, "coneAttachmentBone")
                b_constrained = _get_bone_name(c_node, "constrainedBone")
                if b_constrained in particle_lookup:
                    ci, pi = particle_lookup[b_constrained]
                    target_p = dnode.chains[ci].particles[pi]
                    pen = target_p.pendulum_constraints.add()
                    pen.target_bone = b_attach
                    pen.constraint_type = PEND_MAP.get(
                        str(_get_wk(c_node, "constraintType", "Cone")),
                        "CONE",
                    )
                    pen.half_aperture_angle = float(
                        _get_wk(c_node, "halfOfMaxApertureAngle", 45.0)
                    )
                    raw_pproj = str(_get_wk(c_node, "projectionType", "Disabled"))
                    pen.projection_type = PEND_PROJ_MAP.get(raw_pproj, "DISABLED")
                    pen.cone_collision_radius = float(
                        _get_wk(c_node, "collisionCapsuleRadius", 0.0)
                    )
                    pen.cone_collision_height = float(
                        _get_wk(c_node, "collisionCapsuleHeightExtent", 0.0)
                    )
                    ct_raw = _get_wk(c_node, "coneTransformLS", {})
                    rot_raw = _get_wk(ct_raw, "Rotation", {})
                    pen.cone_transform_ls_quat = _parse_quat(rot_raw)
                    pen.cone_transform_ls_offset = _parse_vec3(
                        _get_wk(ct_raw, "Translation", {})
                    )
                    order = dnode.constraint_order.add()
                    order.constraint_type = "CONE"
                    order.particle_bone = b_constrained
                    order.constraint_index = len(target_p.pendulum_constraints) - 1

            elif c_type == "animDyngConstraintEllipsoid":
                b_name = _get_bone_name(c_node, "bone")
                if b_name in particle_lookup:
                    ci, pi = particle_lookup[b_name]
                    target_p = dnode.chains[ci].particles[pi]
                    ell = target_p.ellipsoid_constraints.add()
                    ell.target_bone = b_name
                    ell.radius = float(_get_wk(c_node, "constraintRadius", 0.1))
                    ell.scale1 = float(_get_wk(c_node, "constraintScale1", 1.0))
                    ell.scale2 = float(_get_wk(c_node, "constraintScale2", 1.0))
                    exf = _get_wk(c_node, "ellipsoidTransformLS", {})
                    if exf:
                        rot_raw = _get_wk(exf, "Rotation", {})
                        ell.ellipsoid_transform_ls_quat = _parse_quat(rot_raw)
                        trans_raw = _get_wk(exf, "Translation", {})
                        ell.ellipsoid_transform_ls_offset = _parse_vec3(trans_raw)
                    order = dnode.constraint_order.add()
                    order.constraint_type = "ELLIPSOID"
                    order.particle_bone = b_name
                    order.constraint_index = len(target_p.ellipsoid_constraints) - 1

    return dnode_idx

def _parse_drag_node(raw, addon_state):
    source = _get_bone_name(raw, "sourceBone")
    target = _get_bone_name(raw, "outTargetBone") or source
    if not source or not target:
        return None

    node = addon_state.drag_nodes.add()
    node.source_bone_name = source
    node.bone_name = target
    node.simulation_fps = float(_get_wk(raw, "simulationFps", 100.0))
    node.source_speed_multiplier = float(_get_wk(raw, "sourceSpeedMultiplier", 10.0))
    node.has_overshoot = bool(_get_wk(raw, "hasOvershoot", 1))
    node.overshoot_detection_min_speed = float(
        _get_wk(raw, "overshootDetectionMinSpeed", 0.4)
    )
    node.overshoot_detection_max_speed = float(
        _get_wk(raw, "overshootDetectionMaxSpeed", 4.0)
    )
    node.overshoot_duration = float(_get_wk(raw, "overshootDuration", 1.0))
    node.use_steps = bool(_get_wk(raw, "useSteps", 0))
    node.steps_target_speed_multiplier = float(
        _get_wk(raw, "stepsTargetSpeedMultiplier", 10000.0)
    )
    node.time_between_steps = float(_get_wk(raw, "timeBetweenSteps", 0.1))
    node.time_in_step = float(_get_wk(raw, "timeInStep", 0.1))
    return len(addon_state.drag_nodes) - 1


def _append_graph_operation(addon_state, node_type, node_index, identity, path):
    collection = getattr(addon_state, "evaluation_order", None)
    if collection is None:
        return
    operation = collection.add()
    operation.node_type = node_type
    operation.node_index = int(node_index)
    operation.source_handle = identity
    operation.graph_path = path


def _parse_wolvenkit_animgraph(data, addon_state):
    node_map, node_ids = _build_handle_maps(data)
    nodes_by_type = _find_nodes_by_types(data, {
        "animAnimNode_Root",
        "animAnimNode_Output",
        "animAnimNode_Dangle",
        "animAnimNode_Drag",
    })
    ordered = _collect_graph_operations(
        data, node_map, node_ids, nodes_by_type
    )

    dangle_indices = {}
    drag_indices = {}
    parsed_dangle_nodes = set()
    parsed_drag_nodes = set()

    for node_type, raw_node, identity, path in ordered:
        if node_type == "DANGLE":
            info = _extract_dangle_info(raw_node, node_map)
            if info is None or not info[2]:
                continue
            if identity not in dangle_indices:
                _dangle, sim_data, bone_set, _sim_type = info
                label = _make_node_label(
                    sim_data, raw_node, bone_set, len(addon_state.dangle_nodes)
                )
                dangle_indices[identity] = _parse_dangle_as_node(
                    raw_node, sim_data, addon_state, node_map, label
                )
            parsed_dangle_nodes.add(id(raw_node))
            _append_graph_operation(
                addon_state, "DANGLE", dangle_indices[identity], identity, path
            )
        else:
            if identity not in drag_indices:
                parsed = _parse_drag_node(raw_node, addon_state)
                if parsed is None:
                    continue
                drag_indices[identity] = parsed
            parsed_drag_nodes.add(id(raw_node))
            _append_graph_operation(
                addon_state, "DRAG", drag_indices[identity], identity, path
            )

    # Preserve disconnected authoring nodes for editing, but do not execute them.
    for raw_node in nodes_by_type["animAnimNode_Dangle"]:
        if id(raw_node) in parsed_dangle_nodes:
            continue
        info = _extract_dangle_info(raw_node, node_map)
        if info is None or not info[2]:
            continue
        _dangle, sim_data, bone_set, _sim_type = info
        label = _make_node_label(
            sim_data, raw_node, bone_set, len(addon_state.dangle_nodes)
        )
        _parse_dangle_as_node(
            raw_node, sim_data, addon_state, node_map, label
        )

    seen_drag_pairs = {
        (node.source_bone_name, node.bone_name)
        for node in addon_state.drag_nodes
    }
    for raw_node in nodes_by_type["animAnimNode_Drag"]:
        if id(raw_node) in parsed_drag_nodes:
            continue
        source = _get_bone_name(raw_node, "sourceBone")
        target = _get_bone_name(raw_node, "outTargetBone") or source
        if not source or not target or (source, target) in seen_drag_pairs:
            continue
        parsed = _parse_drag_node(raw_node, addon_state)
        if parsed is not None:
            seen_drag_pairs.add((source, target))

    if not getattr(addon_state, "evaluation_order", ()):
        for node_index in range(len(addon_state.dangle_nodes)):
            _append_graph_operation(
                addon_state, "DANGLE", node_index, "fallback",
                f"fallback.dangle[{node_index}]",
            )
        for node_index in range(len(addon_state.drag_nodes)):
            _append_graph_operation(
                addon_state, "DRAG", node_index, "fallback",
                f"fallback.drag[{node_index}]",
            )

    addon_state.substeps = max(
        1, int(round((1.0 / 60.0) / addon_state.substep_time))
    )
    return len(addon_state.dangle_nodes)

def _clear_addon_state(addon_state):
    addon_state.is_playing = False
    addon_state.dangle_nodes.clear()
    addon_state.collision_shapes.clear()
    addon_state.drag_nodes.clear()
    evaluation_order = getattr(addon_state, "evaluation_order", None)
    if evaluation_order is not None:
        evaluation_order.clear()
    addon_state.active_dangle_node = 0
    addon_state.active_shape_index = 0
    addon_state.external_force_ws = (0.0, 0.0, 0.0)
    addon_state.substep_time = 0.01
    addon_state.substeps = 1
    addon_state.solver_iterations = 1


def _serialize_shape(shape):
    return {
        "name": shape.name,
        "bone": shape.bone_name,
        "shapeType": shape.shape_type,
        "radius": shape.radius,
        "xBoxExtent": shape.x_box_extent,
        "yBoxExtent": shape.y_box_extent,
        "zBoxExtent": shape.height_extent,
        "offsetLS": list(shape.offset_ls),
        "rotationLS": list(_quat_wxyz_to_ijkr(shape.rotation_ls_quat)),
    }


def _serialize_editor_state(addon_state):
    arm_obj = getattr(addon_state, "id_data", None)
    gravity = 9.81
    if bpy.context and bpy.context.scene and hasattr(bpy.context.scene, "physx"):
        gravity = -float(bpy.context.scene.physx.gravity[2])

    data = {
        "format": EDITOR_FORMAT,
        "version": EDITOR_VERSION,
        "coordinateSpace": spaces.EDITOR_SPACE_CONTRACT,
        "rigSpaceContract": spaces.rig_space_contract(arm_obj),
        "runtime": "ORDERED_DYNG_POSITION_PROJECTION_SPRING_PENDULUM_DRAG",
        "gravityWS": gravity,
        "externalForceWS": list(addon_state.external_force_ws),
        "substepTime": addon_state.substep_time,
        "substeps": addon_state.substeps,
        "solverIterations": addon_state.solver_iterations,
        "collisionShapes": [_serialize_shape(s) for s in addon_state.collision_shapes],
        "dangleNodes": [],
        "dragNodes": [],
        "evaluationOrder": [
            {
                "type": operation.node_type,
                "nodeIndex": operation.node_index,
                "sourceHandle": operation.source_handle,
                "graphPath": operation.graph_path,
            }
            for operation in getattr(addon_state, "evaluation_order", ())
        ],
    }

    for dnode in addon_state.dangle_nodes:
        node_data = {
            "name": dnode.name,
            "alpha": dnode.alpha,
            "rotateParentToLookAt": dnode.rotate_parent_to_look_at,
            "lookAtAxis": list(dnode.look_at_axis),
            "gravityWS": dnode.gravity_ws,
            "externalForceWS": list(dnode.external_force_ws),
            "substepTime": dnode.substep_time,
            "solverIterations": dnode.solver_iterations,
            "importedSolverIterations": dnode.imported_solver_iterations,
            "parentRotationAltersDangleChildren": dnode.parent_rotation_alters_dangle_children,
            "parentRotationAltersNonDangleChildren": dnode.parent_rotation_alters_non_dangle_children,
            "dangleAltersChildren": dnode.dangle_alters_children,
            "chains": [],
            "constraintOrder": [
                {
                    "type": entry.constraint_type,
                    "particleBone": entry.particle_bone,
                    "constraintIndex": entry.constraint_index,
                }
                for entry in dnode.constraint_order
            ],
            "collisionShapes": [_serialize_shape(s) for s in dnode.collision_shapes],
        }
        for chain in dnode.chains:
            chain_data = {"name": chain.name, "solver": chain.solver, "particles": []}
            for particle in chain.particles:
                particle_data = {
                    "bone": particle.bone_name,
                    "mass": particle.mass,
                    "damping": particle.damping,
                    "pullForceFactor": particle.pull_force,
                    "isFree": not particle.is_pinned,
                    "collisionCapsuleRadius": particle.capsule_radius,
                    "collisionCapsuleHeightExtent": particle.capsule_height,
                    "collisionCapsuleAxisLS": list(particle.capsule_axis_ls),
                    "dyngProjectionType": particle.dyng_projection_type,
                    "posProjectionType": particle.pos_projection_type,
                    "directionReferenceBone": particle.direction_reference_bone,
                    "springSimulationFps": particle.spring_simulation_fps,
                    "springConstraintRadius": particle.spring_constraint_radius,
                    "springConstraintScale1": particle.spring_constraint_scale1,
                    "springConstraintScale2": particle.spring_constraint_scale2,
                    "springConstraintOrientation": list(
                        particle.spring_constraint_orientation
                    ),
                    "springPullForceOriginLS": list(
                        particle.spring_pull_force_origin_ls
                    ),
                    "springProjectionType": particle.spring_projection_type,
                    "springCollisionRadius": particle.spring_collision_radius,
                    "pendulumSimulationFps": getattr(particle, "pendulum_simulation_fps", 10.0),
                    "pendulumConstraintType": getattr(particle, "pendulum_constraint_type", "CONE"),
                    "pendulumHalfApertureAngle": getattr(particle, "pendulum_half_aperture_angle", 45.0),
                    "pendulumConstraintOrientation": list(
                        getattr(particle, "pendulum_constraint_orientation", (90.0, 0.0, 0.0))
                    ),
                    "pendulumPullForceDirectionLS": list(
                        getattr(particle, "pendulum_pull_force_direction_ls", (0.0, 0.0, 0.0))
                    ),
                    "pendulumProjectionType": getattr(particle, "pendulum_projection_type", "SHORTEST_PATH_ROTATIONAL"),
                    "pendulumCollisionRadius": getattr(particle, "pendulum_collision_radius", 0.0),
                    "pendulumCollisionHeight": getattr(particle, "pendulum_collision_height", 0.0),
                    "links": [],
                    "ellipsoids": [],
                    "pendulums": [],
                }
                for link in particle.link_constraints:
                    particle_data["links"].append({
                        "targetBone": link.target_bone,
                        "linkType": link.link_type,
                        "lowerRatio": link.lower_ratio,
                        "upperRatio": link.upper_ratio,
                        "stiffness": link.stiffness,
                        "explicitRestDistance": link.explicit_rest_distance,
                        "lookAtAxis": list(link.look_at_axis),
                    })
                for ellipsoid in particle.ellipsoid_constraints:
                    particle_data["ellipsoids"].append({
                        "targetBone": ellipsoid.target_bone,
                        "radius": ellipsoid.radius,
                        "scale1": ellipsoid.scale1,
                        "scale2": ellipsoid.scale2,
                        "transformLsQuat": list(_quat_wxyz_to_ijkr(
                            ellipsoid.ellipsoid_transform_ls_quat
                        )),
                        "transformLsOffset": list(ellipsoid.ellipsoid_transform_ls_offset),
                    })
                for pendulum in particle.pendulum_constraints:
                    particle_data["pendulums"].append({
                        "targetBone": pendulum.target_bone,
                        "constraintType": pendulum.constraint_type,
                        "halfApertureAngle": pendulum.half_aperture_angle,
                        "projectionType": pendulum.projection_type,
                        "coneCollisionRadius": pendulum.cone_collision_radius,
                        "coneCollisionHeight": pendulum.cone_collision_height,
                        "coneTransformLsQuat": list(_quat_wxyz_to_ijkr(
                            pendulum.cone_transform_ls_quat
                        )),
                        "coneTransformLsOffset": list(
                            pendulum.cone_transform_ls_offset
                        ),
                    })
                chain_data["particles"].append(particle_data)
            node_data["chains"].append(chain_data)
        data["dangleNodes"].append(node_data)

    for drag in addon_state.drag_nodes:
        data["dragNodes"].append({
            "sourceBone": drag.source_bone_name or drag.bone_name,
            "outTargetBone": drag.bone_name,
            "simulationFps": drag.simulation_fps,
            "sourceSpeedMultiplier": drag.source_speed_multiplier,
            "hasOvershoot": drag.has_overshoot,
            "overshootDetectionMinSpeed": drag.overshoot_detection_min_speed,
            "overshootDetectionMaxSpeed": drag.overshoot_detection_max_speed,
            "overshootDuration": drag.overshoot_duration,
            "useSteps": drag.use_steps,
            "stepsTargetSpeedMultiplier": drag.steps_target_speed_multiplier,
            "timeBetweenSteps": drag.time_between_steps,
            "timeInStep": drag.time_in_step,
        })
    return data


def _parse_editor_shape(raw, collection, existing=None):
    extents = (
        float(raw.get("xBoxExtent", 0.0)),
        float(raw.get("yBoxExtent", 0.0)),
        float(raw.get("zBoxExtent", 0.0)),
    )
    values = {
        "name": str(raw.get("name", "Shape")),
        "bone": str(raw.get("bone", "")),
        "shape_type": str(raw.get(
            "shapeType", _shape_type_from_extents(extents)
        )),
        "radius": float(raw.get("radius", 0.05)),
        "extents": extents,
        "offset": _sequence(raw.get("offsetLS"), 3, (0.0, 0.0, 0.0)),
        "rotation": _quat_ijkr_to_wxyz(raw.get("rotationLS")),
    }
    return _add_collision_shape(collection, values, existing)


def _parse_editor_state(data, addon_state):
    if not isinstance(data, dict) or not isinstance(data.get("dangleNodes", []), list):
        raise ValueError("Invalid Dangle Physics Editor JSON")

    coordinate_space = data.get("coordinateSpace")
    supported_spaces = {
        None,
        spaces.EDITOR_SPACE_CONTRACT,
        spaces.RIG_SPACE_CONTRACT_CURRENT,
        spaces.RIG_SPACE_CONTRACT_DIRECT,
    }
    if coordinate_space not in supported_spaces:
        raise ValueError(
            f"Unsupported Dangle editor coordinate space: {coordinate_space}"
        )
    # Versions <= 12 wrote the target rig contract here even though all local
    # axes/transforms were still serialized as authored REDengine values. They
    # therefore require no numeric migration; version 13 names that data space
    # explicitly and records the target rig contract separately.

    addon_state.external_force_ws = _sequence(
        data.get("externalForceWS"), 3, (0.0, 0.0, 0.0)
    )
    addon_state.substep_time = max(0.005, min(0.1, float(data.get("substepTime", 0.01))))
    addon_state.substeps = max(1, int(data.get("substeps", 1)))
    addon_state.solver_iterations = max(1, min(8, int(data.get("solverIterations", 1))))

    if bpy.context and bpy.context.scene and hasattr(bpy.context.scene, "physx"):
        gravity = abs(float(data.get("gravityWS", 9.81)))
        bpy.context.scene.physx.gravity[2] = -gravity

    global_shape_keys = set()
    for raw_shape in data.get("collisionShapes", []):
        _parse_editor_shape(raw_shape, addon_state.collision_shapes, global_shape_keys)

    for raw_node in data.get("dangleNodes", []):
        node = addon_state.dangle_nodes.add()
        node.name = str(raw_node.get("name", f"DangleNode_{len(addon_state.dangle_nodes)}"))
        node.alpha = float(raw_node.get("alpha", 1.0))
        node.rotate_parent_to_look_at = bool(raw_node.get("rotateParentToLookAt", True))
        node.look_at_axis = _sequence(
            raw_node.get("lookAtAxis"), 3, (1.0, 0.0, 0.0)
        )
        node.gravity_ws = abs(float(raw_node.get("gravityWS", data.get("gravityWS", 9.81))))
        node.external_force_ws = _sequence(
            raw_node.get("externalForceWS"), 3, tuple(addon_state.external_force_ws)
        )
        node.substep_time = max(0.005, min(0.1, float(
            raw_node.get("substepTime", addon_state.substep_time)
        )))
        node.solver_iterations = max(1, min(8, int(
            raw_node.get("solverIterations", addon_state.solver_iterations)
        )))
        node.imported_solver_iterations = max(0, int(
            raw_node.get("importedSolverIterations", node.solver_iterations)
        ))
        node.parent_rotation_alters_dangle_children = bool(
            raw_node.get("parentRotationAltersDangleChildren", False)
        )
        node.parent_rotation_alters_non_dangle_children = bool(
            raw_node.get("parentRotationAltersNonDangleChildren", False)
        )
        node.dangle_alters_children = bool(raw_node.get("dangleAltersChildren", False))

        for raw_order in raw_node.get("constraintOrder", []):
            entry = node.constraint_order.add()
            entry.constraint_type = str(raw_order.get("type", "LINK"))
            entry.particle_bone = str(raw_order.get("particleBone", ""))
            entry.constraint_index = max(0, int(raw_order.get("constraintIndex", 0)))

        node_shape_keys = set()
        for raw_shape in raw_node.get("collisionShapes", []):
            _parse_editor_shape(raw_shape, node.collision_shapes, node_shape_keys)

        for raw_chain in raw_node.get("chains", []):
            chain = node.chains.add()
            chain.name = str(raw_chain.get("name", "Chain"))
            chain.solver = str(raw_chain.get("solver", "DYNG"))
            for raw_particle in raw_chain.get("particles", []):
                particle = chain.particles.add()
                particle.bone_name = str(raw_particle.get("bone", ""))
                particle.mass = float(raw_particle.get("mass", 1.0))
                particle.damping = float(raw_particle.get("damping", 1.0))
                particle.pull_force = float(raw_particle.get("pullForceFactor", 0.0))
                particle.is_pinned = not bool(raw_particle.get("isFree", True))
                particle.capsule_radius = float(raw_particle.get("collisionCapsuleRadius", 0.0))
                particle.capsule_height = float(raw_particle.get("collisionCapsuleHeightExtent", 0.0))
                particle.capsule_axis_ls = _sequence(
                    raw_particle.get("collisionCapsuleAxisLS"), 3, (0.5, 0.0, 0.0)
                )
                particle.dyng_projection_type = str(
                    raw_particle.get("dyngProjectionType", "SHORTEST_PATH")
                )
                particle.pos_projection_type = str(
                    raw_particle.get("posProjectionType", "SHORTEST_PATH")
                )
                particle.direction_reference_bone = str(
                    raw_particle.get("directionReferenceBone", "")
                )
                particle.spring_simulation_fps = float(
                    raw_particle.get("springSimulationFps", 10.0)
                )
                particle.spring_constraint_radius = float(
                    raw_particle.get("springConstraintRadius", 0.5)
                )
                particle.spring_constraint_scale1 = float(
                    raw_particle.get("springConstraintScale1", 1.0)
                )
                particle.spring_constraint_scale2 = float(
                    raw_particle.get("springConstraintScale2", 1.0)
                )
                particle.spring_constraint_orientation = _sequence(
                    raw_particle.get("springConstraintOrientation"),
                    2,
                    (0.0, 90.0),
                )
                particle.spring_pull_force_origin_ls = _sequence(
                    raw_particle.get("springPullForceOriginLS"),
                    3,
                    (0.0, 0.0, 0.0),
                )
                particle.spring_projection_type = str(
                    raw_particle.get("springProjectionType", "SHORTEST_PATH")
                )
                particle.spring_collision_radius = float(
                    raw_particle.get("springCollisionRadius", 0.0)
                )
                particle.pendulum_simulation_fps = float(
                    raw_particle.get("pendulumSimulationFps", 10.0)
                )
                particle.pendulum_constraint_type = str(
                    raw_particle.get("pendulumConstraintType", "CONE")
                )
                particle.pendulum_half_aperture_angle = float(
                    raw_particle.get("pendulumHalfApertureAngle", 45.0)
                )
                particle.pendulum_constraint_orientation = _sequence(
                    raw_particle.get("pendulumConstraintOrientation"),
                    3, (90.0, 0.0, 0.0),
                )
                particle.pendulum_pull_force_direction_ls = _sequence(
                    raw_particle.get("pendulumPullForceDirectionLS"),
                    3, (0.0, 0.0, 0.0),
                )
                particle.pendulum_projection_type = str(
                    raw_particle.get(
                        "pendulumProjectionType", "SHORTEST_PATH_ROTATIONAL"
                    )
                )
                particle.pendulum_collision_radius = float(
                    raw_particle.get("pendulumCollisionRadius", 0.0)
                )
                particle.pendulum_collision_height = float(
                    raw_particle.get("pendulumCollisionHeight", 0.0)
                )

                for raw_link in raw_particle.get("links", []):
                    link = particle.link_constraints.add()
                    link.target_bone = str(raw_link.get("targetBone", ""))
                    link.link_type = str(raw_link.get("linkType", "FIXED"))
                    link.lower_ratio = float(raw_link.get("lowerRatio", 100.0))
                    link.upper_ratio = float(raw_link.get("upperRatio", 100.0))
                    link.stiffness = float(raw_link.get("stiffness", 1.0))
                    link.explicit_rest_distance = float(
                        raw_link.get("explicitRestDistance", 0.0)
                    )
                    link.look_at_axis = _sequence(
                        raw_link.get("lookAtAxis"), 3, (1.0, 0.0, 0.0)
                    )

                for raw_ellipsoid in raw_particle.get("ellipsoids", []):
                    ellipsoid = particle.ellipsoid_constraints.add()
                    ellipsoid.target_bone = str(raw_ellipsoid.get("targetBone", ""))
                    ellipsoid.radius = float(raw_ellipsoid.get("radius", 0.1))
                    ellipsoid.scale1 = float(raw_ellipsoid.get("scale1", 1.0))
                    ellipsoid.scale2 = float(raw_ellipsoid.get("scale2", 1.0))
                    ellipsoid.ellipsoid_transform_ls_quat = _quat_ijkr_to_wxyz(
                        raw_ellipsoid.get("transformLsQuat")
                    )
                    ellipsoid.ellipsoid_transform_ls_offset = _sequence(
                        raw_ellipsoid.get("transformLsOffset"), 3, (0.0, 0.0, 0.0)
                    )

                for raw_pendulum in raw_particle.get("pendulums", []):
                    pendulum = particle.pendulum_constraints.add()
                    pendulum.target_bone = str(raw_pendulum.get("targetBone", ""))
                    pendulum.constraint_type = str(
                        raw_pendulum.get("constraintType", "CONE")
                    )
                    pendulum.half_aperture_angle = float(
                        raw_pendulum.get("halfApertureAngle", 45.0)
                    )
                    pendulum.projection_type = str(
                        raw_pendulum.get("projectionType", "DISABLED")
                    )
                    pendulum.cone_collision_radius = float(
                        raw_pendulum.get("coneCollisionRadius", 0.0)
                    )
                    pendulum.cone_collision_height = float(
                        raw_pendulum.get("coneCollisionHeight", 0.0)
                    )
                    pendulum.cone_transform_ls_quat = _quat_ijkr_to_wxyz(
                        raw_pendulum.get("coneTransformLsQuat")
                    )
                    pendulum.cone_transform_ls_offset = _sequence(
                        raw_pendulum.get("coneTransformLsOffset"),
                        3,
                        (0.0, 0.0, 0.0),
                    )

    for raw_drag in data.get("dragNodes", []):
        drag = addon_state.drag_nodes.add()
        target = str(raw_drag.get("outTargetBone", raw_drag.get("bone", "")))
        drag.source_bone_name = str(raw_drag.get("sourceBone", target))
        drag.bone_name = target
        drag.simulation_fps = float(raw_drag.get("simulationFps", 100.0))
        drag.source_speed_multiplier = float(raw_drag.get("sourceSpeedMultiplier", 10.0))
        drag.has_overshoot = bool(raw_drag.get("hasOvershoot", True))
        drag.overshoot_detection_min_speed = float(
            raw_drag.get("overshootDetectionMinSpeed", 0.4)
        )
        drag.overshoot_detection_max_speed = float(
            raw_drag.get("overshootDetectionMaxSpeed", 4.0)
        )
        drag.overshoot_duration = float(raw_drag.get("overshootDuration", 1.0))
        drag.use_steps = bool(raw_drag.get("useSteps", False))
        drag.steps_target_speed_multiplier = float(
            raw_drag.get("stepsTargetSpeedMultiplier", 10000.0)
        )
        drag.time_between_steps = float(raw_drag.get("timeBetweenSteps", 0.1))
        drag.time_in_step = float(raw_drag.get("timeInStep", 0.1))

    for raw_operation in data.get("evaluationOrder", []):
        node_type = str(raw_operation.get("type", "DANGLE"))
        node_index = max(0, int(raw_operation.get("nodeIndex", 0)))
        limit = (
            len(addon_state.dangle_nodes)
            if node_type == "DANGLE"
            else len(addon_state.drag_nodes)
        )
        if node_type not in {"DANGLE", "DRAG"} or node_index >= limit:
            continue
        _append_graph_operation(
            addon_state, node_type, node_index,
            str(raw_operation.get("sourceHandle", "editor")),
            str(raw_operation.get("graphPath", "editor")),
        )

    if not getattr(addon_state, "evaluation_order", ()):
        for node_index in range(len(addon_state.dangle_nodes)):
            _append_graph_operation(
                addon_state, "DANGLE", node_index, "editor-fallback",
                f"editor.dangle[{node_index}]",
            )
        for node_index in range(len(addon_state.drag_nodes)):
            _append_graph_operation(
                addon_state, "DRAG", node_index, "editor-fallback",
                f"editor.drag[{node_index}]",
            )

    return len(addon_state.dangle_nodes)



_JSON_NUMBER = re.compile(
    r"-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?"
)


def _skip_json_whitespace(text, index):
    length = len(text)
    while index < length and text[index] in " \t\r\n":
        index += 1
    return index


def _parse_json_primitive(text, index):
    character = text[index]
    if character == '"':
        return scanstring(text, index + 1, True)
    if text.startswith("true", index):
        return True, index + 4
    if text.startswith("false", index):
        return False, index + 5
    if text.startswith("null", index):
        return None, index + 4
    if text.startswith("NaN", index):
        return float("nan"), index + 3
    if text.startswith("Infinity", index):
        return float("inf"), index + 8
    if text.startswith("-Infinity", index):
        return float("-inf"), index + 9

    match = _JSON_NUMBER.match(text, index)
    if match is None:
        raise json.JSONDecodeError("Expecting value", text, index)
    token = match.group(0)
    if "." in token or "e" in token or "E" in token:
        return float(token), match.end()
    return int(token), match.end()


def _loads_iterative(text):
    root = {"kind": "root", "state": "value", "value": None}
    stack = [root]
    index = 0
    length = len(text)

    def attach_value(frame, value):
        if frame["kind"] == "root":
            frame["value"] = value
            frame["state"] = "done"
        elif frame["kind"] == "array":
            frame["value"].append(value)
            frame["state"] = "comma_or_end"
        else:
            frame["value"][frame["key"]] = value
            frame["key"] = None
            frame["state"] = "comma_or_end"

    def begin_value(frame, value_index):
        character = text[value_index]
        if character == "[":
            value = []
            attach_value(frame, value)
            stack.append({
                "kind": "array",
                "state": "value_or_end",
                "value": value,
            })
            return value_index + 1
        if character == "{":
            value = {}
            attach_value(frame, value)
            stack.append({
                "kind": "object",
                "state": "key_or_end",
                "value": value,
                "key": None,
            })
            return value_index + 1
        value, next_index = _parse_json_primitive(text, value_index)
        attach_value(frame, value)
        return next_index

    while stack:
        frame = stack[-1]
        index = _skip_json_whitespace(text, index)

        if frame["kind"] == "root":
            if frame["state"] == "value":
                if index >= length:
                    raise json.JSONDecodeError("Expecting value", text, index)
                index = begin_value(frame, index)
                continue
            if len(stack) > 1:
                continue
            if index != length:
                raise json.JSONDecodeError("Extra data", text, index)
            return frame["value"]

        if frame["kind"] == "array":
            if frame["state"] in {"value_or_end", "value"}:
                if index >= length:
                    raise json.JSONDecodeError("Expecting value", text, index)
                if text[index] == "]":
                    if frame["state"] == "value":
                        raise json.JSONDecodeError("Expecting value", text, index)
                    stack.pop()
                    index += 1
                    continue
                index = begin_value(frame, index)
                continue
            if index >= length:
                raise json.JSONDecodeError("Expecting ',' delimiter", text, index)
            if text[index] == ",":
                frame["state"] = "value"
                index += 1
                continue
            if text[index] == "]":
                stack.pop()
                index += 1
                continue
            raise json.JSONDecodeError("Expecting ',' delimiter", text, index)

        state = frame["state"]
        if state in {"key_or_end", "key"}:
            if index >= length:
                raise json.JSONDecodeError(
                    "Expecting property name enclosed in double quotes",
                    text,
                    index,
                )
            if text[index] == "}":
                if state == "key":
                    raise json.JSONDecodeError(
                        "Expecting property name enclosed in double quotes",
                        text,
                        index,
                    )
                stack.pop()
                index += 1
                continue
            if text[index] != '"':
                raise json.JSONDecodeError(
                    "Expecting property name enclosed in double quotes",
                    text,
                    index,
                )
            frame["key"], index = scanstring(text, index + 1, True)
            frame["state"] = "colon"
            continue

        if state == "colon":
            if index >= length or text[index] != ":":
                raise json.JSONDecodeError("Expecting ':' delimiter", text, index)
            frame["state"] = "value"
            index += 1
            continue

        if state == "value":
            if index >= length:
                raise json.JSONDecodeError("Expecting value", text, index)
            index = begin_value(frame, index)
            continue

        if index >= length:
            raise json.JSONDecodeError("Expecting ',' delimiter", text, index)
        if text[index] == ",":
            frame["state"] = "key"
            index += 1
            continue
        if text[index] == "}":
            stack.pop()
            index += 1
            continue
        raise json.JSONDecodeError("Expecting ',' delimiter", text, index)

    raise json.JSONDecodeError("Expecting value", text, index)


def _load_json_document(filepath):
    with open(filepath, "r", encoding="utf-8") as file:
        text = file.read()
    try:
        return json.loads(text)
    except RecursionError:
        return _loads_iterative(text)

def import_chains(filepath, addon_state):
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")
    data = _load_json_document(filepath)

    is_wolvenkit = (
        isinstance(data, dict)
        and isinstance(data.get("Header"), dict)
        and "WolvenKitVersion" in data["Header"]
    )
    is_editor = (
        isinstance(data, dict)
        and (
            data.get("format") == EDITOR_FORMAT
            or ("dangleNodes" in data and "version" in data)
        )
    )
    if not is_wolvenkit and not is_editor:
        raise ValueError("Unsupported JSON format")

    backup = _serialize_editor_state(addon_state)
    _clear_addon_state(addon_state)
    try:
        if is_wolvenkit:
            count = _parse_wolvenkit_animgraph(data, addon_state)
        else:
            count = _parse_editor_state(data, addon_state)

        arm_obj = getattr(addon_state, "id_data", None)
        space_errors = spaces.armature_space_errors(arm_obj)
        if space_errors:
            raise ValueError(space_errors[0])
        missing = spaces.unresolved_state_bones(
            arm_obj, addon_state, executable_only=True
        )
        if missing:
            names = []
            seen = set()
            for _role, name in missing:
                if name not in seen:
                    seen.add(name)
                    names.append(name)
            preview = ", ".join(names[:12])
            suffix = f" (+{len(names) - 12} more)" if len(names) > 12 else ""
            raise ValueError(
                f"The selected MetaRig is missing Dangle bones: {preview}{suffix}"
            )
        return count
    except Exception:
        _clear_addon_state(addon_state)
        _parse_editor_state(backup, addon_state)
        raise


def export_chains(filepath, addon_state):
    with open(filepath, "w", encoding="utf-8") as file:
        json.dump(_serialize_editor_state(addon_state), file, indent=2)

