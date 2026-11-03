from __future__ import annotations

# Rigify limb and torso control names exposed by the Animation Tools Rigify panel.

_LEG_CHAIN = ("thigh", "shin", "foot")
_ARM_CHAIN = ("upper_arm", "forearm", "hand")

LIMBS: tuple[tuple[str, str, str, bool], ...] = (
    ("Arm L", "arm", "L", False),
    ("Arm R", "arm", "R", False),
    ("Leg L", "leg", "L", True),
    ("Leg R", "leg", "R", True),
)

TORSO_SELECTION: frozenset[str] = frozenset(
    {
        "torso",
        "chest",
        "hips",
        "spine_fk",
        "spine_fk.001",
        "spine_fk.002",
        "spine_fk.003",
        "pelvis_fk",
        "tweak_pelvis",
        "tweak_spine",
        "head",
        "neck",
    }
)


def limb_chain(*, is_leg: bool) -> tuple[str, str, str]:
    return _LEG_CHAIN if is_leg else _ARM_CHAIN


def limb_fk_bones(side: str, *, is_leg: bool) -> str:
    a, b, c = limb_chain(is_leg=is_leg)
    return f'["{a}_fk.{side}", "{b}_fk.{side}", "{c}_fk.{side}"]'


def limb_descriptor(side: str, *, is_leg: bool) -> dict[str, str]:
    """Arguments shared by the generated rig's IK/FK snap and pole operators for one limb"""
    a, b, c = limb_chain(is_leg=is_leg)
    extra = f'["foot_heel_ik.{side}", "foot_spin_ik.{side}"]' if is_leg else "[]"
    ik_mch = f'["{a}_ik.{side}", "MCH-{b}_ik.{side}", "MCH-{a}_ik_target.{side}"]'
    ik_ctrl = (
        (
            f'["{a}_ik.{side}", "{a}_ik_target.{side}", "{c}_ik.{side}", '
            f'"foot_heel_ik.{side}", "foot_spin_ik.{side}"]'
        )
        if is_leg
        else (f'["{a}_ik.{side}", "{a}_ik_target.{side}", "{c}_ik.{side}"]')
    )
    return {
        "prop_bone": f"{a}_parent.{side}",
        "fk_bones": limb_fk_bones(side, is_leg=is_leg),
        "ik_bones": ik_mch,
        "ctrl_bones": ik_ctrl,
        "tail_bones": "[]",
        "extra_ctrls": extra,
    }


def limb_selection(side: str, *, is_leg: bool) -> frozenset[str]:
    """Bone names whose selection exposes the limb's IK/FK block"""
    extras = (
        {f"foot_heel_ik.{side}", f"foot_spin_ik.{side}", f"toe.{side}"}
        if is_leg
        else set()
    )
    names = set(extras)
    for bone in limb_chain(is_leg=is_leg):
        for suffix in ("_fk", "_ik", "_tweak", ""):
            names.add(f"{bone}{suffix}.{side}")
        names.add(f"{bone}_parent.{side}")
        names.add(f"{bone}_ik_target.{side}")
    return frozenset(names)
