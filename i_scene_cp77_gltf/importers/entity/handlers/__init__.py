from .collisions import (
    COLLIDER_COMPONENT_TYPES,
    EntityColliderHandler,
)
from .animators import (
    EntityTransformAnimatorHandler,
    EntityTransformAnimatorService,
)
from .meshes import (
    EntityMeshHandler,
    EntityMeshService,
    EntitySkinnedMeshOperations,
    EntitySkinnedMeshService,
    EntityStaticMeshHandler,
    EntityStaticMeshOperations,
    EntityStaticMeshService,
)
from ..policy import (
    MESH_COMPONENT_TYPES,
    SKINNED_MESH_COMPONENT_TYPES,
    STATIC_MESH_COMPONENT_TYPES,
    STATIC_OCCLUDER_COMPONENT_TYPES,
)
from .lights import (
    EntityLightChannelHandler,
    EntityLightHandler,
    create_auxiliary_component_registry,
)


def create_component_registry():
    registry = create_auxiliary_component_registry()
    registry.register(
        EntityColliderHandler.component_types,
        EntityColliderHandler(),
    )
    registry.register(
        EntityTransformAnimatorHandler.component_types,
        EntityTransformAnimatorHandler(),
    )
    registry.register(
        EntityMeshHandler.component_types,
        EntityMeshHandler(),
    )
    return registry


__all__ = [
    "COLLIDER_COMPONENT_TYPES",
    "EntityColliderHandler",
    "EntityLightChannelHandler",
    "EntityLightHandler",
    "EntityTransformAnimatorHandler",
    "EntityTransformAnimatorService",
    "EntityMeshHandler",
    "EntityMeshService",
    "EntitySkinnedMeshOperations",
    "EntitySkinnedMeshService",
    "EntityStaticMeshHandler",
    "EntityStaticMeshOperations",
    "EntityStaticMeshService",
    "MESH_COMPONENT_TYPES",
    "SKINNED_MESH_COMPONENT_TYPES",
    "STATIC_MESH_COMPONENT_TYPES",
    "STATIC_OCCLUDER_COMPONENT_TYPES",
    "create_auxiliary_component_registry",
    "create_component_registry",
]
