import bpy
from mathutils import Vector, Quaternion, Euler, Matrix
from math import radians
import idprop
import bmesh

## I get that these are lazy but they're convenient type checks
def is_mesh(o: bpy.types.Object) -> bool:
    return isinstance(o.data, bpy.types.Mesh)
 
def world_mtx(armature, bone):
    return armature.convert_space(bone, bone.matrix, from_space='POSE', to_space='WORLD')

def pose_mtx(armature, bone, mat):
    return armature.convert_space(bone, mat, from_space='WORLD', to_space='POSE')

def is_armature(o: bpy.types.Object) -> bool: # I just found out I could leave annotations like that -> future presto will appreciate knowing wtf I though I was going to return 
    return isinstance(o.data, bpy.types.Armature)

def has_anims(o: bpy.types.Object) -> bool:
    return isinstance(o.data, bpy.types.Armature) and o.animation_data is not None

def rotate_quat_180(self,context):
    if context.selected_objects is not None:
        for obj in context.selected_objects:
            obj.rotation_mode = 'QUATERNION'

            rotation_quat = Quaternion((0, 0, 1), radians(180))
            obj.rotation_quaternion = rotation_quat @ obj.rotation_quaternion
            bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
            # Update the object to reflect the changes
            obj.update_tag()
            obj.update_from_editmode()

        # Update the scene to see the changes
        bpy.context.view_layer.update()

    else:
        return{'FINISHED'}

# deselects other objects and fully selects an object in both the viewport and the outliner
def select_object(obj):
    for o in bpy.context.selected_objects:
        o.select_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

## returns the volume of a given mesh by applying a rigid body with a material density of 1 and then returning the calculated mass
def calculate_mesh_volume(obj):
    select_object(obj)
    bpy.ops.rigidbody.object_add()
    bpy.ops.rigidbody.mass_calculate(material='Custom', density=1) # density in kg/m^3
    volume = obj.rigid_body.mass
    bpy.ops.rigidbody.objects_remove()
    return volume
    
## Returns True if the given object has shape keys, works for meshes and curves
def hasShapeKeys(obj):
    if obj.id_data.type in ['MESH', 'CURVE']:
        return obj.data.shape_keys != None
        
def getShapeKeyNames(obj):
    if hasShapeKeys(obj):
        key_names = []
        for key_block in obj.data.shape_keys.key_blocks:
            key_names.append(key_block.name)
        return key_names       
    return ""

# Return the name of the shape key data block if the object has shape keys.
def getShapeKeyByName(obj, name):
    if hasShapeKeys(obj):
        for key_block in obj.data.shape_keys.key_blocks:
            if key_block.name == name:
                return key_block
    return None

def setActiveShapeKey(obj, name):
    shape_key = getShapeKeyByName(obj, name)
    if shape_key:
        for index, key_block in enumerate(obj.data.shape_keys.key_blocks):
            if key_block == shape_key:
                obj.active_shape_key_index = index
                return shape_key
    return False

# returns a dictionary with all the property names for the objects shape keys.
def getShapeKeyProps(obj):

    props = {}
    
    if hasShapeKeys(obj):
        for prop in obj.data.shape_keys.key_blocks:
            props[prop.name] = prop.value
            
    return props

# returns a list of the given objects custom properties.
def getCustomProps(obj):

    props = []
    
    for prop in obj.keys():
        if prop not in '_RNA_UI' and isinstance(obj[prop], (int, float, list, idprop.types.IDPropertyArray)):
            props.append(prop)
            
    return props

# returns a list of modifiers for the given object
def getModNames(obj):
    mods = []
    for mod in obj.modifiers:
        mods.append(mod.name)        
    return mods

def getModByName(obj, name):
    for mod in obj.modifiers:
        if mod.name == name:
            return mod
    return None    

# returns a list with the modifier properties of the given modifier.
def getModProps(modifier):
    props = []    
    for prop, value in modifier.bl_rna.properties.items():
        if isinstance(value, bpy.types.FloatProperty):
            props.append(prop)            
    return props

# checks the active object for a material by name and returns the material if found
def getMaterial(name):
    obj = bpy.context.active_object
    if obj:
        index = obj.active_material_index
        if index is None:
            return
        mat = obj.material_slots[index].material
        if mat and mat.node_tree and mat.node_tree.name == name:
            return mat   

def UV_by_bounds(selected_objects):
    current_mode = bpy.context.object.mode
    min_vertex = Vector((float('inf'), float('inf'), float('inf')))
    max_vertex = Vector((float('-inf'), float('-inf'), float('-inf')))
    for obj in selected_objects:
        if obj.type == 'MESH':
            matrix = obj.matrix_world
            mesh = obj.data
            for vertex in mesh.vertices:
                vertex_world = matrix @ vertex.co
                min_vertex = Vector(min(min_vertex[i], vertex_world[i]) for i in range(3))
                max_vertex = Vector(max(max_vertex[i], vertex_world[i]) for i in range(3))

    for obj in selected_objects:
        if  len(obj.data.uv_layers)<1:
            me = obj.data
            bpy.ops.object.mode_set(mode='EDIT', toggle=False)
            bm = bmesh.from_edit_mesh(me)
            
            uv_layer = bm.loops.layers.uv.verify()
            
            # adjust uv coordinates
            for face in bm.faces:
                for loop in face.loops:
                    loop_uv = loop[uv_layer]
                    # use xy position of the vertex as a uv coordinate
                    loop_uv.uv[0]=(loop.vert.co.x-min_vertex[0])/(max_vertex[0]-min_vertex[0])
                    loop_uv.uv[1]=(loop.vert.co.y-min_vertex[1])/(max_vertex[1]-min_vertex[1])

            bmesh.update_edit_mesh(me)
    bpy.ops.object.mode_set(mode=current_mode)   
 
