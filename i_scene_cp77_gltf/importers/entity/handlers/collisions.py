from __future__ import annotations

from mathutils import Matrix

from ...common.entity_data import component_name
from ...common.handles import resolve_handle_data
from ....assetio.values import cname_value
from ....blender.collections import newly_linked_collection_object
from ....collisiontools.pxbridge.io_phys import import_collider_as_actor

COLLIDER_COMPONENT_TYPES = frozenset({
    "entColliderComponent",
    "entSimpleColliderComponent",
})


def _physx_actor_type(component):
    simulation_type = cname_value(component.get('simulationType')) if isinstance(component, dict) else ''
    actor_type = str(simulation_type).rsplit('::', 1)[-1].upper()
    return actor_type if actor_type in {'STATIC', 'DYNAMIC', 'KINEMATIC'} else 'STATIC'


def _collider_component_mass(component):
    if not isinstance(component, dict):
        return 0.0
    for key in ('massOverride', 'mass'):
        value = component.get(key)
        try:
            value = float(value)
        except (TypeError, ValueError):
            continue
        if value > 0.0:
            return value
    return 0.0



class EntityColliderHandler:
    """Import entity collider components through the existing PhysX bridge."""

    component_types = COLLIDER_COMPONENT_TYPES

    def execute(self, component, context):
        actor_count, shape_count = self._execute_component(component, context)
        self._finalize_scene(context, actor_count, shape_count)
        return actor_count, shape_count

    def execute_many(self, components, context):
        actor_count = 0
        shape_count = 0
        for component in components or ():
            component_actors, component_shapes = self._execute_component(component, context)
            actor_count += component_actors
            shape_count += component_shapes
        self._finalize_scene(context, actor_count, shape_count)
        return actor_count, shape_count

    @staticmethod
    def _execute_component(component, context):
        operations = context.operations
        if not isinstance(component, dict) or not operations.is_component_enabled(component):
            return 0, 0

        collider_refs = component.get('colliders')
        if isinstance(collider_refs, dict):
            collider_refs = [collider_refs]
        if not collider_refs:
            return 0, 0

        if context.transform_resolver is not None:
            resolved_matrix, bind_name, slot_name, binding_type, attach_armature = (
                context.transform_resolver.resolve_component_matrix(component)
            )
        else:
            resolved_matrix, bind_name, slot_name, binding_type, attach_armature = (
                Matrix.Identity(4), '', '', 'none', None
            )

        component_type = component.get('$type', 'entColliderComponent')
        component_label = component_name(component) or component_type
        actor_type = _physx_actor_type(component)
        mass = _collider_component_mass(component)
        inertia = component.get('inertia')
        com_offset = component.get('comOffset')
        component_filter = component.get('filterData') or component.get('filter')
        actor_obj = None
        component_shapes = 0

        for shape_index, collider_ref in enumerate(collider_refs):
            collider_data = resolve_handle_data(collider_ref, context.handle_lookup)
            if not isinstance(collider_data, dict):
                continue

            collider_type = collider_data.get('$type', 'physicsColliderBox')
            actor_name = f'{component_label}_{component_type}'
            submesh_name = actor_name if actor_obj is None else f'{actor_name}_{shape_index}_{collider_type}'
            existing_objects = set(context.target_collection.objects) if actor_obj is None else None

            try:
                shape_item = import_collider_as_actor(
                    collider_data,
                    submesh_name,
                    context.target_collection,
                    actor_obj=actor_obj,
                    context=context.blender_context,
                    actor_type=actor_type,
                    mass=mass,
                    inertia=inertia,
                    com_offset=com_offset,
                    filter_data=collider_data.get('filterData') or component_filter,
                )
            except Exception as exc:
                print(f'Error importing {collider_type} for {component_label}: {exc}')
                continue

            if shape_item is None:
                continue

            if actor_obj is None:
                actor_obj = newly_linked_collection_object(
                    context.target_collection,
                    existing_objects,
                    actor_name,
                )
                if actor_obj is None:
                    print(f'PhysX actor registration did not create an actor object for {component_label}')
                    break
                actor_obj.matrix_world = resolved_matrix
                actor_obj['ntype'] = component_type
                actor_obj['componentName'] = component_label
                actor_obj['bindingType'] = binding_type
                actor_obj['actorType'] = actor_type
                if bind_name:
                    actor_obj['bindname'] = bind_name
                if slot_name:
                    actor_obj['slotName'] = slot_name
                if 'simulationType' in component:
                    actor_obj['simulationType'] = component['simulationType']

                if (
                    actor_type != 'DYNAMIC'
                    and binding_type in {'slot', 'bone'}
                    and bind_name
                    and attach_armature is not None
                ):
                    operations.configure_child_of_constraint(
                        actor_obj,
                        attach_armature,
                        bind_name,
                        operations.child_of_inverse_matrix(attach_armature, bind_name),
                    )

            shape_item.name = f'{component_label}_{shape_index}_{shape_item.name}'[:63]
            component_shapes += 1

        return (1, component_shapes) if actor_obj is not None and component_shapes else (0, 0)

    @staticmethod
    def _finalize_scene(context, actor_count, shape_count):
        scene_physx = getattr(context.blender_context.scene, 'physx', None)
        if scene_physx is not None and actor_count:
            if hasattr(scene_physx, 'scene_built'):
                scene_physx.scene_built = False
            if hasattr(scene_physx, 'active_actor_count'):
                scene_physx.active_actor_count = len(scene_physx.actors)
            print(f'Registered {actor_count} PhysX actors with {shape_count} collider shapes')
        elif actor_count == 0:
            print('No supported entity collider shapes were registered')
