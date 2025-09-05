# This script updates the mesh data in a JSON file based on the selected mesh object in Blender.
# It retrieves the mesh vertices and indices, and saves them back to the JSON file.
# Simarilius 13/4/2025

import bpy
import json
import os
from itertools import chain

def update_mesh_data_from_json():
    # Ensure a single object is selected
    selected_objects = bpy.context.selected_objects
    if len(selected_objects) != 1 or selected_objects[0].type != 'MESH':
        print("Please select a single mesh object.")
        return

    mesh_object = selected_objects[0]

    # Check if the object has a custom property 'entJSON'
    if 'entJSON' not in mesh_object:
        print("The selected object does not have an 'entJSON' property.")
        return

    json_path = mesh_object['entJSON']

    # Check if the JSON file exists
    if not os.path.isfile(json_path):
        print(f"JSON file not found at path: {json_path}")
        return

    # Load the JSON file
    with open(json_path, 'r') as json_file:
        data = json.load(json_file)

    # Locate the compiled data section
    compiled_data = data['Data']['RootChunk']['compiledData']['Data']['Chunks']
    if not compiled_data:
        print("No compiled data found in the JSON file.")
        return

    # Find the component with the same name as the mesh
    component = next((comp for comp in compiled_data if 'name' in comp.keys() and comp['name']['$value'] == mesh_object.name), None)
    if not component:
        print(f"No component found in the JSON file with the name: {mesh_object.name}")
        return

    # Update vertices and indices in the JSON data
    mesh = mesh_object.data
    vertices = [{'$type': 'Vector3', 'X': vert.co.x, 'Y': vert.co.y, 'Z': vert.co.z} for vert in mesh.vertices]  # Add "$type": "Vector3"
    faces = [list(poly.vertices) for poly in mesh.polygons]
    indices= list(chain.from_iterable(faces))
    shape = component.get('shape', {})
    shape['Data']['vertices'] = vertices
    shape['Data']['indices'] = indices

    # Save the updated JSON file
    with open(json_path, 'w') as json_file:
        json.dump(data, json_file, indent=4)

    print(f"Updated JSON file saved at: {json_path}")

# Run the function
update_mesh_data_from_json()