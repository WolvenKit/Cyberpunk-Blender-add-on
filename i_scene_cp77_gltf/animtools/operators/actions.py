from bpy.props import BoolProperty, StringProperty
from bpy.types import Operator

from ...blender.animation_context import active_armature
from ..services import actions, pose


def _finish(operator, result):
    if result.message:
        operator.report({result.level}, result.message)
    return result.blender_status


class CP77_OT_ToggleSIMD(Operator):
    bl_idname = "cp77.toggle_simd"
    bl_label = "Toggle SIMD Encoding"
    bl_options = {"REGISTER", "UNDO"}

    name: StringProperty(options={"HIDDEN"})

    def execute(self, context):
        return _finish(self, actions.toggle_simd(self.name))


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
        return _finish(self, actions.delete_action(self.name))


class CP77Animset(Operator):
    bl_idname = "cp77.set_animset"
    bl_label = "Animsets"
    bl_options = {"INTERNAL", "UNDO"}

    name: StringProperty(options={"HIDDEN"})
    new_name: StringProperty(name="New name", default="")
    play: BoolProperty(options={"HIDDEN"}, default=False)

    @classmethod
    def poll(cls, context):
        return active_armature(context) is not None

    def execute(self, context):
        return _finish(
            self,
            actions.set_action(
                context,
                self.name,
                new_name=self.new_name,
                play=self.play,
            ),
        )

    def invoke(self, context, event):
        if event.ctrl:
            self.new_name = self.name
            return context.window_manager.invoke_props_dialog(self)
        self.new_name = ""
        return self.execute(context)


class CP77Keyframe(Operator):
    bl_idname = "insert_keyframe.cp77"
    bl_parent_id = "CP77_PT_animspanel"
    bl_label = "Keyframe Pose"

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        props = context.scene.cp77_panel_props
        return _finish(
            self,
            pose.insert_pose_keyframes(
                context,
                frame_all=bool(props.frameall),
                step=max(1, int(getattr(context.scene, "cp77_keyframe_step", 1))),
            ),
        )

    def draw(self, context):
        layout = self.layout
        props = context.scene.cp77_panel_props
        row = layout.row(align=True)
        row.label(text="Insert a keyframe for every bone at each sampled frame")
        row = layout.row(align=True)
        row.prop(props, "frameall", text="")


class CP77ResetArmature(Operator):
    bl_idname = "reset_armature.cp77"
    bl_parent_id = "CP77_PT_animspanel"
    bl_label = "Reset Armature Position"

    def execute(self, context):
        return _finish(self, actions.reset_armature(context))


class CP77NewAction(Operator):
    bl_idname = "cp77.new_action"
    bl_label = "Add Action"
    bl_options = {"INTERNAL", "UNDO"}

    name: StringProperty(default="New action")

    @classmethod
    def poll(cls, context):
        return active_armature(context) is not None

    def execute(self, context):
        return _finish(self, actions.new_action(context, self.name))

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)


class CP77AnimNamer(Operator):
    bl_idname = "cp77.anim_namer"
    bl_label = "Fix Action Names"
    bl_options = {"INTERNAL", "UNDO"}

    def execute(self, context):
        return _finish(self, actions.normalize_action_names())
