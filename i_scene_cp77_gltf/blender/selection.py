import bpy

from .identity import rna_identity, rna_is_live
from .transactions import track_mutation


def _find_layer_collection_by_name(name, collection):
    if collection.name == name:
        return collection
    for child in collection.children:
        found = _find_layer_collection_by_name(name, child)
        if found:
            return found
    return None


def selected_meshes(context=None, *, include_active=False):
    """The selected mesh objects, or the active mesh when include_active is set and none is selected"""
    context = context or bpy.context
    meshes = [
        obj
        for obj in getattr(context, "selected_objects", ())
        if getattr(obj, "type", None) == "MESH"
    ]
    if meshes or not include_active:
        return meshes
    active = getattr(context, "active_object", None)
    return [active] if getattr(active, "type", None) == "MESH" else []


def _attribute_restore(owner, attribute, value):
    def restore():
        if rna_is_live(owner):
            setattr(owner, attribute, value)

    return restore


def _layer_restore(view_layer, collection, attribute, value):
    def restore():
        if not (rna_is_live(view_layer) and rna_is_live(collection)):
            return
        found = _find_layer_collection_by_name(
            collection.name, view_layer.layer_collection
        )
        if found is not None:
            setattr(found, attribute, value)

    return restore


def _hide_restore(obj, view_layer):
    def restore():
        if rna_is_live(obj) and rna_is_live(view_layer):
            obj.hide_set(True, view_layer=view_layer)

    return restore


def _clear_flag(owner, attribute, restore):
    if getattr(owner, attribute):
        track_mutation((attribute, rna_identity(owner)), restore, label=attribute)
        setattr(owner, attribute, False)


def _clear_id_flag(owner, attribute):
    _clear_flag(owner, attribute, _attribute_restore(owner, attribute, True))


def _clear_layer_flag(view_layer, layer_collection, attribute):
    _clear_flag(
        layer_collection,
        attribute,
        _layer_restore(view_layer, layer_collection.collection, attribute, True),
    )


def set_active_collection(collection, context=None):
    context = context or bpy.context
    found = _find_layer_collection_by_name(
        collection.name, context.view_layer.layer_collection
    )
    if found is None:
        return False

    _clear_id_flag(collection, "hide_viewport")
    _clear_layer_flag(context.view_layer, found, "hide_viewport")
    _clear_id_flag(collection, "hide_select")
    context.view_layer.active_layer_collection = found
    return True


def _reveal_object_collection(view_layer, layer_collection, obj):
    """Reveal one collection path containing the object in the current view layer"""
    if obj.name in layer_collection.collection.objects or any(
        _reveal_object_collection(view_layer, child, obj)
        for child in layer_collection.children
    ):
        _clear_layer_flag(view_layer, layer_collection, "exclude")
        _clear_layer_flag(view_layer, layer_collection, "hide_viewport")
        _clear_id_flag(layer_collection.collection, "hide_viewport")
        _clear_id_flag(layer_collection.collection, "hide_select")
        return True
    return False


def select_objects(
    objects, make_first_active=True, clear=True, reveal=False, context=None
):
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
            _reveal_object_collection(
                context.view_layer, context.view_layer.layer_collection, obj
            )
            _clear_id_flag(obj, "hide_viewport")
            _clear_id_flag(obj, "hide_select")
        resolved.append(obj)

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
        if reveal and obj.hide_get(view_layer=context.view_layer):
            track_mutation(
                ("hide_get", rna_identity(obj), rna_identity(context.view_layer)),
                _hide_restore(obj, context.view_layer),
                label="object hide",
            )
            obj.hide_set(False, view_layer=context.view_layer)

    if clear:
        for obj in list(context.selected_objects):
            obj.select_set(False)

    for obj in resolved:
        obj.select_set(True)
        context.view_layer.objects.active = obj

    if make_first_active and resolved:
        context.view_layer.objects.active = resolved[0]

    return resolved
