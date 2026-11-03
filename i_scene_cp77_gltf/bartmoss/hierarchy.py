from __future__ import annotations

import numpy as np


def children_by_parent(parent_indices):
    parents = np.asarray(parent_indices, dtype=np.int64)
    children = [[] for _ in range(len(parents))]
    for index, parent in enumerate(parents):
        if 0 <= parent < len(parents):
            children[int(parent)].append(index)
    return tuple(tuple(group) for group in children)


def parent_first_order(parent_indices):
    parents = np.asarray(parent_indices, dtype=np.int64)
    children = children_by_parent(parents)
    roots = [index for index, parent in enumerate(parents) if parent < 0]
    order = []
    pending = list(reversed(roots))
    while pending:
        index = pending.pop()
        order.append(index)
        pending.extend(reversed(children[index]))
    if len(order) != len(parents):
        raise ValueError("Bone hierarchy contains a cycle or invalid parent chain")
    return tuple(order)


def local_matrices_to_model(local_matrices, parent_indices, order=None) -> np.ndarray:
    local = np.asarray(local_matrices)
    parents = np.asarray(parent_indices, dtype=np.int64)
    result = np.empty_like(local)
    order = parent_first_order(parents) if order is None else tuple(order)
    for index in order:
        parent = int(parents[index])
        result[..., index, :, :] = (
            local[..., index, :, :]
            if parent < 0
            else np.matmul(result[..., parent, :, :], local[..., index, :, :])
        )
    return result


def model_matrices_to_local(model_matrices, parent_indices, order=None) -> np.ndarray:
    model = np.asarray(model_matrices)
    parents = np.asarray(parent_indices, dtype=np.int64)
    result = np.empty_like(model)
    order = parent_first_order(parents) if order is None else tuple(order)
    for index in order:
        parent = int(parents[index])
        result[..., index, :, :] = (
            model[..., index, :, :]
            if parent < 0
<<<<<<< Updated upstream
            else np.matmul(np.linalg.inv(model[..., parent, :, :]), model[..., index, :, :])
=======
            else np.matmul(
                np.linalg.inv(model[..., parent, :, :]), model[..., index, :, :]
            )
>>>>>>> Stashed changes
        )
    return result


def descendant_indices(parent_indices, root_index: int):
    children = children_by_parent(parent_indices)
    result = []
    pending = list(reversed(children[int(root_index)]))
    while pending:
        index = pending.pop()
        result.append(index)
        pending.extend(reversed(children[index]))
    return tuple(result)


def local_transform_pairs_to_model(local_transforms, parent_indices):
    result = [None] * len(local_transforms)
    for index in parent_first_order(parent_indices):
        translation, rotation = local_transforms[index]
        parent = int(parent_indices[index])
        if parent < 0:
            result[index] = (translation.copy(), rotation.copy())
            continue
        parent_translation, parent_rotation = result[parent]
        result[index] = (
            parent_translation + parent_rotation @ translation,
            parent_rotation @ rotation,
        )
    return result


def model_transform_pairs_to_local(model_transforms, parent_indices):
    result = [None] * len(model_transforms)
    for index in parent_first_order(parent_indices):
        translation, rotation = model_transforms[index]
        parent = int(parent_indices[index])
        if parent < 0:
            result[index] = (translation.copy(), rotation.copy())
            continue
        parent_translation, parent_rotation = model_transforms[parent]
        inverse_parent = parent_rotation.inverted()
        result[index] = (
            inverse_parent @ (translation - parent_translation),
            inverse_parent @ rotation,
        )
    return result
<<<<<<< Updated upstream
=======


def parent_depth(node, cache=None):
    """Return ancestor count"""
    if cache is None:
        depth = 0
        parent = node.parent
        while parent is not None:
            depth += 1
            parent = parent.parent
        return depth
    path = []
    current = node
    while current is not None and current not in cache:
        path.append(current)
        current = current.parent
    depth = -1 if current is None else cache[current]
    for current in reversed(path):
        depth += 1
        cache[current] = depth
    return cache[node]


def bone_basis_corrections(source_rest_relative, parent_indices, target_rest_model):
    """Preserve source deformation when a target rig uses different rest axes or pivots"""
    source_model = local_matrices_to_model(source_rest_relative, parent_indices)
    target_model = np.asarray(target_rest_model, dtype=np.float64)
    source_axes = source_model[:, :3, :3]
    target_axes = target_model[:, :3, :3]
    source_axes = source_axes / np.maximum(
        np.linalg.norm(source_axes, axis=1)[:, None, :], 1e-15
    )
    target_axes = target_axes / np.maximum(
        np.linalg.norm(target_axes, axis=1)[:, None, :], 1e-15
    )
    result = np.tile(np.eye(4), (len(source_axes), 1, 1))
    result[:, :3, :3] = np.swapaxes(source_axes, 1, 2) @ target_axes
    offsets = target_model[:, :3, 3] - source_model[:, :3, 3]
    offsets[np.linalg.norm(offsets, axis=1) <= 1e-5] = 0.0
    result[:, :3, 3] = np.einsum("bji,bj->bi", source_axes, offsets)
    return result


def model_matrices_to_basis(pose_model, rest_model, parent_indices) -> np.ndarray:
    """Pose-channel bases"""
    order = parent_first_order(parent_indices)
    rest_local = model_matrices_to_local(rest_model, parent_indices, order)
    pose_local = model_matrices_to_local(pose_model, parent_indices, order)
    return np.matmul(np.linalg.inv(rest_local), pose_local)
>>>>>>> Stashed changes
