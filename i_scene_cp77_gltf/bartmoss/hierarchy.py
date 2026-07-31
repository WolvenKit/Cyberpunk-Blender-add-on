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
            else np.matmul(np.linalg.inv(model[..., parent, :, :]), model[..., index, :, :])
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
