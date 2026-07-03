import bpy
import json
import os
import re
from pathlib import Path
from .main.common import show_message, load_zip


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


class JSONTool:
    _json_cache = {}
    _use_cache = False

    cachable_types = {
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
        if isinstance(data, dict):
            for key, value in data.items():
                data[key] = JSONTool.normalize_paths(value)
            return data

        if isinstance(data, list):
            for index, value in enumerate(data):
                data[index] = JSONTool.normalize_paths(value)
            return data

        if isinstance(data, str):
            # Normalize the path if it is absolute
            if data.startswith(('base', 'ep1')) or data[1:3] == ':\\':
                return data.replace('\\', os.sep)

        return data

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
    def _load_ent_data(data):
        root = data['Data']['RootChunk']
        compiled_data = root.get('compiledData')
        ent_components = root.get('components') or []
        ent_component_data = compiled_data['Data']['Chunks'] if compiled_data is not None else []
        return root['appearances'], ent_components, ent_component_data, root['resolvedDependencies'], root['defaultAppearance']['$value']

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
    def jsonload(filepath, errorMessages=None):
        if not os.path.isfile(filepath):
            print(f"File does not exist: {filepath}")
            return None

        if not filepath.endswith(('.json', '.zip')):
            raise ValueError(f"{filepath} is not a json, what are you doing?")

        cp77_addon_prefs = bpy.context.preferences.addons['i_scene_cp77_gltf'].preferences
        suppress_verbose = cp77_addon_prefs.non_verbose
        base_name = os.path.basename(filepath)
        file_extension = ''.join(Path(base_name).suffixes)
        cache_key = os.path.abspath(filepath)
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

        # do not append error messages twice
        has_error = not is_cached and not is_refitter and not JSONTool.json_ver_validate(data)

        if file_extension in JSONTool.passthrough_errors:
            JSONTool._create_error_if_needed(
                has_error,
                suppress_verbose,
                base_name,
                file_extension,
                JSONTool.passthrough_errors[file_extension],
                errorMessages,
            )
            return data

        match file_extension:
            case '.ent.json':
                JSONTool._create_error_if_needed(has_error, suppress_verbose, base_name, file_extension, invalid_json_error, errorMessages)
                return JSONTool._load_ent_data(data)

            case '.streamingsector.json':
                JSONTool._create_error_if_needed(has_error, suppress_verbose, base_name, file_extension, invalid_json_error, errorMessages)
                return JSONTool._load_streaming_sector_data(data)

            case '.Material.json':
                JSONTool._create_error_if_needed(has_error, suppress_verbose, base_name, file_extension, invalid_json_error, errorMessages)
                return JSONTool._load_material_data(data, suppress_verbose)

            case _ if is_refitter:
                return JSONTool._load_refitter_data(data)

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
