from __future__ import annotations
from ...blender.transactions import track_created_datablock

import os
import traceback
from dataclasses import dataclass, field
from typing import Any

import bpy
from bpy.app.handlers import persistent

from ...addon_identity import get_addon_preferences
from ..animation import import_anims_glb_to_armature
from ..rig import (
    create_armature_from_data,
    create_armature_from_rig_data,
    create_armature_from_rig_files,
    merge_rig_datas,
    merged_rig_document,
    rig_data_to_root_chunk,
)
from ..common.entity_data import component_name
from ..common.paths import depot_path_value, depot_to_local_path, norm_path_key
from .transforms import (
    cache_armature_bones,
    is_live_armature_object,
    rig_bone_index_for,
)

ARMATURE_TYPE = "ARMATURE"
_RIG_ARMATURE_OBJECT_CACHE: dict[str, Any] = {}
_RIG_ARMATURE_PROTOTYPE_CACHE: dict[str, Any] = {}
_RIG_ARMATURE_PROTOTYPE_LIMIT = 32
_RIG_PROTOTYPE_MARKER = 'cp77_entity_rig_prototype'


def _remove_armature_prototype(prototype) -> None:
    if prototype is None:
        return
    try:
        data = prototype.data
    except (AttributeError, ReferenceError, RuntimeError):
        return
    try:
        bpy.data.objects.remove(prototype, do_unlink=True)
    except (AttributeError, ReferenceError, RuntimeError):
        pass
    if data is None:
        return
    try:
        unused = data.users == 0
    except (AttributeError, ReferenceError, RuntimeError):
        return
    if unused:
        try:
            bpy.data.armatures.remove(data)
        except (AttributeError, ReferenceError, RuntimeError):
            pass


def clear_rig_prototype_cache() -> None:
    for prototype in tuple(_RIG_ARMATURE_PROTOTYPE_CACHE.values()):
        _remove_armature_prototype(prototype)
    _RIG_ARMATURE_PROTOTYPE_CACHE.clear()


def clear_rig_caches(*, clear_prototypes: bool = False) -> None:
    """Clear per-import rig objects and optionally reusable armature prototypes."""
    _RIG_ARMATURE_OBJECT_CACHE.clear()
    if clear_prototypes:
        clear_rig_prototype_cache()


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
    for key in ('ent', 'componentName', 'animset', 'animation_source_rig_json', _RIG_PROTOTYPE_MARKER):
        try:
            if key in armature:
                del armature[key]
        except (KeyError, TypeError):
            pass


def _store_armature_prototype(cache_key: str, armature) -> None:
    if not is_live_armature_object(armature) or getattr(armature, 'data', None) is None:
        return
    try:
        prototype = track_created_datablock("objects", armature.copy())
        prototype.data = track_created_datablock("armatures", armature.data.copy())
        prototype.name = '__CP77_ENTITY_RIG_PROTOTYPE__'
        prototype.data.name = '__CP77_ENTITY_RIG_PROTOTYPE_DATA__'
        prototype.hide_viewport = True
        prototype.hide_render = True
        if getattr(prototype, 'animation_data', None) is not None:
            prototype.animation_data_clear()
        _clear_instance_rig_metadata(prototype)
        prototype[_RIG_PROTOTYPE_MARKER] = True
    except Exception:
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
    if not is_live_armature_object(prototype) or getattr(prototype, 'data', None) is None:
        if prototype is not None:
            _RIG_ARMATURE_PROTOTYPE_CACHE.pop(cache_key, None)
        return None
    clone = None
    try:
        clone = track_created_datablock("objects", prototype.copy())
        clone.data = track_created_datablock("armatures", prototype.data.copy())
        clone.name = object_name
        clone.data.name = f'{object_name}_Data'
        clone.hide_viewport = False
        clone.hide_render = False
        if getattr(clone, 'animation_data', None) is not None:
            clone.animation_data_clear()
        _clear_instance_rig_metadata(clone)

        rig_collection = bpy.data.collections.get(object_name)
        if rig_collection is None:
            rig_collection = track_created_datablock("collections", bpy.data.collections.new(object_name))
            bpy.context.scene.collection.children.link(rig_collection)
        rig_collection.objects.link(clone)
        try:
            clone.hide_set(False)
        except RuntimeError:
            pass
        cache_armature_bones(clone)
        return clone
    except Exception:
        if clone is not None:
            try:
                bpy.data.objects.remove(clone, do_unlink=True)
            except (ReferenceError, RuntimeError):
                pass
        return None


def _rig_prototype_key(source_key: str, source_paths) -> str:
    """Include file state so reusable prototypes cannot outlive changed rig exports."""
    signatures = []
    for path in source_paths or ():
        normalized = norm_path_key(path)
        try:
            stat = os.stat(path)
            signatures.append(f'{normalized}:{stat.st_mtime_ns}:{stat.st_size}')
        except OSError:
            signatures.append(f'{normalized}:missing')
    return source_key + '|files=' + ';'.join(signatures)



def import_animset_to_metarig(anim_path, rig, rig_path='', ent_name='', import_tracks=True):
    if not anim_path:
        return False
    if not is_live_armature_object(rig):
        raise RuntimeError('A live JSON MetaRig is required before importing an animation set')

    bpy.context.scene.render.fps = 30
    cp77_addon_prefs = get_addon_preferences()
    summary = import_anims_glb_to_armature(
            anim_path,
            rig,
            import_tracks=import_tracks,
            verbose=not cp77_addon_prefs.non_verbose,
            )
    cache_armature_bones(rig)
    rig['animset'] = anim_path
    if rig_path:
        rig['animation_source_rig_json'] = rig_path
    if ent_name:
        rig['ent'] = ent_name + '.ent.json'
    print(
            f"imported {summary['animation_count']} animations directly onto "
            f"JSON MetaRig: {rig.name}"
            )
    return summary


def _armature_matches_rig_source(armature, rig_source_key):
    if armature.get('animation_only', False):
        return False
    stored = armature.get('source_rig_file') or armature.get('rig') or ''
    if not stored and getattr(armature, 'data', None) is not None:
        stored = armature.data.get('source_rig_file') or ''
    return bool(stored) and norm_path_key(str(stored)) == rig_source_key


def ensure_armature_from_rig_json(rig_json_path, component_name_value='', ent_name='', rig_repository=None):
    if not rig_json_path:
        return None
    target = norm_path_key(rig_json_path)
    existing = _RIG_ARMATURE_OBJECT_CACHE.get(target)
    if is_live_armature_object(existing):
        cache_armature_bones(existing)
        return existing
    if existing is not None:
        _RIG_ARMATURE_OBJECT_CACHE.pop(target, None)

    expected_name = os.path.basename(rig_json_path).replace('.rig.json', '')
    prototype_key = _rig_prototype_key(target, (rig_json_path,))
    prototype_clone = _clone_armature_prototype(prototype_key, expected_name)
    if prototype_clone is not None:
        _RIG_ARMATURE_OBJECT_CACHE[target] = prototype_clone
        prototype_clone['rig'] = rig_json_path
        prototype_clone['source_rig_file'] = rig_json_path
        if component_name_value:
            prototype_clone['componentName'] = component_name_value
        if ent_name:
            prototype_clone['ent'] = ent_name + '.ent.json'
        return prototype_clone
    direct = bpy.data.objects.get(expected_name)
    if getattr(direct, 'type', None) == ARMATURE_TYPE and _armature_matches_rig_source(direct, target):
        cache_armature_bones(direct)
        _RIG_ARMATURE_OBJECT_CACHE[target] = direct
        return direct

    created = create_armature_from_data(rig_json_path, 'A-Pose', False, rig_repository=rig_repository)
    armature = created if getattr(created, 'type', None) == ARMATURE_TYPE else None

    if armature is not None:
        cache_armature_bones(armature)
        _RIG_ARMATURE_OBJECT_CACHE[target] = armature
        armature['rig'] = rig_json_path
        armature['source_rig_file'] = rig_json_path
        if component_name_value:
            armature['componentName'] = component_name_value
        if ent_name:
            armature['ent'] = ent_name + '.ent.json'
        _store_armature_prototype(prototype_key, armature)
    return armature


def ensure_armature_from_rig_jsons(rig_json_paths, ent_name='', merged_rig_data=None, rig_repository=None):
    ordered_paths = []
    ordered_keys = []
    seen_keys = set()
    for path in rig_json_paths or ():
        if not path:
            continue
        key = norm_path_key(path)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        ordered_paths.append(path)
        ordered_keys.append(key)
    if not ordered_paths:
        return None
    merged_key = 'metarig:' + ';'.join(ordered_keys)
    existing = _RIG_ARMATURE_OBJECT_CACHE.get(merged_key)
    if is_live_armature_object(existing):
        cache_armature_bones(existing)
        return existing
    if existing is not None:
        _RIG_ARMATURE_OBJECT_CACHE.pop(merged_key, None)

    merged_name = (ent_name + '_rig') if ent_name else 'merged_rig'
    prototype_key = _rig_prototype_key(merged_key, ordered_paths)
    prototype_clone = _clone_armature_prototype(prototype_key, merged_name)
    if prototype_clone is not None:
        _RIG_ARMATURE_OBJECT_CACHE[merged_key] = prototype_clone
        prototype_clone['rig'] = ordered_paths[0]
        prototype_clone['source_rig_file'] = merged_key
        prototype_clone['merged_rigs'] = list(ordered_paths)
        if ent_name:
            prototype_clone['ent'] = ent_name + '.ent.json'
        return prototype_clone
    direct = bpy.data.objects.get(merged_name)
    if getattr(direct, 'type', None) == ARMATURE_TYPE and _armature_matches_rig_source(direct, merged_key):
        cache_armature_bones(direct)
        _RIG_ARMATURE_OBJECT_CACHE[merged_key] = direct
        return direct

    if merged_rig_data is not None:
        source_document = merged_rig_document(
            ordered_paths,
            merged_rig_data,
            merged_key,
        )
        created = create_armature_from_rig_data(
            merged_rig_data,
            'A-Pose',
            False,
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
    armature = created if getattr(created, 'type', None) == ARMATURE_TYPE else None
    if armature is not None:
        cache_armature_bones(armature)
        _RIG_ARMATURE_OBJECT_CACHE[merged_key] = armature
        armature['rig'] = ordered_paths[0]
        armature['source_rig_file'] = merged_key
        armature['merged_rigs'] = list(ordered_paths)
        if ent_name:
            armature['ent'] = ent_name + '.ent.json'
        _store_armature_prototype(prototype_key, armature)
    return armature


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
    base_rig_name: str = ''
    base_rig_path: str = ''
    animation_path: str = ''
    animation_source_rig_path: str = ''
    meta_rig_metadata: dict[str, Any] = field(default_factory=dict)


class EntityRigService:
    """Build the JSON MetaRig and resolve its animation target for one import."""

    def __init__(
        self,
        *,
        resources: Any,
        source_root: str,
        entity_name: str,
        animation_files: tuple[str, ...] | list[str],
        import_animations: bool,
        warnings: list[str],
    ) -> None:
        self.resources = resources
        self.source_root = source_root
        self.entity_name = entity_name
        self.animation_files = tuple(animation_files or ())
        self.import_animations = bool(import_animations)
        self.warnings = warnings

    def build(self, rig_plan: Any) -> EntityRigRuntime:
        ordered_components = tuple(rig_plan.ordered_components)
        runtime = EntityRigRuntime(ordered_components=ordered_components)

        deformation_authorities = list(rig_plan.deformation_authorities)
        if deformation_authorities:
            print('JSON MetaRig deformation base authority: ' + ', '.join(deformation_authorities))
        print(
            'JSON MetaRig component order: ' + ' -> '.join(
                component_name(component, '<unnamed>') for component in ordered_components
            )
        )

        ordered_rig_names: list[str] = []
        ordered_rig_paths: list[str] = []
        ordered_rig_datas: list[Any] = []

        for component in ordered_components:
            rig_name = component_name(component)
            rig_depot = depot_path_value(component, 'rig')
            rig_json_path = self.resources.resolve_rig(rig_depot)
            rig_data = self.resources.load_rig(rig_json_path) if rig_json_path else None
            rig_json = (
                rig_data.source_document.get("Data", {}).get("RootChunk")
                if rig_data is not None and isinstance(rig_data.source_document, dict)
                else None
            )
            if not rig_name or not rig_json_path or rig_json is None or rig_data is None:
                print(f"unable to load JSON rig for animated component '{rig_name or '<unnamed>'}': {rig_depot}")
                continue
            if rig_name not in runtime.rig_json_path_by_component_name:
                runtime.rig_json_path_by_component_name[rig_name] = rig_json_path
                runtime.rig_json_by_component_name[rig_name] = rig_json
                ordered_rig_names.append(rig_name)
            ordered_rig_paths.append(rig_json_path)
            ordered_rig_datas.append(rig_data)

        base_component = ordered_components[0] if ordered_components else None
        runtime.base_rig_name = component_name(base_component) if base_component else ''
        runtime.base_rig_path = runtime.rig_json_path_by_component_name.get(runtime.base_rig_name, '')

        animation_source_component = None
        if self.import_animations:
            for component in ordered_components:
                gameplay_anims = component.get('animations', {}).get('gameplay')
                if not gameplay_anims:
                    continue
                try:
                    anim_depot = gameplay_anims[0]['animSet']['DepotPath']['$value']
                except (KeyError, IndexError, TypeError):
                    continue
                runtime.animation_path = self.resources.resolve_export(
                    anim_depot,
                    '.anims.glb',
                ) or ''
                if runtime.animation_path:
                    animation_source_component = component
                    break

            if not runtime.animation_path and base_component is not None:
                base_rig_depot = depot_path_value(base_component, 'rig')
                base_rig_key = norm_path_key(
                    depot_to_local_path(self.source_root, base_rig_depot)
                )
                for anim_path in self.animation_files:
                    anim_json_path = self.resources.resolve_export(
                        anim_path,
                        '.anims.json',
                    )
                    if not anim_json_path:
                        continue
                    anim_json = self.resources.load_json(anim_json_path)
                    anim_rig_depot = (
                        anim_json.get('Data', {})
                        .get('RootChunk', {})
                        .get('rig', {})
                        .get('DepotPath', {})
                        .get('$value')
                        if anim_json is not None else ''
                    )
                    if (
                        anim_rig_depot
                        and norm_path_key(
                            depot_to_local_path(
                                self.source_root,
                                anim_rig_depot,
                            )
                        ) == base_rig_key
                    ):
                        runtime.animation_path = anim_path
                        animation_source_component = base_component
                        break

            if runtime.animation_path:
                source_rig_name = (
                    component_name(animation_source_component)
                    if animation_source_component is not None
                    else runtime.base_rig_name
                )
                runtime.animation_source_rig_path = (
                    runtime.rig_json_path_by_component_name.get(
                        source_rig_name,
                        runtime.base_rig_path,
                    )
                )
            else:
                print(
                    'no animation GLB found for the ordered animated '
                    'components'
                )

        if ordered_rig_datas and runtime.base_rig_path:
            merged_rig_data, runtime.meta_rig_metadata = merge_rig_datas(
                ordered_rig_datas,
                (self.entity_name + '_rig') if self.entity_name else 'merged_rig',
                return_metadata=True,
            )
            merged_rig_json = rig_data_to_root_chunk(merged_rig_data)
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
                runtime.rig['base_rig_component'] = runtime.base_rig_name
                runtime.rig['base_rig_json'] = runtime.base_rig_path
                runtime.rig['rig_merge_order'] = list(ordered_rig_paths)
                runtime.rig['meta_rig_bone_count'] = len(merged_rig_data.bone_names)
                print(
                    f"JSON MetaRig base: {runtime.base_rig_name} "
                    f"({os.path.basename(runtime.base_rig_path)})"
                )
                for merge_index, rig_path in enumerate(ordered_rig_paths[1:], start=1):
                    print(f"JSON MetaRig part {merge_index}: {os.path.basename(rig_path)}")
            else:
                print('failed to create the JSON MetaRig armature')

            for meta_name, source in runtime.meta_rig_metadata.get('bone_sources', {}).items():
                runtime.rig_json_by_bone_name.setdefault(meta_name, merged_rig_json)
                source_name = source.get('source_name')
                if source_name:
                    runtime.rig_json_by_bone_name.setdefault(source_name, merged_rig_json)
        elif ordered_components:
            print(
                f"base animated component '{runtime.base_rig_name}' has no usable JSON rig; "
                "no entity rig was created"
            )
        else:
            print('no entAnimatedComponent rig found in the entity or selected appearances')

        runtime.ordered_rig_paths = tuple(ordered_rig_paths)
        if self.import_animations:
            self._import_animation(runtime)
        return runtime

    def _import_animation(self, runtime: EntityRigRuntime) -> None:
        if not runtime.animation_path:
            return
        if not is_live_armature_object(runtime.rig):
            message = (
                f"animation set '{os.path.basename(runtime.animation_path)}' could not be imported "
                "because the JSON MetaRig was not created"
            )
            print(message)
            self.warnings.append(message)
            return
        try:
            import_animset_to_metarig(
                runtime.animation_path,
                runtime.rig,
                runtime.animation_source_rig_path,
                self.entity_name,
                import_tracks=True,
            )
        except Exception as exc:
            message = (
                f"direct animation import failed for "
                f"'{os.path.basename(runtime.animation_path)}': {exc}"
            )
            print(message)
            print(traceback.format_exc())
            self.warnings.append(message)
