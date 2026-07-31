from bpy.types import UIList


class CP77_UL_AnimEventList(UIList):

    """Draws one row per animation event."""

    bl_idname = "CP77_UL_anim_event_list"


    def draw_item(self, context, layout, data, item, icon, active_data, active_property, index):

        if self.layout_type in {'DEFAULT', 'COMPACT'}:

            row = layout.row(align=True)

            row.prop(item, "event_type", text="", emboss=False)

            row.prop(item, "event_name", text="", emboss=False)

            row.label(text=f"@{item.start_frame}")

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
