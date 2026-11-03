from __future__ import annotations

from mathutils import Matrix

from ...animation.domain.rig.naming import merged_bone_name
from ...bartmoss.qs_transform import QsTransform
from ...blender.armature_bones import resolve_pose_bone, rig_space_contract
from ...blender.pose import matrix_from_qs, qs_from_matrix
from ...redSpace.contracts import RIG_SPACE_CONTRACT_DIRECT
from ...redSpace.transforms import red_local_transform_to_current_bone


def _reference_pose_from_rigs(armature, rigs, names) -> dict[str, QsTransform]:
    requested = {str(name) for name in names}
    result = {}
    for rig in rigs:
        for index, source_name in enumerate(rig.bone_names):
            resolved = merged_bone_name(str(source_name or ""))
            pose_bone = resolve_pose_bone(armature, resolved)
            if pose_bone is None:
                continue
            name = str(pose_bone.name)
            if name not in requested or name in result:
                continue
            result[name] = QsTransform.from_components(
                tuple(float(value) for value in rig.ls_t[index]),
                tuple(float(value) for value in rig.ls_q[index]),
                tuple(float(value) for value in rig.ls_s[index]),
            )
    missing = sorted(requested - result.keys())
    if missing:
        raise KeyError(
            "Rig reference pose is missing additive bone(s): "
            + ", ".join(missing[:8])
            + (" ..." if len(missing) > 8 else "")
        )
    return result


def reference_basis_from_rigs(armature, rigs, names) -> dict[str, QsTransform]:
    """Pose-bone basis transforms that place the named bones in the source rigs' reference pose"""
    references = _reference_pose_from_rigs(armature, rigs, names)
    direct = rig_space_contract(armature) == RIG_SPACE_CONTRACT_DIRECT
    result = {}
    for name, reference in references.items():
        pose_bone = resolve_pose_bone(armature, name)
        if pose_bone is None:
            continue
        bind_ms = pose_bone.bone.matrix_local
        parent = pose_bone.parent
        bind_ls = (
            parent.bone.matrix_local.inverted_safe() @ bind_ms
            if parent is not None
            else bind_ms
        )
        red_matrix = matrix_from_qs(reference)
        reference_ls = (
            red_matrix
            if direct
            else Matrix(red_local_transform_to_current_bone(red_matrix))
        )
        result[name] = qs_from_matrix(bind_ls.inverted_safe() @ reference_ls)
    return result
