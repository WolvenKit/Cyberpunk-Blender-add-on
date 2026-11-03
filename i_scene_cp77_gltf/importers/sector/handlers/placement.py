from __future__ import annotations

import hashlib
import json
import os

from ..context import (
    DeformationDataError,
    FoliageResourceError,
    SectorContentError,
)
from ..options import OPTIONAL_SECTOR_NODE_TYPES
from ..registry import NODE_HANDLERS


STANDARD_PHASE = 20
PROXY_PHASE = 30
OCCLUDER_TRANSFORM_CONTRACT = "EMBEDDED_OCCLUDER_MATRIX_ABSOLUTE"

ENTITY_NODE_TYPES = frozenset({
    "worldEntityNode",
    "worldDeviceNode",
})

STANDARD_COPIED_MESH_NODE_TYPES = frozenset({
    "worldStaticMeshNode",
    "worldRotatingMeshNode",
    "worldPhysicalDestructionNode",
    "worldBakedDestructionNode",
    "worldAdvertisingNode",
    "worldAdvertisementNode",
    "worldStaticOccluderMeshNode",
    "worldTerrainMeshNode",
    "worldClothMeshNode",
    "worldDecorationMeshNode",
    "worldDynamicMeshNode",
    "worldMeshNode",
    "worldWaterPatchNode",
})

PROXY_COPIED_MESH_NODE_TYPES = frozenset(
    OPTIONAL_SECTOR_NODE_TYPES["proxies"]
)


def _assign_placement_metadata(context, obj, contract, handler_name):
    context.operations.assign_id_properties(
        obj,
        placementContract=contract,
        placementHandler=handler_name,
        placementPhase=context.plan.placement_phase,
    )


class EntityPlacementHandler:
    placement_phase = STANDARD_PHASE

    def place(self, context):
        data = context.data
        requested = context.node.entity_appearance or "default"
        ent_depot = context.node.entity_template_path
        entity_master = context.session.master_assets.entities.require(
            context.masters,
            ent_depot,
            requested,
        )

        resolved = entity_master.resolved_appearance
        if resolved != requested:
            print(
                f"Entity appearance resolved: {requested} -> {resolved}"
            )

        placed = 0
        for instance_index, instance in enumerate(context.instances):
            node_matrix = context.operations.instance_matrix(
                instance,
                context.execution.scale_factor,
            )
            instance_name = (
                f'ENT_{instance["nodeDataIndex"]}_'
                f'{os.path.basename(ent_depot).split(".")[0]}_'
                f'{entity_master.identity}'
            )
            new, placement_root, _ = (
                context.operations.copy_collection_tree_with_placement_root(
                    entity_master.collection,
                    instance_name,
                    node_matrix,
                    color=(0.567942, 0.0247339, 0.600028, 1),
                    hide_armatures=True,
                )
            )
            shared_properties = {
                "nodeDataIndex": instance["nodeDataIndex"],
                "instance_idx": instance_index,
                "entityTemplate": ent_depot,
                "requestedAppearance": requested,
                "resolvedAppearance": resolved,
                "placementHandler": type(self).__name__,
                "placementPhase": context.plan.placement_phase,
            }
            context.operations.assign_custom_properties(
                new,
                data,
                context.sector_name,
                context.node_index,
                HandleId=context.node.handle_id,
                pivot=instance.get("Pivot", {}),
                **shared_properties,
            )
            context.operations.assign_custom_properties(
                placement_root,
                data,
                context.sector_name,
                context.node_index,
                **shared_properties,
            )
            matrix_values = context.operations.matrix_values(node_matrix)
            new["matrix"] = matrix_values
            placement_root["matrix"] = matrix_values
            context.sector_collection.children.link(new)
            placed += 1

        context.record_placements(placed)
        return placed


class CopiedMeshPlacementHandler:
    def __init__(self, placement_phase):
        self.placement_phase = int(placement_phase)

    @staticmethod
    def _proxy_properties(context, *, road):
        data = context.data
        properties = {
            "proxySemantic": True,
            "proxyOwnerResolved": False,
            "nearAutoHideDistance": float(
                data.get("nearAutoHideDistance", 0.0) or 0.0
            ),
            "forceAutoHideDistance": float(
                data.get("forceAutoHideDistance", 0.0) or 0.0
            ),
            "lodLevelScales": int(data.get("lodLevelScales", 0) or 0),
            "occluderType": str(data.get("occluderType", "")),
            "renderSceneLayerMask": str(
                data.get("renderSceneLayerMask", "")
            ),
            "nbNodesUnderProxy": int(
                data.get("nbNodesUnderProxy", 0) or 0
            ),
            "proxyData": context.operations.safe_json(data),
        }
        if not road:
            owner_global_id = (
                context.operations.nested_value(
                    data,
                    "ownerGlobalId",
                    "hash",
                    default="",
                )
                or data.get("ownerHash", "")
            )
            properties.update({
                "proxyOwnerGlobalId": str(owner_global_id),
                "entityAttachDistance": float(
                    data.get("entityAttachDistance", 0.0) or 0.0
                ),
            })
        return properties

    @staticmethod
    def _contract(node_type):
        return {
            "worldRoadProxyMeshNode": "ROAD_PROXY_MESH_NODE_WORLD",
            "worldStaticMeshNode": "STATIC_MESH_NODE_WORLD",
            "worldRotatingMeshNode": "ROTATING_MESH_PLACEMENT_ROOT",
            "worldPhysicalDestructionNode": (
                "PHYSICAL_DESTRUCTION_NODE_WORLD"
            ),
            "worldBakedDestructionNode": (
                "BAKED_DESTRUCTION_NODE_WORLD"
            ),
        }.get(node_type, f"{node_type}_NODE_WORLD")

    def _extra_properties(self, context):
        data = context.data
        node_type = context.node_type
        properties = {
            "placementHandler": type(self).__name__,
            "placementPhase": context.plan.placement_phase,
        }

        if node_type == "worldPhysicalDestructionNode":
            properties.update({
                "destructionSemantic": "physical",
                "destructionParams": json.dumps(
                    data.get("destructionParams", {}),
                    separators=(",", ":"),
                ),
            })
        elif node_type == "worldBakedDestructionNode":
            properties["destructionSemantic"] = "baked"

        if (
            node_type in {"worldAdvertisingNode", "worldAdvertisementNode"}
            and "lightData" in data
        ):
            properties["lightData"] = json.dumps(
                data["lightData"],
                separators=(",", ":"),
            )

        if node_type == "worldWaterPatchNode":
            properties.update({
                "waterPatchDepth": float(data.get("depth", 0.0) or 0.0),
                "waterPatchType": context.operations.cname_value(
                    context.operations.nested_value(
                        data,
                        "type",
                        "typeName",
                        default={},
                    )
                ),
                "generateNavmesh": bool(data.get("generateNavmesh", 0)),
                "waterPatchVersion": int(data.get("version", 0) or 0),
                "waterPatchData": context.operations.safe_json(data),
            })

        if context.node_type in PROXY_COPIED_MESH_NODE_TYPES:
            properties.update(self._proxy_properties(
                context,
                road=context.node_type == "worldRoadProxyMeshNode",
            ))

        if node_type == "worldRotatingMeshNode":
            properties.update({
                "rot_axis": data.get("rotationAxis", "Z"),
                "reverseDirection": bool(data.get("reverseDirection", 0)),
                "fullRotationTime": float(
                    data.get("fullRotationTime", 0.0)
                ),
            })
        return properties

    def place(self, context):
        meshname = context.node.mesh_path
        if not meshname:
            raise SectorContentError(
                f"{context.node_type} has no mesh resource"
            )

        rotating = context.node_type == "worldRotatingMeshNode"
        placed = context.operations.place_copied_mesh_instances(
            data=context.data,
            node_entry=context.node_entry,
            node_index=context.node_index,
            instances=context.instances,
            sector_name=context.sector_name,
            sector_collection=context.sector_collection,
            masters=context.masters,
            master_assets=context.session.master_assets,
            meshname=meshname,
            mesh_appearance=context.node.mesh_appearance,
            contract=self._contract(context.node_type),
            scale=context.execution.scale_factor,
            rotating=rotating,
            extra_props=self._extra_properties(context),
        )

        if rotating:
            data = context.data
            for _, _, rotation_root, instance, instance_index in placed:
                if rotation_root is None:
                    context.operations.warning(
                        f"{context.sector_name}: rotating node "
                        f"{context.node_index} did not create a rotation root"
                    )
                    continue
                context.operations.assign_custom_properties(
                    rotation_root,
                    data,
                    context.sector_name,
                    context.node_index,
                    nodeDataIndex=instance["nodeDataIndex"],
                    instance_idx=instance_index,
                    rotationAxis=data.get("rotationAxis", "Z"),
                    reverseDirection=bool(
                        data.get("reverseDirection", 0)
                    ),
                    fullRotationTime=float(
                        data.get("fullRotationTime", 0.0)
                    ),
                    placementHandler=type(self).__name__,
                    placementPhase=context.plan.placement_phase,
                )
                rotation_root["rotationContract"] = (
                    "LOCAL_AXIS_UNDER_PLACEMENT_ROOT"
                )
                context.operations.animate_rotation_root(
                    rotation_root,
                    data.get("rotationAxis", "Z"),
                    data.get("fullRotationTime", 0.0),
                    data.get("reverseDirection", 0),
                )

        if context.node_type == "worldClothMeshNode":
            for new, placement_root, _, instance, _ in placed:
                if "windImpulseEnabled" not in instance:
                    continue
                new["windImpulseEnabled"] = instance["windImpulseEnabled"]
                placement_root["windImpulseEnabled"] = (
                    instance["windImpulseEnabled"]
                )

        context.record_placements(len(placed))
        return len(placed)


class InstancedMeshPlacementHandler:
    placement_phase = STANDARD_PHASE

    def place(self, context):
        meshname = context.node.mesh_path
        if not meshname:
            raise SectorContentError(
                f"{context.node_type} has no mesh resource"
            )
        if len(context.instances) > 1:
            context.operations.warning(
                f"{context.sector_name}: node {context.node_index} has "
                f"{len(context.instances)} nodeData records, but "
                "worldTransformsBuffer entries are absolute and are emitted "
                "only once"
            )

        group, groupname = context.session.master_assets.get_mesh_master(
            context.masters,
            meshname,
            context.node.mesh_appearance,
        )
        if group is None:
            raise SectorContentError(
                f"Mesh not found in masters - {meshname} - "
                f"{context.node_index} - {context.node.handle_id}"
            )

        buffer_slice = context.transform_buffers.world_slice(context)
        source = context.instances[0] if context.instances else None
        node_data_index = (
            source.get("nodeDataIndex")
            if source is not None
            else None
        )
        collection = context.operations.new_collection(
            context.operations.trim_name(
                f"NDI{context.node_index}_{groupname}"
            )
        )
        context.sector_collection.children.link(collection)

        properties = {
            "mesh": meshname,
            "numElements": buffer_slice.declared_count,
            "bufferStart": buffer_slice.start,
            "bufferRef": buffer_slice.reference_id,
            "placementContract": buffer_slice.contract,
            "placementHandler": type(self).__name__,
            "placementPhase": context.plan.placement_phase,
        }
        if node_data_index is not None:
            properties["nodeDataIndex"] = node_data_index
        context.operations.assign_custom_properties(
            collection,
            context.data,
            context.sector_name,
            context.node_index,
            **properties,
        )

        placed = 0
        for element_index, raw_transform in buffer_slice.entries:
            matrix = context.operations.instance_matrix(
                raw_transform,
                context.execution.scale_factor,
            )
            instance = context.operations.collection_instance_object(
                f"NDI{context.node_index}_{element_index}_{groupname}",
                group,
                collection,
                matrix,
                color=(0.785188, 0.409408, 0.0430124, 1),
            )
            object_properties = {
                "mesh": meshname,
                "Element_idx": element_index,
                "placementContract": buffer_slice.contract,
                "placementHandler": type(self).__name__,
                "placementPhase": context.plan.placement_phase,
            }
            if node_data_index is not None:
                object_properties["nodeDataIndex"] = node_data_index
            context.operations.assign_custom_properties(
                instance,
                context.data,
                context.sector_name,
                context.node_index,
                **object_properties,
            )
            if buffer_slice.reference_id:
                instance["bufferID"] = buffer_slice.reference_id
            placed += 1

        context.record_placements(
            placed,
            expected=buffer_slice.actual_count,
        )
        return placed


class InstancedOccluderPlacementHandler:
    placement_phase = STANDARD_PHASE

    def place(self, context):
        meshname = context.node.mesh_path
        if not meshname:
            raise SectorContentError(
                f"{context.node_type} has no mesh resource"
            )
        if len(context.instances) > 1:
            context.operations.warning(
                f"{context.sector_name}: instanced occluder node "
                f"{context.node_index} has {len(context.instances)} "
                "nodeData records; embedded buffer matrices are absolute "
                "and are emitted once"
            )

        group, groupname = context.session.master_assets.get_mesh_master(
            context.masters,
            meshname,
            context.node.mesh_appearance,
        )
        if group is None:
            raise SectorContentError(
                f"Mesh not found in masters - {meshname} - "
                f"{context.node_index} - {context.node.handle_id}"
            )

        records = context.transform_buffers.occluder_records(context.data)
        source = context.instances[0] if context.instances else None
        node_data_index = (
            source.get("nodeDataIndex")
            if source is not None
            else -1
        )
        collection = context.operations.new_collection(
            context.operations.trim_name(
                f"InstancedOccluder_{context.node_index}_{groupname}"
            )
        )
        context.sector_collection.children.link(collection)
        context.operations.assign_custom_properties(
            collection,
            context.data,
            context.sector_name,
            context.node_index,
            mesh=meshname,
            numElements=len(records),
            nodeDataIndex=node_data_index,
            placementContract=OCCLUDER_TRANSFORM_CONTRACT,
            placementHandler=type(self).__name__,
            placementPhase=context.plan.placement_phase,
        )

        placed = 0
        normalized_frames = 0
        for element_index, record in enumerate(records):
            try:
                matrix = context.transform_buffers.occluder_matrix(record)
            except (TypeError, ValueError) as error:
                context.operations.warning(
                    f"{context.sector_name}: instanced occluder node "
                    f"{context.node_index} element {element_index} is "
                    f"invalid: {error}"
                )
                continue
            if context.transform_buffers.has_noncanonical_homogeneous_frame(
                record
            ):
                normalized_frames += 1

            instance = context.operations.collection_instance_object(
                f"InstancedOccluder_{context.node_index}_"
                f"{element_index}_{groupname}",
                group,
                collection,
                matrix,
                color=(0.35, 0.15, 0.05, 1.0),
            )
            context.operations.assign_custom_properties(
                instance,
                context.data,
                context.sector_name,
                context.node_index,
                mesh=meshname,
                Element_idx=element_index,
                nodeDataIndex=node_data_index,
                autohideDistanceScale=int(
                    context.data.get("autohideDistanceScale", 0) or 0
                ),
                occluderType=str(
                    context.data.get("occluderType", "")
                ),
                placementContract=OCCLUDER_TRANSFORM_CONTRACT,
                placementHandler=type(self).__name__,
                placementPhase=context.plan.placement_phase,
            )
            placed += 1

        collection["normalizedHomogeneousFrames"] = normalized_frames
        context.record_placements(placed, expected=len(records))
        return placed


class InstancedDestructiblePlacementHandler:
    placement_phase = STANDARD_PHASE

    def place(self, context):
        meshname = context.node.mesh_path
        if not meshname:
            raise SectorContentError(
                f"{context.node_type} has no mesh resource"
            )
        group, groupname = context.session.master_assets.get_mesh_master(
            context.masters,
            meshname,
            context.node.mesh_appearance,
        )
        if group is None:
            raise SectorContentError(
                f"Mesh not found in masters - {meshname} - "
                f"{context.node_index} - {context.node.handle_id}"
            )

        buffer_slice = context.transform_buffers.cooked_slice(context)
        appearance_name = context.operations.cname_value(
            context.data.get("appearanceName"),
            context.node.mesh_appearance,
        )

        placed = 0
        for top_level_index, source in enumerate(context.instances):
            node_matrix = context.operations.instance_matrix(
                source,
                context.execution.scale_factor,
            )
            collection = context.operations.new_collection(
                context.operations.trim_name(
                    f'wIDMn{source["nodeDataIndex"]}_{groupname}'
                )
            )
            context.sector_collection.children.link(collection)
            context.operations.assign_custom_properties(
                collection,
                context.data,
                context.sector_name,
                context.node_index,
                nodeDataIndex=source["nodeDataIndex"],
                mesh=meshname,
                pivot=source.get("Pivot", {}),
                numElements=buffer_slice.declared_count,
                bufferStart=buffer_slice.start,
                bufferRef=buffer_slice.reference_id,
                appearanceName=appearance_name,
                placementContract=buffer_slice.contract,
                placementHandler=type(self).__name__,
                placementPhase=context.plan.placement_phase,
            )

            for element_index, raw_transform in buffer_slice.entries:
                local_matrix = context.operations.instance_matrix(
                    raw_transform
                )
                final_matrix = node_matrix @ local_matrix
                instance = context.operations.collection_instance_object(
                    f'wIDMi{source["nodeDataIndex"]}_'
                    f"{element_index}_{groupname}",
                    group,
                    collection,
                    final_matrix,
                    color=(0.3, 0.3, 0.3, 1),
                )
                context.operations.assign_custom_properties(
                    instance,
                    context.data,
                    context.sector_name,
                    context.node_index,
                    nodeDataIndex=source["nodeDataIndex"],
                    mesh=meshname,
                    Element_idx=element_index,
                    tl_instance_idx=top_level_index,
                    sub_instance_idx=element_index,
                    appearanceName=appearance_name,
                    placementContract=buffer_slice.contract,
                    placementHandler=type(self).__name__,
                    placementPhase=context.plan.placement_phase,
                )
                instance["pivot"] = source.get("Pivot", {})
                if buffer_slice.reference_id:
                    instance["bufferID"] = buffer_slice.reference_id
                placed += 1

        context.record_placements(
            placed,
            expected=len(context.instances) * buffer_slice.actual_count,
        )
        return placed


class FoliagePlacementHandler:
    placement_phase = STANDARD_PHASE

    def place(self, context):
        meshname = context.node.mesh_path
        if not meshname:
            raise SectorContentError(
                f"{context.node_type} has no mesh resource"
            )
        foliage_resource = context.node.foliage_resource_path
        if not foliage_resource:
            raise SectorContentError(
                f"{context.node_type} has no foliage resource"
            )

        group, groupname = context.session.master_assets.get_mesh_master(
            context.masters,
            meshname,
            context.node.mesh_appearance,
        )
        if group is None:
            raise SectorContentError(
                f"{context.sector_name}: foliage mesh not found in masters: "
                f"{meshname} - node {context.node_index}"
            )

        try:
            selection = context.foliage_assets.select(
                foliage_resource,
                context.data.get("populationSpanInfo", {}),
                sector_name=context.sector_name,
                node_index=context.node_index,
                warning=context.operations.warning,
            )
        except FoliageResourceError as error:
            raise SectorContentError(str(error)) from error

        resource = selection.resource
        placed = 0
        for source in context.instances:
            node_matrix = context.operations.instance_matrix(
                source,
                context.execution.scale_factor,
            )
            collection = context.operations.new_collection(
                context.operations.trim_name(
                    f'WFI_{source["nodeDataIndex"]}_{groupname}'
                )
            )
            context.sector_collection.children.link(collection)
            context.operations.assign_custom_properties(
                collection,
                context.data,
                context.sector_name,
                context.node_index,
                nodeDataIndex=source["nodeDataIndex"],
                mesh=meshname,
                foliageResource=foliage_resource,
                resolvedFoliagePath=resource.resolved_path,
                bucketBegin=selection.bucket_begin,
                bucketCount=selection.bucket_count,
                instancesBegin=selection.instances_begin,
                instancesCount=selection.instances_count,
                resolvedPopulationCount=selection.resolved_count,
                emittedPopulationCount=selection.active_count,
                inactivePopulationCount=len(selection.inactive),
                inactivePopulationDigest=selection.inactive_digest,
                resourceBucketCount=len(resource.buckets),
                resourcePopulationCount=len(resource.populations),
                resourceDeclaredBucketCount=(
                    resource.declared_bucket_count
                ),
                resourceDeclaredPopulationCount=(
                    resource.declared_population_count
                ),
                resourceVersion=resource.version,
                placementContract=(
                    "NODE_WORLD_X_FOLIAGE_POPULATION_LOCAL"
                ),
                placementHandler=type(self).__name__,
                placementPhase=context.plan.placement_phase,
            )

            for (
                bucket_index,
                population_index,
                relative_index,
            ) in selection.active:
                population = resource.populations[population_index]
                population_matrix = (
                    context.foliage_assets.population_matrix(population)
                )
                final_matrix = node_matrix @ population_matrix
                instance = context.operations.collection_instance_object(
                    f'WFI_{source["nodeDataIndex"]}_'
                    f"{population_index}_{groupname}",
                    group,
                    collection,
                    final_matrix,
                    color=(0.0, 1.0, 0.0, 1),
                )
                context.operations.assign_custom_properties(
                    instance,
                    context.data,
                    context.sector_name,
                    context.node_index,
                    nodeDataIndex=source["nodeDataIndex"],
                    mesh=meshname,
                    Element_idx=population_index,
                    populationIndex=population_index,
                    populationLocalIndex=relative_index,
                    bucketIndex=bucket_index,
                    populationScale=(
                        context.foliage_assets.population_scale(population)
                    ),
                    foliageResource=foliage_resource,
                    placementContract=(
                        "NODE_WORLD_X_FOLIAGE_POPULATION_LOCAL"
                    ),
                    placementHandler=type(self).__name__,
                    placementPhase=context.plan.placement_phase,
                )
                placed += 1

        context.record_placements(
            placed,
            expected=len(context.instances) * selection.active_count,
        )
        return placed


class GIPlacementHandler:
    placement_phase = STANDARD_PHASE
    placement_contract = "GLOBAL_ILLUMINATION_RESOURCE_NODE_WORLD"

    def place(self, context):
        placed = 0
        for instance_index, instance in enumerate(context.instances):
            result = context.gi_assets.create(
                context,
                instance,
                instance_index,
            )
            _assign_placement_metadata(
                context,
                result.object,
                self.placement_contract,
                type(self).__name__,
            )
            placed += 1
        context.record_placements(placed)
        return placed


class CollisionMetadataPlacementHandler:
    placement_phase = STANDARD_PHASE

    def place(self, context):
        options = context.session.options
        if not options.import_collisions:
            context.record_placements(0, expected=0)
            return 0
        if (
            context.node_type == "worldFoliageDestructionNode"
            and not options.import_foliage
        ):
            context.record_placements(0, expected=0)
            return 0
        contract = context.collision_metadata_assets.contract(
            context.node_type
        )
        placed = 0
        for instance_index, instance in enumerate(context.instances):
            result = context.collision_metadata_assets.create(
                context,
                instance,
                instance_index,
            )
            _assign_placement_metadata(
                context,
                result.object,
                contract,
                type(self).__name__,
            )
            placed += 1
        context.record_placements(placed)
        return placed


class WorldCollisionPlacementHandler:
    placement_phase = STANDARD_PHASE

    def place(self, context):
        if not context.session.options.import_collisions:
            context.record_placements(0, expected=0)
            return 0
        placed = int(
            context.operations.place_world_collision_node(context)
        )
        context.record_placements(
            placed,
            expected=placed,
        )
        return placed


class ExplicitNoOpPlacementHandler:
    placement_phase = STANDARD_PHASE

    def place(self, context):
        context.record_placements(0, expected=0)
        return 0


class SplinePlacementHandler:
    placement_phase = STANDARD_PHASE

    def place(self, context):
        placed = 0
        contract = context.spline_assets.contract(
            context.node_type
        )
        for instance_index, instance in enumerate(context.instances):
            result = context.spline_assets.create(
                context,
                instance,
                instance_index,
            )
            if result is None:
                continue
            _assign_placement_metadata(
                context,
                result.object,
                contract,
                type(self).__name__,
            )
            placed += 1

        context.record_placements(placed)
        return placed


class SemanticMarkerPlacementHandler:
    placement_phase = STANDARD_PHASE

    def place(self, context):
        placed = 0
        contract = (
            context.semantic_assets.marker_contract(
                context.node_type
            )
        )
        for instance_index, instance in enumerate(context.instances):
            result = context.semantic_assets.create(
                context,
                instance,
                instance_index,
            )
            _assign_placement_metadata(
                context,
                result.object,
                contract,
                type(self).__name__,
            )
            placed += 1

        context.record_placements(placed)
        return placed


class AcousticSectorPlacementHandler:
    placement_phase = STANDARD_PHASE
    placement_contract = "ACOUSTIC_SECTOR_GRID_CELL_32M"

    def place(self, context):
        placed = 0
        for instance_index, instance in enumerate(context.instances):
            result = context.acoustic_assets.create(
                context,
                instance,
                instance_index,
            )
            _assign_placement_metadata(
                context,
                result.object,
                self.placement_contract,
                type(self).__name__,
            )
            placed += 1

        context.record_placements(placed)
        return placed


class MinimapPlacementHandler:
    placement_phase = STANDARD_PHASE
    placement_contract = "EXACT_LOCAL_BOUNDS_RESOURCE_MARKER"

    def place(self, context):
        placed = 0
        for instance_index, instance in enumerate(context.instances):
            result = context.minimap_assets.create(
                context,
                instance,
                instance_index,
            )
            _assign_placement_metadata(
                context,
                result.object,
                self.placement_contract,
                type(self).__name__,
            )
            placed += 1

        context.record_placements(placed)
        return placed


class EffectPlacementHandler:
    placement_phase = STANDARD_PHASE
    placement_contract = "EFFECT_RESOURCE_MARKER_NODE_WORLD"

    def place(self, context):
        placed = 0
        for instance_index, instance in enumerate(context.instances):
            result = context.effect_assets.create(
                context,
                instance,
                instance_index,
            )
            _assign_placement_metadata(
                context,
                result.object,
                self.placement_contract,
                type(self).__name__,
            )
            if result.resource.status == "RESOURCE_NOT_INDEXED":
                context.operations.warning(
                    f"{context.sector_name}: {context.node_type} node "
                    f"{context.node_index} resource not indexed: "
                    f"{result.resource.depot_path}"
                )
            placed += 1

        context.record_placements(placed)
        return placed


class StaticLightPlacementHandler:
    placement_phase = STANDARD_PHASE
    placement_contract = "CP77_LIGHT_NODE_WORLD"

    def place(self, context):
        placed = 0
        for instance_index, instance in enumerate(context.instances):
            result = context.lighting_assets.create(
                context,
                instance,
                instance_index,
            )
            _assign_placement_metadata(
                context,
                result.object,
                self.placement_contract,
                type(self).__name__,
            )
            placed += 1

        context.record_placements(placed)
        return placed


class ReflectionProbePlacementHandler:
    placement_phase = STANDARD_PHASE
    placement_contract = "REFLECTION_PROBE_BOX_NODE_WORLD"

    def place(self, context):
        placed = 0
        for instance_index, instance in enumerate(context.instances):
            result = context.probe_assets.create(
                context,
                instance,
                instance_index,
            )
            _assign_placement_metadata(
                context,
                result.object,
                self.placement_contract,
                type(self).__name__,
            )
            placed += 1

        context.record_placements(placed)
        return placed


class StaticDecalPlacementHandler:
    placement_phase = STANDARD_PHASE
    placement_contract = "DECAL_PROJECTOR_LOCAL_Z_UNIT_PLANE"

    def place(self, context):
        data = context.data
        placed = 0
        for instance_index, instance in enumerate(context.instances):
            result = context.decal_assets.create(
                context,
                instance,
                instance_index,
            )
            material_result = result.material_result
            properties = {
                "instance_idx": instance_index,
                "nodeDataIndex": instance["nodeDataIndex"],
                "decal": material_result.material_path,
                "resolvedDecalMaterial": (
                    material_result.resolved_path
                ),
                "decalMaterialStatus": material_result.status,
                "decalMaterialError": material_result.error,
                "horizontalFlip": bool(
                    data.get("horizontalFlip", 0)
                ),
                "verticalFlip": bool(
                    data.get("verticalFlip", 0)
                ),
                "alpha": float(data.get("alpha", 1.0)),
                "roughnessScale": float(
                    data.get("roughnessScale", 1.0)
                ),
                "isStretchingEnabled": bool(
                    data.get("isStretchingEnabled", 0)
                ),
                "orderNo": int(data.get("orderNo", 0)),
                "normalThreshold": float(
                    data.get("normalThreshold", 0.0)
                ),
                "enableNormalThreshold": bool(
                    data.get("enableNormalTreshold", 0)
                ),
                "projectionDepth": float(
                    context.operations.instance_scale(instance)[2]
                ),
                "projectionAxisLocal": "Z",
                "placementContract": self.placement_contract,
                "placementHandler": type(self).__name__,
                "placementPhase": context.plan.placement_phase,
            }
            context.operations.assign_custom_properties(
                result.plane,
                data,
                context.sector_name,
                context.node_index,
                **properties,
            )
            context.operations.assign_custom_properties(
                result.projector,
                data,
                context.sector_name,
                context.node_index,
                **properties,
            )
            context.execution.track_matrix_object(result.projector)
            context.execution.track_matrix_object(result.plane)

            if material_result.status == "MATERIAL_NOT_INDEXED":
                context.operations.warning(
                    f"{context.sector_name}: decal node "
                    f"{context.node_index} material not found: "
                    f"{material_result.expected_path}"
                )
            elif material_result.status in {
                "INVALID_MATERIAL_DOCUMENT",
                "BUILDER_RETURNED_NONE",
                "MATERIAL_BUILD_FAILED",
            }:
                context.operations.warning(
                    f"{context.sector_name}: decal node "
                    f"{context.node_index} material import failed "
                    f"({material_result.status}): "
                    f"{material_result.error}"
                )
            placed += 1

        context.record_placements(placed)
        return placed


class WorldMetadataPlacementHandler:
    placement_phase = STANDARD_PHASE

    OUTLINE_TYPES = frozenset({
        "worldTriggerAreaNode",
        "gameKillTriggerNode",
        "worldAmbientAreaNode",
        "worldLightChannelVolumeNode",
        "gameWorldBoundaryNode",
        "worldGISpaceNode",
        "worldInteriorAreaNode",
    })

    CONTRACTS = {
        "worldTriggerAreaNode": "TRIGGER_OUTLINE_VOLUME_NODE_WORLD",
        "gameKillTriggerNode": "KILL_TRIGGER_OUTLINE_VOLUME_NODE_WORLD",
        "worldAmbientAreaNode": "AMBIENT_OUTLINE_VOLUME_NODE_WORLD",
        "worldLightChannelVolumeNode": (
            "LIGHT_CHANNEL_OUTLINE_VOLUME_NODE_WORLD"
        ),
        "gameWorldBoundaryNode": (
            "WORLD_BOUNDARY_OUTLINE_VOLUME_NODE_WORLD"
        ),
        "worldGISpaceNode": "GI_SPACE_OUTLINE_VOLUME_NODE_WORLD",
        "worldInteriorAreaNode": (
            "INTERIOR_OUTLINE_VOLUME_NODE_WORLD"
        ),
        "worldInteriorMapNode": (
            "INTERIOR_MAP_RASTER_METADATA_NODE_WORLD"
        ),
        "worldLightChannelShapeNode": (
            "LIGHT_CHANNEL_SHAPE_NODE_WORLD"
        ),
        "worldStaticFogVolumeNode": (
            "STATIC_FOG_VOLUME_NODE_WORLD"
        ),
        "worldStaticSoundEmitterNode": (
            "STATIC_SOUND_EMITTER_NODE_WORLD"
        ),
    }

    def _outline_metadata(self, context, obj):
        data = context.data
        node_type = context.node_type
        if node_type == "worldLightChannelVolumeNode":
            obj["lightChannels"] = str(data.get("channels", ""))
            obj["streamingDistanceFactor"] = float(
                data.get("streamingDistanceFactor", 0.0) or 0.0
            )
        elif node_type == "worldAmbientAreaNode":
            notifier_settings = (
                data.get("notifiers", [{}])[0]
                .get("Data", {})
                .get("Settings", {})
                if data.get("notifiers")
                else {}
            )
            events = context.world_metadata_assets.audio_events(
                notifier_settings,
                context.operations.cname_value,
            )
            obj["audioEvents"] = context.operations.safe_json(events)
            obj["useCustomColor"] = bool(
                data.get("useCustomColor", 0)
            )
        elif node_type == "worldGISpaceNode":
            obj["giGroup"] = str(data.get("group", ""))
            obj["giPriority"] = int(data.get("priority", 0) or 0)
            obj["giInterior"] = bool(data.get("interior", 0))
            obj["giRuntime"] = bool(data.get("runtime", 0))
        elif node_type == "worldInteriorAreaNode":
            obj["interiorAreaNotifiers"] = (
                context.operations.safe_json(data.get("notifiers", []))
            )
        elif node_type == "gameWorldBoundaryNode":
            obj["worldBoundaryData"] = (
                context.operations.safe_json(data)
            )

    def _create(self, context, instance, instance_index):
        node_type = context.node_type
        service = context.world_metadata_assets
        if node_type in self.OUTLINE_TYPES:
            obj = service.create_outline_volume(
                context,
                instance,
                instance_index,
            )
            if obj is not None:
                self._outline_metadata(context, obj)
            return obj
        if node_type == "worldInteriorMapNode":
            return service.create_interior_map(
                context,
                instance,
                instance_index,
            )
        if node_type == "worldLightChannelShapeNode":
            return service.create_light_channel_shape(
                context,
                instance,
                instance_index,
            )
        if node_type == "worldStaticFogVolumeNode":
            return service.create_fog_volume(
                context,
                instance,
                instance_index,
            )
        if node_type == "worldStaticSoundEmitterNode":
            return service.create_sound_emitter(
                context,
                instance,
                instance_index,
            )
        raise SectorContentError(
            f"Unsupported world metadata node type: {node_type}"
        )

    def place(self, context):
        contract = self.CONTRACTS[context.node_type]
        placed = 0
        for instance_index, instance in enumerate(context.instances):
            obj = self._create(context, instance, instance_index)
            if obj is None:
                continue
            _assign_placement_metadata(
                context,
                obj,
                contract,
                type(self).__name__,
            )
            placed += 1

        context.record_placements(placed)
        return placed


class DeformedMeshPlacementHandler:
    placement_phase = STANDARD_PHASE

    def place(self, context):
        meshname = context.node.mesh_path
        if not meshname:
            raise SectorContentError(
                f"{context.sector_name}: deformation node "
                f"{context.node_index} has no mesh resource"
            )

        group, groupname = context.session.master_assets.get_mesh_master(
            context.masters,
            meshname,
            context.node.mesh_appearance,
        )
        try:
            analysis = context.deformation_assets.analyze(
                context.node_type,
                context.data,
                group,
                sector_name=context.sector_name,
                node_index=context.node_index,
                handle_id=context.node.handle_id,
                meshname=meshname,
                warning=context.operations.warning,
            )
        except DeformationDataError as error:
            raise SectorContentError(str(error)) from error

        data = context.data
        cable_radius = float(data.get("cableRadius", 0.0) or 0.0)
        metrics = analysis.metrics
        deformation_payload = context.operations.safe_json(
            data.get("deformationData", [])
        )
        deformation_digest = hashlib.sha1(
            deformation_payload.encode("utf-8")
        ).hexdigest()

        placed = 0
        for instance_index, instance in enumerate(context.instances):
            node_matrix = context.operations.instance_matrix(
                instance,
                context.execution.scale_factor,
            )
            prefix = (
                "BEND"
                if context.node_type == "worldBendedMeshNode"
                else "CABLE"
            )
            instance_name = context.operations.trim_name(
                f'{prefix}_{instance["nodeDataIndex"]}_'
                f'{groupname or context.node_index}'
            )
            result = context.deformation_assets.instantiate(
                group,
                instance_name,
                node_matrix,
                analysis,
                context.operations,
                cable_radius=cable_radius,
            )

            properties = {
                "nodeDataIndex": instance["nodeDataIndex"],
                "instance_idx": instance_index,
                "mesh": meshname,
                "meshAppearance": context.node.mesh_appearance,
                "deformationAxis": analysis.contract.axis_name,
                "deformationFrameCount": len(analysis.frames),
                "deformationSourceVertexCount": (
                    analysis.source_vertex_count
                ),
                "deformationSourceAxisMin": (
                    analysis.source_axis_min
                ),
                "deformationSourceAxisMax": (
                    analysis.source_axis_max
                ),
                "deformationFrameAxisMin": (
                    metrics.contract_axis_min
                ),
                "deformationFrameAxisMax": (
                    metrics.contract_axis_max
                ),
                "deformationMinimumFrameStep": (
                    metrics.minimum_frame_step
                ),
                "deformationMaximumFrameStep": (
                    metrics.maximum_frame_step
                ),
                "deformationFramesMonotonic": (
                    metrics.monotonic_contract_axis
                ),
                "deformationDominantAxis": (
                    "XYZ"[metrics.dominant_axis_index]
                ),
                "deformationNormalizedHomogeneousFrames": (
                    metrics.normalized_homogeneous_frames
                ),
                "isBendedRoad": bool(data.get("isBendedRoad", 0)),
                "deformedBox": context.operations.safe_json(
                    data.get("deformedBox", {})
                ),
                "placementContract": "FRAME_MATRIX_VERTEX_BAKE",
                "placementHandler": type(self).__name__,
                "placementPhase": context.plan.placement_phase,
            }
            if context.node_type == "worldCableMeshNode":
                properties.update({
                    "cableLength": float(
                        data.get("cableLength", 0.0) or 0.0
                    ),
                    "cableRadius": cable_radius,
                    "destructionHashes": (
                        context.operations.safe_json(
                            data.get("destructionHashes", [])
                        )
                    ),
                })

            context.operations.assign_custom_properties(
                result.collection,
                data,
                context.sector_name,
                context.node_index,
                **properties,
            )
            context.operations.assign_custom_properties(
                result.placement_root,
                data,
                context.sector_name,
                context.node_index,
                **properties,
            )
            if result.path_object is not None:
                context.operations.assign_custom_properties(
                    result.path_object,
                    data,
                    context.sector_name,
                    context.node_index,
                    **properties,
                )

            result.collection["deformationContract"] = (
                "FRAME_MATRIX_VERTEX_BAKE"
            )
            result.collection["deformationDataDigest"] = (
                deformation_digest
            )
            result.collection["deformationFallbackCurveRendered"] = (
                result.rendered_fallback_curve
            )
            if analysis.frames:
                result.collection["deformationFirstFrame"] = (
                    context.operations.matrix_values(
                        analysis.frames[0]
                    )
                )
                result.collection["deformationLastFrame"] = (
                    context.operations.matrix_values(
                        analysis.frames[-1]
                    )
                )

            context.sector_collection.children.link(result.collection)
            placed += 1

        context.record_placements(placed)
        return placed


ENTITY_PLACEMENT_HANDLER = EntityPlacementHandler()
STANDARD_COPIED_MESH_HANDLER = CopiedMeshPlacementHandler(STANDARD_PHASE)
PROXY_COPIED_MESH_HANDLER = CopiedMeshPlacementHandler(PROXY_PHASE)
INSTANCED_MESH_PLACEMENT_HANDLER = InstancedMeshPlacementHandler()
INSTANCED_OCCLUDER_PLACEMENT_HANDLER = InstancedOccluderPlacementHandler()
INSTANCED_DESTRUCTIBLE_PLACEMENT_HANDLER = (
    InstancedDestructiblePlacementHandler()
)
FOLIAGE_PLACEMENT_HANDLER = FoliagePlacementHandler()
DEFORMED_MESH_PLACEMENT_HANDLER = DeformedMeshPlacementHandler()
WORLD_METADATA_PLACEMENT_HANDLER = WorldMetadataPlacementHandler()
STATIC_DECAL_PLACEMENT_HANDLER = StaticDecalPlacementHandler()
STATIC_LIGHT_PLACEMENT_HANDLER = StaticLightPlacementHandler()
REFLECTION_PROBE_PLACEMENT_HANDLER = ReflectionProbePlacementHandler()
EFFECT_PLACEMENT_HANDLER = EffectPlacementHandler()
ACOUSTIC_SECTOR_PLACEMENT_HANDLER = AcousticSectorPlacementHandler()
MINIMAP_PLACEMENT_HANDLER = MinimapPlacementHandler()
SEMANTIC_MARKER_PLACEMENT_HANDLER = SemanticMarkerPlacementHandler()
SPLINE_PLACEMENT_HANDLER = SplinePlacementHandler()
GI_PLACEMENT_HANDLER = GIPlacementHandler()
COLLISION_METADATA_PLACEMENT_HANDLER = (
    CollisionMetadataPlacementHandler()
)
WORLD_COLLISION_PLACEMENT_HANDLER = WorldCollisionPlacementHandler()
EXPLICIT_NO_OP_PLACEMENT_HANDLER = ExplicitNoOpPlacementHandler()

NODE_HANDLERS.register_placement(
    ENTITY_PLACEMENT_HANDLER,
    *ENTITY_NODE_TYPES,
)
NODE_HANDLERS.register_placement(
    STANDARD_COPIED_MESH_HANDLER,
    *STANDARD_COPIED_MESH_NODE_TYPES,
)
NODE_HANDLERS.register_placement(
    PROXY_COPIED_MESH_HANDLER,
    *PROXY_COPIED_MESH_NODE_TYPES,
)


NODE_HANDLERS.register_placement(
    INSTANCED_MESH_PLACEMENT_HANDLER,
    "worldInstancedMeshNode",
)
NODE_HANDLERS.register_placement(
    INSTANCED_OCCLUDER_PLACEMENT_HANDLER,
    "worldInstancedOccluderNode",
)
NODE_HANDLERS.register_placement(
    INSTANCED_DESTRUCTIBLE_PLACEMENT_HANDLER,
    "worldInstancedDestructibleMeshNode",
)
NODE_HANDLERS.register_placement(
    FOLIAGE_PLACEMENT_HANDLER,
    "worldFoliageNode",
)


NODE_HANDLERS.register_placement(
    DEFORMED_MESH_PLACEMENT_HANDLER,
    "worldBendedMeshNode",
    "worldCableMeshNode",
)


NODE_HANDLERS.register_placement(
    WORLD_METADATA_PLACEMENT_HANDLER,
    "worldTriggerAreaNode",
    "gameKillTriggerNode",
    "worldAmbientAreaNode",
    "worldLightChannelVolumeNode",
    "gameWorldBoundaryNode",
    "worldGISpaceNode",
    "worldInteriorAreaNode",
    "worldInteriorMapNode",
    "worldLightChannelShapeNode",
    "worldStaticFogVolumeNode",
    "worldStaticSoundEmitterNode",
)


NODE_HANDLERS.register_placement(
    STATIC_DECAL_PLACEMENT_HANDLER,
    "worldStaticDecalNode",
)


NODE_HANDLERS.register_placement(
    STATIC_LIGHT_PLACEMENT_HANDLER,
    "worldStaticLightNode",
)
NODE_HANDLERS.register_placement(
    REFLECTION_PROBE_PLACEMENT_HANDLER,
    "worldReflectionProbeNode",
)


NODE_HANDLERS.register_placement(
    EFFECT_PLACEMENT_HANDLER,
    "worldStaticParticleNode",
    "worldEffectNode",
)


NODE_HANDLERS.register_placement(
    ACOUSTIC_SECTOR_PLACEMENT_HANDLER,
    "worldAcousticSectorNode",
)
NODE_HANDLERS.register_placement(
    MINIMAP_PLACEMENT_HANDLER,
    "MinimapDataNode",
)


NODE_HANDLERS.register_placement(
    SEMANTIC_MARKER_PLACEMENT_HANDLER,
    "worldAISpotNode",
    "worldPopulationSpawnerNode",
    "worldCompiledSmartObjectsNode",
    "worldSmartObjectNode",
    "worldStaticGpsLocationEntranceMarkerNode",
)


NODE_HANDLERS.register_placement(
    SPLINE_PLACEMENT_HANDLER,
    "worldSplineNode",
    "worldSpeedSplineNode",
)


NODE_HANDLERS.register_placement(
    GI_PLACEMENT_HANDLER,
    "worldGINode",
)
NODE_HANDLERS.register_placement(
    COLLISION_METADATA_PLACEMENT_HANDLER,
    "worldFoliageDestructionNode",
    "worldTerrainCollisionNode",
)
NODE_HANDLERS.register_placement(
    WORLD_COLLISION_PLACEMENT_HANDLER,
    "worldCollisionNode",
)
NODE_HANDLERS.register_placement(
    EXPLICIT_NO_OP_PLACEMENT_HANDLER,
    "worldCompiledCommunityAreaNode_Streamable",
    "worldCompiledCrowdParkingSpaceNode",
    "XworldInstancedOccluderNode",
)
