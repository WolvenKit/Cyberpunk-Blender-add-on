from time import perf_counter
from typing import Any, Mapping

_MATERIAL_PROFILING_ENABLED = False


def _emit_material_phase(
    phase: str,
    seconds: float,
    label: str = "",
    metadata: Mapping[str, Any] | None = None,
):
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
