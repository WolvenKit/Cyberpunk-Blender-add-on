#
# Streaming Sector Blender import Script for Cyberpunk 2077 by Simarilius
# Jan 2023
# Latest Version available at https://github.com/Simarilius-uk/CP2077_BlenderScripts
# Assumes import plugin version >1.1
#
#    ________  ______  __________  ____  __  ___   ____ __    _____ ______________________  ____     ______  _______  ____  ____  ______
#   / ____/\ \/ / __ )/ ____/ __ \/ __ \/ / / / | / / //_/   / ___// ____/ ____/_  __/ __ \/ __ \   /  _/  |/  / __ \/ __ \/ __ \/_  __/
#  / /      \  / __  / __/ / /_/ / /_/ / / / /  |/ / ,<      \__ \/ __/ / /     / / / / / / /_/ /   / // /|_/ / /_/ / / / / /_/ / / /
# / /___    / / /_/ / /___/ _, _/ ____/ /_/ / /|  / /| |    ___/ / /___/ /___  / / / /_/ / _, _/  _/ // /  / / ____/ /_/ / _, _/ / /
# \____/   /_/_____/_____/_/ |_/_/    \____/_/ |_/_/ |_|   /____/_____/\____/ /_/  \____/_/ |_|  /___/_/  /_/_/    \____/_/ |_| /_/
#
# 1) Change the project path defined below to the wkit project folder
# 2) If you want collision objects, change want_collisions to True
# 3) If you want it to generate the _new collections for you to add new stuff in set am_modding to True
# 4) Run it
from collections import defaultdict

import base64
import copy
import hashlib
import json
import math
import os
import time
import traceback

from bpy_extras import anim_utils
from mathutils import Matrix, Quaternion, Vector

from .collision_mesh_import import CP77CollisionTriangleMeshJSONimport_by_hashes
from .entity_import import importEnt
from .fog_volume import create_fog_volume_object
from .import_common import _collection_import_snapshot, _imported_collection_from_diff, \
    _remap_copied_object_references, add_to_list, get_group, meshes_from_mesheswapps
from .import_with_materials import *
from ..collisiontools.pxbridge.io_phys import import_collider_as_actor
from ..datakrash import DepotAssetIndex
from ..jsontool import resolve_entity_appearance
from ..main.common import *

VERBOSE = True
scale_factor = 1


def _sector_warning(message):
    print(f"Sector import warning: {message}")


def _warn_missing_resource(depot_path, resolved_path='', required=False, context=''):
    if required and depot_path and not resolved_path:
        _sector_warning(f'{context}: required resource not indexed: {depot_path}')


def _first_dict_value(data, *keys):
    if type(data) is not dict:
        return {}
    for key in keys:
        value = data.get(key)
        if type(value) is dict:
            return value
    return {}


def _axis_value(data, axis, default=0.0):
    if type(data) is not dict:
        return default
    value = data.get(axis)
    if value is not None:
        return value
    value = data.get(axis.lower())
    if value is not None:
        return value
    props = data.get('Properties')
    if type(props) is dict:
        return _axis_value(props, axis, default)
    return default


def get_pos(inst):
    data = _first_dict_value(inst, 'Position', 'position', 'Translation', 'translation')
    return [
        float(_axis_value(data, 'X')),
        float(_axis_value(data, 'Y')),
        float(_axis_value(data, 'Z')),
        ]


def get_rot(inst):
    data = _first_dict_value(inst, 'Orientation', 'orientation', 'Rotation', 'rotation')
    if type(data) is not dict:
        return [1.0, 0.0, 0.0, 0.0]
    if 'r' in data or 'i' in data or 'j' in data or 'k' in data:
        return [
            float(data.get('r', 1.0)),
            float(data.get('i', 0.0)),
            float(data.get('j', 0.0)),
            float(data.get('k', 0.0)),
            ]
    return [
        float(data.get('W', 1.0)),
        float(data.get('X', 0.0)),
        float(data.get('Y', 0.0)),
        float(data.get('Z', 0.0)),
        ]


def get_scale(inst):
    if type(inst) is not dict:
        return [1.0, 1.0, 1.0]
    data = inst.get('Scale')
    if data is None:
        data = inst.get('scale')
    if type(data) is dict:
        return [
            float(_axis_value(data, 'X', 1.0)),
            float(_axis_value(data, 'Y', 1.0)),
            float(_axis_value(data, 'Z', 1.0)),
            ]
    if data is not None:
        value = float(data)
        return [value, value, value]
    return [1.0, 1.0, 1.0]


MESH_GLB_EXTENSIONS = ('.glb', '.physicalscene.glb', '.w2mesh.glb')


SECTOR_INDEX_EXTENSIONS = (
    '.streamingsector.json',
    '.ent.json',
    '.app.json',
    '.mesh.json',
    '.glb',
    '.physicalscene.glb',
    '.w2mesh.glb',
    '.anims.glb',
    '.rig.json',
    '.mi.json',
    '.cfoliage.json',
    '.particle.json',
    '.effect.json',
    '.acousticdata.json',
    '.envprobe.json',
    '.cminimap.json',
    '.gidata.json',
    '.smartobjects.json',
    '.workspot.json',
    '.actionanimdb.json',
    '.ies.json',
    '.ies',
    )


OPTIONAL_SECTOR_NODE_TYPES = {
    'proxies': {
        'worldBuildingProxyMeshNode',
        'worldGenericProxyMeshNode',
        'worldEntityProxyMeshNode',
        'worldDestructibleEntityProxyMeshNode',
        'worldDestructibleProxyMeshNode',
        'worldTerrainProxyMeshNode',
        'worldRoadProxyMeshNode',
        },
    'acoustics': {'worldAcousticSectorNode'},
    'occluders': {
        'worldStaticOccluderMeshNode',
        'worldInstancedOccluderNode',
        },
    'minimap': {'MinimapDataNode'},
    'environment_probes': {'worldReflectionProbeNode'},
    'gi': {
        'worldGINode',
        'worldGISpaceNode',
        },
    }

OPTIONAL_SECTOR_INDEX_EXTENSIONS = {
    'acoustics': {'.acousticdata.json'},
    'minimap': {'.cminimap.json'},
    'environment_probes': {'.envprobe.json'},
    'gi': {'.gidata.json'},
    }

GI_HELPER_MESH_PATHS = frozenset({
    'base/lighting/gi_visible_game_invisible.w2mesh',
    })

WATER_PATCH_PROXY_PREFIX = 'base/prefabs/generic/water/global_ocean_patch_'
WATER_PATCH_PROXY_SUFFIX = '_proxy.mesh'


def _depot_path_key(value):
    return str(value or '').replace('\\', '/').strip().lower()


def _is_water_patch_proxy(data):
    if not isinstance(data, dict):
        return False
    node_type = str(data.get('$type', ''))
    if node_type not in OPTIONAL_SECTOR_NODE_TYPES['proxies']:
        return False
    meshname = _depot_path(data, 'mesh', 'meshRef')
    mesh_key = _depot_path_key(meshname)
    return (
        mesh_key.startswith(WATER_PATCH_PROXY_PREFIX)
        and mesh_key.endswith(WATER_PATCH_PROXY_SUFFIX)
        )


def _skip_disabled_gi_helper(meshname, optional_imports):
    return (
        not optional_imports.get('gi', False)
        and _depot_path_key(meshname) in GI_HELPER_MESH_PATHS
        )


def _optional_sector_imports(
        import_proxies=False,
        import_acoustics=False,
        import_occluders=False,
        import_minimap=False,
        import_environment_probes=False,
        import_gi=False,
        ):
    return {
        'proxies': bool(import_proxies),
        'acoustics': bool(import_acoustics),
        'occluders': bool(import_occluders),
        'minimap': bool(import_minimap),
        'environment_probes': bool(import_environment_probes),
        'gi': bool(import_gi),
        }


def _should_import_sector_node(data, optional_imports):
    node_type = str(data.get('$type', '')) if isinstance(data, dict) else str(data)
    if node_type in OPTIONAL_SECTOR_NODE_TYPES['proxies'] and _is_water_patch_proxy(data):
        return True
    for category, node_types in OPTIONAL_SECTOR_NODE_TYPES.items():
        if node_type in node_types:
            return bool(optional_imports.get(category, False))
    return True


def _sector_index_extensions(optional_imports):
    excluded = set()
    for category, extensions in OPTIONAL_SECTOR_INDEX_EXTENSIONS.items():
        if not optional_imports.get(category, False):
            excluded.update(extensions)
    return tuple(
        extension
        for extension in SECTOR_INDEX_EXTENSIONS
        if extension not in excluded
        )


def _indexed_files(asset_index, *extensions):
    files = []
    seen = set()
    for extension in extensions:
        for filepath in asset_index.get_files_by_extension(extension):
            key = os.path.normcase(os.path.normpath(filepath))
            if key not in seen:
                seen.add(key)
                files.append(filepath)
    return files


def _normalize_depot_path(value):
    if not value:
        return ''
    return str(value).replace('\\', os.sep).replace('/', os.sep)


def _depot_path_from_value(value):
    if not isinstance(value, dict):
        return ''
    depot_path = value.get('DepotPath')
    if isinstance(depot_path, dict):
        return _normalize_depot_path(depot_path.get('$value', ''))
    if isinstance(depot_path, str):
        return _normalize_depot_path(depot_path)
    return _normalize_depot_path(value.get('$value', ''))


def _depot_path(data, *keys):
    if not isinstance(data, dict):
        return ''
    for key in keys:
        depot_path = _depot_path_from_value(data.get(key))
        if depot_path:
            return depot_path
    return ''


def _resolve_indexed_json(asset_index, depot_path, extension):
    depot_path = _normalize_depot_path(depot_path)
    if not depot_path:
        return None
    if not depot_path.lower().endswith('.json'):
        depot_path = f'{depot_path}.json'
    return asset_index.resolve_expected(depot_path, extension)


def _resolve_indexed_glb(asset_index, depot_path):
    depot_path = _normalize_depot_path(depot_path)
    if not depot_path:
        return None
    return asset_index.resolve_export(depot_path, MESH_GLB_EXTENSIONS)


def _project_sector_path(raw_root, project_name):
    return os.path.normcase(os.path.normpath(os.path.join(raw_root, 'base', f'{project_name}.streamingsector.json')))


def _same_path(left, right):
    return os.path.normcase(os.path.normpath(left)) == os.path.normcase(os.path.normpath(right))


def _trim_name(name, max_len=63):
    return name[:max_len]


def _entity_collection_name(entpath, appearance_name):
    return _trim_name(os.path.basename(entpath).split('.')[0] + '_' + appearance_name) if appearance_name else ''


def _entity_collection_candidates(entpath, requested_app, resolved_app):
    names = []
    for appearance_name in (resolved_app, requested_app):
        name = _entity_collection_name(entpath, appearance_name)
        if name and name not in names:
            names.append(name)
    return names


def _first_child_collection(parent_collection, names):
    for name in names:
        collection = parent_collection.children.get(name)
        if collection is not None:
            return collection
    return None


def _node_instances(node_data):
    instances = defaultdict(list)
    for index, item in enumerate(node_data or []):
        item['nodeDataIndex'] = index
        instances[item.get('NodeIndex')].append(item)
    return instances


def _node_handle_lookup(nodes):
    return {node.get('HandleId'): node for node in nodes or [] if isinstance(node, dict)}


def _shared_transform_buffer_lookup(nodes, buffer_key):
    lookup = {}
    for node in nodes or ():
        if not isinstance(node, dict):
            continue
        data = node.get('Data')
        if not isinstance(data, dict):
            continue
        buffer_owner = data.get(buffer_key)
        if not isinstance(buffer_owner, dict):
            continue
        shared = buffer_owner.get('sharedDataBuffer')
        if not isinstance(shared, dict) or 'HandleId' not in shared or 'Data' not in shared:
            continue
        transforms = shared.get('Data', {}).get('buffer', {}).get('Data', {}).get('Transforms')
        if transforms is not None:
            lookup[str(shared['HandleId'])] = transforms
    return lookup


def _shared_transform_buffer(data, buffer_lookup, buffer_key):
    buffer_owner = data.get(buffer_key) if isinstance(data, dict) else None
    if not isinstance(buffer_owner, dict):
        return []
    shared = buffer_owner.get('sharedDataBuffer')
    if not isinstance(shared, dict):
        return []
    if 'Data' in shared:
        return shared.get('Data', {}).get('buffer', {}).get('Data', {}).get('Transforms', [])
    handle_ref = shared.get('HandleRefId')
    if handle_ref is not None:
        return buffer_lookup.get(str(handle_ref), [])
    return []


def _buffer_ref_id(data, buffer_key):
    shared = data.get(buffer_key, {}).get('sharedDataBuffer', {}) if isinstance(data, dict) else {}
    return shared.get('HandleRefId') if isinstance(shared, dict) else None


def _read_sector_root(filepath):
    with open(filepath, 'r', encoding='utf-8-sig') as stream:
        payload = json.load(stream)
    return payload.get('Data', {}).get('RootChunk', {})


def _resource_depot_paths(value):
    paths = []

    def visit(item):
        if isinstance(item, dict):
            depot = item.get('DepotPath')
            if isinstance(depot, dict):
                raw = depot.get('$value')
                if raw not in (None, '', 0, '0'):
                    paths.append(_normalize_depot_path(raw))
            for child in item.values():
                visit(child)
        elif isinstance(item, list):
            for child in item:
                visit(child)

    visit(value)
    result = []
    seen = set()
    for path in paths:
        key = _path_key(path)
        if key and key not in seen:
            seen.add(key)
            result.append(path)
    return result


def _is_streaming_sector_resource(depot_path):
    normalized = _normalize_depot_path(depot_path).lower()
    return normalized.endswith(('.streamingsector', '.streamingsector_inplace', '.streamingsector.json', '.streamingsector_inplace.json'))


def _load_sector_entry(
        filepath, parent_sector='', parent_sector_path='', composition_depth=0, source_kind='root', source_depot_path=''
        ):
    node_data, nodes = JSONTool.jsonload(filepath)
    root = _read_sector_root(filepath)
    referenced_paths = []
    referenced_paths.extend(_resource_depot_paths(root.get('externInplaceResource')))
    referenced_paths.extend(_resource_depot_paths(root.get('localInplaceResource')))
    inplace_paths = [path for path in referenced_paths if _is_streaming_sector_resource(path)]
    return {
        'filepath': filepath,
        'sectorName': os.path.basename(filepath)[:-5],
        'nodeData': node_data,
        'nodes': nodes,
        'instances_by_node': _node_instances(node_data),
        'nodes_by_handle': _node_handle_lookup(nodes),
        'world_transform_buffers': _shared_transform_buffer_lookup(nodes, 'worldTransformsBuffer'),
        'cooked_transform_buffers': _shared_transform_buffer_lookup(nodes, 'cookedInstanceTransforms'),
        'category': root.get('category', ''),
        'level': root.get('level', 0),
        'variantIndices': [int(value) for value in root.get('variantIndices', [])],
        'variantNodes': root.get('variantNodes', []),
        'inplaceDepotPaths': inplace_paths,
        'parentSector': parent_sector,
        'parentSectorPath': parent_sector_path,
        'compositionParents': [parent_sector] if parent_sector else [],
        'compositionParentPaths': [parent_sector_path] if parent_sector_path else [],
        'compositionDepth': int(composition_depth),
        'sourceKind': source_kind,
        'sourceDepotPath': source_depot_path,
        'compositionIssues': [],
        'resolvedInplacePaths': [],
        }


def _resolve_inplace_sector(asset_index, depot_path):
    return (
        _resolve_indexed_json(asset_index, depot_path, '.streamingsector_inplace.json')
        or _resolve_indexed_json(asset_index, depot_path, '.streamingsector.json')
        )


def _sector_entries(sector_jsons, base_path, project_name, asset_index):
    project_sector = os.path.join(base_path, project_name + '.streamingsector.json')
    root_paths = [
        path for path in sorted(sector_jsons)
        if path.lower().endswith('.streamingsector.json')
        and not _same_path(path, project_sector)
        and 'sim_' not in path
        ]
    return [_load_sector_entry(path) for path in root_paths]


def _sector_collection_for_entry(scene_collection, sector_entry, created_collections):
    filepath = sector_entry['filepath']
    path_key = _path_key(filepath)
    collection = created_collections.get(path_key)
    if collection is None:
        for candidate in bpy.data.collections:
            stored_path = candidate.get('filepath', '')
            if stored_path and _same_path(stored_path, filepath):
                collection = candidate
                break
    if collection is None:
        base_name = sector_entry['sectorName']
        name = base_name
        existing = bpy.data.collections.get(name)
        if existing is not None and not _same_path(existing.get('filepath', ''), filepath):
            identity = hashlib.sha1(path_key.encode('utf-8')).hexdigest()[:8]
            name = _trim_name(f'{base_name}_{identity}')
        collection = bpy.data.collections.new(name)
    created_collections[path_key] = collection

    parent_sector = sector_entry.get('parentSector', '')
    parent_path = sector_entry.get('parentSectorPath', '')
    parent_collection = created_collections.get(_path_key(parent_path)) if parent_path else None
    if parent_collection is None and parent_sector:
        for candidate in created_collections.values():
            if candidate.get('sectorName') == parent_sector or candidate.name == parent_sector:
                parent_collection = candidate
                break
    if parent_collection is not None:
        if parent_collection.children.get(collection.name) is not collection:
            parent_collection.children.link(collection)
        if scene_collection.children.get(collection.name) is collection:
            scene_collection.children.unlink(collection)
    elif scene_collection.children.get(collection.name) is not collection:
        scene_collection.children.link(collection)
    return collection


def _link_sector_composition(sector_entries, created_collections, scene_collection):
    for entry in sector_entries:
        child = created_collections.get(_path_key(entry['filepath']))
        if child is None:
            continue
        parent_paths = entry.get('compositionParentPaths', [])
        linked_parent = False
        for parent_path in parent_paths:
            parent = created_collections.get(_path_key(parent_path))
            if parent is None or parent is child:
                continue
            if parent.children.get(child.name) is not child:
                parent.children.link(child)
            linked_parent = True
        if linked_parent and scene_collection.children.get(child.name) is child:
            scene_collection.children.unlink(child)


def _first_instance(instances_by_node, node_index):
    instances = instances_by_node.get(node_index)
    return instances[0] if instances else None


def _instance_matrix(inst, scale=1):
    pos = Vector(get_pos(inst))
    rot = Quaternion(get_rot(inst))
    inst_scale = Vector(get_scale(inst))
    if scale != 1:
        inst_scale = Vector((inst_scale.x / scale, inst_scale.y / scale, inst_scale.z / scale))
    return Matrix.LocRotScale(pos, rot, inst_scale)


def _pivot_vector(inst):
    pivot = inst.get('Pivot') if type(inst) is dict else None
    if type(pivot) is dict:
        return Vector(
                (
                    float(_axis_value(pivot, 'X')),
                    float(_axis_value(pivot, 'Y')),
                    float(_axis_value(pivot, 'Z')),
                    )
                )
    return Vector((0.0, 0.0, 0.0))


def _world_buffer_matrix(buffer_inst, scale=1):
    return _instance_matrix(buffer_inst, scale)


def _matrix_values(matrix):
    return [float(matrix[row][column]) for row in range(4) for column in range(4)]


def _buffer_slice(data, buffer_lookup, buffer_key, sector_name, node_index):
    owner = data.get(buffer_key, {}) if isinstance(data, dict) else {}
    start = int(owner.get('startIndex', 0) or 0)
    count = int(owner.get('numElements', 0) or 0)
    transforms = _shared_transform_buffer(data, buffer_lookup, buffer_key)
    if start < 0 or count < 0:
        _sector_warning(f'{sector_name}: node {node_index} has invalid {buffer_key} slice start={start}, count={count}')
        return start, count, transforms, []
    end = start + count
    if end > len(transforms):
        _sector_warning(f'{sector_name}: node {node_index} requests {buffer_key}[{start}:{end}] from a buffer containing {len(transforms)} transforms')
    return start, count, transforms, [
        (index, transforms[index])
        for index in range(start, min(end, len(transforms)))
        ]


def _path_key(value):
    return os.path.normcase(os.path.normpath(str(value))) if value else ''


def _entity_master_key(entpath, appearance_name):
    return (_path_key(entpath), str(appearance_name or ''))


def _relative_entity_json_path(ent_depot):
    path = _normalize_depot_path(ent_depot)
    return path if path.lower().endswith('.json') else f'{path}.json'


def _find_entity_master(masters, ent_depot, requested_app, resolved_app, candidates):
    expected_path = _path_key(_relative_entity_json_path(ent_depot))
    valid_apps = {str(value) for value in (requested_app, resolved_app) if value}
    fallback = None
    for collection in masters.children:
        stored_path = _path_key(collection.get('depotPath', ''))
        stored_app = str(collection.get('appearanceName', ''))
        if stored_path == expected_path and (not valid_apps or stored_app in valid_apps):
            return collection
        if fallback is None and collection.name in candidates:
            fallback = collection
    if fallback is not None:
        stored_path = _path_key(fallback.get('depotPath', ''))
        if not stored_path or stored_path == expected_path:
            return fallback
    return None


def _new_empty(name, collection, display_size=0.25):
    obj = bpy.data.objects.new(_trim_name(name), None)
    obj.empty_display_type = 'PLAIN_AXES'
    obj.empty_display_size = display_size
    collection.objects.link(obj)
    return obj


def _copy_collection_tree_with_placement_root(
        src_collection, name, transform, color=None, hide_armatures=True, rotating=False,
        ):
    dst_root = bpy.data.collections.new(_trim_name(name))
    copy_map = {}

    def copy_into(src, dst):
        for child in src.children:
            child_dst = bpy.data.collections.new(child.name)
            dst.children.link(child_dst)
            copy_into(child, child_dst)
        for old_obj in src.objects:
            obj = _copy_object(old_obj, color=color, hide_armature=hide_armatures)
            copy_map[old_obj] = obj
            dst.objects.link(obj)

    copy_into(src_collection, dst_root)
    _remap_copied_object_references(tuple(copy_map.values()), copy_map)

    placement_root = _new_empty(f'{name}_Placement', dst_root)
    content_root = placement_root
    rotation_root = None
    if rotating:
        location, rotation, scale = transform.decompose()
        placement_root.matrix_world = Matrix.LocRotScale(
            location, rotation, Vector((1.0, 1.0, 1.0))
            )
        rotation_root = _new_empty(f'{name}_Rotation', dst_root)
        rotation_root.parent = placement_root
        rotation_root.matrix_parent_inverse = Matrix.Identity(4)
        rotation_root.matrix_basis = Matrix.Identity(4)
        scale_root = _new_empty(f'{name}_Scale', dst_root)
        scale_root.parent = rotation_root
        scale_root.matrix_parent_inverse = Matrix.Identity(4)
        scale_root.matrix_basis = Matrix.LocRotScale(
            Vector((0.0, 0.0, 0.0)), Quaternion((1.0, 0.0, 0.0, 0.0)), scale
            )
        content_root = scale_root
    else:
        placement_root.matrix_world = transform

    for old_obj, obj in copy_map.items():
        if old_obj.parent in copy_map:
            continue
        obj.parent = content_root
        obj.matrix_parent_inverse = Matrix.Identity(4)
        obj.matrix_basis = (
            old_obj.matrix_basis.copy() if old_obj.parent is None else old_obj.matrix_world.copy()
            )

    return dst_root, placement_root, rotation_root


def _variant_for_node_data(entry, node_data_index):
    indices = entry.get('variantIndices', [])
    if len(indices) < 2 or node_data_index is None:
        return None
    index = int(node_data_index)
    for variant_index, (start, end) in enumerate(zip(indices, indices[1:])):
        if start <= index < end:
            return variant_index
    return None


def _ensure_child_collection(parent, name):
    for collection in parent.children:
        if collection.get('semanticCollectionName') == name or collection.name == name:
            return collection
    collection = bpy.data.collections.new(_trim_name(f'{parent.name}_{name}'))
    collection['semanticCollectionName'] = name
    parent.children.link(collection)
    return collection


def _placement_node_data_index(item):
    for key in ('nodeDataIndex', 'ndi'):
        value = item.get(key)
        if value is not None:
            try:
                return int(value)
            except (TypeError, ValueError):
                return None
    return None


def _is_proxy_node_type(node_type):
    return str(node_type) in {
        'worldBuildingProxyMeshNode',
        'worldGenericProxyMeshNode',
        'worldEntityProxyMeshNode',
        'worldDestructibleEntityProxyMeshNode',
        'worldDestructibleProxyMeshNode',
        'worldTerrainProxyMeshNode',
        'worldRoadProxyMeshNode',
        }


def _organize_sector_placements(sector_collection, sector_entry, selected_variant=None):
    variant_indices = sector_entry.get('variantIndices', [])
    variant_root = None
    variant_collections = {}
    if len(variant_indices) >= 2:
        variant_root = _ensure_child_collection(sector_collection, '_Variants')
        variant_root['variantIndices'] = list(variant_indices)
        variant_root['variantCount'] = len(variant_indices) - 1
        for variant_index, (start, end) in enumerate(zip(variant_indices, variant_indices[1:])):
            collection = _ensure_child_collection(variant_root, f'Variant_{variant_index:02d}')
            collection['variantIndex'] = variant_index
            collection['nodeDataStart'] = int(start)
            collection['nodeDataEndExclusive'] = int(end)
            collection['variantNodes'] = json.dumps(
                sector_entry.get('variantNodes', [])[variant_index]
                if variant_index < len(sector_entry.get('variantNodes', [])) else [],
                separators=(',', ':')
                )
            if selected_variant is not None:
                is_selected = variant_index == int(selected_variant)
                collection.hide_viewport = not is_selected
                collection.hide_render = not is_selected
                collection['selectedForImport'] = is_selected
            else:
                collection.hide_viewport = False
                collection.hide_render = False
                collection['selectedForImport'] = True
            variant_collections[variant_index] = collection

    if selected_variant is not None and not 0 <= int(selected_variant) < max(0, len(variant_indices) - 1):
        _sector_warning(f"{sector_entry.get('sectorName', '')}: selected variant {selected_variant} is outside the available range")
    placements = []
    node_data = sector_entry.get('nodeData', [])

    def annotate(item):
        node_data_index = _placement_node_data_index(item)
        variant_index = _variant_for_node_data(sector_entry, node_data_index)
        item['variantIndex'] = -1 if variant_index is None else variant_index
        if node_data_index is not None and 0 <= node_data_index < len(node_data):
            record = node_data[node_data_index]
            item['nodeDataId'] = str(record.get('Id', ''))
            quest_ref = record.get('QuestPrefabRefHash', {})
            item['questPrefabRefHash'] = _cname_value(quest_ref)
        placements.append(item)
        return variant_index

    def destination(item):
        variant_index = annotate(item)
        parent = variant_collections.get(variant_index, sector_collection)
        if _is_proxy_node_type(item.get('nodeType', '')):
            parent = _ensure_child_collection(parent, '_Proxies')
            parent['proxyDisplayCollection'] = True
            item['proxySemantic'] = True
        return parent

    protected = {'_Variants', '_Proxies'}
    for collection in tuple(sector_collection.children):
        semantic_name = collection.get('semanticCollectionName')
        if semantic_name in protected or collection.name in protected or collection is variant_root:
            continue
        target = destination(collection)
        if target is not sector_collection:
            target.children.link(collection)
            sector_collection.children.unlink(collection)

    for obj in tuple(sector_collection.objects):
        target = destination(obj)
        if target is not sector_collection:
            target.objects.link(obj)
            sector_collection.objects.unlink(obj)

    owner_targets = {}
    for item in placements:
        if _is_proxy_node_type(item.get('nodeType', '')):
            continue
        for key in ('sourcePrefabHash', 'nodeDataId'):
            value = str(item.get(key, ''))
            if value and value != '0':
                owner_targets.setdefault(value, item)

    unresolved = 0
    resolved = 0
    for item in placements:
        if not _is_proxy_node_type(item.get('nodeType', '')):
            continue
        owner_id = str(item.get('proxyOwnerGlobalId', ''))
        owner = owner_targets.get(owner_id)
        if owner is None:
            item['proxyOwnerResolved'] = False
            unresolved += 1
            continue
        item['proxyOwnerResolved'] = True
        item['proxyOwnerName'] = owner.name
        item['proxyOwnerNodeIndex'] = int(owner.get('nodeIndex', -1))
        item['proxyOwnerNodeDataIndex'] = int(owner.get('nodeDataIndex', -1))
        resolved += 1

    sector_collection['proxyOwnerResolvedCount'] = resolved
    sector_collection['proxyOwnerUnresolvedCount'] = unresolved


def _safe_json(value):
    return json.dumps(value, separators=(',', ':'), ensure_ascii=False)


def _cname_value(value, default=''):
    if isinstance(value, dict):
        return str(value.get('$value', default))
    return str(value) if value not in (None, '') else default


def _nested_value(value, *keys, default=''):
    current = value
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
    return current if current is not None else default


def _resolve_optional_resource(asset_index, depot_path):
    normalized = _normalize_depot_path(depot_path)
    if not normalized:
        return None
    suffix = os.path.splitext(normalized)[1].lower()
    extension = f'{suffix}.json' if suffix else '.json'
    return _resolve_indexed_json(asset_index, normalized, extension)


def _resolve_ies_resource(asset_index, depot_path):
    normalized = _normalize_depot_path(depot_path)
    if not normalized:
        return None
    return (
        asset_index.resolve_expected(normalized, '.ies')
        or _resolve_indexed_json(asset_index, normalized, '.ies.json')
        )


def _temperature_rgb(kelvin):
    temperature = max(1000.0, min(40000.0, float(kelvin))) / 100.0
    if temperature <= 66.0:
        red = 255.0
        green = 99.4708025861 * math.log(temperature) - 161.1195681661
        blue = 0.0 if temperature <= 19.0 else 138.5177312231 * math.log(temperature - 10.0) - 305.0447927307
    else:
        red = 329.698727446 * ((temperature - 60.0) ** -0.1332047592)
        green = 288.1221695283 * ((temperature - 60.0) ** -0.0755148492)
        blue = 255.0
    return tuple(max(0.0, min(1.0, value / 255.0)) for value in (red, green, blue))


def _light_color(data):
    color = get_col(data.get('color', {'Red': 255, 'Green': 255, 'Blue': 255}))
    temperature = float(data.get('temperature', -1) or -1)
    if temperature > 0:
        temp = _temperature_rgb(temperature)
        color = [color[index] * temp[index] for index in range(3)]
    return tuple(max(0.0, min(1.0, value)) for value in color)


def _light_area(data):
    source_radius = max(0.0, float(data.get('sourceRadius', 0.0) or 0.0))
    length = max(0.0, float(data.get('capsuleLength', 0.0) or 0.0))
    side_a = max(0.0, float(data.get('areaRectSideA', 0.0) or 0.0))
    side_b = max(0.0, float(data.get('areaRectSideB', 0.0) or 0.0))
    if data.get('areaShape') == 'ALS_Capsule':
        effective_radius = source_radius if source_radius > 0.0 else side_b * 0.5
        return max(1e-6, length * (2.0 * effective_radius) + math.pi * effective_radius * effective_radius)
    return max(1e-6, side_a * side_b)


def _light_energy(data):
    intensity = max(0.0, float(data.get('intensity', 0.0) or 0.0))
    unit = str(data.get('unit', 'LU_Lumen'))
    light_type = str(data.get('type', 'LT_Point'))
    if unit == 'LU_Lumen':
        lumens = intensity
    elif unit == 'LU_Candela':
        if light_type == 'LT_Spot':
            outer = max(0.01, min(179.0, float(data.get('outerAngle', 90.0) or 90.0)))
            solid_angle = 2.0 * math.pi * (1.0 - math.cos(math.radians(outer * 0.5)))
        else:
            solid_angle = 4.0 * math.pi
        lumens = intensity * solid_angle
    elif unit == 'LU_Nit':
        lumens = intensity * _light_area(data) * math.pi
    else:
        lumens = intensity
    return lumens / 683.0


def _animate_light_flicker(light, flicker):
    if not isinstance(flicker, dict):
        return
    strength = max(0.0, float(flicker.get('flickerStrength', 0.0) or 0.0))
    period = max(0.0, float(flicker.get('flickerPeriod', 0.0) or 0.0))
    if strength <= 0.0 or period <= 0.0:
        return
    fps = float(bpy.context.scene.render.fps) / max(float(bpy.context.scene.render.fps_base), 1e-8)
    end_frame = 1 + max(2, round(period * fps))
    midpoint = 1 + max(1, (end_frame - 1) // 2)
    base_energy = float(light.energy)
    amplitude = min(strength, 1.0)
    for frame, energy in (
            (1, base_energy),
            (midpoint, base_energy * (1.0 - amplitude)),
            (end_frame, base_energy),
            ):
        light.energy = energy
        light.keyframe_insert('energy', frame=frame)
    action = light.animation_data.action if light.animation_data else None
    if action is None:
        return
    try:
        channelbag = anim_utils.action_get_channelbag_for_slot(action, light.animation_data.action_slot)
        fcurves = channelbag.fcurves
    except Exception:
        fcurves = getattr(action, 'fcurves', ())
    for fcurve in fcurves:
        for point in fcurve.keyframe_points:
            point.interpolation = 'LINEAR'
        if not any(modifier.type == 'CYCLES' for modifier in fcurve.modifiers):
            modifier = fcurve.modifiers.new(type='CYCLES')
            modifier.mode_before = 'REPEAT'
            modifier.mode_after = 'REPEAT'


def _create_static_light(data, node_index, inst, instance_index, sector_name, collection, asset_index):
    node_matrix = _instance_matrix(inst, scale_factor)
    cp_type = str(data.get('type', 'LT_Point'))
    blender_type = {'LT_Point': 'POINT', 'LT_Spot': 'SPOT', 'LT_Area': 'AREA'}.get(cp_type, 'POINT')
    if cp_type not in {'LT_Point', 'LT_Spot', 'LT_Area'}:
        _sector_warning(f'{sector_name}: light node {node_index} has unknown type {cp_type}')
    debug_name = _cname_value(data.get('debugName'), f'Light_{node_index}')
    light = bpy.data.lights.new(_trim_name(f'{node_index}_{debug_name}'), blender_type)
    obj = bpy.data.objects.new(_trim_name(f'{node_index}_{debug_name}'), light)
    collection.objects.link(obj)
    light.energy = _light_energy(data)
    light.color = _light_color(data)
    radius = max(0.0, float(data.get('radius', 0.0) or 0.0))
    source_radius = max(0.0, float(data.get('sourceRadius', 0.0) or 0.0))
    if hasattr(light, 'shadow_soft_size'):
        light.shadow_soft_size = source_radius
    if radius > 0.0 and hasattr(light, 'use_custom_distance'):
        light.use_custom_distance = True
        light.cutoff_distance = radius
    if blender_type == 'SPOT':
        outer = max(0.01, min(179.0, float(data.get('outerAngle', 90.0) or 90.0)))
        inner = max(0.0, min(outer, float(data.get('innerAngle', 0.0) or 0.0)))
        light.spot_size = math.radians(outer)
        light.spot_blend = max(0.0, min(1.0, 1.0 - inner / outer))
    elif blender_type == 'AREA':
        shape = str(data.get('areaShape', 'ALS_Capsule'))
        capsule_length = max(0.001, float(data.get('capsuleLength', 0.0) or 0.0))
        side_a = max(0.001, float(data.get('areaRectSideA', 1.0) or 1.0))
        side_b = max(0.001, float(data.get('areaRectSideB', 1.0) or 1.0))
        if shape == 'ALS_Capsule':
            light.shape = 'RECTANGLE'
            effective_source_radius = source_radius if source_radius > 0.0 else side_b * 0.5
            light.size = max(side_a, capsule_length + 2.0 * effective_source_radius)
            light.size_y = max(side_b, 2.0 * effective_source_radius)
        elif shape in {'ALS_Sphere', 'ALS_Disc'}:
            light.shape = 'DISK'
            light.size = max(side_a, 2.0 * radius)
        else:
            light.shape = 'RECTANGLE'
            light.size = side_a
            light.size_y = side_b
    axis_matrix = Matrix.Rotation(math.radians(90.0), 4, 'X') if blender_type in {'SPOT', 'AREA'} else Matrix.Identity(4)
    obj.matrix_world = node_matrix @ axis_matrix
    obj['lightAxisContract'] = 'CP77_LOCAL_Y_TO_BLENDER_LOCAL_NEGATIVE_Z' if blender_type in {'SPOT', 'AREA'} else 'OMNIDIRECTIONAL'
    ies_path = _depot_path(data, 'iesProfile')
    resolved_ies = _resolve_ies_resource(asset_index, ies_path)
    _warn_missing_resource(ies_path, resolved_ies or '', required=False, context=f'{sector_name}: light node {node_index} IES profile')
    assign_custom_properties(
        obj, data, sector_name, node_index, nodeDataIndex=inst['nodeDataIndex'],
        instance_idx=instance_index, cp77LightType=cp_type, cp77LightUnit=data.get('unit', ''),
        cp77Intensity=float(data.get('intensity', 0.0) or 0.0),
        lightChannel=str(data.get('lightChannel', '')), iesProfile=ies_path,
        resolvedIESProfile=resolved_ies or '',
        areaShape=str(data.get('areaShape', '')), radius=radius, sourceRadius=source_radius,
        capsuleLength=float(data.get('capsuleLength', 0.0) or 0.0),
        innerAngle=float(data.get('innerAngle', 0.0) or 0.0),
        outerAngle=float(data.get('outerAngle', 0.0) or 0.0),
        contactShadows=str(data.get('contactShadows', '')),
        enableLocalShadows=bool(data.get('enableLocalShadows', 0)),
        shadowSoftnessMode=str(data.get('shadowSoftnessMode', '')),
        )
    obj['lightEnergyContract'] = 'LUMINOUS_UNIT_TO_RADIOMETRIC_WATTS_683_LM_PER_W'
    obj['iesIntegration'] = 'RESOLVED_METADATA' if resolved_ies else 'UNRESOLVED_OR_NONE'
    obj['cp77LightData'] = _safe_json(data)
    _animate_light_flicker(light, data.get('flicker'))
    return obj


def _outline_data(data):
    outline = data.get('outline', {}) if isinstance(data, dict) else {}
    outline_data = outline.get('Data', {}) if isinstance(outline, dict) else {}
    points = outline_data.get('points', []) if isinstance(outline_data, dict) else []
    height = float(outline_data.get('height', 0.0) or 0.0) if isinstance(outline_data, dict) else 0.0
    return points, height


def _create_outline_volume(data, node_index, inst, instance_index, sector_name, collection, color):
    points, height = _outline_data(data)
    if len(points) < 3:
        _sector_warning(f"{sector_name}: {data['$type']} node {node_index} has no usable outline")
        return None
    half_height = height * 0.5
    vertices = []
    for z in (-half_height, half_height):
        vertices.extend((float(_axis_value(point, 'X')), float(_axis_value(point, 'Y')), float(_axis_value(point, 'Z')) + z) for point in points)
    count = len(points)
    faces = [tuple(range(count - 1, -1, -1)), tuple(range(count, count * 2))]
    faces.extend((index, (index + 1) % count, (index + 1) % count + count, index + count) for index in range(count))
    name = _trim_name(f'{data["$type"]}_{node_index}_{instance_index}')
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)
    node_matrix = _instance_matrix(inst, scale_factor)
    obj.matrix_world = node_matrix
    obj.display_type = 'WIRE'
    obj.color = color
    obj.show_wire = True
    assign_custom_properties(
        obj, data, sector_name, node_index, nodeDataIndex=inst['nodeDataIndex'],
        instance_idx=instance_index, outlineHeight=height, outlinePointCount=count
        )
    obj['outlineData'] = _safe_json(data.get('outline', {}))
    if 'notifiers' in data:
        obj['notifiers'] = _safe_json(data.get('notifiers', []))
    return obj


def _unit_box_mesh(name, half_extent=1.0):
    h = float(half_extent)
    vertices = [
        (-h, -h, -h), (h, -h, -h), (h, h, -h), (-h, h, -h),
        (-h, -h, h), (h, -h, h), (h, h, h), (-h, h, h),
        ]
    faces = [
        (0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
        (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7),
        ]
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    return mesh


def _create_box_semantic(data, node_index, inst, instance_index, sector_name, collection, contract, color, half_extent=1.0):
    name = _trim_name(f'{data["$type"]}_{node_index}_{instance_index}')
    obj = bpy.data.objects.new(name, _unit_box_mesh(name, half_extent))
    collection.objects.link(obj)
    node_matrix = _instance_matrix(inst, scale_factor)
    obj.matrix_world = node_matrix
    obj.display_type = 'WIRE'
    obj.color = color
    obj.show_wire = True
    assign_custom_properties(
        obj, data, sector_name, node_index, nodeDataIndex=inst['nodeDataIndex'], instance_idx=instance_index
        )
    return obj


def _audio_events(settings):
    data = settings.get('Data', {}) if isinstance(settings, dict) else {}
    events = {}
    for key in ('EventsOnActive', 'EventsOnEnter', 'EventsOnExit'):
        values = []
        for item in data.get(key, []) if isinstance(data, dict) else []:
            value = _cname_value(item.get('event') if isinstance(item, dict) else None)
            if value:
                values.append(value)
        events[key] = values
    return events


def _create_effect_marker(data, node_index, inst, instance_index, sector_name, collection, asset_index):
    node_type = data['$type']
    depot_path = _depot_path(data, 'particleSystem' if node_type == 'worldStaticParticleNode' else 'effect')
    resolved_path = _resolve_optional_resource(asset_index, depot_path)
    _warn_missing_resource(depot_path, resolved_path or '', required=False, context=f'{sector_name}: node {node_index}')
    name = _trim_name(f'{node_type}_{_cname_value(data.get("debugName"), str(node_index))}_{instance_index}')
    obj = bpy.data.objects.new(name, None)
    obj.empty_display_type = 'SPHERE'
    obj.empty_display_size = 0.5
    collection.objects.link(obj)
    node_matrix = _instance_matrix(inst, scale_factor)
    obj.matrix_world = node_matrix
    obj.display_type = 'WIRE'
    obj.color = (1.0, 0.005, 0.062, 1.0)
    assign_custom_properties(
        obj, data, sector_name, node_index, nodeDataIndex=inst['nodeDataIndex'],
        instance_idx=instance_index, assetDepotPath=depot_path,
        resolvedAssetPath=resolved_path or '', emissionRate=float(data.get('emissionRate', 0.0) or 0.0),
        forcedAutoHideDistance=float(data.get('forcedAutoHideDistance', -1.0) or -1.0),
        forcedAutoHideRange=float(data.get('forcedAutoHideRange', -1.0) or -1.0),
        streamingDistanceOverride=float(data.get('streamingDistanceOverride', 0.0) or 0.0),
        )
    obj['effectNodeData'] = _safe_json(data)
    return obj


def _interior_map_raster(data):
    buffer_data = data.get('buffer', {}) if isinstance(data, dict) else {}
    encoded = buffer_data.get('Bytes', '') if isinstance(buffer_data, dict) else ''
    if not encoded:
        return b'', 0, 0, ''
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, TypeError):
        return b'', 0, 0, ''
    side = math.isqrt(len(raw))
    width = side if side * side == len(raw) else len(raw)
    height = side if side * side == len(raw) else 1
    return raw, width, height, hashlib.sha1(raw).hexdigest()


def _interior_map_image(data, node_index, sector_name):
    raw, width, height, digest = _interior_map_raster(data)
    if not raw:
        _sector_warning(f'{sector_name}: interior map node {node_index} has no decodable buffer')
        return None, b'', 0, 0, ''
    if width * height != len(raw):
        _sector_warning(f'{sector_name}: interior map node {node_index} buffer length {len(raw)} is not rectangular')
    image_name = _trim_name(f'InteriorMap_{digest[:16]}')
    image = bpy.data.images.get(image_name)
    if image is None:
        image = bpy.data.images.new(image_name, width=width, height=height, alpha=True)
        pixels = [0.0] * (len(raw) * 4)
        for index, value in enumerate(raw):
            normalized = value / 255.0
            offset = index * 4
            pixels[offset] = normalized
            pixels[offset + 1] = normalized
            pixels[offset + 2] = normalized
            pixels[offset + 3] = 1.0
        image.pixels.foreach_set(pixels)
        image.update()
        try:
            image.colorspace_settings.name = 'Non-Color'
        except (TypeError, ValueError):
            pass
        image.pack()
        image['interiorMapRaster'] = True
        image['sourceByteCount'] = len(raw)
        image['sourceWidth'] = width
        image['sourceHeight'] = height
        image['sourceSha1'] = digest
        image['sourceRowOrder'] = 'ROW_MAJOR_UNFLIPPED'
    return image, raw, width, height, digest


def _create_interior_map_marker(data, node_index, inst, instance_index, sector_name, collection):
    image, raw, width, height, digest = _interior_map_image(
        data, node_index, sector_name
        )
    name = _trim_name(
        f'InteriorMap_{_cname_value(data.get("debugName"), str(node_index))}_{instance_index}'
        )
    obj = bpy.data.objects.new(name, None)
    obj.empty_display_type = 'CUBE'
    obj.empty_display_size = 1.0
    obj.display_type = 'WIRE'
    obj.color = (0.1, 0.65, 1.0, 1.0)
    collection.objects.link(obj)
    node_matrix = _instance_matrix(inst, scale_factor)
    obj.matrix_world = node_matrix

    compact_data = copy.deepcopy(data)
    compact_buffer = compact_data.get('buffer')
    if isinstance(compact_buffer, dict) and 'Bytes' in compact_buffer:
        compact_buffer['Bytes'] = (
            f'<{len(raw)} bytes sha1={digest}>' if raw else '<unavailable>'
            )

    assign_custom_properties(
        obj, data, sector_name, node_index,
        nodeDataIndex=inst['nodeDataIndex'], instance_idx=instance_index,
        interiorMapCoords=str(data.get('coords', '')),
        interiorMapVersion=int(data.get('version', 0) or 0),
        interiorMapBufferId=str(data.get('buffer', {}).get('BufferId', '')),
        interiorMapByteCount=len(raw),
        interiorMapWidth=width,
        interiorMapHeight=height,
        interiorMapSha1=digest,
        interiorMapImage=image.name if image is not None else '',
        interiorMapRepresentation='RASTER_IMAGE_METADATA_ONLY',
        )
    obj['interiorMapNodeData'] = _safe_json(compact_data)
    obj['nodeDataBounds'] = _safe_json(inst.get('Bounds', {}))
    obj['rasterNonZeroCount'] = sum(1 for value in raw if value)
    obj['rasterUniqueValueCount'] = len(set(raw))
    return obj


def _vector_from_xyz(value, default=(0.0, 0.0, 0.0)):
    if not isinstance(value, dict):
        return Vector(default)
    return Vector(
        (
            float(_axis_value(value, 'X', default[0])),
            float(_axis_value(value, 'Y', default[1])),
            float(_axis_value(value, 'Z', default[2])),
            )
        )


def _bounds_mesh(name, bounds):
    if not isinstance(bounds, dict):
        return None
    minimum = _vector_from_xyz(bounds.get('Min'))
    maximum = _vector_from_xyz(bounds.get('Max'))
    if any(maximum[index] < minimum[index] for index in range(3)):
        return None
    x0, y0, z0 = minimum
    x1, y1, z1 = maximum
    vertices = [
        (x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
        (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1),
        ]
    faces = [
        (0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
        (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7),
        ]
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    return mesh


def _create_minimap_data_marker(data, node_index, inst, instance_index, sector_name, collection, asset_index):
    resource = _depot_path(data, 'encodedShapesRef')
    resolved = _resolve_optional_resource(asset_index, resource)
    _warn_missing_resource(resource, resolved or '', required=False, context=f'{sector_name}: minimap data node {node_index}')
    name = _trim_name(
        f'MinimapData_{_cname_value(data.get("debugName"), str(node_index))}_{instance_index}'
        )
    mesh = _bounds_mesh(name, data.get('localBounds'))
    if mesh is None:
        _sector_warning(f'{sector_name}: minimap data node {node_index} has invalid localBounds')
    obj = bpy.data.objects.new(name, mesh)
    if mesh is None:
        obj.empty_display_type = 'CUBE'
        obj.empty_display_size = 1.0
    collection.objects.link(obj)
    node_matrix = _instance_matrix(inst, scale_factor)
    obj.matrix_world = node_matrix
    obj.display_type = 'WIRE'
    obj.color = (0.05, 0.75, 1.0, 1.0)
    obj.show_wire = mesh is not None
    assign_custom_properties(
        obj, data, sector_name, node_index,
        nodeDataIndex=inst['nodeDataIndex'], instance_idx=instance_index,
        encodedShapesRef=resource, resolvedEncodedShapes=resolved or '',
        allInteriorShapes=bool(data.get('allInteriorShapes', 0)),
        streamingDistance=float(data.get('streamingDistance', 0.0) or 0.0),
        minimapRepresentation='EXACT_LOCAL_BOUNDS_RESOURCE_MARKER',
        )
    obj['minimapLocalBounds'] = _safe_json(data.get('localBounds', {}))
    obj['minimapNodeData'] = _safe_json(data)
    return obj


def _create_light_channel_shape(data, node_index, inst, instance_index, sector_name, collection):
    shape = data.get('shape', {}).get('Data', {})
    source_vertices = shape.get('vertices', []) if isinstance(shape, dict) else []
    indices = shape.get('indices', []) if isinstance(shape, dict) else []
    vertices = [
        (
            float(_axis_value(vertex, 'X')),
            float(_axis_value(vertex, 'Y')),
            float(_axis_value(vertex, 'Z')),
            )
        for vertex in source_vertices if isinstance(vertex, dict)
        ]
    faces = []
    invalid_indices = 0
    for offset in range(0, len(indices) - 2, 3):
        try:
            face = tuple(int(indices[offset + step]) for step in range(3))
        except (TypeError, ValueError):
            invalid_indices += 1
            continue
        if any(index < 0 or index >= len(vertices) for index in face):
            invalid_indices += 1
            continue
        faces.append(face)
    if len(indices) % 3:
        invalid_indices += len(indices) % 3
    if not vertices or not faces:
        _sector_warning(f'{sector_name}: light channel shape node {node_index} has no usable mesh')
        return None
    name = _trim_name(f'LightChannelShape_{node_index}_{instance_index}')
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)
    node_matrix = _instance_matrix(inst, scale_factor)
    obj.matrix_world = node_matrix
    obj.display_type = 'WIRE'
    obj.color = (0.75, 0.2, 1.0, 1.0)
    obj.show_wire = True
    assign_custom_properties(
        obj, data, sector_name, node_index,
        nodeDataIndex=inst['nodeDataIndex'], instance_idx=instance_index,
        lightChannels=str(data.get('channels', '')),
        streamingDistanceFactor=float(data.get('streamingDistanceFactor', 0.0) or 0.0),
        shapeVertexCount=len(vertices), shapeTriangleCount=len(faces),
        invalidShapeIndices=invalid_indices,
        )
    shape_digest = hashlib.sha1(_safe_json(shape).encode('utf-8')).hexdigest()
    obj['shapeDataSha1'] = shape_digest
    if invalid_indices:
        _sector_warning(f'{sector_name}: light channel shape node {node_index} skipped {invalid_indices} invalid indices')
    return obj


def _create_semantic_marker(data, node_index, inst, instance_index, sector_name, collection, contract, color, display_type='SPHERE', display_size=0.5, asset_index=None, resource_keys=(), extra_props=None):
    resource = _depot_path(data, *resource_keys) if resource_keys else ''
    resolved = _resolve_optional_resource(asset_index, resource) if asset_index is not None and resource else None
    if resource:
        _warn_missing_resource(resource, resolved or '', required=False, context=f"{sector_name}: {data['$type']} node {node_index}")
    name = _trim_name(
        f'{data["$type"]}_{_cname_value(data.get("debugName"), str(node_index))}_{instance_index}'
        )
    obj = bpy.data.objects.new(name, None)
    obj.empty_display_type = display_type
    obj.empty_display_size = float(display_size)
    obj.display_type = 'WIRE'
    obj.color = color
    collection.objects.link(obj)
    node_matrix = _instance_matrix(inst, scale_factor)
    obj.matrix_world = node_matrix
    properties = {
        'nodeDataIndex': inst['nodeDataIndex'],
        'instance_idx': instance_index,
        'semanticRepresentation': contract,
        }
    if resource:
        properties['assetDepotPath'] = resource
        properties['resolvedAssetPath'] = resolved or ''
    if extra_props:
        properties.update(extra_props)
    assign_custom_properties(obj, data, sector_name, node_index, **properties)
    return obj


def _instanced_occluder_matrix(record):
    if not isinstance(record, dict):
        raise TypeError('occluder buffer entry must be a dictionary')
    columns = []
    for key in ('Unknown1', 'Unknown2', 'Unknown3', 'Unknown4'):
        column = record.get(key)
        if not isinstance(column, dict):
            raise ValueError(f'occluder buffer entry has no {key}')
        columns.append(column)
    x_axis, y_axis, z_axis, translation = columns
    return Matrix(
        (
            (
                float(_axis_value(x_axis, 'X', 1.0)),
                float(_axis_value(y_axis, 'X')),
                float(_axis_value(z_axis, 'X')),
                float(_axis_value(translation, 'X')),
                ),
            (
                float(_axis_value(x_axis, 'Y')),
                float(_axis_value(y_axis, 'Y', 1.0)),
                float(_axis_value(z_axis, 'Y')),
                float(_axis_value(translation, 'Y')),
                ),
            (
                float(_axis_value(x_axis, 'Z')),
                float(_axis_value(y_axis, 'Z')),
                float(_axis_value(z_axis, 'Z', 1.0)),
                float(_axis_value(translation, 'Z')),
                ),
            (0.0, 0.0, 0.0, 1.0),
            )
        )


def _binary_digest(encoded):
    if not encoded:
        return b'', ''
    try:
        raw = base64.b64decode(encoded, validate=False)
    except (ValueError, TypeError):
        return b'', ''
    return raw, hashlib.sha1(raw).hexdigest()


def _create_collision_metadata_marker(data, node_index, inst, instance_index, sector_name, collection):
    node_type = data['$type']
    name = _trim_name(f'{node_type}_{node_index}_{instance_index}')
    mesh = None
    if node_type == 'worldFoliageDestructionNode':
        extents = _vector_from_xyz(data.get('extents'))
        bounds = {
            'Min': {'X': -extents.x, 'Y': -extents.y, 'Z': -extents.z},
            'Max': {'X': extents.x, 'Y': extents.y, 'Z': extents.z},
            }
        mesh = _bounds_mesh(name, bounds)
    obj = bpy.data.objects.new(name, mesh)
    if mesh is None:
        obj.empty_display_type = 'CUBE'
        obj.empty_display_size = 1.0
    collection.objects.link(obj)
    node_matrix = _instance_matrix(inst, scale_factor)
    obj.matrix_world = node_matrix
    obj.display_type = 'WIRE'
    obj.color = (0.85, 0.25, 0.05, 1.0)
    obj.show_wire = mesh is not None
    assign_custom_properties(
        obj, data, sector_name, node_index,
        nodeDataIndex=inst['nodeDataIndex'], instance_idx=instance_index,
        collisionRepresentation='METADATA_ONLY_NO_PHYSX_ACTOR',
        )
    compact = copy.deepcopy(data)
    byte_count = 0
    digest = ''
    if node_type == 'worldTerrainCollisionNode':
        geometry = compact.get('heightfieldGeometry', {})
        encoded = geometry.get('Bytes', '') if isinstance(geometry, dict) else ''
        raw, digest = _binary_digest(encoded)
        byte_count = len(raw)
        if isinstance(geometry, dict) and 'Bytes' in geometry:
            geometry['Bytes'] = f'<{byte_count} bytes sha1={digest}>' if raw else '<unavailable>'
        obj['heightfieldByteCount'] = byte_count
        obj['heightfieldSha1'] = digest
        obj['rowScale'] = float(data.get('rowScale', 0.0) or 0.0)
        obj['columnScale'] = float(data.get('columnScale', 0.0) or 0.0)
        obj['heightScale'] = float(data.get('heightScale', 0.0) or 0.0)
        obj['terrainActorTransform'] = _safe_json(data.get('actorTransform', {}))
        semantic = 'collisionMetadata:terrainHeightfield'
    else:
        compiled = compact.get('compiledData', {})
        encoded_compiled = _safe_json(compiled).encode('utf-8') if compiled else b''
        digest = hashlib.sha1(encoded_compiled).hexdigest() if encoded_compiled else ''
        byte_count = len(encoded_compiled)
        compact['compiledData'] = (
            f'<json bytes={byte_count} sha1={digest}>' if encoded_compiled else '<unavailable>'
            )
        obj['compiledDataByteCount'] = byte_count
        obj['compiledDataSha1'] = digest
        obj['populationIndex'] = list(data.get('populationIndex', []))
        semantic = 'collisionMetadata:foliageDestruction'
    obj['collisionNodeData'] = _safe_json(compact)
    return obj

def _create_spline_object(data, node_index, inst, instance_index, sector_name, collection):
    spline_data = data.get('splineData', {}).get('Data', {})
    points = spline_data.get('points', [])
    if not points:
        _sector_warning(f'{sector_name}: spline node {node_index} contains no points')
        return None
    node_type = data['$type']
    name = _trim_name(f'{node_type}_{node_index}_{instance_index}')
    curve = bpy.data.curves.new(name, 'CURVE')
    curve.dimensions = '3D'
    curve.twist_mode = 'Z_UP'
    curve.resolution_u = 24
    curve_obj = bpy.data.objects.new(name, curve)
    collection.objects.link(curve_obj)
    node_matrix = _instance_matrix(inst, scale_factor)
    curve_obj.matrix_world = node_matrix
    spline = curve.splines.new('BEZIER')
    spline.use_cyclic_u = bool(spline_data.get('looped', 0))
    spline.bezier_points.add(len(points) - 1)
    point_metadata = []
    for point_index, point in enumerate(points):
        point_pos = Vector(get_pos(point))
        tangents = get_tan_pos(point.get('tangents', {}))
        bezier = spline.bezier_points[point_index]
        bezier.co = point_pos
        bezier.handle_left_type = 'FREE'
        bezier.handle_right_type = 'FREE'
        bezier.handle_right = point_pos + Vector(tangents[0])
        bezier.handle_left = point_pos + Vector(tangents[1])
        point_metadata.append({
            'rotation': point.get('rotation', {}),
            'automaticTangents': point.get('automaticTangents', 0),
            'continuousTangents': point.get('continuousTangents', 0),
            'id': point.get('id', 0),
            })
    assign_custom_properties(
        curve_obj, data, sector_name, node_index, nodeDataIndex=inst['nodeDataIndex'],
        instance_idx=instance_index, splinePointCount=len(points),
        splineLooped=bool(spline_data.get('looped', 0)), splineHasDirection=bool(spline_data.get('hasDirection', 0)),
        entrySnappedNode=_cname_value(data.get('entrySnapedNode')),
        entrySnappedSocket=_cname_value(data.get('entrySnapedSocketName')),
        destSnappedNode=_cname_value(data.get('destSnapedNode')),
        destSnappedSocket=_cname_value(data.get('destSnapedSocketName')),
        )
    curve_obj['splinePointMetadata'] = _safe_json(point_metadata)
    if node_type == 'worldSpeedSplineNode':
        curve_obj['speedChangeSections'] = _safe_json(data.get('speedChangeSections', []))
        curve_obj['orientationChangeSections'] = _safe_json(data.get('orientationChangeSections', []))
        curve_obj['roadAdjustmentFactorChangeSections'] = _safe_json(data.get('roadAdjustmentFactorChangeSections', []))
        curve_obj['deprecatedSpeedRestrictions'] = _safe_json(data.get('deprecatedSpeedRestrictions', []))
        curve_obj['useDeprecated'] = bool(data.get('useDeprecated', 0))
        curve_obj['ignoreTerrain'] = bool(data.get('ignoreTerrain', 0))
    return curve_obj


def _animate_rotation_root(rotation_root, axis_name, full_rotation_time, reverse_direction):
    axis_index = {'X': 0, 'Y': 1, 'Z': 2}.get(str(axis_name).upper(), 2)
    seconds = max(float(full_rotation_time or 0.0), 1.0 / 24.0)
    fps = float(bpy.context.scene.render.fps) / max(float(bpy.context.scene.render.fps_base), 1e-8)
    end_frame = 1 + max(1, round(seconds * fps))
    direction = -1.0 if bool(reverse_direction) else 1.0

    rotation_root.rotation_mode = 'XYZ'
    rotation_root.rotation_euler = (0.0, 0.0, 0.0)
    rotation_root.keyframe_insert('rotation_euler', index=axis_index, frame=1)
    rotation_root.rotation_euler[axis_index] = direction * math.tau
    rotation_root.keyframe_insert('rotation_euler', index=axis_index, frame=end_frame)

    action = rotation_root.animation_data.action if rotation_root.animation_data else None
    if action is None:
        return
    try:
        channelbag = anim_utils.action_get_channelbag_for_slot(action, rotation_root.animation_data.action_slot)
        fcurves = channelbag.fcurves
    except Exception:
        fcurves = getattr(action, 'fcurves', ())
    for fcurve in fcurves:
        if fcurve.data_path != 'rotation_euler' or fcurve.array_index != axis_index:
            continue
        for point in fcurve.keyframe_points:
            point.interpolation = 'LINEAR'
        if not any(modifier.type == 'CYCLES' for modifier in fcurve.modifiers):
            modifier = fcurve.modifiers.new(type='CYCLES')
            modifier.mode_before = 'REPEAT'
            modifier.mode_after = 'REPEAT'


def _decal_color_scale(data):
    color = data.get('diffuseColorScale', {}) if isinstance(data, dict) else {}
    return (
        float(color.get('Red', 1.0)),
        float(color.get('Green', 1.0)),
        float(color.get('Blue', 1.0)),
        float(color.get('Alpha', 1.0)),
        )


def _decal_color(data):
    color = _decal_color_scale(data)
    return (*color[:3], color[3] * float(data.get('alpha', 1.0)))


def _decal_material_signature(material_path, data):
    color = _decal_color(data)
    return (
        _path_key(material_path),
        *(round(value, 6) for value in color),
        round(float(data.get('roughnessScale', 1.0)), 6),
        bool(data.get('horizontalFlip', 0)),
        bool(data.get('verticalFlip', 0)),
        bool(data.get('isStretchingEnabled', 0)),
        int(data.get('orderNo', 0)),
        )


def _set_decal_uvs(mesh, horizontal_flip=False, vertical_flip=False):
    uv_layer = mesh.uv_layers.get('UVMap') or mesh.uv_layers.new(name='UVMap')
    for polygon in mesh.polygons:
        for loop_index in polygon.loop_indices:
            vertex = mesh.vertices[mesh.loops[loop_index].vertex_index].co
            u = vertex.x + 0.5
            v = vertex.y + 0.5
            if horizontal_flip:
                u = 1.0 - u
            if vertical_flip:
                v = 1.0 - v
            uv_layer.data[loop_index].uv = (u, v)


def _configure_decal_render_state(material):
    if hasattr(material, 'surface_render_method'):
        try:
            material.surface_render_method = 'DITHERED'
        except (TypeError, ValueError):
            pass
    if hasattr(material, 'blend_method'):
        try:
            material.blend_method = 'HASHED'
        except (TypeError, ValueError):
            pass
    material['no_shadows'] = True


def _decal_alpha_factor_present(alpha_socket, sector_alpha, tolerance=1e-6):
    if alpha_socket is None or not getattr(alpha_socket, 'is_linked', False):
        return False
    links = list(getattr(alpha_socket, 'links', ()))
    if len(links) != 1:
        return False
    source_node = getattr(links[0], 'from_node', None)
    if (
            source_node is None
            or getattr(source_node, 'bl_idname', '') != 'ShaderNodeMath'
            or getattr(source_node, 'operation', '') != 'MULTIPLY'
            ):
        return False
    for socket in list(getattr(source_node, 'inputs', ()))[:2]:
        if getattr(socket, 'is_linked', False):
            continue
        try:
            if math.isclose(float(socket.default_value), sector_alpha, abs_tol=tolerance):
                return True
        except (TypeError, ValueError):
            continue
    return False


def _apply_sector_decal_alpha(material, sector_alpha):
    if not material.use_nodes or material.node_tree is None:
        return 'NO_NODE_TREE'

    tree = material.node_tree
    alpha_sockets = []
    for node in tree.nodes:
        if getattr(node, 'bl_idname', '') != 'ShaderNodeBsdfPrincipled':
            continue
        alpha_socket = node.inputs.get('Alpha')
        if alpha_socket is not None:
            alpha_sockets.append(alpha_socket)

    if not alpha_sockets:
        return 'NO_PRINCIPLED_ALPHA'

    modes = []
    for alpha_socket in alpha_sockets:
        if _decal_alpha_factor_present(alpha_socket, sector_alpha):
            modes.append('HANDLER')
            continue

        links = list(alpha_socket.links)
        if links:
            source_socket = links[0].from_socket
            for link in links:
                tree.links.remove(link)
            alpha_multiply = tree.nodes.new('ShaderNodeMath')
            alpha_multiply.name = 'CP77 Sector Decal Alpha'
            alpha_multiply.label = 'CP77 Sector Decal Alpha'
            alpha_multiply.operation = 'MULTIPLY'
            alpha_multiply.inputs[1].default_value = sector_alpha
            alpha_multiply.location = (
                alpha_socket.node.location.x - 220.0,
                alpha_socket.node.location.y - 260.0,
                )
            tree.links.new(source_socket, alpha_multiply.inputs[0])
            tree.links.new(alpha_multiply.outputs[0], alpha_socket)
            modes.append('POST_MULTIPLY')
        else:
            try:
                alpha_socket.default_value = float(alpha_socket.default_value) * sector_alpha
            except (TypeError, ValueError):
                alpha_socket.default_value = sector_alpha
            modes.append('SOCKET_DEFAULT')

    unique_modes = sorted(set(modes))
    return '+'.join(unique_modes)


def _apply_decal_material_overrides(material, data):
    color_scale = _decal_color_scale(data)
    display_color = _decal_color(data)
    sector_alpha = float(data.get('alpha', 1.0))
    material.diffuse_color = display_color
    material['cp77Alpha'] = sector_alpha
    material['cp77DiffuseColorScale'] = list(color_scale)
    material['cp77RoughnessScale'] = float(data.get('roughnessScale', 1.0))
    material['cp77HorizontalFlip'] = bool(data.get('horizontalFlip', 0))
    material['cp77VerticalFlip'] = bool(data.get('verticalFlip', 0))
    material['cp77StretchingEnabled'] = bool(data.get('isStretchingEnabled', 0))
    material['cp77OrderNo'] = int(data.get('orderNo', 0))
    _configure_decal_render_state(material)

    if not material.use_nodes or material.node_tree is None:
        material['cp77SectorAlphaMode'] = 'NO_NODE_TREE'
        return

    values = {
        'diffusecolorscale': color_scale,
        'roughnessscale': float(data.get('roughnessScale', 1.0)),
        }
    for node in material.node_tree.nodes:
        for socket in getattr(node, 'inputs', ()):
            key = socket.name.replace(' ', '').replace('_', '').lower()
            if key not in values or not hasattr(socket, 'default_value'):
                continue
            try:
                socket.default_value = values[key]
            except (TypeError, ValueError):
                pass

    material['cp77SectorAlphaMode'] = _apply_sector_decal_alpha(
        material, sector_alpha
        )
    material['cp77SectorAlphaApplied'] = True


def _place_copied_mesh_instances(*, data, node_entry, node_index, instances, sector_name, sector_collection, masters, meshname, mesh_appearance, resolved_path, contract, color=(0.3, 0.3, 0.3, 1), rotating=False, extra_props=None):
    node_type = data['$type']
    group, groupname = get_group(meshname, mesh_appearance, masters, resolved_path)
    if group is None:
        message = f'Mesh not found in masters - {meshname} - {node_index} - {node_entry.get("HandleId", "")}'
        print(message)
        _sector_warning(f'{sector_name}: {message}')
        return []

    placed = []
    for instance_index, inst in enumerate(instances):
        node_matrix = _instance_matrix(inst, scale_factor)
        prefix = {
            'worldRotatingMeshNode': 'ROT',
            'worldPhysicalDestructionNode': 'PDEST',
            'worldBakedDestructionNode': 'BDEST',
            }.get(node_type, 'MESH')
        instance_name = _trim_name(
            f'{prefix}_{inst["nodeDataIndex"]}_{groupname}'
            )
        new, placement_root, rotation_root = _copy_collection_tree_with_placement_root(
            group, instance_name, node_matrix, color=color, hide_armatures=True, rotating=rotating
            )
        properties = {
            'nodeDataIndex': inst['nodeDataIndex'],
            'instance_idx': instance_index,
            'mesh': meshname,
            'pivot': inst.get('Pivot', {}),
            'meshAppearance': mesh_appearance,
            'appearanceName': mesh_appearance,
            }
        if extra_props:
            properties.update(extra_props)
        assign_custom_properties(new, data, sector_name, node_index, **properties)
        assign_custom_properties(placement_root, data, sector_name, node_index, **properties)
        new['matrix'] = _matrix_values(node_matrix)
        placement_root['matrix'] = _matrix_values(node_matrix)
        sector_collection.children.link(new)
        placed.append((new, placement_root, rotation_root, inst, instance_index))
    return placed

DEFORMATION_AXIS_CONTRACTS = {
    'worldBendedMeshNode': (1, 1.0, 'POS_Y'),
    'worldCableMeshNode': (0, -1.0, 'NEG_X'),
    }


def _deformation_records(data):
    records = data.get('deformationData', []) if isinstance(data, dict) else []
    if isinstance(records, dict):
        for key in ('Data', 'Matrices', 'Elements', 'entries'):
            candidate = records.get(key)
            if isinstance(candidate, list):
                records = candidate
                break
    return records if isinstance(records, list) else []


def _deformation_matrix(record):
    if not isinstance(record, dict):
        raise TypeError('deformation frame must be a dictionary')
    source = record.get('Properties') if isinstance(record.get('Properties'), dict) else record
    columns = []
    for column_name in ('X', 'Y', 'Z', 'W'):
        column = source.get(column_name)
        if not isinstance(column, dict):
            column = source.get(column_name.lower())
        if not isinstance(column, dict):
            raise ValueError(f'deformation frame has no {column_name} column')
        columns.append(column)
    x_axis, y_axis, z_axis, translation = columns
    return Matrix(
        (
            (
                float(_axis_value(x_axis, 'X', 1.0)),
                float(_axis_value(y_axis, 'X')),
                float(_axis_value(z_axis, 'X')),
                float(_axis_value(translation, 'X')),
                ),
            (
                float(_axis_value(x_axis, 'Y')),
                float(_axis_value(y_axis, 'Y', 1.0)),
                float(_axis_value(z_axis, 'Y')),
                float(_axis_value(translation, 'Y')),
                ),
            (
                float(_axis_value(x_axis, 'Z')),
                float(_axis_value(y_axis, 'Z')),
                float(_axis_value(z_axis, 'Z', 1.0)),
                float(_axis_value(translation, 'Z')),
                ),
            (0.0, 0.0, 0.0, 1.0),
            )
        )


def _deformation_frame_metrics(records, frames, axis_index):
    normalized_homogeneous_frames = 0
    for record in records:
        if not isinstance(record, dict):
            continue
        source = record.get('Properties') if isinstance(record.get('Properties'), dict) else record
        columns = [source.get(name, source.get(name.lower(), {})) for name in ('X', 'Y', 'Z', 'W')]
        if not all(isinstance(column, dict) for column in columns):
            continue
        x_axis, y_axis, z_axis, translation = columns
        if (
                abs(float(_axis_value(x_axis, 'W'))) > 1e-8
                or abs(float(_axis_value(y_axis, 'W'))) > 1e-8
                or abs(float(_axis_value(z_axis, 'W'))) > 1e-8
                or abs(float(_axis_value(translation, 'W', 1.0)) - 1.0) > 1e-8
                ):
            normalized_homogeneous_frames += 1

    translations = [frame.to_translation() for frame in frames]
    spans = [0.0, 0.0, 0.0]
    if translations:
        for component in range(3):
            values = [float(location[component]) for location in translations]
            spans[component] = max(values) - min(values)
    dominant_axis = max(range(3), key=lambda component: spans[component]) if translations else axis_index
    axis_values = [float(location[axis_index]) for location in translations]
    steps = [axis_values[index + 1] - axis_values[index] for index in range(len(axis_values) - 1)]
    monotonic = (
        all(step >= -1e-6 for step in steps)
        or all(step <= 1e-6 for step in steps)
        )
    return {
        'normalizedHomogeneousFrames': normalized_homogeneous_frames,
        'dominantAxisIndex': dominant_axis,
        'dominantAxisSpan': float(spans[dominant_axis]) if spans else 0.0,
        'contractAxisSpan': float(spans[axis_index]) if spans else 0.0,
        'contractAxisMin': min(axis_values) if axis_values else 0.0,
        'contractAxisMax': max(axis_values) if axis_values else 0.0,
        'minimumFrameStep': min((abs(step) for step in steps), default=0.0),
        'maximumFrameStep': max((abs(step) for step in steps), default=0.0),
        'monotonicContractAxis': monotonic,
        }


def _deformation_frames(data, sector_name, node_index):
    frames = []
    for frame_index, record in enumerate(_deformation_records(data)):
        try:
            frames.append(_deformation_matrix(record))
        except (TypeError, ValueError, KeyError) as error:
            _sector_warning(f'{sector_name}: node {node_index} deformation frame {frame_index} is invalid: {error}')
    if len(frames) < 2:
        _sector_warning(f'{sector_name}: node {node_index} contains {len(frames)} usable deformation frames; at least two are required')
    return frames


def _collection_axis_bounds(collection, axis_index):
    lower = float('inf')
    upper = float('-inf')
    vertex_count = 0
    for obj in collection.all_objects:
        if obj.type != 'MESH' or obj.data is None:
            continue
        source_matrix = obj.matrix_world
        for vertex in obj.data.vertices:
            coordinate = float((source_matrix @ vertex.co)[axis_index])
            lower = min(lower, coordinate)
            upper = max(upper, coordinate)
            vertex_count += 1
    return lower, upper, vertex_count


def _interpolate_deformation_frame(frames, factor):
    if len(frames) == 1:
        return frames[0].decompose()
    position = max(0.0, min(1.0, float(factor))) * (len(frames) - 1)
    frame_index = min(int(math.floor(position)), len(frames) - 2)
    blend = position - frame_index
    location_a, rotation_a, scale_a = frames[frame_index].decompose()
    location_b, rotation_b, scale_b = frames[frame_index + 1].decompose()
    return (
        location_a.lerp(location_b, blend),
        rotation_a.slerp(rotation_b, blend),
        scale_a.lerp(scale_b, blend),
        )


def _deform_content_point(point, frames, axis_index, axis_sign, axis_min, axis_max):
    span = axis_max - axis_min
    if abs(span) <= 1e-8:
        return point.copy()
    coordinate = float(point[axis_index])
    factor = (
        (coordinate - axis_min) / span
        if axis_sign > 0.0 else
        (axis_max - coordinate) / span
        )
    location, rotation, scale = _interpolate_deformation_frame(frames, factor)
    cross_section = point.copy()
    cross_section[axis_index] = 0.0
    scaled_cross_section = Vector(
        (
            cross_section.x * scale.x,
            cross_section.y * scale.y,
            cross_section.z * scale.z,
            )
        )
    return location + rotation @ scaled_cross_section


def _deform_mesh_copy(old_obj, new_obj, frames, axis_index, axis_sign, axis_min, axis_max):
    source_matrix = old_obj.matrix_world.copy()
    inverse_source = source_matrix.inverted_safe()

    def deform_coordinate(coordinate):
        content_point = source_matrix @ coordinate
        deformed_point = _deform_content_point(
            content_point, frames, axis_index, axis_sign, axis_min, axis_max
            )
        return inverse_source @ deformed_point

    shape_keys = getattr(new_obj.data, 'shape_keys', None)
    if shape_keys is not None and shape_keys.key_blocks:
        for key_block in shape_keys.key_blocks:
            for point in key_block.data:
                point.co = deform_coordinate(point.co)
        basis = shape_keys.key_blocks[0]
        for vertex_index, vertex in enumerate(new_obj.data.vertices):
            vertex.co = basis.data[vertex_index].co
    else:
        for vertex in new_obj.data.vertices:
            vertex.co = deform_coordinate(vertex.co)
    new_obj.data.update()


def _create_deformation_path(
        name, frames, target_collection, placement_root, cable_radius=0.0, render_geometry=False
        ):
    curve = bpy.data.curves.new(_trim_name(f'{name}_Path'), 'CURVE')
    curve.dimensions = '3D'
    curve.twist_mode = 'MINIMUM'
    curve.resolution_u = 1
    spline = curve.splines.new('POLY')
    spline.points.add(len(frames) - 1)
    for frame_index, frame in enumerate(frames):
        location = frame.to_translation()
        spline.points[frame_index].co = (*location, 1.0)
    if render_geometry and cable_radius > 0.0:
        curve.bevel_depth = float(cable_radius)
        curve.bevel_resolution = 2
        curve.resolution_u = 2
        curve.fill_mode = 'FULL'
    path_obj = bpy.data.objects.new(curve.name, curve)
    target_collection.objects.link(path_obj)
    path_obj.parent = placement_root
    path_obj.matrix_parent_inverse = Matrix.Identity(4)
    path_obj.matrix_basis = Matrix.Identity(4)
    path_obj.display_type = 'WIRE'
    path_obj.hide_render = not render_geometry
    path_obj.show_in_front = True
    path_obj['deformationFrameCount'] = len(frames)
    return path_obj


def _copy_deformed_collection(
        src_collection, name, node_matrix, frames, axis_index, axis_sign, axis_min, axis_max,
        color=None, hide_armatures=True
        ):
    dst_root = bpy.data.collections.new(_trim_name(name))
    copy_map = {}

    def copy_into(src, dst):
        for child in src.children:
            child_dst = bpy.data.collections.new(child.name)
            dst.children.link(child_dst)
            copy_into(child, child_dst)
        for old_obj in src.objects:
            obj = _copy_object(old_obj, color=color, hide_armature=hide_armatures)
            if obj.type == 'MESH' and obj.data is not None:
                obj.data = old_obj.data.copy()
            copy_map[old_obj] = obj
            dst.objects.link(obj)

    copy_into(src_collection, dst_root)
    _remap_copied_object_references(tuple(copy_map.values()), copy_map)

    placement_root = _new_empty(f'{name}_Placement', dst_root)
    placement_root.matrix_world = node_matrix
    content_root = _new_empty(f'{name}_Content', dst_root)
    content_root.parent = placement_root
    content_root.matrix_parent_inverse = Matrix.Identity(4)
    content_root.matrix_basis = Matrix.Identity(4)

    for old_obj, obj in copy_map.items():
        if old_obj.parent in copy_map:
            continue
        obj.parent = content_root
        obj.matrix_parent_inverse = Matrix.Identity(4)
        obj.matrix_basis = old_obj.matrix_world.copy()

    for old_obj, obj in copy_map.items():
        if obj.type == 'MESH' and obj.data is not None:
            _deform_mesh_copy(
                old_obj, obj, frames, axis_index, axis_sign, axis_min, axis_max
                )
    return dst_root, placement_root


def _place_deformed_mesh_instances(*, data, node_entry, node_index, instances, sector_name, sector_collection, masters, meshname, mesh_appearance, resolved_path):
    node_type = data['$type']
    axis_index, axis_sign, axis_name = DEFORMATION_AXIS_CONTRACTS[node_type]
    records = _deformation_records(data)
    frames = _deformation_frames(data, sector_name, node_index)
    frame_metrics = _deformation_frame_metrics(records, frames, axis_index)
    if (
            len(frames) >= 2
            and frame_metrics['dominantAxisSpan'] > 1e-6
            and frame_metrics['dominantAxisIndex'] != axis_index
            ):
        _sector_warning(f"{sector_name}: node {node_index} deformation frames move primarily along {'XYZ'[frame_metrics['dominantAxisIndex']]} but {node_type} expects {axis_name}")
    if len(frames) >= 2 and not frame_metrics['monotonicContractAxis']:
        _sector_warning(f'{sector_name}: node {node_index} deformation frames are not monotonic along {axis_name}')
    group, groupname = get_group(meshname, mesh_appearance, masters, resolved_path)
    axis_min = axis_max = 0.0
    vertex_count = 0
    if group is not None:
        axis_min, axis_max, vertex_count = _collection_axis_bounds(group, axis_index)
        if vertex_count == 0 or abs(axis_max - axis_min) <= 1e-8:
            _sector_warning(f'{sector_name}: node {node_index} source mesh has no usable {axis_name} longitudinal span')
    else:
        _sector_warning(f"{sector_name}: deformation mesh not found in masters: {meshname} - node {node_index} - {node_entry.get('HandleId', '')}")

    placed = []
    for instance_index, inst in enumerate(instances):
        node_matrix = _instance_matrix(inst, scale_factor)
        instance_name = _trim_name(
            f'{"BEND" if node_type == "worldBendedMeshNode" else "CABLE"}_{inst["nodeDataIndex"]}_{groupname or node_index}'
            )
        can_deform = group is not None and len(frames) >= 2 and vertex_count > 0 and abs(axis_max - axis_min) > 1e-8
        if can_deform:
            collection, placement_root = _copy_deformed_collection(
                group, instance_name, node_matrix, frames, axis_index, axis_sign, axis_min, axis_max,
                color=(0.0380098, 0.595213, 0.600022, 1), hide_armatures=True
                )
        else:
            collection = bpy.data.collections.new(instance_name)
            placement_root = _new_empty(f'{instance_name}_Placement', collection)
            placement_root.matrix_world = node_matrix

        cable_radius = float(data.get('cableRadius', 0.0) or 0.0)
        path_obj = None
        if frames:
            path_obj = _create_deformation_path(
                instance_name, frames, collection, placement_root,
                cable_radius=cable_radius,
                render_geometry=node_type == 'worldCableMeshNode' and not can_deform
                )
        properties = {
            'nodeDataIndex': inst['nodeDataIndex'],
            'instance_idx': instance_index,
            'mesh': meshname,
            'meshAppearance': mesh_appearance,
            'deformationAxis': axis_name,
            'deformationFrameCount': len(frames),
            'deformationSourceVertexCount': vertex_count,
            'deformationSourceAxisMin': float(axis_min),
            'deformationSourceAxisMax': float(axis_max),
            'deformationFrameAxisMin': frame_metrics['contractAxisMin'],
            'deformationFrameAxisMax': frame_metrics['contractAxisMax'],
            'deformationMinimumFrameStep': frame_metrics['minimumFrameStep'],
            'deformationMaximumFrameStep': frame_metrics['maximumFrameStep'],
            'deformationFramesMonotonic': frame_metrics['monotonicContractAxis'],
            'deformationDominantAxis': 'XYZ'[frame_metrics['dominantAxisIndex']],
            'deformationNormalizedHomogeneousFrames': frame_metrics['normalizedHomogeneousFrames'],
            'isBendedRoad': bool(data.get('isBendedRoad', 0)),
            'deformedBox': _safe_json(data.get('deformedBox', {})),
            }
        if node_type == 'worldCableMeshNode':
            properties.update({
                'cableLength': float(data.get('cableLength', 0.0) or 0.0),
                'cableRadius': cable_radius,
                'destructionHashes': _safe_json(data.get('destructionHashes', [])),
                })
        assign_custom_properties(collection, data, sector_name, node_index, **properties)
        assign_custom_properties(placement_root, data, sector_name, node_index, **properties)
        if path_obj is not None:
            assign_custom_properties(path_obj, data, sector_name, node_index, **properties)
        collection['deformationContract'] = 'FRAME_MATRIX_VERTEX_BAKE'
        deformation_payload = _safe_json(data.get('deformationData', []))
        collection['deformationDataDigest'] = hashlib.sha1(
            deformation_payload.encode('utf-8')
            ).hexdigest()
        if frames:
            collection['deformationFirstFrame'] = _matrix_values(frames[0])
            collection['deformationLastFrame'] = _matrix_values(frames[-1])
        sector_collection.children.link(collection)
        placed.append((collection, placement_root, path_obj))
    return placed


def _foliage_population_matrix(pop_info):
    rot = Quaternion(get_rot(pop_info))
    if sum(float(component) * float(component) for component in rot) <= 1e-12:
        rot = Quaternion((1.0, 0.0, 0.0, 0.0))
    else:
        rot.normalize()
    return Matrix.LocRotScale(
        Vector(get_pos(pop_info)), rot, Vector(get_scale(pop_info))
        )


def _integer_field(data, *keys, default=0):
    if not isinstance(data, dict):
        return int(default)
    for key in keys:
        if key not in data:
            continue
        value = data[key]
        if isinstance(value, dict):
            value = value.get('$value', value.get('Value', value.get('value', default)))
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return int(default)


def _foliage_resource_data(foliage_json):
    root = foliage_json.get('Data', {}).get('RootChunk', {}) if isinstance(foliage_json, dict) else {}
    buffer_data = root.get('dataBuffer', {}).get('Data', {})
    if isinstance(buffer_data.get('Data'), dict):
        buffer_data = buffer_data['Data']

    def as_list(value):
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            for key in ('Data', 'Elements', 'items'):
                if isinstance(value.get(key), list):
                    return value[key]
        return []

    buckets = as_list(buffer_data.get('Buckets'))
    populations = as_list(buffer_data.get('Populations'))
    declared_bucket_count = _integer_field(root, 'bucketCount', 'BucketCount', default=len(buckets))
    declared_population_count = _integer_field(
        root, 'populationCount', 'PopulationCount', default=len(populations)
        )
    bucket_population_count = sum(
        max(0, _integer_field(bucket, 'PopulationCount', 'populationCount'))
        for bucket in buckets
        )
    return {
        'buckets': buckets,
        'populations': populations,
        'declaredBucketCount': declared_bucket_count,
        'declaredPopulationCount': declared_population_count,
        'bucketPopulationCount': bucket_population_count,
        'version': _integer_field(root, 'version', 'Version'),
        }


def _validate_foliage_resource(resource_data, sector_name, resource_name):
    buckets = resource_data['buckets']
    populations = resource_data['populations']
    declared_buckets = resource_data['declaredBucketCount']
    declared_populations = resource_data['declaredPopulationCount']
    bucket_population_count = resource_data['bucketPopulationCount']

    if declared_buckets != len(buckets):
        _sector_warning(f'{sector_name}: foliage resource {resource_name} declares {declared_buckets} buckets but contains {len(buckets)}')
    if declared_populations != len(populations):
        _sector_warning(f'{sector_name}: foliage resource {resource_name} declares {declared_populations} populations but contains {len(populations)}')
    if bucket_population_count != len(populations):
        _sector_warning(f'{sector_name}: foliage resource {resource_name} bucket counts total {bucket_population_count}, expected {len(populations)}')


def _foliage_population_is_active(population):
    if not isinstance(population, dict):
        return False
    scale = population.get('Scale', population.get('scale', 1.0))
    if isinstance(scale, dict):
        values = get_scale(population)
        return all(math.isfinite(value) and value > 0.0 for value in values)
    try:
        value = float(scale)
    except (TypeError, ValueError):
        return False
    return math.isfinite(value) and value > 0.0


def _foliage_population_indices(span, buckets, populations, sector_name, node_index):
    bucket_begin = _integer_field(span, 'bucketBegin', 'BucketBegin', 'cketBegin')
    bucket_count = _integer_field(span, 'bucketCount', 'BucketCount', 'cketCount')
    instances_begin = _integer_field(span, 'instancesBegin', 'InstancesBegin', 'stancesBegin')
    instances_count = _integer_field(span, 'instancesCount', 'InstancesCount', 'stancesCount')
    node_end = instances_begin + max(0, instances_count)

    if bucket_begin < 0 or bucket_count < 0 or instances_begin < 0 or instances_count < 0:
        _sector_warning(f'{sector_name}: foliage node {node_index} has a negative population span: {span}')
        return [], (bucket_begin, bucket_count, instances_begin, instances_count)

    bucket_end = bucket_begin + bucket_count
    if bucket_end > len(buckets):
        _sector_warning(f'{sector_name}: foliage node {node_index} requests buckets[{bucket_begin}:{bucket_end}] from {len(buckets)} buckets')

    selected = []
    seen_populations = set()
    seen_relative = set()
    for bucket_index in range(bucket_begin, min(bucket_end, len(buckets))):
        bucket = buckets[bucket_index]
        relative_start = _integer_field(bucket, 'PopulationSubIndex', 'populationSubIndex')
        population_count = _integer_field(bucket, 'PopulationCount', 'populationCount')
        if relative_start < 0 or population_count < 0:
            _sector_warning(f'{sector_name}: foliage node {node_index} bucket {bucket_index} has a negative population span')
            continue

        relative_end = relative_start + population_count
        population_start = instances_begin + relative_start
        population_end = population_start + population_count
        clipped_start = max(instances_begin, population_start, 0)
        clipped_end = min(node_end, population_end, len(populations))
        if relative_end > instances_count or population_end > len(populations):
            _sector_warning(f'{sector_name}: foliage node {node_index} bucket {bucket_index} population range [{population_start}:{population_end}] was clipped to [{clipped_start}:{clipped_end}]')

        for relative_index in range(
                clipped_start - instances_begin,
                max(clipped_start - instances_begin, clipped_end - instances_begin)
                ):
            if relative_index in seen_relative:
                _sector_warning(f'{sector_name}: foliage node {node_index} relative population {relative_index} occurs in overlapping buckets')
                continue
            seen_relative.add(relative_index)
            population_index = instances_begin + relative_index
            if population_index in seen_populations:
                _sector_warning(f'{sector_name}: foliage node {node_index} population {population_index} occurs in overlapping buckets')
                continue
            seen_populations.add(population_index)
            selected.append((bucket_index, population_index, relative_index))

    expected_relative = set(range(instances_count))
    missing_relative = expected_relative - seen_relative
    extra_relative = seen_relative - expected_relative
    if missing_relative or extra_relative:
        _sector_warning(f'{sector_name}: foliage node {node_index} bucket-relative population partition is incomplete: missing={len(missing_relative)}, extra={len(extra_relative)}')
    if len(selected) != instances_count:
        _sector_warning(f'{sector_name}: foliage node {node_index} span declares {instances_count} populations but {len(selected)} unique populations were resolved from its buckets')

    selected.sort(key=lambda item: item[2])
    return selected, (bucket_begin, bucket_count, instances_begin, instances_count)


def _set_collection_props(collection, data, sector_name, node_index, inst=None, **kwargs):
    if inst is None:
        assign_custom_properties(collection, data, sector_name, node_index, **kwargs)
    else:
        assign_custom_properties(
            collection, data, sector_name, node_index, ndi=inst.get('nodeDataIndex'), pivot=inst.get('Pivot'), **kwargs
            )


def _copy_object(old_obj, color=None, hide_armature=True):
    obj = old_obj.copy()
    if color is not None:
        obj.color = color
    if hide_armature and 'Armature' in obj.name:
        obj.hide_viewport = True
        obj.hide_render = True
    return obj


def _copy_collection_tree(src_collection, name, transform=None, color=None, hide_armatures=True):
    dst_root = bpy.data.collections.new(_trim_name(name))
    copy_map = {}

    def copy_into(src, dst):
        for child in src.children:
            child_dst = bpy.data.collections.new(child.name)
            dst.children.link(child_dst)
            copy_into(child, child_dst)
        for old_obj in src.objects:
            obj = _copy_object(old_obj, color=color, hide_armature=hide_armatures)
            copy_map[old_obj] = obj
            dst.objects.link(obj)

    copy_into(src_collection, dst_root)

    _remap_copied_object_references(tuple(copy_map.values()), copy_map)

    if transform is not None:
        for old_obj, obj in copy_map.items():
            if old_obj.parent not in copy_map:
                obj.matrix_world = transform @ old_obj.matrix_world

    return dst_root


def _collection_instance_object(name, collection, target_collection, matrix=None, color=None):
    obj = bpy.data.objects.new(_trim_name(name), None)
    obj.empty_display_type = 'PLAIN_AXES'
    obj.empty_display_size = 0.25
    obj.instance_type = 'COLLECTION'
    obj.instance_collection = collection
    if color is not None:
        obj.color = color
    target_collection.objects.link(obj)
    if matrix is not None:
        obj.matrix_world = matrix
        obj['matrix'] = matrix
    return obj


_IDPROP_INT_MIN = -(1 << 31)
_IDPROP_INT_MAX = (1 << 31) - 1


def _id_property_safe_value(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        if _IDPROP_INT_MIN <= value <= _IDPROP_INT_MAX:
            return value
        return str(value)
    if isinstance(value, dict):
        return {
            str(key): _id_property_safe_value(item)
            for key, item in value.items()
            }
    if isinstance(value, tuple):
        value = list(value)
    if isinstance(value, list):
        return [_id_property_safe_value(item) for item in value]
    return value


def _assign_id_property(obj, key, value):
    safe_value = _id_property_safe_value(value)
    try:
        obj[key] = safe_value
        return
    except (OverflowError, TypeError, ValueError):
        pass

    try:
        obj[key] = _safe_json(value)
    except (OverflowError, TypeError, ValueError):
        obj[key] = str(value)


def assign_custom_properties(obj, data, sectorName, i, **kwargs):
    ntype = data['$type']
    _assign_id_property(obj, 'nodeType', ntype)
    _assign_id_property(obj, 'nodeIndex', i)
    if 'debugName' in data:
        _assign_id_property(obj, 'debugName', data['debugName']['$value'])
    _assign_id_property(obj, 'sectorName', sectorName)
    if 'sourcePrefabHash' in data:
        _assign_id_property(obj, 'sourcePrefabHash', data['sourcePrefabHash'])
    if ntype == 'worldAISpotNode':
        if data['spot']:
            _assign_id_property(
                obj,
                'workspot',
                data['spot']['Data']['resource']['DepotPath']['$value'],
                )
        else:
            _assign_id_property(obj, 'workspot', 'None')
        if data['markings']:
            _assign_id_property(obj, 'markings', data['markings'][0]['$value'])
    if 'entityTemplate' in data:
        _assign_id_property(
            obj,
            'entityTemplate',
            data['entityTemplate']['DepotPath']['$value'],
            )

    if 'appearanceName' in data:
        appearance_name = data['appearanceName']['$value']
    elif 'meshAppearance' in data:
        appearance_name = data['meshAppearance']['$value']
    else:
        appearance_name = ''
    _assign_id_property(obj, 'appearanceName', appearance_name)

    for key, value in kwargs.items():
        _assign_id_property(obj, key, value)


def find_debugName(obj):
    debugName = None
    if 'debugName' in obj.users_collection[0]:
        debugName = obj.users_collection[0]['debugName']
    else:
        if 'debugName' in D.collections[coll_parents.get(obj.users_collection[0].name)]:
            debugName = D.collections[coll_parents.get(obj.users_collection[0].name)]['debugName']
        else:
            if 'debugName' in D.collections[coll_parents.get(coll_parents.get(obj.users_collection[0].name.name))]:
                debugName = D.collections[coll_parents.get(coll_parents.get(obj.users_collection[0].name.name))][
                    'debugName']
    return debugName


def get_pos_whole(inst):
    pos = [0, 0, 0]
    if 'Position' in inst:
        if 'Properties' in inst['Position']:
            pos[0] = inst['Position']['Properties']['X']
            pos[1] = inst['Position']['Properties']['Y']
            pos[2] = inst['Position']['Properties']['Z']
        else:
            pos[0] = inst['Position']['X']
            pos[1] = inst['Position']['Y']
            pos[2] = inst['Position']['Z']
    elif 'position' in inst:
        pos[0] = inst['position']['X']
        pos[1] = inst['position']['Y']
        pos[2] = inst['position']['Z']
    return pos


def get_col(color):
    col = [0, 0, 0]
    col[0] = color['Red'] / 255
    col[1] = color['Green'] / 255
    col[2] = color['Blue'] / 255
    return col


def get_tan_pos(inst):
    pos = [[0, 0, 0], [0, 0, 0]]
    if 'Elements' in inst:
        pos[0][0] = inst['Elements'][0]['X']
        pos[0][1] = inst['Elements'][0]['Y']
        pos[0][2] = inst['Elements'][0]['Z']
        pos[1][0] = inst['Elements'][1]['X']
        pos[1][1] = inst['Elements'][1]['Y']
        pos[1][2] = inst['Elements'][1]['Z']
    return pos


def get_meshappearance(data):
    if 'meshAppearance' in data:
        meshAppearance = data['meshAppearance']
    else:
        meshAppearance = {'$type': 'CName', '$storage': 'string', '$value': 'default'}
    return meshAppearance


def get_meshname(data, include_entity_template=True):
    keys = ('mesh', 'meshRef', 'entityTemplate') if include_entity_template else ('mesh', 'meshRef')
    return _depot_path(data, *keys)


def importSectors(
        filepath,
        with_mats,
        remap_depot=False,
        want_collisions=False,
        am_modding=False,
        with_lights=False,
        selected_variant=None,
        import_proxies=False,
        import_acoustics=False,
        import_occluders=False,
        import_minimap=False,
        import_environment_probes=False,
        import_gi=False,
        ):
    initiated_cache = False
    if not JSONTool._use_cache:
        clear_material_cache()
        JSONTool.start_caching()
        initiated_cache = True
    try:
        return _importSectors_cached(
            filepath,
            with_mats,
            remap_depot,
            want_collisions,
            am_modding,
            with_lights,
            selected_variant,
            import_proxies,
            import_acoustics,
            import_occluders,
            import_minimap,
            import_environment_probes,
            import_gi,
            )
    finally:
        if initiated_cache:
            JSONTool.stop_caching()
            clear_material_cache()


def _importSectors_cached(
        filepath,
        with_mats,
        remap_depot,
        want_collisions,
        am_modding,
        with_lights,
        selected_variant,
        import_proxies,
        import_acoustics,
        import_occluders,
        import_minimap,
        import_environment_probes,
        import_gi,
        ):
    if selected_variant is not None:
        try:
            selected_variant = int(selected_variant)
        except (TypeError, ValueError):
            print(f'Invalid selected_variant {selected_variant!r}; importing all variants')
            selected_variant = None
    cp77_addon_prefs = bpy.context.preferences.addons['i_scene_cp77_gltf'].preferences
    if not cp77_addon_prefs.non_verbose:
        print('')
        print('-------------------- Importing Cyberpunk 2077 Streaming Sectors --------------------')
        print('')
    start_time = time.time()
    # Set this to true to limit import to the types listed in the import_types list.
    limittypes = False
    import_types = None
    # import_types=['worldEntityNode'    ]
    wkit_proj_name = os.path.basename(filepath)
    # Enter the path to your projects source\raw\base folder below, needs double slashes between folder names.
    raw_root = os.path.join(os.path.dirname(filepath), 'source', 'raw')
    print('path is ', raw_root)
    project = os.path.dirname(filepath)
    project_name = os.path.basename(project)
    optional_imports = _optional_sector_imports(
        import_proxies=import_proxies,
        import_acoustics=import_acoustics,
        import_occluders=import_occluders,
        import_minimap=import_minimap,
        import_environment_probes=import_environment_probes,
        import_gi=import_gi,
        )

    # A sector import is a user-facing operation boundary: rescan so exports created since
    # the last import are visible; per-entity imports inside the batch reuse this index.
    asset_index = DepotAssetIndex.cached(
        raw_root,
        _sector_index_extensions(optional_imports),
        force_refresh=True,
        )
    # If your importing to edit the sectors and want to add stuff then set the am_modding to True and it will auto create the _new collectors
    # want_collisions when True will import/generate the box and capsule collisions

    if scale_factor == 1:
        # Set the view clip to 10000 so you can actually see the models were imported (used to scale down by 100)
        for a in bpy.context.screen.areas:
            if a.type == 'VIEW_3D':
                for s in a.spaces:
                    if s.type == 'VIEW_3D':
                        s.clip_end = 50000
    props = bpy.context.scene.cp77_panel_props
    sector_jsons = _indexed_files(asset_index, '.streamingsector.json')
    mesh_jsons = _indexed_files(asset_index, '.mesh.json')
    anim_files = _indexed_files(asset_index, '.anims.glb')
    app_path = _indexed_files(asset_index, '.app.json')
    rigjsons = _indexed_files(asset_index, '.rig.json')
    glbs = _indexed_files(asset_index, *MESH_GLB_EXTENSIONS)
    base_path = os.path.join(raw_root, 'base')
    raw_path = raw_root
    meshes = {}
    C = bpy.context
    I_want_to_break_free = False
    sector_entries = _sector_entries(sector_jsons, base_path, project_name, asset_index)
    # Use object wireframe colors not theme - doesnt work need to find hte viewport as the context doesnt return that for this call
    # bpy.context.space_data.shading.wireframe_color_type = 'OBJECT'
    for sector_entry in sector_entries:
        filepath = sector_entry['filepath']
        nodes = sector_entry['nodes']
        sectorName = sector_entry['sectorName']
        if VERBOSE:
            print(os.path.join(base_path, project_name + '.streamingsector.json'))
        # print(len(nodes))
        # nodes=[]

        for i, e in enumerate(nodes):
            # print(i)
            data = e['Data']
            ntype = data['$type']
            if I_want_to_break_free:
                break
            if not _should_import_sector_node(data, optional_imports):
                continue
            if (
                    limittypes and ntype in import_types) or limittypes == False:  # or type=='worldCableMeshNode': # can add a filter for dev here
                meshname = get_meshname(data, include_entity_template=False)
                if _skip_disabled_gi_helper(meshname, optional_imports):
                    continue
                meshAppearance = get_meshappearance(data)
                match ntype:
                    case 'worldEntityNode' | 'worldDeviceNode':
                        # print('worldEntityNode',i)
                        if meshname:
                            if meshname not in meshes:
                                meshes[meshname] = {'appearances': [meshAppearance], 'sector': sectorName}
                            else:
                                meshes[meshname]['appearances'].append(meshAppearance)

                    case 'worldInstancedMeshNode':
                        if meshname:
                            if meshname not in meshes:
                                meshes[meshname] = {'appearances': [meshAppearance], 'sector': sectorName}
                            else:
                                meshes[meshname]['appearances'].append(meshAppearance)

                    case 'worldStaticMeshNode' | 'worldRotatingMeshNode' | 'worldAdvertisingNode' | 'worldAdvertisementNode' | 'worldPhysicalDestructionNode' | 'worldBakedDestructionNode' \
                         | 'worldTerrainMeshNode' | 'worldBendedMeshNode' | 'worldCableMeshNode' | 'worldClothMeshNode' | 'worldDynamicMeshNode' \
                         | 'worldMeshNode' | 'worldStaticOccluderMeshNode' | 'worldDecorationMeshNode' | 'worldFoliageNode' \
                         | 'worldWaterPatchNode' | 'worldInstancedOccluderNode':
                        if isinstance(e, dict) and 'mesh' in data and isinstance(data['mesh'], dict) and 'DepotPath' in \
                                data['mesh']:
                            # if ntype=='worldBendedMeshNode':
                            #    print('worldBendedMeshNode',i)
                            # print('Mesh name is - ',meshname, e['HandleId'])
                            # print('Mesh - ',meshname, ' - ',i, e['HandleId'])
                            if meshname not in meshes:
                                meshes[meshname] = {'appearances': [meshAppearance], 'sector': sectorName}
                            else:
                                meshes[meshname]['appearances'].append(meshAppearance)

                        elif isinstance(e, dict) and 'meshRef' in data:
                            if meshname:
                                # print('Mesh - ',meshname, ' - ',i, e['HandleId'])
                                if meshname not in meshes:
                                    meshes[meshname] = {
                                        'appearances': [{'$type': 'CName', '$storage': 'string', '$value': 'default'}],
                                        'sector': sectorName}
                                else:
                                    meshes[meshname]['appearances'].append(
                                            {'$type': 'CName', '$storage': 'string', '$value': 'default'}
                                            )

                    case 'worldInstancedDestructibleMeshNode':
                        # print('worldInstancedDestructibleMeshNode',i)
                        if isinstance(e, dict) and 'mesh' in data:
                            # print('Mesh name is - ',meshname, e['HandleId'])
                            if meshname:
                                if meshname not in meshes:
                                    meshes[meshname] = {'appearances': [meshAppearance], 'sector': sectorName}
                                else:
                                    meshes[meshname]['appearances'].append(meshAppearance)

        # Do the proxy nodes after all the others, that way none proxies will be imported first and wont be hidden by the proxy ones
        for i, e in enumerate(nodes):
            data = e['Data']
            ntype = data['$type']
            if I_want_to_break_free:
                break
            if not _should_import_sector_node(data, optional_imports):
                continue
            if (
                    limittypes and ntype in import_types) or limittypes == False:  # or type=='worldCableMeshNode': # can add a filter for dev here
                match ntype:
                    case 'worldGenericProxyMeshNode' | 'worldEntityProxyMeshNode' | 'worldTerrainProxyMeshNode' | 'worldDestructibleEntityProxyMeshNode' | 'worldDestructibleProxyMeshNode' | 'worldBuildingProxyMeshNode' | 'worldRoadProxyMeshNode':
                        if isinstance(e, dict) and 'mesh' in data and isinstance(data['mesh'], dict) and 'DepotPath' in \
                                data['mesh']:
                            meshname = _depot_path(data, 'mesh')
                            if meshname:
                                if 'meshAppearance' in e['Data']:
                                    if meshname not in meshes:
                                        meshes[meshname] = {'appearances': [e['Data']['meshAppearance']],
                                                            'sector': sectorName}
                                    else:
                                        meshes[meshname]['appearances'].append(e['Data']['meshAppearance'])
                                else:
                                    if meshname not in meshes:
                                        meshes[meshname] = {'appearances': [
                                            {'$type': 'CName', '$storage': 'string', '$value': 'default'}],
                                                            'sector': sectorName}
                                    else:
                                        meshes[meshname]['appearances'].append(
                                                {'$type': 'CName', '$storage': 'string', '$value': 'default'}
                                                )
                        elif isinstance(e, dict) and 'meshRef' in data:
                            meshname = _depot_path(data, 'meshRef')
                            if meshname:
                                if meshname not in meshes:
                                    meshes[meshname] = {
                                        'appearances': [{'$type': 'CName', '$storage': 'string', '$value': 'default'}],
                                        'sector': sectorName}
                                else:
                                    meshes[meshname]['appearances'].append(
                                            {'$type': 'CName', '$storage': 'string', '$value': 'default'}
                                            )

    basenames = {}
    for m in meshes:
        if m not in basenames:
            basenames[m] = True

    meshes_w_apps = {}
    mesh_source_paths = {}

    for meshname, mesh_data in meshes.items():
        if not meshname:
            continue
        meshpath = _resolve_indexed_glb(asset_index, meshname)
        if meshpath:
            mesh_data['meshpath'] = meshpath
            mesh_source_paths[meshname] = meshpath
        else:
            print(f'Mesh export not indexed: {meshname}')
        add_to_list(meshname, meshes, meshes_w_apps)

    coll_scene = C.scene.collection
    mis = {}
    entity_master_cache = {}
    foliage_cache = {}
    if "MasterInstances" not in coll_scene.children:
        coll_target = bpy.data.collections.new("MasterInstances")
        coll_scene.children.link(coll_target)
    else:
        coll_target = bpy.data.collections.get("MasterInstances")

    Masters = coll_target
    Masters.hide_viewport = False  # if its hidden it breaks entity positioning for some reason?!?

    # could take this out but its useful in edge cases.
    from_mesh_no = 0
    to_mesh_no = 100000

    meshes_from_mesheswapps(
        meshes_w_apps, raw_path, from_mesh_no=from_mesh_no, to_mesh_no=to_mesh_no, with_mats=with_mats, glbs=glbs,
        mesh_jsons=mesh_jsons, Masters=Masters
        )

    empty = []
    for child in Masters.children:
        if len(child.objects) < 1:
            empty.append(child)

    for failed in empty:
        Masters.children.unlink(failed)
    inst_pos = (0, 0, 0)
    inst_rot = Quaternion((0.707, 0, .707, 0))
    inst_scale = Vector((1, 1, 1))
    inst_m = Matrix.LocRotScale(inst_pos, inst_rot, inst_scale)
    no_sectors = len(sector_entries)
    sector_collections = {}
    for fpn, sector_entry in enumerate(sector_entries):
        filepath = sector_entry['filepath']
        t = sector_entry['nodeData']
        nodes = sector_entry['nodes']
        instances_by_node = sector_entry['instances_by_node']
        nodes_by_handle = sector_entry['nodes_by_handle']
        world_transform_buffers = sector_entry['world_transform_buffers']
        cooked_transform_buffers = sector_entry['cooked_transform_buffers']
        projectjson = os.path.join(base_path, project_name + '.streamingsector.json')
        if VERBOSE:
            print(projectjson)
            print(filepath)

        numExpectedNodes = len(t)
        sectorName = sector_entry['sectorName']

        Sector_coll = _sector_collection_for_entry(
            coll_scene, sector_entry, sector_collections
            )
        Sector_coll['filepath'] = filepath
        Sector_coll['expectedNodes'] = numExpectedNodes
        Sector_coll['sectorCategory'] = str(sector_entry.get('category', ''))
        Sector_coll['sectorLevel'] = int(sector_entry.get('level', 0))
        Sector_coll['sourceKind'] = str(sector_entry.get('sourceKind', 'root'))
        Sector_coll['parentSector'] = str(sector_entry.get('parentSector', ''))
        Sector_coll['parentSectorPath'] = str(sector_entry.get('parentSectorPath', ''))
        Sector_coll['compositionParents'] = _safe_json(sector_entry.get('compositionParents', []))
        Sector_coll['compositionParentPaths'] = _safe_json(sector_entry.get('compositionParentPaths', []))
        Sector_coll['compositionDepth'] = int(sector_entry.get('compositionDepth', 0))
        Sector_coll['sourceDepotPath'] = str(sector_entry.get('sourceDepotPath', ''))
        Sector_coll['sectorName'] = sectorName
        Sector_coll['inplaceDepotPaths'] = _safe_json(sector_entry.get('inplaceDepotPaths', []))
        Sector_coll['resolvedInplacePaths'] = _safe_json(sector_entry.get('resolvedInplacePaths', []))
        Sector_coll['inplaceResolvedCount'] = len(sector_entry.get('resolvedInplacePaths', []))
        Sector_coll['variantImportMode'] = 'SELECTED_VISIBLE' if selected_variant is not None else 'ALL_GROUPED'
        Sector_coll['selectedVariant'] = int(selected_variant) if selected_variant is not None else -1
        Sector_coll['importProxies'] = optional_imports['proxies']
        Sector_coll['importAcoustics'] = optional_imports['acoustics']
        Sector_coll['importOccluders'] = optional_imports['occluders']
        Sector_coll['importMinimapData'] = optional_imports['minimap']
        Sector_coll['importEnvironmentProbes'] = optional_imports['environment_probes']
        Sector_coll['importGIData'] = optional_imports['gi']
        Sector_coll['proxyDisplayMode'] = 'SEPARATE_COLLECTIONS'
        for composition_issue in sector_entry.get('compositionIssues', []):
            _sector_warning(composition_issue)

        if am_modding == True:
            if sectorName + '_new' in coll_scene.children:
                Sector_additions_coll = bpy.data.collections.get(sectorName + '_new')
            else:
                Sector_additions_coll = bpy.data.collections.new(sectorName + '_new')
                coll_scene.children.link(Sector_additions_coll)

        print(
            fpn, ' Processing ', len(nodes), ' nodes for sector', sectorName, '(no ', fpn + 1, ' of ', no_sectors, ')'
            )
        group = ''
        for i, e in enumerate(nodes):

            # if i % 20==0:
            #   continue
            data = e['Data']
            ntype = data['$type']
            if not _should_import_sector_node(data, optional_imports):
                continue
            mesh_appearance_value = data.get('meshAppearance', 'default')
            meshAppearance = (
                mesh_appearance_value.get('$value', 'default')
                if isinstance(mesh_appearance_value, dict)
                else (mesh_appearance_value or 'default')
                )
            if _skip_disabled_gi_helper(
                    get_meshname(data, include_entity_template=False),
                    optional_imports,
                    ):
                continue
            if (
                    limittypes and ntype in import_types) or limittypes == False:  # or type=='worldCableMeshNode': # can add a filter for dev here
                match ntype:
                    case 'worldAISpotNode':
                        instances = instances_by_node.get(i, [])
                        print('worldAISpotNode', i)
                        for idx, inst in enumerate(instances):
                            node_matrix = _instance_matrix(inst, scale_factor)
                            o = bpy.data.objects.new("empty", None)
                            assign_custom_properties(
                                o, data, sectorName, i, instance_idx=idx,
                                nodeDataIndex=inst['nodeDataIndex']
                                )
                            o.empty_display_size = 0.2
                            o.empty_display_type = 'CONE'
                            Sector_coll.objects.link(o)
                            o.name = ntype + '_' + data['debugName']['$value']
                            o.matrix_world = node_matrix

                    case 'worldEntityNode' | 'worldDeviceNode':
                        instances = instances_by_node.get(i, [])
                        appearance_value = data.get('appearanceName', 'default')
                        app = (
                            appearance_value.get('$value', 'default')
                            if isinstance(appearance_value, dict)
                            else (appearance_value or 'default')
                            )
                        ent_depot = _depot_path(data, 'entityTemplate')
                        entpath = _resolve_indexed_json(asset_index, ent_depot, '.ent.json')
                        if not entpath:
                            message = f"Entity template not indexed: {ent_depot}"
                            print(message)
                            _sector_warning(f'{sectorName}: node {i}: {message}')
                            continue

                        resolved_app = resolve_entity_appearance(entpath, app) or app
                        if resolved_app != app:
                            print(f"Entity appearance alias resolved: {app} -> {resolved_app}")
                        cache_key = _entity_master_key(entpath, resolved_app)
                        ent_groupnames = _entity_collection_candidates(entpath, app, resolved_app)
                        move_coll = entity_master_cache.get(cache_key)
                        if move_coll is None:
                            move_coll = _find_entity_master(
                                Masters, ent_depot, app, resolved_app, ent_groupnames
                                )
                        if move_coll is None:
                            try:
                                importEnt(
                                    with_mats, filepath=entpath, appearances=[app], inColl='MasterInstances', meshes=glbs,
                                    mesh_jsons=mesh_jsons, app_path=app_path, anim_files=anim_files, rigjsons=rigjsons,
                                    create_rig_bone_shapes=False,
                                    )
                                move_coll = _find_entity_master(
                                    Masters, ent_depot, app, resolved_app, ent_groupnames
                                    )
                            except Exception:
                                print(traceback.format_exc())
                                print(f"Failed during Entity import on {entpath} from app {app}")
                        if move_coll is None:
                            message = (
                                f"Imported entity collection not found for {ent_depot}@{resolved_app}; "
                                f"tried names: {', '.join(ent_groupnames)}"
                                )
                            print(message)
                            _sector_warning(f'{sectorName}: node {i}: {message}')
                            continue

                        entity_master_cache[cache_key] = move_coll
                        move_coll['sectorEntityMaster'] = True
                        move_coll['sectorEntityPath'] = ent_depot
                        move_coll['sectorEntityAppearance'] = resolved_app
                        identity = hashlib.sha1(
                            f'{_path_key(entpath)}|{resolved_app}'.encode('utf-8')
                            ).hexdigest()[:8]
                        for idx, inst in enumerate(instances):
                            node_matrix = _instance_matrix(inst, scale_factor)
                            instance_name = (
                                f'ENT_{inst["nodeDataIndex"]}_{os.path.basename(ent_depot).split(".")[0]}_{identity}'
                                )
                            new, placement_root, _ = _copy_collection_tree_with_placement_root(
                                move_coll, instance_name, node_matrix,
                                color=(0.567942, 0.0247339, 0.600028, 1), hide_armatures=True
                                )
                            assign_custom_properties(
                                new, data, sectorName, i, nodeDataIndex=inst['nodeDataIndex'],
                                instance_idx=idx, HandleId=e.get('HandleId', ''), pivot=inst.get('Pivot', {}),
                                entityTemplate=ent_depot, requestedAppearance=app,
                                resolvedAppearance=resolved_app
                                )
                            assign_custom_properties(
                                placement_root, data, sectorName, i,
                                nodeDataIndex=inst['nodeDataIndex'], instance_idx=idx,
                                entityTemplate=ent_depot, requestedAppearance=app,
                                resolvedAppearance=resolved_app
                                )
                            new['matrix'] = _matrix_values(node_matrix)
                            placement_root['matrix'] = _matrix_values(node_matrix)
                            Sector_coll.children.link(new)

                    case 'worldBendedMeshNode' | 'worldCableMeshNode':
                        meshname = _depot_path(data, 'mesh')
                        instances = instances_by_node.get(i, [])
                        if not meshname:
                            _sector_warning(f'{sectorName}: deformation node {i} has no mesh resource')
                            continue
                        _place_deformed_mesh_instances(
                            data=data, node_entry=e, node_index=i, instances=instances,
                            sector_name=sectorName, sector_collection=Sector_coll, masters=Masters,
                            meshname=meshname, mesh_appearance=meshAppearance,
                            resolved_path=mesh_source_paths.get(meshname, '')
                            )

                    case 'worldInstancedMeshNode':
                        meshname = _depot_path(data, 'mesh')
                        instances = instances_by_node.get(i, [])
                        source_inst = instances[0] if instances else None
                        if len(instances) > 1:
                            _sector_warning(f'{sectorName}: node {i} has {len(instances)} nodeData records, but worldTransformsBuffer entries are absolute and are emitted only once')
                        start, num, transform_buffer, transform_slice = _buffer_slice(
                            data, world_transform_buffers, 'worldTransformsBuffer',
                            sectorName, i
                            )
                        if not meshname:
                            _sector_warning(f'{sectorName}: node {i} has no mesh resource')
                            continue
                        group, groupname = get_group(
                            meshname, meshAppearance, Masters, mesh_source_paths.get(meshname, '')
                            )
                        if group is None:
                            message = f'Mesh not found in masters - {meshname} - {i} - {e.get("HandleId", "")}'
                            print(message)
                            _sector_warning(f'{sectorName}: {message}')
                            continue

                        node_data_index = source_inst.get('nodeDataIndex') if source_inst else None
                        source_node_matrix = (
                            _instance_matrix(source_inst, scale_factor) if source_inst is not None else None
                            )
                        NDI_Coll_name = _trim_name(f'NDI{i}_{groupname}')
                        NDI_Coll = bpy.data.collections.new(NDI_Coll_name)
                        Sector_coll.children.link(NDI_Coll)
                        props = {'mesh': meshname, 'numElements': num}
                        if node_data_index is not None:
                            props['nodeDataIndex'] = node_data_index
                        assign_custom_properties(NDI_Coll, data, sectorName, i, **props)

                        buffer_ref = _buffer_ref_id(data, 'worldTransformsBuffer')
                        for element_index, buffer_inst in transform_slice:
                            buffer_matrix = _world_buffer_matrix(buffer_inst, scale_factor)
                            empty_inst = _collection_instance_object(
                                f'NDI{i}_{element_index}_{groupname}', group, NDI_Coll,
                                buffer_matrix, color=(0.785188, 0.409408, 0.0430124, 1)
                                )
                            object_props = {'mesh': meshname, 'Element_idx': element_index}
                            if node_data_index is not None:
                                object_props['nodeDataIndex'] = node_data_index
                            assign_custom_properties(
                                empty_inst, data, sectorName, i, **object_props
                                )
                            if buffer_ref is not None:
                                empty_inst['bufferID'] = str(buffer_ref)

                    case 'worldInstancedOccluderNode':
                        instances = instances_by_node.get(i, [])
                        source_inst = instances[0] if instances else None
                        if len(instances) > 1:
                            _sector_warning(f'{sectorName}: instanced occluder node {i} has {len(instances)} nodeData records; embedded buffer matrices are absolute and are emitted once')
                        records = data.get('buffer', []) if isinstance(data.get('buffer'), list) else []
                        meshname = _depot_path(data, 'mesh')
                        if not meshname:
                            _sector_warning(f'{sectorName}: instanced occluder node {i} has no mesh')
                            continue
                        group, groupname = get_group(
                            meshname, meshAppearance, Masters, mesh_source_paths.get(meshname, '')
                            )
                        if group is None:
                            message = f'Mesh not found in masters - {meshname} - {i} - {e.get("HandleId", "")}'
                            print(message)
                            _sector_warning(f'{sectorName}: {message}')
                            continue
                        node_data_index = source_inst.get('nodeDataIndex') if source_inst else None
                        source_node_matrix = (
                            _instance_matrix(source_inst, scale_factor) if source_inst is not None else None
                            )
                        occluder_collection = bpy.data.collections.new(
                            _trim_name(f'InstancedOccluder_{i}_{groupname}')
                            )
                        Sector_coll.children.link(occluder_collection)
                        assign_custom_properties(
                            occluder_collection, data, sectorName, i,
                            mesh=meshname, numElements=len(records),
                            nodeDataIndex=node_data_index if node_data_index is not None else -1,
                            )
                        normalized_frames = 0
                        for element_index, record in enumerate(records):
                            try:
                                buffer_matrix = _instanced_occluder_matrix(record)
                            except (TypeError, ValueError) as error:
                                _sector_warning(f'{sectorName}: instanced occluder node {i} element {element_index} is invalid: {error}')
                                continue
                            columns = [record.get(key, {}) for key in ('Unknown1', 'Unknown2', 'Unknown3', 'Unknown4')]
                            if (
                                    any(abs(float(_axis_value(column, 'W'))) > 1e-8 for column in columns[:3])
                                    or abs(float(_axis_value(columns[3], 'W', 1.0)) - 1.0) > 1e-8
                                    ):
                                normalized_frames += 1
                            obj = _collection_instance_object(
                                f'InstancedOccluder_{i}_{element_index}_{groupname}',
                                group, occluder_collection, buffer_matrix,
                                color=(0.35, 0.15, 0.05, 1.0)
                                )
                            assign_custom_properties(
                                obj, data, sectorName, i,
                                mesh=meshname, Element_idx=element_index,
                                nodeDataIndex=node_data_index if node_data_index is not None else -1,
                                autohideDistanceScale=int(data.get('autohideDistanceScale', 0) or 0),
                                occluderType=str(data.get('occluderType', '')),
                                )
                        occluder_collection['normalizedHomogeneousFrames'] = normalized_frames

                    case 'worldFoliageNode':
                        instances = instances_by_node.get(i, [])
                        meshname = _depot_path(data, 'mesh')
                        foliage_resource = _depot_path(data, 'foliageResource')
                        foliage_path = _resolve_indexed_json(asset_index, foliage_resource, '.cfoliage.json')
                        _warn_missing_resource(foliage_resource, foliage_path or '', required=True, context=f'{sectorName}: foliage node {i}')
                        if not meshname:
                            _sector_warning(f'{sectorName}: foliage node {i} has no mesh resource')
                            continue
                        group, groupname = get_group(
                            meshname, meshAppearance, Masters, mesh_source_paths.get(meshname, '')
                            )
                        if group is None:
                            _sector_warning(f'{sectorName}: foliage mesh not found in masters: {meshname} - node {i}')
                            continue
                        if not foliage_path:
                            continue
                        foliage_key = _path_key(foliage_path)
                        if foliage_key not in foliage_cache:
                            resource_data = _foliage_resource_data(JSONTool.jsonload(foliage_path))
                            _validate_foliage_resource(
                                resource_data, sectorName, foliage_resource
                                )
                            foliage_cache[foliage_key] = resource_data
                        resource_data = foliage_cache[foliage_key]
                        buckets = resource_data['buckets']
                        populations = resource_data['populations']
                        population_indices, span_values = _foliage_population_indices(
                            data.get('populationSpanInfo', {}), buckets, populations,
                            sectorName, i
                            )
                        bucket_begin, bucket_count, instances_begin, instances_count = span_values
                        active_population_indices = []
                        inactive_population_indices = []
                        for bucket_index, population_index, relative_index in population_indices:
                            population = populations[population_index]
                            target = (
                                active_population_indices
                                if _foliage_population_is_active(population)
                                else inactive_population_indices
                                )
                            target.append((bucket_index, population_index, relative_index))

                        inactive_digest = hashlib.sha1(
                            ','.join(
                                str(population_index)
                                for _, population_index, _ in inactive_population_indices
                                ).encode('utf-8')
                            ).hexdigest() if inactive_population_indices else ''

                        for instance_index, inst in enumerate(instances):
                            node_matrix = _instance_matrix(inst, scale_factor)
                            collection_name = _trim_name(
                                f'WFI_{inst["nodeDataIndex"]}_{groupname}'
                                )
                            foliage_collection = bpy.data.collections.new(collection_name)
                            Sector_coll.children.link(foliage_collection)
                            assign_custom_properties(
                                foliage_collection, data, sectorName, i,
                                nodeDataIndex=inst['nodeDataIndex'], mesh=meshname,
                                foliageResource=foliage_resource, resolvedFoliagePath=foliage_path,
                                bucketBegin=bucket_begin, bucketCount=bucket_count,
                                instancesBegin=instances_begin, instancesCount=instances_count,
                                resolvedPopulationCount=len(population_indices),
                                emittedPopulationCount=len(active_population_indices),
                                inactivePopulationCount=len(inactive_population_indices),
                                inactivePopulationDigest=inactive_digest,
                                resourceBucketCount=len(buckets),
                                resourcePopulationCount=len(populations),
                                resourceDeclaredBucketCount=resource_data['declaredBucketCount'],
                                resourceDeclaredPopulationCount=resource_data['declaredPopulationCount'],
                                resourceVersion=resource_data['version']
                                )

                            for bucket_index, population_index, relative_index in active_population_indices:
                                population = populations[population_index]
                                population_matrix = _foliage_population_matrix(population)
                                final_matrix = node_matrix @ population_matrix
                                empty_inst = _collection_instance_object(
                                    f'WFI_{inst["nodeDataIndex"]}_{population_index}_{groupname}',
                                    group, foliage_collection, final_matrix, color=(0.0, 1.0, 0.0, 1)
                                    )
                                assign_custom_properties(
                                    empty_inst, data, sectorName, i,
                                    nodeDataIndex=inst['nodeDataIndex'], mesh=meshname,
                                    Element_idx=population_index, populationIndex=population_index,
                                    populationLocalIndex=relative_index, bucketIndex=bucket_index,
                                    populationScale=float(population.get('Scale', 1.0)),
                                    foliageResource=foliage_resource
                                    )

                    case 'XworldInstancedOccluderNode':
                        # print('worldInstancedOccluderNode')
                        pass

                    case 'worldStaticDecalNode':
                        instances = instances_by_node.get(i, [])
                        material_path = _depot_path(data, 'material')
                        for idx, inst in enumerate(instances):
                            node_matrix = _instance_matrix(inst, scale_factor)
                            projector = _new_empty(
                                f'DecalProjector_{i}_{inst["nodeDataIndex"]}', Sector_coll, display_size=0.2
                                )
                            projector.empty_display_type = 'CUBE'
                            projector.matrix_world = node_matrix

                            vertices = [
                                (-0.5, -0.5, 0.0),
                                (0.5, -0.5, 0.0),
                                (-0.5, 0.5, 0.0),
                                (0.5, 0.5, 0.0),
                                ]
                            faces = [(0, 1, 3, 2)]
                            mesh_data = bpy.data.meshes.new(f'DecalPlane_{i}_{idx}')
                            mesh_data.from_pydata(vertices, [], faces)
                            _set_decal_uvs(
                                mesh_data,
                                horizontal_flip=bool(data.get('horizontalFlip', 0)),
                                vertical_flip=bool(data.get('verticalFlip', 0)),
                                )
                            plane = bpy.data.objects.new(f'DecalPlane_{i}_{idx}', mesh_data)
                            Sector_coll.objects.link(plane)
                            plane.parent = projector
                            plane.matrix_parent_inverse = Matrix.Identity(4)
                            plane.matrix_basis = Matrix.Identity(4)
                            plane.color = _decal_color(data)

                            decal_props = {
                                'instance_idx': idx,
                                'nodeDataIndex': inst['nodeDataIndex'],
                                'decal': material_path,
                                'horizontalFlip': bool(data.get('horizontalFlip', 0)),
                                'verticalFlip': bool(data.get('verticalFlip', 0)),
                                'alpha': float(data.get('alpha', 1.0)),
                                'roughnessScale': float(data.get('roughnessScale', 1.0)),
                                'isStretchingEnabled': bool(data.get('isStretchingEnabled', 0)),
                                'orderNo': int(data.get('orderNo', 0)),
                                'normalThreshold': float(data.get('normalThreshold', 0.0)),
                                'enableNormalThreshold': bool(data.get('enableNormalTreshold', 0)),
                                'projectionDepth': float(get_scale(inst)[2]),
                                'projectionAxisLocal': 'Z',
                                }
                            assign_custom_properties(plane, data, sectorName, i, **decal_props)
                            assign_custom_properties(projector, data, sectorName, i, **decal_props)

                            resolved_material_path = ''
                            if with_mats and material_path:
                                expected_jsonpath = os.path.join(raw_path, _normalize_depot_path(material_path)) + '.json'
                                jsonpath = _resolve_indexed_json(asset_index, material_path, '.mi.json')
                                resolved_material_path = jsonpath or ''
                                try:
                                    if not jsonpath:
                                        raise FileNotFoundError(expected_jsonpath)
                                    material_document = copy.deepcopy(JSONTool.jsonload(jsonpath))
                                    signature = _decal_material_signature(material_path, data)
                                    bpymat = mis.get(signature)
                                    if bpymat is None and material_document:
                                        root_chunk = material_document.get('Data', {}).get('RootChunk', {})
                                        root_chunk['alpha'] = float(data.get('alpha', 1.0))
                                        root_chunk['diffuseColorScale'] = copy.deepcopy(
                                            data.get('diffuseColorScale', {})
                                            )
                                        root_chunk['roughnessScale'] = float(data.get('roughnessScale', 1.0))
                                        root_chunk['horizontalFlip'] = bool(data.get('horizontalFlip', 0))
                                        root_chunk['verticalFlip'] = bool(data.get('verticalFlip', 0))
                                        root_chunk['isStretchingEnabled'] = bool(
                                            data.get('isStretchingEnabled', 0)
                                            )
                                        builder = MaterialBuilder(material_document, raw_path, 'png', raw_path)
                                        built_material = builder.createdecal(0)
                                        if built_material is not None:
                                            bpymat = built_material.copy()
                                            suffix = hashlib.sha1(repr(signature).encode('utf-8')).hexdigest()[:8]
                                            bpymat.name = _trim_name(f'{built_material.name}_{suffix}', 63)
                                            _apply_decal_material_overrides(bpymat, data)
                                            mis[signature] = bpymat
                                    if bpymat is not None:
                                        plane.data.materials.append(bpymat)
                                    else:
                                        plane.display_type = 'WIRE'
                                except FileNotFoundError:
                                    missing_path = jsonpath or expected_jsonpath
                                    print(
                                        f'File not found {os.path.basename(missing_path)} ({missing_path}), '
                                        'you need to export .mi files'
                                        )
                                    _sector_warning(f'{sectorName}: decal node {i} material not found: {missing_path}')
                                    plane.display_type = 'WIRE'
                                except Exception as error:
                                    print(traceback.format_exc())
                                    _sector_warning(f'{sectorName}: decal node {i} material import failed: {error}')
                                    plane.display_type = 'WIRE'
                            else:
                                plane.display_type = 'WIRE'

                            if plane.display_type == 'WIRE':
                                plane.color = (1.0, 0.905, 0.062, 1.0)
                                plane.show_wire = True
                                plane.display.show_shadows = False


                    case 'worldSplineNode' | 'worldSpeedSplineNode':
                        instances = instances_by_node.get(i, [])
                        for idx, inst in enumerate(instances):
                            _create_spline_object(
                                data, i, inst, idx, sectorName, Sector_coll
                                )

                    case 'worldRoadProxyMeshNode':
                        meshname = _depot_path(data, 'mesh')
                        instances = instances_by_node.get(i, [])
                        if not meshname:
                            _sector_warning(f'{sectorName}: road proxy node {i} has no mesh resource')
                            continue
                        extra_props = {
                            'proxySemantic': True,
                            'proxyOwnerResolved': False,
                            'nearAutoHideDistance': float(data.get('nearAutoHideDistance', 0.0) or 0.0),
                            'forceAutoHideDistance': float(data.get('forceAutoHideDistance', 0.0) or 0.0),
                            'lodLevelScales': int(data.get('lodLevelScales', 0) or 0),
                            'occluderType': str(data.get('occluderType', '')),
                            'renderSceneLayerMask': str(data.get('renderSceneLayerMask', '')),
                            'nbNodesUnderProxy': int(data.get('nbNodesUnderProxy', 0) or 0),
                            'proxyData': _safe_json(data),
                            }
                        _place_copied_mesh_instances(
                            data=data, node_entry=e, node_index=i, instances=instances,
                            sector_name=sectorName, sector_collection=Sector_coll, masters=Masters,
                            meshname=meshname, mesh_appearance=meshAppearance,
                            resolved_path=mesh_source_paths.get(meshname, ''),
                            contract='ROAD_PROXY_MESH_NODE_WORLD',
                            extra_props=extra_props
                            )

                    case 'worldStaticMeshNode':
                        meshname = get_meshname(data, include_entity_template=False)
                        instances = instances_by_node.get(i, [])
                        if not meshname:
                            _sector_warning(f'{sectorName}: node {i} has no mesh resource')
                            continue
                        _place_copied_mesh_instances(
                            data=data, node_entry=e, node_index=i, instances=instances,
                            sector_name=sectorName, sector_collection=Sector_coll, masters=Masters,
                            meshname=meshname, mesh_appearance=meshAppearance,
                            resolved_path=mesh_source_paths.get(meshname, ''),
                            contract='STATIC_MESH_NODE_WORLD'
                            )

                    case 'worldRotatingMeshNode':
                        meshname = get_meshname(data, include_entity_template=False)
                        instances = instances_by_node.get(i, [])
                        if not meshname:
                            _sector_warning(f'{sectorName}: node {i} has no rotating mesh resource')
                            continue
                        placed = _place_copied_mesh_instances(
                            data=data, node_entry=e, node_index=i, instances=instances,
                            sector_name=sectorName, sector_collection=Sector_coll, masters=Masters,
                            meshname=meshname, mesh_appearance=meshAppearance,
                            resolved_path=mesh_source_paths.get(meshname, ''),
                            contract='ROTATING_MESH_PLACEMENT_ROOT',
                            rotating=True,
                            extra_props={
                                'rot_axis': data.get('rotationAxis', 'Z'),
                                'reverseDirection': bool(data.get('reverseDirection', 0)),
                                'fullRotationTime': float(data.get('fullRotationTime', 0.0)),
                                }
                            )
                        for new, placement_root, rotation_root, inst, instance_index in placed:
                            if rotation_root is None:
                                _sector_warning(f'{sectorName}: rotating node {i} did not create a rotation root')
                                continue
                            assign_custom_properties(
                                rotation_root, data, sectorName, i,
                                nodeDataIndex=inst['nodeDataIndex'], instance_idx=instance_index,
                                rotationAxis=data.get('rotationAxis', 'Z'),
                                reverseDirection=bool(data.get('reverseDirection', 0)),
                                fullRotationTime=float(data.get('fullRotationTime', 0.0))
                                )
                            rotation_root['rotationContract'] = 'LOCAL_AXIS_UNDER_PLACEMENT_ROOT'
                            _animate_rotation_root(
                                rotation_root,
                                data.get('rotationAxis', 'Z'),
                                data.get('fullRotationTime', 0.0),
                                data.get('reverseDirection', 0),
                                )

                    case 'worldPhysicalDestructionNode':
                        meshname = get_meshname(data, include_entity_template=False)
                        instances = instances_by_node.get(i, [])
                        if not meshname:
                            _sector_warning(f'{sectorName}: node {i} has no physical destruction mesh')
                            continue
                        _place_copied_mesh_instances(
                            data=data, node_entry=e, node_index=i, instances=instances,
                            sector_name=sectorName, sector_collection=Sector_coll, masters=Masters,
                            meshname=meshname, mesh_appearance=meshAppearance,
                            resolved_path=mesh_source_paths.get(meshname, ''),
                            contract='PHYSICAL_DESTRUCTION_NODE_WORLD',
                            extra_props={
                                'destructionSemantic': 'physical',
                                'destructionParams': json.dumps(
                                    data.get('destructionParams', {}), separators=(',', ':')
                                    ),
                                }
                            )

                    case 'worldBakedDestructionNode':
                        meshname = get_meshname(data, include_entity_template=False)
                        instances = instances_by_node.get(i, [])
                        if not meshname:
                            _sector_warning(f'{sectorName}: node {i} has no baked destruction mesh')
                            continue
                        _place_copied_mesh_instances(
                            data=data, node_entry=e, node_index=i, instances=instances,
                            sector_name=sectorName, sector_collection=Sector_coll, masters=Masters,
                            meshname=meshname, mesh_appearance=meshAppearance,
                            resolved_path=mesh_source_paths.get(meshname, ''),
                            contract='BAKED_DESTRUCTION_NODE_WORLD',
                            extra_props={'destructionSemantic': 'baked'}
                            )

                    case 'worldBuildingProxyMeshNode' | 'worldAdvertisingNode' | 'worldAdvertisementNode' | \
                         'worldGenericProxyMeshNode' | 'worldEntityProxyMeshNode' | 'worldDestructibleEntityProxyMeshNode' | 'worldDestructibleProxyMeshNode' | 'worldTerrainProxyMeshNode' | 'worldStaticOccluderMeshNode' | 'worldTerrainMeshNode' | 'worldClothMeshNode' | \
                         'worldDecorationMeshNode' | 'worldDynamicMeshNode' | 'worldMeshNode' | 'worldWaterPatchNode':
                        meshname = get_meshname(data, include_entity_template=False)
                        instances = instances_by_node.get(i, [])
                        if not meshname:
                            _sector_warning(f'{sectorName}: node {i} has no mesh resource')
                            continue
                        extra_props = {}
                        if ntype in {'worldAdvertisingNode', 'worldAdvertisementNode'} and 'lightData' in data:
                            extra_props['lightData'] = json.dumps(data['lightData'], separators=(',', ':'))
                        if ntype == 'worldWaterPatchNode':
                            extra_props.update({
                                'waterPatchDepth': float(data.get('depth', 0.0) or 0.0),
                                'waterPatchType': _cname_value(
                                    _nested_value(data, 'type', 'typeName', default={})
                                    ),
                                'generateNavmesh': bool(data.get('generateNavmesh', 0)),
                                'waterPatchVersion': int(data.get('version', 0) or 0),
                                'waterPatchData': _safe_json(data),
                                })
                        if _is_proxy_node_type(ntype):
                            owner_global_id = (
                                _nested_value(data, 'ownerGlobalId', 'hash', default='')
                                or data.get('ownerHash', '')
                                )
                            extra_props.update({
                                'proxySemantic': True,
                                'proxyOwnerGlobalId': str(owner_global_id),
                                'proxyOwnerResolved': False,
                                'entityAttachDistance': float(data.get('entityAttachDistance', 0.0) or 0.0),
                                'nearAutoHideDistance': float(data.get('nearAutoHideDistance', 0.0) or 0.0),
                                'forceAutoHideDistance': float(data.get('forceAutoHideDistance', 0.0) or 0.0),
                                'lodLevelScales': int(data.get('lodLevelScales', 0) or 0),
                                'occluderType': str(data.get('occluderType', '')),
                                'renderSceneLayerMask': str(data.get('renderSceneLayerMask', '')),
                                'nbNodesUnderProxy': int(data.get('nbNodesUnderProxy', 0) or 0),
                                'proxyData': _safe_json(data),
                                })
                        placed = _place_copied_mesh_instances(
                            data=data, node_entry=e, node_index=i, instances=instances,
                            sector_name=sectorName, sector_collection=Sector_coll, masters=Masters,
                            meshname=meshname, mesh_appearance=meshAppearance,
                            resolved_path=mesh_source_paths.get(meshname, ''),
                            contract=f'{ntype}_NODE_WORLD',
                            extra_props=extra_props
                            )
                        if ntype == 'worldClothMeshNode':
                            for new, placement_root, rotation_root, inst, instance_index in placed:
                                if 'windImpulseEnabled' in inst:
                                    new['windImpulseEnabled'] = inst['windImpulseEnabled']
                                    placement_root['windImpulseEnabled'] = inst['windImpulseEnabled']

                    case 'worldInstancedDestructibleMeshNode':
                        instances = instances_by_node.get(i, [])
                        meshname = _depot_path(data, 'mesh')
                        start, num, transform_buffer, transform_slice = _buffer_slice(
                            data, cooked_transform_buffers, 'cookedInstanceTransforms',
                            sectorName, i
                            )
                        if not meshname:
                            _sector_warning(f'{sectorName}: instanced destructible node {i} has no mesh resource')
                            continue
                        group, groupname = get_group(
                            meshname, meshAppearance, Masters, mesh_source_paths.get(meshname, '')
                            )
                        if group is None:
                            message = f'Mesh not found in masters - {meshname} - {i} - {e.get("HandleId", "")}'
                            print(message)
                            _sector_warning(f'{sectorName}: {message}')
                            continue

                        buffer_ref = _buffer_ref_id(data, 'cookedInstanceTransforms')
                        appearance_name = data.get('appearanceName', {}).get('$value', meshAppearance)
                        for top_level_index, inst in enumerate(instances):
                            node_matrix = _instance_matrix(inst, scale_factor)
                            parent_name = _trim_name(
                                f'wIDMn{inst["nodeDataIndex"]}_{groupname}'
                                )
                            parent_collection = bpy.data.collections.new(parent_name)
                            Sector_coll.children.link(parent_collection)
                            assign_custom_properties(
                                parent_collection, data, sectorName, i,
                                nodeDataIndex=inst['nodeDataIndex'], mesh=meshname,
                                pivot=inst.get('Pivot', {}), numElements=num,
                                bufferStart=start, bufferRef=str(buffer_ref or ''),
                                appearanceName=appearance_name
                                )

                            for element_index, local_transform in transform_slice:
                                local_matrix = _instance_matrix(local_transform)
                                final_matrix = node_matrix @ local_matrix
                                empty_inst = _collection_instance_object(
                                    f'wIDMi{inst["nodeDataIndex"]}_{element_index}_{groupname}',
                                    group, parent_collection, final_matrix,
                                    color=(0.3, 0.3, 0.3, 1)
                                    )
                                assign_custom_properties(
                                    empty_inst, data, sectorName, i,
                                    nodeDataIndex=inst['nodeDataIndex'], mesh=meshname,
                                    Element_idx=element_index, tl_instance_idx=top_level_index,
                                    sub_instance_idx=element_index, appearanceName=appearance_name
                                    )
                                empty_inst['pivot'] = inst.get('Pivot', {})
                                if buffer_ref is not None:
                                    empty_inst['bufferID'] = str(buffer_ref)

                    case 'MinimapDataNode':
                        instances = instances_by_node.get(i, [])
                        for idx, inst in enumerate(instances):
                            _create_minimap_data_marker(
                                data, i, inst, idx, sectorName, Sector_coll,
                                asset_index
                                )

                    case 'worldInteriorMapNode':
                        instances = instances_by_node.get(i, [])
                        for idx, inst in enumerate(instances):
                            _create_interior_map_marker(
                                data, i, inst, idx, sectorName, Sector_coll
                                )

                    case 'worldStaticLightNode':
                        if with_lights:
                            instances = instances_by_node.get(i, [])
                            for idx, inst in enumerate(instances):
                                _create_static_light(
                                    data, i, inst, idx, sectorName, Sector_coll, asset_index
                                    )

                    case 'worldTriggerAreaNode' | 'gameKillTriggerNode' | 'worldAmbientAreaNode' | 'worldLightChannelVolumeNode' | \
                         'gameWorldBoundaryNode' | 'worldGISpaceNode' | 'worldInteriorAreaNode':
                        instances = instances_by_node.get(i, [])
                        colors = {
                            'worldTriggerAreaNode': (1.0, 0.35, 0.05, 1.0),
                            'gameKillTriggerNode': (1.0, 0.0, 0.0, 1.0),
                            'worldAmbientAreaNode': (0.15, 0.55, 1.0, 1.0),
                            'worldLightChannelVolumeNode': (0.75, 0.2, 1.0, 1.0),
                            'gameWorldBoundaryNode': (1.0, 0.0, 0.4, 1.0),
                            'worldGISpaceNode': (0.2, 1.0, 0.65, 1.0),
                            'worldInteriorAreaNode': (0.2, 0.65, 1.0, 1.0),
                            }
                        for idx, inst in enumerate(instances):
                            obj = _create_outline_volume(
                                data, i, inst, idx, sectorName, Sector_coll, 
                                colors.get(ntype, (0.8, 0.8, 0.8, 1.0))
                                )
                            if obj is None:
                                continue
                            if ntype == 'worldLightChannelVolumeNode':
                                obj['lightChannels'] = str(data.get('channels', ''))
                                obj['streamingDistanceFactor'] = float(data.get('streamingDistanceFactor', 0.0) or 0.0)
                            elif ntype == 'worldAmbientAreaNode':
                                notifier_settings = (
                                    data.get('notifiers', [{}])[0].get('Data', {}).get('Settings', {})
                                    if data.get('notifiers') else {}
                                    )
                                obj['audioEvents'] = _safe_json(_audio_events(notifier_settings))
                                obj['useCustomColor'] = bool(data.get('useCustomColor', 0))
                            elif ntype == 'worldGISpaceNode':
                                obj['giGroup'] = str(data.get('group', ''))
                                obj['giPriority'] = int(data.get('priority', 0) or 0)
                                obj['giInterior'] = bool(data.get('interior', 0))
                                obj['giRuntime'] = bool(data.get('runtime', 0))
                            elif ntype == 'worldInteriorAreaNode':
                                obj['interiorAreaNotifiers'] = _safe_json(data.get('notifiers', []))
                            elif ntype == 'gameWorldBoundaryNode':
                                obj['worldBoundaryData'] = _safe_json(data)

                    case 'worldLightChannelShapeNode':
                        instances = instances_by_node.get(i, [])
                        for idx, inst in enumerate(instances):
                            _create_light_channel_shape(
                                data, i, inst, idx, sectorName, Sector_coll
                                )

                    case 'worldStaticFogVolumeNode':
                        instances = instances_by_node.get(i, [])
                        for idx, inst in enumerate(instances):
                            name = _trim_name(f'{ntype}_{i}_{idx}')
                            obj = create_fog_volume_object(
                                name,
                                data,
                                Sector_coll,
                                matrix=_instance_matrix(inst, scale_factor),
                                source_kind='sector',
                                )
                            assign_custom_properties(
                                obj,
                                data,
                                sectorName,
                                i,
                                nodeDataIndex=inst['nodeDataIndex'],
                                instance_idx=idx,
                                )
                            obj['fogVolumeRepresentation'] = 'CP77_UNIT_BOX_MINUS_ONE_TO_ONE_SCALED_BY_NODE_DATA'
                            obj['fogLightChannels'] = str(data.get('lightChannels', ''))
                            obj['fogEnvironmentColorGroup'] = str(data.get('envColorGroup', ''))
                            obj['fogApplyGlobalHeightFalloff'] = bool(data.get('applyHeightFalloff', 0))
                            obj['fogNodeData'] = _safe_json(data)

                    case 'worldReflectionProbeNode':
                        instances = instances_by_node.get(i, [])
                        probe_path = _depot_path(data, 'probeDataRef')
                        resolved_probe = _resolve_optional_resource(asset_index, probe_path)
                        _warn_missing_resource(probe_path, resolved_probe or '', required=False, context=f'{sectorName}: reflection probe node {i}')
                        for idx, inst in enumerate(instances):
                            obj = _create_box_semantic(
                                data, i, inst, idx, sectorName, Sector_coll, 
                                'REFLECTION_PROBE_BOX_NODE_WORLD', (0.1, 0.8, 1.0, 1.0)
                                )
                            obj['probeDataRef'] = probe_path
                            obj['resolvedProbeData'] = resolved_probe or ''
                            obj['captureOffset'] = list(get_pos({'Position': data.get('captureOffset', {})}))
                            obj['edgeScale'] = list(get_scale({'Scale': data.get('edgeScale', {})}))
                            obj['lightChannels'] = str(data.get('lightChannels', ''))
                            obj['volumeChannels'] = str(data.get('volumeChannels', ''))
                            obj['priority'] = int(data.get('priority', 0) or 0)
                            obj['blendRange'] = float(data.get('blendRange', 0.0) or 0.0)
                            obj['boxProjection'] = bool(data.get('boxProjection', 0))
                            obj['reflectionProbeData'] = _safe_json(data)

                    case 'worldAcousticSectorNode':
                        instances = instances_by_node.get(i, [])
                        acoustic_path = _depot_path(data, 'data')
                        resolved_acoustic = _resolve_optional_resource(asset_index, acoustic_path)
                        _warn_missing_resource(acoustic_path, resolved_acoustic or '', required=False, context=f'{sectorName}: acoustic sector node {i}')
                        for idx, inst in enumerate(instances):
                            obj = _create_box_semantic(
                                data, i, inst, idx, sectorName, Sector_coll, 
                                'ACOUSTIC_SECTOR_GRID_CELL_32M', (0.2, 0.9, 0.4, 1.0), half_extent=16.0
                                )
                            obj['acousticData'] = acoustic_path
                            obj['resolvedAcousticData'] = resolved_acoustic or ''
                            obj['representationApproximate'] = True
                            obj['generatorId'] = int(data.get('generatorId', 0) or 0)
                            obj['edgeMask'] = int(data.get('edgeMask', 0) or 0)
                            obj['acousticSectorData'] = _safe_json(data)
                            obj['inSectorCoords'] = [
                                int(data.get('inSectorCoordsX', 0) or 0),
                                int(data.get('inSectorCoordsY', 0) or 0),
                                int(data.get('inSectorCoordsZ', 0) or 0),
                                ]

                    case 'worldStaticParticleNode' | 'worldEffectNode':
                        instances = instances_by_node.get(i, [])
                        for idx, inst in enumerate(instances):
                            _create_effect_marker(
                                data, i, inst, idx, sectorName, Sector_coll, asset_index
                                )

                    case 'worldPopulationSpawnerNode':
                        instances = instances_by_node.get(i, [])
                        for idx, inst in enumerate(instances):
                            o = bpy.data.objects.new('empty', None)
                            o.name = ntype + '_' + _cname_value(data.get('debugName'), str(i))
                            assign_custom_properties(
                                o, data, sectorName, i, instance_idx=idx,
                                nodeDataIndex=inst['nodeDataIndex'],
                                appearanceName=_cname_value(data.get('appearanceName')),
                                objectRecordId=_cname_value(data.get('objectRecordId')),
                                spawnOnStart=bool(data.get('spawnOnStart', 0))
                                )
                            Sector_coll.objects.link(o)
                            o.matrix_world = _instance_matrix(inst, scale_factor)
                            o.display_type = 'WIRE'
                            o.color = (1.0, 0.005, .062, 1)

                    case 'worldGINode':
                        instances = instances_by_node.get(i, [])
                        for idx, inst in enumerate(instances):
                            location = data.get('location', {}).get('Elements', [])
                            obj = _create_semantic_marker(
                                data, i, inst, idx, sectorName, Sector_coll, 
                                'GLOBAL_ILLUMINATION_RESOURCE_NODE_WORLD',
                                (0.15, 0.9, 0.55, 1.0),
                                display_type='CUBE', display_size=0.75,
                                asset_index=asset_index, resource_keys=('data',),
                                extra_props={'giGridLocation': list(location)}
                                )
                            obj['giNodeData'] = _safe_json(data)

                    case 'worldCompiledSmartObjectsNode':
                        instances = instances_by_node.get(i, [])
                        for idx, inst in enumerate(instances):
                            obj = _create_semantic_marker(
                                data, i, inst, idx, sectorName, Sector_coll, 
                                'COMPILED_SMART_OBJECT_RESOURCE_NODE_WORLD',
                                (1.0, 0.55, 0.1, 1.0),
                                display_type='CUBE', display_size=0.5,
                                asset_index=asset_index, resource_keys=('resource',),
                                )
                            obj['compiledSmartObjectData'] = _safe_json(data)

                    case 'worldSmartObjectNode':
                        instances = instances_by_node.get(i, [])
                        smart_data = data.get('object', {}).get('Data', {})
                        workspot = _depot_path(smart_data, 'workspotTemplate')
                        action_database = _depot_path(smart_data, 'motionActionDatabase')
                        resolved_workspot = _resolve_optional_resource(asset_index, workspot)
                        resolved_action_database = _resolve_optional_resource(asset_index, action_database)
                        _warn_missing_resource(workspot, resolved_workspot or '', required=False, context=f'{sectorName}: smart object node {i} workspot')
                        _warn_missing_resource(action_database, resolved_action_database or '', required=False, context=f'{sectorName}: smart object node {i} action database')
                        for idx, inst in enumerate(instances):
                            obj = _create_semantic_marker(
                                data, i, inst, idx, sectorName, Sector_coll, 
                                'SMART_OBJECT_NODE_WORLD',
                                (1.0, 0.35, 0.05, 1.0),
                                display_type='CONE', display_size=0.4,
                                extra_props={
                                    'workspotTemplate': workspot,
                                    'resolvedWorkspotTemplate': resolved_workspot or '',
                                    'motionActionDatabase': action_database,
                                    'resolvedMotionActionDatabase': resolved_action_database or '',
                                    'smartObjectEnabled': bool(smart_data.get('enabled', 0)),
                                    'smartObjectType': str(smart_data.get('$type', '')),
                                    }
                                )
                            obj['smartObjectActions'] = _safe_json(smart_data.get('actions', []))
                            obj['smartObjectData'] = _safe_json(smart_data)

                    case 'worldStaticGpsLocationEntranceMarkerNode':
                        instances = instances_by_node.get(i, [])
                        for idx, inst in enumerate(instances):
                            obj = _create_semantic_marker(
                                data, i, inst, idx, sectorName, Sector_coll, 
                                'GPS_LOCATION_ENTRANCE_MARKER_NODE_WORLD',
                                (0.1, 1.0, 0.2, 1.0),
                                display_type='ARROWS', display_size=0.7,
                                )
                            obj['gpsMarkerData'] = _safe_json(data)

                    case 'worldFoliageDestructionNode' | 'worldTerrainCollisionNode':
                        instances = instances_by_node.get(i, [])
                        for idx, inst in enumerate(instances):
                            _create_collision_metadata_marker(
                                data, i, inst, idx, sectorName, Sector_coll
                                )

                    case 'worldStaticSoundEmitterNode':
                        instances = instances_by_node.get(i, [])
                        events = _audio_events(data.get('Settings', {}))
                        for idx, inst in enumerate(instances):
                            node_matrix = _instance_matrix(inst, scale_factor)
                            o = bpy.data.objects.new(
                                _trim_name(f'{ntype}_{_cname_value(data.get("debugName"), str(i))}_{idx}'), None
                                )
                            o.empty_display_type = 'SPHERE'
                            o.empty_display_size = max(0.1, float(data.get('radius', 1.0) or 1.0))
                            Sector_coll.objects.link(o)
                            o.matrix_world = node_matrix
                            assign_custom_properties(
                                o, data, sectorName, i, nodeDataIndex=inst['nodeDataIndex'],
                                instance_idx=idx, radius=float(data.get('radius', 0.0) or 0.0),
                                audioName=_cname_value(data.get('audioName')),
                                emitterMetadataName=_cname_value(data.get('emitterMetadataName')),
                                occlusionEnabled=bool(data.get('occlusionEnabled', 0)),
                                usePhysicsObstruction=bool(data.get('usePhysicsObstruction', 0)),
                                useDoppler=bool(data.get('useDoppler', 0)),
                                dopplerFactor=float(data.get('dopplerFactor', 1.0) or 1.0),
                                )
                            o['audioEvents'] = _safe_json(events)
                            o['audioSettings'] = _safe_json(data.get('Settings', {}))

                    case 'worldCollisionNode':

                        #   ______      _____      _
                        #  / ____/___  / / (_)____(_)___  ____  _____
                        # / /   / __ \/ / / / ___/ / __ \/ __ \/ ___/
                        # / /___/ /_/ / / / (__  ) / /_/ / / / (__  )
                        # \____/\____/_/_/_/____/_/\____/_/ /_/____/
                        #
                        # Collisions are only partially supported, cant get the mesh object ones out of the geomCache from wkit enmasse currently so only box and capsule ones
                        if want_collisions:
                            # print('worldCollisionNode',i)
                            sector_Collisions = sectorName + '_colls'
                            if sector_Collisions in coll_scene.children:
                                sector_Collisions_coll = bpy.data.collections.get(sector_Collisions)
                            else:
                                sector_Collisions_coll = bpy.data.collections.new(sector_Collisions)
                                coll_scene.children.link(sector_Collisions_coll)
                            inst = _first_instance(instances_by_node, i)
                            if inst is None:
                                continue
                            Actors = e['Data']['compiledData']['Data']['Actors']
                            for idx, act in enumerate(Actors):
                                # print(len(act['Shapes']))
                                [x, y, z] = get_pos(act)
                                # x=act['Position']['x']['Bits']/131072*scale_factor
                                # y=act['Position']['y']['Bits']/131072*scale_factor
                                # z=act['Position']['z']['Bits']/131072*scale_factor
                                sector_Hash = e['Data']['sectorHash']
                                arot = get_rot(act)
                                for s, shape in enumerate(act['Shapes']):
                                    # We don't need ssize anymore because pxbridge handles scale internally!
                                    spos = get_pos(shape)
                                    srot = get_rot(shape)
                                    arot_q = Quaternion((arot[0], arot[1], arot[2], arot[3]))
                                    srot_q = Quaternion((srot[0], srot[1], srot[2], srot[3]))
                                    rot = arot_q @ srot_q
                                    loc = (spos[0] + x, spos[1] + y, spos[2] + z)

                                    # convert back from game type to native representation for bridge
                                    physx_shape_type = shape['ShapeType']
                                    bridge_shape_type = 'physicsColliderBox'

                                    if physx_shape_type in ('Box', 'Capsule', 'Sphere'):
                                        shape_data = shape

                                        if physx_shape_type == 'Box':
                                            bridge_shape_type = 'physicsColliderBox'
                                            if 'Size' in shape:
                                                # Bridge expects halfExtents vector Dict
                                                shape_data = {
                                                    'X': shape['Size']['X'] * act['Scale']['X'],
                                                    'Y': shape['Size']['Y'] * act['Scale']['Y'],
                                                    'Z': shape['Size']['Z'] * act['Scale']['Z']
                                                    }
                                            else:
                                                shape_data = {'X': 0.5, 'Y': 0.5, 'Z': 0.5}

                                        elif physx_shape_type == 'Capsule':
                                            bridge_shape_type = 'physicsColliderCapsule'
                                            radius = 0.5
                                            if 'Size' in shape:
                                                radius = shape['Size']['X'] * act['Scale']['X']
                                            shape_data = {'radius': radius, 'height': 1.0}

                                        elif physx_shape_type == 'Sphere':
                                            bridge_shape_type = 'physicsColliderSphere'
                                            radius = 0.5
                                            if 'Size' in shape:
                                                radius = shape['Size']['X'] * act['Scale']['X']
                                            shape_data = {'radius': radius}

                                        submeshName = f'NodeDataIndex_{inst["nodeDataIndex"]}_Actor_{idx}_Shape_{s}'
                                        physmat = shape.get('Materials', [{'$value': 'Default'}])[0]['$value']

                                        # It might make sense to create an empty parent object acting as the actor to hold these shapes
                                        act_name = f'NodeDataIndex_{inst["nodeDataIndex"]}_Actor_{idx}'
                                        act_obj = None
                                        for child in sector_Collisions_coll.objects:
                                            if child.name == act_name:
                                                act_obj = child
                                                break
                                        if not act_obj:
                                            act_obj = bpy.data.objects.new(act_name, None)
                                            sector_Collisions_coll.objects.link(act_obj)
                                            act_obj.location = (x, y, z)
                                            act_obj.rotation_mode = "QUATERNION"
                                            act_obj.rotation_quaternion = arot_q
                                            act_obj['nodeType'] = 'worldCollisionNode'
                                            act_obj['nodeIndex'] = i
                                            act_obj['nodeDataIndex'] = inst['nodeDataIndex']
                                            act_obj['ActorIdx'] = idx
                                            act_obj['sectorName'] = sectorName

                                        # Add the actual shape representation
                                        try:
                                            # Using the updated signature
                                            shape_cdata = shape_data
                                            if isinstance(shape_cdata, dict) and ('$type' not in shape_cdata):
                                                shape_cdata['$type'] = bridge_shape_type
                                                shape_cdata['localToBody'] = {
                                                    'position': {'X': spos[0], 'Y': spos[1], 'Z': spos[2]},
                                                    'orientation': {'r': srot[0], 'i': srot[1], 'j': srot[2],
                                                                    'k': srot[3]}
                                                    }
                                                shape_cdata['material'] = {'$value': physmat}
                                            # The function expects cdata, submeshName, new_col, optionally obj
                                            obj = import_collider_as_actor(
                                                shape_cdata, submeshName, sector_Collisions_coll, act_obj
                                                )
                                        except Exception as e:
                                            print('Error importing collision shape:', e)

                                    else:
                                        # print(f"unsupported shape {shape['ShapeType']}")
                                        meshname = sector_Hash + '_' + shape['Hash']
                                        if meshname not in Masters.objects:
                                            o = CP77CollisionTriangleMeshJSONimport_by_hashes(
                                                sectorHashStr=sector_Hash, entryHashStr=shape['Hash'],
                                                project_raw_dir=raw_path
                                                )
                                            if not o:
                                                o = bpy.data.objects.new(
                                                    'NDI_' + str(inst['nodeDataIndex']) + '_Actor_' + str(
                                                        idx
                                                        ) + '_Shape_' + str(
                                                        s
                                                        ), None
                                                    )
                                            Masters.objects.link(o)
                                        if meshname not in Masters.objects:
                                            print(
                                                f"Mesh {meshname} not found in Masters, skipping collision import for this shape"
                                                )
                                            continue
                                        o = Masters.objects[meshname].copy()
                                        o['nodeType'] = 'worldCollisionNode'
                                        o['nodeIndex'] = i
                                        o['nodeDataIndex'] = inst['nodeDataIndex']
                                        o['ShapeType'] = shape['ShapeType']
                                        o['ShapeNo'] = s
                                        o['ActorIdx'] = idx
                                        o['sectorName'] = sectorName
                                        sector_Collisions_coll.objects.link(o)
                                        o.location = (loc[0], loc[1], loc[2])
                                        o.rotation_mode = "QUATERNION"
                                        o.rotation_quaternion = rot

                    case _:
                        # print('None of the above',i)
                        pass
        _organize_sector_placements(
            Sector_coll, sector_entry, selected_variant=selected_variant
            )
        print('Nodes complete, updating view layer and saving world matrices')
        # Have to do a view_layer update or the matrices are all blank
        bpy.context.view_layer.update()
        for col in Sector_coll.children:
            if len(col.all_objects) > 0 and 'matrix' not in col:
                col['matrix'] = _matrix_values(col.all_objects[0].matrix_world)

        print('Finished with ', filepath, ' (no ', fpn + 1, ' of ', no_sectors, ')')
    _link_sector_composition(sector_entries, sector_collections, coll_scene)
    # doing this earlier in the file was breaking the entity postitioning. NO idea how that works, but be warned.
    Masters.hide_viewport = True
    for obj in bpy.data.objects:
        if 'Decal' in obj.name:
            obj['matrix'] = _matrix_values(obj.matrix_world)
    print(f"Imported Sectors from : {wkit_proj_name} in {time.time() - start_time}")
    print('')
    print('-------------------- Finished Importing Cyberpunk 2077 Streaming Sectors --------------------')
    print('')


# The above is  the code thats for the import plugin below is to allow testing/dev, you can run this file to import something

if __name__ == "__main__":
    filepath = 'F:\\CPMod\\judysApt\\judysApt.cpmodproj'

    importSectors(filepath, with_mats=True, want_collisions=False, am_modding=False)
