import bpy
import json
import os
from .main.common import show_message, load_zip
from pathlib import Path

def normalize_paths(data):
    if isinstance(data, dict):
        for key, value in data.items():
            data[key] = normalize_paths(value)
    elif isinstance(data, list):
        for i in range(len(data)):
            data[i] = normalize_paths(data[i])
    elif isinstance(data, str):
        # Normalize the path if it is absolute
        if data[0:4]=='base' or data[0:3]=='ep1' or data[1:3]==':\\':
            data = data.replace('\\',os.sep)
    return data

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

def load_json(file_path):
    with open(file_path, 'r') as file:
        data = json.load(file)
        normalize_paths(data)
    return data

# Handles generation of error messages depending on verbosity and/or print_immediately settings.
# If print_immediately is set to false, then the error message will be appended to the errorMessages array.
def create_error(print_immediately, suppress_verbose, base_name, file_extension, specific_error, errorMessages = []):
    error_message = f"invalid {file_extension} found at: {base_name}. {specific_error}"
    if not suppress_verbose:
        print(error_message)
    if print_immediately:
        show_message(error_message)
    else:
        errorMessages.append(error_message)

# error messages for different file types
invalid_json_error = "This plugin requires jsons generated using the latest version of Wolvenkit."
invalid_material_error = "Import will continue, but shaders may be incorrectly set up for these objects."
invalid_phys_error = "Import may continue, but .phys colliders will not be imported."

# Pass an errorMessages array to process error messages outside of this function (e.g. for calling it in a loop)
def jsonload(filepath, errorMessages = None):

    print_messages = errorMessages is None #function caled in a loop
    errorMessages = [] if errorMessages is None else errorMessages

    if not filepath.endswith('.json') and not filepath.endswith('.zip'):
        raise ValueError(f"{filepath} is not a json, what are you doing?")

    cp77_addon_prefs = bpy.context.preferences.addons['i_scene_cp77_gltf'].preferences

    # Extract the base name of the file
    base_name = os.path.basename(filepath)

    file_extension = ''.join(Path(filepath).suffixes)

    if not cp77_addon_prefs.non_verbose:
        print(f"  Processing: {base_name}")
        data=load_json(filepath)

    has_error = json_ver_validate(data) == False

    match file_extension:
        case '.ent.json':
            if has_error:
                create_error(print_messages, cp77_addon_prefs.non_verbose, base_name, file_extension, invalid_json_error, errorMessages)
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
            # Do something for .ent.json
            return ent_apps, ent_components, ent_component_data, res, ent_default

        case '.anims.json' | '.app.json' | '.streamingblock.json' |  '.mesh.json' | '.gradient.json' | '.rig.json' | '.cfoliage.json' | '.hp.json' | '.streamingblock.json':
            if has_error:
                create_error(print_messages, cp77_addon_prefs.non_verbose, base_name, file_extension, invalid_json_error, errorMessages)
            return data

        case '.phys.json':
            if has_error:
                create_error(print_messages, cp77_addon_prefs.non_verbose, base_name, file_extension, invalid_phys_error, errorMessages)
            return data

        case '.mlsetup.json' | '.mltemplate.json' | '.mt.json' | '.mi.json':
            if has_error:
                create_error(print_messages, cp77_addon_prefs.non_verbose, base_name, file_extension, invalid_material_error, errorMessages)
            return data

        case '.streamingsector.json':
            if has_error:
                create_error(print_messages, cp77_addon_prefs.non_verbose, base_name, file_extension, invalid_json_error, errorMessages)

            t = data['Data']['RootChunk']['nodeData']['Data']
            nodes = data["Data"]["RootChunk"]["nodes"]
            return t, nodes

        case '.Material.json':
            if has_error:
                create_error(print_messages, cp77_addon_prefs.non_verbose, base_name, file_extension, invalid_json_error, errorMessages)

            if not cp77_addon_prefs.non_verbose:
                print('  Building shaders')
            depotpath = data["MaterialRepo"] + "\\"
            json_apps = data['Appearances']
            mats = data['Materials']

            return depotpath, json_apps, mats

        case _ if base_name.endswith('.refitter.zip'):
            data=load_zip(filepath)
            data=jsonloads(data)
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
            create_error(print_messages, cp77_addon_prefs.non_verbose, base_name, file_extension, invalid_json_error, errorMessages)
            # Do something for other json files


def jsonloads(jsonstrings):

    data=json.loads(jsonstrings)
    normalize_paths(data)
    return data

def openJSON(path, mode='r',  ProjPath='', DepotPath=''):
    path = path.replace('\\', os.sep)
    ProjPath = ProjPath.replace('\\', os.sep)
    DepotPath = DepotPath.replace('\\', os.sep)

    inproj=os.path.join(ProjPath,path)
    if os.path.exists(inproj):
        data = jsonload(inproj)
    else:
        data = jsonload(os.path.join(DepotPath,path))
    return data
