import bpy

try:
    from ...core.log import get_logger
except ImportError:
    import logging

    def get_logger(name):
        return logging.getLogger(f"i_scene_cp77_gltf.user_scripts.{name}")


_LOG = get_logger(__name__)

bpy.ops.mesh.primitive_cube_add(
    size=2, enter_editmode=False, align="WORLD", location=(0, 0, 0)
)
cube = bpy.context.object


bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.quads_convert_to_tris(quad_method="BEAUTY", ngon_method="BEAUTY")
bpy.ops.object.mode_set(mode="OBJECT")


bpy.ops.object.armature_add(enter_editmode=False, align="WORLD", location=(0, 0, 0))
armature = bpy.context.object
armature.data.bones[0].name = "Root"


vertex_group_names = [
    "Root",
    "Hips",
    "Spine",
    "Spine1",
    "Spine2",
    "Spine3",
    "LeftShoulder",
    "LeftArm",
    "LeftForeArm",
    "LeftHand",
    "WeaponLeft",
    "LeftInHandThumb",
    "LeftHandThumb1",
    "LeftHandThumb2",
    "LeftInHandIndex",
    "LeftHandIndex1",
    "LeftHandIndex2",
    "LeftHandIndex3",
    "LeftInHandMiddle",
    "LeftHandMiddle1",
    "LeftHandMiddle2",
    "LeftHandMiddle3",
    "LeftInHandRing",
    "LeftHandRing1",
    "LeftHandRing2",
    "LeftHandRing3",
    "LeftInHandPinky",
    "LeftHandPinky1",
    "LeftHandPinky2",
    "LeftHandPinky3",
    "RightShoulder",
    "RightArm",
    "RightForeArm",
    "RightHand",
    "WeaponRight",
    "RightInHandThumb",
    "RightHandThumb1",
    "RightHandThumb2",
    "RightInHandIndex",
    "RightHandIndex1",
    "RightHandIndex2",
    "RightHandIndex3",
    "RightInHandMiddle",
    "RightHandMiddle1",
    "RightHandMiddle2",
    "RightHandMiddle3",
    "RightInHandRing",
    "RightHandRing1",
    "RightHandRing2",
    "RightHandRing3",
    "RightInHandPinky",
    "RightHandPinky1",
    "RightHandPinky2",
    "RightHandPinky3",
    "Neck",
    "Neck1",
    "Head",
    "LeftEye",
    "RightEye",
    "LeftUpLeg",
    "LeftLeg",
    "LeftFoot",
    "LeftHeel",
    "LeftToeBase",
    "RightUpLeg",
    "RightLeg",
    "RightFoot",
    "RightHeel",
    "RightToeBase",
]


for group_name in vertex_group_names:
    vertex_group = cube.vertex_groups.new(name=group_name)
    for vertex in cube.data.vertices:
        vertex_group.add([vertex.index], 1.0, "REPLACE")

cube.select_set(True)
bpy.context.view_layer.objects.active = armature
bpy.ops.object.parent_set(type="ARMATURE")

_LOG.info("finished")
