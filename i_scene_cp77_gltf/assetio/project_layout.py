from __future__ import annotations

import ntpath
import os
from dataclasses import dataclass

from .files import read_bytes
from .paths import (
    confined_join,
    depot_parts,
    normalize_local_path,
    split_source_tree_root,
    strip_json_suffix,
)

_RAW_MESH_SIDECARS = (".Material.json",)
_ARCHIVE_MESH_SIDECARS = (".morphtarget",)


def _without_extension(depot_path: str) -> tuple[str, ...]:
    parts = list(depot_parts(depot_path))
    if parts:
        parts[-1] = ntpath.splitext(parts[-1])[0]
    return tuple(parts)


@dataclass(frozen=True, slots=True)
class ProjectLayout:
    root: str
    archive: str
    raw: str
    # The stem of the project's .cpmodproj, which names the depot folder of the files the project adds; "" when the
    # layout was found from a file inside the project.
    name: str = ""

    def depot_path_for(self, local_path: str) -> str:
        """The depot path of a file under source/raw or source/archive, without its .json suffix"""
        for tree in ("raw", "archive"):
            root, remainder = split_source_tree_root(
                normalize_local_path(local_path), tree
            )
            if root and remainder:
                return strip_json_suffix(remainder).replace("/", "\\")
        raise ValueError(
            f"{local_path} is not inside the project's source/raw or source/archive"
        )

    def raw_file(self, depot_path: str, suffix: str) -> str:
        """The source/raw file for a depot path with its extension replaced by suffix (".glb", ".app.json")"""
        return os.path.join(self.raw, *_without_extension(depot_path)) + suffix

    def archive_file(self, depot_path: str) -> str:
        return confined_join(self.archive, depot_path)


def project_layout_for(path: str) -> ProjectLayout | None:
    """The project a file or folder under source/raw or source/archive belongs to, or None"""
    local = normalize_local_path(path)
    for tree in ("raw", "archive"):
        tree_root, _remainder = split_source_tree_root(local, tree)
        if tree_root:
            source = os.path.dirname(tree_root)
            return ProjectLayout(
                root=os.path.dirname(source),
                archive=os.path.join(source, "archive"),
                raw=os.path.join(source, "raw"),
            )
    return None


def cpmodproj_layout(project_file: str) -> ProjectLayout:
    """The layout of the WolvenKit project whose .cpmodproj is project_file, named after that file"""
    path = normalize_local_path(project_file)
    source = os.path.join(os.path.dirname(path), "source")
    return ProjectLayout(
        root=os.path.dirname(path),
        archive=os.path.join(source, "archive"),
        raw=os.path.join(source, "raw"),
        name=os.path.splitext(os.path.basename(path))[0],
    )


def base_mesh_copy_payloads(
    layout: ProjectLayout, base_depot: str, new_depot: str
) -> dict[str, bytes]:
    """The files that give new_depot a copy of the base .mesh"""
    source = layout.archive_file(base_depot)
    if not os.path.isfile(source):
        raise FileNotFoundError(
            f"{base_depot} is not in the project's source/archive; add it to the WolvenKit project"
        )
    payloads = {layout.archive_file(new_depot): read_bytes(source)}
    for suffix in _ARCHIVE_MESH_SIDECARS:
        sidecar = os.path.splitext(source)[0] + suffix
        if os.path.isfile(sidecar):
            payloads[os.path.splitext(layout.archive_file(new_depot))[0] + suffix] = (
                read_bytes(sidecar)
            )
    for suffix in _RAW_MESH_SIDECARS:
        sidecar = layout.raw_file(base_depot, suffix)
        if os.path.isfile(sidecar):
            payloads[layout.raw_file(new_depot, suffix)] = read_bytes(sidecar)
    return payloads
