from __future__ import annotations

import numpy as np

from ....assetio.mocap import MocapClip
from ....bartmoss.curve import sample_linear, sample_quaternions_xyzw
from ....bartmoss.geometry import signed_angles, unit_vectors, vector_angles
from ....bartmoss.hierarchy import (
    local_matrices_to_model,
    model_matrices_to_local,
    parent_first_order,
)
from ....bartmoss.ik import two_bone_middle_positions
from ....bartmoss.matrix import axis_angle_matrices, rotation_vectors, swing_matrices
from ....bartmoss.quaternion import (
    IDENTITY_XYZW,
    matrix_from_xyzw,
    shortest_rotation_xyzw,
    slerp_xyzw,
    xyzw_from_matrices,
)
from ....bartmoss.trs import compose_matrices, compose_matrix
from ....redSpace.transforms import mocap_model_to_red
from ...model.mocap.clip import RetargetResult, TargetRig
from .body import clear_arms
from .shoulders import axis_angles, chest_axes, clavicle_directions, deviations, rhythm
from .skeleton_map import REQUIRED_BONES, SkeletonMap

_SPINE = ("Spine", "Spine1", "Spine2", "Spine3")
_NECK = ("Neck", "Neck1")
# How much of the head's turn from the chest the game's clips put on Neck, and on Neck and Neck1 together (the rest is
# the head's own): medians over the woman_average unarmed clips.
_NECK_SHARES = (0.35, 0.85)
_CLAVICLES = ("LeftShoulder", "RightShoulder")
# The game body bones the motion lands on.
TARGET_BONES = REQUIRED_BONES + tuple(
    bone for bone in (*_SPINE, *_NECK, *_CLAVICLES) if bone not in REQUIRED_BONES
)
# Only the long limb bones aim at the next bone of their chain: their rest differs between skeletons by pose (arms
# down, T-pose, arms forward, legs apart). Torso, neck, hands and feet differ by where each skeleton puts its joints,
# so they turn from their own rest instead of copying the source's bone directions. The legs then reach for where
# the performer's feet are from the pelvis, and the clavicles follow the game's rhythm with the upper arm.
_AIM_CHAINS = (
    ("Arm", "ForeArm", "Hand"),
    ("UpLeg", "Leg", "Foot"),
)
_UP = np.array((0.0, 0.0, 1.0))
# The game rigs' elbows and knees bend only about their upper bone's local -Z, and the forearm and shin never twist.
_HINGE = np.array((0.0, 0.0, -1.0))
# A source limb bent further than this (degrees) shows its hinge.
_BENT = 25.0
# Below _STRAIGHT degrees a limb's roll is left to the calibration; from _ROLLED on its bend plane sets the roll.
_STRAIGHT = 2.0
_ROLLED = 12.0


def _frame_times(clip, fps):
    return np.arange(int(round(clip.duration * fps)) + 1, dtype=np.float64) / fps


def _source_space_model(skeleton, rotations, translations):
    local = compose_matrices(translations, rotations, np.ones_like(translations))
    return local_matrices_to_model(local, skeleton.parents)


def sample_source_model(clip: MocapClip, fps: float) -> np.ndarray:
    """Source model matrices at times f / fps, in the game's model axes and the source's units"""
    skeleton = clip.skeleton
    times = _frame_times(clip, fps)
    rotations = np.repeat(skeleton.rest_rotations[None], len(times), axis=0)
    translations = np.repeat(skeleton.rest_translations[None], len(times), axis=0)
    for index, track in enumerate(clip.tracks):
        if track is None:
            continue
        rotations[:, index] = sample_quaternions_xyzw(
            track.times, track.rotations, times
        )
        if track.translations is not None:
            translations[:, index] = sample_linear(
                track.times, track.translations, times
            )
    return mocap_model_to_red(
        _source_space_model(skeleton, rotations, translations), clip.space
    )


def _rest_points(clip):
    """Rest model matrices of the joints and the positions of the joints and their end sites, in game axes"""
    skeleton = clip.skeleton
    model = _source_space_model(
        skeleton, skeleton.rest_rotations, skeleton.rest_translations
    )
    ends = [
        model[joint] @ compose_matrix(offset, IDENTITY_XYZW, (1.0, 1.0, 1.0))
        for joint, offset in enumerate(skeleton.end_offsets)
        if offset is not None
    ]
    converted = mocap_model_to_red(
        np.concatenate((model, np.asarray(ends).reshape(-1, 4, 4))), clip.space
    )
    return converted[: len(model)], converted[:, :3, 3]


def _leg_length(positions, legs):
    return float(
        np.mean(
            [
                np.linalg.norm(positions[thigh] - positions[shin])
                + np.linalg.norm(positions[shin] - positions[foot])
                for thigh, shin, foot in legs
            ]
        )
    )


def _heading(current, wanted):
    """The turn about the vertical axis that points current's horizontal part along wanted's"""
    current, wanted = current * (1.0, 1.0, 0.0), wanted * (1.0, 1.0, 0.0)
    return matrix_from_xyzw(shortest_rotation_xyzw(current, wanted, fallback_axis=_UP))[
        :3, :3
    ]


def _aims(mapping, index):
    """Source joint -> (source aim joint, target bone, target aim bone) for every mapped pair along a chain"""
    bones = mapping.bones
    aims = {}
    for side in ("Left", "Right"):
        for chain in _AIM_CHAINS:
            for bone, aim in zip(chain, chain[1:]):
                bone, aim = side + bone, side + aim
                if bone in bones and aim in bones and bone in index and aim in index:
                    aims[bones[bone]] = (bones[aim], index[bone], index[aim])
    return aims


def _source_hinges(source, mapping):
    """Each upper limb joint's bend axis in its own frame, measured on the clip's bent frames"""
    bones = mapping.bones
    hinges = {}
    for side in ("Left", "Right"):
        for upper, lower, end in _AIM_CHAINS:
            joints = [bones[side + bone] for bone in (upper, lower, end)]
            first = source[:, joints[1], :3, 3] - source[:, joints[0], :3, 3]
            second = source[:, joints[2], :3, 3] - source[:, joints[1], :3, 3]
            bent = np.degrees(vector_angles(first, second)) > _BENT
            if np.count_nonzero(bent) < 10:
                continue
            axes = unit_vectors(np.cross(first, second)[bent])
            local = np.einsum("fji,fj->fi", source[bent, joints[0], :3, :3], axes)
            mean = local.mean(axis=0)
            # A source whose elbow or knee does not bend about one axis of its own frame has no hinge to match.
            if np.linalg.norm(mean) > 0.8:
                hinges[joints[0]] = mean / np.linalg.norm(mean)
    return hinges


def _calibration(clip, rest, positions, mapping, target, index, hinges):
    """World rotations of the source posed like the target's reference pose"""
    bones = mapping.bones
    target_positions = target.reference_model[:, :3, 3]
    aims = _aims(mapping, index)
    hips = bones["Hips"]
    corrections = np.empty((len(rest), 3, 3))
    inherited = np.empty((len(rest), 3, 3))
    for joint in parent_first_order(clip.skeleton.parents):
        parent = clip.skeleton.parents[joint]
        correction = np.eye(3) if parent < 0 else inherited[parent]
        if joint == hips:
            correction = (
                _heading(
                    correction
                    @ (positions[bones["LeftUpLeg"]] - positions[bones["RightUpLeg"]]),
                    target_positions[index["LeftUpLeg"]]
                    - target_positions[index["RightUpLeg"]],
                )
                @ correction
            )
        elif joint in aims:
            aim, bone, bone_aim = aims[joint]
            wanted = unit_vectors(target_positions[bone_aim] - target_positions[bone])
            correction = (
                swing_matrices(correction @ (positions[aim] - positions[joint]), wanted)
                @ correction
            )
        inherited[joint] = correction
        if joint in hinges:
            # Roll the limb about itself so the source's elbow or knee hinge lies on the game's. The roll only relabels
            # the source bone's axes, so the joints below it do not take it.
            wanted = unit_vectors(
                target_positions[aims[joint][2]] - target_positions[aims[joint][1]]
            )
            hinge = correction @ rest[joint, :3, :3] @ hinges[joint]
            game = target.reference_model[aims[joint][1], :3, :3] @ _HINGE
            correction = (
                axis_angle_matrices(wanted, signed_angles(hinge, game, wanted))
                @ correction
            )
        corrections[joint] = correction
    return corrections @ rest[:, :3, :3]


def _chain_positions(points):
    lengths = np.concatenate(
        ([0.0], np.cumsum(np.linalg.norm(np.diff(points, axis=0), axis=1)))
    )
    return lengths / max(lengths[-1], 1e-12)


def _shared_deltas(keys, key_deltas, positions):
    """Deltas at chain positions, slerped between the two keys that bracket each position"""
    quaternions = [xyzw_from_matrices(delta, continuous=False) for delta in key_deltas]
    result = []
    for position in positions:
        upper = int(np.searchsorted(keys, position, side="right"))
        if upper == 0:
            value = quaternions[0]
        elif upper >= len(keys):
            value = quaternions[-1]
        else:
            weight = (position - keys[upper - 1]) / max(
                keys[upper] - keys[upper - 1], 1e-12
            )
            value = slerp_xyzw(quaternions[upper - 1], quaternions[upper], weight)
        frames = len(value)
        result.append(
            compose_matrices(np.zeros((frames, 3)), value, np.ones((frames, 3)))[
                :, :3, :3
            ]
        )
    return result


def retarget(
    clip: MocapClip, mapping: SkeletonMap, target: TargetRig, fps: float
) -> RetargetResult:
    """Target model matrices for every frame"""
    bones = mapping.bones
    index = {name: position for position, name in enumerate(target.names)}
    source = sample_source_model(clip, fps)
    rest, points = _rest_points(clip)
    positions = rest[:, :3, 3]
    target_positions = target.reference_model[:, :3, 3]
    legs = [
        tuple(f"{side}{bone}" for bone in ("UpLeg", "Leg", "Foot"))
        for side in ("Left", "Right")
    ]
    scale = _leg_length(
        target_positions, [[index[bone] for bone in leg] for leg in legs]
    ) / _leg_length(positions, [[bones[bone] for bone in leg] for leg in legs])

    calibrated = _calibration(
        clip, rest, positions, mapping, target, index, _source_hinges(source, mapping)
    )
    deltas = source[..., :3, :3] @ np.swapaxes(calibrated, -1, -2)
    turns = {
        index[bone]: deltas[:, joint]
        for bone, joint in bones.items()
        if bone not in _NECK and bone in index
    }

    hips = bones["Hips"]
    # Arms and neck hang from the last source spine joint and from Spine3, so the two chains end together there.
    spine_keys = _chain_positions(positions[[hips, *mapping.spine]])
    spine_targets = _chain_positions(
        target_positions[[index[bone] for bone in ("Hips", *_SPINE)]]
    )[1:]
    shared = _shared_deltas(
        spine_keys,
        [deltas[:, joint] for joint in (hips, *mapping.spine)],
        spine_targets,
    )
    turns.update({index[bone]: delta for bone, delta in zip(_SPINE, shared)})
    # The head keeps the performer's turn from the chest, spread over the neck as the game spreads it: sources that
    # carry it all on the head joint would otherwise bend the game's head on a still neck.
    chest = turns[index["Spine3"]]
    head_turn = rotation_vectors(np.swapaxes(chest, 1, 2) @ turns[index["Head"]])
    for bone, share in zip(_NECK, _NECK_SHARES):
        turns[index[bone]] = chest @ axis_angle_matrices(
            head_turn, share * np.linalg.norm(head_turn, axis=1)
        )

    _clavicles(turns, source, rest, positions, mapping, target, index)

    hips_path = source[:, hips, :3, 3]
    rest_height = positions[hips, 2] - float(np.min(points[:, 2]))
    hips_positions = np.column_stack(
        (
            scale * hips_path[:, :2],
            target_positions[index["Hips"], 2]
            + scale * (hips_path[:, 2] - rest_height),
        )
    )

    model = _compose(target, turns, index["Hips"], hips_positions)
    _place_legs(model, turns, source, mapping, target, index, scale)
    model = _compose(target, turns, index["Hips"], hips_positions)
    _hinge_limbs(model, turns, target, index, _AIM_CHAINS)
    model = _compose(target, turns, index["Hips"], hips_positions)
    if target.body is not None:
        clear_arms(model, turns, target.body, target.rest_model, index)
        model = _compose(target, turns, index["Hips"], hips_positions)
        _hinge_limbs(model, turns, target, index, _AIM_CHAINS[:1])
        model = _compose(target, turns, index["Hips"], hips_positions)
    keyed = tuple(
        bone in turns or bone == index["Hips"] for bone in range(len(target.names))
    )
    return RetargetResult(
        frame_count=len(model), model_matrices=model, keyed=keyed, scale=scale
    )


def _compose(target, turns, hips, hips_positions):
    """Model matrices of the target with the turned bones' world rotations and the hips' travel"""
    frame_count = len(hips_positions)
    rest_local = model_matrices_to_local(target.rest_model, target.parents)
    model = np.empty((frame_count, len(target.names), 4, 4))
    for bone in parent_first_order(target.parents):
        parent = target.parents[bone]
        pose = (
            np.repeat(target.rest_model[bone][None], frame_count, axis=0)
            if parent < 0
            else (model[:, parent] @ rest_local[bone])
        )
        if bone in turns:
            pose[:, :3, :3] = turns[bone] @ target.reference_model[bone, :3, :3]
        if bone == hips:
            pose[:, :3, 3] = hips_positions
        model[:, bone] = pose
    return model


def _hinge_limbs(model, turns, target, index, chains):
    """Roll the upper limbs into the game's hinge plane and bend the lower limbs only about the hinge"""
    reference = target.reference_model[:, :3, :3]
    rest = target.rest_model
    for side in ("Left", "Right"):
        for names in chains:
            upper, lower, end = (index[side + name] for name in names)
            first = model[:, lower, :3, 3] - model[:, upper, :3, 3]
            second = model[:, end, :3, 3] - model[:, lower, :3, 3]
            along = unit_vectors(first)
            hinge = model[:, upper, :3, :3] @ _HINGE
            bend = np.cross(first, second)
            bend = np.where(
                np.sum(bend * hinge, axis=-1, keepdims=True) < 0.0, -bend, bend
            )
            # A nearly straight limb shows no bend plane, so its roll eases back to the calibration's.
            weight = np.clip(
                (np.degrees(vector_angles(first, second)) - _STRAIGHT)
                / (_ROLLED - _STRAIGHT),
                0.0,
                1.0,
            )
            roll = axis_angle_matrices(
                along, weight * signed_angles(hinge, bend, along)
            )
            turns[upper] = roll @ turns[upper]
            upper_rotation = roll @ model[:, upper, :3, :3]
            straight = upper_rotation @ (rest[upper, :3, :3].T @ rest[lower, :3, :3])
            axes = upper_rotation @ _HINGE
            local = unit_vectors((np.linalg.inv(rest[lower]) @ rest[end][:, 3])[:3])
            pointing = np.einsum("fij,j->fi", straight, local)
            lower_rotation = (
                axis_angle_matrices(axes, signed_angles(pointing, second, axes))
                @ straight
            )
            # Bent past _ROLLED the limb lies in its hinge plane already; below it a small swing keeps the lower limb
            # on the performer's line.
            reached = np.einsum("fij,j->fi", lower_rotation, local)
            turns[lower] = (
                swing_matrices(reached, second) @ lower_rotation @ reference[lower].T
            )


def _clavicles(turns, source, rest, positions, mapping, target, index):
    """Clavicle turns that follow the game's rhythm with the upper arm and the performer's shrugs"""
    bones = mapping.bones
    reference = target.reference_model[:, :3, 3]
    chest = turns[index["Spine3"]]
    axes = chest @ chest_axes(
        reference[index["Neck"]] - reference[index["Spine"]],
        reference[index["LeftUpLeg"]] - reference[index["RightUpLeg"]],
    )
    source_chest = mapping.spine[-1]
    source_axes = (
        source[:, source_chest, :3, :3]
        @ rest[source_chest, :3, :3].T
        @ chest_axes(
            positions[mapping.neck[0]] - positions[mapping.spine[0]],
            positions[bones["LeftUpLeg"]] - positions[bones["RightUpLeg"]],
        )
    )
    joints = source[:, :, :3, 3]
    for side, outward in (("Left", 1.0), ("Right", -1.0)):
        arm, forearm, clavicle = (
            index[side + bone] for bone in ("Arm", "ForeArm", "Shoulder")
        )
        angles = rhythm(
            axis_angles(
                turns[arm] @ unit_vectors(reference[forearm] - reference[arm]), axes
            )
        )
        if side + "Shoulder" in bones:
            source_arm = joints[:, bones[side + "Arm"]]
            angles = angles + deviations(
                axis_angles(
                    source_arm - joints[:, bones[side + "Shoulder"]], source_axes
                ),
                axis_angles(
                    joints[:, bones[side + "ForeArm"]] - source_arm, source_axes
                ),
            )
        rigid = chest @ unit_vectors(reference[arm] - reference[clavicle])
        turns[clavicle] = (
            swing_matrices(rigid, clavicle_directions(angles, axes, outward)) @ chest
        )


def _place_legs(model, turns, source, mapping, target, index, scale):
    """Thigh and shin turns that set each foot where the performer's foot is from their pelvis, scaled"""
    bones = mapping.bones
    joints = source[:, :, :3, 3]
    source_centre = (
        joints[:, bones["LeftUpLeg"]] + joints[:, bones["RightUpLeg"]]
    ) / 2.0
    centre = (
        model[:, index["LeftUpLeg"], :3, 3] + model[:, index["RightUpLeg"], :3, 3]
    ) / 2.0
    rest = target.rest_model[:, :3, 3]
    for side in ("Left", "Right"):
        thigh, shin, foot = (index[side + bone] for bone in ("UpLeg", "Leg", "Foot"))
        hip, knee, ankle = (model[:, bone, :3, 3] for bone in (thigh, shin, foot))
        goal = centre + scale * (joints[:, bones[side + "Foot"]] - source_centre)
        thigh_length = float(np.linalg.norm(rest[shin] - rest[thigh]))
        shin_length = float(np.linalg.norm(rest[foot] - rest[shin]))
        # The knee bends toward where the performer's knee is from their pelvis; a straight leg bends the way its own
        # hinge lets it, toward the kneecap.
        kneecap = unit_vectors(np.cross(knee - hip, model[:, thigh, :3, :3] @ _HINGE))
        bend = (
            centre
            + scale * (joints[:, bones[side + "Leg"]] - source_centre)
            - hip
            + 0.02 * thigh_length * kneecap
        )
        placed = two_bone_middle_positions(hip, goal, thigh_length, shin_length, bend)
        swing = swing_matrices(knee - hip, placed - hip)
        turns[thigh] = swing @ turns[thigh]
        turns[shin] = swing_matrices(ankle - knee, goal - placed) @ turns[shin]
