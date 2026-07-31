import logging
import os
import threading
from collections import OrderedDict
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType

from .catalog import (
    COOKED_RESOURCE_EXPORTS,
    COOKED_RESOURCE_SUFFIXES,
    EXPORTED_RESOURCE_SUFFIXES,
    EXPORT_GROUPS_BY_OUTPUT_EXTENSION,
    normalize_extension,
    normalize_extensions,
)
from .paths import (
    DepotPath,
    LocalPath,
    depot_path_key,
    is_local_absolute,
    local_path_key,
)


_SKIP_DIRS = frozenset({
    "__pycache__",
    ".git",
    ".svn",
    "node_modules",
    ".vscode",
    ".idea",
    "archive",
    "backup",
})


class IndexPolicy(str, Enum):
    REUSE = "reuse"
    REFRESH = "refresh"


@dataclass(frozen=True, slots=True)
class IndexCollision:
    extension: str
    key_type: str
    key: str
    paths: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AssetIndexSnapshot:
    root: LocalPath
    generation: int
    indexed_suffixes: tuple[str, ...]
    files_by_suffix: Mapping[str, tuple[str, ...]]
    collisions: tuple[IndexCollision, ...]
    _local_lookup: Mapping[str, Mapping[str, str]]
    _depot_lookup: Mapping[str, Mapping[str, str]]
    _ambiguous_local: Mapping[str, frozenset[str]]
    _ambiguous_depot: Mapping[str, frozenset[str]]

    @property
    def extensions(self):
        return frozenset(self.indexed_suffixes)

    @property
    def has_collisions(self):
        return bool(self.collisions)

    def get_files_by_extension(self, extension):
        suffix = normalize_extension(extension)
        return list(self.files_by_suffix.get(suffix, ()))

    def files(self, extension):
        return self.get_files_by_extension(extension)

    def contains(self, path, extension):
        suffix = normalize_extension(extension)
        if is_local_absolute(path):
            return local_path_key(path) in self._local_lookup.get(suffix, {})
        return depot_path_key(path) in self._depot_lookup.get(suffix, {})

    def export_candidates(self, reference, export_extensions=None):
        value = os.fspath(reference) if reference else ""
        if not value:
            return []

        requested = normalize_extensions(export_extensions or self.indexed_suffixes)
        key = value.replace("\\", "/").casefold()
        cooked_suffix = _first_matching_suffix(key, COOKED_RESOURCE_SUFFIXES)
        exported_suffix = "" if cooked_suffix else _first_matching_suffix(
            key,
            EXPORTED_RESOURCE_SUFFIXES,
        )

        if cooked_suffix:
            base = value[:-len(cooked_suffix)]
            outputs = COOKED_RESOURCE_EXPORTS[cooked_suffix]
        elif exported_suffix:
            base = value[:-len(exported_suffix)]
            outputs = EXPORT_GROUPS_BY_OUTPUT_EXTENSION[exported_suffix]
        else:
            current = _first_matching_suffix(key, requested)
            if current:
                return [value]
            base = value
            outputs = requested

        candidates = []
        seen = set()
        requested_set = set(requested)
        for output in outputs:
            if output not in requested_set:
                continue
            candidate = f"{base}{output}"
            candidate_key = candidate.replace("\\", "/").casefold()
            if candidate_key in seen:
                continue
            seen.add(candidate_key)
            candidates.append(candidate)
        return candidates

    def resolve_export(self, reference, export_extensions=None, warn=False):
        for candidate in self.export_candidates(reference, export_extensions):
            resolved, ambiguous = self._resolve_candidate(candidate)
            if resolved:
                return resolved
            if ambiguous:
                if warn:
                    logging.warning(
                        "Asset reference is ambiguous and will be skipped: %s",
                        candidate,
                    )
                return None

        if warn:
            logging.warning(
                "Exported asset reference is not indexed and will be skipped: %s",
                reference,
            )
        return None

    def resolve_expected(self, reference, expected_extension, warn=False):
        return self.resolve_export(reference, (expected_extension,), warn=warn)

    def resolve_any(self, reference, extensions=None, warn=False):
        return self.resolve_export(reference, extensions, warn=warn)

    def _resolve_candidate(self, candidate):
        suffix = _first_matching_suffix(
            str(candidate).replace("\\", "/").casefold(),
            self.indexed_suffixes,
        )
        if not suffix:
            return None, False

        if is_local_absolute(candidate):
            key = local_path_key(candidate)
            ambiguous = key in self._ambiguous_local.get(suffix, frozenset())
            return self._local_lookup.get(suffix, {}).get(key), ambiguous

        key = DepotPath.from_value(candidate).key
        ambiguous = key in self._ambiguous_depot.get(suffix, frozenset())
        return self._depot_lookup.get(suffix, {}).get(key), ambiguous


_cache_lock = threading.RLock()
_snapshots_by_key = OrderedDict()
_next_generation = 0
_MAX_CACHED_INDEXES = 64


def build_asset_index(root, extensions, *, policy=IndexPolicy.REUSE):
    global _next_generation
    root_identity = LocalPath.from_value(root)
    suffixes = normalize_extensions(extensions)
    policy = IndexPolicy(policy)
    cache_key = (root_identity.key, suffixes)

    with _cache_lock:
        if policy is IndexPolicy.REUSE:
            requested = set(suffixes)
            compatible = [
                snapshot
                for (root_key, _), snapshot in _snapshots_by_key.items()
                if root_key == root_identity.key
                if requested.issubset(snapshot.extensions)
            ]
            if compatible:
                selected = max(
                    compatible,
                    key=lambda snapshot: snapshot.generation,
                )
                selected_key = (selected.root.key, selected.indexed_suffixes)
                if selected_key in _snapshots_by_key:
                    _snapshots_by_key.move_to_end(selected_key)
                return selected
        _next_generation += 1
        generation = _next_generation

    # Filesystem traversal is deliberately outside the global cache lock.
    snapshot = _scan_snapshot(root_identity, suffixes, generation)

    with _cache_lock:
        existing = _snapshots_by_key.get(cache_key)
        if existing is not None and (
            policy is IndexPolicy.REUSE
            or existing.generation > snapshot.generation
        ):
            _snapshots_by_key.move_to_end(cache_key)
            return existing
        _snapshots_by_key[cache_key] = snapshot
        _snapshots_by_key.move_to_end(cache_key)
        while len(_snapshots_by_key) > _MAX_CACHED_INDEXES:
            _snapshots_by_key.popitem(last=False)
        return snapshot


def clear_asset_index_cache(root=None):
    with _cache_lock:
        if root is None:
            _snapshots_by_key.clear()
            return
        root_key = LocalPath.from_value(root).key
        for key in tuple(_snapshots_by_key):
            if key[0] == root_key:
                _snapshots_by_key.pop(key, None)


def cached_asset_indexes(root=None):
    with _cache_lock:
        if root is None:
            return tuple(_snapshots_by_key.values())
        root_key = LocalPath.from_value(root).key
        return tuple(
            snapshot
            for (snapshot_root, _), snapshot in _snapshots_by_key.items()
            if snapshot_root == root_key
        )


def indexed_files(asset_index, *extensions):
    files = []
    seen = set()
    for extension in extensions:
        for filepath in asset_index.get_files_by_extension(extension):
            key = local_path_key(filepath)
            if key in seen:
                continue
            seen.add(key)
            files.append(filepath)
    return tuple(files)


def _scan_snapshot(root, suffixes, generation):
    files_by_suffix = {suffix: [] for suffix in suffixes}
    local_lookup = {suffix: {} for suffix in suffixes}
    depot_lookup = {suffix: {} for suffix in suffixes}
    local_collision_paths = {suffix: {} for suffix in suffixes}
    depot_collision_paths = {suffix: {} for suffix in suffixes}

    if not os.path.isdir(root.value):
        logging.error("Root directory not found: %s", root.value)
    else:
        stack = [(root.value, "")]
        while stack:
            folder, relative_folder = stack.pop()
            try:
                with os.scandir(folder) as entries:
                    for entry in entries:
                        try:
                            if entry.is_dir(follow_symlinks=False):
                                if entry.name.casefold() not in _SKIP_DIRS:
                                    child_relative = (
                                        os.path.join(relative_folder, entry.name)
                                        if relative_folder
                                        else entry.name
                                    )
                                    stack.append((entry.path, child_relative))
                                continue
                            if not entry.is_file(follow_symlinks=False):
                                continue
                            suffix = _first_matching_suffix(
                                entry.name.casefold(),
                                suffixes,
                            )
                            if not suffix:
                                continue

                            path = os.path.normpath(entry.path)
                            relative = (
                                os.path.join(relative_folder, entry.name)
                                if relative_folder
                                else entry.name
                            )
                            files_by_suffix[suffix].append(path)
                            _record_lookup(
                                local_lookup[suffix],
                                local_collision_paths[suffix],
                                _indexed_local_key(path),
                                path,
                            )
                            _record_lookup(
                                depot_lookup[suffix],
                                depot_collision_paths[suffix],
                                _indexed_depot_key(relative),
                                path,
                            )
                        except (PermissionError, OSError) as error:
                            logging.debug("Could not access %s: %s", entry.path, error)
            except (PermissionError, OSError) as error:
                logging.warning("Could not scan directory %s: %s", folder, error)

    collisions = []
    ambiguous_local = {}
    ambiguous_depot = {}
    for suffix in suffixes:
        files_by_suffix[suffix] = tuple(sorted(files_by_suffix[suffix]))
        ambiguous_local[suffix] = frozenset(local_collision_paths[suffix])
        ambiguous_depot[suffix] = frozenset(depot_collision_paths[suffix])
        collisions.extend(
            _collision_records(suffix, "local", local_collision_paths[suffix])
        )
        collisions.extend(
            _collision_records(suffix, "depot", depot_collision_paths[suffix])
        )
        local_lookup[suffix] = MappingProxyType(local_lookup[suffix])
        depot_lookup[suffix] = MappingProxyType(depot_lookup[suffix])

    return AssetIndexSnapshot(
        root=root,
        generation=generation,
        indexed_suffixes=suffixes,
        files_by_suffix=MappingProxyType(files_by_suffix),
        collisions=tuple(collisions),
        _local_lookup=MappingProxyType(local_lookup),
        _depot_lookup=MappingProxyType(depot_lookup),
        _ambiguous_local=MappingProxyType(ambiguous_local),
        _ambiguous_depot=MappingProxyType(ambiguous_depot),
    )



def _indexed_local_key(path):
    return os.path.normcase(path).replace("\\", "/")


def _indexed_depot_key(path):
    return path.replace("\\", "/").casefold()

def _record_lookup(lookup, collision_paths, key, path):
    if key in collision_paths:
        collision_paths[key].append(path)
        return
    previous = lookup.get(key)
    if previous is None:
        lookup[key] = path
        return
    lookup.pop(key, None)
    collision_paths[key] = [previous, path]


def _collision_records(extension, key_type, collisions):
    return (
        IndexCollision(
            extension,
            key_type,
            key,
            tuple(sorted(set(paths))),
        )
        for key, paths in collisions.items()
    )


def _first_matching_suffix(value, suffixes):
    for suffix in suffixes:
        if value.endswith(suffix):
            return suffix
    return ""
