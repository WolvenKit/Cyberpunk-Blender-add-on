from __future__ import annotations

import os
from collections.abc import Callable

from ...assetio.documents import DocumentLoadError, load_json_payload
from ...assetio.paths import normalize_depot_path, normalize_local_path
from ...assetio.project_layout import project_layout_for
from ...assetio.resolver import resolve_mirrored_export
from ...assetio.values import resource_path_text

# (depot path, export suffix such as ".inkatlas.json" or ".png") → the exported file, or "".
Resolver = Callable[[str, str], str]


def rooted_resolver(*roots: str) -> Resolver:
    roots = tuple(root for root in roots if root)

    def resolve(depot_path: str, suffix: str) -> str:
        if not depot_path:
            return ""
        for root in roots:
            found = resolve_mirrored_export(depot_path, root, (suffix,))
            if found:
                return found
        return ""

    return resolve


def _loose_depot_root(widget_path: str) -> str:
    """The folder a loose export mirrors depot paths under"""
    try:
        document = load_json_payload(widget_path)
    except (DocumentLoadError, OSError, ValueError):
        return ""
    resource = (
        document.get("Data", {}).get("RootChunk", {})
        if isinstance(document, dict)
        else {}
    )
    folder = normalize_local_path(os.path.dirname(os.path.abspath(widget_path)))
    parts = folder.replace("\\", "/").split("/")
    references = [
        *(resource.get("externalDependenciesForInternalItems") or ()),
        resource.get("animationLibraryResRef"),
    ]
    for entry in references:
        depot_folder = normalize_depot_path(resource_path_text(entry)).rpartition("/")[
            0
        ]
        if not depot_folder:
            continue
        tail = depot_folder.split("/")
        for index in range(len(parts) - 1, 0, -1):
            if parts[index].casefold() != tail[0].casefold():
                continue
            root = os.sep.join(parts[:index])
            if os.path.isdir(os.path.join(root, *tail)):
                return root
    return ""


def resolver_for(widget_path: str) -> Resolver:
    """A resolver for the resources of the widget library exported at widget_path"""
    layout = project_layout_for(widget_path)
    if layout is not None:
        return rooted_resolver(layout.raw)
    return rooted_resolver(
        _loose_depot_root(widget_path), os.path.dirname(os.path.abspath(widget_path))
    )
