from __future__ import annotations

<<<<<<< Updated upstream
from dataclasses import dataclass, field
from typing import Any, Callable
=======
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
>>>>>>> Stashed changes


@dataclass(frozen=True, slots=True)
class EntityHandlerOperations:
<<<<<<< Updated upstream
    """Shared execution operations injected into component handlers."""

    is_component_enabled: Callable[[dict], bool]
    child_of_inverse_matrix: Callable[[Any, str], Any]
    configure_child_of_constraint: Callable[[Any, Any, str, Any], Any]
=======
    """Shared execution operations injected into component handlers"""

    is_component_enabled: Callable[[dict], bool]
    configure_child_of_constraint: Callable[[Any, Any, str], Any]
    visual_scale_matrix: Callable[[dict], Any]
>>>>>>> Stashed changes


@dataclass(slots=True)
class AppearanceExecutionContext:
<<<<<<< Updated upstream
    """Per-appearance Blender execution state for component handlers."""
=======
    """Per-appearance Blender execution state for component handlers"""
>>>>>>> Stashed changes

    filepath: str
    appearance_name: str
    entity_collection: Any
    transform_resolver: Any
    shape_lookup: Any
    transform_animators: Any
    operations: EntityHandlerOperations
<<<<<<< Updated upstream
=======
    resolve_export: Callable[[str, Any], str] | None = None
>>>>>>> Stashed changes
    meshes: Any = None
    static_meshes: Any = None
    skinned_meshes: Any = None
    state: dict[str, Any] = field(default_factory=dict)
<<<<<<< Updated upstream


@dataclass(slots=True)
class CollisionExecutionContext:
    """Runtime state for entity collider component handlers."""

    transform_resolver: Any
    target_collection: Any
    blender_context: Any
    handle_lookup: dict
    operations: EntityHandlerOperations
=======
>>>>>>> Stashed changes
