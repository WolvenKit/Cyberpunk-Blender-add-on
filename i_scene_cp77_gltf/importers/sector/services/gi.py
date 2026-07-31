from __future__ import annotations
from ....blender.transactions import track_created_datablock

from dataclasses import dataclass

import bpy


GI_PLACEMENT_CONTRACT = "GLOBAL_ILLUMINATION_RESOURCE_NODE_WORLD"



@dataclass(slots=True, frozen=True)
class GIResourceResult:
    depot_path: str
    resolved_path: str
    expected_path: str
    status: str


@dataclass(slots=True, frozen=True)
class GIPlacement:
    object: object
    resource: GIResourceResult


class GIResourceService:
    def __init__(self, session):
        self.session = session

    def resolve(self, depot_path):
        resolved = self.session.resource_resolver.resolve_json(
            "gi",
            depot_path,
            ".gidata.json",
        )
        return GIResourceResult(
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
        debug_name = context.operations.cname_value(
            data.get("debugName"),
            str(context.node_index),
        )
        name = context.operations.trim_name(
            f"{context.node_type}_{debug_name}_{instance_index}"
        )

        obj = track_created_datablock("objects", bpy.data.objects.new(name, None))
        obj.empty_display_type = "CUBE"
        obj.empty_display_size = 0.75
        obj.display_type = "WIRE"
        obj.color = (0.15, 0.9, 0.55, 1.0)
        context.sector_collection.objects.link(obj)
        obj.matrix_world = context.operations.instance_matrix(
            instance,
            context.execution.scale_factor,
        )

        location = data.get("location", {}).get(
            "Elements",
            [],
        )
        context.operations.assign_custom_properties(
            obj,
            data,
            context.sector_name,
            context.node_index,
            nodeDataIndex=instance["nodeDataIndex"],
            instance_idx=instance_index,
            semanticRepresentation=GI_PLACEMENT_CONTRACT,
            assetDepotPath=resource.depot_path,
            resolvedAssetPath=resource.resolved_path,
            expectedAssetPath=resource.expected_path,
            giResourceStatus=resource.status,
            giGridLocation=list(location),
        )
        obj["giNodeData"] = context.operations.safe_json(data)

        return GIPlacement(
            object=obj,
            resource=resource,
        )
