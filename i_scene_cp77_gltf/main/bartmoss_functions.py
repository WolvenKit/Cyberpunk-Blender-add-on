import bpy
from mathutils import Vector, Quaternion, Euler, Matrix
from typing import Dict, List
from math import radians
import idprop
import bmesh
import os
import unicodedata
from collections import defaultdict

# Internal state for restoring
_previous_selection = []
_previous_active = None
_previous_mode = None
_dummy_name = "TemporaryContextObject"


def normalize(path):
    """Normalize path for cross-platform and Unicode safety."""
    return unicodedata.normalize('NFC', os.path.abspath(os.path.normpath(path)))

def dataKrash(root, extensions):
    """Recursively find files by extension, matching longest ones first, returning keys with leading dots."""
    root = normalize(root)
    # Normalize and sort extensions by length (descending)
    norm_exts = sorted({ext.lower() for ext in extensions}, key=len, reverse=True)
    ext_map = defaultdict(list)

    def recurse(folder):
        try:
            for entry in os.scandir(folder):
                if entry.is_file():
                    name_lower = entry.name.lower()
                    for ext in norm_exts:
                        if name_lower.endswith(ext):
                            ext_map[ext].append(normalize(entry.path))
                            break
                elif entry.is_dir():
                    recurse(entry.path)
        except (PermissionError, FileNotFoundError):
            pass #todo: some useful output here in cases of errors

    recurse(root)
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
