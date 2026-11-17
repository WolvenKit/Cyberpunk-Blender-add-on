from __future__ import annotations

import numpy as np

from ....assetio.mocap import MocapClip
from ....bartmoss.curve import (
    gaussian_smoothed,
    sample_linear,
    sample_quaternions_xyzw,
    stepped_path,
)
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
from ....bartmoss.scalar import smoothstep
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
# so they turn from their own rest instead of copying the source's bone directions. The clavicles follow the game's
# rhythm with the upper arm.
_AIM_CHAINS = (
    ("Arm", "ForeArm", "Hand"),
    ("UpLeg", "Leg", "Foot"),
)
_UP = np.array((0.0, 0.0, 1.0))
# The game rigs' elbows and knees bend only about their upper bone's local -Z, and the forearm and shin never twist.
_HINGE = np.array((0.0, 0.0, -1.0))
# A source limb bent further than this (degrees) shows its elbow's or knee's hinge.
_BENT = 25.0
# Below _STRAIGHT degrees a limb's roll is held from the frames around it; from _ROLLED on its bend plane sets it.
_STRAIGHT = 5.0
_ROLLED = 15.0
# Frames (standard deviation) over which a limb's roll is eased.
_ROLL_SMOOTHING = 1.5
# The feet stand on the floor where the lower foot's lowest point, ankle or toe, sits on the clip's lowest twentieth of
# frames.
_PLANTED = 5.0
# Planted ankles this far (metres, at game scale) above where the source's rest pose stands mean the performer stands on
# something, so the source's own floor is kept.
_RAISED = 0.5
# A foot is on the floor while its lowest point is within _GROUNDED of where it stands and off it from _LIFTED (metres).
_GROUNDED = 0.03
_LIFTED = 0.06
# On the floor a foot steps as the performer's does, keeping none of a step slower than _STILL and all of one faster
# than _MOVING (metres a second, over _SPEED_SMOOTHING frames): it stands still where theirs creeps but swivels and
# shuffles.
_STILL = 0.03
_MOVING = 0.1
_SPEED_SMOOTHING = 2.0
# Off the floor a foot gives back this much each frame of its offset from where the performer's leg puts it, and it
# never strays further than _MOST_STRAY (metres).
_RELEASE = 0.25
_MOST_STRAY = 0.03


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


def _hinges(source, mapping):
    """Each upper limb joint's bend axis in its own frame, measured on the clip's bent frames"""
    bones = mapping.bones
    hinges = {}
    for side, chain in (
        (side, chain) for side in ("Left", "Right") for chain in _AIM_CHAINS
    ):
        joints = [bones[side + bone] for bone in chain]
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
            # Roll the limb about itself so the source's elbow or knee hinge lies on the game's: the performer's own
            # twist then turns the game's hinge as it turns theirs. The roll only relabels the source bone's axes, so
            # the joints below it do not take it.
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


def _soles(model, target, index):
    """Per frame and foot, how far the foot's lowest point, ankle or toe, is above where it stands"""
    reference = target.reference_model[:, 2, 3]
    heights = []
    for side in ("Left", "Right"):
        points = [
            index[side + bone] for bone in ("Foot", "ToeBase") if side + bone in index
        ]
        heights.append(np.min(model[:, points, 2, 3] - reference[points], axis=1))
    return np.stack(heights, axis=1)


def _hips_positions(model, source, positions, points, mapping, target, index, scale):
    """The hips' travel that moves the hip joints as the performer's do and stands the planted feet on the floor"""
    bones = mapping.bones
    # The legs hang from the hip joints, so those carry the performer's travel: the game's hips sit wherever its own
    # pelvis puts them from there.
    source_hips = np.mean(
        source[:, [bones[side + "UpLeg"] for side in ("Left", "Right")]][..., :3, 3],
        axis=1,
    )
    hip_joints = [index[side + "UpLeg"] for side in ("Left", "Right")]
    travel = (
        scale * source_hips
        - np.mean(model[:, hip_joints][..., :3, 3], axis=1)
        + model[:, index["Hips"], :3, 3]
    )
    ankles = [bones[side + "Foot"] for side in ("Left", "Right")]
    standing = float(np.mean(positions[ankles, 2])) - float(np.min(points[:, 2]))
    planted = float(np.percentile(np.min(source[:, ankles, 2, 3], axis=1), _PLANTED))
    if (planted - standing) * scale >= _RAISED:
        # The source's own floor is kept: the performer's rest stance lands on the game's.
        game_ankles = float(
            np.mean(
                target.reference_model[
                    [index[side + "Foot"] for side in ("Left", "Right")], 2, 3
                ]
            )
        )
        return travel + (0.0, 0.0, game_ankles - scale * standing)
    soles = (
        _soles(model, target, index)
        + (travel[:, 2] - model[:, index["Hips"], 2, 3])[:, None]
    )
    return travel - (0.0, 0.0, float(np.percentile(np.min(soles, axis=1), _PLANTED)))


def _limit_feet(model, turns, target, index):
    """Turn back any foot pointed past the line of its shin, which no ankle bends"""
    reference = target.reference_model
    for side in ("Left", "Right"):
        if side + "ToeBase" not in index:
            continue
        shin, foot, toe = (index[side + bone] for bone in ("Leg", "Foot", "ToeBase"))
        joints = reference[[shin, foot, toe], :3, 3]
        lateral = np.cross(joints[1] - joints[0], joints[2] - joints[1])
        axes = model[:, foot, :3, :3] @ unit_vectors(
            reference[foot, :3, :3].T @ lateral
        )
        angles = signed_angles(
            model[:, foot, :3, 3] - model[:, shin, :3, 3],
            model[:, toe, :3, 3] - model[:, foot, :3, 3],
            axes,
        )
        turns[foot] = axis_angle_matrices(axes, np.maximum(-angles, 0.0)) @ turns[foot]


def _held(ankle, performer, sole, fps):
    """An ankle path that steps as the performer's foot does while on the floor, less its creep"""
    steps = np.diff(performer[:, :2], axis=0, prepend=performer[:1, :2])
    kept = smoothstep(
        _STILL,
        _MOVING,
        gaussian_smoothed(np.linalg.norm(steps, axis=1), _SPEED_SMOOTHING) * fps,
    )
    grounded = 1.0 - smoothstep(_GROUNDED, _LIFTED, sole)
    own = np.diff(ankle[:, :2], axis=0, prepend=ankle[:1, :2])
    held = ankle.copy()
    held[:, :2] = stepped_path(
        ankle[:, :2],
        (grounded * kept)[:, None] * steps + (1.0 - grounded)[:, None] * own,
        _RELEASE * (1.0 - grounded),
        _MOST_STRAY,
    )
    return held


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
        clip, rest, positions, mapping, target, index, _hinges(source, mapping)
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

    rest_local = model_matrices_to_local(target.rest_model, target.parents)
    order = parent_first_order(target.parents)
    read = _read_bones(target, index)
    partial = tuple(bone for bone in order if bone in read)
    hips_bone = index["Hips"]
    # The pose is built at the origin first: the hips' travel is found from it and only moves it.
    model = _compose(
        target, turns, hips_bone, np.zeros((len(source), 3)), rest_local, partial
    )
    hips_positions = _hips_positions(
        model, source, positions, points, mapping, target, index, scale
    )
    limbs = _arm_directions(model, index)
    performer = {
        side: scale * source[:, bones[side + "Foot"], :3, 3]
        for side in ("Left", "Right")
    }
    limbs.update(_leg_directions(model, hips_positions, performer, target, index, fps))
    _solve_limbs(model, turns, target, index, limbs)
    _limit_feet(
        _compose(target, turns, hips_bone, hips_positions, rest_local, partial),
        turns,
        target,
        index,
    )
    if target.body is not None:
        model = _compose(target, turns, hips_bone, hips_positions, rest_local, partial)
        turned = clear_arms(model, turns, target.body, target.rest_model, index)
        if turned:
            model = _compose(
                target, turns, hips_bone, hips_positions, rest_local, partial
            )
            arms = _arm_directions(model, index)
            _solve_limbs(
                model,
                turns,
                target,
                index,
                {limb: arms[limb] for limb in arms if limb[0] in turned},
            )
    model = _compose(target, turns, hips_bone, hips_positions, rest_local, order)
    keyed = tuple(
        bone in turns or bone == hips_bone for bone in range(len(target.names))
    )
    return RetargetResult(
        frame_count=len(model), model_matrices=model, keyed=keyed, scale=scale
    )


def _read_bones(target, index):
    """The bones the foot, limb and arm passes read, with the bones they hang from"""
    wanted = {index[bone] for bone in TARGET_BONES}
    wanted.update(
        index[side + bone]
        for side in ("Left", "Right")
        for bone in ("HandMiddle1", "ToeBase")
        if side + bone in index
    )
    if target.body is not None:
        wanted.update(target.body.bones)
    read = set()
    for bone in wanted:
        while bone >= 0 and bone not in read:
            read.add(bone)
            bone = target.parents[bone]
    return read


def _compose(target, turns, hips, hips_positions, rest_local, bones):
    """Model matrices of bones, parents first, with the turned bones' world rotations and the hips' travel"""
    frame_count = len(hips_positions)
    model = np.empty((frame_count, len(target.names), 4, 4))
    for bone in bones:
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


def _arm_directions(model, index):
    """Per arm, the upper arm and forearm directions it holds now"""
    chain = _AIM_CHAINS[0]
    limbs = {}
    for side in ("Left", "Right"):
        shoulder, elbow, wrist = (model[:, index[side + name], :3, 3] for name in chain)
        limbs[side, chain] = (elbow - shoulder, wrist - elbow)
    return limbs


def _continuous_rolls(rolls, confidence):
    """Rolls carried on from frame to frame, held from the neighbouring frames where the bend plane cannot be seen"""
    frames = np.arange(len(rolls))
    sure = confidence >= 1.0
    held = (
        np.interp(frames, frames[sure], np.unwrap(rolls[sure]))
        if np.any(sure)
        else np.zeros(len(rolls))
    )
    # A partly bent limb leans toward its own roll, taken the short way round from the held one and eased, since a
    # small bend's plane is mostly noise. A clearly bent limb keeps its own roll.
    own = held + (rolls - held + np.pi) % (2.0 * np.pi) - np.pi
    return np.where(
        sure, own, gaussian_smoothed(held + confidence * (own - held), _ROLL_SMOOTHING)
    )


def _swung(rotations, axis, directions):
    """rotations swung so their axis points along directions"""
    return (
        swing_matrices(
            np.einsum("fij,j->fi", rotations, axis), unit_vectors(directions)
        )
        @ rotations
    )


def _solve_limbs(model, turns, target, index, limbs):
    """Turn each limb's upper and lower bones along the wanted directions, bending only about the game hinge"""
    reference = target.reference_model[:, :3, :3]
    rest = target.rest_model
    for (side, names), (upper_directions, lower_directions) in limbs.items():
        upper, lower, end = (index[side + name] for name in names)
        upper_axis = unit_vectors((np.linalg.inv(rest[upper]) @ rest[lower][:, 3])[:3])
        rotations = model[:, upper, :3, :3]
        planes = signed_angles(
            _swung(rotations, upper_axis, upper_directions) @ _HINGE,
            unit_vectors(np.cross(upper_directions, lower_directions)),
            unit_vectors(upper_directions),
        )
        # A limb bent the way its joint cannot is the performer's elbow or knee pushed past straight: it straightens,
        # aimed where their limb ends, and keeps their twist.
        backward = np.abs(planes) > np.pi / 2
        reach = upper_directions + lower_directions
        upper_directions = np.where(backward[:, None], reach, upper_directions)
        lower_directions = np.where(backward[:, None], reach, lower_directions)
        along = unit_vectors(upper_directions)
        upper_rotation = _swung(rotations, upper_axis, upper_directions)
        # The upper bone rolls its hinge onto the bend, so the bend always flexes the joint.
        bend = np.degrees(vector_angles(upper_directions, lower_directions))
        rolls = _continuous_rolls(
            np.where(backward, 0.0, planes),
            np.clip((bend - _STRAIGHT) / (_ROLLED - _STRAIGHT), 0.0, 1.0),
        )
        upper_rotation = axis_angle_matrices(along, rolls) @ upper_rotation
        straight = upper_rotation @ (rest[upper, :3, :3].T @ rest[lower, :3, :3])
        axes = upper_rotation @ _HINGE
        local = unit_vectors((np.linalg.inv(rest[lower]) @ rest[end][:, 3])[:3])
        pointing = np.einsum("fij,j->fi", straight, local)
        lower_rotation = (
            axis_angle_matrices(axes, signed_angles(pointing, lower_directions, axes))
            @ straight
        )
        # Where the roll is held rather than measured, a small swing keeps the lower limb on the wanted line.
        reached = np.einsum("fij,j->fi", lower_rotation, local)
        turns[upper] = upper_rotation @ reference[upper].T
        turns[lower] = (
            swing_matrices(reached, lower_directions)
            @ lower_rotation
            @ reference[lower].T
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


def _leg_directions(model, hips_positions, performer, target, index, fps):
    """Per leg, the thigh and shin directions: the performer's, turned only to stand a planted foot still"""
    rest = target.rest_model[:, :3, 3]
    offset = hips_positions - model[:, index["Hips"], :3, 3]
    soles = _soles(model, target, index) + offset[:, 2:3]
    chain = _AIM_CHAINS[1]
    limbs = {}
    for column, side in enumerate(("Left", "Right")):
        thigh, shin, foot = (index[side + bone] for bone in chain)
        hip, knee, ankle = (
            model[:, bone, :3, 3] + offset for bone in (thigh, shin, foot)
        )
        goal = _held(ankle, performer[side], soles[:, column], fps)
        thigh_length = float(np.linalg.norm(rest[shin] - rest[thigh]))
        shin_length = float(np.linalg.norm(rest[foot] - rest[shin]))
        # Holding the foot moves the performer's own knee only as far as the hold needs. A leg they hold straight shows
        # no bend direction, so the hold bends it the way its own hinge lets it, toward the kneecap.
        shown = np.clip(
            (np.degrees(vector_angles(knee - hip, ankle - knee)) - _STRAIGHT)
            / (_ROLLED - _STRAIGHT),
            0.0,
            1.0,
        )[:, None]
        reach = unit_vectors(ankle - hip)
        bent = unit_vectors(
            (knee - hip) - np.sum((knee - hip) * reach, axis=1, keepdims=True) * reach
        )
        kneecap = unit_vectors(np.cross(knee - hip, model[:, thigh, :3, :3] @ _HINGE))
        bend = shown * bent + (1.0 - shown) * kneecap
        placed = knee + (
            two_bone_middle_positions(hip, goal, thigh_length, shin_length, bend)
            - two_bone_middle_positions(hip, ankle, thigh_length, shin_length, bend)
        )
        limbs[side, chain] = (placed - hip, goal - placed)
    return limbs
