import bpy
from mathutils import Vector, Quaternion
from typing import Dict, List
from math import radians
import idprop
import bmesh
import os
from collections import defaultdict
from typing import List, Dict, Set

# Internal state for restoring
_previous_selection = []
_previous_active = None
_previous_mode = None
_dummy_name = "TemporaryContextObject"

def compute_model_space(local_transforms, bone_parents):
    """
    Converts local-space transforms to model-space transforms using bone hierarchy.
    """
    model_space = [None] * len(local_transforms)
    for i, (trans, rot) in enumerate(local_transforms):
        if bone_parents[i] == -1:
            # Root bone: LS == MS
            model_space[i] = (trans.copy(), rot.copy())
        else:
            p_trans, p_rot = model_space[bone_parents[i]]
            ms_trans = p_trans + p_rot @ trans
            ms_rot = p_rot @ rot
            model_space[i] = (ms_trans, ms_rot)
    return model_space

def compute_local_space(model_transforms, bone_parents):
    """
    Converts model-space transforms to local-space transforms using bone hierarchy.
    """
    local_space = [None] * len(model_transforms)
    for i, (trans, rot) in enumerate(model_transforms):
        if bone_parents[i] == -1:
            local_space[i] = (trans.copy(), rot.copy())
        else:
            p_trans, p_rot = model_transforms[bone_parents[i]]
            inv_p_rot = p_rot.inverted()
            ls_trans = inv_p_rot @ (trans - p_trans)
            ls_rot = inv_p_rot @ rot
            local_space[i] = (ls_trans, ls_rot)
    return local_space

import os
import unicodedata
import logging
from collections import defaultdict
from typing import List, Dict

#basic logging to report errors instead of silently passing
logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(levelname)s - %(message)s')

def normalize(path: str) -> str:
    """
    Normalize path for cross-platform and Unicode safety, ensuring it is an absolute path.
    """
    # os.path.abspath to ensure all paths are full and unambiguous.
    return unicodedata.normalize('NFC', os.path.abspath(os.path.normpath(path)))


def dataKrash(root: str, extensions: List[str]) -> Dict[str, Set[str]]:
    """
    Recursively find files by extension using os.scandir, returning full absolute paths.
    The output is a dictionary mapping each extension to a SET of file paths.
    """
    normalized_root = normalize(root)
    if not os.path.isdir(normalized_root):
        logging.error(f"Root directory not found: {normalized_root}")
        return {}

    # Normalize and sort extensions by length (descending)
    norm_exts = sorted({ext.lower() for ext in extensions}, key=len, reverse=True)
    ext_map = defaultdict(set)

    def recurse(folder: str):
        try:
            for entry in os.scandir(folder):
                if entry.is_file():
                    name_lower = entry.name.lower()
                    for ext in norm_exts:
                        if name_lower.endswith(ext):
                            full_path = normalize(entry.path)
                            ext_map[ext].add(full_path)
                            break
                elif entry.is_dir():
                    recurse(entry.path)
        except (PermissionError, FileNotFoundError) as e:
            logging.warning(f"Could not scan {folder}: {e}")

    recurse(normalized_root)
    return dict(ext_map)

mode_map = {
    'OBJECT': 'OBJECT',
    'EDIT_ARMATURE': 'EDIT',
    'POSE': 'POSE',
    'EDIT_MESH': 'EDIT',
    'EDIT_CURVE': 'EDIT',
    'EDIT_CURVES': 'EDIT',
    'EDIT_SURFACE': 'EDIT',
    'EDIT_TEXT': 'EDIT',
    'EDIT_METABALL': 'EDIT',
    'EDIT_LATTICE': 'EDIT',
    'EDIT_GREASE_PENCIL': 'EDIT',
    'EDIT_POINT_CLOUD': 'EDIT',
    'EDIT_GPENCIL': 'EDIT',
    'SCULPT': 'OBJECT',
    'SCULPT_CURVES': 'OBJECT',
    'SCULPT_GPENCIL': 'OBJECT',
    'SCULPT_GREASE_PENCIL': 'OBJECT',
    'PAINT_WEIGHT': 'OBJECT',
    'PAINT_VERTEX': 'OBJECT',
    'PAINT_TEXTURE': 'OBJECT',
    'PAINT_GPENCIL': 'OBJECT',
    'PAINT_GREASE_PENCIL': 'OBJECT',
    'WEIGHT_GPENCIL': 'OBJECT',
    'WEIGHT_GREASE_PENCIL': 'OBJECT',
    'VERTEX_GPENCIL': 'OBJECT',
    'VERTEX_GREASE_PENCIL': 'OBJECT',
    'PARTICLE': 'OBJECT',
    }

def parse_transform_data(data: Dict) -> Dict[str, List[float]]:
    """
    Parses a transform dictionary and returns a normalized transform with:
    - position: [x, y, z]
    - orientation: [i, j, k, r]
    - scale: [x, y, z]
    """
    def parse_position(pos_dict):
        def get_val(val):
            if isinstance(val, dict) and 'Bits' in val:
                return val['Bits'] / 131072
            return float(val) if isinstance(val, (int, float)) else 0.0
        return [
            get_val(pos_dict.get('x')),
            get_val(pos_dict.get('y')),
            get_val(pos_dict.get('z')),
        ]

    def parse_orientation(ori_dict):
        return [
            ori_dict.get('i', 0.0),
            ori_dict.get('j', 0.0),
            ori_dict.get('k', 0.0),
            ori_dict.get('r', 1.0),
        ]

    def parse_scale(scale_dict):
        return [
            scale_dict.get('X', 1.0),
            scale_dict.get('Y', 1.0),
            scale_dict.get('Z', 1.0),
        ]

    return {
        'position': parse_position(data.get('Position', {})),
        'orientation': parse_orientation(data.get('Orientation', {})),
        'scale': parse_scale(data.get('scale', {})),
    }

def safe_mode_switch(target_mode: str):
    """
    Safely switches to the given mode. Creates a temporary object if no valid context is available.
    Stores selection, active object, and mode to restore later.
    """
    global _previous_selection, _previous_active, _previous_mode
    dummy = None
    ctx = bpy.context
    _previous_mode = ctx.mode
    _previous_selection = list(ctx.selected_objects)
    _previous_active = ctx.active_object

    # If the desired mode is already active, do nothing
    if ctx.mode == target_mode:
        return

    # If context doesn't support mode switch, create a dummy
    if not bpy.ops.object.mode_set.poll():
        bpy.ops.object.select_all(action='DESELECT')
        bpy.ops.mesh.primitive_cube_add(size=0.1, location=(0, 0, 0))
        dummy = bpy.context.active_object
        dummy.name = _dummy_name
        dummy.hide_viewport = True
        dummy.hide_render = True
        dummy.hide_set(True)
        dummy.select_set(False)

    try:
        bpy.ops.object.mode_set(mode=target_mode)
    except Exception as e:
        print(f"[safe_mode_switch] Failed to switch to mode {target_mode}: {e}")

    if dummy:
        bpy.data.objects.remove(dummy, do_unlink=True)

def restore_previous_context():
    """
    Restores the previous selection, active object, and mode.

    """
    global _previous_selection, _previous_active, _previous_mode

    bpy.ops.object.select_all(action='DESELECT')
    for obj in _previous_selection:
        if obj.name in bpy.data.objects:
            obj.select_set(True)

    if _previous_active and _previous_active.name in bpy.data.objects:
        bpy.context.view_layer.objects.active = _previous_active

    if _previous_mode == get_safe_mode():
        pass
    else:
        # Attempt to restore mode if possible
        try:
                safe_mode_switch(_previous_mode)
        except Exception as e:
            print(f"[CP77 Blender Addon] Failed to restore mode {_previous_mode}: {e}")

    _previous_selection.clear()
    _previous_active = None
    _previous_mode = None

def get_safe_mode():
    """
    Maps the current context mode to a valid mode string for bpy.ops.object.mode_set().
    Returns one of: 'OBJECT', 'EDIT', 'POSE'.
    """
    return mode_map.get(bpy.context.mode, 'OBJECT')
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
