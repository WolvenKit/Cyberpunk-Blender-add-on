import bpy

from ...blender.animation_context import active_armature


class CP77_UL_AnimList(bpy.types.UIList):

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            obj = active_armature(context)
            if obj is None or not obj.animation_data:
                return

            active_action = obj.animation_data.action
            selected = item == active_action

            _hints = item.get("optimizationHints", None)
            _is_simd = False
            if _hints is not None:
                try:
                    _is_simd = bool(_hints.get("preferSIMD", False)) if hasattr(_hints, 'get') else bool(
                            _hints["preferSIMD"]
                            )
                except (KeyError, TypeError):
                    pass
            _simd_icon = 'FORCE_MAGNETIC' if _is_simd else 'FORCE_CHARGE'

            row = layout.row(align=True)

            if selected and context.screen.is_animation_playing:
                op = row.operator('screen.animation_cancel', icon='PAUSE', text="", emboss=False)
                op.restore_frame = False
            else:
                icon = 'PLAY' if selected else 'TRIA_RIGHT'
                op = row.operator('cp77.set_animset', icon=icon, text="", emboss=False)
                op.name = item.name
                op.play = True

            op = row.operator('cp77.set_animset', text=item.name, emboss=False)
            op.name = item.name
            op.play = False

            if selected and active_action and active_action.use_frame_range:
                row.prop(active_action, 'use_cyclic', icon='CON_FOLLOWPATH', text="", emboss=False)

            row.operator('cp77.toggle_simd', icon=_simd_icon, text="", emboss=False).name = item.name

            row.operator('cp77.delete_anims', icon='X', text="", emboss=False).name = item.name

    def filter_items(self, context, data, propname):
        actions = getattr(data, propname)
        helper_funcs = bpy.types.UI_UL_list

        flt_flags = []
        flt_neworder = []

        if self.filter_name:
            flt_flags = helper_funcs.filter_items_by_name(
                    self.filter_name,
                    self.bitflag_filter_item,
                    actions,
                    "name",
                    reverse=False
                    )

        if not flt_flags:
            flt_flags = [self.bitflag_filter_item] * len(actions)

        if self.use_filter_sort_alpha:
            flt_neworder = helper_funcs.sort_items_by_name(actions, "name")

        return flt_flags, flt_neworder
