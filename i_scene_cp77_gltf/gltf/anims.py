from __future__ import annotations

import numpy as np

from .extras import skin_extras_for_export
from .nodes import node_transforms


def skin_nodes(
    names,
    parent_indices,
    rest_relative,
    rest_global,
    skin_extras,
    builder,
    *,
    authored_transforms=(),
):
    """The skin's joint nodes under an Armature node, and the skin"""
    inverse_bind_accessor = builder.add_float_accessor(
        np.linalg.inv(rest_global),
        "MAT4",
        name="Bind Matrices",
        matrix_column_major=True,
        include_bounds=False,
    )
    child_lists = [[] for _ in names]
    root_indices = []
    for index, parent_index in enumerate(parent_indices):
        if parent_index < 0:
            root_indices.append(index)
        else:
            child_lists[parent_index].append(index)

    nodes = [{"name": "Armature", "children": [index + 1 for index in root_indices]}]
    transforms = (
        list(authored_transforms) if authored_transforms else [None] * len(names)
    )
    missing = [index for index, transform in enumerate(transforms) if transform is None]
    if missing:
        for index, transform in zip(
            missing, node_transforms(rest_relative[missing], matrix_fallback=False)
        ):
            transforms[index] = transform
    for index, name in enumerate(names):
        node = {"name": name}
        node.update(transforms[index])
        if child_lists[index]:
            node["children"] = [child + 1 for child in child_lists[index]]
        nodes.append(node)

    skin = {
        "name": "Armature",
        "inverseBindMatrices": inverse_bind_accessor,
        "joints": [index + 1 for index in range(len(names))],
        "extras": skin_extras_for_export(skin_extras),
    }
    return nodes, skin


def _rotation_values(values):
    """Equivalent quaternion signs that keep small rotations in WolvenKit"""
    values = np.asarray(values, dtype=np.float32)
    mask = (values[:, 3] == 1.0) & np.any(values[:, :3] != 0.0, axis=1)
    if np.any(mask):
        values = values.copy()
        values[mask] *= -1.0
    return values


def animation_channels(payloads, builder):
    """Samplers and channels for joint payloads of joint_index, path, interpolation, times and values"""
    samplers = []
    channels = []
    for payload in payloads:
        path = str(payload["path"])
        input_accessor = builder.add_shared_float_accessor(payload["times"], "SCALAR")
        output_accessor = builder.add_shared_float_accessor(
            _rotation_values(payload["values"])
            if path == "rotation"
            else payload["values"],
            "VEC4" if path == "rotation" else "VEC3",
            include_bounds=False,
        )
        samplers.append(
            {
                "input": input_accessor,
                "output": output_accessor,
                "interpolation": str(payload["interpolation"]),
            }
        )
        channels.append(
            {
                "sampler": len(samplers) - 1,
                "target": {"node": int(payload["joint_index"]) + 1, "path": path},
            }
        )
    return samplers, channels


def anims_document(nodes, skin, animations, builder, generator) -> dict:
    """The glTF document of one skin and its animations"""
    return {
        "asset": {"generator": generator, "version": "2.0"},
        "accessors": builder.accessors,
        "animations": animations,
        "bufferViews": builder.buffer_views,
        "buffers": [{"byteLength": len(builder.binary)}],
        "nodes": nodes,
        "scenes": [{"nodes": [0]}],
        "skins": [skin],
    }
