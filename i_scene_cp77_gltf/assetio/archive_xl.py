from __future__ import annotations

import json
import math
from collections.abc import Sequence
from dataclasses import dataclass


def _require_counted(kind: str, indices: Sequence[int], expected: int | None) -> None:
    """Refuse a sub-entry list ArchiveXL cannot read"""
    if indices and (
        expected is None or any(not 0 <= index < expected for index in indices)
    ):
        raise ValueError(
            f"{kind} {list(indices)} need an expected count that holds them, not {expected}"
        )


@dataclass(frozen=True, slots=True)
class InstanceMutation:
    """One instance of an instanced node moved to a world transform"""

    index: int
    position: tuple[float, float, float]
    orientation: tuple[float, float, float, float]
    scale: tuple[float, float, float] | None = None


@dataclass(frozen=True, slots=True)
class ActorMutation:
    """One actor of a collision node moved to a world transform"""

    index: int
    position: tuple[float, float, float]
    orientation: tuple[float, float, float, float]


@dataclass(frozen=True, slots=True)
class NodeMutation:
    """The node data entry index of type node_type moved to a new placement"""

    index: int
    node_type: str
    position: tuple[float, float, float] | None = None
    orientation: tuple[float, float, float, float] | None = None
    scale: tuple[float, float, float] | None = None
    instance_mutations: tuple[InstanceMutation, ...] = ()
    expected_instances: int | None = None
    actor_mutations: tuple[ActorMutation, ...] = ()
    expected_actors: int | None = None

    def __post_init__(self):
        _require_counted(
            "instance mutations",
            [entry.index for entry in self.instance_mutations],
            self.expected_instances,
        )
        _require_counted(
            "actor mutations",
            [entry.index for entry in self.actor_mutations],
            self.expected_actors,
        )


@dataclass(frozen=True, slots=True)
class NodeDeletion:
    """The node data entry index of type node_type deleted, or only the listed instances or actors of it"""

    index: int
    node_type: str
    instance_deletions: tuple[int, ...] = ()
    expected_instances: int | None = None
    actor_deletions: tuple[int, ...] = ()
    expected_actors: int | None = None

    def __post_init__(self):
        _require_counted(
            "instance deletions", self.instance_deletions, self.expected_instances
        )
        _require_counted("actor deletions", self.actor_deletions, self.expected_actors)


@dataclass(frozen=True, slots=True)
class SectorEdits:
    """The edits to the sector at depot path path, which holds expected_nodes node data entries"""

    path: str
    expected_nodes: int
    deletions: tuple[NodeDeletion, ...]
    mutations: tuple[NodeMutation, ...]

    def __post_init__(self):
        for edit in (*self.deletions, *self.mutations):
            if not 0 <= edit.index < self.expected_nodes:
                raise ValueError(
                    f"{self.path}: node {edit.index} lies outside its {self.expected_nodes} nodes"
                )


def _floats(values: Sequence[float]) -> list[float]:
    return [float(value) for value in values]


def _sub_mutation(
    entry: InstanceMutation | ActorMutation, scale: Sequence[float] | None = None
) -> dict:
    data = {
        "index": entry.index,
        "position": [*_floats(entry.position), 0.0],
        "orientation": _floats(entry.orientation),
    }
    if scale is not None:
        data["scale"] = _floats(scale)
    return data


def _node_mutation(mutation: NodeMutation) -> dict:
    data = {"index": mutation.index, "type": mutation.node_type}
    for key, value in (
        ("position", mutation.position),
        ("orientation", mutation.orientation),
        ("scale", mutation.scale),
    ):
        if value is not None:
            data[key] = _floats(value)
    if mutation.instance_mutations:
        data["instanceMutations"] = [
            _sub_mutation(entry, entry.scale) for entry in mutation.instance_mutations
        ]
        data["expectedInstances"] = mutation.expected_instances
    if mutation.actor_mutations:
        data["actorMutations"] = [
            _sub_mutation(entry) for entry in mutation.actor_mutations
        ]
        data["expectedActors"] = mutation.expected_actors
    return data


def _node_deletion(deletion: NodeDeletion) -> dict:
    data = {"index": deletion.index, "type": deletion.node_type}
    if deletion.instance_deletions:
        data["instanceDeletions"] = list(deletion.instance_deletions)
        data["expectedInstances"] = deletion.expected_instances
    if deletion.actor_deletions:
        data["actorDeletions"] = list(deletion.actor_deletions)
        data["expectedActors"] = deletion.expected_actors
    return data


def archive_xl_document(sectors: Sequence[SectorEdits], blocks: Sequence[str]) -> dict:
    """The .xl document"""
    entries = []
    for sector in sectors:
        if not sector.deletions and not sector.mutations:
            continue
        entry = {"path": sector.path, "expectedNodes": sector.expected_nodes}
        if sector.deletions:
            entry["nodeDeletions"] = [
                _node_deletion(deletion) for deletion in sector.deletions
            ]
        if sector.mutations:
            entry["nodeMutations"] = [
                _node_mutation(mutation) for mutation in sector.mutations
            ]
        entries.append(entry)
    return {"streaming": {"sectors": entries, "blocks": list(blocks)}}


def _yaml_scalar(value):
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("ArchiveXL YAML cannot contain non-finite numbers.")
        return repr(value)
    if isinstance(value, str):
        # JSON double-quoted strings are valid YAML scalars and safely preserve
        # depot-path backslashes, punctuation, and Unicode.
        return json.dumps(value, ensure_ascii=False)
    raise TypeError(f"Unsupported ArchiveXL YAML value: {type(value).__name__}")


def _yaml_lines(value, indent=0):
    prefix = " " * indent
    if isinstance(value, dict):
        if not value:
            yield f"{prefix}{{}}"
            return
        for key, child in value.items():
            key_text = _yaml_scalar(str(key))
            if isinstance(child, (dict, list)):
                if child:
                    yield f"{prefix}{key_text}:"
                    yield from _yaml_lines(child, indent + 2)
                else:
                    empty = "{}" if isinstance(child, dict) else "[]"
                    yield f"{prefix}{key_text}: {empty}"
            else:
                yield f"{prefix}{key_text}: {_yaml_scalar(child)}"
        return
    if isinstance(value, list):
        if not value:
            yield f"{prefix}[]"
            return
        for child in value:
            if isinstance(child, (dict, list)):
                if child:
                    yield f"{prefix}-"
                    yield from _yaml_lines(child, indent + 2)
                else:
                    empty = "{}" if isinstance(child, dict) else "[]"
                    yield f"{prefix}- {empty}"
            else:
                yield f"{prefix}- {_yaml_scalar(child)}"
        return
    yield f"{prefix}{_yaml_scalar(value)}"


def serialize_archive_xl(data, *, use_yaml=False):
    if use_yaml:
        return "\n".join(_yaml_lines(data)) + "\n"
    return json.dumps(data, indent=4)
