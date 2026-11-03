from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

import bpy
from bpy.app.handlers import persistent

from ...animation.domain.rig.assembly import merge_rig_datas
from ...animation.domain.rig.ordering import promote_rig_base
from ...animation.services.rig.repository import stored_rig_document
from ...assetio.documents import file_identity
from ...assetio.paths import depot_path_key, local_path_key
from ...blender.armature_edit import assembly_name, atomic_armature_update
from ...blender.identity import rna_identity
from ...blender.rig_metadata import (
    effective_metarig_part_ledger,
    source_rig_part_bindings,
    stored_json_array,
)
from ...blender.transactions import track_created_datablock, track_mutation
from ...core.log import debug_exception, get_logger, is_enabled, log_once
from ...gltf.provenance import GLBProvenanceError, read_glb_json
from ..animation.document import import_anims_glb_to_armature
from ..common.entity_data import component_name
from ..common.paths import depot_path
from ..rig.reader import (
    create_armature_from_rig_data,
    create_armature_from_rig_files,
    load_rig_data,
    merged_rig_document,
    reconcile_armature_from_rig_data,
    reconcile_armature_overlay_from_rig_data,
    rig_collection_for,
    rig_data_definition_hash,
    rig_data_to_root_chunk,
)
from .transforms import (
    cache_armature_bones,
    is_live_armature_object,
    rig_bone_index_for,
)

_LOG = get_logger(__name__)

ARMATURE_TYPE = "ARMATURE"
_RIG_ARMATURE_OBJECT_CACHE: dict[str, Any] = {}
_RIG_ARMATURE_PROTOTYPE_CACHE: dict[str, Any] = {}
_RIG_ARMATURE_PROTOTYPE_LIMIT = 32
_RIG_PROTOTYPE_MARKER = "cp77_entity_rig_prototype"


def _part_bindings_for_ledger(armature, ledger) -> tuple[dict[str, str], ...]:
    stored = source_rig_part_bindings(armature)
    by_source = {
        local_path_key(str(value.get("source_path", "") or "")): value
        for value in stored
        if value.get("source_path")
    }
    by_path = {
        local_path_key(str(value.get("path", "") or "")): value
        for value in stored
        if value.get("path")
    }
    result = []
    for entry in ledger:
        source_path = str(entry.get("source_path", "") or "")
        path = str(entry.get("path", "") or "")
        previous = (
            by_source.get(local_path_key(source_path))
            or by_path.get(local_path_key(path))
            or {}
        )
        result.append(
            {
                "source_path": source_path,
                "path": path,
                "component": str(previous.get("component", "") or ""),
                "graph": str(previous.get("graph", "") or ""),
            }
        )
    return tuple(result)


def _build_meta_rig_part_bindings(loaded_rigs, ledger) -> tuple[dict[str, str], ...]:
    return tuple(
        {
            "source_path": str(ledger_entry.get("source_path", "") or ""),
            "path": str(record[2] or ""),
            "component": str(record[1] or ""),
            "graph": depot_path(record[0], "graph", normalize=False)
            if isinstance(record[0], dict)
            else "",
        }
        for record, ledger_entry in zip(loaded_rigs, ledger)
    )


def _remove_armature_prototype(prototype) -> None:
    if prototype is None:
        return
    try:
        data = prototype.data
    except (AttributeError, ReferenceError, RuntimeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_remove_armature_prototype 1", type(error).__name__),
            "remove armature prototype: fell back after %s",
            error,
            exc_info=True,
        )
        return
    try:
        bpy.data.objects.remove(prototype, do_unlink=True)
    except (AttributeError, ReferenceError, RuntimeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_remove_armature_prototype 2", type(error).__name__),
            "remove armature prototype: fell back after %s",
            error,
            exc_info=True,
        )
    if data is None:
        return
    try:
        unused = data.users == 0
    except (AttributeError, ReferenceError, RuntimeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_remove_armature_prototype 3", type(error).__name__),
            "remove armature prototype: fell back after %s",
            error,
            exc_info=True,
        )
        return
    if unused:
        try:
            bpy.data.armatures.remove(data)
        except (AttributeError, ReferenceError, RuntimeError) as error:
            log_once(
                _LOG,
                "DEBUG",
                ("_remove_armature_prototype 4", type(error).__name__),
                "remove armature prototype: fell back after %s",
                error,
                exc_info=True,
            )


def clear_rig_prototype_cache() -> None:
    for prototype in tuple(_RIG_ARMATURE_PROTOTYPE_CACHE.values()):
        _remove_armature_prototype(prototype)
    _RIG_ARMATURE_PROTOTYPE_CACHE.clear()


def clear_rig_caches(*, clear_prototypes: bool = False) -> None:
    """Clear per-import rig objects and optionally reusable armature prototypes"""
    _RIG_ARMATURE_OBJECT_CACHE.clear()
    if clear_prototypes:
        clear_rig_prototype_cache()


@atomic_armature_update
def reconcile_existing_metarig_parts(
    existing_rig, source_paths, *, rig_repository=None
):
    if not is_live_armature_object(existing_rig):
        raise ValueError("An existing MetaRig armature is required")
    ledger = effective_metarig_part_ledger(existing_rig, source_paths)
    paths = tuple(entry["path"] for entry in ledger)
    if not paths:
        raise ValueError("The appearance does not define a usable MetaRig composition")
    missing = [
        path
        for path in paths
        if not os.path.isfile(path) and stored_rig_document(path) is None
    ]
    if missing:
        raise FileNotFoundError("Rig export not found: " + ", ".join(missing[:4]))
    rig_datas = [load_rig_data(path, rig_repository) for path in paths]
    invalid = [path for path, data in zip(paths, rig_datas) if data is None]
    if invalid:
        raise ValueError("Rig export could not be parsed: " + ", ".join(invalid[:4]))

    merged, metadata = merge_rig_datas(
        rig_datas,
        assembly_name(existing_rig),
        return_metadata=True,
    )
    definition_hash = rig_data_definition_hash(merged)
    source_label = "metarig:" + ";".join(paths)
    # The stored source label and export template list the parts, so a new part list
    # rebuilds them even when the merged definition is unchanged.
    if (
        str(existing_rig.get("cp77_metarig_definition_hash", "") or "")
        != definition_hash
        or str(existing_rig.data.get("cp77_source_rig_file", "") or "") != source_label
        or not set(merged.bone_names).issubset(existing_rig.data.bones.keys())
    ):
        source_document = merged_rig_document(
            paths,
            merged,
            source_label,
            rig_datas,
        )
        reconcile_armature_from_rig_data(
            existing_rig,
            merged,
            source_rig_file=source_label,
            source_document=source_document,
            assign_shapes=False,
        )

    existing_rig["rig"] = paths[0]
    existing_rig["cp77_source_rig_file"] = source_label
    existing_rig["cp77_rig_merge_order"] = list(paths)
    existing_rig["cp77_rig_merge_order"] = list(paths)
    existing_rig["cp77_metarig_definition_hash"] = definition_hash
    existing_rig["cp77_metarig_part_ledger"] = json.dumps(
        list(ledger), separators=(",", ":")
    )
    existing_rig["cp77_metarig_part_bindings"] = json.dumps(
        list(_part_bindings_for_ledger(existing_rig, ledger)), separators=(",", ":")
    )
    clear_rig_caches()
    cache_armature_bones(existing_rig)
    return existing_rig


@atomic_armature_update
def reconcile_existing_metarig_overlay(
    existing_rig,
    base_source_paths,
    overlay_source_paths,
    *,
    rig_repository=None,
):
    if not is_live_armature_object(existing_rig):
        raise ValueError("An existing MetaRig armature is required")

    base_sources = tuple(str(path or "") for path in base_source_paths if path)
    overlay_sources = tuple(str(path or "") for path in overlay_source_paths if path)
    combined_sources = tuple(dict.fromkeys((*base_sources, *overlay_sources)))
    if not combined_sources:
        raise ValueError("The appearance does not define a usable MetaRig composition")

    ledger = effective_metarig_part_ledger(existing_rig, combined_sources)
    base_source_keys = {local_path_key(path) for path in base_sources}
    overlay_source_keys = {local_path_key(path) for path in overlay_sources}
    base_ledger = tuple(
        entry
        for entry in ledger
        if entry.get("user_addition")
        or local_path_key(str(entry.get("source_path", "") or "")) in base_source_keys
    )
    overlay_ledger = tuple(
        entry
        for entry in ledger
        if local_path_key(str(entry.get("source_path", "") or ""))
        in overlay_source_keys
    )

    paths = tuple(str(entry["path"]) for entry in ledger)
    base_paths = tuple(str(entry["path"]) for entry in base_ledger)
    overlay_paths = tuple(str(entry["path"]) for entry in overlay_ledger)
    missing = [
        path
        for path in paths
        if not os.path.isfile(path) and stored_rig_document(path) is None
    ]
    if missing:
        raise FileNotFoundError("Rig export not found: " + ", ".join(missing[:4]))

    rig_datas = [load_rig_data(path, rig_repository) for path in paths]
    invalid = [path for path, data in zip(paths, rig_datas) if data is None]
    if invalid:
        raise ValueError("Rig export could not be parsed: " + ", ".join(invalid[:4]))

    base_path_keys = {local_path_key(path) for path in base_paths}
    base_rig_datas = [
        data
        for entry, data in zip(ledger, rig_datas)
        if entry.get("user_addition")
        or local_path_key(str(entry.get("path", "") or "")) in base_path_keys
    ]
    base_rig_data = None
    if base_rig_datas:
        base_rig_data = merge_rig_datas(
            base_rig_datas,
            assembly_name(existing_rig) + "_base",
        )
    merged, _metadata = merge_rig_datas(
        rig_datas,
        assembly_name(existing_rig),
        return_metadata=True,
    )
    definition_hash = rig_data_definition_hash(merged)
    current_definition_hash = str(
        existing_rig.get("cp77_metarig_definition_hash", "") or ""
    )
    overlay_owner_hash = str(
        existing_rig.get("cp77_metarig_overlay_owner_hash", "") or ""
    )
    previous_overlay_bones = (
        stored_json_array(existing_rig, "cp77_metarig_overlay_bones")
        if overlay_owner_hash and overlay_owner_hash == current_definition_hash
        else []
    )
    if not previous_overlay_bones and base_rig_data is not None:
        base_names = {str(name) for name in base_rig_data.bone_names}
        previous_overlay_bones = [
            bone.name
            for bone in existing_rig.data.bones
            if bone.name not in base_names and bone.get("cp77_rig_source_name")
        ]

    source_label = "metarig:" + ";".join(paths)
    previous_overlay_paths = tuple(
        str(value)
        for value in stored_json_array(
            existing_rig,
            "cp77_metarig_overlay_effective_order",
        )
        if value
    )
    topology_changed = str(
        existing_rig.get("cp77_metarig_definition_hash", "") or ""
    ) != definition_hash or tuple(
        local_path_key(path) for path in previous_overlay_paths
    ) != tuple(local_path_key(path) for path in overlay_paths)
    if topology_changed or not set(merged.bone_names).issubset(
        existing_rig.data.bones.keys()
    ):
        source_document = merged_rig_document(
            paths,
            merged,
            source_label,
            rig_datas,
        )
        overlay_bones = reconcile_armature_overlay_from_rig_data(
            existing_rig,
            base_rig_data,
            merged,
            source_rig_file=source_label,
            source_document=source_document,
        )
    else:
        overlay_bones = tuple(str(value) for value in previous_overlay_bones)

    existing_rig["rig"] = paths[0]
    existing_rig["cp77_source_rig_file"] = source_label
    existing_rig["cp77_rig_merge_order"] = list(paths)
    existing_rig["cp77_rig_merge_order"] = list(paths)
    existing_rig["cp77_metarig_definition_hash"] = definition_hash
    existing_rig["cp77_metarig_part_ledger"] = json.dumps(
        list(ledger), separators=(",", ":")
    )
    existing_rig["cp77_metarig_part_bindings"] = json.dumps(
        list(_part_bindings_for_ledger(existing_rig, ledger)), separators=(",", ":")
    )
    existing_rig["cp77_metarig_base_source_order"] = json.dumps(
        list(base_sources), separators=(",", ":")
    )
    existing_rig["cp77_metarig_overlay_source_order"] = json.dumps(
        list(overlay_sources), separators=(",", ":")
    )
    existing_rig["cp77_metarig_base_effective_order"] = json.dumps(
        list(base_paths), separators=(",", ":")
    )
    existing_rig["cp77_metarig_overlay_effective_order"] = json.dumps(
        list(overlay_paths), separators=(",", ":")
    )
    existing_rig["cp77_metarig_overlay_bones"] = json.dumps(
        list(overlay_bones), separators=(",", ":")
    )
    existing_rig["cp77_metarig_overlay_owner_hash"] = definition_hash
    if base_rig_data is not None:
        existing_rig["cp77_metarig_base_definition_hash"] = rig_data_definition_hash(
            base_rig_data
        )

    clear_rig_caches()
    cache_armature_bones(existing_rig)
    return existing_rig


@atomic_armature_update
def _apply_imported_composition(target, merged, paths, rig_datas, properties):
    source_label = "metarig:" + ";".join(paths)
    if (
        str(target.get("cp77_metarig_definition_hash", ""))
        != properties["cp77_metarig_definition_hash"]
        or not set(merged.bone_names).issubset(target.data.bones.keys())
        or str(target.data.get("cp77_source_rig_file", "")) != source_label
    ):
        reconcile_armature_from_rig_data(
            target,
            merged,
            source_rig_file=source_label,
            source_document=merged_rig_document(paths, merged, source_label, rig_datas),
            assign_shapes=False,
        )
    for key, value in properties.items():
        target[key] = value
    clear_rig_caches()
    return target


@persistent
def invalidate_rig_caches_on_file_load(_unused=None) -> None:
    clear_rig_caches(clear_prototypes=True)


def register_rig_cache_handlers() -> None:
    handlers = bpy.app.handlers.load_pre
    if invalidate_rig_caches_on_file_load not in handlers:
        handlers.append(invalidate_rig_caches_on_file_load)


def unregister_rig_cache_handlers() -> None:
    handlers = bpy.app.handlers.load_pre
    if invalidate_rig_caches_on_file_load in handlers:
        handlers.remove(invalidate_rig_caches_on_file_load)
    clear_rig_caches(clear_prototypes=True)


def _clear_instance_rig_metadata(armature) -> None:
    for key in ("cp77_entity_file", "componentName", "animset", _RIG_PROTOTYPE_MARKER):
        try:
            if key in armature:
                del armature[key]
        except (KeyError, TypeError):
            pass


def _store_armature_prototype(cache_key: str, armature) -> None:
    if not is_live_armature_object(armature) or getattr(armature, "data", None) is None:
        return
    prototype = None
    try:
        prototype = track_created_datablock("objects", armature.copy())
        prototype.data = track_created_datablock("armatures", armature.data.copy())
        prototype.name = "__CP77_ENTITY_RIG_PROTOTYPE__"
        prototype.data.name = "__CP77_ENTITY_RIG_PROTOTYPE_DATA__"
        prototype.hide_viewport = True
        prototype.hide_render = True
        if getattr(prototype, "animation_data", None) is not None:
            prototype.animation_data_clear()
        _clear_instance_rig_metadata(prototype)
        prototype[_RIG_PROTOTYPE_MARKER] = True
    except Exception:
        debug_exception(_LOG, "Could not cache the entity rig prototype")
        _remove_armature_prototype(prototype)
        return

    previous = _RIG_ARMATURE_PROTOTYPE_CACHE.pop(cache_key, None)
    _remove_armature_prototype(previous)
    _RIG_ARMATURE_PROTOTYPE_CACHE[cache_key] = prototype
    while len(_RIG_ARMATURE_PROTOTYPE_CACHE) > _RIG_ARMATURE_PROTOTYPE_LIMIT:
        _old_key, old_prototype = next(iter(_RIG_ARMATURE_PROTOTYPE_CACHE.items()))
        _RIG_ARMATURE_PROTOTYPE_CACHE.pop(_old_key, None)
        _remove_armature_prototype(old_prototype)


def _clone_armature_prototype(cache_key: str, object_name: str):
    prototype = _RIG_ARMATURE_PROTOTYPE_CACHE.get(cache_key)
    if (
        not is_live_armature_object(prototype)
        or getattr(prototype, "data", None) is None
    ):
        if prototype is not None:
            _RIG_ARMATURE_PROTOTYPE_CACHE.pop(cache_key, None)
        return None
    clone = None
    try:
        clone = track_created_datablock("objects", prototype.copy())
        clone.data = track_created_datablock("armatures", prototype.data.copy())
        clone.name = object_name
        clone.data.name = f"{object_name}_Data"
        clone.hide_viewport = False
        clone.hide_render = False
        if getattr(clone, "animation_data", None) is not None:
            clone.animation_data_clear()
        _clear_instance_rig_metadata(clone)

        rig_collection_for(object_name).objects.link(clone)
        try:
            clone.hide_set(False)
        except RuntimeError:
            pass
        cache_armature_bones(clone)
        return clone
    except Exception:
        debug_exception(_LOG, "Could not clone the entity rig prototype %s", cache_key)
        _remove_armature_prototype(clone)
        return None


def _rig_prototype_key(source_key: str, source_paths) -> str:
    """Include file state so reusable prototypes cannot outlive changed rig exports"""
    signatures = []
    for path in source_paths or ():
        normalized = local_path_key(path)
        identity = file_identity(path)
        if identity.mtime_ns or identity.size:
            signatures.append(f"{normalized}:{identity.mtime_ns}:{identity.size}")
        else:
            signatures.append(f"{normalized}:missing")
    return source_key + "|files=" + ";".join(signatures)


def _use_animation_frame_rate(scene):
    render = scene.render
    if render.fps == 30 and render.fps_base == 1.0:
        return
    previous = (render.fps, render.fps_base)
    track_mutation(
        ("scene_frame_rate", rna_identity(scene)),
        lambda render=render, previous=previous: (
            setattr(render, "fps", previous[0]),
            setattr(render, "fps_base", previous[1]),
        ),
        label="scene frame rate",
    )
    render.fps = 30
    render.fps_base = 1.0
    _LOG.info(
        "Scene frame rate changed from %.3f to 30 fps to match imported animation sets",
        previous[0] / previous[1],
    )


def import_animset_to_metarig(anim_path, rig, ent_name="", import_tracks=True):
    if not anim_path:
        return False
    if not is_live_armature_object(rig):
        raise RuntimeError(
            "A live JSON MetaRig is required before importing an animation set"
        )

    _use_animation_frame_rate(bpy.context.scene)
    summary = import_anims_glb_to_armature(
        anim_path,
        rig,
        import_tracks=import_tracks,
        verbose=is_enabled("DEBUG", _LOG),
        assign_action=False,
    )
    cache_armature_bones(rig)
    rig["animset"] = anim_path
    if ent_name:
        rig["cp77_entity_file"] = ent_name + ".ent.json"
    _LOG.debug(
        "Imported %d animations directly onto JSON MetaRig %s",
        summary["animation_count"],
        rig.name,
    )
    return summary


def ensure_armature_from_rig_jsons(
    rig_json_paths, ent_name="", merged_rig_data=None, rig_repository=None
):
    ordered_paths = []
    ordered_keys = []
    seen_keys = set()
    for path in rig_json_paths or ():
        if not path:
            continue
        key = local_path_key(path)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        ordered_paths.append(path)
        ordered_keys.append(key)
    if not ordered_paths:
        return None
    merged_key = "metarig:" + ";".join(ordered_keys)
    existing = _RIG_ARMATURE_OBJECT_CACHE.get(merged_key)
    if is_live_armature_object(existing):
        cache_armature_bones(existing)
        return existing
    if existing is not None:
        _RIG_ARMATURE_OBJECT_CACHE.pop(merged_key, None)

    merged_name = (ent_name + "_rig") if ent_name else "merged_rig"
    prototype_key = _rig_prototype_key(merged_key, ordered_paths)
    prototype_clone = _clone_armature_prototype(prototype_key, merged_name)
    if prototype_clone is not None:
        _RIG_ARMATURE_OBJECT_CACHE[merged_key] = prototype_clone
        prototype_clone["rig"] = ordered_paths[0]
        prototype_clone["cp77_source_rig_file"] = merged_key
        prototype_clone["cp77_rig_merge_order"] = list(ordered_paths)
        if ent_name:
            prototype_clone["cp77_entity_file"] = ent_name + ".ent.json"
        return prototype_clone
    if merged_rig_data is not None:
        source_document = merged_rig_document(
            ordered_paths,
            merged_rig_data,
            merged_key,
        )
        created = create_armature_from_rig_data(
            merged_rig_data,
            "A-Pose",
            source_rig_file=merged_key,
            source_document=source_document,
        )
    else:
        created = create_armature_from_rig_files(
            ordered_paths,
            merged_name,
            source_label=merged_key,
            rig_repository=rig_repository,
        )
    armature = created if getattr(created, "type", None) == ARMATURE_TYPE else None
    if armature is not None:
        cache_armature_bones(armature)
        _RIG_ARMATURE_OBJECT_CACHE[merged_key] = armature
        armature["rig"] = ordered_paths[0]
        armature["cp77_source_rig_file"] = merged_key
        armature["cp77_rig_merge_order"] = list(ordered_paths)
        if ent_name:
            armature["cp77_entity_file"] = ent_name + ".ent.json"
        _store_armature_prototype(prototype_key, armature)
    return armature


_ANIMATION_COMPONENT_TYPES = frozenset(
    {
        "entAnimatedComponent",
        "entAnimationSetupExtensionComponent",
    }
)


def _animation_components(payloads):
    """Yield animated and animation-setup components in document order"""
    pending = list(reversed(tuple(payloads)))
    while pending:
        value = pending.pop()
        if isinstance(value, dict):
            if value.get("$type") in _ANIMATION_COMPONENT_TYPES:
                yield value
            pending.extend(reversed(tuple(value.values())))
        elif isinstance(value, (list, tuple)):
            pending.extend(reversed(value))


def declared_animation_sets(payloads) -> tuple[str, ...]:
    """Gameplay animation sets declared by the components, in entity order"""
    declared = {}
    for component in _animation_components(payloads):
        animations = component.get("animations")
        if not isinstance(animations, dict):
            continue
        for entry in animations.get("gameplay") or ():
            try:
                depot = entry["animSet"]["DepotPath"]["$value"]
            except (KeyError, TypeError):
                continue
            if depot:
                declared.setdefault(depot_path_key(depot), depot)
    return tuple(declared.values())


@dataclass(slots=True)
class EntityRigRuntime:
    ordered_components: tuple[dict, ...]
    rig: Any = None
    rig_json: Any = None
    rig_bone_index: dict[str, int] = field(default_factory=dict)
    rig_json_by_component_name: dict[str, Any] = field(default_factory=dict)
    rig_json_path_by_component_name: dict[str, str] = field(default_factory=dict)
    armature_by_component_name: dict[str, Any] = field(default_factory=dict)
    rig_json_by_bone_name: dict[str, Any] = field(default_factory=dict)
    ordered_rig_paths: tuple[str, ...] = ()
    base_rig_name: str = ""
    base_rig_path: str = ""
    animation_path: str = ""
    meta_rig_metadata: dict[str, Any] = field(default_factory=dict)
    rig_part_ledger: tuple[dict[str, Any], ...] = ()
    meta_rig_part_bindings: tuple[dict[str, str], ...] = ()
    source_rig_paths: tuple[str, ...] = ()
    base_source_rig_paths: tuple[str, ...] = ()
    overlay_source_rig_paths: tuple[str, ...] = ()
    base_effective_rig_paths: tuple[str, ...] = ()
    overlay_effective_rig_paths: tuple[str, ...] = ()


class EntityRigService:
    """Build the JSON MetaRig and resolve its animation target for one import"""

    def __init__(
        self,
        *,
        resources: Any,
        source_root: str,
        entity_name: str,
        animation_files: tuple[str, ...] | list[str],
        animation_files_provider: Any = None,
        import_animations: bool = False,
        component_payloads: tuple = (),
        warnings: list[str],
    ) -> None:
        self.resources = resources
        self.source_root = source_root
        self.entity_name = entity_name
        self.animation_files = tuple(animation_files or ())
        self.animation_files_provider = animation_files_provider
        self.import_animations = bool(import_animations)
        self.component_payloads = tuple(component_payloads or ())
        self.warnings = warnings
        self._animation_rigs = {}

    def _animation_rig_key(self, anim_path: str) -> str:
        """Depot key of the rig an exported animation set targets, from its JSON chunk"""
        key = local_path_key(anim_path)
        if key not in self._animation_rigs:
            try:
                skins = read_glb_json(anim_path).get("skins") or ()
                rig_path = (
                    (skins[0].get("extras") or {}).get("rigPath", "") if skins else ""
                )
            except (GLBProvenanceError, OSError, AttributeError, TypeError) as error:
                log_once(
                    _LOG,
                    "DEBUG",
                    ("EntityRigService._animation_rig_key", type(error).__name__),
                    "animation rig key: fell back after %s",
                    error,
                    exc_info=True,
                )
                rig_path = ""
            self._animation_rigs[key] = depot_path_key(rig_path) if rig_path else ""
        return self._animation_rigs[key]

    def _first_set_for_rig(self, depot_paths, rig_key: str) -> str:
        for depot in depot_paths:
            anim_path = self.resources.resolve_export(depot, ".anims.glb")
            if anim_path and self._animation_rig_key(anim_path) == rig_key:
                return anim_path
        return ""

    def _fallback_animation_files(self) -> tuple[str, ...]:
        if self.animation_files:
            return self.animation_files
        provider = self.animation_files_provider
        if provider is None:
            return ()
        self.animation_files = tuple(provider() or ())
        self.animation_files_provider = None
        return self.animation_files

    def build(self, rig_plan: Any, existing_rig: Any = None) -> EntityRigRuntime:
        ordered_components = tuple(
            promote_rig_base(rig_plan.ordered_components, component_name)
        )
        base_component_ids = {
            id(component)
            for component in getattr(rig_plan, "ordered_base_components", ())
        }
        overlay_component_ids = {
            id(component)
            for component in getattr(rig_plan, "ordered_overlay_components", ())
        }
        runtime = EntityRigRuntime(ordered_components=ordered_components)
        if is_live_armature_object(existing_rig):
            runtime.rig = existing_rig

        if is_enabled("DEBUG", _LOG):
            deformation_authorities = list(rig_plan.deformation_authorities)
            if deformation_authorities:
                _LOG.debug(
                    "JSON MetaRig deformation base authority: %s",
                    ", ".join(deformation_authorities),
                )
            _LOG.debug(
                "JSON MetaRig component order: %s",
                " -> ".join(
                    component_name(component, "<unnamed>")
                    for component in ordered_components
                ),
            )

        loaded_rigs: list[tuple[dict, str, str, Any, dict]] = []

        for component in ordered_components:
            rig_name = component_name(component)
            rig_depot = depot_path(component, "rig", normalize=False)
            rig_json_path = self.resources.resolve_rig(rig_depot)
            rig_data = self.resources.load_rig(rig_json_path) if rig_json_path else None
            rig_json = (
                rig_data.source_document.get("Data", {}).get("RootChunk")
                if rig_data is not None and isinstance(rig_data.source_document, dict)
                else None
            )
            if (
                not rig_name
                or not rig_json_path
                or rig_json is None
                or rig_data is None
            ):
                _LOG.warning(
                    "unable to load JSON rig for animated component '%s': %s",
                    rig_name or "<unnamed>",
                    rig_depot,
                )
                continue
            if rig_name not in runtime.rig_json_path_by_component_name:
                runtime.rig_json_path_by_component_name[rig_name] = rig_json_path
                runtime.rig_json_by_component_name[rig_name] = rig_json
            loaded_rigs.append((component, rig_name, rig_json_path, rig_data, rig_json))

        loaded_components = promote_rig_base(
            [record[0] for record in loaded_rigs], component_name
        )
        record_by_identity = {id(record[0]): record for record in loaded_rigs}
        loaded_rigs = [
            record_by_identity[id(component)] for component in loaded_components
        ]

        runtime.source_rig_paths = tuple(record[2] for record in loaded_rigs)
        runtime.base_source_rig_paths = tuple(
            record[2] for record in loaded_rigs if id(record[0]) in base_component_ids
        )
        runtime.overlay_source_rig_paths = tuple(
            record[2]
            for record in loaded_rigs
            if id(record[0]) in overlay_component_ids
        )
        rig_part_ledger = effective_metarig_part_ledger(
            existing_rig if is_live_armature_object(existing_rig) else {},
            runtime.source_rig_paths,
        )
        records = {local_path_key(record[2]): record for record in loaded_rigs}
        customized = []
        for entry in rig_part_ledger:
            path = entry["path"]
            record = records.get(local_path_key(entry["source_path"]))
            if record is not None and local_path_key(record[2]) == local_path_key(path):
                customized.append(record)
                continue
            data = self.resources.load_rig(path)
            if data is None or not isinstance(data.source_document, dict):
                raise ValueError(f"Required MetaRig part is unavailable: {path}")
            root = data.source_document.get("Data", {}).get("RootChunk")
            if root is None:
                raise ValueError(f"Required MetaRig part has no rig definition: {path}")
            component, name = (
                (record[0], record[1]) if record else ({}, os.path.basename(path)[:-9])
            )
            customized.append((component, name, path, data, root))
        loaded_rigs = customized
        runtime.rig_part_ledger = tuple(rig_part_ledger)
        runtime.meta_rig_part_bindings = _build_meta_rig_part_bindings(
            loaded_rigs, runtime.rig_part_ledger
        )
        if is_enabled("DEBUG", _LOG):
            _LOG.debug(
                "JSON MetaRig graph bindings: %s",
                tuple(
                    (
                        value.get("component", ""),
                        value.get("graph", ""),
                        value.get("path", ""),
                    )
                    for value in runtime.meta_rig_part_bindings
                ),
            )
        base_source_keys = {
            local_path_key(path) for path in runtime.base_source_rig_paths
        }
        overlay_source_keys = {
            local_path_key(path) for path in runtime.overlay_source_rig_paths
        }
        base_effective_records = []
        overlay_effective_records = []
        for record, ledger_entry in zip(loaded_rigs, runtime.rig_part_ledger):
            source_key = local_path_key(str(ledger_entry.get("source_path", "") or ""))
            if ledger_entry.get("user_addition") or source_key in base_source_keys:
                base_effective_records.append(record)
            elif source_key in overlay_source_keys:
                overlay_effective_records.append(record)
        runtime.base_effective_rig_paths = tuple(
            record[2] for record in base_effective_records
        )
        runtime.overlay_effective_rig_paths = tuple(
            record[2] for record in overlay_effective_records
        )

        runtime.rig_json_path_by_component_name.clear()
        runtime.rig_json_by_component_name.clear()
        for component, rig_name, rig_json_path, _rig_data, rig_json in loaded_rigs:
            if rig_name and rig_name not in runtime.rig_json_path_by_component_name:
                runtime.rig_json_path_by_component_name[rig_name] = rig_json_path
                runtime.rig_json_by_component_name[rig_name] = rig_json

        ordered_rig_names = [record[1] for record in loaded_rigs]
        ordered_rig_paths = [record[2] for record in loaded_rigs]
        ordered_rig_datas = [record[3] for record in loaded_rigs]

        base_component = loaded_rigs[0][0] if loaded_rigs else None
        runtime.base_rig_name = component_name(base_component) if base_component else ""
        runtime.base_rig_path = runtime.rig_json_path_by_component_name.get(
            runtime.base_rig_name, ""
        )

        if self.import_animations and base_component is not None:
            base_rig_key = depot_path_key(
                depot_path(base_component, "rig", normalize=False)
            )
            declared = declared_animation_sets(
                self.component_payloads or ordered_components
            )
            runtime.animation_path = self._first_set_for_rig(declared, base_rig_key)
            if not runtime.animation_path:
                runtime.animation_path = next(
                    (
                        anim_path
                        for anim_path in self._fallback_animation_files()
                        if self._animation_rig_key(anim_path) == base_rig_key
                    ),
                    "",
                )
                if runtime.animation_path:
                    message = (
                        f"No animation set declared by {self.entity_name or 'the entity'} "
                        f"is exported; imported {os.path.basename(runtime.animation_path)} "
                        "because it targets the same rig"
                    )
                    _LOG.warning("%s", message)
                    self.warnings.append(message)
            if not runtime.animation_path:
                _LOG.debug("No exported animation set targets the entity base rig")

        if ordered_rig_datas and runtime.base_rig_path:
            merged_rig_data, runtime.meta_rig_metadata = merge_rig_datas(
                ordered_rig_datas,
                (self.entity_name + "_rig") if self.entity_name else "merged_rig",
                return_metadata=True,
            )
            base_rig_data = None
            if base_effective_records:
                base_rig_data = merge_rig_datas(
                    [record[3] for record in base_effective_records],
                    (self.entity_name + "_rig_base")
                    if self.entity_name
                    else "merged_rig_base",
                )
            merged_rig_json = rig_data_to_root_chunk(merged_rig_data)
            definition_hash = rig_data_definition_hash(merged_rig_data)
            source_label = "metarig:" + ";".join(ordered_rig_paths)
            base_names = {
                str(name) for name in getattr(base_rig_data, "bone_names", ())
            }
            target_overlay_bones = tuple(
                str(name)
                for name in merged_rig_data.bone_names
                if str(name) not in base_names
            )
            if is_live_armature_object(existing_rig):
                runtime.rig = existing_rig
            else:
                runtime.rig = ensure_armature_from_rig_jsons(
                    ordered_rig_paths,
                    self.entity_name,
                    merged_rig_data=merged_rig_data,
                    rig_repository=self.resources.rigs,
                )
            if is_live_armature_object(runtime.rig):
                cache_armature_bones(runtime.rig)
                for rig_name in ordered_rig_names:
                    runtime.armature_by_component_name[rig_name] = runtime.rig
                runtime.rig_json = merged_rig_json
                runtime.rig_bone_index = rig_bone_index_for(runtime.rig_json)
                properties = {}
                properties["rig"] = ordered_rig_paths[0]
                properties["cp77_source_rig_file"] = source_label
                properties["cp77_rig_merge_order"] = list(ordered_rig_paths)
                properties["cp77_rig_merge_order"] = list(ordered_rig_paths)
                properties["cp77_metarig_definition_hash"] = definition_hash
                properties["cp77_metarig_part_ledger"] = json.dumps(
                    list(runtime.rig_part_ledger), separators=(",", ":")
                )
                properties["cp77_metarig_part_bindings"] = json.dumps(
                    list(runtime.meta_rig_part_bindings), separators=(",", ":")
                )
                properties["cp77_metarig_base_source_order"] = json.dumps(
                    list(runtime.base_source_rig_paths), separators=(",", ":")
                )
                properties["cp77_metarig_overlay_source_order"] = json.dumps(
                    list(runtime.overlay_source_rig_paths), separators=(",", ":")
                )
                properties["cp77_metarig_base_effective_order"] = json.dumps(
                    list(runtime.base_effective_rig_paths), separators=(",", ":")
                )
                properties["cp77_metarig_overlay_effective_order"] = json.dumps(
                    list(runtime.overlay_effective_rig_paths), separators=(",", ":")
                )
                properties["cp77_metarig_overlay_bones"] = json.dumps(
                    list(target_overlay_bones), separators=(",", ":")
                )
                properties["cp77_metarig_overlay_owner_hash"] = definition_hash
                if base_rig_data is not None:
                    properties["cp77_metarig_base_definition_hash"] = (
                        rig_data_definition_hash(base_rig_data)
                    )
                for key, default in (
                    ("cp77_metarig_part_overrides", "{}"),
                    ("cp77_metarig_user_additions", "[]"),
                    ("cp77_metarig_removed_parts", "[]"),
                    ("cp77_metarig_removed_slots", "[]"),
                ):
                    if key not in runtime.rig:
                        properties[key] = default
                if is_live_armature_object(existing_rig):
                    _apply_imported_composition(
                        existing_rig,
                        merged_rig_data,
                        ordered_rig_paths,
                        ordered_rig_datas,
                        properties,
                    )
                else:
                    for key, value in properties.items():
                        runtime.rig[key] = value
                _LOG.debug(
                    "JSON MetaRig base: %s (%s)",
                    runtime.base_rig_name,
                    os.path.basename(runtime.base_rig_path),
                )
                for merge_index, rig_path in enumerate(ordered_rig_paths[1:], start=1):
                    _LOG.debug(
                        "JSON MetaRig part %d: %s",
                        merge_index,
                        os.path.basename(rig_path),
                    )
            else:
                _LOG.error("Failed to create JSON MetaRig armature")

            for meta_name, source in runtime.meta_rig_metadata.get(
                "bone_sources", {}
            ).items():
                runtime.rig_json_by_bone_name.setdefault(meta_name, merged_rig_json)
                source_name = source.get("source_name")
                if source_name:
                    runtime.rig_json_by_bone_name.setdefault(
                        source_name, merged_rig_json
                    )
        elif ordered_components:
            _LOG.warning(
                "base animated component '%s' has no usable JSON rig; no entity rig was created",
                runtime.base_rig_name,
            )
        else:
            _LOG.debug(
                "No entAnimatedComponent rig found in the entity or selected appearances"
            )

        runtime.ordered_rig_paths = tuple(ordered_rig_paths)
        if self.import_animations:
            self._import_animation(runtime)
        return runtime

    def _import_animation_set(self, runtime: EntityRigRuntime, anim_path: str) -> None:
        if not is_live_armature_object(runtime.rig):
            message = (
                f"animation set '{os.path.basename(anim_path)}' could not be imported "
                "because the JSON MetaRig was not created"
            )
            _LOG.warning("%s", message)
            self.warnings.append(message)
            return
        try:
            summary = import_animset_to_metarig(
                anim_path,
                runtime.rig,
                self.entity_name,
                import_tracks=True,
            )
        except Exception as exc:
            message = (
                f"direct animation import failed for "
                f"'{os.path.basename(anim_path)}': {exc}"
            )
            _LOG.warning("%s", message, exc_info=True)
            self.warnings.append(message)
            return
        self.warnings.extend(summary.get("warnings", ()) if summary else ())

    def _import_animation(self, runtime: EntityRigRuntime) -> None:
        if runtime.animation_path:
            self._import_animation_set(runtime, runtime.animation_path)

    def import_facial_animations(
        self, runtime: EntityRigRuntime, face_rig_path: str
    ) -> None:
        """Import the first declared animation set that targets the bound facial rig"""
        face_rig_key = local_path_key(face_rig_path)
        declared = declared_animation_sets(
            self.component_payloads or runtime.ordered_components
        )
        for depot in declared:
            anim_path = self.resources.resolve_export(depot, ".anims.glb")
            if not anim_path:
                continue
            rig_depot = self._animation_rig_key(anim_path)
            rig_path = (
                self.resources.resolve_export(rig_depot, ".rig.json")
                if rig_depot
                else ""
            )
            if rig_path and local_path_key(rig_path) == face_rig_key:
                self._import_animation_set(runtime, anim_path)
                return
        message = (
            "Facial animations were requested, but no exported animation set "
            f"declared by {self.entity_name or 'the entity'} targets the facial rig "
            f"{os.path.basename(face_rig_path)}"
        )
        _LOG.warning("%s", message)
        self.warnings.append(message)
