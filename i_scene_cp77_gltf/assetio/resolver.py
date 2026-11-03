import os
from pathlib import Path

from .catalog import normalize_extensions
from .index import IndexPolicy, build_asset_index
from .paths import normalize_local_path


def full_suffix(path):
    return "".join(Path(os.path.basename(os.fspath(path))).suffixes).lower()


def resolve_asset_path(reference, *, roots=(), extensions=(), policy=IndexPolicy.REUSE, warn=False):
    if not reference:
        return ""
    value = os.fspath(reference)
    if os.path.isfile(value):
        return normalize_local_path(value)
    requested = normalize_extensions(extensions)
    if not requested:
        raise ValueError("extensions are required for indexed resolution")
    supplied_roots = tuple(root for root in roots if root)
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


def resolve_rooted_path(reference, *, project_root="", depot_root="", extensions=(), policy=IndexPolicy.REUSE):
    return resolve_asset_path(
        reference,
        roots=tuple(root for root in (project_root, depot_root) if root),
        extensions=extensions,
        policy=policy,
    )
