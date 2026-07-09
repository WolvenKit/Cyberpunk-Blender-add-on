"""Fast cached file indexing and exact depot asset resolution."""

import logging
import os
from typing import Dict, Iterable, List, Set

_file_index_cache: Dict[str, Set[str]] = {}
_cache_root = None
_cache_extensions: Set[str] = set()
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


def _normalize_path(path: str) -> str:
    return os.path.abspath(os.path.normpath(path)) if path else ''


def _path_key(path: str) -> str:
    return os.path.normcase(os.path.normpath(path)).replace('\\', '/') if path else ''


def _local_ref(reference: str) -> str:
    return reference.replace('\\', os.sep).replace('/', os.sep) if reference else ''


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


def _first_matching_suffix(value: str, suffixes: Iterable[str]) -> str:
    key = _path_key(value)
    for suffix in sorted(suffixes, key=len, reverse=True):
        if key.endswith(suffix):
            return suffix
    return ''


def _matching_export_extension(path: str, extensions: Iterable[str]) -> str:
    return _first_matching_suffix(path, _normalize_extensions(extensions))


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
                                ext_map[ext].add(_normalize_path(entry.path))
                                break
                    except (PermissionError, OSError) as exc:
                        logging.debug("Could not access %s: %s", entry.path, exc)
        except (PermissionError, OSError) as exc:
            logging.warning("Could not scan directory %s: %s", folder, exc)

    return ext_map


def dataKrash_cached(root: str, extensions: List[str], force_refresh: bool = False) -> Dict[str, Set[str]]:
    """Return a cached recursive index for root, expanding when new suffixes are requested."""
    global _file_index_cache, _cache_root, _cache_extensions

    root = _normalize_path(root)
    requested = _normalize_extensions(extensions)

    if not force_refresh and _cache_root == root and _file_index_cache and requested.issubset(_cache_extensions):
        return {ext: set(_file_index_cache.get(ext, set())) for ext in requested}

    same_root = _cache_root == root
    _cache_root = root
    _cache_extensions = requested if force_refresh or not same_root else _cache_extensions.union(requested)
    _file_index_cache = dataKrash_fast(root, sorted(_cache_extensions, key=len, reverse=True))
    for ext in _cache_extensions:
        _file_index_cache.setdefault(ext, set())
    return {ext: set(_file_index_cache.get(ext, set())) for ext in requested}


def clear_dataKrash_cache():
    """Clear the global file index cache."""
    global _file_index_cache, _cache_root, _cache_extensions
    _file_index_cache = {}
    _cache_root = None
    _cache_extensions = set()


def dataKrash(root: str, extensions: List[str]) -> Dict[str, Set[str]]:
    """Uncached compatibility entrypoint for direct file indexing."""
    return dataKrash_fast(root, extensions)


class DepotAssetIndex:
    """Indexed source/raw asset resolver with exact extension-bucket membership checks."""

    def __init__(self, root: str, extensions: Iterable[str] = DEFAULT_ASSET_EXTENSIONS, force_refresh: bool = False, warn_missing: bool = True):
        self.root = _normalize_path(root)
        self.extensions = tuple(sorted(_normalize_extensions(extensions), key=len, reverse=True))
        self.warn_missing = warn_missing
        self.files_by_ext = dataKrash_cached(self.root, list(self.extensions), force_refresh=force_refresh)
        for ext in self.extensions:
            self.files_by_ext.setdefault(ext, set())
        self._keys_by_ext = {
            ext: {_path_key(path): path for path in paths}
            for ext, paths in self.files_by_ext.items()
        }

    @classmethod
    def cached(cls, root: str, extensions: Iterable[str] = DEFAULT_ASSET_EXTENSIONS, force_refresh: bool = False, warn_missing: bool = True):
        return cls(root, extensions, force_refresh=force_refresh, warn_missing=warn_missing)

    def get_files_by_extension(self, extension: str):
        return sorted(self.files_by_ext.get(_extension_key(extension), set()))

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
        extension = _matching_export_extension(candidate, self.extensions)
        if not extension:
            return None
        return self._keys_by_ext.get(extension, {}).get(_path_key(self._candidate(candidate)))

    def export_candidates(self, reference: str, export_extensions: Iterable[str] = None):
        local = _local_ref(reference)
        if not local:
            return []

        requested = _normalize_extensions(export_extensions or self.extensions)
        cooked_suffix = _first_matching_suffix(local, COOKED_RESOURCE_EXPORTS)
        exported_suffix = '' if cooked_suffix else _first_matching_suffix(local, _EXPORT_GROUPS_BY_OUTPUT_EXTENSION)

        if cooked_suffix:
            base = local[:-len(cooked_suffix)]
            outputs = COOKED_RESOURCE_EXPORTS[cooked_suffix]
        elif exported_suffix:
            base = local[:-len(exported_suffix)]
            outputs = _EXPORT_GROUPS_BY_OUTPUT_EXTENSION[exported_suffix]
        else:
            current_extension = _matching_export_extension(local, requested)
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
