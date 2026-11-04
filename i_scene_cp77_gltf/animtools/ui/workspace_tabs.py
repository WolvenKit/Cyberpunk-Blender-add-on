import bpy

from ...blender.animation_context import active_action, active_armature
from ...blender.workspace import is_animation_workspace
from ...collisiontools.ui.dangles import draw_dangles
from . import facial as facial_ui
from . import rig_setup as rig_setup_ui
from .additive import draw_additive
from .animation import (
    draw_clip_list,
    draw_clip_tools,
    draw_playback_settings,
    draw_rigify_bakes,
)
from .events import CP77_PT_AnimEventsPanel
from .root_motion import draw_root_motion


class _WorkspaceTab:
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_options = {"HIDE_HEADER"}

    @classmethod
    def poll(cls, context):
        return is_animation_workspace(context)


def _armature(layout, context):
    armature = active_armature(context)
    if armature is None:
        layout.label(text="Select an armature", icon="ARMATURE_DATA")
    return armature


class CP77_PT_AnimClips(_WorkspaceTab, bpy.types.Panel):
    bl_idname = "CP77_PT_anim_clips"
    bl_label = "Clips"
    bl_category = "Clips"

    def draw(self, context):
        layout = self.layout
        if _armature(layout, context) is None:
            return
        draw_clip_list(layout, context.scene.cp77_additive_preview)
        action = active_action(context)
        col = layout.column(align=True)
        draw_playback_settings(col, context, action)
        col.separator()
        draw_clip_tools(col)
        if action is not None:
            CP77_PT_AnimEventsPanel.draw_events(layout.box(), action)


class CP77_PT_AnimAdditive(_WorkspaceTab, bpy.types.Panel):
    bl_idname = "CP77_PT_anim_additive"
    bl_label = "Additive"
    bl_category = "Additive"

    def draw(self, context):
        if _armature(self.layout, context) is not None:
            draw_additive(context, self.layout)


class CP77_PT_AnimRootMotion(_WorkspaceTab, bpy.types.Panel):
    bl_idname = "CP77_PT_anim_root_motion"
    bl_label = "Root Motion"
    bl_category = "Root Motion"

    def draw(self, context):
        armature = _armature(self.layout, context)
        if armature is not None:
            draw_root_motion(self.layout, context, armature)


class CP77_PT_AnimRig(_WorkspaceTab, bpy.types.Panel):
    bl_idname = "CP77_PT_anim_rig"
    bl_label = "Rig"
    bl_category = "Rig"

    def draw(self, context):
        armature = active_armature(context)
        rig_setup_ui.draw(context, self.layout, armature)
        if armature is not None:
            draw_rigify_bakes(self.layout.column(align=True), armature)


class CP77_PT_AnimFace(_WorkspaceTab, bpy.types.Panel):
    bl_idname = "CP77_PT_anim_face"
    bl_label = "Face"
    bl_category = "Face"

    def draw(self, context):
        facial_ui.draw(context, self.layout, active_armature(context))


class CP77_PT_AnimDangles(_WorkspaceTab, bpy.types.Panel):
    bl_idname = "CP77_PT_anim_dangles"
    bl_label = "Dangles"
    bl_category = "Dangles"

    def draw(self, context):
        draw_dangles(self.layout, context, context.scene.physx)


WORKSPACE_TAB_CLASSES = (
    CP77_PT_AnimClips,
    CP77_PT_AnimAdditive,
    CP77_PT_AnimRootMotion,
    CP77_PT_AnimRig,
    CP77_PT_AnimFace,
    CP77_PT_AnimDangles,
)
