import bpy
import json
import os
import re
from functools import lru_cache
from pathlib import Path
from .main.common import show_message, load_zip
from .main.datashards import ParsedApp, ParsedEntity


# Error messages for different file types
invalid_json_error = (
    "This plugin requires JSONs generated with WolvenKit 8.17 or newer.\n"
    "Please re-export your files using a compatible WolvenKit version.\n\n"
    "Download links:\n"
    "• Latest stable: https://github.com/WolvenKit/WolvenKit/releases/latest\n"
    "• Nightly builds (recommended): https://github.com/WolvenKit/WolvenKit-nightly-releases/releases"
)
invalid_material_error = "Import will continue, but shaders may be incorrectly set up for these objects."
invalid_phys_error = "Import may continue, but .phys colliders will not be imported."

MIN_WOLVENKIT_VERSION = (8, 17)
MIN_MATERIAL_JSON_VERSION = (1, 0)



def _cname_value(value, default=''):
    if type(value) is dict:
        return value.get('$value', default)
    return value if value is not None else default


def _component_name(component, default=''):
    if type(component) is not dict:
        return default
    return _cname_value(component.get('name'), default)


def _build_component_lookup(components):
    lookup = {}
    for component in components or ():
        name = _component_name(component)
        if name:
            # Preserve the first component registered under each name.
            lookup.setdefault(name, component)
    return lookup


def _build_app_lookup(appearances):
    by_appearance = {}
    by_name = {}
    appearance_names = []
    for index, app in enumerate(appearances or ()): 
        if type(app) is not dict:
            continue
        appearance = _cname_value(app.get('appearanceName'))
        if appearance:
            # Preserve the first appearance registered under each name.
            by_appearance.setdefault(appearance, index)
            appearance_names.append(appearance)
        name = _cname_value(app.get('name'))
        if name:
            by_name.setdefault(name, index)
    return appearance_names, by_appearance, by_name


def _build_chunk_lookup(chunks, target_key, handle_key='HandleId'):
    lookup = {}
    for chunk in chunks or ():
        if type(chunk) is not dict:
            continue
        target = chunk.get(target_key)
        if type(target) is dict and handle_key in target:
            lookup[target[handle_key]] = target
    return lookup


def _build_slot_lookup(slots):
    lookup = {}
    for slot in slots or ():
        if type(slot) is not dict:
            continue
        name = _cname_value(slot.get('slotName'))
        if name:
            # Preserve the first slot registered under each name.
            lookup.setdefault(name, slot)
    return lookup


def _build_slot_component_lookups(components):
    lookups = {}
    for component in components or ():
        if type(component) is not dict:
            continue
        name = _component_name(component)
        slots = component.get('slots')
        if name and type(slots) is list:
            lookups.setdefault(name, _build_slot_lookup(slots))
    return lookups


def ent_appearance_name(ent_app, default=''):
    return _cname_value(ent_app.get('appearanceName'), default) if type(ent_app) is dict else default


def _ent_template_appearance_name(ent_app, default=''):
    return _cname_value(ent_app.get('name'), default) if type(ent_app) is dict else default


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
        template_name = _ent_template_appearance_name(ent_app)
        if app_name == appearance_name or app_name == template_name:
            return ent_app_idx, appearance_name or app_name

    return -1, ''


def resolve_requested_appearance_name(app_name, ent_default, ent_apps, by_appearance, by_name):
    if app_name == 'default':
        if not ent_default:
            return 'default'
        _, resolved_name = resolve_ent_appearance_alias(ent_default, ent_apps, by_appearance, by_name)
        return resolved_name or ent_default

    _, resolved_name = resolve_ent_appearance_alias(app_name, ent_apps, by_appearance, by_name)
    return resolved_name or app_name


def _components_by_type(components, type_name):
    return [component for component in components or () if type(component) is dict and component.get('$type') == type_name]


def _normalize_default_appearance(default_appearance, appearances, by_appearance, by_name):
    if not default_appearance or default_appearance == 'None':
        return ''
    if default_appearance in by_appearance or default_appearance == 'random':
        return default_appearance
    by_name_idx = by_name.get(default_appearance, -1)
    if by_name_idx >= 0:
        return _cname_value(appearances[by_name_idx].get('appearanceName'), default_appearance)
    return default_appearance


@lru_cache(maxsize=8192)
def _full_suffix(base_name):
    return ''.join(Path(base_name).suffixes)


class JSONTool:
    _json_cache = {}
    _entity_cache = {}
    _app_cache = {}
    _use_cache = False

    cachable_types = {
        '.ent.json',
        '.anims.json',
        '.app.json',
        '.streamingblock.json',
        '.mesh.json',
        '.gradient.json',
        '.rig.json',
        '.cfoliage.json',
        '.hp.json',
        '.phys.json',
        '.mlsetup.json',
        '.mltemplate.json',
        '.mt.json',
        '.mi.json',
    }

    passthrough_errors = {
        '.ent.json': invalid_json_error,
        '.anims.json': invalid_json_error,
        '.app.json': invalid_json_error,
        '.streamingblock.json': invalid_json_error,
        '.mesh.json': invalid_json_error,
        '.gradient.json': invalid_json_error,
        '.rig.json': invalid_json_error,
        '.cfoliage.json': invalid_json_error,
        '.hp.json': invalid_json_error,
        '.phys.json': invalid_phys_error,
        '.mlsetup.json': invalid_material_error,
        '.mltemplate.json': invalid_material_error,
        '.mt.json': invalid_material_error,
        '.mi.json': invalid_material_error,
    }

    @staticmethod
    def normalize_paths(data):
        separator = os.sep

        def normalize(value):
            if isinstance(value, dict):
                for key, item in value.items():
                    value[key] = normalize(item)
                return value

            if isinstance(value, list):
                for index, item in enumerate(value):
                    value[index] = normalize(item)
                return value

            if isinstance(value, str):
                if value.startswith(('base', 'ep1')) or value[1:3] == ':\\':
                    return value.replace('\\', separator)

            return value

        return normalize(data)

    @staticmethod
    def _version_components(version_string):
        if version_string is None:
            return None

        match = re.search(r'\d+(?:\.\d+)*', str(version_string))
        if match is None:
            return None

        return tuple(int(part) for part in match.group().split('.'))

    @staticmethod
    def _version_at_least(version_string, minimum):
        components = JSONTool._version_components(version_string)
        if components is None:
            return False

        width = max(len(components), len(minimum))
        components += (0,) * (width - len(components))
        minimum += (0,) * (width - len(minimum))
        return components >= minimum

    @staticmethod
    def json_ver_validate(json_data):
        if not isinstance(json_data, dict):
            return False

        header = json_data.get('Header')
        if not isinstance(header, dict):
            return False

        version_fields = {
            'MaterialJsonVersion': MIN_MATERIAL_JSON_VERSION,
            'WolvenKitVersion': MIN_WOLVENKIT_VERSION,
        }
        found_version = False

        for field, minimum in version_fields.items():
            if field not in header:
                continue
            found_version = True
            if not JSONTool._version_at_least(header[field], minimum):
                return False

        return found_version

    @staticmethod
    def load_json(file_path):
        if not os.path.isfile(file_path):
            print(f"File not found: {file_path}")
            return None

        with open(file_path, 'r', encoding='utf-8') as file:
            return JSONTool.normalize_paths(json.load(file))

    @staticmethod
    def start_caching():
        JSONTool._use_cache = True

    @staticmethod
    def stop_caching():
        JSONTool._use_cache = False
        JSONTool._json_cache.clear()
        JSONTool._entity_cache.clear()
        JSONTool._app_cache.clear()

    @staticmethod
    def create_error(suppress_verbose, base_name, file_extension, specific_error, error_Messages=None):
        error_message = f"invalid {file_extension} found at: {base_name}. {specific_error}"
        if not suppress_verbose:
            print(error_message)
        if error_Messages is None:
            show_message(error_message)
        else:
            error_Messages.append(error_message)

    @staticmethod
    def _create_error_if_needed(has_error, suppress_verbose, base_name, file_extension, specific_error, errorMessages):
        if has_error:
            JSONTool.create_error(suppress_verbose, base_name, file_extension, specific_error, errorMessages)

    @staticmethod
    def _load_streaming_sector_data(data):
        root = data['Data']['RootChunk']
        return root['nodeData']['Data'], root['nodes']

    @staticmethod
    def _load_material_data(data, suppress_verbose):
        if not suppress_verbose:
            print('  Building shaders')
        return data['MaterialRepo'] + "\\", data['Appearances'], data['Materials']

    @staticmethod
    def _load_refitter_data(data):
        return (
            data['lattice_object_name'],
            data['deformed_control_points'],
            data['lattice_points'],
            data['lattice_object_location'],
            data['lattice_object_rotation'],
            data['lattice_object_scale'],
            data['lattice_interpolation_u'],
            data['lattice_interpolation_v'],
            data['lattice_interpolation_w'],
        )


    @staticmethod
    def _parsed_cache_key(filepath):
        abs_path = os.path.abspath(filepath)
        try:
            stat_result = os.stat(abs_path)
        except OSError:
            return abs_path, 0

        mtime_ns = getattr(stat_result, 'st_mtime_ns', None)
        if mtime_ns is None:
            mtime_ns = int(stat_result.st_mtime * 1_000_000_000)
        return abs_path, mtime_ns

    @staticmethod
    def _load_raw_json(filepath, errorMessages=None):
        if not os.path.isfile(filepath):
            print(f"File does not exist: {filepath}")
            return None

        if not filepath.endswith(('.json', '.zip')):
            raise ValueError(f"{filepath} is not a json, what are you doing?")

        cp77_addon_prefs = bpy.context.preferences.addons['i_scene_cp77_gltf'].preferences
        suppress_verbose = cp77_addon_prefs.non_verbose
        base_name = os.path.basename(filepath)
        file_extension = _full_suffix(base_name)
        # Same validity rule as the parsed caches: a changed file must not serve stale raw
        # data under a fresh parsed-cache key.
        cache_key = JSONTool._parsed_cache_key(filepath)
        is_refitter = base_name.endswith('.refitter.zip')
        is_cacheable = file_extension in JSONTool.cachable_types
        is_cached = is_cacheable and JSONTool._use_cache and cache_key in JSONTool._json_cache

        if is_cached:
            data = JSONTool._json_cache[cache_key]
        else:
            if not suppress_verbose:
                print(f"  Parsing json file {base_name}")
            data = JSONTool.jsonloads(load_zip(filepath)) if is_refitter else JSONTool.load_json(filepath)
            if data is None:
                return None
            if is_cacheable and JSONTool._use_cache:
                JSONTool._json_cache[cache_key] = data

        has_error = not is_cached and not is_refitter and not JSONTool.json_ver_validate(data)
        specific_error = JSONTool.passthrough_errors.get(file_extension, invalid_json_error)
        JSONTool._create_error_if_needed(has_error, suppress_verbose, base_name, file_extension, specific_error, errorMessages)
        return data

    @staticmethod
    def load_entity(filepath, errorMessages=None):
        cache_key = JSONTool._parsed_cache_key(filepath)
        if JSONTool._use_cache and cache_key in JSONTool._entity_cache:
            return JSONTool._entity_cache[cache_key]

        data = JSONTool._load_raw_json(filepath, errorMessages)
        if data is None:
            return None

        root = data['Data']['RootChunk']
        compiled_data = root.get('compiledData')
        appearances = root.get('appearances') or []
        components = root.get('components') or []
        component_data = compiled_data.get('Data', {}).get('Chunks', []) if type(compiled_data) is dict else []
        appearance_names, by_appearance, by_name = _build_app_lookup(appearances)
        default_appearance = _normalize_default_appearance(_cname_value(root.get('defaultAppearance')), appearances, by_appearance, by_name)
        components_by_name = _build_component_lookup(components)
        appearance_index_by_name = {}
        for index, name in enumerate(appearance_names):
            if name:
                appearance_index_by_name.setdefault(name, index)
        component_ids = {id(component) for component in components}
        component_data_ids = {id(component) for component in component_data}
        vehicle_slot_component = next((component for component in components if _component_name(component) in ('vehicle_slots', 'slots')), None)

        parsed = ParsedEntity(
            appearances=appearances,
            appearance_names=appearance_names,
            appearance_index_by_name=appearance_index_by_name,
            appearances_by_appearance=by_appearance,
            appearances_by_name=by_name,
            default_appearance=default_appearance,
            component_dicts=components,
            component_data=component_data,
            components_by_name=components_by_name,
            components_by_id={id(component): component for component in components},
            component_ids=component_ids,
            component_data_ids=component_data_ids,
            parent_transform_lookup=_build_chunk_lookup(component_data, 'parentTransform'),
            skinning_lookup=_build_chunk_lookup(component_data, 'skinning'),
            shape_lookup=_build_chunk_lookup(component_data, 'shape'),
            slot_component_lookups=_build_slot_component_lookups(components),
            collider_components=_components_by_type(component_data, 'entColliderComponent'),
            simple_collider_components=_components_by_type(component_data, 'entSimpleColliderComponent'),
            light_channel_components=_components_by_type(component_data, 'entLightChannelComponent') + _components_by_type(components, 'entLightChannelComponent'),
            resolved_dependencies=root.get('resolvedDependencies') or [],
            vehicle_slot_component=vehicle_slot_component,
        )

        if JSONTool._use_cache:
            JSONTool._entity_cache[cache_key] = parsed
        return parsed

    @staticmethod
    def load_app(filepath, errorMessages=None):
        cache_key = JSONTool._parsed_cache_key(filepath)
        if JSONTool._use_cache and cache_key in JSONTool._app_cache:
            return JSONTool._app_cache[cache_key]

        data = JSONTool._load_raw_json(filepath, errorMessages)
        if data is None:
            return None

        root = data['Data']['RootChunk']
        appearances = root.get('appearances') or []
        names = []
        by_name = {}
        components_by_name = {}
        chunks_by_name = {}
        parent_by_name = {}
        skinning_by_name = {}
        shape_by_name = {}
        light_by_name = {}

        for index, appearance in enumerate(appearances):
            if type(appearance) is not dict:
                continue
            app_data = appearance.get('Data') if type(appearance.get('Data')) is dict else {}
            name = _cname_value(app_data.get('name'), str(index))
            names.append(name)
            by_name[name] = index
            components = app_data.get('components') or []
            compiled_data = app_data.get('compiledData')
            chunks = compiled_data.get('Data', {}).get('Chunks', []) if type(compiled_data) is dict else []
            components_by_name[name] = components
            chunks_by_name[name] = chunks
            parent_by_name[name] = _build_chunk_lookup(chunks, 'parentTransform')
            skinning_by_name[name] = _build_chunk_lookup(chunks, 'skinning')
            shape_by_name[name] = _build_chunk_lookup(chunks, 'shape')
            light_by_name[name] = _components_by_type(chunks, 'entLightChannelComponent') + _components_by_type(components, 'entLightChannelComponent')

        parsed = ParsedApp(
            appearances=appearances,
            appearance_names=names,
            appearances_by_name=by_name,
            components_by_appearance_name=components_by_name,
            chunks_by_appearance_name=chunks_by_name,
            parent_transform_lookup_by_appearance_name=parent_by_name,
            skinning_lookup_by_appearance_name=skinning_by_name,
            shape_lookup_by_appearance_name=shape_by_name,
            light_channels_by_appearance_name=light_by_name,
        )

        if JSONTool._use_cache:
            JSONTool._app_cache[cache_key] = parsed
        return parsed

    @staticmethod
    def jsonload(filepath, errorMessages=None):
        # _load_raw_json owns file IO, caching, and version validation; this only dispatches
        # by resource type. Structured entity/appearance parsing lives in load_entity/load_app.
        data = JSONTool._load_raw_json(filepath, errorMessages)
        if data is None:
            return None

        base_name = os.path.basename(filepath)
        file_extension = _full_suffix(base_name)
        if base_name.endswith('.refitter.zip'):
            return JSONTool._load_refitter_data(data)
        if file_extension in JSONTool.passthrough_errors:
            return data

        cp77_addon_prefs = bpy.context.preferences.addons['i_scene_cp77_gltf'].preferences
        suppress_verbose = cp77_addon_prefs.non_verbose
        match file_extension:
            case '.streamingsector.json':
                return JSONTool._load_streaming_sector_data(data)

            case '.Material.json':
                return JSONTool._load_material_data(data, suppress_verbose)

            case _:
                JSONTool.create_error(suppress_verbose, base_name, file_extension, invalid_json_error, errorMessages)
                return None

    @staticmethod
    def jsonloads(jsonstrings):
        data = json.loads(jsonstrings)
        return JSONTool.normalize_paths(data)

    @staticmethod
    def openJSON(path, mode='r', ProjPath='', DepotPath=''):
        path = path.replace('\\', os.sep)
        ProjPath = ProjPath.replace('\\', os.sep)
        DepotPath = DepotPath.replace('\\', os.sep)

        inproj = os.path.join(ProjPath, path)
        if os.path.exists(inproj):
            return JSONTool.jsonload(inproj)

        return JSONTool.jsonload(os.path.join(DepotPath, path))


def resolve_entity_appearance(filepath, requested_app, error_messages=None):
    parsed_ent = JSONTool.load_entity(filepath, error_messages if error_messages is not None else []) if filepath else None
    if parsed_ent is None:
        return requested_app
    return resolve_requested_appearance_name(
        requested_app,
        parsed_ent.default_appearance,
        parsed_ent.appearances,
        parsed_ent.appearances_by_appearance,
        parsed_ent.appearances_by_name,
    )
