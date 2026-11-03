from __future__ import annotations

<<<<<<< Updated upstream

=======
>>>>>>> Stashed changes
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
<<<<<<< Updated upstream
    """Clear lookup indexes while preserving persistent material signatures."""
=======
    """Clear lookup indexes while preserving persistent material signatures"""
>>>>>>> Stashed changes
    from ...materials.blender.cache import clear_material_cache

    clear_material_cache(
        clear_persistent=False,
        reset_stats=False,
        clear_helpers=False,
    )


def acquire_material_cache(enabled: bool = True) -> bool:
<<<<<<< Updated upstream
    """Join the active import material-cache lease."""
=======
    """Join the active import material-cache lease"""
>>>>>>> Stashed changes
    global _MATERIAL_CACHE_LEASE_DEPTH
    if not enabled:
        return False
    _MATERIAL_CACHE_LEASE_STATS["acquisitions"] += 1
    if _MATERIAL_CACHE_LEASE_DEPTH == 0:
        _MATERIAL_CACHE_LEASE_STATS["outer_acquisitions"] += 1
        _clear_transient_material_cache()
        _MATERIAL_CACHE_LEASE_STATS["clears"] += 1
<<<<<<< Updated upstream
=======
        from ...materials.blender.cache import begin_structure_sharing

        begin_structure_sharing()
>>>>>>> Stashed changes
    _MATERIAL_CACHE_LEASE_DEPTH += 1
    _MATERIAL_CACHE_LEASE_STATS["max_depth"] = max(
        _MATERIAL_CACHE_LEASE_STATS["max_depth"],
        _MATERIAL_CACHE_LEASE_DEPTH,
    )
    return True


def release_material_cache(acquired: bool) -> None:
<<<<<<< Updated upstream
    """Leave the active import material-cache lease."""
=======
    """Leave the active import material-cache lease"""
>>>>>>> Stashed changes
    global _MATERIAL_CACHE_LEASE_DEPTH
    if not acquired:
        return
    if _MATERIAL_CACHE_LEASE_DEPTH <= 0:
        raise RuntimeError("Material cache lease released without acquisition")
    _MATERIAL_CACHE_LEASE_STATS["releases"] += 1
    _MATERIAL_CACHE_LEASE_DEPTH -= 1
    if _MATERIAL_CACHE_LEASE_DEPTH == 0:
        _MATERIAL_CACHE_LEASE_STATS["outer_releases"] += 1
<<<<<<< Updated upstream
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
=======
        from ...materials.blender.cache import end_structure_sharing

        end_structure_sharing()
        _clear_transient_material_cache()
        _MATERIAL_CACHE_LEASE_STATS["clears"] += 1
>>>>>>> Stashed changes
