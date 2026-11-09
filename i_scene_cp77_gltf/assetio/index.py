import os
import threading
import time
from collections import OrderedDict
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType

from ..core.log import debug_exception, get_logger
from .cache import store_bounded_lru
from .catalog import (
    COOKED_RESOURCE_EXPORTS,
    COOKED_RESOURCE_SUFFIXES,
    EXPORT_GROUPS_BY_OUTPUT_EXTENSION,
    EXPORTED_RESOURCE_SUFFIXES,
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

_LOG = get_logger(__name__)

_SKIP_DIRS = frozenset(
    {
        "__pycache__",
        ".git",
        ".svn",
        "node_modules",
        ".vscode",
        ".idea",
        "archive",
        "backup",
    }
)


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
    directory_mtimes: tuple[tuple[str, int], ...] = ()
    depth: int | None = None

    @property
    def extensions(self):
        return frozenset(self.indexed_suffixes)

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
        return export_candidates(
            reference,
            export_extensions or self.indexed_suffixes,
        )

    def resolve_export(self, reference, export_extensions=None, warn=False):
        for candidate in self.export_candidates(reference, export_extensions):
            resolved, ambiguous = self._resolve_candidate(candidate)
            if resolved:
                return resolved
            if ambiguous:
                if warn:
                    _LOG.warning(
                        "Asset reference is ambiguous and will be skipped: %s",
                        candidate,
                    )
                return None

        if warn:
            _LOG.warning(
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


def export_candidates(reference, export_extensions):
    value = os.fspath(reference) if reference else ""
    if not value:
        return []

    requested = normalize_extensions(export_extensions)
    if not requested:
        return []
    key = value.replace("\\", "/").casefold()
    cooked_suffix = _first_matching_suffix(key, COOKED_RESOURCE_SUFFIXES)
    exported_suffix = (
        ""
        if cooked_suffix
        else _first_matching_suffix(
            key,
            EXPORTED_RESOURCE_SUFFIXES,
        )
    )

    if cooked_suffix:
        base = value[: -len(cooked_suffix)]
        outputs = COOKED_RESOURCE_EXPORTS[cooked_suffix]
    elif exported_suffix:
        base = value[: -len(exported_suffix)]
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


_cache_lock = threading.RLock()
_snapshots_by_key = OrderedDict()
# Snapshots of a few folder levels are kept apart, so many of them never push a whole tree's snapshot out.
_shallow_snapshots_by_key = OrderedDict()
_name_lookups = OrderedDict()
_next_generation = 0
_MAX_CACHED_INDEXES = 64
_MAX_SHALLOW_INDEXES = 512
# Reused snapshots are revalidated against directory mtimes at most this often,
# so one import does not repeat the check while a later import sees new exports.
_VALIDATION_INTERVAL_SECONDS = 2.0
# Trees beyond this size (a full game depot) are static in practice; they keep
# session-lifetime reuse and are refreshed explicitly by the user.
_MAX_VALIDATED_DIRECTORIES = 20000
_validated_at = {}


def _snapshot_is_current(snapshot):
    mtimes = snapshot.directory_mtimes
    if not mtimes:
        return not os.path.isdir(snapshot.root.value)
    if len(mtimes) > _MAX_VALIDATED_DIRECTORIES:
        return True
    # One stamp per root and suffix set, holding the generation it checked: a rescan replaces it rather than adding one.
    key = (snapshot.root.key, snapshot.indexed_suffixes, snapshot.depth)
    now = time.monotonic()
    checked = _validated_at.get(key)
    if (
        checked is not None
        and checked[0] == snapshot.generation
        and now - checked[1] < _VALIDATION_INTERVAL_SECONDS
    ):
        return True
    for folder, mtime in mtimes:
        try:
            if os.stat(folder).st_mtime_ns != mtime:
                return False
        except OSError:
            debug_exception(
                _LOG,
                "Could not read the time of %s; the asset index is rebuilt",
                folder,
            )
            return False
    with _cache_lock:
        _validated_at[key] = (snapshot.generation, now)
    return True


def build_asset_index(root, extensions, *, policy=IndexPolicy.REUSE, depth=None):
    """The files under root with extensions"""
    global _next_generation
    root_identity = LocalPath.from_value(root)
    suffixes = normalize_extensions(extensions)
    policy = IndexPolicy(policy)
    depth = None if depth is None else max(0, int(depth))
    cache = _snapshots_by_key if depth is None else _shallow_snapshots_by_key
    cache_key = (root_identity.key, suffixes, depth)

    selected = None
    if policy is IndexPolicy.REUSE:
        with _cache_lock:
            requested = set(suffixes)
            compatible = [
                snapshot
                for (root_key, _, snapshot_depth), snapshot in cache.items()
                if root_key == root_identity.key and snapshot_depth == depth
                if requested.issubset(snapshot.extensions)
            ]
            if compatible:
                selected = max(
                    compatible,
                    key=lambda snapshot: snapshot.generation,
                )
    if selected is not None:
        if _snapshot_is_current(selected):
            with _cache_lock:
                selected_key = (
                    selected.root.key,
                    selected.indexed_suffixes,
                    selected.depth,
                )
                if selected_key in cache:
                    cache.move_to_end(selected_key)
            return selected
        _LOG.debug("Asset index for %s is stale; rescanning", root_identity.value)

    with _cache_lock:
        _next_generation += 1
        generation = _next_generation

    # Filesystem traversal is deliberately outside the global cache lock.
    snapshot = _scan_snapshot(root_identity, suffixes, generation, depth)

    with _cache_lock:
        existing = cache.get(cache_key)
        if existing is not None and existing.generation > snapshot.generation:
            cache.move_to_end(cache_key)
            return existing
        return store_bounded_lru(
            cache,
            cache_key,
            snapshot,
            limit=_MAX_CACHED_INDEXES if depth is None else _MAX_SHALLOW_INDEXES,
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


def files_by_name(asset_index, extension, *, folder_suffix=""):
    """The indexed extension files in a folder whose name ends with folder_suffix"""
    suffix = normalize_extension(extension)
    folder_suffix = str(folder_suffix or "").casefold()
    key = (asset_index.generation, suffix, folder_suffix)
    with _cache_lock:
        cached = _name_lookups.get(key)
        if cached is not None:
            _name_lookups.move_to_end(key)
            return cached
    found = {}
    for path in asset_index.files_by_suffix.get(suffix, ()):
        if os.path.basename(os.path.dirname(path)).casefold().endswith(folder_suffix):
            found.setdefault(os.path.basename(path).casefold(), path)
    with _cache_lock:
        return store_bounded_lru(
            _name_lookups, key, MappingProxyType(found), limit=_MAX_SHALLOW_INDEXES
        )


def _scan_snapshot(root, suffixes, generation, depth=None):
    files_by_suffix = {suffix: [] for suffix in suffixes}
    local_lookup = {suffix: {} for suffix in suffixes}
    depot_lookup = {suffix: {} for suffix in suffixes}
    local_collision_paths = {suffix: {} for suffix in suffixes}
    depot_collision_paths = {suffix: {} for suffix in suffixes}

    directory_mtimes = []
    if not os.path.isdir(root.value):
        _LOG.warning("Root directory not found: %s", root.value)
    else:
        try:
            directory_mtimes.append((root.value, os.stat(root.value).st_mtime_ns))
        except OSError:
            debug_exception(
                _LOG,
                "Could not read the time of %s; the snapshot leaves it out",
                root.value,
            )
        stack = [(root.value, "", 0)]
        while stack:
            folder, relative_folder, level = stack.pop()
            try:
                with os.scandir(folder) as entries:
                    for entry in entries:
                        try:
                            if entry.is_dir(follow_symlinks=False):
                                if entry.name.casefold() not in _SKIP_DIRS and (
                                    depth is None or level < depth
                                ):
                                    child_relative = (
                                        os.path.join(relative_folder, entry.name)
                                        if relative_folder
                                        else entry.name
                                    )
                                    stack.append(
                                        (entry.path, child_relative, level + 1)
                                    )
                                    directory_mtimes.append(
                                        (
                                            entry.path,
                                            entry.stat(
                                                follow_symlinks=False
                                            ).st_mtime_ns,
                                        )
                                    )
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
                            _LOG.debug("Could not access %s: %s", entry.path, error)
            except (PermissionError, OSError) as error:
                _LOG.warning(
                    "Could not scan directory %s: %s", folder, error, exc_info=True
                )

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
        directory_mtimes=tuple(directory_mtimes),
        depth=depth,
    )


# Scanned paths need no normalizing: local_path_key and depot_path_key give these keys 4x slower and fill their caches.
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
