<<<<<<< Updated upstream
from bpy.props import BoolProperty, StringProperty
from bpy.types import Operator

from ...blender.animation_context import active_armature
from ..services import actions, pose


def _finish(operator, result):
    if result.message:
        operator.report({result.level}, result.message)
    return result.blender_status
=======
from bpy.props import BoolProperty, IntProperty, StringProperty
from bpy.types import Operator

from ...blender.animation_context import active_armature
from ...blender.operator_results import execute_operation
from ..model.additive import ActionListSlot
from ..services import actions, additive, pose
>>>>>>> Stashed changes


class CP77_OT_ToggleSIMD(Operator):
    bl_idname = "cp77.toggle_simd"
    bl_label = "Toggle SIMD Encoding"
    bl_options = {"REGISTER", "UNDO"}

    name: StringProperty(options={"HIDDEN"})

    def execute(self, context):
<<<<<<< Updated upstream
        return _finish(self, actions.toggle_simd(self.name))
=======
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
>>>>>>> Stashed changes


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
<<<<<<< Updated upstream
        return _finish(self, actions.delete_action(self.name))
=======
        return execute_operation(
            self, "Action delete", actions.delete_action, context, self.name
        )
>>>>>>> Stashed changes


class CP77Animset(Operator):
    bl_idname = "cp77.set_animset"
    bl_label = "Animsets"
    bl_options = {"INTERNAL", "UNDO"}

    name: StringProperty(options={"HIDDEN"})
    new_name: StringProperty(name="New name", default="")
    play: BoolProperty(options={"HIDDEN"}, default=False)
<<<<<<< Updated upstream
=======
    additive_slot: IntProperty(options={"HIDDEN"}, default=0, min=0, max=2)
>>>>>>> Stashed changes

    @classmethod
    def poll(cls, context):
        return active_armature(context) is not None

    def execute(self, context):
<<<<<<< Updated upstream
        return _finish(
            self,
            actions.set_action(
                context,
                self.name,
                new_name=self.new_name,
                play=self.play,
            ),
=======
        return execute_operation(
            self,
            "Action selection",
            actions.set_action,
            context,
            self.name,
            new_name=self.new_name,
            play=self.play,
            slot=ActionListSlot(int(self.additive_slot)),
>>>>>>> Stashed changes
        )

    def invoke(self, context, event):
        if event.ctrl:
            self.new_name = self.name
            return context.window_manager.invoke_props_dialog(self)
        self.new_name = ""
        return self.execute(context)


class CP77Keyframe(Operator):
    bl_idname = "insert_keyframe.cp77"
<<<<<<< Updated upstream
    bl_parent_id = "CP77_PT_animspanel"
    bl_label = "Keyframe Pose"
=======
    bl_label = "Keyframe Pose"
    bl_options = {"REGISTER", "UNDO"}
>>>>>>> Stashed changes

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
<<<<<<< Updated upstream
        props = context.scene.cp77_panel_props
        return _finish(
            self,
            pose.insert_pose_keyframes(
                context,
                frame_all=bool(props.frameall),
                step=max(1, int(getattr(context.scene, "cp77_keyframe_step", 1))),
            ),
=======
        return execute_operation(
            self,
            "Pose keyframing",
            pose.insert_pose_keyframes,
            context,
            frame_all=bool(context.scene.cp77_panel_props.frameall),
>>>>>>> Stashed changes
        )

    def draw(self, context):
        layout = self.layout
        props = context.scene.cp77_panel_props
        row = layout.row(align=True)
<<<<<<< Updated upstream
        row.label(text="Insert a keyframe for every bone at each sampled frame")
=======
        row.label(text="Key every bone on each frame")
>>>>>>> Stashed changes
        row = layout.row(align=True)
        row.prop(props, "frameall", text="")


class CP77ResetArmature(Operator):
    bl_idname = "reset_armature.cp77"
<<<<<<< Updated upstream
    bl_parent_id = "CP77_PT_animspanel"
    bl_label = "Reset Armature Position"

    def execute(self, context):
        return _finish(self, actions.reset_armature(context))
=======
    bl_label = "Reset Armature Position"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        return execute_operation(
            self, "Armature reset", actions.reset_armature, context
        )
>>>>>>> Stashed changes


class CP77NewAction(Operator):
    bl_idname = "cp77.new_action"
    bl_label = "Add Action"
    bl_options = {"INTERNAL", "UNDO"}

    name: StringProperty(default="New action")
<<<<<<< Updated upstream
=======
    additive: BoolProperty(options={"HIDDEN"}, default=False)
>>>>>>> Stashed changes

    @classmethod
    def poll(cls, context):
        return active_armature(context) is not None

    def execute(self, context):
<<<<<<< Updated upstream
        return _finish(self, actions.new_action(context, self.name))
=======
        return execute_operation(
            self,
            "New action",
            actions.new_action,
            context,
            self.name,
            additive=bool(self.additive),
        )
>>>>>>> Stashed changes

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)


class CP77AnimNamer(Operator):
    bl_idname = "cp77.anim_namer"
    bl_label = "Fix Action Names"
    bl_options = {"INTERNAL", "UNDO"}

    def execute(self, context):
<<<<<<< Updated upstream
        return _finish(self, actions.normalize_action_names())
=======
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
>>>>>>> Stashed changes
