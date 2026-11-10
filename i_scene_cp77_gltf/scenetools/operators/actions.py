from __future__ import annotations

from bpy.props import FloatProperty
from bpy.types import Operator

from ...blender.operator_results import OperationResult, execute_operation
from ..application.execution import (
    bake_environment,
    center_weather,
    clear_bake,
    setup_environment,
)
from ..runtime.ownership import scene_has_owned_runtime


def _setup(context):
    return OperationResult.finished(f"CP77 environment: {setup_environment(context)}")


def _center_weather(context):
    source = center_weather(context)
    settings = context.scene.cp77_scene_tools
    if settings.weather_follow_scene_camera:
        settings.weather_follow_scene_camera = False
    return OperationResult.finished(
        f"Weather preview centered on {source.lower().replace('_', ' ')}"
    )


def _bake(context):
    return OperationResult.finished(bake_environment(context))


def _clear_bake(context):
    return OperationResult.finished(clear_bake(context))


class CP77_OT_SceneEnvironmentSetup(Operator):
    bl_idname = "cp77.scene_environment_setup"
    bl_label = "Set Up Environment"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        return execute_operation(self, "SceneTools setup", _setup, context)


class CP77_OT_SceneWeatherCenterView(Operator):
    bl_idname = "cp77.scene_weather_center_view"
    bl_label = "Center Weather on View"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        return execute_operation(self, "Weather centering", _center_weather, context)


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
        return execute_operation(self, "Environment bake", _bake, context)


class CP77_OT_SceneEnvironmentClearBake(Operator):
    bl_idname = "cp77.scene_environment_clear_bake"
    bl_label = "Clear Environment Bake"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        scene = getattr(context, "scene", None)
        return scene is not None and scene_has_owned_runtime(scene)

    def execute(self, context):
        return execute_operation(self, "Clear environment bake", _clear_bake, context)


ENVIRONMENT_OPERATOR_CLASSES = (
    CP77_OT_SceneEnvironmentSetup,
    CP77_OT_SceneWeatherCenterView,
    CP77_OT_SceneTimeNudge,
    CP77_OT_SceneEnvironmentBake,
    CP77_OT_SceneEnvironmentClearBake,
)
