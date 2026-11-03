from __future__ import annotations

from typing import Any

from ...core.log import get_logger, log_once
from ..animation_context import active_armature
from ..armature_bones import armature_bone_names, armature_bone_parent_map

_LOG = get_logger(__name__)


def armature_poll(_tree, obj) -> bool:
    return obj is not None and getattr(obj, "type", None) == "ARMATURE"


def binding_tree(tree: Any):
    if tree is None:
        return None
    try:
        from . import variables

        return variables.root_tree_for(tree) or tree
    except (AttributeError, ReferenceError, RuntimeError, TypeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("binding_tree", type(error).__name__),
            "binding tree: fell back after %s",
            error,
            exc_info=True,
        )
        return tree


def bound_armature(tree: Any, context: Any = None, *, active_fallback: bool = False):
    owner = binding_tree(tree)
    armature = getattr(owner, "red_bound_armature", None) if owner is not None else None
    if armature is not None and getattr(armature, "type", None) == "ARMATURE":
        return armature
    if active_fallback and context is not None:
        return active_armature(context)
    return None


def bind_armature(tree: Any, armature: Any) -> None:
    owner = binding_tree(tree)
    if owner is None:
        raise ValueError("AnimGraph tree is required")
    if armature is not None and getattr(armature, "type", None) != "ARMATURE":
        raise TypeError("AnimGraph binding target must be an armature")
    owner.red_bound_armature = armature


def bound_rig_names(tree: Any, context: Any = None) -> tuple[str, ...]:
    armature = bound_armature(tree, context, active_fallback=False)
    return armature_rig_names(armature)


def armature_rig_names(armature: Any) -> tuple[str, ...]:
    return armature_bone_names(armature) if armature is not None else ()


def bound_rig_parent_map(tree: Any, context: Any = None) -> dict[str, str]:
    armature = bound_armature(tree, context, active_fallback=False)
    return armature_rig_parent_map(armature)


def armature_rig_parent_map(armature: Any) -> dict[str, str]:
    return armature_bone_parent_map(armature) if armature is not None else {}
