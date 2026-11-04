from __future__ import annotations

from ...bartmoss.celestial import DAY_HOURS
from ...core.log import get_logger
from ...importers.common.light_environment import rebuild_environment_light_registry
from ..blender.clouds import (
    clear_cloud_preview_animation,
    cloud_keyframe_targets,
    ensure_cloud_preview,
)
from ..blender.fog import (
    clear_fog_preview_animation,
    ensure_fog_preview,
    fog_keyframe_targets,
)
from ..blender.weather import (
    center_weather_on_view,
    clear_weather_preview_animation,
    ensure_weather_preview,
    weather_keyframe_targets,
)
from ..blender.world import (
    apply_sample,
    clear_world_animation,
    ensure_global_light,
    ensure_global_specular_light,
    ensure_world,
    global_light_keyframe_targets,
    world_keyframe_targets,
)
from ..model.solver import sunrise_sunset
from .options import BAKE_SAMPLES, RefreshScope, SceneToolsRequest, format_hour
from .session import SceneToolsSession

_LOG = get_logger(__name__)


def _ensure_previews(scene, request):
    weather_created = ensure_weather_preview(scene, request)
    cloud_created = ensure_cloud_preview(scene, request)
    fog_created = ensure_fog_preview(scene, request)
    return weather_created, cloud_created, fog_created


def setup_environment(context):
    scene = context.scene
    settings = scene.cp77_scene_tools
    request = SceneToolsRequest.from_settings(settings)
    with SceneToolsSession(scene, settings, context=context, transactional=True):
        if request.create_world:
            ensure_world(scene)
        if request.create_global_light:
            ensure_global_light(scene)
            ensure_global_specular_light(scene)
        managed_lights = rebuild_environment_light_registry(scene)
        preview_created, cloud_created, fog_created = _ensure_previews(scene, request)
        if (
            request.preview_volumetric_clouds
            or request.preview_rain
            or request.preview_volumetric_fog
            or request.preview_distant_fog
        ) and not request.weather_follow_scene_camera:
            center_weather_on_view(context)
        sample = request.sample()
        apply_sample(scene, request, sample)

    rise, set_hour = sunrise_sunset(
        request.weather,
        request.latitude if request.override_latitude else None,
        request.season if request.override_season else None,
    )
    rise_text = format_hour(rise) if rise is not None else "never"
    set_text = format_hour(set_hour) if set_hour is not None else "never"
    created = (
        preview_created["clouds"]
        + preview_created["rain"]
        + cloud_created
        + fog_created
    )
    status = (
        f"sunrise {rise_text} · sunset {set_text} · {managed_lights} managed light(s)"
        f" · {created} weather object(s) created"
    )
    _LOG.info("SceneTools environment setup: %s", status)
    return status


def refresh_environment(scene, settings, scope=RefreshScope.FULL):
    request = SceneToolsRequest.from_settings(settings)
    scope = RefreshScope(scope)
    with SceneToolsSession(scene, settings) as session:
        if not session.has_runtime:
            return False
        sample = request.sample()
        if scope is RefreshScope.FULL:
            if session.weather_collection is not None:
                _ensure_previews(scene, request)
            apply_sample(scene, request, sample)
        elif scope is RefreshScope.EXPOSURE:
            apply_sample(
                scene,
                request,
                sample,
                update_cloud_preview=False,
                update_fog_preview=False,
                sync_registered=False,
            )
        elif scope is RefreshScope.WEATHER_PREVIEW:
            ensure_weather_preview(scene, request)
            apply_sample(
                scene,
                request,
                sample,
                update_world=False,
                update_global_lights=False,
                update_cloud_preview=False,
                update_fog_preview=False,
                sync_registered=False,
            )
        elif scope is RefreshScope.CLOUD_PREVIEW:
            ensure_cloud_preview(scene, request)
            apply_sample(
                scene,
                request,
                sample,
                update_world=False,
                update_global_lights=False,
                update_weather_preview=False,
                update_fog_preview=False,
                sync_registered=False,
            )
        elif scope is RefreshScope.FOG_PREVIEW:
            ensure_fog_preview(scene, request)
            apply_sample(
                scene,
                request,
                sample,
                update_world=False,
                update_global_lights=False,
                update_weather_preview=False,
                update_cloud_preview=False,
                sync_registered=False,
            )
    return True


def center_weather(context):
    scene = context.scene
    settings = scene.cp77_scene_tools
    with SceneToolsSession(scene, settings, context=context):
        source = center_weather_on_view(context)
    # Fog boxes are kept under the cloud deck relative to the anchor height.
    refresh_environment(scene, settings, RefreshScope.FOG_PREVIEW)
    return source


def _bake_keyframe_targets(scene, light_objects, world):
    return (
        *global_light_keyframe_targets(light_objects),
        *world_keyframe_targets(world),
        *weather_keyframe_targets(scene),
        *cloud_keyframe_targets(scene),
        *fog_keyframe_targets(scene),
    )


def bake_environment(context):
    scene = context.scene
    settings = scene.cp77_scene_tools
    request = SceneToolsRequest.from_settings(settings)
    with SceneToolsSession(scene, settings, context=context) as session:
        global_light = session.global_light
        specular_light = session.global_specular_light
        world = session.world
        fps = float(scene.render.fps) / max(float(scene.render.fps_base), 1.0e-8)
        step = DAY_HOURS / BAKE_SAMPLES
        # The keyed sockets and datablocks are resolved once, after the first sample has
        # ensured them, instead of being looked up again for every frame.
        targets = None

        for index in range(BAKE_SAMPLES + 1):
            hour = index * step
            frame = int(round(hour * fps)) + 1
            sample = request.sample(hour)
            apply_sample(
                scene,
                request,
                sample,
                sync_registered=False,
            )
            if targets is None:
                targets = _bake_keyframe_targets(
                    scene, (global_light, specular_light), world
                )
            for owner, path in targets:
                owner.keyframe_insert(path, frame=frame)

        scene.frame_start = 1
        scene.frame_end = int(round(DAY_HOURS * fps)) + 1
        apply_sample(scene, request, request.sample())
    return f"baked {BAKE_SAMPLES} samples through the midnight seam"


def clear_bake(context):
    scene = context.scene
    settings = scene.cp77_scene_tools
    request = SceneToolsRequest.from_settings(settings)
    with SceneToolsSession(scene, settings, context=context) as session:
        for light_obj in (session.global_light, session.global_specular_light):
            if light_obj is None:
                continue
            light_obj.animation_data_clear()
            if getattr(light_obj, "data", None) is not None:
                light_obj.data.animation_data_clear()
        clear_world_animation(session.world)
        clear_weather_preview_animation(scene)
        clear_cloud_preview_animation(scene)
        clear_fog_preview_animation(scene)
        apply_sample(scene, request, request.sample())
    return "environment bake cleared"
