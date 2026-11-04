from ...gltf.provenance import SelectionOrigin, selection_origin
from ..common.glb_output import write_validated_glb
from .document import build_direct_animation_glb
from .errors import DirectAnimationExportError
from .rig_source import animation_rig_export_entries
from .validation import (
    validate_direct_animation_document,
    validate_direct_animation_glb_file,
)


def animation_glb_path(filepath: str) -> str:
    """Use the WolvenKit animation suffix once at every animation output boundary"""
    path = str(filepath)
    if path.lower().endswith(".glb"):
        path = path[:-4]
    while path.lower().endswith(".anims"):
        path = path[:-6]
    return path + ".anims.glb"


def export_anims_glb_direct(
    filepath: str,
    armature,
    *,
    export_tracks: bool = True,
    active_action_only: bool = False,
    selected_action_names=None,
    source_rig_path: str = "",
    root_motion: str = "CLIP",
) -> dict:
    document, binary, summary = build_direct_animation_glb(
        armature,
        export_tracks=export_tracks,
        active_action_only=active_action_only,
        selected_action_names=selected_action_names,
        source_rig_path=source_rig_path,
        root_motion=root_motion,
    )
    summary["document_validation"] = validate_direct_animation_document(
        document, binary
    )
    summary.update(
        write_validated_glb(
            animation_glb_path(filepath),
            document,
            binary,
            validate_direct_animation_glb_file,
        )
    )
    return summary


def export_animation(
    filepath: str,
    armatures,
    *,
    export_tracks: bool = True,
    active_action_only: bool = False,
    selected_action_names=None,
    source_rig_path: str = "",
    root_motion: str = "CLIP",
) -> dict:
    """The animation export every entry point uses"""
    armatures = tuple(armatures)
    if len(armatures) != 1:
        raise DirectAnimationExportError(
            "Animation export requires exactly one selected MetaRig."
        )
    armature = armatures[0]
    if selection_origin(armatures) is not SelectionOrigin.PLUGIN:
        raise DirectAnimationExportError(
            f"{armature.name!r} carries no Cyberpunk IO Suite metadata; animation export needs a rig the add-on "
            "imported."
        )
    if not source_rig_path and len(animation_rig_export_entries(armature)) > 1:
        raise DirectAnimationExportError(
            f"{armature.name!r} merges several source rigs. Export it from File > Export > Cyberpunk GLB and choose "
            "the source rig the animations belong to."
        )
    return export_anims_glb_direct(
        filepath,
        armature,
        export_tracks=export_tracks,
        active_action_only=active_action_only,
        selected_action_names=selected_action_names,
        source_rig_path=source_rig_path,
        root_motion=root_motion,
    )
