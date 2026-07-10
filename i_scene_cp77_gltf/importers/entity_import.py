# Blender Entity import script by Simarilius
import re
import os
import bpy
import time
import math
import random
import traceback
from functools import lru_cache
from mathutils import Vector, Matrix, Quaternion
from ..main.common import *
from ..jsontool import JSONTool
from .phys_import import cp77_phys_import
from ..collisiontools.pxbridge.io_phys import import_collider_as_actor
from .import_common import *
from .import_common import _remap_copied_object_references
from ..datakrash import DEFAULT_ASSET_EXTENSIONS, DepotAssetIndex
from .read_rig import create_armature_from_data
from bpy_extras import anim_utils

SUBMESH_PATTERN = re.compile(r"submesh_(\d+)", re.IGNORECASE)
ARMATURE_TYPE = 'ARMATURE'
FIXED_POINT_DIVISOR = 131072
POSITION_KEYS = ('Position', 'Translation', 'relativePosition')
ROTATION_KEYS = ('Orientation', 'Rotation', 'relativeRotation')
_AXIS_INDEX = {'X': 0, 'Y': 1, 'Z': 2}
_UNSET = object()

_SUBMESH_INDEX_CACHE = {}
_RIG_ARMATURE_OBJECT_CACHE = {}
_ARMATURE_BONE_SET_CACHE = {}
_RIG_BONE_INDEX_CACHE = {}
_RIG_BONE_MATRIX_CACHE = {}


def clear_transient_import_caches():
    _SUBMESH_INDEX_CACHE.clear()
    _RIG_ARMATURE_OBJECT_CACHE.clear()
    _ARMATURE_BONE_SET_CACHE.clear()
    _RIG_BONE_INDEX_CACHE.clear()
    _RIG_BONE_MATRIX_CACHE.clear()


def create_axes(ent_coll, name):
    obj = ent_coll.objects.get(name)
    if obj is None:
        obj = bpy.data.objects.new(name, None)
        ent_coll.objects.link(obj)
        obj.empty_display_size = .5
        obj.empty_display_type = 'PLAIN_AXES'
        obj.rotation_mode = 'XYZ'
    return obj


def ensure_action_slot(action, datablock):
    anim_data = datablock.animation_data_create()
    anim_data.action = action
    if anim_data.action_slot is not None:
        return anim_data.action_slot
    slots = action.slots
    slot = slots[0] if len(slots) else slots.new(id_type=datablock.id_type, name=datablock.name)
    anim_data.action_slot = slot
    return slot


def set_rotation_axis_cycles(obj, axis_no, delta_radians, end_frame):
    start_value = obj.rotation_euler[axis_no]
    action = bpy.data.actions.new(f'{obj.name}_rotation')
    channelbag = anim_utils.action_ensure_channelbag_for_slot(action, ensure_action_slot(action, obj))
    fcurve = channelbag.fcurves.ensure('rotation_euler', index=axis_no, group_name='Rotation')
    keyframes = fcurve.keyframe_points
    if len(keyframes) < 2:
        keyframes.add(2 - len(keyframes))
    keyframes[0].co = (1, start_value)
    keyframes[1].co = (end_frame, start_value + delta_radians)
    keyframes[0].interpolation = 'LINEAR'
    keyframes[1].interpolation = 'LINEAR'
    fcurve.update()
    modifier = fcurve.modifiers.new(type='CYCLES')
    modifier.mode_before = 'REPEAT'
    modifier.mode_after = 'REPEAT'


def cname_value(value, default=''):
    if type(value) is dict:
        return value.get('$value', default)
    return value if value is not None else default


def component_name(component, default=''):
    return cname_value(component.get('name'), default) if type(component) is dict else default


def depot_path_value(component, *keys):
    if type(component) is not dict:
        return ''
    for key in keys:
        resource = component.get(key)
        if type(resource) is dict:
            depot_path = cname_value(resource.get('DepotPath'))
            if depot_path:
                return depot_path
    return ''


def red_quaternion(value):
    if type(value) is not dict:
        return Quaternion((1, 0, 0, 0))
    return Quaternion((
        value.get('r', 1),
        value.get('i', 0),
        value.get('j', 0),
        value.get('k', 0),
    ))


def is_component_enabled(component):
    return component.get('isEnabled', 1) != 0 if type(component) is dict else True


def depot_to_local_path(root, depot_path):
    return os.path.join(root, depot_path).replace('\\', os.sep) if depot_path else ''


@lru_cache(maxsize=65536)
def norm_path_key(value):
    return os.path.normcase(os.path.normpath(value)) if value else ''


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


def indexed_asset_files(asset_index, extension, provided=None):
    if provided:
        return sorted(os.path.normpath(path) for path in provided)
    return asset_index.get_files_by_extension(extension)


def load_root_chunk_json(json_path, error_messages):
    if not json_path:
        return None
    loaded = JSONTool.jsonload(json_path, error_messages)
    if loaded is None:
        return None
    return loaded.get('Data', {}).get('RootChunk')


def build_component_lookup(components):
    lookup = {}
    for component in components or []:
        name = component_name(component)
        if name:
            lookup[name] = component
    return lookup


def ent_appearance_name(ent_app, default=''):
    return cname_value(ent_app.get('appearanceName'), default) if type(ent_app) is dict else default


def ent_template_appearance_name(ent_app, default=''):
    return cname_value(ent_app.get('name'), default) if type(ent_app) is dict else default


def _appearance_lookup_index(lookup, key):
    if not key or not lookup:
        return -1
    try:
        return int(lookup.get(key, -1))
    except (TypeError, ValueError):
        return -1


def resolve_ent_appearance_alias(app_name, ent_apps, by_appearance=None, by_name=None):
    if not app_name or app_name == 'None':
        return -1, ''

    for lookup in (by_appearance, by_name):
        ent_app_idx = _appearance_lookup_index(lookup, app_name)
        if 0 <= ent_app_idx < len(ent_apps):
            return ent_app_idx, ent_appearance_name(ent_apps[ent_app_idx], app_name)

    for ent_app_idx, ent_app in enumerate(ent_apps or []):
        appearance_name = ent_appearance_name(ent_app)
        template_name = ent_template_appearance_name(ent_app)
        if app_name == appearance_name or app_name == template_name:
            return ent_app_idx, appearance_name or app_name

    return -1, ''


def appearance_request_is_known(app_name, ent_default, ent_apps, by_appearance, by_name):
    if not app_name or app_name == 'BASE_COMPONENTS_ONLY' or app_name.upper() == 'ALL':
        return True
    if app_name == 'default':
        return not ent_apps or not ent_default or resolve_ent_appearance_alias(ent_default, ent_apps, by_appearance, by_name)[0] >= 0
    return resolve_ent_appearance_alias(app_name, ent_apps, by_appearance, by_name)[0] >= 0


def resolve_requested_appearance_name(app_name, ent_default, ent_apps, by_appearance, by_name):
    if app_name == 'default':
        if not ent_default:
            return 'default'
        _, resolved_name = resolve_ent_appearance_alias(ent_default, ent_apps, by_appearance, by_name)
        return resolved_name or ent_default

    _, resolved_name = resolve_ent_appearance_alias(app_name, ent_apps, by_appearance, by_name)
    return resolved_name or app_name


def resolve_ent_app(app_name, ent_apps, by_appearance, by_name, ent_default=None):
    candidates = []
    if app_name and app_name != 'default':
        candidates.append((app_name, app_name))
    if ent_default and ent_default != 'default' and ent_default != 'None':
        candidates.append((ent_default, app_name))

    seen = set()
    for search_term, fallback_name in candidates:
        if search_term in seen:
            continue
        seen.add(search_term)

        ent_app_idx, resolved_name = resolve_ent_appearance_alias(search_term, ent_apps, by_appearance, by_name)
        if ent_app_idx >= 0:
            print('appearance matched, id = ', ent_app_idx)
            if search_term != resolved_name and search_term != fallback_name:
                print(f'appearance alias resolved: {search_term} -> {resolved_name}')
            return ent_app_idx, resolved_name or fallback_name

    return 0, ent_appearance_name(ent_apps[0], app_name) if ent_apps else app_name


def resolve_entity_appearance_for_file(filepath, requested_app, error_messages=None):
    parsed_ent = JSONTool.load_entity(filepath, error_messages or []) if filepath else None
    if parsed_ent is None:
        return requested_app
    return resolve_requested_appearance_name(
        requested_app,
        parsed_ent.default_appearance,
        parsed_ent.appearances,
        parsed_ent.appearances_by_appearance,
        parsed_ent.appearances_by_name,
    )


def build_chunk_lookup(chunks, target_key, handle_key='HandleId'):
    lookup = {}
    for chunk in chunks or []:
        if not isinstance(chunk, dict):
            continue
        target_data = chunk.get(target_key)
        if isinstance(target_data, dict) and handle_key in target_data:
            lookup[target_data[handle_key]] = target_data
    return lookup


def light_channel_geometry(component, shape_lookup=None):
    shape = resolve_handle_data(component, shape_lookup, 'shape') if shape_lookup is not None else None
    if not isinstance(shape, dict):
        shape = component.get('shape') if type(component) is dict else None
        if isinstance(shape, dict) and isinstance(shape.get('Data'), dict):
            shape = shape.get('Data')
    if not isinstance(shape, dict):
        return None, None
    vertices = shape.get('vertices')
    indices = shape.get('indices') or shape.get('faces')
    if not vertices or not indices:
        return None, None
    return vertices, indices


def collect_light_channel_components(*component_groups):
    collected = {}
    order = []
    for components in component_groups:
        for source in components or ():
            if not isinstance(source, dict) or source.get('$type') != 'entLightChannelComponent':
                continue
            key = component_name(source) or str(id(source))
            if key not in collected:
                collected[key] = source
                order.append(key)
            elif light_channel_geometry(collected[key])[0] is None and light_channel_geometry(source)[0] is not None:
                collected[key] = source
    return [collected[key] for key in order]


def build_component_pass_index(components):
    indexed = {
        'components': [],
        'by_name': {},
        'rig_components': [],
        'slot_components': [],
        'mesh_components': [],
        'transform_animator_components': [],
    }
    for component in components or ():
        if type(component) is not dict:
            continue
        indexed['components'].append(component)
        name = component_name(component)
        if name:
            indexed['by_name'][name] = component
        if depot_path_value(component, 'rig'):
            indexed['rig_components'].append(component)
        if isinstance(component.get('slots'), list):
            indexed['slot_components'].append(component)
        if 'mesh' in component or 'graphicsMesh' in component:
            indexed['mesh_components'].append(component)
        if component.get('$type') == 'gameTransformAnimatorComponent':
            indexed['transform_animator_components'].append(component)
    return indexed


def create_light_channel_mesh(component, shape_lookup, filepath):
    vertices, indices = light_channel_geometry(component, shape_lookup)
    if not vertices or not indices:
        return None
    name = component_name(component) or 'LightChannel'
    mesh_data = bpy.data.meshes.new(name)
    verts = [(v.get('X', 0), v.get('Y', 0), v.get('Z', 0)) for v in vertices]
    if isinstance(indices[0], (list, tuple)):
        faces = [list(face[:3]) for face in indices if len(face) >= 3]
    else:
        faces = [indices[i:i + 3] for i in range(0, len(indices), 3) if len(indices[i:i + 3]) == 3]
    mesh_data.from_pydata(verts, [], faces)
    mesh_data.update()

    obj = bpy.data.objects.new(name, mesh_data)
    obj.display_type = 'WIRE'
    obj.color = (0.005, 0.79105, 1, 1)
    obj.show_wire = True
    obj.show_in_front = True
    obj.display.show_shadows = False
    obj.rotation_mode = 'QUATERNION'
    obj['ntype'] = 'entLightChannelComponent'
    obj['name'] = name
    obj['entJSON'] = filepath
    return obj


class ComponentHandleLookup:
    def __init__(self, default_lookup=None):
        self.default_lookup = default_lookup or {}
        self.by_component_id = {}

    def set_component_lookup(self, component, lookup):
        if type(component) is dict:
            self.by_component_id[id(component)] = lookup or {}

    def get_for_component(self, component, handle_id):
        lookup = self.by_component_id.get(id(component), self.default_lookup)
        return lookup.get(handle_id)


def build_anim_impl_lookup(chunks):
    lookup = {}
    for chunk in chunks or ():
        if not isinstance(chunk, dict) or chunk.get('$type') != 'gameTransformAnimatorComponent':
            continue
        try:
            impl = chunk['animations'][0]['timeline']['items'][0]['impl']
        except (KeyError, IndexError, TypeError):
            continue
        if 'HandleId' in impl:
            lookup[int(impl['HandleId'])] = impl.get('Data')
    return lookup


def transform_animator_info(component, anim_impl_lookup):
    if not isinstance(component, dict) or component.get('$type') != 'gameTransformAnimatorComponent':
        return None
    try:
        animation = (component.get('animations') or [])[0]
        if animation.get('$type') != 'gameTransformAnimationDefinition':
            return None
        item = animation['timeline']['items'][0]
        impl_ref = int(item['impl']['HandleRefId'])
        chunk_anim = anim_impl_lookup.get(impl_ref)
    except (KeyError, IndexError, TypeError, ValueError):
        return None

    if not isinstance(chunk_anim, dict) or chunk_anim.get('$type') != 'gameTransformAnimation_RotateOnAxis':
        return None

    axis_name = chunk_anim.get('axis') or 'X'
    direction = -1 if chunk_anim.get('reverseDirection', False) else 1
    return {
        'axis_name': axis_name,
        'axis_no': _AXIS_INDEX.get(axis_name, 0),
        'duration': item.get('duration', 0),
        'delta_radians': math.radians(chunk_anim.get('numberOfFullRotations', 0) * direction * 360),
    }


def build_transform_animator_lookup(components, anim_impl_lookup):
    lookup = {}
    for component in components or []:
        info = transform_animator_info(component, anim_impl_lookup)
        name = component_name(component)
        if name and info is not None:
            lookup[name] = info
    return lookup


def ensure_transform_animator_empty(ent_coll, name, info):
    target = create_axes(ent_coll=ent_coll, name=name)
    if info is None:
        return target
    target['transformAnimatorAxis'] = info['axis_no']
    target['transformAnimatorAxisName'] = info['axis_name']
    if not target.get('transformAnimatorInitialized'):
        set_rotation_axis_cycles(target, info['axis_no'], info['delta_radians'], info['duration'] * 30)
        target['transformAnimatorInitialized'] = True
    return target


def component_transform_animator_info(component, parent_transform_lookup, transform_animator_lookup):
    binding = parent_transform_data(component, parent_transform_lookup)
    bind_name = cname_value(binding.get('bindName')) if isinstance(binding, dict) else ''
    if not bind_name:
        return '', None
    return bind_name, transform_animator_lookup.get(bind_name)


def add_rotation_axis_driver(obj, target, axis_no):
    if obj is None or target is None or axis_no is None:
        return None
    if getattr(obj, 'rotation_mode', 'XYZ') == 'QUATERNION':
        obj.rotation_mode = 'XYZ'
    base_value = obj.rotation_euler[axis_no]
    try:
        obj.driver_remove('rotation_euler', axis_no)
    except (TypeError, RuntimeError):
        pass
    fcurve = obj.driver_add('rotation_euler', axis_no)
    driver = fcurve.driver
    driver.type = 'SCRIPTED'
    driver.expression = f'{base_value:.17g} + animator_axis'
    var = driver.variables.new()
    var.name = 'animator_axis'
    var.type = 'SINGLE_PROP'
    target_ref = var.targets[0]
    target_ref.id = target
    target_ref.data_path = f'rotation_euler[{axis_no}]'
    return driver


def build_slot_lookup(vehicle_slots):
    lookup = {}
    for slot in vehicle_slots or []:
        name = cname_value(slot.get('slotName'))
        if name:
            lookup[name] = slot
    return lookup


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
    if type(rig_j) is not dict:
        return {}
    key = id(rig_j)
    cached = _RIG_BONE_INDEX_CACHE.get(key)
    if cached is None:
        cached = build_rig_bone_index(rig_j)
        _RIG_BONE_INDEX_CACHE[key] = cached
    return cached


def _rig_json_bone_matrix_for_index(rig_j, index, matrices, resolving=None):
    if type(rig_j) is not dict or index is None or index < 0:
        return Matrix.Identity(4)
    index_key = ('index', index)
    cached = matrices.get(index_key)
    if cached is not None:
        return cached

    resolving = resolving or set()
    if index in resolving:
        return Matrix.Identity(4)
    resolving.add(index)

    # aPoseMS is already model-space. boneTransforms/aPoseLS are local-to-parent
    # in vehicle rigs, so they must be accumulated through boneParentIndexes.
    apose_ms = rig_j.get('aPoseMS')
    if type(apose_ms) is list and index < len(apose_ms):
        matrix = transform_matrix(apose_ms[index])
    else:
        transforms = rig_j.get('boneTransforms')
        if not (type(transforms) is list and index < len(transforms)):
            transforms = rig_j.get('aPoseLS')
        if type(transforms) is list and index < len(transforms):
            local_matrix = transform_matrix(transforms[index])
            parents = rig_j.get('boneParentIndexes')
            parent_index = parents[index] if type(parents) is list and index < len(parents) else -1
            parent_matrix = _rig_json_bone_matrix_for_index(rig_j, parent_index, matrices, resolving) if parent_index is not None and parent_index >= 0 else Matrix.Identity(4)
            matrix = parent_matrix @ local_matrix
        else:
            matrix = Matrix.Identity(4)

    resolving.remove(index)
    matrices[index_key] = matrix
    return matrix


def rig_json_bone_matrix(rig_j, bone_name, rig_bone_index=None):
    if type(rig_j) is not dict or not bone_name:
        return Matrix.Identity(4)
    matrices = _RIG_BONE_MATRIX_CACHE.setdefault(id(rig_j), {})
    cached = matrices.get(bone_name)
    if cached is not None:
        return cached
    index = (rig_bone_index or rig_bone_index_for(rig_j)).get(bone_name)
    matrix = _rig_json_bone_matrix_for_index(rig_j, index, matrices) if index is not None else Matrix.Identity(4)
    matrices[bone_name] = matrix
    return matrix


def build_slot_owner_binding_maps(slot_components, parent_transform_lookup, rig_json_by_component_name, rig_component_names):
    rig_jsons = {}
    rig_owner_names = {}
    for component in slot_components or ():
        owner_name = component_name(component)
        if not owner_name:
            continue
        binding = parent_transform_data(component, parent_transform_lookup)
        bind_name = cname_value(binding.get('bindName')) if type(binding) is dict else ''
        if bind_name in rig_json_by_component_name:
            rig_jsons[owner_name] = rig_json_by_component_name[bind_name]
        if bind_name in rig_component_names:
            rig_owner_names[owner_name] = bind_name
    return rig_jsons, rig_owner_names


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


def transform_field(transform, keys):
    if type(transform) is not dict:
        return {}
    for key in keys:
        value = transform.get(key)
        if type(value) is dict:
            return value
    return {}


def transform_position(transform, keys=POSITION_KEYS):
    data = transform_field(transform, keys)
    if not data:
        return Vector((0, 0, 0))
    x = data.get('x')
    y = data.get('y')
    z = data.get('z')
    return Vector((
        x.get('Bits', 0) / FIXED_POINT_DIVISOR if type(x) is dict else data.get('X', 0),
        y.get('Bits', 0) / FIXED_POINT_DIVISOR if type(y) is dict else data.get('Y', 0),
        z.get('Bits', 0) / FIXED_POINT_DIVISOR if type(z) is dict else data.get('Z', 0),
    ))


def transform_scale(transform, visual_scale=None):
    scale = transform.get('Scale') or transform.get('scale') if type(transform) is dict else None
    if type(scale) is not dict and type(visual_scale) is dict:
        scale = visual_scale
    if type(scale) is not dict:
        return Vector((1, 1, 1))
    return Vector((scale.get('X', 1), scale.get('Y', 1), scale.get('Z', 1)))


def transform_matrix(transform, pos_keys=POSITION_KEYS, rot_keys=ROTATION_KEYS, scale=None, visual_scale=None):
    if type(transform) is not dict:
        return Matrix.Identity(4)
    return Matrix.LocRotScale(
        transform_position(transform, pos_keys),
        red_quaternion(transform_field(transform, rot_keys)),
        scale if scale is not None else transform_scale(transform, visual_scale),
    )


def resolve_handle_data(component, lookup, key):
    data = component.get(key) if type(component) is dict else None
    if type(data) is not dict:
        return None
    if type(data.get('Data')) is dict:
        return data.get('Data')

    handle_id = data.get('HandleRefId')
    if handle_id is None:
        return None

    if hasattr(lookup, 'get_for_component'):
        referenced = lookup.get_for_component(component, handle_id)
    else:
        referenced = lookup.get(handle_id) if lookup else None
    return referenced.get('Data') if type(referenced) is dict else None


def parent_transform_data(component, parent_transform_lookup):
    return resolve_handle_data(component, parent_transform_lookup, 'parentTransform')


def skinning_binding_data(component, skinning_lookup=None):
    resolved = resolve_handle_data(component, skinning_lookup, 'skinning')
    if resolved is not None:
        return resolved
    skinning = component.get('skinning') if type(component) is dict else None
    return skinning if isinstance(skinning, dict) and 'Data' not in skinning else None


def skinning_bind_name(component, skinning_lookup=None):
    data = skinning_binding_data(component, skinning_lookup)
    return cname_value(data.get('bindName')) if isinstance(data, dict) else ''


def component_uses_skinning(component, skinning_lookup=None):
    bind_name = skinning_bind_name(component, skinning_lookup)
    return bool(bind_name and bind_name != 'None')


def imported_armatures_from_selection():
    selected = [obj for obj in bpy.context.selected_objects if getattr(obj, 'type', None) == ARMATURE_TYPE]
    if selected:
        return selected
    active = bpy.context.view_layer.objects.active
    return [active] if getattr(active, 'type', None) == ARMATURE_TYPE else []


def load_anim_rig(with_materials, anim_path, rig_path='', ent_name=''):
    if not anim_path:
        return None
    bpy.ops.io_scene_gltf.cp77(with_materials, filepath=anim_path, scripting=True)
    arms = imported_armatures_from_selection()
    if not arms:
        print('anim rig import did not create an armature')
        return None
    rig = arms[0]
    cache_armature_bones(rig)
    rig['animset'] = anim_path
    if rig_path:
        rig['rig'] = rig_path
    if ent_name:
        rig['ent'] = ent_name + '.ent.json'
    print('anim rig loaded')
    return rig


def child_of_inverse_matrix(target, subtarget_name=''):
    target_matrix = target.matrix_world.copy()
    if armature_has_bone(target, subtarget_name):
        target_matrix = target.matrix_world @ target.pose.bones[subtarget_name].matrix
    try:
        return target_matrix.inverted()
    except Exception:
        return Matrix.Identity(4)


def root_constraint_bone_name(rig):
    if getattr(rig, 'type', None) != ARMATURE_TYPE:
        return ''
    for bone_name in ('root', 'Root', 'base', 'Base'):
        if armature_has_bone(rig, bone_name):
            return bone_name
    return ''


def vector_is_zero(value, eps=1e-6):
    return abs(value.x) <= eps and abs(value.y) <= eps and abs(value.z) <= eps


def quaternion_is_identity(value, eps=1e-6):
    return abs(value.x) <= eps and abs(value.y) <= eps and abs(value.z) <= eps and abs(value.w - 1.0) <= eps


def is_root_like_bone_name(name):
    return (name or '').lower() in {'root', 'base', 'trajectory'}


def transform_has_authored_local_basis(transform):
    if type(transform) is not dict:
        return False
    return (
        not vector_is_zero(transform_position(transform, ('Position',)))
        or not quaternion_is_identity(red_quaternion(transform.get('Orientation')))
    )


def rig_parent_bone_name(rig, rig_j, bone_name):
    if not bone_name:
        return ''
    if getattr(rig, 'type', None) == ARMATURE_TYPE:
        bone = rig.data.bones.get(bone_name) if getattr(rig, 'data', None) else None
        if bone is not None and bone.parent is not None:
            return bone.parent.name
    if type(rig_j) is not dict:
        return ''
    index = rig_bone_index_for(rig_j).get(bone_name)
    parents = rig_j.get('boneParentIndexes')
    names = rig_j.get('boneNames')
    if index is None or type(parents) is not list or type(names) is not list or index >= len(parents):
        return ''
    parent_index = parents[index]
    if parent_index is None or parent_index < 0 or parent_index >= len(names):
        return ''
    return cname_value(names[parent_index])


def root_inverse_hard_slot_workflow(component, transform_resolver, rig):
    if type(component) is not dict:
        return None
    local_transform = component.get('localTransform', {})
    if not transform_has_authored_local_basis(local_transform):
        return None
    binding = transform_resolver._binding_data(component)
    if type(binding) is not dict:
        return None
    bind_name = cname_value(binding.get('bindName'))
    slot_name = cname_value(binding.get('slotName'))
    if not bind_name or not slot_name or slot_name == 'None':
        return None
    if transform_resolver._get_binding_target(bind_name) != 'slot':
        return None
    slot = transform_resolver._slot(bind_name, slot_name)
    if type(slot) is not dict:
        return None
    bone_name = cname_value(slot.get('boneName'), slot_name)
    if is_root_like_bone_name(bone_name) or is_root_like_bone_name(slot_name):
        return None
    if bone_name != slot_name or not armature_has_bone(rig, bone_name):
        return None
    if not vector_is_zero(transform_position(slot, ('relativePosition',))):
        return None
    if not quaternion_is_identity(red_quaternion(slot.get('relativeRotation'))):
        return None
    root_bone = root_constraint_bone_name(rig)
    if not root_bone:
        return None
    local_matrix = transform_matrix(local_transform, visual_scale=component.get('visualScale'))
    return local_matrix, bone_name, slot_name, root_bone


def matching_child_of_constraint(obj, target, subtarget):
    for constraint in getattr(obj, 'constraints', ()):
        if constraint.type == 'CHILD_OF' and constraint.target == target and constraint.subtarget == subtarget:
            return constraint
    return None


def configure_child_of_constraint(obj, target, subtarget, inverse_matrix):
    constraints = obj.constraints
    constraint = matching_child_of_constraint(obj, target, subtarget)
    if constraint is None:
        constraint = constraints.get('Child Of')
        if constraint is None or constraint.type != 'CHILD_OF':
            constraint = constraints.new(type='CHILD_OF')
            constraint.name = 'Child Of'
    constraint.target = target
    constraint.subtarget = subtarget
    constraint.inverse_matrix = inverse_matrix
    return constraint


def configure_root_inverse_child_of(obj, rig, root_bone, target_bone):
    return configure_child_of_constraint(obj, rig, target_bone, child_of_inverse_matrix(rig, root_bone))


def mesh_armature_modifier(obj):
    for modifier in getattr(obj, 'modifiers', []):
        if modifier.type == 'ARMATURE' and getattr(modifier, 'object', None) is not None:
            return modifier
    return None


def copied_armatures_from_objects(objects):
    object_ids = {id(obj) for obj in objects}
    armatures = []
    seen = set()
    for obj in objects:
        if getattr(obj, 'type', None) != 'MESH':
            continue
        modifier = mesh_armature_modifier(obj)
        armature = getattr(modifier, 'object', None) if modifier is not None else None
        if getattr(armature, 'type', None) != ARMATURE_TYPE:
            continue
        if id(armature) not in object_ids or id(armature) in seen:
            continue
        seen.add(id(armature))
        armatures.append(armature)
    return armatures


def mesh_vertex_group_names(objects):
    names = set()
    for obj in objects:
        if getattr(obj, 'type', None) == 'MESH':
            names.update(group.name for group in getattr(obj, 'vertex_groups', []))
    return names


def pose_bone_head_world(armature, bone_name):
    if getattr(armature, 'type', None) != ARMATURE_TYPE or not armature_has_bone(armature, bone_name):
        return None
    return armature.matrix_world @ armature.pose.bones[bone_name].head


def average_vector(values):
    values = tuple(value for value in values if value is not None)
    return sum(values, Vector((0, 0, 0))) / len(values) if values else None


def shared_deformation_bone_names(objects, source_armature, target_armature):
    shared = cache_armature_bones(source_armature) & cache_armature_bones(target_armature)
    if not shared:
        return []
    preferred = shared & mesh_vertex_group_names(objects)
    return sorted(preferred or shared)


def deformation_rig_centroid_translation_matrix(objects, rig):
    if getattr(rig, 'type', None) != ARMATURE_TYPE:
        return None, None, []
    best_armature = None
    best_bones = []
    for armature in copied_armatures_from_objects(objects):
        if armature == rig:
            continue
        bones = shared_deformation_bone_names(objects, armature, rig)
        if len(bones) > len(best_bones):
            best_armature = armature
            best_bones = bones
    if best_armature is None or not best_bones:
        return None, None, []
    source_centroid = average_vector(pose_bone_head_world(best_armature, bone_name) for bone_name in best_bones)
    target_centroid = average_vector(pose_bone_head_world(rig, bone_name) for bone_name in best_bones)
    if source_centroid is None or target_centroid is None:
        return None, None, []
    return Matrix.Translation(target_centroid - source_centroid), best_armature, best_bones

def is_skinned_overlay_component(component, meshpath=''):
    name = component_name(component).lower()
    path = (meshpath or depot_path_value(component, 'mesh', 'graphicsMesh')).lower()
    return 'decal' in name or 'decal' in path


def skinned_source_armature(objects):
    armatures = copied_armatures_from_objects(objects)
    return armatures[0] if armatures else None


def skinned_overlay_alignment_matrix(objects, resolved_matrix, anchors):
    source_armature = skinned_source_armature(objects)
    if source_armature is None or not anchors:
        return None, '', []

    source_groups = mesh_vertex_group_names(objects)
    source_bones = cache_armature_bones(source_armature)
    best = None
    for anchor in anchors:
        target_armature = anchor.get('armature')
        if not is_live_armature_object(target_armature):
            continue
        shared = source_bones & cache_armature_bones(target_armature)
        if not shared:
            continue
        anchor_groups = anchor.get('vertex_groups') or set()
        preferred = shared & source_groups & anchor_groups
        bones = sorted(preferred or (shared & source_groups) or shared)
        if not bones:
            continue
        source_centroid = average_vector(pose_bone_head_world(source_armature, bone_name) for bone_name in bones)
        target_centroid = average_vector(pose_bone_head_world(target_armature, bone_name) for bone_name in bones)
        if source_centroid is None or target_centroid is None:
            continue
        score = (len(preferred), len(shared & source_groups), len(shared))
        if best is None or score > best[0]:
            best = (score, target_centroid - (resolved_matrix @ source_centroid), anchor.get('component_name', ''), bones)

    if best is None:
        return None, '', []
    return Matrix.Translation(best[1]), best[2], best[3]



def is_live_armature_object(obj):
    if getattr(obj, 'type', None) != ARMATURE_TYPE:
        return False
    try:
        return bpy.data.objects.get(obj.name) is obj
    except ReferenceError:
        return False


def ensure_armature_from_rig_json(rig_json_path, component_name_value='', ent_name=''):
    if not rig_json_path:
        return None
    target = norm_path_key(rig_json_path)
    existing = _RIG_ARMATURE_OBJECT_CACHE.get(target)
    if is_live_armature_object(existing):
        cache_armature_bones(existing)
        return existing
    if existing is not None:
        _RIG_ARMATURE_OBJECT_CACHE.pop(target, None)

    expected_name = os.path.basename(rig_json_path).replace('.rig.json', '')
    direct = bpy.data.objects.get(expected_name)
    if getattr(direct, 'type', None) == ARMATURE_TYPE:
        cache_armature_bones(direct)
        _RIG_ARMATURE_OBJECT_CACHE[target] = direct
        return direct

    created = create_armature_from_data(rig_json_path, "T-Pose", False)
    armature = created if getattr(created, 'type', None) == ARMATURE_TYPE else None
    if armature is None and isinstance(created, (list, tuple)):
        armature = next((item for item in created if getattr(item, 'type', None) == ARMATURE_TYPE), None)
    if armature is None:
        selected = imported_armatures_from_selection()
        armature = selected[0] if selected else None

    if armature is not None:
        cache_armature_bones(armature)
        _RIG_ARMATURE_OBJECT_CACHE[target] = armature
        armature['rig'] = rig_json_path
        armature['source_rig_file'] = rig_json_path
        if component_name_value:
            armature['componentName'] = component_name_value
        if ent_name:
            armature['ent'] = ent_name + '.ent.json'
    return armature


def cache_armature_bones(armature):
    if not is_live_armature_object(armature) or not getattr(armature, 'pose', None):
        return set()
    cache_key = id(armature)
    bone_count = len(armature.pose.bones)
    cached = _ARMATURE_BONE_SET_CACHE.get(cache_key)
    if cached is not None and cached[0] is armature and cached[1] == bone_count:
        return cached[2]
    bone_set = set(armature.pose.bones.keys())
    _ARMATURE_BONE_SET_CACHE[cache_key] = (armature, bone_count, bone_set)
    return bone_set


def armature_has_bone(armature, bone_name):
    return bool(armature and bone_name and bone_name in cache_armature_bones(armature))


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
        slots = component.get('slots') if type(component) is dict else None
        name = component_name(component)
        if name and isinstance(slots, list):
            lookups[name] = build_slot_lookup(slots)
    return lookups


class EntityTransformResolver:
    def __init__(self, components, parent_transform_lookup, skinning_lookup=None, rig=None, rig_j=None, rig_bone_index=None, default_slot_lookup=None, slot_owner_rig_jsons=None, rig_json_by_component_name=None, armature_by_component_name=None, slot_owner_rig_owner_names=None, components_by_name=None, slot_component_lookups=None):
        self.components = components or []
        self.components_by_name = components_by_name if components_by_name is not None else build_component_lookup(self.components)
        self.parent_transform_lookup = parent_transform_lookup or {}
        self.skinning_lookup = skinning_lookup or {}
        self.slot_component_lookups = slot_component_lookups if slot_component_lookups is not None else build_slot_component_lookups(self.components)
        self.rig = rig
        self.rig_j = rig_j
        self.rig_bone_index = rig_bone_index or rig_bone_index_for(rig_j)
        self.slot_owner_rig_jsons = slot_owner_rig_jsons or {}
        self.rig_json_by_component_name = rig_json_by_component_name or {}
        self.armature_by_component_name = armature_by_component_name or {}
        self.slot_owner_rig_owner_names = slot_owner_rig_owner_names or {}
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
        self.slot_cache = {}
        self.binding_target_cache = {}
        self.slot_component_is_animated_child_cache = {}
        self.animated_base_slot_cache = {}
        self.slot_primary_bone_cache = {}
        self.rig_bone_translation_matrix_cache = {}
        self.rig_bone_yaw_matrix_cache = {}
        self.resolving = set()

    def _slot_owner_rig_json(self, slot_owner=None):
        if slot_owner and slot_owner in self.slot_owner_rig_jsons:
            return self.slot_owner_rig_jsons[slot_owner]
        return self.rig_j

    def _binding_data(self, component):
        key = id(component)
        binding = self.binding_cache.get(key, _UNSET)
        if binding is _UNSET:
            binding = parent_transform_data(component, self.parent_transform_lookup)
            self.binding_cache[key] = binding
        return binding

    def _local_matrix(self, component, transform=None, visual_scale=None):
        key = id(component)
        matrix = self.local_matrix_cache.get(key)
        if matrix is None:
            if transform is None or visual_scale is None:
                default_transform, default_scale = self._component_local_fields(component)
                transform = default_transform if transform is None else transform
                visual_scale = default_scale if visual_scale is None else visual_scale
            matrix = transform_matrix(transform, visual_scale=visual_scale)
            self.local_matrix_cache[key] = matrix
        return matrix

    def _component_local_fields(self, component):
        if type(component) is dict:
            return component.get('localTransform', {}), component.get('visualScale')
        return {}, None

    def _rig_json_index(self, rig_j):
        return rig_bone_index_for(rig_j)

    def _rig_json_has_bone(self, bone_name, rig_j=None):
        return bool(bone_name and bone_name in self._rig_json_index(rig_j))

    def _rig_json_for_bone(self, bone_name, slot_owner=None):
        cache_key = (bone_name, slot_owner)
        if cache_key in self.rig_json_for_bone_cache:
            return self.rig_json_for_bone_cache[cache_key]
        preferred = self._slot_owner_rig_json(slot_owner)
        result = preferred
        if not self._rig_json_has_bone(bone_name, preferred):
            for rig_json in self.rig_json_by_component_name.values():
                if rig_json is not preferred and self._rig_json_has_bone(bone_name, rig_json):
                    result = rig_json
                    break
        self.rig_json_for_bone_cache[cache_key] = result
        return result

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
        result = None
        owner_name = self._slot_owner_rig_owner_name(slot_owner)
        if owner_name:
            armature = self.armature_by_component_name.get(owner_name)
            if armature_has_bone(armature, bone_name):
                result = armature
        if result is None and armature_has_bone(self.rig, bone_name):
            result = self.rig
        if result is None:
            for armature in self.armature_by_component_name.values():
                if armature_has_bone(armature, bone_name):
                    result = armature
                    break
        self.armature_for_bone_cache[cache_key] = result
        return result

    def _pose_bone(self, bone_name, slot_owner=None):
        armature = self._armature_for_bone(bone_name, slot_owner)
        if armature is not None:
            return armature, armature.pose.bones[bone_name]
        return None, None

    def _rig_json_fallback_matrix(self, bone_name, slot_owner):
        rig_j = self._rig_json_for_bone(bone_name, slot_owner)
        if self._rig_json_has_bone(bone_name, rig_j):
            return rig_json_bone_matrix(rig_j, bone_name, self._rig_json_index(rig_j))
        return None

    def bone_matrix(self, bone_name, slot_owner=None):
        cache_key = (bone_name, slot_owner)
        cached = self.bone_matrix_cache.get(cache_key)
        if cached is not None:
            return cached
        armature, pose_bone = self._pose_bone(bone_name, slot_owner)
        if pose_bone is not None:
            matrix = armature.matrix_world @ pose_bone.matrix
        else:
            fallback = self._rig_json_fallback_matrix(bone_name, slot_owner)
            matrix = fallback if fallback is not None else Matrix.Identity(4)
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
            result = (self.bone_matrix(bone_name, slot_owner) @ transform_matrix(slot), bone_name, slot_name)
        self.slot_matrix_cache[cache_key] = result
        return result

    def _get_binding_target(self, bind_name):
        cached = self.binding_target_cache.get(bind_name)
        if cached is not None:
            return cached
        if not bind_name or bind_name == 'None':
            target = 'none'
        elif bind_name in ('vehicle_slots', 'slots'):
            target = 'slot'
        elif bind_name == 'deformation_rig':
            target = 'deformation_rig'
        elif bind_name in self.components_by_name:
            target = 'component'
        elif armature_has_bone(self.rig, bind_name):
            target = 'bone'
        else:
            target = 'unresolved'
        self.binding_target_cache[bind_name] = target
        return target

    def _resolve_parent_target(self, bind_name, slot_name, is_hard=False, component=None):
        target_type = self._get_binding_target(bind_name)
        if target_type == 'none':
            return Matrix.Identity(4), bind_name, slot_name, 'none'

        if target_type == 'deformation_rig':
            base = self.rig.matrix_world.copy() if self.rig else Matrix.Identity(4)
            return base, bind_name, slot_name, 'deformation_rig'

        if target_type == 'bone':
            if is_hard and component is not None:
                local_transform, visual_scale = self._component_local_fields(component)
                matrix = self._hard_bone_slot_matrix(bind_name, bind_name, slot_name, local_transform, visual_scale)
            else:
                matrix = self.bone_matrix(bind_name)
            return matrix, bind_name, slot_name, 'bone'

        if target_type == 'slot':
            if is_hard and component is not None:
                bone_name = self._slot_bone_name(bind_name, slot_name)
                local_transform, visual_scale = self._component_local_fields(component)
                matrix = self._hard_bone_slot_matrix(bone_name, bind_name, slot_name, local_transform, visual_scale)
                return matrix, bone_name, slot_name, 'slot'
            matrix, bone_name, resolved_slot = self.resolve_slot_matrix(bind_name, slot_name)
            return matrix, bone_name, resolved_slot, 'slot'

        if target_type == 'component':
            bound_component = self.components_by_name[bind_name]
            if not is_hard:
                if component_uses_skinning(component, self.skinning_lookup) and self._component_is_rig_owner(bound_component):
                    base = self.rig.matrix_world.copy() if self.rig else Matrix.Identity(4)
                    return base, bind_name, slot_name, 'skinning_root'
                parent_matrix, _, _, _ = self.resolve_component_matrix(bound_component)
                if slot_name and slot_name != 'None':
                    slot_lookup = self.slot_component_lookups.get(bind_name)
                    if slot_lookup and slot_name in slot_lookup:
                        return parent_matrix @ transform_matrix(slot_lookup[slot_name]), bind_name, slot_name, 'component_slot'
                return parent_matrix, bind_name, slot_name, 'component'

            parent_matrix, parent_bind, parent_slot, parent_type = self.resolve_hard_component_matrix(bound_component)
            if slot_name and slot_name != 'None':
                slot = self._slot(bind_name, slot_name)
                if slot:
                    bound_is_animated_child = self._slot_component_is_animated_child(bound_component)
                    skip_animated_base_slot = bind_name == 'base' and slot_name == 'base' and bound_is_animated_child
                    animated_parent_name = self._binding_name(bound_component) if bound_is_animated_child else ''
                    animated_base_slot = self._animated_base_slot(animated_parent_name) if animated_parent_name else None
                    bone_name = cname_value(slot.get('boneName'), slot_name)
                    if animated_parent_name and type(animated_base_slot) is not dict:
                        animated_parent = self.components_by_name.get(animated_parent_name)
                        animated_parent_matrix = Matrix.Identity(4)
                        if animated_parent is not None:
                            animated_parent_matrix, _, _, _ = self.resolve_hard_component_matrix(animated_parent)
                        parent_matrix = (
                            animated_parent_matrix
                            @ self._rig_bone_translation_matrix(bone_name)
                            @ self._rig_bone_yaw_matrix(bone_name)
                            @ Matrix.Translation(transform_position(slot, ('relativePosition',)))
                        )
                        parent_bind = bone_name or parent_bind or bind_name
                        parent_slot = slot_name
                        parent_type = 'slot'
                    elif not skip_animated_base_slot:
                        parent_matrix = parent_matrix @ transform_matrix(slot)
                        parent_type = 'component_slot'
            return parent_matrix, parent_bind or bind_name, parent_slot or slot_name, parent_type if parent_type != 'none' else 'component'

        return Matrix.Identity(4), bind_name, slot_name, 'unresolved'

    def resolve_binding(self, component):
        binding = self._binding_data(component)
        if type(binding) is not dict:
            return Matrix.Identity(4), '', '', 'none'
        bind_name = cname_value(binding.get('bindName'))
        slot_name = cname_value(binding.get('slotName'))
        return self._resolve_parent_target(bind_name, slot_name, is_hard=False, component=component)

    def resolve_component_matrix(self, component):
        key = ('component', id(component))
        if key in self.cache:
            return self.cache[key]
        if key in self.resolving:
            return Matrix.Identity(4), '', '', 'cycle'
        self.resolving.add(key)
        parent_matrix, bind_name, slot_name, binding_type = self.resolve_binding(component)
        matrix = parent_matrix @ self._local_matrix(component)
        result = (matrix, bind_name, slot_name, binding_type)
        self.cache[key] = result
        self.resolving.remove(key)
        return result

    def _bone_rotation(self, bone_name, slot_owner=None):
        cache_key = (bone_name, slot_owner)
        cached = self.bone_rotation_cache.get(cache_key)
        if cached is not None:
            return cached
        # Hard slot placement must use the RED rig's model-space rest rotation.
        # Blender PoseBone channels are pose/local values and may include import-axis
        # basis effects; RED boneTransforms/aPoseLS are accumulated by rig_json_bone_matrix.
        fallback = self._rig_json_fallback_matrix(bone_name, slot_owner)
        if fallback is not None:
            rotation = fallback.to_quaternion()
        else:
            _, pose_bone = self._pose_bone(bone_name, slot_owner)
            rotation = pose_bone.rotation_quaternion.copy() if pose_bone is not None else Quaternion((1, 0, 0, 0))
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
            fallback = self._rig_json_fallback_matrix(bone_name, slot_owner)
            head = fallback.to_translation() if fallback is not None else Vector((0, 0, 0))
        self.bone_head_cache[cache_key] = head
        return head

    def _rig_space_bone_matrix(self, bone_name):
        cached = self.rig_space_bone_matrix_cache.get(bone_name)
        if cached is not None:
            return cached
        if type(self.rig_j) is dict and self._rig_json_has_bone(bone_name, self.rig_j):
            matrix = rig_json_bone_matrix(self.rig_j, bone_name, self.rig_bone_index)
        elif armature_has_bone(self.rig, bone_name):
            matrix = self.rig.pose.bones[bone_name].matrix.copy()
        else:
            matrix = Matrix.Identity(4)
        self.rig_space_bone_matrix_cache[bone_name] = matrix
        return matrix

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
        cached = self.rig_bone_translation_matrix_cache.get(bone_name)
        if cached is not None:
            return cached
        matrix = Matrix.Translation(self._rig_space_bone_matrix(bone_name).to_translation())
        self.rig_bone_translation_matrix_cache[bone_name] = matrix
        return matrix

    def _rig_bone_yaw_matrix(self, bone_name):
        if not bone_name or bone_name == 'None':
            return Matrix.Identity(4)
        cached = self.rig_bone_yaw_matrix_cache.get(bone_name)
        if cached is not None:
            return cached
        try:
            yaw = self._rig_space_bone_matrix(bone_name).to_euler().z
        except Exception:
            yaw = 0
        matrix = Matrix.Rotation(yaw, 4, 'Z')
        self.rig_bone_yaw_matrix_cache[bone_name] = matrix
        return matrix

    def _slot_lookup_for_owner(self, owner):
        lookup = self.slot_component_lookups.get(owner)
        if not lookup and owner in ('vehicle_slots', 'slots'):
            lookup = self.default_slot_lookup
        return lookup

    def _slot(self, owner, slot_name):
        cache_key = (owner, slot_name)
        if cache_key in self.slot_cache:
            return self.slot_cache[cache_key]
        lookup = self._slot_lookup_for_owner(owner)
        slot = lookup.get(slot_name) if lookup else None
        self.slot_cache[cache_key] = slot
        return slot

    def _slot_bone_name(self, owner, slot_name):
        slot = self._slot(owner, slot_name)
        if slot:
            return cname_value(slot.get('boneName'), slot_name)
        return slot_name or owner

    def _binding_name(self, component):
        binding = self._binding_data(component)
        return cname_value(binding.get('bindName')) if type(binding) is dict else ''

    def _component_is_rig_owner(self, component):
        return type(component) is dict and bool(depot_path_value(component, 'rig'))

    def _slot_component_is_animated_child(self, component):
        cache_key = id(component)
        cached = self.slot_component_is_animated_child_cache.get(cache_key)
        if cached is not None:
            return cached
        parent_name = self._binding_name(component)
        parent = self.components_by_name.get(parent_name)
        result = bool(parent_name and self._component_is_rig_owner(parent))
        self.slot_component_is_animated_child_cache[cache_key] = result
        return result

    def _animated_base_slot(self, animated_component_name):
        if animated_component_name in self.animated_base_slot_cache:
            return self.animated_base_slot_cache[animated_component_name]
        for slot_owner in self.components:
            if type(slot_owner) is not dict or slot_owner.get('$type') != 'entSlotComponent':
                continue
            if self._binding_name(slot_owner) != animated_component_name:
                continue
            slots = slot_owner.get('slots')
            if type(slots) is not list:
                continue
            for slot in slots:
                slot_name = cname_value(slot.get('slotName'))
                bone_name = cname_value(slot.get('boneName'))
                if slot_name == 'base' or bone_name == 'base':
                    self.animated_base_slot_cache[animated_component_name] = slot
                    return slot
        self.animated_base_slot_cache[animated_component_name] = None
        return None

    def _slot_component_primary_bone(self, component):
        cache_key = id(component)
        if cache_key in self.slot_primary_bone_cache:
            return self.slot_primary_bone_cache[cache_key]
        result = None
        slots = component.get('slots') if type(component) is dict else None
        if type(slots) is list:
            for slot in slots:
                bone_name = cname_value(slot.get('boneName'))
                if bone_name and bone_name != 'None':
                    result = bone_name
                    break
        self.slot_primary_bone_cache[cache_key] = result
        return result

    def _animated_slot_component_basis(self, component):
        parent_name = self._binding_name(component)
        if not parent_name:
            return None
        parent = self.components_by_name.get(parent_name)
        if not self._component_is_rig_owner(parent):
            return None
        if component_name(component) == 'base':
            return None
        base_slot = self._animated_base_slot(parent_name)
        if not isinstance(base_slot, dict):
            return None
        base_bone_name = cname_value(base_slot.get('boneName'))
        target_bone_name = self._slot_component_primary_bone(component)
        return transform_matrix(base_slot) @ self._rig_bone_translation_delta_matrix(base_bone_name or 'base', target_bone_name)

    def _slot_for_bone(self, owner, bone_name):
        slot = self._slot(owner, bone_name)
        if type(slot) is dict and cname_value(slot.get('boneName'), bone_name) == bone_name:
            return slot
        lookup = self._slot_lookup_for_owner(owner)
        if not lookup:
            return None
        for candidate in lookup.values():
            if type(candidate) is dict and cname_value(candidate.get('boneName')) == bone_name:
                return candidate
        return None

    def _parent_slot_relative_rotation(self, owner, bone_name, slot_rot):
        if quaternion_is_identity(slot_rot):
            return None
        parent_bone_name = rig_parent_bone_name(self.rig, self._rig_json_for_bone(bone_name, owner), bone_name)
        if not parent_bone_name:
            return None
        parent_slot = self._slot_for_bone(owner, parent_bone_name)
        if type(parent_slot) is not dict:
            return None
        return red_quaternion(parent_slot.get('relativeRotation')).inverted() @ slot_rot

    def _hard_bone_slot_matrix(self, bone_name, slot_owner, slot_name, local_transform, visual_scale=None):
        slot = self._slot(slot_owner, slot_name)
        slot_pos = Vector((0, 0, 0))
        slot_rot = Quaternion((1, 0, 0, 0))
        if type(slot) is dict:
            slot_pos = transform_position(slot, ('relativePosition',))
            slot_rot = red_quaternion(slot.get('relativeRotation'))

        local_pos = transform_position(local_transform, ('Position',))
        local_rot = red_quaternion(local_transform.get('Orientation'))
        parent_relative_rot = None
        if (
            type(slot) is dict
            and bone_name == slot_name
            and cname_value(slot.get('boneName'), slot_name) == slot_name
            and vector_is_zero(slot_pos)
            and not transform_has_authored_local_basis(local_transform)
        ):
            parent_relative_rot = self._parent_slot_relative_rotation(slot_owner, bone_name, slot_rot)

        if parent_relative_rot is None and bone_name and bone_name != 'Base':
            z_ang = self.bone_matrix(bone_name, slot_owner).to_euler().z
            local_pos = Matrix.Rotation(z_ang, 4, 'Z') @ local_pos

        rotation = (parent_relative_rot @ local_rot) if parent_relative_rot is not None else self._bone_rotation(bone_name, slot_owner) @ slot_rot @ local_rot
        scale = transform_scale(local_transform, visual_scale)
        return Matrix.LocRotScale(self._bone_head(bone_name, slot_owner) + slot_pos + local_pos, rotation, scale)

    def resolve_hard_component_matrix(self, component):
        key = ('hard', id(component))
        if key in self.cache:
            return self.cache[key]
        if key in self.resolving:
            return Matrix.Identity(4), '', '', 'cycle'
        self.resolving.add(key)

        local_transform, visual_scale = self._component_local_fields(component)
        animated_slot_basis = self._animated_slot_component_basis(component)
        if animated_slot_basis is not None:
            result = (animated_slot_basis @ self._local_matrix(component, local_transform, visual_scale), self._binding_name(component), '', 'animated_slot_component')
        else:
            binding = self._binding_data(component)
            if type(binding) is not dict:
                result = (self._local_matrix(component, local_transform, visual_scale), '', '', 'none')
            else:
                bind_name = cname_value(binding.get('bindName'))
                slot_name = cname_value(binding.get('slotName'))
                target_type = self._get_binding_target(bind_name)
                parent_matrix, res_bind, res_slot, res_type = self._resolve_parent_target(bind_name, slot_name, is_hard=True, component=component)

                if target_type in {'bone', 'slot'}:
                    result = (parent_matrix, res_bind, res_slot, res_type)
                else:
                    result = (parent_matrix @ self._local_matrix(component, local_transform, visual_scale), res_bind, res_slot, res_type)

        self.cache[key] = result
        self.resolving.remove(key)
        return result


def importEnt(with_materials, filepath='', appearances=None, exclude_meshes=None, include_collisions=False, include_phys=False,
              include_entCollider=False, inColl='', remap_depot=None, escaped_path=None, meshes=None, mesh_jsons=None, app_path=None, anim_files=None,
              rigjsons=None, generate_overrides=False):
    cp77_addon_prefs = bpy.context.preferences.addons['i_scene_cp77_gltf'].preferences
    if appearances is None:
        appearances = ['']
    elif isinstance(appearances, str):
        appearances = [appearances]
    else:
        appearances = list(appearances)
    excluded_meshes = {norm_path_key(mesh) for mesh in (exclude_meshes or []) if mesh}
    if not cp77_addon_prefs.non_verbose:
        print('\n-------------------- Importing Cyberpunk 2077 Entity --------------------')
    C = bpy.context
    coll_scene = C.scene.collection
    start_time = time.time()
    clear_transient_import_caches()

    path, after = split_source_raw_root(filepath)
    asset_index = DepotAssetIndex.cached(path, DEFAULT_ASSET_EXTENSIONS)

    error_messages = []
    entinitiatedcache = False
    if not JSONTool._use_cache:
        JSONTool.start_caching()
        entinitiatedcache = True

    rig = None
    Masters = None
    try:
        ent_name = os.path.basename(filepath)[:-9]
        if not cp77_addon_prefs.non_verbose:
            print(f"Importing appearance: {', '.join(appearances)} from entity: {ent_name}")
        parsed_ent = JSONTool.load_entity(filepath, error_messages) if filepath is not None else None
        if parsed_ent is None:
            return {'CANCELLED'}

        ent_apps = parsed_ent.appearances
        ent_components = parsed_ent.component_dicts
        ent_component_data = parsed_ent.component_data
        res = parsed_ent.resolved_dependencies
        ent_default = parsed_ent.default_appearance
        ent_applist = parsed_ent.appearance_names
        ent_app_index_by_name = parsed_ent.appearance_index_by_name
        ent_app_by_appearance = parsed_ent.appearances_by_appearance
        ent_app_by_name = parsed_ent.appearances_by_name

        if len(ent_applist) == 0:
            print(f"No appearances found in entity file {ent_name}. Imported objects may be incomplete or missing.")

        if ent_default == 'random':
            if ent_applist:
                ent_default = random.choice(ent_applist)
                print(f"Default appearance set to random choice: {ent_default}")
            else:
                print("No appearances available to select a random default from.")

        for appidx, app in enumerate(appearances):
            if app == 'default':
                if ent_default:
                    resolved_default = resolve_requested_appearance_name(app, ent_default, ent_apps, ent_app_by_appearance, ent_app_by_name)
                    print(f"Using default appearance {resolved_default} for entity {ent_name}.")
                    continue
                if ent_applist:
                    print(f"No default appearance specified in entity {ent_name}. Using first available appearance {ent_applist[0]}.")
                    ent_default = ent_applist[0]
                    continue
                print(f"No appearances specified in entity {ent_name}. Using root entities.")
                appearances[appidx] = 'BASE_COMPONENTS_ONLY'
                continue
            if not appearance_request_is_known(app, ent_default, ent_apps, ent_app_by_appearance, ent_app_by_name):
                print(f"Appearance {app} not found in entity {ent_name}. Available appearances: {', '.join(ent_applist)}")

        ent_rigs = []
        for component in parsed_ent.parsed_components:
            if component.rig_depot:
                print(f"Rig found in entity: {component.rig_depot}")
                ent_rigs.append(depot_to_local_path(path, component.rig_depot))
        ent_colliderComps = parsed_ent.collider_components
        ent_simpleCollComps = parsed_ent.simple_collider_components
        chassis_info = parsed_ent.components_by_name.get('Chassis', [])

        ent_rig_keys = {norm_path_key(rig_path) for rig_path in ent_rigs}

        if len(appearances[0]) == 0 or appearances[0].upper() == 'ALL':
            appearances = [app['appearanceName']['$value'] for app in ent_apps]
        if len(appearances) == 0:
            appearances.append('BASE_COMPONENTS_ONLY')

        initial_vehicle_slot_component = parsed_ent.vehicle_slot_component
        VS = [initial_vehicle_slot_component] if initial_vehicle_slot_component else []
        vehicle_slot_component_ids = {id(initial_vehicle_slot_component)} if initial_vehicle_slot_component else set()
        vehicle_slots = initial_vehicle_slot_component.get('slots') if initial_vehicle_slot_component else None
        vehicle_slot_lookup = build_slot_lookup(vehicle_slots)

        app_path = indexed_asset_files(asset_index, '.app.json', app_path)
        app_resource = app_path[0] if app_path else ''
        if ent_apps and not app_path:
            print('No Appearance file JSONs found in path, run the Ent export script first')

        mesh_files = indexed_asset_files(asset_index, '.glb', meshes)
        if len(mesh_files) == 0:
            print('No Meshes found in path, run the Ent export script first')

        mesh_jsons = indexed_asset_files(asset_index, '.mesh.json', mesh_jsons)
        anim_files = indexed_asset_files(asset_index, '.anims.glb', anim_files)

        if len(anim_files) == 0 or len(ent_rigs) == 0:
            print('no anim rig found')
        else:
            resolved_keys = set()
            for res_p in res:
                depot_value = cname_value(res_p.get('DepotPath')) if type(res_p) is dict else ''
                if depot_value:
                    resolved_keys.add(norm_path_key(depot_to_local_path(path, depot_value)))
            animsinres = [x for x in anim_files if norm_path_key(os.path.splitext(x)[0]) in resolved_keys]
            if len(animsinres) == 0:
                for anim in anim_files:
                    anim_json_path = asset_index.resolve_export(anim, '.anims.json')
                    if anim_json_path:
                        anm_j = JSONTool.jsonload(anim_json_path, error_messages)
                        if anm_j is not None:
                            rig_depot = anm_j.get('Data', {}).get('RootChunk', {}).get('rig', {}).get('DepotPath', {}).get('$value')
                            if rig_depot and norm_path_key(depot_to_local_path(path, rig_depot)) in ent_rig_keys:
                                animsinres.append(anim)

            if len(animsinres) > 0:
                anim_file_name = animsinres[0]
                rig_file_name = anim_file_name + '.rig.json' if anim_file_name.endswith('.glb') else ''
                rig = load_anim_rig(with_materials, anim_file_name, rig_file_name, ent_name)

        rigjsons = indexed_asset_files(asset_index, '.rig.json', rigjsons)
        rig_j = None
        if len(rigjsons) == 0 or len(ent_rigs) == 0:
            print('no rig json loaded')
        else:
            for entrig in (x for x in rigjsons if norm_path_key(x[:-5]) in ent_rig_keys):
                loaded_rig = load_root_chunk_json(entrig, error_messages)
                if loaded_rig is not None:
                    rig_j = loaded_rig
                    print('rig json loaded')
        rig_bone_index = rig_bone_index_for(rig_j)

        rig_json_by_component_name = {}
        rig_json_path_by_component_name = {}
        armature_by_component_name = {}
        rig_json_cache = {}
        rig_json_path_cache = {}

        def rig_json_path_for_depot(rig_depot):
            if not rig_depot:
                return ''
            if rig_depot not in rig_json_path_cache:
                rig_json_path_cache[rig_depot] = asset_index.resolve_export(rig_depot, '.rig.json') or ''
            return rig_json_path_cache[rig_depot]

        def rig_json_for_depot(rig_depot):
            if not rig_depot:
                return None
            if rig_depot in rig_json_cache:
                return rig_json_cache[rig_depot]
            rig_json_path = rig_json_path_for_depot(rig_depot)
            rig_root = load_root_chunk_json(rig_json_path, error_messages) if rig_json_path else None
            rig_json_cache[rig_depot] = rig_root
            return rig_root

        if not mesh_files or (not app_path and len(ent_components) < 1):
            print("You need to export the meshes and convert app and ent to json")

        else:
            Masters = coll_scene.children.get("MasterInstances")
            if Masters is None:
                Masters = bpy.data.collections.new("MasterInstances")
                coll_scene.children.link(Masters)

            # Master collection must stay visible during import or entity positioning breaks.
            Masters.hide_viewport = False

            mesh_entries = {}
            app_comps = {}
            ent_chunks = {}
            parsed_app_cache = {}
            app_lookup = {}
            app_bundle_lookup = {}
            app_resource_lookup = {}
            display_app_names = {}
            component_mesh_info_cache = {}
            ent_component_ids = parsed_ent.component_ids
            ent_component_data_ids = parsed_ent.component_data_ids
            ent_parent_transform_lookup = parsed_ent.parent_transform_lookup
            ent_skinning_lookup = parsed_ent.skinning_lookup
            ent_shape_lookup = parsed_ent.shape_lookup
            base_components_by_id = parsed_ent.components_by_id
            base_components_by_name = parsed_ent.components_by_name
            base_slot_component_lookups = parsed_ent.slot_component_lookups

            def component_mesh_info(component):
                cache_key = id(component)
                cached = component_mesh_info_cache.get(cache_key)
                if cached is not None:
                    return cached
                depot_path = depot_path_value(component, 'mesh', 'graphicsMesh')
                if not depot_path:
                    cached = ('', '', '', '', True)
                else:
                    meshpath = asset_index.resolve_export(depot_path, ('.glb', '.physicalscene.glb', '.w2mesh.glb'))
                    meshname = os.path.basename(depot_path.replace('\\', os.sep))
                    meshapp = cname_value(component.get('meshAppearance'), 'default')
                    cached = (depot_path, meshname, meshpath, meshapp, is_component_enabled(component))
                component_mesh_info_cache[cache_key] = cached
                return cached

            master_group_objects_cache = {}

            def master_group_objects(group):
                cache_key = id(group)
                cached = master_group_objects_cache.get(cache_key)
                if cached is None:
                    cached = tuple(group.all_objects)
                    master_group_objects_cache[cache_key] = cached
                return cached

            def store_for_names(mapping, value, requested, resolved):
                mapping[requested] = value
                if resolved != requested:
                    mapping[resolved] = value

            for requested_app_name in appearances:
                app_name = resolve_requested_appearance_name(requested_app_name, ent_default, ent_apps, ent_app_by_appearance, ent_app_by_name)
                display_app_names[requested_app_name] = app_name
                app_comps[requested_app_name] = []
                chunks = None
                if len(ent_apps) == 0 and ent_component_data:
                    chunks = ent_component_data
                elif len(ent_apps) > 0:
                    ent_app_idx, app_name = resolve_ent_app(app_name, ent_apps, ent_app_by_appearance, ent_app_by_name, ent_default)
                    app_lookup[requested_app_name] = app_name

                    app_file = ent_apps[ent_app_idx]['appearanceResource']['DepotPath']['$value']
                    appfilepath = asset_index.resolve_export(app_file, '.app.json')
                    store_for_names(app_resource_lookup, appfilepath or app_file, requested_app_name, app_name)
                    if not appfilepath:
                        print('app file not found -', depot_to_local_path(path, app_file) + '.json')
                    else:
                        parsed_app = parsed_app_cache.get(appfilepath)
                        if parsed_app is None:
                            parsed_app = JSONTool.load_app(appfilepath, error_messages)
                            parsed_app_cache[appfilepath] = parsed_app
                        if parsed_app is not None:
                            app_idx = parsed_app.appearances_by_name.get(app_name, 0)
                            parsed_app_name = app_name
                            if app_name in parsed_app.appearances_by_name:
                                print('appearance matched, id = ', app_idx)
                            elif parsed_app.appearance_names:
                                parsed_app_name = parsed_app.appearance_names[app_idx]
                            app_components = parsed_app.components_by_appearance_name.get(parsed_app_name, [])
                            if app_components:
                                store_for_names(app_comps, ent_components + app_components, requested_app_name, app_name)
                            chunks = parsed_app.chunks_by_appearance_name.get(parsed_app_name)
                            store_for_names(app_bundle_lookup, (parsed_app, parsed_app_name), requested_app_name, app_name)
                            if chunks:
                                store_for_names(ent_chunks, chunks, requested_app_name, app_name)
                                print('Chunks found')

                if len(app_comps[requested_app_name]) == 0:
                    print('falling back to rootchunk components...')
                    store_for_names(app_comps, ent_components, requested_app_name, app_name)
                if chunks is not None and requested_app_name not in ent_chunks:
                    ent_chunks[requested_app_name] = chunks
                for c in app_comps[requested_app_name]:
                    depot_path, meshname, meshpath, meshApp, _ = component_mesh_info(c)
                    if depot_path and meshname and meshpath and not is_excluded_mesh(depot_path, meshpath, meshname, excluded_meshes):
                        mesh_key = depot_to_local_path(path, depot_path)
                        entry = mesh_entries.get(mesh_key)
                        if entry is None:
                            mesh_entries[mesh_key] = {'appearances': [meshApp], 'sector': 'ALL', 'meshpath': meshpath}
                        else:
                            entry['appearances'].append(meshApp)
                            if meshpath and not entry.get('meshpath'):
                                entry['meshpath'] = meshpath

            meshes_w_apps = {}
            for m in mesh_entries:
                add_to_list(m, mesh_entries, meshes_w_apps)

            meshes_from_mesheswapps(meshes_w_apps, path, from_mesh_no=0, to_mesh_no=10000000, with_mats=with_materials, glbs=mesh_entries, mesh_jsons=mesh_jsons,
                                    Masters=Masters, generate_overrides=generate_overrides)

            for x, requested_app_name in enumerate(appearances):
                app_name = display_app_names.get(requested_app_name, requested_app_name)
                print(f"\nImporting appearance {x+1} of {len(appearances)}: {app_name}")
                app_start_time = time.time()
                ent_coll = bpy.data.collections.new(ent_name + '_' + app_name)
                app_name = app_lookup.get(requested_app_name, app_name)
                if inColl and inColl in coll_scene.children:
                    bpy.data.collections.get(inColl).children.link(ent_coll)
                else:
                    coll_scene.children.link(ent_coll)
                ent_coll['depotPath'] = after
                app_bundle = app_bundle_lookup.get(requested_app_name) or app_bundle_lookup.get(app_name)
                chunks = ent_chunks.get(requested_app_name) or ent_chunks.get(app_name) or ent_component_data

                current_app_resource = app_resource_lookup.get(requested_app_name) or app_resource_lookup.get(app_name) or app_resource
                ent_coll['appearanceName'] = app_name
                ent_coll['appearanceIndex'] = ent_app_index_by_name.get(app_name, 0)
                if current_app_resource:
                    ent_coll['appResource'] = current_app_resource

                comps = app_comps.get(requested_app_name) or app_comps.get(app_name) or ent_components
                appearance_index = build_component_pass_index(comps)
                transform_components_by_id = dict(base_components_by_id)
                for comp in appearance_index['components']:
                    transform_components_by_id[id(comp)] = comp
                transform_components = list(transform_components_by_id.values())
                transform_index = build_component_pass_index(transform_components)
                if app_bundle:
                    parsed_app, parsed_app_name = app_bundle
                    app_parent_transform_lookup = parsed_app.parent_transform_lookup_by_appearance_name.get(parsed_app_name, {})
                    app_skinning_lookup = parsed_app.skinning_lookup_by_appearance_name.get(parsed_app_name, {})
                    app_shape_lookup = parsed_app.shape_lookup_by_appearance_name.get(parsed_app_name, {})
                    app_light_channels = parsed_app.light_channels_by_appearance_name.get(parsed_app_name, [])
                else:
                    app_parent_transform_lookup = build_chunk_lookup(chunks, 'parentTransform')
                    app_skinning_lookup = build_chunk_lookup(chunks, 'skinning')
                    app_shape_lookup = build_chunk_lookup(chunks, 'shape')
                    app_light_channels = []
                parent_transform_lookup = ComponentHandleLookup(app_parent_transform_lookup)
                skinning_lookup = ComponentHandleLookup(app_skinning_lookup)
                shape_lookup = ComponentHandleLookup(app_shape_lookup)
                set_parent_lookup = parent_transform_lookup.set_component_lookup
                set_skinning_lookup = skinning_lookup.set_component_lookup
                set_shape_lookup = shape_lookup.set_component_lookup
                for comp in transform_index['components']:
                    if id(comp) in ent_component_ids:
                        set_parent_lookup(comp, ent_parent_transform_lookup)
                        set_skinning_lookup(comp, ent_skinning_lookup)
                        set_shape_lookup(comp, ent_shape_lookup)
                for comp in transform_index['rig_components']:
                    rig_depot = depot_path_value(comp, 'rig')
                    rig_name = component_name(comp)
                    if rig_name:
                        if rig_name not in rig_json_by_component_name:
                            rig_json_by_component_name[rig_name] = rig_json_for_depot(rig_depot)
                        rig_json_path_by_component_name[rig_name] = rig_json_path_for_depot(rig_depot)
                rig_component_names = set(rig_json_by_component_name.keys())
                slot_owner_rig_jsons, slot_owner_rig_owner_names = build_slot_owner_binding_maps(
                    transform_index['slot_components'],
                    parent_transform_lookup,
                    rig_json_by_component_name,
                    rig_component_names,
                )
                anim_impl_lookup = build_anim_impl_lookup(chunks)
                transform_animator_lookup = build_transform_animator_lookup(transform_index['transform_animator_components'], anim_impl_lookup)

                if not rig:
                    for c in appearance_index['slot_components']:
                        if component_name(c) in ('vehicle_slots', 'slot', 'slots') and id(c) not in vehicle_slot_component_ids:
                            VS.append(c)
                            vehicle_slot_component_ids.add(id(c))
                    for c in appearance_index['rig_components']:
                        rig_depot = depot_path_value(c, 'rig')
                        rig_path = depot_to_local_path(path, rig_depot)
                        print(f"Rig found in app components: {rig_depot}")
                        if rig is None:
                            rig_json_path = asset_index.resolve_export(rig_depot, '.rig.json')
                            if rig_json_path:
                                loaded_rig = load_root_chunk_json(rig_json_path, error_messages)
                                if loaded_rig is not None:
                                    rig_j = loaded_rig
                                    rig_bone_index = rig_bone_index_for(rig_j)
                                    print('rig json loaded')
                            gameplay_anims = c.get('animations', {}).get('gameplay')
                            if gameplay_anims is not None and len(gameplay_anims) > 0:
                                anim_depot = gameplay_anims[0]['animSet']['DepotPath']['$value']
                                animpath = asset_index.resolve_export(anim_depot, '.anims.glb')
                                if animpath:
                                    rig = load_anim_rig(with_materials, animpath, rig_path, ent_name)
                        elif rig.get('rig') == rig_path:
                            print('using existing rig')
                        else:
                            print('another rig', rig.get('rig'), ' is already loaded ', rig_path)
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
                            rig_j = rig_json_by_component_name.get(rig_name, rig_j)
                            rig_bone_index = rig_bone_index_for(rig_j)
                else:
                    component_name_value = rig.get('componentName') if hasattr(rig, 'get') else None
                    if component_name_value and component_name_value not in armature_by_component_name:
                        cache_armature_bones(rig)
                        armature_by_component_name[component_name_value] = rig

                if not vehicle_slots:
                    if len(VS) > 0:
                        vehicle_slots = VS[0]['slots']
                        vehicle_slot_lookup = build_slot_lookup(vehicle_slots)

                light_channel_components = collect_light_channel_components(app_light_channels, chunks, comps, parsed_ent.light_channel_components, ent_components)
                for comp in light_channel_components:
                    if id(comp) in ent_component_ids or id(comp) in ent_component_data_ids:
                        set_parent_lookup(comp, ent_parent_transform_lookup)
                        set_skinning_lookup(comp, ent_skinning_lookup)
                        set_shape_lookup(comp, ent_shape_lookup)
                resolver_components_by_id = dict(transform_components_by_id)
                for comp in light_channel_components:
                    resolver_components_by_id[id(comp)] = comp
                resolver_components = list(resolver_components_by_id.values())
                resolver_index = build_component_pass_index(resolver_components)
                resolver_components_by_name = dict(base_components_by_name)
                resolver_components_by_name.update(resolver_index['by_name'])
                resolver_slot_component_lookups = dict(base_slot_component_lookups)
                for comp in resolver_index['slot_components']:
                    name = component_name(comp)
                    if name:
                        resolver_slot_component_lookups[name] = build_slot_lookup(comp.get('slots'))

                transform_resolver = EntityTransformResolver(
                    resolver_components,
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
                    components_by_name=resolver_components_by_name,
                    slot_component_lookups=resolver_slot_component_lookups,
                )

                skinned_alignment_anchors = []

                for c in appearance_index['transform_animator_components']:
                    comp_name = component_name(c)
                    try:
                        ensure_transform_animator_empty(ent_coll, comp_name, transform_animator_lookup.get(comp_name))
                    except Exception:
                        print('Failed on animator component ', comp_name)
                        print(traceback.format_exc())

                for c in appearance_index['mesh_components']:
                    comp_name = component_name(c)
                    depot_path, meshname, meshpath, meshApp, component_enabled = component_mesh_info(c)
                    if meshname and meshpath and not is_excluded_mesh(depot_path, meshpath, meshname, excluded_meshes):
                        new = None
                        hide_disabled = not component_enabled
                        try:
                            group, groupname = get_group(meshpath, meshApp, Masters)
                            if group:
                                new = bpy.data.collections.new(groupname)
                                copied_objects = []
                                object_copy_map = {}
                                link_object = new.objects.link
                                for old_obj in master_group_objects(group):
                                    obj = old_obj.copy()
                                    object_copy_map[old_obj] = obj
                                    copied_objects.append(obj)
                                    link_object(obj)
                                    obj['componentName'] = comp_name
                                    obj['sourcePath'] = meshpath
                                    obj['meshAppearance'] = meshApp
                                    obj['componentEnabled'] = component_enabled
                                    if current_app_resource:
                                        obj['appResource'] = current_app_resource
                                    obj['entAppearance'] = app_name
                                    if hide_disabled:
                                        obj.hide_viewport = True
                                        obj.hide_render = True
                                    if 'Armature' in obj.name:
                                        obj.hide_viewport = True
                                _remap_copied_object_references(copied_objects, object_copy_map)
                            else:
                                print('BREAK collection not found after import - ', meshname)
                            print('checking for collection - ', meshname)
                            if new is None:
                                print('collection not found after import - ', meshname)
                                continue
                            objs = copied_objects
                            component_is_skinned = component_uses_skinning(c, skinning_lookup)
                            if component_is_skinned:
                                resolved_matrix, bindname, slotname, binding_type = transform_resolver.resolve_component_matrix(c)
                            else:
                                resolved_matrix, bindname, slotname, binding_type = transform_resolver.resolve_hard_component_matrix(c)
                            if component_is_skinned and skinning_bind_name(c, skinning_lookup) == 'deformation_rig':
                                centroid_matrix, centroid_armature, centroid_bones = deformation_rig_centroid_translation_matrix(objs, rig)
                                if centroid_matrix is not None:
                                    resolved_matrix = centroid_matrix @ resolved_matrix
                                    new['deformationCentroidArmature'] = centroid_armature.name if centroid_armature else ''
                                    new['deformationCentroidBones'] = len(centroid_bones)
                            if component_is_skinned and is_skinned_overlay_component(c, meshpath):
                                overlay_matrix, overlay_anchor, overlay_bones = skinned_overlay_alignment_matrix(objs, resolved_matrix, skinned_alignment_anchors)
                                if overlay_matrix is not None:
                                    resolved_matrix = overlay_matrix @ resolved_matrix
                            root_inverse_workflow = None if component_is_skinned else root_inverse_hard_slot_workflow(c, transform_resolver, rig)
                            if root_inverse_workflow is not None:
                                resolved_matrix, bindname, slotname, root_inverse_bone = root_inverse_workflow
                                binding_type = 'slot_root_inverse'
                                can_bind_bone = False
                                child_inverse = None
                            else:
                                root_inverse_bone = ''
                                can_bind_bone = (
                                    not component_is_skinned
                                    and binding_type in {'slot', 'bone'}
                                    and bindname
                                    and armature_has_bone(rig, bindname)
                                )
                                child_inverse = child_of_inverse_matrix(rig, bindname) if can_bind_bone else None
                            transform_animator_name, transform_animator_info_value = component_transform_animator_info(c, parent_transform_lookup, transform_animator_lookup)
                            transform_animator_target = ensure_transform_animator_empty(ent_coll, transform_animator_name, transform_animator_info_value) if transform_animator_info_value is not None else None
                            has_bindname = bool(bindname)
                            has_slotname = bool(slotname)
                            for obj in objs:
                                obj['bindingType'] = binding_type
                                if has_bindname:
                                    obj['bindname'] = bindname
                                if has_slotname:
                                    obj['slotName'] = slotname
                                obj['deformationRigSkinning'] = component_is_skinned
                                if root_inverse_workflow is not None:
                                    configure_root_inverse_child_of(obj, rig, root_inverse_bone, bindname)
                                obj.matrix_world = resolved_matrix @ obj.matrix_world
                                if hide_disabled:
                                    obj.hide_viewport = True
                                    obj.hide_render = True
                                if can_bind_bone:
                                    configure_child_of_constraint(obj, rig, bindname, child_inverse)
                                if transform_animator_target is not None:
                                    add_rotation_axis_driver(obj, transform_animator_target, transform_animator_info_value['axis_no'])
                            if component_is_skinned:
                                bind_skinned_objects_to_rig(objs, rig)
                                if not is_skinned_overlay_component(c, meshpath):
                                    source_armature = skinned_source_armature(objs)
                                    if source_armature is not None:
                                        skinned_alignment_anchors.append({
                                            'component_name': comp_name,
                                            'armature': source_armature,
                                            'vertex_groups': mesh_vertex_group_names(objs),
                                        })

                            if objs:
                                new['depotPath'] = depot_path
                                new['meshAppearance'] = meshApp
                                if 'meshpath' not in new:
                                    new['meshpath'] = "its an entity"
                                if bindname:
                                    new['bindname'] = bindname

                            if 'chunkMask' in c:
                                cm_int = int(c['chunkMask'])
                                for obj in objs:
                                    subnum = submesh_index_for_object(obj)
                                    if subnum is None:
                                        continue
                                    hidden = hide_disabled or not bool((cm_int >> subnum) & 1)
                                    obj.hide_viewport = hidden
                                    obj.hide_render = hidden

                            if new is not None:
                                ent_coll.children.link(new)

                        except Exception:
                            print("Failed on ", meshname)
                            print(traceback.format_exc())
                            if new is not None and ent_coll.children.get(new.name) is None:
                                for obj in list(new.objects):
                                    bpy.data.objects.remove(obj, do_unlink=True)
                                bpy.data.collections.remove(new, do_unlink=True)

                for c in light_channel_components:
                    lcgroupname = component_name(c) or 'LightChannel'
                    mesh_obj = create_light_channel_mesh(c, shape_lookup, filepath)
                    if mesh_obj is None:
                        continue

                    lcgroup = bpy.data.collections.new(lcgroupname)
                    lcgroup.objects.link(mesh_obj)

                    resolved_matrix, bindname, slotname, binding_type = transform_resolver.resolve_hard_component_matrix(c)
                    mesh_obj['bindingType'] = binding_type
                    if bindname:
                        mesh_obj['bindname'] = bindname
                        lcgroup['bindname'] = bindname
                    if slotname:
                        mesh_obj['slotName'] = slotname
                    component_enabled = is_component_enabled(c)
                    mesh_obj['componentEnabled'] = component_enabled
                    mesh_obj.matrix_world = resolved_matrix @ mesh_obj.matrix_world
                    if not component_enabled:
                        mesh_obj.hide_viewport = True
                        mesh_obj.hide_render = True

                    if binding_type in {'slot', 'bone'} and bindname and armature_has_bone(rig, bindname):
                        configure_child_of_constraint(mesh_obj, rig, bindname, child_of_inverse_matrix(rig, bindname))

                    lcgroup['componentName'] = lcgroupname
                    lcgroup['nodeType'] = 'entLightChannelComponent'
                    lcgroup['bindingType'] = binding_type
                    lcgroup['entAppearance'] = app_name
                    ent_coll.children.link(lcgroup)
                print('Appearance import time:', time.time() - app_start_time, 'Seconds')

            if include_collisions:
                collision_collection = bpy.data.collections.new('colliders')
                ent_coll.children.link(collision_collection)
                if include_phys:
                    try:
                        physJsonPaths = asset_index.get_files_by_extension('.phys.json')
                        if len(physJsonPaths) == 0:
                            print('No phys file JSONs found in path')
                        else:
                            if chassis_info:
                                chassis_z = chassis_info['localTransform']['Position']['z']['Bits'] / FIXED_POINT_DIVISOR
                                chassis_phys_j = os.path.basename(chassis_info['collisionResource']['DepotPath']['$value']) + '.json'
                            else:
                                # Approximation when no Chassis component exists: bone 2 translation tracks chassis height closely.
                                chassis_z = rig_j['boneTransforms'][2]['Translation']['Z']
                            for physJsonPath in physJsonPaths:
                                if os.path.basename(physJsonPath) == chassis_phys_j:
                                    cp77_phys_import(physJsonPath, rig, chassis_z)
                    except Exception as e:
                        print(e)

                if include_entCollider:
                    if len(ent_colliderComps) == 0 and len(ent_simpleCollComps) == 0:
                        print('No entColliderComponent or entSimpleColliderComponents found')
                        return('FINISHED')
                    else:
                        for i in ent_colliderComps + ent_simpleCollComps:
                            col_name = i['$type']
                            new_col = collision_collection.children.get(col_name)

                            if not new_col:
                                new_col = bpy.data.collections.new(col_name)
                                collision_collection.children.link(new_col)

                            cdata = i['colliders'][0]['Data']
                            collision_shape = cdata['$type']
                            submeshName = '_' + collision_shape

                            try:
                                obj = import_collider_as_actor(cdata, submeshName, new_col)
                                if obj and 'simulationType' in i:
                                    obj['simulationType'] = i['simulationType']
                            except Exception as e:
                                print(f'Error importing {collision_shape} via pxbridge: {e}')
        if len(error_messages) > 0:
            show_message('Errors during import:\n\t' + '\n\t'.join(error_messages))
        if not cp77_addon_prefs.non_verbose:
            print(f"Imported Entity in {time.time() - start_time} Seconds from {ent_name}.ent")
            print('-------------------- Finished Importing Cyberpunk 2077 Entity --------------------\n')
    finally:
        if rig and getattr(rig, 'type', None) == 'ARMATURE' and getattr(rig, 'data', None):
            rig.data.pose_position = 'POSE'
        if entinitiatedcache:
            JSONTool.stop_caching()
        if Masters:
            Masters.hide_viewport = True
        clear_transient_import_caches()
