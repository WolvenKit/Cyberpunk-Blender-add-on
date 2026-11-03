import hashlib
import json

import bpy

from ...blender.identity import rna_identity, rna_is_live
from ...blender.transactions import (
    register_rollback_hook,
    track_created_datablock,
    track_mutation,
)
from .helper_caches import clear_helper_caches, helper_cache_stats
from .profiling import begin_material_phase, end_material_phase

_MATERIAL_SIGNATURE_PROP = "_cp77_material_signature"
_MATERIAL_PROTOTYPE_SIGNATURE_PROP = "_cp77_material_prototype_signature"
# The material's name when its signatures were written. A copy keeps the signatures but never the name (decal receiver
# composites and surfaces, render-texture copies, a user's duplicate), so only the material they were written on is
# indexed under them.
_MATERIAL_SIGNED_NAME_PROP = "_cp77_material_signed_name"
# A rollback that removes any of these can leave the caches naming removed datablocks.
_ROLLBACK_DATABLOCKS = frozenset({"materials", "node_groups", "images"})
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
    "semantic_identities": 0,
    "semantic_reduced_materials": 0,
    "semantic_trimmed_keys": 0,
    "structure_shapes": 0,
    "structure_copies": 0,
}
# One snapshot per material graph shape built during the current import, copied for the next material of that shape.
# Snapshots are taken right after a build, before the import adds to the material, and removed when the import ends;
# outside an import every material is built in full.
_STRUCTURE_SNAPSHOTS = {}
# Snapshots replaced during the import, removed with the rest when it ends.
_RETIRED_SNAPSHOTS = []
_STRUCTURE_SHARING = {"active": False}
_STRUCTURE_SNAPSHOT_NAME = "CP77 Material Shape"


def _prefer_material(cache, signature, material):
    current = cache.get(signature)
    if current is None or not rna_is_live(current):
        cache[signature] = material
        return True
    try:
        if material.users > current.users:
            cache[signature] = material
    except ReferenceError:
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
            if material.get(_MATERIAL_SIGNED_NAME_PROP) != material.name:
                continue
            signature = material.get(_MATERIAL_SIGNATURE_PROP)
            prototype_signature = material.get(_MATERIAL_PROTOTYPE_SIGNATURE_PROP)
        except ReferenceError:
            continue

        if isinstance(signature, str) and signature:
            indexed += int(
                _prefer_material(
                    _MATERIAL_CACHE,
                    signature,
                    material,
                )
            )
        if isinstance(prototype_signature, str) and prototype_signature:
            prototype_indexed += int(
                _prefer_material(
                    _MATERIAL_PROTOTYPE_CACHE,
                    prototype_signature,
                    material,
                )
            )

    _MATERIAL_CACHE_STATS["indexed"] += indexed
    _MATERIAL_CACHE_STATS["prototype_indexed"] += prototype_indexed
    _MATERIAL_CACHE_INDEXED = True


def _lookup_cached(cache, signature):
    global _MATERIAL_CACHE_INDEXED
    _ensure_material_cache_indexed()
    material = cache.get(signature)
    if rna_is_live(material):
        return material
    if material is None:
        return None

    cache.pop(signature, None)
    _MATERIAL_CACHE_STATS["stale"] += 1
    _MATERIAL_CACHE_INDEXED = False
    _ensure_material_cache_indexed()
    material = cache.get(signature)
    return material if rna_is_live(material) else None


def _record_exact_hit():
    _MATERIAL_CACHE_STATS["hits"] += 1
    _MATERIAL_CACHE_STATS["exact_hits"] += 1


def _record_prototype_hit():
    _MATERIAL_CACHE_STATS["hits"] += 1
    _MATERIAL_CACHE_STATS["prototype_hits"] += 1


def _restore_material_signature(material, signature):
    """Restore persistent identity and rebuild transient lookups after rollback"""
    global _MATERIAL_CACHE_INDEXED
    material[_MATERIAL_SIGNATURE_PROP] = signature
    _MATERIAL_CACHE_INDEXED = False


def _invalidate_material_signature(signature):
    _MATERIAL_CACHE.pop(signature, None)
    for material in bpy.data.materials:
        try:
            if material.get(_MATERIAL_SIGNATURE_PROP) == signature:
                track_mutation(
                    ("material_signature", rna_identity(material)),
                    lambda material=material, signature=signature: (
                        _restore_material_signature(material, signature)
                    ),
                    verify=lambda material=material, signature=signature: (
                        material.get(_MATERIAL_SIGNATURE_PROP) == signature
                    ),
                    label=f"material signature {material.name}",
                )
                del material[_MATERIAL_SIGNATURE_PROP]
        except ReferenceError:
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
        material[_MATERIAL_SIGNED_NAME_PROP] = material.name
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


def rename_cached_material(material, name):
    """Rename material, keeping the signatures written on it valid"""
    signed = material.get(_MATERIAL_SIGNED_NAME_PROP) == material.name
    material.name = name
    if signed:
        material[_MATERIAL_SIGNED_NAME_PROP] = material.name


def _raw_material_digests(raw_material):
    if not isinstance(raw_material, dict):
        encoded = json.dumps(
            raw_material,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        digest = hashlib.blake2b(encoded, digest_size=20).hexdigest()
        return digest, digest

    prototype = {key: item for key, item in raw_material.items() if key != "Name"}
    encoded = json.dumps(
        prototype,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    prototype_digest = hashlib.blake2b(
        encoded,
        digest_size=20,
    ).hexdigest()

    exact = hashlib.blake2b(digest_size=20)
    exact.update(prototype_digest.encode("ascii"))
    exact.update(b"\0")
    if "Name" in raw_material:
        exact.update(b"1")
        exact.update(b"\0")
        exact.update(
            json.dumps(
                raw_material["Name"],
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
        )
    else:
        exact.update(b"0")
    return exact.hexdigest(), prototype_digest


def reset_material_cache_stats():
    for key in _MATERIAL_CACHE_STATS:
        _MATERIAL_CACHE_STATS[key] = 0


def begin_structure_sharing():
    """Share material graph shapes until end_structure_sharing (one import)"""
    _clear_structure_snapshots()
    _STRUCTURE_SHARING["active"] = True


def end_structure_sharing():
    _STRUCTURE_SHARING["active"] = False
    _clear_structure_snapshots()


def structure_sharing_active():
    return _STRUCTURE_SHARING["active"]


def remember_structure(key, material, slots):
    """Keep a snapshot of a freshly built material for later materials of the same shape"""
    if not _STRUCTURE_SHARING["active"]:
        return
    snapshot = track_created_datablock("materials", material.copy())
    snapshot.name = _STRUCTURE_SNAPSHOT_NAME
    previous = _STRUCTURE_SNAPSHOTS.get(key)
    _STRUCTURE_SNAPSHOTS[key] = (snapshot, dict(slots))
    _MATERIAL_CACHE_STATS["structure_shapes"] += 1
    if previous is not None:
        _RETIRED_SNAPSHOTS.append(previous[0])


def structure_snapshot(key):
    """The snapshot and node slots kept for a graph shape, if one was built during this import"""
    entry = _STRUCTURE_SNAPSHOTS.get(key) if _STRUCTURE_SHARING["active"] else None
    if entry is None:
        return None
    if not rna_is_live(entry[0]):
        _STRUCTURE_SNAPSHOTS.pop(key, None)
        return None
    return entry


def record_structure_copy():
    _MATERIAL_CACHE_STATS["structure_copies"] += 1


def _clear_structure_snapshots():
    snapshots = [
        snapshot
        for snapshot in (
            *(entry[0] for entry in _STRUCTURE_SNAPSHOTS.values()),
            *_RETIRED_SNAPSHOTS,
        )
        if rna_is_live(snapshot)
    ]
    _STRUCTURE_SNAPSHOTS.clear()
    _RETIRED_SNAPSHOTS.clear()
    if snapshots:
        # One pass for all of them: every single removal scans the whole file for users.
        bpy.data.batch_remove(snapshots)


def clear_material_cache(
    *,
    clear_persistent=True,
    reset_stats=True,
    clear_helpers=True,
):
    """Clear transient lookup state without necessarily erasing telemetry or live signatures"""
    global _MATERIAL_CACHE_INDEXED
    _MATERIAL_CACHE.clear()
    _MATERIAL_PROTOTYPE_CACHE.clear()
    _MATERIAL_CACHE_INDEXED = False

    if reset_stats:
        reset_material_cache_stats()
    if clear_helpers:
        clear_helper_caches()

    if not clear_persistent:
        return
    for material in bpy.data.materials:
        try:
            for property_name in (
                _MATERIAL_SIGNATURE_PROP,
                _MATERIAL_PROTOTYPE_SIGNATURE_PROP,
                _MATERIAL_SIGNED_NAME_PROP,
            ):
                if property_name in material:
                    del material[property_name]
        except ReferenceError:
            pass


def _clear_after_rollback(removed_types):
    if removed_types & _ROLLBACK_DATABLOCKS:
        clear_material_cache(
            clear_persistent=False, reset_stats=False, clear_helpers=True
        )


register_rollback_hook("material_cache", _clear_after_rollback)


def warm_material_cache_index():
    """Index signature-tagged Blender materials for persistent cache reuse"""
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
        helpers = helper_cache_stats()
        stats["helpers"] = helpers
        stats["multilayer"] = helpers.get("multilayer", {})
        stats["decal_helpers"] = helpers.get("decal", {})
        stats["parameter_keys"] = helpers.get("material_params", {})
        stats["material_node_groups"] = helpers.get("material_node_groups", {})
        stats["images"] = helpers.get("images", {})
        stats["skin_runtime"] = helpers.get("skin_runtime", {})
    return stats
