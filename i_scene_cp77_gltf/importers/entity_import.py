# Blender Entity import script by Simarilius
# Updated May 23 with vehicle rig support
import json
import re
import os
import bpy
import time
import math
import traceback
from mathutils import Vector, Matrix , Quaternion
from ..main.common import *
from ..jsontool import JSONTool
from .phys_import import cp77_phys_import
from ..collisiontools.pxbridge.io_phys import import_collider_as_actor
from .import_common import *
from ..datakrash import DepotAssetIndex
from .read_rig import create_armature_from_data
from bpy_extras import anim_utils

SUBMESH_PATTERN = re.compile(r"submesh_(\d+)", re.IGNORECASE)
_SUBMESH_INDEX_CACHE = {}
ARMATURE_TYPE = 'ARMATURE'
_RIG_ARMATURE_OBJECT_CACHE = {}
_ARMATURE_BONE_SET_CACHE = {}
FIXED_POINT_DIVISOR = 131072


def create_axes(ent_coll,name):
    if name not in ent_coll.objects:
        o = bpy.data.objects.new( name , None )

        ent_coll.objects.link( o )
        o.empty_display_size = .5
        o.empty_display_type = 'PLAIN_AXES'
        orig_rot= o.rotation_quaternion
        o.rotation_mode='XYZ'
    else:
        o=ent_coll.objects[name]
    return o


def cname_value(value, default=''):
    if isinstance(value, dict):
        return value.get('$value', default)
    return value if value is not None else default


def component_name(component, default=''):
    return cname_value(component.get('name'), default) if isinstance(component, dict) else default


def depot_path_value(component, key):
    resource = component.get(key) if isinstance(component, dict) else None
    if not isinstance(resource, dict):
        return ''
    depot_path = resource.get('DepotPath')
    return cname_value(depot_path)


def mesh_component_depot(component):
    return depot_path_value(component, 'mesh') or depot_path_value(component, 'graphicsMesh')


def mesh_appearance_value(component):
    value = component.get('meshAppearance') if isinstance(component, dict) else None
    return cname_value(value, 'default')


def red_quaternion(value):
    if not isinstance(value, dict):
        return Quaternion((1, 0, 0, 0))
    return Quaternion((
        value.get('r', 1),
        value.get('i', 0),
        value.get('j', 0),
        value.get('k', 0),
    ))


def position_axis_value(data, fixed_key, float_key):
    value = data.get(fixed_key) if isinstance(data, dict) else None
    if isinstance(value, dict):
        return value.get('Bits', 0) / FIXED_POINT_DIVISOR
    return data.get(float_key, 0) if isinstance(data, dict) else 0


def position_vector(data):
    return Vector((
        position_axis_value(data, 'x', 'X'),
        position_axis_value(data, 'y', 'Y'),
        position_axis_value(data, 'z', 'Z'),
    ))


def fixed_point_position(transform):
    position = transform.get('Position', {}) if isinstance(transform, dict) else {}
    return position_vector(position)


def component_local_transform(component):
    transform = component.get('localTransform', {}) if isinstance(component, dict) else {}
    return fixed_point_position(transform), red_quaternion(transform.get('Orientation'))


def is_component_enabled(component):
    return component.get('isEnabled', 1) != 0 if isinstance(component, dict) else True


def depot_to_local_path(root, depot_path):
    return os.path.join(root, depot_path).replace('\\', os.sep) if depot_path else ''


def depot_to_glb_path(root, depot_path):
    local_path = depot_to_local_path(root, depot_path)
    if not local_path:
        return ''
    return os.path.splitext(local_path)[0] + '.glb'


def norm_path_key(value):
    return os.path.normcase(os.path.normpath(value)) if value else ''


def anim_json_path_from_glb(anim_path):
    return os.path.splitext(anim_path)[0] + '.json'


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


ASSET_INDEX_EXTENSIONS = (
    '.app.json',
    '.glb',
    '.mesh.json',
    '.anims.glb',
    '.anims.json',
    '.rig.json',
    '.phys.json',
)


def split_source_raw_root(filepath):
    if not filepath:
        return '', ''
    normalized = os.path.normpath(filepath)
    lowered = normalized.replace('\\', '/').lower()
    marker = '/source/raw'
    marker_index = lowered.find(marker)
    if marker_index < 0:
        marker = 'source/raw'
        marker_index = lowered.find(marker)
    if marker_index < 0:
        root = os.path.dirname(normalized)
        return root, os.path.basename(normalized)
    end = marker_index + len(marker)
    root = normalized[:end].replace('/', os.sep)
    remainder = normalized[end:].lstrip('/\\')
    return root, remainder.replace('/', os.sep)


def build_asset_index(root):
    return DepotAssetIndex.cached(root, ASSET_INDEX_EXTENSIONS)


def indexed_asset_files(asset_index, extension, provided=None):
    if provided:
        return sorted(os.path.normpath(path) for path in provided)
    return asset_index.get_files_by_extension(extension)


def resolve_app_json_path(asset_index, depot_path):
    return asset_index.resolve_app_json(depot_path)


def resolve_mesh_glb_path(asset_index, depot_path):
    return asset_index.resolve_mesh_glb(depot_path)


def resolve_mesh_json_path(asset_index, depot_path):
    return asset_index.resolve_mesh_json(depot_path)


def resolve_rig_json_path(asset_index, depot_path):
    return asset_index.resolve_rig_json(depot_path)


def resolve_anim_glb_path(asset_index, depot_path):
    return asset_index.resolve_anim_glb(depot_path)


def resolve_anim_json_path_from_glb(asset_index, anim_path):
    return asset_index.resolve_anim_json_from_glb(anim_path)


def build_component_lookup(components):
    lookup = {}
    for component in components or []:
        name = component_name(component)
        if name:
            lookup[name] = component
    return lookup


def build_ent_app_lookup(ent_apps):
    by_appearance = {}
    by_name = {}
    for index, app in enumerate(ent_apps or []):
        appearance = cname_value(app.get('appearanceName'))
        if appearance:
            by_appearance[appearance] = index
        name = cname_value(app.get('name'))
        if name:
            by_name[name] = index
    return by_appearance, by_name


def default_appearance_from_json(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as handle:
            root = json.load(handle)
    except Exception:
        return ''
    root_chunk = root.get('Data', {}).get('RootChunk', {}) if isinstance(root, dict) else {}
    return cname_value(root_chunk.get('defaultAppearance'))


def normalize_default_appearance(ent_default, ent_apps, by_appearance, by_name, filepath):
    candidates = []
    if ent_default and ent_default != 'None':
        candidates.append(ent_default)
    json_default = default_appearance_from_json(filepath)
    if json_default and json_default != 'None' and json_default not in candidates:
        candidates.append(json_default)

    for candidate in candidates:
        if candidate in by_appearance:
            return candidate
        by_name_idx = by_name.get(candidate, -1)
        if by_name_idx >= 0:
            return cname_value(ent_apps[by_name_idx].get('appearanceName'), candidate)
    return candidates[0] if candidates else ''


def resolve_requested_appearance_name(app_name, ent_default, ent_apps, by_appearance, by_name):
    if app_name == 'default':
        return ent_default or 'default'
    return app_name


def resolve_ent_app(app_name, ent_apps, by_appearance, by_name, ent_default=None):
    ent_app_idx = by_appearance.get(app_name, -1)
    if ent_app_idx >= 0:
        print('appearance matched, id = ', ent_app_idx)
        return ent_app_idx, app_name
    ent_app_idx = by_name.get(app_name, -1)
    if ent_app_idx >= 0:
        print('appearance matched, id = ', ent_app_idx)
        return ent_app_idx, cname_value(ent_apps[ent_app_idx].get('appearanceName'), app_name)
    if app_name != 'default':
        return 0, cname_value(ent_apps[0].get('appearanceName'), app_name) if ent_apps else app_name
    ent_app_idx = by_name.get(ent_default, -1)
    if ent_app_idx >= 0:
        print('appearance matched, id = ', ent_app_idx)
        return ent_app_idx, cname_value(ent_apps[ent_app_idx].get('appearanceName'), app_name)
    ent_app_idx = by_appearance.get(ent_default, -1)
    if ent_app_idx >= 0:
        print('appearance matched, id = ', ent_app_idx)
        return ent_app_idx, cname_value(ent_apps[ent_app_idx].get('appearanceName'), app_name)
    return 0, cname_value(ent_apps[0].get('appearanceName'), app_name) if ent_apps else app_name


def build_chunk_lookup(chunks, target_key, handle_key='HandleId'):
    lookup = {}
    for chunk in chunks or []:
        if not isinstance(chunk, dict):
            continue
        target_data = chunk.get(target_key)
        if isinstance(target_data, dict) and handle_key in target_data:
            lookup[target_data[handle_key]] = target_data
    return lookup


def build_parent_transform_lookup(chunks):
    return build_chunk_lookup(chunks, 'parentTransform')


def build_skinning_lookup(chunks):
    return build_chunk_lookup(chunks, 'skinning')


class ComponentHandleLookup:
    def __init__(self, default_lookup=None):
        self.default_lookup = default_lookup or {}
        self.by_component_id = {}

    def set_component_lookup(self, component, lookup):
        if isinstance(component, dict):
            self.by_component_id[id(component)] = lookup or {}

    def get_for_component(self, component, handle_id):
        lookup = self.by_component_id.get(id(component), self.default_lookup)
        return lookup.get(handle_id)

    def get(self, handle_id):
        return self.default_lookup.get(handle_id)


def build_anim_impl_lookup(chunks):
    lookup = {}
    if not chunks:
        return lookup
    for chunk in chunks:
        if not isinstance(chunk, dict) or chunk.get('$type') != 'gameTransformAnimatorComponent':
            continue
        try:
            impl = chunk['animations'][0]['timeline']['items'][0]['impl']
        except (KeyError, IndexError, TypeError):
            continue
        if 'HandleId' in impl:
            lookup[int(impl['HandleId'])] = impl.get('Data')
    return lookup


def build_slot_lookup(vehicle_slots):
    lookup = {}
    for slot in vehicle_slots or []:
        name = cname_value(slot.get('slotName'))
        if name:
            lookup[name] = slot
    return lookup


def resolve_slot_bone(slot_lookup, slotname, fallback=None):
    slot = slot_lookup.get(slotname) if slot_lookup else None
    return cname_value(slot.get('boneName'), fallback) if slot else fallback


_RIG_BONE_INDEX_CACHE = {}
_RIG_BONE_MATRIX_CACHE = {}


def build_rig_bone_index(rig_j):
    if not rig_j or not rig_j.get('boneNames'):
        return {}
    out = {}
    for index, bone in enumerate(rig_j['boneNames']):
        name = cname_value(bone)
        if name:
            out[name] = index
    return out


def rig_bone_index_for(rig_j):
    if not isinstance(rig_j, dict):
        return {}
    cache_key = id(rig_j)
    index = _RIG_BONE_INDEX_CACHE.get(cache_key)
    if index is None:
        index = build_rig_bone_index(rig_j)
        _RIG_BONE_INDEX_CACHE[cache_key] = index
    return index


def rig_json_bone_matrix(rig_j, bone_name, rig_bone_index=None):
    if not isinstance(rig_j, dict) or not bone_name:
        return Matrix.Identity(4)
    rig_id = id(rig_j)
    matrices = _RIG_BONE_MATRIX_CACHE.get(rig_id)
    if matrices is None:
        matrices = {}
        _RIG_BONE_MATRIX_CACHE[rig_id] = matrices
    cached = matrices.get(bone_name)
    if cached is not None:
        return cached
    index = (rig_bone_index or rig_bone_index_for(rig_j)).get(bone_name)
    if index is None:
        matrices[bone_name] = Matrix.Identity(4)
        return matrices[bone_name]
    for key in ('aPoseMS', 'boneTransforms', 'aPoseLS'):
        transforms = rig_j.get(key)
        if isinstance(transforms, list) and index < len(transforms):
            matrices[bone_name] = qs_transform_matrix(transforms[index])
            return matrices[bone_name]
    matrices[bone_name] = Matrix.Identity(4)
    return matrices[bone_name]


def build_slot_owner_rig_jsons(components, parent_transform_lookup, rig_json_by_component_name):
    slot_owner_rig_jsons = {}
    if not components or not rig_json_by_component_name:
        return slot_owner_rig_jsons
    for component in components:
        if not isinstance(component, dict) or component.get('$type') != 'entSlotComponent':
            continue
        owner_name = component_name(component)
        if not owner_name:
            continue
        binding = parent_transform_data(component, parent_transform_lookup)
        bind_name = cname_value(binding.get('bindName')) if isinstance(binding, dict) else ''
        rig_json = rig_json_by_component_name.get(bind_name)
        if rig_json is not None:
            slot_owner_rig_jsons[owner_name] = rig_json
    return slot_owner_rig_jsons


def build_slot_owner_rig_owner_names(components, parent_transform_lookup, rig_component_names):
    slot_owner_rig_owner_names = {}
    if not components or not rig_component_names:
        return slot_owner_rig_owner_names
    for component in components:
        if not isinstance(component, dict) or component.get('$type') != 'entSlotComponent':
            continue
        owner_name = component_name(component)
        if not owner_name:
            continue
        binding = parent_transform_data(component, parent_transform_lookup)
        bind_name = cname_value(binding.get('bindName')) if isinstance(binding, dict) else ''
        if bind_name in rig_component_names:
            slot_owner_rig_owner_names[owner_name] = bind_name
    return slot_owner_rig_owner_names



def is_excluded_mesh(depot_path, meshpath, meshname, excluded_meshes):
    if not excluded_meshes:
        return False
    if meshpath and norm_path_key(meshpath) in excluded_meshes:
        return True
    if meshname and norm_path_key(meshname) in excluded_meshes:
        return True
    if depot_path:
        if norm_path_key(depot_path) in excluded_meshes:
            return True
        if norm_path_key(os.path.basename(depot_path.replace('\\', os.sep))) in excluded_meshes:
            return True
    return False



def red_scale(transform, visual_scale=None):
    scale = transform.get('Scale') or transform.get('scale') if isinstance(transform, dict) else None
    if not isinstance(scale, dict) and isinstance(visual_scale, dict):
        scale = visual_scale
    if not isinstance(scale, dict):
        return Vector((1, 1, 1))
    return Vector((
        scale.get('X', 1),
        scale.get('Y', 1),
        scale.get('Z', 1),
    ))


def vector_from_transform_position(transform, keys):
    if not isinstance(transform, dict):
        return Vector((0, 0, 0))
    for key in keys:
        data = transform.get(key)
        if isinstance(data, dict):
            return position_vector(data)
    return Vector((0, 0, 0))


def first_transform_value(transform, keys):
    if not isinstance(transform, dict):
        return {}
    for key in keys:
        value = transform.get(key)
        if isinstance(value, dict):
            return value
    return {}


def transform_dict_matrix(transform, pos_keys=('Position', 'Translation', 'relativePosition'), rot_keys=('Orientation', 'Rotation', 'relativeRotation'), scale=None):
    if not isinstance(transform, dict):
        return Matrix.Identity(4)
    return Matrix.LocRotScale(
        vector_from_transform_position(transform, pos_keys),
        red_quaternion(first_transform_value(transform, rot_keys)),
        scale if scale is not None else red_scale(transform),
    )


def red_transform_matrix(transform, visual_scale=None):
    if not isinstance(transform, dict):
        return Matrix.Identity(4)
    return transform_dict_matrix(
        transform,
        ('Position',),
        ('Orientation',),
        red_scale(transform, visual_scale),
    )


def slot_transform_matrix(slot):
    return transform_dict_matrix(
        slot,
        ('relativePosition',),
        ('relativeRotation',),
        Vector((1, 1, 1)),
    )


def slot_translation_matrix(slot):
    if not isinstance(slot, dict):
        return Matrix.Identity(4)
    return Matrix.Translation(vector_from_transform_position(slot, ('relativePosition',)))


def qs_transform_matrix(transform):
    return transform_dict_matrix(
        transform,
        ('Translation', 'Position'),
        ('Rotation', 'Orientation'),
        red_scale(transform),
    )


def resolve_handle_data(component, lookup, key, fallback_to_inline=False):
    data = component.get(key) if isinstance(component, dict) else None
    if not isinstance(data, dict):
        return None
    if isinstance(data.get('Data'), dict):
        return data.get('Data')

    handle_id = data.get('HandleRefId')
    if handle_id is None:
        return data if fallback_to_inline else None

    if hasattr(lookup, 'get_for_component'):
        referenced = lookup.get_for_component(component, handle_id)
    else:
        referenced = lookup.get(handle_id) if lookup else None
    if isinstance(referenced, dict):
        return referenced.get('Data')
    return data if fallback_to_inline else None


def parent_transform_data(component, parent_transform_lookup):
    return resolve_handle_data(component, parent_transform_lookup, 'parentTransform')


def skinning_binding_data(component, skinning_lookup=None):
    return resolve_handle_data(component, skinning_lookup, 'skinning', fallback_to_inline=True)


def skinning_bind_name(component, skinning_lookup=None):
    data = skinning_binding_data(component, skinning_lookup)
    return cname_value(data.get('bindName')) if isinstance(data, dict) else ''


def component_uses_skinning(component, skinning_lookup=None):
    bind_name = skinning_bind_name(component, skinning_lookup)
    return bool(bind_name and bind_name != 'None')


def component_uses_deformation_skinning(component, skinning_lookup=None):
    return component_uses_skinning(component, skinning_lookup)


def find_collection_armature(objects):
    for obj in objects:
        if getattr(obj, 'type', None) == ARMATURE_TYPE:
            return obj
    for obj in objects:
        parent = getattr(obj, 'parent', None)
        if parent is not None and getattr(parent, 'type', None) == ARMATURE_TYPE:
            return parent
        for modifier in getattr(obj, 'modifiers', []):
            if modifier.type == 'ARMATURE' and getattr(modifier, 'object', None):
                return modifier.object
    return None


def selected_armatures():
    return [obj for obj in bpy.context.selected_objects if getattr(obj, 'type', None) == ARMATURE_TYPE]


def active_armature():
    obj = bpy.context.view_layer.objects.active
    return obj if getattr(obj, 'type', None) == ARMATURE_TYPE else None


def imported_armatures_from_selection():
    selected = selected_armatures()
    if selected:
        return selected
    active = active_armature()
    return [active] if active is not None else []


def child_of_inverse_matrix(target, subtarget_name=''):
    target_matrix = target.matrix_world.copy()
    if subtarget_name and getattr(target, 'pose', None) and subtarget_name in target.pose.bones:
        target_matrix = target.matrix_world @ target.pose.bones[subtarget_name].matrix
    try:
        return target_matrix.inverted()
    except Exception:
        return Matrix.Identity(4)


def set_child_of_inverse(constraint, target, subtarget_name=''):
    constraint.inverse_matrix = child_of_inverse_matrix(target, subtarget_name)

def existing_armature_for_rig_json(rig_json_path):
    target = norm_path_key(rig_json_path)
    if not target:
        return None
    cached = _RIG_ARMATURE_OBJECT_CACHE.get(target)
    if cached is not None and cached.name in bpy.data.objects:
        cache_armature_bones(cached)
        return cached

    expected_name = os.path.basename(rig_json_path).replace('.rig.json', '')
    direct = bpy.data.objects.get(expected_name)
    if getattr(direct, 'type', None) == ARMATURE_TYPE:
        cache_armature_bones(direct)
        _RIG_ARMATURE_OBJECT_CACHE[target] = direct
        return direct

    return None


def ensure_armature_from_rig_json(rig_json_path, component_name_value='', ent_name=''):
    if not rig_json_path:
        return None
    existing = existing_armature_for_rig_json(rig_json_path)
    if existing is not None:
        return existing

    created = create_armature_from_data(rig_json_path, "T-Pose", False)

    if getattr(created, 'type', None) == ARMATURE_TYPE:
        armature = created
    else:
        armature = None
        if isinstance(created, (list, tuple)):
            for item in created:
                if getattr(item, 'type', None) == ARMATURE_TYPE:
                    armature = item
                    break
        if armature is None:
            selected = imported_armatures_from_selection()
            if selected:
                armature = selected[0]

    if armature is not None:
        cache_armature_bones(armature)
        _RIG_ARMATURE_OBJECT_CACHE[norm_path_key(rig_json_path)] = armature
        armature['rig'] = rig_json_path
        armature['source_rig_file'] = rig_json_path
        if component_name_value:
            armature['componentName'] = component_name_value
        if ent_name:
            armature['ent'] = ent_name + '.ent.json'
    return armature


def cache_armature_bones(armature):
    if not armature or getattr(armature, 'type', None) != ARMATURE_TYPE or not getattr(armature, 'pose', None):
        return set()
    cache_key = id(armature)
    cached = _ARMATURE_BONE_SET_CACHE.get(cache_key)
    if cached is not None and cached[0] is armature:
        return cached[1]
    bone_set = set(armature.pose.bones.keys())
    _ARMATURE_BONE_SET_CACHE[cache_key] = (armature, bone_set)
    return bone_set


def armature_has_bone(armature, bone_name):
    return bool(armature and bone_name and bone_name in cache_armature_bones(armature))


def remap_copied_object_references(copied_objects, object_map):
    modifier_targets = 0
    parent_targets = 0
    constraint_targets = 0
    for obj in copied_objects:
        parent = getattr(obj, 'parent', None)
        if parent in object_map:
            world = obj.matrix_world.copy()
            obj.parent = object_map[parent]
            obj.matrix_world = world
            parent_targets += 1
        for modifier in getattr(obj, 'modifiers', []):
            target = getattr(modifier, 'object', None)
            if target in object_map:
                modifier.object = object_map[target]
                modifier_targets += 1
        for constraint in getattr(obj, 'constraints', []):
            target = getattr(constraint, 'target', None)
            if target in object_map:
                constraint.target = object_map[target]
                constraint_targets += 1
    return modifier_targets, parent_targets, constraint_targets


def bind_skinned_objects_to_rig(objects, rig):
    if rig is None:
        return 0, 0
    retargeted = 0
    reparented = 0
    for obj in objects:
        if getattr(obj, 'type', None) != 'MESH':
            continue
        for modifier in getattr(obj, 'modifiers', []):
            if modifier.type != 'ARMATURE':
                continue
            if modifier.object != rig:
                modifier.object = rig
                retargeted += 1
        parent = getattr(obj, 'parent', None)
        if parent is not None and getattr(parent, 'type', None) == 'ARMATURE' and parent != rig:
            world = obj.matrix_world.copy()
            obj.parent = rig
            obj.matrix_parent_inverse = rig.matrix_world.inverted()
            obj.matrix_world = world
            reparented += 1
    return retargeted, reparented




def build_slot_component_lookups(components):
    lookups = {}
    for component in components or []:
        slots = component.get('slots') if isinstance(component, dict) else None
        name = component_name(component)
        if name and isinstance(slots, list):
            lookups[name] = build_slot_lookup(slots)
    return lookups


class EntityTransformResolver:
    def __init__(self, components, parent_transform_lookup, skinning_lookup=None, rig=None, rig_j=None, rig_bone_index=None, default_slot_lookup=None, slot_owner_rig_jsons=None, rig_json_by_component_name=None, armature_by_component_name=None, slot_owner_rig_owner_names=None):
        self.components = components or []
        self.components_by_name = build_component_lookup(self.components)
        self.parent_transform_lookup = parent_transform_lookup or {}
        self.skinning_lookup = skinning_lookup or {}
        self.slot_component_lookups = build_slot_component_lookups(self.components)
        self.rig = rig
        self.rig_j = rig_j
        self.rig_bone_index = rig_bone_index or build_rig_bone_index(rig_j)
        self.slot_owner_rig_jsons = slot_owner_rig_jsons or {}
        self.rig_json_by_component_name = rig_json_by_component_name or {}
        self.armature_by_component_name = armature_by_component_name or {}
        self.slot_owner_rig_owner_names = slot_owner_rig_owner_names or {}
        self.rig_json_bone_indices = {id(rig_json): build_rig_bone_index(rig_json) for rig_json in self.rig_json_by_component_name.values() if isinstance(rig_json, dict)}
        if isinstance(self.rig_j, dict):
            self.rig_json_bone_indices[id(self.rig_j)] = self.rig_bone_index
        self.default_slot_lookup = default_slot_lookup or {}
        self.cache = {}
        self.local_matrix_cache = {}
        self.binding_cache = {}
        self.slot_matrix_cache = {}
        self.armature_for_bone_cache = {}
        self.bone_matrix_cache = {}
        self.bone_rotation_cache = {}
        self.bone_head_cache = {}
        self.rig_space_bone_matrix_cache = {}
        self.rig_json_for_bone_cache = {}
        self.resolving = set()

    def _slot_owner_rig_json(self, slot_owner=None):
        if slot_owner and slot_owner in self.slot_owner_rig_jsons:
            return self.slot_owner_rig_jsons[slot_owner]
        return self.rig_j

    def _binding_data(self, component):
        key = id(component)
        binding = self.binding_cache.get(key)
        if binding is None and key not in self.binding_cache:
            binding = parent_transform_data(component, self.parent_transform_lookup)
            self.binding_cache[key] = binding
        return binding

    def _local_matrix(self, component, transform=None, visual_scale=None):
        key = id(component)
        matrix = self.local_matrix_cache.get(key)
        if matrix is None:
            if transform is None:
                transform = component.get('localTransform', {}) if isinstance(component, dict) else {}
            if visual_scale is None and isinstance(component, dict):
                visual_scale = component.get('visualScale')
            matrix = red_transform_matrix(transform, visual_scale)
            self.local_matrix_cache[key] = matrix
        return matrix

    def _rig_json_index(self, rig_j):
        if not isinstance(rig_j, dict):
            return {}
        index = self.rig_json_bone_indices.get(id(rig_j))
        if index is None:
            index = rig_bone_index_for(rig_j)
            self.rig_json_bone_indices[id(rig_j)] = index
        return index

    def _rig_json_has_bone(self, bone_name, rig_j=None):
        return bool(bone_name and bone_name in self._rig_json_index(rig_j))

    def _rig_json_for_bone(self, bone_name, slot_owner=None):
        cache_key = (bone_name, slot_owner)
        if cache_key in self.rig_json_for_bone_cache:
            return self.rig_json_for_bone_cache[cache_key]
        preferred = self._slot_owner_rig_json(slot_owner)
        if self._rig_json_has_bone(bone_name, preferred):
            self.rig_json_for_bone_cache[cache_key] = preferred
            return preferred
        for rig_json in self.rig_json_by_component_name.values():
            if rig_json is not preferred and self._rig_json_has_bone(bone_name, rig_json):
                self.rig_json_for_bone_cache[cache_key] = rig_json
                return rig_json
        self.rig_json_for_bone_cache[cache_key] = preferred
        return preferred

    def _slot_owner_rig_owner_name(self, slot_owner=None):
        if slot_owner and slot_owner in self.slot_owner_rig_owner_names:
            return self.slot_owner_rig_owner_names[slot_owner]
        return ''

    def _armature_for_bone(self, bone_name, slot_owner=None):
        if not bone_name:
            return None
        cache_key = (bone_name, slot_owner)
        if cache_key in self.armature_for_bone_cache:
            return self.armature_for_bone_cache[cache_key]
        owner_name = self._slot_owner_rig_owner_name(slot_owner)
        if owner_name:
            armature = self.armature_by_component_name.get(owner_name)
            if armature_has_bone(armature, bone_name):
                self.armature_for_bone_cache[cache_key] = armature
                return armature
        if armature_has_bone(self.rig, bone_name):
            self.armature_for_bone_cache[cache_key] = self.rig
            return self.rig
        for armature in self.armature_by_component_name.values():
            if armature_has_bone(armature, bone_name):
                self.armature_for_bone_cache[cache_key] = armature
                return armature
        self.armature_for_bone_cache[cache_key] = None
        return None

    def _pose_bone(self, bone_name, slot_owner=None):
        armature = self._armature_for_bone(bone_name, slot_owner)
        if armature is not None:
            return armature, armature.pose.bones[bone_name]
        return None, None

    def bone_matrix(self, bone_name, slot_owner=None):
        cache_key = (bone_name, slot_owner)
        cached = self.bone_matrix_cache.get(cache_key)
        if cached is not None:
            return cached
        armature, pose_bone = self._pose_bone(bone_name, slot_owner)
        if pose_bone is not None:
            matrix = armature.matrix_world @ pose_bone.matrix
        else:
            rig_j = self._rig_json_for_bone(bone_name, slot_owner)
            if self._rig_json_has_bone(bone_name, rig_j):
                matrix = rig_json_bone_matrix(rig_j, bone_name, self._rig_json_index(rig_j))
            else:
                matrix = Matrix.Identity(4)
        self.bone_matrix_cache[cache_key] = matrix
        return matrix

    def resolve_slot_matrix(self, slot_owner, slot_name):
        cache_key = (slot_owner, slot_name)
        cached = self.slot_matrix_cache.get(cache_key)
        if cached is not None:
            return cached
        slot = self._slot(slot_owner, slot_name)
        if not slot:
            result = (Matrix.Identity(4), slot_owner, slot_name)
        else:
            bone_name = cname_value(slot.get('boneName'), slot_name)
            result = (self.bone_matrix(bone_name, slot_owner) @ slot_transform_matrix(slot), bone_name, slot_name)
        self.slot_matrix_cache[cache_key] = result
        return result

    def resolve_binding(self, component):
        binding = self._binding_data(component)
        if not isinstance(binding, dict):
            return Matrix.Identity(4), '', '', 'none'

        bind_name = cname_value(binding.get('bindName'))
        slot_name = cname_value(binding.get('slotName'))
        if not bind_name or bind_name == 'None':
            return Matrix.Identity(4), bind_name, slot_name, 'none'

        if bind_name in ('vehicle_slots', 'slots'):
            matrix, bone_name, slot_name = self.resolve_slot_matrix(bind_name, slot_name)
            return matrix, bone_name, slot_name, 'slot'

        if bind_name == 'deformation_rig':
            base = self.rig.matrix_world.copy() if self.rig else Matrix.Identity(4)
            return base, bind_name, slot_name, 'deformation_rig'

        if bind_name in self.components_by_name:
            bound_component = self.components_by_name[bind_name]
            if component_uses_skinning(component, self.skinning_lookup) and self._component_is_rig_owner(bound_component):
                base = self.rig.matrix_world.copy() if self.rig else Matrix.Identity(4)
                return base, bind_name, slot_name, 'skinning_root'
            parent_matrix, _, _, _ = self.resolve_component_matrix(bound_component)
            if slot_name and slot_name != 'None':
                slot_lookup = self.slot_component_lookups.get(bind_name)
                if slot_lookup and slot_name in slot_lookup:
                    return parent_matrix @ slot_transform_matrix(slot_lookup[slot_name]), bind_name, slot_name, 'component_slot'
            return parent_matrix, bind_name, slot_name, 'component'

        if self.rig and getattr(self.rig, 'pose', None) and bind_name in self.rig.pose.bones:
            return self.bone_matrix(bind_name), bind_name, slot_name, 'bone'

        return Matrix.Identity(4), bind_name, slot_name, 'unresolved'

    def resolve_component_matrix(self, component):
        key = ('component', id(component))
        if key in self.cache:
            return self.cache[key]
        if key in self.resolving:
            return Matrix.Identity(4), '', '', 'cycle'
        self.resolving.add(key)
        parent_matrix, bind_name, slot_name, binding_type = self.resolve_binding(component)
        local_matrix = self._local_matrix(component)
        matrix = parent_matrix @ local_matrix
        result = (matrix, bind_name, slot_name, binding_type)
        self.cache[key] = result
        self.resolving.remove(key)
        return result

    def _bone_rotation(self, bone_name, slot_owner=None):
        cache_key = (bone_name, slot_owner)
        cached = self.bone_rotation_cache.get(cache_key)
        if cached is not None:
            return cached
        _, pose_bone = self._pose_bone(bone_name, slot_owner)
        if pose_bone is not None:
            rotation = pose_bone.rotation_quaternion.copy()
        else:
            rig_j = self._rig_json_for_bone(bone_name, slot_owner)
            if self._rig_json_has_bone(bone_name, rig_j):
                rotation = rig_json_bone_matrix(rig_j, bone_name, self._rig_json_index(rig_j)).to_quaternion()
            else:
                rotation = Quaternion((1, 0, 0, 0))
        self.bone_rotation_cache[cache_key] = rotation
        return rotation

    def _bone_head(self, bone_name, slot_owner=None):
        cache_key = (bone_name, slot_owner)
        cached = self.bone_head_cache.get(cache_key)
        if cached is not None:
            return cached
        _, pose_bone = self._pose_bone(bone_name, slot_owner)
        if pose_bone is not None:
            head = pose_bone.head.copy()
        else:
            rig_j = self._rig_json_for_bone(bone_name, slot_owner)
            if self._rig_json_has_bone(bone_name, rig_j):
                head = rig_json_bone_matrix(rig_j, bone_name, self._rig_json_index(rig_j)).to_translation()
            else:
                head = Vector((0, 0, 0))
        self.bone_head_cache[cache_key] = head
        return head

    def _rig_bone_index(self, bone_name):
        if not bone_name:
            return None
        return self.rig_bone_index.get(bone_name)

    def _rig_space_bone_matrix(self, bone_name):
        cached = self.rig_space_bone_matrix_cache.get(bone_name)
        if cached is not None:
            return cached
        index = self._rig_bone_index(bone_name)
        if index is None:
            if self.rig and getattr(self.rig, 'pose', None) and bone_name in self.rig.pose.bones:
                matrix = self.rig.pose.bones[bone_name].matrix.copy()
            else:
                matrix = Matrix.Identity(4)
            self.rig_space_bone_matrix_cache[bone_name] = matrix
            return matrix
        for key in ('aPoseMS', 'boneTransforms', 'aPoseLS'):
            transforms = self.rig_j.get(key) if isinstance(self.rig_j, dict) else None
            if isinstance(transforms, list) and index < len(transforms):
                matrix = qs_transform_matrix(transforms[index])
                self.rig_space_bone_matrix_cache[bone_name] = matrix
                return matrix
        if self.rig and getattr(self.rig, 'pose', None) and bone_name in self.rig.pose.bones:
            matrix = self.rig.pose.bones[bone_name].matrix.copy()
        else:
            matrix = Matrix.Identity(4)
        self.rig_space_bone_matrix_cache[bone_name] = matrix
        return matrix

    def _rig_bone_delta_matrix(self, base_bone_name, target_bone_name):
        if not target_bone_name or target_bone_name == 'None' or target_bone_name == base_bone_name:
            return Matrix.Identity(4)
        base_matrix = self._rig_space_bone_matrix(base_bone_name)
        target_matrix = self._rig_space_bone_matrix(target_bone_name)
        try:
            return base_matrix.inverted() @ target_matrix
        except Exception:
            return target_matrix

    def _rig_bone_translation_delta_matrix(self, base_bone_name, target_bone_name):
        if not target_bone_name or target_bone_name == 'None' or target_bone_name == base_bone_name:
            return Matrix.Identity(4)
        base_matrix = self._rig_space_bone_matrix(base_bone_name)
        target_matrix = self._rig_space_bone_matrix(target_bone_name)
        delta = target_matrix.to_translation() - base_matrix.to_translation()
        return Matrix.Translation(delta)

    def _rig_bone_translation_matrix(self, bone_name):
        if not bone_name or bone_name == 'None':
            return Matrix.Identity(4)
        return Matrix.Translation(self._rig_space_bone_matrix(bone_name).to_translation())

    def _rig_bone_yaw_matrix(self, bone_name):
        if not bone_name or bone_name == 'None':
            return Matrix.Identity(4)
        try:
            yaw = self._rig_space_bone_matrix(bone_name).to_euler().z
        except Exception:
            yaw = 0
        return Matrix.Rotation(yaw, 4, 'Z')

    def _slot(self, owner, slot_name):
        slot_lookup = self.slot_component_lookups.get(owner)
        if not slot_lookup and owner in ('vehicle_slots', 'slots'):
            slot_lookup = self.default_slot_lookup
        return slot_lookup.get(slot_name) if slot_lookup else None

    def _slot_bone_name(self, owner, slot_name):
        slot = self._slot(owner, slot_name)
        if slot:
            return cname_value(slot.get('boneName'), slot_name)
        return slot_name or owner

    def _binding_name(self, component):
        binding = self._binding_data(component)
        return cname_value(binding.get('bindName')) if isinstance(binding, dict) else ''

    def _component_is_rig_owner(self, component):
        return isinstance(component, dict) and bool(depot_path_value(component, 'rig'))

    def _slot_component_is_animated_child(self, component):
        parent_name = self._binding_name(component)
        parent = self.components_by_name.get(parent_name)
        return bool(parent_name and self._component_is_rig_owner(parent))

    def _animated_base_slot(self, animated_component_name):
        for slot_owner in self.components:
            if not isinstance(slot_owner, dict) or slot_owner.get('$type') != 'entSlotComponent':
                continue
            if self._binding_name(slot_owner) != animated_component_name:
                continue
            slots = slot_owner.get('slots')
            if not isinstance(slots, list):
                continue
            for slot in slots:
                slot_name = cname_value(slot.get('slotName'))
                bone_name = cname_value(slot.get('boneName'))
                if slot_name == 'base' or bone_name == 'base':
                    return slot
        return None

    def _animated_base_slot_matrix(self, animated_component_name):
        return slot_transform_matrix(self._animated_base_slot(animated_component_name))

    def _slot_component_primary_bone(self, component):
        slots = component.get('slots') if isinstance(component, dict) else None
        if not isinstance(slots, list):
            return None
        for slot in slots:
            bone_name = cname_value(slot.get('boneName'))
            if bone_name and bone_name != 'None':
                return bone_name
        return None

    def _animated_slot_component_basis(self, component):
        parent_name = self._binding_name(component)
        if not parent_name:
            return None
        parent = self.components_by_name.get(parent_name)
        if not self._component_is_rig_owner(parent):
            return None
        name = component_name(component)
        if name == 'base':
            return None
        base_slot = self._animated_base_slot(parent_name)
        if not isinstance(base_slot, dict):
            return None
        base_bone_name = cname_value(base_slot.get('boneName'))
        target_bone_name = self._slot_component_primary_bone(component)
        return self._animated_base_slot_matrix(parent_name) @ self._rig_bone_translation_delta_matrix(base_bone_name or 'base', target_bone_name)

    def _hard_bone_slot_matrix(self, bone_name, slot_owner, slot_name, local_transform, visual_scale=None):
        slot = self._slot(slot_owner, slot_name)
        slot_pos = Vector((0, 0, 0))
        slot_rot = Quaternion((1, 0, 0, 0))
        if slot:
            slot_pos_data = slot.get('relativePosition') if isinstance(slot.get('relativePosition'), dict) else {}
            slot_pos = Vector((
                slot_pos_data.get('X', 0),
                slot_pos_data.get('Y', 0),
                slot_pos_data.get('Z', 0),
            ))
            slot_rot = red_quaternion(slot.get('relativeRotation'))

        local_pos = fixed_point_position(local_transform)
        if bone_name and bone_name != 'Base':
            z_ang = self.bone_matrix(bone_name, slot_owner).to_euler().z
            local_pos = Matrix.Rotation(z_ang, 4, 'Z') @ local_pos

        rotation = self._bone_rotation(bone_name, slot_owner) @ slot_rot @ red_quaternion(local_transform.get('Orientation'))
        scale = red_scale(local_transform, visual_scale)
        return Matrix.LocRotScale(self._bone_head(bone_name, slot_owner) + slot_pos + local_pos, rotation, scale)

    def resolve_hard_component_matrix(self, component):
        key = ('hard', id(component))
        if key in self.cache:
            return self.cache[key]
        if key in self.resolving:
            return Matrix.Identity(4), '', '', 'cycle'
        self.resolving.add(key)

        local_transform = component.get('localTransform', {}) if isinstance(component, dict) else {}
        visual_scale = component.get('visualScale') if isinstance(component, dict) else None
        animated_slot_basis = self._animated_slot_component_basis(component)
        if animated_slot_basis is not None:
            result = (animated_slot_basis @ self._local_matrix(component, local_transform, visual_scale), self._binding_name(component), '', 'animated_slot_component')
            self.cache[key] = result
            self.resolving.remove(key)
            return result
        binding = self._binding_data(component)
        if not isinstance(binding, dict):
            result = (self._local_matrix(component, local_transform, visual_scale), '', '', 'none')
            self.cache[key] = result
            self.resolving.remove(key)
            return result

        bind_name = cname_value(binding.get('bindName'))
        slot_name = cname_value(binding.get('slotName'))
        if not bind_name or bind_name == 'None':
            result = (self._local_matrix(component, local_transform, visual_scale), bind_name, slot_name, 'none')
            self.cache[key] = result
            self.resolving.remove(key)
            return result

        if bind_name in ('vehicle_slots', 'slots'):
            bone_name = self._slot_bone_name(bind_name, slot_name)
            result = (self._hard_bone_slot_matrix(bone_name, bind_name, slot_name, local_transform, visual_scale), bone_name, slot_name, 'slot')
            self.cache[key] = result
            self.resolving.remove(key)
            return result

        if bind_name == 'deformation_rig':
            base = self.rig.matrix_world.copy() if self.rig else Matrix.Identity(4)
            result = (base @ self._local_matrix(component, local_transform, visual_scale), bind_name, slot_name, 'deformation_rig')
            self.cache[key] = result
            self.resolving.remove(key)
            return result

        if bind_name in self.components_by_name:
            bound_component = self.components_by_name[bind_name]
            parent_matrix, parent_bind, parent_slot, parent_type = self.resolve_hard_component_matrix(bound_component)
            if slot_name and slot_name != 'None':
                slot = self._slot(bind_name, slot_name)
                if slot:
                    skip_animated_base_slot = (
                        bind_name == 'base'
                        and slot_name == 'base'
                        and self._slot_component_is_animated_child(bound_component)
                    )
                    animated_parent_name = self._binding_name(bound_component) if self._slot_component_is_animated_child(bound_component) else ''
                    animated_base_slot = self._animated_base_slot(animated_parent_name) if animated_parent_name else None
                    bone_name = cname_value(slot.get('boneName'), slot_name)
                    if animated_parent_name and not isinstance(animated_base_slot, dict):
                        animated_parent = self.components_by_name.get(animated_parent_name)
                        animated_parent_matrix = Matrix.Identity(4)
                        if animated_parent is not None:
                            animated_parent_matrix, _, _, _ = self.resolve_hard_component_matrix(animated_parent)
                        parent_matrix = (
                            animated_parent_matrix
                            @ self._rig_bone_translation_matrix(bone_name)
                            @ self._rig_bone_yaw_matrix(bone_name)
                            @ slot_translation_matrix(slot)
                        )
                        parent_bind = bone_name or parent_bind or bind_name
                        parent_slot = slot_name
                        parent_type = 'slot'
                    elif not skip_animated_base_slot:
                        parent_matrix = parent_matrix @ slot_transform_matrix(slot)
                        parent_type = 'component_slot'
            result = (parent_matrix @ self._local_matrix(component, local_transform, visual_scale), parent_bind or bind_name, parent_slot or slot_name, parent_type if parent_type != 'none' else 'component')
            self.cache[key] = result
            self.resolving.remove(key)
            return result

        if self.rig and getattr(self.rig, 'pose', None) and bind_name in self.rig.pose.bones:
            result = (self._hard_bone_slot_matrix(bind_name, bind_name, slot_name, local_transform, visual_scale), bind_name, slot_name, 'bone')
            self.cache[key] = result
            self.resolving.remove(key)
            return result

        result = (self._local_matrix(component, local_transform, visual_scale), bind_name, slot_name, 'unresolved')
        self.cache[key] = result
        self.resolving.remove(key)
        return result

# The appearance list needs to be the appearanceNames for each ent that you want to import, will import all if not specified
# if you've already imported the body/head and set the rig up you can exclude them by putting them in the exclude_meshes list
# presto_stash=[]

def importEnt(with_materials, filepath='', appearances=None, exclude_meshes=None, include_collisions=False, include_phys=False,
                   include_entCollider=False, inColl='', remapdepot=False, meshes=None, mesh_jsons=None, escaped_path=None,
                   app_path=None, anim_files=None, rigjsons=None,generate_overrides=False):
    cp77_addon_prefs = bpy.context.preferences.addons['i_scene_cp77_gltf'].preferences
    if appearances is None:
        appearances = ['']
    elif isinstance(appearances, str):
        appearances = [appearances]
    else:
        appearances = list(appearances)
    excluded_meshes = {norm_path_key(mesh) for mesh in (exclude_meshes or []) if mesh}
    with_materials = with_materials
    if not cp77_addon_prefs.non_verbose:
        print('\n-------------------- Importing Cyberpunk 2077 Entity --------------------')
    C = bpy.context
    coll_scene = C.scene.collection
    start_time = time.time()

    path, after = split_source_raw_root(filepath)
    asset_index = build_asset_index(path)

    error_messages = []
    entinitiatedcache = False
    if not JSONTool._use_cache:
        JSONTool.start_caching()
        entinitiatedcache = True

    ent_name=os.path.basename(filepath)[:-9]
    if not cp77_addon_prefs.non_verbose:
        if isinstance(appearances, list):
            print(f"Importing appearance: {', '.join(appearances)} from entity: {ent_name}")
        else:
            print(f"Importing appearance: {appearances} from entity: {ent_name}")
    if filepath is not None:
        ent_apps, ent_components, ent_component_data, res, ent_default = JSONTool.jsonload(filepath, error_messages)

    ent_applist=[cname_value(app.get('appearanceName')) for app in ent_apps]
    ent_app_index_by_name = {name: index for index, name in enumerate(ent_applist) if name}
    ent_app_by_appearance, ent_app_by_name = build_ent_app_lookup(ent_apps)
    ent_default = normalize_default_appearance(ent_default, ent_apps, ent_app_by_appearance, ent_app_by_name, filepath)

    if len(ent_applist) == 0:
        print(f"No appearances found in entity file {ent_name}. Imported objects may be incomplete or missing.")
        #show_message("No appearances found in entity file. Imported objects may be incomplete or missing. "+ent_name)
        # this just isnt true, loads of stuff doesnt have appearances, and the popup is annoying

    #print(ent_applist)
    was_random=False
    if ent_default and ent_default != 'None' and ent_default=='random':
        if len(ent_applist)>0:
            import random
            ent_default= random.choice(ent_applist)
            was_random=True
            print(f"Default appearance set to random choice: {ent_default}")
        else:
            print("No appearances available to select a random default from.")

    for appidx, app in enumerate(appearances):
        if app == 'default':
            if ent_default:
                print(f"Using default appearance {ent_default} for entity {ent_name}.")
                continue
            if ent_applist:
                print(f"No default appearance specified in entity {ent_name}. Using first available appearance {ent_applist[0]}.")
                ent_default = ent_applist[0]
                continue
            print(f"No appearances specified in entity {ent_name}. Using root entities.")
            appearances[appidx] = 'BASE_COMPONENTS_ONLY'
            continue
        if app.upper() != 'ALL' and app not in ent_applist:
            print(f"Appearance {app} not found in entity {ent_name}. Available appearances: {', '.join(ent_applist)}")


    #presto_stash.append(ent_components)
    ent_complist=[]
    ent_rigs=[]
    ent_colliderComps=[]
    ent_simpleCollComps=[]
    chassis_info=[]
    for comp in ent_components:
        comp_name = component_name(comp)
        if comp_name:
            ent_complist.append(comp['name'])
        rig_depot = depot_path_value(comp, 'rig')
        if rig_depot:
            print(f"Rig found in entity: {rig_depot}")
            ent_rigs.append(depot_to_local_path(path, rig_depot))
        if comp_name == 'Chassis':
            chassis_info = comp
    for comp in ent_component_data:
        comp_type = comp.get('$type')
        if comp_type == 'entColliderComponent':
            ent_colliderComps.append(comp)
        if comp_type == 'entSimpleColliderComponent':
            ent_simpleCollComps.append(comp)
    #print('collider components:', ent_colliderComps)
    #print('simple collider components:', ent_simpleCollComps)
    #    presto_stash.append(ent_rigs)

    resolved=[]
    for res_p in res:
        depot_value = depot_path_value({'resource': res_p}, 'resource')
        if not depot_value and isinstance(res_p, dict) and isinstance(res_p.get('DepotPath'), dict):
            depot_value = cname_value(res_p.get('DepotPath'))
        if depot_value:
            resolved.append(depot_to_local_path(path, depot_value))

    # if no apps requested populate the list with all available.

    if len(appearances[0])==0 or appearances[0].upper()=='ALL':
        appearances=[]
        for app in ent_apps:
            appearances.append(app['appearanceName']['$value'])
    if len(appearances)==0:
        appearances.append('BASE_COMPONENTS_ONLY')

    VS=[]
    vehicle_slots=None
    for x in ent_components:
        if component_name(x) in ('vehicle_slots', 'slots'):
            VS.append(x)
    if len(VS)>0:
        vehicle_slots= VS[0]['slots']
    vehicle_slot_lookup = build_slot_lookup(vehicle_slots)

    # Discover exported resources from the indexed source/raw tree.
    app_path = indexed_asset_files(asset_index, '.app.json', app_path)
    app_resource = app_path[0] if app_path else ''
    if ent_apps and len(ent_apps) > 0 and len(app_path) == 0:
        print('No Appearance file JSONs found in path, run the Ent export script first')

    mesh_files = indexed_asset_files(asset_index, '.glb', meshes)
    if len(mesh_files) == 0:
        print('No Meshes found in path, run the Ent export script first')

    mesh_jsons = indexed_asset_files(asset_index, '.mesh.json', mesh_jsons)
    mesh_json_set = {norm_path_key(mesh_json) for mesh_json in mesh_jsons}

    # Find anims through the asset index, then match by resolved entity rig dependency.
    anim_files = indexed_asset_files(asset_index, '.anims.glb', anim_files)

    rig=None
    bones=None
    chunks=None

    if len(anim_files) == 0 or len(ent_rigs) == 0: # we have glbs and we have rigs called up in the ent
        print('no anim rig found')
    else:
        resolved_keys = {norm_path_key(resolved_path) for resolved_path in resolved}
        ent_rig_keys = {norm_path_key(rig_path) for rig_path in ent_rigs}
        animsinres=[x for x in anim_files if norm_path_key(os.path.splitext(x)[0]) in resolved_keys]
        if len(animsinres)==0:
            for anim in anim_files:
                anim_json_path = resolve_anim_json_path_from_glb(asset_index, anim)
                if anim_json_path:
                    anm_j=JSONTool.jsonload(anim_json_path, error_messages)
                    if anm_j is not None:
                        rig_depot = anm_j.get('Data', {}).get('RootChunk', {}).get('rig', {}).get('DepotPath', {}).get('$value')
                        if rig_depot and norm_path_key(depot_to_local_path(path, rig_depot)) in ent_rig_keys:
                            animsinres.append(anim)
                        # presto_stash.append(animsinres)

        if len(animsinres)>0:
            bpy.ops.io_scene_gltf.cp77(with_materials, filepath=animsinres[0],scripting=True)
            #find what we just loaded
            arms = imported_armatures_from_selection()
            if arms:
                rig=arms[0]
                cache_armature_bones(rig)
                bones=rig.pose.bones
                print('anim rig loaded')
            else:
                print('anim rig import did not create an armature')

            if rig and animsinres[0].endswith(".glb"):
                anim_file_name = (animsinres[0])
                rig_file_name = anim_file_name + ".rig.json"
                rig["animset"] = anim_file_name
                rig["rig"] = rig_file_name
                rig["ent"] = ent_name + ".ent.json"

    # find the rig json associated with the ent
    rigjsons = indexed_asset_files(asset_index, '.rig.json', rigjsons)
    rig_j=None
    if len(rigjsons)==0 or len(ent_rigs)==0:
        print('no rig json loaded')
    else:
        ent_rig_keys = {norm_path_key(rig_path) for rig_path in ent_rigs}
        entrigjsons=[x for x in rigjsons if norm_path_key(x[:-5]) in ent_rig_keys]
        if len(entrigjsons)>0:
            for entrig in entrigjsons:
                rig_j=JSONTool.jsonload(entrig, error_messages)
                if rig_j is not None:
                    rig_j=rig_j.get('Data', {}).get('RootChunk')
                    if rig_j is not None:
                        print('rig json loaded')
    rig_bone_index = build_rig_bone_index(rig_j)

    rig_json_by_component_name = {}
    rig_json_path_by_component_name = {}
    armature_by_component_name = {}
    rig_json_cache = {}
    rig_json_path_cache = {}

    def rig_json_path_for_depot(rig_depot):
        if not rig_depot:
            return ''
        if rig_depot not in rig_json_path_cache:
            rig_json_path_cache[rig_depot] = resolve_rig_json_path(asset_index, rig_depot) or ''
        return rig_json_path_cache[rig_depot]

    def rig_json_for_depot(rig_depot):
        if not rig_depot:
            return None
        if rig_depot in rig_json_cache:
            return rig_json_cache[rig_depot]
        rig_json_path = rig_json_path_for_depot(rig_depot)
        rig_root = None
        if rig_json_path:
            loaded_rig_json = JSONTool.jsonload(rig_json_path, error_messages)
            if loaded_rig_json is not None:
                rig_root = loaded_rig_json.get('Data', {}).get('RootChunk')
        rig_json_cache[rig_depot] = rig_root
        return rig_root

    for rig_component in ent_components:
        rig_depot = depot_path_value(rig_component, 'rig')
        rig_name = component_name(rig_component)
        if rig_depot and rig_name:
            rig_json_by_component_name[rig_name] = rig_json_for_depot(rig_depot)
            rig_json_path_by_component_name[rig_name] = rig_json_path_for_depot(rig_depot)


    Masters = None
    if len(mesh_files)<1 or (not app_path or len(app_path)<1) and len(ent_components)<1:
        print("You need to export the meshes and convert app and ent to json")
        pass

    else:
        coll_scene = C.scene.collection
        mis={}
        if "MasterInstances" not in coll_scene.children:
            Masters=bpy.data.collections.new("MasterInstances")
            coll_scene.children.link(Masters)
        else:
            Masters=bpy.data.collections.get("MasterInstances")

        Masters.hide_viewport=False #if its hidden it breaks entity positioning for some reason?!?

        # loop through the appearances we want to import to find & load the meshes/appearances we need
        meshes={}
        app_comps={}
        ent_chunks={}
        app_json_cache={}
        app_lookup={}
        component_mesh_info_cache = {}

        def component_mesh_info(component):
            cache_key = id(component)
            cached = component_mesh_info_cache.get(cache_key)
            if cached is not None:
                return cached
            depot_path = mesh_component_depot(component)
            if not depot_path:
                cached = ('', '', '', '', True)
            else:
                meshpath = resolve_mesh_glb_path(asset_index, depot_path)
                meshname = os.path.basename(depot_path.replace('\\', os.sep))
                meshapp = mesh_appearance_value(component)
                enabled = is_component_enabled(component)
                cached = (depot_path, meshname, meshpath, meshapp, enabled)
            component_mesh_info_cache[cache_key] = cached
            return cached

        for x,requested_app_name in enumerate(appearances):
            app_name = resolve_requested_appearance_name(requested_app_name, ent_default, ent_apps, ent_app_by_appearance, ent_app_by_name)
            app_comps[requested_app_name]=[]
            chunks = None
            if len(ent_apps)==0 and ent_component_data:
                chunks= ent_component_data
            elif len(ent_apps)>0:
                ent_app_idx, app_name = resolve_ent_app(app_name, ent_apps, ent_app_by_appearance, ent_app_by_name, ent_default)
                app_lookup[requested_app_name] = app_name

                app_file = ent_apps[ent_app_idx]['appearanceResource']['DepotPath']['$value']
                appfilepath=resolve_app_json_path(asset_index, app_file)
                a_j=None
                if not appfilepath:
                    print('app file not found -', depot_to_local_path(path, app_file) + '.json')
                else:
                    if appfilepath not in app_json_cache:
                        app_json_cache[appfilepath]=JSONTool.jsonload(appfilepath, error_messages)
                    a_j=app_json_cache.get(appfilepath)
                    if a_j is not None:
                        apps=a_j['Data']['RootChunk']['appearances']

                        app_idx=0
                        app_definition_by_name = {cname_value(a.get('Data', {}).get('name')): i for i, a in enumerate(apps) if isinstance(a, dict)}
                        matched_app_idx = app_definition_by_name.get(app_name)
                        if matched_app_idx is not None:
                            app_idx=matched_app_idx
                            print('appearance matched, id = ',app_idx)
                        chunks=None
                        app_data = a_j['Data']['RootChunk']['appearances'][app_idx].get('Data')
                        if app_data:
                            if app_data.get('components'):
                                app_comps[requested_app_name]= ent_components+app_data['components']
                                if app_name != requested_app_name:
                                    app_comps[app_name]=app_comps[requested_app_name]
                            compiled_data = app_data.get('compiledData')
                            if compiled_data and compiled_data.get('Data', {}).get('Chunks'):
                                chunks= compiled_data['Data']['Chunks']
                                ent_chunks[requested_app_name]=chunks
                                if app_name != requested_app_name:
                                    ent_chunks[app_name]=chunks
                                print('Chunks found')


            if len(app_comps[requested_app_name])==0:
                print('falling back to rootchunk components...')
                app_comps[requested_app_name]= ent_components
                if app_name != requested_app_name:
                    app_comps[app_name]=app_comps[requested_app_name]
            if chunks is not None and requested_app_name not in ent_chunks:
                ent_chunks[requested_app_name] = chunks
            for c in app_comps[requested_app_name]:
                depot_path, meshname, meshpath, meshApp, _ = component_mesh_info(c)
                if depot_path and meshname and meshpath and not is_excluded_mesh(depot_path, meshpath, meshname, excluded_meshes):
                    mesh_key = depot_to_local_path(path, depot_path)
                    if mesh_key not in meshes:
                        meshes[mesh_key] = {'appearances':[meshApp],'sector':'ALL'}
                    else:
                        meshes[mesh_key]['appearances'].append(meshApp)

        meshes_w_apps={}

        for m in meshes:
            if len(m)>0:
                    add_to_list(m , meshes, meshes_w_apps)

        meshes_from_mesheswapps( meshes_w_apps, path, from_mesh_no=0, to_mesh_no=10000000, with_mats=with_materials, glbs=meshes, mesh_jsons=mesh_jsons,
                                    Masters=Masters,generate_overrides=generate_overrides)


        # loop through again to actually build the appearances
        for x,app_name in enumerate(appearances):
            requested_app_name = app_name
            app_name = resolve_requested_appearance_name(app_name, ent_default, ent_apps, ent_app_by_appearance, ent_app_by_name)
            print(f"\nImporting appearance {x+1} of {len(appearances)}: {app_name}")
            app_start_time = time.time()
            chunks = None
            ent_coll = bpy.data.collections.new(ent_name+'_'+app_name)
            app_name = app_lookup.get(requested_app_name, app_name)
            if inColl and inColl in coll_scene.children:
                par_coll=bpy.data.collections.get(inColl)
                par_coll.children.link(ent_coll)
            else:
                #link it to the scene
                coll_scene.children.link(ent_coll)
            # tag it with some custom properties.
            ent_coll['depotPath']=after
            if len(ent_apps)==0 and ent_component_data:
                chunks= ent_component_data
            elif len(ent_apps)>0:
                ent_app_idx, app_name = resolve_ent_app(app_name, ent_apps, ent_app_by_appearance, ent_app_by_name, ent_default)
            if not chunks:
                chunks=ent_chunks.get(requested_app_name) or ent_chunks.get(app_name) or ent_component_data

            ent_coll['appearanceName'] = app_name
            ent_coll['appearanceIndex'] = ent_app_index_by_name.get(app_name, 0)

            comps=app_comps.get(requested_app_name) or app_comps.get(app_name) or ent_components
            transform_components = list({id(comp): comp for comp in list(ent_components) + list(comps)}.values())
            ent_component_ids = {id(comp) for comp in ent_components}
            ent_parent_transform_lookup = build_parent_transform_lookup(ent_component_data)
            app_parent_transform_lookup = build_parent_transform_lookup(chunks)
            parent_transform_lookup = ComponentHandleLookup(app_parent_transform_lookup)
            ent_skinning_lookup = build_skinning_lookup(ent_component_data)
            app_skinning_lookup = build_skinning_lookup(chunks)
            skinning_lookup = ComponentHandleLookup(app_skinning_lookup)
            for comp in transform_components:
                if id(comp) in ent_component_ids:
                    parent_transform_lookup.set_component_lookup(comp, ent_parent_transform_lookup)
                    skinning_lookup.set_component_lookup(comp, ent_skinning_lookup)
                else:
                    parent_transform_lookup.set_component_lookup(comp, app_parent_transform_lookup)
                    skinning_lookup.set_component_lookup(comp, app_skinning_lookup)
                rig_depot = depot_path_value(comp, 'rig')
                rig_name = component_name(comp)
                if rig_depot and rig_name:
                    if rig_name not in rig_json_by_component_name:
                        rig_json_by_component_name[rig_name] = rig_json_for_depot(rig_depot)
                    rig_json_path_by_component_name[rig_name] = rig_json_path_for_depot(rig_depot)
            rig_component_names = set(rig_json_by_component_name.keys())
            slot_owner_rig_jsons = build_slot_owner_rig_jsons(transform_components, parent_transform_lookup, rig_json_by_component_name)
            slot_owner_rig_owner_names = build_slot_owner_rig_owner_names(transform_components, parent_transform_lookup, rig_component_names)
            anim_impl_lookup = build_anim_impl_lookup(chunks)

            if not rig:
                for c in comps:
                    if component_name(c) in ('vehicle_slots', 'slot', 'slots'):
                        VS.append(c)
                    rig_depot = depot_path_value(c, 'rig')
                    if rig_depot:
                        rig_path = depot_to_local_path(path, rig_depot)
                        ent_rigs.append(rig_path)
                        if rig_path in ent_rigs:
                            print(f"Rig found in app components: {rig_depot}")
                            if rig is None:
                                rig_json_path = resolve_rig_json_path(asset_index, rig_depot)
                                if rig_json_path:
                                    rig_j=JSONTool.jsonload(rig_json_path, error_messages)
                                    if rig_j is not None:
                                        rig_j=rig_j.get('Data', {}).get('RootChunk')
                                        rig_bone_index = build_rig_bone_index(rig_j)
                                        print('rig json loaded')
                                gameplay_anims = c.get('animations', {}).get('gameplay')
                                if gameplay_anims is not None and len(gameplay_anims)>0:
                                    anim_depot = gameplay_anims[0]['animSet']['DepotPath']['$value']
                                    animpath=resolve_anim_glb_path(asset_index, anim_depot)
                                    if animpath:
                                        bpy.ops.io_scene_gltf.cp77(with_materials, filepath=animpath, scripting=True)
                                        # find the armature we just loaded
                                        arms = imported_armatures_from_selection()
                                        if arms:
                                            rig=arms[0]
                                            cache_armature_bones(rig)
                                            bones=rig.pose.bones
                                            rig["animset"] = animpath
                                            rig["rig"] = rig_path
                                            rig["ent"] = ent_name + ".ent.json"
                                            print('anim rig loaded')
                                        else:
                                            print('anim rig import did not create an armature')
                            elif rig.get('rig')==rig_path:
                                print('using existing rig')
                            else:
                                print('another rig',rig.get('rig'),' is already loaded ',rig_path)
            if rig is None:
                required_rig_names = []
                if 'deformation_rig' in rig_json_path_by_component_name:
                    required_rig_names.append('deformation_rig')
                for rig_owner_name in slot_owner_rig_owner_names.values():
                    if rig_owner_name not in required_rig_names:
                        required_rig_names.append(rig_owner_name)
                for rig_name in rig_json_path_by_component_name:
                    if rig_name not in required_rig_names:
                        required_rig_names.append(rig_name)

                for rig_name in required_rig_names:
                    rig_json_path = rig_json_path_by_component_name.get(rig_name)
                    if not rig_json_path:
                        continue
                    armature = armature_by_component_name.get(rig_name)
                    if armature is None:
                        armature = ensure_armature_from_rig_json(rig_json_path, rig_name, ent_name)
                        if armature is not None:
                            armature_by_component_name[rig_name] = armature
                            print(f"rig armature created from json for {rig_name}")
                    if armature is not None and (rig is None or rig_name == 'deformation_rig'):
                        rig = armature
                        cache_armature_bones(rig)
                        bones = rig.pose.bones
                        rig_j = rig_json_by_component_name.get(rig_name, rig_j)
                        rig_bone_index = build_rig_bone_index(rig_j)
            else:
                component_name_value = rig.get('componentName') if hasattr(rig, 'get') else None
                if component_name_value and component_name_value not in armature_by_component_name:
                    cache_armature_bones(rig)
                    armature_by_component_name[component_name_value] = rig

            if not vehicle_slots:
                if len(VS)>0:
                    vehicle_slots= VS[0]['slots']
                    vehicle_slot_lookup = build_slot_lookup(vehicle_slots)


            transform_resolver = EntityTransformResolver(
                transform_components,
                parent_transform_lookup,
                skinning_lookup=skinning_lookup,
                rig=rig,
                rig_j=rig_j,
                rig_bone_index=rig_bone_index,
                default_slot_lookup=vehicle_slot_lookup,
                slot_owner_rig_jsons=slot_owner_rig_jsons,
                rig_json_by_component_name=rig_json_by_component_name,
                armature_by_component_name=armature_by_component_name,
                slot_owner_rig_owner_names=slot_owner_rig_owner_names,
            )

            for c in comps:
                comp_name = component_name(c)
                if not (c.get('$type')=='gameTransformAnimatorComponent' or 'mesh' in c or 'graphicsMesh' in c):
                    continue

                if c.get('$type')=='gameTransformAnimatorComponent' and c['animations'][0]['$type']=='gameTransformAnimationDefinition':
                    duration=c['animations'][0]['timeline']['items'][0]['duration']
                    HRID=c['animations'][0]['timeline']['items'][0]['impl']['HandleRefId']
                    chunk_anim = anim_impl_lookup.get(int(HRID), 0)
                    if isinstance(chunk_anim, dict) and chunk_anim['$type']=='gameTransformAnimation_RotateOnAxis':
                        rot_axis=chunk_anim['axis']
                        axis_no=0 # default to x
                        if rot_axis=='Z':
                            axis_no=2
                            
                        elif rot_axis=='Y': #y & z are swapped
                            axis_no=1

                        reverse=chunk_anim['reverseDirection']
                        no_rot=chunk_anim['numberOfFullRotations']
                        o = create_axes(ent_coll=ent_coll,name=comp_name)
                        o.keyframe_insert('rotation_euler', index=axis_no ,frame=1)
                        o.rotation_euler[axis_no] = o.rotation_euler[axis_no] +math.radians(no_rot*(-1*reverse)*360)
                        o.keyframe_insert('rotation_euler', index=axis_no ,frame=duration*24)
                        if o.animation_data.action:
                            obj_action = bpy.data.actions.get(o.animation_data.action.name)
                            obj_slot = o.animation_data.action_slot
                            channelbag = anim_utils.action_get_channelbag_for_slot(obj_action, obj_slot)
                            obj_fcu = channelbag.fcurves[0]
                            modifier = obj_fcu.modifiers.new(type='CYCLES')
                            modifier.mode_before = 'REPEAT'
                            modifier.mode_after = 'REPEAT'
                            for pt in obj_fcu.keyframe_points:
                                pt.interpolation = 'LINEAR'
                elif 'mesh' in c or 'graphicsMesh' in c:
                    depot_path, meshname, meshpath, meshApp, component_enabled = component_mesh_info(c)
                    if meshname and meshpath and not is_excluded_mesh(depot_path, meshpath, meshname, excluded_meshes):
                        new=None
                        try:
                            # TODO: sim, this is broken, pls fix Y_Y
                            # make this instance from masters rather than loading multiple times
                            #bpy.ops.io_scene_gltf.cp77(with_materials, filepath=meshpath, appearances=meshApp,scripting=True,generate_overrides=generate_overrides)
                            group, groupname = get_group(meshpath,meshApp,Masters)
                            if (group):
                                new=bpy.data.collections.new(groupname)                                       
                                ent_coll.children.link(new)
                                copied_objects = []
                                object_copy_map = {}
                                link_object = new.objects.link
                                for old_obj in tuple(group.all_objects):
                                    obj=old_obj.copy()
                                    object_copy_map[old_obj] = obj
                                    copied_objects.append(obj)
                                    link_object(obj)
                                remap_copied_object_references(copied_objects, object_copy_map)
                                for obj in copied_objects:
                                    obj['componentName'] = comp_name
                                    obj['sourcePath'] = meshpath
                                    obj['meshAppearance'] = meshApp
                                    obj['componentEnabled'] = component_enabled
                                    if app_resource:
                                        obj['appResource'] = app_resource
                                    obj['entAppearance'] = app_name
                                    if not component_enabled:
                                        obj.hide_set(True)
                                        obj.hide_render = True
                                    if 'Armature' in obj.name:
                                        obj.hide_set(True)
                            else:
                                print('BREAK collection not found after import - ', meshname)
                            print('checking for collection - ', meshname)
                            if new is None:
                                print('collection not found after import - ', meshname)
                                continue
                            objs = copied_objects
                            component_is_skinned = component_uses_deformation_skinning(c, skinning_lookup)
                            if component_is_skinned:
                                resolved_matrix, bindname, slotname, binding_type = transform_resolver.resolve_component_matrix(c)
                            else:
                                resolved_matrix, bindname, slotname, binding_type = transform_resolver.resolve_hard_component_matrix(c)
                            if component_is_skinned:
                                bind_skinned_objects_to_rig(objs, rig)
                            can_bind_bone = (
                                not component_is_skinned
                                and binding_type in {'slot', 'bone'}
                                and bindname
                                and armature_has_bone(rig, bindname)
                            )
                            child_inverse = child_of_inverse_matrix(rig, bindname) if can_bind_bone else None
                            copy_wheel_rotation = can_bind_bone and 'wheel' in bindname
                            set_steering_subtarget = copy_wheel_rotation and 'steering' not in bindname
                            for obj in objs:
                                obj['bindingType'] = binding_type
                                if bindname:
                                    obj['bindname'] = bindname
                                if slotname:
                                    obj['slotName'] = slotname
                                obj['deformationRigSkinning'] = component_is_skinned
                                obj.matrix_world = resolved_matrix @ obj.matrix_world
                                if not component_enabled:
                                    obj.hide_set(True)
                                    obj.hide_render = True
                                if can_bind_bone:
                                    if 'Child Of' not in obj.constraints:
                                        co = obj.constraints.new(type='CHILD_OF')
                                        co.target = rig
                                        co.subtarget = bindname
                                        co.inverse_matrix = child_inverse
                                    if copy_wheel_rotation:
                                        cr = obj.constraints.new(type='COPY_ROTATION')
                                        cr.target = rig
                                        if set_steering_subtarget:
                                            cr.subtarget = bindname


                            if (len(objs) > 0):
                                move_coll=new
                                move_coll['depotPath']=depot_path
                                move_coll['meshAppearance']=meshApp
                                if 'meshpath' not in move_coll:
                                    move_coll['meshpath']="its an entity"
                                if bindname:
                                    move_coll['bindname']=bindname
                                if move_coll.name in coll_scene.children:
                                    coll_scene.children.unlink(move_coll)

                            if 'chunkMask' in c:
                                cm_int = int(c['chunkMask'])
                                for obj in objs:
                                    subnum = submesh_index_for_object(obj)
                                    if subnum is None:
                                        continue
                                    hidden = (not component_enabled) or not bool((cm_int >> subnum) & 1)
                                    obj.hide_set(hidden)
                                    obj.hide_render = hidden

                        except:
                            print("Failed on ",meshname)
                            print(traceback.format_exc())

            for c in ent_component_data:
                if (c['$type']=='entLightChannelComponent'):
                    print('Light channel found')
                    mesh_obj=None
                    lcgroup=None
                    lcgroupname=c['name']['$value']
                    if lcgroupname not in bpy.data.collections.get("MasterInstances").children:
                        if 'shape' in c and 'Data' in c['shape'] and 'vertices' in c['shape']['Data']:
                            vertices=c['shape']['Data']['vertices']
                            if len(vertices)>0 and 'indices' in c['shape']['Data']:
                                indices=c['shape']['Data']['indices']
                                if len(indices)>0:
                                    lcgroup=bpy.data.collections.new(lcgroupname)
                                    mesh_data = bpy.data.meshes.new(lcgroupname)
                                    mesh_obj = bpy.data.objects.new(mesh_data.name, mesh_data)
                                    mesh_obj.display_type = 'WIRE'
                                    mesh_obj.color = (0.005, 0.79105, 1, 1)
                                    mesh_obj.show_wire = True
                                    mesh_obj.show_in_front = True
                                    mesh_obj.display.show_shadows = False
                                    mesh_obj.rotation_mode = 'QUATERNION'
                                    verts=[]
                                    for v in vertices:
                                        verts.append((v['X'],v['Y'],v['Z']))
                                    edges=[]
                                    Faces=[indices[i:i+3] for i in range(0, len(indices), 3)]
                                    mesh_data.from_pydata(verts, edges, Faces)
                                    mesh_obj['ntype'] = 'entLightChannelComponent'
                                    mesh_obj['name'] = c['name']['$value']
                                    mesh_obj['entJSON'] = filepath

                                    bindname=c['parentTransform']['Data']['bindName']['$value']
                                    if bindname=='vehicle_slots':
                                        if vehicle_slots:
                                            slotname=c['parentTransform']['Data']['slotName']['$value']
                                            if slotname=='None':
                                                slotname='Base'
                                            for slot in vehicle_slots:
                                                if slot['slotName']['$value']==slotname:
                                                    bindname=slot['boneName']['$value']
                                                    mesh_obj['bindname']=bindname
                                    lcgroup.objects.link(mesh_obj)
                                    Masters.children.link(lcgroup)
                    if lcgroupname in bpy.data.collections.get("MasterInstances").children:
                        Mastlcgroup=bpy.data.collections.get(lcgroupname)
                        if (Mastlcgroup):
                            lcgroup=bpy.data.collections.new(lcgroupname)
                            ent_coll.children.link(lcgroup)
                            for old_obj in Mastlcgroup.all_objects:
                                obj=old_obj.copy()
                                lcgroup.objects.link(obj)
                            mesh_obj=lcgroup.all_objects[0]
                            bindname=mesh_obj.get('bindname','')
                        if bindname and rig and lcgroup and mesh_obj:
                            co=mesh_obj.constraints.new(type='COPY_LOCATION')
                            co.target=rig
                            co.subtarget= bindname
            print('Appearance import time:', time.time() - app_start_time, 'Seconds')


              # find the .phys file jsons
        if include_collisions:
            collision_collection = bpy.data.collections.new('colliders')
            ent_coll.children.link(collision_collection)
            if include_phys:
                try:
                    physJsonPaths = asset_index.get_files_by_extension('.phys.json')
                    if len(physJsonPaths) == 0:
                        print('No phys file JSONs found in path')
                    else:
                        if len(chassis_info) > 0:
                            chassis_z = chassis_info['localTransform']['Position']['z']['Bits'] / 131072
                            chassis_phys_j=os.path.basename(chassis_info['collisionResource']['DepotPath']['$value'])+'.json'
                        else:
                            #this isn't really right, but the value seems to always be very close so it's better than 0
                            chassis_z = rig_j['boneTransforms'][2]['Translation']['Z']
                        #print('colliders:', ent_colliderComps)
                        for physJsonPath in physJsonPaths:
                            if os.path.basename(physJsonPath)==chassis_phys_j:
                                cp77_phys_import(physJsonPath, rig, chassis_z)
                except Exception as e:
                    print(e)

            if include_entCollider:
                if len(ent_colliderComps) == 0 and len(ent_simpleCollComps)== 0:
                    print('No entColliderComponent or entSimpleColliderComponents found')
                    return('FINISHED')
                else:
                    for index, i in enumerate(ent_component_data):
                        if i['$type'] in ('entColliderComponent', 'entSimpleColliderComponent'):
                            collision_type = 'ENTITY'
                            col_name = i['$type']
                            
                            # Find or create a sub-collection for these collider types
                            new_col = None
                            for child in collision_collection.children:
                                if child.name == col_name:
                                    new_col = child
                                    break
                            
                            if not new_col:
                                new_col = bpy.data.collections.new(col_name)
                                collision_collection.children.link(new_col)
                                
                            cdata = i['colliders'][0]['Data']
                            collision_shape = cdata['$type']
                            submeshName = '_' + collision_shape
                            
                            # Pass to pxbridge to create a native PhysX actor instead of a mesh representation
                            try:
                                obj = import_collider_as_actor(cdata, submeshName, new_col)
                                if obj:
                                    # Add extra properties for reference
                                    if 'simulationType' in i:
                                        obj['simulationType'] = i['simulationType']
                            except Exception as e:
                                print(f'Error importing {collision_shape} via pxbridge: {e}')
    if rig and getattr(rig, 'type', None) == 'ARMATURE' and getattr(rig, 'data', None):
        rig.data.pose_position = 'REST'
    if entinitiatedcache:
        JSONTool.stop_caching()
    if len(error_messages) > 0:
        show_message('Errors during import:\n\t' + '\n\t'.join(error_messages))
    if Masters:
        Masters.hide_viewport=True
    if not cp77_addon_prefs.non_verbose:
        print(f"Imported Entity in {time.time() - start_time} Seconds from {ent_name}.ent")
        print('-------------------- Finished Importing Cyberpunk 2077 Entity --------------------\n')
