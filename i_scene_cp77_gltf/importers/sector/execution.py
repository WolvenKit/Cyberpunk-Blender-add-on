from ...blender.transactions import track_created_datablock
from bisect import bisect_right
import hashlib
import json
import math
import os
import time
import traceback

import bpy

from bpy_extras import anim_utils
from mathutils import Matrix, Quaternion, Vector

from ...addon_identity import get_addon_preferences
from ..common.cache import acquire_material_cache, release_material_cache
from ..common.collections import _remap_copied_object_references
from ..common.paths import (
    depot_path as _depot_path,
    path_key as _path_key,
    same_path as _same_path,
    trim_name as _trim_name,
)
from ...assetio.values import (
    axis_value as _axis_value,
    cname_text as _cname_value,
    first_dict_value as _first_dict_value,
    nested_value as _nested_value,
)
from .context import (
    SectorContentError,
    SectorExecutionContext,
    SectorPlacementOperations,
)
from ..common.results import ImportResult, unique_messages
from ...blender.transactions import (
    BlenderImportTransaction,
    child_import_savepoint,
    rollback_import_child,
)
from .options import (
    OPTIONAL_SECTOR_NODE_TYPES,
    SectorImportOptions,
)
from .registry import NODE_HANDLERS
from .session import SectorImportSession



def _sector_warning(message):
    print(f"Sector import warning: {message}")


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


def _existing_sector_collections():
    result = {}
    for collection in bpy.data.collections:
        try:
            stored_path = collection.get("filepath", "")
        except (AttributeError, ReferenceError, TypeError):
            continue
        if stored_path:
            result[_path_key(stored_path)] = collection
    return result


def _sector_collection_for_parsed(
    scene_collection,
    parsed_sector,
    created_by_path,
    created_by_name,
    existing_by_path,
):
    filepath = parsed_sector.source_path
    path_key = _path_key(filepath)
    collection = created_by_path.get(path_key) or existing_by_path.get(path_key)
    if collection is None:
        base_name = parsed_sector.sector_name
        name = base_name
        existing = bpy.data.collections.get(name)
        if existing is not None and not _same_path(
            existing.get("filepath", ""),
            filepath,
        ):
            identity = hashlib.sha1(path_key.encode("utf-8")).hexdigest()[:8]
            name = _trim_name(f"{base_name}_{identity}")
        collection = track_created_datablock("collections", bpy.data.collections.new(name))

    created_by_path[path_key] = collection
    created_by_name.setdefault(parsed_sector.sector_name, collection)
    existing_by_path[path_key] = collection

    parent_collection = None
    if parsed_sector.parent_sector_path:
        parent_collection = created_by_path.get(
            _path_key(parsed_sector.parent_sector_path)
        )
    if parent_collection is None and parsed_sector.parent_sector:
        parent_collection = created_by_name.get(parsed_sector.parent_sector)

    if parent_collection is not None and parent_collection is not collection:
        if parent_collection.children.get(collection.name) is not collection:
            parent_collection.children.link(collection)
        if scene_collection.children.get(collection.name) is collection:
            scene_collection.children.unlink(collection)
    elif scene_collection.children.get(collection.name) is not collection:
        scene_collection.children.link(collection)
    return collection


def _link_sector_composition(
    planned_sectors,
    created_collections,
    scene_collection,
):
    for planned in planned_sectors:
        parsed = planned.parsed
        child = created_collections.get(_path_key(parsed.source_path))
        if child is None:
            continue
        linked_parent = False
        for parent_path in parsed.composition_parent_paths:
            parent = created_collections.get(_path_key(parent_path))
            if parent is None or parent is child:
                continue
            if parent.children.get(child.name) is not child:
                parent.children.link(child)
            linked_parent = True
        if linked_parent and scene_collection.children.get(child.name) is child:
            scene_collection.children.unlink(child)


def _instance_matrix(inst, scale=1):
    pos = Vector(get_pos(inst))
    rot = Quaternion(get_rot(inst))
    inst_scale = Vector(get_scale(inst))
    if scale != 1:
        inst_scale = Vector((inst_scale.x / scale, inst_scale.y / scale, inst_scale.z / scale))
    return Matrix.LocRotScale(pos, rot, inst_scale)


def _new_empty(name, collection, display_size=0.25):
    obj = track_created_datablock("objects", bpy.data.objects.new(_trim_name(name), None))
    obj.empty_display_type = 'PLAIN_AXES'
    obj.empty_display_size = display_size
    collection.objects.link(obj)
    return obj


def _copy_collection_contents(
        src_collection, dst_collection, copy_map, *, color=None, hide_armatures=True,
        ):
    for child in src_collection.children:
        child_dst = track_created_datablock("collections", bpy.data.collections.new(child.name))
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
    dst_root = track_created_datablock("collections", bpy.data.collections.new(_trim_name(name)))
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


def _variant_for_node_data(variant_indices, node_data_index):
    if len(variant_indices) < 2 or node_data_index is None:
        return None
    index = int(node_data_index)
    if all(
        start <= end
        for start, end in zip(variant_indices, variant_indices[1:])
    ):
        variant_index = bisect_right(variant_indices, index) - 1
        if (
            0 <= variant_index < len(variant_indices) - 1
            and index < variant_indices[variant_index + 1]
        ):
            return variant_index
        return None
    for variant_index, (start, end) in enumerate(
        zip(variant_indices, variant_indices[1:])
    ):
        if start <= index < end:
            return variant_index
    return None


def _ensure_child_collection(parent, name):
    for collection in parent.children:
        if (
            collection.get("semanticCollectionName") == name
            or collection.name == name
        ):
            return collection
    collection = track_created_datablock("collections", bpy.data.collections.new(_trim_name(f"{parent.name}_{name}")))
    collection["semanticCollectionName"] = name
    parent.children.link(collection)
    return collection


def _placement_node_data_index(item):
    for key in ("nodeDataIndex", "ndi"):
        value = item.get(key)
        if value is not None:
            try:
                return int(value)
            except (TypeError, ValueError):
                return None
    return None


def _is_proxy_node_type(node_type):
    return str(node_type) in OPTIONAL_SECTOR_NODE_TYPES["proxies"]


def _organize_sector_placements(
    sector_collection,
    parsed_sector,
    *,
    selected_variant=None,
    safe_json,
):
    variant_indices = parsed_sector.variant_indices
    variant_nodes = parsed_sector.variant_nodes
    variant_root = None
    variant_collections = {}
    child_cache = {}

    def semantic_child(parent, name):
        cache_key = (id(parent), name)
        collection = child_cache.get(cache_key)
        if collection is None:
            collection = _ensure_child_collection(parent, name)
            child_cache[cache_key] = collection
        return collection

    if len(variant_indices) >= 2:
        variant_root = semantic_child(sector_collection, "_Variants")
        variant_root["variantIndices"] = list(variant_indices)
        variant_root["variantCount"] = len(variant_indices) - 1
        for variant_index, (start, end) in enumerate(
            zip(variant_indices, variant_indices[1:])
        ):
            collection = semantic_child(
                variant_root,
                f"Variant_{variant_index:02d}",
            )
            collection["variantIndex"] = variant_index
            collection["nodeDataStart"] = int(start)
            collection["nodeDataEndExclusive"] = int(end)
            collection["variantNodes"] = safe_json(
                variant_nodes[variant_index]
                if variant_index < len(variant_nodes)
                else ()
            )
            is_selected = (
                selected_variant is None
                or variant_index == int(selected_variant)
            )
            collection.hide_viewport = not is_selected
            collection.hide_render = not is_selected
            collection["selectedForImport"] = is_selected
            variant_collections[variant_index] = collection

    available_variants = max(0, len(variant_indices) - 1)
    if (
        selected_variant is not None
        and not 0 <= int(selected_variant) < available_variants
    ):
        _sector_warning(
            f"{parsed_sector.sector_name}: selected variant "
            f"{selected_variant} is outside the available range"
        )

    proxy_items = []
    owner_targets = {}
    node_data = parsed_sector.indexed_node_data

    def annotate(item):
        node_data_index = _placement_node_data_index(item)
        variant_index = _variant_for_node_data(
            variant_indices,
            node_data_index,
        )
        item["variantIndex"] = (
            -1 if variant_index is None else variant_index
        )
        if node_data_index is not None and 0 <= node_data_index < len(node_data):
            record = node_data[node_data_index]
            item["nodeDataId"] = str(record.get("Id", ""))
            item["questPrefabRefHash"] = _cname_value(
                record.get("QuestPrefabRefHash", {})
            )
        if _is_proxy_node_type(item.get("nodeType", "")):
            proxy_items.append(item)
        else:
            for key in ("sourcePrefabHash", "nodeDataId"):
                value = str(item.get(key, ""))
                if value and value != "0":
                    owner_targets.setdefault(value, item)
        return variant_index

    def destination(item):
        variant_index = annotate(item)
        parent = variant_collections.get(variant_index, sector_collection)
        if _is_proxy_node_type(item.get("nodeType", "")):
            parent = semantic_child(parent, "_Proxies")
            parent["proxyDisplayCollection"] = True
            item["proxySemantic"] = True
        return parent

    protected = {"_Variants", "_Proxies"}
    for collection in tuple(sector_collection.children):
        semantic_name = collection.get("semanticCollectionName")
        if (
            semantic_name in protected
            or collection.name in protected
            or collection is variant_root
        ):
            continue
        target = destination(collection)
        if target is not sector_collection:
            if target.children.get(collection.name) is not collection:
                target.children.link(collection)
            if sector_collection.children.get(collection.name) is collection:
                sector_collection.children.unlink(collection)

    for obj in tuple(sector_collection.objects):
        target = destination(obj)
        if target is not sector_collection:
            if target.objects.get(obj.name) is not obj:
                target.objects.link(obj)
            if sector_collection.objects.get(obj.name) is obj:
                sector_collection.objects.unlink(obj)

    unresolved = 0
    resolved = 0
    for item in proxy_items:
        owner_id = str(item.get("proxyOwnerGlobalId", ""))
        owner = owner_targets.get(owner_id)
        if owner is None:
            item["proxyOwnerResolved"] = False
            unresolved += 1
            continue
        item["proxyOwnerResolved"] = True
        item["proxyOwnerName"] = owner.name
        item["proxyOwnerNodeIndex"] = int(owner.get("nodeIndex", -1))
        item["proxyOwnerNodeDataIndex"] = int(
            owner.get("nodeDataIndex", -1)
        )
        resolved += 1

    sector_collection["proxyOwnerResolvedCount"] = resolved
    sector_collection["proxyOwnerUnresolvedCount"] = unresolved


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
        channelbag = anim_utils.action_get_channelbag_for_slot(
            action,
            rotation_root.animation_data.action_slot,
        )
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


def _place_copied_mesh_instances(
    *,
    data,
    node_entry,
    node_index,
    instances,
    sector_name,
    sector_collection,
    masters,
    master_assets,
    meshname,
    mesh_appearance,
    contract,
    scale,
    color=(0.3, 0.3, 0.3, 1),
    rotating=False,
    extra_props=None,
):
    node_type = data['$type']
    group, groupname = master_assets.get_mesh_master(
        masters,
        meshname,
        mesh_appearance,
    )
    if group is None:
        message = (
            f'Mesh not found in masters - {meshname} - {node_index} - '
            f'{node_entry.get("HandleId", "")}'
        )
        print(message)
        _sector_warning(f'{sector_name}: {message}')
        return []

    placed = []
    for instance_index, inst in enumerate(instances):
        node_matrix = _instance_matrix(inst, scale)
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
    obj = track_created_datablock("objects", old_obj.copy())
    if color is not None:
        obj.color = color
    if hide_armature and 'Armature' in obj.name:
        obj.hide_viewport = True
        obj.hide_render = True
    return obj


def _collection_instance_object(name, collection, target_collection, matrix=None, color=None):
    obj = track_created_datablock("objects", bpy.data.objects.new(_trim_name(name), None))
    obj.empty_display_type = 'PLAIN_AXES'
    obj.empty_display_size = 0.25
    obj.instance_type = 'COLLECTION'
    obj.instance_collection = collection
    if color is not None:
        obj.color = color
    target_collection.objects.link(obj)
    if matrix is not None:
        obj.matrix_world = matrix
        obj['matrix'] = _matrix_values(matrix)
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
        obj[key] = json.dumps(value, separators=(',', ':'), ensure_ascii=False)
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


def _normalize_selected_variant(value):
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        _sector_warning(
            f"Invalid selected_variant {value!r}; importing all variants"
        )
        return None


def _set_sector_view_clip(scale):
    if float(scale) != 1.0:
        return
    screen = getattr(bpy.context, "screen", None)
    if screen is None:
        return
    for area in screen.areas:
        if area.type != "VIEW_3D":
            continue
        for space in area.spaces:
            if space.type == "VIEW_3D":
                space.clip_end = 50000


def _assign_sector_collection_metadata(
    collection,
    parsed_sector,
    optional_imports,
    selected_variant,
    safe_json,
):
    collection["filepath"] = parsed_sector.source_path
    collection["expectedNodes"] = len(parsed_sector.indexed_node_data)
    collection["sectorCategory"] = str(parsed_sector.category)
    collection["sectorLevel"] = int(parsed_sector.level)
    collection["sourceKind"] = str(parsed_sector.source_kind)
    collection["parentSector"] = str(parsed_sector.parent_sector)
    collection["parentSectorPath"] = str(parsed_sector.parent_sector_path)
    collection["compositionParents"] = safe_json(
        parsed_sector.composition_parents
    )
    collection["compositionParentPaths"] = safe_json(
        parsed_sector.composition_parent_paths
    )
    collection["compositionDepth"] = int(parsed_sector.composition_depth)
    collection["sourceDepotPath"] = str(parsed_sector.source_depot_path)
    collection["sectorName"] = parsed_sector.sector_name
    collection["inplaceDepotPaths"] = safe_json(
        parsed_sector.inplace_depot_paths
    )
    collection["resolvedInplacePaths"] = safe_json(
        parsed_sector.resolved_inplace_paths
    )
    collection["inplaceResolvedCount"] = len(
        parsed_sector.resolved_inplace_paths
    )
    collection["variantImportMode"] = (
        "SELECTED_VISIBLE" if selected_variant is not None else "ALL_GROUPED"
    )
    collection["selectedVariant"] = (
        int(selected_variant) if selected_variant is not None else -1
    )
    collection["importProxies"] = optional_imports["proxies"]
    collection["importFoliage"] = optional_imports["foliage"]
    collection["importEffects"] = optional_imports["effects"]
    collection["importCollisions"] = optional_imports["collisions"]
    collection["importLights"] = optional_imports["lights"]
    collection["importAcoustics"] = optional_imports["acoustics"]
    collection["importOccluders"] = optional_imports["occluders"]
    collection["importMinimapData"] = optional_imports["minimap"]
    collection["importEnvironmentProbes"] = optional_imports[
        "environment_probes"
    ]
    collection["importGIData"] = optional_imports["gi"]
    collection["importWorldMetadata"] = optional_imports["world_metadata"]
    collection["proxyDisplayMode"] = "SEPARATE_COLLECTIONS"


def _ensure_modding_collection(scene_collection, sector_name):
    name = f"{sector_name}_new"
    collection = scene_collection.children.get(name)
    if collection is not None:
        return collection
    collection = bpy.data.collections.get(name)
    if collection is None:
        collection = track_created_datablock("collections", bpy.data.collections.new(name))
    if scene_collection.children.get(collection.name) is not collection:
        scene_collection.children.link(collection)
    return collection


def _create_placement_operations(
    session,
    scene_collection,
    raw_path,
    want_collisions,
):
    def place_world_collision(node_context):
        return _place_world_collision_node(
            e=node_context.node_entry,
            i=node_context.node_index,
            instances=node_context.instances,
            sectorName=node_context.sector_name,
            coll_scene=scene_collection,
            Masters=node_context.masters,
            raw_path=raw_path,
            want_collisions=want_collisions,
            actor_objects=node_context.execution.collision_actor_objects,
        )

    return SectorPlacementOperations(
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
        remap_copied_object_references=_remap_copied_object_references,
        new_empty=_new_empty,
        place_world_collision_node=place_world_collision,
    )


def _capture_import_matrices(sector_collections, matrix_objects):
    if not sector_collections and not matrix_objects:
        return
    bpy.context.view_layer.update()

    for sector_collection in sector_collections:
        for collection in sector_collection.children:
            if "matrix" in collection:
                continue
            try:
                first_object = next(iter(collection.all_objects), None)
            except (AttributeError, ReferenceError, TypeError):
                continue
            if first_object is not None:
                collection["matrix"] = _matrix_values(
                    first_object.matrix_world
                )

    seen = set()
    for obj in matrix_objects:
        identity = id(obj)
        if identity in seen:
            continue
        seen.add(identity)
        try:
            obj["matrix"] = _matrix_values(obj.matrix_world)
        except (AttributeError, ReferenceError, TypeError):
            continue


def import_sectors(
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
    *,
    force_refresh=True,
):
    selected_variant = _normalize_selected_variant(selected_variant)
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
        scale_factor=1.0,
    )
    transaction = BlenderImportTransaction(capture_existing_state=False)
    material_cache_acquired = acquire_material_cache(options.with_materials)
    try:
        try:
            with transaction.scope():
                with SectorImportSession(
                    filepath,
                    options,
                    force_refresh=force_refresh,
                ) as session:
                    result = _import_sectors(session)
        except Exception as error:
            report = transaction.rollback()
            rollback_error = rollback_report_message(report)
            if rollback_error:
                raise RuntimeError(
                    f"{error}; rollback incomplete: {rollback_error}"
                ) from error
            raise
        if result.failures:
            report = transaction.rollback()
            failures = list(result.failures)
            rollback_error = rollback_report_message(report)
            if rollback_error:
                failures.append("Rollback incomplete: " + rollback_error)
            return ImportResult(
                created_items=(),
                warnings=result.warnings,
                failures=tuple(failures),
                label=result.label,
            )
        transaction.commit()
        return result
    finally:
        release_material_cache(material_cache_acquired)


def _place_world_collision_node(
        *,
        e,
        i,
        instances,
        sectorName,
        coll_scene,
        Masters,
        raw_path,
        want_collisions,
        actor_objects,
        ):
    placed = 0
    if want_collisions:
        from ..collision import import_collision_mesh_by_hashes
        from ...collisiontools.pxbridge.io_phys import import_collider_as_actor

        sector_Collisions = sectorName + '_colls'
        if sector_Collisions in coll_scene.children:
            sector_Collisions_coll = bpy.data.collections.get(
                sector_Collisions
                )
        else:
            sector_Collisions_coll = track_created_datablock("collections", bpy.data.collections.new(
                sector_Collisions
                ))
            coll_scene.children.link(sector_Collisions_coll)
        inst = instances[0] if instances else None
        if inst is None:
            return placed
        if not actor_objects:
            actor_objects.update(
                (child.name, child)
                for child in sector_Collisions_coll.objects
            )
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
                    act_obj = actor_objects.get(act_name)
                    if not act_obj:
                        act_obj = track_created_datablock("objects", bpy.data.objects.new(
                            act_name,
                            None,
                            ))
                        sector_Collisions_coll.objects.link(act_obj)
                        actor_objects[act_name] = act_obj
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
                            import_collision_mesh_by_hashes(
                                sector_hash=sector_Hash,
                                entry_hash=shape['Hash'],
                                project_raw_dir=raw_path,
                                )
                            )
                        if not o:
                            o = track_created_datablock("objects", bpy.data.objects.new(
                                (
                                    'NDI_'
                                    + str(inst['nodeDataIndex'])
                                    + '_Actor_'
                                    + str(idx)
                                    + '_Shape_'
                                    + str(s)
                                    ),
                                None,
                                ))
                        Masters.objects.link(o)
                    if meshname not in Masters.objects:
                        print(
                            f"Mesh {meshname} not found in Masters, "
                            "skipping collision import for this shape"
                            )
                        continue
                    o = track_created_datablock("objects", Masters.objects[meshname].copy())
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


def _import_sectors(session):
    options = session.options
    preferences = get_addon_preferences()
    verbose = not preferences.non_verbose
    if verbose:
        print()
        print(
            "-------------------- Importing Cyberpunk 2077 "
            "Streaming Sectors --------------------"
        )
        print()
        print("path is", session.raw_root)

    start_time = time.perf_counter()
    _set_sector_view_clip(options.scale_factor)
    planned_sectors = session.planned_sectors()
    optional_imports = options.optional_imports
    planning_elapsed = time.perf_counter() - start_time

    scene_collection = bpy.context.scene.collection
    masters = scene_collection.children.get("MasterInstances")
    if masters is None:
        masters = bpy.data.collections.get("MasterInstances")
        if masters is None:
            masters = track_created_datablock("collections", bpy.data.collections.new("MasterInstances"))
        if scene_collection.children.get(masters.name) is not masters:
            scene_collection.children.link(masters)
    masters.hide_viewport = False
    session.masters = masters

    warnings = []
    master_started = time.perf_counter()
    try:
        session.master_assets.prepare_meshes(
            planned_sectors,
            masters,
        )
    except Exception as error:
        message = (
            "Sector mesh-master preparation continued after failure: "
            f"{type(error).__name__}: {error}"
        )
        _sector_warning(message)
        print(traceback.format_exc())
        warnings.append(message)
    master_elapsed = time.perf_counter() - master_started
    placement_operations = _create_placement_operations(
        session,
        scene_collection,
        session.raw_root,
        options.import_collisions,
    )

    existing_by_path = _existing_sector_collections()
    sector_collections = {}
    sector_collections_by_name = {}
    matrix_sector_collections = []
    matrix_objects = []
    sector_count = len(planned_sectors)
    placement_started = time.perf_counter()

    for sector_number, planned_sector in enumerate(planned_sectors, start=1):
        parsed = planned_sector.parsed
        sector_collection = _sector_collection_for_parsed(
            scene_collection,
            parsed,
            sector_collections,
            sector_collections_by_name,
            existing_by_path,
        )
        _assign_sector_collection_metadata(
            sector_collection,
            parsed,
            optional_imports,
            options.selected_variant,
            session.safe_json,
        )
        for issue in parsed.composition_issues:
            _sector_warning(issue)
            warnings.append(issue)

        if options.am_modding:
            _ensure_modding_collection(
                scene_collection,
                parsed.sector_name,
            )

        if verbose:
            print(
                f"{sector_number - 1} Processing {len(parsed.nodes)} nodes "
                f"for sector {parsed.sector_name} "
                f"(no {sector_number} of {sector_count})"
            )

        execution_context = SectorExecutionContext(
            session=session,
            planned_sector=planned_sector,
            sector_collection=sector_collection,
            masters_collection=masters,
            world_transform_buffers=parsed.world_transform_buffers,
            cooked_transform_buffers=parsed.cooked_transform_buffers,
            operations=placement_operations,
        )

        for plan in planned_sector.placement_plans():
            binding = NODE_HANDLERS.get(plan.node.node_type)
            if binding is None or not binding.has_placement:
                continue
            node_context = execution_context.node_context(plan)
            child_state = child_import_savepoint()
            try:
                binding.place(node_context)
            except Exception as error:
                rollback_import_child(
                    child_state,
                    f"sector node {parsed.sector_name}:{plan.node.index}",
                )
                node_context.record_error(error)
                message = (
                    f"{parsed.sector_name}: node {plan.node.index} "
                    f"{plan.node.node_type} skipped: "
                    f"{type(error).__name__}: {error}"
                )
                _sector_warning(message)
                warnings.append(message)
                if not isinstance(error, SectorContentError):
                    print(traceback.format_exc())

        summary = execution_context.summary()
        sector_collection["registeredHandlerNodes"] = summary[
            "handlerNodes"
        ]
        sector_collection["registeredHandlerExpectedPlacements"] = summary[
            "expectedPlacements"
        ]
        sector_collection["registeredHandlerActualPlacements"] = summary[
            "actualPlacements"
        ]
        sector_collection["registeredHandlerFailedNodes"] = summary[
            "failedNodes"
        ]
        sector_collection["registeredHandlerMismatchedNodes"] = summary[
            "mismatchedNodes"
        ]
        for issue in execution_context.validation_issues():
            _sector_warning(issue)
            warnings.append(issue)

        child_state = child_import_savepoint()
        try:
            _organize_sector_placements(
                sector_collection,
                parsed,
                selected_variant=options.selected_variant,
                safe_json=session.safe_json,
            )
        except Exception as error:
            rollback_import_child(
                child_state,
                f"sector placement organization {parsed.sector_name}",
            )
            message = (
                f"{parsed.sector_name}: placement organization skipped: "
                f"{type(error).__name__}: {error}"
            )
            _sector_warning(message)
            print(traceback.format_exc())
            warnings.append(message)
        matrix_sector_collections.append(sector_collection)
        matrix_objects.extend(execution_context.matrix_objects)

        if verbose:
            print(
                f"Finished with {parsed.source_path} "
                f"(no {sector_number} of {sector_count})"
            )

    placement_elapsed = time.perf_counter() - placement_started
    finalization_started = time.perf_counter()
    try:
        _link_sector_composition(
            planned_sectors,
            sector_collections,
            scene_collection,
        )
    except Exception as error:
        message = (
            "Sector composition linking skipped: "
            f"{type(error).__name__}: {error}"
        )
        _sector_warning(message)
        print(traceback.format_exc())
        warnings.append(message)
    try:
        _capture_import_matrices(
            matrix_sector_collections,
            matrix_objects,
        )
    except Exception as error:
        message = (
            "Sector import-matrix capture skipped: "
            f"{type(error).__name__}: {error}"
        )
        _sector_warning(message)
        print(traceback.format_exc())
        warnings.append(message)
    masters.hide_viewport = True
    finalization_elapsed = time.perf_counter() - finalization_started

    if verbose:
        elapsed = time.perf_counter() - start_time
        print(
            f"Imported Sectors from: "
            f"{os.path.basename(session.project_filepath)} in {elapsed}"
        )
        print(
            "Sector phases: "
            f"planning={planning_elapsed:.3f}s, "
            f"masters={master_elapsed:.3f}s, "
            f"placement={placement_elapsed:.3f}s, "
            f"finalization={finalization_elapsed:.3f}s"
        )
        print()
        print(
            "-------------------- Finished Importing Cyberpunk 2077 "
            "Streaming Sectors --------------------"
        )
        print()

    return ImportResult(
        created_items=tuple(matrix_sector_collections),
        warnings=unique_messages(warnings),
        label="sector import",
    )
