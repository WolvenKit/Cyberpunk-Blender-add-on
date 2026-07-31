from __future__ import annotations
from ....blender.transactions import track_created_datablock

from dataclasses import dataclass
import os

import bpy

from ...common.paths import depot_path_from_value
from ....assetio.values import nested_dict


SEMANTIC_MARKER_CONTRACTS = {
    "worldAISpotNode": "AI_SPOT_NODE_WORLD",
    "worldPopulationSpawnerNode": "POPULATION_SPAWNER_NODE_WORLD",
    "worldCompiledSmartObjectsNode": (
        "COMPILED_SMART_OBJECT_RESOURCE_NODE_WORLD"
    ),
    "worldSmartObjectNode": "SMART_OBJECT_NODE_WORLD",
    "worldStaticGpsLocationEntranceMarkerNode": (
        "GPS_LOCATION_ENTRANCE_MARKER_NODE_WORLD"
    ),
}


@dataclass(slots=True, frozen=True)
class SemanticMarkerSpec:
    display_type: str
    display_size: float
    color: tuple | None
    append_instance_index: bool
    wire_display: bool = True


SEMANTIC_MARKER_SPECS = {
    "worldAISpotNode": SemanticMarkerSpec(
        display_type="CONE",
        display_size=0.2,
        color=None,
        append_instance_index=False,
        wire_display=False,
    ),
    "worldPopulationSpawnerNode": SemanticMarkerSpec(
        display_type="PLAIN_AXES",
        display_size=1.0,
        color=(1.0, 0.005, 0.062, 1.0),
        append_instance_index=False,
    ),
    "worldCompiledSmartObjectsNode": SemanticMarkerSpec(
        display_type="CUBE",
        display_size=0.5,
        color=(1.0, 0.55, 0.1, 1.0),
        append_instance_index=True,
    ),
    "worldSmartObjectNode": SemanticMarkerSpec(
        display_type="CONE",
        display_size=0.4,
        color=(1.0, 0.35, 0.05, 1.0),
        append_instance_index=True,
    ),
    "worldStaticGpsLocationEntranceMarkerNode": SemanticMarkerSpec(
        display_type="ARROWS",
        display_size=0.7,
        color=(0.1, 1.0, 0.2, 1.0),
        append_instance_index=True,
    ),
}


@dataclass(slots=True, frozen=True)
class SemanticResourceResult:
    label: str
    kind: str
    depot_path: str
    resolved_path: str
    expected_path: str
    status: str
    warn_missing: bool


@dataclass(slots=True, frozen=True)
class SemanticPlacement:
    object: object
    resources: tuple[SemanticResourceResult, ...]



class SemanticMarkerService:
    def __init__(self, session):
        self.session = session

    @staticmethod
    def marker_spec(node_type):
        try:
            return SEMANTIC_MARKER_SPECS[node_type]
        except KeyError as error:
            raise ValueError(
                f"Unsupported semantic marker node type: {node_type}"
            ) from error

    @staticmethod
    def marker_contract(node_type):
        try:
            return SEMANTIC_MARKER_CONTRACTS[node_type]
        except KeyError as error:
            raise ValueError(
                f"Unsupported semantic marker node type: {node_type}"
            ) from error

    def resolve(
        self,
        *,
        label,
        kind,
        depot_path,
        warn_missing,
    ):
        normalized = str(depot_path or "")
        suffix = os.path.splitext(normalized)[1].lower()
        expected_extension = (
            f"{suffix}.json"
            if suffix
            else ".json"
        )
        resolved = self.session.resource_resolver.resolve_json(
            kind,
            normalized,
            expected_extension,
        )
        return SemanticResourceResult(
            label=label,
            kind=kind,
            depot_path=resolved.depot_path,
            resolved_path=resolved.resolved_path,
            expected_path=resolved.expected_path,
            status=resolved.status,
            warn_missing=bool(warn_missing),
        )

    @staticmethod
    def resource_requests(node_type, data):
        if node_type == "worldAISpotNode":
            spot_data = nested_dict(data, "spot", "Data")
            workspot = depot_path_from_value(
                spot_data.get("resource")
            )
            return (
                ("workspotTemplate", "workspot", workspot, False),
            ) if workspot else ()

        if node_type == "worldCompiledSmartObjectsNode":
            resource = depot_path_from_value(
                data.get("resource")
            )
            return (
                (
                    "compiledSmartObjects",
                    "smartobjects",
                    resource,
                    True,
                ),
            ) if resource else ()

        if node_type == "worldSmartObjectNode":
            smart_data = nested_dict(data, "object", "Data")
            requests = []
            workspot = depot_path_from_value(
                smart_data.get("workspotTemplate")
            )
            action_database = depot_path_from_value(
                smart_data.get("motionActionDatabase")
            )
            if workspot:
                requests.append(
                    (
                        "workspotTemplate",
                        "workspot",
                        workspot,
                        True,
                    )
                )
            if action_database:
                requests.append(
                    (
                        "motionActionDatabase",
                        "actionanimdb",
                        action_database,
                        True,
                    )
                )
            return tuple(requests)

        return ()

    def resources(self, node_type, data):
        return tuple(
            self.resolve(
                label=label,
                kind=kind,
                depot_path=depot_path,
                warn_missing=warn_missing,
            )
            for (
                label,
                kind,
                depot_path,
                warn_missing,
            ) in self.resource_requests(node_type, data)
        )

    @staticmethod
    def _name(
        node_type,
        debug_name,
        instance_index,
        spec,
    ):
        base = f"{node_type}_{debug_name}"
        return (
            f"{base}_{instance_index}"
            if spec.append_instance_index
            else base
        )

    @staticmethod
    def _resource_by_label(resources):
        return {
            resource.label: resource
            for resource in resources
        }

    def _node_properties(
        self,
        context,
        resources,
    ):
        data = context.data
        node_type = context.node_type
        properties = {
            "semanticRepresentation": self.marker_contract(node_type),
        }
        resources_by_label = self._resource_by_label(resources)

        if node_type == "worldAISpotNode":
            spot_data = nested_dict(data, "spot", "Data")
            spot_definition = nested_dict(
                data,
                "spotDef",
                "Data",
            )
            workspot = resources_by_label.get(
                "workspotTemplate"
            )
            properties.update({
                "workspotTemplate": (
                    workspot.depot_path if workspot else ""
                ),
                "resolvedWorkspotTemplate": (
                    workspot.resolved_path if workspot else ""
                ),
                "workspotResourceStatus": (
                    workspot.status if workspot else "NO_RESOURCE_PATH"
                ),
                "spotType": str(spot_data.get("$type", "")),
                "spotDefinitionType": str(
                    spot_definition.get("$type", "")
                ),
                "snapToGround": bool(
                    spot_data.get("snapToGround", 0)
                ),
                "useClippingSpace": bool(
                    spot_data.get("useClippingSpace", 0)
                ),
                "isWorkspotInfinite": bool(
                    data.get("isWorkspotInfinite", 0)
                ),
                "isWorkspotStatic": bool(
                    data.get("isWorkspotStatic", 0)
                ),
                "disableBumps": bool(
                    data.get("disableBumps", 0)
                ),
            })

        elif node_type == "worldPopulationSpawnerNode":
            properties.update({
                "appearanceName": context.operations.cname_value(
                    data.get("appearanceName")
                ),
                "objectRecordId": context.operations.cname_value(
                    data.get("objectRecordId")
                ),
                "spawnOnStart": bool(
                    data.get("spawnOnStart", 0)
                ),
                "spawnInView": str(
                    data.get("spawnInView", "")
                ),
                "alwaysSpawned": str(
                    data.get("alwaysSpawned", "")
                ),
                "prefetchAppearance": bool(
                    data.get("prefetchAppearance", 0)
                ),
                "isVehicle": bool(
                    data.get("isVehicle", 0)
                ),
            })

        elif node_type == "worldCompiledSmartObjectsNode":
            resource = resources_by_label.get(
                "compiledSmartObjects"
            )
            properties.update({
                "assetDepotPath": (
                    resource.depot_path if resource else ""
                ),
                "resolvedAssetPath": (
                    resource.resolved_path if resource else ""
                ),
                "expectedAssetPath": (
                    resource.expected_path if resource else ""
                ),
                "semanticResourceStatus": (
                    resource.status
                    if resource
                    else "NO_RESOURCE_PATH"
                ),
            })

        elif node_type == "worldSmartObjectNode":
            smart_data = nested_dict(data, "object", "Data")
            workspot = resources_by_label.get(
                "workspotTemplate"
            )
            action_database = resources_by_label.get(
                "motionActionDatabase"
            )
            properties.update({
                "workspotTemplate": (
                    workspot.depot_path if workspot else ""
                ),
                "resolvedWorkspotTemplate": (
                    workspot.resolved_path if workspot else ""
                ),
                "workspotResourceStatus": (
                    workspot.status
                    if workspot
                    else "NO_RESOURCE_PATH"
                ),
                "motionActionDatabase": (
                    action_database.depot_path
                    if action_database
                    else ""
                ),
                "resolvedMotionActionDatabase": (
                    action_database.resolved_path
                    if action_database
                    else ""
                ),
                "motionActionDatabaseStatus": (
                    action_database.status
                    if action_database
                    else "NO_RESOURCE_PATH"
                ),
                "smartObjectEnabled": bool(
                    smart_data.get("enabled", 0)
                ),
                "smartObjectType": str(
                    smart_data.get("$type", "")
                ),
            })

        return properties

    def create(self, context, instance, instance_index):
        data = context.data
        node_type = context.node_type
        spec = self.marker_spec(node_type)
        resources = self.resources(node_type, data)
        debug_name = context.operations.cname_value(
            data.get("debugName"),
            str(context.node_index),
        )
        name = context.operations.trim_name(
            self._name(
                node_type,
                debug_name,
                instance_index,
                spec,
            )
        )

        obj = track_created_datablock("objects", bpy.data.objects.new(name, None))
        obj.empty_display_type = spec.display_type
        obj.empty_display_size = float(spec.display_size)
        if spec.wire_display:
            obj.display_type = "WIRE"
        if spec.color is not None:
            obj.color = spec.color
        context.sector_collection.objects.link(obj)
        obj.matrix_world = context.operations.instance_matrix(
            instance,
            context.execution.scale_factor,
        )

        properties = self._node_properties(
            context,
            resources,
        )
        properties.update({
            "nodeDataIndex": instance["nodeDataIndex"],
            "instance_idx": instance_index,
        })
        context.operations.assign_custom_properties(
            obj,
            data,
            context.sector_name,
            context.node_index,
            **properties,
        )

        if node_type == "worldAISpotNode":
            obj["aiSpotData"] = context.operations.safe_json(
                data.get("spot", {})
            )
            obj["aiSpotDefinitionData"] = (
                context.operations.safe_json(
                    data.get("spotDef", {})
                )
            )
        elif node_type == "worldCompiledSmartObjectsNode":
            obj["compiledSmartObjectData"] = (
                context.operations.safe_json(data)
            )
        elif node_type == "worldSmartObjectNode":
            smart_data = nested_dict(
                data,
                "object",
                "Data",
            )
            obj["smartObjectActions"] = (
                context.operations.safe_json(
                    smart_data.get("actions", [])
                )
            )
            obj["smartObjectData"] = (
                context.operations.safe_json(smart_data)
            )
        elif (
            node_type
            == "worldStaticGpsLocationEntranceMarkerNode"
        ):
            obj["gpsMarkerData"] = (
                context.operations.safe_json(data)
            )

        for resource in resources:
            if (
                resource.warn_missing
                and resource.depot_path
                and not resource.resolved_path
            ):
                context.operations.warning(
                    f"{context.sector_name}: {node_type} node "
                    f"{context.node_index} {resource.label} not found: "
                    f"{resource.depot_path}"
                )

        return SemanticPlacement(
            object=obj,
            resources=resources,
        )
