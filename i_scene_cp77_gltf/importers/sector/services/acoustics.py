from __future__ import annotations
from ....blender.transactions import track_created_datablock

from dataclasses import dataclass

import bpy


ACOUSTIC_PLACEMENT_CONTRACT = "ACOUSTIC_SECTOR_GRID_CELL_32M"



@dataclass(slots=True, frozen=True)
class AcousticResourceResult:
    depot_path: str
    resolved_path: str
    expected_path: str
    status: str


@dataclass(slots=True, frozen=True)
class AcousticPlacement:
    object: object
    resource: AcousticResourceResult


class AcousticSectorService:
    def __init__(self, session):
        self.session = session

    def resolve(self, depot_path):
        resolved = self.session.resource_resolver.resolve_json(
            "acoustic",
            depot_path,
            ".acousticdata.json",
        )
        return AcousticResourceResult(
            depot_path=resolved.depot_path,
            resolved_path=resolved.resolved_path,
            expected_path=resolved.expected_path,
            status=resolved.status,
        )

    def create(self, context, instance, instance_index):
        data = context.data
        depot_path = context.operations.depot_path(
            data,
            "data",
        )
        resource = self.resolve(depot_path)

        name = context.operations.trim_name(
            f"{context.node_type}_{context.node_index}_{instance_index}"
        )
        obj = track_created_datablock("objects", bpy.data.objects.new(
            name,
            self.session.primitive_meshes.centered_box(
                "CP77_AcousticSector_32m",
                (16.0, 16.0, 16.0),
            ),
        ))
        context.sector_collection.objects.link(obj)
        obj.matrix_world = context.operations.instance_matrix(
            instance,
            context.execution.scale_factor,
        )
        obj.display_type = "WIRE"
        obj.color = (0.2, 0.9, 0.4, 1.0)
        obj.show_wire = True

        context.operations.assign_custom_properties(
            obj,
            data,
            context.sector_name,
            context.node_index,
            nodeDataIndex=instance["nodeDataIndex"],
            instance_idx=instance_index,
        )
        obj["acousticData"] = resource.depot_path
        obj["resolvedAcousticData"] = resource.resolved_path
        obj["acousticResourceStatus"] = resource.status
        obj["expectedAcousticData"] = resource.expected_path
        obj["representationApproximate"] = True
        obj["generatorId"] = int(
            data.get("generatorId", 0) or 0
        )
        obj["edgeMask"] = int(
            data.get("edgeMask", 0) or 0
        )
        obj["acousticSectorData"] = (
            context.operations.safe_json(data)
        )
        obj["inSectorCoords"] = [
            int(data.get("inSectorCoordsX", 0) or 0),
            int(data.get("inSectorCoordsY", 0) or 0),
            int(data.get("inSectorCoordsZ", 0) or 0),
        ]

        return AcousticPlacement(
            object=obj,
            resource=resource,
        )
