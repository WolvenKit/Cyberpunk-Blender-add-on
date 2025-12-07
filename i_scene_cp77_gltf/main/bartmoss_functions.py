import bpy
import idprop
import bmesh
import os
import unicodedata
import logging
from mathutils import Vector, Quaternion, Matrix, Vector
from math import radians
from collections import defaultdict
from typing import List, Dict, Set

_stored_context = None

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
    'SCULPT': 'SCULPT',
    'SCULPT_CURVES': 'SCULPT',
    'SCULPT_GPENCIL': 'SCULPT',
    'SCULPT_GREASE_PENCIL': 'SCULPT',
    'PAINT_WEIGHT': 'WEIGHT_PAINT',
    'PAINT_VERTEX': 'VERTEX_PAINT',
    'PAINT_TEXTURE': 'TEXTURE_PAINT',
    'PAINT_GPENCIL': 'PAINT_GPENCIL',
    'PAINT_GREASE_PENCIL': 'PAINT_GREASE_PENCIL',
    'WEIGHT_GPENCIL': 'WEIGHT_PAINT',
    'WEIGHT_GREASE_PENCIL': 'WEIGHT_PAINT',
    'VERTEX_GPENCIL': 'VERTEX_PAINT',
    'VERTEX_GREASE_PENCIL': 'VERTEX_PAINT',
    'PARTICLE': 'PARTICLE_EDIT',
}

class CP77Context:
    """Somewhere to store everything needed to restore the user's state."""

    def __init__(self):
        self.mode = None
        self.active_object = None
        self.selected_objects = []
        self.object_visibility = {}
        self.cursor_location = None

    def store(self):
        """Store current user state."""
        context = bpy.context

        # Store mode
        self.mode = context.mode  # Store actual mode, not mapped

        # Store active and selected objects
        self.active_object = context.view_layer.objects.active
        self.selected_objects = list(context.selected_objects)

        # Store visibility for objects we're working with
        for obj in self.selected_objects:
            if obj:
                self.object_visibility[obj.name] = {
                    'hide_viewport': obj.hide_viewport,
                    'hide_select': obj.hide_select,
                    'hide_get': obj.hide_get(),
                }

        # Also store active object visibility if not in selection
        if self.active_object and self.active_object.name not in self.object_visibility:
            self.object_visibility[self.active_object.name] = {
                'hide_viewport': self.active_object.hide_viewport,
                'hide_select': self.active_object.hide_select,
                'hide_get': self.active_object.hide_get(),
            }

        # Store cursor
        self.cursor_location = tuple(context.scene.cursor.location)

    def restore(self):
        """Restore user state."""
        context = bpy.context

        # Restore visibility first (before selection)
        for obj_name, vis_state in self.object_visibility.items():
            if obj_name in bpy.data.objects:
                obj = bpy.data.objects[obj_name]
                try:
                    obj.hide_viewport = vis_state['hide_viewport']
                    obj.hide_select = vis_state['hide_select']
                    obj.hide_set(vis_state['hide_get'])
                except:
                    pass  # Object might be deleted

        # Restore mode (use normalized mode for safety)
        if self.mode:
            target_mode = mode_map.get(self.mode, self.mode)
            current_mode = mode_map.get(context.mode, context.mode)
            if current_mode != target_mode:
                try:
                    bpy.ops.object.mode_set(mode=target_mode)
                except:
                    pass  # Mode might not be available

        # Restore selection
        try:
            bpy.ops.object.select_all(action='DESELECT')
            for obj in self.selected_objects:
                if obj and obj.name in bpy.data.objects:
                    obj.select_set(True)
        except:
            pass

        # Restore active object
        if self.active_object and self.active_object.name in bpy.data.objects:
            context.view_layer.objects.active = self.active_object

        # Restore cursor
        if self.cursor_location:
            context.scene.cursor.location = self.cursor_location

def store_current_context():
    """Store the current user context."""
    global _stored_context
    _stored_context = CP77Context()
    _stored_context.store()

def restore_previous_context():
    """Restore the previously stored context."""
    global _stored_context
    if _stored_context:
        _stored_context.restore()
        _stored_context = None  # Clear after restoring
    else:
        print("Warning: No saved context to restore")

def get_safe_mode():
    """
    Get current mode mapped to a valid mode string for bpy.ops.object.mode_set().
     - now properly maps 'SCULPT', 'VERTEX_PAINT', 'WEIGHT_PAINT', 'TEXTURE_PAINT', 'PARTICLE_EDIT'
    """
    return mode_map.get(bpy.context.mode, 'OBJECT')

def safe_mode_switch(target_mode: str):
    """
    Switch to target mode. Handles mode normalization.
    """
    if not target_mode:
        return

    # Normalize the target mode
    target_mode = mode_map.get(target_mode, target_mode)

    # Get current normalized mode
    current_mode = get_safe_mode()

    # Already in target mode
    if current_mode == target_mode:
        return

    # Ensure valid context for mode switching
    if not bpy.context.active_object:
        # Need an object for mode switching
        # Try to find one
        if bpy.context.selected_objects:
            bpy.context.view_layer.objects.active = bpy.context.selected_objects[0]
        else:
            # Create temporary object
            bpy.ops.mesh.primitive_cube_add(size=0.1, location=(0, 0, 0))
            temp = bpy.context.active_object
            temp.name = "TempModeSwitch"
            temp.hide_viewport = True

            try:
                bpy.ops.object.mode_set(mode=target_mode)
            finally:
                # Remove temp object
                bpy.data.objects.remove(temp, do_unlink=True)
            return

    # Switch mode
    try:
        bpy.ops.object.mode_set(mode=target_mode)
    except Exception as e:
        print(f"Failed to switch to mode {target_mode}: {e}")

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

def iter_edited_meshes():
    """Return only the meshes that are actually being edited right now. Useful for bmesh.from_edit_mesh"""
    c = bpy.context
    if c.mode == 'EDIT_MESH':
        objs = getattr(c, "objects_in_mode_unique_data", None)
        if not objs and c.edit_object:
            objs = [c.edit_object]
        return [o for o in (objs or []) if o and o.type == 'MESH']
    return []

def get_armature_modifier(ob: bpy.types.Object):
    """
    Returns the Armature modifier that has an object assigned, else None.
    """
    return next((m for m in ob.modifiers
                 if m.type == 'ARMATURE' and getattr(m, "object", None)), None)

# ENSURE ARMATURE + GROUP/BONE CONSISTENCY -
def ensure_armature_and_groups(ob: bpy.types.Object):
    """
    - Finds the armature modifier and ensures it references the parent armature if present.
    - Makes the armature visible & selected (no operators).
    - Validates that every vertex group has a bone with the same name.
    Raises ValueError on failure.
    """
    arm_mod = get_armature_modifier(ob)
    if not arm_mod:
        raise ValueError(
            f"Armature missing from: {ob.name} Armatures are required for movement. "
            "If this is intentional, try 'export as static prop'. See https://tinyurl.com/armature-missing"
        )

    arm = arm_mod.object

    # Visibility & selection for export
    arm.hide_set(False)
    arm.select_set(True)

    # If parent is an armature, ensure the modifier references it
    if ob.parent and ob.parent.type == 'ARMATURE' and arm_mod.object != ob.parent:
        arm_mod.object = ob.parent
        arm = arm_mod.object

    # Compare vertex group names with armature bone names
    bone_names = {b.name for b in arm.data.bones}
    group_names = {g.name for g in ob.vertex_groups}
    missing = group_names - bone_names

    if missing:
        lst = ", ".join(sorted(missing))
        raise ValueError(
            "The following vertex groups are not assigned to a bone, this will result in blender creating a "
            f"neutral_bone and cause Wolvenkit import to fail:    {lst}\n"
            "See https://tinyurl.com/unassigned-bone"
        )

def _locrotscale(loc, rot, scale):
    return Matrix.LocRotScale(loc, rot, scale)

def apply_xform_to_mesh(
    ob: bpy.types.Object,
    apply_location=True,
    apply_rotation=True,
    apply_scale=True,
    include_delta=True,
    affect_shape_keys=True,
    make_single_user=True,
):
    """
    Apply the object's local transform to its mesh data,
    then reset the object's local transform to identity.
    """
    if ob.type != 'MESH':
        return

    me = ob.data
    if make_single_user and me.users > 1:
        ob.data = me.copy()
        me = ob.data

    # Decompose local (basis) and delta
    basis = ob.matrix_basis.copy()
    loc_b = basis.to_translation()
    rot_b = basis.to_quaternion()
    scl_b = basis.to_scale()

    if include_delta:
        dloc = ob.delta_location.copy()
        drot = ob.delta_rotation_euler.to_quaternion()
        dscl = ob.delta_scale.copy()
    else:
        dloc = Vector((0,0,0))
        drot = Quaternion((1,0,0,0))
        dscl = Vector((1,1,1))

    loc = loc_b if apply_location else Vector((0,0,0))
    rot = rot_b if apply_rotation else Quaternion((1,0,0,0))
    scl = scl_b if apply_scale    else Vector((1,1,1))

    M = _locrotscale(loc, rot, scl) @ _locrotscale(dloc, drot, dscl)

    # Early out if identity
    if M.is_identity:
        return

    # --- Transform geometry ---
    if ob.mode == 'EDIT':
        bm = bmesh.from_edit_mesh(me)
        bm.verts.ensure_lookup_table()
        bm.transform(M)
        bm.normal_update()
        bmesh.update_edit_mesh(me, loop_triangles=False, destructive=False)
    else:
        me.transform(M)
        me.calc_normals()

    # Transform shape keys (keep them aligned with new basis)
    if affect_shape_keys and me.shape_keys:
        for kb in me.shape_keys.key_blocks:
            # Transform absolute positions of each key
            for kd in kb.data:
                kd.co = M @ kd.co

    # --- Reset object local transforms to identity ---
    ob.matrix_basis.identity()
    if include_delta:
        ob.delta_location = (0.0, 0.0, 0.0)
        ob.delta_rotation_euler = (0.0, 0.0, 0.0)
        ob.delta_scale = (1.0, 1.0, 1.0)

    # clear and let Blender recalc custom split normals
    if getattr(me, "has_custom_normals", False):
        me.use_auto_smooth = me.use_auto_smooth  # keep flag
        me.calc_normals_split()
        me.free_normals_split()

def rotate_quat_180(self, context):
    from math import radians
    q = Quaternion((0, 0, 1), radians(180))
    M = Matrix.LocRotScale((0,0,0), q, (1,1,1))
    for obj in context.selected_objects or []:
        apply_object_xform_to_mesh(obj, M)
    return {'FINISHED'}

# just a stub now that calls select_objects
def select_object(obj):
    return(f"{select_objects(obj)}")

def find_layer_collection_by_name(collName, coll):
    found = None
    if (coll.name == collName):
        return coll
    for layer in coll.children:
        found = find_layer_collection_by_name(collName, layer)
        if found:
            return found
    return None

def set_active_collection(collection, context=None):
    c = context or bpy.context

    found = find_layer_collection_by_name(collection.name, c.view_layer.layer_collection)
    if found is None:
        return False

    collection.hide_viewport = False
    found.hide_viewport = False
    collection.hide_select = False
    c.view_layer.active_layer_collection = found
    return True

# deselects other objects and fully selects an object in both the viewport and the outliner
# if this fails silently, use set_active_collection
def select_objects(objs, make_first_active=True, clear=True, reveal=False, context=None):
    c = context or bpy.context

    # Normalize to a list
    if objs is None:
        objs = []
    elif isinstance(objs, (list, tuple, set)):
        objs = list(objs)
    else:
        objs = [objs]

    # Resolve names → objects; filter Nones
    resolved = []
    for o in objs:
        if isinstance(o, bpy.types.Object):
            ob = o
        elif isinstance(o, str):
            ob = bpy.data.objects.get(o)
        else:
            ob = None

        if not ob:
            continue

        if reveal:
            # ensure selectable & visible
            try:
                ob.hide_set(False)
            except Exception:
                pass
            ob.hide_viewport = False
            ob.hide_select = False
        resolved.append(ob)

    if clear:
        for o in list(c.selected_objects):
            o.select_set(False)

    for ob in resolved:
        ob.select_set(True)
        c.view_layer.objects.active = ob

    if make_first_active and resolved:
        c.view_layer.objects.active = resolved[0]

    return resolved

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
    for prop in modifier.bl_rna.properties:
        if prop.is_readonly:
            continue
        if prop.identifier in {'rna_type', 'name', 'type'}:
            continue
        if prop.type in {'BOOLEAN', 'INT', 'FLOAT', 'ENUM'}:
            props.append(prop.identifier)
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
