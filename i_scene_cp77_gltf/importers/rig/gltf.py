from __future__ import annotations

import os

import numpy as np

from ...animation.model.clip.metadata import SOURCE_REST_SNAPSHOT_KEY
from ...bartmoss.quaternion import wxyz_from_xyzw
from ...bartmoss.trs import decompose_matrices
from ...blender.action_metadata import apply_skin_extras, store_json_snapshot
from ...gltf.container import read_gltf_container
from ...gltf.mesh_contract import validate_direct_extensions
from ...gltf.provenance import ORIGIN_PLUGIN, mark_origin
from ...gltf.skeleton import (
    SamplingContext,
    SkeletonBinding,
    build_node_hierarchy,
    build_sampling_context,
    build_skeleton_binding,
)
from ...redSpace.contracts import SOURCE_REST_SPACE_CONTRACT
from ...redSpace.transforms import gltf_matrix_to_red, gltf_rest_relative_to_blender


def import_gltf_rig(filepath):
    """Reconstruct a skin-only glTF using the same rig contract as animation import"""
    gltf = read_gltf_container(filepath)
    validate_direct_extensions(gltf.document)
    if len(gltf.document.get("skins") or ()) != 1:
        raise ValueError(
            "Direct CP77 animation and rig import requires exactly one skin."
        )
    hierarchy = build_node_hierarchy(gltf.document)
    binding = build_skeleton_binding(gltf.document, hierarchy)
    context = build_sampling_context(hierarchy, binding)
    armature = build_rest_armature_from_binding(binding, context, source_label=filepath)
    extras = dict(binding.skin_extras)
    extras.update(
        boneNames=list(binding.bone_names),
        boneParentIndexes=list(binding.source_parent_indices),
    )
    extras.setdefault("trackNames", [])
    apply_skin_extras(armature, extras)
    source_rest = gltf_rest_relative_to_blender(
        context.default_local_matrices,
        context.joint_default_prefixes,
        binding.joint_nodes,
        binding.source_parent_indices,
    )
    store_json_snapshot(
        armature,
        SOURCE_REST_SNAPSHOT_KEY,
        {
            "version": 1,
            "space": SOURCE_REST_SPACE_CONTRACT,
            "boneNames": list(binding.bone_names),
            "matrices": source_rest.reshape(len(binding.bone_names), 16).tolist(),
        },
    )
    mark_origin(armature, ORIGIN_PLUGIN, source_path=filepath)
    return {"armature": armature, "all_objects": [armature], "rig_only": True}


def _rest_local_trs_red(binding: SkeletonBinding, context: SamplingContext):
    """Per-joint parent-relative rest as REDengine-space TRS dictionaries"""
    relative_gltf = np.stack(
        [
            context.joint_default_prefixes[joint_index]
            @ context.default_local_matrices[node_index]
            for joint_index, node_index in enumerate(binding.joint_nodes)
        ]
    )
    red_local = gltf_matrix_to_red(relative_gltf)
    translations, rotations_xyzw, scales = decompose_matrices(red_local)
    transforms = [
        {
            "Translation": {
                "X": float(translations[index, 0]),
                "Y": float(translations[index, 1]),
                "Z": float(translations[index, 2]),
            },
            "Rotation": {
                "i": float(rotations_xyzw[index, 0]),
                "j": float(rotations_xyzw[index, 1]),
                "k": float(rotations_xyzw[index, 2]),
                "r": float(rotations_xyzw[index, 3]),
            },
            "Scale": {
                "X": float(scales[index, 0]),
                "Y": float(scales[index, 1]),
                "Z": float(scales[index, 2]),
            },
        }
        for index in range(len(binding.bone_names))
    ]
    return transforms, translations, rotations_xyzw, scales


def build_rest_armature_from_binding(
    binding: SkeletonBinding,
    context: SamplingContext,
    *,
    source_label: str = "",
    name: str | None = None,
    assign_shapes: bool = True,
    model_space_matrices=None,
    collection=None,
):
    """Construct a rig-import-compatible armature from an anims GLB rest pose"""
    # Armature construction stays owned by the importer rig domain.
    from ...animation.model.rig.data import RigData
    from .reader import create_armature_from_rig_data

    skin_extras = binding.skin_extras or {}
    bone_transforms, translations, rotations_xyzw, scales = _rest_local_trs_red(
        binding, context
    )
    rig_path = str(skin_extras.get("rigPath", "") or "")
    rig_name = name or (
        os.path.splitext(os.path.basename(rig_path.replace("\\", "/")))[0]
        if rig_path
        else "Armature__rest"
    )

    rig_data = RigData(
        num_bones=len(binding.bone_names),
        parent_indices=np.asarray(binding.source_parent_indices, dtype=np.int16),
        bone_names=list(binding.bone_names),
        track_names=[str(value) for value in (skin_extras.get("trackNames") or ())],
        ls_q=np.ascontiguousarray(wxyz_from_xyzw(rotations_xyzw), dtype=np.float32),
        ls_t=np.ascontiguousarray(translations, dtype=np.float32),
        ls_s=np.ascontiguousarray(scales, dtype=np.float32),
        rig_name=rig_name,
        disable_connect=True,
        apose_ms=[],
        apose_ls=[],
        bone_transforms=bone_transforms,
        parts=[],
        rig_extra_tracks=[],
        reference_tracks=[],
        cooking_platform="",
        distance_category_to_lod_map=[],
        ik_setups=[],
        level_of_detail_start_indices=[],
        ragdoll_desc=[],
        ragdoll_names=[],
    )
    return create_armature_from_rig_data(
        rig_data,
        "cp77_t_pose",
        source_rig_file=source_label or rig_path,
        source_document=None,
        assign_shapes=assign_shapes,
        model_space_matrices=model_space_matrices,
        collection=collection,
    )
