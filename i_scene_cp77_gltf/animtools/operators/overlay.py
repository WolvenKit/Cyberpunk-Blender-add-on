from bpy.types import Operator

from ...blender.animation_context import active_armature
from ..services import overlay


class BHLS_OT_Start(Operator):
    bl_idname = "view3d.bhls_start"
    bl_label = "Start Bone Lines"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        return active_armature(context) is not None

    def execute(self, context):
        if overlay.is_running():
            self.report({"INFO"}, "Already running")
            return {"CANCELLED"}
        armature = active_armature(context)
        overlay.start(armature)
        self.report({"INFO"}, f"Drawing lines for: {armature.name}")
        if context.area is not None:
            context.area.tag_redraw()
        return {"FINISHED"}


class BHLS_OT_Stop(Operator):
    bl_idname = "view3d.bhls_stop"
    bl_label = "Stop Bone Lines"
    bl_options = {"REGISTER"}

    def execute(self, context):
        overlay.stop()
        self.report({"INFO"}, "Bone Lines stopped")
        if context.area is not None:
            context.area.tag_redraw()
        return {"FINISHED"}
