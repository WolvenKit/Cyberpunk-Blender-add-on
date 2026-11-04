from __future__ import annotations

import os

import bpy

from ....assetio.values import cname_text
from ....blender.naming import fit_id_name
from ....blender.transactions import track_created_datablock
from ...common.paths import depot_path

_EFFECT_RESOURCE_KEY = {
    "worldStaticParticleNode": ("particle", "particleSystem"),
    "worldEffectNode": ("effect", "effect"),
}


class EffectResourceService:
    def __init__(self, session):
        self.session = session

    @staticmethod
    def resource_contract(node_type):
        try:
            return _EFFECT_RESOURCE_KEY[node_type]
        except KeyError as error:
            raise ValueError(f"Unsupported effect node type: {node_type}") from error

    def resolve(self, node_type, path):
        resource_kind, _ = self.resource_contract(node_type)
        normalized = str(path or "")
        extension = os.path.splitext(normalized)[1].lower()
        expected_extension = (
            f"{extension}.json" if extension else f".{resource_kind}.json"
        )
        return self.session.resource_resolver.resolve_json(
            resource_kind,
            normalized,
            expected_extension,
        )

    def create(self, context, instance, instance_index):
        data = context.data
        _resource_kind, resource_key = self.resource_contract(context.node_type)
        resource = self.resolve(
            context.node_type,
            depot_path(data, resource_key),
        )

        debug_name = cname_text(
            data.get("debugName"),
            str(context.node_index),
        )
        name = fit_id_name(f"{context.node_type}_{debug_name}_{instance_index}")
        obj = track_created_datablock("objects", bpy.data.objects.new(name, None))
        obj.empty_display_type = "SPHERE"
        obj.empty_display_size = 0.5
        context.collection_for_instance(instance).objects.link(obj)
        obj.matrix_world = context.operations.instance_matrix(
            instance,
            context.execution.scale_factor,
        )
        obj.display_type = "WIRE"
        obj.color = (1.0, 0.005, 0.062, 1.0)

        context.operations.assign_custom_properties(
            obj,
            context.node,
            context.sector_name,
            cp77_node_data_index=instance.index,
            cp77_instance_idx=instance_index,
            emissionRate=float(data.get("emissionRate", 0.0) or 0.0),
            forcedAutoHideDistance=float(
                data.get("forcedAutoHideDistance", -1.0) or -1.0
            ),
            forcedAutoHideRange=float(data.get("forcedAutoHideRange", -1.0) or -1.0),
            streamingDistanceOverride=float(
                data.get("streamingDistanceOverride", 0.0) or 0.0
            ),
            isHostOnly=bool(data.get("isHostOnly", 0)),
            isVisibleInGame=bool(data.get("isVisibleInGame", 1)),
            sourcePrefabHash=str(data.get("sourcePrefabHash", "")),
            tag=str(data.get("tag", "")),
            tagExt=str(data.get("tagExt", "")),
        )
        if resource.status == "RESOURCE_NOT_INDEXED":
            context.operations.warning(
                f"{context.sector_name}: {context.node_type} node "
                f"{context.node_index} resource not indexed: "
                f"{resource.depot_path}"
            )
