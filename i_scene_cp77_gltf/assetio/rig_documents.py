from __future__ import annotations

from .headers import SUPPORTED_WKIT_JSON_VERSION
from .paths import strip_json_suffix


def minimal_rig_document(source_rig_file: str = "") -> dict:
    """An animRig document with empty bone, pose and track arrays, archived under source_rig_file"""
    return {
        "Header": {
            "WKitJsonVersion": SUPPORTED_WKIT_JSON_VERSION,
            "DataType": "CR2W",
            "ArchiveFileName": strip_json_suffix(source_rig_file),
        },
        "Data": {
            "RootChunk": {
                "$type": "animRig",
                "aPoseLS": [],
                "aPoseMS": [],
                "boneNames": [],
                "boneParentIndexes": [],
                "boneTransforms": [],
                "referencePoseMS": [],
                "referenceTracks": [],
                "rigExtraTracks": [],
                "trackNames": [],
            }
        },
    }
