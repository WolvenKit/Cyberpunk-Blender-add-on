from __future__ import annotations

import time

import bpy
from mathutils import Matrix

from ....assetio.values import cname_text, field_float
from ....blender.light_preview import (
    animate_flicker,
    capture_base_energy,
    configure_cycles_distribution,
    configure_static_light,
    create_proxy_samples,
)
from ....blender.naming import fit_id_name
from ....blender.transactions import track_created_datablock
from ....entity.domain.light_representation import (
    light_representation,
    proxy_offsets,
    uses_direction_axis,
)
from ....entity.domain.lights import static_light_flicker_seed, static_light_settings
from ....redSpace.transforms import red_light_local_to_blender_light
from ...common.light_environment import register_environment_lights
from ...common.light_probe_participation import apply_probe_capture_participation
from ...common.paths import depot_path


class _Laps:
    """Adds the time since the last lap to the named total at each lap"""

    __slots__ = ("started", "totals")

    def __init__(self, totals):
        self.totals = totals
        self.started = time.perf_counter()

    def __call__(self, name):
        now = time.perf_counter()
        self.totals[name] += now - self.started
        self.started = now


class StaticLightingService:
    def __init__(self, session):
        self.session = session
        self._registry_objects = []
        self._registry_flush_seconds = 0.0
        self._registry_flushes = 0
        self._primary_lights = 0
        self._proxy_lights = 0
        self._create_seconds = 0.0
        self._create_timing = {
            "prepare": 0.0,
            "datablocks": 0.0,
            "configure": 0.0,
            "resources": 0.0,
            "distribution": 0.0,
            "metadata": 0.0,
            "proxies": 0.0,
            "registry_queue": 0.0,
            "flicker": 0.0,
        }

    def finalize_environment_registry(self, scene=None):
        objects = tuple(obj for obj in self._registry_objects if obj is not None)
        self._registry_objects.clear()
        if not objects:
            return 0
        started = time.perf_counter()
        try:
            return register_environment_lights(
                scene if scene is not None else getattr(bpy.context, "scene", None),
                objects,
            )
        finally:
            self._registry_flush_seconds += time.perf_counter() - started
            self._registry_flushes += 1

    def timing_stats(self):
        stats = {
            "registry_objects": len(self._registry_objects),
            "registry_flushes": self._registry_flushes,
            "registry_flush_seconds": self._registry_flush_seconds,
            "primary_lights": self._primary_lights,
            "proxy_lights": self._proxy_lights,
            "create_seconds": self._create_seconds,
        }
        stats.update(
            {
                f"create_{key}_seconds": value
                for key, value in self._create_timing.items()
            }
        )
        return stats

    def resolve_ies(self, depot_path):
        return self.session.resource_resolver.resolve(
            "ies",
            depot_path,
            (
                (False, ".ies"),
                (True, ".ies.json"),
            ),
            append_expected_json=False,
        ).resolved_path

    def resolve_projection(self, depot_path):
        return self.session.resource_resolver.resolve(
            "light_projection",
            depot_path,
            (
                (False, ".dds"),
                (False, ".png"),
                (False, ".tga"),
                (False, ".jpg"),
                (False, ".jpeg"),
            ),
            append_expected_json=False,
        ).resolved_path

    @staticmethod
    def _decorate_proxy(obj, data):
        obj["cp77_node_type"] = "CP77LightProxySample"
        apply_probe_capture_participation(obj, data)
        for key in (
            "group",
            "envColorGroup",
            "colorGroupSaturation",
            "portalAngleCutoff",
            "lightChannel",
            "innerAngle",
            "outerAngle",
            "highBeamConeMultiplier",
            "highBeamRadiusMultiplier",
            "highBeamPitchAngle",
        ):
            value = data.get(key)
            if isinstance(value, (str, int, float, bool)):
                obj[key] = value

    def create(self, context, instance, instance_index):
        create_started = time.perf_counter()
        lap = _Laps(self._create_timing)
        data = context.data
        cp77_type = str(data.get("type", "LT_Point"))
        blender_type, representation = light_representation(data)
        if cp77_type not in {"LT_Point", "LT_Spot", "LT_Area"}:
            context.operations.warning(
                f"{context.sector_name}: light node "
                f"{context.node_index} has unknown type {cp77_type}"
            )
        if cp77_type == "LT_Area" and str(data.get("areaShape", "ALS_Capsule")) not in {
            "ALS_Sphere",
            "ALS_Capsule",
        }:
            context.operations.warning(
                f"{context.sector_name}: light node {context.node_index} uses non-native area shape "
                f"{data.get('areaShape')}; importing as punctual Point fallback"
            )

        debug_name = cname_text(
            data.get("debugName"),
            f"Light_{context.node_index}",
        )
        name = fit_id_name(f"{context.node_index}_{debug_name}")
        offsets = proxy_offsets(data, representation)
        lap("prepare")

        light = track_created_datablock(
            "lights", bpy.data.lights.new(name, blender_type)
        )
        obj = track_created_datablock("objects", bpy.data.objects.new(name, light))
        target_collection = context.collection_for_instance(instance)
        target_collection.objects.link(obj)
        apply_probe_capture_participation(obj, data)
        lap("datablocks")

        radius, source_radius = configure_static_light(
            light, data, representation, len(offsets)
        )

        axis_matrix = (
            Matrix(red_light_local_to_blender_light())
            if uses_direction_axis(representation)
            else Matrix.Identity(4)
        )
        obj.matrix_world = (
            context.operations.instance_matrix(
                instance,
                context.execution.scale_factor,
            )
            @ Matrix.Translation((float(offsets[0]), 0.0, 0.0))
            @ axis_matrix
        )
        obj["cp77_proxy_representation"] = representation
        lap("configure")

        ies_path = depot_path(data, "iesProfile")
        resolved_ies = self.resolve_ies(ies_path)
        projection_path = depot_path(data, "projectionTexture")
        resolved_projection = self.resolve_projection(projection_path)
        lap("resources")

        configure_cycles_distribution(
            light,
            data.get("attenuation", ""),
            radius,
            bool(data.get("clampAttenuation", False)),
            ies_path=resolved_ies,
            projection_path=resolved_projection,
        )
        lap("distribution")

        context.operations.assign_custom_properties(
            obj,
            context.node,
            context.sector_name,
            cp77_node_data_index=instance.index,
            cp77_instance_idx=instance_index,
            type=cp77_type,
            unit=data.get("unit", ""),
            **static_light_settings(data),
            iesProfile=ies_path,
            cp77_resolved_ies_profile=resolved_ies,
            projectionTexture=projection_path,
            cp77_resolved_projection_texture=resolved_projection,
            areaShape=str(data.get("areaShape", "")),
            cp77_effective_radius=radius,
            sourceRadius=source_radius,
            capsuleLength=field_float(data, "capsuleLength", 0.0),
            contactShadows=str(data.get("contactShadows", "")),
            shadowSoftnessMode=str(data.get("shadowSoftnessMode", "")),
            attenuation=str(data.get("attenuation", "")),
            clampAttenuation=bool(data.get("clampAttenuation", 0)),
            spotCapsule=bool(data.get("spotCapsule", 0)),
            areaTwoSided=bool(data.get("areaTwoSided", 0)),
            envColorGroup=str(data.get("envColorGroup", "")),
            colorGroupSaturation=field_float(data, "colorGroupSaturation", 100.0),
            portalAngleCutoff=field_float(data, "portalAngleCutoff", 0.0),
            shadowAngle=field_float(data, "shadowAngle", -1.0),
            shadowRadius=field_float(data, "shadowRadius", -1.0),
            useInEnvProbes=bool(obj["useInEnvProbes"]),
            useInFog=bool(data.get("useInFog", 0)),
            useInGI=bool(data.get("useInGI", 0)),
            useInParticles=bool(data.get("useInParticles", 0)),
            useInTransparents=bool(data.get("useInTransparents", 1)),
            sceneDiffuse=field_float(data, "sceneDiffuse", 1.0),
            sceneSpecular=field_float(data, "sceneSpecular", 1.0),
            sceneSpecularScale=field_float(data, "sceneSpecularScale", 100.0),
            scaleEnvProbes=field_float(data, "scaleEnvProbes", 0.0),
            scaleGI=field_float(data, "scaleGI", 0.0),
            scaleVolFog=field_float(data, "scaleVolFog", 0.0),
            rayTracingIntensityScale=field_float(data, "rayTracingIntensityScale", 1.0),
            cp77_proxy_representation=representation,
        )
        capture_base_energy(obj)
        lap("metadata")

        proxy_children = create_proxy_samples(
            obj, representation, offsets, radius, resolved_ies, resolved_projection
        )
        for child in proxy_children:
            target_collection.objects.link(child)
            self._decorate_proxy(child, data)
        self._primary_lights += 1
        self._proxy_lights += len(proxy_children)
        lap("proxies")

        self._registry_objects.extend((obj, *proxy_children))
        lap("registry_queue")

        seed = static_light_flicker_seed(
            context.sector_name, context.node_index, instance_index
        )
        animate_flicker(light, data.get("flicker"), seed)
        for child in proxy_children:
            animate_flicker(
                child.data,
                data.get("flicker"),
                seed,
            )
        lap("flicker")
        self._create_seconds += time.perf_counter() - create_started
