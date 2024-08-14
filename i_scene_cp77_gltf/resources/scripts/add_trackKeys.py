import bpy
import idprop.types

def convert_idproperty(prop):
    """Convert Blender IDProperty to a standard Python data structure."""
    if isinstance(prop, idprop.types.IDPropertyArray):
        return list(prop)
    elif isinstance(prop, (list, tuple)):
        return [convert_idproperty(item) for item in prop]
    elif isinstance(prop, dict):
        return {key: convert_idproperty(value) for key, value in prop.items()}
    else:
        return prop

def extract_track_keys(track_keys):
    """Extract and print the actual data from the trackKeys property."""
    if isinstance(track_keys, (list, tuple)):
        return [extract_track_keys(item) for item in track_keys]
    elif hasattr(track_keys, "to_dict"):
        return track_keys.to_dict()
    else:
        return track_keys

def add_to_track_keys(track_keys, new_data):
    """Add new data to the trackKeys property."""
    # Convert IDPropertyArray to a regular Python list
    if isinstance(track_keys, idprop.types.IDPropertyArray):
        track_keys = list(track_keys)
    elif isinstance(track_keys, list):
        track_keys = track_keys
    
    # Add the new data as a dictionary directly, not as a list
    track_keys.append(new_data)

    return track_keys

def modify_track_keys():
    for action in bpy.data.actions:
        if "constTrackKeys" in action.keys(): ## works for constTrackKeys or trackKeys
            track_keys = action["constTrackKeys"]

            # Convert to standard Python structure for manipulation
            converted_track_keys = convert_idproperty(track_keys)
            print(f"Original trackKeys: {converted_track_keys}")

            # Add new data (as a dictionary, not a list)
            new_data = {"trackIndex": 7, "time": 0.050059766, "value": 0.00}  ##populate this with the data
            updated_track_keys = add_to_track_keys(converted_track_keys, new_data)

            # Reassign the modified trackKeys to the action
            action["constTrackKeys"] = updated_track_keys

            # Print the updated trackKeys
            updated_track_keys = convert_idproperty(action["constTrackKeys"])
            print(f"Updated trackKeys: {updated_track_keys}")

# Call the function to modify the trackKeys property
modify_track_keys()
