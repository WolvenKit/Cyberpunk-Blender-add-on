from __future__ import annotations

import bpy

from ....assetio.values import cname_text
from ....blender.naming import fit_id_name
from ....blender.transactions import track_created_datablock


class GIResourceService:
    def __init__(self, session):
        self.session = session

    def create(self, context, instance, instance_index):
        data = context.data
        debug_name = cname_text(
            data.get("debugName"),
            str(context.node_index),
        )
        name = fit_id_name(f"{context.node_type}_{debug_name}_{instance_index}")

        obj = track_created_datablock("objects", bpy.data.objects.new(name, None))
        obj.empty_display_type = "CUBE"
        obj.empty_display_size = 0.75
        obj.display_type = "WIRE"
        obj.color = (0.15, 0.9, 0.55, 1.0)
        context.collection_for_instance(instance).objects.link(obj)
        obj.matrix_world = context.operations.instance_matrix(
            instance,
            context.execution.scale_factor,
        )

        context.operations.assign_custom_properties(
            obj,
            context.node,
            context.sector_name,
            cp77_node_data_index=instance.index,
            cp77_instance_idx=instance_index,
        )
