from __future__ import annotations

from collections.abc import Callable
from typing import Any


_MATERIAL_CACHE_LEASE_DEPTH = 0
_MATERIAL_CACHE_LEASE_STATS = {
    "acquisitions": 0,
    "releases": 0,
    "outer_acquisitions": 0,
    "outer_releases": 0,
    "clears": 0,
    "max_depth": 0,
}


def _clear_transient_material_cache() -> None:
    """Clear lookup indexes while preserving persistent material signatures."""
    from ...main.setup import clear_material_cache

    clear_material_cache(
        clear_persistent=False,
        reset_stats=False,
        clear_helpers=False,
    )


def acquire_material_cache(enabled: bool = True) -> bool:
    """Join the active import material-cache lease."""
    global _MATERIAL_CACHE_LEASE_DEPTH
    if not enabled:
        return False
    _MATERIAL_CACHE_LEASE_STATS["acquisitions"] += 1
    if _MATERIAL_CACHE_LEASE_DEPTH == 0:
        _MATERIAL_CACHE_LEASE_STATS["outer_acquisitions"] += 1
        _clear_transient_material_cache()
        _MATERIAL_CACHE_LEASE_STATS["clears"] += 1
    _MATERIAL_CACHE_LEASE_DEPTH += 1
    _MATERIAL_CACHE_LEASE_STATS["max_depth"] = max(
        _MATERIAL_CACHE_LEASE_STATS["max_depth"],
        _MATERIAL_CACHE_LEASE_DEPTH,
    )
    return True


def release_material_cache(acquired: bool) -> None:
    """Leave the active import material-cache lease."""
    global _MATERIAL_CACHE_LEASE_DEPTH
    if not acquired:
        return
    if _MATERIAL_CACHE_LEASE_DEPTH <= 0:
        raise RuntimeError("Material cache lease released without acquisition")
    _MATERIAL_CACHE_LEASE_STATS["releases"] += 1
    _MATERIAL_CACHE_LEASE_DEPTH -= 1
    if _MATERIAL_CACHE_LEASE_DEPTH == 0:
        _MATERIAL_CACHE_LEASE_STATS["outer_releases"] += 1
        _clear_transient_material_cache()
        _MATERIAL_CACHE_LEASE_STATS["clears"] += 1


def material_cache_lease_depth() -> int:
    """Return the active nested material-cache lease count."""
    return _MATERIAL_CACHE_LEASE_DEPTH


def material_cache_lease_stats() -> dict[str, int]:
    """Return cumulative import material-cache lease telemetry."""
    return {
        **_MATERIAL_CACHE_LEASE_STATS,
        "depth": _MATERIAL_CACHE_LEASE_DEPTH,
    }


def acquire_json_cache(
    json_tool: Any,
    *,
    before_start: Callable[[], None] | None = None,
) -> bool:
    """Start JSON caching only when the caller becomes the cache owner."""
    if json_tool._use_cache:
        return False
    if before_start is not None:
        before_start()
    json_tool.start_caching()
    return True


def release_json_cache(
    json_tool: Any,
    owned: bool,
    *,
    after_stop: Callable[[], None] | None = None,
) -> None:
    if not owned:
        return
    json_tool.stop_caching()
    if after_stop is not None:
        after_stop()
