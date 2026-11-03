from bpy.props import StringProperty
from bpy.types import Panel

from ...addon_identity import get_addon_preferences
from ...blender.animation_context import active_armature
from . import facial as facial_ui
from . import animation as animation_ui
from . import rig_setup as rig_setup_ui


class CP77_PT_AnimsPanel(Panel):
    bl_idname = "CP77_PT_animspanel"
    bl_label = "Animation Tools"
    bl_category = "CP77 Modding"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_options = {"DEFAULT_CLOSED"}

    name: StringProperty(options={"HIDDEN"})

    @classmethod
    def poll(cls, context):
        preferences = get_addon_preferences(context, required=False)
        if preferences is None:
            return False
        return active_armature(context) is not None if preferences.context_only else True

    def draw(self, context):
        layout = self.layout
        preferences = get_addon_preferences(context, required=False)
        if preferences is None or not preferences.show_animtools:
            return

        props = context.scene.cp77_panel_props
        obj = active_armature(context)

        row = layout.row(align=True)
        row.prop(props, "animtab", expand=True)

        layout.separator()

        if props.animtab == 'RIGSETUP':
            rig_setup_ui.draw(context, layout, obj)

        elif props.animtab == 'ANIMATION':
            animation_ui.draw(context, layout, obj)

        elif props.animtab == 'FACIAL':
            facial_ui.draw(context, layout, obj)
