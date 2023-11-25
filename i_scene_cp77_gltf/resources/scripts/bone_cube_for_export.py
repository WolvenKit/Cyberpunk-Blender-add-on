import bpy

c = bpy.context
bops = bpy.ops


## make a cube
bops.mesh.primitive_cube_add(size=2, enter_editmode=False, align='WORLD', location=(0, 0, 0))
cube = c.object

#trianghulate the faces of the cube so it'll impport 

bops.object.mode_set(mode='EDIT')
bops.mesh.quads_convert_to_tris(quad_method='BEAUTY', ngon_method='BEAUTY')
bops.object.mode_set(mode='OBJECT')

#add a single bone named root so that export works
bops.object.armature_add(enter_editmode=False, align='WORLD', location=(0, 0, 0))
armature = c.object
armature.data.bones[0].name = "Root"


## put the names of all the bones in all of the rigs you are trying to export from wkit here
vertex_group_names =[
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
    "RightToeBase"
    ]

# Create vertex groups and assign the verts to them 
for group_name in vertex_group_names:
    vertex_group = cube.vertex_groups.new(name=group_name)
    for vertex in cube.data.vertices:
        vertex_group.add([vertex.index], 1.0, 'REPLACE')

cube.select_set(True)
c.view_layer.objects.active = armature
bops.object.parent_set(type='ARMATURE')

print('finished')
