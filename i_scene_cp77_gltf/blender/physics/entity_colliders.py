from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from mathutils import Matrix

from ...assetio.values import cname_value, resolve_handle_reference
from ...core.log import get_logger
from ...physics.domain.mass import positive_mass
from ..naming import fit_id_name
from .actors import (
    add_red_collider_to_actor,
    create_actor_object,
    remove_actor_object,
    supports_collider_type,
)

_LOG = get_logger(__name__)


@dataclass(slots=True)
class PhysXEntityContext:
    transform_resolver: Any
    target_collection: Any
    blender_context: Any
    handle_lookup: dict
    operations: Any


COLLIDER_COMPONENT_TYPES = frozenset(
    {
        "entColliderComponent",
        "entSimpleColliderComponent",
    }
)


def _physx_actor_type(component):
    simulation_type = (
        cname_value(component.get("simulationType"))
        if isinstance(component, dict)
        else ""
    )
    actor_type = str(simulation_type).rsplit("::", 1)[-1].upper()
    return actor_type if actor_type in {"STATIC", "DYNAMIC", "KINEMATIC"} else "STATIC"


class EntityColliderImporter:
    component_types = COLLIDER_COMPONENT_TYPES

    def execute(self, component, context):
        actor_count, shape_count = self._execute_component(component, context)
        self._finalize_scene(context, actor_count, shape_count)
        return actor_count, shape_count

    def execute_many(self, components, context):
        actor_count = 0
        shape_count = 0
        for component in components or ():
            component_actors, component_shapes = self._execute_component(
                component, context
            )
            actor_count += component_actors
            shape_count += component_shapes
        self._finalize_scene(context, actor_count, shape_count)
        return actor_count, shape_count

    @staticmethod
    def _execute_component(component, context):
        operations = context.operations
        if not isinstance(component, dict) or not operations.is_component_enabled(
            component
        ):
            return 0, 0

        collider_refs = component.get("colliders")
        if isinstance(collider_refs, dict):
            collider_refs = [collider_refs]
        if not collider_refs:
            return 0, 0

        if context.transform_resolver is not None:
            resolved_matrix, bind_name, slot_name, binding_type, _ = (
                context.transform_resolver.resolve_component_matrix(component)
            )
        else:
            resolved_matrix, bind_name, slot_name, binding_type = (
                Matrix.Identity(4),
                "",
                "",
                "none",
            )

        component_type = component.get("$type", "entColliderComponent")
        component_label = cname_value(component.get("name")) or component_type
        actor_type = _physx_actor_type(component)
        mass = positive_mass(component)
        inertia = component.get("inertia")
        com_offset = component.get("comOffset")
        component_filter = component.get("filterData") or component.get("filter")
        resolved_colliders = []
        for shape_index, collider_ref in enumerate(collider_refs):
            collider_data = resolve_handle_reference(
                collider_ref, context.handle_lookup
            )
            if not isinstance(collider_data, dict):
                continue
            collider_type = collider_data.get("$type", "")
            if not supports_collider_type(collider_type):
                _LOG.warning(
                    "Unsupported entity collider type %s for %s",
                    collider_type,
                    component_label,
                )
                continue
            resolved_colliders.append((shape_index, collider_data))

        if not resolved_colliders:
            return 0, 0

        actor_name = f"{component_label}_{component_type}"
        actor_obj = create_actor_object(
            actor_name,
            context.target_collection,
            context=context.blender_context,
            actor_type=actor_type,
            mass=mass,
            inertia=inertia,
            com_offset=com_offset,
        )
        actor_obj.matrix_world = resolved_matrix
        actor_obj["cp77_type"] = component_type
        actor_obj["componentName"] = component_label
        actor_obj["cp77_binding_type"] = binding_type
        if bind_name:
            actor_obj["bindname"] = bind_name
        if slot_name:
            actor_obj["slotName"] = slot_name

        if actor_type != "DYNAMIC" and context.transform_resolver is not None:
            target, subtarget, _attachment_type = (
                context.transform_resolver.resolve_dynamic_attachment(component)
            )
            if target is not None:
                operations.configure_child_of_constraint(actor_obj, target, subtarget)

        component_shapes = 0
        for shape_index, collider_data in resolved_colliders:
            collider_type = collider_data.get("$type", "")
            try:
                shape_item = add_red_collider_to_actor(
                    actor_obj,
                    collider_data,
                    context=context.blender_context,
                    filter_data=collider_data.get("filterData") or component_filter,
                )
            except Exception as exc:
                _LOG.warning(
                    "Unable to import %s for %s: %s",
                    collider_type,
                    component_label,
                    exc,
                    exc_info=True,
                )
                continue
            shape_item.name = fit_id_name(
                component_label, f"_{shape_index}_{shape_item.name}"
            )
            component_shapes += 1

        if not component_shapes:
            remove_actor_object(actor_obj, context.blender_context)
            return 0, 0
        return 1, component_shapes

    @staticmethod
    def _finalize_scene(context, actor_count, shape_count):
        scene_physx = getattr(context.blender_context.scene, "physx", None)
        if scene_physx is not None and actor_count:
            if hasattr(scene_physx, "scene_built"):
                scene_physx.scene_built = False
            if hasattr(scene_physx, "active_actor_count"):
                scene_physx.active_actor_count = len(scene_physx.actors)
            _LOG.debug(
                "Registered %d PhysX actors with %d collider shapes",
                actor_count,
                shape_count,
            )
        elif actor_count == 0:
            _LOG.debug("No supported entity collider shapes were registered")
