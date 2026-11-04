EVENT_TYPE_ITEMS = (
    ("Sound", "Sound", "Wwise sound event (animAnimEvent_Sound)"),
    (
        "SoundFromEmitter",
        "SoundFromEmitter",
        "Sound from named emitter (animAnimEvent_SoundFromEmitter)",
    ),
    ("Effect", "Effect", "VFX trigger (animAnimEvent_Effect)"),
    (
        "EffectDuration",
        "EffectDuration",
        "VFX trigger with duration (animAnimEvent_EffectDuration)",
    ),
    ("Simple", "Simple", "Simple event — no extra fields (animAnimEvent_Simple)"),
    ("Phase", "Phase", "Phase event (animAnimEvent_Phase)"),
    ("KeyPose", "KeyPose", "Key pose marker (animAnimEvent_KeyPose)"),
    ("ForceRagdoll", "ForceRagdoll", "Force ragdoll (animAnimEvent_ForceRagdoll)"),
    ("ItemEffect", "ItemEffect", "Item effect (animAnimEvent_ItemEffect)"),
    (
        "ItemEffectDuration",
        "ItemEffectDuration",
        "Item effect with duration (animAnimEvent_ItemEffectDuration)",
    ),
    ("FootIK", "FootIK", "Foot IK event (animAnimEvent_FootIK)"),
    ("FootPlant", "FootPlant", "Foot plant event (animAnimEvent_FootPlant)"),
    ("FootPhase", "FootPhase", "Foot phase event (animAnimEvent_FootPhase)"),
    ("FoleyAction", "FoleyAction", "Foley action (animAnimEvent_FoleyAction)"),
    ("GameplayVo", "GameplayVo", "Gameplay VO (animAnimEvent_GameplayVo)"),
    ("Slide", "Slide", "Slide event (animAnimEvent_Slide)"),
    ("SafeCut", "SafeCut", "Safe cut event (animAnimEvent_SafeCut)"),
    (
        "SimpleDuration",
        "SimpleDuration",
        "Simple event with duration (animAnimEvent_SimpleDuration)",
    ),
    (
        "TrajectoryAdjustment",
        "TrajectoryAdjustment",
        "Trajectory adjustment (animAnimEvent_TrajectoryAdjustment)",
    ),
    (
        "WorkspotFastExitCutoff",
        "WorkspotFastExitCutoff",
        "Workspot fast exit cutoff (animAnimEvent_WorkspotFastExitCutoff)",
    ),
    ("Valued", "Valued", "Valued event (animAnimEvent_Valued)"),
    ("SceneItem", "SceneItem", "Scene item event (animAnimEvent_SceneItem)"),
    (
        "WorkspotItem",
        "WorkspotItem",
        "Workspot item event (animAnimEvent_WorkspotItem)",
    ),
    (
        "WorkspotPlayFacialAnim",
        "WorkspotPlayFacialAnim",
        "Workspot facial anim (animAnimEvent_WorkspotPlayFacialAnim)",
    ),
)

GENDER_ALT_ITEMS = (
    ("None", "None", "No gender alt"),
    ("Female", "Female", "Female alternative"),
    ("Male", "Male", "Male alternative"),
)

LEG_ITEMS = (
    ("Left", "Left", "Left leg"),
    ("Right", "Right", "Right leg"),
)

SIDE_ITEMS = (
    ("Left", "Left", "Left side"),
    ("Right", "Right", "Right side"),
)

FOOT_PHASE_ITEMS = (
    ("RightUp", "Right Up", "Right foot up"),
    ("RightForward", "Right Forward", "Right foot forward"),
    ("LeftUp", "Left Up", "Left foot up"),
    ("LeftForward", "Left Forward", "Left foot forward"),
    ("NotConsidered", "Not Considered", "Phase not considered"),
)

WORKSPOT_ACTION_TYPE_ITEMS = (
    ("EquipItemToSlot", "Equip Item To Slot", "Equip an item to a specific slot"),
    ("EquipPropToSlot", "Equip Prop To Slot", "Equip a prop with attachment options"),
    ("EquipInventoryWeapon", "Equip Inventory Weapon", "Equip a weapon from inventory"),
    ("UnequipFromSlot", "Unequip From Slot", "Unequip from a slot"),
    ("UnequipProp", "Unequip Prop", "Unequip a prop"),
    ("UnequipItem", "Unequip Item", "Unequip an item"),
)

ATTACH_METHOD_ITEMS = (
    ("BonePosition", "Bone Position", "Attach at bone position"),
    ("RelativePosition", "Relative Position", "Attach at relative position"),
    ("Custom", "Custom", "Custom offset"),
)


EVENT_TYPES = frozenset(item[0] for item in EVENT_TYPE_ITEMS)
GENDER_ALTS = frozenset(item[0] for item in GENDER_ALT_ITEMS)
LEGS = frozenset(item[0] for item in LEG_ITEMS)
SIDES = frozenset(item[0] for item in SIDE_ITEMS)
FOOT_PHASES = frozenset(item[0] for item in FOOT_PHASE_ITEMS)
WORKSPOT_ACTION_TYPES = frozenset(item[0] for item in WORKSPOT_ACTION_TYPE_ITEMS)
ATTACH_METHODS = frozenset(item[0] for item in ATTACH_METHOD_ITEMS)
