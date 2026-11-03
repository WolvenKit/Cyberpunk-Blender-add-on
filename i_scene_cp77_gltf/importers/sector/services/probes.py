from __future__ import annotations

import bpy
from mathutils import Matrix, Vector

from ....assetio.transform_values import vector3_from_data
from ....assetio.values import coerce_float
from ....blender.naming import fit_id_name
from ....blender.transactions import track_created_datablock
from ...common.paths import depot_path
from ...common.reflection_probe_registry import register_reflection_probe
from ...common.reflection_probe_semantics import (
    scalar_edge_falloff,
    source_bool,
    source_float,
)


class ReflectionProbeService:
    def __init__(self, session):
        self.session = session

    @staticmethod
    def scale3(value):
        if isinstance(value, dict):
            return list(vector3_from_data(value, (1.0, 1.0, 1.0)))
        scalar = coerce_float(value, 1.0, unwrap=False)
        return [scalar, scalar, scalar]

    @staticmethod
    def color4(value, default=(1.0, 1.0, 1.0, 1.0)):
        if not isinstance(value, dict):
            return list(default)
        result = []
        for key, fallback in zip(("Red", "Green", "Blue", "Alpha"), default):
            result.append(
                coerce_float(
                    value.get(key, fallback), fallback, unwrap=False, finite=False
                )
            )
        return result

    @staticmethod
    def _configure_blender_probe(probe, data, edge_scale, global_probe, global_radius):
        near_clip = max(source_float(data, "nearClipDistance", 0.01), 1e-6)
        far_clip = max(source_float(data, "farClipDistance", 20.0), near_clip + 1e-6)
        probe.clip_start = near_clip
        probe.clip_end = far_clip
        probe.falloff = scalar_edge_falloff(edge_scale)
        probe.data_display_size = 0.2
        probe.show_clip = False
        if hasattr(probe, "show_influence"):
            probe.show_influence = False

        if global_probe:
            probe.influence_type = "ELIPSOID"
            probe.influence_distance = max(float(global_radius), 1.0)
        else:
            probe.influence_type = "BOX"
            probe.influence_distance = 1.0

        box_projection = source_bool(data, "boxProjection", False)
        probe.use_custom_parallax = box_projection
        if box_projection:
            probe.parallax_type = "BOX"
            probe.parallax_distance = (
                1.0 if not global_probe else max(float(global_radius), 1.0)
            )
        probe.show_parallax = False

    def create(self, context, instance, instance_index):
        data = context.data
        name = fit_id_name(f"{context.node_type}_{context.node_index}_{instance_index}")
        probe = track_created_datablock(
            "lightprobes",
            bpy.data.lightprobes.new(name, "SPHERE"),
        )
        obj = track_created_datablock("objects", bpy.data.objects.new(name, probe))
        context.collection_for_instance(instance).objects.link(obj)

        capture_offset = list(vector3_from_data(data.get("captureOffset", {})))
        edge_scale = self.scale3(data.get("edgeScale", {}))
        global_probe = source_bool(data, "globalProbe", False)
        streaming_distance = max(source_float(data, "streamingDistance", 0.0), 0.0)
        far_clip = max(source_float(data, "farClipDistance", 20.0), 0.0)
        global_radius = (
            streaming_distance if streaming_distance > 0.0 else max(far_clip, 1.0)
        )

        node_matrix = context.operations.instance_matrix(
            instance,
            context.execution.scale_factor,
        )
        node_location, node_rotation, _scale = node_matrix.decompose()
        if global_probe:
            obj.matrix_world = Matrix.LocRotScale(
                node_location,
                node_rotation,
                Vector((1.0, 1.0, 1.0)),
            )
        else:
            obj.matrix_world = node_matrix
        self._configure_blender_probe(
            probe,
            data,
            edge_scale,
            global_probe,
            global_radius,
        )

        brightness_ev = source_float(data, "brightnessEVClamp", 8.0)
        fog_color = self.color4(data.get("simpleFogColor", {}))

        context.operations.assign_custom_properties(
            obj,
            context.node,
            context.sector_name,
            cp77_node_data_index=instance.index,
            cp77_instance_idx=instance_index,
            cp77_reflection_probe=True,
            probeDataRef=depot_path(data, "probeDataRef"),
            captureOffset=capture_offset,
            edgeScale=edge_scale,
            priority=int(source_float(data, "priority", 0.0)),
            globalProbe=global_probe,
            boxProjection=source_bool(data, "boxProjection", False),
            nearClipDistance=source_float(data, "nearClipDistance", 0.01),
            farClipDistance=far_clip,
            streamingDistance=streaming_distance,
            streamingHeight=source_float(data, "streamingHeight", -1.0),
            blendRange=source_float(data, "blendRange", 0.0),
            emissiveScale=source_float(data, "emissiveScale", 1.0),
            reflectionDimming=source_float(data, "reflectionDimming", 1.0),
            skyScale=source_float(data, "skyScale", 1.0),
            simpleFogColor=fog_color,
            simpleFogDensity=source_float(data, "simpleFogDensity", 0.0),
            volFogAmbient=source_float(data, "volFogAmbient", 1.0),
            brightnessEVClamp=brightness_ev,
            ambientMode=str(data.get("ambientMode", "")),
            neighborMode=str(data.get("neighborMode", "")),
            noFadeBlend=source_bool(data, "noFadeBlend", False),
            allInShadow=source_bool(data, "allInShadow", False),
            hideSkyColor=source_bool(data, "hideSkyColor", False),
            lightChannels=str(data.get("lightChannels", "0")),
            volumeChannels=str(data.get("volumeChannels", "0")),
        )

        scene = getattr(bpy.context, "scene", None)
        if scene is not None:
            register_reflection_probe(scene, obj)
