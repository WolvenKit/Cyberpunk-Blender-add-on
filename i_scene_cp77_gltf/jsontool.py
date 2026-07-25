import copy
import json
import os
import re
from collections import OrderedDict
from functools import lru_cache
from pathlib import Path

import bpy

from .main.common import load_zip, show_message
from .main.datashards import ParsedApp, ParsedEntity
from .importers.common.entity_data import (
    build_chunk_handle_lookup as _build_chunk_lookup,
    build_component_lookup as _build_component_lookup,
    cname_value as _cname_value,
    component_name as _component_name,
    ent_appearance_name,
    resolve_ent_appearance_alias,
    resolve_requested_appearance_name,
)

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


def _components_by_type(components, type_name):
    return [component for component in components or () if
            type(component) is dict and component.get('$type') == type_name]


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
    _persistent_cache_limits = {
        '.Material.json': 512,
        '.mlsetup.json': 512,
        '.mltemplate.json': 512,
        '.mt.json': 256,
        '.mi.json': 256,
        '.dtex.json': 128,
    }
    _persistent_json_caches = {
        '.Material.json': OrderedDict(),
        '.mlsetup.json': OrderedDict(),
        '.mltemplate.json': OrderedDict(),
        '.mt.json': OrderedDict(),
        '.mi.json': OrderedDict(),
        '.dtex.json': OrderedDict(),
    }
    _persistent_app_cache = OrderedDict()
    _persistent_app_cache_limit = 128
    _cache_stats = {
        "transient_hits": 0,
        "persistent_hits": 0,
        "misses": 0,
        "persistent_stores": 0,
        "persistent_evictions": 0,
        "parsed_app_hits": 0,
        "parsed_app_stores": 0,
        "parsed_app_evictions": 0,
    }
    _persistent_family_stats = {
        '.Material.json': {"hits": 0, "stores": 0, "evictions": 0},
        '.mlsetup.json': {"hits": 0, "stores": 0, "evictions": 0},
        '.mltemplate.json': {"hits": 0, "stores": 0, "evictions": 0},
        '.mt.json': {"hits": 0, "stores": 0, "evictions": 0},
        '.mi.json': {"hits": 0, "stores": 0, "evictions": 0},
        '.dtex.json': {"hits": 0, "stores": 0, "evictions": 0},
    }

    cachable_types = {
        '.ent.json',
        '.anims.json',
        '.app.json',
        '.streamingblock.json',
        '.mesh.json',
        '.gradient.json',
        '.rig.json',
        '.facialsetup.json',
        '.cfoliage.json',
        '.hp.json',
        '.phys.json',
        '.mlsetup.json',
        '.mltemplate.json',
        '.mt.json',
        '.mi.json',
        '.dtex.json',
        '.Material.json',
        }

    persistent_cachable_types = frozenset(_persistent_cache_limits)

    passthrough_errors = {
        '.ent.json': invalid_json_error,
        '.anims.json': invalid_json_error,
        '.app.json': invalid_json_error,
        '.streamingblock.json': invalid_json_error,
        '.mesh.json': invalid_json_error,
        '.gradient.json': invalid_json_error,
        '.rig.json': invalid_json_error,
        '.facialsetup.json': invalid_json_error,
        '.cfoliage.json': invalid_json_error,
        '.hp.json': invalid_json_error,
        '.phys.json': invalid_phys_error,
        '.mlsetup.json': invalid_material_error,
        '.mltemplate.json': invalid_material_error,
        '.mt.json': invalid_material_error,
        '.mi.json': invalid_material_error,
        '.dtex.json': invalid_material_error,
        }

    @staticmethod
    def resolve_asset_path(reference, roots=(), extensions=(), warn_missing=False):
        """Resolve an explicit path or depot reference through DepotAssetIndex."""
        if not reference:
            return ""

        from .datakrash import DEFAULT_ASSET_EXTENSIONS, asset_index_for_root

        expanded = bpy.path.abspath(str(reference))
        requested = tuple(extensions) or DEFAULT_ASSET_EXTENSIONS
        supplied_roots = tuple(root for root in roots if root)
        for root in supplied_roots:
            index = asset_index_for_root(
                bpy.path.abspath(str(root)),
                extensions=requested,
                warn_missing=warn_missing,
            )
            resolved = index.resolve_any(expanded, requested, warn=warn_missing)
            if resolved:
                return resolved

        # A caller supplying roots has declared the complete resolution boundary.
        # Do not create one-off indexes for arbitrary parent folders on a miss.
        if supplied_roots:
            return ""

        parent = os.path.dirname(expanded)
        if not parent:
            return ""
        index = asset_index_for_root(
            parent, extensions=requested, warn_missing=warn_missing
        )
        return index.resolve_any(expanded, requested, warn=warn_missing) or ""

    @staticmethod
    def resolve_existing_path(reference, roots=(), warn_missing=False):
        """Resolve an existing local file through the indexed path resolver."""
        if not reference:
            return ""
        expanded = bpy.path.abspath(str(reference))
        suffix = _full_suffix(os.path.basename(expanded))
        extensions = (suffix,) if suffix else ()
        return JSONTool.resolve_asset_path(
            expanded, roots=roots, extensions=extensions,
            warn_missing=warn_missing,
        )

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
    def _file_signature(file_path, length=16):
        try:
            with open(file_path, 'rb') as handle:
                return handle.read(length)
        except OSError:
            return b''

    @staticmethod
    def load_json(file_path):
        if not os.path.isfile(file_path):
            print(f"File not found: {file_path}")
            return None

        # utf-8-sig strips a leading BOM when present and is a no-op otherwise.
        # Several Windows editors and PowerShell redirects emit BOM-prefixed
        # JSON, which the plain utf-8 codec surfaces as a column-0 decode error.
        with open(file_path, 'r', encoding='utf-8-sig') as file:
            try:
                return JSONTool.normalize_paths(json.load(file))
            except json.JSONDecodeError as error:
                signature = JSONTool._file_signature(file_path)
                if not signature:
                    detail = "file is empty"
                elif signature[:4] == b'PK\x03\x04':
                    detail = "file is a zip archive, not JSON"
                else:
                    detail = f"starts with {signature!r}"
                raise json.JSONDecodeError(
                    f"{error.msg} in {os.path.abspath(file_path)} "
                    f"({os.path.getsize(file_path)} bytes, {detail})",
                    error.doc, error.pos,
                ) from None

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
    def clear_persistent_cache():
        for cache in JSONTool._persistent_json_caches.values():
            cache.clear()
        JSONTool._persistent_app_cache.clear()
        for key in JSONTool._cache_stats:
            JSONTool._cache_stats[key] = 0
        for family in JSONTool._persistent_family_stats.values():
            for key in family:
                family[key] = 0

    @staticmethod
    def cache_stats():
        families = {
            extension: {
                **JSONTool._persistent_family_stats[extension],
                "entries": len(JSONTool._persistent_json_caches[extension]),
                "limit": JSONTool._persistent_cache_limits[extension],
            }
            for extension in JSONTool._persistent_cache_limits
        }
        return {
            **JSONTool._cache_stats,
            "transient_entries": len(JSONTool._json_cache),
            "entity_entries": len(JSONTool._entity_cache),
            "app_entries": len(JSONTool._app_cache),
            "persistent_entries": sum(
                len(cache) for cache in JSONTool._persistent_json_caches.values()
            ),
            "persistent_families": families,
            "parsed_app_entries": len(JSONTool._persistent_app_cache),
            "parsed_app_limit": JSONTool._persistent_app_cache_limit,
        }

    @staticmethod
    def _persistent_cache_get(file_extension, cache_key):
        cache = JSONTool._persistent_json_caches.get(file_extension)
        if cache is None:
            return None
        cached = cache.get(cache_key)
        if cached is None:
            return None
        cache.move_to_end(cache_key)
        JSONTool._cache_stats["persistent_hits"] += 1
        JSONTool._persistent_family_stats[file_extension]["hits"] += 1
        return copy.deepcopy(cached)

    @staticmethod
    def _persistent_cache_store(file_extension, cache_key, data):
        cache = JSONTool._persistent_json_caches.get(file_extension)
        if cache is None:
            return
        cache[cache_key] = copy.deepcopy(data)
        cache.move_to_end(cache_key)
        JSONTool._cache_stats["persistent_stores"] += 1
        JSONTool._persistent_family_stats[file_extension]["stores"] += 1
        limit = JSONTool._persistent_cache_limits[file_extension]
        while len(cache) > limit:
            cache.popitem(last=False)
            JSONTool._cache_stats["persistent_evictions"] += 1
            JSONTool._persistent_family_stats[file_extension]["evictions"] += 1

    @staticmethod
    def _persistent_app_get(cache_key):
        cached = JSONTool._persistent_app_cache.get(cache_key)
        if cached is None:
            return None
        JSONTool._persistent_app_cache.move_to_end(cache_key)
        JSONTool._cache_stats["parsed_app_hits"] += 1
        # ParsedApp is an immutable pipeline view. Returning it directly avoids cloning
        # the complete appearance graph on every top-level entity import.
        return cached

    @staticmethod
    def _persistent_app_store(cache_key, parsed):
        cache = JSONTool._persistent_app_cache
        # Do not also persist the raw APP document; the parsed view is the durable form.
        cache[cache_key] = parsed
        cache.move_to_end(cache_key)
        JSONTool._cache_stats["parsed_app_stores"] += 1
        while len(cache) > JSONTool._persistent_app_cache_limit:
            cache.popitem(last=False)
            JSONTool._cache_stats["parsed_app_evictions"] += 1

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
    def _parse_streaming_sector_data(data, filepath=''):
        from .importers.sector.parser import parse_sector_document
        return parse_sector_document(data, source_path=filepath)

    @staticmethod
    def _load_streaming_sector_data(data, filepath=''):
        return JSONTool._parse_streaming_sector_data(
            data,
            filepath,
        ).legacy_jsonload()

    @staticmethod
    def load_sector(filepath, errorMessages=None):
        data = JSONTool._load_raw_json(filepath, errorMessages)
        if data is None:
            return None
        return JSONTool._parse_streaming_sector_data(data, filepath)

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
    def resource_cache_key(filepath):
        """Return the canonical path/version key used by JSONTool caches."""
        return JSONTool._parsed_cache_key(filepath)

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
        return abs_path, mtime_ns, int(stat_result.st_size)

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
        persistent_cacheable = file_extension in JSONTool.persistent_cachable_types

        if is_cached:
            JSONTool._cache_stats["transient_hits"] += 1
            data = JSONTool._json_cache[cache_key]
        else:
            data = JSONTool._persistent_cache_get(file_extension, cache_key) if persistent_cacheable else None
            if data is not None:
                is_cached = True
            else:
                JSONTool._cache_stats["misses"] += 1
                if not suppress_verbose:
                    print(f"  Parsing json file {base_name}")
                data = JSONTool.jsonloads(load_zip(filepath)) if is_refitter else JSONTool.load_json(filepath)
                if data is None:
                    return None
            if is_cacheable and JSONTool._use_cache:
                JSONTool._json_cache[cache_key] = data

        has_error = not is_cached and not is_refitter and not JSONTool.json_ver_validate(data)
        specific_error = JSONTool.passthrough_errors.get(file_extension, invalid_json_error)
        JSONTool._create_error_if_needed(
            has_error, suppress_verbose, base_name, file_extension, specific_error, errorMessages
            )
        if persistent_cacheable and not is_cached and not has_error:
            JSONTool._persistent_cache_store(file_extension, cache_key, data)
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
        default_appearance = _normalize_default_appearance(
            _cname_value(root.get('defaultAppearance')), appearances, by_appearance, by_name
            )
        components_by_name = _build_component_lookup(components)
        appearance_index_by_name = {}
        for index, name in enumerate(appearance_names):
            if name:
                appearance_index_by_name.setdefault(name, index)
        component_ids = {id(component) for component in components}
        component_data_ids = {id(component) for component in component_data}
        vehicle_slot_component = next(
                (component for component in components if _component_name(component) in ('vehicle_slots', 'slots')),
                None
                )

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
                light_channel_components=_components_by_type(
                    component_data, 'entLightChannelComponent'
                    ) + _components_by_type(
                    components, 'entLightChannelComponent'
                    ),
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

        persistent = JSONTool._persistent_app_get(cache_key)
        if persistent is not None:
            if JSONTool._use_cache:
                JSONTool._app_cache[cache_key] = persistent
            return persistent

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
            light_by_name[name] = _components_by_type(chunks, 'entLightChannelComponent') + _components_by_type(
                components, 'entLightChannelComponent'
                )

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

        JSONTool._persistent_app_store(cache_key, parsed)
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
                return JSONTool._load_streaming_sector_data(data, filepath)

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
    parsed_ent = JSONTool.load_entity(
        filepath, error_messages if error_messages is not None else []
        ) if filepath else None
    if parsed_ent is None:
        return requested_app
    return resolve_requested_appearance_name(
            requested_app,
            parsed_ent.default_appearance,
            parsed_ent.appearances,
            parsed_ent.appearances_by_appearance,
            parsed_ent.appearances_by_name,
            )