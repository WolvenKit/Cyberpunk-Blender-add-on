import json
import os
import traceback

import bpy

from ..main.setup import bcolors
from .import_with_materials import CP77GLBimport

NAME_MAX_LEN = 256


def _appearance_name(meshAppearance):
    if isinstance(meshAppearance, dict):
        return meshAppearance.get('$value', '')
    return meshAppearance or ''


def get_groupname(meshname, meshAppearance):
    groupname = os.path.splitext(os.path.basename(meshname))[0]
    if 'intersection' in meshname:
        groupname = os.path.basename(os.path.dirname(meshname)) + '_' + groupname
    appearance = _appearance_name(meshAppearance)
    if appearance:
        groupname += '@' + appearance
    return groupname[:NAME_MAX_LEN]


def get_group(meshname, meshAppearance, Masters):
    groupname = get_groupname(meshname, meshAppearance)
    group = Masters.children.get(groupname)
    if group:
        return group, groupname

    appearance = _appearance_name(meshAppearance)
    for candidate in Masters.children:
        if candidate.get('meshpath') == meshname and candidate.get('appearance') == appearance:
            return candidate, candidate.name
    return None, groupname


def _dedupe_key(value):
    if isinstance(value, dict):
        if '$value' in value:
            return ('cname', value.get('$value'))
        try:
            return ('dict', json.dumps(value, sort_keys=True, separators=(',', ':'), default=str))
        except TypeError:
            return ('dict', repr(value))
    if isinstance(value, (list, tuple)):
        return tuple(_dedupe_key(item) for item in value)
    try:
        hash(value)
    except TypeError:
        return repr(value)
    return value


def add_to_list(basename, meshes, target):
    mesh = meshes[basename]
    entry = target.setdefault(basename, {'apps': [], 'sectors': []})

    seen_apps = {_dedupe_key(app) for app in entry['apps']}
    for app in mesh.get('appearances', []):
        key = _dedupe_key(app)
        if key not in seen_apps:
            seen_apps.add(key)
            entry['apps'].append(app)

    sector = mesh.get('sector')
    sector_key = _dedupe_key(sector)
    seen_sectors = {_dedupe_key(existing) for existing in entry['sectors']}
    if sector_key not in seen_sectors:
        entry['sectors'].append(sector)


def _mesh_glb_path(path, mesh_ref, asset_index=None):
    if asset_index is not None:
        if mesh_ref.endswith(('physicalscene', 'w2mesh')):
            resolved = asset_index.resolve_expected(mesh_ref + '.glb', '.glb', warn=False)
        else:
            resolved = asset_index.resolve_mesh_glb(mesh_ref)
        if resolved:
            return resolved

    if mesh_ref.endswith(('physicalscene', 'w2mesh')):
        return os.path.join(path, mesh_ref + '.glb').replace('\\', os.sep)
    return os.path.join(path, os.path.splitext(mesh_ref)[0] + '.glb').replace('\\', os.sep)


def _appearance_list(raw_apps):
    if len(raw_apps) == 1 and isinstance(raw_apps[0], list):
        raw_apps = raw_apps[0]

    apps = []
    seen = set()
    for app in raw_apps:
        value = _appearance_name(app)
        if value and value not in seen:
            seen.add(value)
            apps.append(value)
    return apps


def _prune_materials(obj, mat_name):
    materials = obj.data.materials
    if len(mat_name) >= NAME_MAX_LEN or len(materials) <= 1 or mat_name not in materials.keys():
        return
    for index in range(len(materials) - 1, -1, -1):
        if materials.keys()[index].split('.')[0] != mat_name:
            materials.pop(index=index)


def meshes_from_mesheswapps(meshes_w_apps, path='', from_mesh_no=0, to_mesh_no=10000000, with_mats=False, glbs=None, mesh_jsons=None, Masters=None, generate_overrides=False, asset_index=None):
    props = bpy.context.scene.cp77_panel_props
    context = bpy.context
    coll_scene = context.scene.collection
    master_children = Masters.children

    for index, mesh_ref in enumerate(meshes_w_apps):
        if index < from_mesh_no or index > to_mesh_no:
            continue
        if not mesh_ref.endswith(('mesh', 'physicalscene', 'w2mesh')):
            continue

        apps = _appearance_list(meshes_w_apps[mesh_ref].get('apps', []))
        meshpath = _mesh_glb_path(path, mesh_ref, asset_index=asset_index)
        print(meshpath)

        groupname = get_groupname(meshpath, '')
        if groupname in master_children.keys():
            continue
        if not os.path.exists(meshpath):
            print('Mesh ', meshpath, ' does not exist')
            continue

        try:
            CP77GLBimport(with_materials=with_mats, remap_depot=props.remap_depot, filepath=meshpath, appearances=apps, scripting=True, generate_overrides=generate_overrides)
            objs = context.selected_objects
            if not objs:
                print('failed on ', os.path.basename(meshpath))
                print('No objects selected after import')
                continue

            source_coll = objs[0].users_collection[0]
            if source_coll.name != groupname:
                source_coll.name = groupname
            move_coll = coll_scene.children.get(source_coll.name)
            move_coll['meshpath'] = mesh_ref
            move_coll['appearance'] = 'default'
            master_children.link(move_coll)

            json_apps = json.loads(move_coll['json_apps']) if 'json_apps' in move_coll.keys() else None
            if json_apps is None:
                print(f'{bcolors.FAIL}No material json found for - {mesh_ref}{bcolors.ENDC}')

            source_objects = tuple(move_coll.objects)
            for app in apps:
                new_coll = bpy.data.collections.new(groupname + '@' + app)
                master_children.link(new_coll)
                new_coll['meshpath'] = mesh_ref
                new_coll['appearance'] = app
                app_materials = json_apps.get(app) if json_apps else None

                for obj_index, obj in enumerate(source_objects):
                    obj_copy = obj.copy()
                    obj_copy.data = obj.data.copy()
                    if obj_copy.type == 'MESH' and app_materials and obj_index < len(app_materials):
                        mat_name = app_materials[obj_index]
                        if 'sidewalk' in mesh_ref:
                            mat_name = 'sidewalksidewalksidewalksidewalksidewalksidewalksidewalksidewalksidewalk'
                        _prune_materials(obj_copy, mat_name)
                    new_coll.objects.link(obj_copy)

            coll_scene.children.unlink(move_coll)
        except Exception:
            print('failed on ', os.path.basename(meshpath))
            print(traceback.format_exc())
