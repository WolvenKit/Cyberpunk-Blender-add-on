from bpy.props import EnumProperty
from bpy.types import Operator

from ...blender.operator_results import execute_operation
from ...core.log import get_logger
from ...core.notifications import report
from ..services import root_motion

_LOG = get_logger(__name__)

_EDIT_ITEMS = (
    ("ZERO", "Zero Start", "Rebase the trajectory to its first transform"),
    (
        "SCALE",
        "Apply Travel & Turn",
        "Adjust distance, travel direction and accumulated yaw",
    ),
    (
        "GENERATE",
        "Create Motion",
        "Replace the trajectory with linear travel and a steady turn",
    ),
    ("FILTER", "Keep Channels", "Keep the selected translation and rotation channels"),
    ("SMOOTH", "Smooth Motion", "Smooth selected channels with fixed endpoints"),
)


class RootMotionOperatorBase(Operator):
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        armature = root_motion.animated_armature(context)
        return (
            armature is not None
            and getattr(armature, "mode", "OBJECT") in {"OBJECT", "POSE"}
            and not getattr(
                getattr(context, "screen", None), "is_animation_playing", False
            )
        )

    def run(self, context, label, operation, *args):
        armature = root_motion.animated_armature(context)
        if armature is None:
            report(
                self,
                "ERROR_INVALID_CONTEXT",
                "Select an animated armature",
                logger=_LOG,
            )
            return {"CANCELLED"}
        try:
            request, start, end = root_motion.motion_request(context, armature)
        except (TypeError, ValueError) as error:
            report(self, "ERROR", str(error), logger=_LOG, error=error)
            return {"CANCELLED"}

        def apply():
            result = operation(context, armature, request, start, end, *args)
            if result.ok and "report" in result.details:
                data = context.scene.rm_data
                data.report = result.details["report"]
                data.report_action = armature.animation_data.action.name
            return result

        return execute_operation(self, label, apply)


class CP77_OT_RootMotionExtract(RootMotionOperatorBase):
    bl_idname = "cp77.root_motion_extract"
    bl_label = "Extract Motion"
    bl_description = "Transfer source-bone travel to the export root and preserve the sampled character pose"

    def execute(self, context):
        return self.run(
            context, "Root motion extraction", root_motion.run_root_motion, "extract"
        )


class CP77_OT_RootMotionIntegrate(RootMotionOperatorBase):
    bl_idname = "cp77.root_motion_integrate"
    bl_label = "Bake Into Pose"
    bl_description = "Move root travel into its child branches and disable motion extraction on export"

    def execute(self, context):
        return self.run(
            context, "Root motion bake", root_motion.run_root_motion, "integrate"
        )


class CP77_OT_RootMotionClear(RootMotionOperatorBase):
    bl_idname = "cp77.root_motion_clear"
    bl_label = "Make In Place"
    bl_description = (
        "Clear all root travel and turn while retaining the child animation"
    )

    def execute(self, context):
        return self.run(
            context, "Root motion clear", root_motion.run_root_motion, "remove"
        )


class CP77_OT_RootMotionEdit(RootMotionOperatorBase):
    bl_idname = "cp77.root_motion_edit"
    bl_label = "Edit Root Motion"
    operation: EnumProperty(items=_EDIT_ITEMS)

    @classmethod
    def description(cls, context, properties):
        return next(item[2] for item in _EDIT_ITEMS if item[0] == properties.operation)

    def execute(self, context):
        return self.run(
            context,
            "Root motion edit",
            root_motion.run_root_motion,
            self.operation,
            root_motion.edit_options(context),
        )


class CP77_OT_RootMotionInspect(RootMotionOperatorBase):
    bl_idname = "cp77.root_motion_inspect"
    bl_label = "Check Motion"
    bl_description = "Measure action travel, speed, turn and the first-frame offset"

    def execute(self, context):
        return self.run(
            context, "Root motion check", root_motion.run_root_motion, "inspect"
        )


class CP77_OT_RootMotionFormat(RootMotionOperatorBase):
    bl_idname = "cp77.root_motion_format"
    bl_label = "Set Export Format"
    bl_description = (
        "Check the trajectory and set its motion format for animation export"
    )

    def execute(self, context):
        return self.run(
            context, "Root motion format", root_motion.run_root_motion, "format"
        )


class CP77_OT_RootMotionSelect(RootMotionOperatorBase):
    bl_idname = "cp77.root_motion_select"
    bl_label = "Select Root Curves"
    bl_description = (
        "Select the root bone and its transform keys for Graph Editor editing"
    )

    def execute(self, context):
        return self.run(
            context,
            "Root curve selection",
            lambda _context, armature, request, _start, _end: (
                root_motion.select_root_curves(armature, request)
            ),
        )


class CP77_OT_RootMotionDuplicate(RootMotionOperatorBase):
    bl_idname = "cp77.root_motion_duplicate"
    bl_label = "Duplicate Action"
    bl_description = (
        "Create an editable copy of the action, including its source metadata"
    )

    def execute(self, context):
        armature = root_motion.animated_armature(context)

        def duplicate():
            result = root_motion.duplicate_action(armature)
            if result.ok:
                context.scene.rm_data.report = ""
            return result

        return execute_operation(self, "Action duplicate", duplicate)


ROOT_MOTION_OPERATOR_CLASSES = (
    CP77_OT_RootMotionExtract,
    CP77_OT_RootMotionIntegrate,
    CP77_OT_RootMotionClear,
    CP77_OT_RootMotionEdit,
    CP77_OT_RootMotionInspect,
    CP77_OT_RootMotionFormat,
    CP77_OT_RootMotionSelect,
    CP77_OT_RootMotionDuplicate,
)
