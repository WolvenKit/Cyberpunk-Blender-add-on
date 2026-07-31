from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(frozen=True, slots=True)
class EntityHandlerOperations:
    """Shared execution operations injected into component handlers."""

    is_component_enabled: Callable[[dict], bool]
    child_of_inverse_matrix: Callable[[Any, str], Any]
    configure_child_of_constraint: Callable[[Any, Any, str, Any], Any]


@dataclass(slots=True)
class AppearanceExecutionContext:
    """Per-appearance Blender execution state for component handlers."""

    filepath: str
    appearance_name: str
    entity_collection: Any
    transform_resolver: Any
    shape_lookup: Any
    transform_animators: Any
    operations: EntityHandlerOperations
    meshes: Any = None
    static_meshes: Any = None
    skinned_meshes: Any = None
    state: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class CollisionExecutionContext:
    """Runtime state for entity collider component handlers."""

    transform_resolver: Any
    target_collection: Any
    blender_context: Any
    handle_lookup: dict
    operations: EntityHandlerOperations
