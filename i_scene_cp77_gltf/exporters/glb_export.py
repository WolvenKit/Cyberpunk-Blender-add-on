import os
import bpy
import bmesh
import numpy as np
from ..animtools import reset_armature
from ..main.common import show_message
from ..animtools.tracks import export_anim_tracks
from ..main.bartmoss_functions import (
    store_current_context, restore_previous_context,
    get_safe_mode, safe_mode_switch, select_objects,
    set_active_collection,
    )
POSE_EXPORT_OPTIONS = {
    'export_animations': True,
    'export_anim_slide_to_zero': True,
    'export_animation_mode': 'ACTIONS',
    'export_anim_single_armature': True,
    'export_bake_animation': False,
    }

RED_COLOR = (1, 0, 0, 1)  # RGBA
GARMENT_CAP_NAME = "_GarmentSupportCap"
GARMENT_WEIGHT_NAME = "_GarmentSupportWeight"

EXPORT_DEFAULTS = {
    'system': 'METRIC',
    'length_unit': 'METERS',
    'scale_length': 1.0,
    'system_rotation': 'DEGREES',
    'mass_unit': 'KILOGRAMS',
    'temperature_unit': 'KELVIN',
    'time_unit': 'SECONDS',
    'use_separate': False,
    }

# Vertex count limit
VERT_LIMIT = 65535

# Quantization for float comparisons
_Q = 1_000_000

# Tolerance values
WEIGHT_EPSILON = 1e-5

def default_cp77_options():
    """Build default glTF export options"""
    major, minor = bpy.app.version[:2]
    options = {
        'export_format': 'GLB',
        'check_existing': True,
        'export_skins': True,
        'export_yup': True,
        'export_cameras': False,
        'export_materials': 'NONE',
        'export_all_influences': True,
        'export_lights': False,
        'export_apply': False,
        'export_extras': True,
    }
    if major >= 4:
        options.update({
            'export_image_format': 'NONE',
            'export_try_sparse_sk': False,
        })
        if minor >= 1:
            options.update({
                'export_shared_accessors': True,
                'export_try_omit_sparse_sk': False,
            })
    return options

def cp77_mesh_options():
    """Mesh-specific export options."""
    major, minor = bpy.app.version[:2]
    options = {
        'export_animations': False,
        'export_tangents': True,
        'export_normals': True,
        'export_morph_tangent': True,
        'export_morph_normal': True,
        'export_morph': True,
        'export_attributes': True,
    }
    if major < 4:
        options.update({'export_colors': True})
        if minor >= 2:
            options.update({
                "export_all_vertex_colors ": True,
                "export_active_vertex_color_when_no_material": True,
            })
    return options

def pose_export_options():
    """Get pose export options (returns copy to avoid mutation)."""
    return POSE_EXPORT_OPTIONS.copy()

_excluded_objects_cache = None
_excluded_cache_timestamp = 0

def get_excluded_objects():
    """A cached set of objects in glTF_not_exported collection"""
    # This should work regardless of user language selection - gltf_not_exported is explicitly defined in Khronos' code
    global _excluded_objects_cache, _excluded_cache_timestamp

    # Simple cache invalidation using scene update
    current_time = bpy.context.scene.frame_current

    if _excluded_objects_cache is None or current_time != _excluded_cache_timestamp:
        _excluded_objects_cache = set()
        if "glTF_not_exported" in bpy.data.collections:
            not_exported_coll = bpy.data.collections["glTF_not_exported"]

            def get_all_objects_recursive(coll):
                objects = set(coll.objects)
                for child in coll.children:
                    objects.update(get_all_objects_recursive(child))
                return objects

            _excluded_objects_cache = get_all_objects_recursive(not_exported_coll)
        _excluded_cache_timestamp = current_time

    return _excluded_objects_cache

def clear_excluded_cache():
    """Clear the excluded objects cache."""
    global _excluded_objects_cache, _excluded_cache_timestamp
    _excluded_objects_cache = None
    _excluded_cache_timestamp = 0

def add_garment_cap(mesh):
    """Add garment support color attributes to mesh."""
    cap_layer = mesh.data.color_attributes.get(GARMENT_CAP_NAME)
    weight_layer = mesh.data.color_attributes.get(GARMENT_WEIGHT_NAME)

    if cap_layer is None:
        cap_layer = mesh.data.color_attributes.new(
            name=GARMENT_CAP_NAME, domain='CORNER', type='BYTE_COLOR'
        )

    if weight_layer is None:
        weight_layer = mesh.data.color_attributes.new(
            name=GARMENT_WEIGHT_NAME, domain='CORNER', type='BYTE_COLOR'
        )

    # Paint cap layer red
    if cap_layer is not None:
        n = len(cap_layer.data)
        if n:
            cap_layer.data.foreach_set("color", RED_COLOR * n)

def save_user_settings_and_reset_to_default():
    """Back up user's workbench configuration and reset to factory defaults."""
    us = bpy.context.scene.unit_settings
    user_settings = {
        'bpy_context': bpy.context.mode,
        'system': us.system,
        'length_unit': us.length_unit,
        'scale_length': us.scale_length,
        'system_rotation': us.system_rotation,
        'mass_unit': us.mass_unit,
        'temperature_unit': us.temperature_unit,
        'time_unit': us.time_unit,
        'use_separate': us.use_separate,
    }
    for key, value in EXPORT_DEFAULTS.items():
        setattr(us, key, value)
    return user_settings

def restore_user_settings(user_settings):
    """Restore user's previous settings."""
    us = bpy.context.scene.unit_settings
    for key, value in user_settings.items():
        if key == 'bpy_context':
            continue
        setattr(us, key, value)
    if bpy.context.mode != user_settings['bpy_context']:
        try:
            bpy.ops.object.mode_set(mode=user_settings['bpy_context'])
        except:
            pass

_Q = 1_000_000  # quantization to make float comparisons robust

def _loop_verts(tempshit):
    n_loops = len(tempshit.loops)
    lv = np.empty(n_loops, dtype=np.int32)
    tempshit.loops.foreach_get("vertex_index", lv)
    return lv

def _quantize(arr_f32, scale=_Q):
    return np.round(arr_f32 * scale).astype(np.int64, copy=False)

def count_per_vertex(vertex_col, attr_cols, n_verts):
    """
    Count how many unique attr tuples each vertex has across its loops.
    vertex_col: (n_loops,) int64/int32 with vertex indices
    attr_cols: list of 1D int64 arrays (same length as vertex_col)
    returns: (n_verts,) int32 counts
    """
    if not attr_cols:
        return np.zeros(n_verts, dtype=np.int32)
    S = np.column_stack([vertex_col] + attr_cols)  # (n_loops, k)
    U = np.unique(S, axis=0)                       # unique (v, attrs...)
    counts = np.bincount(U[:, 0].astype(np.int32, copy=False), minlength=n_verts)
    return counts

def calc_vert_splits(tempshit):
    """
    glTF splits per-corner attribute: UVs, loop normals, and corner colours
    We can measure and predict these splits efficiently and accurately and save confusing problems

    Returns:
      stats: dict of used/export/split/new vert counts
      reasons: dict mapping reason name -> bool array (per vertex) where True means it causes a split
      split_count: np.ndarray (n_verts,) total splits per vertex (how many verts it will become on export)
    """

    n_loops = len(tempshit.loops)
    n_verts = len(tempshit.vertices)


    # Stop Early if not needed
    if not tempshit.loop_triangles:

        return n_verts, n_verts, 0, 0
    # Column 0: loop -> vertex indices
    loop_verts = _loop_verts(tempshit).astype(np.int64, copy=False)

    # UV sets (all layers, not just active)
    uv_layers = list(getattr(tempshit, "uv_layers", []))
    uv_cols = []          # combined per-vertex signature including all uvs
    uv_reason_cols = {}   # per-layer columns for reason isolation - not used currently

    for i, uvl in enumerate(uv_layers):
        uv = np.empty(n_loops * 2, dtype=np.float32)
        uvl.data.foreach_get("uv", uv)
        uv = uv.reshape(-1, 2)
        uv_q = _quantize(uv)  # (n_loops, 2)
        # store separately for reason breakdown if we want it later
        uv_reason_cols[f"uv{i}"] = [uv_q[:, 0], uv_q[:, 1]]
        uv_cols.extend([uv_q[:, 0], uv_q[:, 1]])

    # Loop normals if needed
    normals_cols = []
    has_custom_normals = getattr(tempshit, "has_custom_normals", False) or any(not p.use_smooth for p in tempshit.polygons)
    if has_custom_normals:
        ln = np.empty(n_loops * 3, dtype=np.float32)
        tempshit.loops.foreach_get("normal", ln)
        ln = ln.reshape(-1, 3)
        ln_q = _quantize(ln)
        normals_cols = [ln_q[:, 0], ln_q[:, 1], ln_q[:, 2]]

    color_layers = [ca for ca in getattr(tempshit, "color_attributes", []) if ca.domain == 'CORNER']
    color_reason_cols = {}
    color_cols = []
    for i, ca in enumerate(color_layers):
        c = np.empty(n_loops * 4, dtype=np.float32)
        ca.data.foreach_get("color", c)
        c = c.reshape(-1, 4)[:, :3]
        c_q = _quantize(c)
        color_reason_cols[f"color{i}"] = [c_q[:, 0], c_q[:, 1], c_q[:, 2]]
        color_cols.extend([c_q[:, 0], c_q[:, 1], c_q[:, 2]])


    all_cols = []
    all_cols.extend(uv_cols)
    all_cols.extend(normals_cols)
    all_cols.extend(color_cols)

    total_counts = count_per_vertex(loop_verts, all_cols, n_verts)  # per-vertex split count
    used = int((total_counts > 0).sum())
    export = int(total_counts.sum())
    split = int((total_counts > 1).sum())
    new = export - used

    return used, export, split, new

def find_3d_degenerates(tempshit, eps=1e-10):
    """
    Check for degenerates (area = 1e-10 or less)

    Returns:
        np.array: Indices of polygons with degenerate triangles
    """
    if not tempshit.loop_triangles:
        return np.array([], dtype=np.int32)

    n_verts = len(tempshit.vertices)
    n_tris = len(tempshit.loop_triangles)

    # Get vertex coordinates
    vco = np.empty(n_verts * 3, dtype=np.float64)
    tempshit.vertices.foreach_get("co", vco)
    vco = vco.reshape(-1, 3)

    # Get triangle vertex indices
    tri_idx = np.empty(n_tris * 3, dtype=np.int32)
    tempshit.loop_triangles.foreach_get("vertices", tri_idx)
    tri_idx = tri_idx.reshape(-1, 3)

    # Get triangle polygon mapping
    tri_poly = np.empty(n_tris, dtype=np.int32)
    tempshit.loop_triangles.foreach_get("polygon_index", tri_poly)

    # Calculate triangle areas using cross product
    a = vco[tri_idx[:, 1]] - vco[tri_idx[:, 0]]
    b = vco[tri_idx[:, 2]] - vco[tri_idx[:, 0]]
    areas = 0.5 * np.linalg.norm(np.cross(a, b), axis=1)

    # Find degenerate triangles
    degenerate_mask = areas <= eps

    if not np.any(degenerate_mask):
        return np.array([], dtype=np.int32)

    # Map to unique polygon indices
    n_polys = len(tempshit.polygons)
    hits = np.bincount(
        tri_poly,
        weights=degenerate_mask.astype(np.int32),
        minlength=n_polys
    )

    return np.flatnonzero(hits > 0)

def check_uv_degenerates(tempshit, uv_eps=1e-17):
    """
    Check for UV degenerate triangles using vectorized operations.

    Returns:
        np.array: Indices of polygons with UV degenerate triangles
    """
    # Not sure if we need this one, but it's probably worthwhile

    if not tempshit.uv_layers.active or not tempshit.loop_triangles:
        return np.array([], dtype=np.int32)

    uv_layer = tempshit.uv_layers.active
    n_loops = len(tempshit.loops)
    n_tris = len(tempshit.loop_triangles)

    # Get all UV data
    uv = np.empty(n_loops * 2, dtype=np.float64)
    uv_layer.data.foreach_get("uv", uv)
    uv = uv.reshape(-1, 2)

    # Get triangle loop indices
    tri_loops = np.empty(n_tris * 3, dtype=np.int32)
    tempshit.loop_triangles.foreach_get("loops", tri_loops)
    tri_loops = tri_loops.reshape(-1, 3)

    # Get triangle polygon mapping
    tri_poly = np.empty(n_tris, dtype=np.int32)
    tempshit.loop_triangles.foreach_get("polygon_index", tri_poly)

    # Get triangle UVs
    tri_uvs = uv[tri_loops]

    # Calculate UV areas
    uv_a = tri_uvs[:, 1] - tri_uvs[:, 0]
    uv_b = tri_uvs[:, 2] - tri_uvs[:, 0]
    uv_areas = 0.5 * np.abs(uv_a[:, 0] * uv_b[:, 1] - uv_a[:, 1] * uv_b[:, 0])

    # Find degenerate triangles
    degenerate_mask = uv_areas <= uv_eps

    if not np.any(degenerate_mask):
        return np.array([], dtype=np.int32)

    # Map to unique polygon indices
    n_polys = len(tempshit.polygons)
    hits = np.bincount(
        tri_poly,
        weights=degenerate_mask.astype(np.int32),
        minlength=n_polys
    )

    return np.flatnonzero(hits > 0)

class ValidationIssue:
    """Represents a validation issue with context and remediation."""

    def __init__(self, issue_type, message, wiki_url, severity='ERROR'):
        self.type = issue_type
        self.message = message
        self.wiki_url = wiki_url
        self.severity = severity  # 'ERROR', 'WARNING', 'INFO'

    def __str__(self):
        return f"[{self.severity}] {self.message}"

def select_bmesh_problems(bm, me, face_indices=None, vertex_indices=None):
    """Select problematic elements in BMesh for visual feedback."""
    # Clear selection
    for v in bm.verts:
        v.select = False
    for e in bm.edges:
        e.select = False
    for f in bm.faces:
        f.select = False

    # Select faces
    if face_indices is not None and len(face_indices) > 0:
        bm.faces.ensure_lookup_table()
        for idx in face_indices:
            if 0 <= idx < len(bm.faces):
                bm.faces[idx].select = True

    # Select vertices
    if vertex_indices is not None and len(vertex_indices) > 0:
        bm.verts.ensure_lookup_table()
        for idx in vertex_indices:
            if 0 <= idx < len(bm.verts):
                bm.verts[idx].select = True

    # Update mesh
    bmesh.update_edit_mesh(me, loop_triangles=False, destructive=False)

def validate_skinned_mesh(ob, me, bm):
    """
    Validate skinned meshes.

    Returns:
        dict: {
            'valid': bool,
            'issues': list[ValidationIssue],
            'ungrouped_verts': set,
            'unassigned_groups': set,
            'armature': Object or None
        }
    """
    issues = []

    # Check for armature modifier
    arm_mod = next((m for m in ob.modifiers
                    if m.type == 'ARMATURE' and getattr(m, "object", None)), None)

    if not arm_mod:
        issues.append(ValidationIssue(
            'missing_armature',
            f"Missing armature modifier on '{ob.name}'. Armatures are required for skinned meshes.",
            "https://tinyurl.com/armature-missing"
        ))
        return {
            'valid': False,
            'issues': issues,
            'ungrouped_verts': set(),
            'unassigned_groups': set(),
            'armature': None
        }

    arm = arm_mod.object

    # Check for weighted vertices
    grouped = set()
    for v in me.vertices:
        if any(ge.weight > WEIGHT_EPSILON for ge in v.groups):
            grouped.add(v.index)

    if not grouped:
        issues.append(ValidationIssue(
            'no_weights',
            f"No weighted vertices in '{ob.name}'. Skinned meshes require weight painting.",
            "https://tinyurl.com/assign-vertex-weights"
        ))
        return {
            'valid': False,
            'issues': issues,
            'ungrouped_verts': set(range(len(me.vertices))),
            'unassigned_groups': set(),
            'armature': arm
        }

    # Check for ungrouped vertices
    ungrouped = set(range(len(me.vertices))) - grouped

    if ungrouped:
        issues.append(ValidationIssue(
            'ungrouped_vertices',
            f"{len(ungrouped)} vertices in '{ob.name}' lack weights. All vertices must be weighted.",
            "https://tinyurl.com/ungrouped-vertices"
        ))

    # Check for vertex groups without bones
    bone_names = {b.name for b in arm.data.bones}
    group_names = {g.name for g in ob.vertex_groups}
    missing = group_names - bone_names

    if missing:
        issues.append(ValidationIssue(
            'unassigned_groups',
            f"Vertex groups without bones in '{ob.name}': {', '.join(sorted(missing))}. "
            f"This creates neutral_bone and breaks WolvenKit import.",
            "https://tinyurl.com/unassigned-bone"
        ))

    return {
        'valid': len(issues) == 0,
        'issues': issues,
        'ungrouped_verts': ungrouped,
        'unassigned_groups': missing,
        'armature': arm
    }

def validate_mesh(ob, tempshit, eps=1e-10, uv_eps=1e-12):
#I've renamed this function three times because I can't read "General Mesh" without thinking the mesh has an army
    """
    Validate general mesh requirements (UV, vertex count, degenerates).
    Returns:
        dict: {
            'valid': bool,
            'issues': list[ValidationIssue],
            'bad_3d_faces': np.array,
            'vertex_stats': dict
        }
    """
    issues = []

    # Check for UV layer
    missing_uv = len(tempshit.uv_layers) == 0 or tempshit.uv_layers.active is None
    if missing_uv:
        issues.append(ValidationIssue(
            'missing_uv',
            f"'{ob.name}' has no UV layer. A UV layer is required for glTF export.",
            "https://tinyurl.com/uv-layers"
        ))

    # Calculate vertex counts with splits - this accounts for verts which will be added in the gltf on export
    used_vert_count, export_vert_count, split_verts, new_verts = calc_vert_splits(tempshit)

    vertex_stats = {
        'used': used_vert_count,
        'export': export_vert_count,
        'split': split_verts,
        'new': new_verts
    }

    # Check vertex count
    if export_vert_count > VERT_LIMIT:
        issues.append(ValidationIssue(
            'vertex_count',
            f"'{ob.name}' will have {export_vert_count} vertices after export "
            f"(base: {used_vert_count}, splits: {new_verts}). "
            f"glTF requires < {VERT_LIMIT}. Reduce UV seams or split the mesh.",
            "https://tinyurl.com/vertex-count"
        ))

    # Check for degenerates
    bad_3d_faces = find_3d_degenerates(tempshit, eps)
    if len(bad_3d_faces) > 0:
        issues.append(ValidationIssue(
            'degenerate_3d',
            f"{len(bad_3d_faces)} zero-area faces detected in '{ob.name}'. "
            f"Remove or fix these faces before export.",
            "https://tinyurl.com/wkit-io-degen-geometry"
        ))


    bad_uv_faces = np.array([], dtype=np.int32)
    if not missing_uv:
        pass
        # bad_uv_faces = check_uv_degenerates(tempshit, uv_eps)
        # if len(bad_uv_faces) > 0:
        #     issues.append(ValidationIssue(
        #         'degenerate_uv',
        #         f"{len(bad_uv_faces)} UV degenerate faces detected in '{ob.name}'. "
        #         f"Fix UV mapping to ensure proper texture coordinates.",
        #         "https://tinyurl.com/uv-degenerate"
        #     ))

    return {
        'valid': len(issues) == 0,
        'issues': issues,
        'bad_3d_faces': bad_3d_faces,
        #'bad_uv_faces': bad_uv_faces,
        'vertex_stats': vertex_stats
    }

def create_fixed_mesh_copy(ob, skinned_result, general_result):
    """
    Creates a copy of the mesh for export. Fixes it, doesn't modify the original.
    We destory the fixed copy when we're done because we want to and nobody can stop us

    Returns:
        tuple: (fixed_object, list_of_fixes_applied)
    """
    fixes_applied = []

    # Create mesh copy
    fixed_mesh = ob.data.copy()
    fixed_mesh.name = f"{ob.name}_fixed"

    # Create object copy
    tempshit = ob.copy()
    tempshit.data = fixed_mesh
    tempshit.name = f"{ob.name}_temp_export"

    # Link to scene temporarily
    bpy.context.collection.objects.link(tempshit)

    # Copy modifiers
    tempshit.modifiers.clear()
    for mod in ob.modifiers:
        new_mod = tempshit.modifiers.new(name=mod.name, type=mod.type)
        # Copy common properties
        for prop in ['show_viewport', 'show_render']:
            if hasattr(mod, prop):
                try:
                    setattr(new_mod, prop, getattr(mod, prop))
                except:
                    pass
        # Copy type-specific properties
        if mod.type == 'ARMATURE' and hasattr(mod, 'object'):
            new_mod.object = mod.object
        elif mod.type == 'LATTICE' and hasattr(mod, 'object'):
            new_mod.object = mod.object

    # Apply fixes if this is a skinned mesh
    if skinned_result and not skinned_result['valid']:
        ungrouped = skinned_result.get('ungrouped_verts', set())
        unassigned = skinned_result.get('unassigned_groups', set())
        armature = skinned_result.get('armature')

        # Fix ungrouped vertices
        if ungrouped and armature and armature.data.bones:
            root_bone = armature.data.bones[0].name
            if root_bone not in tempshit.vertex_groups:
                vg = tempshit.vertex_groups.new(name=root_bone)
            else:
                vg = tempshit.vertex_groups[root_bone]
            vg.add(list(ungrouped), 0.01, 'ADD')
            fixes_applied.append(f"Assigned {len(ungrouped)} ungrouped vertices to {root_bone} (weight: 0.01)")

        # Remove unassigned vertex groups
        if unassigned:
            for vg_name in unassigned:
                vg = tempshit.vertex_groups.get(vg_name)
                if vg:
                    tempshit.vertex_groups.remove(vg)
            fixes_applied.append(f"Removed {len(unassigned)} vertex groups without bones")

    # Apply general fixes
    if general_result and not general_result['valid']:
        # Fix missing UVs
        if not fixed_mesh.uv_layers:
            uv_layer = fixed_mesh.uv_layers.new(name="UVMap", do_init=True)
            fixes_applied.append("Added default UV layer")

        # Remove degenerate faces
        bad_3d = general_result.get('bad_3d_faces', np.array([]))
        bad_uv = general_result.get('bad_uv_faces', np.array([]))
        all_bad_faces = list(set(bad_3d.tolist()) | set(bad_uv.tolist()))

        if all_bad_faces:
            bm = bmesh.new()
            bm.from_mesh(fixed_mesh)
            bm.faces.ensure_lookup_table()

            faces_to_delete = [bm.faces[i] for i in all_bad_faces if i < len(bm.faces)]
            if faces_to_delete:
                bmesh.ops.delete(bm, geom=faces_to_delete, context='FACES')
                fixes_applied.append(f"Removed {len(faces_to_delete)} degenerate faces")

            bm.to_mesh(fixed_mesh)
            bm.free()

    fixed_mesh.update(calc_edges=True, calc_edges_loose=True)

    return tempshit, fixes_applied

def cp77_meshValidation(
    meshes: list[bpy.types.Object],
    *,
    eps: float = 1e-10,
    uv_eps: float = 1e-17,
    is_skinned: bool = False,
    try_fix: bool = True,
) -> dict:
    """
    Validate meshes for CP77 glTF export. NEVER modifies original meshes.

    If try_fix=True: Creates temporary fixed copies for export, but still reports issues.
    If try_fix=False: Selects problem areas and halts with clear instructions.

    Returns:
        dict: {
            'valid': bool,
            'export_objects': list,  # Originals or fixed copies
            'tempshit_objs': list,     # Temporary objects to cleanup
            'fixes_applied': dict,    # Fixes made to temp copies
            'issues_found': dict,     # All issues (even if auto-fixed)
        }
    """
    if not meshes:
        raise ValueError("No meshes to export, please select at least one mesh")

    # Filter excluded objects
    excluded_objects = get_excluded_objects()
    meshes = [m for m in meshes if m not in excluded_objects]

    if not meshes:
        return {
            'valid': True,
            'export_objects': [],
            'tempshit_objs': [],
            'fixes_applied': {},
            'issues_found': {}
        }

    # Store context
    store_current_context()

    # Enter edit mode for all meshes
    select_objects(meshes, make_first_active=True)
    if get_safe_mode() != 'EDIT':
        safe_mode_switch('EDIT')

    # Get edited objects
    c = bpy.context
    edited = getattr(c, "objects_in_mode_unique_data", None) or [c.edit_object]
    edited = [ob for ob in edited if ob and ob.type == 'MESH']

    if not edited:
        restore_previous_context()
        return {
            'valid': False,
            'export_objects': [],
            'tempshit_objs': [],
            'fixes_applied': {},
            'issues_found': {}
        }

    # Track results
    export_objects = []
    tempshit_objs = []
    all_fixes = {}
    all_issues = {}
    first_problem_object = None  # Track first object with issues for visual feedback

    try:
        for ob in edited:
            me = ob.data
            bm = bmesh.from_edit_mesh(me)
            bm.faces.ensure_lookup_table()
            bm.verts.ensure_lookup_table()

            # Validate skinned mesh requirements
            skinned_result = None
            if is_skinned:
                skinned_result = validate_skinned_mesh(ob, me, bm)

            # Create temp mesh for general validation
            bm_temp = bm.copy()
            tempshit = bpy.data.meshes.new(name=f"_temp_{ob.name}")

            try:
                bm_temp.to_mesh(tempshit)
                tempshit.calc_loop_triangles()

                # Validate general mesh requirements
                general_result = validate_mesh(ob, tempshit, eps, uv_eps)

            finally:
                bpy.data.meshes.remove(tempshit)
                bm_temp.free()

            # Collect all issues
            all_obj_issues = []
            if skinned_result:
                all_obj_issues.extend(skinned_result['issues'])
            if general_result:
                all_obj_issues.extend(general_result['issues'])

            # If there are issues
            if all_obj_issues:
                all_issues[ob.name] = all_obj_issues

                # Track first problem object for visual feedback
                if first_problem_object is None:
                    first_problem_object = (ob, bm, me, general_result, skinned_result)

                # If NOT trying to fix, select problem areas and halt
                if not try_fix:
                    bad_faces = list(general_result.get('bad_3d_faces', np.array([])).tolist())
                    ungrouped_verts = None
                    if skinned_result:
                        ungrouped_verts = skinned_result.get('ungrouped_verts')

                    if bad_faces or ungrouped_verts:
                        c.tool_settings.mesh_select_mode = (True, False, True)
                        select_bmesh_problems(bm, me, bad_faces, ungrouped_verts)

                    # Build error message
                    error_parts = [f"Validation failed for '{ob.name}':"]
                    for issue in all_obj_issues:
                        error_parts.append(f"  • {issue.message}")
                    error_parts.append("\nProblem areas selected. Fix these issues before export.")
                    error_parts.append(f"See: {all_obj_issues[0].wiki_url}")

                    # DON'T restore context - leave user in edit mode with selection
                    raise ValueError("\n".join(error_parts))

                # If trying to fix, create a fixed copy
                tempshit, fixes = create_fixed_mesh_copy(ob, skinned_result, general_result)
                export_objects.append(tempshit)
                tempshit_objs.append(tempshit)
                all_fixes[ob.name] = fixes

            else:
                # No issues - use original
                export_objects.append(ob)

        # If we fixed issues, show them to the user BEFORE proceeding
        if first_problem_object and all_fixes:
            ob, bm, me, general_result, skinned_result = first_problem_object

            # Select problem areas in the ORIGINAL mesh
            bad_faces = list(set(
                list(general_result.get('bad_3d_faces', [])) +
                list(general_result.get('bad_uv_faces', []))
            ))
            ungrouped_verts = None
            if skinned_result:
                ungrouped_verts = skinned_result.get('ungrouped_verts')

            if bad_faces or ungrouped_verts:
                c.tool_settings.mesh_select_mode = (True, False, True)
                select_bmesh_problems(bm, me, bad_faces, ungrouped_verts)

            # Build detailed message
            message_parts = [
                "EXPORT WILL PROCEED WITH AUTO-FIXES",
                "=" * 50,
                "",
                "Issues found in your original mesh(es):",
                ""
            ]

            for obj_name in sorted(all_issues.keys()):
                message_parts.append(f"{obj_name}:")
                for issue in all_issues[obj_name]:
                    message_parts.append(f"  {issue.message}")
                message_parts.append("")

            message_parts.extend([
                "Auto-fixes attempted on temporary mesh copies:",
                ""
            ])

            for obj_name in sorted(all_fixes.keys()):
                message_parts.append(f"{obj_name}:")
                for fix in all_fixes[obj_name]:
                    message_parts.append(f"  Fixed: {fix}")
                message_parts.append("")

            message_parts.extend([
                "YOUR ORIGINAL MESHES REMAIN UNCHANGED",
                "",
                "Problem areas are now selected in edit mode.",
                "Consider fixing these in your source files.",
                "",
                f"See: {all_issues[list(all_issues.keys())[0]][0].wiki_url}"
            ])

            # Show message but DON'T restore context yet
            # User stays in edit mode with problem areas selected
            show_message("\n".join(message_parts))

            # Context will be restored when export_meshes runs

        else:
            # No issues so no fixes needed - restore context normally
            pass
            restore_previous_context()

        return {
            'valid': True,
            'export_objects': export_objects,
            'tempshit_objs': tempshit_objs,
            'fixes_applied': all_fixes,
            'issues_found': all_issues
        }

    except Exception:
        # Clean up temp objects on error
        for tempshit in tempshit_objs:
            if tempshit.name in bpy.data.objects:
                bpy.data.objects.remove(tempshit, do_unlink=True)
        raise

def set_visible(collection, new_visibility_state):
    for obj in collection.objects:
        if obj.type == 'MESH':
            obj.hide_set(new_visibility_state and not obj.name.startswith('submesh_'))
        if obj.type == 'ARMATURE':
            obj.hide_set(not new_visibility_state)

    return [f for f in collection.objects if f.visible_get()]

def export_cyberpunk_collections_glb(context, filepath, export_poses=False, is_skinned=True, try_fix=True,
    red_garment_col=False, apply_transform=True,
    action_filter=False, export_tracks=False, apply_modifiers=True,
    only_visible=False):

    user_settings = save_user_settings_and_reset_to_default()

    exported = []

    # store_current_context()

    # Ensure object mode
    if get_safe_mode() != 'OBJECT':
        safe_mode_switch('OBJECT')

    for collection in bpy.data.collections:
        if (only_visible and collection.hide_viewport) or collection.name.endswith("not_exported"):
            continue

        oldVisible = collection.hide_viewport
        oldRender = collection.hide_render

        collection.hide_viewport = False
        collection.hide_render = False

        visible_objects = [f for f in collection.objects if f.type == 'ARMATURE' or (f.type == 'MESH' and f.name.startswith('submesh'))]
        if (len(visible_objects) == 0):
            exported.append((collection.name, f"No armatures or meshes starting with 'submesh'"))
            continue

        if not set_active_collection(collection, context):
            exported.append((collection.name, f"Failed to set collection as active"))
            continue

        select_objects(visible_objects, reveal=True, clear=True, context=context)

        if len(context.selected_objects) == 0:
            exported.append((collection.name, f"Failed to set child object selection"))
            continue

        collection_path = os.path.join(filepath, f"{collection.name}.glb")
        try:
            export_cyberpunk_glb(context, collection_path, export_poses=export_poses, export_visible=False,
                limit_selected=True, is_skinned=is_skinned, try_fix=try_fix,
                red_garment_col=red_garment_col, apply_transform=apply_transform,
                action_filter=action_filter, export_tracks=export_tracks, apply_modifiers=apply_modifiers,
                called_from_loop=True
            )
            exported.append((collection.name, None))
        except Exception as e:
            exported.append((collection.name, str(e)))

        collection.hide_viewport = oldVisible
        collection.hide_render = oldRender

    restore_user_settings(user_settings)
    return exported

def export_cyberpunk_glb(
    context, filepath, export_poses=False, export_visible=False,
    limit_selected=True, is_skinned=True, try_fix=True,
    red_garment_col=False, apply_transform=True,
    action_filter=False, export_tracks=False, apply_modifiers=True, called_from_loop=False
):
    """Main export function for CP77 glTF files."""
    user_settings = None if called_from_loop else save_user_settings_and_reset_to_default()

    objects = context.selected_objects
    options = default_cp77_options()

    if not called_from_loop:
        store_current_context()

    # Ensure object mode
    if get_safe_mode() != 'OBJECT':
        safe_mode_switch('OBJECT')

    # Filter excluded objects
    excluded_objects = get_excluded_objects()


    if export_poses:
        armatures = [obj for obj in objects if obj.type == 'ARMATURE']
        if not armatures:
            raise ValueError("No armature objects selected. Please select an armature.")

        if bpy.app.version >= (4, 0, 0) and action_filter:
            options['export_action_filter'] = True

        export_anims(context, filepath, options, armatures, export_tracks)

    else:
        # Export meshes
        meshes = [m for m in objects if m.type == 'MESH' and m not in excluded_objects] or []
        if  len(meshes) == 0:
            raise ValueError("No meshes selected. Please select at least one mesh.")

        export_meshes(
            context, filepath, export_visible, limit_selected,
            is_skinned, try_fix, red_garment_col, apply_transform,
            apply_modifiers, meshes, options
        )

    if user_settings is not None:
        restore_user_settings(user_settings)

    return {'FINISHED'}

def export_anims(context, filepath, options, armatures, export_tracks=False):
    """Export animation data."""
    # Set animation defaults on actions
    for action in bpy.data.actions:
        if "schema" not in action:
            action["schema"] = {"type": "wkit.cp2077.gltf.anims", "version": 4}
        if "animationType" not in action:
            action["animationType"] = "Normal"
        if "rootMotionType" not in action:
            action["rootMotionType"] = "Unknown"
        if "frameClamping" not in action:
            action["frameClamping"] = False
        if "frameClampingStartFrame" not in action:
            action["frameClampingStartFrame"] = -1
        if "frameClampingEndFrame" not in action:
            action["frameClampingEndFrame"] = -1
        if "numExtraJoints" not in action:
            action["numExtraJoints"] = 0
        if "numExtraTracks" not in action:
            action["numExtraTracks"] = 0
        if "constTrackKeys" not in action:
            action["constTrackKeys"] = []
        if "trackKeys" not in action:
            action["trackKeys"] = []
        if "fallbackFrameIndices" not in action:
            action["fallbackFrameIndices"] = []
        if "optimizationHints" not in action:
            action["optimizationHints"] = {"preferSIMD": False, "maxRotationCompression": 0}

        if export_tracks:
            try:
                if any(fc.data_path and fc.data_path.startswith('["T') for fc in action.fcurves):
                    export_anim_tracks(action)
            except Exception as e:
                print(f"export_anim_tracks failed for {action.name}: {e}")

    options.update(pose_export_options())

    for armature in armatures:
        reset_armature(armature, context)
        bpy.ops.export_scene.gltf(filepath=filepath, use_selection=True, **options)
        return {'FINISHED'}

    return {'FINISHED'}

def export_meshes(
    context, filepath, export_visible, limit_selected,
    is_skinned, try_fix, red_garment_col, apply_transform,
    apply_modifiers, meshes, options
):
    """Export mesh data."""
    options.update(cp77_mesh_options())

    # Run validation
    validation_result = cp77_meshValidation(
        meshes,
        is_skinned=is_skinned,
        try_fix=try_fix
    )

    # If validation left us in edit mode with selections, restore context now
    # This happens when try_fix=True and issues were found
    if bpy.context.mode == 'EDIT_MESH':
        restore_previous_context()

    if not validation_result['valid']:
        raise ValueError("Mesh validation failed. Check console for details.")

    # Use export objects (may be fixed copies)
    export_objects = validation_result['export_objects']
    tempshit_objs = validation_result['tempshit_objs']

    # Track armatures for visibility
    armatures_to_hide = set()

    try:
        for mesh in export_objects:
            # Apply garment support if requested
            if red_garment_col:
                add_garment_cap(mesh)

            # Ensure data name matches object name
            if mesh.data.name != mesh.name:
                mesh.data.name = mesh.name

            # Apply transforms if requested
            if apply_transform:
                bpy.ops.object.select_all(action='DESELECT')
                mesh.select_set(True)
                context.view_layer.objects.active = mesh
                bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

            # Set modifier application
            if apply_modifiers:
                options['export_apply'] = True

            # Handle armature visibility
            if is_skinned:
                for modifier in mesh.modifiers:
                    if modifier.type == 'ARMATURE' and modifier.object:
                        armature = modifier.object
                        armature.hide_set(False)
                        armature.select_set(True)
                        armatures_to_hide.add(armature)
                        break

        # Select all export objects
        bpy.ops.object.select_all(action='DESELECT')
        for obj in export_objects:
            obj.select_set(True)

        # Also select armatures if skinned
        if is_skinned:
            for armature in armatures_to_hide:
                armature.select_set(True)

        # Export
        if limit_selected:
            bpy.ops.export_scene.gltf(filepath=filepath, use_selection=True, **options)
        elif export_visible:
            bpy.ops.export_scene.gltf(filepath=filepath, use_visible=True, **options)
        else:
            bpy.ops.export_scene.gltf(filepath=filepath, **options)

        # Show success message if fixes were applied
        if validation_result['fixes_applied']:
            show_message("Export completed successfully with auto-fixes. Your original meshes remain unchanged.")

        return {'FINISHED'}

    finally:
        # Clean up temporary objects
        for tempshit in tempshit_objs:
            if tempshit.name in bpy.data.objects:
                bpy.data.objects.remove(tempshit, do_unlink=True)

        # Hide armatures
        for armature in armatures_to_hide:
            armature.hide_set(True)

def ExportAll(self, context):
    """Export all meshes with sourcePath or projPath."""
    to_exp = [
        obj for obj in context.scene.objects
        if obj.type == 'MESH' and ('sourcePath' in obj or 'projPath' in obj)
    ]

    if len(to_exp) > 0:
        for obj in to_exp:
            filepath = obj.get('projPath', '')
            if filepath:
                export_cyberpunk_glb(
                    context, filepath=filepath, export_poses=False
                )

# TESTING
if __name__ == "__main__":
    names = ['submesh_00_LOD_1', 'submesh_01_LOD_1', 'submesh_02_LOD_1', 'submesh_03_LOD_1']
    meshes = [obj for obj in bpy.data.objects if obj.name in names]
    result = cp77_meshValidation(meshes, is_skinned=True, try_fix=True)

    if result['valid']:
        print('Validation passed!')
        if result['fixes_applied']:
            print('Fixes applied:', result['fixes_applied'])
        else:
            print('No fixes needed')