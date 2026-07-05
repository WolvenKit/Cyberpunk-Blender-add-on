"""Fast cached file indexing and exact depot asset resolution."""

import logging
import os
from typing import Dict, Iterable, List, Set

_file_index_cache: Dict[str, Set[str]] = {}
_cache_root = None
_cache_extensions: Set[str] = set()
_SKIP_DIRS = frozenset({'__pycache__', '.git', '.svn', 'node_modules', '.vscode', '.idea', 'archive', 'backup'})
DEFAULT_ASSET_EXTENSIONS = (
    '.app.json',
    '.glb',
    '.mesh.json',
    '.anims.glb',
    '.anims.json',
    '.rig.json',
    '.phys.json',
)


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
    return {_extension_key(ext) for ext in extensions if ext}


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

    def resolve_expected(self, reference: str, expected_extension: str, warn=None):
        ext = _extension_key(expected_extension)
        candidate = self._candidate(reference)
        if not candidate:
            return None
        resolved = self._keys_by_ext.get(ext, {}).get(_path_key(candidate))
        if resolved:
            return resolved
        if self.warn_missing if warn is None else warn:
            logging.warning("Expected %s path is not indexed and will be skipped: %s", ext, candidate)
        return None

    def resolve_app_json(self, depot_path: str):
        return self.resolve_expected(f'{depot_path}.json', '.app.json')

    def resolve_mesh_glb(self, depot_path: str):
        if not depot_path:
            return None
        return self.resolve_expected(os.path.splitext(depot_path)[0] + '.glb', '.glb')

    def resolve_mesh_json(self, depot_path: str):
        return self.resolve_expected(f'{depot_path}.json', '.mesh.json')

    def resolve_rig_json(self, depot_path: str):
        return self.resolve_expected(f'{depot_path}.json', '.rig.json')

    def resolve_anim_glb(self, depot_path: str):
        return self.resolve_expected(f'{depot_path}.glb', '.anims.glb')

    def resolve_anim_json(self, depot_path: str):
        return self.resolve_expected(f'{depot_path}.json', '.anims.json')

    def resolve_anim_json_from_glb(self, anim_glb_path: str):
        if not anim_glb_path:
            return None
        return self.resolve_expected(os.path.splitext(anim_glb_path)[0] + '.json', '.anims.json')
