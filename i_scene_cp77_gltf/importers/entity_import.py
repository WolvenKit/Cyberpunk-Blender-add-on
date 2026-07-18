# Blender Entity import script by Simarilius
import heapq
import random
import time

import numpy as np
from mathutils import Matrix, Quaternion, Vector

from .direct_anim_import import import_anims_glb_to_armature
from .import_common import *
from .import_common import _remap_copied_object_references, clear_submesh_index_cache, submesh_index_for_object
from .phys_import import cp77_phys_import_into_collection
from .read_rig import (
    create_armature_from_data, create_armature_from_rig_files, merge_rig_datas, meta_bone_name, read_rig,
    rig_data_to_root_chunk,
    )
from ..collisiontools.pxbridge.io_phys import import_collider_as_actor
from ..datakrash import DEFAULT_ASSET_EXTENSIONS, DepotAssetIndex
from ..jsontool import ent_appearance_name, resolve_ent_appearance_alias, resolve_requested_appearance_name
from ..main.animation_api import assign_action_with_slot, ensure_fcurve
from ..main.common import *

ARMATURE_TYPE = 'ARMATURE'
# Proxy meshes and visual controllers do not represent authored visual geometry.
NON_VISUAL_MESH_COMPONENT_TYPES = frozenset({'entAppearanceProxyMeshComponent', 'entVisualControllerComponent'})
# These component families are omitted when their resolved chunk mask is zero.
ZERO_MASK_CULLED_COMPONENT_TYPES = frozenset(
        {
            'entMeshComponent',
            'entPhysicalMeshComponent',
            'entSkinnedMeshComponent',
            'entPhysicalSkinnedMeshComponent',
            'entGarmentSkinnedMeshComponent',
            'entMorphTargetSkinnedMeshComponent',
            }
        )
FIXED_POINT_DIVISOR = 131072
POSITION_KEYS = ('Position', 'Translation', 'relativePosition')
ROTATION_KEYS = ('Orientation', 'Rotation', 'relativeRotation')
_AXIS_INDEX = {'X': 0, 'Y': 1, 'Z': 2}
_UNSET = object()
LIGHT_COMPONENT_TYPES = frozenset({'entLightComponent', 'vehicleLightComponent'})
_LIGHT_DIRECTION_CORRECTION = Matrix.Rotation(math.radians(90.0), 4, 'X')

_RIG_ARMATURE_OBJECT_CACHE = {}
_ARMATURE_BONE_SET_CACHE = {}
_RIG_BONE_INDEX_CACHE = {}
_RIG_BONE_MATRIX_CACHE = {}
_RIG_MODEL_SPACE_CACHE = {}
_RIG_BONE_MATRIX_ARRAY_CACHE = {}
_RIG_BONE_SOURCE_CACHE = {}
_RED_MATRIX_CACHE = {}
_RED_MATRIX_ARRAY_CACHE = {}
_SKIN_ATTACHMENT_CACHE = {}
_SKINNING_BIND_NAME_CACHE = {}
_COMPONENT_PASS_INDEX_CACHE = {}
_CHUNK_LOOKUP_CACHE = {}


def clear_transient_import_caches():
    clear_submesh_index_cache()
    _RIG_ARMATURE_OBJECT_CACHE.clear()
    _ARMATURE_BONE_SET_CACHE.clear()
    _RIG_BONE_INDEX_CACHE.clear()
    _RIG_BONE_MATRIX_CACHE.clear()
    _RIG_MODEL_SPACE_CACHE.clear()
    _RIG_BONE_MATRIX_ARRAY_CACHE.clear()
    _RIG_BONE_SOURCE_CACHE.clear()
    _RED_MATRIX_CACHE.clear()
    _RED_MATRIX_ARRAY_CACHE.clear()
    _SKIN_ATTACHMENT_CACHE.clear()
    _SKINNING_BIND_NAME_CACHE.clear()
    _COMPONENT_PASS_INDEX_CACHE.clear()
    _CHUNK_LOOKUP_CACHE.clear()


def create_axes(ent_coll, name):
    obj = ent_coll.objects.get(name)
    if obj is None:
        obj = bpy.data.objects.new(name, None)
        ent_coll.objects.link(obj)
        obj.empty_display_size = .5
        obj.empty_display_type = 'PLAIN_AXES'
        obj.rotation_mode = 'XYZ'
    return obj


def set_rotation_axis_cycles(obj, axis_no, delta_radians, end_frame):
    start_value = obj.rotation_euler[axis_no]
    action = bpy.data.actions.new(f'{obj.name}_rotation')
    assign_action_with_slot(obj, action)
    fcurve = ensure_fcurve(action, obj, 'rotation_euler', axis_no, 'Rotation')
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


def is_animated_rig_component(component):
    return (
            type(component) is dict
            and component.get('$type') == 'entAnimatedComponent'
            and bool(depot_path_value(component, 'rig'))
    )


def build_embedded_handle_lookup(components, key):
    lookup = {}
    for component in components or ():
        value = component.get(key) if type(component) is dict else None
        if type(value) is not dict:
            continue
        handle_id = value.get('HandleId')
        if handle_id is not None and type(value.get('Data')) is dict:
            lookup[handle_id] = value
    return lookup


def animated_component_control_target(component, lookup=None):
    data = resolve_handle_data(component, lookup, 'controlBinding')
    if type(data) is not dict or data.get('enabled', 1) == 0:
        return ''
    return cname_value(data.get('bindName'))


def is_deformation_rig_component(component):
    if type(component) is not dict:
        return False
    name = component_name(component).lower()
    rig_path = depot_path_value(component, 'rig').replace('\\', '/').lower()
    return (
            'deformation' in name
            or '/deformations_rig/' in rig_path
            or rig_path.endswith('_deformations.rig')
            or rig_path.endswith('_deformation.rig')
    )


def promote_deformation_control_targets(components, control_targets=None):
    components = list(components or ())
    if len(components) < 2:
        return components

    component_by_name = {}
    for component in components:
        name = component_name(component)
        if name and name not in component_by_name:
            component_by_name[name] = component

    authorities = []
    authority_ids = set()
    for component in components:
        if not is_deformation_rig_component(component):
            continue
        target_name = (control_targets or {}).get(id(component), '')
        target = component_by_name.get(target_name)
        if target is None or id(target) in authority_ids:
            continue
        authority_ids.add(id(target))
        authorities.append(target)

    if not authorities:
        return components
    return authorities + [component for component in components if id(component) not in authority_ids]


def order_animated_rig_components(components, control_targets=None):
    components = list(components or ())
    component_count = len(components)
    if component_count < 2:
        return components

    first_index_by_name = {}
    for index, component in enumerate(components):
        name = component_name(component)
        if name and name not in first_index_by_name:
            first_index_by_name[name] = index

    targets = control_targets or {}
    dependency_counts = [0] * component_count
    dependents = [[] for _ in range(component_count)]
    for index, component in enumerate(components):
        target_index = first_index_by_name.get(targets.get(id(component), ''))
        if target_index is None or target_index == index:
            continue
        dependency_counts[index] = 1
        dependents[target_index].append(index)

    ready = [index for index, count in enumerate(dependency_counts) if count == 0]
    heapq.heapify(ready)
    emitted = [False] * component_count
    result = []
    while ready:
        index = heapq.heappop(ready)
        if emitted[index]:
            continue
        emitted[index] = True
        result.append(components[index])
        for dependent_index in dependents[index]:
            dependency_counts[dependent_index] = 0
            if not emitted[dependent_index]:
                heapq.heappush(ready, dependent_index)

    if len(result) != component_count:
        remaining = [component for index, component in enumerate(components) if not emitted[index]]
        cycle_names = ', '.join(component_name(component, '<unnamed>') for component in remaining)
        print(f'animation control binding cycle detected; preserving source order for: {cycle_names}')
        result.extend(remaining)
    return promote_deformation_control_targets(result, control_targets)


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
    return Quaternion(
            (
                value.get('r', 1),
                value.get('i', 0),
                value.get('j', 0),
                value.get('k', 0),
                )
            )


def is_component_enabled(component):
    return component.get('isEnabled', 1) != 0 if type(component) is dict else True


def chunk_mask_value(component):
    raw = component.get('chunkMask') if type(component) is dict else None
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def component_is_zero_mask_culled(component):
    return (
            type(component) is dict
            and component.get('$type') in ZERO_MASK_CULLED_COMPONENT_TYPES
            and chunk_mask_value(component) == 0
    )


def depot_to_local_path(root, depot_path):
    return os.path.join(root, depot_path).replace('\\', os.sep) if depot_path else ''


@lru_cache(maxsize=65536)
def norm_path_key(value):
    return os.path.normcase(os.path.normpath(value)) if value else ''


_SOURCE_RAW_PATTERN = re.compile(r'(?:^|/)source/raw(?=$|/)', re.IGNORECASE)


def split_source_raw_root(filepath):
    if not filepath:
        return '', ''
    normalized = os.path.normpath(filepath)
    # Segment-boundary match: a plain substring search also matches paths like '.../resource/raw...'.
    match = _SOURCE_RAW_PATTERN.search(normalized.replace('\\', '/'))
    if match is None:
        root = os.path.dirname(normalized)
        return root, os.path.basename(normalized)
    end = match.end()
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
            # Preserve the first component registered under each name.
            lookup.setdefault(name, component)
    return lookup


def merge_components_first_wins(primary, secondary):
    # Entity components take precedence over appearance components with the same name.
    merged = list(primary or [])
    seen = set()
    for component in merged:
        name = component_name(component)
        if name:
            seen.add(name)
    append = merged.append
    for component in secondary or ():
        name = component_name(component)
        if name and name in seen:
            continue
        if name:
            seen.add(name)
        append(component)
    return merged


def appearance_request_is_known(app_name, ent_default, ent_apps, by_appearance, by_name):
    if not app_name or app_name == 'BASE_COMPONENTS_ONLY' or app_name.upper() == 'ALL':
        return True
    if app_name == 'default':
        return not ent_apps or not ent_default or \
            resolve_ent_appearance_alias(ent_default, ent_apps, by_appearance, by_name)[0] >= 0
    return resolve_ent_appearance_alias(app_name, ent_apps, by_appearance, by_name)[0] >= 0


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


def build_chunk_lookup(chunks, target_key, handle_key='HandleId'):
    source = chunks or ()
    cache_key = (id(source), target_key, handle_key, len(source))
    cached = _CHUNK_LOOKUP_CACHE.get(cache_key)
    if cached is not None and cached[0] is source:
        return cached[1]
    lookup = {}
    for chunk in source:
        if not isinstance(chunk, dict):
            continue
        target_data = chunk.get(target_key)
        if isinstance(target_data, dict) and handle_key in target_data:
            lookup[target_data[handle_key]] = target_data
    _CHUNK_LOOKUP_CACHE[cache_key] = (source, lookup)
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
    has_geometry = {}
    order = []
    for components in component_groups:
        for source in components or ():
            if not isinstance(source, dict) or source.get('$type') != 'entLightChannelComponent':
                continue
            key = component_name(source) or str(id(source))
            if key not in collected:
                collected[key] = source
                has_geometry[key] = _UNSET
                order.append(key)
                continue
            current_has_geometry = has_geometry[key]
            if current_has_geometry is _UNSET:
                current_has_geometry = light_channel_geometry(collected[key])[0] is not None
                has_geometry[key] = current_has_geometry
            if not current_has_geometry and light_channel_geometry(source)[0] is not None:
                collected[key] = source
                has_geometry[key] = True
    return [collected[key] for key in order]


def collect_light_components(*component_groups):
    collected = {}
    order = []
    for components in component_groups:
        for component in components or ():
            if not isinstance(component, dict) or component.get('$type') not in LIGHT_COMPONENT_TYPES:
                continue
            name = component_name(component)
            key = name or str(component.get('id') or id(component))
            if key not in collected:
                collected[key] = component
                order.append(key)
    return [collected[key] for key in order]


def _light_float(component, key, default=0.0):
    value = component.get(key, default) if isinstance(component, dict) else default
    if isinstance(value, dict):
        value = value.get('$value', default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _light_color(component):
    color = component.get('color') if isinstance(component, dict) else None
    if not isinstance(color, dict):
        return 1.0, 1.0, 1.0
    return tuple(
            max(0.0, min(1.0, _light_float(color, channel, 255.0) / 255.0)) for channel in ('Red', 'Green', 'Blue')
            )


def _blender_light_type(component):
    light_type = component.get('type') if isinstance(component, dict) else None
    if light_type == 'LT_Spot':
        return 'SPOT'
    if light_type == 'LT_Area':
        return 'AREA'
    if light_type in {'LT_Directional', 'LT_Sun'} or (isinstance(component, dict) and component.get('directional', 0)):
        return 'SUN'
    return 'POINT'


def _set_light_distance(light_data, radius):
    if radius <= 0.0:
        return
    if hasattr(light_data, 'use_custom_distance'):
        light_data.use_custom_distance = True
    if hasattr(light_data, 'cutoff_distance'):
        light_data.cutoff_distance = radius


def _set_light_softness(light_data, component):
    source_radius = _light_float(component, 'sourceRadius', -1.0)
    if source_radius < 0.0:
        source_radius = _light_float(component, 'shadowRadius', -1.0)
    if source_radius >= 0.0 and hasattr(light_data, 'shadow_soft_size'):
        light_data.shadow_soft_size = source_radius


def _configure_area_light(light_data, component):
    shape = component.get('areaShape', 'ALS_Rectangle')
    radius = max(_light_float(component, 'radius', 0.0), 0.0)
    side_a = max(_light_float(component, 'areaRectSideA', 1.0), 0.001)
    side_b = max(_light_float(component, 'areaRectSideB', 1.0), 0.001)
    capsule_length = max(_light_float(component, 'capsuleLength', 0.0), 0.0)

    if shape == 'ALS_Capsule':
        light_data.shape = 'RECTANGLE'
        light_data.size = max(capsule_length + radius * 2.0, 0.001)
        light_data.size_y = max(radius * 2.0, 0.001)
    elif shape in {'ALS_Sphere', 'ALS_Circle', 'ALS_Disc'}:
        light_data.shape = 'DISK'
        light_data.size = max(radius * 2.0, side_a, 0.001)
    elif shape in {'ALS_Ellipse', 'ALS_Oval'}:
        light_data.shape = 'ELLIPSE'
        light_data.size = side_a
        light_data.size_y = side_b
    elif shape in {'ALS_Rectangle', 'ALS_Rect'}:
        light_data.shape = 'RECTANGLE'
        light_data.size = side_a
        light_data.size_y = side_b
    else:
        light_data.shape = 'SQUARE'
        light_data.size = side_a


def _configure_light_data(light_data, component):
    intensity = max(_light_float(component, 'intensity', 0.0), 0.0)
    on_strength = max(_light_float(component, 'onStrength', 1.0), 0.0)
    light_data.energy = intensity * on_strength / 10.0
    light_data.color = _light_color(component)

    radius = max(_light_float(component, 'radius', 0.0), 0.0)
    _set_light_distance(light_data, radius)
    if hasattr(light_data, 'use_shadow'):
        light_data.use_shadow = bool(component.get('enableLocalShadows', 1))
    if hasattr(light_data, 'diffuse_factor'):
        light_data.diffuse_factor = max(_light_float(component, 'sceneDiffuse', 1.0), 0.0)
    if hasattr(light_data, 'specular_factor'):
        specular = 0.0 if component.get('noSpecular', 0) else max(_light_float(component, 'sceneSpecular', 1.0), 0.0)
        light_data.specular_factor = specular * max(_light_float(component, 'sceneSpecularScale', 100.0), 0.0) / 100.0
    if hasattr(light_data, 'volume_factor'):
        light_data.volume_factor = max(_light_float(component, 'scaleVolFog', 0.0), 0.0) / 100.0 if component.get(
            'useInFog', 0
            ) else 0.0
    if hasattr(light_data, 'transmission_factor'):
        light_data.transmission_factor = 1.0 if component.get('useInTransparents', 1) else 0.0

    temperature = _light_float(component, 'temperature', -1.0)
    if temperature > 0.0 and hasattr(light_data, 'temperature'):
        if hasattr(light_data, 'use_temperature'):
            light_data.use_temperature = True
        light_data.temperature = temperature

    if light_data.type == 'SPOT':
        outer_angle = max(_light_float(component, 'outerAngle', 45.0), 0.001)
        inner_angle = max(0.0, min(_light_float(component, 'innerAngle', outer_angle), outer_angle))
        light_data.spot_size = math.radians(min(outer_angle, 179.0))
        light_data.spot_blend = max(0.0, min(1.0, 1.0 - inner_angle / outer_angle))
        _set_light_softness(light_data, component)
    elif light_data.type == 'AREA':
        _configure_area_light(light_data, component)
    elif light_data.type == 'SUN':
        shadow_angle = _light_float(component, 'shadowAngle', -1.0)
        if shadow_angle >= 0.0 and hasattr(light_data, 'angle'):
            light_data.angle = math.radians(shadow_angle)
    else:
        _set_light_softness(light_data, component)


def _store_light_metadata(light_obj, component, filepath):
    component_type = component.get('$type', 'entLightComponent')
    light_obj['ntype'] = component_type
    light_obj['componentName'] = component_name(component)
    light_obj['entJSON'] = filepath

    for key in (
            'type', 'unit', 'intensity', 'EV', 'radius', 'innerAngle', 'outerAngle',
            'sourceRadius', 'shadowRadius', 'softness', 'areaShape', 'areaRectSideA',
            'areaRectSideB', 'capsuleLength', 'areaTwoSided', 'attenuation',
            'lightChannel', 'group', 'turnOnByDefault', 'onStrength', 'materialZone',
            'enableLocalShadows', 'enableContactShadows', 'contactShadows',
            'sceneDiffuse', 'sceneSpecular', 'sceneSpecularScale', 'scaleVolFog',
            'useInFog', 'useInGI', 'useInTransparents', 'temperature',
            ):
        value = component.get(key)
        if isinstance(value, (str, int, float, bool)):
            light_obj[key] = value

    color = component.get('color')
    if isinstance(color, dict):
        light_obj['redColor'] = [
            int(_light_float(color, 'Red', 255)),
            int(_light_float(color, 'Green', 255)),
            int(_light_float(color, 'Blue', 255)),
            int(_light_float(color, 'Alpha', 255)),
            ]

    flicker = component.get('flicker')
    if isinstance(flicker, dict):
        for source_key, target_key in (
                ('flickerPeriod', 'flickerPeriod'),
                ('flickerStrength', 'flickerStrength'),
                ('positionOffset', 'flickerPositionOffset'),
                ):
            value = flicker.get(source_key)
            if isinstance(value, (int, float)):
                light_obj[target_key] = value

    ies_profile = depot_path_value(component, 'iesProfile')
    if ies_profile:
        light_obj['iesProfile'] = ies_profile


def create_entity_light(component, filepath):
    name = component_name(component) or component.get('$type', 'Light')
    light_data = bpy.data.lights.new(name, _blender_light_type(component))
    _configure_light_data(light_data, component)
    light_obj = bpy.data.objects.new(name, light_data)
    light_obj.rotation_mode = 'QUATERNION'
    light_obj.show_in_front = True
    _store_light_metadata(light_obj, component, filepath)
    return light_obj


def _physx_actor_type(component):
    simulation_type = cname_value(component.get('simulationType')) if isinstance(component, dict) else ''
    actor_type = str(simulation_type).rsplit('::', 1)[-1].upper()
    return actor_type if actor_type in {'STATIC', 'DYNAMIC', 'KINEMATIC'} else 'STATIC'


def _collider_component_mass(component):
    if not isinstance(component, dict):
        return 0.0
    for key in ('massOverride', 'mass'):
        value = component.get(key)
        try:
            value = float(value)
        except (TypeError, ValueError):
            continue
        if value > 0.0:
            return value
    return 0.0


def _collect_handle_data(value, lookup):
    if isinstance(value, dict):
        data = value.get('Data')
        handle_id = value.get('HandleId')
        if handle_id is not None and isinstance(data, dict):
            lookup.setdefault(handle_id, data)
            lookup.setdefault(str(handle_id), data)
        for child in value.values():
            _collect_handle_data(child, lookup)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _collect_handle_data(child, lookup)


def _resolve_handle_reference(value, lookup=None, component=None):
    if not isinstance(value, dict):
        return None
    data = value.get('Data')
    if isinstance(data, dict):
        return data
    handle_ref = value.get('HandleRefId')
    if handle_ref is not None and lookup is not None:
        if component is not None and hasattr(lookup, 'get_for_component'):
            referenced = lookup.get_for_component(component, handle_ref)
        else:
            referenced = lookup.get(handle_ref)
            if referenced is None:
                referenced = lookup.get(str(handle_ref))
        if isinstance(referenced, dict) and isinstance(referenced.get('Data'), dict):
            return referenced['Data']
        if isinstance(referenced, dict):
            return referenced
    return value if '$type' in value else None


def _resolve_handle_data(value, lookup):
    return _resolve_handle_reference(value, lookup)


def _new_collection_object(collection, existing_objects, expected_name):
    for obj in collection.objects:
        if obj not in existing_objects:
            return obj
    return collection.objects.get(expected_name)


def _import_registered_entity_colliders(components, transform_resolver, handle_sources, target_collection, context):
    handle_lookup = {}
    _collect_handle_data(handle_sources, handle_lookup)
    actor_count = 0
    shape_count = 0

    for component in components or ():
        if not isinstance(component, dict) or not is_component_enabled(component):
            continue

        collider_refs = component.get('colliders')
        if isinstance(collider_refs, dict):
            collider_refs = [collider_refs]
        if not collider_refs:
            continue

        if transform_resolver is not None:
            resolved_matrix, bind_name, slot_name, binding_type, attach_armature = transform_resolver.resolve_component_matrix(
                component
                )
        else:
            resolved_matrix, bind_name, slot_name, binding_type, attach_armature = Matrix.Identity(
                4
                ), '', '', 'none', None

        component_type = component.get('$type', 'entColliderComponent')
        component_label = component_name(component) or component_type
        actor_type = _physx_actor_type(component)
        mass = _collider_component_mass(component)
        inertia = component.get('inertia')
        com_offset = component.get('comOffset')
        component_filter = component.get('filterData') or component.get('filter')
        actor_obj = None
        component_shapes = 0

        for shape_index, collider_ref in enumerate(collider_refs):
            collider_data = _resolve_handle_data(collider_ref, handle_lookup)
            if not isinstance(collider_data, dict):
                continue

            collider_type = collider_data.get('$type', 'physicsColliderBox')
            actor_name = f'{component_label}_{component_type}'
            submesh_name = actor_name if actor_obj is None else f'{actor_name}_{shape_index}_{collider_type}'
            existing_objects = set(target_collection.objects) if actor_obj is None else None

            try:
                shape_item = import_collider_as_actor(
                        collider_data,
                        submesh_name,
                        target_collection,
                        actor_obj=actor_obj,
                        context=context,
                        actor_type=actor_type,
                        mass=mass,
                        inertia=inertia,
                        com_offset=com_offset,
                        filter_data=collider_data.get('filterData') or component_filter,
                        )
            except Exception as exc:
                print(f'Error importing {collider_type} for {component_label}: {exc}')
                continue

            if shape_item is None:
                continue

            if actor_obj is None:
                actor_obj = _new_collection_object(target_collection, existing_objects, actor_name)
                if actor_obj is None:
                    print(f'PhysX actor registration did not create an actor object for {component_label}')
                    break
                actor_obj.matrix_world = resolved_matrix
                actor_obj['ntype'] = component_type
                actor_obj['componentName'] = component_label
                actor_obj['bindingType'] = binding_type
                actor_obj['actorType'] = actor_type
                if bind_name:
                    actor_obj['bindname'] = bind_name
                if slot_name:
                    actor_obj['slotName'] = slot_name
                if 'simulationType' in component:
                    actor_obj['simulationType'] = component['simulationType']

                if actor_type != 'DYNAMIC' and binding_type in {'slot',
                                                                'bone'} and bind_name and attach_armature is not None:
                    configure_child_of_constraint(
                            actor_obj,
                            attach_armature,
                            bind_name,
                            child_of_inverse_matrix(attach_armature, bind_name),
                            )

            shape_item.name = f'{component_label}_{shape_index}_{shape_item.name}'[:63]
            component_shapes += 1

        if actor_obj is not None and component_shapes:
            actor_count += 1
            shape_count += component_shapes

    scene_physx = getattr(context.scene, 'physx', None)
    if scene_physx is not None and actor_count:
        if hasattr(scene_physx, 'scene_built'):
            scene_physx.scene_built = False
        if hasattr(scene_physx, 'active_actor_count'):
            scene_physx.active_actor_count = len(scene_physx.actors)
        print(f'Registered {actor_count} PhysX actors with {shape_count} collider shapes')
    elif actor_count == 0:
        print('No supported entity collider shapes were registered')

    return actor_count, shape_count


def build_component_pass_index(components):
    source = components or ()
    source_ids = tuple(id(component) for component in source)
    cached = _COMPONENT_PASS_INDEX_CACHE.get(source_ids)
    if cached is not None:
        cached_source, cached_index = cached
        if len(cached_source) == len(source) and all(a is b for a, b in zip(cached_source, source)):
            return cached_index
    indexed = {
        'components': [],
        'by_name': {},
        'rig_components': [],
        'slot_components': [],
        'mesh_components': [],
        'transform_animator_components': [],
        }
    all_components = indexed['components']
    by_name = indexed['by_name']
    rig_components = indexed['rig_components']
    slot_components = indexed['slot_components']
    mesh_components = indexed['mesh_components']
    animator_components = indexed['transform_animator_components']
    for component in source:
        if type(component) is not dict:
            continue
        all_components.append(component)
        name = component_name(component)
        if name:
            by_name.setdefault(name, component)
        component_type = component.get('$type')
        if depot_path_value(component, 'rig'):
            rig_components.append(component)
        if isinstance(component.get('slots'), list):
            slot_components.append(component)
        if (
                'mesh' in component or 'graphicsMesh' in component) and component_type not in NON_VISUAL_MESH_COMPONENT_TYPES:
            mesh_components.append(component)
        if component_type == 'gameTransformAnimatorComponent':
            animator_components.append(component)
    _COMPONENT_PASS_INDEX_CACHE[source_ids] = (tuple(source), indexed)
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
            # Preserve the first slot registered under each name.
            lookup.setdefault(name, slot)
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
    if cached is not None and cached[0] is rig_j:
        return cached[1]
    index = build_rig_bone_index(rig_j)
    _RIG_BONE_INDEX_CACHE[key] = (rig_j, index)
    return index


def _rig_json_bone_source(rig_j):
    cache_key = id(rig_j)
    cached = _RIG_BONE_SOURCE_CACHE.get(cache_key)
    if cached is not None and cached[0] is rig_j:
        return cached[1]
    bone_count = len(rig_j.get('boneNames') or ())
    apose_ls = rig_j.get('aPoseLS')
    has_apose = type(apose_ls) is list and len(apose_ls) == bone_count
    apose_ms = rig_j.get('aPoseMS')
    use_model_space = has_apose and type(apose_ms) is list and len(apose_ms) == bone_count
    transforms = apose_ms if use_model_space else (apose_ls if has_apose else rig_j.get('boneTransforms'))
    source = (transforms, rig_j.get('boneParentIndexes'), use_model_space)
    _RIG_BONE_SOURCE_CACHE[cache_key] = (rig_j, source)
    return source


def _rig_json_model_space_matrices(rig_j):
    if type(rig_j) is not dict:
        return ()
    cache_key = id(rig_j)
    cached = _RIG_MODEL_SPACE_CACHE.get(cache_key)
    if cached is not None and cached[0] is rig_j:
        return cached[1]
    matrix_cache = _RIG_BONE_MATRIX_CACHE.setdefault(cache_key, {})
    matrices = tuple(
            _rig_json_bone_matrix_for_index(rig_j, index, matrix_cache)
            for index in range(len(rig_j.get('boneNames') or ()))
            )
    _RIG_MODEL_SPACE_CACHE[cache_key] = (rig_j, matrices)
    return matrices


def _rig_json_bone_matrix_array(rig_j):
    if type(rig_j) is not dict:
        return np.empty((0, 4, 4), dtype=np.float64)
    cache_key = id(rig_j)
    cached = _RIG_BONE_MATRIX_ARRAY_CACHE.get(cache_key)
    if cached is not None and cached[0] is rig_j:
        return cached[1]
    matrices = _rig_json_model_space_matrices(rig_j)
    array = np.asarray(matrices, dtype=np.float64)
    if not matrices:
        array = np.empty((0, 4, 4), dtype=np.float64)
    _RIG_BONE_MATRIX_ARRAY_CACHE[cache_key] = (rig_j, array)
    return array


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

    transforms, parents, use_model_space = _rig_json_bone_source(rig_j)
    if type(transforms) is list and index < len(transforms):
        matrix = transform_matrix(transforms[index])
        if not use_model_space:
            parent_index = parents[index] if type(parents) is list and index < len(parents) else -1
            parent_matrix = _rig_json_bone_matrix_for_index(
                rig_j, parent_index, matrices, resolving
                ) if parent_index is not None and parent_index >= 0 else Matrix.Identity(
                4
                )
            matrix = parent_matrix @ matrix
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


def build_slot_owner_binding_maps(
        slot_components, parent_transform_lookup, rig_json_by_component_name, rig_component_names,
        ):
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
    return Vector(
            (
                x.get('Bits', 0) / FIXED_POINT_DIVISOR if type(x) is dict else data.get('X', 0),
                y.get('Bits', 0) / FIXED_POINT_DIVISOR if type(y) is dict else data.get('Y', 0),
                z.get('Bits', 0) / FIXED_POINT_DIVISOR if type(z) is dict else data.get('Z', 0),
                )
            )


def transform_scale(transform):
    scale = transform.get('Scale') or transform.get('scale') if type(transform) is dict else None
    if type(scale) is not dict:
        return Vector((1, 1, 1))
    return Vector((scale.get('X', 1), scale.get('Y', 1), scale.get('Z', 1)))


def transform_matrix(transform, pos_keys=POSITION_KEYS, rot_keys=ROTATION_KEYS, scale=None):
    if type(transform) is not dict:
        return Matrix.Identity(4)
    return Matrix.LocRotScale(
            transform_position(transform, pos_keys),
            red_quaternion(transform_field(transform, rot_keys)),
            scale if scale is not None else transform_scale(transform),
            )


def visual_scale_matrix(component):
    # visualScale scales the component's own geometry; it is not part of the placement
    # hierarchy, so children and slot offsets must never inherit it.
    scale = component.get('visualScale') if type(component) is dict else None
    if type(scale) is not dict:
        return None
    vec = Vector((scale.get('X', 1), scale.get('Y', 1), scale.get('Z', 1)))
    if abs(vec.x - 1.0) <= 1e-9 and abs(vec.y - 1.0) <= 1e-9 and abs(vec.z - 1.0) <= 1e-9:
        return None
    return Matrix.LocRotScale(Vector((0, 0, 0)), Quaternion((1, 0, 0, 0)), vec)


def resolve_handle_data(component, lookup, key):
    value = component.get(key) if isinstance(component, dict) else None
    return _resolve_handle_reference(value, lookup, component)


def parent_transform_data(component, parent_transform_lookup):
    return resolve_handle_data(component, parent_transform_lookup, 'parentTransform')


def skinning_binding_data(component, skinning_lookup=None):
    resolved = resolve_handle_data(component, skinning_lookup, 'skinning')
    if resolved is not None:
        return resolved
    skinning = component.get('skinning') if type(component) is dict else None
    return skinning if isinstance(skinning, dict) and 'Data' not in skinning else None


def skinning_bind_name(component, skinning_lookup=None):
    cache_key = (id(component), id(skinning_lookup))
    cached = _SKINNING_BIND_NAME_CACHE.get(cache_key)
    if cached is not None and cached[0] is component and cached[1] is skinning_lookup:
        return cached[2]
    data = skinning_binding_data(component, skinning_lookup)
    bind_name = cname_value(data.get('bindName')) if isinstance(data, dict) else ''
    _SKINNING_BIND_NAME_CACHE[cache_key] = (component, skinning_lookup, bind_name)
    return bind_name


def component_uses_skinning(component, skinning_lookup=None):
    bind_name = skinning_bind_name(component, skinning_lookup)
    return bool(bind_name and bind_name != 'None')


def import_animset_to_metarig(anim_path, rig, rig_path='', ent_name='', import_tracks=True):
    if not anim_path:
        return False
    if not is_live_armature_object(rig):
        raise RuntimeError('A live JSON MetaRig is required before importing an animation set')

    bpy.context.scene.render.fps = 30
    cp77_addon_prefs = bpy.context.preferences.addons['i_scene_cp77_gltf'].preferences
    summary = import_anims_glb_to_armature(
            anim_path,
            rig,
            import_tracks=import_tracks,
            verbose=not cp77_addon_prefs.non_verbose,
            )
    cache_armature_bones(rig)
    rig['animset'] = anim_path
    if rig_path:
        rig['animation_source_rig_json'] = rig_path
    if ent_name:
        rig['ent'] = ent_name + '.ent.json'
    print(
            f"imported {summary['animation_count']} animations directly onto "
            f"JSON MetaRig: {rig.name}"
            )
    return summary


def child_of_inverse_matrix(target, subtarget_name=''):
    target_matrix = target.matrix_world.copy()
    if armature_has_bone(target, subtarget_name):
        target_matrix = target.matrix_world @ target.pose.bones[subtarget_name].matrix
    try:
        return target_matrix.inverted()
    except Exception:
        return Matrix.Identity(4)


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


def _armature_matches_rig_source(armature, rig_source_key):
    # Animation-GLB armatures are intentionally excluded from the entity rig pipeline.
    if armature.get('animation_only', False):
        return False
    # Same-named armatures from different rig assets must not alias; only reuse an armature
    # whose recorded source rig matches.
    stored = armature.get('source_rig_file') or armature.get('rig') or ''
    if not stored and getattr(armature, 'data', None) is not None:
        stored = armature.data.get('source_rig_file') or ''
    return bool(stored) and norm_path_key(str(stored)) == rig_source_key


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
    if getattr(direct, 'type', None) == ARMATURE_TYPE and _armature_matches_rig_source(direct, target):
        cache_armature_bones(direct)
        _RIG_ARMATURE_OBJECT_CACHE[target] = direct
        return direct

    # A-Pose matches the resolver's bind-pose preference (aPose arrays when populated);
    # create_armature_from_data falls back to the boneTransforms T-pose itself.
    created = create_armature_from_data(rig_json_path, 'A-Pose', False)
    armature = created if getattr(created, 'type', None) == ARMATURE_TYPE else None

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


def ensure_armature_from_rig_jsons(rig_json_paths, ent_name=''):
    ordered_paths = []
    ordered_keys = []
    seen_keys = set()
    for path in rig_json_paths or ():
        if not path:
            continue
        key = norm_path_key(path)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        ordered_paths.append(path)
        ordered_keys.append(key)
    if not ordered_paths:
        return None
    # A MetaRig is a distinct product even when it contains one source rig. Never reuse
    # the ordinary raw-rig armature created by ensure_armature_from_rig_json.
    merged_key = 'metarig:' + ';'.join(ordered_keys)
    existing = _RIG_ARMATURE_OBJECT_CACHE.get(merged_key)
    if is_live_armature_object(existing):
        cache_armature_bones(existing)
        return existing
    if existing is not None:
        _RIG_ARMATURE_OBJECT_CACHE.pop(merged_key, None)

    merged_name = (ent_name + '_rig') if ent_name else 'merged_rig'
    direct = bpy.data.objects.get(merged_name)
    if getattr(direct, 'type', None) == ARMATURE_TYPE and _armature_matches_rig_source(direct, merged_key):
        cache_armature_bones(direct)
        _RIG_ARMATURE_OBJECT_CACHE[merged_key] = direct
        return direct

    # Every rig referenced by the entity's animated components contributes bones so
    # skinning retarget never drops influences (partial skeletons spaghettify meshes).
    created = create_armature_from_rig_files(ordered_paths, merged_name, source_label=merged_key)
    armature = created if getattr(created, 'type', None) == ARMATURE_TYPE else None
    if armature is not None:
        cache_armature_bones(armature)
        _RIG_ARMATURE_OBJECT_CACHE[merged_key] = armature
        armature['rig'] = ordered_paths[0]
        armature['source_rig_file'] = merged_key
        armature['merged_rigs'] = list(ordered_paths)
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


def _red_matrix_to_blender(value):
    """Convert a serialized RED Matrix to mathutils column-vector form."""
    if not isinstance(value, dict):
        return None
    cache_key = id(value)
    cached = _RED_MATRIX_CACHE.get(cache_key)
    if cached is not None and cached[0] is value:
        return cached[1]
    x = value.get('X')
    y = value.get('Y')
    z = value.get('Z')
    w = value.get('W')
    matrix = None
    if all(isinstance(column, dict) for column in (x, y, z, w)):
        try:
            matrix = Matrix(
                    (
                        (float(x['X']), float(y['X']), float(z['X']), float(w['X'])),
                        (float(x['Y']), float(y['Y']), float(z['Y']), float(w['Y'])),
                        (float(x['Z']), float(y['Z']), float(z['Z']), float(w['Z'])),
                        (float(x['W']), float(y['W']), float(z['W']), float(w['W'])),
                        )
                    )
        except (KeyError, TypeError, ValueError):
            matrix = None
    _RED_MATRIX_CACHE[cache_key] = (value, matrix)
    return matrix


def _red_matrix_to_array(value):
    if not isinstance(value, dict):
        return None
    cache_key = id(value)
    cached = _RED_MATRIX_ARRAY_CACHE.get(cache_key)
    if cached is not None and cached[0] is value:
        return cached[1]
    matrix = _red_matrix_to_blender(value)
    array = None if matrix is None else np.asarray(matrix, dtype=np.float64)
    _RED_MATRIX_ARRAY_CACHE[cache_key] = (value, array)
    return array


def _mesh_skin_anchor(mesh_j, rig_j):
    """Return the first valid mesh bone in authored mesh order.

    RigTargetMapping maps every mesh bone independently by name and does not rebuild a
    hierarchy or identify a unique root. For Blender's component-level adapter, the
    deterministic anchor is therefore the first authored mesh bone that resolves in the
    completed MetaRig. Later mapped bones remain deformers and do not participate in
    choosing the component attachment.
    """
    if not isinstance(mesh_j, dict) or not isinstance(rig_j, dict):
        return None, 'missing_json'
    raw_names = mesh_j.get('boneNames')
    raw_matrices = mesh_j.get('boneRigMatrices')
    if not isinstance(raw_names, list) or not isinstance(raw_matrices, list):
        return None, 'missing_skin_data'

    rig_index = rig_bone_index_for(rig_j)
    saw_named_bone = False
    for mesh_index, raw_name in enumerate(raw_names):
        source_name = cname_value(raw_name)
        if not source_name:
            continue
        saw_named_bone = True
        if mesh_index >= len(raw_matrices):
            continue
        target_name = meta_bone_name(source_name)
        target_index = rig_index.get(target_name)
        if target_index is not None:
            return (mesh_index, source_name, target_name, target_index), 'ok'

    return None, 'missing_mapped_bone' if saw_named_bone else 'missing_bones'


def _matrices_near(a, b, epsilon=1e-4):
    for row in range(4):
        a_row = a[row]
        b_row = b[row]
        for column in range(4):
            if abs(a_row[column] - b_row[column]) > epsilon:
                return False
    return True


def component_skin_attachment_matrix(mesh_j, rig_j):
    """Return the RED attachment transform of the first mapped mesh bone.

    RigTargetMapping preserves authored mesh-bone order and maps every bone independently.
    The first valid mapped mesh bone supplies the component attachment anchor; later
    mesh bones remain deformers and must not veto that attachment.

    In Blender column-vector convention the anchor attachment is:

        merged_anchor_ms @ mesh_anchor_bone_rig_matrix

    Both operands come from RED JSON. No GLTF armature or Blender pose matrix participates.
    """
    cache_key = (id(mesh_j), id(rig_j))
    cached = _SKIN_ATTACHMENT_CACHE.get(cache_key)
    if cached is not None and cached[0] is mesh_j and cached[1] is rig_j:
        return cached[2]

    root, status = _mesh_skin_anchor(mesh_j, rig_j)
    if root is None:
        result = (None, '', status)
        _SKIN_ATTACHMENT_CACHE[cache_key] = (mesh_j, rig_j, result)
        return result

    mesh_index, source_name, target_name, target_index = root
    raw_matrices = mesh_j.get('boneRigMatrices') or ()
    if mesh_index >= len(raw_matrices):
        result = (None, source_name, 'missing_anchor_bind_matrix')
        _SKIN_ATTACHMENT_CACHE[cache_key] = (mesh_j, rig_j, result)
        return result

    skin_to_rig = _red_matrix_to_blender(raw_matrices[mesh_index])
    if skin_to_rig is None:
        result = (None, source_name, 'invalid_anchor_bind_matrix')
        _SKIN_ATTACHMENT_CACHE[cache_key] = (mesh_j, rig_j, result)
        return result

    rig_matrices = _rig_json_model_space_matrices(rig_j)
    rig_model_space = rig_matrices[target_index] if target_index < len(rig_matrices) else Matrix.Identity(4)
    placement = rig_model_space @ skin_to_rig

    # Descendant products are diagnostic only. They describe deformation within the
    # attached component and are not required to equal the root attachment matrix.
    rig_index = rig_bone_index_for(rig_j)
    non_uniform_children = []
    missing_children = []
    child_names = []
    child_target_indices = []
    child_bind_matrices = []
    raw_names = mesh_j.get('boneNames') or ()
    for child_index, raw_name in enumerate(raw_names):
        if child_index == mesh_index or child_index >= len(raw_matrices):
            continue
        child_source_name = cname_value(raw_name)
        if not child_source_name:
            continue
        child_target_index = rig_index.get(meta_bone_name(child_source_name))
        child_skin_to_rig = _red_matrix_to_array(raw_matrices[child_index])
        if child_target_index is None or child_skin_to_rig is None:
            missing_children.append(child_source_name)
            continue
        child_names.append(child_source_name)
        child_target_indices.append(child_target_index)
        child_bind_matrices.append(child_skin_to_rig)

    if child_names:
        rig_matrix_array = _rig_json_bone_matrix_array(rig_j)
        target_array = rig_matrix_array[np.asarray(child_target_indices, dtype=np.intp)]
        bind_array = np.stack(child_bind_matrices)
        products = np.matmul(target_array, bind_array)
        placement_array = np.asarray(placement, dtype=np.float64)
        differences = np.max(np.abs(products - placement_array), axis=(1, 2))
        non_uniform_children = [
            name for name, difference in zip(child_names, differences)
            if difference > 1e-4
            ]

    if missing_children:
        status = 'anchor_ok_missing_mappings:' + ','.join(missing_children)
    elif non_uniform_children:
        status = 'anchor_ok_deforming_bones:' + ','.join(non_uniform_children)
    else:
        status = 'ok'
    result = (placement, source_name, status)
    _SKIN_ATTACHMENT_CACHE[cache_key] = (mesh_j, rig_j, result)
    return result


def _rename_vertex_groups_to_meta(obj, rig):
    rig_bones = cache_armature_bones(rig)
    for group in getattr(obj, 'vertex_groups', ()):
        source_name = group.name
        target_name = meta_bone_name(source_name)
        if target_name != source_name and target_name in rig_bones and source_name not in rig_bones:
            group.name = target_name


def bind_skinned_objects_to_rig(objects, rig):
    """Redirect copied mesh modifiers after the JSON MetaRig is fully assembled."""
    if rig is None:
        return 0, 0

    copied = set(objects)
    live_sources = {}
    skinned_meshes = 0
    redirected_modifiers = 0
    for obj in objects:
        if getattr(obj, 'type', None) != 'MESH':
            continue
        mesh_redirected = False
        for modifier in getattr(obj, 'modifiers', ()):
            if modifier.type != 'ARMATURE':
                continue
            source_armature = modifier.object
            if source_armature is rig:
                mesh_redirected = True
                continue
            if source_armature is None or source_armature not in copied:
                continue
            source_key = id(source_armature)
            source_is_live = live_sources.get(source_key, _UNSET)
            if source_is_live is _UNSET:
                source_is_live = is_live_armature_object(source_armature)
                live_sources[source_key] = source_is_live
            if not source_is_live:
                continue
            _rename_vertex_groups_to_meta(obj, rig)
            modifier.object = rig
            redirected_modifiers += 1
            mesh_redirected = True
        if mesh_redirected:
            skinned_meshes += 1
    return skinned_meshes, redirected_modifiers


def build_slot_component_lookups(components):
    lookups = {}
    for component in components or []:
        slots = component.get('slots') if type(component) is dict else None
        name = component_name(component)
        if name and isinstance(slots, list):
            lookups[name] = build_slot_lookup(slots)
    return lookups


class EntityTransformResolver:
    def __init__(
            self, components, parent_transform_lookup, skinning_lookup=None, rig=None, rig_j=None, rig_bone_index=None,
            default_slot_lookup=None, slot_owner_rig_jsons=None, rig_json_by_component_name=None,
            rig_json_by_bone_name=None, armature_by_component_name=None, slot_owner_rig_owner_names=None,
            components_by_name=None, slot_component_lookups=None, component_skin_placements=None,
            ):
        self.components = components or []
        self.components_by_name = components_by_name if components_by_name is not None else build_component_lookup(
            self.components
            )
        self.parent_transform_lookup = parent_transform_lookup or {}
        self.skinning_lookup = skinning_lookup or {}
        self.slot_component_lookups = slot_component_lookups if slot_component_lookups is not None else build_slot_component_lookups(
            self.components
            )
        self.rig = rig
        self.rig_j = rig_j
        self.rig_bone_index = rig_bone_index or rig_bone_index_for(rig_j)
        self.slot_owner_rig_jsons = slot_owner_rig_jsons or {}
        self.rig_json_by_component_name = rig_json_by_component_name or {}
        self.rig_json_by_bone_name = rig_json_by_bone_name or {}
        self.armature_by_component_name = armature_by_component_name or {}
        self.slot_owner_rig_owner_names = slot_owner_rig_owner_names or {}
        self.default_slot_lookup = default_slot_lookup or {}
        self.component_skin_placements = component_skin_placements or {}
        self.cache = {}
        self.local_matrix_cache = {}
        self.binding_cache = {}
        self.slot_matrix_cache = {}
        self.bone_matrix_cache = {}
        self.bone_source_cache = {}
        self.slot_cache = {}
        self.binding_target_cache = {}
        self.resolving = set()
        self.warned_missing_bones = set()

    def _slot_owner_rig_owner_name(self, slot_owner=None):
        if slot_owner and slot_owner in self.slot_owner_rig_owner_names:
            return self.slot_owner_rig_owner_names[slot_owner]
        return ''

    def _slot_owner_rig_json(self, slot_owner=None):
        owner_name = self._slot_owner_rig_owner_name(slot_owner)
        if owner_name:
            rig_json = self.rig_json_by_component_name.get(owner_name)
            if rig_json is not None:
                return rig_json
        if slot_owner and slot_owner in self.slot_owner_rig_jsons:
            return self.slot_owner_rig_jsons[slot_owner]
        return self.rig_j

    def _binding_data(self, component):
        key = id(component)
        binding = self.binding_cache.get(key, _UNSET)
        if binding is _UNSET:
            binding = parent_transform_data(component, self.parent_transform_lookup)
            # Disabled bindings resolve the component at the entity root.
            if type(binding) is dict and binding.get('enabled', 1) == 0:
                binding = None
            self.binding_cache[key] = binding
        return binding

    def _local_matrix(self, component):
        key = id(component)
        matrix = self.local_matrix_cache.get(key)
        if matrix is None:
            transform = component.get('localTransform', {}) if type(component) is dict else {}
            matrix = transform_matrix(transform)
            self.local_matrix_cache[key] = matrix
        return matrix

    def _rig_json_index(self, rig_j):
        return rig_bone_index_for(rig_j)

    def _rig_json_has_bone(self, bone_name, rig_j=None):
        target_name = meta_bone_name(bone_name)
        return bool(target_name and target_name in self._rig_json_index(rig_j))

    def _armature_for_rig_json(self, rig_json, bone_name, preferred_owner=''):
        if rig_json is None:
            return None
        target_name = meta_bone_name(bone_name)
        owner_names = []
        if preferred_owner and self.rig_json_by_component_name.get(preferred_owner) is rig_json:
            owner_names.append(preferred_owner)
        for owner_name, owner_rig_json in self.rig_json_by_component_name.items():
            if owner_rig_json is rig_json and owner_name not in owner_names:
                owner_names.append(owner_name)
        for owner_name in owner_names:
            armature = self.armature_by_component_name.get(owner_name)
            if armature_has_bone(armature, target_name):
                return armature
        if rig_json is self.rig_j and armature_has_bone(self.rig, target_name):
            return self.rig
        return None

    def _pose_bone_fallback_armature(self, bone_name, slot_owner=None):
        if not bone_name or bone_name == 'None':
            return None
        target_name = meta_bone_name(bone_name)
        owner_name = self._slot_owner_rig_owner_name(slot_owner)
        owner = self.armature_by_component_name.get(owner_name) if owner_name else None
        if armature_has_bone(owner, target_name):
            return owner
        if owner is not self.rig and armature_has_bone(self.rig, target_name):
            return self.rig
        return None

    def _bone_source(self, bone_name, slot_owner=None):
        target_name = meta_bone_name(bone_name)
        cache_key = (target_name, slot_owner)
        cached = self.bone_source_cache.get(cache_key, _UNSET)
        if cached is not _UNSET:
            return cached

        # Bone lookup and model-space accumulation use the completed merged hierarchy.
        if self._rig_json_has_bone(target_name, self.rig_j):
            armature = self.rig if armature_has_bone(self.rig, target_name) else None
            result = (self.rig_j, armature)
        else:
            result = (None, self._pose_bone_fallback_armature(target_name, slot_owner))
        self.bone_source_cache[cache_key] = result
        return result

    def _rig_json_for_bone(self, bone_name, slot_owner=None):
        return self._bone_source(bone_name, slot_owner)[0]

    def _armature_for_owner(self, slot_owner=None):
        owner_name = self._slot_owner_rig_owner_name(slot_owner)
        if owner_name:
            armature = self.armature_by_component_name.get(owner_name)
            if is_live_armature_object(armature):
                return armature
        return self.rig if is_live_armature_object(self.rig) else None

    def _armature_world(self, slot_owner=None):
        armature = self._armature_for_owner(slot_owner)
        return armature.matrix_world.copy() if armature is not None else Matrix.Identity(4)

    def bone_matrix(self, bone_name, slot_owner=None):
        target_name = meta_bone_name(bone_name)
        cache_key = (target_name, slot_owner)
        cached = self.bone_matrix_cache.get(cache_key)
        if cached is not None:
            return cached
        rig_json, armature = self._bone_source(target_name, slot_owner)
        if rig_json is not None:
            armature_world = armature.matrix_world.copy() if armature is not None else Matrix.Identity(4)
            matrix = armature_world @ rig_json_bone_matrix(rig_json, target_name, self._rig_json_index(rig_json))
        elif armature is not None and armature_has_bone(armature, target_name):
            matrix = armature.matrix_world @ armature.pose.bones[target_name].matrix
        else:
            if target_name and target_name != 'None' and target_name not in self.warned_missing_bones:
                self.warned_missing_bones.add(target_name)
                print(f"bone '{bone_name}' (MetaRig '{target_name}') not found; resolving at the entity root")
            matrix = self._armature_world(slot_owner)
        self.bone_matrix_cache[cache_key] = matrix
        return matrix

    def resolve_slot_matrix(self, slot_owner, slot_name):
        # Slot transforms are relative to their owning bone.
        cache_key = (slot_owner, slot_name)
        cached = self.slot_matrix_cache.get(cache_key)
        if cached is not None:
            return cached
        slot = self._slot(slot_owner, slot_name)
        if not slot:
            result = (self._owner_component_matrix(slot_owner), slot_owner, slot_name, None)
        else:
            source_bone_name = cname_value(slot.get('boneName'), slot_name)
            bone_name = meta_bone_name(source_bone_name)
            result = (
                self.bone_matrix(source_bone_name, slot_owner) @ transform_matrix(slot),
                bone_name,
                slot_name,
                self._attachment_armature(bone_name, slot_owner),
                )
        self.slot_matrix_cache[cache_key] = result
        return result

    def _attachment_armature(self, bone_name, slot_owner=None):
        if not bone_name or bone_name == 'None':
            return None
        return self._bone_source(bone_name, slot_owner)[1]

    def _rig_owner_armature(self, component_name_value):
        armature = self.armature_by_component_name.get(component_name_value)
        if is_live_armature_object(armature):
            return armature
        return self._armature_for_owner()

    def _owner_component_matrix(self, owner):
        component = self.components_by_name.get(owner)
        if component is None:
            return Matrix.Identity(4)
        return self.resolve_component_matrix(component)[0]

    def _get_binding_target(self, bind_name):
        # A binding targets a component; slot lookup is performed on that component.
        cached = self.binding_target_cache.get(bind_name)
        if cached is not None:
            return cached
        if not bind_name or bind_name == 'None':
            target = 'none'
        elif bind_name in self.components_by_name:
            target = 'component'
        elif bind_name == 'deformation_rig':
            target = 'deformation_rig'
        elif bind_name in ('vehicle_slots', 'slots'):
            target = 'slot'
        elif self._rig_json_for_bone(bind_name) is not None or armature_has_bone(self.rig, meta_bone_name(bind_name)):
            target = 'bone'
        else:
            target = 'unresolved'
        self.binding_target_cache[bind_name] = target
        return target

    def _resolve_parent_target(self, bind_name, slot_name, component=None):
        target_type = self._get_binding_target(bind_name)
        if target_type == 'none':
            return Matrix.Identity(4), bind_name, slot_name, 'none', None

        if target_type == 'deformation_rig':
            armature = self._rig_owner_armature('deformation_rig')
            matrix = armature.matrix_world.copy() if armature is not None else Matrix.Identity(4)
            return matrix, bind_name, slot_name, 'deformation_rig', armature

        if target_type == 'bone':
            target_name = meta_bone_name(bind_name)
            return self.bone_matrix(bind_name), target_name, slot_name, 'bone', self._attachment_armature(bind_name)

        if target_type == 'slot':
            matrix, bone_name, resolved_slot, armature = self.resolve_slot_matrix(bind_name, slot_name)
            return matrix, bone_name, resolved_slot, 'slot', armature

        if target_type == 'component':
            bound_component = self.components_by_name[bind_name]
            if slot_name and slot_name != 'None':
                lookup = self._slot_lookup_for_owner(bind_name)
                if lookup and slot_name in lookup:
                    matrix, bone_name, resolved_slot, armature = self.resolve_slot_matrix(bind_name, slot_name)
                    return matrix, bone_name, resolved_slot, 'slot', armature
            if component is not None and component_uses_skinning(
                    component, self.skinning_lookup
                    ) and self._component_is_rig_owner(bound_component):
                armature = self._rig_owner_armature(bind_name)
                matrix = armature.matrix_world.copy() if armature is not None else Matrix.Identity(4)
                return matrix, bind_name, slot_name, 'skinning_root', armature
            parent_matrix, _, _, _, parent_armature = self.resolve_component_matrix(bound_component)
            return parent_matrix, bind_name, slot_name, 'component', parent_armature

        return Matrix.Identity(4), bind_name, slot_name, 'unresolved', None

    def resolve_binding(self, component):
        binding = self._binding_data(component)
        if type(binding) is not dict:
            # Floating skin targets inherit the transform of their skinning component.
            skin_bind = skinning_bind_name(component, self.skinning_lookup)
            if skin_bind and skin_bind != 'None':
                armature = self._rig_owner_armature(skin_bind)
                matrix = armature.matrix_world.copy() if armature is not None else Matrix.Identity(4)
                return matrix, skin_bind, '', 'skinning_root', armature
            return Matrix.Identity(4), '', '', 'none', None
        bind_name = cname_value(binding.get('bindName'))
        slot_name = cname_value(binding.get('slotName'))
        return self._resolve_parent_target(bind_name, slot_name, component=component)

    def resolve_component_matrix(self, component):
        # All binding types compose world transforms as parent multiplied by local.
        # Skinned components use the armature that supplied the parent transform.
        key = id(component)
        cached = self.cache.get(key)
        if cached is not None:
            return cached
        if key in self.resolving:
            return Matrix.Identity(4), '', '', 'cycle', None
        self.resolving.add(key)
        parent_matrix, bind_name, slot_name, binding_type, attach_armature = self.resolve_binding(component)
        matrix = parent_matrix @ self._local_matrix(component)
        skin_placement = self.component_skin_placements.get(key)
        if skin_placement is not None:
            matrix = matrix @ skin_placement
        result = (matrix, bind_name, slot_name, binding_type, attach_armature)
        self.cache[key] = result
        self.resolving.discard(key)
        return result

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

    def _component_is_rig_owner(self, component):
        return type(component) is dict and bool(depot_path_value(component, 'rig'))


def importEnt(
        with_materials, filepath='', appearances=None, exclude_meshes=None, include_collisions=False,
        include_phys=False,
        include_entCollider=False, inColl='', remap_depot=None, escaped_path=None, meshes=None, mesh_jsons=None,
        app_path=None, anim_files=None,
        rigjsons=None, generate_overrides=False,
        ):
    cp77_addon_prefs = bpy.context.preferences.addons['i_scene_cp77_gltf'].preferences
    if appearances is None:
        appearances = ['']
    elif isinstance(appearances, str):
        appearances = [appearances]
    else:
        appearances = list(appearances)
    if not appearances:
        appearances = ['']
    if include_collisions and not include_phys and not include_entCollider:
        include_entCollider = True
    excluded_meshes = {norm_path_key(mesh) for mesh in (exclude_meshes or []) if mesh}
    if not cp77_addon_prefs.non_verbose:
        print('\n-------------------- Importing Cyberpunk 2077 Entity --------------------')
    C = bpy.context
    coll_scene = C.scene.collection
    start_time = time.time()
    clear_transient_import_caches()

    path, after = split_source_raw_root(filepath)
    # Top-level imports rescan the export tree so files created since the last import are
    # visible; nested calls (per-entity imports inside a sector batch) reuse the shared index.
    asset_index = DepotAssetIndex.cached(path, DEFAULT_ASSET_EXTENSIONS, force_refresh=not JSONTool._use_cache)

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
            if app.lower() == 'random':
                if ent_applist:
                    appearances[appidx] = random.choice(ent_applist)
                    print(f"Random appearance requested: using {appearances[appidx]}")
                else:
                    print("No appearances available for a random selection. Importing root entity components only.")
                    appearances[appidx] = 'BASE_COMPONENTS_ONLY'
                continue
            if app == 'default':
                if ent_default:
                    resolved_default = resolve_requested_appearance_name(
                        app, ent_default, ent_apps, ent_app_by_appearance, ent_app_by_name
                        )
                    print(f"Using default appearance {resolved_default} for entity {ent_name}.")
                    continue
                if ent_applist:
                    print(
                        f"No default appearance specified in entity {ent_name}. Using first available appearance {ent_applist[0]}."
                        )
                    ent_default = ent_applist[0]
                    continue
                print(f"No appearances specified in entity {ent_name}. Using root entities.")
                appearances[appidx] = 'BASE_COMPONENTS_ONLY'
                continue
            if not appearance_request_is_known(app, ent_default, ent_apps, ent_app_by_appearance, ent_app_by_name):
                print(
                    f"Appearance {app} not found in entity {ent_name}. Available appearances: {', '.join(ent_applist)}"
                    )

        ent_animated_components = [component for component in ent_components if is_animated_rig_component(component)]
        ent_rigs = []
        for component in ent_animated_components:
            ent_rig_depot = depot_path_value(component, 'rig')
            print(f"Animated-component rig found in entity: {ent_rig_depot}")
            ent_rigs.append(depot_to_local_path(path, ent_rig_depot))
        ent_colliderComps = parsed_ent.collider_components
        ent_simpleCollComps = parsed_ent.simple_collider_components
        chassis_info = parsed_ent.components_by_name.get('Chassis')

        if len(appearances[0]) == 0 or appearances[0].upper() == 'ALL':
            # Ent files may repeat appearanceName across aliases; import each appearance once.
            appearances = list(dict.fromkeys(ent_applist))
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

        # Animation GLBs are imported later for their animation data only. The entity rig
        # is always constructed exclusively from JSON rigs.
        rigjsons = indexed_asset_files(asset_index, '.rig.json', rigjsons)
        rig_j = None
        rig_bone_index = {}

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
            appearance_only_components = {}
            ent_chunks = {}
            parsed_app_cache = {}
            app_lookup = {}
            app_bundle_lookup = {}
            app_resource_lookup = {}
            display_app_names = {}
            component_mesh_info_cache = {}
            component_mesh_json_cache = {}
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
                if component.get('$type') in NON_VISUAL_MESH_COMPONENT_TYPES:
                    depot_path = ''
                else:
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

            def component_mesh_json(component):
                cached_info = component_mesh_info_cache.get(id(component))
                depot_path = cached_info[0] if cached_info is not None else depot_path_value(
                    component, 'mesh', 'graphicsMesh'
                    )
                if not depot_path:
                    return None
                cached = component_mesh_json_cache.get(depot_path, _UNSET)
                if cached is not _UNSET:
                    return cached
                json_path = asset_index.resolve_export(depot_path, '.mesh.json') or ''
                root = load_root_chunk_json(json_path, error_messages) if json_path else None
                component_mesh_json_cache[depot_path] = root
                return root

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
                app_name = resolve_requested_appearance_name(
                    requested_app_name, ent_default, ent_apps, ent_app_by_appearance, ent_app_by_name
                    )
                display_app_names[requested_app_name] = app_name
                app_comps[requested_app_name] = []
                appearance_only_components[requested_app_name] = []
                chunks = None
                if requested_app_name == 'BASE_COMPONENTS_ONLY':
                    # Root entity components only: never resolve or merge an .app appearance.
                    chunks = ent_component_data or None
                elif len(ent_apps) == 0 and ent_component_data:
                    chunks = ent_component_data
                elif len(ent_apps) > 0:
                    ent_app_idx, app_name = resolve_ent_app(
                        app_name, ent_apps, ent_app_by_appearance, ent_app_by_name, ent_default
                        )
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
                            app_idx = parsed_app.appearances_by_name.get(app_name)
                            if app_idx is None:
                                available = ', '.join(parsed_app.appearance_names)
                                print(
                                    f"appearance '{app_name}' not found in {os.path.basename(appfilepath)}; available: {available}"
                                    )
                            else:
                                parsed_app_name = app_name
                                print('appearance matched, id = ', app_idx)
                                app_components = parsed_app.components_by_appearance_name.get(parsed_app_name, [])
                                store_for_names(
                                    appearance_only_components, app_components, requested_app_name, app_name
                                    )
                                if app_components:
                                    store_for_names(
                                        app_comps, merge_components_first_wins(ent_components, app_components),
                                        requested_app_name, app_name
                                        )
                                chunks = parsed_app.chunks_by_appearance_name.get(parsed_app_name)
                                store_for_names(
                                    app_bundle_lookup, (parsed_app, parsed_app_name), requested_app_name, app_name
                                    )
                                if chunks:
                                    store_for_names(ent_chunks, chunks, requested_app_name, app_name)
                                    print('Chunks found')

                if len(app_comps[requested_app_name]) == 0:
                    print('falling back to rootchunk components...')
                    store_for_names(app_comps, ent_components, requested_app_name, app_name)
                if chunks is not None and requested_app_name not in ent_chunks:
                    ent_chunks[requested_app_name] = chunks
                for c in app_comps[requested_app_name]:
                    # Components with a resolved zero chunk mask are omitted.
                    if component_is_zero_mask_culled(c):
                        continue
                    depot_path, meshname, meshpath, meshApp, _ = component_mesh_info(c)
                    if depot_path and meshname and meshpath and not is_excluded_mesh(
                            depot_path, meshpath, meshname, excluded_meshes
                            ):
                        mesh_key = depot_to_local_path(path, depot_path)
                        entry = mesh_entries.get(mesh_key)
                        if entry is None:
                            mesh_entries[mesh_key] = {'appearances': [meshApp], 'sector': 'ALL', 'meshpath': meshpath}
                        else:
                            entry['appearances'].append(meshApp)
                            if meshpath and not entry.get('meshpath'):
                                entry['meshpath'] = meshpath

            # Build the entity animation rig from JSON only. Component order is
            # authoritative: the first entAnimatedComponent in the entity is the base;
            # only when the entity has none does the first selected appearance supply it.
            ordered_rig_components = []
            seen_rig_components = set()
            control_targets = {}

            def append_animated_rig_components(source_components, control_binding_lookup=None):
                for component in source_components or ():
                    if not is_animated_rig_component(component):
                        continue
                    component_id = id(component)
                    if component_id in seen_rig_components:
                        continue
                    seen_rig_components.add(component_id)
                    ordered_rig_components.append(component)
                    control_targets[component_id] = animated_component_control_target(
                            component, control_binding_lookup
                            )

            ent_control_binding_lookup = build_embedded_handle_lookup(
                    parsed_ent.component_data, 'controlBinding'
                    )
            append_animated_rig_components(ent_components, ent_control_binding_lookup)
            for requested_app_name in appearances:
                resolved_app_name = display_app_names.get(requested_app_name, requested_app_name)
                appearance_components = appearance_only_components.get(requested_app_name)
                if appearance_components is None:
                    appearance_components = appearance_only_components.get(resolved_app_name, [])
                parsed_app_bundle = app_bundle_lookup.get(requested_app_name)
                if parsed_app_bundle is None:
                    parsed_app_bundle = app_bundle_lookup.get(resolved_app_name)
                if parsed_app_bundle is not None:
                    parsed_app, parsed_app_name = parsed_app_bundle
                    appearance_chunks = parsed_app.chunks_by_appearance_name.get(parsed_app_name, [])
                    app_control_binding_lookup = build_embedded_handle_lookup(
                            appearance_chunks, 'controlBinding'
                            )
                else:
                    app_control_binding_lookup = None
                append_animated_rig_components(appearance_components, app_control_binding_lookup)

            ordered_rig_components = order_animated_rig_components(
                    ordered_rig_components, control_targets
                    )
            deformation_authorities = []
            ordered_by_name = {component_name(component): component for component in ordered_rig_components}
            for component in ordered_rig_components:
                if not is_deformation_rig_component(component):
                    continue
                target_name = control_targets.get(id(component), '')
                if target_name in ordered_by_name and target_name not in deformation_authorities:
                    deformation_authorities.append(target_name)
            if deformation_authorities:
                print('JSON MetaRig deformation base authority: ' + ', '.join(deformation_authorities))
            print(
                'JSON MetaRig component order: ' + ' -> '.join(
                        component_name(component, '<unnamed>') for component in ordered_rig_components
                        )
                )

            ordered_rig_names = []
            ordered_rig_paths = []
            ordered_rig_jsons = []
            ordered_rig_datas = []
            ordered_rig_entries = []
            for component in ordered_rig_components:
                rig_name = component_name(component)
                rig_depot = depot_path_value(component, 'rig')
                rig_json_path = rig_json_path_for_depot(rig_depot)
                rig_json = rig_json_for_depot(rig_depot)
                rig_data = read_rig(rig_json_path) if rig_json_path else None
                if not rig_name or not rig_json_path or rig_json is None or rig_data is None:
                    print(f"unable to load JSON rig for animated component '{rig_name or '<unnamed>'}': {rig_depot}")
                    continue
                if rig_name not in rig_json_path_by_component_name:
                    rig_json_path_by_component_name[rig_name] = rig_json_path
                    rig_json_by_component_name[rig_name] = rig_json
                    ordered_rig_names.append(rig_name)
                ordered_rig_paths.append(rig_json_path)
                ordered_rig_jsons.append(rig_json)
                ordered_rig_datas.append(rig_data)
                ordered_rig_entries.append((rig_name, rig_json_path, rig_json, rig_data))

            base_rig_component = ordered_rig_components[0] if ordered_rig_components else None
            base_rig_name = component_name(base_rig_component) if base_rig_component else ''
            base_rig_path = rig_json_path_by_component_name.get(base_rig_name, '')

            # Resolve the animation set now, then import it only after the JSON MetaRig exists.
            animation_path = ''
            animation_source_component = None
            for component in ordered_rig_components:
                gameplay_anims = component.get('animations', {}).get('gameplay')
                if not gameplay_anims:
                    continue
                try:
                    anim_depot = gameplay_anims[0]['animSet']['DepotPath']['$value']
                except (KeyError, IndexError, TypeError):
                    continue
                animation_path = asset_index.resolve_export(anim_depot, '.anims.glb') or ''
                if animation_path:
                    animation_source_component = component
                    break

            if not animation_path and base_rig_component is not None:
                base_rig_depot = depot_path_value(base_rig_component, 'rig')
                base_rig_key = norm_path_key(depot_to_local_path(path, base_rig_depot))
                for anim_path in anim_files:
                    anim_json_path = asset_index.resolve_export(anim_path, '.anims.json')
                    if not anim_json_path:
                        continue
                    anim_json = JSONTool.jsonload(anim_json_path, error_messages)
                    anim_rig_depot = (
                        anim_json.get('Data', {}).get('RootChunk', {}).get('rig', {}).get('DepotPath', {}).get('$value')
                        if anim_json is not None else ''
                    )
                    if anim_rig_depot and norm_path_key(depot_to_local_path(path, anim_rig_depot)) == base_rig_key:
                        animation_path = anim_path
                        animation_source_component = base_rig_component
                        break

            animation_source_rig_path = ''
            if animation_path:
                source_rig_name = component_name(
                    animation_source_component
                    ) if animation_source_component else base_rig_name
                animation_source_rig_path = rig_json_path_by_component_name.get(source_rig_name, base_rig_path)
            else:
                print('no animation GLB found for the ordered animated components')

            rig_json_by_bone_name = {}
            meta_rig_metadata = {}
            if ordered_rig_datas and base_rig_path:
                merged_rig_data, meta_rig_metadata = merge_rig_datas(
                        ordered_rig_datas,
                        (ent_name + '_rig') if ent_name else 'merged_rig',
                        return_metadata=True,
                        )
                merged_rig_json = rig_data_to_root_chunk(merged_rig_data)
                rig = ensure_armature_from_rig_jsons(ordered_rig_paths, ent_name)
                if is_live_armature_object(rig):
                    cache_armature_bones(rig)
                    for rig_name in ordered_rig_names:
                        armature_by_component_name[rig_name] = rig
                    # Transform and slot evaluation must use the MetaRig's merged local pose
                    # and merged parent array, not any source rig's original model-space pose.
                    rig_j = merged_rig_json
                    rig_bone_index = rig_bone_index_for(rig_j)
                    rig['base_rig_component'] = base_rig_name
                    rig['base_rig_json'] = base_rig_path
                    rig['rig_merge_order'] = list(ordered_rig_paths)
                    rig['meta_rig_bone_count'] = len(merged_rig_data.bone_names)
                    print(f"JSON MetaRig base: {base_rig_name} ({os.path.basename(base_rig_path)})")
                    for merge_index, rig_path in enumerate(ordered_rig_paths[1:], start=1):
                        print(f"JSON MetaRig part {merge_index}: {os.path.basename(rig_path)}")
                else:
                    print('failed to create the JSON MetaRig armature')

                # Resolve both authored source names and MetaRig names to the merged pose.
                for meta_name, source in meta_rig_metadata.get('bone_sources', {}).items():
                    rig_json_by_bone_name.setdefault(meta_name, merged_rig_json)
                    source_name = source.get('source_name')
                    if source_name:
                        rig_json_by_bone_name.setdefault(source_name, merged_rig_json)
            elif ordered_rig_components:
                print(f"base animated component '{base_rig_name}' has no usable JSON rig; no entity rig was created")
            else:
                print('no entAnimatedComponent rig found in the entity or selected appearances')

            if animation_path:
                if not is_live_armature_object(rig):
                    message = (
                        f"animation set '{os.path.basename(animation_path)}' could not be imported "
                        "because the JSON MetaRig was not created"
                    )
                    print(message)
                    error_messages.append(message)
                else:
                    try:
                        import_animset_to_metarig(
                                animation_path,
                                rig,
                                animation_source_rig_path,
                                ent_name,
                                import_tracks=True,
                                )
                    except Exception as exc:
                        message = (
                            f"direct animation import failed for "
                            f"'{os.path.basename(animation_path)}': {exc}"
                        )
                        print(message)
                        print(traceback.format_exc())
                        error_messages.append(message)

            meshes_w_apps = {}
            for m in mesh_entries:
                add_to_list(m, mesh_entries, meshes_w_apps)

            meshes_from_mesheswapps(
                meshes_w_apps, path, from_mesh_no=0, to_mesh_no=10000000, with_mats=with_materials, glbs=mesh_entries,
                mesh_jsons=mesh_jsons,
                Masters=Masters, generate_overrides=generate_overrides
                )

            imported_appearance_collections = []
            for x, requested_app_name in enumerate(appearances):
                app_name = display_app_names.get(requested_app_name, requested_app_name)
                print(f"\nImporting appearance {x + 1} of {len(appearances)}: {app_name}")
                app_start_time = time.time()
                ent_coll = bpy.data.collections.new(ent_name + '_' + app_name)
                app_name = app_lookup.get(requested_app_name, app_name)
                if inColl and inColl in coll_scene.children:
                    bpy.data.collections.get(inColl).children.link(ent_coll)
                else:
                    coll_scene.children.link(ent_coll)
                ent_coll['depotPath'] = after
                imported_appearance_collections.append(ent_coll)
                app_bundle = app_bundle_lookup.get(requested_app_name) or app_bundle_lookup.get(app_name)
                chunks = ent_chunks.get(requested_app_name) or ent_chunks.get(app_name) or ent_component_data

                current_app_resource = app_resource_lookup.get(requested_app_name) or app_resource_lookup.get(
                    app_name
                    ) or app_resource
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
                    app_parent_transform_lookup = parsed_app.parent_transform_lookup_by_appearance_name.get(
                        parsed_app_name, {}
                        )
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
                    if not is_animated_rig_component(comp):
                        continue
                    rig_name = component_name(comp)
                    if rig_name and rig_name not in rig_json_path_by_component_name:
                        # All selected appearance rigs should have been discovered before the
                        # JSON armature was built. Do not mutate the merge order per appearance.
                        print(
                            f"animated component '{rig_name}' was not present in the ordered JSON rig prepass; leaving it unmerged"
                            )
                rig_component_names = set(rig_json_by_component_name.keys())
                slot_owner_rig_jsons, slot_owner_rig_owner_names = build_slot_owner_binding_maps(
                        transform_index['slot_components'],
                        parent_transform_lookup,
                        rig_json_by_component_name,
                        rig_component_names,
                        )
                anim_impl_lookup = build_anim_impl_lookup(chunks)
                transform_animator_lookup = build_transform_animator_lookup(
                        transform_index['transform_animator_components'], anim_impl_lookup
                        )

                for c in appearance_index['slot_components']:
                    if component_name(c) in ('vehicle_slots', 'slot', 'slots') and id(
                            c
                            ) not in vehicle_slot_component_ids:
                        VS.append(c)
                        vehicle_slot_component_ids.add(id(c))

                if not vehicle_slots:
                    if len(VS) > 0:
                        vehicle_slots = VS[0]['slots']
                        vehicle_slot_lookup = build_slot_lookup(vehicle_slots)

                light_channel_components = collect_light_channel_components(
                    app_light_channels, chunks, comps, parsed_ent.light_channel_components, ent_components
                    )
                light_components = collect_light_components(ent_component_data, ent_components, chunks, comps)
                auxiliary_components = light_channel_components + light_components
                for comp in auxiliary_components:
                    if id(comp) in ent_component_ids or id(comp) in ent_component_data_ids:
                        set_parent_lookup(comp, ent_parent_transform_lookup)
                        set_skinning_lookup(comp, ent_skinning_lookup)
                        set_shape_lookup(comp, ent_shape_lookup)
                resolver_components_by_id = dict(transform_components_by_id)
                for comp in auxiliary_components:
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

                component_skin_placements = {}
                component_skin_placement_info = {}
                if rig_j is not None:
                    for component in resolver_index['mesh_components']:
                        if not component_uses_skinning(component, skinning_lookup):
                            continue
                        placement, root_bone, status = component_skin_attachment_matrix(
                                component_mesh_json(component),
                                rig_j,
                                )
                        component_skin_placement_info[id(component)] = (root_bone, status)
                        if placement is not None:
                            component_skin_placements[id(component)] = placement

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
                        rig_json_by_bone_name=rig_json_by_bone_name,
                        armature_by_component_name=armature_by_component_name,
                        slot_owner_rig_owner_names=slot_owner_rig_owner_names,
                        components_by_name=resolver_components_by_name,
                        slot_component_lookups=resolver_slot_component_lookups,
                        component_skin_placements=component_skin_placements,
                        )

                for c in appearance_index['transform_animator_components']:
                    comp_name = component_name(c)
                    try:
                        ensure_transform_animator_empty(ent_coll, comp_name, transform_animator_lookup.get(comp_name))
                    except Exception:
                        print('Failed on animator component ', comp_name)
                        print(traceback.format_exc())

                for c in appearance_index['mesh_components']:
                    # Components with a resolved zero chunk mask are omitted.
                    if component_is_zero_mask_culled(c):
                        continue
                    comp_name = component_name(c)
                    depot_path, meshname, meshpath, meshApp, component_enabled = component_mesh_info(c)
                    if meshname and meshpath and not is_excluded_mesh(depot_path, meshpath, meshname, excluded_meshes):
                        new = None
                        hide_disabled = not component_enabled
                        try:
                            group, groupname = get_group(meshpath, meshApp, Masters, source_glb=meshpath)
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
                            resolved_matrix, bindname, slotname, binding_type, attach_armature = transform_resolver.resolve_component_matrix(
                                c
                                )
                            skin_root_bone, skin_attachment_status = component_skin_placement_info.get(
                                id(c), ('', 'not_applicable')
                                )
                            component_scale = visual_scale_matrix(c)
                            if component_scale is not None:
                                resolved_matrix = resolved_matrix @ component_scale
                            can_bind_bone = (
                                    not component_is_skinned
                                    and binding_type in {'slot', 'bone'}
                                    and bindname
                                    and attach_armature is not None
                            )
                            child_inverse = child_of_inverse_matrix(
                                attach_armature, bindname
                                ) if can_bind_bone else None
                            transform_animator_name, transform_animator_info_value = component_transform_animator_info(
                                c, parent_transform_lookup, transform_animator_lookup
                                )
                            transform_animator_target = ensure_transform_animator_empty(
                                ent_coll, transform_animator_name, transform_animator_info_value
                                ) if transform_animator_info_value is not None else None
                            has_bindname = bool(bindname)
                            has_slotname = bool(slotname)
                            cm_int = chunk_mask_value(c)
                            copied_object_set = set(objs)
                            for obj in objs:
                                obj['bindingType'] = binding_type
                                if has_bindname:
                                    obj['bindname'] = bindname
                                if has_slotname:
                                    obj['slotName'] = slotname
                                obj['deformationRigSkinning'] = component_is_skinned
                                if component_is_skinned:
                                    obj['skinAttachmentStatus'] = skin_attachment_status
                                    if skin_root_bone:
                                        obj['skinAttachmentRootBone'] = skin_root_bone
                                if cm_int is not None:
                                    submesh_index = submesh_index_for_object(obj)
                                    if submesh_index is not None:
                                        hidden = hide_disabled or not bool((cm_int >> submesh_index) & 1)
                                        obj.hide_viewport = hidden
                                        obj.hide_render = hidden
                                elif hide_disabled:
                                    obj.hide_viewport = True
                                    obj.hide_render = True
                                if obj.parent in copied_object_set:
                                    # Hierarchy children follow their copied parent; transforming
                                    # them again would apply the component transform twice.
                                    continue
                                obj.matrix_world = resolved_matrix @ obj.matrix_world
                                if can_bind_bone:
                                    configure_child_of_constraint(obj, attach_armature, bindname, child_inverse)
                                if transform_animator_target is not None:
                                    add_rotation_axis_driver(
                                        obj, transform_animator_target, transform_animator_info_value['axis_no']
                                        )
                            if component_is_skinned:
                                bind_skinned_objects_to_rig(objs, rig)

                            if objs:
                                new['depotPath'] = depot_path
                                new['meshAppearance'] = meshApp
                                if 'meshpath' not in new:
                                    new['meshpath'] = "its an entity"
                                if bindname:
                                    new['bindname'] = bindname

                            if new is not None:
                                ent_coll.children.link(new)

                        except Exception:
                            print("Failed on ", meshname)
                            print(traceback.format_exc())
                            if new is not None and ent_coll.children.get(new.name) is None:
                                for obj in list(new.objects):
                                    bpy.data.objects.remove(obj, do_unlink=True)
                                bpy.data.collections.remove(new, do_unlink=True)

                if light_components:
                    light_collection = bpy.data.collections.new(ent_coll.name + '_lights')
                    light_collection['nodeType'] = 'entLightComponent, vehicleLightComponent'
                    light_collection['entAppearance'] = app_name
                    ent_coll.children.link(light_collection)

                    for c in light_components:
                        light_obj = create_entity_light(c, filepath)
                        light_collection.objects.link(light_obj)

                        resolved_matrix, bindname, slotname, binding_type, attach_armature = transform_resolver.resolve_component_matrix(
                            c
                            )
                        if light_obj.data.type in {'SPOT', 'AREA', 'SUN'}:
                            resolved_matrix = resolved_matrix @ _LIGHT_DIRECTION_CORRECTION
                        light_obj.matrix_world = resolved_matrix @ light_obj.matrix_world
                        light_obj['bindingType'] = binding_type
                        if bindname:
                            light_obj['bindname'] = bindname
                        if slotname:
                            light_obj['slotName'] = slotname

                        component_enabled = is_component_enabled(c)
                        light_obj['componentEnabled'] = component_enabled
                        if not component_enabled:
                            light_obj.hide_viewport = True
                            light_obj.hide_render = True

                        if binding_type in {'slot', 'bone'} and bindname and attach_armature is not None:
                            configure_child_of_constraint(
                                light_obj, attach_armature, bindname, child_of_inverse_matrix(attach_armature, bindname)
                                )

                        transform_animator_name, transform_animator_info_value = component_transform_animator_info(
                            c, parent_transform_lookup, transform_animator_lookup
                            )
                        if transform_animator_info_value is not None:
                            transform_animator_target = ensure_transform_animator_empty(
                                ent_coll, transform_animator_name, transform_animator_info_value
                                )
                            add_rotation_axis_driver(
                                light_obj, transform_animator_target, transform_animator_info_value['axis_no']
                                )

                for c in light_channel_components:
                    lcgroupname = component_name(c) or 'LightChannel'
                    mesh_obj = create_light_channel_mesh(c, shape_lookup, filepath)
                    if mesh_obj is None:
                        continue

                    lcgroup = bpy.data.collections.new(lcgroupname)
                    lcgroup.objects.link(mesh_obj)

                    resolved_matrix, bindname, slotname, binding_type, attach_armature = transform_resolver.resolve_component_matrix(
                        c
                        )
                    component_scale = visual_scale_matrix(c)
                    if component_scale is not None:
                        resolved_matrix = resolved_matrix @ component_scale
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

                    if binding_type in {'slot', 'bone'} and bindname and attach_armature is not None:
                        configure_child_of_constraint(
                            mesh_obj, attach_armature, bindname, child_of_inverse_matrix(attach_armature, bindname)
                            )

                    lcgroup['componentName'] = lcgroupname
                    lcgroup['nodeType'] = 'entLightChannelComponent'
                    lcgroup['bindingType'] = binding_type
                    lcgroup['entAppearance'] = app_name
                    ent_coll.children.link(lcgroup)
                print('Appearance import time:', time.time() - app_start_time, 'Seconds')

            collision_transform_resolver = None
            if include_collisions and include_entCollider and (ent_colliderComps or ent_simpleCollComps):
                collision_components = list(ent_components)
                collision_components.extend(ent_component_data)
                collision_components_by_name = dict(base_components_by_name)
                for component in ent_component_data:
                    name = component_name(component)
                    if name:
                        collision_components_by_name.setdefault(name, component)
                collision_parent_lookup = ComponentHandleLookup(ent_parent_transform_lookup)
                collision_skinning_lookup = ComponentHandleLookup(ent_skinning_lookup)
                base_slot_components = [
                    component
                    for component in ent_components
                    if isinstance(component, dict) and isinstance(component.get('slots'), list)
                    ]
                collision_slot_owner_jsons, collision_slot_owner_names = build_slot_owner_binding_maps(
                        base_slot_components,
                        collision_parent_lookup,
                        rig_json_by_component_name,
                        set(rig_json_by_component_name),
                        )
                collision_transform_resolver = EntityTransformResolver(
                        collision_components,
                        collision_parent_lookup,
                        skinning_lookup=collision_skinning_lookup,
                        rig=rig,
                        rig_j=rig_j,
                        rig_bone_index=rig_bone_index,
                        default_slot_lookup=vehicle_slot_lookup,
                        slot_owner_rig_jsons=collision_slot_owner_jsons,
                        rig_json_by_component_name=rig_json_by_component_name,
                        rig_json_by_bone_name=rig_json_by_bone_name,
                        armature_by_component_name=armature_by_component_name,
                        slot_owner_rig_owner_names=collision_slot_owner_names,
                        components_by_name=collision_components_by_name,
                        slot_component_lookups=base_slot_component_lookups,
                        )

            if include_collisions:
                collision_target_collection = imported_appearance_collections[
                    0] if imported_appearance_collections else coll_scene
                if include_phys:
                    try:
                        physJsonPaths = asset_index.get_files_by_extension('.phys.json')
                        if len(physJsonPaths) == 0:
                            print('No phys file JSONs found in path')
                        elif not isinstance(chassis_info, dict):
                            print('No valid Chassis component in entity; skipping chassis collision import')
                        else:
                            chassis_matrix = transform_matrix(chassis_info.get('localTransform', {}))
                            chassis_phys_j = os.path.basename(
                                    chassis_info['collisionResource']['DepotPath']['$value']
                                    ) + '.json'
                            for physJsonPath in physJsonPaths:
                                if os.path.basename(physJsonPath) == chassis_phys_j:
                                    cp77_phys_import_into_collection(
                                            physJsonPath,
                                            rig=rig,
                                            target_collection=collision_target_collection,
                                            actor_matrix=chassis_matrix,
                                            context=bpy.context,
                                            )
                    except Exception as e:
                        print(e)

                if include_entCollider:
                    _import_registered_entity_colliders(
                            ent_colliderComps + ent_simpleCollComps,
                            collision_transform_resolver,
                            (ent_components, ent_component_data),
                            collision_target_collection,
                            bpy.context,
                            )
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
    return {'FINISHED'}
