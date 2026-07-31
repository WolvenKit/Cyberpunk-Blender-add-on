from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Tuple

from ...redSpace.qs_transform import encode_qs_transform
from ...assetio.animgraph_json import dumps as dumps_json


LINK_TO_RED = {
    "FIXED": "KeepFixedDistance",
    "VARIABLE": "KeepVariableDistance",
    "GREATER": "Greater",
    "CLOSER": "Closer",
}
PROJECTION_TO_RED = {
    "DISABLED": "Disabled",
    "SHORTEST_PATH": "ShortestPath",
    "DIRECTED": "Directed",
    "DIRECTIONAL": "Directional",
}
PENDULUM_TO_RED = {
    "CONE": "Cone",
    "HINGE_PLANE": "HingePlane",
    "HALF_CONE": "HalfCone",
}
PENDULUM_PROJECTION_TO_RED = {
    "DISABLED": "Disabled",
    "SHORTEST_PATH_ROTATIONAL": "ShortestPathRotational",
    "DIRECTED_ROTATIONAL": "DirectedRotational",
}
SOLVER_TO_RED_TYPE = {
    "DYNG": "animDangleConstraint_SimulationDyng",
    "PBD": "animDangleConstraint_SimulationPositionProjection",
    "SPRING": "animDangleConstraint_SimulationSpring",
    "PENDULUM": "animDangleConstraint_SimulationPendulum",
}


class AnimGraphPatchError(ValueError):
    pass


def _iter_nested(root: Any) -> Iterable[Any]:
    stack = [root]
    while stack:
        value = stack.pop()
        yield value
        if isinstance(value, dict):
            stack.extend(reversed(tuple(value.values())))
        elif isinstance(value, list):
            stack.extend(reversed(value))


def build_handle_maps(root: Any) -> Tuple[Dict[str, dict], Dict[str, dict]]:
    data_by_handle: Dict[str, dict] = {}
    wrapper_by_handle: Dict[str, dict] = {}
    for value in _iter_nested(root):
        if not isinstance(value, dict):
            continue
        data = value.get("Data")
        if "HandleId" not in value or not isinstance(data, dict):
            continue
        handle = str(value["HandleId"])
        if handle in data_by_handle and data_by_handle[handle] is not data:
            raise AnimGraphPatchError(f"Duplicate HandleId {handle}")
        data_by_handle[handle] = data
        wrapper_by_handle[handle] = value
    return data_by_handle, wrapper_by_handle


def resolve_handle(value: Any, data_by_handle: Mapping[str, dict]) -> Any:
    if not isinstance(value, dict):
        return value
    if isinstance(value.get("Data"), dict):
        return value["Data"]
    if "HandleRefId" in value:
        return data_by_handle.get(str(value["HandleRefId"]))
    return value


def _numeric_handle_max(root: Any) -> int:
    maximum = -1
    for value in _iter_nested(root):
        if isinstance(value, dict) and "HandleId" in value:
            try:
                maximum = max(maximum, int(str(value["HandleId"])))
            except (TypeError, ValueError):
                continue
    return maximum


def _state_list(value: Any) -> List[Any]:
    try:
        return list(value)
    except Exception:
        return []


def _get(value: Any, name: str, default: Any = None) -> Any:
    try:
        return getattr(value, name)
    except Exception:
        return default


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _vec3(values: Any, *, vector_type: str = "Vector3") -> dict:
    seq = list(values or ())
    seq += [0.0] * max(0, 3 - len(seq))
    return {
        "$type": vector_type,
        "X": _as_float(seq[0]),
        "Y": _as_float(seq[1]),
        "Z": _as_float(seq[2]),
    }


def _vec4(values: Any, *, w: float = 1.0) -> dict:
    seq = list(values or ())
    seq += [0.0] * max(0, 3 - len(seq))
    return {
        "$type": "Vector4",
        "W": _as_float(w, 1.0),
        "X": _as_float(seq[0]),
        "Y": _as_float(seq[1]),
        "Z": _as_float(seq[2]),
    }


def _cname(name: Any) -> dict:
    return {
        "$type": "CName",
        "$storage": "string",
        "$value": str(name or "None"),
    }


def _transform_index(name: Any) -> dict:
    return {"$type": "animTransformIndex", "name": _cname(name)}


def _qs_transform(offset: Any, rotation_wxyz: Any, *, translation_w: float = 1.0) -> dict:
    return encode_qs_transform(
        rotation_wxyz,
        offset,
        (1.0, 1.0, 1.0),
        translation_w=translation_w,
        scale_w=1.0,
        quaternion_order="wxyz",
    )


def _copy_template(template: Any, fallback: dict) -> dict:
    if isinstance(template, dict):
        # Normalize Blender proxy values through JSON.
        try:
            return json.loads(json.dumps(template))
        except Exception:
            return dict(template)
    return dict(fallback)


def _shape_payload(shape: Any, template: Any = None) -> dict:
    result = _copy_template(template, {"$type": "animCollisionRoundedShape"})
    result["$type"] = "animCollisionRoundedShape"
    result["bone"] = _transform_index(_get(shape, "bone_name", ""))
    result.setdefault("drawAxis", 1)
    result["roundedCornerRadius"] = _as_float(_get(shape, "radius", 0.05), 0.05)
    result["transformLS"] = _qs_transform(
        _get(shape, "offset_ls", (0.0, 0.0, 0.0)),
        _get(shape, "rotation_ls_quat", (1.0, 0.0, 0.0, 0.0)),
        translation_w=1.0,
    )
    result["xBoxExtent"] = _as_float(_get(shape, "x_box_extent", 0.0))
    result["yBoxExtent"] = _as_float(_get(shape, "y_box_extent", 0.0))
    result["zBoxExtent"] = _as_float(_get(shape, "height_extent", 0.0))
    return result


def _patch_common_simulation(sim: MutableMapping[str, Any], node: Any) -> None:
    sim["alpha"] = _as_float(_get(node, "alpha", 1.0), 1.0)
    sim["rotateParentToLookAtDangle"] = int(bool(_get(node, "rotate_parent_to_look_at", True)))
    sim["substepTime"] = _as_float(_get(node, "substep_time", 0.01), 0.01)
    sim["solverIterations"] = max(1, _as_int(_get(node, "solver_iterations", 1), 1))
    sim["parentRotationAltersTransformsOfDangleAndItsChildren"] = int(bool(
        _get(node, "parent_rotation_alters_dangle_children", False)
    ))
    sim["parentRotationAltersTransformsOfNonDanglesAndItsChildren"] = int(bool(
        _get(node, "parent_rotation_alters_non_dangle_children", False)
    ))
    sim["dangleAltersTransformsOfItsChildren"] = int(bool(
        _get(node, "dangle_alters_children", False)
    ))

    existing_shapes = sim.get("collisionRoundedShapes")
    existing_shapes = existing_shapes if isinstance(existing_shapes, list) else []
    sim["collisionRoundedShapes"] = [
        _shape_payload(shape, existing_shapes[index] if index < len(existing_shapes) else None)
        for index, shape in enumerate(_state_list(_get(node, "collision_shapes", ())))
    ]


def _particle_payload(particle: Any, template: Any = None) -> dict:
    result = _copy_template(template, {"$type": "animDyngParticle"})
    result["$type"] = "animDyngParticle"
    result["bone"] = _transform_index(_get(particle, "bone_name", ""))
    result["collisionCapsuleAxisLS"] = _vec3(_get(particle, "capsule_axis_ls", (0.5, 0.0, 0.0)))
    result["collisionCapsuleHeightExtent"] = _as_float(_get(particle, "capsule_height", 0.0))
    result["collisionCapsuleRadius"] = _as_float(_get(particle, "capsule_radius", 0.0))
    result["damping"] = _as_float(_get(particle, "damping", 1.0), 1.0)
    result.setdefault("isDebugEnabled", 1)
    result["isFree"] = int(not bool(_get(particle, "is_pinned", False)))
    result["mass"] = _as_float(_get(particle, "mass", 1.0), 1.0)
    result["projectionType"] = PROJECTION_TO_RED.get(
        str(_get(particle, "dyng_projection_type", "SHORTEST_PATH")), "ShortestPath"
    )
    result["pullForceFactor"] = _as_float(_get(particle, "pull_force", 0.0))
    return result


def _link_payload(source_bone: str, link: Any, template: Any = None) -> dict:
    result = _copy_template(template, {"$type": "animDyngConstraintLink"})
    result["$type"] = "animDyngConstraintLink"
    result["bone1"] = _transform_index(source_bone)
    result["bone2"] = _transform_index(_get(link, "target_bone", ""))
    result.setdefault("isDebugEnabled", 1)
    result["lengthLowerBoundRatioPercentage"] = _as_float(_get(link, "lower_ratio", 100.0), 100.0)
    result["lengthUpperBoundRatioPercentage"] = _as_float(_get(link, "upper_ratio", 100.0), 100.0)
    result["linkType"] = LINK_TO_RED.get(str(_get(link, "link_type", "FIXED")), "KeepFixedDistance")
    result["lookAtAxis"] = _vec3(_get(link, "look_at_axis", (1.0, 0.0, 0.0)))
    return result


def _cone_payload(constrained_bone: str, cone: Any, template: Any = None) -> dict:
    result = _copy_template(template, {"$type": "animDyngConstraintCone"})
    result["$type"] = "animDyngConstraintCone"
    result["collisionCapsuleHeightExtent"] = _as_float(_get(cone, "cone_collision_height", 0.0))
    result["collisionCapsuleRadius"] = _as_float(_get(cone, "cone_collision_radius", 0.0))
    result["coneAttachmentBone"] = _transform_index(_get(cone, "target_bone", ""))
    result["coneTransformLS"] = _qs_transform(
        _get(cone, "cone_transform_ls_offset", (0.0, 0.0, 0.0)),
        _get(cone, "cone_transform_ls_quat", (1.0, 0.0, 0.0, 0.0)),
        translation_w=1.0,
    )
    result["constrainedBone"] = _transform_index(constrained_bone)
    result["constraintType"] = PENDULUM_TO_RED.get(
        str(_get(cone, "constraint_type", "CONE")), "Cone"
    )
    result["halfOfMaxApertureAngle"] = _as_float(_get(cone, "half_aperture_angle", 45.0), 45.0)
    result.setdefault("isDebugEnabled", 0)
    result["projectionType"] = PENDULUM_PROJECTION_TO_RED.get(
        str(_get(cone, "projection_type", "DISABLED")), "Disabled"
    )
    return result


def _ellipsoid_payload(particle_bone: str, ellipsoid: Any, template: Any = None) -> dict:
    result = _copy_template(template, {"$type": "animDyngConstraintEllipsoid"})
    result["$type"] = "animDyngConstraintEllipsoid"
    result["bone"] = _transform_index(_get(ellipsoid, "target_bone", "") or particle_bone)
    result["constraintRadius"] = _as_float(_get(ellipsoid, "radius", 0.1), 0.1)
    result["constraintScale1"] = _as_float(_get(ellipsoid, "scale1", 1.0), 1.0)
    result["constraintScale2"] = _as_float(_get(ellipsoid, "scale2", 1.0), 1.0)
    result["ellipsoidTransformLS"] = _qs_transform(
        _get(ellipsoid, "ellipsoid_transform_ls_offset", (0.0, 0.0, 0.0)),
        _get(ellipsoid, "ellipsoid_transform_ls_quat", (1.0, 0.0, 0.0, 0.0)),
        translation_w=1.0,
    )
    return result


def _constraint_entries(node: Any) -> List[Tuple[str, str, Any]]:
    particles: Dict[str, Any] = {}
    all_entries: List[Tuple[str, str, int, Any]] = []
    for chain in _state_list(_get(node, "chains", ())):
        if str(_get(chain, "solver", "DYNG")) != "DYNG":
            continue
        for particle in _state_list(_get(chain, "particles", ())):
            bone = str(_get(particle, "bone_name", "") or "")
            particles[bone] = particle
            for index, link in enumerate(_state_list(_get(particle, "link_constraints", ()))):
                all_entries.append(("LINK", bone, index, link))
            for index, ellipsoid in enumerate(_state_list(_get(particle, "ellipsoid_constraints", ()))):
                all_entries.append(("ELLIPSOID", bone, index, ellipsoid))
            for index, cone in enumerate(_state_list(_get(particle, "pendulum_constraints", ()))):
                all_entries.append(("CONE", bone, index, cone))

    by_key = {(kind, bone, index): item for kind, bone, index, item in all_entries}
    ordered: List[Tuple[str, str, Any]] = []
    used = set()
    for entry in _state_list(_get(node, "constraint_order", ())):
        key = (
            str(_get(entry, "constraint_type", "") or ""),
            str(_get(entry, "particle_bone", "") or ""),
            _as_int(_get(entry, "constraint_index", 0), 0),
        )
        item = by_key.get(key)
        if item is None or key in used:
            continue
        used.add(key)
        ordered.append((key[0], key[1], item))
    for kind, bone, index, item in all_entries:
        key = (kind, bone, index)
        if key not in used:
            ordered.append((kind, bone, item))
    return ordered


def _patch_dyng(
    sim: MutableMapping[str, Any], node: Any,
    data_by_handle: MutableMapping[str, dict],
    next_handle: List[int],
) -> None:
    container = sim.get("particlesContainer")
    if not isinstance(container, dict):
        container = {"$type": "animDyngParticlesContainer"}
        sim["particlesContainer"] = container
    container["$type"] = "animDyngParticlesContainer"
    container["gravityWS"] = _as_float(_get(node, "gravity_ws", 9.81), 9.81)
    container["externalForceWS"] = _vec3(_get(node, "external_force_ws", (0.0, 0.0, 0.0)))
    container.setdefault("externalForceWsLink", {"$type": "animVectorLink", "node": None})

    state_particles: List[Any] = []
    for chain in _state_list(_get(node, "chains", ())):
        if str(_get(chain, "solver", "DYNG")) != "DYNG":
            raise AnimGraphPatchError("A Dyng source node cannot contain non-Dyng specialist chains")
        state_particles.extend(_state_list(_get(chain, "particles", ())))
    existing_particles = container.get("particles")
    existing_particles = existing_particles if isinstance(existing_particles, list) else []
    existing_by_bone = {}
    for particle in existing_particles:
        if not isinstance(particle, dict):
            continue
        try:
            bone = particle["bone"]["name"]["$value"]
        except Exception:
            continue
        existing_by_bone[str(bone)] = particle
    container["particles"] = [
        _particle_payload(
            particle,
            existing_by_bone.get(str(_get(particle, "bone_name", "")))
            or (existing_particles[index] if index < len(existing_particles) else None),
        )
        for index, particle in enumerate(state_particles)
    ]

    dyng_wrapper = sim.get("dyngConstraint")
    dyng = resolve_handle(dyng_wrapper, data_by_handle)
    if not isinstance(dyng, dict) or dyng.get("$type") != "animDyngConstraintMulti":
        handle = str(next_handle[0]); next_handle[0] += 1
        dyng = {"$type": "animDyngConstraintMulti", "innerConstraints": []}
        dyng_wrapper = {"HandleId": handle, "Data": dyng}
        sim["dyngConstraint"] = dyng_wrapper
        data_by_handle[handle] = dyng
    existing_wrappers = dyng.get("innerConstraints")
    existing_wrappers = existing_wrappers if isinstance(existing_wrappers, list) else []

    wrappers = []
    for index, (kind, particle_bone, item) in enumerate(_constraint_entries(node)):
        existing = existing_wrappers[index] if index < len(existing_wrappers) else None
        existing_data = resolve_handle(existing, data_by_handle)
        if kind == "LINK":
            data = _link_payload(particle_bone, item, existing_data)
        elif kind == "CONE":
            data = _cone_payload(particle_bone, item, existing_data)
        elif kind == "ELLIPSOID":
            data = _ellipsoid_payload(particle_bone, item, existing_data)
        else:
            continue

        if isinstance(existing, dict) and "HandleId" in existing:
            handle = str(existing["HandleId"])
            wrapper = {"HandleId": handle, "Data": data}
            data_by_handle[handle] = data
        elif (
            isinstance(existing, dict)
            and "HandleRefId" in existing
            and isinstance(existing_data, dict)
            and existing_data.get("$type") == data.get("$type")
        ):
            handle = str(existing["HandleRefId"])
            existing_data.clear()
            existing_data.update(data)
            wrapper = {"HandleRefId": handle}
            data_by_handle[handle] = existing_data
        else:
            handle = str(next_handle[0]); next_handle[0] += 1
            wrapper = {"HandleId": handle, "Data": data}
            data_by_handle[handle] = data
        wrappers.append(wrapper)
    dyng["innerConstraints"] = wrappers


def _single_particle(node: Any, expected_solver: str) -> Any:
    chains = _state_list(_get(node, "chains", ()))
    if len(chains) != 1 or str(_get(chains[0], "solver", "")) != expected_solver:
        raise AnimGraphPatchError(
            f"{expected_solver} source node must contain exactly one {expected_solver} chain"
        )
    particles = _state_list(_get(chains[0], "particles", ()))
    if len(particles) != 1:
        raise AnimGraphPatchError(f"{expected_solver} source node must contain exactly one particle")
    return particles[0]


def _patch_pbd(sim: MutableMapping[str, Any], node: Any) -> None:
    p = _single_particle(node, "PBD")
    sim["dangleBone"] = _transform_index(_get(p, "bone_name", ""))
    sim["collisionCapsuleRadius"] = _as_float(_get(p, "capsule_radius", 0.0))
    sim["collisionCapsuleHeightExtent"] = _as_float(_get(p, "capsule_height", 0.0))
    sim["collisionCapsuleAxisLS"] = _vec3(_get(p, "capsule_axis_ls", (0.5, 0.0, 0.0)))
    sim["projectionType"] = PROJECTION_TO_RED.get(str(_get(p, "pos_projection_type", "SHORTEST_PATH")), "ShortestPath")
    sim["directionReferenceBone"] = _transform_index(_get(p, "direction_reference_bone", ""))


def _patch_spring(sim: MutableMapping[str, Any], node: Any) -> None:
    p = _single_particle(node, "SPRING")
    sim["dangleBone"] = _transform_index(_get(p, "bone_name", ""))
    sim["mass"] = _as_float(_get(p, "mass", 1.0), 1.0)
    sim["damping"] = _as_float(_get(p, "damping", 1.0), 1.0)
    sim["pullForceFactor"] = _as_float(_get(p, "pull_force", 0.0))
    sim["simulationFps"] = _as_float(_get(p, "spring_simulation_fps", 10.0), 10.0)
    sim["constraintSphereRadius"] = _as_float(_get(p, "spring_constraint_radius", 0.5), 0.5)
    sim["constraintScale1"] = _as_float(_get(p, "spring_constraint_scale1", 1.0), 1.0)
    sim["constraintScale2"] = _as_float(_get(p, "spring_constraint_scale2", 1.0), 1.0)
    orientation = list(_get(p, "spring_constraint_orientation", (0.0, 90.0)) or ())
    orientation += [0.0] * max(0, 2 - len(orientation))
    sim["constraintOrientation"] = {"$type": "Vector2", "X": _as_float(orientation[0]), "Y": _as_float(orientation[1])}
    sim["pullForceOriginLS"] = _vec3(_get(p, "spring_pull_force_origin_ls", (0.0, 0.0, 0.0)))
    sim["projectionType"] = PROJECTION_TO_RED.get(str(_get(p, "spring_projection_type", "SHORTEST_PATH")), "ShortestPath")
    sim["collisionSphereRadius"] = _as_float(_get(p, "spring_collision_radius", 0.0))
    sim["gravityWS"] = _as_float(_get(node, "gravity_ws", 9.81), 9.81)
    sim["externalForceWS"] = _vec3(_get(node, "external_force_ws", (0.0, 0.0, 0.0)))


def _patch_pendulum(sim: MutableMapping[str, Any], node: Any) -> None:
    p = _single_particle(node, "PENDULUM")
    sim["dangleBone"] = _transform_index(_get(p, "bone_name", ""))
    sim["mass"] = _as_float(_get(p, "mass", 1.0), 1.0)
    sim["damping"] = _as_float(_get(p, "damping", 1.0), 1.0)
    sim["pullForceFactor"] = _as_float(_get(p, "pull_force", 0.0))
    sim["simulationFps"] = _as_float(_get(p, "pendulum_simulation_fps", 10.0), 10.0)
    sim["constraintType"] = PENDULUM_TO_RED.get(str(_get(p, "pendulum_constraint_type", "CONE")), "Cone")
    sim["halfOfMaxApertureAngle"] = _as_float(_get(p, "pendulum_half_aperture_angle", 45.0), 45.0)
    sim["constraintOrientation"] = _vec3(_get(p, "pendulum_constraint_orientation", (90.0, 0.0, 0.0)))
    sim["pullForceDirectionLS"] = _vec3(_get(p, "pendulum_pull_force_direction_ls", (0.0, 0.0, 0.0)))
    sim["projectionType"] = PENDULUM_PROJECTION_TO_RED.get(
        str(_get(p, "pendulum_projection_type", "SHORTEST_PATH_ROTATIONAL")),
        "ShortestPathRotational",
    )
    sim["collisionCapsuleRadius"] = _as_float(_get(p, "pendulum_collision_radius", 0.0))
    sim["collisionCapsuleHeightExtent"] = _as_float(_get(p, "pendulum_collision_height", 0.0))
    sim["gravityWS"] = _as_float(_get(node, "gravity_ws", 9.81), 9.81)
    sim["externalForceWS"] = _vec3(_get(node, "external_force_ws", (0.0, 0.0, 0.0)))


def _source_handle(value: Any) -> str:
    text = str(value or "")
    return text.split(":", 1)[1] if text.startswith("handle:") else text


def _runtime_handles(data_by_handle: Mapping[str, dict], node_type: str) -> List[str]:
    return [handle for handle, data in data_by_handle.items() if data.get("$type") == node_type]


def _operation_handles(state: Any, node_type: str) -> Dict[int, str]:
    result: Dict[int, str] = {}
    for operation in _state_list(_get(state, "evaluation_order", ())):
        if str(_get(operation, "node_type", "")) != node_type:
            continue
        handle = _source_handle(_get(operation, "source_handle", ""))
        if not handle or handle in {"editor", "fallback"}:
            continue
        result.setdefault(_as_int(_get(operation, "node_index", 0)), handle)
    return result


def _patch_dangle_nodes(payload: dict, state: Any, data_by_handle: MutableMapping[str, dict], next_handle: List[int]) -> int:
    nodes = _state_list(_get(state, "dangle_nodes", ()))
    source_handles = _runtime_handles(data_by_handle, "animAnimNode_Dangle")
    if len(nodes) != len(source_handles):
        raise AnimGraphPatchError(
            "The specialist Dangle editor can patch imported Dangle nodes, but cannot "
            f"change graph topology ({len(source_handles)} source nodes, {len(nodes)} editor nodes). "
            "Use the Graph View to add or remove runtime nodes."
        )
    mapped = _operation_handles(state, "DANGLE")
    used = set()
    patched = 0
    for index, node in enumerate(nodes):
        handle = mapped.get(index)
        if handle not in data_by_handle or data_by_handle.get(handle, {}).get("$type") != "animAnimNode_Dangle":
            handle = next((h for h in source_handles if h not in used), "")
        if not handle:
            raise AnimGraphPatchError(f"Could not map Dangle editor node {index} to a source HandleId")
        used.add(handle)
        runtime_node = data_by_handle[handle]
        sim = resolve_handle(runtime_node.get("dangleConstraint"), data_by_handle)
        if not isinstance(sim, dict):
            raise AnimGraphPatchError(f"Dangle HandleId {handle} has no resolvable dangleConstraint")

        chains = _state_list(_get(node, "chains", ()))
        solver = str(_get(chains[0], "solver", "DYNG")) if chains else "DYNG"
        expected_type = SOLVER_TO_RED_TYPE.get(solver)
        source_type = str(sim.get("$type", ""))
        if not expected_type or source_type != expected_type:
            raise AnimGraphPatchError(
                f"Dangle HandleId {handle} changed solver from {source_type or '<unknown>'} "
                f"to {expected_type or solver}; use the Graph View for runtime type changes"
            )
        _patch_common_simulation(sim, node)
        if solver == "DYNG":
            _patch_dyng(sim, node, data_by_handle, next_handle)
        elif solver == "PBD":
            _patch_pbd(sim, node)
        elif solver == "SPRING":
            _patch_spring(sim, node)
        elif solver == "PENDULUM":
            _patch_pendulum(sim, node)
        patched += 1
    return patched


def _patch_drag_nodes(state: Any, data_by_handle: Mapping[str, dict]) -> int:
    nodes = _state_list(_get(state, "drag_nodes", ()))
    source_handles = _runtime_handles(data_by_handle, "animAnimNode_Drag")
    if len(nodes) != len(source_handles):
        raise AnimGraphPatchError(
            "The specialist Dangle editor can patch imported Drag nodes, but cannot "
            f"change graph topology ({len(source_handles)} source nodes, {len(nodes)} editor nodes)."
        )
    mapped = _operation_handles(state, "DRAG")
    used = set()
    patched = 0
    for index, node in enumerate(nodes):
        handle = mapped.get(index)
        if handle not in data_by_handle or data_by_handle.get(handle, {}).get("$type") != "animAnimNode_Drag":
            handle = next((h for h in source_handles if h not in used), "")
        if not handle:
            raise AnimGraphPatchError(f"Could not map Drag editor node {index} to a source HandleId")
        used.add(handle)
        raw = data_by_handle[handle]
        raw["sourceBone"] = _transform_index(_get(node, "source_bone_name", "") or _get(node, "bone_name", ""))
        raw["outTargetBone"] = _transform_index(_get(node, "bone_name", ""))
        raw["simulationFps"] = _as_float(_get(node, "simulation_fps", 120.0), 120.0)
        raw["sourceSpeedMultiplier"] = _as_float(_get(node, "source_speed_multiplier", 10.0), 10.0)
        raw["hasOvershoot"] = int(bool(_get(node, "has_overshoot", False)))
        raw["overshootDetectionMinSpeed"] = _as_float(_get(node, "overshoot_detection_min_speed", 0.4), 0.4)
        raw["overshootDetectionMaxSpeed"] = _as_float(_get(node, "overshoot_detection_max_speed", 4.0), 4.0)
        raw["overshootDuration"] = _as_float(_get(node, "overshoot_duration", 1.0), 1.0)
        raw["useSteps"] = int(bool(_get(node, "use_steps", False)))
        raw["stepsTargetSpeedMultiplier"] = _as_float(_get(node, "steps_target_speed_multiplier", 10000.0), 10000.0)
        raw["timeBetweenSteps"] = _as_float(_get(node, "time_between_steps", 0.1), 0.1)
        raw["timeInStep"] = _as_float(_get(node, "time_in_step", 0.1), 0.1)
        patched += 1
    return patched


def patch_wolvenkit_payload(
    payload: dict, state: Any, *, export_path: str = "", update_header: bool = True
) -> dict:
    root = (((payload or {}).get("Data") or {}).get("RootChunk") or {})
    if not isinstance(root, dict) or root.get("$type") != "animAnimGraph":
        raise AnimGraphPatchError("Expected Data.RootChunk.$type == animAnimGraph")
    data_by_handle, _wrappers = build_handle_maps(payload)
    next_handle = [_numeric_handle_max(payload) + 1]
    dangles = _patch_dangle_nodes(payload, state, data_by_handle, next_handle)
    drags = _patch_drag_nodes(state, data_by_handle)

    header = payload.setdefault("Header", {})
    if not isinstance(header, dict):
        header = {}; payload["Header"] = header
    header.setdefault("WolvenKitVersion", "8.18.2")
    header.setdefault("WKitJsonVersion", "0.0.9")
    header.setdefault("GameVersion", 2310)
    header["DataType"] = "CR2W"
    if update_header:
        header["ExportedDateTime"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        if export_path:
            basename = os.path.basename(export_path)
            archive = basename[:-5] if basename.lower().endswith(".json") else basename
            header["ArchiveFileName"] = archive
    payload.setdefault("Data", {}).setdefault("EmbeddedFiles", [])
    payload["_cp77_dangle_export_summary"] = {"dangleNodes": dangles, "dragNodes": drags}
    return payload


def strip_private_export_metadata(payload: dict) -> dict:
    payload.pop("_cp77_dangle_export_summary", None)
    return payload


def validate_payload(payload: dict) -> dict:
    errors: List[str] = []
    warnings: List[str] = []
    root = (((payload or {}).get("Data") or {}).get("RootChunk") or {})
    if not isinstance(root, dict) or root.get("$type") != "animAnimGraph":
        errors.append("Data.RootChunk is not animAnimGraph")

    handles: Dict[str, int] = {}
    refs: List[str] = []
    for value in _iter_nested(payload):
        if not isinstance(value, dict):
            continue
        if "HandleId" in value:
            handle = str(value["HandleId"])
            handles[handle] = handles.get(handle, 0) + 1
            if not isinstance(value.get("Data"), dict):
                errors.append(f"HandleId {handle} has no Data object")
        if "HandleRefId" in value:
            refs.append(str(value["HandleRefId"]))
    for handle, count in handles.items():
        if count != 1:
            errors.append(f"HandleId {handle} occurs {count} times")
    for ref in refs:
        if ref not in handles:
            errors.append(f"HandleRefId {ref} does not resolve")

    dangle_count = 0
    drag_count = 0
    for value in _iter_nested(payload):
        if not isinstance(value, dict):
            continue
        if value.get("$type") == "animAnimNode_Dangle":
            dangle_count += 1
        elif value.get("$type") == "animAnimNode_Drag":
            drag_count += 1
    if not dangle_count and not drag_count:
        warnings.append("Graph contains no Dangle or Drag runtime nodes")
    return {
        "ready": not errors,
        "errors": errors,
        "warnings": warnings,
        "handles": len(handles),
        "references": len(refs),
        "dangleNodes": dangle_count,
        "dragNodes": drag_count,
    }


def dumps_pretty(payload: dict) -> str:
    return dumps_json(payload, indent=2) + "\n"


def write_json(filepath: str, payload: dict) -> None:
    text = dumps_pretty(strip_private_export_metadata(payload))
    with open(filepath, "w", encoding="utf-8", newline="\n") as stream:
        stream.write(text)
