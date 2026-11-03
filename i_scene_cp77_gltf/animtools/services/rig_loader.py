from __future__ import annotations

<<<<<<< Updated upstream
from ...blender.transforms import rotate_quat_180
from ...animation.rig.catalog import bundled_rig_paths_and_names
from ..model import OperationResult
from .rigify.build import cp77_to_rigify


def load_selected_rig(context, *, selected_name: str, fbx_rotation: bool, generate_rigify: bool) -> OperationResult:
    rig_files, rig_names = bundled_rig_paths_and_names()
    if selected_name not in rig_names:
        return OperationResult(False, f"Rig '{selected_name}' is not available", "ERROR")
    filepath = rig_files[rig_names.index(selected_name)]
    from ...importers.mesh import import_cyberpunk_glb

    result = import_cyberpunk_glb(
        with_materials=False,
        exclude_unused_mats=True,
        image_format="PNG",
        filepath=filepath,
        hide_armatures=False,
        import_garmentsupport=False,
        files=[],
        directory="",
        appearances=["ALL"],
        remap_depot=False,
        scripting=True,
    )
    if not result.ok:
        return OperationResult(False, "Rig import failed: " + "; ".join(result.failures), "ERROR")
=======
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
>>>>>>> Stashed changes
    if fbx_rotation:
        rotate_quat_180(None, context)
    if generate_rigify:
        cp77_to_rigify(context)
<<<<<<< Updated upstream
    return OperationResult(True, f"Loaded rig '{selected_name}'", details={"filepath": filepath})
=======
    return OperationResult(
        True, f"Loaded rig '{selected_name}'", details={"filepath": filepath}
    )
>>>>>>> Stashed changes
