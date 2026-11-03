import bpy


def _find_layer_collection_by_name(name, collection):
    if collection.name == name:
        return collection
    for child in collection.children:
        found = _find_layer_collection_by_name(name, child)
        if found:
            return found
    return None


<<<<<<< Updated upstream
def set_active_collection(collection, context=None):
    context = context or bpy.context
    found = _find_layer_collection_by_name(collection.name, context.view_layer.layer_collection)
=======
def selected_meshes(context=None):
    """The selected mesh objects"""
    return [
        obj for obj in (context or bpy.context).selected_objects if obj.type == "MESH"
    ]


def set_active_collection(collection, context=None):
    context = context or bpy.context
    found = _find_layer_collection_by_name(
        collection.name, context.view_layer.layer_collection
    )
>>>>>>> Stashed changes
    if found is None:
        return False

    collection.hide_viewport = False
    found.hide_viewport = False
    collection.hide_select = False
    context.view_layer.active_layer_collection = found
    return True


<<<<<<< Updated upstream
def select_objects(objects, make_first_active=True, clear=True, reveal=False, context=None):
=======
def _reveal_object_collection(layer_collection, obj):
    """Reveal one collection path containing the object in the current view layer"""
    if obj.name in layer_collection.collection.objects or any(
        _reveal_object_collection(child, obj) for child in layer_collection.children
    ):
        layer_collection.exclude = False
        layer_collection.hide_viewport = False
        layer_collection.collection.hide_viewport = False
        layer_collection.collection.hide_select = False
        return True
    return False


def select_objects(
    objects, make_first_active=True, clear=True, reveal=False, context=None
):
>>>>>>> Stashed changes
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
<<<<<<< Updated upstream
            try:
                obj.hide_set(False)
            except Exception:
                pass
=======
            _reveal_object_collection(context.view_layer.layer_collection, obj)
>>>>>>> Stashed changes
            obj.hide_viewport = False
            obj.hide_select = False
        resolved.append(obj)

<<<<<<< Updated upstream
=======
    if reveal and resolved:
        context.view_layer.update()
    # Objects linked since the view layer last synchronized are not yet among its objects.
    if any(obj.name not in context.view_layer.objects for obj in resolved):
        context.view_layer.update()
    for obj in resolved:
        if obj.name not in context.view_layer.objects:
            raise ValueError(
                f"Object '{obj.name}' is not linked to the active view layer"
            )
        if reveal:
            obj.hide_set(False, view_layer=context.view_layer)

>>>>>>> Stashed changes
    if clear:
        for obj in list(context.selected_objects):
            obj.select_set(False)

    for obj in resolved:
        obj.select_set(True)
        context.view_layer.objects.active = obj

    if make_first_active and resolved:
        context.view_layer.objects.active = resolved[0]

    return resolved
