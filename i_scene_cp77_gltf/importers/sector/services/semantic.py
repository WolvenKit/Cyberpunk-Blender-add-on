from __future__ import annotations
<<<<<<< Updated upstream
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
=======

import os
from dataclasses import dataclass

import bpy

from ....assetio.values import cname_text, nested_dict
from ....blender.naming import fit_id_name
from ....blender.transactions import track_created_datablock
from ...common.paths import depot_path_from_value
>>>>>>> Stashed changes


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


<<<<<<< Updated upstream
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



=======
>>>>>>> Stashed changes
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

<<<<<<< Updated upstream
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
=======
    def resolve(self, kind, depot_path):
        normalized = str(depot_path or "")
        suffix = os.path.splitext(normalized)[1].lower()
        expected_extension = f"{suffix}.json" if suffix else ".json"
        return self.session.resource_resolver.resolve_json(
>>>>>>> Stashed changes
            kind,
            normalized,
            expected_extension,
        )
<<<<<<< Updated upstream
        return SemanticResourceResult(
            label=label,
            kind=kind,
            depot_path=resolved.depot_path,
            resolved_path=resolved.resolved_path,
            expected_path=resolved.expected_path,
            status=resolved.status,
            warn_missing=bool(warn_missing),
        )
=======
>>>>>>> Stashed changes

    @staticmethod
    def resource_requests(node_type, data):
        if node_type == "worldAISpotNode":
            spot_data = nested_dict(data, "spot", "Data")
<<<<<<< Updated upstream
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
=======
            workspot = depot_path_from_value(spot_data.get("resource"))
            return (
                (("workspotTemplate", "cp77_workspot", workspot, False),)
                if workspot
                else ()
            )

        if node_type == "worldCompiledSmartObjectsNode":
            resource = depot_path_from_value(data.get("resource"))
            return (
                (
                    (
                        "compiledSmartObjects",
                        "smartobjects",
                        resource,
                        True,
                    ),
                )
                if resource
                else ()
            )
>>>>>>> Stashed changes

        if node_type == "worldSmartObjectNode":
            smart_data = nested_dict(data, "object", "Data")
            requests = []
<<<<<<< Updated upstream
            workspot = depot_path_from_value(
                smart_data.get("workspotTemplate")
            )
=======
            workspot = depot_path_from_value(smart_data.get("workspotTemplate"))
>>>>>>> Stashed changes
            action_database = depot_path_from_value(
                smart_data.get("motionActionDatabase")
            )
            if workspot:
                requests.append(
                    (
                        "workspotTemplate",
<<<<<<< Updated upstream
                        "workspot",
=======
                        "cp77_workspot",
>>>>>>> Stashed changes
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
<<<<<<< Updated upstream
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
=======
        """(label, whether a missing one is warned of, resolution) of each resource the node names"""
        return tuple(
            (label, warn_missing, self.resolve(kind, depot_path))
            for label, kind, depot_path, warn_missing in self.resource_requests(
                node_type, data
            )
>>>>>>> Stashed changes
        )

    @staticmethod
    def _name(
        node_type,
        debug_name,
        instance_index,
        spec,
    ):
        base = f"{node_type}_{debug_name}"
<<<<<<< Updated upstream
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
=======
        return f"{base}_{instance_index}" if spec.append_instance_index else base

    @staticmethod
    def _resource_by_label(resources):
        return {label: resource for label, _warn_missing, resource in resources}
>>>>>>> Stashed changes

    def _node_properties(
        self,
        context,
        resources,
    ):
        data = context.data
        node_type = context.node_type
<<<<<<< Updated upstream
        properties = {
            "semanticRepresentation": self.marker_contract(node_type),
        }
=======
        properties = {}
>>>>>>> Stashed changes
        resources_by_label = self._resource_by_label(resources)

        if node_type == "worldAISpotNode":
            spot_data = nested_dict(data, "spot", "Data")
            spot_definition = nested_dict(
                data,
                "spotDef",
                "Data",
            )
<<<<<<< Updated upstream
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
=======
            workspot = resources_by_label.get("workspotTemplate")
            properties.update(
                {
                    "workspotTemplate": (workspot.depot_path if workspot else ""),
                    "spotType": str(spot_data.get("$type", "")),
                    "spotDefinitionType": str(spot_definition.get("$type", "")),
                    "snapToGround": bool(spot_data.get("snapToGround", 0)),
                    "useClippingSpace": bool(spot_data.get("useClippingSpace", 0)),
                    "isWorkspotInfinite": bool(data.get("isWorkspotInfinite", 0)),
                    "isWorkspotStatic": bool(data.get("isWorkspotStatic", 0)),
                    "disableBumps": bool(data.get("disableBumps", 0)),
                }
            )

        elif node_type == "worldPopulationSpawnerNode":
            properties.update(
                {
                    "appearanceName": cname_text(data.get("appearanceName")),
                    "objectRecordId": cname_text(data.get("objectRecordId")),
                    "spawnOnStart": bool(data.get("spawnOnStart", 0)),
                    "spawnInView": str(data.get("spawnInView", "")),
                    "alwaysSpawned": str(data.get("alwaysSpawned", "")),
                    "prefetchAppearance": bool(data.get("prefetchAppearance", 0)),
                    "isVehicle": bool(data.get("isVehicle", 0)),
                }
            )

        elif node_type == "worldSmartObjectNode":
            smart_data = nested_dict(data, "object", "Data")
            workspot = resources_by_label.get("workspotTemplate")
            action_database = resources_by_label.get("motionActionDatabase")
            properties.update(
                {
                    "workspotTemplate": (workspot.depot_path if workspot else ""),
                    "motionActionDatabase": (
                        action_database.depot_path if action_database else ""
                    ),
                    "smartObjectEnabled": bool(smart_data.get("enabled", 0)),
                    "smartObjectType": str(smart_data.get("$type", "")),
                }
            )
>>>>>>> Stashed changes

        return properties

    def create(self, context, instance, instance_index):
        data = context.data
        node_type = context.node_type
        spec = self.marker_spec(node_type)
        resources = self.resources(node_type, data)
<<<<<<< Updated upstream
        debug_name = context.operations.cname_value(
            data.get("debugName"),
            str(context.node_index),
        )
        name = context.operations.trim_name(
=======
        debug_name = cname_text(
            data.get("debugName"),
            str(context.node_index),
        )
        name = fit_id_name(
>>>>>>> Stashed changes
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
<<<<<<< Updated upstream
        context.sector_collection.objects.link(obj)
=======
        context.collection_for_instance(instance).objects.link(obj)
>>>>>>> Stashed changes
        obj.matrix_world = context.operations.instance_matrix(
            instance,
            context.execution.scale_factor,
        )

        properties = self._node_properties(
            context,
            resources,
        )
<<<<<<< Updated upstream
        properties.update({
            "nodeDataIndex": instance["nodeDataIndex"],
            "instance_idx": instance_index,
        })
        context.operations.assign_custom_properties(
            obj,
            data,
            context.sector_name,
            context.node_index,
=======
        properties.update(
            {
                "cp77_node_data_index": instance.index,
                "cp77_instance_idx": instance_index,
            }
        )
        context.operations.assign_custom_properties(
            obj,
            context.node,
            context.sector_name,
>>>>>>> Stashed changes
            **properties,
        )

        if node_type == "worldAISpotNode":
<<<<<<< Updated upstream
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
=======
            obj["aiSpotData"] = context.session.safe_json(data.get("spot", {}))
            obj["aiSpotDefinitionData"] = context.session.safe_json(
                data.get("spotDef", {})
>>>>>>> Stashed changes
            )
        elif node_type == "worldSmartObjectNode":
            smart_data = nested_dict(
                data,
                "object",
                "Data",
            )
<<<<<<< Updated upstream
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
=======
            obj["smartObjectData"] = context.session.safe_json(smart_data)

        for label, warn_missing, resource in resources:
            if warn_missing and resource.depot_path and not resource.resolved_path:
                context.operations.warning(
                    f"{context.sector_name}: {node_type} node "
                    f"{context.node_index} {label} not found: "
                    f"{resource.depot_path}"
                )
>>>>>>> Stashed changes
