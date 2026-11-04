from bpy.props import BoolProperty, IntProperty, StringProperty
from bpy.types import Operator

from ...blender.animation_context import active_armature
from ...blender.operator_results import execute_operation
from ..model.additive import ActionListSlot
from ..services import actions, additive, pose


class CP77_OT_ToggleSIMD(Operator):
    bl_idname = "cp77.toggle_simd"
    bl_label = "Toggle SIMD Encoding"
    bl_options = {"REGISTER", "UNDO"}

    name: StringProperty(options={"HIDDEN"})

    def execute(self, context):
        return execute_operation(self, "SIMD toggle", actions.toggle_simd, self.name)


class CP77_OT_CycleAdditiveType(Operator):
    bl_idname = "cp77.cycle_additive_type"
    bl_label = "Additive Type"
    bl_description = "Cycle additive type"
    bl_options = {"REGISTER", "UNDO"}

    name: StringProperty(options={"HIDDEN"})

    def execute(self, context):
        return execute_operation(
            self,
            "Additive type change",
            actions.cycle_additive_type,
            context,
            self.name,
        )


class CP77AnimsDelete(Operator):
    bl_idname = "cp77.delete_anims"
    bl_label = "Delete action"
    bl_options = {"INTERNAL", "UNDO"}
    bl_description = "Delete this action"

    name: StringProperty()

    @classmethod
    def poll(cls, context):
        obj = active_armature(context)
        return obj is not None and obj.animation_data is not None

    def execute(self, context):
        return execute_operation(
            self, "Action delete", actions.delete_action, context, self.name
        )


class CP77Animset(Operator):
    bl_idname = "cp77.set_animset"
    bl_label = "Animsets"
    bl_options = {"INTERNAL", "UNDO"}

    name: StringProperty(options={"HIDDEN"})
    new_name: StringProperty(name="New name", default="")
    play: BoolProperty(options={"HIDDEN"}, default=False)
    additive_slot: IntProperty(options={"HIDDEN"}, default=0, min=0, max=2)

    @classmethod
    def poll(cls, context):
        return active_armature(context) is not None

    def execute(self, context):
        return execute_operation(
            self,
            "Action selection",
            actions.set_action,
            context,
            self.name,
            new_name=self.new_name,
            play=self.play,
            slot=ActionListSlot(int(self.additive_slot)),
        )

    def invoke(self, context, event):
        if event.ctrl:
            self.new_name = self.name
            return context.window_manager.invoke_props_dialog(self)
        self.new_name = ""
        return self.execute(context)


class CP77Keyframe(Operator):
    bl_idname = "insert_keyframe.cp77"
    bl_label = "Keyframe Pose"
    bl_options = {"REGISTER", "UNDO"}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        return execute_operation(
            self,
            "Pose keyframing",
            pose.insert_pose_keyframes,
            context,
            frame_all=bool(context.scene.cp77_panel_props.frameall),
        )

    def draw(self, context):
        layout = self.layout
        props = context.scene.cp77_panel_props
        row = layout.row(align=True)
        row.label(text="Key every bone on each frame")
        row = layout.row(align=True)
        row.prop(props, "frameall", text="")


class CP77ResetArmature(Operator):
    bl_idname = "reset_armature.cp77"
    bl_label = "Reset Armature Position"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        return execute_operation(
            self, "Armature reset", actions.reset_armature, context
        )


class CP77NewAction(Operator):
    bl_idname = "cp77.new_action"
    bl_label = "Add Action"
    bl_options = {"INTERNAL", "UNDO"}

    name: StringProperty(default="New action")
    additive: BoolProperty(options={"HIDDEN"}, default=False)

    @classmethod
    def poll(cls, context):
        return active_armature(context) is not None

    def execute(self, context):
        return execute_operation(
            self,
            "New action",
            actions.new_action,
            context,
            self.name,
            additive=bool(self.additive),
        )

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)


class CP77AnimNamer(Operator):
    bl_idname = "cp77.anim_namer"
    bl_label = "Fix Action Names"
    bl_options = {"INTERNAL", "UNDO"}

    def execute(self, context):
        return execute_operation(
            self, "Action name fix", actions.normalize_action_names
        )


class CP77_OT_PreviewAdditiveAction(Operator):
    bl_idname = "cp77.preview_additive_action"
    bl_label = "Preview Additive Action"
    bl_options = {"INTERNAL"}

    name: StringProperty(options={"HIDDEN"})
    play: BoolProperty(options={"HIDDEN"}, default=True)

    @classmethod
    def poll(cls, context):
        return active_armature(context) is not None

    def execute(self, context):
        return execute_operation(
            self,
            "Additive preview",
            additive.start,
            context,
            self.name,
            play=bool(self.play),
        )


class CP77_OT_StopAdditivePreview(Operator):
    bl_idname = "cp77.stop_additive_preview"
    bl_label = "Stop Additive Preview"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        return execute_operation(self, "Additive preview stop", additive.stop, context)


ACTION_OPERATOR_CLASSES = (
    CP77_OT_ToggleSIMD,
    CP77_OT_CycleAdditiveType,
    CP77AnimsDelete,
    CP77Animset,
    CP77_OT_PreviewAdditiveAction,
    CP77_OT_StopAdditivePreview,
    CP77Keyframe,
    CP77ResetArmature,
    CP77NewAction,
    CP77AnimNamer,
)
