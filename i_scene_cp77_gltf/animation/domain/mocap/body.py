from __future__ import annotations

import numpy as np

from ....assetio.mesh_npz import SkinnedMesh
from ....bartmoss.geometry import closest_point_on_segment
from ....bartmoss.matrix import axis_angle_matrices, rotation_vectors
from ....bartmoss.skinning import skinned_points
from ...model.mocap.clip import TargetBody

_SIDES = ("Left", "Right")
# Body points closer together than this (metres) are merged, which keeps the per-frame search small.
_SPACING = 0.02
# How deep (metres) an arm may sink into the body before it is turned out: the game's own clips sink about this far,
# where its deformation bones reshape the skin that this body follows rigidly.
_ALLOWANCE = 0.02
_PASSES = 6
_MOST_STEP = np.radians(8.0)
_FRAMES_PER_BLOCK = 128
# Frames (standard deviation) over which the turns are smoothed, so the arm never pops between frames.
_SMOOTHING = 4.0
# Where the upper arm and forearm are tested, as fractions of the way from their root joint. The upper arm nearer the
# shoulder lies against the chest's side, which the game reshapes as the arm moves; the legs bend the same way, so
# only the torso and pelvis are kept out of.
_UPPER = (0.85, 1.0)
_FORE = (0.25, 0.5, 0.75, 1.0)
# Arm segments the body file cannot measure keep these thicknesses (metres).
_DEFAULT_RADII = (0.045, 0.035, 0.025)


def _limb_bones(names, parents, index, limb):
    roots = {index[side + limb] for side in _SIDES}
    found = set()
    for bone in range(len(names)):
        current = bone
        while current >= 0 and current not in roots:
            current = parents[current]
        if current >= 0:
            found.add(bone)
    return found


def _owners(groups, bone_parents, index):
    """The rig bone each weight group deforms with"""
    owners = []
    for group in groups:
        bone, steps = group, 0
        while bone not in index and bone in bone_parents and steps < 64:
            bone, steps = bone_parents[bone], steps + 1
        owners.append(index.get(bone, -1))
    return np.array(owners, dtype=np.int64)


def _radius(points, dominant, column, start, end, fallback):
    """The median distance of the points a bone drives most from the bone's segment"""
    near = dominant == column
    if column < 0 or np.count_nonzero(near) < 8:
        return fallback
    return float(
        np.median(
            np.linalg.norm(
                points[near] - closest_point_on_segment(points[near], start, end),
                axis=1,
            )
        )
    )


def target_body(
    mesh: SkinnedMesh, bone_parents: dict, names, parents, rest_model, skin_names
) -> TargetBody:
    """The torso as the rig's skin bones deform it, and the arm thicknesses"""
    # Helpers fold into their skin bone even where the armature has them, so every rig of one skin gets one body.
    skin = set(skin_names)
    index = {name: position for position, name in enumerate(names) if name in skin}
    owners = _owners(mesh.groups, bone_parents, index)[mesh.group_indices]
    kept = owners >= 0
    bones = np.unique(owners[kept])
    column = np.full(len(names), -1, dtype=np.int64)
    column[bones] = np.arange(len(bones))
    weights = np.zeros((len(mesh.points), len(bones)))
    np.add.at(
        weights, (mesh.vertex_indices[kept], column[owners[kept]]), mesh.weights[kept]
    )
    totals = weights.sum(axis=1)
    skinned = totals > 1e-4
    weights[skinned] /= totals[skinned, None]

    arm = [
        column[bone]
        for bone in _limb_bones(names, parents, index, "Arm")
        if column[bone] >= 0
    ]
    leg = [
        column[bone]
        for bone in _limb_bones(names, parents, index, "UpLeg")
        if column[bone] >= 0
    ]
    body = (
        skinned
        & (weights[:, arm].sum(axis=1) < 0.05)
        & (weights[:, leg].sum(axis=1) < 0.5)
    )
    rest = rest_model[:, :3, 3]
    dominant = np.where(skinned, np.argmax(weights, axis=1), -1)
    knuckle = index.get("LeftHandMiddle1", index["LeftHand"])
    radii = tuple(
        _radius(
            mesh.points,
            dominant,
            column[index[start]],
            rest[index[start]],
            rest[end],
            fallback,
        )
        for start, end, fallback in zip(
            ("LeftArm", "LeftForeArm", "LeftHand"),
            (index["LeftForeArm"], index["LeftHand"], knuckle),
            _DEFAULT_RADII,
        )
    )
    candidates = np.flatnonzero(body)
    _cells, first = np.unique(
        np.floor(mesh.points[candidates] / _SPACING).astype(np.int64),
        axis=0,
        return_index=True,
    )
    chosen = candidates[np.sort(first)]
    return TargetBody(
        points=mesh.points[chosen],
        normals=mesh.normals[chosen],
        bones=tuple(int(bone) for bone in bones),
        weights=weights[chosen],
        arm_radii=radii,
    )


def _depths(points, normals, tests, radii):
    """How deep each test point sinks into the body, and the body normal nearest it"""
    gaps = tests[:, :, None, :] - points[:, None, :, :]
    nearest = np.argmin(np.einsum("ftnk,ftnk->ftn", gaps, gaps), axis=2)
    frames = np.arange(len(points))[:, None]
    normal = normals[frames, nearest]
    outside = np.einsum("ftk,ftk->ft", tests - points[frames, nearest], normal)
    return radii[None, :] - outside - _ALLOWANCE, normal


def _turn_out(points, normals, pivot, joints, segments):
    """Per-frame turns about pivot that lift the tested segments out of the body"""
    # joints[0] turns about pivot and the later joints move with it. Each segment (joint, fractions, radius) tests the
    # stretch from the joint before it (or the pivot) to that joint.
    turn = np.repeat(np.eye(3)[None], len(pivot), axis=0)
    radii = np.array(
        [radius for _joint, fractions, radius in segments for _fraction in fractions]
    )
    frames = np.arange(len(pivot))
    for _pass in range(_PASSES):
        turned = pivot + np.einsum("fij,fj->fi", turn, joints[0] - pivot)
        placed = [turned] + [joint + turned - joints[0] for joint in joints[1:]]
        tests = np.stack(
            [
                (pivot if joint == 0 else placed[joint - 1]) * (1.0 - fraction)
                + placed[joint] * fraction
                for joint, fractions, _radius in segments
                for fraction in fractions
            ],
            axis=1,
        )
        depths, normal = _depths(points, normals, tests, radii)
        levers = tests - pivot[:, None, :]
        axes = np.cross(levers, normal)
        reach = np.linalg.norm(axes, axis=2)
        # A point pushed along the arm itself cannot be turned out.
        depths = np.where(reach > 0.3 * np.linalg.norm(levers, axis=2), depths, 0.0)
        deepest = np.argmax(depths, axis=1)
        depth = depths[frames, deepest]
        if not np.any(depth > 1e-5):
            break
        angles = np.clip(
            depth / np.maximum(reach[frames, deepest], 1e-6), 0.0, _MOST_STEP
        )
        turn = (
            axis_angle_matrices(
                axes[frames, deepest], np.where(depth > 1e-5, angles, 0.0)
            )
            @ turn
        )
    return turn


def _smoothed(turns):
    """Turns eased in and out over neighbouring frames, never weaker than the frames' own"""
    radius = int(np.ceil(3.0 * _SMOOTHING))
    kernel = np.exp(-0.5 * (np.arange(-radius, radius + 1) / _SMOOTHING) ** 2)
    vectors = rotation_vectors(turns)
    # Each frame first takes the strongest turn near it, so smoothing ramps into a brief contact instead of halving it.
    reach = int(np.ceil(2.0 * _SMOOTHING))
    padded = np.pad(vectors, ((reach, reach), (0, 0)), mode="edge")
    windows = np.stack(
        [padded[offset : offset + len(vectors)] for offset in range(2 * reach + 1)],
        axis=1,
    )
    strongest = np.argmax(np.linalg.norm(windows, axis=2), axis=1)
    vectors = np.pad(
        windows[np.arange(len(vectors)), strongest],
        ((radius, radius), (0, 0)),
        mode="edge",
    )
    kernel /= kernel.sum()
    smoothed = np.stack(
        [np.convolve(vectors[:, axis], kernel, mode="valid") for axis in range(3)],
        axis=1,
    )
    return axis_angle_matrices(smoothed, np.linalg.norm(smoothed, axis=1))


def clear_arms(model, turns, body: TargetBody, rest_model, index) -> None:
    """Turn the upper arms and forearms out of the torso on the frames they would pass into it"""
    bones = list(body.bones)
    inverse_rest = np.linalg.inv(rest_model[bones])
    upper, fore, hand = body.arm_radii
    frame_count = len(model)
    corrections = {
        side: (np.empty((frame_count, 3, 3)), np.empty((frame_count, 3, 3)))
        for side in _SIDES
    }
    for start in range(0, frame_count, _FRAMES_PER_BLOCK):
        block = slice(start, start + _FRAMES_PER_BLOCK)
        points, normals = skinned_points(
            body.points,
            body.normals,
            body.weights,
            model[block][:, bones] @ inverse_rest,
        )
        for side in _SIDES:
            arm, forearm, wrist = (
                index[side + bone] for bone in ("Arm", "ForeArm", "Hand")
            )
            shoulder, elbow, hand_joint = (
                model[block, bone, :3, 3] for bone in (arm, forearm, wrist)
            )
            knuckle = model[block, index.get(side + "HandMiddle1", wrist), :3, 3]
            upper_turn = _turn_out(
                points,
                normals,
                shoulder,
                (elbow, hand_joint, knuckle),
                ((0, _UPPER, upper),),
            )
            shift = (
                shoulder + np.einsum("fij,fj->fi", upper_turn, elbow - shoulder) - elbow
            )
            corrections[side][0][block] = upper_turn
            corrections[side][1][block] = _turn_out(
                points,
                normals,
                elbow + shift,
                (hand_joint + shift, knuckle + shift),
                ((0, _FORE, fore), (1, (1.0,), hand)),
            )
    for side, (upper_turns, fore_turns) in corrections.items():
        for bone, correction in (("Arm", upper_turns), ("ForeArm", fore_turns)):
            turns[index[side + bone]] = (
                _smoothed(correction) @ turns[index[side + bone]]
            )
