import os

from ..common.atomic import atomic_replace_staged
from ..common.glb import encode_glb
from .document import build_direct_animation_glb
from .validation import validate_direct_animation_document, validate_direct_animation_glb_file


def export_anims_glb_direct(
    filepath: str,
    armature,
    *,
    export_tracks: bool = True,
    active_action_only: bool = False,
    selected_action_names=None,
) -> dict:
    document, binary, summary = build_direct_animation_glb(
        armature,
        export_tracks=export_tracks,
        active_action_only=active_action_only,
        selected_action_names=selected_action_names,
    )
    summary["document_validation"] = validate_direct_animation_document(document, binary)
    filepath = os.path.abspath(filepath)
    if not filepath.lower().endswith(".glb"):
        filepath += ".glb"
    directory = os.path.dirname(filepath)
    if directory:
        os.makedirs(directory, exist_ok=True)
    temporary = filepath + ".tmp"
    payload = encode_glb(document, binary)
    try:
        with open(temporary, "wb") as stream:
            stream.write(payload)
        summary["file_validation"] = validate_direct_animation_glb_file(temporary)
        atomic_replace_staged({filepath: temporary})
        temporary = ""
    except Exception:
        try:
            if os.path.exists(temporary):
                os.remove(temporary)
        finally:
            raise
    summary["filepath"] = filepath
    summary["file_bytes"] = len(payload)
    return summary
