from __future__ import annotations

import copy
import os
import tempfile
from functools import lru_cache

import numpy as np

from ...animation.domain.clip.source_rest import source_rest_relative
from ...animation.domain.mocap.body import target_body
from ...animation.domain.mocap.calibration import without_calibration_frame
from ...animation.domain.mocap.retarget import TARGET_BONES, retarget
from ...animation.domain.mocap.skeleton_map import map_skeleton
from ...animation.domain.rig.metadata import (
    RIG_EXPORT_TEMPLATE_KEY,
    decode_rig_export_template,
)
from ...animation.domain.rig.model_space import rig_model_matrices
from ...animation.model.clip.metadata import (
    ACTION_DEFAULTS,
    FPS,
    SOURCE_REST_SNAPSHOT_KEY,
)
from ...animation.model.mocap.clip import MocapTargetError, TargetRig
from ...animation.services.rig.export_source import load_animation_rig_export_source
from ...assetio.bvh import read_bvh
from ...assetio.mesh_npz import read_skinned_mesh
from ...assetio.metarig_bundle import bundled_bone_parents, bundled_rig_document
from ...assetio.mocap import MocapFormatError
from ...assetio.paths import backslash_depot_key, strip_json_suffix
from ...assetio.resources import base_body_path
from ...assetio.rlmotion import read_rlmotion
from ...assetio.values import cname_text
from ...bartmoss.hierarchy import (
    bone_basis_corrections,
    local_matrices_to_model,
    model_matrices_to_basis,
    model_matrices_to_local,
)
from ...bartmoss.trs import decompose_matrices
from ...blender.action_metadata import armature_skin_extras, load_json_snapshot
from ...blender.armature import inheritance_issue, rest_model_matrices
from ...blender.keyframes import assign_action_with_slot
from ...blender.rig_metadata import source_rig_paths
from ...blender.transactions import transactional
from ...core.log import get_logger
from ...gltf.anims import animation_channels, anims_document, skin_nodes
from ...gltf.builder import GLBBuilder
from ...gltf.container import encode_glb
from ...gltf.extras import animation_extras_for_export
from ...gltf.provenance import (
    DIRECT_ANIMATION_GENERATOR,
    ORIGIN_KEY,
    ORIGIN_PLUGIN,
    SOURCE_PATH_KEY,
    mark_origin,
)
from ...redSpace.transforms import (
    current_bone_model_transform_to_red,
    red_model_transform_to_current_bone,
    skeleton_relative_to_gltf,
)
from .document import import_anims_glb_to_armature

_LOG = get_logger(__name__)
_READERS = {".bvh": read_bvh, ".rlmotion": read_rlmotion}
_PROVENANCE_KEYS = (ORIGIN_KEY, SOURCE_PATH_KEY)


def _rig_skin(armature) -> dict:
    """The game rig's skin the clip is written for"""
    skin = armature_skin_extras(armature)
    if skin.get("boneNames"):
        return skin
    sources = [
        path
        for path in source_rig_paths(armature)
        if path.casefold().endswith(".rig.json")
    ]
    if not sources:
        raise MocapTargetError(
            "Select a Cyberpunk rig imported from its .glb, a bundled rig or a .rig.json."
        )
    return load_animation_rig_export_source(sources[0]).skin_extras


def _rig_document(armature, rig_path) -> dict:
    """The rig document holding the game's T-pose"""
    # A MetaRig's merged template holds the pose it was built in, so the shipped base rig comes first.
    shipped = bundled_rig_document(rig_path) if rig_path else None
    if shipped:
        return shipped
    return (
        decode_rig_export_template(str(armature.data.get(RIG_EXPORT_TEMPLATE_KEY, "")))
        or {}
    )


def _reference_model(document, names, rest):
    """The game's T-pose in model space for the armature's bones"""
    root = document.get("Data", {}).get("RootChunk", {})
    rig_names = [cname_text(entry) for entry in root.get("boneNames", ())]
    parents = root.get("boneParentIndexes") or ()
    transforms = root.get("boneTransforms") or ()
    reference = np.array(rest)
    if (
        not rig_names
        or len(parents) != len(rig_names)
        or len(transforms) != len(rig_names)
    ):
        return reference
    model = rig_model_matrices(transforms, parents)
    position = {name: index for index, name in enumerate(rig_names)}
    for bone, name in enumerate(names):
        if name in position:
            reference[bone] = model[position[name]]
    return reference


@lru_cache(maxsize=4)
def _body_source(rig_path):
    """The bundled base body for the rig at rig_path and its bones' parents, or None"""
    name = backslash_depot_key(strip_json_suffix(rig_path)).rsplit("\\", 1)[-1]
    body_path = base_body_path(name.removesuffix(".rig"))
    if body_path is None or not os.path.isfile(body_path):
        return None
    return read_skinned_mesh(body_path), bundled_bone_parents(rig_path)


def target_rig_from_armature(armature) -> TargetRig:
    """The armature's bones, rest and game T-pose in the game's model space"""
    if getattr(armature, "type", None) != "ARMATURE":
        raise MocapTargetError("Select the Cyberpunk rig the motion goes onto.")
    bones = armature.data.bones
    names = tuple(bone.name for bone in bones)
    missing = [name for name in TARGET_BONES if name not in names]
    if missing:
        raise MocapTargetError(
            f"{armature.name} lacks the game body bones {', '.join(missing)}."
        )
    changed = [bone.name for bone in bones if inheritance_issue(bone)]
    if changed:
        raise MocapTargetError(
            f"{armature.name} has bones with changed parent inheritance or local location: {', '.join(changed)}."
        )
    index = {name: position for position, name in enumerate(names)}
    parents = tuple(
        index[bone.parent.name] if bone.parent is not None else -1 for bone in bones
    )
    rest = current_bone_model_transform_to_red(rest_model_matrices(bones))
    skin = _rig_skin(armature)
    rig_path = str(skin.get("rigPath", ""))
    reference = _reference_model(_rig_document(armature, rig_path), names, rest)
    body = _body_source(rig_path) if rig_path else None
    return TargetRig(
        names=names,
        parents=parents,
        rest_model=rest,
        reference_model=reference,
        body=target_body(
            *body, names, parents, rest, [str(name) for name in skin["boneNames"]]
        )
        if body
        else None,
    )


def _read(filepath):
    reader = _READERS.get(os.path.splitext(filepath)[1].lower())
    if reader is None:
        raise MocapFormatError(
            f"{os.path.basename(filepath)}: only .bvh and .rlMotion files can be imported"
        )
    return reader(filepath)


def _clip_glb(name, armature, target, result, skin) -> bytes:
    """The retargeted motion as a game clip GLB"""
    joints = [str(joint) for joint in skin["boneNames"]]
    parents = [int(parent) for parent in skin["boneParentIndexes"]]
    index = {bone: position for position, bone in enumerate(target.names)}
    missing = [joint for joint in joints if joint not in index]
    if missing:
        raise MocapTargetError(
            f"{armature.name} lacks the rig's bones {', '.join(missing)}."
        )
    rows = [index[joint] for joint in joints]
    rest_model = rest_model_matrices(armature.data.bones)[rows]
    pose_model = red_model_transform_to_current_bone(result.model_matrices[:, rows])
    source_rest = source_rest_relative(
        load_json_snapshot(armature, SOURCE_REST_SNAPSHOT_KEY), tuple(joints)
    )
    if source_rest is None:
        source_rest = model_matrices_to_local(rest_model, parents)
    # Keyed as the exporter keys a pose, on the game rig's rest axes: a GLB-imported rig's Root bone points elsewhere.
    corrections = bone_basis_corrections(source_rest, parents, rest_model)
    basis = model_matrices_to_basis(pose_model, rest_model, parents)
    rest = skeleton_relative_to_gltf(source_rest, parents)
    pose = skeleton_relative_to_gltf(
        source_rest @ corrections @ basis @ np.linalg.inv(corrections), parents
    )
    # Bone-major, so the quaternion sign stays continuous along each joint's frames.
    translations, rotations, _scales = decompose_matrices(np.swapaxes(pose, 0, 1))
    times = np.arange(result.frame_count, dtype=np.float64) / FPS
    payloads = [
        {
            "joint_index": joint,
            "path": path,
            "interpolation": "LINEAR",
            "times": times,
            "values": values[joint],
        }
        for joint in range(len(joints))
        for path, values in (("translation", translations), ("rotation", rotations))
    ]
    builder = GLBBuilder(error_type=MocapTargetError)
    nodes, skin_node = skin_nodes(
        joints, parents, rest, local_matrices_to_model(rest, parents), skin, builder
    )
    samplers, channels = animation_channels(payloads, builder)
    extras = copy.deepcopy(ACTION_DEFAULTS)
    extras["rootMotionType"] = "None"
    animation = {
        "name": name,
        "channels": channels,
        "samplers": samplers,
        "extras": animation_extras_for_export(extras),
    }
    document = anims_document(
        nodes, skin_node, [animation], builder, DIRECT_ANIMATION_GENERATOR
    )
    return encode_glb(document, bytes(builder.binary))


@transactional("Mocap import")
def import_mocap_to_armature(filepath: str, armature) -> dict:
    """Retarget one BVH or rlMotion file onto the game rig as a game clip"""
    target = target_rig_from_armature(armature)
    skin = _rig_skin(armature)
    clip = _read(filepath)
    clip, dropped = without_calibration_frame(clip)
    result = retarget(clip, map_skeleton(clip.skeleton), target, FPS)
    payload = _clip_glb(clip.name, armature, target, result, skin)
    provenance = {key: armature[key] for key in _PROVENANCE_KEYS if key in armature}
    with tempfile.TemporaryDirectory(prefix="cp77_mocap_") as folder:
        path = os.path.join(folder, f"{clip.name}.anims.glb")
        with open(path, "wb") as handle:
            handle.write(payload)
        action = import_anims_glb_to_armature(path, armature)["actions"][0]
    # The clip comes from filepath, not the temporary .anims.glb, and the rig keeps the origin it had.
    for key in _PROVENANCE_KEYS:
        if key in provenance:
            armature[key] = provenance[key]
        elif key in armature:
            del armature[key]
    mark_origin(action, ORIGIN_PLUGIN, source_path=filepath)
    assign_action_with_slot(armature, action)
    _LOG.info(
        "Retargeted %s onto %s: %d frames at %.4g scale%s",
        clip.name,
        armature.name,
        result.frame_count,
        result.scale,
        ", calibration frame dropped" if dropped else "",
    )
    return {
        "action": action,
        "armature": armature,
        "frame_count": result.frame_count,
        "dropped_calibration_frame": dropped,
    }
