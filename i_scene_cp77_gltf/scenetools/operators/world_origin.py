from __future__ import annotations

from bpy.types import Operator

from ...blender.world_origin import (
    recentre_scene,
    restore_world_position,
)
from ...core.log import get_logger
from ...core.notifications import report

_LOG = get_logger(__name__)


def _describe(offset, shifted):
    return (
        f"({offset.x:g}, {offset.y:g}, {offset.z:g}): {shifted.moved} objects moved, "
        f"{shifted.templates} instance templates kept, {shifted.child_of_fixed} Child Of constraints adjusted"
    )


class CP77_OT_SceneRecentre(Operator):
    bl_idname = "cp77.scene_recentre"
    bl_label = "Recentre Scene"
    bl_description = (
        "Shift the whole scene so its content sits near Blender's origin, by a whole-metre offset stored on the "
        "scene. Fixes float precision artifacts kilometres out (ridged Cycles skin, shadow acne, jitter); "
        "sector export adds the offset back"
    )
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        offset, shifted = recentre_scene(context.scene)
        if offset is None:
            report(self, "INFO", "The scene already sits near the origin", logger=_LOG)
            return {"CANCELLED"}
        report(self, "INFO", f"Recentred by {_describe(offset, shifted)}", logger=_LOG)
        return {"FINISHED"}


class CP77_OT_SceneRestoreWorldPosition(Operator):
    bl_idname = "cp77.scene_restore_world_position"
    bl_label = "Restore World Position"
    bl_description = (
        "Undo the scene's recentring so objects hold true game coordinates again"
    )
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        offset, shifted = restore_world_position(context.scene)
        if offset is None:
            report(self, "INFO", "The scene is not recentred", logger=_LOG)
            return {"CANCELLED"}
        report(self, "INFO", f"Moved back by {_describe(offset, shifted)}", logger=_LOG)
        return {"FINISHED"}


WORLD_ORIGIN_OPERATOR_CLASSES = (
    CP77_OT_SceneRecentre,
    CP77_OT_SceneRestoreWorldPosition,
)
