import bpy


def _find_layer_collection_by_name(name, collection):
    if collection.name == name:
        return collection
    for child in collection.children:
        found = _find_layer_collection_by_name(name, child)
        if found:
            return found
    return None


def set_active_collection(collection, context=None):
    context = context or bpy.context
    found = _find_layer_collection_by_name(collection.name, context.view_layer.layer_collection)
    if found is None:
        return False

    collection.hide_viewport = False
    found.hide_viewport = False
    collection.hide_select = False
    context.view_layer.active_layer_collection = found
    return True


def select_objects(objects, make_first_active=True, clear=True, reveal=False, context=None):
    context = context or bpy.context
    if objects is None:
        objects = []
    elif isinstance(objects, (list, tuple, set)):
        objects = list(objects)
    else:
        objects = [objects]

    resolved = []
    for value in objects:
        if isinstance(value, bpy.types.Object):
            obj = value
        elif isinstance(value, str):
            obj = bpy.data.objects.get(value)
        else:
            obj = None

        if not obj:
            continue

        if reveal:
            try:
                obj.hide_set(False)
            except Exception:
                pass
            obj.hide_viewport = False
            obj.hide_select = False
        resolved.append(obj)

    if clear:
        for obj in list(context.selected_objects):
            obj.select_set(False)

    for obj in resolved:
        obj.select_set(True)
        context.view_layer.objects.active = obj

    if make_first_active and resolved:
        context.view_layer.objects.active = resolved[0]

    return resolved
