from __future__ import annotations

from dataclasses import dataclass

import bpy

from ....assetio.transform_values import vector3_from_data
from ....assetio.values import cname_text
from ....blender.naming import fit_id_name
from ....blender.transactions import track_created_datablock
from ...common.paths import depot_path


@dataclass(slots=True, frozen=True)
class MinimapBounds:
    minimum: tuple
    maximum: tuple
    valid: bool


class MinimapResourceService:
    def __init__(self, session):
        self.session = session

    @staticmethod
    def bounds(bounds):
        if not isinstance(bounds, dict):
            return MinimapBounds(
                minimum=(0.0, 0.0, 0.0),
                maximum=(0.0, 0.0, 0.0),
                valid=False,
            )

        minimum = vector3_from_data(bounds.get("Min"))
        maximum = vector3_from_data(bounds.get("Max"))
        valid = not any(maximum[index] < minimum[index] for index in range(3))
        return MinimapBounds(
            minimum=minimum,
            maximum=maximum,
            valid=valid,
        )

    def create(self, context, instance, instance_index):
        data = context.data
        bounds = self.bounds(data.get("localBounds"))

        name = fit_id_name(
            "MinimapData_"
            f"{cname_text(data.get('debugName'), str(context.node_index))}_"
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
        context.collection_for_instance(instance).objects.link(obj)
        obj.matrix_world = context.operations.instance_matrix(
            instance,
            context.execution.scale_factor,
        )
        obj.display_type = "WIRE"
        obj.color = (0.05, 0.75, 1.0, 1.0)
        obj.show_wire = mesh is not None

        context.operations.assign_custom_properties(
            obj,
            context.node,
            context.sector_name,
            cp77_node_data_index=instance.index,
            cp77_instance_idx=instance_index,
            encodedShapesRef=depot_path(data, "encodedShapesRef"),
            allInteriorShapes=bool(data.get("allInteriorShapes", 0)),
            streamingDistance=float(data.get("streamingDistance", 0.0) or 0.0),
        )
