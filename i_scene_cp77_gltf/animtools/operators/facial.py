import bpy
from bpy.props import IntProperty
from bpy.types import Operator

from ...blender.animation_context import active_armature
from ...blender.facial import session as facial_session
from ...blender.operator_results import execute_operation
from ...core.notifications import import_operation
from ..model.requests import FacialBakeRequest
from ..services import facial


class CP77_OT_LoadFacial(Operator):
    bl_idname = "cp77.load_facial"
    bl_label = "Load Facial Setup"
    bl_options = {"REGISTER", "UNDO"}

    @import_operation
    def execute(self, context):
        return execute_operation(
            self,
            "Facial setup load",
            facial.load,
            context,
            context.scene.cp77_facial.facial_json,
        )


class CP77_OT_UnbindFacial(Operator):
    bl_idname = "cp77_facial.unbind"
    bl_label = "Unbind Facial Setup"
    bl_options = {"REGISTER", "UNDO"}

    keep_properties: bpy.props.BoolProperty(name="Keep Track Properties", default=False)

    @classmethod
    def poll(cls, context):
        armature = active_armature(context)
        return bool(armature and facial_session.is_bound(armature))

    def execute(self, context):
        return execute_operation(
            self,
            "Facial setup unbind",
            facial.unbind,
            context,
            keep_properties=bool(self.keep_properties),
        )


class CP77_OT_RebuildFacialSession(Operator):
    bl_idname = "cp77_facial.rebuild_cache"
    bl_label = "Rebuild Facial Session"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        armature = active_armature(context)
        return bool(armature and facial_session.is_bound(armature))

    def execute(self, context):
        return execute_operation(
            self, "Facial session rebuild", facial.rebuild, context
        )


class CP77_OT_ResetNeutral(Operator):
    bl_idname = "cp77.reset_neutral"
    bl_label = "Reset to Rest"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        return execute_operation(
            self, "Facial rest pose", facial.reset_neutral, context
        )


class CP77_OT_ResetTracksToDefaults(Operator):
    bl_idname = "cp77.reset_tracks_defaults"
    bl_label = "Reset Tracks to Defaults"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return active_armature(context) is not None

    def execute(self, context):
        return execute_operation(
            self, "Facial track reset", facial.reset_tracks, context
        )


class CP77_OT_ApplyMainPose(Operator):
    bl_idname = "cp77.apply_main_pose"
    bl_label = "Apply Pose"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return active_armature(context) is not None

    def execute(self, context):
        props = context.scene.cp77_facial
        return execute_operation(
            self,
            "Facial pose preview",
            facial.apply_main_pose,
            context,
            props.preview_part,
            int(props.preview_pose_index),
        )


class CP77_OT_BrowsePose(Operator):
    bl_idname = "cp77.browse_pose"
    bl_label = "Browse Poses"
    bl_options = {"REGISTER", "UNDO"}

    direction: IntProperty(name="Direction", default=1, min=-1, max=1)

    @classmethod
    def poll(cls, context):
        armature = active_armature(context)
        return bool(armature and facial_session.peek_session(armature) is not None)

    def execute(self, context):
        props = context.scene.cp77_facial

        def browse():
            result = facial.browse_pose(
                context,
                props.preview_part,
                int(props.preview_pose_index),
                self.direction,
            )
            if result.ok:
                props.preview_pose_index = int(result.details["pose_index"])
            return result

        return execute_operation(self, "Facial pose browse", browse)


class CP77_OT_ClearPosePreview(Operator):
    bl_idname = "cp77.clear_pose_preview"
    bl_label = "Clear Preview"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        armature = active_armature(context)
        session = (
            facial_session.peek_session(armature) if armature is not None else None
        )
        return bool(session is not None and session.has_preview)

    def execute(self, context):
        return execute_operation(
            self, "Facial preview clear", facial.clear_preview, context
        )


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
        return execute_operation(self, "Facial bake", facial.bake, context, request)

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
    bl_description = "Remove the facial bones' keys from the rig's Action; other bones and rigs keep theirs"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        armature = active_armature(context)
        return bool(
            armature and armature.animation_data and armature.animation_data.action
        )

    def execute(self, context):
        return execute_operation(
            self, "Facial animation clear", facial.clear_animation, context
        )

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)


class FACIAL_OT_SolveNow(Operator):
    bl_idname = "cp77_facial.solve_now"
    bl_label = "Solve Now"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return any(
            obj.type == "ARMATURE" and facial_session.is_bound(obj)
            for obj in context.scene.objects
        )

    def execute(self, context):
        return execute_operation(self, "Facial solve", facial.solve_now, context.scene)


FACIAL_OPERATOR_CLASSES = (
    CP77_OT_LoadFacial,
    CP77_OT_ApplyMainPose,
    CP77_OT_BrowsePose,
    CP77_OT_ClearPosePreview,
    CP77_OT_UnbindFacial,
    CP77_OT_RebuildFacialSession,
    CP77_OT_ResetNeutral,
    CP77_OT_ResetTracksToDefaults,
    CP77_OT_BakeFacialAnimation,
    CP77_OT_ClearFacialAnimation,
    FACIAL_OT_SolveNow,
)
