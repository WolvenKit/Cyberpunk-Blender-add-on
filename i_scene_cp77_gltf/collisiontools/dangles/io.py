import json
import bpy
import os

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

def _build_handle_map(obj, node_map):
    if isinstance(obj, dict):
        if "HandleId" in obj and "Data" in obj:
            node_map[obj["HandleId"]] = obj["Data"]
        for v in obj.values():
            _build_handle_map(v, node_map)
    elif isinstance(obj, list):
        for item in obj:
            _build_handle_map(item, node_map)

def _resolve_handle(obj, node_map):
    if not isinstance(obj, dict):
        return obj
    if "HandleRefId" in obj:
        return node_map.get(obj["HandleRefId"], {})
    if "Data" in obj:
        return obj["Data"]
    return obj

def _find_nodes_by_type(data, target_type):
    results = []
    if isinstance(data, dict):
        if data.get("$type") == target_type:
            results.append(data)
        for v in data.values():
            results.extend(_find_nodes_by_type(v, target_type))
    elif isinstance(data, list):
        for item in data:
            results.extend(_find_nodes_by_type(item, target_type))
    return results

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

def _axis_re_to_bl(v):
    return (-v[1], v[0], v[2])

def _axis_bl_to_re(v):
    return (v[1], -v[0], v[2])

def _parse_vec3(v_dict, default=(0.0, 0.0, 0.0)):
    if not isinstance(v_dict, dict):
        return default
    return (
        float(v_dict.get("X", default[0])),
        float(v_dict.get("Y", default[1])),
        float(v_dict.get("Z", default[2])),
    )

def _bone_prefix(name):
    return name.rsplit("_", 1)[0] if "_" in name else name

def _extract_dangle_info(dangle_node, node_map):
    constraint_ref = _get_wk(dangle_node, "dangleConstraint", {})
    sim_data = _resolve_handle(constraint_ref, node_map)

    if not sim_data or sim_data.get("$type") != "animDangleConstraint_SimulationDyng":
        return None

    container = _get_wk(sim_data, "particlesContainer", {})
    particles_array = _get_wk(container, "particles", [])

    bone_set = frozenset(
        _get_bone_name(p, "bone")
        for p in particles_array
        if _get_bone_name(p, "bone")
    )

    dyng_ref = _get_wk(sim_data, "dyngConstraint", {})
    multi_node = _resolve_handle(dyng_ref, node_map)
    c_count = 0
    if multi_node.get("$type") == "animDyngConstraintMulti":
        c_count = len(_get_wk(multi_node, "innerConstraints", []))

    return (dangle_node, sim_data, bone_set, c_count)

def _deduplicate_dangles(dangle_infos):
    groups = {}
    for info in dangle_infos:
        _, _, bone_set, c_count = info
        if bone_set not in groups or c_count > groups[bone_set][3]:
            groups[bone_set] = info
    return list(groups.values())

def _make_node_label(sim_data, dangle_node, bone_set, index):
    iters = int(_get_wk(sim_data, "solverIterations", 1))
    container = _get_wk(sim_data, "particlesContainer", {})
    particles = _get_wk(container, "particles", [])
    n_particles = len(particles)

    rotate = bool(_get_wk(sim_data, "rotateParentToLookAtDangle", 1))

    if n_particles <= 2:
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

    container = _get_wk(sim_data, "particlesContainer", {})

    grav = _get_wk(container, "gravityWS", 9.81)
    grav_val = float(grav.get("Z", 9.81)) if isinstance(grav, dict) else float(grav)
    if bpy.context and bpy.context.scene:
        if abs(grav_val) > abs(bpy.context.scene.physx.gravity[2]):
            bpy.context.scene.physx.gravity[2] = -grav_val

    ext_force = _get_wk(container, "externalForceWS", {})
    if isinstance(ext_force, dict):
        ef = _parse_vec3(ext_force)
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

    dnode_idx = len(addon_state.dangle_nodes) - 1

    existing_shapes = set()
    for s in addon_state.collision_shapes:
        existing_shapes.add((s.bone_name, tuple(s.offset_ls)))

    shapes_raw = _get_wk(sim_data, "collisionRoundedShapes", [])
    for si, s_raw in enumerate(shapes_raw):
        bone = _get_bone_name(s_raw, "bone")
        t_ls = _get_wk(s_raw, "transformLS", {})
        offset_dict = _get_wk(t_ls, "Translation", {})
        offset = _parse_vec3(offset_dict)

        key = (bone, offset)
        if key in existing_shapes:
            continue
        existing_shapes.add(key)

        s = addon_state.collision_shapes.add()
        s.bone_name = bone
        s.name = f"Shape_{bone}_{len(addon_state.collision_shapes) - 1}"
        x_ext = float(_get_wk(s_raw, "xBoxExtent", 0.0))
        y_ext = float(_get_wk(s_raw, "yBoxExtent", 0.0))
        z_ext = float(_get_wk(s_raw, "zBoxExtent", 0.0))
        s.shape_type = "CAPSULE" if (x_ext + y_ext + z_ext) > 0.0 else "SPHERE"
        s.radius = float(_get_wk(s_raw, "roundedCornerRadius", 0.05))
        s.x_box_extent = x_ext
        s.y_box_extent = y_ext
        s.height_extent = z_ext
        s.offset_ls = offset
        rot_dict = _get_wk(t_ls, "Rotation", {})
        s.rotation_ls_quat = _parse_quat(rot_dict)

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
                    lnk.look_at_axis = _axis_re_to_bl(re_axis)

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

    return dnode_idx

def _parse_drag_nodes(data, addon_state, node_map):
    drag_nodes = _find_nodes_by_type(data, "animAnimNode_Drag")
    seen_bones = set()
    count = 0
    for d in drag_nodes:
        bone = _get_bone_name(d, "sourceBone")
        if not bone or bone in seen_bones:
            continue
        target = _get_bone_name(d, "outTargetBone")
        if target and target != bone:
            continue
        seen_bones.add(bone)
        dn = addon_state.drag_nodes.add()
        dn.bone_name = bone
        dn.simulation_fps = float(_get_wk(d, "simulationFps", 120.0))
        dn.source_speed_multiplier = float(_get_wk(d, "sourceSpeedMultiplier", 6.0))
        dn.has_overshoot = bool(_get_wk(d, "hasOvershoot", 0))
        dn.overshoot_detection_min_speed = float(_get_wk(d, "overshootDetectionMinSpeed", 0.4))
        dn.overshoot_detection_max_speed = float(_get_wk(d, "overshootDetectionMaxSpeed", 4.0))
        dn.overshoot_duration = float(_get_wk(d, "overshootDuration", 1.0))
        count += 1
    return count

def _parse_wolvenkit_animgraph(data, addon_state):
    node_map = {}
    _build_handle_map(data, node_map)

    dangle_nodes = _find_nodes_by_type(data, "animAnimNode_Dangle")
    dangle_infos = []
    parsed_sim_ids = set()

    for d_node in dangle_nodes:
        info = _extract_dangle_info(d_node, node_map)
        if info is None:
            continue
        _, sim_data, bone_set, _ = info
        sid = id(sim_data)
        if sid in parsed_sim_ids:
            continue
        parsed_sim_ids.add(sid)
        if not bone_set:
            continue
        dangle_infos.append(info)

    unique_dangles = _deduplicate_dangles(dangle_infos)

    imported_nodes = 0
    for idx, (d_node, sim_data, bone_set, _) in enumerate(unique_dangles):
        label = _make_node_label(sim_data, d_node, bone_set, idx)
        _parse_dangle_as_node(d_node, sim_data, addon_state, node_map, label)
        imported_nodes += 1

    _parse_drag_nodes(data, addon_state, node_map)

    addon_state.substeps = max(
        1, int(round((1.0 / 60.0) / addon_state.substep_time))
    )
    return imported_nodes

def import_chains(filepath, addon_state):
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    if "Header" in data and "WolvenKitVersion" in data["Header"]:
        return _parse_wolvenkit_animgraph(data, addon_state)
    return 0

def export_chains(filepath, addon_state):
    data = {
        "version": 5,
        "gravityWS": -bpy.context.scene.physx.gravity[2] if bpy.context else 9.81,
        "externalForceWS": list(addon_state.external_force_ws),
        "substepTime": addon_state.substep_time,
        "substeps": addon_state.substeps,
        "solverIterations": addon_state.solver_iterations,
        "collisionShapes": [],
        "dangleNodes": [],
        "dragNodes": [],
    }
    for s in addon_state.collision_shapes:
        data["collisionShapes"].append({
            "name": s.name, "bone": s.bone_name, "shapeType": s.shape_type,
            "radius": s.radius,
            "xBoxExtent": getattr(s, 'x_box_extent', 0.0),
            "yBoxExtent": getattr(s, 'y_box_extent', 0.0),
            "zBoxExtent": s.height_extent,
            "offsetLS": list(s.offset_ls),
            "rotationLS": list(_quat_wxyz_to_ijkr(s.rotation_ls_quat)),
        })
    for dnode in addon_state.dangle_nodes:
        nd = {
            "name": dnode.name, "alpha": dnode.alpha,
            "rotateParentToLookAt": dnode.rotate_parent_to_look_at,
            "lookAtAxis": list(_axis_bl_to_re(dnode.look_at_axis)),
            "substepTime": dnode.substep_time,
            "solverIterations": dnode.solver_iterations,
            "importedSolverIterations": dnode.imported_solver_iterations,
            "chains": [], "collisionShapes": [],
        }
        for cs in dnode.collision_shapes:
            nd["collisionShapes"].append({
                "name": cs.name, "bone": cs.bone_name, "shapeType": cs.shape_type,
                "radius": cs.radius,
                "xBoxExtent": getattr(cs, 'x_box_extent', 0.0),
                "yBoxExtent": getattr(cs, 'y_box_extent', 0.0),
                "zBoxExtent": cs.height_extent,
                "offsetLS": list(cs.offset_ls),
                "rotationLS": list(_quat_wxyz_to_ijkr(cs.rotation_ls_quat)),
            })
        for ch in dnode.chains:
            chd = {"name": ch.name, "solver": ch.solver, "particles": []}
            for p in ch.particles:
                pd = {
                    "bone": p.bone_name, "mass": p.mass, "damping": p.damping,
                    "pullForceFactor": p.pull_force, "isFree": not p.is_pinned,
                    "collisionCapsuleRadius": p.capsule_radius,
                    "collisionCapsuleHeightExtent": p.capsule_height,
                    "collisionCapsuleAxisLS": list(p.capsule_axis_ls),
                    "dyngProjectionType": p.dyng_projection_type,
                    "posProjectionType": p.pos_projection_type,
                    "directionReferenceBone": p.direction_reference_bone,
                    "links": [], "ellipsoids": [], "pendulums": [],
                }
                for lnk in p.link_constraints:
                    pd["links"].append({
                        "targetBone": lnk.target_bone, "linkType": lnk.link_type,
                        "lowerRatio": lnk.lower_ratio, "upperRatio": lnk.upper_ratio,
                        "stiffness": lnk.stiffness,
                        "explicitRestDistance": lnk.explicit_rest_distance,
                        "lookAtAxis": list(_axis_bl_to_re(lnk.look_at_axis)),
                    })
                for ell in p.ellipsoid_constraints:
                    pd["ellipsoids"].append({
                        "targetBone": ell.target_bone, "radius": ell.radius,
                        "scale1": ell.scale1, "scale2": ell.scale2,
                        "transformLsQuat": list(_quat_wxyz_to_ijkr(ell.ellipsoid_transform_ls_quat)),
                        "transformLsOffset": list(ell.ellipsoid_transform_ls_offset),
                    })
                for pen in p.pendulum_constraints:
                    pd["pendulums"].append({
                        "targetBone": pen.target_bone,
                        "constraintType": pen.constraint_type,
                        "halfApertureAngle": pen.half_aperture_angle,
                        "projectionType": pen.projection_type,
                        "coneCollisionRadius": pen.cone_collision_radius,
                        "coneCollisionHeight": pen.cone_collision_height,
                        "coneTransformLsQuat": list(_quat_wxyz_to_ijkr(pen.cone_transform_ls_quat)),
                    })
                chd["particles"].append(pd)
            nd["chains"].append(chd)
        data["dangleNodes"].append(nd)
    for dn in addon_state.drag_nodes:
        data["dragNodes"].append({
            "bone": dn.bone_name, "simulationFps": dn.simulation_fps,
            "sourceSpeedMultiplier": dn.source_speed_multiplier,
            "hasOvershoot": dn.has_overshoot,
            "overshootDetectionMinSpeed": dn.overshoot_detection_min_speed,
            "overshootDetectionMaxSpeed": dn.overshoot_detection_max_speed,
            "overshootDuration": dn.overshoot_duration,
        })
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)