from bpy.types import Operator

from ...blender.animation_context import active_armature
from ...blender.operator_results import execute_operation
from ..services import overlay


class BHLS_OT_Start(Operator):
    bl_idname = "view3d.bhls_start"
    bl_label = "Start Bone Lines"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        return active_armature(context) is not None

    def execute(self, context):
        return execute_operation(self, "Bone lines", overlay.start, context)


class BHLS_OT_Stop(Operator):
    bl_idname = "view3d.bhls_stop"
    bl_label = "Stop Bone Lines"
    bl_options = {"REGISTER"}

    def execute(self, context):
        return execute_operation(self, "Bone lines", overlay.stop)


OVERLAY_OPERATOR_CLASSES = (BHLS_OT_Start, BHLS_OT_Stop)
