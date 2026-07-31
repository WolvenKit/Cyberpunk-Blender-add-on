from __future__ import annotations

import numpy as np


def parse_wkit_trs(
    records,
    count: int | None = None,
    *,
    quaternion_order: str = "xyzw",
    normalize_rotations: bool = True,
):
    records = records or ()
    size = len(records) if count is None else int(count)
    quaternions = np.zeros((size, 4), dtype=np.float32)
    translations = np.zeros((size, 3), dtype=np.float32)
    scales = np.ones((size, 3), dtype=np.float32)
    if quaternion_order == "xyzw":
        identity_index = 3
        component_keys = ("i", "j", "k", "r")
    elif quaternion_order == "wxyz":
        identity_index = 0
        component_keys = ("r", "i", "j", "k")
    else:
        raise ValueError(f"Unsupported quaternion order: {quaternion_order}")
    quaternions[:, identity_index] = 1.0
    for index, transform in enumerate(records[:size]):
        if not transform:
            continue
        rotation = transform.get("Rotation", {})
        quaternions[index] = tuple(
            float(rotation.get(key, 1.0 if key == "r" else 0.0))
            for key in component_keys
        )
        translation = transform.get("Translation", {})
        translations[index] = (
            float(translation.get("X", 0.0)),
            float(translation.get("Y", 0.0)),
            float(translation.get("Z", 0.0)),
        )
        scale = transform.get("Scale", {})
        scales[index] = (
            float(scale.get("X", 1.0)),
            float(scale.get("Y", 1.0)),
            float(scale.get("Z", 1.0)),
        )
    if normalize_rotations:
        norms = np.linalg.norm(quaternions, axis=1, keepdims=True)
        np.divide(quaternions, np.where(norms > 0.0, norms, 1.0), out=quaternions)
    return quaternions, translations, scales


def parse_qs_transform(
    transform,
    *,
    quaternion_order: str = "xyzw",
    normalize_rotation: bool = True,
):
    rotations, translations, scales = parse_wkit_trs(
        (transform,),
        quaternion_order=quaternion_order,
        normalize_rotations=normalize_rotation,
    )
    return rotations[0], translations[0], scales[0]


def quaternion_wxyz_from_wkit(value, default=(1.0, 0.0, 0.0, 0.0)):
    if not isinstance(value, dict):
        return tuple(float(component) for component in default)
    return (
        float(value.get("r", default[0])),
        float(value.get("i", default[1])),
        float(value.get("j", default[2])),
        float(value.get("k", default[3])),
    )


def quaternion_wxyz_from_ijkr(value, default=(1.0, 0.0, 0.0, 0.0)):
    if isinstance(value, dict):
        return quaternion_wxyz_from_wkit(value, default)
    if isinstance(value, (list, tuple)) and len(value) >= 4:
        return (float(value[3]), float(value[0]), float(value[1]), float(value[2]))
    return tuple(float(component) for component in default)


def quaternion_ijkr_from_wxyz(value):
    return (float(value[1]), float(value[2]), float(value[3]), float(value[0]))


def encode_wkit_quaternion(value, *, quaternion_order: str = "xyzw"):
    values = np.asarray(value)
    if quaternion_order == "xyzw":
        i, j, k, r = (float(component) for component in values)
    elif quaternion_order == "wxyz":
        r, i, j, k = (float(component) for component in values)
    else:
        raise ValueError(f"Unsupported quaternion order: {quaternion_order}")
    return {"$type": "Quaternion", "i": i, "j": j, "k": k, "r": r}

def encode_qs_transform(
    rotation,
    translation,
    scale,
    *,
    translation_w: float,
    scale_w: float,
    quaternion_order: str = "xyzw",
):
    rotation = np.asarray(rotation)
    translation = np.asarray(translation)
    scale = np.asarray(scale)
    return {
        "$type": "QsTransform",
        "Rotation": encode_wkit_quaternion(rotation, quaternion_order=quaternion_order),
        "Scale": {
            "$type": "Vector4",
            "W": float(scale_w),
            "X": float(scale[0]),
            "Y": float(scale[1]),
            "Z": float(scale[2]),
        },
        "Translation": {
            "$type": "Vector4",
            "W": float(translation_w),
            "X": float(translation[0]),
            "Y": float(translation[1]),
            "Z": float(translation[2]),
        },
    }


def encode_qs_transforms(
    rotations,
    translations,
    scales,
    *,
    translation_w: float,
    scale_w: float,
    quaternion_order: str = "xyzw",
):
    return [
        encode_qs_transform(
            rotation,
            translation,
            scale,
            translation_w=translation_w,
            scale_w=scale_w,
            quaternion_order=quaternion_order,
        )
        for rotation, translation, scale in zip(rotations, translations, scales)
    ]
