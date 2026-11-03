import math

import bmesh
from mathutils import Matrix, Quaternion, Vector

from ...physics.model.collision_layers import COLLISION_PRESETS, get_layer_bit


def update_collision_bits(self, context):
    """Set the collision layer vectors from the chosen preset's layers"""
    if self.collision_preset not in COLLISION_PRESETS:
        return

    # tuple: ([MyLayers], [CollidesWith], [QueryableBy])
    data = COLLISION_PRESETS[self.collision_preset]
    my_layers = data[0]
    collides_with = data[1]
    query_layers = data[2]

    new_group = [False] * 20
    new_mask = [False] * 20
    new_query = [False] * 20

    for name in my_layers:
        idx = get_layer_bit(name, is_query=False)
        if 0 <= idx < 20:
            new_group[idx] = True

    for name in collides_with:
        idx = get_layer_bit(name, is_query=False)
        if 0 <= idx < 20:
            new_mask[idx] = True

    for name in query_layers:
        idx = get_layer_bit(name, is_query=True)
        if 0 <= idx < 20:
            new_query[idx] = True

    self.filter_group = new_group
    self.filter_mask = new_mask
    self.filter_query = new_query


def get_bone_world_matrix(armature_obj, bone_name):
    if not armature_obj or armature_obj.type != "ARMATURE":
        return Matrix.Identity(4)

    pose_bone = armature_obj.pose.bones.get(bone_name)
    if pose_bone is not None:
        return armature_obj.matrix_world @ pose_bone.matrix

    bone = armature_obj.data.bones.get(bone_name)
    if bone is not None:
        return armature_obj.matrix_world @ bone.matrix_local

    return Matrix.Identity(4)


def set_bone_world_matrix(armature_obj, bone_name, world_matrix):
    """Set the world-space pose matrix for one armature bone"""
    if not armature_obj or armature_obj.type != "ARMATURE":
        return

    pose_bone = armature_obj.pose.bones.get(bone_name)
    if pose_bone is None:
        return

    pose_bone.matrix = armature_obj.matrix_world.inverted_safe() @ world_matrix


def get_actor_world_transform(actor_item, context):
    """Get the world transform (location + quaternion) for an actor"""
    if (
        actor_item.use_bone_parent
        and actor_item.parent_armature != "NONE"
        and actor_item.target_bone != "NONE"
    ):
        armature_obj = context.scene.objects.get(actor_item.parent_armature)
        if armature_obj and armature_obj.type == "ARMATURE":
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
    try:
        bm.from_mesh(obj.data)
        scale_matrix = Matrix.LocRotScale(None, None, obj.scale)
        bmesh.ops.transform(bm, matrix=scale_matrix, verts=bm.verts)

        if shape_type == "CONVEX":
            bmesh.ops.convex_hull(bm, input=bm.verts)
            if len(bm.verts) > vert_limit:
                bmesh.ops.dissolve_limit(
                    bm,
                    angle_limit=math.radians(5),
                    verts=bm.verts,
                    edges=bm.edges,
                )

        bmesh.ops.triangulate(bm, faces=bm.faces)
        bm.verts.index_update()
        verts = [component for vertex in bm.verts for component in vertex.co]
        indices = [vertex.index for face in bm.faces for vertex in face.verts]
        return verts, indices
    finally:
        bm.free()
