from bpy.props import IntProperty
from bpy.types import Operator

from ...blender.animation_context import active_armature
from ..services.facial import operations, preview, session


def _finish(operator, result):
    if result.message:
        operator.report({result.level}, result.message)
    return result.blender_status


class CP77_OT_ApplyMainPose(Operator):
    bl_idname = "cp77.apply_main_pose"
    bl_label = "Apply Pose"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return active_armature(context) is not None

    def execute(self, context):
        props = context.scene.cp77_facial
        part = getattr(props, "preview_part", "face")
        pose_index = int(getattr(props, "preview_pose_index", getattr(props, "main_pose", 0)))
        return _finish(self, operations.apply_main_pose(context, part, pose_index))


class CP77_OT_BrowsePose(Operator):
    bl_idname = "cp77.browse_pose"
    bl_label = "Browse Poses"
    bl_options = {"REGISTER", "UNDO"}

    direction: IntProperty(name="Direction", default=1, min=-1, max=1)

    @classmethod
    def poll(cls, context):
        armature = active_armature(context)
        return bool(armature and session.get_session(armature) is not None)

    def execute(self, context):
        props = context.scene.cp77_facial
        part = getattr(props, "preview_part", "face")
        current = int(getattr(props, "preview_pose_index", getattr(props, "main_pose", 0)))
        result = operations.browse_pose(context, part, current, self.direction)
        if result.ok:
            index = int(result.details["pose_index"])
            if hasattr(props, "preview_pose_index"):
                props.preview_pose_index = index
            if hasattr(props, "main_pose"):
                props.main_pose = index
        return _finish(self, result)


class CP77_OT_ClearPosePreview(Operator):
    bl_idname = "cp77.clear_pose_preview"
    bl_label = "Clear Preview"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        armature = active_armature(context)
        return bool(armature and preview.has_preview(session.get_session(armature)))

    def execute(self, context):
        return _finish(self, operations.clear_preview(context))
