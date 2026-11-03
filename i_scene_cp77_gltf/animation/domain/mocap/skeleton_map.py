from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

from ....assetio.mocap import MocapSkeleton
from ...model.mocap.clip import MocapSkeletonError

REQUIRED_BONES = (
    "Hips",
    "LeftUpLeg",
    "LeftLeg",
    "LeftFoot",
    "RightUpLeg",
    "RightLeg",
    "RightFoot",
    "Neck",
    "Head",
    "LeftArm",
    "LeftForeArm",
    "LeftHand",
    "RightArm",
    "RightForeArm",
    "RightHand",
)
_LEG_ROLES = (
    ("UpLeg", frozenset({"upleg", "thigh", "hip", "upperleg"})),
    ("Leg", frozenset({"leg", "shin", "knee", "lowleg", "lowerleg", "calf"})),
    ("Foot", frozenset({"foot", "ankle"})),
    ("ToeBase", frozenset({"toebase", "toe"})),
)
_UPPER_ARM = frozenset({"arm", "shldr", "uparm", "upperarm"})
_ARM_ROLES = (
    ("Shoulder", frozenset({"collar", "clavicle"})),
    ("Arm", _UPPER_ARM),
    ("ForeArm", frozenset({"forearm", "elbow", "lowarm", "lowerarm"})),
    ("Hand", frozenset({"hand", "wrist"})),
)
_FOOT = _LEG_ROLES[2][1]
_HAND = _ARM_ROLES[3][1]
_NECK = frozenset({"neck", "neck1", "neck2"})
_HEAD = frozenset({"head"})
_FINGERS = ("Thumb", "Index", "Middle", "Ring", "Pinky")
_FINGER_WORDS = {
    "thumb": "Thumb",
    "index": "Index",
    "middle": "Middle",
    "mid": "Middle",
    "ring": "Ring",
    "pinky": "Pinky",
}
_NAMED_FINGER = re.compile(r"^(?:hand)?(thumb|index|middle|mid|ring|pinky)(\d)(_end)?$")
_NUMBERED_FINGER = re.compile(r"^finger([0-4])(\d?)$")
_SIDE_PREFIX = re.compile(r"^(?:(Left|Right)|([LRlr])(?=[A-Z_]))_?(.+)$")
_SIDE_SUFFIX = re.compile(r"^(.+?)[_.](Left|Right|[LRlr])$")
# HumanIK slots: body bones, then the left hand's thumb and finger joints (the right hand's are 24 higher).
_HIK_BONES = {
    1: "Hips",
    2: "LeftUpLeg",
    3: "LeftLeg",
    4: "LeftFoot",
    16: "LeftToeBase",
    5: "RightUpLeg",
    6: "RightLeg",
    7: "RightFoot",
    17: "RightToeBase",
    18: "LeftShoulder",
    9: "LeftArm",
    10: "LeftForeArm",
    11: "LeftHand",
    19: "RightShoulder",
    12: "RightArm",
    13: "RightForeArm",
    14: "RightHand",
    20: "Neck",
    15: "Head",
}
_HIK_SPINE = (8, 23, 24)
_HIK_FINGERS = {
    50: "InHandThumb",
    51: "HandThumb1",
    52: "HandThumb2",
    **{
        54 + 4 * finger + segment: f"Hand{name}{segment + 1}"
        for finger, name in enumerate(_FINGERS[1:])
        for segment in range(3)
    },
}
_HIK_RIGHT_OFFSET = 24


@dataclass(frozen=True)
class SkeletonMap:
    bones: Mapping[str, int]
    spine: tuple[int, ...]
    neck: tuple[int, ...]


def map_skeleton(skeleton: MocapSkeleton) -> SkeletonMap:
    """Match a source skeleton's joints to the game body bones, or fail naming what does not match"""
    if skeleton.hik_slots:
        return _map_hik(skeleton)
    return _map_named(skeleton)


def _map_hik(skeleton):
    slots = {slot: index for index, slot in enumerate(skeleton.hik_slots) if slot >= 0}
    bones = {bone: slots[slot] for slot, bone in _HIK_BONES.items() if slot in slots}
    for slot, name in _HIK_FINGERS.items():
        for side, offset in (("Left", 0), ("Right", _HIK_RIGHT_OFFSET)):
            if slot + offset in slots:
                bones[side + name] = slots[slot + offset]
    _require(bones, {})
    spine = tuple(slots[slot] for slot in _HIK_SPINE if slot in slots)
    return SkeletonMap(bones=bones, spine=spine, neck=(bones["Neck"],))


def _side_and_base(name):
    """The joint's side and its lower-case name without namespace and side marker"""
    name = name.rsplit(":", 1)[-1]
    match = _SIDE_PREFIX.match(name)
    if match is not None:
        word, letter, base = match.groups()
        return ("Left" if (word or letter)[0] in "Ll" else "Right"), base.lower()
    match = _SIDE_SUFFIX.match(name)
    if match is not None:
        return ("Left" if match.group(2)[0] in "Ll" else "Right"), match.group(
            1
        ).lower()
    return None, name.lower()


def _map_named(skeleton):
    names = skeleton.names
    sides, bases = zip(*(_side_and_base(name) for name in names))
    children = [[] for _ in names]
    for index, parent in enumerate(skeleton.parents):
        if parent >= 0:
            children[parent].append(index)

    def contains(index, aliases):
        pending = [index]
        while pending:
            current = pending.pop()
            if bases[current] in aliases:
                return True
            pending.extend(children[current])
        return False

    hips = next(index for index, parent in enumerate(skeleton.parents) if parent < 0)
    while len(children[hips]) == 1 and sides[children[hips][0]] is None:
        hips = children[hips][0]
    bones, ambiguous = {"Hips": hips}, {}

    trunk = []
    current = hips
    while bases[current] not in _HEAD:
        upward = [
            child
            for child in children[current]
            if sides[child] is None and contains(child, _HEAD)
        ]
        if not upward:
            break
        current = upward[0]
        trunk.append(current)
    if trunk and bases[trunk[-1]] in _HEAD:
        bones["Head"] = trunk.pop()
    neck = tuple(joint for joint in trunk if bases[joint] in _NECK)
    if neck:
        bones["Neck"] = neck[0]
    spine = tuple(trunk[: trunk.index(neck[0])]) if neck else tuple(trunk)

    for side in ("Left", "Right"):
        legs = [
            child
            for child in children[hips]
            if sides[child] == side and contains(child, _FOOT)
        ]
        if legs:
            chain = _linear_chain(legs[0], children)
            _assign(
                chain,
                side,
                [_role(bases[joint], _LEG_ROLES) for joint in chain],
                names,
                bones,
                ambiguous,
            )
        arms = [
            child
            for joint in trunk
            for child in children[joint]
            if sides[child] == side and contains(child, _HAND)
        ]
        if arms:
            chain = _linear_chain(arms[0], children)
            _assign(chain, side, _arm_roles(chain, bases), names, bones, ambiguous)
        if side + "Hand" in bones:
            bones.update(_finger_bones(side, bones[side + "Hand"], children, bases))
    _require(bones, ambiguous)
    return SkeletonMap(bones=bones, spine=spine, neck=neck)


def _linear_chain(start, children):
    """The joints from start down while each has a single child, ending at the first branch or leaf"""
    chain = [start]
    while len(children[chain[-1]]) == 1:
        chain.append(children[chain[-1]][0])
    return chain


def _role(base, roles):
    return next((role for role, aliases in roles if base in aliases), None)


def _arm_roles(chain, bases):
    """A "shoulder" joint is the clavicle when an upper arm follows it, else the upper arm itself"""
    roles = []
    for position, joint in enumerate(chain):
        if bases[joint] == "shoulder":
            following = bases[chain[position + 1]] if position + 1 < len(chain) else ""
            roles.append("Shoulder" if following in _UPPER_ARM else "Arm")
        else:
            roles.append(_role(bases[joint], _ARM_ROLES))
    return roles


def _assign(chain, side, roles, names, bones, ambiguous):
    found = {}
    for joint, role in zip(chain, roles):
        if role is not None:
            found.setdefault(side + role, []).append(joint)
    for bone, joints in found.items():
        if len(joints) > 1:
            ambiguous[bone] = tuple(names[joint] for joint in joints)
        else:
            bones[bone] = joints[0]


def _finger_segment(base):
    match = _NAMED_FINGER.match(base)
    if match is not None:
        return _FINGER_WORDS[match.group(1)], int(match.group(2)) + (
            1 if match.group(3) else 0
        )
    match = _NUMBERED_FINGER.match(base)
    if match is not None:
        return _FINGERS[int(match.group(1))], int(match.group(2)) + 1 if match.group(
            2
        ) else 1
    return None, None


def _finger_bones(side, hand, children, bases):
    """Game finger bones for every finger whose three joints all sit below the hand"""
    segments = {}
    pending = [(child, None) for child in children[hand]]
    while pending:
        joint, finger = pending.pop()
        name, segment = _finger_segment(bases[joint])
        if name is not None and finger in (None, name):
            segments.setdefault(name, {}).setdefault(segment, []).append(joint)
            finger = name
        pending.extend((child, finger) for child in children[joint])
    bones = {}
    for name, found in segments.items():
        if any(len(found.get(segment, ())) != 1 for segment in (1, 2, 3)):
            continue
        targets = (
            ("InHandThumb", "HandThumb1", "HandThumb2")
            if name == "Thumb"
            else (f"Hand{name}1", f"Hand{name}2", f"Hand{name}3")
        )
        for segment, target in zip((1, 2, 3), targets):
            bones[side + target] = found[segment][0]
    return bones


def _require(bones, ambiguous):
    missing = tuple(
        bone for bone in REQUIRED_BONES if bone not in bones and bone not in ambiguous
    )
    if missing or ambiguous:
        raise MocapSkeletonError(missing, ambiguous)
