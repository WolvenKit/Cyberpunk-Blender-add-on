import hashlib
import json
import os
import re
import traceback
from array import array
from functools import lru_cache

import bpy

from .import_with_materials import CP77GLBimport
from ..jsontool import JSONTool
from ..main.setup import bcolors, clear_material_cache

NAME_MAX_LEN = 256
SUBMESH_PATTERN = re.compile(r"submesh_(\d+)", re.IGNORECASE)

_SUBMESH_INDEX_CACHE = {}
_JSON_APPS_CACHE = {}


def clear_submesh_index_cache():
    _SUBMESH_INDEX_CACHE.clear()


def submesh_index_for_object(obj):
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
        return mesh_appearance.get('$value', '')
    return mesh_appearance or ''


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
    # Collections created before source stamping carry no identity; accept them for continuity.
    return not stored or stored == source_key


def get_group(meshname, meshAppearance, Masters, source_glb=''):
    # The master collection is the mesh asset cache key: same-named assets from different
    # depot paths must not alias, so lookups verify the stored source identity.
    source_key = _asset_source_key(source_glb)
    candidates = [get_groupname(meshname, meshAppearance)]
    if source_key:
        candidates.append(_hashed_groupname(meshname, meshAppearance, source_key))
    for groupname in candidates:
        group = Masters.children.get(groupname)
        if group is not None and _collection_matches_source(group, source_key):
            return group, groupname
    return None, candidates[0]


def add_to_list(basename, meshes, out):
    mesh = meshes.get(basename)
    if not mesh:
        return

    entry = out.setdefault(basename, {'apps': [[]], 'sectors': []})
    apps = entry['apps'][0]
    for appearance in mesh.get('appearances', []):
        if appearance not in apps:
            apps.append(appearance)

    sector = mesh.get('sector')
    if sector and sector not in entry['sectors']:
        entry['sectors'].append(sector)
    meshpath = mesh.get('meshpath')
    if meshpath and not entry.get('meshpath'):
        entry['meshpath'] = meshpath


def _collection_import_snapshot():
    return set(bpy.data.collections), set(bpy.data.objects)


def _imported_collection_from_diff(before_collections, before_objects, expected_name=''):
    new_collections = [collection for collection in bpy.data.collections if collection not in before_collections]
    if not new_collections:
        return None

    if expected_name:
        exact = next((collection for collection in new_collections if collection.name == expected_name), None)
        if exact is not None:
            return exact

    new_objects = {obj for obj in bpy.data.objects if obj not in before_objects}
    object_collections = []
    if new_objects:
        for collection in new_collections:
            try:
                collection_objects = set(collection.all_objects)
            except ReferenceError:
                continue
            if collection_objects.intersection(new_objects):
                object_collections.append(collection)

    candidates = object_collections or new_collections
    nested_children = {child for collection in new_collections for child in collection.children}
    roots = [collection for collection in candidates if collection not in nested_children]
    if len(roots) == 1:
        return roots[0]
    if len(candidates) == 1:
        return candidates[0]
    return max(candidates, key=lambda collection: len(collection.all_objects))


def _link_collection_once(parent, child):
    if parent.children.get(child.name) is not child:
        parent.children.link(child)


def _unlink_collection_once(parent, child):
    if parent.children.get(child.name) is child:
        parent.children.unlink(child)


def _remap_copied_object_references(copied_objects, object_map):
    """Remap parent, modifier .object, and constraint .target references between copied
    objects. Other reference kinds (geometry-node inputs, drivers, particle systems,
    custom-property datablocks) are not covered and need dedicated handling if they appear."""
    for obj in copied_objects:
        parent = obj.parent
        if parent in object_map:
            world = obj.matrix_world.copy()
            obj.parent = object_map[parent]
            obj.matrix_world = world

        for modifier in obj.modifiers:
            target = getattr(modifier, 'object', None)
            if target in object_map:
                modifier.object = object_map[target]

        for constraint in obj.constraints:
            target = getattr(constraint, 'target', None)
            if target in object_map:
                constraint.target = object_map[target]


def _json_apps_for_collection(collection, mesh_key):
    json_apps_raw = collection.get('json_apps')
    if not json_apps_raw:
        print(f'{bcolors.FAIL}No material json found for - {mesh_key}{bcolors.ENDC}')
        return None

    cache_key = collection.as_pointer()
    cached = _JSON_APPS_CACHE.get(cache_key)
    if cached is not None and cached[0] == json_apps_raw:
        return cached[1]

    try:
        json_apps = json.loads(json_apps_raw)
    except json.JSONDecodeError:
        print(f'{bcolors.FAIL}Invalid material json found for - {mesh_key}{bcolors.ENDC}')
        return None
    if not json_apps:
        print(f'{bcolors.FAIL}No material json found for - {mesh_key}{bcolors.ENDC}')
        return json_apps

    _JSON_APPS_CACHE[cache_key] = (json_apps_raw, json_apps)
    return json_apps


def _matching_material(materials, mat_name):
    material = materials.get(mat_name)
    if material is not None:
        return material
    mat_base = mat_name.split('.')[0]
    for material in materials:
        if material and material.name.split('.')[0] == mat_base:
            return material
    return None


def _keep_only_material(obj, mat_name):
    if obj.type != 'MESH' or not obj.data or not obj.data.materials or not mat_name:
        return
    material = _matching_material(obj.data.materials, mat_name)
    if material is None:
        return
    obj.data.materials.clear()
    obj.data.materials.append(material)
    polygons = obj.data.polygons
    if polygons:
        polygons.foreach_set('material_index', array('i', [0]) * len(polygons))


def _copy_collection_objects(source_collection, target_collection, appearance, mesh_key, json_apps):
    copied_objects = []
    object_map = {}
    appearance_materials = json_apps.get(appearance, []) if json_apps else []
    # Sidewalk meshes keep their imported materials; the appearance material lists do not apply to them.
    assign_materials = bool(appearance_materials) and 'sidewalk' not in mesh_key
    # all_objects: entity instancing copies nested collection contents, so variants must too.
    for source_obj in source_collection.all_objects:
        obj = source_obj.copy()
        object_map[source_obj] = obj
        copied_objects.append(obj)
        if source_obj.data:
            obj.data = source_obj.data.copy()

        if obj.type == 'MESH' and assign_materials:
            # Material lists are ordered by submesh index. Enumeration order is unreliable:
            # collections are name-sorted and skinned imports include an Armature object.
            submesh_index = submesh_index_for_object(source_obj)
            if submesh_index is not None and submesh_index < len(appearance_materials):
                mat_name = appearance_materials[submesh_index]
                if mat_name and len(mat_name) < 63:
                    _keep_only_material(obj, mat_name)

        target_collection.objects.link(obj)

    _remap_copied_object_references(copied_objects, object_map)


def _ensure_appearance_variants(Masters, master_coll, mesh_key, source_key, apps, json_apps):
    for app in apps:
        variant_name = (master_coll.name + '@' + app)[:NAME_MAX_LEN] if app else master_coll.name
        existing = Masters.children.get(variant_name)
        if existing is not None and _collection_matches_source(existing, source_key):
            continue
        if existing is not None:
            continue
        new_coll = bpy.data.collections.new(variant_name)
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


def _fallback_meshpath(path, mesh_key):
    if mesh_key.endswith('physicalscene') or mesh_key.endswith('w2mesh'):
        return os.path.join(path, mesh_key + '.glb').replace('\\', os.sep)
    if mesh_key.endswith('mesh'):
        return os.path.join(path, os.path.splitext(mesh_key)[0] + '.glb').replace('\\', os.sep)
    return ''


def _mesh_glb_path(path, mesh_key, mesh_data, glbs):
    meshpath = _resolved_meshpath(mesh_data)
    if meshpath:
        return meshpath
    if isinstance(glbs, dict):
        meshpath = _resolved_meshpath(glbs.get(mesh_key))
        if meshpath:
            return meshpath
    return _fallback_meshpath(path, mesh_key)


def meshes_from_mesheswapps(
        meshes_w_apps, path='', from_mesh_no=0, to_mesh_no=10000000, with_mats=False, glbs=None, mesh_jsons=None,
        Masters=None, generate_overrides=False,
        ):
    initiated_cache = False
    if not JSONTool._use_cache:
        clear_material_cache()
        JSONTool.start_caching()
        initiated_cache = True

    try:
        props = bpy.context.scene.cp77_panel_props
        context = bpy.context
        scene_collection = context.scene.collection

        for index, mesh_key in enumerate(meshes_w_apps):
            if index < from_mesh_no or index > to_mesh_no:
                continue
            if not (mesh_key.endswith('mesh') or mesh_key.endswith('physicalscene') or mesh_key.endswith('w2mesh')):
                continue

            mesh_data = meshes_w_apps[mesh_key]
            apps = _mesh_appearances(mesh_data)
            meshpath = _mesh_glb_path(path, mesh_key, mesh_data, glbs)

            source_key = _asset_source_key(meshpath)
            groupname = get_groupname(meshpath, '')
            existing_master = Masters.children.get(groupname)
            if existing_master is not None and not _collection_matches_source(existing_master, source_key):
                # A different asset already owns this display name; this asset gets a
                # source-hashed name so the two never alias.
                groupname = _hashed_groupname(meshpath, '', source_key)
                existing_master = Masters.children.get(groupname)
                if existing_master is not None and not _collection_matches_source(existing_master, source_key):
                    existing_master = None
            if existing_master is not None:
                # A previous import created this master; still create any appearance
                # variants that this import needs but the earlier one did not.
                json_apps = _json_apps_for_collection(existing_master, mesh_key)
                _ensure_appearance_variants(Masters, existing_master, mesh_key, source_key, apps, json_apps)
                continue
            if not os.path.exists(meshpath):
                print('Mesh ', meshpath, ' does not exist')
                continue

            try:
                before_collections, before_objects = _collection_import_snapshot()
                CP77GLBimport(
                        with_materials=with_mats,
                        remap_depot=props.remap_depot,
                        filepath=meshpath,
                        appearances=apps,
                        scripting=True,
                        generate_overrides=generate_overrides,
                        )

                move_coll = _imported_collection_from_diff(before_collections, before_objects, groupname)
                if move_coll is None:
                    print(f'{bcolors.FAIL}Import produced no collection for - {mesh_key}{bcolors.ENDC}')
                    continue

                if move_coll.name != groupname:
                    move_coll.name = groupname
                move_coll['meshpath'] = mesh_key
                move_coll['appearance'] = 'default'
                move_coll['source_glb'] = source_key
                _unlink_collection_once(scene_collection, move_coll)
                _link_collection_once(Masters, move_coll)

                json_apps = _json_apps_for_collection(move_coll, mesh_key)
                _ensure_appearance_variants(Masters, move_coll, mesh_key, source_key, apps, json_apps)
            except Exception:
                print('failed on ', os.path.basename(meshpath))
                print(traceback.format_exc())
    finally:
        if initiated_cache:
            JSONTool.stop_caching()
            clear_material_cache()
