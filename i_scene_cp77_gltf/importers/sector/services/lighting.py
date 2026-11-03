from __future__ import annotations
<<<<<<< Updated upstream
from ....blender.transactions import track_created_datablock

from dataclasses import dataclass
import math

import bpy
from bpy_extras import anim_utils
from mathutils import Matrix


STATIC_LIGHT_PLACEMENT_CONTRACT = "CP77_LIGHT_NODE_WORLD"
LIGHT_ENERGY_CONTRACT = "LUMINOUS_UNIT_TO_RADIOMETRIC_WATTS_683_LM_PER_W"
DIRECTIONAL_LIGHT_AXIS_CONTRACT = (
    "CP77_LOCAL_Y_TO_BLENDER_LOCAL_NEGATIVE_Z"
)


@dataclass(slots=True, frozen=True)
class StaticLightResult:
    object: object
    light: object
    cp77_type: str
    blender_type: str
    ies_path: str
    resolved_ies_path: str
    energy: float
    color: tuple

=======

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
>>>>>>> Stashed changes


class StaticLightingService:
    def __init__(self, session):
        self.session = session
<<<<<<< Updated upstream

    @staticmethod
    def temperature_rgb(kelvin):
        temperature = (
            max(1000.0, min(40000.0, float(kelvin)))
            / 100.0
        )
        if temperature <= 66.0:
            red = 255.0
            green = (
                99.4708025861 * math.log(temperature)
                - 161.1195681661
            )
            blue = (
                0.0
                if temperature <= 19.0
                else (
                    138.5177312231
                    * math.log(temperature - 10.0)
                    - 305.0447927307
                )
            )
        else:
            red = (
                329.698727446
                * ((temperature - 60.0) ** -0.1332047592)
            )
            green = (
                288.1221695283
                * ((temperature - 60.0) ** -0.0755148492)
            )
            blue = 255.0
        return tuple(
            max(0.0, min(1.0, value / 255.0))
            for value in (red, green, blue)
        )

    @classmethod
    def light_color(cls, data):
        color_data = data.get(
            "color",
            {"Red": 255, "Green": 255, "Blue": 255},
        )
        color = (
            float(color_data.get("Red", 255)) / 255.0,
            float(color_data.get("Green", 255)) / 255.0,
            float(color_data.get("Blue", 255)) / 255.0,
        )
        temperature = float(data.get("temperature", -1) or -1)
        if temperature > 0:
            temperature_color = cls.temperature_rgb(temperature)
            color = tuple(
                color[index] * temperature_color[index]
                for index in range(3)
            )
        return tuple(
            max(0.0, min(1.0, value))
            for value in color
        )

    @staticmethod
    def light_area(data):
        source_radius = max(
            0.0,
            float(data.get("sourceRadius", 0.0) or 0.0),
        )
        length = max(
            0.0,
            float(data.get("capsuleLength", 0.0) or 0.0),
        )
        side_a = max(
            0.0,
            float(data.get("areaRectSideA", 0.0) or 0.0),
        )
        side_b = max(
            0.0,
            float(data.get("areaRectSideB", 0.0) or 0.0),
        )
        if data.get("areaShape") == "ALS_Capsule":
            effective_radius = (
                source_radius
                if source_radius > 0.0
                else side_b * 0.5
            )
            return max(
                1e-6,
                (
                    length * (2.0 * effective_radius)
                    + math.pi * effective_radius * effective_radius
                ),
            )
        return max(1e-6, side_a * side_b)

    @classmethod
    def light_energy(cls, data):
        intensity = max(
            0.0,
            float(data.get("intensity", 0.0) or 0.0),
        )
        unit = str(data.get("unit", "LU_Lumen"))
        light_type = str(data.get("type", "LT_Point"))
        if unit == "LU_Lumen":
            lumens = intensity
        elif unit == "LU_Candela":
            if light_type == "LT_Spot":
                outer = max(
                    0.01,
                    min(
                        179.0,
                        float(data.get("outerAngle", 90.0) or 90.0),
                    ),
                )
                solid_angle = (
                    2.0
                    * math.pi
                    * (
                        1.0
                        - math.cos(math.radians(outer * 0.5))
                    )
                )
            else:
                solid_angle = 4.0 * math.pi
            lumens = intensity * solid_angle
        elif unit == "LU_Nit":
            lumens = intensity * cls.light_area(data) * math.pi
        else:
            lumens = intensity
        return lumens / 683.0
=======
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
>>>>>>> Stashed changes

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

<<<<<<< Updated upstream
    @staticmethod
    def animate_flicker(light, flicker):
        if not isinstance(flicker, dict):
            return False
        strength = max(
            0.0,
            float(flicker.get("flickerStrength", 0.0) or 0.0),
        )
        period = max(
            0.0,
            float(flicker.get("flickerPeriod", 0.0) or 0.0),
        )
        if strength <= 0.0 or period <= 0.0:
            return False

        scene = bpy.context.scene
        fps = (
            float(scene.render.fps)
            / max(float(scene.render.fps_base), 1e-8)
        )
        end_frame = 1 + max(2, round(period * fps))
        midpoint = 1 + max(1, (end_frame - 1) // 2)
        base_energy = float(light.energy)
        amplitude = min(strength, 1.0)
        for frame, energy in (
            (1, base_energy),
            (midpoint, base_energy * (1.0 - amplitude)),
            (end_frame, base_energy),
        ):
            light.energy = energy
            light.keyframe_insert("energy", frame=frame)

        action = (
            light.animation_data.action
            if light.animation_data
            else None
        )
        if action is None:
            return False
        try:
            channelbag = anim_utils.action_get_channelbag_for_slot(
                action,
                light.animation_data.action_slot,
            )
            fcurves = channelbag.fcurves
        except Exception:
            fcurves = getattr(action, "fcurves", ())

        for fcurve in fcurves:
            for point in fcurve.keyframe_points:
                point.interpolation = "LINEAR"
            if not any(
                modifier.type == "CYCLES"
                for modifier in fcurve.modifiers
            ):
                modifier = fcurve.modifiers.new(type="CYCLES")
                modifier.mode_before = "REPEAT"
                modifier.mode_after = "REPEAT"
        return True

    @staticmethod
    def _configure_shape(light, blender_type, data):
        source_radius = max(
            0.0,
            float(data.get("sourceRadius", 0.0) or 0.0),
        )
        radius = max(
            0.0,
            float(data.get("radius", 0.0) or 0.0),
        )

        if hasattr(light, "shadow_soft_size"):
            light.shadow_soft_size = source_radius
        if radius > 0.0 and hasattr(light, "use_custom_distance"):
            light.use_custom_distance = True
            light.cutoff_distance = radius

        if blender_type == "SPOT":
            outer = max(
                0.01,
                min(
                    179.0,
                    float(data.get("outerAngle", 90.0) or 90.0),
                ),
            )
            inner = max(
                0.0,
                min(
                    outer,
                    float(data.get("innerAngle", 0.0) or 0.0),
                ),
            )
            light.spot_size = math.radians(outer)
            light.spot_blend = max(
                0.0,
                min(1.0, 1.0 - inner / outer),
            )
        elif blender_type == "AREA":
            shape = str(data.get("areaShape", "ALS_Capsule"))
            capsule_length = max(
                0.001,
                float(data.get("capsuleLength", 0.0) or 0.0),
            )
            side_a = max(
                0.001,
                float(data.get("areaRectSideA", 1.0) or 1.0),
            )
            side_b = max(
                0.001,
                float(data.get("areaRectSideB", 1.0) or 1.0),
            )
            if shape == "ALS_Capsule":
                light.shape = "RECTANGLE"
                effective_source_radius = (
                    source_radius
                    if source_radius > 0.0
                    else side_b * 0.5
                )
                light.size = max(
                    side_a,
                    (
                        capsule_length
                        + 2.0 * effective_source_radius
                    ),
                )
                light.size_y = max(
                    side_b,
                    2.0 * effective_source_radius,
                )
            elif shape in {"ALS_Sphere", "ALS_Disc"}:
                light.shape = "DISK"
                light.size = max(side_a, 2.0 * radius)
            else:
                light.shape = "RECTANGLE"
                light.size = side_a
                light.size_y = side_b

        return radius, source_radius

    def create(self, context, instance, instance_index):
        data = context.data
        cp77_type = str(data.get("type", "LT_Point"))
        blender_type = {
            "LT_Point": "POINT",
            "LT_Spot": "SPOT",
            "LT_Area": "AREA",
        }.get(cp77_type, "POINT")
=======
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
>>>>>>> Stashed changes
        if cp77_type not in {"LT_Point", "LT_Spot", "LT_Area"}:
            context.operations.warning(
                f"{context.sector_name}: light node "
                f"{context.node_index} has unknown type {cp77_type}"
            )
<<<<<<< Updated upstream

        debug_name = context.operations.cname_value(
            data.get("debugName"),
            f"Light_{context.node_index}",
        )
        name = context.operations.trim_name(
            f"{context.node_index}_{debug_name}"
        )
        light = track_created_datablock("lights", bpy.data.lights.new(name, blender_type))
        obj = track_created_datablock("objects", bpy.data.objects.new(name, light))
        context.sector_collection.objects.link(obj)

        energy = self.light_energy(data)
        color = self.light_color(data)
        light.energy = energy
        light.color = color
        radius, source_radius = self._configure_shape(
            light,
            blender_type,
            data,
        )

        axis_matrix = (
            Matrix.Rotation(math.radians(90.0), 4, "X")
            if blender_type in {"SPOT", "AREA"}
=======
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
>>>>>>> Stashed changes
            else Matrix.Identity(4)
        )
        obj.matrix_world = (
            context.operations.instance_matrix(
                instance,
                context.execution.scale_factor,
            )
<<<<<<< Updated upstream
            @ axis_matrix
        )
        obj["lightAxisContract"] = (
            DIRECTIONAL_LIGHT_AXIS_CONTRACT
            if blender_type in {"SPOT", "AREA"}
            else "OMNIDIRECTIONAL"
        )

        ies_path = context.operations.depot_path(
            data,
            "iesProfile",
        )
        resolved_ies = self.resolve_ies(ies_path)

        context.operations.assign_custom_properties(
            obj,
            data,
            context.sector_name,
            context.node_index,
            nodeDataIndex=instance["nodeDataIndex"],
            instance_idx=instance_index,
            cp77LightType=cp77_type,
            cp77LightUnit=data.get("unit", ""),
            cp77Intensity=float(
                data.get("intensity", 0.0) or 0.0
            ),
            lightChannel=str(data.get("lightChannel", "")),
            iesProfile=ies_path,
            resolvedIESProfile=resolved_ies,
            areaShape=str(data.get("areaShape", "")),
            radius=radius,
            sourceRadius=source_radius,
            capsuleLength=float(
                data.get("capsuleLength", 0.0) or 0.0
            ),
            innerAngle=float(
                data.get("innerAngle", 0.0) or 0.0
            ),
            outerAngle=float(
                data.get("outerAngle", 0.0) or 0.0
            ),
            contactShadows=str(data.get("contactShadows", "")),
            enableLocalShadows=bool(
                data.get("enableLocalShadows", 0)
            ),
            shadowSoftnessMode=str(
                data.get("shadowSoftnessMode", "")
            ),
        )
        obj["lightEnergyContract"] = LIGHT_ENERGY_CONTRACT
        obj["iesIntegration"] = (
            "RESOLVED_METADATA"
            if resolved_ies
            else "UNRESOLVED_OR_NONE"
        )
        obj["cp77LightData"] = context.operations.safe_json(data)
        flicker_animated = self.animate_flicker(
            light,
            data.get("flicker"),
        )
        obj["flickerAnimated"] = flicker_animated

        return StaticLightResult(
            object=obj,
            light=light,
            cp77_type=cp77_type,
            blender_type=blender_type,
            ies_path=ies_path,
            resolved_ies_path=resolved_ies,
            energy=energy,
            color=color,
        )
=======
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
>>>>>>> Stashed changes
