from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EntityExportRequest:
    """What the export screen collects"""

    filepath: str
    overwrite: bool
    edited_meshes: bool
    all_appearances: bool
    appearances_folder: str
