from __future__ import annotations

from bpy.props import (
    BoolProperty,
    BoolVectorProperty,
    CollectionProperty,
    EnumProperty,
    FloatProperty,
    FloatVectorProperty,
    IntProperty,
    StringProperty,
)
from bpy.types import PropertyGroup

from ...animation.domain.clip.root_motion import MOTION_EXPORT_ITEMS
from ...animation.model.events.schema import (
    ATTACH_METHOD_ITEMS,
    EVENT_TYPE_ITEMS,
    FOOT_PHASE_ITEMS,
    GENDER_ALT_ITEMS,
    LEG_ITEMS,
    SIDE_ITEMS,
    WORKSPOT_ACTION_TYPE_ITEMS,
)
from ...blender.animation_context import active_armature
from ...core.log import get_logger, log_once
from ...icons.cp77_icons import get_icon
from ..runtime import read_models
from ..services import additive, events

_LOG = get_logger(__name__)
_CALLBACK_ERRORS = (
    AttributeError,
    KeyError,
    ReferenceError,
    RuntimeError,
    TypeError,
    ValueError,
)


def _notify(label: str, function, *args, **kwargs) -> None:
    """Run a property update hook, logging any failure"""
    try:
        function(*args, **kwargs)
    except _CALLBACK_ERRORS as error:
        _LOG.error("%s failed: %s", label, error, exc_info=True)


def _event_changed(self, context):
    if context is not None:
        _notify("Animation event marker sync", events.event_changed, context)


def _reconfigure(self, context):
    if context is not None:
        _notify("Additive preview reconfigure", additive.reconfigure, context)


def _refresh(self, context):
    if context is not None:
        _notify("Additive preview refresh", additive.refresh, context)


def _primary_mask_changed(self, context):
    if context is not None:
        _notify("Additive mask update", additive.mask_changed, context, secondary=False)


def _secondary_mask_changed(self, context):
    if context is not None:
        _notify("Additive mask update", additive.mask_changed, context, secondary=True)


def _storage_mode_changed(self, context):
    if context is not None:
        _notify("Additive storage update", additive.storage_changed, context)


def _mixer_enabled_changed(self, context):
    if context is not None:
        _notify(
            "Additive mixer toggle",
            additive.set_enabled,
            context,
            bool(self.mixer_enabled),
        )


def _mask_items(self, context):
    if context is None:
        return read_models.additive_mask_items(None)
    try:
        armature = active_armature(context)
    except (AttributeError, ReferenceError, RuntimeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_mask_items", type(error).__name__),
            "mask items: fell back after %s",
            error,
            exc_info=True,
        )
        armature = None
    return read_models.additive_mask_items(armature)


def _secondary_action_items(self, context):
    return read_models.additive_action_items()


class CP77_AnimEventSwitchItem(PropertyGroup):
    name: StringProperty(name="Switch Name", default="")
    value: StringProperty(name="Switch Value", default="")
    source_json: StringProperty(default="", options={"HIDDEN"})


class CP77_AnimEventParamItem(PropertyGroup):
    name: StringProperty(name="Param Name", default="")
    value: FloatProperty(name="Param Value", default=0.0)
    enter_curve_type: StringProperty(name="Enter Curve Type", default="Linear")
    enter_curve_time: FloatProperty(name="Enter Curve Time", default=1.0)
    exit_curve_type: StringProperty(name="Exit Curve Type", default="Linear")
    exit_curve_time: FloatProperty(name="Exit Curve Time", default=1.0)
    source_json: StringProperty(default="", options={"HIDDEN"})


class CP77_WorkspotActionItem(PropertyGroup):
    action_type: EnumProperty(
        name="Action Type",
        items=WORKSPOT_ACTION_TYPE_ITEMS,
        default="EquipItemToSlot",
        description="Workspot action subtype",
    )
    # EquipItemToSlot / UnequipItem: item TweakDBID
    item: StringProperty(
        name="Item", default="", description="TweakDBID as numeric string"
    )
    # EquipItemToSlot / EquipPropToSlot / UnequipFromSlot: slot TweakDBID
    item_slot: StringProperty(
        name="Item Slot", default="", description="TweakDBID as numeric string"
    )
    # EquipPropToSlot / UnequipProp: item id CName
    item_id: StringProperty(
        name="Item ID", default="", description="CName of prop item"
    )
    # EquipPropToSlot: attach method
    attach_method: EnumProperty(
        name="Attach Method",
        items=ATTACH_METHOD_ITEMS,
        default="BonePosition",
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
    weapon_type: StringProperty(
        name="Weapon Type", default="Any", description="workWeaponType enum value"
    )
    keep_equipped_after_exit: BoolProperty(
        name="Keep Equipped After Exit", default=False
    )
    fallback_item: StringProperty(
        name="Fallback Item", default="", description="TweakDBID as numeric string"
    )
    fallback_slot: StringProperty(
        name="Fallback Slot", default="", description="TweakDBID as numeric string"
    )
    source_json: StringProperty(default="", options={"HIDDEN"})
    source_action_type: StringProperty(default="", options={"HIDDEN"})


class CP77_AnimEventItem(PropertyGroup):
    event_type: EnumProperty(
        name="Type",
        items=EVENT_TYPE_ITEMS,
        default="Simple",
        description="Event type (maps to animAnimEvent subclass)",
        update=_event_changed,
    )
    event_name: StringProperty(
        name="Event Name",
        default="",
        description="CName of the event (e.g. w_gun_hmg_militech_handle_push)",
        update=_event_changed,
    )
    start_frame: IntProperty(
        name="Start Frame",
        default=0,
        min=0,
        description="Frame at which the event fires",
        update=_event_changed,
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
        items=GENDER_ALT_ITEMS,
        default="None",
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
        items=LEG_ITEMS,
        default="Left",
        description="Which leg for IK",
    )

    foot_phase: EnumProperty(
        name="Foot Phase",
        items=FOOT_PHASE_ITEMS,
        default="RightUp",
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
        items=SIDE_ITEMS,
        default="Left",
        description="Which side for foot plant",
    )
    custom_event: StringProperty(
        name="Custom Event",
        default="",
        description="Custom event CName for foot plant",
    )

    workspot_actions: CollectionProperty(type=CP77_WorkspotActionItem)
    workspot_actions_index: IntProperty(default=0)
    source_json: StringProperty(default="", options={"HIDDEN"})
    source_event_type: StringProperty(default="", options={"HIDDEN"})


class CP77_RigPartItem(PropertyGroup):
    source_path: StringProperty(
        name="Imported Rig Source", subtype="FILE_PATH", options={"HIDDEN"}
    )
    path: StringProperty(name="Active Rig Path", subtype="FILE_PATH")
    label: StringProperty(name="Rig Part")
    role: StringProperty(name="Role")
    user_addition: BoolProperty(default=False, options={"HIDDEN"})


class CP77_RigAssemblyState(PropertyGroup):
    armature_name: StringProperty(options={"HIDDEN"})
    source_signature: StringProperty(options={"HIDDEN"})
    parts: CollectionProperty(type=CP77_RigPartItem)
    active_index: IntProperty(name="Rig Part", default=0, min=0)


def get_preview_parts(self, context):
    """Generates the UI configuration for previewable facial pose categories"""
    return [
        ("face", "Face", "Face poses", get_icon("FACE"), 0),
        ("eyes", "Eyes", "Eye poses", get_icon("EYES"), 1),
        ("tongue", "Tongue", "Tongue poses", get_icon("TONGUE"), 2),
    ]


class CP77_FacialProps(PropertyGroup):
    """Stores configuration and runtime states for the facial animation tools"""

    facial_json: StringProperty(
        name="FacialSetup JSON",
        subtype="FILE_PATH",
        description="Path to *_facialsetup.json file",
    )

    preview_weight: FloatProperty(
        name="Weight",
        default=1.0,
        min=0.0,
        max=2.0,
        description="Pose weight for preview",
    )

    preview_part: EnumProperty(
        name="Part",
        description="Which set of main poses to browse",
        items=get_preview_parts,
    )

    preview_pose_index: IntProperty(
        name="Pose Index",
        description="Index into the selected part's main pose list",
        default=0,
        min=0,
        max=255,
    )

    solver_active: BoolProperty(
        name="Face",
        description="Solve facial tracks during playback",
        default=False,
    )


class RootMotionData(PropertyGroup):
    root: StringProperty(
        name="Root", description="Export root; leave empty for the action's source root"
    )
    source: StringProperty(
        name="Source",
        description="Bone used to extract travel; leave empty for Trajectory",
    )
    step: IntProperty(
        name="Sample Step",
        description="Frame spacing; existing key times are retained",
        default=1,
        min=1,
        max=10,
    )
    translation_axes: BoolVectorProperty(
        name="Translation",
        description="Motion channels in game model space",
        size=3,
        default=(True, True, False),
        subtype="XYZ",
    )
    rotation_mode: EnumProperty(
        name="Rotation",
        items=(
            ("NONE", "None", "Translation only"),
            ("YAW", "Yaw", "Turn around game Z"),
            ("FULL", "Full", "Yaw, pitch and roll"),
        ),
        default="YAW",
    )
    export_type: EnumProperty(name="Format", items=MOTION_EXPORT_ITEMS, default="AUTO")
    preserve_pose: BoolProperty(
        name="Keep Pose",
        description="Compensate root children to keep their sampled positions and orientations",
        default=False,
    )
    travel_scale: FloatVectorProperty(
        name="Travel Scale",
        description="Scale travel from the first frame along game X, Y and Z",
        size=3,
        default=(1, 1, 1),
        soft_min=0,
        soft_max=3,
    )
    direction: FloatProperty(
        name="Travel Direction",
        description="Rotate the travel path around game Z",
        default=0,
        subtype="ANGLE",
    )
    turn_scale: FloatProperty(
        name="Turn Scale",
        description="Scale accumulated yaw from the first frame",
        default=1,
        soft_min=-2,
        soft_max=3,
    )
    displacement: FloatVectorProperty(
        name="Travel",
        description="Total displacement in game metres along X, Y and Z",
        size=3,
        default=(0, 1, 0),
        subtype="XYZ",
    )
    turn: FloatProperty(
        name="Turn", description="Total yaw over the action", default=0, subtype="ANGLE"
    )
    smooth_radius: FloatProperty(
        name="Radius (frames)",
        description="Smooth selected channels while keeping both endpoints",
        default=3,
        min=0.1,
        soft_max=15,
    )
    report: StringProperty(name="Last Check", options={"SKIP_SAVE"})
    report_action: StringProperty(options={"SKIP_SAVE"})


class CP77_AdditivePreviewSettings(PropertyGroup):
    """Action list selection and additive mixer preview settings of the Animation Tools panel"""

    action_index: IntProperty(
        name="Active Action Index", default=0, update=_reconfigure
    )

    additive_index: IntProperty(
        name="Active Additive Action Index", default=0, update=_reconfigure
    )

    secondary_index: IntProperty(
        name="Active Secondary Additive Action Index", default=0, update=_reconfigure
    )

    clip_index: IntProperty(
        name="Active Clip Index",
        default=0,
    )

    mixer_enabled: BoolProperty(
        name="Mix",
        description="Blend additive actions",
        default=False,
        update=_mixer_enabled_changed,
    )

    storage_mode: EnumProperty(
        name="Storage",
        description="Additive bone storage",
        items=(
            ("REFERENCE_APPLIED", "WKit", "Reference-applied bones"),
            ("DELTA", "Delta", "Bone deltas"),
        ),
        default="REFERENCE_APPLIED",
        update=_storage_mode_changed,
    )

    weight: FloatProperty(
        name="Weight",
        description="Blend weight",
        default=1.0,
        min=0.0,
        max=1.0,
        subtype="FACTOR",
        update=_refresh,
    )

    mask: EnumProperty(
        name="Mask",
        description="Rig part mask",
        items=_mask_items,
        update=_primary_mask_changed,
    )

    time_scale: FloatProperty(
        name="Speed",
        default=1.0,
        min=-8.0,
        max=8.0,
        soft_min=0.0,
        soft_max=2.0,
        update=_refresh,
    )

    time_offset: FloatProperty(
        name="Offset", default=0.0, min=-3600.0, max=3600.0, update=_refresh
    )

    loop: BoolProperty(name="Loop", default=False, update=_refresh)

    secondary_enabled: BoolProperty(
        name="Second Additive", default=False, update=_reconfigure
    )

    secondary_action: EnumProperty(name="Action", items=_secondary_action_items)

    secondary_weight: FloatProperty(
        name="Weight", default=1.0, min=0.0, max=1.0, subtype="FACTOR", update=_refresh
    )

    secondary_mask: EnumProperty(
        name="Mask",
        description="Rig part mask",
        items=_mask_items,
        update=_secondary_mask_changed,
    )

    secondary_time_scale: FloatProperty(
        name="Speed 2",
        default=1.0,
        min=-8.0,
        max=8.0,
        soft_min=0.0,
        soft_max=2.0,
        update=_refresh,
    )

    secondary_time_offset: FloatProperty(
        name="Offset 2", default=0.0, min=-3600.0, max=3600.0, update=_refresh
    )

    secondary_loop: BoolProperty(name="Loop 2", default=False, update=_refresh)


PROPERTY_CLASSES = (
    CP77_AnimEventSwitchItem,
    CP77_AnimEventParamItem,
    CP77_WorkspotActionItem,
    CP77_AnimEventItem,
    CP77_RigPartItem,
    CP77_RigAssemblyState,
    CP77_FacialProps,
    RootMotionData,
    CP77_AdditivePreviewSettings,
)
