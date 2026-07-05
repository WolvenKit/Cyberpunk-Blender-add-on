# Blender Entity import script by Simarilius
# Updated May 23 with vehicle rig support
import json
import re
import os
import bpy
import time
import math
import traceback
from math import sin,cos
from mathutils import Vector, Matrix , Quaternion
import bmesh
from ..main.common import *
from ..jsontool import JSONTool
from .phys_import import cp77_phys_import
from ..collisiontools.pxbridge.io_phys import import_collider_as_actor
from io_scene_gltf2.io.imp.gltf2_io_gltf import glTFImporter
from .import_common import *
from ..datakrash import DepotAssetIndex
from .read_rig import create_armature_from_data
from bpy_extras import anim_utils

SUBMESH_PATTERN = re.compile(r"submesh_(\d+)", re.IGNORECASE)
ARMATURE_TYPE = 'ARMATURE'


def create_axes(ent_coll,name):
    if name not in ent_coll.objects.keys():
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


def fixed_point_position(transform):
    position = transform.get('Position', {}) if isinstance(transform, dict) else {}
    return Vector((
        position.get('x', {}).get('Bits', 0) / 131072,
        position.get('y', {}).get('Bits', 0) / 131072,
        position.get('z', {}).get('Bits', 0) / 131072,
    ))


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
    return {component_name(component): component for component in components if component_name(component)}


def build_ent_app_lookup(ent_apps):
    by_appearance = {
        cname_value(app.get('appearanceName')): index
        for index, app in enumerate(ent_apps)
        if cname_value(app.get('appearanceName'))
    }
    by_name = {
        cname_value(app.get('name')): index
        for index, app in enumerate(ent_apps)
        if cname_value(app.get('name'))
    }
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


def build_parent_transform_lookup(chunks):
    lookup = {}
    if not chunks:
        return lookup
    for chunk in chunks:
        parent_transform = chunk.get('parentTransform') if isinstance(chunk, dict) else None
        if isinstance(parent_transform, dict) and 'HandleId' in parent_transform:
            lookup[parent_transform['HandleId']] = parent_transform
    return lookup


def build_skinning_lookup(chunks):
    lookup = {}
    if not chunks:
        return lookup
    for chunk in chunks:
        skinning = chunk.get('skinning') if isinstance(chunk, dict) else None
        if isinstance(skinning, dict) and 'HandleId' in skinning:
            lookup[skinning['HandleId']] = skinning
    return lookup


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
    return {cname_value(slot.get('slotName')): slot for slot in vehicle_slots or [] if cname_value(slot.get('slotName'))}


def resolve_slot_bone(slot_lookup, slotname, fallback=None):
    slot = slot_lookup.get(slotname) if slot_lookup else None
    return cname_value(slot.get('boneName'), fallback) if slot else fallback


def build_rig_bone_index(rig_j):
    if not rig_j or not rig_j.get('boneNames'):
        return {}
    return {cname_value(bone): index for index, bone in enumerate(rig_j['boneNames']) if cname_value(bone)}

def rig_json_bone_matrix(rig_j, bone_name):
    if not isinstance(rig_j, dict) or not bone_name:
        return Matrix.Identity(4)
    bone_names = rig_j.get('boneNames')
    if not isinstance(bone_names, list):
        return Matrix.Identity(4)
    index = None
    for candidate_index, bone in enumerate(bone_names):
        if cname_value(bone) == bone_name:
            index = candidate_index
            break
    if index is None:
        return Matrix.Identity(4)
    for key in ('aPoseMS', 'boneTransforms', 'aPoseLS'):
        transforms = rig_j.get(key)
        if isinstance(transforms, list) and index < len(transforms):
            return qs_transform_matrix(transforms[index])
    return Matrix.Identity(4)


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
    candidates = {depot_path, meshpath, meshname, os.path.basename(depot_path.replace('\\', os.sep)) if depot_path else ''}
    norm_candidates = {norm_path_key(candidate) for candidate in candidates if candidate}
    return bool(norm_candidates.intersection(excluded_meshes))



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


def red_transform_matrix(transform, visual_scale=None):
    if not isinstance(transform, dict):
        return Matrix.Identity(4)
    return Matrix.LocRotScale(
        fixed_point_position(transform),
        red_quaternion(transform.get('Orientation')),
        red_scale(transform, visual_scale),
    )


def slot_transform_matrix(slot):
    if not isinstance(slot, dict):
        return Matrix.Identity(4)
    pos_data = slot.get('relativePosition') if isinstance(slot.get('relativePosition'), dict) else {}
    pos = Vector((
        pos_data.get('X', 0),
        pos_data.get('Y', 0),
        pos_data.get('Z', 0),
    ))
    return Matrix.LocRotScale(
        pos,
        red_quaternion(slot.get('relativeRotation')),
        Vector((1, 1, 1)),
    )


def slot_translation_matrix(slot):
    if not isinstance(slot, dict):
        return Matrix.Identity(4)
    pos_data = slot.get('relativePosition') if isinstance(slot.get('relativePosition'), dict) else {}
    return Matrix.Translation(Vector((
        pos_data.get('X', 0),
        pos_data.get('Y', 0),
        pos_data.get('Z', 0),
    )))


def qs_transform_matrix(transform):
    if not isinstance(transform, dict):
        return Matrix.Identity(4)
    translation = transform.get('Translation')
    if isinstance(translation, dict):
        location = Vector((
            translation.get('X', 0),
            translation.get('Y', 0),
            translation.get('Z', 0),
        ))
    else:
        location = fixed_point_position(transform)
    scale_data = transform.get('Scale') if isinstance(transform.get('Scale'), dict) else None
    scale = Vector((
        scale_data.get('X', 1),
        scale_data.get('Y', 1),
        scale_data.get('Z', 1),
    )) if scale_data else Vector((1, 1, 1))
    return Matrix.LocRotScale(location, red_quaternion(transform.get('Rotation') or transform.get('Orientation')), scale)


def parent_transform_data(component, parent_transform_lookup):
    parent_transform = component.get('parentTransform') if isinstance(component, dict) else None
    if not isinstance(parent_transform, dict):
        return None
    if 'Data' in parent_transform:
        return parent_transform.get('Data')
    handle_id = parent_transform.get('HandleRefId')
    if handle_id is None:
        return None
    if hasattr(parent_transform_lookup, 'get_for_component'):
        referenced = parent_transform_lookup.get_for_component(component, handle_id)
    else:
        referenced = parent_transform_lookup.get(handle_id) if parent_transform_lookup else None
    if isinstance(referenced, dict):
        return referenced.get('Data')
    return None


def skinning_binding_data(component, skinning_lookup=None):
    skinning = component.get('skinning') if isinstance(component, dict) else None
    if not isinstance(skinning, dict):
        return None
    if isinstance(skinning.get('Data'), dict):
        return skinning.get('Data')
    handle_id = skinning.get('HandleRefId')
    if handle_id is None:
        return skinning
    if hasattr(skinning_lookup, 'get_for_component'):
        referenced = skinning_lookup.get_for_component(component, handle_id)
    else:
        referenced = skinning_lookup.get(handle_id) if skinning_lookup else None
    if isinstance(referenced, dict):
        return referenced.get('Data')
    return skinning


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


def current_armature_names():
    return {obj.name for obj in bpy.data.objects if getattr(obj, 'type', None) == ARMATURE_TYPE}


def imported_armatures_since(previous_names):
    selected = [obj for obj in bpy.context.selected_objects if getattr(obj, 'type', None) == ARMATURE_TYPE and obj.name not in previous_names]
    if selected:
        return selected
    return [obj for obj in bpy.data.objects if getattr(obj, 'type', None) == ARMATURE_TYPE and obj.name not in previous_names]


def set_child_of_inverse(constraint, target, subtarget_name=''):
    target_matrix = target.matrix_world.copy()
    if subtarget_name and getattr(target, 'pose', None) and subtarget_name in target.pose.bones:
        target_matrix = target.matrix_world @ target.pose.bones[subtarget_name].matrix
    try:
        constraint.inverse_matrix = target_matrix.inverted()
    except Exception:
        constraint.inverse_matrix = Matrix.Identity(4)

def existing_armature_for_rig_json(rig_json_path):
    target = norm_path_key(rig_json_path)
    if not target:
        return None
    for obj in bpy.data.objects:
        if getattr(obj, 'type', None) != ARMATURE_TYPE:
            continue
        candidates = [obj.get('rig'), obj.get('source_rig_file'), obj.get('sourceRigFile')]
        for candidate in candidates:
            if candidate and norm_path_key(candidate) == target:
                return obj
    return None


def ensure_armature_from_rig_json(rig_json_path, component_name_value='', ent_name=''):
    if not rig_json_path:
        return None
    existing = existing_armature_for_rig_json(rig_json_path)
    if existing is not None:
        return existing

    old_armature_names = current_armature_names()
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
            new_armatures = imported_armatures_since(old_armature_names)
            if new_armatures:
                armature = new_armatures[0]

    if armature is not None:
        armature['rig'] = rig_json_path
        armature['source_rig_file'] = rig_json_path
        if component_name_value:
            armature['componentName'] = component_name_value
        if ent_name:
            armature['ent'] = ent_name + '.ent.json'
    return armature


def armature_has_bone(armature, bone_name):
    return bool(
        armature
        and bone_name
        and getattr(armature, 'pose', None)
        and bone_name in armature.pose.bones
    )


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
        self.resolving = set()

    def _slot_owner_rig_json(self, slot_owner=None):
        if slot_owner and slot_owner in self.slot_owner_rig_jsons:
            return self.slot_owner_rig_jsons[slot_owner]
        return self.rig_j

    def _rig_json_has_bone(self, bone_name, rig_j=None):
        if not bone_name or not isinstance(rig_j, dict) or not rig_j.get('boneNames'):
            return False
        index = self.rig_json_bone_indices.get(id(rig_j))
        if index is None:
            index = build_rig_bone_index(rig_j)
            self.rig_json_bone_indices[id(rig_j)] = index
        return bone_name in index

    def _rig_json_for_bone(self, bone_name, slot_owner=None):
        preferred = self._slot_owner_rig_json(slot_owner)
        if self._rig_json_has_bone(bone_name, preferred):
            return preferred
        for rig_json in self.rig_json_by_component_name.values():
            if rig_json is not preferred and self._rig_json_has_bone(bone_name, rig_json):
                return rig_json
        return preferred

    def _slot_owner_rig_owner_name(self, slot_owner=None):
        if slot_owner and slot_owner in self.slot_owner_rig_owner_names:
            return self.slot_owner_rig_owner_names[slot_owner]
        return ''

    def _armature_for_bone(self, bone_name, slot_owner=None):
        owner_name = self._slot_owner_rig_owner_name(slot_owner)
        if owner_name:
            armature = self.armature_by_component_name.get(owner_name)
            if armature_has_bone(armature, bone_name):
                return armature
        if armature_has_bone(self.rig, bone_name):
            return self.rig
        for armature in self.armature_by_component_name.values():
            if armature_has_bone(armature, bone_name):
                return armature
        return None

    def _pose_bone(self, bone_name, slot_owner=None):
        armature = self._armature_for_bone(bone_name, slot_owner)
        if armature is not None:
            return armature, armature.pose.bones[bone_name]
        return None, None

    def bone_matrix(self, bone_name, slot_owner=None):
        armature, pose_bone = self._pose_bone(bone_name, slot_owner)
        if pose_bone is not None:
            return armature.matrix_world @ pose_bone.matrix
        rig_j = self._rig_json_for_bone(bone_name, slot_owner)
        if self._rig_json_has_bone(bone_name, rig_j):
            return rig_json_bone_matrix(rig_j, bone_name)
        return Matrix.Identity(4)

    def resolve_slot_matrix(self, slot_owner, slot_name):
        slot_lookup = self.slot_component_lookups.get(slot_owner) or {}
        if slot_owner in ('vehicle_slots', 'slots') and self.default_slot_lookup:
            slot_lookup = slot_lookup or self.default_slot_lookup
        slot = slot_lookup.get(slot_name)
        if not slot:
            return Matrix.Identity(4), slot_owner, slot_name
        bone_name = cname_value(slot.get('boneName'), slot_name)
        return self.bone_matrix(bone_name, slot_owner) @ slot_transform_matrix(slot), bone_name, slot_name

    def resolve_binding(self, component):
        binding = parent_transform_data(component, self.parent_transform_lookup)
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
        key = component_name(component) or str(id(component))
        if key in self.cache:
            return self.cache[key]
        if key in self.resolving:
            return Matrix.Identity(4), '', '', 'cycle'
        self.resolving.add(key)
        parent_matrix, bind_name, slot_name, binding_type = self.resolve_binding(component)
        local_matrix = red_transform_matrix(component.get('localTransform', {}), component.get('visualScale'))
        matrix = parent_matrix @ local_matrix
        result = (matrix, bind_name, slot_name, binding_type)
        self.cache[key] = result
        self.resolving.remove(key)
        return result

    def _bone_rotation(self, bone_name, slot_owner=None):
        _, pose_bone = self._pose_bone(bone_name, slot_owner)
        if pose_bone is not None:
            return pose_bone.rotation_quaternion.copy()
        rig_j = self._rig_json_for_bone(bone_name, slot_owner)
        if self._rig_json_has_bone(bone_name, rig_j):
            return rig_json_bone_matrix(rig_j, bone_name).to_quaternion()
        return Quaternion((1, 0, 0, 0))

    def _bone_head(self, bone_name, slot_owner=None):
        _, pose_bone = self._pose_bone(bone_name, slot_owner)
        if pose_bone is not None:
            return pose_bone.head.copy()
        rig_j = self._rig_json_for_bone(bone_name, slot_owner)
        if self._rig_json_has_bone(bone_name, rig_j):
            return rig_json_bone_matrix(rig_j, bone_name).to_translation()
        return Vector((0, 0, 0))

    def _rig_bone_index(self, bone_name):
        if not bone_name:
            return None
        return self.rig_bone_index.get(bone_name)

    def _rig_space_bone_matrix(self, bone_name):
        index = self._rig_bone_index(bone_name)
        if index is None:
            if self.rig and getattr(self.rig, 'pose', None) and bone_name in self.rig.pose.bones:
                return self.rig.pose.bones[bone_name].matrix.copy()
            return Matrix.Identity(4)
        for key in ('aPoseMS', 'boneTransforms', 'aPoseLS'):
            transforms = self.rig_j.get(key) if isinstance(self.rig_j, dict) else None
            if isinstance(transforms, list) and index < len(transforms):
                return qs_transform_matrix(transforms[index])
        if self.rig and getattr(self.rig, 'pose', None) and bone_name in self.rig.pose.bones:
            return self.rig.pose.bones[bone_name].matrix.copy()
        return Matrix.Identity(4)

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
        slot_lookup = self.slot_component_lookups.get(owner) or {}
        if owner in ('vehicle_slots', 'slots') and self.default_slot_lookup:
            slot_lookup = slot_lookup or self.default_slot_lookup
        return slot_lookup.get(slot_name)

    def _slot_bone_name(self, owner, slot_name):
        slot = self._slot(owner, slot_name)
        if slot:
            return cname_value(slot.get('boneName'), slot_name)
        return slot_name or owner

    def _binding_name(self, component):
        binding = parent_transform_data(component, self.parent_transform_lookup)
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
            x = local_pos.x
            y = local_pos.y
            local_pos = Vector((
                x * cos(z_ang) + y * sin(z_ang),
                x * sin(z_ang) + y * cos(z_ang),
                local_pos.z,
            ))

        rotation = self._bone_rotation(bone_name, slot_owner) @ slot_rot @ red_quaternion(local_transform.get('Orientation'))
        scale = red_scale(local_transform, visual_scale)
        return Matrix.LocRotScale(self._bone_head(bone_name, slot_owner) + slot_pos + local_pos, rotation, scale)

    def resolve_hard_component_matrix(self, component):
        key = 'hard:' + (component_name(component) or str(id(component)))
        if key in self.cache:
            return self.cache[key]
        if key in self.resolving:
            return Matrix.Identity(4), '', '', 'cycle'
        self.resolving.add(key)

        local_transform = component.get('localTransform', {}) if isinstance(component, dict) else {}
        visual_scale = component.get('visualScale') if isinstance(component, dict) else None
        animated_slot_basis = self._animated_slot_component_basis(component)
        if animated_slot_basis is not None:
            result = (animated_slot_basis @ red_transform_matrix(local_transform, visual_scale), self._binding_name(component), '', 'animated_slot_component')
            self.cache[key] = result
            self.resolving.remove(key)
            return result
        binding = parent_transform_data(component, self.parent_transform_lookup)
        if not isinstance(binding, dict):
            result = (red_transform_matrix(local_transform, visual_scale), '', '', 'none')
            self.cache[key] = result
            self.resolving.remove(key)
            return result

        bind_name = cname_value(binding.get('bindName'))
        slot_name = cname_value(binding.get('slotName'))
        if not bind_name or bind_name == 'None':
            result = (red_transform_matrix(local_transform, visual_scale), bind_name, slot_name, 'none')
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
            result = (base @ red_transform_matrix(local_transform, visual_scale), bind_name, slot_name, 'deformation_rig')
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
                        )
                        parent_bind = bone_name or parent_bind or bind_name
                        parent_slot = slot_name
                        parent_type = 'slot'
                    elif not skip_animated_base_slot:
                        parent_matrix = parent_matrix @ slot_transform_matrix(slot)
                        parent_type = 'component_slot'
            result = (parent_matrix @ red_transform_matrix(local_transform, visual_scale), parent_bind or bind_name, parent_slot or slot_name, parent_type if parent_type != 'none' else 'component')
            self.cache[key] = result
            self.resolving.remove(key)
            return result

        if self.rig and getattr(self.rig, 'pose', None) and bind_name in self.rig.pose.bones:
            result = (self._hard_bone_slot_matrix(bind_name, bind_name, slot_name, local_transform, visual_scale), bind_name, slot_name, 'bone')
            self.cache[key] = result
            self.resolving.remove(key)
            return result

        result = (red_transform_matrix(local_transform, visual_scale), bind_name, slot_name, 'unresolved')
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
        # get the armatures already in the model
        old_armature_names = current_armature_names()
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
            arms = imported_armatures_since(old_armature_names)
            if arms:
                rig=arms[0]
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
        if "MasterInstances" not in coll_scene.children.keys():
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
                depot_path = mesh_component_depot(c)
                if not depot_path:
                    continue
                meshname=depot_to_local_path(path, depot_path)
                meshpath=resolve_mesh_glb_path(asset_index, depot_path)
                if meshname and meshpath and not is_excluded_mesh(depot_path, meshpath, os.path.basename(meshname), excluded_meshes):
                    meshApp=mesh_appearance_value(c)
                    if(meshname != 0):
                        if meshname not in meshes:
                            meshes[meshname] = {'appearances':[meshApp],'sector':'ALL'}
                        else:
                            meshes[meshname]['appearances'].append(meshApp)

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
            if inColl and inColl in coll_scene.children.keys():
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


            enum_items = []
            default_index = None

            for idx, variant in enumerate(ent_applist):
                enum_items.append((str(idx), variant, f"appearanceName {idx + 1}"))
                if variant == app_name:  # Check if the variant matches the passed app_name
                    default_index = str(idx)  # Set the default index if found

            if default_index is None:
                default_index = '0'

            if len(enum_items)>0:
                bpy.types.Collection.appearanceName = bpy.props.EnumProperty(
                    name="Ent Appearances",
                    items=enum_items,
                    default=default_index,
                )

            comps=app_comps.get(requested_app_name) or app_comps.get(app_name) or ent_components
            transform_components = list(ent_components)
            for comp in comps:
                if comp not in transform_components:
                    transform_components.append(comp)
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
                                    old_armature_names = current_armature_names()
                                    anim_depot = gameplay_anims[0]['animSet']['DepotPath']['$value']
                                    animpath=resolve_anim_glb_path(asset_index, anim_depot)
                                    if animpath:
                                        bpy.ops.io_scene_gltf.cp77(with_materials, filepath=animpath, scripting=True)
                                        # find the armature we just loaded
                                        arms = imported_armatures_since(old_armature_names)
                                        if arms:
                                            rig=arms[0]
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
                        bones = rig.pose.bones
                        rig_j = rig_json_by_component_name.get(rig_name, rig_j)
                        rig_bone_index = build_rig_bone_index(rig_j)
            else:
                component_name_value = rig.get('componentName') if hasattr(rig, 'get') else None
                if component_name_value and component_name_value not in armature_by_component_name:
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
                vs_rot=None
                if not (c.get('$type')=='gameTransformAnimatorComponent' or 'mesh' in c.keys() or 'graphicsMesh' in c.keys()):
                    continue

                if c.get('$type')=='gameTransformAnimatorComponent' and c['animations'][0]['$type']=='gameTransformAnimationDefinition':
                    duration=c['animations'][0]['timeline']['items'][0]['duration']
                    HRID=c['animations'][0]['timeline']['items'][0]['impl']['HandleRefId']
                    chunk_anim = anim_impl_lookup.get(int(HRID), 0)
                    anim_HId=0
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
                elif 'mesh' in c.keys() or 'graphicsMesh' in c.keys():
                    #print(c['mesh']['DepotPath']['$value'])
                    depot_path = mesh_component_depot(c)
                    meshname=os.path.basename(depot_path.replace('\\',os.sep)) if depot_path else ''
                    meshpath=resolve_mesh_glb_path(asset_index, depot_path)
                    component_enabled = is_component_enabled(c)
                    if meshname and meshpath and not is_excluded_mesh(depot_path, meshpath, meshname, excluded_meshes):
                        new=None
                        try:
                            meshApp=mesh_appearance_value(c)
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
                                    for old_obj in group.all_objects:
                                        obj=old_obj.copy()
                                        object_copy_map[old_obj] = obj
                                        copied_objects.append(obj)
                                        new.objects.link(obj)
                                    remap_copied_object_references(copied_objects, object_copy_map)
                                    for obj in copied_objects:
                                        obj['componentName'] = comp_name
                                        obj['sourcePath'] = meshpath
                                        obj['meshAppearance'] = meshApp
                                        obj['componentEnabled'] = component_enabled
                                        if app_path:
                                            obj['appResource'] = app_path[0]
                                        obj['entAppearance'] = app_name
                                        if not component_enabled:
                                            obj.hide_set(True)
                                            obj.hide_render = True
                                        if 'Armature' in obj.name:
                                            obj.hide_set(True)
                                else:
                                    print('BREAK collection not found after import - ', meshname)
                            except:
                                print('import threw an error:')
                                print(traceback.format_exc())
                                continue
                            print('checking for collection - ', meshname)
                            if new is None:
                                print('collection not found after import - ', meshname)
                                continue
                            objs = new.objects
                            component_is_skinned = component_uses_deformation_skinning(c, skinning_lookup)
                            skinning_bind = skinning_bind_name(c, skinning_lookup)
                            if component_is_skinned:
                                resolved_matrix, bindname, slotname, binding_type = transform_resolver.resolve_component_matrix(c)
                            else:
                                resolved_matrix, bindname, slotname, binding_type = transform_resolver.resolve_hard_component_matrix(c)
                            if component_is_skinned:
                                bind_skinned_objects_to_rig(new.objects, rig)
                            for obj in new.objects:
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
                                if component_is_skinned:
                                    continue
                                if binding_type in {'slot', 'bone'} and rig and bindname and getattr(rig, 'pose', None) and bindname in rig.pose.bones:
                                    if 'Child Of' not in obj.constraints.keys():
                                        co = obj.constraints.new(type='CHILD_OF')
                                        co.target = rig
                                        co.subtarget = bindname
                                        set_child_of_inverse(co, rig, bindname)
                                    if 'wheel' in bindname:
                                        cr = obj.constraints.new(type='COPY_ROTATION')
                                        cr.target = rig
                                        if 'steering' not in bindname:
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

                            # New chunkMask reading
                            # convert the value to a list of bools, then apply those statuses to the submeshes.
                            if 'chunkMask' in c.keys():
                                cm= c['chunkMask']
                                if isinstance(cm,str):
                                    bin_str = bin(int(cm))[2:]
                                else:
                                    bin_str = bin(cm)[2:]
                                cm_list = [bool(int(bit)) for bit in bin_str]
                                cm_list.reverse()
                                for obj in objs:
                                    subnum = None
                                    # Try to parse index from object name like 'submesh_00'
                                    m = SUBMESH_PATTERN.search(obj.name)
                                    if m:
                                        subnum = int(m.group(1))
                                    else:
                                        # Fallback: try from material names
                                        mats = getattr(obj.data, 'materials', []) if hasattr(obj, 'data') else []
                                        for mat in mats:
                                            if mat and getattr(mat, 'name', None):
                                                m2 = SUBMESH_PATTERN.search(mat.name)
                                                if m2:
                                                    subnum = int(m2.group(1))
                                                    break
                                    if subnum is None:
                                        continue
                                    bit = cm_list[subnum] if subnum < len(cm_list) else True
                                    hidden = (not component_enabled) or (not bit)
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
                    if not lcgroupname in bpy.data.collections.get("MasterInstances").children.keys():
                        if 'shape' in c.keys() and 'Data' in c['shape'].keys() and 'vertices' in c['shape']['Data'].keys():
                            vertices=c['shape']['Data']['vertices']
                            if len(vertices)>0 and 'indices' in c['shape']['Data'].keys():
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
                    if lcgroupname in bpy.data.collections.get("MasterInstances").children.keys():
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
