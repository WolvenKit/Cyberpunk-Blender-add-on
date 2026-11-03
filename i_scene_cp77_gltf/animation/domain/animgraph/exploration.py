from __future__ import annotations

EXPLORATION_FEATURE = "exploration"
EXPLORATION_INPUTS = ("explorationType", "state", "movementType", "isEvenLoop")

_ENTER, _LOOP, _EXIT = 0, 1, 2
_PHASES = {_ENTER: "startup", _LOOP: "loop", _EXIT: "recover"}
_SPRINT_MOVEMENT = 2  # walk 0, jog 1 (no jog clips, walk is used), sprint 2

# Smart-object type (in enum order) -> (clip family, height, direction, movement-dependent).
_LADDER = "ladder"
_JUMP = "jump"
_CLIMB = "climb"
_VAULT = "vault"
_CHARGED_JUMP = "charged_jump"
_THRUSTER = "thurster"  # the game's clip names keep this spelling
_SMART_OBJECTS = (
    None,  # Default
    (_LADDER, "", "up", True),  # LadderUp
    (_LADDER, "", "down", True),  # LadderDown
    (_JUMP, "", "", True),  # JumpOnSameLevel
    (_JUMP, "high", "", True),  # Jump3mUp
    (_JUMP, "low", "", True),  # Jump3mDown
    (_CLIMB, "110cm", "up", False),  # Climb110cmUp
    (_CLIMB, "110cm", "down", False),  # Climb110cmDown
    (_CLIMB, "200cm", "up", False),  # Climb200cmUp
    (_CLIMB, "200cm", "down", False),  # Climb200cmDown
    (_CLIMB, "300cm", "up", False),  # Climb300cmUp
    (_CLIMB, "300cm", "down", False),  # Climb300cmDown
    (_VAULT, "10cm", "", True),  # Vault10cm
    (_VAULT, "40cm", "", True),  # Vault40cm
    (_VAULT, "100cm", "", True),  # Vault100cm
    (_CHARGED_JUMP, "400cm", "up", False),
    (_CHARGED_JUMP, "400cm", "down", False),
    (_CHARGED_JUMP, "600cm", "up", False),
    (_CHARGED_JUMP, "600cm", "down", False),
    (_CHARGED_JUMP, "800cm", "up", False),
    (_CHARGED_JUMP, "800cm", "down", False),
    None,  # ThrusterJumpUp has no clips
    (_THRUSTER, "", "down", False),  # ThrusterJumpDown
    (_CLIMB, "400cm", "down", False),  # Climb400cmDown
)
_THRUSTER_PHASES = {_ENTER: "start", _LOOP: "idle", _EXIT: "exit"}


def exploration_animation(exploration_type, state, movement_type, is_even_loop) -> str:
    """The clip name for the exploration feature values, or '' when the inputs select none"""
    try:
        entry = _SMART_OBJECTS[int(exploration_type)]
        state = int(state)
    except (IndexError, TypeError, ValueError):
        return ""
    if entry is None or state not in _PHASES:
        return ""
    family, height, direction, by_movement = entry
    movement = "sprint" if int(movement_type or 0) == _SPRINT_MOVEMENT else "walk"
    phase = _PHASES[state]
    if family == _THRUSTER:
        return f"thurster_{_THRUSTER_PHASES[state]}"
    if family == _LADDER:
        # Ladders always enter on the right foot; loops and recoveries alternate feet.
        side = "right" if state == _ENTER or bool(is_even_loop) else "left"
        return f"ladder_{movement}_{direction}_{phase}_{side}"
    if family == _JUMP:
        return "_".join(part for part in ("jump", movement, height, phase) if part)
    if family == _VAULT:
        return f"vault_{height}_{movement}_{phase}"
    return f"{family}_{height}_{direction}_{phase}"


def exploration_inputs(feature_values) -> tuple:
    """The four exploration feature inputs (defaults 0/False), keyed as the node reads them"""
    return tuple(
        feature_values.get(
            (EXPLORATION_FEATURE, name), False if name == "isEvenLoop" else 0
        )
        for name in EXPLORATION_INPUTS
    )
