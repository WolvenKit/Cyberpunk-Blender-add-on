import os

import bpy

from ....animation.domain.animgraph.animation_scope import (
    available_animation_names,
    graph_animation_names,
)
from ....animation.domain.animgraph.constraint_tree import constraint_leaves
from ....animation.domain.animgraph.math_expression import MathExpressionError
from ....animation.domain.animgraph.pose_program import compile_pose_program
from ....animation.domain.animgraph.topology import (
    nested_values,
    visual_tag_requirements,
)
from ....animation.domain.animgraph.vector_preview import (
    collect_dangle_force_requirements,
    collect_vector_input_requirements,
)
from ....assetio import animgraph_json as json_io
from ....assetio.transform_values import (
    quaternion_ijkr_from_wxyz,
    quaternion_wxyz_from_ijkr,
    quaternion_wxyz_from_wkit,
    vector3_from_data,
)
from ....bartmoss.vehicle import STANDARD_GRAVITY
from ....blender.armature_bones import rig_space_contract
from ....core.log import get_logger
from ....gltf.provenance import SOURCE_PATH_KEY
from ....redSpace.contracts import (
    EDITOR_SPACE_CONTRACT,
    RIG_SPACE_CONTRACT_CURRENT,
    RIG_SPACE_CONTRACT_DIRECT,
)
from .simulation import spaces

_LOG = get_logger(__name__)

EDITOR_FORMAT = "DanglePhysicsEditor"
EDITOR_VERSION = 14

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


def _resolve_handle(obj, node_map):
    if not isinstance(obj, dict):
        return obj
    if "HandleRefId" in obj:
        handle_id = obj["HandleRefId"]
        resolved = node_map.get(handle_id)
        if resolved is None:
            resolved = node_map.get(str(handle_id))
        return resolved if resolved is not None else {}
    if "Data" in obj:
        return obj["Data"]
    return obj


def _build_document_index(obj, target_types):
    targets = set(target_types)
    node_map = {}
    node_ids = {}
    nodes_by_type = {target_type: [] for target_type in targets}
    for value in nested_values(obj):
        if not isinstance(value, dict):
            continue
        data = value.get("Data")
        if "HandleId" in value and isinstance(data, dict):
            handle_id = str(value["HandleId"])
            node_map[handle_id] = data
            node_ids[id(data)] = handle_id
        node_type = value.get("$type")
        if node_type in nodes_by_type:
            nodes_by_type[node_type].append(value)
    return node_map, node_ids, nodes_by_type


def _collect_graph_operations(
    data, node_map, addon_state, *, available_animations=frozenset()
):
    root = data.get("Data", {}).get("RootChunk", {})
    tags = frozenset(
        tag.strip() for tag in addon_state.preview_visual_tags.split(",") if tag.strip()
    )
    arm_obj = getattr(addon_state, "id_data", None)
    arm_data = getattr(arm_obj, "data", None)
    rig_tags = frozenset(
        str(tag)
        for tag in (
            arm_data.get("cp77_rig_tags", ()) if hasattr(arm_data, "get") else ()
        )
        if str(tag or "") and str(tag) != "None"
    )
    component_tags = frozenset(
        tag.strip()
        for tag in str(getattr(addon_state, "preview_component_tags", "") or "").split(
            ","
        )
        if tag.strip()
    )
    return compile_pose_program(
        root.get("rootNode"),
        node_map,
        visual_tags=tags,
        skeletal_lod=int(getattr(addon_state, "preview_skeletal_lod", 0) or 0),
        performance_mode=bool(getattr(addon_state, "preview_performance_mode", False)),
        available_animations=available_animations,
        rig_tags=rig_tags,
        parent_tags=component_tags,
    )


def _sync_preview_requirements(data, node_map, addon_state):
    look_at_parts = set()
    for node in node_map.values():
        if (
            isinstance(node, dict)
            and node.get("$type") == "animAnimNode_LookAtController"
        ):
            for part in node.get("orderedBodyParts", ()) or ():
                name = part.get("partName", "")
                if isinstance(name, dict):
                    name = name.get("$value", "")
                if name and name != "None":
                    look_at_parts.add(str(name))
    addon_state.preview_look_at_parts = ",".join(sorted(look_at_parts))
    previous_values = {
        str(item.key): tuple(item.value)
        for item in getattr(addon_state, "preview_vector_inputs", ())
    }
    addon_state.preview_vector_inputs.clear()
    addon_state.preview_visual_tag_requirements.clear()
    addon_state.preview_input_error = ""

    root = data.get("Data", {}).get("RootChunk", {})
    try:
        tag_requirements = visual_tag_requirements(root.get("rootNode"), node_map)
    except ValueError as error:
        tag_requirements = ()
        addon_state.preview_input_error = str(error)
    for tag, graph_path in tag_requirements:
        item = addon_state.preview_visual_tag_requirements.add()
        item.tag = str(tag)
        item.graph_path = str(graph_path)

    requirements = list(collect_vector_input_requirements(data))
    requirement_keys = {requirement.key for requirement in requirements}
    for node in addon_state.dangle_nodes:
        node.external_force_preview_error = ""
        if not node.external_force_linked or not node.source_handle:
            continue
        try:
            node_requirements = collect_dangle_force_requirements(
                data, [str(node.source_handle)]
            )
        except MathExpressionError as error:
            node.external_force_preview_error = str(error)
            continue
        for requirement in node_requirements:
            if requirement.key not in requirement_keys:
                requirement_keys.add(requirement.key)
                requirements.append(requirement)
    for requirement in requirements:
        if requirement.group in look_at_parts and requirement.name in {
            "target",
            "rawTarget",
        }:
            continue
        item = addon_state.preview_vector_inputs.add()
        item.key = requirement.key
        item.group = requirement.group
        item.input_name = requirement.name
        item.source_handle = requirement.source_handle
        item.value = previous_values.get(requirement.key, (0.0, 0.0, 0.0))


def _preview_animation_scope(data):
    graph_names = graph_animation_names(data)
    available = available_animation_names(
        data,
        getattr(getattr(bpy, "data", None), "actions", None),
    )
    return graph_names, available


def _log_preview_compile_context(
    stage, data, addon_state, graph_names, available, plan=None, *, error=None
):
    arm_obj = getattr(addon_state, "id_data", None)
    root = data.get("Data", {}).get("RootChunk", {}) if isinstance(data, dict) else {}
    root_ref = root.get("rootNode") if isinstance(root, dict) else None
    root_handle = ""
    root_type = ""
    if isinstance(root_ref, dict):
        root_handle = str(
            root_ref.get("HandleId", root_ref.get("HandleRefId", "")) or ""
        )
        if "HandleRefId" in root_ref:
            root_data = _build_document_index(data, ())[0].get(
                str(root_ref.get("HandleRefId")), {}
            )
        else:
            root_data = (
                root_ref.get("Data")
                if isinstance(root_ref.get("Data"), dict)
                else root_ref
            )
        root_type = (
            str(root_data.get("$type", "") or "") if isinstance(root_data, dict) else ""
        )
    missing = tuple(sorted(set(graph_names) - set(available)))
    actions = getattr(getattr(bpy, "data", None), "actions", None)
    action_sources = {}
    for name in sorted(graph_names):
        action = (
            actions.get(name)
            if actions is not None and hasattr(actions, "get")
            else None
        )
        if action is None:
            action_sources[name] = None
            continue
        action_sources[name] = (
            str(action.get(SOURCE_PATH_KEY, "") or "") if hasattr(action, "get") else ""
        )
    boundaries = tuple(getattr(plan, "boundaries", ()) or ())
    _LOG.debug(
        "AnimGraph preview compile context: stage=%s rig=%s root_type=%s root_handle=%s "
        "lod=%d performance_mode=%s visual_tags=%r graph_animations=%r "
        "available_animations=%r missing_graph_animations=%r action_sources=%r boundaries=%r error=%s",
        stage,
        getattr(arm_obj, "name", "<none>"),
        root_type or "<unknown>",
        root_handle or "<inline>",
        int(getattr(addon_state, "preview_skeletal_lod", 0) or 0),
        bool(getattr(addon_state, "preview_performance_mode", False)),
        tuple(
            sorted(
                tag.strip()
                for tag in str(
                    getattr(addon_state, "preview_visual_tags", "") or ""
                ).split(",")
                if tag.strip()
            )
        ),
        tuple(sorted(graph_names)),
        tuple(sorted(available)),
        missing,
        action_sources,
        boundaries,
        f"{type(error).__name__}: {error}" if error is not None else "<none>",
    )
    if boundaries or error is not None:
        _LOG.warning(
            "AnimGraph preview compile issue: stage=%s rig=%s boundaries=%r error=%s",
            stage,
            getattr(arm_obj, "name", "<none>"),
            boundaries,
            f"{type(error).__name__}: {error}" if error is not None else "<none>",
        )


def refresh_graph_operations(data, addon_state):
    """Recompile operation selection without replacing edited solver settings"""
    node_map, _node_ids, _nodes_by_type = _build_document_index(data, ())
    _sync_preview_requirements(data, node_map, addon_state)
    graph_names, available = _preview_animation_scope(data)
    try:
        plan = _collect_graph_operations(
            data, node_map, addon_state, available_animations=available
        )
    except Exception as error:
        _log_preview_compile_context(
            "refresh", data, addon_state, graph_names, available, error=error
        )
        raise
    _log_preview_compile_context(
        "refresh", data, addon_state, graph_names, available, plan
    )
    indices = {
        "DANGLE": {
            node.source_handle: i for i, node in enumerate(addon_state.dangle_nodes)
        },
        "DRAG": {
            node.source_handle: i for i, node in enumerate(addon_state.drag_nodes)
        },
    }
    operations, boundaries = [], list(plan.boundaries)
    for kind, identity, path in plan.operations:
        source_identity = (
            f"handle:{identity}"
            if identity and not identity.startswith("handle:")
            else identity
        )
        node_index = indices[kind].get(source_identity)
        if node_index is None:
            boundaries.append(
                f"{path}: {kind} {source_identity} has no editable simulation; reimport the graph"
            )
        else:
            operations.append((kind, node_index, source_identity, path))
    addon_state.evaluation_order.clear()
    addon_state.graph_compiled = True
    addon_state.evaluation_boundary = "\n".join(boundaries)
    if not boundaries:
        for operation in operations:
            _append_graph_operation(addon_state, *operation)


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
        shape.bone_name,
        shape.radius,
        (shape.x_box_extent, shape.y_box_extent, shape.height_extent),
        shape.offset_ls,
        shape.rotation_ls_quat,
    )


def _add_collision_shape(collection, values, existing=None, *, deduplicate=True):
    key = _shape_key_values(
        values["bone"],
        values["radius"],
        values["extents"],
        values["offset"],
        values["rotation"],
    )
    if existing is None:
        existing = {_shape_key(shape) for shape in collection}
    if deduplicate and key in existing:
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
            bone_name
            for p in particles_array
            if (bone_name := _get_bone_name(p, "bone"))
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


def _make_node_label(sim_data, bone_set):
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
            n.lstrip("lr").lstrip("_") if n[:2] in ("l_", "r_") else n for n in bone_set
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


def _parse_dangle_as_node(sim_data, addon_state, node_map, node_label):
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
    grav = _get_wk(force_owner, "gravityWS", STANDARD_GRAVITY)
    grav_val = (
        float(grav.get("Z", STANDARD_GRAVITY))
        if isinstance(grav, dict)
        else float(grav)
    )
    ext_force = _get_wk(force_owner, "externalForceWS", {})
    ef = (
        vector3_from_data(ext_force) if isinstance(ext_force, dict) else (0.0, 0.0, 0.0)
    )

    if is_dyng:
        if any(abs(v) > 0 for v in ef):
            addon_state.external_force_ws = ef
        addon_state.substep_time = min(addon_state.substep_time, node_substep)
        addon_state.solver_iterations = max(addon_state.solver_iterations, node_iters)

    dnode = addon_state.dangle_nodes.add()
    dnode.source_identity_version = 1
    dnode.name = node_label
    dnode.alpha = node_alpha
    dnode.rotate_parent_to_look_at = node_rotate
    dnode.substep_time = node_substep
    dnode.solver_iterations = node_iters
    dnode.imported_solver_iterations = raw_iters
    dnode.gravity_ws = grav_val
    dnode.external_force_ws = ef
    import_warnings = []
    force_link = _get_wk(force_owner, "externalForceWsLink", {}) or {}
    dnode.external_force_linked = force_link.get("node") is not None
    resource = _get_wk(sim_data, "jsonCollisionShapes", {}) or {}
    depot = resource.get("DepotPath", {})
    path = str(depot.get("$value", "")) if isinstance(depot, dict) else str(depot or "")
    if path not in {"", "0", "None"}:
        import_warnings.append(
            f"External collision resource is preserved but not evaluated: {path}"
        )
    dnode.import_warnings = "\n".join(import_warnings)
    inherited_flag_default = (
        0 if sim_data.get("$type") == "animDangleConstraint_SimulationDyng" else 1
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
            "offset": vector3_from_data(_get_wk(t_ls, "Translation", {})),
            "rotation": quaternion_wxyz_from_wkit(_get_wk(t_ls, "Rotation", {})),
        }
        shape = _add_collision_shape(
            dnode.collision_shapes, values, node_shape_keys, deduplicate=False
        )
        shape.source_index = si
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
        particle.capsule_axis_ls = vector3_from_data(
            _get_wk(sim_data, "collisionCapsuleAxisLS", {}),
            default=(0.5, 0.0, 0.0),
        )
        raw_projection = str(_get_wk(sim_data, "projectionType", "ShortestPath"))
        particle.pos_projection_type = PROJ_MAP.get(raw_projection, "SHORTEST_PATH")
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
        particle.spring_simulation_fps = float(_get_wk(sim_data, "simulationFps", 10.0))
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
        particle.spring_pull_force_origin_ls = vector3_from_data(
            _get_wk(sim_data, "pullForceOriginLS", {})
        )
        raw_projection = str(_get_wk(sim_data, "projectionType", "ShortestPath"))
        particle.spring_projection_type = PROJ_MAP.get(raw_projection, "SHORTEST_PATH")
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
        particle.pendulum_pull_force_direction_ls = vector3_from_data(
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

    imported_particle_indices = []
    for source_index, p_raw in enumerate(particles_array):
        b_name = _get_bone_name(p_raw, "bone")
        if not b_name:
            continue
        pfx = _bone_prefix(b_name)
        if pfx not in chain_groups:
            chain_groups[pfx] = []
            chain_order.append(pfx)
        chain_groups[pfx].append((source_index, p_raw))
        imported_particle_indices.append(source_index)

    particle_lookup = {}

    for pfx in chain_order:
        ch = dnode.chains.add()
        ch.name = pfx
        ch.solver = "DYNG"
        ch_idx = len(dnode.chains) - 1

        for source_index, p_raw in chain_groups[pfx]:
            b_name = _get_bone_name(p_raw, "bone")
            p = ch.particles.add()
            p.source_index = source_index
            p.bone_name = b_name
            p.mass = float(_get_wk(p_raw, "mass", 1.0))
            p.damping = float(_get_wk(p_raw, "damping", 1.0))
            p.pull_force = float(_get_wk(p_raw, "pullForceFactor", 0.0))
            p.is_pinned = not bool(_get_wk(p_raw, "isFree", 1))
            p.capsule_radius = float(_get_wk(p_raw, "collisionCapsuleRadius", 0.0))
            p.capsule_height = float(
                _get_wk(p_raw, "collisionCapsuleHeightExtent", 0.0)
            )
            axis_raw = _get_wk(p_raw, "collisionCapsuleAxisLS", {})
            p.capsule_axis_ls = vector3_from_data(axis_raw, default=(0.5, 0.0, 0.0))
            raw_proj = str(_get_wk(p_raw, "projectionType", "ShortestPath"))
            p.dyng_projection_type = PROJ_MAP.get(raw_proj, "SHORTEST_PATH")

            particle_lookup[b_name] = (ch_idx, len(ch.particles) - 1)

    dyng_ref = _get_wk(sim_data, "dyngConstraint", {})

    dnode.particle_source_indices = json_io.dumps(
        imported_particle_indices, indent=None
    )
    imported_paths = []
    warnings = list(import_warnings)
    for source_path, ref, c_node in constraint_leaves(dyng_ref, node_map):
        c_type = c_node.get("$type")
        item = None
        if c_type == "animDyngConstraintLink":
            b1 = _get_bone_name(c_node, "bone1")
            b2 = _get_bone_name(c_node, "bone2")
            if b1 in particle_lookup:
                ci, pi = particle_lookup[b1]
                target_p = dnode.chains[ci].particles[pi]
                lnk = target_p.link_constraints.add()
                lnk.source_path = source_path
                item = lnk
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
                re_axis = vector3_from_data(la_raw, default=(1.0, 0.0, 0.0))
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
                pen.source_path = source_path
                item = pen
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
                pen.cone_transform_ls_quat = quaternion_wxyz_from_wkit(rot_raw)
                pen.cone_transform_ls_offset = vector3_from_data(
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
                ell.source_path = source_path
                item = ell
                ell.target_bone = b_name
                ell.radius = float(_get_wk(c_node, "constraintRadius", 0.1))
                ell.scale1 = float(_get_wk(c_node, "constraintScale1", 1.0))
                ell.scale2 = float(_get_wk(c_node, "constraintScale2", 1.0))
                exf = _get_wk(c_node, "ellipsoidTransformLS", {})
                if exf:
                    rot_raw = _get_wk(exf, "Rotation", {})
                    ell.ellipsoid_transform_ls_quat = quaternion_wxyz_from_wkit(rot_raw)
                    trans_raw = _get_wk(exf, "Translation", {})
                    ell.ellipsoid_transform_ls_offset = vector3_from_data(trans_raw)
                order = dnode.constraint_order.add()
                order.constraint_type = "ELLIPSOID"
                order.particle_bone = b_name
                order.constraint_index = len(target_p.ellipsoid_constraints) - 1

        if item is not None:
            imported_paths.append(source_path)
        else:
            warnings.append(
                f"{source_path}: {c_type or 'unknown constraint'} is preserved but not evaluated"
            )
    dnode.constraint_source_paths = json_io.dumps(imported_paths, indent=None)
    dnode.import_warnings = "\n".join(warnings)

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
    node_map, node_ids, nodes_by_type = _build_document_index(
        data,
        {
            "animAnimNode_Root",
            "animAnimNode_Output",
            "animAnimNode_Dangle",
            "animAnimNode_Drag",
        },
    )
    graph_names, available = _preview_animation_scope(data)
    try:
        plan = _collect_graph_operations(
            data, node_map, addon_state, available_animations=available
        )
    except Exception as error:
        _log_preview_compile_context(
            "import", data, addon_state, graph_names, available, error=error
        )
        raise
    _log_preview_compile_context(
        "import", data, addon_state, graph_names, available, plan
    )

    addon_state.graph_compiled = True
    addon_state.evaluation_boundary = "\n".join(plan.boundaries)
    ordered = plan.operations

    dangle_indices = {}
    drag_indices = {}
    parsed_dangle_nodes = set()
    parsed_drag_nodes = set()

    for node_type, raw_handle, path in ordered:
        raw_node = node_map.get(str(raw_handle))
        if not isinstance(raw_node, dict):
            addon_state.evaluation_boundary = (
                addon_state.evaluation_boundary + "\n"
                if addon_state.evaluation_boundary
                else ""
            ) + f"{path}: {node_type} handle:{raw_handle} does not resolve"
            continue
        identity = f"handle:{raw_handle}"
        if node_type == "DANGLE":
            info = _extract_dangle_info(raw_node, node_map)
            if info is None or not info[2]:
                continue
            if identity not in dangle_indices:
                _dangle, sim_data, bone_set, _sim_type = info
                label = _make_node_label(sim_data, bone_set)
                dangle_indices[identity] = _parse_dangle_as_node(
                    sim_data, addon_state, node_map, label
                )
                addon_state.dangle_nodes[
                    dangle_indices[identity]
                ].source_handle = identity
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
                addon_state.drag_nodes[parsed].source_handle = identity
            parsed_drag_nodes.add(id(raw_node))
            _append_graph_operation(
                addon_state, "DRAG", drag_indices[identity], identity, path
            )

    # Preserve disconnected authoring nodes for editing, but do not execute them.
    # They still retain their source HandleId so specialist export can patch them
    # without relying on positional fallback mapping.
    for disconnected_index, raw_node in enumerate(nodes_by_type["animAnimNode_Dangle"]):
        if id(raw_node) in parsed_dangle_nodes:
            continue
        info = _extract_dangle_info(raw_node, node_map)
        if info is None or not info[2]:
            continue
        _dangle, sim_data, bone_set, _sim_type = info
        label = _make_node_label(sim_data, bone_set)
        node_index = _parse_dangle_as_node(sim_data, addon_state, node_map, label)
        handle_id = node_ids.get(id(raw_node))
        identity = (
            f"handle:{handle_id}" if handle_id is not None else f"inline:{id(raw_node)}"
        )
        addon_state.dangle_nodes[node_index].source_handle = identity

    for disconnected_index, raw_node in enumerate(nodes_by_type["animAnimNode_Drag"]):
        if id(raw_node) in parsed_drag_nodes:
            continue
        source = _get_bone_name(raw_node, "sourceBone")
        target = _get_bone_name(raw_node, "outTargetBone") or source
        if not source or not target:
            continue
        parsed = _parse_drag_node(raw_node, addon_state)
        if parsed is not None:
            handle_id = node_ids.get(id(raw_node))
            identity = (
                f"handle:{handle_id}"
                if handle_id is not None
                else f"inline:{id(raw_node)}"
            )
            addon_state.drag_nodes[parsed].source_handle = identity

    _sync_preview_requirements(data, node_map, addon_state)
    addon_state.substeps = max(1, int(round((1.0 / 60.0) / addon_state.substep_time)))
    return len(addon_state.dangle_nodes)


def _clear_addon_state(addon_state):
    addon_state.is_playing = False
    addon_state.graph_compiled = False
    addon_state.evaluation_boundary = ""
    addon_state.preview_input_error = ""
    addon_state.preview_vector_inputs.clear()
    addon_state.preview_visual_tag_requirements.clear()
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
        "sourceIndex": shape.source_index,
        "name": shape.name,
        "bone": shape.bone_name,
        "shapeType": shape.shape_type,
        "radius": shape.radius,
        "xBoxExtent": shape.x_box_extent,
        "yBoxExtent": shape.y_box_extent,
        "zBoxExtent": shape.height_extent,
        "offsetLS": list(shape.offset_ls),
        "rotationLS": list(quaternion_ijkr_from_wxyz(shape.rotation_ls_quat)),
    }


def _serialize_editor_state(addon_state):
    arm_obj = getattr(addon_state, "id_data", None)
    data = {
        "format": EDITOR_FORMAT,
        "version": EDITOR_VERSION,
        "coordinateSpace": EDITOR_SPACE_CONTRACT,
        "rigSpaceContract": rig_space_contract(arm_obj),
        "runtime": "ORDERED_DYNG_POSITION_PROJECTION_SPRING_PENDULUM_DRAG",
        "externalForceWS": list(addon_state.external_force_ws),
        "substepTime": addon_state.substep_time,
        "substeps": addon_state.substeps,
        "solverIterations": addon_state.solver_iterations,
        "collisionShapes": [_serialize_shape(s) for s in addon_state.collision_shapes],
        "dangleNodes": [],
        "dragNodes": [],
        "graphCompiled": addon_state.graph_compiled,
        "evaluationBoundary": addon_state.evaluation_boundary,
        "previewMode": addon_state.preview_mode,
        "previewVisualTags": addon_state.preview_visual_tags,
        "previewComponentTags": addon_state.preview_component_tags,
        "previewForceWS": list(addon_state.preview_force_ws),
        "previewInputError": addon_state.preview_input_error,
        "previewVectorInputs": [
            {
                "key": item.key,
                "group": item.group,
                "name": item.input_name,
                "sourceHandle": item.source_handle,
                "value": list(item.value),
            }
            for item in addon_state.preview_vector_inputs
        ],
        "previewVisualTagRequirements": [
            {"tag": item.tag, "graphPath": item.graph_path}
            for item in addon_state.preview_visual_tag_requirements
        ],
        "activeDangleNode": addon_state.active_dangle_node,
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
            "sourceIdentityVersion": dnode.source_identity_version,
            "constraintSourcePaths": dnode.constraint_source_paths,
            "particleSourceIndices": dnode.particle_source_indices,
            "importWarnings": dnode.import_warnings,
            "externalForceLinked": dnode.external_force_linked,
            "externalForcePreviewError": dnode.external_force_preview_error,
            "sourceHandle": dnode.source_handle,
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
                    "sourceIndex": particle.source_index,
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
                    "pendulumSimulationFps": getattr(
                        particle, "pendulum_simulation_fps", 10.0
                    ),
                    "pendulumConstraintType": getattr(
                        particle, "pendulum_constraint_type", "CONE"
                    ),
                    "pendulumHalfApertureAngle": getattr(
                        particle, "pendulum_half_aperture_angle", 45.0
                    ),
                    "pendulumConstraintOrientation": list(
                        getattr(
                            particle,
                            "pendulum_constraint_orientation",
                            (90.0, 0.0, 0.0),
                        )
                    ),
                    "pendulumPullForceDirectionLS": list(
                        getattr(
                            particle,
                            "pendulum_pull_force_direction_ls",
                            (0.0, 0.0, 0.0),
                        )
                    ),
                    "pendulumProjectionType": getattr(
                        particle, "pendulum_projection_type", "SHORTEST_PATH_ROTATIONAL"
                    ),
                    "pendulumCollisionRadius": getattr(
                        particle, "pendulum_collision_radius", 0.0
                    ),
                    "pendulumCollisionHeight": getattr(
                        particle, "pendulum_collision_height", 0.0
                    ),
                    "links": [],
                    "ellipsoids": [],
                    "pendulums": [],
                }
                for link in particle.link_constraints:
                    particle_data["links"].append(
                        {
                            "sourcePath": link.source_path,
                            "targetBone": link.target_bone,
                            "linkType": link.link_type,
                            "lowerRatio": link.lower_ratio,
                            "upperRatio": link.upper_ratio,
                            "stiffness": link.stiffness,
                            "explicitRestDistance": link.explicit_rest_distance,
                            "lookAtAxis": list(link.look_at_axis),
                        }
                    )
                for ellipsoid in particle.ellipsoid_constraints:
                    particle_data["ellipsoids"].append(
                        {
                            "sourcePath": ellipsoid.source_path,
                            "targetBone": ellipsoid.target_bone,
                            "radius": ellipsoid.radius,
                            "scale1": ellipsoid.scale1,
                            "scale2": ellipsoid.scale2,
                            "transformLsQuat": list(
                                quaternion_ijkr_from_wxyz(
                                    ellipsoid.ellipsoid_transform_ls_quat
                                )
                            ),
                            "transformLsOffset": list(
                                ellipsoid.ellipsoid_transform_ls_offset
                            ),
                        }
                    )
                for pendulum in particle.pendulum_constraints:
                    particle_data["pendulums"].append(
                        {
                            "sourcePath": pendulum.source_path,
                            "targetBone": pendulum.target_bone,
                            "constraintType": pendulum.constraint_type,
                            "halfApertureAngle": pendulum.half_aperture_angle,
                            "projectionType": pendulum.projection_type,
                            "coneCollisionRadius": pendulum.cone_collision_radius,
                            "coneCollisionHeight": pendulum.cone_collision_height,
                            "coneTransformLsQuat": list(
                                quaternion_ijkr_from_wxyz(
                                    pendulum.cone_transform_ls_quat
                                )
                            ),
                            "coneTransformLsOffset": list(
                                pendulum.cone_transform_ls_offset
                            ),
                        }
                    )
                chain_data["particles"].append(particle_data)
            node_data["chains"].append(chain_data)
        data["dangleNodes"].append(node_data)

    for drag in addon_state.drag_nodes:
        data["dragNodes"].append(
            {
                "sourceHandle": drag.source_handle,
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
            }
        )
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
        "shape_type": str(raw.get("shapeType", _shape_type_from_extents(extents))),
        "radius": float(raw.get("radius", 0.05)),
        "extents": extents,
        "offset": _sequence(raw.get("offsetLS"), 3, (0.0, 0.0, 0.0)),
        "rotation": quaternion_wxyz_from_ijkr(raw.get("rotationLS")),
    }
    shape = _add_collision_shape(collection, values, existing, deduplicate=False)
    shape.source_index = int(raw.get("sourceIndex", -1))
    return shape


def _parse_editor_state(data, addon_state):
    if not isinstance(data, dict) or not isinstance(data.get("dangleNodes", []), list):
        raise ValueError("Invalid Dangle Physics Editor JSON")

    coordinate_space = data.get("coordinateSpace")
    supported_spaces = {
        None,
        EDITOR_SPACE_CONTRACT,
        RIG_SPACE_CONTRACT_CURRENT,
        RIG_SPACE_CONTRACT_DIRECT,
    }
    if coordinate_space not in supported_spaces:
        raise ValueError(
            f"Unsupported Dangle editor coordinate space: {coordinate_space}"
        )
    # Versions up to 12 already hold game-space values and need no migration.

    addon_state.graph_compiled = bool(data.get("graphCompiled", False))
    addon_state.evaluation_boundary = str(data.get("evaluationBoundary", ""))
    addon_state.preview_mode = str(data.get("previewMode", "GRAPH"))
    addon_state.preview_visual_tags = str(data.get("previewVisualTags", ""))
    addon_state.preview_component_tags = str(data.get("previewComponentTags", ""))
    addon_state.preview_force_ws = _sequence(
        data.get("previewForceWS"), 3, (0.0, 0.0, 0.0)
    )
    addon_state.preview_input_error = str(data.get("previewInputError", ""))
    for raw_input in data.get("previewVectorInputs", []):
        if not isinstance(raw_input, dict):
            continue
        item = addon_state.preview_vector_inputs.add()
        item.key = str(raw_input.get("key", ""))
        item.group = str(raw_input.get("group", ""))
        item.input_name = str(raw_input.get("name", ""))
        item.source_handle = str(raw_input.get("sourceHandle", ""))
        item.value = _sequence(raw_input.get("value"), 3, (0.0, 0.0, 0.0))
    for raw_tag in data.get("previewVisualTagRequirements", []):
        if not isinstance(raw_tag, dict):
            continue
        item = addon_state.preview_visual_tag_requirements.add()
        item.tag = str(raw_tag.get("tag", ""))
        item.graph_path = str(raw_tag.get("graphPath", ""))
    addon_state.active_dangle_node = max(0, int(data.get("activeDangleNode", 0)))

    addon_state.external_force_ws = _sequence(
        data.get("externalForceWS"), 3, (0.0, 0.0, 0.0)
    )
    addon_state.substep_time = max(
        0.005, min(0.1, float(data.get("substepTime", 0.01)))
    )
    addon_state.substeps = max(1, int(data.get("substeps", 1)))
    addon_state.solver_iterations = max(1, min(8, int(data.get("solverIterations", 1))))

    global_shape_keys = set()
    for raw_shape in data.get("collisionShapes", []):
        _parse_editor_shape(raw_shape, addon_state.collision_shapes, global_shape_keys)

    for raw_node in data.get("dangleNodes", []):
        node = addon_state.dangle_nodes.add()
        node.source_identity_version = int(raw_node.get("sourceIdentityVersion", 0))
        node.constraint_source_paths = str(raw_node.get("constraintSourcePaths", "[]"))
        node.particle_source_indices = str(raw_node.get("particleSourceIndices", "[]"))
        node.import_warnings = str(raw_node.get("importWarnings", ""))
        node.external_force_linked = bool(raw_node.get("externalForceLinked", False))
        node.external_force_preview_error = str(
            raw_node.get("externalForcePreviewError", "")
        )
        node.source_handle = str(raw_node.get("sourceHandle", ""))
        node.name = str(
            raw_node.get("name", f"DangleNode_{len(addon_state.dangle_nodes)}")
        )
        node.alpha = float(raw_node.get("alpha", 1.0))
        node.rotate_parent_to_look_at = bool(raw_node.get("rotateParentToLookAt", True))
        node.look_at_axis = _sequence(raw_node.get("lookAtAxis"), 3, (1.0, 0.0, 0.0))
        node.gravity_ws = float(
            raw_node.get("gravityWS", data.get("gravityWS", STANDARD_GRAVITY))
        )
        node.external_force_ws = _sequence(
            raw_node.get("externalForceWS"), 3, tuple(addon_state.external_force_ws)
        )
        node.substep_time = max(
            0.005,
            min(0.1, float(raw_node.get("substepTime", addon_state.substep_time))),
        )
        node.solver_iterations = max(
            1,
            min(
                8, int(raw_node.get("solverIterations", addon_state.solver_iterations))
            ),
        )
        node.imported_solver_iterations = max(
            0, int(raw_node.get("importedSolverIterations", node.solver_iterations))
        )
        raw_chains = raw_node.get("chains", [])
        authored_solver = (
            str(raw_chains[0].get("solver", "DYNG")) if raw_chains else "DYNG"
        )
        inherited_flag_default = authored_solver != "DYNG"
        node.parent_rotation_alters_dangle_children = bool(
            raw_node.get("parentRotationAltersDangleChildren", inherited_flag_default)
        )
        node.parent_rotation_alters_non_dangle_children = bool(
            raw_node.get(
                "parentRotationAltersNonDangleChildren", inherited_flag_default
            )
        )
        node.dangle_alters_children = bool(
            raw_node.get("dangleAltersChildren", inherited_flag_default)
        )

        for raw_order in raw_node.get("constraintOrder", []):
            entry = node.constraint_order.add()
            entry.constraint_type = str(raw_order.get("type", "LINK"))
            entry.particle_bone = str(raw_order.get("particleBone", ""))
            entry.constraint_index = max(0, int(raw_order.get("constraintIndex", 0)))

        node_shape_keys = set()
        for raw_shape in raw_node.get("collisionShapes", []):
            _parse_editor_shape(raw_shape, node.collision_shapes, node_shape_keys)

        for raw_chain in raw_chains:
            chain = node.chains.add()
            chain.name = str(raw_chain.get("name", "Chain"))
            chain.solver = str(raw_chain.get("solver", "DYNG"))
            for raw_particle in raw_chain.get("particles", []):
                particle = chain.particles.add()
                particle.source_index = int(raw_particle.get("sourceIndex", -1))
                particle.bone_name = str(raw_particle.get("bone", ""))
                particle.mass = float(raw_particle.get("mass", 1.0))
                particle.damping = float(raw_particle.get("damping", 1.0))
                particle.pull_force = float(raw_particle.get("pullForceFactor", 0.0))
                particle.is_pinned = not bool(raw_particle.get("isFree", True))
                particle.capsule_radius = float(
                    raw_particle.get("collisionCapsuleRadius", 0.0)
                )
                particle.capsule_height = float(
                    raw_particle.get("collisionCapsuleHeightExtent", 0.0)
                )
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
                    3,
                    (90.0, 0.0, 0.0),
                )
                particle.pendulum_pull_force_direction_ls = _sequence(
                    raw_particle.get("pendulumPullForceDirectionLS"),
                    3,
                    (0.0, 0.0, 0.0),
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
                    link.source_path = str(raw_link.get("sourcePath", ""))
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
                    ellipsoid.source_path = str(raw_ellipsoid.get("sourcePath", ""))
                    ellipsoid.target_bone = str(raw_ellipsoid.get("targetBone", ""))
                    ellipsoid.radius = float(raw_ellipsoid.get("radius", 0.1))
                    ellipsoid.scale1 = float(raw_ellipsoid.get("scale1", 1.0))
                    ellipsoid.scale2 = float(raw_ellipsoid.get("scale2", 1.0))
                    ellipsoid.ellipsoid_transform_ls_quat = quaternion_wxyz_from_ijkr(
                        raw_ellipsoid.get("transformLsQuat")
                    )
                    ellipsoid.ellipsoid_transform_ls_offset = _sequence(
                        raw_ellipsoid.get("transformLsOffset"), 3, (0.0, 0.0, 0.0)
                    )

                for raw_pendulum in raw_particle.get("pendulums", []):
                    pendulum = particle.pendulum_constraints.add()
                    pendulum.source_path = str(raw_pendulum.get("sourcePath", ""))
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
                    pendulum.cone_transform_ls_quat = quaternion_wxyz_from_ijkr(
                        raw_pendulum.get("coneTransformLsQuat")
                    )
                    pendulum.cone_transform_ls_offset = _sequence(
                        raw_pendulum.get("coneTransformLsOffset"),
                        3,
                        (0.0, 0.0, 0.0),
                    )

    for raw_drag in data.get("dragNodes", []):
        drag = addon_state.drag_nodes.add()
        drag.source_handle = str(raw_drag.get("sourceHandle", ""))
        target = str(raw_drag.get("outTargetBone", raw_drag.get("bone", "")))
        drag.source_bone_name = str(raw_drag.get("sourceBone", target))
        drag.bone_name = target
        drag.simulation_fps = float(raw_drag.get("simulationFps", 100.0))
        drag.source_speed_multiplier = float(
            raw_drag.get("sourceSpeedMultiplier", 10.0)
        )
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
            addon_state,
            node_type,
            node_index,
            str(raw_operation.get("sourceHandle", "editor")),
            str(raw_operation.get("graphPath", "editor")),
        )

    if not addon_state.graph_compiled and not getattr(
        addon_state, "evaluation_order", ()
    ):
        for node_index in range(len(addon_state.dangle_nodes)):
            _append_graph_operation(
                addon_state,
                "DANGLE",
                node_index,
                "editor-fallback",
                f"editor.dangle[{node_index}]",
            )
        for node_index in range(len(addon_state.drag_nodes)):
            _append_graph_operation(
                addon_state,
                "DRAG",
                node_index,
                "editor-fallback",
                f"editor.drag[{node_index}]",
            )

    return len(addon_state.dangle_nodes)


def import_chains_data(data, addon_state):
    is_wolvenkit = (
        isinstance(data, dict)
        and isinstance(data.get("Header"), dict)
        and "WolvenKitVersion" in data["Header"]
    )
    if not is_wolvenkit:
        raise ValueError("Expected a WolvenKit animgraph JSON export")

    backup = _serialize_editor_state(addon_state)
    _clear_addon_state(addon_state)
    try:
        count = _parse_wolvenkit_animgraph(data, addon_state)

        arm_obj = getattr(addon_state, "id_data", None)
        space_errors = spaces.armature_space_errors(arm_obj)
        if space_errors:
            raise ValueError(space_errors[0])
        return count
    except Exception:
        _clear_addon_state(addon_state)
        _parse_editor_state(backup, addon_state)
        raise
