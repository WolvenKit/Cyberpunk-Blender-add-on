from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class GlbExportOptions:
    export_poses: bool = False
    export_visible: bool = False
    limit_selected: bool = True
    is_skinned: bool = True
    try_fix: bool = False
    apply_transform: bool = True
    export_tracks: bool = True
    apply_modifiers: bool = True
    called_from_loop: bool = False
    selected_action_names: Any = None
    mesh_validation_options: Any = None
    mesh_scope: Any = None
    excluded_objects: Any = None
    root_motion: str = "CLIP"
    source_rig_path: str = ""
