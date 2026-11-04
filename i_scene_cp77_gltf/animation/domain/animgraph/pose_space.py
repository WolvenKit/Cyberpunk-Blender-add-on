from __future__ import annotations

from collections.abc import Mapping, MutableMapping, Sequence
from dataclasses import dataclass

import numpy as np

from ....bartmoss.qs_transform import QsTransform, compose, relative_to
from ....bartmoss.quaternion import multiply_rows_xyzw, rotate_rows_xyzw


@dataclass(frozen=True)
class PoseHierarchyPlan:
    names: tuple[str, ...]
    parent_indices: tuple[int, ...]
    levels: tuple[tuple[int, ...], ...]
    # (child indices, parent indices) arrays per level below the roots, built once.
    level_arrays: tuple[tuple[np.ndarray, np.ndarray], ...] = ()


def build_hierarchy_plan(
    names: Sequence[str],
    parent_map: Mapping[str, str],
) -> PoseHierarchyPlan:
    ordered = tuple(str(name) for name in names)
    index = {name: position for position, name in enumerate(ordered)}
    parents = tuple(
        index.get(str(parent_map.get(name, "") or ""), -1) for name in ordered
    )
    depths = [-1] * len(ordered)
    visiting: set[int] = set()

    def depth(position: int) -> int:
        cached = depths[position]
        if cached >= 0:
            return cached
        if position in visiting:
            raise ValueError(f"cycle in rig hierarchy at {ordered[position]}")
        visiting.add(position)
        parent = parents[position]
        value = 0 if parent < 0 else depth(parent) + 1
        visiting.discard(position)
        depths[position] = value
        return value

    for position in range(len(ordered)):
        depth(position)
    max_depth = max(depths, default=0)
    levels = tuple(
        tuple(position for position, value in enumerate(depths) if value == level)
        for level in range(max_depth + 1)
    )
    level_arrays = tuple(
        (
            np.asarray(level, dtype=np.intp),
            np.asarray([parents[index] for index in level], dtype=np.intp),
        )
        for level in levels[1:]
        if level
    )
    return PoseHierarchyPlan(ordered, parents, levels, level_arrays)


def _components(pose: Mapping[str, QsTransform], names: tuple[str, ...]):
    translations = np.asarray(
        [pose[name].translation for name in names], dtype=np.float64
    )
    rotations = np.asarray(
        [pose[name].rotation_xyzw for name in names], dtype=np.float64
    )
    scales = np.asarray([pose[name].scale for name in names], dtype=np.float64)
    return translations, rotations, scales


def _rows_to_qs(
    translations: np.ndarray,
    rotations: np.ndarray,
    scales: np.ndarray,
    names: tuple[str, ...],
    roots: set[int] | None = None,
    original: Mapping[str, QsTransform] | None = None,
) -> dict[str, QsTransform]:
    result: dict[str, QsTransform] = {}
    root_set = roots or set()
    t_rows, r_rows, s_rows = translations.tolist(), rotations.tolist(), scales.tolist()
    for index, name in enumerate(names):
        if index in root_set and original is not None:
            result[name] = original[name]
        else:
            result[name] = QsTransform(
                tuple(t_rows[index]), tuple(r_rows[index]), tuple(s_rows[index])
            )
    return result


def pose_ls_to_ms(
    local_pose: Mapping[str, QsTransform],
    parent_map: Mapping[str, str],
    plan: PoseHierarchyPlan | None = None,
) -> dict[str, QsTransform]:
    if plan is None:
        cache: dict[str, QsTransform] = {}
        return {
            name: model_transform(name, local_pose, parent_map, cache)
            for name in local_pose
        }
    if tuple(local_pose) != plan.names:
        plan = build_hierarchy_plan(tuple(local_pose), parent_map)

    local_t, local_r, local_s = _components(local_pose, plan.names)
    model_t = local_t.copy()
    model_r = local_r.copy()
    model_s = local_s.copy()

    level_arrays = plan.level_arrays or tuple(
        (
            np.asarray(level, dtype=np.intp),
            np.asarray([plan.parent_indices[index] for index in level], dtype=np.intp),
        )
        for level in plan.levels[1:]
        if level
    )
    for indices, parent_indices in level_arrays:
        scaled_local = model_s[parent_indices] * local_t[indices]
        model_t[indices] = model_t[parent_indices] + rotate_rows_xyzw(
            model_r[parent_indices], scaled_local
        )
        model_r[indices] = multiply_rows_xyzw(model_r[parent_indices], local_r[indices])
        model_s[indices] = model_s[parent_indices] * local_s[indices]

    roots = set(plan.levels[0] if plan.levels else ())
    return _rows_to_qs(model_t, model_r, model_s, plan.names, roots, local_pose)


def pose_ms_to_ls(
    model_pose: Mapping[str, QsTransform],
    parent_map: Mapping[str, str],
    plan: PoseHierarchyPlan | None = None,
) -> dict[str, QsTransform]:
    if plan is None:
        local_pose: dict[str, QsTransform] = {}
        for name, model in model_pose.items():
            parent = str(parent_map.get(name, "") or "")
            local_pose[name] = (
                relative_to(model_pose[parent], model)
                if parent and parent in model_pose
                else model
            )
        return local_pose
    if tuple(model_pose) != plan.names:
        plan = build_hierarchy_plan(tuple(model_pose), parent_map)

    model_t, model_r, model_s = _components(model_pose, plan.names)
    parent_indices = np.asarray(plan.parent_indices, dtype=np.intp)
    children = np.flatnonzero(parent_indices >= 0)
    local_t = model_t.copy()
    local_r = model_r.copy()
    local_s = model_s.copy()
    if len(children):
        parents = parent_indices[children]
        parent_scale = model_s[parents]
        safe = np.all(np.abs(parent_scale) > 1e-15, axis=1)
        if np.any(safe):
            safe_children = children[safe]
            safe_parents = parents[safe]
            inverse_rotation = model_r[safe_parents].copy()
            inverse_rotation[:, :3] *= -1.0
            delta = model_t[safe_children] - model_t[safe_parents]
            local_t[safe_children] = (
                rotate_rows_xyzw(inverse_rotation, delta) / model_s[safe_parents]
            )
            local_r[safe_children] = multiply_rows_xyzw(
                inverse_rotation, model_r[safe_children]
            )
            local_s[safe_children] = model_s[safe_children] / model_s[safe_parents]
        if np.any(~safe):
            for child, parent in zip(children[~safe], parents[~safe]):
                relative = relative_to(
                    model_pose[plan.names[int(parent)]],
                    model_pose[plan.names[int(child)]],
                )
                local_t[child] = relative.translation
                local_r[child] = relative.rotation_xyzw
                local_s[child] = relative.scale

    roots = set(np.flatnonzero(parent_indices < 0).tolist())
    return _rows_to_qs(local_t, local_r, local_s, plan.names, roots, model_pose)


def model_transform(
    name: str,
    local_pose: Mapping[str, QsTransform],
    parent_map: Mapping[str, str],
    cache: MutableMapping[str, QsTransform] | None = None,
    stack: set[str] | None = None,
) -> QsTransform:
    cache = cache if cache is not None else {}
    if name in cache:
        return cache[name]
    if name not in local_pose:
        raise KeyError(name)
    visiting = stack if stack is not None else set()
    chain = []
    current = name
    while current and current not in cache:
        if current not in local_pose:
            raise KeyError(current)
        if current in visiting:
            raise ValueError(f"cycle in rig hierarchy at {current}")
        visiting.add(current)
        chain.append(current)
        current = str(parent_map.get(current, "") or "")

    result = cache.get(current) if current else None
    try:
        for bone_name in reversed(chain):
            local = local_pose[bone_name]
            result = compose(result, local) if result is not None else local
            cache[bone_name] = result
        return cache[name]
    finally:
        for bone_name in chain:
            visiting.discard(bone_name)


def frame_model_transform(
    name: str,
    pose: Mapping[str, QsTransform],
    parent_map: Mapping[str, str],
    model_space: bool,
    cache: MutableMapping[str, QsTransform] | None = None,
) -> QsTransform:
    """name's model-space transform in a pose held in model space (model_space) or in local space"""
    return pose[name] if model_space else model_transform(name, pose, parent_map, cache)


def write_model_transform(
    local_pose, parent_map, target: str, output_ms: QsTransform, model_space: bool
) -> None:
    """Store a model-space result in the pose's own space (relative to the rig parent in local space)"""
    parent = "" if model_space else str(parent_map.get(target, "") or "")
    if parent and parent in local_pose:
        local_pose[target] = relative_to(
            model_transform(parent, local_pose, parent_map, {}), output_ms
        )
    else:
        local_pose[target] = output_ms
