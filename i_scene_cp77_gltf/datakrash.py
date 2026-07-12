"""Fast cached file indexing and exact depot asset resolution."""

import logging
import os
from functools import lru_cache
from typing import Dict, Iterable, List, Set

_file_index_cache: Dict[str, Set[str]] = {}
_cache_root = None
_cache_extensions: Set[str] = set()
_root_index_cache = {}
_depot_asset_index_cache = {}

_SKIP_DIRS = frozenset({'__pycache__', '.git', '.svn', 'node_modules', '.vscode', '.idea', 'archive', 'backup'})
DEFAULT_IMAGE_EXTENSIONS = (
    '.png',
    '.jpg',
    '.jpeg',
    '.tga',
    '.dds',
    '.bmp',
    '.webp',
    '.tif',
    '.tiff',
)

COOKED_RESOURCE_EXPORTS = {
    '.mesh': ('.glb', '.mesh.json'),
    '.anims': ('.anims.glb', '.anims.json'),
    '.physicalscene': ('.physicalscene.glb', '.physicalscene.json'),
    '.w2mesh': ('.w2mesh.glb', '.w2mesh.json'),
    '.rig': ('.rig.json',),
    '.xbm': ('.png',),
    '.ent': ('.ent.json',),
    '.app': ('.app.json',),
    '.streamingsector_inplace': ('.streamingsector_inplace.json',),
    '.streamingsector': ('.streamingsector.json',),
    '.phys': ('.phys.json',),
}

EXPORTED_RESOURCE_EXTENSIONS = tuple(
    sorted(
        {ext for exports in COOKED_RESOURCE_EXPORTS.values() for ext in exports},
        key=len,
        reverse=True,
    )
)

DEFAULT_ASSET_EXTENSIONS = (*EXPORTED_RESOURCE_EXTENSIONS, *DEFAULT_IMAGE_EXTENSIONS)
_COOKED_DEPOT_EXTENSIONS = frozenset(COOKED_RESOURCE_EXPORTS)
_EXPORT_GROUPS_BY_OUTPUT_EXTENSION = {
    export_extension: exports
    for exports in COOKED_RESOURCE_EXPORTS.values()
    for export_extension in exports
}
_COOKED_RESOURCE_SUFFIXES = tuple(sorted(COOKED_RESOURCE_EXPORTS, key=len, reverse=True))
_EXPORTED_RESOURCE_SUFFIXES = tuple(sorted(_EXPORT_GROUPS_BY_OUTPUT_EXTENSION, key=len, reverse=True))


@lru_cache(maxsize=131072)
def _normalize_absolute_path(path: str) -> str:
    return os.path.normpath(path)


def _normalize_path(path: str) -> str:
    if not path:
        return ''
    normalized = os.path.normpath(path)
    if os.path.isabs(normalized):
        return _normalize_absolute_path(normalized)
    return os.path.abspath(normalized)


@lru_cache(maxsize=262144)
def _path_key(path: str) -> str:
    return os.path.normcase(os.path.normpath(path)).replace('\\', '/') if path else ''


@lru_cache(maxsize=131072)
def _local_ref(reference: str) -> str:
    return reference.replace('\\', os.sep).replace('/', os.sep) if reference else ''


@lru_cache(maxsize=128)
def _extension_key(extension: str) -> str:
    if not extension:
        return ''
    extension = extension.lower()
    return extension if extension.startswith('.') else f'.{extension}'


def _normalize_extensions(extensions: Iterable[str]) -> Set[str]:
    if isinstance(extensions, str):
        extensions = (extensions,)
    return {
        ext
        for ext in (_extension_key(extension) for extension in extensions if extension)
        if ext and ext not in _COOKED_DEPOT_EXTENSIONS
    }


def _normalized_extension_tuple(extensions: Iterable[str]):
    return tuple(sorted(_normalize_extensions(extensions), key=len, reverse=True))


@lru_cache(maxsize=256)
def _ordered_suffixes(suffixes):
    return tuple(sorted(suffixes, key=len, reverse=True))


def _first_matching_suffix(value: str, suffixes: Iterable[str]) -> str:
    key = _path_key(value)
    ordered = _ordered_suffixes(tuple(suffixes))
    for suffix in ordered:
        if key.endswith(suffix):
            return suffix
    return ''


def _matching_export_extension(path: str, extensions: Iterable[str]) -> str:
    return _first_matching_suffix(path, _normalized_extension_tuple(extensions))


def _append_exported_extension(base: str, extension: str) -> str:
    return f'{base}{extension}'


def dataKrash_fast(root: str, extensions: List[str]) -> Dict[str, Set[str]]:
    """Recursively index files by longest exact extension suffix using os.scandir."""
    root = _normalize_path(root)
    requested = _normalize_extensions(extensions)
    ext_map = {ext: set() for ext in requested}
    if not os.path.isdir(root):
        logging.error("Root directory not found: %s", root)
        return ext_map

    norm_exts = tuple(sorted(requested, key=len, reverse=True))
    stack = [root]

    while stack:
        folder = stack.pop()
        try:
            with os.scandir(folder) as entries:
                for entry in entries:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            if entry.name.lower() not in _SKIP_DIRS:
                                stack.append(entry.path)
                            continue
                        if not entry.is_file(follow_symlinks=False):
                            continue
                        name_lower = entry.name.lower()
                        for ext in norm_exts:
                            if name_lower.endswith(ext):
                                ext_map[ext].add(os.path.normpath(entry.path))
                                break
                    except (PermissionError, OSError) as exc:
                        logging.debug("Could not access %s: %s", entry.path, exc)
        except (PermissionError, OSError) as exc:
            logging.warning("Could not scan directory %s: %s", folder, exc)

    return ext_map


def _build_root_index(root: str, requested: Set[str], force_refresh: bool = False):
    root = _normalize_path(root)
    state = _root_index_cache.get(root)
    if not force_refresh and state is not None and requested.issubset(state['extensions']):
        return state

    extensions = requested if force_refresh or state is None else state['extensions'].union(requested)
    files_by_ext = dataKrash_fast(root, tuple(sorted(extensions, key=len, reverse=True)))
    for ext in extensions:
        files_by_ext.setdefault(ext, set())
    keys_by_ext = {
        ext: {_path_key(path): path for path in paths}
        for ext, paths in files_by_ext.items()
    }
    state = {
        'extensions': frozenset(extensions),
        'files_by_ext': files_by_ext,
        'keys_by_ext': keys_by_ext,
    }
    _root_index_cache[root] = state

    stale_keys = [key for key in _depot_asset_index_cache if key[0] == root]
    for key in stale_keys:
        del _depot_asset_index_cache[key]
    return state


def dataKrash_cached(root: str, extensions: List[str], force_refresh: bool = False) -> Dict[str, Set[str]]:
    """Return a cached recursive index for root, expanding when new suffixes are requested."""
    global _file_index_cache, _cache_root, _cache_extensions

    root = _normalize_path(root)
    requested = _normalize_extensions(extensions)
    state = _build_root_index(root, requested, force_refresh=force_refresh)

    _cache_root = root
    _cache_extensions = set(state['extensions'])
    _file_index_cache = state['files_by_ext']
    return {ext: set(state['files_by_ext'].get(ext, ())) for ext in requested}


def clear_dataKrash_cache():
    """Clear the global file index cache."""
    global _file_index_cache, _cache_root, _cache_extensions
    _file_index_cache = {}
    _cache_root = None
    _cache_extensions = set()
    _root_index_cache.clear()
    _depot_asset_index_cache.clear()
    _normalize_absolute_path.cache_clear()
    _path_key.cache_clear()
    _local_ref.cache_clear()
    _extension_key.cache_clear()
    _ordered_suffixes.cache_clear()


def dataKrash(root: str, extensions: List[str]) -> Dict[str, Set[str]]:
    """Uncached compatibility entrypoint for direct file indexing."""
    return dataKrash_fast(root, extensions)


class DepotAssetIndex:
    """Indexed source/raw asset resolver with exact extension-bucket membership checks."""

    def __init__(self, root: str, extensions: Iterable[str] = DEFAULT_ASSET_EXTENSIONS, force_refresh: bool = False, warn_missing: bool = True):
        self.root = _normalize_path(root)
        self.extensions = _normalized_extension_tuple(extensions)
        self.warn_missing = warn_missing
        state = _build_root_index(self.root, set(self.extensions), force_refresh=force_refresh)
        self.files_by_ext = {
            ext: set(state['files_by_ext'].get(ext, ()))
            for ext in self.extensions
        }
        self._keys_by_ext = {
            ext: state['keys_by_ext'].get(ext, {})
            for ext in self.extensions
        }
        self._sorted_files_by_ext = {}

    @classmethod
    def cached(cls, root: str, extensions: Iterable[str] = DEFAULT_ASSET_EXTENSIONS, force_refresh: bool = False, warn_missing: bool = True):
        normalized_root = _normalize_path(root)
        normalized_extensions = _normalized_extension_tuple(extensions)
        key = (normalized_root, normalized_extensions, bool(warn_missing))
        if not force_refresh:
            cached = _depot_asset_index_cache.get(key)
            if cached is not None:
                return cached

        instance = cls(
            normalized_root,
            normalized_extensions,
            force_refresh=force_refresh,
            warn_missing=warn_missing,
        )
        _depot_asset_index_cache[key] = instance
        return instance

    def get_files_by_extension(self, extension: str):
        ext = _extension_key(extension)
        cached = self._sorted_files_by_ext.get(ext)
        if cached is None:
            cached = tuple(sorted(self.files_by_ext.get(ext, ())))
            self._sorted_files_by_ext[ext] = cached
        return list(cached)

    def files(self, extension: str):
        return self.get_files_by_extension(extension)

    def contains(self, path: str, extension: str) -> bool:
        ext = _extension_key(extension)
        return _path_key(path) in self._keys_by_ext.get(ext, {})

    def _candidate(self, reference: str) -> str:
        local = _local_ref(reference)
        if not local:
            return ''
        return _normalize_path(local if os.path.isabs(local) else os.path.join(self.root, local))

    def _resolve_candidate(self, candidate: str):
        extension = _first_matching_suffix(candidate, self.extensions)
        if not extension:
            return None
        return self._keys_by_ext.get(extension, {}).get(_path_key(self._candidate(candidate)))

    def export_candidates(self, reference: str, export_extensions: Iterable[str] = None):
        local = _local_ref(reference)
        if not local:
            return []

        requested = _normalize_extensions(export_extensions or self.extensions)
        cooked_suffix = _first_matching_suffix(local, _COOKED_RESOURCE_SUFFIXES)
        exported_suffix = '' if cooked_suffix else _first_matching_suffix(local, _EXPORTED_RESOURCE_SUFFIXES)

        if cooked_suffix:
            base = local[:-len(cooked_suffix)]
            outputs = COOKED_RESOURCE_EXPORTS[cooked_suffix]
        elif exported_suffix:
            base = local[:-len(exported_suffix)]
            outputs = _EXPORT_GROUPS_BY_OUTPUT_EXTENSION[exported_suffix]
        else:
            current_extension = _first_matching_suffix(local, tuple(sorted(requested, key=len, reverse=True)))
            if current_extension:
                return [local]
            outputs = tuple(sorted(requested, key=len, reverse=True))
            base = local

        candidates = []
        seen = set()
        for output in outputs:
            if output not in requested:
                continue
            candidate = _append_exported_extension(base, output)
            key = _path_key(candidate)
            if key not in seen:
                seen.add(key)
                candidates.append(candidate)
        return candidates

    def resolve_export(self, reference: str, export_extensions: Iterable[str] = None, warn=None):
        candidates = self.export_candidates(reference, export_extensions)
        for candidate in candidates:
            resolved = self._resolve_candidate(candidate)
            if resolved:
                return resolved

        if self.warn_missing if warn is None else warn:
            logging.warning(
                "Exported asset reference is not indexed and will be skipped: %s",
                self._candidate(reference),
            )
        return None

    def resolve_expected(self, reference: str, expected_extension: str, warn=None):
        return self.resolve_export(reference, (expected_extension,), warn=warn)

    def resolve_any(self, reference: str, extensions: Iterable[str] = None, warn=None):
        return self.resolve_export(reference, extensions, warn=warn)
