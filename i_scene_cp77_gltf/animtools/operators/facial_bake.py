import bpy
from bpy.types import Operator

from ...blender.animation_context import active_armature
from ..model import FacialBakeRequest
from ..services.facial import operations


def _finish(operator, result):
    if result.message:
        operator.report({result.level}, result.message)
    return result.blender_status


class CP77_OT_BakeFacialAnimation(Operator):
    bl_idname = "cp77.bake_facial_animation"
    bl_label = "Bake Facial Animation"
    bl_options = {"REGISTER", "UNDO"}

    frame_start: bpy.props.IntProperty(name="Start Frame", default=1, min=0)
    frame_end: bpy.props.IntProperty(name="End Frame", default=250, min=0)
    keyframe_step: bpy.props.IntProperty(name="Step", default=1, min=1, max=10)

    @classmethod
    def poll(cls, context):
        return active_armature(context) is not None

    def execute(self, context):
        request = FacialBakeRequest(
            frame_start=int(self.frame_start),
            frame_end=int(self.frame_end),
            keyframe_step=max(1, int(self.keyframe_step)),
        )
        return _finish(self, operations.bake(context, request))

    def invoke(self, context, event):
        self.frame_start = context.scene.frame_start
        self.frame_end = context.scene.frame_end
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "frame_start")
        layout.prop(self, "frame_end")
        layout.prop(self, "keyframe_step")


class CP77_OT_ClearFacialAnimation(Operator):
    bl_idname = "cp77.clear_facial_animation"
    bl_label = "Clear Facial Animation"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        armature = active_armature(context)
        return bool(armature and armature.animation_data and armature.animation_data.action)

    def execute(self, context):
        return _finish(self, operations.clear_animation(context))

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)
