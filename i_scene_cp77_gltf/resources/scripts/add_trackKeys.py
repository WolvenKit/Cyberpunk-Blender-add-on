import bpy
import idprop.types

try:
    from ...core.log import get_logger
except ImportError:
    import logging

    def get_logger(name):
        return logging.getLogger(f"i_scene_cp77_gltf.user_scripts.{name}")


_LOG = get_logger(__name__)


def convert_idproperty(prop):
    """Convert Blender IDProperty to a standard Python data structure"""
    if isinstance(prop, idprop.types.IDPropertyArray):
        return list(prop)
    elif isinstance(prop, (list, tuple)):
        return [convert_idproperty(item) for item in prop]
    elif isinstance(prop, dict):
        return {key: convert_idproperty(value) for key, value in prop.items()}
    else:
        return prop


def extract_track_keys(track_keys):
    """Extract and print the actual data from the trackKeys property"""
    if isinstance(track_keys, (list, tuple)):
        return [extract_track_keys(item) for item in track_keys]
    elif hasattr(track_keys, "to_dict"):
        return track_keys.to_dict()
    else:
        return track_keys


def add_to_track_keys(track_keys, new_data):
    """Add new data to the trackKeys property"""

    if isinstance(track_keys, idprop.types.IDPropertyArray):
        track_keys = list(track_keys)
    elif isinstance(track_keys, list):
        track_keys = track_keys

    track_keys.append(new_data)

    return track_keys


def modify_track_keys():
    for action in bpy.data.actions:
        if "constTrackKeys" in action.keys():  ## works for constTrackKeys or trackKeys
            track_keys = action["constTrackKeys"]

            converted_track_keys = convert_idproperty(track_keys)
            _LOG.info("Original trackKeys: %s", converted_track_keys)

            new_data = {
                "trackIndex": 7,
                "time": 0.050059766,
                "value": 0.00,
            }  ##populate this with the data
            updated_track_keys = add_to_track_keys(converted_track_keys, new_data)

            action["constTrackKeys"] = updated_track_keys

            updated_track_keys = convert_idproperty(action["constTrackKeys"])
            _LOG.info("Updated trackKeys: %s", updated_track_keys)


modify_track_keys()
