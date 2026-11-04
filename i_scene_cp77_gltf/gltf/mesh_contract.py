from __future__ import annotations

import numpy as np

WOLVENKIT_SKIN_SETS = 2
WOLVENKIT_UV_SETS = 2
# Four joints per skin set.
MAX_SKIN_INFLUENCES = WOLVENKIT_SKIN_SETS * 4
# Weights at or below this carry no influence.
SKIN_WEIGHT_EPSILON = 1.0e-8


def validate_primitive_accessors(accessors, primitive):
    """Validate attribute layouts before numeric conversion can hide malformed data"""
    mode = primitive.get("mode", 4)
    if isinstance(mode, bool) or not isinstance(mode, int) or mode != 4:
        raise ValueError("Direct CP77 meshes require integer triangle-list mode 4.")
    attributes = primitive.get("attributes") or {}
    position_index = attributes.get("POSITION")
    if (
        isinstance(position_index, bool)
        or not isinstance(position_index, int)
        or not 0 <= position_index < len(accessors)
    ):
        raise ValueError("Mesh primitive requires a valid POSITION accessor.")
    count = accessors[position_index].get("count")
    for name, index in attributes.items():
        if (
            isinstance(index, bool)
            or not isinstance(index, int)
            or not 0 <= index < len(accessors)
        ):
            raise ValueError(f"{name} references an invalid accessor.")
        accessor = accessors[index]
        if accessor.get("count") != count:
            raise ValueError(f"{name} vertex count disagrees with POSITION.")
        shape, component = accessor.get("type"), accessor.get("componentType")
        if name in {"POSITION", "NORMAL", "TANGENT"}:
            expected = "VEC4" if name == "TANGENT" else "VEC3"
            if (
                shape != expected
                or component != 5126
                or accessor.get("normalized", False)
            ):
                raise ValueError(
                    f"{name} must use an unnormalized FLOAT {expected} accessor."
                )
        elif name.startswith(("JOINTS_", "WEIGHTS_", "COLOR_", "TEXCOORD_")):
            semantic, channel = name.rsplit("_", 1)
            if not channel.isdigit():
                raise ValueError(f"Invalid attribute semantic {name!r}.")
            if semantic in {"JOINTS", "WEIGHTS"}:
                if shape != "VEC4":
                    raise ValueError(f"{name} must use a VEC4 accessor.")
                allowed = (5121, 5123) if semantic == "JOINTS" else (5121, 5123, 5126)
                if component not in allowed or bool(
                    accessor.get("normalized", False)
                ) != (semantic == "WEIGHTS" and component != 5126):
                    raise ValueError(
                        f"{name} has an invalid component type or normalization."
                    )
                if int(channel) >= WOLVENKIT_SKIN_SETS:
                    raise ValueError(
                        "WolvenKit supports at most eight skin influences per vertex."
                    )
            else:
                if shape not in (
                    ("VEC2",) if semantic == "TEXCOORD" else ("VEC3", "VEC4")
                ):
                    raise ValueError(f"{name} has an invalid vector shape.")
                if component not in (5121, 5123, 5126) or bool(
                    accessor.get("normalized", False)
                ) != (component != 5126):
                    raise ValueError(
                        f"{name} has an invalid component type or normalization."
                    )
    index = primitive.get("indices")
    if index is not None:
        if (
            isinstance(index, bool)
            or not isinstance(index, int)
            or not 0 <= index < len(accessors)
        ):
            raise ValueError("Triangle indices reference an invalid accessor.")
        accessor = accessors[index]
        if (
            accessor.get("type") != "SCALAR"
            or accessor.get("componentType") not in (5121, 5123, 5125)
            or accessor.get("normalized", False)
        ):
            raise ValueError(
                "Triangle indices require unnormalized unsigned SCALAR values."
            )


def validate_direct_extensions(document):
    required = document.get("extensionsRequired") or ()
    if required:
        raise ValueError(
            "The direct WolvenKit reader does not support required glTF extensions: "
            + ", ".join(map(str, required))
        )


def validate_mesh_arrays(attributes, indices, *, joint_count=0, allow_unweighted=False):
    position = attributes.get("POSITION")
    if (
        position is None
        or position.ndim != 2
        or position.shape[1] != 3
        or not len(position)
    ):
        raise ValueError("POSITION must contain a non-empty VEC3 array.")
    count = len(position)
    for name, values in attributes.items():
        width = (
            3
            if name in {"POSITION", "NORMAL"}
            else 2
            if name.startswith("TEXCOORD_")
            else 4
            if name == "TANGENT" or name.startswith(("JOINTS_", "WEIGHTS_"))
            else None
        )
        if (
            values.ndim != 2
            or len(values) != count
            or (width and values.shape[1] != width)
        ):
            raise ValueError(
                f"{name} has an invalid shape {values.shape} for {count} vertices."
            )
        if not np.all(np.isfinite(values)):
            raise ValueError(f"{name} contains non-finite values.")
        if name.startswith("COLOR_"):
            if values.shape[1] not in (3, 4) or np.any((values < 0) | (values > 1)):
                raise ValueError(f"{name} requires RGB/RGBA values between 0 and 1.")
        if name.startswith("JOINTS_"):
            if (
                values.dtype.kind not in "ui"
                or np.any(values < 0)
                or np.any(values >= joint_count)
            ):
                raise ValueError(f"{name} references an invalid skin joint.")
        if name.startswith("WEIGHTS_") and np.any(values < 0):
            raise ValueError(f"{name} contains negative weights.")
        if name in {"NORMAL", "TANGENT"}:
            if np.any(np.einsum("ij,ij->i", values[:, :3], values[:, :3]) <= 1e-12):
                raise ValueError(f"{name} contains zero-length vectors.")
            if name == "TANGENT" and not np.all(
                np.isclose(np.abs(values[:, 3]), 1.0, rtol=0, atol=1e-5)
            ):
                raise ValueError("TANGENT handedness must be -1 or 1.")
    if indices.dtype.kind not in "ui" or indices.size % 3:
        raise ValueError("Triangle indices require integral triples.")
    if np.any(indices < 0) or np.any(indices >= count):
        raise ValueError("Triangle index is outside the POSITION array.")
    weights = [
        values for name, values in attributes.items() if name.startswith("WEIGHTS_")
    ]
    if weights:
        totals = sum(values.sum(axis=1, dtype=np.float64) for values in weights)
        normalized = np.isclose(totals, 1.0, rtol=0, atol=1e-5)
        if allow_unweighted:
            normalized |= np.isclose(totals, 0.0, rtol=0, atol=1e-5)
        if not np.all(normalized):
            raise ValueError(
                "Every skinned vertex must have normalized, non-zero weights."
            )


def validate_wolvenkit_channels(attributes):
    for required in ("POSITION", "NORMAL", "TANGENT"):
        if required not in attributes:
            raise ValueError(
                f"WolvenKit mesh export requires {required}; check mesh normals and UV0 tangents."
            )
    for name in attributes:
        if (
            name.startswith(("JOINTS_", "WEIGHTS_"))
            and int(name.rsplit("_", 1)[1]) >= WOLVENKIT_SKIN_SETS
        ):
            raise ValueError(
                "WolvenKit mesh export supports at most 8 influences per vertex; reduce weights explicitly."
            )
        if (
            name.startswith("TEXCOORD_")
            and int(name.rsplit("_", 1)[1]) >= WOLVENKIT_UV_SETS
        ):
            raise ValueError(
                "WolvenKit mesh export supports TEXCOORD_0 and TEXCOORD_1; remove or reassign extra UV channels."
            )


JOINT_ATTRIBUTES = tuple(f"JOINTS_{index}" for index in range(4))
WEIGHT_ATTRIBUTES = tuple(f"WEIGHTS_{index}" for index in range(4))
UV_ATTRIBUTES = ("TEXCOORD_0", "TEXCOORD_1", "TEXCOORD_2", "TEXCOORD_3")
COLOR_ATTRIBUTES = ("COLOR_0", "COLOR_1")
