"""Low-overhead hooks for detachable material-import profiling.

Production imports leave profiling disabled, so hot shader helpers pay only a
single boolean branch. The entity and sector audit modules enable the hook and
replace ``_emit_material_phase`` while an audited import is running.
"""

from __future__ import annotations

from time import perf_counter
from typing import Any, Mapping

_MATERIAL_PROFILING_ENABLED = False


def _emit_material_phase(
    phase: str,
    seconds: float,
    label: str = "",
    metadata: Mapping[str, Any] | None = None,
):
    """No-op hook patched by the detachable importer audits."""
    return None


def set_material_profiling_enabled(enabled: bool) -> None:
    global _MATERIAL_PROFILING_ENABLED
    _MATERIAL_PROFILING_ENABLED = bool(enabled)


def material_profiling_enabled() -> bool:
    return _MATERIAL_PROFILING_ENABLED


def begin_material_phase():
    return perf_counter() if _MATERIAL_PROFILING_ENABLED else None


def end_material_phase(
    started,
    phase: str,
    *,
    label: str = "",
    metadata: Mapping[str, Any] | None = None,
) -> None:
    if started is None:
        return
    _emit_material_phase(
        str(phase or "unknown"),
        max(0.0, perf_counter() - started),
        str(label or ""),
        metadata,
    )
