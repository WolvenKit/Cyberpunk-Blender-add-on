from __future__ import annotations

import numpy as np

from ....assetio.transform_values import parse_wkit_trs
from ....bartmoss.hierarchy import local_matrices_to_model
from ....bartmoss.trs import compose_matrices_wxyz


def rig_model_matrices(local_transforms, parent_indices) -> np.ndarray:
    """Model matrices of a rig's local bone transforms, such as its T-pose boneTransforms or its aPoseLS"""
    rotations, translations, scales = parse_wkit_trs(
        local_transforms, quaternion_order="wxyz"
    )
    return local_matrices_to_model(
        compose_matrices_wxyz(translations, rotations, scales), parent_indices
    )
