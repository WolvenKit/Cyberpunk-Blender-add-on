from __future__ import annotations

from ...blender.world_origin import (
    game_world_matrix,
    has_world_offset,
    to_game_location,
    world_offset,
)
from ..operators.world_origin import (
    CP77_OT_SceneRecentre,
    CP77_OT_SceneRestoreWorldPosition,
)


def _xyz(vector):
    return f"{vector.x:.3f}, {vector.y:.3f}, {vector.z:.3f}"


def draw_world_origin(layout, context):
    """The World Origin section: recentring and game-space readouts"""
    scene = context.scene
    header, body = layout.panel("cp77_scene_world_origin", default_closed=True)
    header.label(text="World Origin")
    if not body:
        return
    column = body.column(align=True)
    if has_world_offset(scene):
        offset = world_offset(scene)
        column.label(text=f"Offset: {offset.x:g}, {offset.y:g}, {offset.z:g}")
        column.label(
            text=f"Cursor (game): {_xyz(to_game_location(scene, scene.cursor.location))}"
        )
        obj = context.active_object
        if obj is not None:
            column.label(
                text=f"{obj.name} (game): {_xyz(game_world_matrix(obj, scene).translation)}"
            )
    else:
        column.label(text="Scene holds game coordinates")
    row = body.row(align=True)
    row.operator(CP77_OT_SceneRecentre.bl_idname, icon="PIVOT_CURSOR")
    sub = row.row(align=True)
    sub.enabled = has_world_offset(scene)
    sub.operator(CP77_OT_SceneRestoreWorldPosition.bl_idname, text="", icon="LOOP_BACK")
