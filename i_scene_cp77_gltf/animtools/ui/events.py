from bpy.types import Panel

from ...blender.animation_context import active_action


class CP77_PT_AnimEventsPanel(Panel):

    bl_idname = "CP77_PT_anim_events"

    bl_label = "CP77 Animation Events"

    bl_category = "CP77 Modding"

    bl_space_type = 'DOPESHEET_EDITOR'

    bl_region_type = 'UI'

    bl_options = {'DEFAULT_CLOSED'}


    @classmethod

    def poll(cls, context):

        return active_action(context) is not None


    def draw(self, context):

        layout = self.layout

        action = active_action(context)

        events = action.cp77_anim_events

        idx = action.cp77_anim_events_index


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


        row = layout.row(align=True)

        row.operator("cp77.anim_event_sync_markers", icon='MARKER_HLT', text="Sync Markers")

        row.operator("cp77.anim_event_from_markers", icon='MARKER', text="From Markers")

        row.operator("cp77.anim_event_goto", icon='PLAY', text="Go To")


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
