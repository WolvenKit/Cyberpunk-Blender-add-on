import bpy

# Clean up external objects (e.g. from Sketchfab). This function will flatten the hierarchy and rename the objects
# in a more Cyberpunk-specific way.

valid_object_types = [
    'MESH',
    'ARMATURE'
]

def apply_object_transformations(ob):
    try:
        mb = ob.matrix_basis
        if hasattr(ob.data, "transform"):
            ob.data.transform(mb)
        for c in ob.children:
            c.matrix_local = mb @ c.matrix_local

        ob.matrix_basis.identity()
    except Exception as e:
        print("Exception when trying to apply transformations: " + str(e))

def cleanup_names_and_apply_transformations(old_object_names):
    mesh_index = 0
    new_object_names = []
    for object_name in old_object_names:
        object =  bpy.data.objects[object_name]
        if object == None:
            continue
        apply_object_transformations(object)
        if object.type == 'ARMATURE':
            object.name = "Armature"
        if object.type == 'MESH':
            object.name = "submesh_{}_LOD_1".format(str(mesh_index).zfill(2))
            mesh_index += 1

        new_object_names.append(object.name)

    return new_object_names

# traverse the object's parent hierarchy all the way up, and collect all empties
def get_parented_empties(current_obj):
    empties = []
    if current_obj == None:
        return empties

    if current_obj.type == 'EMPTY':
        empties.append(current_obj)

    if current_obj.parent == None:
        return empties

    empties.extend(get_parented_empties(current_obj.parent))
    return empties

# if the object is nested under something we'd like to keep (an armature or a mesh), we need to re-parent it
# after removing all intermediate empties
def get_closest_valid_parent(obj):
    if obj == None or obj.parent == None:
        return None
    if obj.parent.type in valid_object_types:
        return obj.parent
    return get_closest_valid_parent(obj.parent)

def CP77_cleanup_external_export(importedObjects):

    empties=[]
    


    # collect mesh names for iterating
    validObjectNames = sorted([obj.name for obj in filter(lambda obj: obj.type in valid_object_types, importedObjects)])

    # clear parents, keep transforms
    for ob in importedObjects:
        try:
            empties.extend(get_parented_empties(ob))
            bpy.ops.object.select_all(action="DESELECT")
            new_parent = get_closest_valid_parent(ob)
            if new_parent == ob.parent:
                continue
            ob.select_set(state=True)
            bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
            if (new_parent != None and new_parent != ob):
                ob.parent = new_parent
        except Exception as e:
            print("Exception while cleaning up object: " + str(e))
            continue

    # delete empties
    counter = 0
    empty_names = [e.name for e in empties]
    try:
        while len(empty_names) and counter < 99:
            counter += 1
            for name in empty_names.copy():
                e = bpy.data.objects.get(name)
                if e == None:
                    empty_names.remove(name)
                    continue
                if not e.children:
                    bpy.data.objects.remove(e)
                    empty_names.remove(name)

    except Exception as e:
        print("Exception when trying to delete empties: " + str(e))

    new_object_names = cleanup_names_and_apply_transformations(validObjectNames)

    for object_name in new_object_names:
        bpy.data.objects[object_name].select_set(True)


