import bpy

from ...blender.workspace import open_animation_workspace
from ...core.log import get_logger
from ...core.notifications import report

_LOG = get_logger(__name__)


class CP77_OT_OpenAnimationWorkspace(bpy.types.Operator):
    bl_idname = "cp77.open_animation_workspace"
    bl_label = "Animation Workspace"
    bl_description = "Switch to the Cyberpunk Animation workspace, adding it to the file when it is missing"

    def execute(self, context):
        if context.window is None:
            report(
                self,
                "WARNING",
                "The Animation workspace needs a Blender window.",
                logger=_LOG,
            )
            return {"CANCELLED"}
        try:
            open_animation_workspace(context)
        except (OSError, RuntimeError) as error:
            report(
                self,
                "ERROR",
                f"Couldn't open the Animation workspace: {error}",
                logger=_LOG,
                error=error,
            )
            return {"CANCELLED"}
        return {"FINISHED"}


WORKSPACE_OPERATOR_CLASSES = (CP77_OT_OpenAnimationWorkspace,)
