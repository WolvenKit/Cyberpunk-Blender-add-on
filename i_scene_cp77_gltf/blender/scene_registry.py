from ..assetio.values import json_array, json_text


def stored_names(scene, key):
    if scene is None:
        return []
    return [str(value) for value in json_array(scene.get(key)) if value]


def store_names(scene, key, names):
    if scene is None:
        return
    encoded = json_text(list(dict.fromkeys(str(name) for name in names if name)))
    if str(scene.get(key, "") or "") != encoded:
        scene[key] = encoded
