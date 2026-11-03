from __future__ import annotations

from ...assetio.metarig_bundle import bundled_metarigs
from ...blender.operator_results import OperationResult
from ...blender.selection import select_objects
from ...blender.transforms import rotate_quat_180
from ...importers.rig.bundled import import_bundled_metarig
from .rigify import cp77_to_rigify


def load_selected_rig(
    context, *, selected_name: str, fbx_rotation: bool, generate_rigify: bool
) -> OperationResult:
    filepath = next(
        (
            path
            for identifier, _name, path in bundled_metarigs()
            if identifier == selected_name
        ),
        None,
    )
    if filepath is None:
        return OperationResult(
            False, f"Rig '{selected_name}' is not available", "ERROR"
        )
    try:
        armature = import_bundled_metarig(filepath)
    except (OSError, ValueError) as error:
        return OperationResult(False, f"Rig load failed: {error}", "ERROR")
    select_objects([armature], clear=True, context=context)
    if fbx_rotation:
        rotate_quat_180(None, context)
    if generate_rigify:
        cp77_to_rigify(context)
    return OperationResult(
        True, f"Loaded rig '{selected_name}'", details={"filepath": filepath}
    )
