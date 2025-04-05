import bpy
import json
import os
from .main.common import show_message, load_zip
from pathlib import Path


# Error messages for different file types
invalid_json_error = "This plugin requires jsons generated using the latest version of Wolvenkit."
invalid_material_error = "Import will continue, but shaders may be incorrectly set up for these objects."
invalid_phys_error = "Import may continue, but .phys colliders will not be imported."


class JSONTool:
    _json_cache = {}
    _use_cache = False

    @staticmethod
    def normalize_paths(data):
        if isinstance(data, dict):
            for key, value in data.items():
                data[key] = JSONTool.normalize_paths(value)
        elif isinstance(data, list):
            for i in range(len(data)):
                data[i] = JSONTool.normalize_paths(data[i])
        elif isinstance(data, str):
            # Normalize the path if it is absolute
            if data[0:4]=='base' or data[0:3]=='ep1' or data[1:3]==':\\':
                data = data.replace('\\',os.sep)
        return data

    @staticmethod
    def json_ver_validate(json_data):
        if 'Header' not in json_data:
            return False
        header = json_data['Header']
        if "WolvenKitVersion" in header and "8.13" not in header["WolvenKitVersion"]:
            if "8.15" not in header["WolvenKitVersion"] and "8.16" not in header["WolvenKitVersion"]:
                return False
        if "MaterialJsonVersion" in header:
            if "1." not in header["MaterialJsonVersion"]:
                return False
        return True

    @staticmethod
    def load_json(file_path):
        with open(file_path, 'r') as file:
            data = json.load(file)
            JSONTool.normalize_paths(data)
        return data

    @staticmethod
    def start_caching():
        JSONTool._use_cache = True

    @staticmethod
    def stop_caching():
        JSONTool._use_cache = False
        JSONTool._json_cache.clear()

    @staticmethod
    def create_error(suppress_verbose, base_name, file_extension, specific_error, error_messages = None):
        error_message = f"invalid {file_extension} found at: {base_name}. {specific_error}"
        if not suppress_verbose:
            print(error_message)
        if error_messages is None:
            show_message(error_message)
        else:
            errorMessages.append(error_message)

    cachable_types = [
        '.anims.json',
        '.app.json',
        '.streamingblock.json',
        '.mesh.json',
        '.gradient.json',
        '.rig.json',
        '.cfoliage.json',
        '.hp.json',
        '.streamingblock.json',
        '.phys.json' '.mlsetup.json',
        '.mltemplate.json',
        '.mt.json',
        '.mi.json',
    ]

    @staticmethod
    def jsonload(filepath, errorMessages = None):
        if not filepath.endswith('.json') and not filepath.endswith('.zip'):
            raise ValueError(f"{filepath} is not a json, what are you doing?")

        cp77_addon_prefs = bpy.context.preferences.addons['i_scene_cp77_gltf'].preferences

        # Extract the base name of the file
        base_name = os.path.basename(filepath)

        file_extension = ''.join(Path(filepath).suffixes)

        isCached = JSONTool._use_cache and base_name in JSONTool._json_cache.keys()

        # Check if it's cached
        if isCached:
            data = JSONTool._json_cache[base_name]
            if file_extension in JSONTool.cachable_types:
                return data
        else:
            if not cp77_addon_prefs.non_verbose:
                print(f"  Parsing json file {base_name}")
            data = JSONTool.load_json(filepath)

        # do not append error messages twice
        has_error = not isCached and JSONTool.json_ver_validate(data) == False

        # only cache items if we are not in a loop
        if JSONTool._use_cache:
            JSONTool._json_cache[base_name] = data

        match file_extension:
            case '.anims.json' | '.app.json' | '.streamingblock.json' |  '.mesh.json' | '.gradient.json' | '.rig.json' | '.cfoliage.json' | '.hp.json' | '.streamingblock.json':
                if has_error:
                    JSONTool.create_error(cp77_addon_prefs.non_verbose, base_name, file_extension, invalid_json_error, errorMessages)
                return data

            case '.phys.json':
                if has_error:
                    JSONTool.create_error(cp77_addon_prefs.non_verbose, base_name, file_extension, invalid_phys_error, errorMessages)
                return data

            case '.mlsetup.json' | '.mltemplate.json' | '.mt.json' | '.mi.json':
                if has_error:
                    JSONTool.create_error(cp77_addon_prefs.non_verbose, base_name, file_extension, invalid_material_error, errorMessages)
                return data
            case '.ent.json':
                if has_error:
                    JSONTool.create_error(cp77_addon_prefs.non_verbose, base_name, file_extension, invalid_json_error, errorMessages)
                    return 'CANCELLED'
                ent_apps= data['Data']['RootChunk']['appearances']
                ent_components=[]
                if data['Data']['RootChunk']['components']!=None:
                    ent_components= data['Data']['RootChunk']['components']
                ent_component_data=[]
                if data['Data']['RootChunk']['compiledData']!=None:
                    ent_component_data= data['Data']['RootChunk']['compiledData']['Data']['Chunks']
                res = data['Data']['RootChunk']['resolvedDependencies']
                ent_default = data['Data']['RootChunk']['defaultAppearance']['$value']
                return ent_apps, ent_components, ent_component_data, res, ent_default

            case '.streamingsector.json':
                if has_error:
                    JSONTool.create_error(cp77_addon_prefs.non_verbose, base_name, file_extension, invalid_json_error, errorMessages)

                t = data['Data']['RootChunk']['nodeData']['Data']
                nodes = data["Data"]["RootChunk"]["nodes"]
                return t, nodes


            case '.Material.json':
                if has_error:
                    JSONTool.create_error(cp77_addon_prefs.non_verbose, base_name, file_extension, invalid_json_error, errorMessages)

                if not cp77_addon_prefs.non_verbose:
                    print('  Building shaders')
                depotpath = data["MaterialRepo"] + "\\"
                json_apps = data['Appearances']
                mats = data['Materials']

                return depotpath, json_apps, mats

            case _ if base_name.endswith('.refitter.zip'):
                data=load_zip(filepath)
                data=JSONTool.jsonloads(data)
                lattice_object_name = data["lattice_object_name"]
                control_points = data["deformed_control_points"]
                lattice_points = data["lattice_points"]
                lattice_object_location = data["lattice_object_location"]
                lattice_object_rotation = data["lattice_object_rotation"]
                lattice_object_scale = data["lattice_object_scale"]
                lattice_interpolation_u = data["lattice_interpolation_u"]
                lattice_interpolation_v = data["lattice_interpolation_v"]
                lattice_interpolation_w = data["lattice_interpolation_w"]
                return lattice_object_name, control_points, lattice_points, lattice_object_location, lattice_object_rotation, lattice_object_scale, lattice_interpolation_u, lattice_interpolation_v, lattice_interpolation_w
            case _:
                JSONTool.create_error(cp77_addon_prefs.non_verbose, base_name, file_extension, invalid_json_error, errorMessages)

    @staticmethod
    def jsonloads(jsonstrings):
        data=json.loads(jsonstrings)
        JSONTool.normalize_paths(data)
        return data

    @staticmethod
    def openJSON(path, mode='r', ProjPath='', DepotPath=''):
        path = path.replace('\\', os.sep)
        ProjPath = ProjPath.replace('\\', os.sep)
        DepotPath = DepotPath.replace('\\', os.sep)

        inproj=os.path.join(ProjPath,path)
        if os.path.exists(inproj):
            data = JSONTool.jsonload(inproj)
        else:
            data = JSONTool.jsonload(os.path.join(DepotPath,path))
        return data

