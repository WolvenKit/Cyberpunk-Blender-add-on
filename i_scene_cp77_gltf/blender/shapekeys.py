def has_shape_keys(obj):
    data = getattr(obj, "data", None)
    shape_keys = getattr(data, "shape_keys", None)
    return bool(shape_keys and shape_keys.key_blocks)


<<<<<<< Updated upstream
def shape_key_names(obj):
    if not has_shape_keys(obj):
        return ()
    return tuple(obj.data.shape_keys.key_blocks.keys())


=======
>>>>>>> Stashed changes
def shape_key_by_name(obj, name):
    if not has_shape_keys(obj):
        return None
    return obj.data.shape_keys.key_blocks.get(name)
