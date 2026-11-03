from __future__ import annotations

import math
import os
from collections.abc import Iterable, Mapping, MutableMapping
from typing import Any

from ...animation.domain.animgraph.constraint_tree import constraint_leaves
from ...animation.domain.animgraph.topology import (
    initialization_handles,
    nested_values,
    state_machine_diagnostics,
)
from ...animation.model.animgraph.handles import normalized_source_handle
from ...animation.model.animgraph.indices import transform_index
from ...animation.model.animgraph.schema import registry, rtti
from ...assetio.animgraph_json import dumps, loads
from ...assetio.atomic import atomic_write_text
from ...assetio.headers import (
    SUPPORTED_GAME_VERSION,
    SUPPORTED_WKIT_JSON_VERSION,
    SUPPORTED_WOLVENKIT_VERSION,
    utc_timestamp,
)
from ...assetio.paths import strip_json_suffix
from ...assetio.transform_values import encode_qs_transform
from ...assetio.values import coerce_float, coerce_int
from ...bartmoss.vehicle import STANDARD_GRAVITY
from ...core.log import debug_exception, get_logger
from .references import normalize_inline_first_references

_LOG = get_logger(__name__)

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


def _build_handle_index(
    root: Any,
) -> tuple[dict[str, dict], dict[str, dict], int]:
    data_by_handle: dict[str, dict] = {}
    wrapper_by_handle: dict[str, dict] = {}
    maximum = -1
    for value in nested_values(root):
        if not isinstance(value, dict):
            continue
        if "HandleId" in value:
            try:
                maximum = max(maximum, int(str(value["HandleId"])))
            except (TypeError, ValueError):
                pass
        data = value.get("Data")
        if "HandleId" not in value or not isinstance(data, dict):
            continue
        handle = str(value["HandleId"])
        if handle in data_by_handle and data_by_handle[handle] is not data:
            raise AnimGraphPatchError(f"Duplicate HandleId {handle}")
        data_by_handle[handle] = data
        wrapper_by_handle[handle] = value
    return data_by_handle, wrapper_by_handle, maximum


def resolve_handle(value: Any, data_by_handle: Mapping[str, dict]) -> Any:
    if not isinstance(value, dict):
        return value
    if isinstance(value.get("Data"), dict):
        return value["Data"]
    if "HandleRefId" in value:
        return data_by_handle.get(str(value["HandleRefId"]))
    return value


def _state_list(value: Any) -> list[Any]:
    try:
        return list(value)
    except (ReferenceError, TypeError):
        return []


def _get(value: Any, name: str, default: Any = None) -> Any:
    try:
        return getattr(value, name, default)
    except ReferenceError:
        return default


def _vec3(values: Any, *, vector_type: str = "Vector3") -> dict:
    seq = list(values or ())
    seq += [0.0] * max(0, 3 - len(seq))
    return {
        "$type": vector_type,
        "X": coerce_float(seq[0], unwrap=False),
        "Y": coerce_float(seq[1], unwrap=False),
        "Z": coerce_float(seq[2], unwrap=False),
    }


def _qs_transform(
    offset: Any, rotation_wxyz: Any, *, translation_w: float = 1.0
) -> dict:
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
            return loads(dumps(template, indent=None))
        except Exception:
            debug_exception(
                _LOG,
                "Could not deep-copy the template through JSON; using a shallow copy",
            )
            return dict(template)
    return dict(fallback)


def _shape_payload(shape: Any, template: Any = None) -> dict:
    result = _copy_template(template, {"$type": "animCollisionRoundedShape"})
    result["$type"] = "animCollisionRoundedShape"
    result["bone"] = transform_index(_get(shape, "bone_name", ""))
    result.setdefault("drawAxis", 1)
    result["roundedCornerRadius"] = coerce_float(
        _get(shape, "radius", 0.05), 0.05, unwrap=False
    )
    source_transform = result.get("transformLS")
    result["transformLS"] = _qs_transform(
        _get(shape, "offset_ls", (0.0, 0.0, 0.0)),
        _get(shape, "rotation_ls_quat", (1.0, 0.0, 0.0, 0.0)),
        translation_w=1.0,
    )
    if isinstance(source_transform, dict) and "Scale" in source_transform:
        result["transformLS"]["Scale"] = source_transform["Scale"]

    result["xBoxExtent"] = coerce_float(_get(shape, "x_box_extent", 0.0), unwrap=False)
    result["yBoxExtent"] = coerce_float(_get(shape, "y_box_extent", 0.0), unwrap=False)
    result["zBoxExtent"] = coerce_float(_get(shape, "height_extent", 0.0), unwrap=False)
    return result


def _patch_common_simulation(sim: MutableMapping[str, Any], node: Any) -> None:
    sim["alpha"] = coerce_float(_get(node, "alpha", 1.0), 1.0, unwrap=False)
    sim["rotateParentToLookAtDangle"] = int(
        bool(_get(node, "rotate_parent_to_look_at", True))
    )
    # Substeps and solver iterations are animDangleConstraint_SimulationDyng properties only.
    if (
        str(sim.get("$type", "")) == "animDangleConstraint_SimulationDyng"
        or "substepTime" in sim
    ):
        sim["substepTime"] = coerce_float(
            _get(node, "substep_time", 0.01), 0.01, unwrap=False
        )
    if (
        str(sim.get("$type", "")) == "animDangleConstraint_SimulationDyng"
        or "solverIterations" in sim
    ):
        sim["solverIterations"] = max(
            1, coerce_int(_get(node, "solver_iterations", 1), 1, unwrap=False)
        )
    chains = _state_list(_get(node, "chains", ()))
    solver = str(_get(chains[0], "solver", "DYNG")) if chains else "DYNG"
    inherited_flag_default = solver != "DYNG"
    sim["parentRotationAltersTransformsOfDangleAndItsChildren"] = int(
        bool(
            _get(node, "parent_rotation_alters_dangle_children", inherited_flag_default)
        )
    )
    sim["parentRotationAltersTransformsOfNonDanglesAndItsChildren"] = int(
        bool(
            _get(
                node,
                "parent_rotation_alters_non_dangle_children",
                inherited_flag_default,
            )
        )
    )
    sim["dangleAltersTransformsOfItsChildren"] = int(
        bool(_get(node, "dangle_alters_children", inherited_flag_default))
    )

    existing_shapes = sim.get("collisionRoundedShapes")
    existing_shapes = existing_shapes if isinstance(existing_shapes, list) else []
    sim["collisionRoundedShapes"] = [
        _shape_payload(
            shape,
            existing_shapes[shape.source_index]
            if 0 <= shape.source_index < len(existing_shapes)
            else None,
        )
        for index, shape in enumerate(_state_list(_get(node, "collision_shapes", ())))
    ]


def _particle_payload(particle: Any, template: Any = None) -> dict:
    result = _copy_template(template, {"$type": "animDyngParticle"})
    result["$type"] = "animDyngParticle"
    result["bone"] = transform_index(_get(particle, "bone_name", ""))
    result["collisionCapsuleAxisLS"] = _vec3(
        _get(particle, "capsule_axis_ls", (0.5, 0.0, 0.0))
    )
    result["collisionCapsuleHeightExtent"] = coerce_float(
        _get(particle, "capsule_height", 0.0), unwrap=False
    )
    result["collisionCapsuleRadius"] = coerce_float(
        _get(particle, "capsule_radius", 0.0), unwrap=False
    )
    result["damping"] = coerce_float(_get(particle, "damping", 1.0), 1.0, unwrap=False)
    result.setdefault("isDebugEnabled", 1)
    result["isFree"] = int(not bool(_get(particle, "is_pinned", False)))
    result["mass"] = coerce_float(_get(particle, "mass", 1.0), 1.0, unwrap=False)
    result["projectionType"] = PROJECTION_TO_RED.get(
        str(_get(particle, "dyng_projection_type", "SHORTEST_PATH")), "ShortestPath"
    )
    result["pullForceFactor"] = coerce_float(
        _get(particle, "pull_force", 0.0), unwrap=False
    )
    return result


def _link_payload(source_bone: str, link: Any, template: Any = None) -> dict:
    result = _copy_template(template, {"$type": "animDyngConstraintLink"})
    result["$type"] = "animDyngConstraintLink"
    result["bone1"] = transform_index(source_bone)
    result["bone2"] = transform_index(_get(link, "target_bone", ""))
    result.setdefault("isDebugEnabled", 1)
    result["lengthLowerBoundRatioPercentage"] = coerce_float(
        _get(link, "lower_ratio", 100.0), 100.0, unwrap=False
    )
    result["lengthUpperBoundRatioPercentage"] = coerce_float(
        _get(link, "upper_ratio", 100.0), 100.0, unwrap=False
    )
    result["linkType"] = LINK_TO_RED.get(
        str(_get(link, "link_type", "FIXED")), "KeepFixedDistance"
    )
    result["lookAtAxis"] = _vec3(_get(link, "look_at_axis", (1.0, 0.0, 0.0)))
    return result


def _cone_payload(constrained_bone: str, cone: Any, template: Any = None) -> dict:
    result = _copy_template(template, {"$type": "animDyngConstraintCone"})
    result["$type"] = "animDyngConstraintCone"
    result["collisionCapsuleHeightExtent"] = coerce_float(
        _get(cone, "cone_collision_height", 0.0), unwrap=False
    )
    result["collisionCapsuleRadius"] = coerce_float(
        _get(cone, "cone_collision_radius", 0.0), unwrap=False
    )
    result["coneAttachmentBone"] = transform_index(_get(cone, "target_bone", ""))
    source_transform = result.get("coneTransformLS")
    result["coneTransformLS"] = _qs_transform(
        _get(cone, "cone_transform_ls_offset", (0.0, 0.0, 0.0)),
        _get(cone, "cone_transform_ls_quat", (1.0, 0.0, 0.0, 0.0)),
        translation_w=1.0,
    )
    if isinstance(source_transform, dict) and "Scale" in source_transform:
        result["coneTransformLS"]["Scale"] = source_transform["Scale"]

    result["constrainedBone"] = transform_index(constrained_bone)
    result["constraintType"] = PENDULUM_TO_RED.get(
        str(_get(cone, "constraint_type", "CONE")), "Cone"
    )
    result["halfOfMaxApertureAngle"] = coerce_float(
        _get(cone, "half_aperture_angle", 45.0), 45.0, unwrap=False
    )
    result.setdefault("isDebugEnabled", 0)
    result["projectionType"] = PENDULUM_PROJECTION_TO_RED.get(
        str(_get(cone, "projection_type", "DISABLED")), "Disabled"
    )
    return result


def _ellipsoid_payload(
    particle_bone: str, ellipsoid: Any, template: Any = None
) -> dict:
    result = _copy_template(template, {"$type": "animDyngConstraintEllipsoid"})
    result["$type"] = "animDyngConstraintEllipsoid"
    result["bone"] = transform_index(
        _get(ellipsoid, "target_bone", "") or particle_bone
    )
    result["constraintRadius"] = coerce_float(
        _get(ellipsoid, "radius", 0.1), 0.1, unwrap=False
    )
    result["constraintScale1"] = coerce_float(
        _get(ellipsoid, "scale1", 1.0), 1.0, unwrap=False
    )
    result["constraintScale2"] = coerce_float(
        _get(ellipsoid, "scale2", 1.0), 1.0, unwrap=False
    )
    source_transform = result.get("ellipsoidTransformLS")
    result["ellipsoidTransformLS"] = _qs_transform(
        _get(ellipsoid, "ellipsoid_transform_ls_offset", (0.0, 0.0, 0.0)),
        _get(ellipsoid, "ellipsoid_transform_ls_quat", (1.0, 0.0, 0.0, 0.0)),
        translation_w=1.0,
    )
    if isinstance(source_transform, dict) and "Scale" in source_transform:
        result["ellipsoidTransformLS"]["Scale"] = source_transform["Scale"]

    return result


def _constraint_entries(node: Any) -> list[tuple[str, str, Any]]:
    all_entries: list[tuple[str, str, int, Any]] = []
    for chain in _state_list(_get(node, "chains", ())):
        if str(_get(chain, "solver", "DYNG")) != "DYNG":
            continue
        for particle in _state_list(_get(chain, "particles", ())):
            bone = str(_get(particle, "bone_name", "") or "")
            for index, link in enumerate(
                _state_list(_get(particle, "link_constraints", ()))
            ):
                all_entries.append(("LINK", bone, index, link))
            for index, ellipsoid in enumerate(
                _state_list(_get(particle, "ellipsoid_constraints", ()))
            ):
                all_entries.append(("ELLIPSOID", bone, index, ellipsoid))
            for index, cone in enumerate(
                _state_list(_get(particle, "pendulum_constraints", ()))
            ):
                all_entries.append(("CONE", bone, index, cone))

    by_key = {(kind, bone, index): item for kind, bone, index, item in all_entries}
    ordered: list[tuple[str, str, Any]] = []
    used = set()
    for entry in _state_list(_get(node, "constraint_order", ())):
        key = (
            str(_get(entry, "constraint_type", "") or ""),
            str(_get(entry, "particle_bone", "") or ""),
            coerce_int(_get(entry, "constraint_index", 0), 0, unwrap=False),
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
    sim: MutableMapping[str, Any],
    node: Any,
    data_by_handle: MutableMapping[str, dict],
    next_handle: list[int],
) -> None:
    container = sim.get("particlesContainer")
    if not isinstance(container, dict):
        container = {"$type": "animDyngParticlesContainer"}
        sim["particlesContainer"] = container
    container["$type"] = "animDyngParticlesContainer"
    container["gravityWS"] = coerce_float(
        _get(node, "gravity_ws", STANDARD_GRAVITY), STANDARD_GRAVITY, unwrap=False
    )
    container["externalForceWS"] = _vec3(
        _get(node, "external_force_ws", (0.0, 0.0, 0.0))
    )
    container.setdefault(
        "externalForceWsLink", {"$type": "animVectorLink", "node": None}
    )

    state_particles: list[Any] = []
    for chain in _state_list(_get(node, "chains", ())):
        if str(_get(chain, "solver", "DYNG")) != "DYNG":
            raise AnimGraphPatchError(
                "A Dyng source node cannot contain non-Dyng specialist chains"
            )
        state_particles.extend(_state_list(_get(chain, "particles", ())))
    existing_particles = container.get("particles")
    existing_particles = (
        existing_particles if isinstance(existing_particles, list) else []
    )
    imported_indices = set(loads(_get(node, "particle_source_indices", "[]")))
    particles_by_index = {}
    new_particles = []
    for particle in state_particles:
        index = int(_get(particle, "source_index", -1))
        if index < 0:
            new_particles.append(_particle_payload(particle))
        elif (
            index not in imported_indices
            or index >= len(existing_particles)
            or index in particles_by_index
        ):
            raise AnimGraphPatchError(
                "Particle source identity is stale or duplicated; reimport the graph"
            )
        else:
            particles_by_index[index] = _particle_payload(
                particle, existing_particles[index]
            )
    container["particles"] = [
        particles_by_index.get(index, particle)
        for index, particle in enumerate(existing_particles)
        if index not in imported_indices or index in particles_by_index
    ] + new_particles

    dyng_wrapper = sim.get("dyngConstraint")
    leaves = list(constraint_leaves(dyng_wrapper, data_by_handle))
    source_leaves = {path: (reference, data) for path, reference, data in leaves}
    imported_paths = set(loads(_get(node, "constraint_source_paths", "[]")))
    retained_paths = set()
    patched_payloads = {}
    new_constraints = []
    payload_functions = {
        "LINK": _link_payload,
        "CONE": _cone_payload,
        "ELLIPSOID": _ellipsoid_payload,
    }
    for kind, particle_bone, item in _constraint_entries(node):
        path = str(_get(item, "source_path", "") or "")
        if path:
            if (
                path not in imported_paths
                or path not in source_leaves
                or path in retained_paths
            ):
                raise AnimGraphPatchError(
                    "Constraint source identity is stale or duplicated; reimport the graph"
                )
            _reference, existing_data = source_leaves[path]
            data = payload_functions[kind](particle_bone, item, existing_data)
            if data["$type"] != existing_data.get("$type"):
                raise AnimGraphPatchError(f"Constraint type changed at {path}")
            identity = id(existing_data)
            signature = dumps(data, indent=None)
            if identity in patched_payloads and patched_payloads[identity] != signature:
                raise AnimGraphPatchError(
                    f"Shared constraint has conflicting edits at {path}"
                )
            patched_payloads[identity] = signature
            existing_data.clear()
            existing_data.update(data)
            retained_paths.add(path)
        else:
            handle = str(next_handle[0])
            next_handle[0] += 1
            data = payload_functions[kind](particle_bone, item)
            new_constraints.append({"HandleId": handle, "Data": data})
            data_by_handle[handle] = data

    removed_paths = imported_paths - retained_paths
    edits = []
    stack = [(dyng_wrapper, "root", frozenset())]
    while stack:
        reference, path, active = stack.pop()
        data = resolve_handle(reference, data_by_handle)
        if not isinstance(data, dict) or data.get("$type") != "animDyngConstraintMulti":
            continue
        if id(data) in active:
            raise AnimGraphPatchError("Constraint tree contains a cycle")
        active = active | {id(data)}
        children = data.get("innerConstraints") or []
        edits.append(
            (
                data,
                [
                    child
                    for i, child in enumerate(children)
                    if f"{path}/{i}" not in removed_paths
                ],
            )
        )
        stack.extend((child, f"{path}/{i}", active) for i, child in enumerate(children))
    shared_edits = {}
    for data, children in edits:
        signature = dumps(children, indent=None)
        identity = id(data)
        if identity in shared_edits and shared_edits[identity] != signature:
            raise AnimGraphPatchError(
                "Shared constraint subtree has conflicting deletions"
            )
        shared_edits[identity] = signature
    for data, children in edits:
        data["innerConstraints"] = children
    dyng = resolve_handle(dyng_wrapper, data_by_handle)
    if "root" in removed_paths:
        dyng_wrapper = None
        dyng = None
    if new_constraints or dyng is None:
        if not isinstance(dyng, dict) or dyng.get("$type") != "animDyngConstraintMulti":
            handle = str(next_handle[0])
            next_handle[0] += 1
            dyng = {
                "$type": "animDyngConstraintMulti",
                "innerConstraints": [dyng_wrapper] if dyng_wrapper else [],
            }
            sim["dyngConstraint"] = {"HandleId": handle, "Data": dyng}
            data_by_handle[handle] = dyng
        dyng["innerConstraints"].extend(new_constraints)


def _single_particle(node: Any, expected_solver: str) -> Any:
    chains = _state_list(_get(node, "chains", ()))
    if len(chains) != 1 or str(_get(chains[0], "solver", "")) != expected_solver:
        raise AnimGraphPatchError(
            f"{expected_solver} source node must contain exactly one {expected_solver} chain"
        )
    particles = _state_list(_get(chains[0], "particles", ()))
    if len(particles) != 1:
        raise AnimGraphPatchError(
            f"{expected_solver} source node must contain exactly one particle"
        )
    return particles[0]


def _patch_pbd(sim: MutableMapping[str, Any], node: Any) -> None:
    p = _single_particle(node, "PBD")
    sim["dangleBone"] = transform_index(_get(p, "bone_name", ""))
    sim["collisionCapsuleRadius"] = coerce_float(
        _get(p, "capsule_radius", 0.0), unwrap=False
    )
    sim["collisionCapsuleHeightExtent"] = coerce_float(
        _get(p, "capsule_height", 0.0), unwrap=False
    )
    axis = tuple(_get(p, "capsule_axis_ls", (0.5, 0.0, 0.0)) or ())
    if sum(float(value) * float(value) for value in axis[:3]) < 0.0001:
        axis = (0.5, 0.0, 0.0)
    sim["collisionCapsuleAxisLS"] = _vec3(axis)
    sim["projectionType"] = PROJECTION_TO_RED.get(
        str(_get(p, "pos_projection_type", "SHORTEST_PATH")), "ShortestPath"
    )
    sim["directionReferenceBone"] = transform_index(
        _get(p, "direction_reference_bone", "")
    )


def _patch_spring(sim: MutableMapping[str, Any], node: Any) -> None:
    p = _single_particle(node, "SPRING")
    sim["dangleBone"] = transform_index(_get(p, "bone_name", ""))
    mass = max(0.01, coerce_float(_get(p, "mass", 1.0), 1.0, unwrap=False))
    sim["mass"] = mass
    sim["damping"] = coerce_float(_get(p, "damping", 1.0), 1.0, unwrap=False)
    sim["pullForceFactor"] = coerce_float(_get(p, "pull_force", 0.0), unwrap=False)
    sim["simulationFps"] = max(
        10.0, coerce_float(_get(p, "spring_simulation_fps", 10.0), 10.0, unwrap=False)
    )
    sim["constraintSphereRadius"] = max(
        0.0, coerce_float(_get(p, "spring_constraint_radius", 0.5), 0.5, unwrap=False)
    )
    sim["constraintScale1"] = max(
        0.01, coerce_float(_get(p, "spring_constraint_scale1", 1.0), 1.0, unwrap=False)
    )
    sim["constraintScale2"] = max(
        0.01, coerce_float(_get(p, "spring_constraint_scale2", 1.0), 1.0, unwrap=False)
    )
    orientation = list(_get(p, "spring_constraint_orientation", (0.0, 90.0)) or ())
    orientation += [0.0] * max(0, 2 - len(orientation))
    angle_x = max(0.0, coerce_float(orientation[0], unwrap=False))
    angle_y = max(0.0, coerce_float(orientation[1], unwrap=False))
    sim["constraintOrientation"] = {"$type": "Vector2", "X": angle_x, "Y": angle_y}
    sim["pullForceOriginLS"] = _vec3(
        _get(p, "spring_pull_force_origin_ls", (0.0, 0.0, 0.0))
    )
    sim["projectionType"] = PROJECTION_TO_RED.get(
        str(_get(p, "spring_projection_type", "SHORTEST_PATH")), "ShortestPath"
    )
    sim["collisionSphereRadius"] = max(
        0.0, coerce_float(_get(p, "spring_collision_radius", 0.0), unwrap=False)
    )
    sim["gravityWS"] = coerce_float(
        _get(node, "gravity_ws", STANDARD_GRAVITY), STANDARD_GRAVITY, unwrap=False
    )
    sim["externalForceWS"] = _vec3(_get(node, "external_force_ws", (0.0, 0.0, 0.0)))
    cos_x = max(-1.0, min(1.0, math.cos(math.radians(angle_x * 0.5))))
    cos_y = max(-1.0, min(1.0, math.cos(math.radians(angle_y * 0.5))))
    sim["cosOfHalfXAngle"] = cos_x
    sim["cosOfHalfYAngle"] = cos_y
    sim["sinOfHalfXAngle"] = math.sqrt(abs(1.0 - cos_x * cos_x))
    sim["sinOfHalfYAngle"] = math.sqrt(abs(1.0 - cos_y * cos_y))
    sim["invertedMass"] = 1.0 / mass


def _patch_pendulum(sim: MutableMapping[str, Any], node: Any) -> None:
    p = _single_particle(node, "PENDULUM")
    sim["dangleBone"] = transform_index(_get(p, "bone_name", ""))
    mass = max(0.01, coerce_float(_get(p, "mass", 1.0), 1.0, unwrap=False))
    sim["mass"] = mass
    sim["damping"] = coerce_float(_get(p, "damping", 1.0), 1.0, unwrap=False)
    sim["pullForceFactor"] = coerce_float(_get(p, "pull_force", 0.0), unwrap=False)
    sim["simulationFps"] = max(
        10.0, coerce_float(_get(p, "pendulum_simulation_fps", 10.0), 10.0, unwrap=False)
    )
    sim["constraintType"] = PENDULUM_TO_RED.get(
        str(_get(p, "pendulum_constraint_type", "CONE")), "Cone"
    )
    aperture = max(
        0.0,
        min(
            180.0,
            coerce_float(
                _get(p, "pendulum_half_aperture_angle", 45.0), 45.0, unwrap=False
            ),
        ),
    )
    sim["halfOfMaxApertureAngle"] = aperture
    orientation = tuple(
        _get(p, "pendulum_constraint_orientation", (90.0, 0.0, 0.0)) or ()
    )
    orientation = tuple(
        max(
            0.0,
            coerce_float(
                orientation[index] if index < len(orientation) else 0.0, unwrap=False
            ),
        )
        for index in range(3)
    )
    sim["constraintOrientation"] = _vec3(orientation)
    sim["pullForceDirectionLS"] = _vec3(
        _get(p, "pendulum_pull_force_direction_ls", (0.0, 0.0, 0.0))
    )
    sim["projectionType"] = PENDULUM_PROJECTION_TO_RED.get(
        str(_get(p, "pendulum_projection_type", "SHORTEST_PATH_ROTATIONAL")),
        "ShortestPathRotational",
    )
    sim["collisionCapsuleRadius"] = max(
        0.0, coerce_float(_get(p, "pendulum_collision_radius", 0.0), unwrap=False)
    )
    sim["collisionCapsuleHeightExtent"] = max(
        0.0, coerce_float(_get(p, "pendulum_collision_height", 0.0), unwrap=False)
    )
    sim["gravityWS"] = coerce_float(
        _get(node, "gravity_ws", STANDARD_GRAVITY), STANDARD_GRAVITY, unwrap=False
    )
    sim["externalForceWS"] = _vec3(_get(node, "external_force_ws", (0.0, 0.0, 0.0)))
    cosines = [
        max(-1.0, min(1.0, math.cos(math.radians(angle * 0.5))))
        for angle in orientation
    ]
    for axis, cosine in zip("XYZ", cosines):
        sim[f"cosOfHalf{axis}Angle"] = cosine
        sim[f"sinOfHalf{axis}Angle"] = math.sqrt(abs(1.0 - cosine * cosine))
    sim["cosOfHalfMaxApertureAngle"] = math.cos(math.radians(aperture))
    half_half_cos = math.cos(math.radians(aperture * 0.5))
    sim["cosOfHalfOfHalfMaxApertureAngle"] = half_half_cos
    sim["sinOfHalfOfHalfMaxApertureAngle"] = math.sqrt(
        abs(1.0 - half_half_cos * half_half_cos)
    )
    sim["invertedMass"] = 1.0 / mass


def _remove_runtime_handles(root: Any, handles: Iterable[str]) -> None:
    targets = {normalized_source_handle(handle) for handle in handles if str(handle)}
    if not targets:
        return
    index, wrappers, _maximum = _build_handle_index(root)
    replacements = {}
    for handle in targets:
        node = index.get(handle)
        if not node or node.get("$type") not in {
            "animAnimNode_Dangle",
            "animAnimNode_Drag",
        }:
            raise AnimGraphPatchError(f"Cannot splice non-Dangle/Drag handle {handle}")
        link = node.get("inputLink")
        if not isinstance(link, dict) or link.get("$type") != "animPoseLink":
            raise AnimGraphPatchError(f"HandleId {handle} has no pose input to splice")
        replacements[handle] = link.get("node")

    def bypass(reference):
        visited = set()
        while isinstance(reference, dict):
            handle = str(reference.get("HandleId", reference.get("HandleRefId", "")))
            if handle not in targets:
                return reference
            if handle in visited:
                raise AnimGraphPatchError("Cannot delete a cyclic pose chain")
            visited.add(handle)
            reference = replacements[handle]
        return reference

    edits = []
    for value in nested_values(root):
        if not isinstance(value, dict):
            continue
        for key, item in value.items():
            if isinstance(item, dict):
                handle = str(item.get("HandleId", item.get("HandleRefId", "")))
                if handle in targets:
                    if value.get("$type") != "animPoseLink" or key != "node":
                        raise AnimGraphPatchError(
                            f"HandleId {handle} has a non-pose incoming reference"
                        )
                    edits.append((value, key, bypass(item)))
            elif isinstance(item, list):
                matching = [
                    i
                    for i, child in enumerate(item)
                    if isinstance(child, dict)
                    and str(child.get("HandleId", child.get("HandleRefId", "")))
                    in targets
                ]
                if matching:
                    owner_type = value.get("$type", "")
                    is_membership = (
                        key == "nodesToInit"
                        and owner_type == "animAnimGraph"
                        or key == "nodes"
                        and "animAnimNode_Container"
                        in registry.parent_chain(owner_type)
                    )
                    if not is_membership:
                        raise AnimGraphPatchError(f"Cannot remove indexed {key} slots")
                    edits.append(
                        (
                            value,
                            key,
                            [
                                child
                                for i, child in enumerate(item)
                                if i not in matching
                            ],
                        )
                    )
    for owner, key, replacement in edits:
        owner[key] = replacement
    normalized = normalize_inline_first_references(root, list(wrappers.values()))[
        "root"
    ]
    if normalized is not root:
        root.clear()
        root.update(normalized)


def _rebuild_initialization(payload):
    root = payload["Data"]["RootChunk"]
    old_nodes = root.get("nodesToInit") or []
    if not old_nodes:
        return  # a graph without nodesToInit keeps none
    index, wrappers, _maximum = _build_handle_index(payload)
    handles = initialization_handles(root.get("rootNode"), index)
    # Keep definitions in their ownership tree; the initialization list contains references.
    definitions = {
        str(item["HandleId"]): item
        for item in old_nodes
        if isinstance(item, dict) and "HandleId" in item
    }
    root["nodesToInit"] = [
        definitions.get(handle, {"HandleRefId": handle}) for handle in handles
    ]
    normalized = normalize_inline_first_references(payload, list(wrappers.values()))[
        "root"
    ]
    if normalized is not payload:
        payload.clear()
        payload.update(normalized)


def _solver_for_node(node: Any) -> str:
    chains = _state_list(_get(node, "chains", ()))
    return str(_get(chains[0], "solver", "DYNG")) if chains else "DYNG"


def _mapped_source_handles(
    state: Any, node_type: str, runtime_type: str, data_by_handle: Mapping[str, dict]
) -> dict[int, str]:
    collection_name = "dangle_nodes" if node_type == "DANGLE" else "drag_nodes"
    nodes = _state_list(_get(state, collection_name, ()))
    mapped = {}
    for index, node in enumerate(nodes):
        handle = normalized_source_handle(_get(node, "source_handle", ""))
        if not handle or handle in {"editor", "fallback", "editor-fallback"}:
            continue
        if (
            handle in data_by_handle
            and data_by_handle.get(handle, {}).get("$type") == runtime_type
        ):
            mapped[index] = handle
    return mapped


def _patch_dangle_nodes(
    state: Any, data_by_handle: MutableMapping[str, dict], next_handle: list[int]
) -> int:
    nodes = _state_list(_get(state, "dangle_nodes", ()))
    mapped = _mapped_source_handles(
        state, "DANGLE", "animAnimNode_Dangle", data_by_handle
    )
    patched = 0
    for index, node in enumerate(nodes):
        if _get(node, "source_identity_version", 0) != 1:
            raise AnimGraphPatchError(
                "Dangle source identities are missing; reimport the AnimGraph before editing or exporting"
            )
        handle = mapped.get(index, "")
        if (
            handle not in data_by_handle
            or data_by_handle.get(handle, {}).get("$type") != "animAnimNode_Dangle"
        ):
            raise AnimGraphPatchError(
                "Cannot export a new or unmapped Dangle without a pose-chain connection"
            )
        runtime_node = data_by_handle[handle]
        sim = resolve_handle(runtime_node.get("dangleConstraint"), data_by_handle)
        if not isinstance(sim, dict):
            raise AnimGraphPatchError(
                f"Dangle HandleId {handle} has no resolvable dangleConstraint"
            )

        solver = _solver_for_node(node)
        expected_type = SOLVER_TO_RED_TYPE.get(solver)
        source_type = str(sim.get("$type", ""))
        if not expected_type or source_type != expected_type:
            raise AnimGraphPatchError(
                f"Dangle HandleId {handle} changed solver from {source_type or '<unknown>'} "
                f"to {expected_type or solver}; change the runtime node type in Graph View first"
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


def _patch_drag_nodes(
    state: Any,
    data_by_handle: MutableMapping[str, dict],
) -> int:
    nodes = _state_list(_get(state, "drag_nodes", ()))
    mapped = _mapped_source_handles(state, "DRAG", "animAnimNode_Drag", data_by_handle)
    patched = 0
    for index, node in enumerate(nodes):
        handle = mapped.get(index, "")
        if (
            handle not in data_by_handle
            or data_by_handle.get(handle, {}).get("$type") != "animAnimNode_Drag"
        ):
            raise AnimGraphPatchError(
                "Cannot export a new or unmapped Drag without a pose-chain connection"
            )
        raw = data_by_handle[handle]
        raw["sourceBone"] = transform_index(
            _get(node, "source_bone_name", "") or _get(node, "bone_name", "")
        )
        raw["outTargetBone"] = transform_index(_get(node, "bone_name", ""))
        raw["simulationFps"] = coerce_float(
            _get(node, "simulation_fps", 100.0), 100.0, unwrap=False
        )
        raw["sourceSpeedMultiplier"] = coerce_float(
            _get(node, "source_speed_multiplier", 10.0), 10.0, unwrap=False
        )
        raw["hasOvershoot"] = int(bool(_get(node, "has_overshoot", True)))
        raw["overshootDetectionMinSpeed"] = coerce_float(
            _get(node, "overshoot_detection_min_speed", 0.4), 0.4, unwrap=False
        )
        raw["overshootDetectionMaxSpeed"] = coerce_float(
            _get(node, "overshoot_detection_max_speed", 4.0), 4.0, unwrap=False
        )
        raw["overshootDuration"] = coerce_float(
            _get(node, "overshoot_duration", 1.0), 1.0, unwrap=False
        )
        raw["useSteps"] = int(bool(_get(node, "use_steps", False)))
        raw["stepsTargetSpeedMultiplier"] = coerce_float(
            _get(node, "steps_target_speed_multiplier", 10000.0), 10000.0, unwrap=False
        )
        raw["timeBetweenSteps"] = coerce_float(
            _get(node, "time_between_steps", 0.1), 0.1, unwrap=False
        )
        raw["timeInStep"] = coerce_float(
            _get(node, "time_in_step", 0.1), 0.1, unwrap=False
        )
        patched += 1
    return patched


def patch_wolvenkit_payload(
    payload: dict,
    state: Any,
    *,
    export_path: str = "",
    update_header: bool = True,
    removed_handles: Iterable[str] = (),
) -> dict:
    root = ((payload or {}).get("Data") or {}).get("RootChunk") or {}
    if not isinstance(root, dict) or root.get("$type") != "animAnimGraph":
        raise AnimGraphPatchError("Expected Data.RootChunk.$type == animAnimGraph")
    original_payload = payload
    payload = loads(dumps(payload, indent=None))
    _remove_runtime_handles(payload, removed_handles)
    data_by_handle, _wrappers, maximum_handle = _build_handle_index(payload)
    next_handle = [maximum_handle + 1]
    _patch_dangle_nodes(state, data_by_handle, next_handle)
    _patch_drag_nodes(state, data_by_handle)
    _rebuild_initialization(payload)
    validation = validate_payload(payload)
    if validation["errors"]:
        raise AnimGraphPatchError("; ".join(validation["errors"]))

    header = payload.setdefault("Header", {})
    if not isinstance(header, dict):
        header = {}
        payload["Header"] = header
    header.setdefault("WolvenKitVersion", SUPPORTED_WOLVENKIT_VERSION)
    header.setdefault("WKitJsonVersion", SUPPORTED_WKIT_JSON_VERSION)
    header.setdefault("GameVersion", SUPPORTED_GAME_VERSION)
    header["DataType"] = "CR2W"
    if update_header:
        header["ExportedDateTime"] = utc_timestamp()
        if export_path:
            header["ArchiveFileName"] = strip_json_suffix(os.path.basename(export_path))
    payload.setdefault("Data", {}).setdefault("EmbeddedFiles", [])
    original_payload.clear()
    original_payload.update(payload)
    return original_payload


def strip_private_export_metadata(payload: dict) -> dict:
    return payload


def validate_payload(payload: dict) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    root = ((payload or {}).get("Data") or {}).get("RootChunk") or {}
    if not isinstance(root, dict) or root.get("$type") != "animAnimGraph":
        errors.append("Data.RootChunk is not animAnimGraph")

    handles: dict[str, int] = {}
    refs: list[str] = []
    dangle_count = 0
    drag_count = 0
    for value in nested_values(payload):
        if not isinstance(value, dict):
            continue
        if "HandleId" in value:
            handle = str(value["HandleId"])
            handles[handle] = handles.get(handle, 0) + 1
            if not isinstance(value.get("Data"), dict):
                errors.append(f"HandleId {handle} has no Data object")
        if "HandleRefId" in value:
            refs.append(str(value["HandleRefId"]))
        node_type = value.get("$type")
        if node_type == "animAnimNode_Dangle":
            dangle_count += 1
        elif node_type == "animAnimNode_Drag":
            drag_count += 1
    for handle, count in handles.items():
        if count != 1:
            errors.append(f"HandleId {handle} occurs {count} times")
    for ref in refs:
        if ref not in handles:
            errors.append(f"HandleRefId {ref} does not resolve")

    if not errors:
        try:
            index, _wrappers, _maximum = _build_handle_index(payload)
            state_errors, state_warnings = state_machine_diagnostics(index)
            errors.extend(state_errors)
            warnings.extend(state_warnings)
            expected = initialization_handles(root.get("rootNode"), index)
            actual = tuple(
                str(item.get("HandleId", item.get("HandleRefId", "")))
                for item in root.get("nodesToInit") or []
            )
            # Some game graphs leave nodesToInit empty; a written one has to follow the graph.
            if actual and actual != expected:
                errors.append("nodesToInit does not match the current graph traversal")
            for handle, node in index.items():
                if node.get("$type") in {"animAnimNode_Dangle", "animAnimNode_Drag"}:
                    link = node.get("inputLink")
                    if (
                        not isinstance(link, dict)
                        or link.get("$type") != "animPoseLink"
                    ):
                        errors.append(f"HandleId {handle} has no pose input link")
            for handle, node in index.items():
                if (
                    rtti.is_graph_node_type(str(node.get("$type", "")))
                    and handle not in expected
                ):
                    warnings.append(
                        f"Animation node {handle} is unreachable from initialization roots"
                    )
        except ValueError as error:
            errors.append(str(error))
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
    return dumps(payload, indent=2) + "\n"


def write_json(filepath: str, payload: dict) -> str:
    text = dumps_pretty(strip_private_export_metadata(payload))
    atomic_write_text(filepath, text)
    return text
