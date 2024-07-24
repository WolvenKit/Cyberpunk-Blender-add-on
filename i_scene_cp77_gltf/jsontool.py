import bpy
import json
import os
from .main.common import show_message

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
        if "8.14" not in header["WolvenKitVersion"]:
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

def jsonload(filepath):

    if not filepath.endswith('.json'):
        raise ValueError("This is not a json, what are you doing?")
    cp77_addon_prefs = bpy.context.preferences.addons['i_scene_cp77_gltf'].preferences
    
    # Extract the base name of the file
    base_name = os.path.basename(filepath)
    
    # Match/case statement to handle different types of json files
    match base_name:
        case _ if base_name.endswith('.anims.json'):
            if not cp77_addon_prefs.non_verbose:
                print(f"Processing: {base_name}")
            data=load_json(filepath)
            if json_ver_validate(data) == False:
                if not cp77_addon_prefs.non_verbose:
                    print(f"invalid anims.json found at: {filepath} this plugin requires jsons generated using the latest version of Wolvenkit")
                show_message(f"invalid anims.json found at: {base_name} this plugin requires jsons generated using the latest version of Wolvenkit")
            # Do something for .anims.json

        case _ if base_name.endswith('.app.json'):
            if not cp77_addon_prefs.non_verbose:
                print(f"Processing: {base_name}")
            data=load_json(filepath)
            if json_ver_validate(data) == False:
                if not cp77_addon_prefs.non_verbose:
                    print(f"invalid app.json found at: {filepath} this plugin requires jsons generated using the latest version of Wolvenkit")
                show_message(f"invalid app.json: {base_name} this plugin requires jsons generated using the latest version of Wolvenkit")
            # Do something for .app.json

        case _ if base_name.endswith('.ent.json'):
            if not cp77_addon_prefs.non_verbose:
                print(f"Processing: {base_name}")
            data=load_json(filepath)
            if json_ver_validate(data) == False:
                if not cp77_addon_prefs.non_verbose:
                    print(f"attempted import of invalid ent.json from: {filepath} this plugin requires jsons generated using the latest version of Wolvenkit")
                show_message(f"attempted import of invalid ent.json: {base_name} this plugin requires jsons generated using the latest version of Wolvenkit")
                return 'CANCELLED'
            # Do something for .ent.json

        case _ if base_name.endswith('.mesh.json'):
            if not cp77_addon_prefs.non_verbose:
                print(f"Processing: {base_name}")
            data=load_json(filepath)
            if json_ver_validate(data) == False:
                if not cp77_addon_prefs.non_verbose:
                    print(f"invalid mesh.json found at: {filepath} this plugin requires jsons generated using the latest version of Wolvenkit")
                show_message(f"found invalid mesh.json: {base_name} this plugin requires jsons generated using the latest version of Wolvenkit")
            # Do something for .mesh.json
            #        
        case _ if base_name.endswith('.Material.json'):
            if not cp77_addon_prefs.non_verbose:
                print(f"Processing: {base_name}")
            data=load_json(filepath)
            if json_ver_validate(data) == False:
                if not cp77_addon_prefs.non_verbose:
                    print(f"invalid Material.json found at: {filepath} import will continue but materials will not be set up for this mesh")
                show_message(f"invalid material.json: {base_name} Re-Export the Mesh using the latest version of Wolvenkit")
            else:
                if not cp77_addon_prefs.non_verbose:
                    print('Building shaders')
            # Do something for .material.json
            
        case _ if base_name.endswith('.gradient.json'):
            if not cp77_addon_prefs.non_verbose:
                print(f"Processing: {base_name}")
            data=load_json(filepath)
            if json_ver_validate(data) == False:
                if not cp77_addon_prefs.non_verbose:
                    print(f"invalid gradient.json found at: {filepath} this plugin requires jsons generated using the latest version of Wolvenkit")
                show_message(f"found invalid gradient.json: {base_name} this plugin requires jsons generated using the latest version of Wolvenkit")
            
        case _ if base_name.endswith('.mlsetup.json'):
            if not cp77_addon_prefs.non_verbose:
                print(f"Processing: {base_name}")
            data=load_json(filepath)
            if json_ver_validate(data) == False:
                if not cp77_addon_prefs.non_verbose:
                    print(f"invalid mlsetup.json found at: {filepath} import will continue but shaders may be incorrectly set up for this mesh")
                show_message(f"invalid mlsetup.json: {base_name} import will continue but shaders may be incorrectly setup for this mesh")
            # Do something for .mlsetup.json

        case _ if base_name.endswith('.mltemplate.json'):
            if not cp77_addon_prefs.non_verbose:
                print(f"Processing: {base_name}")
            data=load_json(filepath)
            if json_ver_validate(data) == False:
                if not cp77_addon_prefs.non_verbose:
                    print(f"invalid mltemplate.json found at: {filepath} import will continue but shaders may be incorrectly set up for this mesh")
                show_message(f"invalid mltemplate.json: {base_name} import will continue but shaders may be incorrectly setup for this mesh")
            # Do something for .mlsetup.json

        case _ if base_name.endswith('.mt.json'):
            if not cp77_addon_prefs.non_verbose:
                print(f"Processing: {base_name}")
            data=load_json(filepath)
            if json_ver_validate(data) == False:
                if not cp77_addon_prefs.non_verbose:
                    print(f"invalid mt.json found at: {filepath} import will continue but shaders may be incorrectly set up for this mesh")
                show_message(f"invalid mt.json: {base_name} import will continue but shaders may be incorrectly setup for this mesh")
        
        case _ if base_name.endswith('.mi.json'):
            if not cp77_addon_prefs.non_verbose:
                print(f"Processing: {base_name}")
            data=load_json(filepath)
            if json_ver_validate(data) == False:
                if not cp77_addon_prefs.non_verbose:
                    print(f"invalid mi.json found at: {filepath} import will continue but shaders may be incorrectly set up for this mesh")
                show_message(f"invalid mi.json: {base_name} import will continue but shaders may be incorrectly setup for this mesh")
        
        case _ if base_name.endswith('.phys.json'):
            if not cp77_addon_prefs.non_verbose:
                print(f"Processing: {base_name}")
            data=load_json(filepath)
            if json_ver_validate(data) == False:
                if not cp77_addon_prefs.non_verbose:
                    print(f"invalid phys.json found at: {filepath} import may continue but .phys colliders will not be imported")
                show_message(f"invalid phys.json: {base_name} import may continue but .phys colliders will not be imported")
            # Do something for .phys.json

        case _ if base_name.endswith('.streamingsector.json'):
            if not cp77_addon_prefs.non_verbose:
                print(f"Processing: {base_name}")
            data=load_json(filepath)
            if json_ver_validate(data) == False:
                if not cp77_addon_prefs.non_verbose:
                    print(f"invalid streamingsector.json found at: {filepath} this plugin requires jsons generated with the latest version of Wolvenkit")
                show_message(f"invalid streamingsector.json: {base_name} this plugin requires jsons generated with the latest version of Wolvenkit")
            # Do something for .streamingsector.json

        case _ if base_name.endswith('.streamingblock.json'):
            if not cp77_addon_prefs.non_verbose:
                print(f"Processing: {base_name}")
            data=load_json(filepath)
            # Do something for .streamingblock.json

        case _ if base_name.endswith('.rig.json'):
            if not cp77_addon_prefs.non_verbose:
                print(f"Processing: {base_name}")
            data=load_json(filepath)
            if json_ver_validate(data) == False:
                if not cp77_addon_prefs.non_verbose:                
                    print(f"invalid rig.json found at: {filepath} this plugin requires jsons generated with the latest version of Wolvenkit")
                show_message(f"invalid rig.json: {base_name} this plugin requires jsons generated with the latest version of Wolvenkit")
            # Do something for .rig.json

        case _ if base_name.endswith('.hp.json'):
            if not cp77_addon_prefs.non_verbose:
                print(f"Processing: {base_name}")
            data=load_json(filepath)
            if json_ver_validate(data) == False:
                if not cp77_addon_prefs.non_verbose:                
                    print(f"invalid hp.json found at: {filepath} this plugin requires jsons generated with the latest version of Wolvenkit")
                show_message(f"invalid Hair Profile: {base_name} this plugin requires jsons generated with the latest version of Wolvenkit")
        
        case _ if base_name.endswith('.cfoliage.json'):
            if not cp77_addon_prefs.non_verbose:
                print(f"Processing: {base_name}")
            data=load_json(filepath)
            if json_ver_validate(data) == False:
                if not cp77_addon_prefs.non_verbose:                
                    print(f"invalid cfoliage.json found at: {filepath} this plugin requires jsons generated with the latest version of Wolvenkit")
                show_message(f"invalid cfoliage.json : {base_name} this plugin requires jsons generated with the latest version of Wolvenkit")
        
        case _:
            if not cp77_addon_prefs.non_verbose:
                print(f"Incompatible Json: {base_name}")
                print("json files must be generated with a latest version of Wolvenkit")
            show_message(f"Incompatible Json: {base_name} json files must be generated with a latest version of Wolvenkit")
            # Do something for other json files
            
    # Return or process the data as needed
    return data

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