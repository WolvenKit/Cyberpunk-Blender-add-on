import os
from contextlib import contextmanager
from pathlib import Path

from .catalog import normalize_extensions
from .index import IndexPolicy, build_asset_index, export_candidates
from .paths import is_local_absolute, normalize_depot_path, normalize_local_path
from .resources import get_multilayer_defaults_dir


def full_suffix(path):
    return "".join(Path(os.path.basename(os.fspath(path))).suffixes).lower()


# Mirrored-export lookups memoized while a resolution scope is open; None outside any scope.
_mirrored_cache = None


@contextmanager
def resolution_scope():
    """Memoize mirrored-export lookups for the duration of one import"""
    global _mirrored_cache
    outermost = _mirrored_cache is None
    if outermost:
        _mirrored_cache = {}
    try:
        yield
    finally:
        if outermost:
            _mirrored_cache = None


def resolve_mirrored_export(reference, root, extensions):
    if not reference or not root:
        return ""
    value = os.fspath(reference)
    if is_local_absolute(value):
        return normalize_local_path(value) if os.path.isfile(value) else ""
    requested = normalize_extensions(extensions)
    if not requested:
        raise ValueError("extensions are required for mirrored resolution")
    root_value = os.fspath(root)
    cache = _mirrored_cache
    key = (value, root_value, requested)
    if cache is not None:
        cached = cache.get(key)
        if cached is not None:
            return cached
    resolved = ""
    for candidate in export_candidates(value, requested):
        relative = normalize_depot_path(candidate)
        if not relative or relative == ".." or relative.startswith("../"):
            continue
        rooted = os.path.join(root_value, *relative.split("/"))
        if os.path.isfile(rooted):
            resolved = normalize_local_path(rooted)
            break
    if cache is not None:
        cache[key] = resolved
    return resolved


def resolve_asset_path(
    reference, *, roots=(), extensions=(), policy=IndexPolicy.REUSE, warn=False
):
    if not reference:
        return ""
    value = os.fspath(reference)
    supplied_roots = tuple(root for root in roots if root)
    if (not supplied_roots or is_local_absolute(value)) and os.path.isfile(value):
        return normalize_local_path(value)
    requested = normalize_extensions(extensions)
    if not requested:
        raise ValueError("extensions are required for indexed resolution")
    if supplied_roots and not is_local_absolute(value):
        for root in supplied_roots:
            resolved = resolve_mirrored_export(value, root, requested)
            if resolved:
                return resolved
    for root in supplied_roots:
        snapshot = build_asset_index(root, requested, policy=policy)
        resolved = snapshot.resolve_any(value, requested, warn=warn)
        if resolved:
            return resolved
    if supplied_roots:
        return ""
    parent = os.path.dirname(value)
    if not parent or not os.path.isdir(parent):
        return ""
    snapshot = build_asset_index(parent, requested, policy=policy)
    return snapshot.resolve_any(value, requested, warn=warn) or ""


def resolve_existing_path(reference, *, roots=(), policy=IndexPolicy.REUSE, warn=False):
    if not reference:
        return ""
    value = os.fspath(reference)
    if os.path.isfile(value):
        return normalize_local_path(value)
    suffix = full_suffix(value)
    if not suffix:
        return ""
    return resolve_asset_path(
        value,
        roots=roots,
        extensions=(suffix,),
        policy=policy,
        warn=warn,
    )


def resolve_rooted_path(
    reference,
    *,
    project_root="",
    depot_root="",
    extensions=(),
    policy=IndexPolicy.REUSE,
):
    """reference in the project, then the depot, then the game files the add-on bundles"""
    return resolve_asset_path(
        reference,
        roots=tuple(
            root
            for root in (project_root, depot_root, get_multilayer_defaults_dir())
            if root
        ),
        extensions=extensions,
        policy=policy,
    )
