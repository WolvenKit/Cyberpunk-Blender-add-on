import json
import os
import traceback

import bpy

from ..main.setup import bcolors
from .import_with_materials import CP77GLBimport

NAME_MAX_LEN = 256


def _appearance_name(mesh_appearance):
    if isinstance(mesh_appearance, dict):
        return mesh_appearance.get('$value', '')
    return mesh_appearance or ''


def get_groupname(meshname, meshAppearance):
    groupname = os.path.splitext(os.path.basename(meshname))[0]
    if 'intersection' in meshname:
        groupname = os.path.basename(os.path.dirname(meshname)) + '_' + groupname
    appearance = _appearance_name(meshAppearance)
    if appearance:
        groupname += '@' + appearance
    return groupname[:NAME_MAX_LEN]


def get_group(meshname, meshAppearance, Masters):
    appearance = _appearance_name(meshAppearance)
    for group in Masters.children:
        if group.get('meshpath') == meshname and group.get('appearance') == appearance:
            return group, group.name

    groupname = get_groupname(meshname, appearance)
    return Masters.children.get(groupname), groupname


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
    try:
        json_apps = json.loads(json_apps_raw)
    except json.JSONDecodeError:
        print(f'{bcolors.FAIL}Invalid material json found for - {mesh_key}{bcolors.ENDC}')
        return None
    if not json_apps:
        print(f'{bcolors.FAIL}No material json found for - {mesh_key}{bcolors.ENDC}')
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
    for polygon in obj.data.polygons:
        polygon.material_index = 0


def _copy_collection_objects(source_collection, target_collection, appearance, mesh_key, json_apps):
    copied_objects = []
    object_map = {}
    appearance_materials = json_apps.get(appearance, []) if json_apps else []
    for index, source_obj in enumerate(source_collection.objects):
        obj = source_obj.copy()
        object_map[source_obj] = obj
        copied_objects.append(obj)
        if source_obj.data:
            obj.data = source_obj.data.copy()

        if obj.type == 'MESH' and index < len(appearance_materials):
            mat_name = appearance_materials[index]
            if 'sidewalk' in mesh_key:
                mat_name = 'sidewalksidewalksidewalksidewalksidewalksidewalksidewalksidewalksidewalk'
            if len(mat_name) < 63:
                _keep_only_material(obj, mat_name)

        target_collection.objects.link(obj)

    _remap_copied_object_references(copied_objects, object_map)


def _mesh_appearances(mesh_data):
    apps = []
    for mesh_app in mesh_data.get('apps', [[]])[0]:
        appearance = _appearance_name(mesh_app)
        if appearance and appearance not in apps:
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


def meshes_from_mesheswapps(meshes_w_apps, path='', from_mesh_no=0, to_mesh_no=10000000, with_mats=False, glbs=None, mesh_jsons=None, Masters=None, generate_overrides=False):
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
        if mesh_key.endswith('physicalscene') or mesh_key.endswith('w2mesh'):
            print('not a standard mesh')
        print(meshpath)

        groupname = get_groupname(meshpath, '')
        if Masters.children.get(groupname) is not None:
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
            _unlink_collection_once(scene_collection, move_coll)
            _link_collection_once(Masters, move_coll)

            json_apps = _json_apps_for_collection(move_coll, mesh_key)
            for app in apps:
                new_coll = bpy.data.collections.new(groupname + '@' + app)
                new_coll['meshpath'] = mesh_key
                new_coll['appearance'] = app
                _link_collection_once(Masters, new_coll)
                _copy_collection_objects(move_coll, new_coll, app, mesh_key, json_apps)
        except Exception:
            print('failed on ', os.path.basename(meshpath))
            print(traceback.format_exc())
