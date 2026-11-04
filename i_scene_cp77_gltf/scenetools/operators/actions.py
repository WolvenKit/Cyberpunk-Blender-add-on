from __future__ import annotations

from bpy.props import FloatProperty
from bpy.types import Operator

from ...core.log import get_logger
from ...core.notifications import report
from ..application.execution import (
    bake_environment,
    center_weather,
    clear_bake,
    setup_environment,
)
from ..runtime.ownership import scene_has_owned_runtime

_LOG = get_logger(__name__)


class CP77_OT_SceneEnvironmentSetup(Operator):
    bl_idname = "cp77.scene_environment_setup"
    bl_label = "Set Up Environment"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        try:
            status = setup_environment(context)
        except Exception as error:
            report(
                self,
                "ERROR",
                f"SceneTools setup failed: {error}",
                logger=_LOG,
                error=error,
            )
            return {"CANCELLED"}
        report(self, "INFO", f"CP77 environment: {status}", logger=_LOG)
        return {"FINISHED"}


class CP77_OT_SceneWeatherCenterView(Operator):
    bl_idname = "cp77.scene_weather_center_view"
    bl_label = "Center Weather on View"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        try:
            source = center_weather(context)
        except Exception as error:
            report(
                self,
                "ERROR",
                f"Weather centering failed: {error}",
                logger=_LOG,
                error=error,
            )
            return {"CANCELLED"}
        settings = context.scene.cp77_scene_tools
        if settings.weather_follow_scene_camera:
            settings.weather_follow_scene_camera = False
        report(
            self,
            "INFO",
            f"Weather preview centered on {source.lower().replace('_', ' ')}",
            logger=_LOG,
        )
        return {"FINISHED"}


class CP77_OT_SceneTimeNudge(Operator):
    bl_idname = "cp77.scene_time_nudge"
    bl_label = "Adjust Environment Time"
    bl_options = {"UNDO"}

    delta: FloatProperty(default=1.0)

    def execute(self, context):
        settings = context.scene.cp77_scene_tools
        settings.time_of_day = settings.time_of_day + self.delta
        return {"FINISHED"}


class CP77_OT_SceneEnvironmentBake(Operator):
    bl_idname = "cp77.scene_environment_bake"
    bl_label = "Bake 24h Cycle"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        scene = getattr(context, "scene", None)
        return scene is not None and scene_has_owned_runtime(scene)

    def execute(self, context):
        try:
            status = bake_environment(context)
        except Exception as error:
            report(
                self,
                "ERROR",
                f"Environment bake failed: {error}",
                logger=_LOG,
                error=error,
            )
            return {"CANCELLED"}
        report(self, "INFO", status, logger=_LOG)
        return {"FINISHED"}


class CP77_OT_SceneEnvironmentClearBake(Operator):
    bl_idname = "cp77.scene_environment_clear_bake"
    bl_label = "Clear Environment Bake"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        scene = getattr(context, "scene", None)
        return scene is not None and scene_has_owned_runtime(scene)

    def execute(self, context):
        try:
            status = clear_bake(context)
        except Exception as error:
            report(
                self,
                "ERROR",
                f"Clear environment bake failed: {error}",
                logger=_LOG,
                error=error,
            )
            return {"CANCELLED"}
        report(self, "INFO", status, logger=_LOG)
        return {"FINISHED"}


ENVIRONMENT_OPERATOR_CLASSES = (
    CP77_OT_SceneEnvironmentSetup,
    CP77_OT_SceneWeatherCenterView,
    CP77_OT_SceneTimeNudge,
    CP77_OT_SceneEnvironmentBake,
    CP77_OT_SceneEnvironmentClearBake,
)
