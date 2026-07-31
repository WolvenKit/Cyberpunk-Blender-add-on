from __future__ import annotations
from ....blender.transactions import track_created_datablock

from dataclasses import dataclass
import os

import bpy

from ...common.paths import normalize_depot_path
from ....assetio.values import axis_value


REFLECTION_PROBE_PLACEMENT_CONTRACT = (
    "REFLECTION_PROBE_BOX_NODE_WORLD"
)


@dataclass(slots=True, frozen=True)
class ReflectionProbeResult:
    object: object
    probe_path: str
    resolved_probe_path: str



class ReflectionProbeService:
    def __init__(self, session):
        self.session = session

    @staticmethod
    def vector3(value, default=(0.0, 0.0, 0.0)):
        if not isinstance(value, dict):
            return [
                float(default[0]),
                float(default[1]),
                float(default[2]),
            ]
        return [
            float(axis_value(value, "X", default[0])),
            float(axis_value(value, "Y", default[1])),
            float(axis_value(value, "Z", default[2])),
        ]

    @staticmethod
    def scale3(value):
        if isinstance(value, dict):
            return [
                float(axis_value(value, "X", 1.0)),
                float(axis_value(value, "Y", 1.0)),
                float(axis_value(value, "Z", 1.0)),
            ]
        try:
            scalar = float(value)
        except (TypeError, ValueError):
            scalar = 1.0
        return [scalar, scalar, scalar]

    def resolve_probe(self, depot_path):
        normalized = normalize_depot_path(depot_path)
        extension = os.path.splitext(normalized)[1].lower()
        expected_extension = (
            f"{extension}.json"
            if extension
            else ".json"
        )
        return self.session.resource_resolver.resolve_json(
            "environment_probe",
            normalized,
            expected_extension,
        ).resolved_path

    def create(self, context, instance, instance_index):
        data = context.data
        name = context.operations.trim_name(
            f"{context.node_type}_{context.node_index}_"
            f"{instance_index}"
        )
        obj = track_created_datablock("objects", bpy.data.objects.new(
            name,
            self.session.primitive_meshes.unit_box(
                "CP77_ReflectionProbe_UnitBox",
            ),
        ))
        context.sector_collection.objects.link(obj)
        obj.matrix_world = context.operations.instance_matrix(
            instance,
            context.execution.scale_factor,
        )
        obj.display_type = "WIRE"
        obj.color = (0.1, 0.8, 1.0, 1.0)
        obj.show_wire = True

        probe_path = context.operations.depot_path(
            data,
            "probeDataRef",
        )
        resolved_probe = self.resolve_probe(probe_path)
        capture_offset = self.vector3(
            data.get("captureOffset", {})
        )
        edge_scale = self.scale3(
            data.get("edgeScale", {})
        )

        context.operations.assign_custom_properties(
            obj,
            data,
            context.sector_name,
            context.node_index,
            nodeDataIndex=instance["nodeDataIndex"],
            instance_idx=instance_index,
            probeDataRef=probe_path,
            resolvedProbeData=resolved_probe,
            captureOffset=capture_offset,
            edgeScale=edge_scale,
            lightChannels=str(data.get("lightChannels", "")),
            volumeChannels=str(data.get("volumeChannels", "")),
            priority=int(data.get("priority", 0) or 0),
            blendRange=float(
                data.get("blendRange", 0.0) or 0.0
            ),
            boxProjection=bool(data.get("boxProjection", 0)),
        )
        obj["reflectionProbeData"] = (
            context.operations.safe_json(data)
        )
        return ReflectionProbeResult(
            object=obj,
            probe_path=probe_path,
            resolved_probe_path=resolved_probe,
        )
