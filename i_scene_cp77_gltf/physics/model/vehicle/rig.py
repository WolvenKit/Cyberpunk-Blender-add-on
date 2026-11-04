from __future__ import annotations

SWINGARM_BONE_KEYWORD = "swingarm"
BRAKE_BONE_KEYWORDS = ("break", "brake")
STEERING_WHEEL_BONE_ALIASES = ("steering_wheel_turn",)

# Steering input (-1 full left, +1 full right) to steering-wheel rotation about the column, in degrees; the
# CurveFloatValue of base\vehicles\common\gameplay\default_car_anim_graph.animgraph.
STEERING_WHEEL_TURN_DEGREES = (
    (-1.0, -65.0),
    (-0.7, -30.0),
    (-0.5, -15.0),
    (0.0, 0.0),
    (0.5, 15.0),
    (0.7, 30.0),
    (1.0, 65.0),
)
