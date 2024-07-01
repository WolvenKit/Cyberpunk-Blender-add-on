import bpy
from mathutils import Vector, Quaternion, Euler, Matrix
from math import radians
import idprop

## I get that these are lazy but they're convenient type checks
def is_mesh(o: bpy.types.Object) -> bool:
    return isinstance(o.data, bpy.types.Mesh)


def is_armature(o: bpy.types.Object) -> bool: # I just found out I could leave annotations like that -> future presto will appreciate knowing wtf I though I was going to return 
    return isinstance(o.data, bpy.types.Armature)


def has_anims(o: bpy.types.Object) -> bool:
    return isinstance(o.data, bpy.types.Armature) and o.animation_data is not None


def rotate_quat_180(self,context):
    if context.active_object and context.active_object.rotation_quaternion:
        active_obj =  context.active_object
        active_obj.rotation_mode = 'QUATERNION'

        rotation_quat = Quaternion((0, 0, 1), radians(180))
        active_obj.rotation_quaternion = rotation_quat @ active_obj.rotation_quaternion
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
        # Update the object to reflect the changes
        active_obj.update_tag()
        active_obj.update_from_editmode()

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
        return True if obj.data.shape_keys else False
    else:
        return False

    

# Return the name of the shape key data block if the object has shape keys.
def getShapeKeyName(obj):
    if hasShapeKeys(obj):
        return obj.data.shape_keys.name        
    return ""


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
def getMods(obj):
    mods = []
    for mod in obj.modifiers:
        mods.append(mod.name)        
    return mods
    
    
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
    
    
 