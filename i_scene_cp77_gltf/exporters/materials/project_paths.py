from __future__ import annotations

import ntpath

from ...assetio.project_layout import project_layout_for


def source_raw_relative(filepath):
    """The depot-style path of filepath below a project's source/raw folder, or "" outside one"""
    normalized = str(filepath or "").replace("\\", "/")
    marker = "/source/raw/"
    index = normalized.casefold().find(marker)
    if index < 0:
        return ""
    return normalized[index + len(marker) :].replace("/", "\\")


def replace_depot_suffix(path, old_suffix, new_suffix):
    value = str(path or "").replace("/", "\\")
    if value.casefold().endswith(old_suffix.casefold()):
        return value[: -len(old_suffix)] + new_suffix
    stem, _ext = ntpath.splitext(value)
    return stem + new_suffix


def project_raw_file(project_path, depot_path, suffix=".json"):
    """The source/raw file for depot_path in the project project_path belongs to"""
    layout = project_layout_for(str(project_path or ""))
    if layout is None:
        raise ValueError(
            f"{project_path} is not inside a WolvenKit project's source folders"
        )
    extension = ntpath.splitext(str(depot_path).replace("/", "\\"))[1]
    return layout.raw_file(str(depot_path), extension + suffix)


def default_project_output(project_path, depot_path, suffix=".json"):
    """The file browser's starting path for a resource export"""
    try:
        return project_raw_file(project_path, depot_path, suffix)
    except ValueError:
        return ntpath.basename(str(depot_path).replace("/", "\\")) + suffix
