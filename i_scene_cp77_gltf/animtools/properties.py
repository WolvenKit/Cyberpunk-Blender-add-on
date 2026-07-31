from bpy.props import BoolProperty, CollectionProperty, EnumProperty, FloatProperty, IntProperty, StringProperty
from bpy.types import PropertyGroup

from ..animation.events import sync_markers_from_events
from ..blender.animation_context import active_action

EVENT_TYPES = [
    ('Sound', 'Sound', 'Wwise sound event (animAnimEvent_Sound)'),
    ('SoundFromEmitter', 'SoundFromEmitter', 'Sound from named emitter (animAnimEvent_SoundFromEmitter)'),
    ('Effect', 'Effect', 'VFX trigger (animAnimEvent_Effect)'),
    ('EffectDuration', 'EffectDuration', 'VFX trigger with duration (animAnimEvent_EffectDuration)'),
    ('Simple', 'Simple', 'Simple event — no extra fields (animAnimEvent_Simple)'),
    ('Phase', 'Phase', 'Phase event (animAnimEvent_Phase)'),
    ('KeyPose', 'KeyPose', 'Key pose marker (animAnimEvent_KeyPose)'),
    ('ForceRagdoll', 'ForceRagdoll', 'Force ragdoll (animAnimEvent_ForceRagdoll)'),
    ('ItemEffect', 'ItemEffect', 'Item effect (animAnimEvent_ItemEffect)'),
    ('ItemEffectDuration', 'ItemEffectDuration', 'Item effect with duration (animAnimEvent_ItemEffectDuration)'),
    ('FootIK', 'FootIK', 'Foot IK event (animAnimEvent_FootIK)'),
    ('FootPlant', 'FootPlant', 'Foot plant event (animAnimEvent_FootPlant)'),
    ('FootPhase', 'FootPhase', 'Foot phase event (animAnimEvent_FootPhase)'),
    ('FoleyAction', 'FoleyAction', 'Foley action (animAnimEvent_FoleyAction)'),
    ('GameplayVo', 'GameplayVo', 'Gameplay VO (animAnimEvent_GameplayVo)'),
    ('Slide', 'Slide', 'Slide event (animAnimEvent_Slide)'),
    ('SafeCut', 'SafeCut', 'Safe cut event (animAnimEvent_SafeCut)'),
    ('SimpleDuration', 'SimpleDuration', 'Simple event with duration (animAnimEvent_SimpleDuration)'),
    ('TrajectoryAdjustment', 'TrajectoryAdjustment', 'Trajectory adjustment (animAnimEvent_TrajectoryAdjustment)'),
    ('WorkspotFastExitCutoff', 'WorkspotFastExitCutoff',
     'Workspot fast exit cutoff (animAnimEvent_WorkspotFastExitCutoff)'),
    ('Valued', 'Valued', 'Valued event (animAnimEvent_Valued)'),
    ('SceneItem', 'SceneItem', 'Scene item event (animAnimEvent_SceneItem)'),
    ('WorkspotItem', 'WorkspotItem', 'Workspot item event (animAnimEvent_WorkspotItem)'),
    ('WorkspotPlayFacialAnim', 'WorkspotPlayFacialAnim', 'Workspot facial anim (animAnimEvent_WorkspotPlayFacialAnim)'),
    ]

GENDER_ALT_ENUM = [
    ('None', 'None', 'No gender alt'),
    ('Female', 'Female', 'Female alternative'),
    ('Male', 'Male', 'Male alternative'),
    ]

LEG_ENUM = [
    ('Left', 'Left', 'Left leg'),
    ('Right', 'Right', 'Right leg'),
    ]

SIDE_ENUM = [
    ('Left', 'Left', 'Left side'),
    ('Right', 'Right', 'Right side'),
    ]

FOOT_PHASE_ENUM = [
    ('RightUp', 'Right Up', 'Right foot up'),
    ('RightForward', 'Right Forward', 'Right foot forward'),
    ('LeftUp', 'Left Up', 'Left foot up'),
    ('LeftForward', 'Left Forward', 'Left foot forward'),
    ('NotConsidered', 'Not Considered', 'Phase not considered'),
    ]


def on_event_update(self, context):
    action = active_action(context)
    if action is not None:
        sync_markers_from_events(action)


class CP77_AnimEventSwitchItem(PropertyGroup):
    name: StringProperty(name="Switch Name", default="")
    value: StringProperty(name="Switch Value", default="")
    source_json: StringProperty(default="", options={'HIDDEN'})


class CP77_AnimEventParamItem(PropertyGroup):
    name: StringProperty(name="Param Name", default="")
    value: FloatProperty(name="Param Value", default=0.0)
    enter_curve_type: StringProperty(name="Enter Curve Type", default="Linear")
    enter_curve_time: FloatProperty(name="Enter Curve Time", default=1.0)
    exit_curve_type: StringProperty(name="Exit Curve Type", default="Linear")
    exit_curve_time: FloatProperty(name="Exit Curve Time", default=1.0)
    source_json: StringProperty(default="", options={'HIDDEN'})


WORKSPOT_ACTION_TYPES = [
    ('EquipItemToSlot', 'Equip Item To Slot', 'Equip an item to a specific slot'),
    ('EquipPropToSlot', 'Equip Prop To Slot', 'Equip a prop with attachment options'),
    ('EquipInventoryWeapon', 'Equip Inventory Weapon', 'Equip a weapon from inventory'),
    ('UnequipFromSlot', 'Unequip From Slot', 'Unequip from a slot'),
    ('UnequipProp', 'Unequip Prop', 'Unequip a prop'),
    ('UnequipItem', 'Unequip Item', 'Unequip an item'),
    ]

ATTACH_METHOD_ENUM = [
    ('BonePosition', 'Bone Position', 'Attach at bone position'),
    ('RelativePosition', 'Relative Position', 'Attach at relative position'),
    ('Custom', 'Custom', 'Custom offset'),
    ]


class CP77_WorkspotActionItem(PropertyGroup):
    action_type: EnumProperty(
            name="Action Type",
            items=WORKSPOT_ACTION_TYPES,
            default='EquipItemToSlot',
            description="Workspot action subtype",
            )
    # EquipItemToSlot / UnequipItem: item TweakDBID
    item: StringProperty(name="Item", default="", description="TweakDBID as numeric string")
    # EquipItemToSlot / EquipPropToSlot / UnequipFromSlot: slot TweakDBID
    item_slot: StringProperty(name="Item Slot", default="", description="TweakDBID as numeric string")
    # EquipPropToSlot / UnequipProp: item id CName
    item_id: StringProperty(name="Item ID", default="", description="CName of prop item")
    # EquipPropToSlot: attach method
    attach_method: EnumProperty(
            name="Attach Method", items=ATTACH_METHOD_ENUM, default='BonePosition',
            )
    # EquipPropToSlot: custom offset position
    offset_pos_x: FloatProperty(name="Offset X", default=0.0)
    offset_pos_y: FloatProperty(name="Offset Y", default=0.0)
    offset_pos_z: FloatProperty(name="Offset Z", default=0.0)
    # EquipPropToSlot: custom offset rotation (quaternion IJKR)
    offset_rot_i: FloatProperty(name="Rot I", default=0.0)
    offset_rot_j: FloatProperty(name="Rot J", default=0.0)
    offset_rot_k: FloatProperty(name="Rot K", default=0.0)
    offset_rot_r: FloatProperty(name="Rot R", default=1.0)
    # EquipInventoryWeapon: weapon type
    weapon_type: StringProperty(name="Weapon Type", default="Any", description="workWeaponType enum value")
    keep_equipped_after_exit: BoolProperty(name="Keep Equipped After Exit", default=False)
    fallback_item: StringProperty(name="Fallback Item", default="", description="TweakDBID as numeric string")
    fallback_slot: StringProperty(name="Fallback Slot", default="", description="TweakDBID as numeric string")
    source_json: StringProperty(default="", options={'HIDDEN'})
    source_action_type: StringProperty(default="", options={'HIDDEN'})


class CP77_AnimEventItem(PropertyGroup):
    event_type: EnumProperty(
            name="Type",
            items=EVENT_TYPES,
            default='Simple',
            description="Event type (maps to animAnimEvent subclass)",
            update=on_event_update,
            )
    event_name: StringProperty(
            name="Event Name",
            default="",
            description="CName of the event (e.g. w_gun_hmg_militech_handle_push)",
            update=on_event_update,
            )
    start_frame: IntProperty(
            name="Start Frame",
            default=0,
            min=0,
            description="Frame at which the event fires",
            update=on_event_update,
            )
    duration_in_frames: IntProperty(
            name="Duration",
            default=0,
            min=0,
            description="Duration in frames (0 for instant events)",
            )

    switches: CollectionProperty(type=CP77_AnimEventSwitchItem)
    params: CollectionProperty(type=CP77_AnimEventParamItem)
    dynamic_params: StringProperty(
            name="Dynamic Params",
            default="",
            description="Comma-separated list of dynamic parameter CNames",
            )
    metadata_context: StringProperty(name="Metadata Context", default="")
    only_play_on: StringProperty(name="Only Play On", default="")
    dont_play_on: StringProperty(name="Don't Play On", default="")
    player_gender_alt: EnumProperty(
            name="Gender Alt",
            items=GENDER_ALT_ENUM,
            default='None',
            description="Player gender alternative",
            )

    emitter_name: StringProperty(
            name="Emitter Name",
            default="",
            description="Named emitter for sound playback",
            )

    effect_name: StringProperty(
            name="Effect Name",
            default="",
            description="VFX effect name",
            )
    sequence_shift: IntProperty(
            name="Sequence Shift",
            default=0,
            min=0,
            description="Sequence shift for effect duration events",
            )
    break_all_loops_on_stop: BoolProperty(
            name="Break All Loops On Stop",
            default=False,
            description="Whether to break all loops when the event stops",
            )

    # Sub-list indices for switches/params UILists
    switches_index: IntProperty(default=0)
    params_index: IntProperty(default=0)

    event_value: FloatProperty(
            name="Value",
            default=0.0,
            description="Numeric value for Valued events",
            )

    action_name: StringProperty(
            name="Action Name",
            default="",
            description="Foley action CName",
            )

    bone_name: StringProperty(
            name="Bone Name",
            default="",
            description="Target bone CName for scene item",
            )

    facial_anim_name: StringProperty(
            name="Facial Anim Name",
            default="",
            description="Facial animation CName",
            )

    leg: EnumProperty(
            name="Leg",
            items=LEG_ENUM,
            default='Left',
            description="Which leg for IK",
            )

    foot_phase: EnumProperty(
            name="Foot Phase",
            items=FOOT_PHASE_ENUM,
            default='RightUp',
            description="Foot phase state",
            )

    vo_context: StringProperty(
            name="VO Context",
            default="",
            description="Gameplay VO context CName",
            )
    is_quest: BoolProperty(
            name="Is Quest",
            default=False,
            description="Whether this is a quest VO",
            )

    side: EnumProperty(
            name="Side",
            items=SIDE_ENUM,
            default='Left',
            description="Which side for foot plant",
            )
    custom_event: StringProperty(
            name="Custom Event",
            default="",
            description="Custom event CName for foot plant",
            )

    workspot_actions: CollectionProperty(type=CP77_WorkspotActionItem)
    workspot_actions_index: IntProperty(default=0)
    source_json: StringProperty(default="", options={'HIDDEN'})
    source_event_type: StringProperty(default="", options={'HIDDEN'})
