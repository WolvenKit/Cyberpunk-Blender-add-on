from bpy.props import BoolProperty, EnumProperty, IntProperty, StringProperty
from bpy.types import Operator

from ...animation.rigify.mapping import DIRECTION_FORWARD
from ...blender.animation_context import active_armature
from ..model import RigifyBakeRequest
from ..services.rigify.bake import bake_to_source
from ..services.rigify.operations import (
    activate_linked_rig,
    generate_rigify,
    toggle_constraint_direction,
)
from ..services.rigify.pairing import find_pair, get_constraint_direction


def _finish(operator, result):
    if result.message:
        operator.report({result.level}, result.message)
    return result.blender_status


class CP77ToRigify(Operator):
    bl_idname = "rigify_generator.cp77"
    bl_parent_id = "CP77_PT_animspanel"
    bl_options = {"REGISTER", "UNDO"}
    bl_label = "Generate Rigify"

    def execute(self, context):
        return _finish(self, generate_rigify(context))


class CP77_OT_ToggleConstraintDirection(Operator):
    bl_idname = "cp77.toggle_constraint_direction"
    bl_label = "Toggle Rigify Constraint Direction"
    bl_options = {"REGISTER", "UNDO"}

    source_name: StringProperty(options={"HIDDEN"})
    rigify_name: StringProperty(options={"HIDDEN"})

    def execute(self, context):
        return _finish(
            self,
            toggle_constraint_direction(
                context,
                source_name=self.source_name,
                rigify_name=self.rigify_name,
            ),
        )


class CP77_OT_ActivateLinkedRig(Operator):
    bl_idname = "cp77.activate_linked_rig"
    bl_label = "Activate Linked Rig"
    bl_options = {"REGISTER", "UNDO"}

    target_name: StringProperty(options={"HIDDEN"})

    def execute(self, context):
        return _finish(self, activate_linked_rig(context, self.target_name))


class CP77_OT_BakeRigifyToSource(Operator):
    bl_idname = "cp77.bake_rigify_to_source"
    bl_label = "Bake Rigify to Cyberpunk"
    bl_options = {"REGISTER", "UNDO"}

    action_name: StringProperty(
        name="Action Name",
        description="Name of the new action. Defaults to '<rigify action>_baked'",
        default="",
    )
    overwrite: BoolProperty(
        name="Overwrite Existing",
        description="Replace the target action if it already exists",
        default=False,
    )
    frame_range_source: EnumProperty(
        name="Frame Range",
        items=[
            ("SCENE", "Scene Range", "Use scene.frame_start / scene.frame_end"),
            ("ACTION", "Action Range", "Use the Rigify action's own frame_range"),
            ("MANUAL", "Manual", "Specify start and end frames"),
        ],
        default="SCENE",
    )
    frame_start: IntProperty(name="Start", default=1, min=0)
    frame_end: IntProperty(name="End", default=250, min=0)
    step: IntProperty(name="Step", description="Frame step", default=1, min=1, max=10)

    @classmethod
    def poll(cls, context):
        source, rig = find_pair(active_armature(context))
        return bool(rig and rig.animation_data and rig.animation_data.action)

    def invoke(self, context, event):
        source, rig = find_pair(active_armature(context))
        if rig is None or rig.animation_data is None or rig.animation_data.action is None:
            self.report({"ERROR"}, "Rigify rig has no action to bake")
            return {"CANCELLED"}
        action = rig.animation_data.action
        self.action_name = f"{action.name}_baked"
        self.frame_start, self.frame_end = map(int, action.frame_range)
        if get_constraint_direction(source) != DIRECTION_FORWARD:
            self.report({"WARNING"}, "Switch constraints to FORWARD before baking for meaningful results.")
        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        source, rig = find_pair(active_armature(context))
        if rig is not None and rig.animation_data and rig.animation_data.action:
            col = layout.column(align=True)
            col.enabled = False
            col.label(text=f"From: {rig.name} → {rig.animation_data.action.name}", icon="ARMATURE_DATA")
            col.label(text=f"Onto: {source.name}", icon="OUTLINER_OB_ARMATURE")
            layout.separator()
        layout.prop(self, "action_name")
        layout.prop(self, "overwrite")
        layout.separator()
        layout.prop(self, "frame_range_source")
        if self.frame_range_source == "MANUAL":
            row = layout.row(align=True)
            row.prop(self, "frame_start")
            row.prop(self, "frame_end")
        layout.prop(self, "step")
        layout.separator()
        info = layout.column(align=True)
        info.scale_y = 0.85
        info.label(text="Animation-bone subset only (animBones).", icon="INFO")
        info.label(text="Forward constraints are preserved.", icon="INFO")

    def execute(self, context):
        source, rig = find_pair(active_armature(context))
        if self.frame_range_source == "SCENE":
            start, end = context.scene.frame_start, context.scene.frame_end
        elif self.frame_range_source == "ACTION" and rig and rig.animation_data and rig.animation_data.action:
            start, end = map(int, rig.animation_data.action.frame_range)
        else:
            start, end = self.frame_start, self.frame_end
        request = RigifyBakeRequest(
            action_name=self.action_name,
            overwrite=bool(self.overwrite),
            frame_start=int(start),
            frame_end=int(end),
            step=max(1, int(self.step)),
        )
        return _finish(self, bake_to_source(context, source, rig, request))
