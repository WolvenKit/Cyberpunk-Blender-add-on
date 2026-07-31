from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from ..common.entity_data import component_name
from ..common.paths import depot_path_value
from ..common.handles import collect_handle_data
from .context import CollisionExecutionContext, EntityHandlerOperations
from .handlers.collisions import EntityColliderHandler
from .transforms import EntityTransformResolver, build_slot_owner_binding_maps, transform_matrix
from ..collision import import_phys_into_collection


@dataclass(frozen=True, slots=True)
class EntityCollisionRuntime:
    """Inputs required to resolve and import entity collision data."""

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
    handler_registry: Any


class EntityCollisionService:
    """Import chassis .phys data and entity-authored collider components."""

    def __init__(self, runtime: EntityCollisionRuntime) -> None:
        self.runtime = runtime
        self.collider_handler = EntityColliderHandler()

    def execute(self, include_collisions, include_phys, include_entity_colliders):
        if not include_collisions:
            return 0, 0

        transform_resolver = None
        collider_components = self._collider_components()
        if include_entity_colliders and collider_components:
            transform_resolver = self._build_transform_resolver()

        if include_phys:
            self._import_chassis_phys()

        if not include_entity_colliders:
            return 0, 0

        handle_lookup = {}
        parsed = self.runtime.parsed_entity
        collect_handle_data((parsed.component_dicts, parsed.component_data), handle_lookup)
        context = CollisionExecutionContext(
            transform_resolver=transform_resolver,
            target_collection=self.runtime.target_collection,
            blender_context=self.runtime.blender_context,
            handle_lookup=handle_lookup,
            operations=self.runtime.operations,
        )
        handler = self.collider_handler
        if collider_components and self.runtime.handler_registry is not None:
            registered = self.runtime.handler_registry.handler_for(collider_components[0])
            if registered is not None:
                handler = registered
        return handler.execute_many(collider_components, context)

    def _collider_components(self):
        parsed = self.runtime.parsed_entity
        return parsed.collider_components + parsed.simple_collider_components

    def _build_transform_resolver(self):
        runtime = self.runtime
        parsed = runtime.parsed_entity
        collision_components = list(parsed.component_dicts)
        collision_components.extend(parsed.component_data)
        collision_components_by_name = dict(parsed.components_by_name)
        for component in parsed.component_data:
            name = component_name(component)
            if name:
                collision_components_by_name.setdefault(name, component)

        collision_parent_lookup = runtime.lookup_factory(parsed.parent_transform_lookup)
        collision_skinning_lookup = runtime.lookup_factory(parsed.skinning_lookup)
        base_slot_components = [
            component
            for component in parsed.component_dicts
            if isinstance(component, dict) and isinstance(component.get('slots'), list)
        ]
        collision_slot_owner_jsons, collision_slot_owner_names = build_slot_owner_binding_maps(
            base_slot_components,
            collision_parent_lookup,
            runtime.rig_json_by_component_name,
            set(runtime.rig_json_by_component_name),
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
            chassis_info = parsed.components_by_name.get('Chassis')
            if not isinstance(chassis_info, dict):
                print('No valid Chassis component in entity; skipping chassis collision import')
                return

            collision_resource = depot_path_value(
                chassis_info,
                'collisionResource',
            )
            if not collision_resource:
                print('No chassis collision resource in entity')
                return

            resource = runtime.resources.load_physics(collision_resource)
            if resource is None:
                print(f'Chassis collision resource not found: {collision_resource}')
                return

            import_phys_into_collection(
                resource,
                rig=runtime.rig,
                target_collection=runtime.target_collection,
                actor_matrix=transform_matrix(chassis_info.get('localTransform', {})),
                context=runtime.blender_context,
            )
        except Exception as exc:
            print(exc)
