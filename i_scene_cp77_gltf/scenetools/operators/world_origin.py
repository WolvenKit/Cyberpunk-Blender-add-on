from __future__ import annotations

from bpy.types import Operator

from ...blender.operator_results import execute_operation
from ...blender.world_origin import (
    has_world_offset,
    recentre_scene,
    restore_world_position,
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
        return execute_operation(self, "Recentre scene", recentre_scene, context.scene)


class CP77_OT_SceneRestoreWorldPosition(Operator):
    bl_idname = "cp77.scene_restore_world_position"
    bl_label = "Restore World Position"
    bl_description = (
        "Undo the scene's recentring so objects hold true game coordinates again"
    )
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return has_world_offset(context.scene)

    def execute(self, context):
        return execute_operation(
            self, "Restore world position", restore_world_position, context.scene
        )


WORLD_ORIGIN_OPERATOR_CLASSES = (
    CP77_OT_SceneRecentre,
    CP77_OT_SceneRestoreWorldPosition,
)
