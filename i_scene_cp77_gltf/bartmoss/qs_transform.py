from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from .quaternion import (
    multiply_scalar_xyzw,
    nlerp_xyzw,
    normalized_single_xyzw,
    rotate_vector_unit_scalar_xyzw,
    slerp_xyzw,
)
from .scalar import lerp
from .trs import compose_matrix, decompose_matrices


@dataclass(frozen=True)
class QsTransform:
    translation: tuple[float, float, float]
    rotation_xyzw: tuple[float, float, float, float]
    scale: tuple[float, float, float]

    @classmethod
    def identity(cls) -> QsTransform:
        return cls((0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0), (1.0, 1.0, 1.0))

    @classmethod
    def from_components(
        cls,
        translation: Sequence[float],
        rotation_xyzw: Sequence[float],
        scale: Sequence[float],
    ) -> QsTransform:
        return cls(
            tuple(float(value) for value in translation[:3]),
            normalized_single_xyzw(rotation_xyzw),
            tuple(float(value) for value in scale[:3]),
        )


def matrix_from_qs(value: QsTransform) -> np.ndarray:
    return compose_matrix(value.translation, value.rotation_xyzw, value.scale)


def qs_from_matrix(matrix: np.ndarray) -> QsTransform:
    translation, rotation, scale = decompose_matrices(matrix, mirrored_axis="largest")
    return QsTransform.from_components(translation, rotation, scale)


def compose(parent: QsTransform, local: QsTransform) -> QsTransform:
    psx, psy, psz = parent.scale
    ltx, lty, ltz = local.translation
    rtx, rty, rtz = rotate_vector_unit_scalar_xyzw(
        parent.rotation_xyzw,
        (ltx * psx, lty * psy, ltz * psz),
    )
    ptx, pty, ptz = parent.translation
    rotation = multiply_scalar_xyzw(parent.rotation_xyzw, local.rotation_xyzw)
    lsx, lsy, lsz = local.scale
    return QsTransform(
        (ptx + rtx, pty + rty, ptz + rtz),
        rotation,
        (psx * lsx, psy * lsy, psz * lsz),
    )


def relative_to(parent: QsTransform, model: QsTransform) -> QsTransform:
    psx, psy, psz = parent.scale
    if abs(psx) <= 1e-15 or abs(psy) <= 1e-15 or abs(psz) <= 1e-15:
        return qs_from_matrix(
            np.linalg.inv(matrix_from_qs(parent)) @ matrix_from_qs(model)
        )

    px, py, pz, pw = parent.rotation_xyzw
    inverse_rotation = (-px, -py, -pz, pw)
    mtx, mty, mtz = model.translation
    ptx, pty, ptz = parent.translation
    tx, ty, tz = rotate_vector_unit_scalar_xyzw(
        inverse_rotation,
        (mtx - ptx, mty - pty, mtz - ptz),
    )
    rotation = multiply_scalar_xyzw(inverse_rotation, model.rotation_xyzw)
    msx, msy, msz = model.scale
    return QsTransform(
        (tx / psx, ty / psy, tz / psz),
        rotation,
        (msx / psx, msy / psy, msz / psz),
    )


def lerp_qs(base: QsTransform, target: QsTransform, weight: float) -> QsTransform:
    """Translation and scale lerp with rotation slerp"""
    weight = float(weight)
    if weight == 0.0:
        return base
    if weight == 1.0:
        return target
    return QsTransform.from_components(
        lerp(base.translation, target.translation, weight),
        slerp_xyzw(base.rotation_xyzw, target.rotation_xyzw, weight),
        lerp(base.scale, target.scale, weight),
    )


def blend_qs(base: QsTransform, override: QsTransform, weight: float) -> QsTransform:
    """lerp_qs with non-positive weights keeping base"""
    if float(weight) <= 0.0:
        return base
    return lerp_qs(base, override, weight)


def without_translation(value: QsTransform) -> QsTransform:
    return QsTransform.from_components(
        (0.0, 0.0, 0.0), value.rotation_xyzw, value.scale
    )


def translation_only(value: QsTransform) -> QsTransform:
    return QsTransform.from_components(
        value.translation, (0.0, 0.0, 0.0, 1.0), (1.0, 1.0, 1.0)
    )


def interpolate_qs(
    start: QsTransform, end: QsTransform, weight: float, interpolation: str
) -> QsTransform:
    """Slerp or Lerp between two transforms"""
    weight = float(weight)
    if str(interpolation or "Slerp") != "Lerp":
        return QsTransform.from_components(
            lerp(start.translation, end.translation, weight),
            slerp_xyzw(start.rotation_xyzw, end.rotation_xyzw, weight),
            lerp(start.scale, end.scale, weight),
        )
    return QsTransform.from_components(
        lerp(start.translation, end.translation, weight),
        nlerp_xyzw(
            np.asarray(start.rotation_xyzw, dtype=np.float64),
            np.asarray(end.rotation_xyzw, dtype=np.float64),
            weight,
        ),
        lerp(start.scale, end.scale, weight),
    )
