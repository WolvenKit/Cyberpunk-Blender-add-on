from __future__ import annotations

import re
from collections.abc import Iterable

from ....core.log import get_logger, log_once

_LOG = get_logger(__name__)

# CP77 source bones mapped to Rigify human metarig names.
CP77_TO_METARIG: dict[str, str] = {
    "Hips": "pelvis",
    "Spine": "spine",
    "Spine1": "spine.001",
    "Spine2": "spine.002",
    "Spine3": "spine.003",
    "Neck": "spine.004",
    "Neck1": "spine.005",
    "Head": "spine.006",
    "LeftEye": "eye.L",
    "RightEye": "eye.R",
    "LeftUpLeg": "thigh.L",
    "LeftLeg": "shin.L",
    "LeftFoot": "foot.L",
    "LeftHeel": "heel.L",
    "LeftToeBase": "toe.L",
    "RightUpLeg": "thigh.R",
    "RightLeg": "shin.R",
    "RightFoot": "foot.R",
    "RightHeel": "heel.R",
    "RightToeBase": "toe.R",
    "LeftShoulder": "shoulder.L",
    "LeftArm": "upper_arm.L",
    "LeftForeArm": "forearm.L",
    "LeftHand": "hand.L",
    "WeaponLeft": "weapon.L",
    "RightShoulder": "shoulder.R",
    "RightArm": "upper_arm.R",
    "RightForeArm": "forearm.R",
    "RightHand": "hand.R",
    "WeaponRight": "weapon.R",
    "LeftInHandThumb": "thumb.01.L",
    "LeftHandThumb1": "thumb.02.L",
    "LeftHandThumb2": "thumb.03.L",
    "LeftInHandIndex": "palm.01.L",
    "LeftHandIndex1": "f_index.01.L",
    "LeftHandIndex2": "f_index.02.L",
    "LeftHandIndex3": "f_index.03.L",
    "LeftInHandMiddle": "palm.02.L",
    "LeftHandMiddle1": "f_middle.01.L",
    "LeftHandMiddle2": "f_middle.02.L",
    "LeftHandMiddle3": "f_middle.03.L",
    "LeftInHandRing": "palm.03.L",
    "LeftHandRing1": "f_ring.01.L",
    "LeftHandRing2": "f_ring.02.L",
    "LeftHandRing3": "f_ring.03.L",
    "LeftInHandPinky": "palm.04.L",
    "LeftHandPinky1": "f_pinky.01.L",
    "LeftHandPinky2": "f_pinky.02.L",
    "LeftHandPinky3": "f_pinky.03.L",
    "RightInHandThumb": "thumb.01.R",
    "RightHandThumb1": "thumb.02.R",
    "RightHandThumb2": "thumb.03.R",
    "RightInHandIndex": "palm.01.R",
    "RightHandIndex1": "f_index.01.R",
    "RightHandIndex2": "f_index.02.R",
    "RightHandIndex3": "f_index.03.R",
    "RightInHandMiddle": "palm.02.R",
    "RightHandMiddle1": "f_middle.01.R",
    "RightHandMiddle2": "f_middle.02.R",
    "RightHandMiddle3": "f_middle.03.R",
    "RightInHandRing": "palm.03.R",
    "RightHandRing1": "f_ring.01.R",
    "RightHandRing2": "f_ring.02.R",
    "RightHandRing3": "f_ring.03.R",
    "RightInHandPinky": "palm.04.R",
    "RightHandPinky1": "f_pinky.01.R",
    "RightHandPinky2": "f_pinky.02.R",
    "RightHandPinky3": "f_pinky.03.R",
}

METARIG_TO_CP77: dict[str, str] = {v: k for k, v in CP77_TO_METARIG.items()}


RIGIFY_TYPES: dict[str, str] = {
    "pelvis": "spines.basic_spine",
    "spine.004": "spines.super_head",
    "eye.L": "basic.super_copy",
    "eye.R": "basic.super_copy",
    "thigh.L": "limbs.leg",
    "thigh.R": "limbs.leg",
    "shoulder.L": "basic.super_copy",
    "shoulder.R": "basic.super_copy",
    "upper_arm.L": "limbs.arm",
    "upper_arm.R": "limbs.arm",
    "palm.01.L": "limbs.super_palm",
    "palm.01.R": "limbs.super_palm",
    "weapon.L": "basic.super_copy",
    "weapon.R": "basic.super_copy",
}
for _side in ("L", "R"):
    for _finger in ("thumb.01", "f_index.01", "f_middle.01", "f_ring.01", "f_pinky.01"):
        RIGIFY_TYPES[f"{_finger}.{_side}"] = "limbs.super_finger"


# Metarig connectivity applied before Rigify generation.
CHAINS: list[list[str]] = [
    ["pelvis", "spine", "spine.001", "spine.002", "spine.003"],
    ["spine.004", "spine.005", "spine.006"],
]
for _s in ("L", "R"):
    CHAINS.append([f"thigh.{_s}", f"shin.{_s}", f"foot.{_s}"])
    CHAINS.append([f"upper_arm.{_s}", f"forearm.{_s}", f"hand.{_s}"])


# Per-side finger chains used for endpoint repair and roll alignment.
METARIG_FINGER_CHAINS: dict[str, tuple[tuple[str, ...], ...]] = {}
for _s in ("L", "R"):
    METARIG_FINGER_CHAINS[_s] = (
        tuple(f"thumb.0{_j}.{_s}" for _j in range(1, 4)),
        tuple(f"f_index.0{_j}.{_s}" for _j in range(1, 4)),
        tuple(f"f_middle.0{_j}.{_s}" for _j in range(1, 4)),
        tuple(f"f_ring.0{_j}.{_s}" for _j in range(1, 4)),
        tuple(f"f_pinky.0{_j}.{_s}" for _j in range(1, 4)),
    )

# Palm bone at the base of each finger chain (the thumb's first segment is its own metacarpal).
FINGER_PALMS: dict[str, str | None] = {
    "thumb": None,
    "f_index": "palm.01",
    "f_middle": "palm.02",
    "f_ring": "palm.03",
    "f_pinky": "palm.04",
}


# Bone collection layout, after Rigify's human metarig: name -> (metarig members, UI row, color set, UI title).
COLLECTIONS: dict[str, tuple[list[str], int, int, str]] = {
    "Face": (["eye.L", "eye.R"], 1, 5, ""),
    "Torso": (
        [
            "pelvis",
            "spine",
            "spine.001",
            "spine.002",
            "spine.003",
            "spine.004",
            "spine.005",
            "spine.006",
            "shoulder.L",
            "shoulder.R",
        ],
        4,
        3,
        "",
    ),
    "Torso (Tweak)": ([], 5, 4, "(Tweak)"),
    "Fingers": (
        [f"palm.0{_i}.{_s}" for _s in ("L", "R") for _i in range(1, 5)]
        + [
            f"{_f}.0{_j}.{_s}"
            for _s in ("L", "R")
            for _f in ("thumb", "f_index", "f_middle", "f_ring", "f_pinky")
            for _j in range(1, 4)
        ],
        7,
        6,
        "",
    ),
    "Fingers (Detail)": ([], 8, 5, "(Detail)"),
}
for _s in ("L", "R"):
    COLLECTIONS[f"Arm.{_s} (IK)"] = (
        [f"upper_arm.{_s}", f"forearm.{_s}", f"hand.{_s}"],
        10,
        2,
        "",
    )
    COLLECTIONS[f"Arm.{_s} (FK)"] = ([], 11, 5, "(FK)")
    COLLECTIONS[f"Arm.{_s} (Tweak)"] = ([], 12, 4, "(Tweak)")
for _s in ("L", "R"):
    COLLECTIONS[f"Leg.{_s} (IK)"] = (
        [f"thigh.{_s}", f"shin.{_s}", f"foot.{_s}", f"heel.{_s}", f"toe.{_s}"],
        14,
        2,
        "",
    )
    COLLECTIONS[f"Leg.{_s} (FK)"] = ([], 15, 5, "(FK)")
    COLLECTIONS[f"Leg.{_s} (Tweak)"] = ([], 16, 4, "(Tweak)")
COLLECTIONS["Weapons"] = (["weapon.L", "weapon.R"], 18, 6, "")
COLLECTIONS["Root"] = (["root"], 19, 1, "")

# Collections each rig places its secondary controls in: metarig rig root -> ((parameter, collection), ...).
COLLECTION_REFS: dict[str, tuple[tuple[str, str], ...]] = {
    "pelvis": (("tweak", "Torso (Tweak)"), ("fk", "Torso (Tweak)")),
    "spine.004": (("tweak", "Torso (Tweak)"),),
}
for _s in ("L", "R"):
    COLLECTION_REFS[f"upper_arm.{_s}"] = (
        ("fk", f"Arm.{_s} (FK)"),
        ("tweak", f"Arm.{_s} (Tweak)"),
    )
    COLLECTION_REFS[f"thigh.{_s}"] = (
        ("fk", f"Leg.{_s} (FK)"),
        ("tweak", f"Leg.{_s} (Tweak)"),
    )
    for _finger in ("thumb.01", "f_index.01", "f_middle.01", "f_ring.01", "f_pinky.01"):
        COLLECTION_REFS[f"{_finger}.{_s}"] = (("tweak", "Fingers (Detail)"),)


COLOR_SETS: list[tuple[str, tuple[float, float, float], tuple[float, float, float]]] = [
    ("Root", (0.549, 1.000, 1.000), (0.435, 0.184, 0.416)),
    ("IK", (0.549, 1.000, 1.000), (0.604, 0.000, 0.000)),
    ("Special", (0.549, 1.000, 1.000), (0.957, 0.788, 0.047)),
    ("Tweak", (0.549, 1.000, 1.000), (0.039, 0.212, 0.580)),
    ("FK", (0.549, 1.000, 1.000), (0.118, 0.569, 0.035)),
    ("Extra", (0.549, 1.000, 1.000), (0.969, 0.251, 0.094)),
]

SELECT_COLOR: tuple[float, float, float] = (0.314, 0.784, 1.000)


# ID-property keys that link a source armature, its metarig and its generated Rigify rig.
METARIG_KEY: str = "cp77_metarig"
RIGIFY_RIG_KEY: str = "cp77_rigify_rig"
SOURCE_RIG_KEY: str = "cp77_source_rig"
RIG_ID_KEY: str = "cp77_rig_id"
RIGIFY_RIG_ID_KEY: str = "rig_id"

# Constraints that make the source bones follow the Rigify rig: rotation on every followed bone, location on the bones
# that move, and a reach limit on the hands and feet. The reverse constraint drove the Rigify controls from the source
# in an earlier scheme and is removed when the follow is bound.
FORWARD_CONSTRAINT: str = "CP77_RigifyDrivesSource"
FORWARD_LOCATION_CONSTRAINT: str = f"{FORWARD_CONSTRAINT}Location"
FORWARD_LIMIT_CONSTRAINT: str = f"{FORWARD_CONSTRAINT}Limit"
LEGACY_REVERSE_CONSTRAINT: str = "CP77_SourceDrivesRigify"

# Limit forward-sync translation to deform-safe CP77 joints; weapon bones place props, so they follow fully.
FORWARD_LOCATION_BONES = {"Root", "Hips", "WeaponLeft", "WeaponRight"}
FORWARD_LIMITED_LOCATION_BONES = {"LeftHand", "RightHand", "LeftFoot", "RightFoot"}
LIMITED_LOCATION_OFFSETS = {
    "LeftHand": 0.35,
    "RightHand": 0.35,
    "LeftFoot": 1.25,
    "RightFoot": 1.25,
}
MAX_LIMITED_LOCATION_OFFSET = 0.35


# Every follow constraint name, with one an earlier scheme left behind; all are cleared before the follow is bound.
FORWARD_CONSTRAINT_NAMES = (
    FORWARD_CONSTRAINT,
    FORWARD_LOCATION_CONSTRAINT,
    FORWARD_LIMIT_CONSTRAINT,
    "CP77_SourcePoseSyncBridge",
)

# Bones added to the Rigify rig for the follow, one per followed source bone.
FOLLOW_BONE_PREFIX = "MCH-CP77-"


def follow_bone_name(source_bone: str) -> str:
    return FOLLOW_BONE_PREFIX + source_bone


# Prefix for evaluated Rigify neutral matrices stored on the source armature.
FORWARD_NEUTRAL_PROP_PREFIX = "cp77_forward_neutral_"


def forward_neutral_key(source_bone: str) -> str:
    return FORWARD_NEUTRAL_PROP_PREFIX + source_bone


def _first_existing(names: set, candidates: Iterable[str]) -> str | None:
    for name in candidates:
        if name in names:
            return name
    return None


def resolve_forward_target(
    cp77_bone: str, metarig_bone: str, rig_bone_names: set
) -> str | None:
    """The generated bone a CP77 bone follows"""
    if cp77_bone == "Root":
        return _first_existing(rig_bone_names, ("root", "ORG-root", "DEF-root"))
    return _first_existing(
        rig_bone_names,
        (
            f"ORG-{metarig_bone}",
            f"DEF-{metarig_bone}",
            metarig_bone,
        ),
    )


def set_rigify_coll_prop(coll, name: str, value) -> None:
    try:
        setattr(coll, name, value)
    except (AttributeError, TypeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("set_rigify_coll_prop", type(error).__name__),
            "set rigify coll prop: fell back after %s",
            error,
            exc_info=True,
        )
        coll[name] = value


def get_rigify_coll_prop(coll, name: str, default=0):
    if hasattr(coll, name):
        return getattr(coll, name)
    return coll.get(name, default)


# Controls whose pose the control bake keys, by metarig bone. Limbs and the spine bake through their FK controls (the
# limb switches go to FK), the neck through its tweaks; each control moves its ORG bone as one rigid bone, so its
# pose follows from the CP77 bone's delta alone.
CONTROL_OVERRIDES: dict[str, tuple[str, ...]] = {
    # The first spine bone hangs from the hips FK control, so only its tweak turns it apart from the hips.
    "spine": ("tweak_spine",),
    # Each neck ORG bone copies the next tweak and stretches to the one after it.
    "spine.004": ("tweak_spine.005",),
    "spine.005": ("tweak_spine.006",),
    "spine.006": ("head",),
}

# First segment of each Rigify finger chain (thumb included).
FINGER_ROOTS: tuple[str, ...] = tuple(
    f"{_finger}.01.{_s}"
    for _s in ("L", "R")
    for _finger in ("thumb", "f_index", "f_middle", "f_ring", "f_pinky")
)


# Rigify's name structure: base, optional top/bottom and left/right parts, optional three-digit number.
_NAME_PARTS = re.compile(r"^(.*?)([._-][tTbB])?([._-][lLrR])?(?:\.(\d+))?$")


def _fk_name(metarig_bone: str) -> str:
    """Rigify's FK control name"""
    base, side_z, side, number = _NAME_PARTS.match(metarig_bone).groups()
    return f"{base}_fk{side_z or ''}{side or ''}{'.' + number if number else ''}"


def control_candidates(cp77_bone: str, metarig_bone: str) -> tuple[str, ...]:
    if cp77_bone == "Root":
        return ("root",)
    overrides = CONTROL_OVERRIDES.get(metarig_bone)
    if overrides is not None:
        return overrides
    return (_fk_name(metarig_bone), metarig_bone, f"tweak_{metarig_bone}")


# Pose-bone properties the control bake sets on every Rigify limb: FK mode, so the keyed FK controls drive the limbs.
LIMB_SWITCH_PROPERTY: str = "IK_FK"
LIMB_SWITCH_FK: float = 1.0
