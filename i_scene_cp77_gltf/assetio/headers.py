from __future__ import annotations

import os
from datetime import UTC, datetime

from .catalog import ResourceKind
from .diagnostics import IssueSeverity
from .paths import strip_json_suffix
from .validation import ValidationProfile, validate_payload

SUPPORTED_WOLVENKIT_VERSION = "8.18.2"
SUPPORTED_WKIT_JSON_VERSION = "0.0.9"
SUPPORTED_GAME_VERSION = 2310
PATCH_2_5_WOLVENKIT_VERSION = "10.0.0-beta.2-nightly.2026-10-25"
PATCH_2_5_GAME_VERSION = 2500


def utc_timestamp() -> str:
    return (
        datetime.now(UTC)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def _header(archive_name: str, wolvenkit_version: str, game_version: int) -> dict:
    return {
        "WolvenKitVersion": wolvenkit_version,
        "WKitJsonVersion": SUPPORTED_WKIT_JSON_VERSION,
        "GameVersion": game_version,
        "ExportedDateTime": utc_timestamp(),
        "DataType": "CR2W",
        "ArchiveFileName": archive_name,
    }


def cr2w_header(filepath: str) -> dict:
    """A header for the supported WolvenKit and game versions naming the file at filepath"""
    archive_name = strip_json_suffix(os.path.basename(os.fspath(filepath)))
    return _header(archive_name, SUPPORTED_WOLVENKIT_VERSION, SUPPORTED_GAME_VERSION)


def patch_2_5_header(archive_file_name: str) -> dict:
    """A header for the current game naming archive_file_name"""
    return _header(
        strip_json_suffix(archive_file_name),
        PATCH_2_5_WOLVENKIT_VERSION,
        PATCH_2_5_GAME_VERSION,
    )


def validate_physics_payload(payload: dict, filepath: str) -> None:
    result = validate_payload(
        payload,
        path=os.fspath(filepath),
        kind=ResourceKind.PHYSICS,
        profile=ValidationProfile.CR2W,
        expected_root_types=("physicsSystemResource",),
    )
    errors = result.messages(minimum=IssueSeverity.ERROR)
    if errors:
        raise ValueError("Invalid physics export: " + "; ".join(errors))
