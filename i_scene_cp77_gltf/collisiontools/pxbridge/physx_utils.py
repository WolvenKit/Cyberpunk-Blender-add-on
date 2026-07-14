import bpy
import bmesh
import math
import os
from mathutils import Matrix, Vector, Quaternion
from ...main.common import exclusion_cache

# fallback incase the preset lib doesn't load
try:
    from . import presets_lib
except ImportError:
    print("PxBridge Warning: presets_lib.py not found.")


    class presets_lib:
        COLLISION_PRESETS = {}
        COLLISION_LAYERS = []
        QUERY_LAYERS = []
        _OVERRIDES = {}
        _RAW_PRESETS = {}

        @staticmethod
        def get_layer_bit(n, q): return -1

        @staticmethod
        def get_preset_items(s, c): return [("None", "None", "")]

# fallback for mats
try:
    from .physmat_lib import physmat_list
except ImportError:
    def physmat_list():
        return [{"Name": "Default", "Density": 1000}]


def bits_to_int(bool_vector):
    """Convert a Blender BoolVector to a bitmask integer"""
    mask = 0
    for i, val in enumerate(bool_vector):
        if val: mask |= (1 << i)
    return mask


def get_physmat_items(self, context):
    items = [("Default", "Default", "")]
    for mat in physmat_list():
        name = mat.get("Name", "Unknown")
        if name != "Default":
            items.append((name, name, ""))
    return items


def get_mat_data(name):
    for mat in physmat_list():
        if mat.get("Name") == name:
            return [
                float(mat.get("staticFriction", 0.5)),
                float(mat.get("dynamicFriction", 0.5)),
                float(mat.get("restitution", 0.5))
                ]
    return [0.5, 0.5, 0.5]


def get_mat_density(name):
    for mat in physmat_list():
        if mat.get("Name") == name:
            return float(mat.get("Density", 1000.0))
    return 1000.0


def update_collision_bits(self, context):
    """
    Called whenever the user changes the 'collision_preset' Enum.
    It reads the string name, looks up layers in presets_lib, and sets vectors.
    """
    if self.collision_preset not in presets_lib.COLLISION_PRESETS:
        return

    # tuple: ([MyLayers], [CollidesWith], [QueryableBy])
    data = presets_lib.COLLISION_PRESETS[self.collision_preset]
    my_layers = data[0]
    collides_with = data[1]
    query_layers = data[2]

    new_group = [False] * 20
    new_mask = [False] * 20
    new_query = [False] * 20

    for name in my_layers:
        idx = presets_lib.get_layer_bit(name, is_query=False)
        if 0 <= idx < 20:
            new_group[idx] = True

    for name in collides_with:
        idx = presets_lib.get_layer_bit(name, is_query=False)
        if 0 <= idx < 20:
            new_mask[idx] = True

    for name in query_layers:
        idx = presets_lib.get_layer_bit(name, is_query=True)
        if 0 <= idx < 20:
            new_query[idx] = True

    self.filter_group = new_group
    self.filter_mask = new_mask
    self.filter_query = new_query


def get_bone_world_matrix(armature_obj, bone_name):
    if not armature_obj or armature_obj.type != 'ARMATURE':
        return Matrix.Identity(4)

    if bone_name in armature_obj.pose.bones:
        return armature_obj.matrix_world @ armature_obj.pose.bones[bone_name].matrix

    if bone_name in armature_obj.data.bones:
        return armature_obj.matrix_world @ armature_obj.data.bones[bone_name].matrix_local

    return Matrix.Identity(4)


def set_bone_world_matrix(armature_obj, bone_name, world_matrix):
    """Set the world space matrix for a bone (updates pose)."""
    if not armature_obj or armature_obj.type != 'ARMATURE':
        return

    if bone_name not in armature_obj.pose.bones:
        return

    pose_bone = armature_obj.pose.bones[bone_name]
    armature_inv = armature_obj.matrix_world.inverted()
    bone_matrix_armature_space = armature_inv @ world_matrix
    pose_bone.matrix = bone_matrix_armature_space


def get_actor_world_transform(actor_item):
    """Get the world transform (location + quaternion) for an actor."""
    if actor_item.use_bone_parent and actor_item.parent_armature != "NONE" and actor_item.target_bone != "NONE":
        armature_obj = bpy.context.scene.objects.get(actor_item.parent_armature)
        if armature_obj and armature_obj.type == 'ARMATURE':
            bone_matrix = get_bone_world_matrix(armature_obj, actor_item.target_bone)
            loc = bone_matrix.to_translation()
            quat = bone_matrix.to_quaternion()
            return (loc, quat)

    if actor_item.obj_ref:
        loc = actor_item.obj_ref.matrix_world.to_translation()
        quat = actor_item.obj_ref.matrix_world.to_quaternion()
        return (loc, quat)

    return (Vector((0, 0, 0)), Quaternion((1, 0, 0, 0)))


def get_clean_mesh_data(obj, shape_type, vert_limit=256):
    if not obj.data.vertices:
        raise ValueError("No vertices")
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    scale_mat = Matrix.LocRotScale(None, None, obj.scale)
    bmesh.ops.transform(bm, matrix=scale_mat, verts=bm.verts)

    if shape_type == 'CONVEX':
        bmesh.ops.convex_hull(bm, input=bm.verts)
        if len(bm.verts) > vert_limit:
            bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(5), verts=bm.verts, edges=bm.edges)

    bmesh.ops.triangulate(bm, faces=bm.faces)
    verts = []
    indices = []
    for v in bm.verts:
        verts.extend([v.co.x, v.co.y, v.co.z])
    for f in bm.faces:
        for v in f.verts:
            indices.append(v.index)
    bm.free()
    return verts, indices


def get_raw_mesh_data(obj):
    # Extracts raw local vertices and triangle indices
    depsgraph = bpy.context.evaluated_depsgraph_get()
    obj_eval = obj.evaluated_get(depsgraph)
    mesh = obj_eval.to_mesh()

    n_verts = len(mesh.vertices)
    verts = [0.0] * (n_verts * 3)
    mesh.vertices.foreach_get("co", verts)

    mesh.calc_loop_triangles()
    n_tris = len(mesh.loop_triangles)
    indices = [0] * (n_tris * 3)
    mesh.loop_triangles.foreach_get("vertices", indices)

    obj_eval.to_mesh_clear()
    return verts, indices

def add_ground_plane(offset_below: float = 0.05, size_xy: float = 100000.0, thickness: float = 0.01, name: str = "GroundPlane") -> bpy.types.Object:
    """
    Instantiates a procedural ground plane object with defined volumetric extents.
    Calculates the scene's global minimum Z bounding coordinate to position the 
    instantiated plane at a precise vertical offset beneath all existing geometry.
    """
    exclusion_cache.clear_cache()
    if (existing := bpy.data.objects.get(name)):
        bpy.data.objects.remove(existing, do_unlink=True)
        if existing.data:
            bpy.data.meshes.remove(existing.data, do_unlink=True)
    excluded_objects = exclusion_cache.get_excluded_objects()
    objs = [o for o in bpy.context.scene.objects if o.type == 'MESH' and o not in excluded_objects]

    if not objs:
        min_z = 0.0
    else:
        min_z = float('inf')
        for o in objs:
            for v in o.bound_box:
                w = o.matrix_world @ Vector(v)
                min_z = min(min_z, w.z)

    center_x = 0.0
    center_y = 0.0
    center_z = (min_z - offset_below) - (thickness / 2.0)

    dx = size_xy / 2.0
    dy = size_xy / 2.0
    dz = thickness / 2.0

    verts = [
        (-dx, -dy, -dz), (dx, -dy, -dz), (dx, dy, -dz), (-dx, dy, -dz),
        (-dx, -dy, dz),  (dx, -dy, dz),  (dx, dy, dz),  (-dx, dy, dz),
    ]

    faces = [
        (0, 1, 2, 3), (4, 5, 6, 7), 
        (0, 1, 5, 4), (1, 2, 6, 5), 
        (2, 3, 7, 6), (3, 0, 4, 7)
    ]

    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()

    obj = bpy.data.objects.new(name, mesh)
    obj.location = (center_x, center_y, center_z)

    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.update()

    return obj