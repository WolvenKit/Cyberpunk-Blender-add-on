"""
Animation Events — PropertyGroup, UIList, Panel, Operators & Serialization Bridge

Provides a full Blender UI for viewing and editing Cyberpunk 2077 animation events
(animAnimEvent and subclasses) as part of the .anims → .glb → Blender → .glb → .anims
round-trip.

Events are stored in two parallel representations:
  1. action.cp77_anim_events  (CollectionProperty)  — the UI-editable, typed data
  2. action["animEvents"]     (IDProperty)           — the glTF-exportable JSON blob

On import:  IDProperty → CollectionProperty  (load_events_to_collection)
On export:  CollectionProperty → IDProperty  (save_events_to_idproperty)

Pose markers on the Action Editor timeline are synced one-way from the event list
for visualization only; the authoritative data is always the CollectionProperty.
"""

import bpy
from bpy.props import (
    StringProperty, IntProperty, BoolProperty, FloatProperty,
    CollectionProperty, EnumProperty,
)
from bpy.types import PropertyGroup, UIList, Panel, Operator


# ─────────────────────────────────────────────────────────────
# Event type enum — maps to animAnimEvent subclasses
# ─────────────────────────────────────────────────────────────
EVENT_TYPES = [
    ('Sound',             'Sound',             'Wwise sound event (animAnimEvent_Sound)'),
    ('SoundFromEmitter',  'SoundFromEmitter',  'Sound from named emitter (animAnimEvent_SoundFromEmitter)'),
    ('Effect',            'Effect',            'VFX trigger (animAnimEvent_Effect)'),
    ('EffectDuration',    'EffectDuration',    'VFX trigger with duration (animAnimEvent_EffectDuration)'),
    ('Simple',            'Simple',            'Simple event — no extra fields (animAnimEvent_Simple)'),
    ('Phase',             'Phase',             'Phase event (animAnimEvent_Phase)'),
    ('KeyPose',           'KeyPose',           'Key pose marker (animAnimEvent_KeyPose)'),
    ('ForceRagdoll',      'ForceRagdoll',      'Force ragdoll (animAnimEvent_ForceRagdoll)'),
    ('ItemEffect',        'ItemEffect',        'Item effect (animAnimEvent_ItemEffect)'),
    ('ItemEffectDuration','ItemEffectDuration', 'Item effect with duration (animAnimEvent_ItemEffectDuration)'),
    ('FootIK',            'FootIK',            'Foot IK event (animAnimEvent_FootIK)'),
    ('FootPlant',         'FootPlant',         'Foot plant event (animAnimEvent_FootPlant)'),
    ('FootPhase',         'FootPhase',         'Foot phase event (animAnimEvent_FootPhase)'),
    ('FoleyAction',       'FoleyAction',       'Foley action (animAnimEvent_FoleyAction)'),
    ('GameplayVo',        'GameplayVo',        'Gameplay VO (animAnimEvent_GameplayVo)'),
    ('Slide',             'Slide',             'Slide event (animAnimEvent_Slide)'),
    ('SafeCut',           'SafeCut',           'Safe cut event (animAnimEvent_SafeCut)'),
    ('SimpleDuration',    'SimpleDuration',    'Simple event with duration (animAnimEvent_SimpleDuration)'),
    ('TrajectoryAdjustment', 'TrajectoryAdjustment', 'Trajectory adjustment (animAnimEvent_TrajectoryAdjustment)'),
    ('WorkspotFastExitCutoff', 'WorkspotFastExitCutoff', 'Workspot fast exit cutoff (animAnimEvent_WorkspotFastExitCutoff)'),
    ('Valued',            'Valued',            'Valued event (animAnimEvent_Valued)'),
    ('SceneItem',         'SceneItem',         'Scene item event (animAnimEvent_SceneItem)'),
    ('WorkspotItem',      'WorkspotItem',      'Workspot item event (animAnimEvent_WorkspotItem)'),
    ('WorkspotPlayFacialAnim', 'WorkspotPlayFacialAnim', 'Workspot facial anim (animAnimEvent_WorkspotPlayFacialAnim)'),
]

GENDER_ALT_ENUM = [
    ('None',    'None',    'No gender alt'),
    ('Female',  'Female',  'Female alternative'),
    ('Male',    'Male',    'Male alternative'),
]

LEG_ENUM = [
    ('Left',  'Left',  'Left leg'),
    ('Right', 'Right', 'Right leg'),
]

SIDE_ENUM = [
    ('Left',  'Left',  'Left side'),
    ('Right', 'Right', 'Right side'),
]

FOOT_PHASE_ENUM = [
    ('RightUp',       'Right Up',       'Right foot up'),
    ('RightForward',  'Right Forward',  'Right foot forward'),
    ('LeftUp',        'Left Up',        'Left foot up'),
    ('LeftForward',   'Left Forward',   'Left foot forward'),
    ('NotConsidered', 'Not Considered', 'Phase not considered'),
]


# ─────────────────────────────────────────────────────────────
# Marker auto-sync
# ─────────────────────────────────────────────────────────────

def sync_markers_from_events(action):
    """Rebuild all pose markers from the event list."""
    if action is None:
        return

    # Clear existing pose markers (bpy_prop_collection has no .clear())
    while len(action.pose_markers) > 0:
        action.pose_markers.remove(action.pose_markers[0])

    events = getattr(action, 'cp77_anim_events', None)
    if events is None:
        return

    for evt in events:
        marker = action.pose_markers.new(evt.event_name or evt.event_type)
        marker.frame = evt.start_frame


def on_event_update(self, context):
    """Auto-sync markers when an event property changes in the panel."""
    # Walk up to the action
    action = _get_active_action(context)
    if action is not None:
        sync_markers_from_events(action)


def _get_active_action(context):
    """Get the currently active action from context."""
    obj = context.active_object
    if obj and obj.animation_data and obj.animation_data.action:
        return obj.animation_data.action
    return None


# ─────────────────────────────────────────────────────────────
# PropertyGroups
# ─────────────────────────────────────────────────────────────

class CP77_AnimEventSwitchItem(PropertyGroup):
    """A single Wwise switch entry (name -> value)."""
    name: StringProperty(name="Switch Name", default="")
    value: StringProperty(name="Switch Value", default="")


class CP77_AnimEventParamItem(PropertyGroup):
    """A single Wwise parameter entry with curve data."""
    name: StringProperty(name="Param Name", default="")
    value: FloatProperty(name="Param Value", default=0.0)
    enter_curve_type: StringProperty(name="Enter Curve Type", default="Linear")
    enter_curve_time: FloatProperty(name="Enter Curve Time", default=1.0)
    exit_curve_type: StringProperty(name="Exit Curve Type", default="Linear")
    exit_curve_time: FloatProperty(name="Exit Curve Time", default=1.0)


WORKSPOT_ACTION_TYPES = [
    ('EquipItemToSlot',       'Equip Item To Slot',       'Equip an item to a specific slot'),
    ('EquipPropToSlot',       'Equip Prop To Slot',       'Equip a prop with attachment options'),
    ('EquipInventoryWeapon',  'Equip Inventory Weapon',   'Equip a weapon from inventory'),
    ('UnequipFromSlot',       'Unequip From Slot',        'Unequip from a slot'),
    ('UnequipProp',           'Unequip Prop',             'Unequip a prop'),
    ('UnequipItem',           'Unequip Item',             'Unequip an item'),
]

ATTACH_METHOD_ENUM = [
    ('BonePosition',     'Bone Position',     'Attach at bone position'),
    ('RelativePosition', 'Relative Position', 'Attach at relative position'),
    ('Custom',           'Custom',            'Custom offset'),
]


class CP77_WorkspotActionItem(PropertyGroup):
    """One workspot item action — polymorphic, flattened with type discriminator."""
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


class CP77_AnimEventItem(PropertyGroup):
    """One animation event — maps to animAnimEvent and subclasses."""

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

    # ── Sound fields ──
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

    # ── SoundFromEmitter fields ──
    emitter_name: StringProperty(
        name="Emitter Name",
        default="",
        description="Named emitter for sound playback",
    )

    # ── Effect / EffectDuration / ItemEffect / ItemEffectDuration fields ──
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

    # ── Valued field ──
    event_value: FloatProperty(
        name="Value",
        default=0.0,
        description="Numeric value for Valued events",
    )

    # ── FoleyAction field ──
    action_name: StringProperty(
        name="Action Name",
        default="",
        description="Foley action CName",
    )

    # ── SceneItem field ──
    bone_name: StringProperty(
        name="Bone Name",
        default="",
        description="Target bone CName for scene item",
    )

    # ── WorkspotPlayFacialAnim field ──
    facial_anim_name: StringProperty(
        name="Facial Anim Name",
        default="",
        description="Facial animation CName",
    )

    # ── FootIK field ──
    leg: EnumProperty(
        name="Leg",
        items=LEG_ENUM,
        default='Left',
        description="Which leg for IK",
    )

    # ── FootPhase field ──
    foot_phase: EnumProperty(
        name="Foot Phase",
        items=FOOT_PHASE_ENUM,
        default='RightUp',
        description="Foot phase state",
    )

    # ── GameplayVo fields ──
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

    # ── FootPlant fields ──
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

    # ── WorkspotItem fields ──
    workspot_actions: CollectionProperty(type=CP77_WorkspotActionItem)
    workspot_actions_index: IntProperty(default=0)


# ─────────────────────────────────────────────────────────────
# UIList
# ─────────────────────────────────────────────────────────────

class CP77_UL_AnimEventList(UIList):
    """Draws one row per animation event."""
    bl_idname = "CP77_UL_anim_event_list"

    def draw_item(self, context, layout, data, item, icon, active_data, active_property, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)
            row.prop(item, "event_type", text="", emboss=False)
            row.prop(item, "event_name", text="", emboss=False)
            row.label(text=f"@{item.start_frame}")
        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text=item.event_name or item.event_type)


class CP77_UL_SwitchList(UIList):
    """Draws one row per Wwise switch."""
    bl_idname = "CP77_UL_switch_list"

    def draw_item(self, context, layout, data, item, icon, active_data, active_property, index):
        row = layout.row(align=True)
        row.prop(item, "name", text="", emboss=False)
        row.prop(item, "value", text="", emboss=False)


class CP77_UL_ParamList(UIList):
    """Draws one row per Wwise parameter."""
    bl_idname = "CP77_UL_param_list"

    def draw_item(self, context, layout, data, item, icon, active_data, active_property, index):
        row = layout.row(align=True)
        row.prop(item, "name", text="", emboss=False)
        row.prop(item, "value", text="", emboss=False)


class CP77_UL_WorkspotActionList(UIList):
    """Draws one row per workspot action."""
    bl_idname = "CP77_UL_workspot_action_list"

    def draw_item(self, context, layout, data, item, icon, active_data, active_property, index):
        row = layout.row(align=True)
        row.prop(item, "action_type", text="", emboss=False)
        # Show the most relevant identifier per type
        if item.action_type in ('EquipItemToSlot', 'UnequipItem'):
            row.label(text=item.item or "(no item)")
        elif item.action_type in ('EquipPropToSlot', 'UnequipProp'):
            row.label(text=item.item_id or "(no id)")
        elif item.action_type == 'UnequipFromSlot':
            row.label(text=item.item_slot or "(no slot)")
        elif item.action_type == 'EquipInventoryWeapon':
            row.label(text=item.weapon_type or "Any")


# ─────────────────────────────────────────────────────────────
# Panel in Dope Sheet Sidebar
# ─────────────────────────────────────────────────────────────

class CP77_PT_AnimEventsPanel(Panel):
    bl_idname = "CP77_PT_anim_events"
    bl_label = "CP77 Animation Events"
    bl_category = "CP77 Modding"
    bl_space_type = 'DOPESHEET_EDITOR'
    bl_region_type = 'UI'
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj and obj.animation_data and obj.animation_data.action)

    def draw(self, context):
        layout = self.layout
        action = context.active_object.animation_data.action
        events = action.cp77_anim_events
        idx = action.cp77_anim_events_index

        # ── Event list ──
        row = layout.row()
        row.template_list(
            "CP77_UL_anim_event_list", "",
            action, "cp77_anim_events",
            action, "cp77_anim_events_index",
            rows=4,
        )

        col = row.column(align=True)
        col.operator("cp77.anim_event_add", icon='ADD', text="")
        col.operator("cp77.anim_event_remove", icon='REMOVE', text="")
        col.separator()
        col.operator("cp77.anim_event_move", icon='TRIA_UP', text="").direction = 'UP'
        col.operator("cp77.anim_event_move", icon='TRIA_DOWN', text="").direction = 'DOWN'

        # ── Utility buttons ──
        row = layout.row(align=True)
        row.operator("cp77.anim_event_sync_markers", icon='MARKER_HLT', text="Sync Markers")
        row.operator("cp77.anim_event_from_markers", icon='MARKER', text="From Markers")
        row.operator("cp77.anim_event_goto", icon='PLAY', text="Go To")

        # ── Detail panel for selected event ──
        if 0 <= idx < len(events):
            evt = events[idx]
            box = layout.box()
            box.prop(evt, "event_type")
            box.prop(evt, "event_name")
            box.prop(evt, "start_frame")
            box.prop(evt, "duration_in_frames")

            # Type-specific fields
            if evt.event_type == 'Sound':
                self._draw_sound_fields(box, evt)
            elif evt.event_type == 'SoundFromEmitter':
                box.prop(evt, "emitter_name")
            elif evt.event_type in ('Effect', 'ItemEffect'):
                box.prop(evt, "effect_name")
            elif evt.event_type in ('EffectDuration', 'ItemEffectDuration'):
                box.prop(evt, "effect_name")
                box.prop(evt, "sequence_shift")
                box.prop(evt, "break_all_loops_on_stop")
            elif evt.event_type == 'Valued':
                box.prop(evt, "event_value")
            elif evt.event_type == 'FoleyAction':
                box.prop(evt, "action_name")
            elif evt.event_type == 'SceneItem':
                box.prop(evt, "bone_name")
            elif evt.event_type == 'WorkspotPlayFacialAnim':
                box.prop(evt, "facial_anim_name")
            elif evt.event_type == 'FootIK':
                box.prop(evt, "leg")
            elif evt.event_type == 'FootPhase':
                box.prop(evt, "foot_phase")
            elif evt.event_type == 'GameplayVo':
                box.prop(evt, "vo_context")
                box.prop(evt, "is_quest")
            elif evt.event_type == 'FootPlant':
                box.prop(evt, "side")
                box.prop(evt, "custom_event")
            elif evt.event_type == 'WorkspotItem':
                self._draw_workspot_item_fields(box, evt)

    def _draw_workspot_item_fields(self, box, evt):
        """Draw WorkspotItem action list and per-action detail panel."""
        sub = box.box()
        sub.label(text="Workspot Actions:")
        row = sub.row()
        row.template_list(
            "CP77_UL_workspot_action_list", "",
            evt, "workspot_actions",
            evt, "workspot_actions_index",
            rows=3,
        )
        col = row.column(align=True)
        col.operator("cp77.anim_event_add_workspot_action", icon='ADD', text="")
        col.operator("cp77.anim_event_remove_workspot_action", icon='REMOVE', text="")

        # Detail panel for selected action
        wi = evt.workspot_actions_index
        if 0 <= wi < len(evt.workspot_actions):
            wa = evt.workspot_actions[wi]
            detail = sub.box()
            detail.prop(wa, "action_type")

            at = wa.action_type
            if at == 'EquipItemToSlot':
                detail.prop(wa, "item")
                detail.prop(wa, "item_slot")
            elif at == 'EquipPropToSlot':
                detail.prop(wa, "item_id")
                detail.prop(wa, "item_slot")
                detail.prop(wa, "attach_method")
                if wa.attach_method == 'Custom':
                    col2 = detail.column(align=True)
                    col2.label(text="Offset Position:")
                    col2.prop(wa, "offset_pos_x")
                    col2.prop(wa, "offset_pos_y")
                    col2.prop(wa, "offset_pos_z")
                    col2.label(text="Offset Rotation (IJKR):")
                    col2.prop(wa, "offset_rot_i")
                    col2.prop(wa, "offset_rot_j")
                    col2.prop(wa, "offset_rot_k")
                    col2.prop(wa, "offset_rot_r")
            elif at == 'EquipInventoryWeapon':
                detail.prop(wa, "weapon_type")
                detail.prop(wa, "keep_equipped_after_exit")
                detail.prop(wa, "fallback_item")
                detail.prop(wa, "fallback_slot")
            elif at == 'UnequipFromSlot':
                detail.prop(wa, "item_slot")
            elif at == 'UnequipProp':
                detail.prop(wa, "item_id")
            elif at == 'UnequipItem':
                detail.prop(wa, "item")

    def _draw_sound_fields(self, box, evt):
        """Draw Sound-specific sub-fields."""
        # Switches sub-list
        sub = box.box()
        sub.label(text="Wwise Switches:")
        row = sub.row()
        row.template_list(
            "CP77_UL_switch_list", "",
            evt, "switches",
            evt, "switches_index",
            rows=2,
        )
        col = row.column(align=True)
        col.operator("cp77.anim_event_add_switch", icon='ADD', text="")
        col.operator("cp77.anim_event_remove_switch", icon='REMOVE', text="")

        # Params sub-list
        sub = box.box()
        sub.label(text="Wwise Parameters:")
        row = sub.row()
        row.template_list(
            "CP77_UL_param_list", "",
            evt, "params",
            evt, "params_index",
            rows=2,
        )
        col = row.column(align=True)
        col.operator("cp77.anim_event_add_param", icon='ADD', text="")
        col.operator("cp77.anim_event_remove_param", icon='REMOVE', text="")

        # Selected param detail (curve data)
        if 0 <= evt.params_index < len(evt.params):
            param = evt.params[evt.params_index]
            detail = sub.box()
            detail.label(text=f"Curve Data: {param.name}")
            detail.prop(param, "enter_curve_type")
            detail.prop(param, "enter_curve_time")
            detail.prop(param, "exit_curve_type")
            detail.prop(param, "exit_curve_time")

        # Other sound fields
        box.prop(evt, "dynamic_params")
        box.prop(evt, "metadata_context")
        box.prop(evt, "only_play_on")
        box.prop(evt, "dont_play_on")
        box.prop(evt, "player_gender_alt")


# ─────────────────────────────────────────────────────────────
# Operators
# ─────────────────────────────────────────────────────────────

class CP77_OT_AnimEventAdd(Operator):
    bl_idname = "cp77.anim_event_add"
    bl_label = "Add Animation Event"
    bl_description = "Add a new animation event at the current frame"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        action = _get_active_action(context)
        if action is None:
            self.report({'WARNING'}, "No active action")
            return {'CANCELLED'}
        evt = action.cp77_anim_events.add()
        evt.event_type = 'Simple'
        evt.start_frame = context.scene.frame_current
        action.cp77_anim_events_index = len(action.cp77_anim_events) - 1
        sync_markers_from_events(action)
        return {'FINISHED'}


class CP77_OT_AnimEventRemove(Operator):
    bl_idname = "cp77.anim_event_remove"
    bl_label = "Remove Animation Event"
    bl_description = "Remove the selected animation event"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        action = _get_active_action(context)
        if action is None:
            self.report({'WARNING'}, "No active action")
            return {'CANCELLED'}
        idx = action.cp77_anim_events_index
        if 0 <= idx < len(action.cp77_anim_events):
            action.cp77_anim_events.remove(idx)
            action.cp77_anim_events_index = min(idx, len(action.cp77_anim_events) - 1)
            sync_markers_from_events(action)
        return {'FINISHED'}


class CP77_OT_AnimEventGoto(Operator):
    bl_idname = "cp77.anim_event_goto"
    bl_label = "Go To Event"
    bl_description = "Jump playhead to the selected event's start frame"
    bl_options = {'REGISTER'}

    def execute(self, context):
        action = _get_active_action(context)
        if action is None:
            return {'CANCELLED'}
        idx = action.cp77_anim_events_index
        if 0 <= idx < len(action.cp77_anim_events):
            context.scene.frame_set(action.cp77_anim_events[idx].start_frame)
        return {'FINISHED'}


class CP77_OT_AnimEventMove(Operator):
    bl_idname = "cp77.anim_event_move"
    bl_label = "Move Animation Event"
    bl_description = "Reorder event in the list"
    bl_options = {'REGISTER', 'UNDO'}

    direction: EnumProperty(
        items=[('UP', 'Up', ''), ('DOWN', 'Down', '')],
        default='UP',
    )

    def execute(self, context):
        action = _get_active_action(context)
        if action is None:
            return {'CANCELLED'}
        idx = action.cp77_anim_events_index
        count = len(action.cp77_anim_events)
        if self.direction == 'UP' and idx > 0:
            action.cp77_anim_events.move(idx, idx - 1)
            action.cp77_anim_events_index = idx - 1
        elif self.direction == 'DOWN' and idx < count - 1:
            action.cp77_anim_events.move(idx, idx + 1)
            action.cp77_anim_events_index = idx + 1
        sync_markers_from_events(action)
        return {'FINISHED'}


class CP77_OT_AnimEventSyncMarkers(Operator):
    bl_idname = "cp77.anim_event_sync_markers"
    bl_label = "Sync Markers from Events"
    bl_description = "Overwrite pose markers from the event list"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        action = _get_active_action(context)
        if action is None:
            return {'CANCELLED'}
        sync_markers_from_events(action)
        self.report({'INFO'}, f"Synced {len(action.cp77_anim_events)} markers")
        return {'FINISHED'}


class CP77_OT_AnimEventFromMarkers(Operator):
    bl_idname = "cp77.anim_event_from_markers"
    bl_label = "Events from Markers"
    bl_description = "Create new events from existing pose markers (additive)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        action = _get_active_action(context)
        if action is None:
            return {'CANCELLED'}
        count = 0
        for marker in action.pose_markers:
            evt = action.cp77_anim_events.add()
            evt.event_type = 'Simple'
            evt.event_name = marker.name
            evt.start_frame = marker.frame
            count += 1
        if count > 0:
            action.cp77_anim_events_index = len(action.cp77_anim_events) - 1
        self.report({'INFO'}, f"Created {count} events from markers")
        return {'FINISHED'}


class CP77_OT_AnimEventAddSwitch(Operator):
    bl_idname = "cp77.anim_event_add_switch"
    bl_label = "Add Switch"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        action = _get_active_action(context)
        if action is None:
            return {'CANCELLED'}
        idx = action.cp77_anim_events_index
        if 0 <= idx < len(action.cp77_anim_events):
            evt = action.cp77_anim_events[idx]
            evt.switches.add()
            evt.switches_index = len(evt.switches) - 1
        return {'FINISHED'}


class CP77_OT_AnimEventRemoveSwitch(Operator):
    bl_idname = "cp77.anim_event_remove_switch"
    bl_label = "Remove Switch"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        action = _get_active_action(context)
        if action is None:
            return {'CANCELLED'}
        idx = action.cp77_anim_events_index
        if 0 <= idx < len(action.cp77_anim_events):
            evt = action.cp77_anim_events[idx]
            si = evt.switches_index
            if 0 <= si < len(evt.switches):
                evt.switches.remove(si)
                evt.switches_index = min(si, len(evt.switches) - 1)
        return {'FINISHED'}


class CP77_OT_AnimEventAddParam(Operator):
    bl_idname = "cp77.anim_event_add_param"
    bl_label = "Add Parameter"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        action = _get_active_action(context)
        if action is None:
            return {'CANCELLED'}
        idx = action.cp77_anim_events_index
        if 0 <= idx < len(action.cp77_anim_events):
            evt = action.cp77_anim_events[idx]
            p = evt.params.add()
            p.enter_curve_type = "Linear"
            p.enter_curve_time = 1.0
            p.exit_curve_type = "Linear"
            p.exit_curve_time = 1.0
            evt.params_index = len(evt.params) - 1
        return {'FINISHED'}


class CP77_OT_AnimEventRemoveParam(Operator):
    bl_idname = "cp77.anim_event_remove_param"
    bl_label = "Remove Parameter"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        action = _get_active_action(context)
        if action is None:
            return {'CANCELLED'}
        idx = action.cp77_anim_events_index
        if 0 <= idx < len(action.cp77_anim_events):
            evt = action.cp77_anim_events[idx]
            pi = evt.params_index
            if 0 <= pi < len(evt.params):
                evt.params.remove(pi)
                evt.params_index = min(pi, len(evt.params) - 1)
        return {'FINISHED'}


class CP77_OT_AnimEventAddWorkspotAction(Operator):
    bl_idname = "cp77.anim_event_add_workspot_action"
    bl_label = "Add Workspot Action"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        action = _get_active_action(context)
        if action is None:
            return {'CANCELLED'}
        idx = action.cp77_anim_events_index
        if 0 <= idx < len(action.cp77_anim_events):
            evt = action.cp77_anim_events[idx]
            wa = evt.workspot_actions.add()
            wa.action_type = 'EquipItemToSlot'
            evt.workspot_actions_index = len(evt.workspot_actions) - 1
        return {'FINISHED'}


class CP77_OT_AnimEventRemoveWorkspotAction(Operator):
    bl_idname = "cp77.anim_event_remove_workspot_action"
    bl_label = "Remove Workspot Action"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        action = _get_active_action(context)
        if action is None:
            return {'CANCELLED'}
        idx = action.cp77_anim_events_index
        if 0 <= idx < len(action.cp77_anim_events):
            evt = action.cp77_anim_events[idx]
            wi = evt.workspot_actions_index
            if 0 <= wi < len(evt.workspot_actions):
                evt.workspot_actions.remove(wi)
                evt.workspot_actions_index = min(wi, len(evt.workspot_actions) - 1)
        return {'FINISHED'}


# ─────────────────────────────────────────────────────────────
# Serialization Bridge
# ─────────────────────────────────────────────────────────────

def _get(d, key, default=None):
    """Safe dict-like access for IDPropertyGroup or plain dict."""
    try:
        return d[key]
    except (KeyError, TypeError, IndexError):
        return default


def load_events_to_collection(action):
    """
    Deserialize action['animEvents'] IDProperty → cp77_anim_events CollectionProperty.
    Called after glTF import stores the IDProperty.
    """
    raw = _get(action, "animEvents")
    if raw is None or not hasattr(raw, '__iter__'):
        return

    events = action.cp77_anim_events
    events.clear()

    for raw_evt in raw:
        evt = events.add()
        evt.event_type = _get(raw_evt, "type", "Simple")
        evt.event_name = _get(raw_evt, "eventName", "")
        evt.start_frame = int(_get(raw_evt, "startFrame", 0))
        evt.duration_in_frames = int(_get(raw_evt, "durationInFrames", 0))

        # Sound fields
        raw_switches = _get(raw_evt, "switches")
        if raw_switches:
            if hasattr(raw_switches, 'keys'):
                # Dict format: {name: value}
                for k, v in raw_switches.items():
                    s = evt.switches.add()
                    s.name = str(k)
                    s.value = str(v)
            elif hasattr(raw_switches, '__iter__'):
                # List of dicts format: [{name: ..., value: ...}]
                for sw in raw_switches:
                    s = evt.switches.add()
                    s.name = str(_get(sw, "name", ""))
                    s.value = str(_get(sw, "value", ""))

        # Prefer paramCurves (full fidelity) over params (legacy)
        raw_param_curves = _get(raw_evt, "paramCurves")
        if raw_param_curves and hasattr(raw_param_curves, '__iter__'):
            for pc in raw_param_curves:
                p = evt.params.add()
                p.name = str(_get(pc, "name", ""))
                p.value = float(_get(pc, "value", 0.0))
                p.enter_curve_type = str(_get(pc, "enterCurveType", "Linear"))
                p.enter_curve_time = float(_get(pc, "enterCurveTime", 1.0))
                p.exit_curve_type = str(_get(pc, "exitCurveType", "Linear"))
                p.exit_curve_time = float(_get(pc, "exitCurveTime", 1.0))
        else:
            raw_params = _get(raw_evt, "params")
            if raw_params:
                if hasattr(raw_params, 'keys'):
                    for k, v in raw_params.items():
                        p = evt.params.add()
                        p.name = str(k)
                        p.value = float(v)
                elif hasattr(raw_params, '__iter__'):
                    for pm in raw_params:
                        p = evt.params.add()
                        p.name = str(_get(pm, "name", ""))
                        p.value = float(_get(pm, "value", 0.0))

        raw_dyn = _get(raw_evt, "dynamicParams")
        if raw_dyn and hasattr(raw_dyn, '__iter__'):
            evt.dynamic_params = ",".join(str(d) for d in raw_dyn)

        evt.metadata_context = str(_get(raw_evt, "metadataContext", "") or "")
        evt.only_play_on = str(_get(raw_evt, "onlyPlayOn", "") or "")
        evt.dont_play_on = str(_get(raw_evt, "dontPlayOn", "") or "")

        gender_alt = str(_get(raw_evt, "playerGenderAlt", "None") or "None")
        if gender_alt in ('None', 'Female', 'Male'):
            evt.player_gender_alt = gender_alt
        else:
            evt.player_gender_alt = 'None'

        # SoundFromEmitter
        evt.emitter_name = str(_get(raw_evt, "emitterName", "") or "")

        # Effect fields
        evt.effect_name = str(_get(raw_evt, "effectName", "") or "")
        evt.sequence_shift = int(_get(raw_evt, "sequenceShift", 0) or 0)
        evt.break_all_loops_on_stop = bool(_get(raw_evt, "breakAllLoopsOnStop", False))

        # Valued
        evt.event_value = float(_get(raw_evt, "value", 0.0) or 0.0)

        # FoleyAction
        evt.action_name = str(_get(raw_evt, "actionName", "") or "")

        # SceneItem
        evt.bone_name = str(_get(raw_evt, "boneName", "") or "")

        # WorkspotPlayFacialAnim
        evt.facial_anim_name = str(_get(raw_evt, "facialAnimName", "") or "")

        # FootIK
        leg_val = str(_get(raw_evt, "leg", "Left") or "Left")
        if leg_val in ('Left', 'Right'):
            evt.leg = leg_val
        else:
            evt.leg = 'Left'

        # FootPhase
        fp_val = str(_get(raw_evt, "phase", "RightUp") or "RightUp")
        if fp_val in ('RightUp', 'RightForward', 'LeftUp', 'LeftForward', 'NotConsidered'):
            evt.foot_phase = fp_val
        else:
            evt.foot_phase = 'RightUp'

        # GameplayVo
        evt.vo_context = str(_get(raw_evt, "voContext", "") or "")
        evt.is_quest = bool(_get(raw_evt, "isQuest", False))

        # FootPlant
        side_val = str(_get(raw_evt, "side", "Left") or "Left")
        if side_val in ('Left', 'Right'):
            evt.side = side_val
        else:
            evt.side = 'Left'
        evt.custom_event = str(_get(raw_evt, "customEvent", "") or "")

        # WorkspotItem actions
        raw_ws_actions = _get(raw_evt, "workspotActions")
        if raw_ws_actions and hasattr(raw_ws_actions, '__iter__'):
            for raw_wa in raw_ws_actions:
                wa = evt.workspot_actions.add()
                at = str(_get(raw_wa, "$type", "EquipItemToSlot") or "EquipItemToSlot")
                valid_types = {t[0] for t in WORKSPOT_ACTION_TYPES}
                wa.action_type = at if at in valid_types else 'EquipItemToSlot'
                wa.item = str(_get(raw_wa, "item", "") or "")
                wa.item_slot = str(_get(raw_wa, "itemSlot", "") or "")
                wa.item_id = str(_get(raw_wa, "itemId", "") or "")
                am = str(_get(raw_wa, "attachMethod", "BonePosition") or "BonePosition")
                valid_am = {a[0] for a in ATTACH_METHOD_ENUM}
                wa.attach_method = am if am in valid_am else 'BonePosition'
                wa.offset_pos_x = float(_get(raw_wa, "offsetPosX", 0.0) or 0.0)
                wa.offset_pos_y = float(_get(raw_wa, "offsetPosY", 0.0) or 0.0)
                wa.offset_pos_z = float(_get(raw_wa, "offsetPosZ", 0.0) or 0.0)
                wa.offset_rot_i = float(_get(raw_wa, "offsetRotI", 0.0) or 0.0)
                wa.offset_rot_j = float(_get(raw_wa, "offsetRotJ", 0.0) or 0.0)
                wa.offset_rot_k = float(_get(raw_wa, "offsetRotK", 0.0) or 0.0)
                wa.offset_rot_r = float(_get(raw_wa, "offsetRotR", 1.0) or 1.0)
                wa.weapon_type = str(_get(raw_wa, "weaponType", "Any") or "Any")
                wa.keep_equipped_after_exit = bool(_get(raw_wa, "keepEquippedAfterExit", False))
                wa.fallback_item = str(_get(raw_wa, "fallbackItem", "") or "")
                wa.fallback_slot = str(_get(raw_wa, "fallbackSlot", "") or "")

    action.cp77_anim_events_index = 0 if len(events) > 0 else -1

    # Sync markers for visualization
    sync_markers_from_events(action)


def save_events_to_idproperty(action):
    """
    Serialize cp77_anim_events CollectionProperty → action['animEvents'] IDProperty.
    Called before glTF export so the glTF exporter writes it into extras.
    """
    events = getattr(action, 'cp77_anim_events', None)
    if events is None or len(events) == 0:
        # Remove the key if no events, so it doesn't linger
        if "animEvents" in action:
            del action["animEvents"]
        return

    result = []
    for evt in events:
        entry = {
            "type": evt.event_type,
            "eventName": evt.event_name,
            "startFrame": evt.start_frame,
            "durationInFrames": evt.duration_in_frames,
        }

        if evt.event_type == 'Sound':
            if len(evt.switches) > 0:
                entry["switches"] = {s.name: s.value for s in evt.switches}
            if len(evt.params) > 0:
                entry["params"] = {p.name: p.value for p in evt.params}
                entry["paramCurves"] = [
                    {
                        "name": p.name,
                        "value": p.value,
                        "enterCurveType": p.enter_curve_type,
                        "enterCurveTime": p.enter_curve_time,
                        "exitCurveType": p.exit_curve_type,
                        "exitCurveTime": p.exit_curve_time,
                    }
                    for p in evt.params
                ]
            if evt.dynamic_params.strip():
                entry["dynamicParams"] = [s.strip() for s in evt.dynamic_params.split(",") if s.strip()]
            if evt.metadata_context:
                entry["metadataContext"] = evt.metadata_context
            if evt.only_play_on:
                entry["onlyPlayOn"] = evt.only_play_on
            if evt.dont_play_on:
                entry["dontPlayOn"] = evt.dont_play_on
            if evt.player_gender_alt != 'None':
                entry["playerGenderAlt"] = evt.player_gender_alt

        elif evt.event_type == 'SoundFromEmitter':
            if evt.emitter_name:
                entry["emitterName"] = evt.emitter_name

        elif evt.event_type in ('Effect', 'ItemEffect'):
            if evt.effect_name:
                entry["effectName"] = evt.effect_name

        elif evt.event_type in ('EffectDuration', 'ItemEffectDuration'):
            if evt.effect_name:
                entry["effectName"] = evt.effect_name
            entry["sequenceShift"] = evt.sequence_shift
            entry["breakAllLoopsOnStop"] = evt.break_all_loops_on_stop

        elif evt.event_type == 'Valued':
            entry["value"] = evt.event_value

        elif evt.event_type == 'FoleyAction':
            if evt.action_name:
                entry["actionName"] = evt.action_name

        elif evt.event_type == 'SceneItem':
            if evt.bone_name:
                entry["boneName"] = evt.bone_name

        elif evt.event_type == 'WorkspotPlayFacialAnim':
            if evt.facial_anim_name:
                entry["facialAnimName"] = evt.facial_anim_name

        elif evt.event_type == 'FootIK':
            entry["leg"] = evt.leg

        elif evt.event_type == 'FootPhase':
            entry["phase"] = evt.foot_phase

        elif evt.event_type == 'GameplayVo':
            if evt.vo_context:
                entry["voContext"] = evt.vo_context
            entry["isQuest"] = evt.is_quest

        elif evt.event_type == 'FootPlant':
            entry["side"] = evt.side
            if evt.custom_event:
                entry["customEvent"] = evt.custom_event

        elif evt.event_type == 'WorkspotItem':
            actions_list = []
            for wa in evt.workspot_actions:
                act = {"$type": wa.action_type}
                at = wa.action_type
                if at == 'EquipItemToSlot':
                    act["item"] = wa.item
                    act["itemSlot"] = wa.item_slot
                elif at == 'EquipPropToSlot':
                    act["itemId"] = wa.item_id
                    act["itemSlot"] = wa.item_slot
                    act["attachMethod"] = wa.attach_method
                    act["offsetPosX"] = wa.offset_pos_x
                    act["offsetPosY"] = wa.offset_pos_y
                    act["offsetPosZ"] = wa.offset_pos_z
                    act["offsetRotI"] = wa.offset_rot_i
                    act["offsetRotJ"] = wa.offset_rot_j
                    act["offsetRotK"] = wa.offset_rot_k
                    act["offsetRotR"] = wa.offset_rot_r
                elif at == 'EquipInventoryWeapon':
                    act["weaponType"] = wa.weapon_type
                    act["keepEquippedAfterExit"] = wa.keep_equipped_after_exit
                    act["fallbackItem"] = wa.fallback_item
                    act["fallbackSlot"] = wa.fallback_slot
                elif at == 'UnequipFromSlot':
                    act["itemSlot"] = wa.item_slot
                elif at == 'UnequipProp':
                    act["itemId"] = wa.item_id
                elif at == 'UnequipItem':
                    act["item"] = wa.item
                actions_list.append(act)
            if actions_list:
                entry["workspotActions"] = actions_list

        result.append(entry)

    action["animEvents"] = result


# ─────────────────────────────────────────────────────────────
# Registration
# ─────────────────────────────────────────────────────────────

_classes = [
    CP77_AnimEventSwitchItem,
    CP77_AnimEventParamItem,
    CP77_WorkspotActionItem,
    CP77_AnimEventItem,
    CP77_UL_AnimEventList,
    CP77_UL_SwitchList,
    CP77_UL_ParamList,
    CP77_UL_WorkspotActionList,
    CP77_PT_AnimEventsPanel,
    CP77_OT_AnimEventAdd,
    CP77_OT_AnimEventRemove,
    CP77_OT_AnimEventGoto,
    CP77_OT_AnimEventMove,
    CP77_OT_AnimEventSyncMarkers,
    CP77_OT_AnimEventFromMarkers,
    CP77_OT_AnimEventAddSwitch,
    CP77_OT_AnimEventRemoveSwitch,
    CP77_OT_AnimEventAddParam,
    CP77_OT_AnimEventRemoveParam,
    CP77_OT_AnimEventAddWorkspotAction,
    CP77_OT_AnimEventRemoveWorkspotAction,
]


def register_anim_events():
    for cls in _classes:
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            pass  # Already registered
    bpy.types.Action.cp77_anim_events = CollectionProperty(type=CP77_AnimEventItem)
    bpy.types.Action.cp77_anim_events_index = IntProperty(name="Active Event Index", default=0)


def unregister_anim_events():
    if hasattr(bpy.types.Action, 'cp77_anim_events_index'):
        del bpy.types.Action.cp77_anim_events_index
    if hasattr(bpy.types.Action, 'cp77_anim_events'):
        del bpy.types.Action.cp77_anim_events
    for cls in reversed(_classes):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass  # Not registered
