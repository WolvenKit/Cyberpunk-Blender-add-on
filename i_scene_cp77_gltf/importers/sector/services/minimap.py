from __future__ import annotations
from ....blender.transactions import track_created_datablock

from dataclasses import dataclass

import bpy

from ....assetio.values import axis_value


MINIMAP_PLACEMENT_CONTRACT = "EXACT_LOCAL_BOUNDS_RESOURCE_MARKER"



@dataclass(slots=True, frozen=True)
class MinimapResourceResult:
    depot_path: str
    resolved_path: str
    expected_path: str
    status: str


@dataclass(slots=True, frozen=True)
class MinimapBounds:
    minimum: tuple
    maximum: tuple
    valid: bool


@dataclass(slots=True, frozen=True)
class MinimapPlacement:
    object: object
    resource: MinimapResourceResult
    bounds: MinimapBounds


class MinimapResourceService:
    def __init__(self, session):
        self.session = session

    def resolve(self, depot_path):
        resolved = self.session.resource_resolver.resolve_json(
            "minimap",
            depot_path,
            ".cminimap.json",
        )
        return MinimapResourceResult(
            depot_path=resolved.depot_path,
            resolved_path=resolved.resolved_path,
            expected_path=resolved.expected_path,
            status=resolved.status,
        )

    @staticmethod
    def bounds(bounds):
        if not isinstance(bounds, dict):
            return MinimapBounds(
                minimum=(0.0, 0.0, 0.0),
                maximum=(0.0, 0.0, 0.0),
                valid=False,
            )

        minimum_data = bounds.get("Min")
        maximum_data = bounds.get("Max")
        minimum = (
            float(axis_value(minimum_data, "X")),
            float(axis_value(minimum_data, "Y")),
            float(axis_value(minimum_data, "Z")),
        )
        maximum = (
            float(axis_value(maximum_data, "X")),
            float(axis_value(maximum_data, "Y")),
            float(axis_value(maximum_data, "Z")),
        )
        valid = not any(
            maximum[index] < minimum[index]
            for index in range(3)
        )
        return MinimapBounds(
            minimum=minimum,
            maximum=maximum,
            valid=valid,
        )


    def create(self, context, instance, instance_index):
        data = context.data
        depot_path = context.operations.depot_path(
            data,
            "encodedShapesRef",
        )
        resource = self.resolve(depot_path)
        bounds = self.bounds(data.get("localBounds"))

        name = context.operations.trim_name(
            "MinimapData_"
            f"{context.operations.cname_value(data.get('debugName'), str(context.node_index))}_"
            f"{instance_index}"
        )
        mesh = (
            self.session.primitive_meshes.box(
                name,
                bounds.minimum,
                bounds.maximum,
                shared=False,
            )
            if bounds.valid
            else None
        )
        if mesh is None:
            context.operations.warning(
                f"{context.sector_name}: minimap data node "
                f"{context.node_index} has invalid localBounds"
            )

        obj = track_created_datablock("objects", bpy.data.objects.new(name, mesh))
        if mesh is None:
            obj.empty_display_type = "CUBE"
            obj.empty_display_size = 1.0
        context.sector_collection.objects.link(obj)
        obj.matrix_world = context.operations.instance_matrix(
            instance,
            context.execution.scale_factor,
        )
        obj.display_type = "WIRE"
        obj.color = (0.05, 0.75, 1.0, 1.0)
        obj.show_wire = mesh is not None

        context.operations.assign_custom_properties(
            obj,
            data,
            context.sector_name,
            context.node_index,
            nodeDataIndex=instance["nodeDataIndex"],
            instance_idx=instance_index,
            encodedShapesRef=resource.depot_path,
            resolvedEncodedShapes=resource.resolved_path,
            expectedEncodedShapes=resource.expected_path,
            minimapResourceStatus=resource.status,
            allInteriorShapes=bool(
                data.get("allInteriorShapes", 0)
            ),
            streamingDistance=float(
                data.get("streamingDistance", 0.0) or 0.0
            ),
            minimapRepresentation=MINIMAP_PLACEMENT_CONTRACT,
        )
        obj["minimapLocalBounds"] = (
            context.operations.safe_json(
                data.get("localBounds", {})
            )
        )
        obj["minimapNodeData"] = (
            context.operations.safe_json(data)
        )

        return MinimapPlacement(
            object=obj,
            resource=resource,
            bounds=bounds,
        )
