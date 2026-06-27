import json
import bpy
import os
import copy

from ...main.common import get_resources_dir

TEMPLATE_NAME = "template_dangle.animgraph.json"

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

LINK_MAP_INV = {v: k for k, v in LINK_MAP.items()}
PEND_MAP_INV = {v: k for k, v in PEND_MAP.items()}
PEND_PROJ_MAP_INV = {v: k for k, v in PEND_PROJ_MAP.items()}

# Particle dyng projection is a restricted subset of PROJ_MAP (no Directional).
DYNG_PROJ_INV = {
    "DISABLED": "Disabled",
    "SHORTEST_PATH": "ShortestPath",
    "DIRECTED": "Directed",
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

def _load_template():
    resources_dir = get_resources_dir()
    path = os.path.join(resources_dir, TEMPLATE_NAME)
    if not os.path.isfile(path):
        try:
            contents = ", ".join(sorted(os.listdir(resources_dir))) or "<empty>"
        except OSError as exc:
            contents = f"<unreadable: {exc}>"
        raise FileNotFoundError(
            f"Dangle export template '{TEMPLATE_NAME}' not found in resources dir.\n"
            f"  Resources dir: {resources_dir}\n"
            f"  Contents:      {contents}"
        )
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def _make_cname(value):
    return {"$type": "CName", "$storage": "string", "$value": value if value else "None"}

def _make_transform_index(bone_name):
    return {"$type": "animTransformIndex", "name": _make_cname(bone_name)}

def _make_vec3(v):
    return {"$type": "Vector3", "X": float(v[0]), "Y": float(v[1]), "Z": float(v[2])}

def _make_vec4(v, w=1.0):
    return {"$type": "Vector4", "W": float(w), "X": float(v[0]), "Y": float(v[1]), "Z": float(v[2])}

def _make_quat(q_wxyz):
    i, j, k, r = _quat_wxyz_to_ijkr(q_wxyz)
    return {"$type": "Quaternion", "i": float(i), "j": float(j), "k": float(k), "r": float(r)}

def _make_qstransform(rot_wxyz, translation, scale=(1.0, 1.0, 1.0)):
    return {
        "$type": "QsTransform",
        "Rotation": _make_quat(rot_wxyz),
        "Scale": _make_vec4(scale, w=1.0),
        "Translation": _make_vec4(translation, w=1.0),
    }

def _export_gravity_scalar():
    try:
        scene = bpy.context.scene
        if scene is not None and hasattr(scene, "physx"):
            return -float(scene.physx.gravity[2])
    except Exception:
        pass
    return 9.81

def _make_particle(p):
    return {
        "$type": "animDyngParticle",
        "bone": _make_transform_index(p.bone_name),
        "collisionCapsuleAxisLS": _make_vec3(p.capsule_axis_ls),
        "collisionCapsuleHeightExtent": float(p.capsule_height),
        "collisionCapsuleRadius": float(p.capsule_radius),
        "damping": float(p.damping),
        "isDebugEnabled": 1,
        "isFree": 0 if p.is_pinned else 1,
        "mass": float(p.mass),
        "projectionType": DYNG_PROJ_INV.get(p.dyng_projection_type, "ShortestPath"),
        "pullForceFactor": float(p.pull_force),
    }

def _make_link(owner_bone, lnk):
    return {
        "$type": "animDyngConstraintLink",
        "bone1": _make_transform_index(owner_bone),
        "bone2": _make_transform_index(lnk.target_bone),
        "isDebugEnabled": 1,
        "lengthLowerBoundRatioPercentage": float(lnk.lower_ratio),
        "lengthUpperBoundRatioPercentage": float(lnk.upper_ratio),
        "linkType": LINK_MAP_INV.get(lnk.link_type, "KeepFixedDistance"),
        "lookAtAxis": _make_vec3(_axis_bl_to_re(lnk.look_at_axis)),
    }

def _make_cone(constrained_bone, pen):
    return {
        "$type": "animDyngConstraintCone",
        "collisionCapsuleHeightExtent": float(pen.cone_collision_height),
        "collisionCapsuleRadius": float(pen.cone_collision_radius),
        "coneAttachmentBone": _make_transform_index(pen.target_bone),
        "coneTransformLS": _make_qstransform(pen.cone_transform_ls_quat, (0.0, 0.0, 0.0)),
        "constrainedBone": _make_transform_index(constrained_bone),
        "constraintType": PEND_MAP_INV.get(pen.constraint_type, "Cone"),
        "halfOfMaxApertureAngle": float(pen.half_aperture_angle),
        "isDebugEnabled": 1,
        "projectionType": PEND_PROJ_MAP_INV.get(pen.projection_type, "Disabled"),
    }

def _make_ellipsoid(owner_bone, ell):
    return {
        "$type": "animDyngConstraintEllipsoid",
        "bone": _make_transform_index(owner_bone),
        "constraintRadius": float(ell.radius),
        "constraintScale1": float(ell.scale1),
        "constraintScale2": float(ell.scale2),
        "ellipsoidTransformLS": _make_qstransform(
            ell.ellipsoid_transform_ls_quat, ell.ellipsoid_transform_ls_offset
        ),
        "isDebugEnabled": 1,
    }

def _make_collision_shape(s):
    is_sphere = s.shape_type == "SPHERE"
    x_ext = 0.0 if is_sphere else float(getattr(s, "x_box_extent", 0.0))
    y_ext = 0.0 if is_sphere else float(getattr(s, "y_box_extent", 0.0))
    z_ext = 0.0 if is_sphere else float(s.height_extent)
    return {
        "$type": "animCollisionRoundedShape",
        "bone": _make_transform_index(s.bone_name),
        "drawAxis": 1,
        "roundedCornerRadius": float(s.radius),
        "transformLS": _make_qstransform(s.rotation_ls_quat, s.offset_ls),
        "xBoxExtent": x_ext,
        "yBoxExtent": y_ext,
        "zBoxExtent": z_ext,
    }

def _make_allocator(start):
    counter = [start]
    def alloc():
        value = str(counter[0])
        counter[0] += 1
        return value
    return alloc

def _max_handle_id(node):
    found = -1
    if isinstance(node, dict):
        if "HandleId" in node:
            try:
                found = int(node["HandleId"])
            except (TypeError, ValueError):
                pass
        for v in node.values():
            found = max(found, _max_handle_id(v))
    elif isinstance(node, list):
        for v in node:
            found = max(found, _max_handle_id(v))
    return found

def _inject_simulation(sim_data, multi_data, dnode, addon_state, alloc):
    sim_data["alpha"] = float(dnode.alpha)
    sim_data["solverIterations"] = int(dnode.solver_iterations)
    sim_data["substepTime"] = float(dnode.substep_time)
    sim_data["rotateParentToLookAtDangle"] = 1 if dnode.rotate_parent_to_look_at else 0

    container = sim_data["particlesContainer"]
    container["gravityWS"] = _export_gravity_scalar()
    container["externalForceWS"] = _make_vec3(addon_state.external_force_ws)

    particles = []
    inner_constraints = []
    for ch in dnode.chains:
        for p in ch.particles:
            if not p.bone_name:
                continue
            particles.append(_make_particle(p))
            for lnk in p.link_constraints:
                if not lnk.target_bone:
                    continue
                inner_constraints.append(
                    {"HandleId": alloc(), "Data": _make_link(p.bone_name, lnk)}
                )
            for pen in p.pendulum_constraints:
                if not pen.target_bone:
                    continue
                inner_constraints.append(
                    {"HandleId": alloc(), "Data": _make_cone(p.bone_name, pen)}
                )
            for ell in p.ellipsoid_constraints:
                inner_constraints.append(
                    {"HandleId": alloc(), "Data": _make_ellipsoid(p.bone_name, ell)}
                )

    container["particles"] = particles
    multi_data["innerConstraints"] = inner_constraints

    shapes = [_make_collision_shape(s) for s in addon_state.collision_shapes]
    shapes.extend(_make_collision_shape(s) for s in dnode.collision_shapes)
    sim_data["collisionRoundedShapes"] = shapes

def _append_init_refs(root_chunk, anchor_id, new_ids):
    init_list = root_chunk.get("nodesToInit", [])
    insert_at = None
    for i, entry in enumerate(init_list):
        if entry.get("HandleRefId") == anchor_id or entry.get("HandleId") == anchor_id:
            insert_at = i + 1
            break
    refs = [{"HandleRefId": nid} for nid in new_ids]
    if insert_at is None:
        init_list.extend(refs)
    else:
        init_list[insert_at:insert_at] = refs
    root_chunk["nodesToInit"] = init_list

def export_chains(filepath, addon_state):
    doc = _load_template()
    root_chunk = doc["Data"]["RootChunk"]

    posms = _find_nodes_by_type(root_chunk, "animAnimNode_PoseMsToLs")
    if not posms:
        raise ValueError("Export template is missing an animAnimNode_PoseMsToLs node.")
    dangle_wrapper = posms[0].get("inputLink", {}).get("node")
    if not (
        isinstance(dangle_wrapper, dict)
        and isinstance(dangle_wrapper.get("Data"), dict)
        and dangle_wrapper["Data"].get("$type") == "animAnimNode_Dangle"
    ):
        raise ValueError("Export template PoseMsToLs does not feed an animAnimNode_Dangle node.")

    pristine_dangle = copy.deepcopy(dangle_wrapper)
    alloc = _make_allocator(_max_handle_id(doc) + 1)

    dangle_nodes = list(addon_state.dangle_nodes)
    if dangle_nodes:
        head_data = dangle_wrapper["Data"]
        head_sim = head_data["dangleConstraint"]["Data"]
        head_multi = head_sim["dyngConstraint"]["Data"]
        _inject_simulation(head_sim, head_multi, dangle_nodes[0], addon_state, alloc)

        graph_tail = head_data["inputLink"]["node"]
        prev_data = head_data
        appended_ids = []
        for dnode in dangle_nodes[1:]:
            unit = copy.deepcopy(pristine_dangle)
            unit["HandleId"] = alloc()
            sim_wrapper = unit["Data"]["dangleConstraint"]
            sim_wrapper["HandleId"] = alloc()
            multi_wrapper = sim_wrapper["Data"]["dyngConstraint"]
            multi_wrapper["HandleId"] = alloc()
            _inject_simulation(
                sim_wrapper["Data"], multi_wrapper["Data"], dnode, addon_state, alloc
            )
            prev_data["inputLink"]["node"] = unit
            appended_ids.append(unit["HandleId"])
            prev_data = unit["Data"]

        prev_data["inputLink"]["node"] = graph_tail
        if appended_ids:
            _append_init_refs(root_chunk, dangle_wrapper["HandleId"], appended_ids)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2)