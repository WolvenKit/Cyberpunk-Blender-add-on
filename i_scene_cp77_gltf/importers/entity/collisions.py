from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ...assetio.values import collect_handle_data
from ...blender.physics.entity_colliders import (
    COLLIDER_COMPONENT_TYPES,
    EntityColliderImporter,
    PhysXEntityContext,
)
from ...blender.physics.resources import import_phys_resource
from ...core.log import debug_exception, get_logger
from ..common.entity_data import component_name
from ..common.paths import depot_path
from .context import EntityHandlerOperations
from .transforms import EntityTransformResolver, build_slot_owner_binding_maps

_LOG = get_logger(__name__)


def collect_collider_components(*component_groups):
    """Collider components by name, keeping the first group's copy of each"""
    collected = {}
    for components in component_groups:
        for component in components or ():
            if (
                not isinstance(component, dict)
                or component.get("$type") not in COLLIDER_COMPONENT_TYPES
            ):
                continue
            key = component_name(component) or str(component.get("id") or id(component))
            collected.setdefault(key, component)
    return tuple(collected.values())


@dataclass(frozen=True, slots=True)
class AppearanceColliders:
    """An appearance's own collider components, its transform resolver and the data its handles live in"""

    components: tuple
    transform_resolver: Any
    handle_sources: tuple


@dataclass(frozen=True, slots=True)
class EntityCollisionRuntime:
    """Inputs required to resolve and import entity collision data"""

    parsed_entity: Any
    resources: Any
    rig: Any
    rig_json: Any
    rig_bone_index: dict
    vehicle_slot_lookup: dict
    rig_json_by_component_name: dict
    rig_json_by_bone_name: dict
    armature_by_component_name: dict
    lookup_factory: Callable[[dict], Any]
    target_collection: Any
    blender_context: Any
    operations: EntityHandlerOperations
    embedded_physics: tuple = ()
    appearance_colliders: AppearanceColliders | None = None


class EntityCollisionService:
    """Import the entity's chassis .phys, mesh colliders and component colliders"""

    def __init__(self, runtime: EntityCollisionRuntime) -> None:
        self.runtime = runtime
        self.collider_handler = EntityColliderImporter()

    def execute(
        self,
        include_collisions,
        include_phys,
        include_entity_colliders,
        include_mesh_colliders,
    ):
        if not include_collisions:
            return 0, 0

        transform_resolver = None
        collider_components = self._collider_components()
        if include_entity_colliders and collider_components:
            transform_resolver = self._build_transform_resolver()

        if include_mesh_colliders:
            self._import_embedded_mesh_physics()
        if include_phys:
            self._import_chassis_phys()

        if not include_entity_colliders:
            return 0, 0

        handle_lookup = {}
        parsed = self.runtime.parsed_entity
        collect_handle_data(
            (parsed.component_dicts, parsed.component_data), handle_lookup
        )
        actor_count, shape_count = self.collider_handler.execute_many(
            collider_components,
            self._collider_context(transform_resolver, handle_lookup),
        )
        appearance = self.runtime.appearance_colliders
        if appearance is not None:
            # The appearance file numbers its handles apart from the entity's.
            appearance_handle_lookup = {}
            collect_handle_data(appearance.handle_sources, appearance_handle_lookup)
            appearance_actors, appearance_shapes = self.collider_handler.execute_many(
                appearance.components,
                self._collider_context(
                    appearance.transform_resolver, appearance_handle_lookup
                ),
            )
            actor_count += appearance_actors
            shape_count += appearance_shapes
        return actor_count, shape_count

    def _collider_context(self, transform_resolver, handle_lookup):
        return PhysXEntityContext(
            transform_resolver=transform_resolver,
            target_collection=self.runtime.target_collection,
            blender_context=self.runtime.blender_context,
            handle_lookup=handle_lookup,
            operations=self.runtime.operations,
        )

    def _collider_components(self):
        parsed = self.runtime.parsed_entity
        return parsed.collider_components + parsed.simple_collider_components

    def _build_transform_resolver(self):
        runtime = self.runtime
        parsed = runtime.parsed_entity
        collision_components = parsed.all_components
        collision_components_by_name = parsed.all_components_by_name

        collision_parent_lookup = runtime.lookup_factory(parsed.parent_transform_lookup)
        collision_skinning_lookup = runtime.lookup_factory(parsed.skinning_lookup)
        collision_slot_owner_jsons, collision_slot_owner_names = (
            build_slot_owner_binding_maps(
                parsed.slot_components,
                collision_parent_lookup,
                runtime.rig_json_by_component_name,
                set(runtime.rig_json_by_component_name),
            )
        )
        return EntityTransformResolver(
            collision_components,
            collision_parent_lookup,
            skinning_lookup=collision_skinning_lookup,
            rig=runtime.rig,
            rig_j=runtime.rig_json,
            rig_bone_index=runtime.rig_bone_index,
            default_slot_lookup=runtime.vehicle_slot_lookup,
            slot_owner_rig_jsons=collision_slot_owner_jsons,
            rig_json_by_component_name=runtime.rig_json_by_component_name,
            rig_json_by_bone_name=runtime.rig_json_by_bone_name,
            armature_by_component_name=runtime.armature_by_component_name,
            slot_owner_rig_owner_names=collision_slot_owner_names,
            components_by_name=collision_components_by_name,
            slot_component_lookups=parsed.slot_component_lookups,
        )

    def _import_chassis_phys(self):
        runtime = self.runtime
        parsed = runtime.parsed_entity
        try:
            chassis_info = parsed.components_by_name.get("Chassis")
            if (
                not isinstance(chassis_info, dict)
                or chassis_info.get("$type") != "vehicleChassisComponent"
            ):
                chassis_info = next(
                    (
                        component
                        for component in parsed.all_components_by_name.values()
                        if isinstance(component, dict)
                        and component.get("$type") == "vehicleChassisComponent"
                    ),
                    None,
                )
            if not isinstance(chassis_info, dict):
                _LOG.debug(
                    "Entity has no vehicleChassisComponent; chassis collision import not applicable"
                )
                return

            collision_resource = depot_path(
                chassis_info,
                "collisionResource",
                normalize=False,
            )
            if not collision_resource:
                _LOG.debug("No chassis collision resource in entity")
                return

            resource = runtime.resources.load_physics(collision_resource)
            if resource is None:
                _LOG.warning(
                    "Chassis collision resource not found: %s", collision_resource
                )
                return

            before = {
                item.obj_ref.as_pointer()
                for item in runtime.blender_context.scene.physx.actors
                if item.obj_ref is not None
            }
            component_matrix = (
                self._build_transform_resolver().resolve_component_matrix(chassis_info)[
                    0
                ]
            )
            import_phys_resource(
                resource,
                rig=runtime.rig,
                target_collection=runtime.target_collection,
                actor_matrix=component_matrix,
                context=runtime.blender_context,
            )
            created = (
                item.obj_ref
                for item in runtime.blender_context.scene.physx.actors
                if item.obj_ref is not None and item.obj_ref.as_pointer() not in before
            )
            from ...blender.physics.vehicle_phys import adopt_vehicle_phys_objects

            adopt_vehicle_phys_objects(runtime.rig, created)
        except Exception:
            debug_exception(_LOG, "Could not import the chassis physics")

    def _import_embedded_mesh_physics(self):
        runtime = self.runtime
        for resource, actor_matrix in runtime.embedded_physics:
            try:
                import_phys_resource(
                    resource,
                    target_collection=runtime.target_collection,
                    actor_matrix=actor_matrix,
                    context=runtime.blender_context,
                )
            except Exception as exc:
                _LOG.warning("Embedded mesh physics skipped: %s", exc, exc_info=True)
