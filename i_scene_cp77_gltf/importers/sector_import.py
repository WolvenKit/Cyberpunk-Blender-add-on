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
from operator import add

import bmesh
from bpy_extras import anim_utils
from mathutils import Matrix, Quaternion, Vector

from .collision_mesh_import import CP77CollisionTriangleMeshJSONimport_by_hashes
from .entity_import import importEnt
from .import_common import _collection_import_snapshot, _imported_collection_from_diff, add_to_list, get_group, \
    meshes_from_mesheswapps
from .import_with_materials import *
from ..collisiontools.pxbridge.io_phys import import_collider_as_actor
from ..datakrash import DepotAssetIndex
from ..jsontool import resolve_entity_appearance
from ..main.common import *

VERBOSE = True
scale_factor = 1


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


SECTOR_INDEX_EXTENSIONS = (
    '.streamingsector.json',
    '.streamingsector_inplace.json',
    '.ent.json',
    '.app.json',
    '.mesh.json',
    '.glb',
    '.anims.glb',
    '.rig.json',
    '.mi.json',
    '.cfoliage.json',
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
    depot_root = os.path.splitext(depot_path)[0]
    return asset_index.resolve_expected(f'{depot_root}.glb', '.glb')


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


def _load_sector_entry(filepath):
    node_data, nodes = JSONTool.jsonload(filepath)
    return {
        'filepath': filepath,
        'sectorName': os.path.basename(filepath)[:-5],
        'nodeData': node_data,
        'nodes': nodes,
        'instances_by_node': _node_instances(node_data),
        'nodes_by_handle': _node_handle_lookup(nodes),
        'world_transform_buffers': _shared_transform_buffer_lookup(nodes, 'worldTransformsBuffer'),
        'cooked_transform_buffers': _shared_transform_buffer_lookup(nodes, 'cookedInstanceTransforms'),
        }


def _sector_entries(sector_jsons, base_path, project_name):
    project_sector = os.path.join(base_path, project_name + '.streamingsector.json')
    entries = []
    for sector_path in sorted(sector_jsons):
        if _same_path(sector_path, project_sector) or 'sim_' in sector_path:
            continue
        entries.append(_load_sector_entry(sector_path))
    return entries


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


def _node_buffer_matrix(node_inst, buffer_inst=None, scale=1):
    node_matrix = _instance_matrix(node_inst, scale)
    if buffer_inst is None:
        return node_matrix
    return node_matrix @ _instance_matrix(buffer_inst)


def _foliage_population_matrix(pop_info):
    rot_data = pop_info.get('Rotation', {}) if type(pop_info) is dict else {}
    rot = Quaternion(
            (
                float(rot_data.get('W', 1.0)),
                float(rot_data.get('X', 0.0)),
                float(rot_data.get('Y', 0.0)),
                float(rot_data.get('Z', 0.0)),
                )
            )
    pos = Vector(get_pos(pop_info))
    scale_value = pop_info.get('Scale', 1.0) if type(pop_info) is dict else 1.0
    scale_vec = Vector((float(scale_value), float(scale_value), float(scale_value)))
    return Matrix.LocRotScale(pos, rot, scale_vec)


_AXIS_UNIT_VECTORS = (Vector((1.0, 0.0, 0.0)), Vector((0.0, 1.0, 0.0)), Vector((0.0, 0.0, 1.0)))
_COLLECTION_DIMENSION_CACHE = {}
_IDENTITY_4X4 = Matrix.Identity(4)


def _matrix_from_columns(columns):
    return Matrix(
            (
                (columns[0].x, columns[1].x, columns[2].x, 0.0),
                (columns[0].y, columns[1].y, columns[2].y, 0.0),
                (columns[0].z, columns[1].z, columns[2].z, 0.0),
                (0.0, 0.0, 0.0, 1.0),
                )
            )


def _signed_axis_basis(source_axis, target_axis, target_sign):
    columns = [None, None, None]
    columns[source_axis] = _AXIS_UNIT_VECTORS[target_axis] * target_sign
    remaining_source = [axis for axis in range(3) if columns[axis] is None]
    remaining_target = [axis for axis in range(3) if axis != target_axis]

    for source, target in zip(remaining_source, remaining_target):
        columns[source] = _AXIS_UNIT_VECTORS[target].copy()

    matrix = _matrix_from_columns(columns)
    if matrix.to_3x3().determinant() < 0.0:
        columns[remaining_source[0]] = -columns[remaining_source[0]]
        matrix = _matrix_from_columns(columns)
    return matrix


def _collection_axis_dimensions(collection):
    cached = _COLLECTION_DIMENSION_CACHE.get(collection.name)
    if cached is not None:
        return cached

    minimum = None
    maximum = None
    for obj in collection.all_objects:
        if obj.type != 'MESH':
            continue
        for corner in obj.bound_box:
            point = obj.matrix_world @ Vector(corner)
            if minimum is None:
                minimum = point.copy()
                maximum = point.copy()
            else:
                minimum.x = min(minimum.x, point.x)
                minimum.y = min(minimum.y, point.y)
                minimum.z = min(minimum.z, point.z)
                maximum.x = max(maximum.x, point.x)
                maximum.y = max(maximum.y, point.y)
                maximum.z = max(maximum.z, point.z)

    if minimum is None:
        dims = Vector((0.0, 0.0, 0.0))
    else:
        dims = maximum - minimum
    _COLLECTION_DIMENSION_CACHE[collection.name] = dims
    return dims


def _vertical_axis_correction(collection, placement_matrix):
    dims = _collection_axis_dimensions(collection)
    if dims.z <= max(dims.x, dims.y) * 1.6:
        return _IDENTITY_4X4, False

    axis_scores = []
    axis_signs = []
    for axis in range(3):
        column = Vector((placement_matrix[0][axis], placement_matrix[1][axis], placement_matrix[2][axis]))
        if column.length == 0.0:
            axis_scores.append(0.0)
            axis_signs.append(1.0)
        else:
            axis_scores.append(abs(column.z / column.length))
            axis_signs.append(1.0 if column.z >= 0.0 else -1.0)

    if axis_scores[2] >= 0.75:
        return _IDENTITY_4X4, False

    target_axis = max(range(3), key=lambda axis: axis_scores[axis])
    if target_axis == 2 or axis_scores[target_axis] < 0.85:
        return _IDENTITY_4X4, False

    return _signed_axis_basis(2, target_axis, axis_signs[target_axis]), True


def _apply_vertical_axis_correction(collection, placement_matrix):
    correction, corrected = _vertical_axis_correction(collection, placement_matrix)
    if not corrected:
        return placement_matrix, False
    return placement_matrix @ correction, True


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

    for old_obj, obj in copy_map.items():
        if old_obj.parent in copy_map:
            obj.parent = copy_map[old_obj.parent]
            obj.matrix_parent_inverse = old_obj.matrix_parent_inverse.copy()
            obj.matrix_local = old_obj.matrix_local.copy()

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


def assign_custom_properties(obj, data, sectorName, i, **kwargs):
    ntype = data['$type']
    obj['nodeType'] = ntype
    obj['nodeIndex'] = i
    if 'debugName' in data:
        obj['debugName'] = data['debugName']['$value']
    obj['sectorName'] = sectorName
    if 'sourcePrefabHash' in data:
        obj['sourcePrefabHash'] = data['sourcePrefabHash']
    if ntype == 'worldAISpotNode':
        if data['spot']:
            obj['workspot'] = data['spot']['Data']['resource']['DepotPath']['$value']
        else:
            obj['workspot'] = 'None'
        if data['markings']:
            obj['markings'] = data['markings'][0]['$value']
    if 'entityTemplate' in data:
        obj['entityTemplate'] = data['entityTemplate']['DepotPath']['$value']

    if 'appearanceName' in data:
        obj['appearanceName'] = data['appearanceName']['$value']
    elif 'meshAppearance' in data:
        obj['appearanceName'] = data['meshAppearance']['$value']
    else:
        obj['appearanceName'] = ''

    # Assign any additional properties passed as kwargs
    for key, value in kwargs.items():
        obj[key] = value


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


def points_within_tol(point1, point2, tolerance=0.01):
    """
    Check if two points are within a specified tolerance.

    :param point1: The first point as a tuple or list of (x, y, z) coordinates.
    :param point2: The second point as a tuple or list of (x, y, z) coordinates.
    :param tolerance: The tolerance within which the points should be to be considered close.
    :return: True if the points are within the tolerance, False otherwise.
    """
    # Calculate the Euclidean distance between the points
    distance = math.sqrt(
        (point1[0] - point2[0]) ** 2 +
        (point1[1] - point2[1]) ** 2 +
        (point1[2] - point2[2]) ** 2
        )

    # Check if the distance is within the tolerance
    return distance <= tolerance


def average_vectors(vector1, vector2):
    """
    Calculate the average of two vectors.

    :param vector1: The first vector as a tuple or list of (x, y, z) coordinates.
    :param vector2: The second vector as a tuple or list of (x, y, z) coordinates.
    :return: The average vector as a tuple of (x, y, z) coordinates.
    """
    average = [(vector1[0] + vector2[0]) / 2,
               (vector1[1] + vector2[1]) / 2,
               (vector1[2] + vector2[2]) / 2]
    return Vector(average)


def apply_transform(ob, use_location=True, use_rotation=True, use_scale=True):
    mb = ob.matrix_basis
    I = Matrix()
    loc, rot, scale = mb.decompose()

    # rotation
    T = Matrix.Translation(loc)
    # R = rot.to_matrix().to_4x4()
    R = mb.to_3x3().normalized().to_4x4()
    S = Matrix.Diagonal(scale).to_4x4()

    transform = [I, I, I]
    basis = [T, R, S]

    def swap(i):
        transform[i], basis[i] = basis[i], transform[i]

    if use_location:
        swap(0)
    if use_rotation:
        swap(1)
    if use_scale:
        swap(2)

    M = transform[0] @ transform[1] @ transform[2]
    if hasattr(ob.data, "transform"):
        ob.data.transform(M)
    for c in ob.children:
        c.matrix_local = M @ c.matrix_local

    ob.matrix_basis = basis[0] @ basis[1] @ basis[2]


def ext_row(rowdata):
    row = [0, 0, 0, 0]
    row[0] = rowdata['X']
    row[1] = rowdata['Y']
    row[2] = rowdata['Z']
    row[3] = rowdata['W']
    return row


def get_curve_length(ob):
    total = 0
    me = ob.to_mesh()
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.edges.ensure_lookup_table()
    for i in bm.edges:
        total += i.calc_length()
    return total


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


def importSectors(filepath, with_mats, remap_depot=False, want_collisions=False, am_modding=False, with_lights=False):
    JSONTool.start_caching()
    try:
        return _importSectors_cached(filepath, with_mats, remap_depot, want_collisions, am_modding, with_lights)
    finally:
        JSONTool.stop_caching()


def _importSectors_cached(filepath, with_mats, remap_depot, want_collisions, am_modding, with_lights):
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
    # A sector import is a user-facing operation boundary: rescan so exports created since
    # the last import are visible; per-entity imports inside the batch reuse this index.
    asset_index = DepotAssetIndex.cached(raw_root, SECTOR_INDEX_EXTENSIONS, force_refresh=True)
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
    sector_jsons = _indexed_files(asset_index, '.streamingsector.json', '.streamingsector_inplace.json')
    mesh_jsons = _indexed_files(asset_index, '.mesh.json')
    anim_files = _indexed_files(asset_index, '.anims.glb')
    app_path = _indexed_files(asset_index, '.app.json')
    rigjsons = _indexed_files(asset_index, '.rig.json')
    glbs = _indexed_files(asset_index, '.glb')
    base_path = os.path.join(raw_root, 'base')
    raw_path = raw_root
    meshes = {}
    C = bpy.context
    I_want_to_break_free = False
    sector_entries = _sector_entries(sector_jsons, base_path, project_name)
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
            if (
                    limittypes and ntype in import_types) or limittypes == False:  # or type=='worldCableMeshNode': # can add a filter for dev here
                meshname = get_meshname(data, include_entity_template=False)
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
                         | 'worldMeshNode' | 'worldStaticOccluderMeshNode' | 'worldDecorationMeshNode' | 'worldFoliageNode':
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
            if (
                    limittypes and ntype in import_types) or limittypes == False:  # or type=='worldCableMeshNode': # can add a filter for dev here
                match ntype:
                    case 'worldGenericProxyMeshNode' | 'worldTerrainProxyMeshNode' | 'worldDestructibleEntityProxyMeshNode' | 'worldBuildingProxyMeshNode':
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

    for m in meshes:
        if len(m) > 0:
            add_to_list(m, meshes, meshes_w_apps)

    coll_scene = C.scene.collection
    mis = {}
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
    roads = []
    no_sectors = len(sector_entries)
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

        if sectorName in coll_scene.children:
            Sector_coll = bpy.data.collections.get(sectorName)
        else:
            Sector_coll = bpy.data.collections.new(sectorName)
            coll_scene.children.link(Sector_coll)
        Sector_coll['filepath'] = filepath
        Sector_coll['expectedNodes'] = numExpectedNodes

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
            meshAppearance = 'default'
            if 'meshAppearance' in data:
                meshAppearance = data['meshAppearance']['$value']  # Need to actually use this
            if (
                    limittypes and ntype in import_types) or limittypes == False:  # or type=='worldCableMeshNode': # can add a filter for dev here
                match ntype:
                    case 'worldAISpotNode':
                        instances = instances_by_node.get(i, [])

                        print('worldAISpotNode', i)
                        if instances:
                            inst = instances[0]
                            o = bpy.data.objects.new("empty", None)
                            assign_custom_properties(o, data, sectorName, i)
                            o.empty_display_size = 0.2
                            o.empty_display_type = 'CONE'
                            Sector_coll.objects.link(o)
                            o.name = ntype + '_' + data['debugName']['$value']
                            o.location = get_pos(inst)
                            o.rotation_mode = "QUATERNION"
                            o.rotation_quaternion = get_rot(inst)
                            o.scale = get_scale(inst)

                    case 'worldEntityNode' | 'worldDeviceNode':
                        # print('worldEntityNode',i)

                        app = data['appearanceName']["$value"]
                        ent_depot = _depot_path(data, 'entityTemplate')
                        entpath = _resolve_indexed_json(asset_index, ent_depot, '.ent.json')
                        if not entpath:
                            print(f"Entity template not indexed: {ent_depot}")
                            continue
                        resolved_app = resolve_entity_appearance(entpath, app)
                        if resolved_app != app:
                            print(f"Entity appearance alias resolved: {app} -> {resolved_app}")
                        ent_groupnames = _entity_collection_candidates(entpath, app, resolved_app)
                        ent_groupname = ent_groupnames[0] if ent_groupnames else ''
                        if 'door' in ent_groupname:
                            print('Door entity found, pausing')
                        imported = False
                        move_coll = _first_child_collection(Masters, ent_groupnames)
                        if move_coll is not None:
                            imported = True
                        else:
                            try:
                                # print('Importing ',entpath, ' using app ',app)
                                incoll = 'MasterInstances'
                                importEnt(
                                    with_mats, filepath=entpath, appearances=[app], inColl=incoll, meshes=glbs,
                                    mesh_jsons=mesh_jsons, app_path=app_path, anim_files=anim_files, rigjsons=rigjsons
                                    )
                                move_coll = _first_child_collection(Masters, ent_groupnames)
                                imported = move_coll is not None
                                if not imported:
                                    print(
                                        f"Imported entity collection not found after import. Tried: {', '.join(ent_groupnames)}"
                                        )
                            except:
                                print(traceback.format_exc())
                                print(f"Failed during Entity import on {entpath} from app {app}")
                        if imported:
                            instances = instances_by_node.get(i, [])
                            for idx, inst in enumerate(instances):
                                # print(inst)
                                group = move_coll
                                if (group):
                                    groupname = move_coll.name
                                    move_coll['meshpath'] = 'fake'
                                    move_coll['appearance'] = 'fake'
                                    # print('Group found for ',groupname)
                                    pos = Vector(get_pos(inst))
                                    rot = Quaternion(get_rot(inst))
                                    scale = Vector((1 / scale_factor, 1 / scale_factor, 1 / scale_factor))
                                    inst_trans_mat = Matrix.LocRotScale(pos, rot, scale)
                                    new = _copy_collection_tree(
                                        group, groupname, inst_trans_mat, color=(0.567942, 0.0247339, 0.600028, 1),
                                        hide_armatures=True
                                        )
                                    assign_custom_properties(
                                        new, data, sectorName, i, ndi=inst['nodeDataIndex'], idx=idx,
                                        HandleId=e['HandleId'], pivot=inst['Pivot']
                                        )
                                    new['ent_rot'] = rot.to_euler('XYZ')
                                    new['ent_pos'] = pos
                                    if len(new.all_objects) > 0:
                                        new['matrix'] = new.all_objects[0].matrix_world
                                    Sector_coll.children.link(new)

                    case 'worldBendedMeshNode' | 'worldCableMeshNode':
                        # print(ntype)
                        meshname = _depot_path(data, 'mesh')
                        instances = instances_by_node.get(i, [])
                        # if len(instances)>1:
                        #    print('Multiple Instances of node ',i)

                        if len(instances) > 0 and (meshname != 0):
                            node = nodes[i]
                            defData = node['Data']['deformationData']
                            coll_scene = C.scene.collection

                            inst_pos = (0, 0, 0)
                            inst_rot = Quaternion((0.707, 0, .707, 0))
                            inst_scale = Vector((1, 1, 1))
                            inst_m = Matrix.LocRotScale(inst_pos, inst_rot, inst_scale)

                            joints = []
                            mesh_name = "bendable_" + str(i)
                            mesh_data = bpy.data.meshes.new(mesh_name)

                            for idx, tt in enumerate(defData):
                                M = Matrix(
                                        (ext_row(defData[idx]['X']), ext_row(defData[idx]['Y']),
                                         ext_row(defData[idx]['Z']), ext_row(defData[idx]['W']))
                                        )
                                M = M.transposed()
                                joints.append(M.to_translation())
                            mesh_data.from_pydata(joints, [], [])
                            mesh_obj = bpy.data.objects.new(mesh_data.name, mesh_data)
                            # coll_scene.objects.link(mesh_obj)

                            inst = [n for n in t if n['NodeIndex'] == i][0]

                            mesh_obj.rotation_mode = 'QUATERNION'
                            mesh_obj.rotation_quaternion = get_rot(inst)
                            pos = get_pos(inst)
                            mesh_obj.location = pos
                            apply_transform(mesh_obj)

                            curve = bpy.data.curves.new('worldSplineNode_', 'CURVE')
                            curve.splines.new('BEZIER')
                            curve.dimensions = '3D'
                            curve.twist_mode = 'Z_UP'
                            curve.resolution_u = 64
                            bzps = curve.splines[0].bezier_points
                            bzps.add(len(mesh_obj.data.vertices) - 1)
                            for p_no, v in enumerate(mesh_obj.data.vertices):
                                bzps[p_no].co = v.co
                                bzps[p_no].handle_left_type = 'AUTO'
                                bzps[p_no].handle_right_type = 'AUTO'

                            curve_obj = bpy.data.objects.new('worldSplineNode_', curve)

                            coll_scene.objects.link(curve_obj)
                            curvelength = get_curve_length(curve_obj)

                            group, groupname = get_group(meshname, meshAppearance, Masters)
                            if (group):
                                new = bpy.data.collections.new(groupname)
                                Sector_coll.children.link(new)
                                assign_custom_properties(
                                    new, data, sectorName, i,
                                    nodeDataIndex=inst['nodeDataIndex'], mesh=meshname
                                    )

                                min_vertex = Vector((float('inf'), float('inf'), float('inf')))
                                max_vertex = Vector((float('-inf'), float('-inf'), float('-inf')))
                                for obj in group.all_objects:
                                    if obj.type == 'MESH':
                                        matrix = obj.matrix_world
                                        mesh = obj.data
                                        for vertex in mesh.vertices:
                                            vertex_world = matrix @ vertex.co
                                            min_vertex = Vector(min(min_vertex[i], vertex_world[i]) for i in range(3))
                                            max_vertex = Vector(max(max_vertex[i], vertex_world[i]) for i in range(3))
                                meshxLength = min_vertex[0] - max_vertex[0]
                                meshXScale = curvelength / meshxLength
                                meshyLength = min_vertex[1] - max_vertex[1]
                                meshYScale = curvelength / meshyLength
                                for old_obj in group.all_objects:
                                    obj = old_obj.copy()
                                    obj.color = (0.0380098, 0.595213, 0.600022, 1)
                                    new.objects.link(obj)
                                    if obj.type == 'MESH':
                                        curveMod = obj.modifiers.new('Curve', 'CURVE')
                                        if curveMod:
                                            curveMod.object = curve_obj
                                            if ntype == 'worldCableMeshNode':
                                                curveMod.deform_axis = 'NEG_X'
                                                obj.scale.x = abs(meshXScale)
                                            if ntype == 'worldBendedMeshNode':
                                                curveMod.deform_axis = 'POS_Y'
                                                obj.scale.y = abs(meshYScale)
                                                obj.rotation_mode = 'QUATERNION'
                                                obj.rotation_quaternion = Quaternion((0.707, 0, 0.707, 0))
                                                roads.append(
                                                        {'Mesh': obj, 'Curve': curve_obj, 'Name': new['debugName'],
                                                         'Startpos': bzps[0].co, 'Endpos': bzps[-1].co}
                                                        )

                    case 'worldInstancedMeshNode':
                        # print('worldInstancedMeshNode')
                        instances = instances_by_node.get(i, [])
                        for idx, inst in enumerate(instances):
                            meshname = _depot_path(data, 'mesh')
                            num = data['worldTransformsBuffer']['numElements']
                            start = data['worldTransformsBuffer']['startIndex']
                            if meshname:
                                # print('Mesh - ',meshname, ' - ',i, e['HandleId'])
                                group, groupname = get_group(meshname, meshAppearance, Masters)
                                if (group):
                                    # print('Group found for ',groupname)
                                    NDI_Coll_name = 'NDI' + str(inst['nodeDataIndex']) + '_' + groupname
                                    while len(NDI_Coll_name) > 63:
                                        NDI_Coll_name = NDI_Coll_name[:-1]
                                    NDI_Coll = bpy.data.collections.new(NDI_Coll_name)
                                    Sector_coll.children.link(NDI_Coll)
                                    assign_custom_properties(
                                        NDI_Coll, data, sectorName, i,
                                        nodeDataIndex=inst['nodeDataIndex'], mesh=meshname, numElements=num
                                        )

                                    transform_buffer = _shared_transform_buffer(
                                        data, world_transform_buffers, 'worldTransformsBuffer'
                                        )
                                    buffer_ref = _buffer_ref_id(data, 'worldTransformsBuffer')
                                    for El_idx in range(start, start + num):
                                        new_groupname = 'NDI' + str(inst['nodeDataIndex']) + '_' + str(
                                            El_idx
                                            ) + '_' + groupname
                                        while len(new_groupname) > 63:
                                            new_groupname = new_groupname[:-1]
                                        if not transform_buffer or El_idx >= len(transform_buffer):
                                            print(f'Missing world transform buffer data for node {i}, element {El_idx}')
                                            continue
                                        inst_trans = transform_buffer[El_idx]
                                        tm = _node_buffer_matrix(inst, inst_trans, scale_factor)
                                        tm, axis_corrected = _apply_vertical_axis_correction(group, tm)
                                        empty_inst = _collection_instance_object(
                                            new_groupname, group, NDI_Coll, tm, color=(0.785188, 0.409408, 0.0430124, 1)
                                            )
                                        if axis_corrected:
                                            empty_inst['axisCorrection'] = 'vertical_axis_from_sector_rotation'
                                        assign_custom_properties(
                                            empty_inst, data, sectorName, i,
                                            nodeDataIndex=inst['nodeDataIndex'], mesh=meshname, Element_idx=El_idx
                                            )
                                        if buffer_ref is not None:
                                            empty_inst['bufferID'] = int(buffer_ref)

                            else:
                                print('Mesh not found in masters - ', meshname, ' - ', i, e['HandleId'])

                    case 'worldFoliageNode':
                        # print('worldFoliageNode')
                        instances = instances_by_node.get(i, [])
                        for idx, inst in enumerate(instances):
                            meshname = _depot_path(data, 'mesh')
                            foliageResource = _depot_path(data, 'foliageResource')
                            foliage_json = _resolve_indexed_json(asset_index, foliageResource, '.cfoliage.json')
                            if foliage_json:
                                frjson = JSONTool.jsonload(foliage_json)
                                inst_pos = get_pos(inst)
                                Bucketnum = data['populationSpanInfo']['cketCount']
                                Bucketstart = data['populationSpanInfo']['cketBegin']
                                InstBegin = data['populationSpanInfo']['stancesBegin']
                                InstCount = data['populationSpanInfo']['stancesCount']
                                if meshname:
                                    # print('Mesh - ',meshname, ' - ',i, e['HandleId'])
                                    group, groupname = get_group(meshname, meshAppearance, Masters)
                                    if (group):
                                        # print('Group found for ',groupname)
                                        WFI_Coll_name = 'WFI_' + str(inst['nodeDataIndex']) + '_' + groupname
                                        while len(WFI_Coll_name) > 63:
                                            WFI_Coll_name = NDI_Coll_name[:-1]
                                        WFI_Coll = bpy.data.collections.new(WFI_Coll_name)
                                        Sector_coll.children.link(WFI_Coll)
                                        assign_custom_properties(
                                            WFI_Coll, data, sectorName, i,
                                            nodeDataIndex=inst['nodeDataIndex'], mesh=meshname,
                                            Bucketnum=Bucketnum, Bucketstart=Bucketstart, InstBegin=InstBegin,
                                            InstCount=InstCount
                                            )

                                        PopSubIndex = \
                                        frjson['Data']['RootChunk']['dataBuffer']['Data']['Buckets'][Bucketstart][
                                            'PopulationSubIndex']
                                        PopSubCount = \
                                        frjson['Data']['RootChunk']['dataBuffer']['Data']['Buckets'][Bucketstart][
                                            'PopulationCount']
                                        inst_m = _instance_matrix(inst, scale_factor)

                                        for El_idx in range(InstBegin + PopSubIndex, InstBegin + InstCount):
                                            new_groupname = 'WFI' + str(inst['nodeDataIndex']) + '_' + str(
                                                El_idx
                                                ) + '_' + groupname
                                            while len(new_groupname) > 63:
                                                new_groupname = new_groupname[:-1]
                                            popInfo = frjson['Data']['RootChunk']['dataBuffer']['Data']['Populations'][
                                                El_idx]
                                            inst_trans_m = _foliage_population_matrix(popInfo)
                                            tm = inst_m @ inst_trans_m
                                            tm, axis_corrected = _apply_vertical_axis_correction(group, tm)
                                            empty_inst = _collection_instance_object(
                                                new_groupname, group, WFI_Coll, tm, color=(0.0, 1.0, 0.0, 1)
                                                )
                                            if axis_corrected:
                                                empty_inst['axisCorrection'] = 'vertical_axis_from_sector_rotation'
                                            assign_custom_properties(
                                                empty_inst, data, sectorName, i,
                                                nodeDataIndex=inst['nodeDataIndex'], mesh=meshname, Element_idx=El_idx
                                                )

                                else:
                                    print('Mesh not found in masters - ', meshname, ' - ', i, e['HandleId'])

                    case 'XworldInstancedOccluderNode':
                        # print('worldInstancedOccluderNode')
                        pass

                    case 'worldStaticDecalNode':
                        # print('worldStaticDecalNode')
                        # decals are imported as planes tagged with the material details so you can see what they are and move them.
                        instances = instances_by_node.get(i, [])
                        for idx, inst in enumerate(instances):
                            # print( inst)
                            # o = bpy.data.objects.new( "empty", None )
                            vert = [(-0.5, -0.5, 0.0), (0.5, -0.5, 0.0), (-0.5, 0.5, 0.0), (0.5, 0.5, 0.0)]
                            fac = [(0, 1, 3, 2)]
                            pl_data = bpy.data.meshes.new("PL")
                            pl_data.from_pydata(vert, [], fac)
                            pl_data.uv_layers.new(name="UVMap")

                            o = bpy.data.objects.new("Decal_Plane", pl_data)
                            assign_custom_properties(
                                o, data, sectorName, i,
                                instance_idx=idx, mesh=meshname,
                                decal=_depot_path(data, 'material'),
                                horizontalFlip=data['horizontalFlip'],
                                verticalFlip=data['verticalFlip'],
                                alpha=data['alpha']
                                )

                            Sector_coll.objects.link(o)
                            o.location = get_pos(inst)
                            o.rotation_mode = "QUATERNION"
                            o.rotation_quaternion = get_rot(inst)
                            o.scale = get_scale(inst)

                            # o.empty_display_size = 0.002
                            # o.empty_display_type = 'IMAGE'
                            if with_mats:
                                mipath = _normalize_depot_path(o['decal'])
                                expected_jsonpath = os.path.join(raw_path, mipath) + ".json"
                                jsonpath = _resolve_indexed_json(asset_index, mipath, '.mi.json')
                                # print(jsonpath)
                                try:
                                    if not jsonpath:
                                        raise FileNotFoundError(expected_jsonpath)
                                    obj = JSONTool.jsonload(jsonpath)
                                    if obj:
                                        index = 0
                                        obj["Data"]["RootChunk"]['alpha'] = data['alpha']
                                        # FIXME: image_format
                                        if mipath in mis:
                                            bpymat = mis[mipath]
                                        else:
                                            builder = MaterialBuilder(obj, raw_path, 'png', raw_path)
                                            bpymat = builder.createdecal(index)
                                            mis[mipath] = bpymat
                                        if bpymat:
                                            o.data.materials.append(bpymat)
                                        else:
                                            o.display_type = 'WIRE'
                                            o.color = (1.0, 0.905, .062, 1)
                                            o.show_wire = True
                                            o.display.show_shadows = False
                                except FileNotFoundError:
                                    missing_path = jsonpath or expected_jsonpath
                                    name = os.path.basename(missing_path)
                                    print(f'File not found {name} ({missing_path}), you need to export .mi files')
                                    o.display_type = 'WIRE'
                                    o.color = (1.0, 0.905, .062, 1)
                                    o.show_wire = True
                                    o.display.show_shadows = False
                            else:
                                o.display_type = 'WIRE'
                                o.color = (1.0, 0.905, .062, 1)
                                o.show_wire = True
                                o.display.show_shadows = False

                    case 'worldSplineNode':
                        # print('worldSplineNode',i)
                        instances = instances_by_node.get(i, [])
                        if len(instances) > 0:
                            spline_node = e
                            spline_ndata = instances[0]
                            pos = get_pos(spline_ndata)
                            splineData = spline_node['Data']['splineData']
                            curve = bpy.data.curves.new('worldSplineNode_' + str(i), 'CURVE')
                            curve_obj = bpy.data.objects.new('worldSplineNode_' + str(i), curve)
                            coll_scene.objects.link(curve_obj)
                            curve_obj['nodeType'] = 'worldSplineNode'
                            curve_obj['nodeIndex'] = i
                            curve_obj['sectorName'] = sectorName
                            curve.splines.new('BEZIER')
                            bzps = curve.splines[0].bezier_points
                            bzps.add(len(splineData['Data']['points']) - 1)
                            for p_no, point in enumerate(splineData['Data']['points']):
                                point_pos = list(map(add, pos, get_pos(point)))
                                bzps[p_no].co = point_pos
                                bzps[p_no].handle_left_type = 'AUTO'
                                bzps[p_no].handle_right_type = 'AUTO'
                                tans = get_tan_pos(point['tangents'])
                                bzps[p_no].handle_right = list(map(add, point_pos, tans[0]))
                                bzps[p_no].handle_left = list(map(add, point_pos, tans[1]))
                        pass

                    case 'worldRoadProxyMeshNode':
                        if isinstance(e, dict) and 'mesh' in data:
                            meshname = _depot_path(data, 'mesh')
                            meshpath = _resolve_indexed_glb(asset_index, meshname)
                            if not meshpath:
                                print(f"Road proxy mesh not indexed: {meshname}")
                                continue
                            # print('Mesh path is - ',meshpath, e['HandleId'])
                            if meshname:
                                # print('Mesh - ',meshname, ' - ',i, e['HandleId'])
                                # Roads all have stupid prx0 names so instancing by name wont work.
                                imported = False
                                try:
                                    before_collections, before_objects = _collection_import_snapshot()
                                    bpy.ops.io_scene_gltf.cp77(with_mats, filepath=meshpath, scripting=True)
                                    group = _imported_collection_from_diff(before_collections, before_objects)
                                    if group is None:
                                        raise RuntimeError('Road proxy import produced no collection')
                                    groupname = group.name
                                    if coll_target.children.get(group.name) is not group:
                                        coll_target.children.link(group)
                                    if coll_scene.children.get(group.name) is group:
                                        coll_scene.children.unlink(group)
                                    coll_target['glb_file'] = meshname
                                    imported = True
                                except:
                                    print("Failed on ", meshpath)

                                if (imported):
                                    # print('Group found for ',groupname)
                                    instances = instances_by_node.get(i, [])
                                    for idx, inst in enumerate(instances):
                                        new = bpy.data.collections.new(groupname)
                                        Sector_coll.children.link(new)
                                        assign_custom_properties(
                                            new, data, sectorName, i,
                                            nodeDataIndex=inst['nodeDataIndex'], instance_idx=idx,
                                            mesh=meshname, pivot=inst['Pivot']
                                            )

                                        for old_obj in group.all_objects:
                                            obj = old_obj.copy()
                                            new.objects.link(obj)

                                            obj.location = get_pos(inst)
                                            obj.rotation_mode = 'QUATERNION'

                                            # if obj.location.x == 0:
                                            #    print('Mesh - ',meshname, ' - ',i,'HandleId - ', e['HandleId'])
                                            # print(i,obj.name,' x= ',obj.location.x, ' y= ', obj.location.y, ' z= ',obj.location.z)
                                            obj.rotation_quaternion = get_rot(inst)
                                            obj.scale = get_scale(inst)
                                else:
                                    print('Mesh not found in masters - ', meshname, ' - ', i, e['HandleId'])

                    case 'worldStaticMeshNode' | 'worldRotatingMeshNode' | 'worldPhysicalDestructionNode' | 'worldBakedDestructionNode' | 'worldBuildingProxyMeshNode' | 'worldAdvertisingNode' | 'worldAdvertisementNode' | \
                         'worldGenericProxyMeshNode' | 'worldDestructibleEntityProxyMeshNode' | 'worldTerrainProxyMeshNode' | 'worldStaticOccluderMeshNode' | 'worldTerrainMeshNode' | 'worldClothMeshNode' | \
                         'worldDecorationMeshNode' | 'worldDynamicMeshNode' | 'worldMeshNode':
                        meshname = None
                        if isinstance(e, dict) and 'mesh' in data and isinstance(data['mesh'], dict) and 'DepotPath' in \
                                data['mesh']:
                            meshname = _depot_path(data, 'mesh')
                        elif isinstance(e, dict) and 'meshRef' in data:
                            meshname = _depot_path(data, 'meshRef')
                        if meshname:
                            # print('Mesh name is - ',meshname, e['HandleId'])

                            # print('Mesh - ',meshname, ' - ',i, e['HandleId'])
                            group, groupname = get_group(meshname, meshAppearance, Masters)
                            if (group):
                                # print('Group found for ',groupname)
                                if ntype == 'worldRotatingMeshNode':
                                    rot_axis = data['rotationAxis']
                                    axis_no = 0
                                    if rot_axis == 'Y':
                                        axis_no = 1
                                    elif rot_axis == 'Z':  # y & z are swapped sometimes, need to work out why
                                        axis_no = 2

                                    rot_time = data['fullRotationTime']
                                    reverse = data['reverseDirection']

                                instances = instances_by_node.get(i, [])
                                for idx, inst in enumerate(instances):
                                    inst_trans_mat = _instance_matrix(inst, scale_factor)
                                    inst_trans_mat, axis_corrected = _apply_vertical_axis_correction(
                                        group, inst_trans_mat
                                        )
                                    new = _copy_collection_tree(
                                        group, groupname, inst_trans_mat, color=(0.3, 0.3, 0.3, 1), hide_armatures=True
                                        )
                                    if axis_corrected:
                                        new['axisCorrection'] = 'vertical_axis_from_sector_rotation'
                                    assign_custom_properties(
                                        new, data, sectorName, i,
                                        nodeDataIndex=inst['nodeDataIndex'], instance_idx=idx,
                                        mesh=meshname, pivot=inst['Pivot'],
                                        meshAppearance=meshAppearance,
                                        appearanceName=meshAppearance
                                        )
                                    if ntype == 'worldClothMeshNode' and 'windImpulseEnabled' in inst:
                                        new['windImpulseEnabled'] = inst['windImpulseEnabled']
                                    if ntype == 'worldRotatingMeshNode':
                                        if 'rotationAxis' in data:
                                            new['rot_axis'] = data['rotationAxis']
                                        if 'reverseDirection' in data:
                                            new['reverseDirection'] = data['reverseDirection']
                                        if 'fullRotationTime' in data:
                                            new['fullRotationTime'] = data['fullRotationTime']
                                    if ntype == 'worldAdvertisingNode' or ntype == 'worldAdvertisementNode':
                                        if 'lightData' in data:
                                            new['lightData'] = data['lightData']
                                    if ntype == 'worldRotatingMeshNode':
                                        for obj in new.all_objects:
                                            if obj.type != 'MESH':
                                                continue
                                            obj.rotation_mode = 'YXZ'
                                            obj.keyframe_insert('rotation_euler', index=axis_no, frame=1)
                                            obj.rotation_euler[axis_no] = obj.rotation_euler[axis_no] + math.radians(
                                                360
                                                )
                                            obj.keyframe_insert('rotation_euler', index=axis_no, frame=rot_time * 24)
                                            if obj.animation_data.action:
                                                obj_action = bpy.data.actions.get(obj.animation_data.action.name)
                                                obj_slot = obj.animation_data.action_slot
                                                channelbag = anim_utils.action_get_channelbag_for_slot(
                                                    obj_action, obj_slot
                                                    )
                                                obj_fcu = channelbag.fcurves[0]
                                                for pt in obj_fcu.keyframe_points:
                                                    pt.interpolation = 'LINEAR'
                                    Sector_coll.children.link(new)



                            else:
                                print('Mesh not found in masters - ', meshname, ' - ', i, e['HandleId'])

                    case 'worldInstancedDestructibleMeshNode':
                        # print('worldInstancedDestructibleMeshNode',i)
                        instances = instances_by_node.get(i, [])
                        for instidx, inst in enumerate(instances):
                            if isinstance(e, dict) and 'mesh' in data:
                                meshname = _depot_path(data, 'mesh')
                                num = data['cookedInstanceTransforms']['numElements']
                                start = data['cookedInstanceTransforms']['startIndex']
                                # print('Mesh name is - ',meshname, e['HandleId'])
                                if meshname:
                                    # print('Mesh - ',meshname, ' - ',i, e['HandleId'])
                                    groupname = os.path.splitext(os.path.split(meshname)[-1])[0] + '@' + meshAppearance
                                    group = Masters.children.get(groupname)
                                    if (group):
                                        NDI_Coll_name = 'wIDMn' + str(inst['nodeDataIndex']) + '_' + groupname
                                        while len(NDI_Coll_name) > 63:
                                            NDI_Coll_name = NDI_Coll_name[:-1]
                                        NDI_Coll = bpy.data.collections.new(NDI_Coll_name)
                                        Sector_coll.children.link(NDI_Coll)
                                        assign_custom_properties(
                                            NDI_Coll, data, sectorName, i,
                                            nodeDataIndex=inst['nodeDataIndex'],
                                            mesh=meshname, pivot=inst['Pivot']
                                            )
                                        if 'appearanceName' in e['Data']:
                                            NDI_Coll['appearanceName'] = e['Data']['appearanceName']['$value']
                                        # print('Glb found - ',glbfoundname)
                                        # print('Glb found, looking for instances of ',i)
                                        # print('Node - ',i, ' - ',meshname)
                                        transform_buffer = _shared_transform_buffer(
                                            data, cooked_transform_buffers, 'cookedInstanceTransforms'
                                            )
                                        buffer_ref = _buffer_ref_id(data, 'cookedInstanceTransforms')
                                        for idx in range(start, start + num):
                                            new_groupname = 'wIDMi' + str(inst['nodeDataIndex']) + '_' + str(
                                                idx
                                                ) + '_' + groupname
                                            while len(new_groupname) > 63:
                                                new_groupname = new_groupname[:-1]
                                            if not transform_buffer or idx >= len(transform_buffer):
                                                print(
                                                    f'Missing cooked transform buffer data for node {i}, element {idx}'
                                                    )
                                                continue
                                            inst_trans = transform_buffer[idx]
                                            inst_m = _instance_matrix(inst, scale_factor)
                                            inst_trans_m = _instance_matrix(inst_trans)
                                            tm = inst_m @ inst_trans_m
                                            tm, axis_corrected = _apply_vertical_axis_correction(group, tm)
                                            inst_pos = inst_m.to_translation()
                                            inst_rot = inst_m.to_quaternion()
                                            inst_trans_pos = inst_trans_m.to_translation()
                                            inst_trans_rot = inst_trans_m.to_quaternion()
                                            empty_inst = _collection_instance_object(
                                                new_groupname, group, NDI_Coll, tm, color=(0.3, 0.3, 0.3, 1)
                                                )
                                            if axis_corrected:
                                                empty_inst['axisCorrection'] = 'vertical_axis_from_sector_rotation'
                                            assign_custom_properties(
                                                empty_inst, data, sectorName, i,
                                                nodeDataIndex=inst['nodeDataIndex'], mesh=meshname, Element_idx=idx
                                                )
                                            empty_inst['tl_instance_idx'] = instidx
                                            empty_inst['sub_instance_idx'] = idx
                                            empty_inst['pivot'] = inst['Pivot']
                                            empty_inst['appearanceName'] = NDI_Coll['appearanceName']
                                            empty_inst['inst_rot'] = inst_rot
                                            empty_inst['inst_pos'] = inst_pos
                                            empty_inst['inst_trans_rot'] = inst_trans_rot
                                            empty_inst['inst_trans_pos'] = inst_trans_pos
                                            if buffer_ref is not None:
                                                empty_inst['bufferID'] = int(buffer_ref)
                                    else:
                                        print('Mesh not found in masters - ', meshname, ' - ', i, e['HandleId'])

                    case 'worldStaticLightNode':
                        # print('worldStaticLightNode',i)
                        if with_lights:
                            instances = instances_by_node.get(i, [])
                            for inst in instances:
                                light_node = e['Data']
                                light_name = e['Data']['debugName']['$value']
                                light_ndata = inst
                                color = light_node['color']
                                intensity = light_node['intensity']
                                flicker = light_node['flicker']
                                area_shape = light_node['areaShape']
                                pos = get_pos(light_ndata)
                                rot = get_rot(light_ndata)

                                A_Light = bpy.data.lights.new(str(i) + '_' + light_name, 'AREA')
                                light_obj = bpy.data.objects.new(str(i) + '_' + light_name, A_Light)
                                Sector_coll.objects.link(light_obj)
                                light_obj.location = pos
                                light_obj.rotation_mode = 'QUATERNION'
                                light_obj.rotation_quaternion = rot
                                original_rot = Quaternion(rot)
                                rotation_90_x_local = Quaternion(
                                        (math.cos(math.radians(45)), math.sin(math.radians(45)), 0, 0)
                                        )
                                light_obj.rotation_quaternion = original_rot @ rotation_90_x_local
                                light_obj['flicker'] = light_node['flicker']
                                light_obj['nodeType'] = ntype
                                A_Light.energy = intensity / 10
                                A_Light.color = get_col(color)
                                A_Light.cycles.use_multiple_importance_sampling = False
                                A_Light.cycles.max_bounces = 6
                                light_obj.visible_transmission = False

                                if area_shape == 'ALS_Capsule':
                                    A_Light.shape = 'RECTANGLE'
                                    A_Light.size = 1
                                    light_obj['capsuleLength'] = light_node['capsuleLength']
                                    A_Light.size_y = 1
                                    light_obj['radius'] = light_node['radius']
                                elif area_shape == 'ALS_Sphere':
                                    A_Light.shape = 'DISK'
                                    A_Light.size = 1
                                    light_obj['radius'] = light_node['radius']

                        pass

                    case 'worldStaticParticleNode' | 'worldEffectNode' | 'worldPopulationSpawnerNode':
                        # print('worldStaticParticleNode',i)
                        instances = instances_by_node.get(i, [])
                        for idx, inst in enumerate(instances):
                            o = bpy.data.objects.new("empty", None)
                            o.name = ntype + '_' + e['Data']['debugName']['$value']
                            o['nodeType'] = ntype
                            o['nodeIndex'] = i
                            o['instance_idx'] = idx
                            o['debugName'] = e['Data']['debugName']['$value']
                            o['sectorName'] = sectorName
                            if ntype == 'worldStaticParticleNode':
                                o['particleSystem'] = e['Data']['particleSystem']['DepotPath']['$value']
                            if ntype == 'worldEffectNode':
                                o['effect'] = e['Data']['effect']['DepotPath']['$value']

                            if ntype == 'worldPopulationSpawnerNode':
                                o['appearanceName'] = e['Data']['appearanceName']['$value']
                                o['objectRecordId'] = e['Data']['objectRecordId']['$value']
                                o['spawnonstart'] = e['Data']['spawnOnStart']
                            Sector_coll.objects.link(o)
                            o.location = get_pos(inst)
                            o.rotation_mode = "QUATERNION"
                            o.rotation_quaternion = get_rot(inst)
                            o.scale = get_scale(inst)
                            o.display_type = 'WIRE'
                            o.color = (1.0, 0.005, .062, 1)
                            o.show_wire = True
                            o.display.show_shadows = False

                        pass

                    case 'worldStaticSoundEmitterNode':
                        # print(ntype)
                        instances = instances_by_node.get(i, [])
                        for idx, inst in enumerate(instances):
                            o = bpy.data.objects.new("empty", None)
                            o.empty_display_type = 'SPHERE'
                            o.name = ntype + '_' + e['Data']['debugName']['$value']
                            o['nodeType'] = ntype
                            o['nodeIndex'] = i
                            o['instance_idx'] = idx
                            o['debugName'] = e['Data']['debugName']['$value']
                            o['sectorName'] = sectorName
                            o['Settings'] = e['Data']['Settings']
                            if e['Data']['Settings']['Data']['EventsOnActive']:
                                o['eventName'] = e['Data']['Settings']['Data']['EventsOnActive'][0]['event']['$value']
                            Sector_coll.objects.link(o)
                            o.location = get_pos(inst)
                            o.rotation_mode = "QUATERNION"
                            o.rotation_quaternion = get_rot(inst)

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
        print('Nodes complete, updating view layer and saving world matrices')
        # Have to do a view_layer update or the matrices are all blank
        bpy.context.view_layer.update()
        for col in Sector_coll.children:
            if len(col.all_objects) > 0:
                col['matrix'] = col.all_objects[0].matrix_world

        print('Finished with ', filepath, ' (no ', fpn + 1, ' of ', no_sectors, ')')
    # doing this earlier in the file was breaking the entity postitioning. NO idea how that works, but be warned.
    Masters.hide_viewport = True
    for obj in bpy.data.objects:
        if 'Decal' in obj.name:
            obj['matrix'] = obj.matrix_world
    if len(roads) > 0:
        road_map = {}
        for road in roads:
            start_key = tuple(round(float(c), 2) for c in road['Startpos'])
            end_key = tuple(round(float(c), 2) for c in road['Endpos'])
            road_map.setdefault(start_key, []).append(road)
            road_map.setdefault(end_key, []).append(road)

        for road in roads:
            curve = road['Curve']
            endpoint = curve.data.splines[0].bezier_points[-1]
            end_key = tuple(round(float(c), 2) for c in road['Endpos'])
            nextroad = [r for r in road_map.get(end_key, []) if r['Name'] != road['Name']]
            if len(nextroad) == 1:
                nextroad = nextroad[0]
                nextcurve = nextroad['Curve']
                if points_within_tol(nextroad['Endpos'], road['Endpos']):
                    nextpoint = nextcurve.data.splines[0].bezier_points[-1]
                else:
                    nextpoint = nextcurve.data.splines[0].bezier_points[0]

                if points_within_tol(endpoint.handle_left, nextpoint.handle_left, 0.5):
                    lefthandlepos = average_vectors(endpoint.handle_left, nextpoint.handle_left)
                else:
                    lefthandlepos = average_vectors(endpoint.handle_left, nextpoint.handle_right)
                lh = bpy.data.objects.new("empty", None)
                lh.location = lefthandlepos
                Sector_coll.objects.link(lh)
                if points_within_tol(endpoint.handle_right, nextpoint.handle_right, 0.5):
                    righthandlepos = average_vectors(endpoint.handle_right, nextpoint.handle_right)
                else:
                    righthandlepos = average_vectors(endpoint.handle_right, nextpoint.handle_left)
                lh = bpy.data.objects.new("empty", None)
                lh.location = righthandlepos
                Sector_coll.objects.link(lh)
                nextpoint.handle_left_type = 'ALIGNED'
                nextpoint.handle_right_type = 'ALIGNED'
                endpoint.handle_left_type = 'ALIGNED'
                endpoint.handle_right_type = 'ALIGNED'
                endpoint.handle_left = lefthandlepos
                nextpoint.handle_left = lefthandlepos
                endpoint.handle_right = righthandlepos
                nextpoint.handle_right = righthandlepos
                nextpoint.co = endpoint.co
    print(f"Imported Sectors from : {wkit_proj_name} in {time.time() - start_time}")
    print('')
    print('-------------------- Finished Importing Cyberpunk 2077 Streaming Sectors --------------------')
    print('')


# The above is  the code thats for the import plugin below is to allow testing/dev, you can run this file to import something

if __name__ == "__main__":
    filepath = 'F:\\CPMod\\judysApt\\judysApt.cpmodproj'

    importSectors(filepath, with_mats=True, want_collisions=False, am_modding=False)
