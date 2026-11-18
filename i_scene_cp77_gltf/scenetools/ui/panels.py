from __future__ import annotations

from bpy.types import Panel

from ...blender.workspace import is_animation_workspace
from ...enttools.ui.panel import draw_entity
from ...inktools.ui import draw_ink_widgets
from ..operators.actions import (
    CP77_OT_SceneEnvironmentBake,
    CP77_OT_SceneEnvironmentClearBake,
    CP77_OT_SceneEnvironmentSetup,
    CP77_OT_SceneTimeNudge,
    CP77_OT_SceneWeatherCenterView,
)
from .lights import draw_lights
from .sectors import draw_sectors


def _draw_environment(layout, settings):
    time_box = layout.box()
    time_box.label(text="Environment", icon="WORLD")
    row = time_box.row(align=True)
    back = row.operator(CP77_OT_SceneTimeNudge.bl_idname, text="", icon="TRIA_LEFT")
    back.delta = -1.0
    row.prop(settings, "time_of_day", slider=True)
    forward = row.operator(CP77_OT_SceneTimeNudge.bl_idname, text="", icon="TRIA_RIGHT")
    forward.delta = 1.0
    time_box.prop(settings, "weather")

    trajectory = layout.box()
    trajectory.label(text="Trajectory", icon="LIGHT_SUN")
    row = trajectory.row(align=True)
    row.prop(settings, "override_season", text="")
    sub = row.row(align=True)
    sub.enabled = settings.override_season
    sub.prop(settings, "season", text="")
    row = trajectory.row(align=True)
    row.prop(settings, "override_latitude", text="")
    sub = row.row(align=True)
    sub.enabled = settings.override_latitude
    sub.prop(settings, "latitude", text="Latitude")

    preview = layout.box()
    preview.label(text="Blender Preview", icon="SHADING_RENDERED")
    preview.prop(settings, "preview_exposure")
    row = preview.row(align=True)
    row.prop(settings, "create_global_light", toggle=True)
    row.prop(settings, "create_world", toggle=True)
    row = preview.row(align=True)
    row.prop(settings, "preview_volumetric_clouds", toggle=True)
    row.prop(settings, "preview_high_clouds", toggle=True)
    row = preview.row(align=True)
    row.prop(settings, "preview_rain", toggle=True)
    row = preview.row(align=True)
    row.prop(settings, "preview_volumetric_fog", toggle=True)
    row.prop(settings, "preview_distant_fog", toggle=True)
    if (
        settings.preview_volumetric_clouds
        or settings.preview_rain
        or settings.preview_volumetric_fog
        or settings.preview_distant_fog
    ):
        row = preview.row(align=True)
        row.prop(settings, "weather_follow_scene_camera", toggle=True)
        row.operator(
            CP77_OT_SceneWeatherCenterView.bl_idname,
            text="Center Weather on View",
            icon="PIVOT_BOUNDBOX",
        )
    preview.prop(settings, "live_update")

    controls = layout.column(align=True)
    controls.operator(CP77_OT_SceneEnvironmentSetup.bl_idname, icon="WORLD")
    row = controls.row(align=True)
    row.operator(CP77_OT_SceneEnvironmentBake.bl_idname, icon="KEYFRAME")
    row.operator(CP77_OT_SceneEnvironmentClearBake.bl_idname, text="", icon="X")


class CP77_PT_SceneTools(Panel):
    bl_label = "CP77 Scene"
    bl_idname = "CP77_PT_scene_tools"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "CP77 Modding"

    @classmethod
    def poll(cls, context):
        return not is_animation_workspace(context)

    def draw(self, context):
        layout = self.layout
        draw_sectors(layout, context)
        header, body = layout.panel("cp77_scene_environment", default_closed=True)
        header.label(text="Environment")
        if body:
            _draw_environment(body, context.scene.cp77_scene_tools)
        draw_lights(layout, context)
        draw_entity(layout, context)
        draw_ink_widgets(layout, context)


SCENE_PANEL_CLASSES = (CP77_PT_SceneTools,)
