from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from ..common.entity_data import (
    build_chunk_handle_lookup as _build_chunk_lookup,
    component_name,
)
from ..common.paths import depot_path_value
from .policy import NON_VISUAL_MESH_COMPONENT_TYPES


@dataclass(frozen=True, slots=True)
class ComponentPassIndex:
    components: tuple[dict, ...]
    by_name: dict[str, dict]
    rig_components: tuple[dict, ...]
    slot_components: tuple[dict, ...]
    mesh_components: tuple[dict, ...]
    transform_animator_components: tuple[dict, ...]


def merge_component_groups(*component_groups):
    merged = []
    seen = set()
    for components in component_groups:
        for component in components or ():
            if type(component) is not dict:
                continue
            identity = id(component)
            if identity in seen:
                continue
            seen.add(identity)
            merged.append(component)
    return tuple(merged), tuple(id(component) for component in merged)


class EntityExecutionCache:
    """Cache repeated component scans and derived placement decisions."""

    __slots__ = (
        "_chunk_lookups",
        "_component_indexes",
        "_slot_lookups",
        "_skin_attachments",
        "_skinning_decisions",
        "_component_collections",
        "_hits",
        "_misses",
    )

    def __init__(self) -> None:
        self._chunk_lookups: dict[tuple[int, str, str, int], tuple[Any, Any]] = {}
        self._component_indexes: dict[tuple[Any, ...], tuple[Any, Any]] = {}
        self._slot_lookups: dict[tuple[int, int], tuple[Any, Any]] = {}
        self._skin_attachments: dict[tuple[int, int], tuple[Any, Any, Any]] = {}
        self._skinning_decisions: dict[tuple[int, int], tuple[Any, Any, bool]] = {}
        self._component_collections: dict[tuple[str, tuple[tuple[int, int], ...]], tuple[tuple[Any, ...], Any]] = {}
        self._hits = 0
        self._misses = 0

    @staticmethod
    def _source_sequence(source: Iterable[Any] | None) -> Any:
        if isinstance(source, (list, tuple)):
            return source
        return tuple(source or ())

    def chunk_lookup(
        self,
        chunks: Iterable[dict] | None,
        target_key: str,
        handle_key: str,
        builder: Callable[[Any, str, str], Any],
    ) -> Any:
        source = self._source_sequence(chunks)
        key = (id(source), target_key, handle_key, len(source))
        cached = self._chunk_lookups.get(key)
        if cached is not None and cached[0] is source:
            self._hits += 1
            return cached[1]
        value = builder(source, target_key, handle_key)
        self._chunk_lookups[key] = (source, value)
        self._misses += 1
        return value

    def component_index(
        self,
        components: Iterable[dict] | None,
        builder: Callable[[Any], Any],
        *,
        identity_token: tuple[int, ...] | None = None,
    ) -> Any:
        source = self._source_sequence(components)
        if identity_token is None:
            key = ("source", id(source), len(source))
            cached = self._component_indexes.get(key)
            if cached is not None and cached[0] is source:
                self._hits += 1
                return cached[1]
        else:
            token = tuple(identity_token)
            key = ("members", token)
            cached = self._component_indexes.get(key)
            if cached is not None:
                cached_source, cached_value = cached
                if len(cached_source) == len(source) and all(
                    current is previous
                    for current, previous in zip(source, cached_source)
                ):
                    self._hits += 1
                    return cached_value
        value = builder(source)
        self._component_indexes[key] = (source, value)
        self._misses += 1
        return value

    def slot_lookup(
        self,
        slots: Iterable[dict] | None,
        builder: Callable[[Any], Any],
    ) -> Any:
        source = self._source_sequence(slots)
        key = (id(source), len(source))
        cached = self._slot_lookups.get(key)
        if cached is not None and cached[0] is source:
            self._hits += 1
            return cached[1]
        value = builder(source)
        self._slot_lookups[key] = (source, value)
        self._misses += 1
        return value

    def skin_attachment(
        self,
        component: dict,
        rig_json: Any,
        mesh_json_loader: Callable[[dict], Any],
        evaluator: Callable[[Any, Any], Any],
    ) -> Any:
        key = (id(component), id(rig_json))
        cached = self._skin_attachments.get(key)
        if cached is not None and cached[0] is component and cached[1] is rig_json:
            self._hits += 1
            return cached[2]
        value = evaluator(mesh_json_loader(component), rig_json)
        self._skin_attachments[key] = (component, rig_json, value)
        self._misses += 1
        return value

    def uses_skinning(
        self,
        component: dict,
        lookup: Any,
        evaluator: Callable[[dict, Any], bool],
    ) -> bool:
        key = (id(component), id(lookup))
        cached = self._skinning_decisions.get(key)
        if cached is not None and cached[0] is component and cached[1] is lookup:
            self._hits += 1
            return cached[2]
        value = bool(evaluator(component, lookup))
        self._skinning_decisions[key] = (component, lookup, value)
        self._misses += 1
        return value

    def collect_components(
        self,
        kind: str,
        component_groups: tuple[Iterable[dict] | None, ...],
        collector: Callable[..., Any],
    ) -> Any:
        groups = tuple(self._source_sequence(group) for group in component_groups)
        key = (kind, tuple((id(group), len(group)) for group in groups))
        cached = self._component_collections.get(key)
        if cached is not None:
            cached_groups, cached_value = cached
            if len(cached_groups) == len(groups) and all(
                current is previous for current, previous in zip(groups, cached_groups)
            ):
                self._hits += 1
                return cached_value
        value = collector(*groups)
        self._component_collections[key] = (groups, value)
        self._misses += 1
        return value

    def stats(self) -> dict[str, int]:
        return {
            "hits": self._hits,
            "misses": self._misses,
            "component_indexes": len(self._component_indexes),
            "chunk_lookups": len(self._chunk_lookups),
            "slot_lookups": len(self._slot_lookups),
            "skin_attachments": len(self._skin_attachments),
            "skinning_decisions": len(self._skinning_decisions),
            "component_collections": len(self._component_collections),
        }

    def clear(self) -> None:
        self._chunk_lookups.clear()
        self._component_indexes.clear()
        self._slot_lookups.clear()
        self._skin_attachments.clear()
        self._skinning_decisions.clear()
        self._component_collections.clear()
        self._hits = 0
        self._misses = 0


def build_chunk_lookup(chunks, target_key, handle_key="HandleId", cache=None):
    if cache is None:
        return _build_chunk_lookup(chunks, target_key, handle_key)
    return cache.chunk_lookup(chunks, target_key, handle_key, _build_chunk_lookup)


def _build_component_pass_index(components):
    indexed_components = []
    by_name = {}
    rig_components = []
    slot_components = []
    mesh_components = []
    transform_animator_components = []
    for component in components or ():
        if type(component) is not dict:
            continue
        indexed_components.append(component)
        name = component_name(component)
        if name:
            by_name.setdefault(name, component)
        component_type = component.get("$type")
        if depot_path_value(component, "rig"):
            rig_components.append(component)
        if isinstance(component.get("slots"), list):
            slot_components.append(component)
        if (
            ("mesh" in component or "graphicsMesh" in component)
            and component_type not in NON_VISUAL_MESH_COMPONENT_TYPES
        ):
            mesh_components.append(component)
        if component_type == "gameTransformAnimatorComponent":
            transform_animator_components.append(component)
    return ComponentPassIndex(
        components=tuple(indexed_components),
        by_name=by_name,
        rig_components=tuple(rig_components),
        slot_components=tuple(slot_components),
        mesh_components=tuple(mesh_components),
        transform_animator_components=tuple(transform_animator_components),
    )


def build_component_pass_index(
    components,
    cache=None,
    *,
    identity_token=None,
):
    if cache is None:
        return _build_component_pass_index(components)
    return cache.component_index(
        components,
        _build_component_pass_index,
        identity_token=identity_token,
    )


class ComponentHandleLookup:
    __slots__ = ("default_lookup", "by_component_id")

    def __init__(self, default_lookup=None):
        self.default_lookup = default_lookup or {}
        self.by_component_id = {}

    def set_component_lookup(self, component, lookup):
        if type(component) is dict:
            self.by_component_id[id(component)] = lookup or {}

    def get_for_component(self, component, handle_id):
        lookup = self.by_component_id.get(id(component), self.default_lookup)
        return lookup.get(handle_id)
