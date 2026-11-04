from __future__ import annotations

import json
import os
import time

import bpy

from ....assetio.values import cname_text, nested_value
from ....bartmoss.matrix import flatten_matrix
from ....blender.naming import fit_id_name
from ....blender.physics.actors import register_actors
from ....blender.physics.world import import_world_collision_node
from ....core.log import get_logger
from ..context import (
    DeformationDataError,
    FoliageResourceError,
    SectorContentError,
)
from ..model import PROXY_PHASE, STANDARD_PHASE
from ..objects import (
    animate_rotation_root,
    assign_id_properties,
    collection_instance_object,
    new_collection,
)
from ..options import ENTITY_NODE_TYPES, PROXY_NODE_TYPES
from ..registry import NODE_HANDLERS

_LOG = get_logger(__name__)

STANDARD_COPIED_MESH_NODE_TYPES = frozenset(
    {
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
    }
)


class EntityPlacementHandler:
    placement_phase = STANDARD_PHASE

    def place(self, context):
        requested = context.node.entity_appearance or "default"
        ent_depot = context.node.entity_template_path
        entity_master = context.session.master_assets.entities.require(
            context.masters,
            ent_depot,
            requested,
        )

        resolved = entity_master.resolved_appearance
        if resolved != requested:
            _LOG.debug("Entity appearance resolved: %s -> %s", requested, resolved)

        placed = 0
        colliders = context.session.options.chosen("entity_colliders")
        for instance_index, instance in enumerate(context.instances):
            node_matrix = context.operations.instance_matrix(
                instance,
                context.execution.scale_factor,
            )
            instance_name = (
                f"ENT_{instance.index}_"
                f"{os.path.basename(ent_depot).split('.')[0]}_"
                f"{entity_master.identity}"
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
                "cp77_node_data_index": instance.index,
                "cp77_instance_idx": instance_index,
                "entityTemplate": ent_depot,
                "requestedAppearance": requested,
                "resolvedAppearance": resolved,
            }
            context.operations.assign_custom_properties(
                new,
                context.node,
                context.sector_name,
                HandleId=context.node.handle_id,
                **shared_properties,
            )
            context.operations.assign_custom_properties(
                placement_root,
                context.node,
                context.sector_name,
                **shared_properties,
            )
            new["cp77_matrix"] = flatten_matrix(node_matrix).tolist()
            target_collection = context.collection_for_instance(instance)
            if target_collection.children.get(new.name) is not new:
                target_collection.children.link(new)
            if colliders:
                register_actors(tuple(new.all_objects), bpy.context)
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
            "nearAutoHideDistance": float(data.get("nearAutoHideDistance", 0.0) or 0.0),
            "forceAutoHideDistance": float(
                data.get("forceAutoHideDistance", 0.0) or 0.0
            ),
            "lodLevelScales": int(data.get("lodLevelScales", 0) or 0),
            "occluderType": str(data.get("occluderType", "")),
            "renderSceneLayerMask": str(data.get("renderSceneLayerMask", "")),
            "nbNodesUnderProxy": int(data.get("nbNodesUnderProxy", 0) or 0),
        }
        if not road:
            properties["entityAttachDistance"] = float(
                data.get("entityAttachDistance", 0.0) or 0.0
            )
        return properties

    def _extra_properties(self, context):
        data = context.data
        node_type = context.node_type
        properties = {}

        if node_type == "worldPhysicalDestructionNode":
            properties.update(
                {
                    "destructionParams": json.dumps(
                        data.get("destructionParams", {}),
                        separators=(",", ":"),
                    ),
                }
            )

        if (
            node_type in {"worldAdvertisingNode", "worldAdvertisementNode"}
            and "lightData" in data
        ):
            properties["lightData"] = json.dumps(
                data["lightData"],
                separators=(",", ":"),
            )

        if node_type == "worldWaterPatchNode":
            properties.update(
                {
                    "waterPatchDepth": float(data.get("depth", 0.0) or 0.0),
                    "waterPatchType": cname_text(
                        nested_value(
                            data,
                            "type",
                            "typeName",
                            default={},
                        )
                    ),
                    "generateNavmesh": bool(data.get("generateNavmesh", 0)),
                    "waterPatchVersion": int(data.get("version", 0) or 0),
                    "waterPatchData": context.session.safe_json(data),
                }
            )

        if context.node_type in PROXY_NODE_TYPES:
            properties.update(
                self._proxy_properties(
                    context,
                    road=context.node_type == "worldRoadProxyMeshNode",
                )
            )

        if node_type == "worldRotatingMeshNode":
            properties.update(
                {
                    "rot_axis": data.get("rotationAxis", "Z"),
                    "reverseDirection": bool(data.get("reverseDirection", 0)),
                    "fullRotationTime": float(data.get("fullRotationTime", 0.0)),
                }
            )
        return properties

    def place(self, context):
        meshname = context.node.mesh_path
        if not meshname:
            raise SectorContentError(f"{context.node_type} has no mesh resource")

        rotating = context.node_type == "worldRotatingMeshNode"
        placed = context.operations.place_copied_mesh_instances(
            node=context.node,
            sector_name=context.sector_name,
            sector_collection=context.sector_collection,
            masters=context.masters,
            master_assets=context.session.master_assets,
            scale=context.execution.scale_factor,
            rotating=rotating,
            extra_props=self._extra_properties(context),
            source_collection_for_instance=context.collection_for_instance,
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
                    context.node,
                    context.sector_name,
                    cp77_node_data_index=instance.index,
                    cp77_instance_idx=instance_index,
                    rotationAxis=data.get("rotationAxis", "Z"),
                    reverseDirection=bool(data.get("reverseDirection", 0)),
                    fullRotationTime=float(data.get("fullRotationTime", 0.0)),
                )
                animate_rotation_root(
                    rotation_root,
                    data.get("rotationAxis", "Z"),
                    data.get("fullRotationTime", 0.0),
                    data.get("reverseDirection", 0),
                )

        if (
            context.node_type == "worldClothMeshNode"
            and "windImpulseEnabled" in context.data
        ):
            for new, placement_root, _, _, _ in placed:
                new["windImpulseEnabled"] = context.data["windImpulseEnabled"]
                placement_root["windImpulseEnabled"] = context.data[
                    "windImpulseEnabled"
                ]

        context.record_placements(len(placed))
        return len(placed)


class InstancedMeshPlacementHandler:
    placement_phase = STANDARD_PHASE

    def place(self, context):
        meshname = context.node.mesh_path
        if not meshname:
            raise SectorContentError(f"{context.node_type} has no mesh resource")
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

        # The node's transforms are world space: each entry places its range of them where they are.
        matrices = context.transform_buffers.instanced_mesh_matrices(
            context.node_entry.get("Data"),
            context.node.inner_index,
            context.execution.scale_factor,
        )
        placed = 0
        for source in context.instances:
            collection = context.node_owned_collection(source.index)
            context.operations.assign_custom_properties(
                collection,
                context.node,
                context.sector_name,
                mesh=meshname,
                cp77_placed_count=len(matrices),
                cp77_node_data_index=source.index,
            )
            for element_index, matrix in enumerate(matrices):
                instance = collection_instance_object(
                    f"NDI{source.index}_{element_index}_{groupname}",
                    group,
                    collection,
                    matrix,
                    color=(0.785188, 0.409408, 0.0430124, 1),
                )
                context.operations.assign_custom_properties(
                    instance,
                    context.node,
                    context.sector_name,
                    mesh=meshname,
                    cp77_node_data_index=source.index,
                    cp77_element_idx=element_index,
                )
                placed += 1

        context.record_placements(
            placed,
            expected=len(context.instances) * len(matrices),
        )
        return placed


class InstancedOccluderPlacementHandler:
    placement_phase = STANDARD_PHASE

    def place(self, context):
        meshname = context.node.mesh_path
        if not meshname:
            raise SectorContentError(f"{context.node_type} has no mesh resource")
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
        node_data_index = context.instances[0].index if context.instances else -1
        collection = context.node_owned_collection(node_data_index)
        context.operations.assign_custom_properties(
            collection,
            context.node,
            context.sector_name,
            mesh=meshname,
            cp77_node_data_index=node_data_index,
        )

        placed = 0
        for element_index, record in enumerate(records):
            try:
                matrix = context.transform_buffers.occluder_matrix(record)
            except (TypeError, ValueError) as error:
                context.operations.warning(
                    f"{context.sector_name}: instanced occluder node "
                    f"{context.node_index} element {element_index} is "
                    f"invalid: {error}",
                    exc_info=True,
                )
                continue

            instance = collection_instance_object(
                f"InstancedOccluder_{context.node_index}_{element_index}_{groupname}",
                group,
                collection,
                matrix,
                color=(0.35, 0.15, 0.05, 1.0),
            )
            context.operations.assign_custom_properties(
                instance,
                context.node,
                context.sector_name,
                mesh=meshname,
                cp77_element_idx=element_index,
                cp77_node_data_index=node_data_index,
                autohideDistanceScale=int(
                    context.data.get("autohideDistanceScale", 0) or 0
                ),
                occluderType=str(context.data.get("occluderType", "")),
            )
            placed += 1

        # The instances placed, which export holds the scene's against: an invalid record places none.
        assign_id_properties(collection, cp77_placed_count=placed)
        context.record_placements(placed, expected=len(records))
        return placed


class InstancedDestructiblePlacementHandler:
    placement_phase = STANDARD_PHASE

    def place(self, context):
        meshname = context.node.mesh_path
        if not meshname:
            raise SectorContentError(f"{context.node_type} has no mesh resource")
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

        local_matrices = context.transform_buffers.destructible_matrices(context.data)
        appearance_name = cname_text(
            context.data.get("appearanceName"),
            context.node.mesh_appearance,
        )

        placed = 0
        for source in context.instances:
            node_matrix = context.operations.instance_matrix(
                source,
                context.execution.scale_factor,
            )
            collection = new_collection(fit_id_name(f"wIDMn{source.index}_{groupname}"))
            source_collection = context.collection_for_instance(source)
            source_collection.children.link(collection)
            context.operations.assign_custom_properties(
                collection,
                context.node,
                context.sector_name,
                cp77_node_data_index=source.index,
                mesh=meshname,
                cp77_placed_count=len(local_matrices),
                appearanceName=appearance_name,
            )

            for element_index, local_matrix in local_matrices:
                final_matrix = node_matrix @ local_matrix
                instance = collection_instance_object(
                    f"wIDMi{source.index}_{element_index}_{groupname}",
                    group,
                    collection,
                    final_matrix,
                    color=(0.3, 0.3, 0.3, 1),
                )
                context.operations.assign_custom_properties(
                    instance,
                    context.node,
                    context.sector_name,
                    cp77_node_data_index=source.index,
                    mesh=meshname,
                    cp77_element_idx=element_index,
                    appearanceName=appearance_name,
                )
                placed += 1

        context.record_placements(
            placed,
            expected=len(context.instances) * len(local_matrices),
        )
        return placed


class FoliagePlacementHandler:
    placement_phase = STANDARD_PHASE

    def place(self, context):
        meshname = context.node.mesh_path
        if not meshname:
            raise SectorContentError(f"{context.node_type} has no mesh resource")
        foliage_resource = context.node.foliage_resource_path
        if not foliage_resource:
            raise SectorContentError(f"{context.node_type} has no foliage resource")

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
            collection = new_collection(fit_id_name(f"WFI_{source.index}_{groupname}"))
            source_collection = context.collection_for_instance(source)
            source_collection.children.link(collection)
            context.operations.assign_custom_properties(
                collection,
                context.node,
                context.sector_name,
                cp77_node_data_index=source.index,
                mesh=meshname,
                foliageResource=foliage_resource,
                cp77_placed_count=selection.active_count,
                bucketCount=selection.bucket_count,
                resourceVersion=resource.version,
            )

            for _bucket_index, population_index, _relative_index in selection.active:
                population = resource.populations[population_index]
                population_matrix = context.foliage_assets.cached_population_matrix(
                    population
                )
                final_matrix = node_matrix @ population_matrix
                instance = collection_instance_object(
                    f"WFI_{source.index}_{population_index}_{groupname}",
                    group,
                    collection,
                    final_matrix,
                    color=(0.0, 1.0, 0.0, 1),
                )
                context.operations.assign_custom_properties(
                    instance,
                    context.node,
                    context.sector_name,
                    cp77_node_data_index=source.index,
                    mesh=meshname,
                    cp77_element_idx=population_index,
                    populationIndex=population_index,
                    foliageResource=foliage_resource,
                )
                placed += 1

        context.record_placements(
            placed,
            expected=len(context.instances) * selection.active_count,
        )
        return placed


class GIPlacementHandler:
    placement_phase = STANDARD_PHASE

    def place(self, context):
        placed = 0
        for instance_index, instance in enumerate(context.instances):
            context.gi_assets.create(
                context,
                instance,
                instance_index,
            )
            placed += 1
        context.record_placements(placed)
        return placed


class PhysXCollisionPlacementHandler:
    placement_phase = STANDARD_PHASE

    def place(self, context):
        if context.session.options.missing_choice(context.node_type):
            context.record_placements(0, expected=0)
            return 0
        placed = 0
        for instance_index, instance in enumerate(context.instances):
            context.physx_collision_assets.create(
                context,
                instance,
                instance_index,
            )
            placed += 1
        context.record_placements(placed)
        return placed


class WorldCollisionPlacementHandler:
    placement_phase = STANDARD_PHASE

    def place(self, context):
        if context.session.options.missing_choice(context.node_type):
            context.record_placements(0, expected=0)
            return 0
        placed = int(import_world_collision_node(context))
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
        for instance_index, instance in enumerate(context.instances):
            result = context.spline_assets.create(
                context,
                instance,
                instance_index,
            )
            if result is None:
                continue
            placed += 1

        context.record_placements(placed)
        return placed


class SemanticMarkerPlacementHandler:
    placement_phase = STANDARD_PHASE

    def place(self, context):
        placed = 0
        for instance_index, instance in enumerate(context.instances):
            context.semantic_assets.create(
                context,
                instance,
                instance_index,
            )
            placed += 1

        context.record_placements(placed)
        return placed


class AcousticSectorPlacementHandler:
    placement_phase = STANDARD_PHASE

    def place(self, context):
        placed = 0
        for instance_index, instance in enumerate(context.instances):
            context.acoustic_assets.create(
                context,
                instance,
                instance_index,
            )
            placed += 1

        context.record_placements(placed)
        return placed


class MinimapPlacementHandler:
    placement_phase = STANDARD_PHASE

    def place(self, context):
        placed = 0
        for instance_index, instance in enumerate(context.instances):
            context.minimap_assets.create(
                context,
                instance,
                instance_index,
            )
            placed += 1

        context.record_placements(placed)
        return placed


class EffectPlacementHandler:
    placement_phase = STANDARD_PHASE

    def place(self, context):
        placed = 0
        for instance_index, instance in enumerate(context.instances):
            context.effect_assets.create(
                context,
                instance,
                instance_index,
            )
            placed += 1

        context.record_placements(placed)
        return placed


class StaticLightPlacementHandler:
    placement_phase = STANDARD_PHASE

    def place(self, context):
        placed = 0
        for instance_index, instance in enumerate(context.instances):
            context.lighting_assets.create(
                context,
                instance,
                instance_index,
            )
            placed += 1

        context.record_placements(placed)
        return placed


class ReflectionProbePlacementHandler:
    placement_phase = STANDARD_PHASE

    def place(self, context):
        placed = 0
        for instance_index, instance in enumerate(context.instances):
            context.probe_assets.create(
                context,
                instance,
                instance_index,
            )
            placed += 1

        context.record_placements(placed)
        return placed


class StaticDecalPlacementHandler:
    placement_phase = STANDARD_PHASE

    def place(self, context):
        data = context.data
        placed = 0
        for instance_index, instance in enumerate(context.instances):
            result = context.decal_assets.create(
                context,
                instance,
                instance_index,
            )
            metadata_started = time.perf_counter()
            material_result = result.material_result
            properties = {
                "cp77_instance_idx": instance_index,
                "cp77_node_data_index": instance.index,
                "decal": material_result.material_path,
                "horizontalFlip": bool(data.get("horizontalFlip", 0)),
                "verticalFlip": bool(data.get("verticalFlip", 0)),
                "alpha": float(data.get("alpha", 1.0)),
                "roughnessScale": float(data.get("roughnessScale", 1.0)),
                "isStretchingEnabled": bool(data.get("isStretchingEnabled", 0)),
                "orderNo": int(data.get("orderNo", 0)),
                "normalThreshold": float(data.get("normalThreshold", 0.0)),
                "enableNormalThreshold": bool(data.get("enableNormalTreshold", 0)),
            }
            if result.plane is not None:
                context.operations.assign_custom_properties(
                    result.plane,
                    context.node,
                    context.sector_name,
                    **properties,
                )
            context.operations.assign_custom_properties(
                result.projector,
                context.node,
                context.sector_name,
                **properties,
            )
            context.execution.track_matrix_object(result.projector)
            if result.plane is not None:
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
            context.decal_assets.record_timing(
                "placement_metadata",
                metadata_started,
            )
            placed += 1

        context.record_placements(placed)
        return placed


class WorldMetadataPlacementHandler:
    placement_phase = STANDARD_PHASE

    OUTLINE_TYPES = frozenset(
        {
            "worldTriggerAreaNode",
            "gameKillTriggerNode",
            "worldAmbientAreaNode",
            "worldLightChannelVolumeNode",
            "gameWorldBoundaryNode",
            "worldGISpaceNode",
            "worldInteriorAreaNode",
        }
    )

    def _outline_metadata(self, context, obj):
        data = context.data
        node_type = context.node_type
        if node_type == "worldLightChannelVolumeNode":
            channels = str(data.get("channels", ""))
            obj["lightChannels"] = channels
            obj["cp77_light_channel_volume"] = True
            obj.hide_render = True
            obj["streamingDistanceFactor"] = float(
                data.get("streamingDistanceFactor", 0.0) or 0.0
            )
        elif node_type == "worldAmbientAreaNode":
            obj["useCustomColor"] = bool(data.get("useCustomColor", 0))

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
        raise SectorContentError(f"Unsupported world metadata node type: {node_type}")

    def place(self, context):
        placed = 0
        for instance_index, instance in enumerate(context.instances):
            obj = self._create(context, instance, instance_index)
            if obj is None:
                continue
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

        placed = 0
        for instance_index, instance in enumerate(context.instances):
            node_matrix = context.operations.instance_matrix(
                instance,
                context.execution.scale_factor,
            )
            prefix = "BEND" if context.node_type == "worldBendedMeshNode" else "CABLE"
            instance_name = fit_id_name(
                f"{prefix}_{instance.index}_{groupname or context.node_index}"
            )
            result = context.deformation_assets.instantiate(
                group,
                instance_name,
                node_matrix,
                analysis,
                cable_radius=cable_radius,
            )

            properties = {
                "cp77_node_data_index": instance.index,
                "cp77_instance_idx": instance_index,
                "mesh": meshname,
                "meshAppearance": context.node.mesh_appearance,
                "isBendedRoad": bool(data.get("isBendedRoad", 0)),
                "deformedBox": context.session.safe_json(data.get("deformedBox", {})),
            }
            if context.node_type == "worldCableMeshNode":
                properties.update(
                    {
                        "cableLength": float(data.get("cableLength", 0.0) or 0.0),
                        "cableRadius": cable_radius,
                        "destructionHashes": (
                            context.session.safe_json(data.get("destructionHashes", []))
                        ),
                    }
                )

            context.operations.assign_custom_properties(
                result.collection,
                context.node,
                context.sector_name,
                **properties,
            )
            context.operations.assign_custom_properties(
                result.placement_root,
                context.node,
                context.sector_name,
                **properties,
            )
            if result.path_object is not None:
                context.operations.assign_custom_properties(
                    result.path_object,
                    context.node,
                    context.sector_name,
                    **properties,
                )

            source_collection = context.collection_for_instance(instance)
            if (
                source_collection.children.get(result.collection.name)
                is not result.collection
            ):
                source_collection.children.link(result.collection)
            placed += 1

        context.record_placements(placed)
        return placed


ENTITY_PLACEMENT_HANDLER = EntityPlacementHandler()
STANDARD_COPIED_MESH_HANDLER = CopiedMeshPlacementHandler(STANDARD_PHASE)
PROXY_COPIED_MESH_HANDLER = CopiedMeshPlacementHandler(PROXY_PHASE)
INSTANCED_MESH_PLACEMENT_HANDLER = InstancedMeshPlacementHandler()
INSTANCED_OCCLUDER_PLACEMENT_HANDLER = InstancedOccluderPlacementHandler()
INSTANCED_DESTRUCTIBLE_PLACEMENT_HANDLER = InstancedDestructiblePlacementHandler()
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
PHYSX_COLLISION_PLACEMENT_HANDLER = PhysXCollisionPlacementHandler()
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
    *PROXY_NODE_TYPES,
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
    PHYSX_COLLISION_PLACEMENT_HANDLER,
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
