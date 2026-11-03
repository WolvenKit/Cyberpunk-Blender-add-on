from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class EntityHandlerOperations:
    """Shared execution operations injected into component handlers"""

    is_component_enabled: Callable[[dict], bool]
    configure_child_of_constraint: Callable[[Any, Any, str], Any]
    visual_scale_matrix: Callable[[dict], Any]


@dataclass(slots=True)
class AppearanceExecutionContext:
    """Per-appearance Blender execution state for component handlers"""

    filepath: str
    appearance_name: str
    entity_collection: Any
    transform_resolver: Any
    shape_lookup: Any
    transform_animators: Any
    operations: EntityHandlerOperations
    resolve_export: Callable[[str, Any], str] | None = None
    meshes: Any = None
    static_meshes: Any = None
    skinned_meshes: Any = None
    state: dict[str, Any] = field(default_factory=dict)
