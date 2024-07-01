


import json
import os

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
    if "MaterialJsonVersion" in header and "1." not in header["MaterialJsonVersion"]:
        return False
    return True


def load_json(file_path):
    with open(file_path, 'r') as file:
        data = json.load(file)
        normalize_paths(data)
    return data

def jsonload(filepath):
    if not file_path.endswith('.json'):
        raise ValueError("This is not a json, what are you doing?")
    
    # Extract the base name of the file
    base_name = os.path.basename(filepath)
    
    # Match/case statement to handle different types of json files
    match base_name:
        case _ if base_name.endswith('.anims.json'):
            print(f"Processing: {base_name}")
            data=load_json(filepath)
            # Do something for .anims.json
        case _ if base_name.endswith('.app.json'):
            print(f"Processing: {base_name}")
            data=load_json(filepath)
            # Do something for .app.json            
        case _ if base_name.endswith('.ent.json'):
            print(f"Processing: {base_name}")
            data=load_json(filepath)
            # Do something for .ent.json
        case _ if base_name.endswith('.mesh.json'):
            print(f"Processing: {base_name}")
            data=load_json(filepath)
            # Do something for .mesh.json            
        case _ if base_name.endswith('.material.json'):
            print(f"Processing: {base_name}")
            data=load_json(filepath)
            # Do something for .material.json
        case _ if base_name.endswith('.mlsetup.json'):
            print(f"Processing: {base_name}")
            data=load_json(filepath)
            # Do something for .mlsetup.json
        case _ if base_name.endswith('.mltemplate.json'):
            print(f"Processing: {base_name}")
            data=load_json(filepath)
            # Do something for .mlsetup.json
        case _ if base_name.endswith('.phys.json'):
            print(f"Processing: {base_name}")
            data=load_json(filepath)
            # Do something for .phys.json
        case _ if base_name.endswith('.streamingsector.json'):
            print(f"Processing: {base_name}")
            data=load_json(filepath)
            # Do something for .streamingsector.json            
        case _ if base_name.endswith('.streamingblock.json'):
            print(f"Processing: {base_name}")
            data=load_json(filepath)
            # Do something for .streamingblock.json
        case _ if base_name.endswith('.rig.json'):
            print(f"Processing: {base_name}")
            data=load_json(filepath)
            # Do something for .rig.json
        case _:
            print(f"Incompatible Json: {base_name}")
            print("json files must be generated with a current version of Wolvenkit")
            # Do something for other json files
            
    # Return or process the data as needed
    return data

# Example usage
file_path = 'example.anims.json'
data = process_json(file_path)
