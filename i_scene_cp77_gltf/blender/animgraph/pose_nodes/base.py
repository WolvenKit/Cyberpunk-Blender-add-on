from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from typing import Any

from ....animation.handlers.animgraph.registry import POSE_OP_HANDLERS
from ...action_metadata import armature_track_names
from ...armature_bones import resolve_pose_bone
from .. import rig_binding


class PosePreviewError(RuntimeError):
    pass


@dataclass(frozen=True)
class NodeSpec:
    data: Mapping[str, Any]
    validation_data: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class NodeEvaluation:
    written_bones: Iterable[str] = ()
    written_tracks: Iterable[str] = ()
    dynamic_weights: int = 0


def available_tracks(armature) -> set[str]:
    names = set(armature_track_names(armature))
    if names:
        return names
    return {
        str(name)
        for name in armature.keys()
        if isinstance(armature.get(name), (float, int))
        and not isinstance(armature.get(name), bool)
    }


class BindingContext:
    """Bone and track availability of the armature a chain is planned against"""

    def __init__(self, armature):
        self.armature = armature
        rig_names = set(rig_binding.armature_rig_names(armature))
        rig_names.update(rig_binding.armature_rig_parent_map(armature))
        self._rig_names = rig_names
        self.known_tracks = available_tracks(armature)

    def has_bone(self, name: str) -> bool:
        if not name:
            return False
        return (
            name in self._rig_names
            or resolve_pose_bone(self.armature, name) is not None
        )

    def has_track(self, name: str) -> bool:
        return bool(name) and name in self.known_tracks


class PlanNameResolver:
    """A chain plan's bone and track names, resolved for the pose operation handlers"""

    def __init__(self, resolved: Mapping[str, str], requested_tracks: frozenset[str]):
        self._resolved = resolved
        self._requested_tracks = requested_tracks

    def resolve_structured_bone(self, authored: str, *, required: bool = False) -> str:
        return self._resolved.get(str(authored or ""), "")

    def resolve_structured_track(self, authored: str, *, required: bool = False) -> str:
        name = str(authored or "")
        return name if name in self._requested_tracks else ""


def input_socket(node: Any, path: str):
    for socket in getattr(node, "inputs", ()) or ():
        if str(getattr(socket, "red_json_path", "") or "") == path:
            return socket
    return None


def linked_node(socket: Any):
    links = tuple(getattr(socket, "links", ()) or ()) if socket is not None else ()
    return getattr(links[0], "from_node", None) if links else None


def short_type(node: Any) -> str:
    return str(getattr(node, "red_type", "") or "").removeprefix("animAnimNode_")


def text(mapping: Mapping[str, Any], key: str) -> str:
    return str(mapping.get(key, "") or "")


def float_track_requested(
    data: Mapping[str, Any], mode_key: str, track_key: str
) -> set[str]:
    if text(data, mode_key) != "FloatTrack":
        return set()
    name = text(data, track_key)
    return {name} if name else set()


def check_schema(label: str, validation, index: int, validate_schema: bool) -> None:
    if validate_schema and validation.blocking:
        raise PosePreviewError(
            f"{label} chain node {index + 1}: " + "; ".join(validation.blocking)
        )


class PoseNodeHandler:
    """Plans and evaluates one pose-processing node type inside a preview chain"""

    label = ""

    def spec(self, node, tree):
        raise NotImplementedError

    def bone_names(self, spec) -> set[str]:
        return set()

    def optional_bone_names(self, spec) -> set[str]:
        return set()

    def track_names(self, spec) -> set[str]:
        return set()

    def optional_track_names(self, spec) -> set[str]:
        return set()

    def executable(
        self, spec, index: int, binding: BindingContext, *, validate_schema: bool
    ) -> bool:
        return True

    def runtime_spec(self, spec, node_type: str, names: PlanNameResolver):
        handler = POSE_OP_HANDLERS.get(node_type)
        if handler is None:
            return spec
        return replace(
            spec, data=handler.map_data(names, None, node_type, dict(spec.data))
        )

    def evaluate(self, spec, plan, state, tracks) -> NodeEvaluation:
        raise NotImplementedError

    def is_dynamic(self, spec) -> bool:
        return False

    def refresh(self, node, tree, spec, runtime_spec):
        return spec, runtime_spec

    def node_validation(self, node, armature):
        """Schema validation shown in the node editor, or None when the type has none"""
        return
