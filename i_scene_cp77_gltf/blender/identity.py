from __future__ import annotations

from ..core.log import get_logger, log_once

_LOG = get_logger(__name__)


def rna_identity(value) -> int:
    try:
        pointer = int(value.as_pointer())
        return pointer if pointer else id(value)
    except (
        AttributeError,
        ReferenceError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("rna_identity", type(error).__name__),
            "rna identity: fell back after %s",
            error,
            exc_info=True,
        )
        return id(value)


def real_users(data) -> int:
    """How many users the data has, not counting a fake user"""
    return data.users - (1 if data.use_fake_user else 0)


def rna_is_live(value) -> bool:
    if value is None:
        return False
    try:
        return int(value.as_pointer()) != 0
    except (
        AttributeError,
        ReferenceError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("rna_is_live", type(error).__name__),
            "rna is live: fell back after %s",
            error,
            exc_info=True,
        )
        return False


def authored_material_name(material):
    """Resolve a material's source identity independently of Blender's unique name"""
    if material is None:
        return ""
    return str(material.get("cp77_source_material_name") or material.name)
