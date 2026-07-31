from __future__ import annotations
from ....blender.transactions import track_created_datablock

from dataclasses import dataclass
import os

import bpy


EFFECT_PLACEMENT_CONTRACT = "EFFECT_RESOURCE_MARKER_NODE_WORLD"

_EFFECT_RESOURCE_KEY = {
    "worldStaticParticleNode": ("particle", "particleSystem"),
    "worldEffectNode": ("effect", "effect"),
}



@dataclass(slots=True, frozen=True)
class EffectResourceResult:
    resource_kind: str
    depot_path: str
    resolved_path: str
    expected_path: str
    status: str


@dataclass(slots=True, frozen=True)
class EffectPlacement:
    object: object
    resource: EffectResourceResult


class EffectResourceService:
    def __init__(self, session):
        self.session = session

    @staticmethod
    def resource_contract(node_type):
        try:
            return _EFFECT_RESOURCE_KEY[node_type]
        except KeyError as error:
            raise ValueError(
                f"Unsupported effect node type: {node_type}"
            ) from error

    def resolve(self, node_type, depot_path):
        resource_kind, _ = self.resource_contract(node_type)
        normalized = str(depot_path or "")
        extension = os.path.splitext(normalized)[1].lower()
        expected_extension = (
            f"{extension}.json"
            if extension
            else f".{resource_kind}.json"
        )
        resolved = self.session.resource_resolver.resolve_json(
            resource_kind,
            normalized,
            expected_extension,
        )
        return EffectResourceResult(
            resource_kind=resource_kind,
            depot_path=resolved.depot_path,
            resolved_path=resolved.resolved_path,
            expected_path=resolved.expected_path,
            status=resolved.status,
        )

    def create(self, context, instance, instance_index):
        data = context.data
        resource_kind, resource_key = self.resource_contract(
            context.node_type
        )
        depot_path = context.operations.depot_path(
            data,
            resource_key,
        )
        resource = self.resolve(
            context.node_type,
            depot_path,
        )

        debug_name = context.operations.cname_value(
            data.get("debugName"),
            str(context.node_index),
        )
        name = context.operations.trim_name(
            f"{context.node_type}_{debug_name}_{instance_index}"
        )
        obj = track_created_datablock("objects", bpy.data.objects.new(name, None))
        obj.empty_display_type = "SPHERE"
        obj.empty_display_size = 0.5
        context.sector_collection.objects.link(obj)
        obj.matrix_world = context.operations.instance_matrix(
            instance,
            context.execution.scale_factor,
        )
        obj.display_type = "WIRE"
        obj.color = (1.0, 0.005, 0.062, 1.0)

        context.operations.assign_custom_properties(
            obj,
            data,
            context.sector_name,
            context.node_index,
            nodeDataIndex=instance["nodeDataIndex"],
            instance_idx=instance_index,
            effectResourceKind=resource_kind,
            assetDepotPath=resource.depot_path,
            resolvedAssetPath=resource.resolved_path,
            expectedAssetPath=resource.expected_path,
            effectResourceStatus=resource.status,
            emissionRate=float(
                data.get("emissionRate", 0.0) or 0.0
            ),
            forcedAutoHideDistance=float(
                data.get("forcedAutoHideDistance", -1.0) or -1.0
            ),
            forcedAutoHideRange=float(
                data.get("forcedAutoHideRange", -1.0) or -1.0
            ),
            streamingDistanceOverride=float(
                data.get("streamingDistanceOverride", 0.0) or 0.0
            ),
            isHostOnly=bool(data.get("isHostOnly", 0)),
            isVisibleInGame=bool(
                data.get("isVisibleInGame", 1)
            ),
            sourcePrefabHash=str(
                data.get("sourcePrefabHash", "")
            ),
            tag=str(data.get("tag", "")),
            tagExt=str(data.get("tagExt", "")),
        )
        obj["effectNodeData"] = context.operations.safe_json(data)

        return EffectPlacement(
            object=obj,
            resource=resource,
        )
