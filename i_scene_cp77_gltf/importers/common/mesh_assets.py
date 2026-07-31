import hashlib
import json
import os
import re
import traceback
import time
from array import array
from functools import lru_cache

import bpy

from ...addon_identity import get_addon_preferences
from ...materials.blender.cache import material_cache_counters, material_cache_stats

from ..mesh import (
    ensure_collection_material_coverage,
    import_cyberpunk_glb,
)

from .cache import (
    acquire_material_cache,
    release_material_cache,
)
from ...meshes import MESH_COOKED_NAME_SUFFIXES, MeshRepository
from ...blender.transactions import current_import_transaction, track_created_datablock
from .material_appearances import (
    is_source_default_appearance,
    resolve_appearance_materials,
    wrapped_string,
)

from .collections import (
    _link_collection_once,
    _preserve_world_parent,
    _remap_copied_object_references,
    _unlink_collection_once,
)

NAME_MAX_LEN = 256
SUBMESH_PATTERN = re.compile(r"submesh_(\d+)", re.IGNORECASE)
BLENDER_NUMERIC_SUFFIX_PATTERN = re.compile(r"\.\d{3,}$")
APPEARANCE_ASSIGNMENT_VERSION = 4

_SUBMESH_INDEX_CACHE = {}
_JSON_APPS_CACHE = {}


_DATA_COLLECTION_BY_OBJECT_TYPE = {
    "MESH": "meshes",
    "CURVE": "curves",
    "ARMATURE": "armatures",
    "LATTICE": "lattices",
    "LIGHT": "lights",
    "CAMERA": "cameras",
}


def _copy_object_for_transaction(source_obj):
    obj = track_created_datablock("objects", source_obj.copy())
    source_data = getattr(source_obj, "data", None)
    if source_data is None:
        return obj
    copied_data = source_data.copy()
    collection_name = _DATA_COLLECTION_BY_OBJECT_TYPE.get(
        getattr(obj, "type", "")
    )
    if collection_name:
        track_created_datablock(collection_name, copied_data)
    obj.data = copied_data
    return obj


def clear_submesh_index_cache():
    _SUBMESH_INDEX_CACHE.clear()
    _JSON_APPS_CACHE.clear()


def submesh_index_for_object(obj):
    try:
        explicit_index = int(obj.get('cp77_submesh_index', -1))
    except (AttributeError, ReferenceError, TypeError, ValueError):
        explicit_index = -1
    if explicit_index >= 0:
        return explicit_index

    name = getattr(obj, 'name', '')
    cached = _SUBMESH_INDEX_CACHE.get(name)
    if cached is not None:
        return None if cached < 0 else cached
    match = SUBMESH_PATTERN.search(name)
    if match:
        index = int(match.group(1))
        _SUBMESH_INDEX_CACHE[name] = index
        return index
    data = getattr(obj, 'data', None)
    for mat in getattr(data, 'materials', ()) if data is not None else ():
        mat_name = getattr(mat, 'name', '') if mat else ''
        match = SUBMESH_PATTERN.search(mat_name) if mat_name else None
        if match:
            index = int(match.group(1))
            _SUBMESH_INDEX_CACHE[name] = index
            return index
    _SUBMESH_INDEX_CACHE[name] = -1
    return None


def _appearance_name(mesh_appearance):
    if isinstance(mesh_appearance, dict):
        mesh_appearance = mesh_appearance.get('$value', '')
    return str(mesh_appearance or '')


@lru_cache(maxsize=8192)
def _groupname_cached(meshname, appearance):
    groupname = os.path.splitext(os.path.basename(meshname))[0]
    if 'intersection' in meshname:
        groupname = os.path.basename(os.path.dirname(meshname)) + '_' + groupname
    if appearance:
        groupname += '@' + appearance
    return groupname[:NAME_MAX_LEN]


def get_groupname(meshname, meshAppearance):
    return _groupname_cached(meshname, _appearance_name(meshAppearance))


@lru_cache(maxsize=8192)
def _asset_source_key(meshpath):
    return os.path.normcase(os.path.normpath(meshpath)) if meshpath else ''


@lru_cache(maxsize=8192)
def _source_suffix(source_key):
    return '~' + hashlib.sha1(source_key.encode('utf-8')).hexdigest()[:8]


def _hashed_groupname(meshname, meshAppearance, source_key):
    base = get_groupname(meshname, '')
    suffix = _source_suffix(source_key)
    name = base[:NAME_MAX_LEN - len(suffix)] + suffix
    appearance = _appearance_name(meshAppearance)
    if appearance:
        name += '@' + appearance
    return name[:NAME_MAX_LEN]


def _collection_matches_source(collection, source_key):
    if not source_key:
        return True
    stored = collection.get('source_glb', '')
    # An untagged legacy master cannot safely prove source identity. Rebuild it
    # under the hashed name instead of risking a same-basename asset collision.
    return bool(stored) and _asset_source_key(stored) == source_key


def get_group(meshname, meshAppearance, Masters, source_glb=''):
    # Verify source identity to avoid same-name asset collisions.
    source_key = _asset_source_key(source_glb)
    candidates = [get_groupname(meshname, meshAppearance)]
    if source_key:
        candidates.append(_hashed_groupname(meshname, meshAppearance, source_key))
    for groupname in candidates:
        group = Masters.children.get(groupname)
        if group is not None and _collection_matches_source(group, source_key):
            return group, groupname
    if source_key:
        requested_appearance = _appearance_name(meshAppearance)
        for group in Masters.children:
            if not _collection_matches_source(group, source_key):
                continue
            stored_appearance = _appearance_name(
                group.get('appearance', '')
            )
            if requested_appearance:
                if stored_appearance != requested_appearance:
                    continue
            elif stored_appearance not in ('', 'default'):
                continue
            return group, group.name
    return None, candidates[0]




def _armature_bind_signature(armature):
    data = getattr(armature, 'data', None)
    bones = getattr(data, 'bones', None)
    if data is None or bones is None:
        return ''
    payload = []
    try:
        for bone in bones:
            matrix = tuple(
                round(float(component), 8)
                for row in bone.matrix_local
                for component in row
            )
            payload.append((bone.name, bone.parent.name if bone.parent else '', matrix))
    except (AttributeError, ReferenceError, RuntimeError, TypeError, ValueError):
        return ''
    encoded = json.dumps(payload, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
    return hashlib.blake2b(encoded, digest_size=20).hexdigest()




def _redirect_master_armature(collection, source, target):
    redirected = 0
    for obj in tuple(collection.all_objects):
        if obj is source:
            continue
        changed = False
        for modifier in getattr(obj, 'modifiers', ()):
            if getattr(modifier, 'type', None) == 'ARMATURE' and modifier.object is source:
                modifier.object = target
                changed = True
        if getattr(obj, 'parent', None) is source:
            _preserve_world_parent(obj, target)
            changed = True
        redirected += int(changed)
    return redirected


def _deduplicate_master_source_armatures(master_collection, masters):
    """Share source-rest armatures only when complete bind signatures match."""
    imported = [
        obj for obj in tuple(master_collection.all_objects)
        if getattr(obj, 'type', None) == 'ARMATURE'
    ]
    if not imported:
        return []

    existing_by_signature = {}
    for obj in tuple(masters.all_objects):
        if obj in imported or getattr(obj, 'type', None) != 'ARMATURE':
            continue
        signature = str(obj.get('cp77_master_bind_signature', '') or '')
        if signature:
            existing_by_signature.setdefault(signature, obj)

    authoritative = []
    for source in imported:
        signature = _armature_bind_signature(source)
        if not signature:
            authoritative.append(source)
            continue
        source['cp77_master_bind_signature'] = signature
        target = existing_by_signature.get(signature)
        if target is None:
            existing_by_signature[signature] = source
            authoritative.append(source)
            continue

        _redirect_master_armature(master_collection, source, target)
        if master_collection.objects.get(target.name) is not target:
            master_collection.objects.link(target)
        source_data = getattr(source, 'data', None)
        bpy.data.objects.remove(source, do_unlink=True)
        if source_data is not None and getattr(source_data, 'users', 0) == 0:
            try:
                bpy.data.armatures.remove(source_data)
            except (ReferenceError, RuntimeError, TypeError):
                pass
        target['cp77_master_source_armature'] = True
        target['cp77_master_bind_signature'] = signature
        authoritative.append(target)
    unique = []
    seen_ids = set()
    for armature in authoritative:
        key = id(armature)
        if key in seen_ids:
            continue
        seen_ids.add(key)
        unique.append(armature)
    return unique




def _json_apps_for_collection(collection, mesh_key):
    json_apps_raw = collection.get('json_apps')
    if not json_apps_raw:
        print(f'No material json found for - {mesh_key}')
        return None

    cache_key = collection.as_pointer()
    cached = _JSON_APPS_CACHE.get(cache_key)
    if cached is not None and cached[0] == json_apps_raw:
        return cached[1]

    try:
        json_apps = json.loads(json_apps_raw)
    except json.JSONDecodeError:
        print(f'Invalid material json found for - {mesh_key}')
        return None
    if not json_apps:
        print(f'No material json found for - {mesh_key}')
        return json_apps

    _JSON_APPS_CACHE[cache_key] = (json_apps_raw, json_apps)
    return json_apps


def _authored_material_name(material):
    if material is None:
        return ''
    try:
        metadata = material.get('m')
    except (AttributeError, TypeError):
        metadata = None
    if metadata is not None:
        try:
            name = metadata.get('Name')
        except (AttributeError, TypeError):
            name = None
        if name:
            return wrapped_string(name)
    for key in ('sourceMaterialName', 'cp77MaterialName'):
        try:
            name = material.get(key)
        except (AttributeError, TypeError):
            name = None
        if name:
            return wrapped_string(name)
    return ''


def _blender_material_name(material):
    return str(getattr(material, 'name', '') or '')


def _without_blender_numeric_suffix(name):
    return BLENDER_NUMERIC_SUFFIX_PATTERN.sub('', str(name or ''))


def _unique_materials(materials):
    unique = []
    seen = set()
    for material in materials or ():
        if material is None:
            continue
        try:
            key = ('POINTER', material.as_pointer())
        except (AttributeError, TypeError):
            key = ('OBJECT', id(material))
        if key in seen:
            continue
        seen.add(key)
        unique.append(material)
    return unique


def _resolve_matching_material(materials, mat_name):
    expected = wrapped_string(mat_name)
    if not expected:
        return None, 'empty_material_name', ()

    candidates = _unique_materials(materials)
    expected_folded = expected.casefold()
    records = []
    for material in candidates:
        authored = _authored_material_name(material)
        datablock = _blender_material_name(material)
        stripped = _without_blender_numeric_suffix(datablock)
        records.append((
            material,
            authored,
            authored.casefold(),
            datablock,
            datablock.casefold(),
            stripped,
            stripped.casefold(),
        ))

    matchers = (
        ('authored_exact', 1, expected),
        ('authored_casefold', 2, expected_folded),
        ('datablock_exact', 3, expected),
        ('datablock_casefold', 4, expected_folded),
        ('datablock_suffix_exact', 5, expected),
        ('datablock_suffix_casefold', 6, expected_folded),
    )
    for match_kind, field_index, match_value in matchers:
        matches = [record[0] for record in records if record[field_index] == match_value]
        if len(matches) == 1:
            return matches[0], match_kind, ()
        if len(matches) > 1:
            names = tuple(
                _authored_material_name(material)
                or _blender_material_name(material)
                for material in matches
            )
            return None, f'ambiguous_{match_kind}', names
    return None, 'missing_material', tuple(
        record[1] or record[3]
        for record in records
    )


def _reset_polygon_material_indices(obj):
    polygons = getattr(getattr(obj, 'data', None), 'polygons', None)
    if polygons:
        polygons.foreach_set('material_index', array('i', [0]) * len(polygons))


def _clear_material_assignment(obj):
    if obj.type != 'MESH' or not obj.data:
        return
    obj.data.materials.clear()
    _reset_polygon_material_indices(obj)


def _assign_single_material(obj, material):
    obj.data.materials.clear()
    obj.data.materials.append(material)
    _reset_polygon_material_indices(obj)


def _keep_only_material(
        obj,
        mat_name,
        ):
    result = {
        'status': 'not_a_mesh',
        'matchKind': '',
        'expectedMaterial': wrapped_string(mat_name),
        'assignedMaterial': '',
        'assignedBlenderMaterial': '',
        'candidates': (),
    }
    if obj.type != 'MESH' or not obj.data:
        return result
    material, match_kind, candidates = _resolve_matching_material(
        obj.data.materials,
        mat_name,
    )
    result['matchKind'] = match_kind
    result['candidates'] = candidates
    if material is None:
        result['status'] = match_kind
        return result
    _assign_single_material(obj, material)
    result['status'] = 'assigned'
    result['assignedMaterial'] = (
        _authored_material_name(material)
        or _blender_material_name(material)
    )
    result['assignedBlenderMaterial'] = _blender_material_name(material)
    return result


def _source_default_material_name(source_obj):
    try:
        value = source_obj.get('cp77_material_name')
    except (AttributeError, ReferenceError, TypeError):
        value = None
    return wrapped_string(value)


def _object_json_string_list(obj, key):
    try:
        raw = obj.get(key, '')
    except (AttributeError, ReferenceError, TypeError):
        raw = ''
    if not raw:
        return ()
    try:
        values = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return ()
    if not isinstance(values, list):
        return ()
    result = []
    for value in values:
        name = wrapped_string(value)
        if name:
            result.append(name)
    return tuple(result)


def _prepared_material_names(source_obj):
    prepared = _object_json_string_list(source_obj, 'cp77_material_candidates')
    if prepared:
        return prepared
    return tuple(
        _authored_material_name(material) or _blender_material_name(material)
        for material in _unique_materials(
            getattr(getattr(source_obj, 'data', None), 'materials', ())
        )
    )


def _source_default_assignment(
        obj,
        source_obj,
        *,
        status,
        ):
    expected = _source_default_material_name(source_obj)
    if expected:
        result = _keep_only_material(
            obj,
            expected,
        )
        if result['status'] == 'assigned':
            result['status'] = status
            result['matchKind'] = (
                'source_default_' + result.get('matchKind', '')
            )
            return result

    candidates = _unique_materials(obj.data.materials)
    if len(candidates) == 1:
        material = candidates[0]
        _assign_single_material(obj, material)
        return {
            'status': status,
            'matchKind': 'source_default_single_slot',
            'expectedMaterial': expected,
            'assignedMaterial': (
                _authored_material_name(material)
                or _blender_material_name(material)
            ),
            'assignedBlenderMaterial': _blender_material_name(material),
            'candidates': (),
        }

    return {
        'status': (
            'source_default_ambiguous'
            if candidates
            else 'source_default_missing'
        ),
        'matchKind': (
            'source_default_multiple_slots'
            if candidates
            else 'source_default_missing'
        ),
        'expectedMaterial': expected,
        'assignedMaterial': '',
        'assignedBlenderMaterial': '',
        'candidates': tuple(
            _authored_material_name(material)
            or _blender_material_name(material)
            for material in candidates
        ),
    }


def _record_object_material_assignment(
        obj,
        *,
        requested_appearance,
        resolved_appearance,
        submesh_index,
        result,
        ):
    obj['cp77_requested_appearance'] = requested_appearance
    obj['cp77_resolved_appearance'] = resolved_appearance
    obj['cp77_submesh_index'] = (
        int(submesh_index) if submesh_index is not None else -1
    )
    obj['cp77_expected_material'] = result.get('expectedMaterial', '')
    obj['cp77_assigned_material'] = result.get('assignedMaterial', '')
    obj['cp77_assigned_blender_material'] = result.get(
        'assignedBlenderMaterial',
        '',
    )
    obj['cp77_material_assignment_status'] = result.get('status', '')
    obj['cp77_material_match_source'] = result.get('matchKind', '')


def _copy_collection_objects(source_collection, target_collection, appearance, mesh_key, json_apps):
    copied_objects = []
    object_map = {}
    source_armatures = []
    requested_appearance = wrapped_string(appearance)
    (
        resolved_appearance,
        appearance_materials,
        appearance_status,
    ) = resolve_appearance_materials(json_apps, requested_appearance)
    # Sidewalk meshes retain their imported materials.
    preserve_sidewalk_materials = (
        'sidewalk' in wrapped_string(mesh_key).casefold()
    )
    diagnostics = {
        'version': APPEARANCE_ASSIGNMENT_VERSION,
        'mesh': mesh_key,
        'requestedAppearance': requested_appearance,
        'resolvedAppearance': resolved_appearance,
        'appearanceResolution': appearance_status,
        'meshObjects': 0,
        'assigned': 0,
        'sourceDefaultAssigned': 0,
        'materialless': 0,
        'unresolvedAppearance': 0,
        'missingSubmeshIndex': 0,
        'missingSubmeshMapping': 0,
        'emptyMaterialMapping': 0,
        'missingMaterials': 0,
        'requestedMaterialNotPrepared': 0,
        'ambiguousMaterials': 0,
        'multipleSlots': 0,
        'sidewalkPreserved': 0,
        'issues': [],
        'objects': [],
    }
    # Reuse the master's rest armature across appearance variants.
    for source_obj in source_collection.all_objects:
        if getattr(source_obj, 'type', None) == 'ARMATURE':
            source_armatures.append(source_obj.name)
            continue
        obj = _copy_object_for_transaction(source_obj)
        object_map[source_obj] = obj
        copied_objects.append(obj)

        if obj.type == 'MESH':
            diagnostics['meshObjects'] += 1
            # Use authored submesh indices instead of collection order.
            submesh_index = submesh_index_for_object(source_obj)
            if preserve_sidewalk_materials:
                result = {
                    'status': 'sidewalk_materials_preserved',
                    'matchKind': 'policy',
                    'expectedMaterial': '',
                    'assignedMaterial': '',
                    'assignedBlenderMaterial': '',
                }
                diagnostics['sidewalkPreserved'] += 1
            elif not resolved_appearance:
                fallback_status = (
                    'source_default_assigned'
                    if is_source_default_appearance(requested_appearance)
                    else 'missing_appearance_source_default'
                )
                result = _source_default_assignment(
                    obj,
                    source_obj,
                    status=fallback_status,
                )
                if result['status'] == fallback_status:
                    diagnostics['sourceDefaultAssigned'] += 1
                if appearance_status != 'source_default':
                    diagnostics['unresolvedAppearance'] += 1
            elif submesh_index is None:
                result = _source_default_assignment(
                    obj,
                    source_obj,
                    status='missing_submesh_index_source_default',
                )
                if result['status'] == 'missing_submesh_index_source_default':
                    diagnostics['sourceDefaultAssigned'] += 1
                diagnostics['missingSubmeshIndex'] += 1
            elif submesh_index >= len(appearance_materials):
                result = _source_default_assignment(
                    obj,
                    source_obj,
                    status='missing_submesh_mapping_source_default',
                )
                if (
                    result['status']
                    == 'missing_submesh_mapping_source_default'
                ):
                    diagnostics['sourceDefaultAssigned'] += 1
                diagnostics['missingSubmeshMapping'] += 1
            else:
                mat_name = wrapped_string(
                    appearance_materials[submesh_index]
                )
                if not mat_name:
                    result = _source_default_assignment(
                        obj,
                        source_obj,
                        status='empty_material_mapping_source_default',
                    )
                    if (
                        result['status']
                        == 'empty_material_mapping_source_default'
                    ):
                        diagnostics['sourceDefaultAssigned'] += 1
                    diagnostics['emptyMaterialMapping'] += 1
                else:
                    result = _keep_only_material(
                        obj,
                        mat_name,
                    )
                    if result['status'] == 'assigned':
                        diagnostics['assigned'] += 1
                    else:
                        prepared_names = _prepared_material_names(source_obj)
                        prepared_match, _, _ = _resolve_matching_material(
                            getattr(source_obj.data, 'materials', ()),
                            mat_name,
                        )
                        if prepared_match is None:
                            diagnostics['requestedMaterialNotPrepared'] += 1
                        if 'ambiguous_' in result['status']:
                            diagnostics['ambiguousMaterials'] += 1
                        else:
                            diagnostics['missingMaterials'] += 1
                        _clear_material_assignment(obj)
                        result['preparedMaterials'] = prepared_names

            result.setdefault(
                'preparedMaterials',
                _prepared_material_names(source_obj),
            )
            _record_object_material_assignment(
                obj,
                requested_appearance=requested_appearance,
                resolved_appearance=resolved_appearance,
                submesh_index=submesh_index,
                result=result,
            )
            if len(obj.data.materials) > 1:
                diagnostics['multipleSlots'] += 1
            if len(obj.data.materials) == 0:
                diagnostics['materialless'] += 1
            diagnostics['objects'].append({
                'object': obj.name,
                'submeshIndex': (
                    int(submesh_index)
                    if submesh_index is not None
                    else -1
                ),
                'status': result['status'],
                'matchKind': result.get('matchKind', ''),
                'expectedMaterial': result.get('expectedMaterial', ''),
                'assignedMaterial': result.get('assignedMaterial', ''),
                'assignedBlenderMaterial': result.get(
                    'assignedBlenderMaterial',
                    '',
                ),
                'preparedMaterials': list(
                    result.get('preparedMaterials', ())
                ),
                'materialSlots': len(obj.data.materials),
            })
            if result['status'] not in {
                    'assigned',
                    'source_default_assigned',
                    'sidewalk_materials_preserved',
                    }:
                diagnostics['issues'].append({
                    'object': obj.name,
                    'submeshIndex': (
                        int(submesh_index)
                        if submesh_index is not None
                        else -1
                    ),
                    'status': result['status'],
                    'expectedMaterial': result.get(
                        'expectedMaterial',
                        '',
                    ),
                    'candidates': list(result.get('candidates', ())),
                    'preparedMaterials': list(
                        result.get('preparedMaterials', ())
                    ),
                })

        target_collection.objects.link(obj)

    _remap_copied_object_references(copied_objects, object_map)
    if source_armatures:
        target_collection['cp77_source_armatures'] = json.dumps(source_armatures)
        target_collection['cp77_source_armature_policy'] = 'master_reference'
    target_collection['cp77_material_assignment_version'] = (
        APPEARANCE_ASSIGNMENT_VERSION
    )
    target_collection['cp77_requested_appearance'] = requested_appearance
    target_collection['cp77_resolved_appearance'] = resolved_appearance
    target_collection['cp77_appearance_resolution'] = appearance_status
    collection_diagnostics = dict(diagnostics)
    collection_diagnostics.pop('objects', None)
    target_collection['cp77_material_assignment_summary'] = json.dumps(
        collection_diagnostics,
        separators=(',', ':'),
    )
    issue_count = len(diagnostics['issues'])
    if issue_count:
        print(
            f'Appearance assignment warning for '
            f'{mesh_key}@{requested_appearance}: {issue_count} unresolved '
            f'submesh material mapping(s).'
        )
    return diagnostics


def _ensure_appearance_variants(Masters, master_coll, mesh_key, source_key, apps, json_apps):
    for app in apps:
        variant_name = (master_coll.name + '@' + app)[:NAME_MAX_LEN] if app else master_coll.name
        existing = Masters.children.get(variant_name)
        if existing is not None and _collection_matches_source(existing, source_key):
            continue
        if existing is not None:
            continue
        new_coll = track_created_datablock(
            "collections", bpy.data.collections.new(variant_name)
        )
        new_coll['meshpath'] = mesh_key
        new_coll['appearance'] = app
        new_coll['source_glb'] = source_key
        _link_collection_once(Masters, new_coll)
        _copy_collection_objects(master_coll, new_coll, app, mesh_key, json_apps)


def _mesh_appearances(mesh_data):
    apps = []
    seen = set()
    for mesh_app in mesh_data.get('apps', [[]])[0]:
        appearance = _appearance_name(mesh_app)
        if appearance and appearance not in seen:
            seen.add(appearance)
            apps.append(appearance)
    return apps


def _resolved_meshpath(mesh_data):
    if isinstance(mesh_data, dict):
        meshpath = mesh_data.get('meshpath')
        if meshpath:
            return os.path.normpath(meshpath)
    return ''


def _mesh_glb_path(mesh_repository, mesh_key, mesh_data):
    """Resolve an explicit export or depot mesh reference through the active asset index."""
    meshpath = _resolved_meshpath(mesh_data)
    if meshpath:
        asset = mesh_repository.resolve(meshpath)
        if asset is not None:
            return asset.local_path
    asset = mesh_repository.resolve(mesh_key)
    return asset.local_path if asset is not None else ""


def _appearance_requests_by_source(prepared_meshes):
    appearances_by_source = {}
    seen_by_source = {}
    for _mesh_key, mesh_data, _meshpath, source_key in prepared_meshes:
        source_apps = appearances_by_source.setdefault(source_key, [])
        seen = seen_by_source.setdefault(source_key, set())
        for appearance in _mesh_appearances(mesh_data):
            if appearance in seen:
                continue
            seen.add(appearance)
            source_apps.append(appearance)
    return appearances_by_source


def meshes_from_mesheswapps(
        meshes_w_apps, *, asset_index, from_mesh_no=0, to_mesh_no=10000000,
        with_mats=False, Masters=None, generate_overrides=False, mesh_repository=None,
        document_session=None, material_resources=None, transaction=None,
        ):
    if asset_index is None:
        raise ValueError('meshes_from_mesheswapps requires an AssetIndexSnapshot')
    if Masters is None:
        raise ValueError('meshes_from_mesheswapps requires a master collection')
    mesh_repository = mesh_repository or MeshRepository(asset_index)
    transaction = transaction or current_import_transaction()
    failures = []
    prepared_meshes = []
    imported_source_count = 0
    bulk_started = time.perf_counter()
    cache_before = material_cache_counters() if with_mats else None

    material_cache_acquired = acquire_material_cache(with_mats)
    try:
        props = bpy.context.scene.cp77_panel_props
        context = bpy.context
        scene_collection = context.scene.collection

        for index, (mesh_key, mesh_data) in enumerate(meshes_w_apps.items()):
            if index < from_mesh_no or index > to_mesh_no:
                continue
            if not str(mesh_key).casefold().endswith(
                MESH_COOKED_NAME_SUFFIXES
            ):
                continue

            meshpath = _mesh_glb_path(mesh_repository, mesh_key, mesh_data)
            if not meshpath:
                message = f'Mesh export not indexed: {mesh_key}'
                print(message)
                failures.append(message)
                continue

            source_key = _asset_source_key(meshpath)
            prepared_meshes.append(
                (mesh_key, mesh_data, meshpath, source_key)
            )

        appearances_by_source = _appearance_requests_by_source(
            prepared_meshes
        )

        for mesh_key, mesh_data, meshpath, source_key in prepared_meshes:
            # Merge appearances that resolve to the same GLB.
            apps = appearances_by_source[source_key]
            groupname = get_groupname(meshpath, '')
            existing_master = Masters.children.get(groupname)
            if existing_master is not None and not _collection_matches_source(existing_master, source_key):
                # Use a source hash when another asset owns the display name.
                groupname = _hashed_groupname(meshpath, '', source_key)
                existing_master = Masters.children.get(groupname)
                if existing_master is not None and not _collection_matches_source(existing_master, source_key):
                    existing_master = None
            if existing_master is not None:
                # Add missing materials before creating appearance variants.
                if with_mats:
                    coverage = ensure_collection_material_coverage(
                        existing_master,
                        meshpath,
                        apps,
                        remap_depot=props.remap_depot,
                        document_session=document_session,
                        material_resources=material_resources,
                    )
                    failed_materials = coverage.get("failures", ())
                    if failed_materials:
                        failures.append(
                            "Material setup failed for "
                            f"{mesh_key}: {', '.join(failed_materials)}"
                        )
                    unprepared_materials = coverage.get("unprepared", ())
                    if unprepared_materials:
                        failures.append(
                            "Submesh materials were not prepared for "
                            f"{mesh_key}: "
                            + ", ".join(
                                f"{index}:{name}"
                                for index, name in unprepared_materials
                            )
                        )
                json_apps = _json_apps_for_collection(existing_master, mesh_key)
                _ensure_appearance_variants(
                    Masters,
                    existing_master,
                    mesh_key,
                    source_key,
                    apps,
                    json_apps,
                )
                continue
            try:
                imported_results = import_cyberpunk_glb(
                        with_materials=with_mats,
                        remap_depot=props.remap_depot,
                        filepath=meshpath,
                        appearances=apps,
                        scripting=True,
                        generate_overrides=generate_overrides,
                        document_session=document_session,
                        material_resources=material_resources,
                        transaction=transaction,
                        bulk_import=True,
                        )
                imported_source_count += 1
                if not imported_results.ok:
                    failures.extend(
                        f"{mesh_key}: {message}"
                        for message in imported_results.failures
                    )
                    continue
                failures.extend(
                    f"{mesh_key}: {message}"
                    for message in imported_results.warnings
                )

                move_coll = (
                    imported_results[0].get('collection')
                    if len(imported_results) == 1
                    else None
                )
                if move_coll is None:
                    message = (
                        f'Import produced no collection for: {mesh_key}'
                    )
                    print(message)
                    failures.append(message)
                    continue

                if move_coll.name != groupname:
                    move_coll.name = groupname
                move_coll['meshpath'] = mesh_key
                move_coll['appearance'] = 'default'
                move_coll['source_glb'] = source_key
                _unlink_collection_once(scene_collection, move_coll)
                _link_collection_once(Masters, move_coll)
                authoritative_armatures = _deduplicate_master_source_armatures(
                    move_coll,
                    Masters,
                )
                source_armatures = []
                for obj in authoritative_armatures:
                    obj['cp77_master_source_armature'] = True
                    if not obj.get('cp77_master_source_glb'):
                        obj['cp77_master_source_glb'] = source_key
                    sources = []
                    raw_sources = obj.get('cp77_master_source_glbs', '')
                    if raw_sources:
                        try:
                            sources = list(json.loads(raw_sources))
                        except (TypeError, ValueError, json.JSONDecodeError):
                            sources = []
                    if source_key and source_key not in sources:
                        sources.append(source_key)
                    obj['cp77_master_source_glbs'] = json.dumps(sources)
                    source_armatures.append(obj.name)
                if source_armatures:
                    move_coll['cp77_source_armatures'] = json.dumps(source_armatures)
                    move_coll['cp77_source_armature_policy'] = 'authoritative_master'

                json_apps = _json_apps_for_collection(move_coll, mesh_key)
                _ensure_appearance_variants(Masters, move_coll, mesh_key, source_key, apps, json_apps)
            except Exception as error:
                print('failed on ', os.path.basename(meshpath))
                print(traceback.format_exc())
                failures.append(
                    f'Mesh import failed for {mesh_key}: '
                    f'{type(error).__name__}: {error}'
                )
    finally:
        cache_after = (
            material_cache_stats(include_helpers=False)
            if with_mats
            else None
        )
        release_material_cache(material_cache_acquired)
        try:
            verbose = not get_addon_preferences().non_verbose
        except Exception:
            verbose = False
        if verbose and prepared_meshes:
            elapsed = time.perf_counter() - bulk_started
            summary = (
                f"Bulk mesh preparation: {imported_source_count}/"
                f"{len(prepared_meshes)} GLBs in {elapsed:.3f}s"
            )
            if cache_before is not None and cache_after is not None:
                summary += (
                    "; material cache "
                    f"{cache_after['exact_hits'] - cache_before['exact_hits']} exact, "
                    f"{cache_after['prototype_hits'] - cache_before['prototype_hits']} prototype, "
                    f"{cache_after['builds'] - cache_before['builds']} builds, "
                    f"{cache_after['clones'] - cache_before['clones']} clones, "
                    f"{cache_after['entries']} cached entries"
                )
            if failures:
                summary += f"; {len(tuple(dict.fromkeys(failures)))} warning(s)"
            print(summary)
    return tuple(dict.fromkeys(failures))
