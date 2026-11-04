from __future__ import annotations

import bpy

from ....blender.naming import fit_id_name
from ....blender.transactions import track_created_datablock
from ...common.paths import depot_path


class AcousticSectorService:
    def __init__(self, session):
        self.session = session

    def create(self, context, instance, instance_index):
        data = context.data
        name = fit_id_name(f"{context.node_type}_{context.node_index}_{instance_index}")
        obj = track_created_datablock(
            "objects",
            bpy.data.objects.new(
                name,
                self.session.primitive_meshes.centered_box(
                    "CP77_AcousticSector_32m",
                    (16.0, 16.0, 16.0),
                ),
            ),
        )
        context.collection_for_instance(instance).objects.link(obj)
        obj.matrix_world = context.operations.instance_matrix(
            instance,
            context.execution.scale_factor,
        )
        obj.display_type = "WIRE"
        obj.color = (0.2, 0.9, 0.4, 1.0)
        obj.show_wire = True

        context.operations.assign_custom_properties(
            obj,
            context.node,
            context.sector_name,
            cp77_node_data_index=instance.index,
            cp77_instance_idx=instance_index,
        )
        obj["acousticData"] = depot_path(data, "data")
        obj["generatorId"] = int(data.get("generatorId", 0) or 0)
        obj["edgeMask"] = int(data.get("edgeMask", 0) or 0)
        obj["inSectorCoords"] = [
            int(data.get("inSectorCoordsX", 0) or 0),
            int(data.get("inSectorCoordsY", 0) or 0),
            int(data.get("inSectorCoordsZ", 0) or 0),
        ]
