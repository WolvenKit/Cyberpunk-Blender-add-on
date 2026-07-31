import hashlib
import json

import bpy

from .profiling import begin_material_phase, end_material_phase
from .helper_caches import clear_helper_caches, helper_cache_stats
from ..pathing import context_path_key

_MATERIAL_SIGNATURE_PROP = "_cp77_material_signature"
_MATERIAL_PROTOTYPE_SIGNATURE_PROP = "_cp77_material_prototype_signature"
_MATERIAL_CACHE = {}
_MATERIAL_PROTOTYPE_CACHE = {}
_MATERIAL_CACHE_INDEXED = False
_MATERIAL_CACHE_STATS = {
    "hits": 0,
    "exact_hits": 0,
    "prototype_hits": 0,
    "misses": 0,
    "builds": 0,
    "clones": 0,
    "forced_rebuilds": 0,
    "indexed": 0,
    "prototype_indexed": 0,
    "stale": 0,
}

def _clear_helper_caches():
    clear_helper_caches()


def _helper_cache_stats():
    return helper_cache_stats()


_context_path_key = context_path_key


def _material_is_live(material):
    if material is None:
        return False
    try:
        return bpy.data.materials.get(material.name) is material
    except (AttributeError, ReferenceError, TypeError):
        return False


def _prefer_material(cache, signature, material):
    current = cache.get(signature)
    if current is None or not _material_is_live(current):
        cache[signature] = material
        return True
    try:
        if material.users > current.users:
            cache[signature] = material
    except (AttributeError, ReferenceError, TypeError):
        pass
    return False


def _ensure_material_cache_indexed():
    global _MATERIAL_CACHE_INDEXED
    if _MATERIAL_CACHE_INDEXED:
        return

    indexed = 0
    prototype_indexed = 0
    for material in bpy.data.materials:
        try:
            signature = material.get(_MATERIAL_SIGNATURE_PROP)
            prototype_signature = material.get(
                _MATERIAL_PROTOTYPE_SIGNATURE_PROP
            )
        except (AttributeError, ReferenceError, TypeError):
            continue

        if isinstance(signature, str) and signature:
            indexed += int(_prefer_material(
                _MATERIAL_CACHE,
                signature,
                material,
            ))
        if isinstance(prototype_signature, str) and prototype_signature:
            prototype_indexed += int(_prefer_material(
                _MATERIAL_PROTOTYPE_CACHE,
                prototype_signature,
                material,
            ))

    _MATERIAL_CACHE_STATS["indexed"] += indexed
    _MATERIAL_CACHE_STATS["prototype_indexed"] += prototype_indexed
    _MATERIAL_CACHE_INDEXED = True


def _lookup_cached(cache, signature):
    global _MATERIAL_CACHE_INDEXED
    _ensure_material_cache_indexed()
    material = cache.get(signature)
    if _material_is_live(material):
        return material
    if material is None:
        return None

    cache.pop(signature, None)
    _MATERIAL_CACHE_STATS["stale"] += 1
    _MATERIAL_CACHE_INDEXED = False
    _ensure_material_cache_indexed()
    material = cache.get(signature)
    return material if _material_is_live(material) else None


def _record_exact_hit():
    _MATERIAL_CACHE_STATS["hits"] += 1
    _MATERIAL_CACHE_STATS["exact_hits"] += 1


def _record_prototype_hit():
    _MATERIAL_CACHE_STATS["hits"] += 1
    _MATERIAL_CACHE_STATS["prototype_hits"] += 1


def _invalidate_material_signature(signature):
    _MATERIAL_CACHE.pop(signature, None)
    for material in bpy.data.materials:
        try:
            if material.get(_MATERIAL_SIGNATURE_PROP) == signature:
                del material[_MATERIAL_SIGNATURE_PROP]
        except (AttributeError, ReferenceError, TypeError):
            pass


def _cache_material(
    signature,
    prototype_signature,
    material,
    *,
    cloned=False,
):
    started = begin_material_phase()
    try:
        material[_MATERIAL_SIGNATURE_PROP] = signature
        material[_MATERIAL_PROTOTYPE_SIGNATURE_PROP] = prototype_signature
        _MATERIAL_CACHE[signature] = material
        _MATERIAL_PROTOTYPE_CACHE[prototype_signature] = material
        _MATERIAL_CACHE_STATS["clones" if cloned else "builds"] += 1
        return material
    finally:
        if started is not None:
            end_material_phase(
                started,
                "material.cache_store",
                label=getattr(material, "name", ""),
                metadata={"cloned": bool(cloned)},
            )


def _raw_material_digest(raw_material, *, include_name):
    value = raw_material
    if not include_name and isinstance(raw_material, dict):
        value = {
            key: item
            for key, item in raw_material.items()
            if key != "Name"
        }
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.blake2b(encoded, digest_size=20).hexdigest()

def reset_material_cache_stats():
    for key in _MATERIAL_CACHE_STATS:
        _MATERIAL_CACHE_STATS[key] = 0


def clear_material_cache(
    *,
    clear_persistent=True,
    reset_stats=True,
    clear_helpers=True,
):
    """Clear transient lookup state without necessarily erasing telemetry or live signatures."""
    global _MATERIAL_CACHE_INDEXED
    _MATERIAL_CACHE.clear()
    _MATERIAL_PROTOTYPE_CACHE.clear()
    _MATERIAL_CACHE_INDEXED = False

    if reset_stats:
        reset_material_cache_stats()
    if clear_helpers:
        _clear_helper_caches()

    if not clear_persistent:
        return
    for material in bpy.data.materials:
        try:
            for property_name in (
                _MATERIAL_SIGNATURE_PROP,
                _MATERIAL_PROTOTYPE_SIGNATURE_PROP,
            ):
                if property_name in material:
                    del material[property_name]
        except (AttributeError, ReferenceError, TypeError):
            pass


def warm_material_cache_index():
    """Index signature-tagged Blender materials for persistent cache reuse."""
    before_exact = len(_MATERIAL_CACHE)
    before_prototypes = len(_MATERIAL_PROTOTYPE_CACHE)
    _ensure_material_cache_indexed()
    return {
        "exact_entries_added": max(0, len(_MATERIAL_CACHE) - before_exact),
        "prototype_entries_added": max(
            0,
            len(_MATERIAL_PROTOTYPE_CACHE) - before_prototypes,
        ),
        "indexed": bool(_MATERIAL_CACHE_INDEXED),
    }


def material_cache_counters():
    return dict(_MATERIAL_CACHE_STATS)


def material_cache_stats(*, include_helpers=True):
    stats = {
        **_MATERIAL_CACHE_STATS,
        "entries": len(_MATERIAL_CACHE),
        "prototype_entries": len(_MATERIAL_PROTOTYPE_CACHE),
    }
    if include_helpers:
        helpers = _helper_cache_stats()
        stats["helpers"] = helpers
        stats["multilayer"] = helpers.get("multilayer", {})
        stats["decal_helpers"] = helpers.get("decal", {})
        stats["parameter_keys"] = helpers.get("material_params", {})
        stats["material_node_groups"] = helpers.get("material_node_groups", {})
    return stats
