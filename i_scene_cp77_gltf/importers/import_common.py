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


def _collection_from_selection(context):
    for obj in context.selected_objects:
        collection = next(iter(obj.users_collection), None)
        if collection is not None:
            return collection
    return None


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


def _copy_collection_objects(source_collection, target_collection, appearance, mesh_key):
    json_apps_raw = source_collection.get('json_apps')
    json_apps = json.loads(json_apps_raw) if json_apps_raw else None
    if not json_apps:
        print(f'{bcolors.FAIL}No material json found for - {mesh_key}{bcolors.ENDC}')

    copied_objects = []
    object_map = {}
    for index, source_obj in enumerate(source_collection.objects):
        obj = source_obj.copy()
        object_map[source_obj] = obj
        copied_objects.append(obj)
        if source_obj.data:
            obj.data = source_obj.data.copy()

        if obj.type == 'MESH' and json_apps and appearance in json_apps and index < len(json_apps[appearance]):
            mat_name = json_apps[appearance][index]
            if 'sidewalk' in mesh_key:
                mat_name = 'sidewalksidewalksidewalksidewalksidewalksidewalksidewalksidewalksidewalk'
            if len(mat_name) < 63 and len(obj.data.materials) > 1 and obj.data.materials.find(mat_name) >= 0:
                for material_index in range(len(obj.data.materials) - 1, -1, -1):
                    material = obj.data.materials[material_index]
                    material_name = material.name if material else ''
                    if material_name.split('.')[0] != mat_name:
                        obj.data.materials.pop(index=material_index)

        target_collection.objects.link(obj)

    _remap_copied_object_references(copied_objects, object_map)


def _mesh_appearances(mesh_data):
    apps = []
    for mesh_app in mesh_data.get('apps', [[]])[0]:
        appearance = _appearance_name(mesh_app)
        if appearance and appearance not in apps:
            apps.append(appearance)
    return apps


def meshes_from_mesheswapps(meshes_w_apps, path='', from_mesh_no=0, to_mesh_no=10000000, with_mats=False, glbs=None, mesh_jsons=None, Masters=None, generate_overrides=False):
    props = bpy.context.scene.cp77_panel_props
    context = bpy.context
    scene_collection = context.scene.collection

    for index, mesh_key in enumerate(meshes_w_apps):
        if index < from_mesh_no or index > to_mesh_no:
            continue
        if not (mesh_key.endswith('mesh') or mesh_key.endswith('physicalscene') or mesh_key.endswith('w2mesh')):
            continue

        apps = _mesh_appearances(meshes_w_apps[mesh_key])
        if mesh_key.endswith('physicalscene') or mesh_key.endswith('w2mesh'):
            meshpath = os.path.join(path, mesh_key + '.glb').replace('\\', os.sep)
            print('not a standard mesh')
        else:
            meshpath = os.path.join(path, os.path.splitext(mesh_key)[0] + '.glb').replace('\\', os.sep)
        print(meshpath)

        groupname = get_groupname(meshpath, '')
        if Masters.children.get(groupname) is not None:
            continue
        if not os.path.exists(meshpath):
            print('Mesh ', meshpath, ' does not exist')
            continue

        try:
            CP77GLBimport(
                with_materials=with_mats,
                remap_depot=props.remap_depot,
                filepath=meshpath,
                appearances=apps,
                scripting=True,
                generate_overrides=generate_overrides,
            )

            move_coll = _collection_from_selection(context)
            if move_coll is None:
                print(f'{bcolors.FAIL}Import produced no collection for - {mesh_key}{bcolors.ENDC}')
                continue

            if move_coll.name != groupname:
                move_coll.name = groupname
            move_coll['meshpath'] = mesh_key
            move_coll['appearance'] = 'default'
            if move_coll.name in scene_collection.children:
                scene_collection.children.unlink(move_coll)
            Masters.children.link(move_coll)

            for app in apps:
                new_coll = bpy.data.collections.new(groupname + '@' + app)
                new_coll['meshpath'] = mesh_key
                new_coll['appearance'] = app
                Masters.children.link(new_coll)
                _copy_collection_objects(move_coll, new_coll, app, mesh_key)
        except Exception:
            print('failed on ', os.path.basename(meshpath))
            print(traceback.format_exc())
