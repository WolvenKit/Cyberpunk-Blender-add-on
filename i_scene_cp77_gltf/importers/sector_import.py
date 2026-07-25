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
import hashlib
import json
import math
import os
import time

from bpy_extras import anim_utils
from mathutils import Matrix, Quaternion, Vector

from .collision_mesh_import import CP77CollisionTriangleMeshJSONimport_by_hashes
from .common.collections import _remap_copied_object_references
from .common.paths import (
    depot_path as _depot_path,
    depot_path_from_value as _depot_path_from_value,
    normalize_depot_path as _normalize_depot_path,
    path_key as _path_key,
    same_path as _same_path,
    trim_name as _trim_name,
)
from .common.resources import resolve_mesh_export
from .common.values import (
    axis_value as _axis_value,
    cname_text as _cname_value,
    first_dict_value as _first_dict_value,
    nested_value as _nested_value,
)
from .entity_import import import_entity
from .import_with_materials import *
from ..collisiontools.pxbridge.io_phys import import_collider_as_actor
from .sector.context import (
    SectorContentError,
    SectorExecutionContext,
    SectorPlacementOperations,
)
from .sector.options import (
    MESH_GLB_EXTENSIONS,
    OPTIONAL_SECTOR_NODE_TYPES,
    SectorImportOptions,
)
from .sector.registry import NODE_HANDLERS
from .sector.session import SectorImportSession
from ..main.common import *

VERBOSE = True
scale_factor = 1


def _sector_warning(message):
    print(f"Sector import warning: {message}")


def _warn_missing_resource(depot_path, resolved_path='', required=False, context=''):
    if required and depot_path and not resolved_path:
        _sector_warning(f'{context}: required resource not indexed: {depot_path}')






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
    return resolve_mesh_export(asset_index, depot_path, warn=False) or None


def _project_sector_path(raw_root, project_name):
    return os.path.normcase(os.path.normpath(os.path.join(raw_root, 'base', f'{project_name}.streamingsector.json')))






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




def _new_empty(name, collection, display_size=0.25):
    obj = bpy.data.objects.new(_trim_name(name), None)
    obj.empty_display_type = 'PLAIN_AXES'
    obj.empty_display_size = display_size
    collection.objects.link(obj)
    return obj


def _copy_collection_contents(
        src_collection, dst_collection, copy_map, *, color=None, hide_armatures=True,
        ):
    for child in src_collection.children:
        child_dst = bpy.data.collections.new(child.name)
        dst_collection.children.link(child_dst)
        _copy_collection_contents(
            child,
            child_dst,
            copy_map,
            color=color,
            hide_armatures=hide_armatures,
            )
    for old_obj in src_collection.objects:
        obj = _copy_object(
            old_obj,
            color=color,
            hide_armature=hide_armatures,
            )
        copy_map[old_obj] = obj
        dst_collection.objects.link(obj)


def _copy_collection_tree_with_placement_root(
        src_collection, name, transform, color=None, hide_armatures=True, rotating=False,
        ):
    dst_root = bpy.data.collections.new(_trim_name(name))
    copy_map = {}

    _copy_collection_contents(
        src_collection,
        dst_root,
        copy_map,
        color=color,
        hide_armatures=hide_armatures,
        )
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
    return str(node_type) in OPTIONAL_SECTOR_NODE_TYPES['proxies']


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


def _matrix_values(matrix):
    return [
        float(matrix[row][column])
        for row in range(4)
        for column in range(4)
    ]






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


def _place_copied_mesh_instances(*, data, node_entry, node_index, instances, sector_name, sector_collection, masters, master_assets, meshname, mesh_appearance, resolved_path, contract, color=(0.3, 0.3, 0.3, 1), rotating=False, extra_props=None):
    node_type = data['$type']
    group, groupname = master_assets.get_mesh_master(
        masters,
        meshname,
        mesh_appearance,
    )
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
            'placementContract': contract,
            }
        if extra_props:
            properties.update(extra_props)
        assign_custom_properties(new, data, sector_name, node_index, **properties)
        assign_custom_properties(placement_root, data, sector_name, node_index, **properties)
        matrix_values = _matrix_values(node_matrix)
        new['matrix'] = matrix_values
        placement_root['matrix'] = matrix_values
        sector_collection.children.link(new)
        placed.append((new, placement_root, rotation_root, inst, instance_index))
    return placed

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

    _copy_collection_contents(
        src_collection,
        dst_root,
        copy_map,
        color=color,
        hide_armatures=hide_armatures,
        )

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


def assign_id_properties(obj, **kwargs):
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
        import_foliage=False,
        import_effects=False,
        selected_variant=None,
        import_proxies=False,
        import_acoustics=False,
        import_occluders=False,
        import_minimap=False,
        import_environment_probes=False,
        import_world_metadata=False,
        import_gi=False,
        ):
    options = SectorImportOptions(
        with_materials=bool(with_mats),
        remap_depot=bool(remap_depot),
        import_collisions=bool(want_collisions),
        am_modding=bool(am_modding),
        with_lights=bool(with_lights),
        import_foliage=bool(import_foliage),
        import_effects=bool(import_effects),
        selected_variant=selected_variant,
        import_proxies=bool(import_proxies),
        import_acoustics=bool(import_acoustics),
        import_occluders=bool(import_occluders),
        import_minimap=bool(import_minimap),
        import_environment_probes=bool(import_environment_probes),
        import_world_metadata=bool(import_world_metadata),
        import_gi=bool(import_gi),
        scale_factor=float(scale_factor),
        )
    with SectorImportSession(filepath, options) as session:
        return _importSectors_cached(
            filepath,
            with_mats,
            remap_depot,
            want_collisions,
            am_modding,
            with_lights,
            import_foliage,
            import_effects,
            selected_variant,
            import_proxies,
            import_acoustics,
            import_occluders,
            import_minimap,
            import_environment_probes,
            import_world_metadata,
            import_gi,
            session=session,
            )

def _place_world_collision_node(
        *,
        e,
        i,
        instances_by_node,
        sectorName,
        coll_scene,
        Masters,
        raw_path,
        want_collisions,
        ):
    placed = 0
    if want_collisions:
        sector_Collisions = sectorName + '_colls'
        if sector_Collisions in coll_scene.children:
            sector_Collisions_coll = bpy.data.collections.get(
                sector_Collisions
                )
        else:
            sector_Collisions_coll = bpy.data.collections.new(
                sector_Collisions
                )
            coll_scene.children.link(sector_Collisions_coll)
        inst = _first_instance(instances_by_node, i)
        if inst is None:
            return placed
        Actors = e['Data']['compiledData']['Data']['Actors']
        for idx, act in enumerate(Actors):
            [x, y, z] = get_pos(act)
            sector_Hash = e['Data']['sectorHash']
            arot = get_rot(act)
            for s, shape in enumerate(act['Shapes']):
                spos = get_pos(shape)
                srot = get_rot(shape)
                arot_q = Quaternion(
                    (arot[0], arot[1], arot[2], arot[3])
                    )
                srot_q = Quaternion(
                    (srot[0], srot[1], srot[2], srot[3])
                    )
                rot = arot_q @ srot_q
                loc = (
                    spos[0] + x,
                    spos[1] + y,
                    spos[2] + z,
                    )

                physx_shape_type = shape['ShapeType']
                bridge_shape_type = 'physicsColliderBox'

                if physx_shape_type in ('Box', 'Capsule', 'Sphere'):
                    shape_data = shape

                    if physx_shape_type == 'Box':
                        bridge_shape_type = 'physicsColliderBox'
                        if 'Size' in shape:
                            shape_data = {
                                'X': (
                                    shape['Size']['X']
                                    * act['Scale']['X']
                                    ),
                                'Y': (
                                    shape['Size']['Y']
                                    * act['Scale']['Y']
                                    ),
                                'Z': (
                                    shape['Size']['Z']
                                    * act['Scale']['Z']
                                    ),
                                }
                        else:
                            shape_data = {
                                'X': 0.5,
                                'Y': 0.5,
                                'Z': 0.5,
                                }

                    elif physx_shape_type == 'Capsule':
                        bridge_shape_type = 'physicsColliderCapsule'
                        radius = 0.5
                        if 'Size' in shape:
                            radius = (
                                shape['Size']['X']
                                * act['Scale']['X']
                                )
                        shape_data = {
                            'radius': radius,
                            'height': 1.0,
                            }

                    elif physx_shape_type == 'Sphere':
                        bridge_shape_type = 'physicsColliderSphere'
                        radius = 0.5
                        if 'Size' in shape:
                            radius = (
                                shape['Size']['X']
                                * act['Scale']['X']
                                )
                        shape_data = {'radius': radius}

                    submeshName = (
                        f'NodeDataIndex_{inst["nodeDataIndex"]}_'
                        f'Actor_{idx}_Shape_{s}'
                        )
                    physmat = shape.get(
                        'Materials',
                        [{'$value': 'Default'}],
                        )[0]['$value']

                    act_name = (
                        f'NodeDataIndex_{inst["nodeDataIndex"]}_'
                        f'Actor_{idx}'
                        )
                    act_obj = None
                    for child in sector_Collisions_coll.objects:
                        if child.name == act_name:
                            act_obj = child
                            break
                    if not act_obj:
                        act_obj = bpy.data.objects.new(
                            act_name,
                            None,
                            )
                        sector_Collisions_coll.objects.link(act_obj)
                        act_obj.location = (x, y, z)
                        act_obj.rotation_mode = "QUATERNION"
                        act_obj.rotation_quaternion = arot_q
                        act_obj['nodeType'] = 'worldCollisionNode'
                        act_obj['nodeIndex'] = i
                        act_obj['nodeDataIndex'] = inst['nodeDataIndex']
                        act_obj['ActorIdx'] = idx
                        act_obj['sectorName'] = sectorName

                    try:
                        shape_cdata = shape_data
                        if (
                            isinstance(shape_cdata, dict)
                            and ('$type' not in shape_cdata)
                        ):
                            shape_cdata['$type'] = bridge_shape_type
                            shape_cdata['localToBody'] = {
                                'position': {
                                    'X': spos[0],
                                    'Y': spos[1],
                                    'Z': spos[2],
                                    },
                                'orientation': {
                                    'r': srot[0],
                                    'i': srot[1],
                                    'j': srot[2],
                                    'k': srot[3],
                                    },
                                }
                            shape_cdata['material'] = {
                                '$value': physmat
                                }
                        obj = import_collider_as_actor(
                            shape_cdata,
                            submeshName,
                            sector_Collisions_coll,
                            act_obj,
                            )
                        if obj is not None:
                            placed += 1
                    except Exception as error:
                        print(
                            'Error importing collision shape:',
                            error,
                            )

                else:
                    meshname = sector_Hash + '_' + shape['Hash']
                    if meshname not in Masters.objects:
                        o = (
                            CP77CollisionTriangleMeshJSONimport_by_hashes(
                                sectorHashStr=sector_Hash,
                                entryHashStr=shape['Hash'],
                                project_raw_dir=raw_path,
                                )
                            )
                        if not o:
                            o = bpy.data.objects.new(
                                (
                                    'NDI_'
                                    + str(inst['nodeDataIndex'])
                                    + '_Actor_'
                                    + str(idx)
                                    + '_Shape_'
                                    + str(s)
                                    ),
                                None,
                                )
                        Masters.objects.link(o)
                    if meshname not in Masters.objects:
                        print(
                            f"Mesh {meshname} not found in Masters, "
                            "skipping collision import for this shape"
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
                    placed += 1
    return placed


def _importSectors_cached(
        filepath,
        with_mats,
        remap_depot,
        want_collisions,
        am_modding,
        with_lights,
        import_foliage,
        import_effects,
        selected_variant,
        import_proxies,
        import_acoustics,
        import_occluders,
        import_minimap,
        import_environment_probes,
        import_world_metadata,
        import_gi,
        session=None,
        ):
    if session is None:
        options = SectorImportOptions(
            with_materials=bool(with_mats),
            remap_depot=bool(remap_depot),
            import_collisions=bool(want_collisions),
            am_modding=bool(am_modding),
            with_lights=bool(with_lights),
            import_foliage=bool(import_foliage),
            import_effects=bool(import_effects),
            selected_variant=selected_variant,
            import_proxies=bool(import_proxies),
            import_acoustics=bool(import_acoustics),
            import_occluders=bool(import_occluders),
            import_minimap=bool(import_minimap),
            import_environment_probes=bool(import_environment_probes),
            import_world_metadata=bool(import_world_metadata),
            import_gi=bool(import_gi),
            scale_factor=float(scale_factor),
            )
        with SectorImportSession(filepath, options) as owned_session:
            return _importSectors_cached(
                filepath,
                with_mats,
                remap_depot,
                want_collisions,
                am_modding,
                with_lights,
                import_foliage,
                import_effects,
                selected_variant,
                import_proxies,
                import_acoustics,
                import_occluders,
                import_minimap,
                import_environment_probes,
                import_world_metadata,
                import_gi,
                session=owned_session,
                )

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
    raw_root = session.raw_root
    print('path is ', raw_root)
    project = session.project_path
    project_name = session.project_name
    optional_imports = session.options.optional_imports
    asset_index = session.asset_index
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
    mesh_jsons = list(session.files.mesh_jsons)
    anim_files = list(session.files.animation_glbs)
    app_path = list(session.files.appearance_jsons)
    rigjsons = list(session.files.rig_jsons)
    glbs = list(session.files.mesh_glbs)
    base_path = session.base_path
    raw_path = session.raw_root
    C = bpy.context
    I_want_to_break_free = False
    planned_sectors = session.planned_sectors()
    sector_entries = [
        planned.legacy_entry()
        for planned in planned_sectors
    ]

    coll_scene = C.scene.collection
    if "MasterInstances" not in coll_scene.children:
        coll_target = bpy.data.collections.new("MasterInstances")
        coll_scene.children.link(coll_target)
    else:
        coll_target = bpy.data.collections.get("MasterInstances")

    Masters = coll_target
    Masters.hide_viewport = False
    master_preparation = session.master_assets.prepare_meshes(
        planned_sectors,
        Masters,
    )
    mesh_source_paths = master_preparation.source_paths

    inst_pos = (0, 0, 0)
    inst_rot = Quaternion((0.707, 0, .707, 0))
    inst_scale = Vector((1, 1, 1))
    inst_m = Matrix.LocRotScale(inst_pos, inst_rot, inst_scale)
    no_sectors = len(sector_entries)
    sector_collections = {}
    for fpn, (planned_sector, sector_entry) in enumerate(
            zip(planned_sectors, sector_entries)
            ):
        filepath = sector_entry['filepath']
        t = sector_entry['nodeData']
        nodes = sector_entry['nodes']
        active_node_indexes = sector_entry['activeNodeIndexes']
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
        Sector_coll['importFoliage'] = optional_imports['foliage']
        Sector_coll['importEffects'] = optional_imports['effects']
        Sector_coll['importCollisions'] = optional_imports['collisions']
        Sector_coll['importLights'] = optional_imports['lights']
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
        placement_operations = SectorPlacementOperations(
            place_copied_mesh_instances=_place_copied_mesh_instances,
            copy_collection_tree_with_placement_root=(
                _copy_collection_tree_with_placement_root
            ),
            assign_custom_properties=assign_custom_properties,
            assign_id_properties=assign_id_properties,
            instance_matrix=_instance_matrix,
            instance_scale=get_scale,
            matrix_values=_matrix_values,
            animate_rotation_root=_animate_rotation_root,
            warning=_sector_warning,
            safe_json=session.safe_json,
            cname_value=_cname_value,
            nested_value=_nested_value,
            depot_path=_depot_path,
            new_collection=bpy.data.collections.new,
            collection_instance_object=_collection_instance_object,
            trim_name=_trim_name,
            copy_object=_copy_object,
            remap_copied_object_references=(
                _remap_copied_object_references
            ),
            new_empty=_new_empty,
            place_world_collision_node=(
                lambda node_context: _place_world_collision_node(
                    e=node_context.node_entry,
                    i=node_context.node_index,
                    instances_by_node={
                        node_context.node_index: list(
                            node_context.instances
                        )
                    },
                    sectorName=node_context.sector_name,
                    coll_scene=coll_scene,
                    Masters=node_context.masters,
                    raw_path=raw_path,
                    want_collisions=want_collisions,
                )
            ),
            )
        execution_context = SectorExecutionContext(
            session=session,
            planned_sector=planned_sector,
            sector_entry=sector_entry,
            sector_collection=Sector_coll,
            masters_collection=Masters,
            mesh_source_paths=mesh_source_paths,
            world_transform_buffers=world_transform_buffers,
            cooked_transform_buffers=cooked_transform_buffers,
            operations=placement_operations,
            )

        for plan in planned_sector.placement_plans():
            i = plan.node.index
            ntype = plan.node.node_type
            if limittypes and ntype not in import_types:
                continue

            binding = NODE_HANDLERS.get(ntype)
            if binding is not None and binding.has_placement:
                node_context = execution_context.node_context(plan)
                try:
                    binding.place(node_context)
                except SectorContentError as error:
                    node_context.record_error(error)
                    message = str(error)
                    print(message)
                    _sector_warning(f'{sectorName}: node {i}: {message}')
                continue

        handler_summary = execution_context.summary()
        Sector_coll['registeredHandlerNodes'] = handler_summary['handlerNodes']
        Sector_coll['registeredHandlerExpectedPlacements'] = handler_summary['expectedPlacements']
        Sector_coll['registeredHandlerActualPlacements'] = handler_summary['actualPlacements']
        Sector_coll['registeredHandlerFailedNodes'] = handler_summary['failedNodes']
        Sector_coll['registeredHandlerMismatchedNodes'] = handler_summary['mismatchedNodes']
        for placement_issue in execution_context.validation_issues():
            _sector_warning(placement_issue)

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
