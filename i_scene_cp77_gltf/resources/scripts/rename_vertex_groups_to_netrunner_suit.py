import re

import bpy
from mathutils import Vector

try:
    from ...core.log import get_logger
except ImportError:
    import logging

    def get_logger(name):
        return logging.getLogger(f"i_scene_cp77_gltf.user_scripts.{name}")


_LOG = get_logger(__name__)

current_armature_name = "Armature.002"
target_armature_name = "Armature.003"

current_armature = bpy.data.objects.get(current_armature_name)
target_armature = bpy.data.objects.get(target_armature_name)


def check_prerequisites():
    if not current_armature:
        _LOG.warning("Set current_armature_name to the source armature")
        return False
    if not target_armature:
        _LOG.warning("Set target_armature_name to the destination armature")
        return False
    return True


matching_bones = {}


def find_closest_bone(bone_name):
    active_bone = current_armature.data.bones.get(bone_name)
    if active_bone is None:
        return
    source_location = active_bone.head
    closest_bone = None
    closest_distance = float("inf")
    for bone in target_armature.data.bones:
        if bone.name in current_armature.data.bones:
            continue
        distance = (Vector(bone.head) - source_location).length
        if distance < closest_distance:
            closest_distance = distance
            closest_bone = bone.name
    if closest_bone:
        matching_bones[bone_name] = closest_bone


def rename_vertex_groups(mesh_name):
    obj = bpy.data.objects.get(mesh_name)
    if obj is None:
        return
    renamed = 0
    for original_name, target_name in matching_bones.items():
        group = obj.vertex_groups.get(original_name)
        if group is None or not target_name:
            continue
        group.name = target_name
        renamed += 1
    if renamed:
        _LOG.info("Renamed %d vertex groups in %s", renamed, mesh_name)


def merge_similar_vertex_groups(mesh_name):
    obj = bpy.data.objects.get(mesh_name)
    if obj is None:
        return
    suffix_pattern = re.compile(r"\.\d+$")
    existing_names = tuple(group.name for group in obj.vertex_groups)
    roots = {
        name[: match.start()]
        for name in existing_names
        if (match := suffix_pattern.search(name))
    }
    for root_name in roots:
        group_pattern = re.compile(re.escape(root_name) + r"\.\d+$")
        source_names = [
            name for name in existing_names if group_pattern.fullmatch(name)
        ]
        if not source_names:
            continue
        target_group = obj.vertex_groups.get(root_name) or obj.vertex_groups.new(
            name=root_name
        )
        for source_name in source_names:
            source_group = obj.vertex_groups.get(source_name)
            if source_group is None:
                continue
            for vertex in obj.data.vertices:
                try:
                    weight = source_group.weight(vertex.index)
                except RuntimeError:
                    continue
                target_group.add([vertex.index], weight, "REPLACE")
            obj.vertex_groups.remove(source_group)
        _LOG.info("Merged %s into %s", source_names, root_name)


if check_prerequisites():
    target_bone_names = {bone.name for bone in target_armature.data.bones}
    different_bones = [
        bone.name
        for bone in current_armature.data.bones
        if bone.name not in target_bone_names
    ]
    for bone_name in different_bones:
        find_closest_bone(bone_name)

    _LOG.info(
        "Found %d source bones not present in %s",
        len(matching_bones),
        target_armature_name,
    )

    parented_meshes = [
        obj
        for obj in bpy.context.scene.objects
        if obj.type == "MESH" and obj.parent == current_armature
    ]
    target_armature_collection = next(
        (
            collection
            for collection in bpy.data.collections
            if target_armature_name in collection.objects
        ),
        None,
    )

    for mesh in parented_meshes:
        _LOG.info("Processing %s", mesh.name)
        rename_vertex_groups(mesh.name)
        merge_similar_vertex_groups(mesh.name)
        for modifier in mesh.modifiers:
            if modifier.type == "ARMATURE" and modifier.object == current_armature:
                modifier.object = target_armature
        mesh.parent = target_armature
        if target_armature_collection is not None:
            for collection in tuple(mesh.users_collection):
                collection.objects.unlink(mesh)
            target_armature_collection.objects.link(mesh)

    _LOG.info("Retargeting complete")
