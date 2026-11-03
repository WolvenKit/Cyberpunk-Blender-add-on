from bpy.props import BoolProperty, EnumProperty, IntProperty, StringProperty
from bpy.types import Operator

from ...blender.operator_results import execute_operation
from ...core.log import get_logger
from ...core.notifications import report
from ..model.requests import BAKE_RANGE_ACTION, BAKE_RANGE_MANUAL, BAKE_RANGE_SCENE
from ..services import rigify

_LOG = get_logger(__name__)


class CP77ToRigify(Operator):
    bl_idname = "rigify_generator.cp77"
    bl_options = {"REGISTER", "UNDO"}
    bl_label = "Generate Rigify"

    def execute(self, context):
        return execute_operation(self, "Rigify generation", rigify.generate, context)


class CP77_OT_SetRigifyLiveSync(Operator):
    bl_idname = "cp77.set_rigify_live_sync"
    bl_label = "Rigify Live Sync"
    bl_description = (
        "Make the Cyberpunk rig follow the Rigify rig, or let it play its own action"
    )
    bl_options = {"REGISTER", "UNDO"}

    enabled: BoolProperty(name="Follow Rigify", default=True)
    source_name: StringProperty(options={"HIDDEN"})
    rigify_name: StringProperty(options={"HIDDEN"})

    def execute(self, context):
        return execute_operation(
            self,
            "Rigify live sync",
            rigify.set_live_sync,
            context,
            enabled=self.enabled,
            source_name=self.source_name,
            rigify_name=self.rigify_name,
        )


class CP77_OT_ActivateLinkedRig(Operator):
    bl_idname = "cp77.activate_linked_rig"
    bl_label = "Activate Linked Rig"
    bl_options = {"REGISTER", "UNDO"}

    target_name: StringProperty(options={"HIDDEN"})

    def execute(self, context):
        return execute_operation(
            self,
            "Rig activation",
            rigify.activate_linked_rig,
            context,
            self.target_name,
        )


class _RigifyBakeOperator:
    action_name: StringProperty(
        name="Action Name",
        description="Name of the new action",
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
            (
                BAKE_RANGE_ACTION,
                "Action Range",
                "Use the baked action's own frame range",
            ),
            (
                BAKE_RANGE_SCENE,
                "Scene Range",
                "Use scene.frame_start / scene.frame_end",
            ),
            (BAKE_RANGE_MANUAL, "Manual", "Specify start and end frames"),
        ],
        default=BAKE_RANGE_ACTION,
    )
    frame_start: IntProperty(name="Start", default=1, min=0)
    frame_end: IntProperty(name="End", default=250, min=0)
    step: IntProperty(name="Step", description="Frame step", default=1, min=1, max=10)

    defaults = None
    baker = None
    label = ""

    @classmethod
    def poll(cls, context):
        return cls.defaults(context) is not None

    def invoke(self, context, event):
        defaults = type(self).defaults(context)
        if defaults is None:
            report(self, "ERROR", "Nothing to bake", logger=_LOG)
            return {"CANCELLED"}
        self.action_name = defaults.action_name
        self.frame_start, self.frame_end = defaults.frame_start, defaults.frame_end
        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw_header(self, layout, source, rig):
        pass

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        source, rig = rigify.linked_pair(context)
        if source is not None and rig is not None:
            self.draw_header(layout, source, rig)
            layout.separator()
        layout.prop(self, "action_name")
        layout.prop(self, "overwrite")
        layout.separator()
        layout.prop(self, "frame_range_source")
        if self.frame_range_source == BAKE_RANGE_MANUAL:
            row = layout.row(align=True)
            row.prop(self, "frame_start")
            row.prop(self, "frame_end")
        layout.prop(self, "step")

    def execute(self, context):
        return execute_operation(
            self,
            self.label,
            type(self).baker,
            context,
            action_name=self.action_name,
            overwrite=self.overwrite,
            frame_range_source=self.frame_range_source,
            frame_start=self.frame_start,
            frame_end=self.frame_end,
            step=self.step,
        )


class CP77_OT_BakeRigifyToSource(_RigifyBakeOperator, Operator):
    bl_idname = "cp77.bake_rigify_to_source"
    bl_label = "Bake Rigify to Cyberpunk"
    bl_description = "Bake the Rigify rig's action onto the Cyberpunk rig's animation bones, ready for export"
    bl_options = {"REGISTER", "UNDO"}

    defaults = staticmethod(rigify.bake_defaults)
    baker = staticmethod(rigify.bake_active)
    label = "Rigify bake"

    def draw_header(self, layout, source, rig):
        col = layout.column(align=True)
        col.enabled = False
        action = rig.animation_data.action if rig.animation_data else None
        col.label(
            text=f"From: {rig.name} → {action.name if action else '—'}",
            icon="ARMATURE_DATA",
        )
        col.label(text=f"Onto: {source.name}", icon="OUTLINER_OB_ARMATURE")


class CP77_OT_BakeSourceToRigify(_RigifyBakeOperator, Operator):
    bl_idname = "cp77.bake_source_to_rigify"
    bl_label = "Bake Cyberpunk to Rigify"
    bl_description = "Bake the Cyberpunk rig's action onto the Rigify controls (limbs in FK), so it can be edited with them"
    bl_options = {"REGISTER", "UNDO"}

    defaults = staticmethod(rigify.source_bake_defaults)
    baker = staticmethod(rigify.bake_source_active)
    label = "Rigify control bake"

    def draw_header(self, layout, source, rig):
        col = layout.column(align=True)
        col.enabled = False
        action = source.animation_data.action if source.animation_data else None
        col.label(
            text=f"From: {source.name} → {action.name if action else '—'}",
            icon="OUTLINER_OB_ARMATURE",
        )
        col.label(text=f"Onto: {rig.name} controls", icon="ARMATURE_DATA")


RIGIFY_OPERATOR_CLASSES = (
    CP77ToRigify,
    CP77_OT_SetRigifyLiveSync,
    CP77_OT_ActivateLinkedRig,
    CP77_OT_BakeRigifyToSource,
    CP77_OT_BakeSourceToRigify,
)
