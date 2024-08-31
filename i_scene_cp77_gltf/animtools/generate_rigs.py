import bpy

from rna_prop_ui import rna_idprop_ui_create

from mathutils import Color

def create_meta(obj):
    if obj and obj.type == 'ARMATURE':
        original_armature = obj
        
        # Deselect all objects
        bpy.ops.object.select_all(action='DESELECT')
        
        # Select the original armature
        original_armature.select_set(True)
        bpy.context.view_layer.objects.active = original_armature
        
        # Duplicate the original armature
        bpy.ops.object.duplicate()
        meta_rig = bpy.context.object
        meta_rig.name = original_armature.name + "_meta"
        meta_rig.data.name = meta_rig.name
        
        # Remove all duplicate bones
        for bone in meta_rig.pose.bones:
            if bone.name.endswith(".001"):
                meta_rig.data.edit_bones.remove(meta_rig.data.edit_bones[bone.name])
        
        # Rename the bones in the duplicated armature to match the original
        for original_bone, meta_bone in zip(original_armature.pose.bones, meta_rig.pose.bones):
            if meta_bone.name != original_bone.name:
                bpy.context.view_layer.objects.active = meta_rig
                bpy.ops.object.mode_set(mode='EDIT')
                meta_rig.data.edit_bones[meta_bone.name].name = original_bone.name
                bpy.ops.object.mode_set(mode='POSE')
                
        return meta_rig
    else:
        print("No armature selected.")
        return None

def create_constraints(rigify_rig, original_armature):
    bpy.context.view_layer.objects.active = rigify_rig
    bpy.ops.object.mode_set(mode='POSE')
    
    rigify_pose_bones = rigify_rig.pose.bones
    conbo = {}

    # Create a dictionary to map original armature bones to rigify bones
    for bone in rigify_pose_bones:
        original_bone_name = bone.name[4:]
        if original_bone_name in original_armature.pose.bones:
            conbo[original_bone_name] = bone.name

    # Apply copy transforms constraints
    for original_bone_name, rigify_bone_name in conbo.items():
        original_bone = original_armature.pose.bones[original_bone_name]
        constraint = original_bone.constraints.new(type='COPY_ROTATION')
        constraint.name = "Copy Transforms from " + rigify_bone_name
        constraint.target = rigify_rig
        constraint.subtarget = rigify_bone_name
        
    for original_bone_name, rigify_bone_name in conbo.items():
        original_bone = original_armature.pose.bones[original_bone_name]
        constraint = original_bone.constraints.new(type='COPY_LOCATION')
        constraint.name = "Copy Transforms from " + rigify_bone_name
        constraint.target = rigify_rig
        constraint.subtarget = rigify_bone_name      

    bpy.ops.object.mode_set(mode='OBJECT')

def create_rigify(obj):

    bpy.ops.object.mode_set(mode='EDIT')
    arm = obj.data

    for i in range(6):
        arm.rigify_colors.add()

    arm.rigify_colors[0].name = "Root"
    arm.rigify_colors[0].active = Color((0.5490, 1.0000, 1.0000))
    arm.rigify_colors[0].normal = Color((0.4353, 0.1843, 0.4157))
    arm.rigify_colors[0].select = Color((0.3137, 0.7843, 1.0000))
    arm.rigify_colors[0].standard_colors_lock = True
    arm.rigify_colors[1].name = "IK"
    arm.rigify_colors[1].active = Color((0.5490, 1.0000, 1.0000))
    arm.rigify_colors[1].normal = Color((0.6039, 0.0000, 0.0000))
    arm.rigify_colors[1].select = Color((0.3137, 0.7843, 1.0000))
    arm.rigify_colors[1].standard_colors_lock = True
    arm.rigify_colors[2].name = "Special"
    arm.rigify_colors[2].active = Color((0.5490, 1.0000, 1.0000))
    arm.rigify_colors[2].normal = Color((0.9569, 0.7882, 0.0471))
    arm.rigify_colors[2].select = Color((0.3137, 0.7843, 1.0000))
    arm.rigify_colors[2].standard_colors_lock = True
    arm.rigify_colors[3].name = "Tweak"
    arm.rigify_colors[3].active = Color((0.5490, 1.0000, 1.0000))
    arm.rigify_colors[3].normal = Color((0.0392, 0.2118, 0.5804))
    arm.rigify_colors[3].select = Color((0.3137, 0.7843, 1.0000))
    arm.rigify_colors[3].standard_colors_lock = True
    arm.rigify_colors[4].name = "FK"
    arm.rigify_colors[4].active = Color((0.5490, 1.0000, 1.0000))
    arm.rigify_colors[4].normal = Color((0.1176, 0.5686, 0.0353))
    arm.rigify_colors[4].select = Color((0.3137, 0.7843, 1.0000))
    arm.rigify_colors[4].standard_colors_lock = True
    arm.rigify_colors[5].name = "Extra"
    arm.rigify_colors[5].active = Color((0.5490, 1.0000, 1.0000))
    arm.rigify_colors[5].normal = Color((0.9686, 0.2510, 0.0941))
    arm.rigify_colors[5].select = Color((0.3137, 0.7843, 1.0000))
    arm.rigify_colors[5].standard_colors_lock = True

    bone_collections = {}

    for bcoll in list(arm.collections_all):
        arm.collections.remove(bcoll)

    def add_bone_collection(name, *, parent=None, ui_row=0, ui_title='', sel_set=False, color_set_id=0):
        new_bcoll = arm.collections.new(name, parent=bone_collections.get(parent))
        new_bcoll.rigify_ui_row = ui_row
        new_bcoll.rigify_ui_title = ui_title
        new_bcoll.rigify_sel_set = sel_set
        new_bcoll.rigify_color_set_id = color_set_id
        bone_collections[name] = new_bcoll

    def assign_bone_collections(pose_bone, *coll_names):
        assert not len(pose_bone.bone.collections)
        for name in coll_names:
            bone_collections[name].assign(pose_bone)

    def assign_bone_collection_refs(params, attr_name, *coll_names):
        ref_list = getattr(params, attr_name + '_coll_refs', None)
        if ref_list is not None:
            for name in coll_names:
                ref_list.add().set_collection(bone_collections[name])

    add_bone_collection('Face', ui_row=1, color_set_id=5)
    add_bone_collection('Face (Primary)', ui_row=2, color_set_id=2)
    add_bone_collection('Face (Secondary)', ui_row=2, color_set_id=3)
    add_bone_collection('Torso', ui_row=3, color_set_id=3)
    add_bone_collection('Torso (Tweak)', ui_row=4, color_set_id=4)
    add_bone_collection('Fingers', ui_row=5, color_set_id=6)
    add_bone_collection('Fingers (Detail)', ui_row=6, color_set_id=5)
    add_bone_collection('Arm.L (IK)', ui_row=7, color_set_id=2)
    add_bone_collection('Arm.L (FK)', ui_row=8, color_set_id=5)
    add_bone_collection('Arm.L (Tweak)', ui_row=9, color_set_id=4)
    add_bone_collection('Arm.R (IK)', ui_row=7, color_set_id=2)
    add_bone_collection('Arm.R (FK)', ui_row=8, color_set_id=5)
    add_bone_collection('Arm.R (Tweak)', ui_row=9, color_set_id=4)
    add_bone_collection('Leg.L (IK)', ui_row=10, color_set_id=2)
    add_bone_collection('Leg.L (FK)', ui_row=11, color_set_id=5)
    add_bone_collection('Leg.L (Tweak)', ui_row=12, color_set_id=4)
    add_bone_collection('Leg.R (IK)', ui_row=10, color_set_id=2)
    add_bone_collection('Leg.R (FK)', ui_row=11, color_set_id=5)
    add_bone_collection('Leg.R (Tweak)', ui_row=12, color_set_id=4)
    add_bone_collection('Additional', ui_row=1, color_set_id=3)
    add_bone_collection('Root', ui_row=15, color_set_id=1)

    bones = {}

    bone = arm.edit_bones.new('Root')
    bone.head = 0.0000, 0.0000, 0.0000
    bone.tail = 0.0000, 0.0000, 1.0137
    bone.roll = 0.0000
    bone.use_connect = False
    bones['Root'] = bone.name
    bone = arm.edit_bones.new('Hips')
    bone.head = 0.0000, -0.0410, 1.0128
    bone.tail = -0.0000, -0.0540, 1.0823
    bone.roll = 0.0000
    bone.use_connect = False
    bones['Hips'] = bone.name
    bone = arm.edit_bones.new('Neck1')
    bone.head = -0.0000, -0.0548, 1.5682
    bone.tail = -0.0000, -0.0454, 1.6146
    bone.roll = 0.0000
    bone.use_connect = False
    bones['Neck1'] = bone.name
    bone = arm.edit_bones.new('LeftEye')
    bone.head = -0.0282, 0.0455, 1.6916
    bone.tail = -0.0282, 0.0455, 1.7016
    bone.roll = 0.0000
    bone.use_connect = False
    bones['LeftEye'] = bone.name
    bone = arm.edit_bones.new('RightEye')
    bone.head = 0.0282, 0.0453, 1.6916
    bone.tail = 0.0282, 0.0453, 1.7016
    bone.roll = 0.0000
    bone.use_connect = False
    bones['RightEye'] = bone.name
    bone = arm.edit_bones.new('face_root_JNT')
    bone.head = -0.0000, -0.0403, 1.7105
    bone.tail = -0.0000, 0.0366, 1.7105
    bone.roll = 0.0000
    bone.use_connect = False
    bones['face_root_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_eye_brows_rowA_1_JNT')
    bone.head = -0.0279, 0.0647, 1.7050
    bone.tail = -0.0279, 0.1417, 1.7050
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_eye_brows_rowA_1_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_eye_lid_up_root_1_JNT')
    bone.head = -0.0284, 0.0407, 1.6901
    bone.tail = -0.0284, 0.0555, 1.6901
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_eye_lid_up_root_1_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_eye_lid_up_rowA_1_JNT')
    bone.head = -0.0264, 0.0552, 1.6925
    bone.tail = -0.0264, 0.0699, 1.6925
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_eye_lid_up_rowA_1_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_eye_lid_lashes_up_rowA_1_JNT')
    bone.head = -0.0262, 0.0569, 1.6930
    bone.tail = -0.0262, 0.0716, 1.6930
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_eye_lid_lashes_up_rowA_1_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_jaw_nosabial_rowC_1_JNT')
    bone.head = -0.0458, 0.0480, 1.6508
    bone.tail = -0.0458, 0.1250, 1.6508
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_jaw_nosabial_rowC_1_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_mug_lip_up_0_JNT')
    bone.head = -0.0042, 0.0635, 1.6275
    bone.tail = -0.0042, 0.0574, 1.6275
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_mug_lip_up_0_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_mug_lip_up_inside_0_JNT')
    bone.head = -0.0037, 0.0575, 1.6264
    bone.tail = -0.0037, 0.0513, 1.6264
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_mug_lip_up_inside_0_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_mug_mouth_rowB_3_JNT')
    bone.head = -0.0264, 0.0511, 1.6314
    bone.tail = -0.0264, 0.1281, 1.6314
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_mug_mouth_rowB_3_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_eye_brows_rowA_1_JNT')
    bone.head = 0.0279, 0.0647, 1.7050
    bone.tail = 0.0279, 0.1417, 1.7050
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_eye_brows_rowA_1_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_eye_lid_up_root_1_JNT')
    bone.head = 0.0284, 0.0407, 1.6901
    bone.tail = 0.0284, 0.0555, 1.6901
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_eye_lid_up_root_1_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_eye_lid_up_rowA_1_JNT')
    bone.head = 0.0264, 0.0552, 1.6925
    bone.tail = 0.0264, 0.0700, 1.6925
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_eye_lid_up_rowA_1_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_eye_lid_lashes_up_rowA_1_JNT')
    bone.head = 0.0262, 0.0569, 1.6930
    bone.tail = 0.0262, 0.0717, 1.6930
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_eye_lid_lashes_up_rowA_1_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_jaw_nosabial_rowC_1_JNT')
    bone.head = 0.0458, 0.0480, 1.6508
    bone.tail = 0.0458, 0.1250, 1.6508
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_jaw_nosabial_rowC_1_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_mug_mouth_rowB_3_JNT')
    bone.head = 0.0264, 0.0513, 1.6315
    bone.tail = 0.0264, 0.1283, 1.6315
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_mug_mouth_rowB_3_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_eye_brows_rowA_0_JNT')
    bone.head = -0.0114, 0.0685, 1.7025
    bone.tail = -0.0114, 0.1455, 1.7025
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_eye_brows_rowA_0_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_eye_brows_rowA_0_twk_JNT')
    bone.head = -0.0040, 0.0688, 1.6986
    bone.tail = -0.0040, 0.1458, 1.6986
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_eye_brows_rowA_0_twk_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_eye_brows_rowA_2_JNT')
    bone.head = -0.0393, 0.0595, 1.7055
    bone.tail = -0.0393, 0.1365, 1.7055
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_eye_brows_rowA_2_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_eye_brows_rowA_3_JNT')
    bone.head = -0.0477, 0.0514, 1.7034
    bone.tail = -0.0477, 0.1283, 1.7034
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_eye_brows_rowA_3_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_eye_brows_rowB_0_JNT')
    bone.head = -0.0107, 0.0700, 1.7149
    bone.tail = -0.0107, 0.1470, 1.7149
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_eye_brows_rowB_0_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_eye_brows_rowB_1_JNT')
    bone.head = -0.0281, 0.0647, 1.7196
    bone.tail = -0.0281, 0.1417, 1.7196
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_eye_brows_rowB_1_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_eye_brows_rowB_2_JNT')
    bone.head = -0.0399, 0.0564, 1.7204
    bone.tail = -0.0399, 0.1333, 1.7204
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_eye_brows_rowB_2_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_eye_brows_rowB_3_JNT')
    bone.head = -0.0499, 0.0446, 1.7178
    bone.tail = -0.0499, 0.1215, 1.7178
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_eye_brows_rowB_3_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_eye_brows_rowC_0_JNT')
    bone.head = -0.0206, 0.0661, 1.7270
    bone.tail = -0.0206, 0.1431, 1.7270
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_eye_brows_rowC_0_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_eye_brows_rowC_1_JNT')
    bone.head = -0.0385, 0.0531, 1.7330
    bone.tail = -0.0385, 0.1301, 1.7330
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_eye_brows_rowC_1_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_eye_brows_rowC_2_JNT')
    bone.head = -0.0503, 0.0374, 1.7319
    bone.tail = -0.0503, 0.1144, 1.7319
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_eye_brows_rowC_2_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_eye_check_rowA_0_JNT')
    bone.head = -0.0628, 0.0144, 1.6978
    bone.tail = -0.0628, 0.0914, 1.6978
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_eye_check_rowA_0_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_eye_check_rowA_1_JNT')
    bone.head = -0.0605, 0.0225, 1.7105
    bone.tail = -0.0605, 0.0995, 1.7105
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_eye_check_rowA_1_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_eye_check_rowB_0_JNT')
    bone.head = -0.0530, 0.0377, 1.6893
    bone.tail = -0.0530, 0.1147, 1.6893
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_eye_check_rowB_0_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_eye_check_rowC_0_JNT')
    bone.head = -0.0550, 0.0366, 1.6802
    bone.tail = -0.0550, 0.1136, 1.6802
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_eye_check_rowC_0_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_eye_check_rowC_1_JNT')
    bone.head = -0.0657, 0.0038, 1.6811
    bone.tail = -0.0657, 0.0808, 1.6811
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_eye_check_rowC_1_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_eye_check_rowD_0_JNT')
    bone.head = -0.0541, 0.0399, 1.6726
    bone.tail = -0.0541, 0.1169, 1.6726
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_eye_check_rowD_0_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_eye_check_rowD_1_JNT')
    bone.head = -0.0626, 0.0216, 1.6662
    bone.tail = -0.0626, 0.0985, 1.6662
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_eye_check_rowD_1_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_eye_check_rowE_0_JNT')
    bone.head = -0.0516, 0.0440, 1.6626
    bone.tail = -0.0516, 0.1210, 1.6626
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_eye_check_rowE_0_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_eye_lid_corner_inside_0_JNT')
    bone.head = -0.0140, 0.0537, 1.6866
    bone.tail = -0.0140, 0.1307, 1.6866
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_eye_lid_corner_inside_0_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_eye_lid_up_rowD_4_JNT')
    bone.head = -0.0495, 0.0439, 1.6920
    bone.tail = -0.0495, 0.1209, 1.6920
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_eye_lid_up_rowD_4_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_eye_lid_dn_root_1_JNT')
    bone.head = -0.0284, 0.0407, 1.6901
    bone.tail = -0.0284, 0.0556, 1.6901
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_eye_lid_dn_root_1_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_eye_lid_dn_rowA_1_JNT')
    bone.head = -0.0281, 0.0546, 1.6849
    bone.tail = -0.0281, 0.0695, 1.6849
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_eye_lid_dn_rowA_1_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_eye_lid_lashes_dn_rowA_1_JNT')
    bone.head = -0.0283, 0.0559, 1.6838
    bone.tail = -0.0283, 0.0707, 1.6838
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_eye_lid_lashes_dn_rowA_1_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_eye_lid_dn_root_2_JNT')
    bone.head = -0.0284, 0.0407, 1.6901
    bone.tail = -0.0284, 0.0556, 1.6901
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_eye_lid_dn_root_2_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_eye_lid_dn_rowA_2_JNT')
    bone.head = -0.0367, 0.0522, 1.6858
    bone.tail = -0.0367, 0.0670, 1.6858
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_eye_lid_dn_rowA_2_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_eye_lid_lashes_dn_rowA_2_JNT')
    bone.head = -0.0374, 0.0533, 1.6847
    bone.tail = -0.0374, 0.0681, 1.6847
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_eye_lid_lashes_dn_rowA_2_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_eye_lid_dn_rowB_0_JNT')
    bone.head = -0.0235, 0.0541, 1.6794
    bone.tail = -0.0235, 0.1311, 1.6794
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_eye_lid_dn_rowB_0_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_eye_lid_dn_rowB_1_JNT')
    bone.head = -0.0320, 0.0529, 1.6772
    bone.tail = -0.0320, 0.1299, 1.6772
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_eye_lid_dn_rowB_1_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_eye_lid_dn_rowB_2_JNT')
    bone.head = -0.0396, 0.0494, 1.6779
    bone.tail = -0.0396, 0.1264, 1.6779
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_eye_lid_dn_rowB_2_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_eye_lid_up_root_2_JNT')
    bone.head = -0.0284, 0.0407, 1.6901
    bone.tail = -0.0284, 0.0555, 1.6901
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_eye_lid_up_root_2_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_eye_lid_up_rowA_2_JNT')
    bone.head = -0.0352, 0.0536, 1.6927
    bone.tail = -0.0352, 0.0683, 1.6927
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_eye_lid_up_rowA_2_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_eye_lid_lashes_up_rowA_2_JNT')
    bone.head = -0.0359, 0.0551, 1.6932
    bone.tail = -0.0359, 0.0699, 1.6932
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_eye_lid_lashes_up_rowA_2_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_eye_lid_up_rowA_0_JNT')
    bone.head = -0.0198, 0.0528, 1.6892
    bone.tail = -0.0198, 0.1298, 1.6892
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_eye_lid_up_rowA_0_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_eye_lid_lashes_up_rowA_0_JNT')
    bone.head = -0.0188, 0.0542, 1.6892
    bone.tail = -0.0188, 0.1311, 1.6892
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_eye_lid_lashes_up_rowA_0_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_eye_lid_up_rowA_3_JNT')
    bone.head = -0.0409, 0.0487, 1.6908
    bone.tail = -0.0409, 0.1256, 1.6908
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_eye_lid_up_rowA_3_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_eye_lid_lashes_up_rowA_3_JNT')
    bone.head = -0.0423, 0.0497, 1.6911
    bone.tail = -0.0423, 0.1267, 1.6911
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_eye_lid_lashes_up_rowA_3_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_eye_lid_up_rowB_0_JNT')
    bone.head = -0.0256, 0.0566, 1.6957
    bone.tail = -0.0256, 0.1336, 1.6957
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_eye_lid_up_rowB_0_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_eye_lid_up_rowB_1_JNT')
    bone.head = -0.0359, 0.0551, 1.6963
    bone.tail = -0.0359, 0.1321, 1.6963
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_eye_lid_up_rowB_1_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_eye_lid_up_rowB_2_JNT')
    bone.head = -0.0428, 0.0500, 1.6939
    bone.tail = -0.0428, 0.1269, 1.6939
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_eye_lid_up_rowB_2_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_eye_lid_up_rowC_0_JNT')
    bone.head = -0.0180, 0.0546, 1.6933
    bone.tail = -0.0180, 0.1316, 1.6933
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_eye_lid_up_rowC_0_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_eye_lid_up_rowC_1_JNT')
    bone.head = -0.0261, 0.0579, 1.6972
    bone.tail = -0.0261, 0.1348, 1.6972
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_eye_lid_up_rowC_1_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_eye_lid_up_rowC_2_JNT')
    bone.head = -0.0370, 0.0564, 1.6973
    bone.tail = -0.0370, 0.1334, 1.6973
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_eye_lid_up_rowC_2_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_eye_lid_up_rowC_3_JNT')
    bone.head = -0.0444, 0.0507, 1.6950
    bone.tail = -0.0444, 0.1277, 1.6950
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_eye_lid_up_rowC_3_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_eye_lid_up_rowD_1_JNT')
    bone.head = -0.0263, 0.0607, 1.6994
    bone.tail = -0.0263, 0.1376, 1.6994
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_eye_lid_up_rowD_1_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_eye_lid_up_rowD_2_JNT')
    bone.head = -0.0378, 0.0585, 1.6996
    bone.tail = -0.0378, 0.1354, 1.6996
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_eye_lid_up_rowD_2_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_eye_lid_up_rowD_3_JNT')
    bone.head = -0.0462, 0.0514, 1.6972
    bone.tail = -0.0462, 0.1284, 1.6972
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_eye_lid_up_rowD_3_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_eye_nose_rowA_0_JNT')
    bone.head = -0.0137, 0.0614, 1.6961
    bone.tail = -0.0137, 0.1384, 1.6961
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_eye_nose_rowA_0_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_eye_nose_rowA_1_JNT')
    bone.head = -0.0095, 0.0600, 1.6915
    bone.tail = -0.0095, 0.1370, 1.6915
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_eye_nose_rowA_1_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_eye_nose_rowA_2_JNT')
    bone.head = -0.0080, 0.0595, 1.6876
    bone.tail = -0.0080, 0.1365, 1.6876
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_eye_nose_rowA_2_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_eye_nose_rowA_3_JNT')
    bone.head = -0.0086, 0.0596, 1.6814
    bone.tail = -0.0086, 0.1366, 1.6814
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_eye_nose_rowA_3_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_eye_wetness_root_0_JNT')
    bone.head = -0.0284, 0.0407, 1.6901
    bone.tail = -0.0284, 0.0543, 1.6901
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_eye_wetness_root_0_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_eye_wetness_0_JNT')
    bone.head = -0.0316, 0.0539, 1.6890
    bone.tail = -0.0316, 0.0675, 1.6890
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_eye_wetness_0_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_jaw_ear_0_JNT')
    bone.head = -0.0668, -0.0311, 1.6734
    bone.tail = -0.0668, -0.0311, 1.6519
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_jaw_ear_0_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_jaw_ear_1_JNT')
    bone.head = -0.0674, -0.0294, 1.6520
    bone.tail = -0.0674, -0.0294, 1.6306
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_jaw_ear_1_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_jaw_ear_2_JNT')
    bone.head = -0.0673, -0.0227, 1.6692
    bone.tail = -0.0673, 0.0543, 1.6692
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_jaw_ear_2_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_jaw_nosabial_rowA_0_JNT')
    bone.head = -0.0233, 0.0567, 1.6478
    bone.tail = -0.0233, 0.1337, 1.6478
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_jaw_nosabial_rowA_0_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_jaw_nosabial_rowA_1_JNT')
    bone.head = -0.0353, 0.0522, 1.6362
    bone.tail = -0.0353, 0.1292, 1.6362
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_jaw_nosabial_rowA_1_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_jaw_nosabial_rowB_0_JNT')
    bone.head = -0.0262, 0.0565, 1.6528
    bone.tail = -0.0262, 0.1334, 1.6528
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_jaw_nosabial_rowB_0_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_jaw_nosabial_rowB_1_JNT')
    bone.head = -0.0393, 0.0506, 1.6409
    bone.tail = -0.0393, 0.1276, 1.6409
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_jaw_nosabial_rowB_1_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_jaw_nosabial_rowC_0_JNT')
    bone.head = -0.0300, 0.0549, 1.6614
    bone.tail = -0.0300, 0.1319, 1.6614
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_jaw_nosabial_rowC_0_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_mug_lip_up_1_JNT')
    bone.head = -0.0093, 0.0614, 1.6272
    bone.tail = -0.0093, 0.0559, 1.6272
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_mug_lip_up_1_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_mug_lip_up_inside_1_JNT')
    bone.head = -0.0075, 0.0562, 1.6268
    bone.tail = -0.0075, 0.0508, 1.6268
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_mug_lip_up_inside_1_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_mug_lip_up_2_JNT')
    bone.head = -0.0130, 0.0588, 1.6265
    bone.tail = -0.0130, 0.0539, 1.6265
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_mug_lip_up_2_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_mug_lip_up_inside_2_JNT')
    bone.head = -0.0118, 0.0541, 1.6269
    bone.tail = -0.0118, 0.0492, 1.6269
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_mug_lip_up_inside_2_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_mug_lip_up_3_JNT')
    bone.head = -0.0174, 0.0555, 1.6250
    bone.tail = -0.0174, 0.1325, 1.6250
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_mug_lip_up_3_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_mug_mouth_rowA_0_JNT')
    bone.head = -0.0043, 0.0642, 1.6331
    bone.tail = -0.0043, 0.1412, 1.6331
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_mug_mouth_rowA_0_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_mug_mouth_rowA_1_JNT')
    bone.head = -0.0104, 0.0612, 1.6333
    bone.tail = -0.0104, 0.1382, 1.6333
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_mug_mouth_rowA_1_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_mug_mouth_rowA_2_JNT')
    bone.head = -0.0166, 0.0576, 1.6321
    bone.tail = -0.0166, 0.1346, 1.6321
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_mug_mouth_rowA_2_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_mug_mouth_rowA_3_JNT')
    bone.head = -0.0216, 0.0532, 1.6277
    bone.tail = -0.0216, 0.1302, 1.6277
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_mug_mouth_rowA_3_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_mug_mouth_rowB_0_JNT')
    bone.head = -0.0044, 0.0656, 1.6378
    bone.tail = -0.0044, 0.1426, 1.6378
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_mug_mouth_rowB_0_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_mug_mouth_rowB_1_JNT')
    bone.head = -0.0131, 0.0602, 1.6397
    bone.tail = -0.0131, 0.1372, 1.6397
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_mug_mouth_rowB_1_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_mug_mouth_rowB_2_JNT')
    bone.head = -0.0215, 0.0561, 1.6380
    bone.tail = -0.0215, 0.1331, 1.6380
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_mug_mouth_rowB_2_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_nose_nosabial_rowA_0_JNT')
    bone.head = -0.0124, 0.0635, 1.6584
    bone.tail = -0.0124, 0.1405, 1.6584
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_nose_nosabial_rowA_0_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_nose_nosabial_rowB_0_JNT')
    bone.head = -0.0127, 0.0617, 1.6633
    bone.tail = -0.0127, 0.1386, 1.6633
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_nose_nosabial_rowB_0_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_nose_nosabial_rowB_1_JNT')
    bone.head = -0.0077, 0.0677, 1.6694
    bone.tail = -0.0077, 0.1447, 1.6694
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_nose_nosabial_rowB_1_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_nose_nosabial_rowC_0_JNT')
    bone.head = -0.0105, 0.0588, 1.6776
    bone.tail = -0.0105, 0.1358, 1.6776
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_nose_nosabial_rowC_0_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_nose_nosabial_rowC_1_JNT')
    bone.head = -0.0153, 0.0580, 1.6701
    bone.tail = -0.0153, 0.1349, 1.6701
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_nose_nosabial_rowC_1_JNT'] = bone.name
    bone = arm.edit_bones.new('mid_J_eye_brows_rowB_0_JNT')
    bone.head = -0.0000, 0.0708, 1.7120
    bone.tail = -0.0000, 0.1478, 1.7120
    bone.roll = 0.0000
    bone.use_connect = False
    bones['mid_J_eye_brows_rowB_0_JNT'] = bone.name
    bone = arm.edit_bones.new('mid_J_eye_brows_rowC_0_JNT')
    bone.head = -0.0000, 0.0689, 1.7309
    bone.tail = -0.0000, 0.1459, 1.7309
    bone.roll = 0.0000
    bone.use_connect = False
    bones['mid_J_eye_brows_rowC_0_JNT'] = bone.name
    bone = arm.edit_bones.new('mid_J_eye_brows_rowD_0_JNT')
    bone.head = -0.0000, 0.0643, 1.7565
    bone.tail = -0.0000, 0.1413, 1.7565
    bone.roll = 0.0000
    bone.use_connect = False
    bones['mid_J_eye_brows_rowD_0_JNT'] = bone.name
    bone = arm.edit_bones.new('mid_J_eye_nose_rowA_0_JNT')
    bone.head = -0.0000, 0.0666, 1.6875
    bone.tail = -0.0000, 0.1436, 1.6875
    bone.roll = 0.0000
    bone.use_connect = False
    bones['mid_J_eye_nose_rowA_0_JNT'] = bone.name
    bone = arm.edit_bones.new('mid_J_mug_nose_tip_rowA_0_JNT')
    bone.head = -0.0000, 0.0687, 1.6614
    bone.tail = -0.0000, 0.0687, 1.6472
    bone.roll = 0.0000
    bone.use_connect = False
    bones['mid_J_mug_nose_tip_rowA_0_JNT'] = bone.name
    bone = arm.edit_bones.new('mid_J_mug_nose_tip_rowB_0_JNT')
    bone.head = -0.0000, 0.0731, 1.6432
    bone.tail = -0.0000, 0.0731, 1.6290
    bone.roll = 0.0000
    bone.use_connect = False
    bones['mid_J_mug_nose_tip_rowB_0_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_mug_nose_nostril_0_JNT')
    bone.head = -0.0102, 0.0688, 1.6515
    bone.tail = -0.0102, 0.0688, 1.6373
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_mug_nose_nostril_0_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_mug_nose_nostril_0_JNT')
    bone.head = 0.0102, 0.0688, 1.6515
    bone.tail = 0.0102, 0.0688, 1.6373
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_mug_nose_nostril_0_JNT'] = bone.name
    bone = arm.edit_bones.new('mid_J_nose_nosabial_rowB_0_JNT')
    bone.head = -0.0000, 0.0688, 1.6810
    bone.tail = -0.0000, 0.1457, 1.6810
    bone.roll = 0.0000
    bone.use_connect = False
    bones['mid_J_nose_nosabial_rowB_0_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_eye_brows_rowA_0_JNT')
    bone.head = 0.0114, 0.0685, 1.7025
    bone.tail = 0.0114, 0.1455, 1.7025
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_eye_brows_rowA_0_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_eye_brows_rowA_0_twk_JNT')
    bone.head = 0.0040, 0.0688, 1.6986
    bone.tail = 0.0040, 0.1458, 1.6986
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_eye_brows_rowA_0_twk_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_eye_brows_rowA_2_JNT')
    bone.head = 0.0393, 0.0595, 1.7055
    bone.tail = 0.0393, 0.1365, 1.7055
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_eye_brows_rowA_2_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_eye_brows_rowA_3_JNT')
    bone.head = 0.0477, 0.0514, 1.7034
    bone.tail = 0.0477, 0.1283, 1.7034
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_eye_brows_rowA_3_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_eye_brows_rowB_0_JNT')
    bone.head = 0.0107, 0.0700, 1.7149
    bone.tail = 0.0107, 0.1470, 1.7149
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_eye_brows_rowB_0_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_eye_brows_rowB_1_JNT')
    bone.head = 0.0281, 0.0647, 1.7196
    bone.tail = 0.0281, 0.1417, 1.7196
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_eye_brows_rowB_1_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_eye_brows_rowB_2_JNT')
    bone.head = 0.0399, 0.0564, 1.7204
    bone.tail = 0.0399, 0.1333, 1.7204
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_eye_brows_rowB_2_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_eye_brows_rowB_3_JNT')
    bone.head = 0.0499, 0.0446, 1.7178
    bone.tail = 0.0499, 0.1215, 1.7178
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_eye_brows_rowB_3_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_eye_brows_rowC_0_JNT')
    bone.head = 0.0206, 0.0661, 1.7270
    bone.tail = 0.0206, 0.1431, 1.7270
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_eye_brows_rowC_0_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_eye_brows_rowC_1_JNT')
    bone.head = 0.0384, 0.0531, 1.7330
    bone.tail = 0.0384, 0.1301, 1.7330
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_eye_brows_rowC_1_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_eye_brows_rowC_2_JNT')
    bone.head = 0.0503, 0.0374, 1.7319
    bone.tail = 0.0503, 0.1144, 1.7319
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_eye_brows_rowC_2_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_eye_check_rowA_0_JNT')
    bone.head = 0.0628, 0.0144, 1.6978
    bone.tail = 0.0628, 0.0914, 1.6978
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_eye_check_rowA_0_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_eye_check_rowA_1_JNT')
    bone.head = 0.0604, 0.0225, 1.7105
    bone.tail = 0.0604, 0.0995, 1.7105
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_eye_check_rowA_1_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_eye_check_rowB_0_JNT')
    bone.head = 0.0530, 0.0377, 1.6893
    bone.tail = 0.0530, 0.1147, 1.6893
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_eye_check_rowB_0_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_eye_check_rowC_0_JNT')
    bone.head = 0.0550, 0.0366, 1.6802
    bone.tail = 0.0550, 0.1136, 1.6802
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_eye_check_rowC_0_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_eye_check_rowC_1_JNT')
    bone.head = 0.0657, 0.0038, 1.6811
    bone.tail = 0.0657, 0.0808, 1.6811
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_eye_check_rowC_1_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_eye_check_rowD_0_JNT')
    bone.head = 0.0541, 0.0399, 1.6726
    bone.tail = 0.0541, 0.1169, 1.6726
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_eye_check_rowD_0_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_eye_check_rowD_1_JNT')
    bone.head = 0.0626, 0.0216, 1.6662
    bone.tail = 0.0626, 0.0985, 1.6662
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_eye_check_rowD_1_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_eye_check_rowE_0_JNT')
    bone.head = 0.0516, 0.0440, 1.6626
    bone.tail = 0.0516, 0.1210, 1.6626
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_eye_check_rowE_0_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_eye_lid_corner_inside_0_JNT')
    bone.head = 0.0140, 0.0537, 1.6866
    bone.tail = 0.0140, 0.1307, 1.6866
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_eye_lid_corner_inside_0_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_eye_lid_up_rowD_4_JNT')
    bone.head = 0.0495, 0.0439, 1.6920
    bone.tail = 0.0495, 0.1209, 1.6920
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_eye_lid_up_rowD_4_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_eye_lid_dn_root_1_JNT')
    bone.head = 0.0284, 0.0407, 1.6901
    bone.tail = 0.0284, 0.0556, 1.6901
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_eye_lid_dn_root_1_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_eye_lid_dn_rowA_1_JNT')
    bone.head = 0.0281, 0.0546, 1.6849
    bone.tail = 0.0281, 0.0695, 1.6849
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_eye_lid_dn_rowA_1_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_eye_lid_lashes_dn_rowA_1_JNT')
    bone.head = 0.0283, 0.0559, 1.6838
    bone.tail = 0.0283, 0.0707, 1.6838
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_eye_lid_lashes_dn_rowA_1_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_eye_lid_dn_root_2_JNT')
    bone.head = 0.0284, 0.0407, 1.6901
    bone.tail = 0.0284, 0.0556, 1.6901
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_eye_lid_dn_root_2_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_eye_lid_dn_rowA_2_JNT')
    bone.head = 0.0367, 0.0522, 1.6858
    bone.tail = 0.0367, 0.0671, 1.6858
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_eye_lid_dn_rowA_2_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_eye_lid_lashes_dn_rowA_2_JNT')
    bone.head = 0.0374, 0.0533, 1.6847
    bone.tail = 0.0374, 0.0681, 1.6847
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_eye_lid_lashes_dn_rowA_2_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_eye_lid_dn_rowB_0_JNT')
    bone.head = 0.0235, 0.0541, 1.6794
    bone.tail = 0.0235, 0.1311, 1.6794
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_eye_lid_dn_rowB_0_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_eye_lid_dn_rowB_1_JNT')
    bone.head = 0.0319, 0.0529, 1.6772
    bone.tail = 0.0319, 0.1299, 1.6772
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_eye_lid_dn_rowB_1_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_eye_lid_dn_rowB_2_JNT')
    bone.head = 0.0396, 0.0494, 1.6779
    bone.tail = 0.0396, 0.1264, 1.6779
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_eye_lid_dn_rowB_2_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_eye_lid_up_root_2_JNT')
    bone.head = 0.0284, 0.0407, 1.6901
    bone.tail = 0.0284, 0.0555, 1.6901
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_eye_lid_up_root_2_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_eye_lid_up_rowA_2_JNT')
    bone.head = 0.0352, 0.0536, 1.6927
    bone.tail = 0.0352, 0.0683, 1.6927
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_eye_lid_up_rowA_2_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_eye_lid_lashes_up_rowA_2_JNT')
    bone.head = 0.0359, 0.0551, 1.6932
    bone.tail = 0.0359, 0.0699, 1.6932
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_eye_lid_lashes_up_rowA_2_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_eye_lid_up_rowA_0_JNT')
    bone.head = 0.0198, 0.0528, 1.6892
    bone.tail = 0.0198, 0.1298, 1.6892
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_eye_lid_up_rowA_0_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_eye_lid_lashes_up_rowA_0_JNT')
    bone.head = 0.0188, 0.0542, 1.6892
    bone.tail = 0.0188, 0.1311, 1.6892
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_eye_lid_lashes_up_rowA_0_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_eye_lid_up_rowA_3_JNT')
    bone.head = 0.0409, 0.0487, 1.6908
    bone.tail = 0.0409, 0.1256, 1.6908
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_eye_lid_up_rowA_3_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_eye_lid_lashes_up_rowA_3_JNT')
    bone.head = 0.0423, 0.0497, 1.6911
    bone.tail = 0.0423, 0.1267, 1.6911
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_eye_lid_lashes_up_rowA_3_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_eye_lid_up_rowB_0_JNT')
    bone.head = 0.0256, 0.0566, 1.6957
    bone.tail = 0.0256, 0.1336, 1.6957
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_eye_lid_up_rowB_0_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_eye_lid_up_rowB_1_JNT')
    bone.head = 0.0359, 0.0551, 1.6963
    bone.tail = 0.0359, 0.1321, 1.6963
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_eye_lid_up_rowB_1_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_eye_lid_up_rowB_2_JNT')
    bone.head = 0.0428, 0.0500, 1.6939
    bone.tail = 0.0428, 0.1269, 1.6939
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_eye_lid_up_rowB_2_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_eye_lid_up_rowC_0_JNT')
    bone.head = 0.0180, 0.0546, 1.6933
    bone.tail = 0.0180, 0.1316, 1.6933
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_eye_lid_up_rowC_0_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_eye_lid_up_rowC_1_JNT')
    bone.head = 0.0261, 0.0579, 1.6972
    bone.tail = 0.0261, 0.1348, 1.6972
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_eye_lid_up_rowC_1_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_eye_lid_up_rowC_2_JNT')
    bone.head = 0.0370, 0.0564, 1.6973
    bone.tail = 0.0370, 0.1334, 1.6973
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_eye_lid_up_rowC_2_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_eye_lid_up_rowC_3_JNT')
    bone.head = 0.0444, 0.0507, 1.6950
    bone.tail = 0.0444, 0.1277, 1.6950
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_eye_lid_up_rowC_3_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_eye_lid_up_rowD_1_JNT')
    bone.head = 0.0263, 0.0607, 1.6994
    bone.tail = 0.0263, 0.1376, 1.6994
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_eye_lid_up_rowD_1_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_eye_lid_up_rowD_2_JNT')
    bone.head = 0.0378, 0.0585, 1.6996
    bone.tail = 0.0378, 0.1354, 1.6996
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_eye_lid_up_rowD_2_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_eye_lid_up_rowD_3_JNT')
    bone.head = 0.0462, 0.0514, 1.6972
    bone.tail = 0.0462, 0.1284, 1.6972
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_eye_lid_up_rowD_3_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_eye_nose_rowA_0_JNT')
    bone.head = 0.0137, 0.0614, 1.6961
    bone.tail = 0.0137, 0.1384, 1.6961
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_eye_nose_rowA_0_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_eye_nose_rowA_1_JNT')
    bone.head = 0.0094, 0.0600, 1.6915
    bone.tail = 0.0094, 0.1370, 1.6915
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_eye_nose_rowA_1_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_eye_nose_rowA_2_JNT')
    bone.head = 0.0080, 0.0595, 1.6876
    bone.tail = 0.0080, 0.1365, 1.6876
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_eye_nose_rowA_2_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_eye_nose_rowA_3_JNT')
    bone.head = 0.0086, 0.0596, 1.6814
    bone.tail = 0.0086, 0.1366, 1.6814
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_eye_nose_rowA_3_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_eye_wetness_root_0_JNT')
    bone.head = 0.0283, 0.0407, 1.6901
    bone.tail = 0.0283, 0.0544, 1.6901
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_eye_wetness_root_0_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_eye_wetness_0_JNT')
    bone.head = 0.0316, 0.0539, 1.6890
    bone.tail = 0.0316, 0.0675, 1.6890
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_eye_wetness_0_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_jaw_ear_0_JNT')
    bone.head = 0.0668, -0.0311, 1.6734
    bone.tail = 0.0668, -0.0311, 1.6520
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_jaw_ear_0_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_jaw_ear_1_JNT')
    bone.head = 0.0674, -0.0294, 1.6520
    bone.tail = 0.0674, -0.0294, 1.6306
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_jaw_ear_1_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_jaw_ear_2_JNT')
    bone.head = 0.0673, -0.0227, 1.6692
    bone.tail = 0.0673, 0.0543, 1.6692
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_jaw_ear_2_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_jaw_nosabial_rowA_0_JNT')
    bone.head = 0.0233, 0.0567, 1.6478
    bone.tail = 0.0233, 0.1337, 1.6478
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_jaw_nosabial_rowA_0_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_jaw_nosabial_rowA_1_JNT')
    bone.head = 0.0353, 0.0522, 1.6362
    bone.tail = 0.0353, 0.1292, 1.6362
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_jaw_nosabial_rowA_1_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_jaw_nosabial_rowB_0_JNT')
    bone.head = 0.0262, 0.0565, 1.6528
    bone.tail = 0.0262, 0.1334, 1.6528
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_jaw_nosabial_rowB_0_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_jaw_nosabial_rowB_1_JNT')
    bone.head = 0.0393, 0.0506, 1.6409
    bone.tail = 0.0393, 0.1276, 1.6409
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_jaw_nosabial_rowB_1_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_jaw_nosabial_rowC_0_JNT')
    bone.head = 0.0300, 0.0549, 1.6614
    bone.tail = 0.0300, 0.1319, 1.6614
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_jaw_nosabial_rowC_0_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_mug_mouth_rowB_0_JNT')
    bone.head = 0.0043, 0.0656, 1.6379
    bone.tail = 0.0043, 0.1426, 1.6379
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_mug_mouth_rowB_0_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_mug_mouth_rowB_1_JNT')
    bone.head = 0.0130, 0.0603, 1.6397
    bone.tail = 0.0130, 0.1372, 1.6397
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_mug_mouth_rowB_1_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_mug_mouth_rowB_2_JNT')
    bone.head = 0.0214, 0.0562, 1.6380
    bone.tail = 0.0214, 0.1331, 1.6380
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_mug_mouth_rowB_2_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_nose_nosabial_rowA_0_JNT')
    bone.head = 0.0124, 0.0635, 1.6584
    bone.tail = 0.0124, 0.1405, 1.6584
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_nose_nosabial_rowA_0_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_nose_nosabial_rowB_0_JNT')
    bone.head = 0.0127, 0.0617, 1.6633
    bone.tail = 0.0127, 0.1386, 1.6633
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_nose_nosabial_rowB_0_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_nose_nosabial_rowB_1_JNT')
    bone.head = 0.0077, 0.0677, 1.6694
    bone.tail = 0.0077, 0.1447, 1.6694
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_nose_nosabial_rowB_1_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_nose_nosabial_rowC_0_JNT')
    bone.head = 0.0105, 0.0588, 1.6776
    bone.tail = 0.0105, 0.1358, 1.6776
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_nose_nosabial_rowC_0_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_nose_nosabial_rowC_1_JNT')
    bone.head = 0.0153, 0.0580, 1.6701
    bone.tail = 0.0153, 0.1349, 1.6701
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_nose_nosabial_rowC_1_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_mug_mouth_rowA_3_JNT')
    bone.head = 0.0216, 0.0535, 1.6278
    bone.tail = 0.0216, 0.1305, 1.6278
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_mug_mouth_rowA_3_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_mug_mouth_rowA_2_JNT')
    bone.head = 0.0165, 0.0577, 1.6321
    bone.tail = 0.0165, 0.1347, 1.6321
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_mug_mouth_rowA_2_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_mug_mouth_rowA_1_JNT')
    bone.head = 0.0103, 0.0613, 1.6333
    bone.tail = 0.0103, 0.1382, 1.6333
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_mug_mouth_rowA_1_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_mug_mouth_rowA_0_JNT')
    bone.head = 0.0041, 0.0642, 1.6331
    bone.tail = 0.0041, 0.1412, 1.6331
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_mug_mouth_rowA_0_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_mug_lip_up_3_JNT')
    bone.head = 0.0173, 0.0556, 1.6251
    bone.tail = 0.0173, 0.1326, 1.6251
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_mug_lip_up_3_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_mug_lip_up_2_JNT')
    bone.head = 0.0128, 0.0589, 1.6265
    bone.tail = 0.0128, 0.0541, 1.6265
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_mug_lip_up_2_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_mug_lip_up_inside_2_JNT')
    bone.head = 0.0116, 0.0542, 1.6270
    bone.tail = 0.0116, 0.0494, 1.6270
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_mug_lip_up_inside_2_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_mug_lip_up_1_JNT')
    bone.head = 0.0091, 0.0615, 1.6272
    bone.tail = 0.0091, 0.0560, 1.6272
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_mug_lip_up_1_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_mug_lip_up_inside_1_JNT')
    bone.head = 0.0072, 0.0564, 1.6268
    bone.tail = 0.0072, 0.0509, 1.6268
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_mug_lip_up_inside_1_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_mug_lip_up_0_JNT')
    bone.head = 0.0040, 0.0636, 1.6275
    bone.tail = 0.0040, 0.0574, 1.6275
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_mug_lip_up_0_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_mug_lip_up_inside_0_JNT')
    bone.head = 0.0033, 0.0576, 1.6264
    bone.tail = 0.0033, 0.0514, 1.6264
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_mug_lip_up_inside_0_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_eye_lid_dn_rowA_0_JNT')
    bone.head = -0.0208, 0.0529, 1.6862
    bone.tail = -0.0208, 0.1299, 1.6862
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_eye_lid_dn_rowA_0_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_eye_lid_lashes_dn_rowA_0_JNT')
    bone.head = -0.0202, 0.0541, 1.6854
    bone.tail = -0.0202, 0.1311, 1.6854
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_eye_lid_lashes_dn_rowA_0_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_eye_lid_dn_rowA_3_JNT')
    bone.head = -0.0412, 0.0480, 1.6887
    bone.tail = -0.0412, 0.1250, 1.6887
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_eye_lid_dn_rowA_3_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_eye_lid_lashes_dn_rowA_3_JNT')
    bone.head = -0.0426, 0.0486, 1.6882
    bone.tail = -0.0426, 0.1256, 1.6882
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_eye_lid_lashes_dn_rowA_3_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_eye_lid_dn_rowA_0_JNT')
    bone.head = 0.0208, 0.0529, 1.6862
    bone.tail = 0.0208, 0.1299, 1.6862
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_eye_lid_dn_rowA_0_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_eye_lid_lashes_dn_rowA_0_JNT')
    bone.head = 0.0202, 0.0541, 1.6854
    bone.tail = 0.0202, 0.1311, 1.6854
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_eye_lid_lashes_dn_rowA_0_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_eye_lid_dn_rowA_3_JNT')
    bone.head = 0.0412, 0.0480, 1.6887
    bone.tail = 0.0412, 0.1249, 1.6887
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_eye_lid_dn_rowA_3_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_eye_lid_lashes_dn_rowA_3_JNT')
    bone.head = 0.0426, 0.0486, 1.6882
    bone.tail = 0.0426, 0.1256, 1.6882
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_eye_lid_lashes_dn_rowA_3_JNT'] = bone.name
    bone = arm.edit_bones.new('jaw_root_JNT')
    bone.head = -0.0000, -0.0403, 1.6751
    bone.tail = -0.0000, -0.0071, 1.6751
    bone.roll = 0.0000
    bone.use_connect = False
    bones['jaw_root_JNT'] = bone.name
    bone = arm.edit_bones.new('mid_J_jaw_JNT')
    bone.head = -0.0000, -0.0072, 1.6766
    bone.tail = -0.0000, -0.0072, 1.6236
    bone.roll = 0.0000
    bone.use_connect = False
    bones['mid_J_jaw_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_mug_lip_dn_0_JNT')
    bone.head = -0.0042, 0.0617, 1.6196
    bone.tail = -0.0042, 0.0566, 1.6196
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_mug_lip_dn_0_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_mug_lip_dn_inside_0_JNT')
    bone.head = -0.0038, 0.0573, 1.6221
    bone.tail = -0.0038, 0.0522, 1.6221
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_mug_lip_dn_inside_0_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_jaw_nosabial_rowA_2_JNT')
    bone.head = -0.0393, 0.0429, 1.6218
    bone.tail = -0.0393, 0.0429, 1.5688
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_jaw_nosabial_rowA_2_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_jaw_nosabial_rowA_3_JNT')
    bone.head = -0.0328, 0.0426, 1.6067
    bone.tail = -0.0328, 0.0426, 1.5537
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_jaw_nosabial_rowA_3_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_jaw_nosabial_rowB_2_JNT')
    bone.head = -0.0440, 0.0383, 1.6250
    bone.tail = -0.0440, 0.0383, 1.5720
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_jaw_nosabial_rowB_2_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_jaw_nosabial_rowB_3_JNT')
    bone.head = -0.0400, 0.0336, 1.6073
    bone.tail = -0.0400, 0.0336, 1.5543
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_jaw_nosabial_rowB_3_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_jaw_nosabial_rowB_4_JNT')
    bone.head = -0.0232, 0.0318, 1.5886
    bone.tail = -0.0232, 0.0318, 1.5356
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_jaw_nosabial_rowB_4_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_jaw_nosabial_rowC_2_JNT')
    bone.head = -0.0521, 0.0298, 1.6323
    bone.tail = -0.0521, 0.0298, 1.5793
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_jaw_nosabial_rowC_2_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_jaw_nosabial_rowC_3_JNT')
    bone.head = -0.0493, 0.0217, 1.6125
    bone.tail = -0.0493, 0.0217, 1.5595
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_jaw_nosabial_rowC_3_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_jaw_nosabial_rowD_0_JNT')
    bone.head = -0.0596, 0.0161, 1.6421
    bone.tail = -0.0596, 0.0161, 1.5891
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_jaw_nosabial_rowD_0_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_jaw_rowA_0_JNT')
    bone.head = -0.0627, 0.0001, 1.6517
    bone.tail = -0.0627, 0.0001, 1.5987
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_jaw_rowA_0_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_jaw_rowB_0_JNT')
    bone.head = -0.0575, -0.0200, 1.6348
    bone.tail = -0.0575, -0.0200, 1.5818
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_jaw_rowB_0_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_jaw_rowB_1_JNT')
    bone.head = -0.0524, -0.0118, 1.6158
    bone.tail = -0.0524, -0.0118, 1.5628
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_jaw_rowB_1_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_jaw_rowB_2_JNT')
    bone.head = -0.0393, -0.0032, 1.5994
    bone.tail = -0.0393, -0.0032, 1.5464
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_jaw_rowB_2_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_jaw_throat_rowA_0_JNT')
    bone.head = -0.0224, 0.0116, 1.5901
    bone.tail = -0.0224, 0.0116, 1.5371
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_jaw_throat_rowA_0_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_mug_chin_rowA_0_JNT')
    bone.head = -0.0139, 0.0576, 1.5988
    bone.tail = -0.0139, 0.0576, 1.5458
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_mug_chin_rowA_0_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_mug_chin_rowA_1_JNT')
    bone.head = -0.0145, 0.0568, 1.5906
    bone.tail = -0.0145, 0.0568, 1.5376
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_mug_chin_rowA_1_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_mug_chin_rowA_2_JNT')
    bone.head = -0.0105, 0.0518, 1.5837
    bone.tail = -0.0105, 0.0518, 1.5307
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_mug_chin_rowA_2_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_mug_lip_corner_0_JNT')
    bone.head = -0.0224, 0.0512, 1.6226
    bone.tail = -0.0133, 0.0512, 1.6226
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_mug_lip_corner_0_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_mug_lip_corner_inside_dn_0_JNT')
    bone.head = -0.0158, 0.0466, 1.6185
    bone.tail = -0.0068, 0.0466, 1.6185
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_mug_lip_corner_inside_dn_0_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_mug_lip_corner_inside_up_0_JNT')
    bone.head = -0.0174, 0.0489, 1.6298
    bone.tail = -0.0083, 0.0489, 1.6298
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_mug_lip_corner_inside_up_0_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_mug_lip_dn_1_JNT')
    bone.head = -0.0093, 0.0597, 1.6199
    bone.tail = -0.0093, 0.0549, 1.6199
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_mug_lip_dn_1_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_mug_lip_dn_inside_1_JNT')
    bone.head = -0.0073, 0.0558, 1.6219
    bone.tail = -0.0073, 0.0510, 1.6219
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_mug_lip_dn_inside_1_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_mug_lip_dn_2_JNT')
    bone.head = -0.0129, 0.0577, 1.6202
    bone.tail = -0.0129, 0.0533, 1.6202
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_mug_lip_dn_2_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_mug_lip_dn_inside_2_JNT')
    bone.head = -0.0109, 0.0539, 1.6213
    bone.tail = -0.0109, 0.0494, 1.6213
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_mug_lip_dn_inside_2_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_mug_lip_dn_3_JNT')
    bone.head = -0.0168, 0.0548, 1.6206
    bone.tail = -0.0168, 0.0548, 1.5676
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_mug_lip_dn_3_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_mug_mouth_rowA_4_JNT')
    bone.head = -0.0216, 0.0516, 1.6192
    bone.tail = -0.0216, 0.0516, 1.5662
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_mug_mouth_rowA_4_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_mug_mouth_rowA_5_JNT')
    bone.head = -0.0157, 0.0538, 1.6134
    bone.tail = -0.0157, 0.0538, 1.5604
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_mug_mouth_rowA_5_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_mug_mouth_rowA_6_JNT')
    bone.head = -0.0059, 0.0570, 1.6122
    bone.tail = -0.0059, 0.0570, 1.5592
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_mug_mouth_rowA_6_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_mug_mouth_rowB_4_JNT')
    bone.head = -0.0284, 0.0452, 1.6192
    bone.tail = -0.0284, 0.0452, 1.5662
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_mug_mouth_rowB_4_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_mug_mouth_rowB_5_JNT')
    bone.head = -0.0220, 0.0469, 1.6088
    bone.tail = -0.0220, 0.0469, 1.5558
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_mug_mouth_rowB_5_JNT'] = bone.name
    bone = arm.edit_bones.new('mid_J_jaw_nosabial_rowB_0_JNT')
    bone.head = -0.0000, 0.0317, 1.5844
    bone.tail = -0.0000, 0.0317, 1.5314
    bone.roll = 0.0000
    bone.use_connect = False
    bones['mid_J_jaw_nosabial_rowB_0_JNT'] = bone.name
    bone = arm.edit_bones.new('mid_J_jaw_throat_rowA_0_JNT')
    bone.head = -0.0000, 0.0160, 1.5857
    bone.tail = -0.0000, 0.0160, 1.5327
    bone.roll = 0.0000
    bone.use_connect = False
    bones['mid_J_jaw_throat_rowA_0_JNT'] = bone.name
    bone = arm.edit_bones.new('mid_J_mug_chin_rowA_0_JNT')
    bone.head = -0.0000, 0.0620, 1.6023
    bone.tail = -0.0000, 0.0620, 1.5493
    bone.roll = 0.0000
    bone.use_connect = False
    bones['mid_J_mug_chin_rowA_0_JNT'] = bone.name
    bone = arm.edit_bones.new('mid_J_mug_chin_rowA_1_JNT')
    bone.head = -0.0000, 0.0621, 1.5899
    bone.tail = -0.0000, 0.0621, 1.5369
    bone.roll = 0.0000
    bone.use_connect = False
    bones['mid_J_mug_chin_rowA_1_JNT'] = bone.name
    bone = arm.edit_bones.new('mid_J_tongue_rowA_0_JNT')
    bone.head = 0.0001, 0.0167, 1.6293
    bone.tail = 0.0001, 0.0329, 1.6293
    bone.roll = 0.0000
    bone.use_connect = False
    bones['mid_J_tongue_rowA_0_JNT'] = bone.name
    bone = arm.edit_bones.new('mid_J_tongue_rowB_0_JNT')
    bone.head = 0.0001, 0.0326, 1.6262
    bone.tail = 0.0001, 0.0402, 1.6262
    bone.roll = 0.0000
    bone.use_connect = False
    bones['mid_J_tongue_rowB_0_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_tongue_rowB_0_JNT')
    bone.head = -0.0074, 0.0330, 1.6271
    bone.tail = -0.0074, 0.0406, 1.6271
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_tongue_rowB_0_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_tongue_rowB_0_JNT')
    bone.head = 0.0077, 0.0330, 1.6272
    bone.tail = 0.0077, 0.0406, 1.6272
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_tongue_rowB_0_JNT'] = bone.name
    bone = arm.edit_bones.new('mid_J_tongue_rowC_0_JNT')
    bone.head = 0.0001, 0.0396, 1.6225
    bone.tail = 0.0001, 0.0447, 1.6225
    bone.roll = 0.0000
    bone.use_connect = False
    bones['mid_J_tongue_rowC_0_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_tongue_rowC_0_JNT')
    bone.head = 0.0058, 0.0401, 1.6229
    bone.tail = 0.0058, 0.0452, 1.6229
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_tongue_rowC_0_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_tongue_rowC_0_JNT')
    bone.head = -0.0055, 0.0400, 1.6229
    bone.tail = -0.0055, 0.0451, 1.6229
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_tongue_rowC_0_JNT'] = bone.name
    bone = arm.edit_bones.new('mid_J_tongue_rowD_0_JNT')
    bone.head = 0.0001, 0.0443, 1.6204
    bone.tail = 0.0001, 0.0443, 1.6252
    bone.roll = 0.0000
    bone.use_connect = False
    bones['mid_J_tongue_rowD_0_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_tongue_rowD_0_JNT')
    bone.head = -0.0046, 0.0443, 1.6205
    bone.tail = -0.0046, 0.0443, 1.6253
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_tongue_rowD_0_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_tongue_rowD_0_JNT')
    bone.head = 0.0049, 0.0443, 1.6206
    bone.tail = 0.0049, 0.0443, 1.6253
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_tongue_rowD_0_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_jaw_nosabial_rowA_2_JNT')
    bone.head = 0.0393, 0.0429, 1.6218
    bone.tail = 0.0393, 0.0429, 1.5688
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_jaw_nosabial_rowA_2_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_jaw_nosabial_rowA_3_JNT')
    bone.head = 0.0328, 0.0426, 1.6067
    bone.tail = 0.0328, 0.0426, 1.5537
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_jaw_nosabial_rowA_3_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_jaw_nosabial_rowB_2_JNT')
    bone.head = 0.0440, 0.0383, 1.6250
    bone.tail = 0.0440, 0.0383, 1.5720
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_jaw_nosabial_rowB_2_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_jaw_nosabial_rowB_3_JNT')
    bone.head = 0.0400, 0.0336, 1.6073
    bone.tail = 0.0400, 0.0336, 1.5543
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_jaw_nosabial_rowB_3_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_jaw_nosabial_rowB_4_JNT')
    bone.head = 0.0232, 0.0318, 1.5886
    bone.tail = 0.0232, 0.0318, 1.5356
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_jaw_nosabial_rowB_4_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_jaw_nosabial_rowC_2_JNT')
    bone.head = 0.0521, 0.0298, 1.6323
    bone.tail = 0.0521, 0.0298, 1.5793
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_jaw_nosabial_rowC_2_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_jaw_nosabial_rowC_3_JNT')
    bone.head = 0.0493, 0.0217, 1.6125
    bone.tail = 0.0493, 0.0217, 1.5595
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_jaw_nosabial_rowC_3_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_jaw_nosabial_rowD_0_JNT')
    bone.head = 0.0596, 0.0161, 1.6421
    bone.tail = 0.0596, 0.0161, 1.5891
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_jaw_nosabial_rowD_0_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_jaw_rowA_0_JNT')
    bone.head = 0.0627, 0.0001, 1.6517
    bone.tail = 0.0627, 0.0001, 1.5987
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_jaw_rowA_0_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_jaw_rowB_0_JNT')
    bone.head = 0.0575, -0.0200, 1.6348
    bone.tail = 0.0575, -0.0200, 1.5818
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_jaw_rowB_0_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_jaw_rowB_1_JNT')
    bone.head = 0.0524, -0.0118, 1.6158
    bone.tail = 0.0524, -0.0118, 1.5628
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_jaw_rowB_1_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_jaw_rowB_2_JNT')
    bone.head = 0.0393, -0.0032, 1.5994
    bone.tail = 0.0393, -0.0032, 1.5464
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_jaw_rowB_2_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_jaw_throat_rowA_0_JNT')
    bone.head = 0.0224, 0.0116, 1.5901
    bone.tail = 0.0224, 0.0116, 1.5371
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_jaw_throat_rowA_0_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_mug_chin_rowA_0_JNT')
    bone.head = 0.0139, 0.0576, 1.5988
    bone.tail = 0.0139, 0.0576, 1.5458
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_mug_chin_rowA_0_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_mug_chin_rowA_1_JNT')
    bone.head = 0.0145, 0.0568, 1.5906
    bone.tail = 0.0145, 0.0568, 1.5376
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_mug_chin_rowA_1_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_mug_chin_rowA_2_JNT')
    bone.head = 0.0105, 0.0519, 1.5837
    bone.tail = 0.0105, 0.0519, 1.5307
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_mug_chin_rowA_2_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_mug_lip_corner_0_JNT')
    bone.head = 0.0223, 0.0517, 1.6225
    bone.tail = 0.0130, 0.0517, 1.6225
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_mug_lip_corner_0_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_mug_lip_corner_inside_dn_0_JNT')
    bone.head = 0.0155, 0.0469, 1.6183
    bone.tail = 0.0062, 0.0469, 1.6183
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_mug_lip_corner_inside_dn_0_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_mug_lip_corner_inside_up_0_JNT')
    bone.head = 0.0173, 0.0490, 1.6298
    bone.tail = 0.0080, 0.0490, 1.6298
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_mug_lip_corner_inside_up_0_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_mug_lip_dn_0_JNT')
    bone.head = 0.0040, 0.0618, 1.6196
    bone.tail = 0.0040, 0.0567, 1.6196
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_mug_lip_dn_0_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_mug_lip_dn_inside_0_JNT')
    bone.head = 0.0034, 0.0574, 1.6222
    bone.tail = 0.0034, 0.0522, 1.6222
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_mug_lip_dn_inside_0_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_mug_lip_dn_1_JNT')
    bone.head = 0.0091, 0.0598, 1.6199
    bone.tail = 0.0091, 0.0550, 1.6199
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_mug_lip_dn_1_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_mug_lip_dn_inside_1_JNT')
    bone.head = 0.0070, 0.0560, 1.6219
    bone.tail = 0.0070, 0.0511, 1.6219
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_mug_lip_dn_inside_1_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_mug_lip_dn_2_JNT')
    bone.head = 0.0126, 0.0578, 1.6202
    bone.tail = 0.0126, 0.0534, 1.6202
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_mug_lip_dn_2_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_mug_lip_dn_inside_2_JNT')
    bone.head = 0.0105, 0.0541, 1.6214
    bone.tail = 0.0105, 0.0496, 1.6214
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_mug_lip_dn_inside_2_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_mug_lip_dn_3_JNT')
    bone.head = 0.0166, 0.0550, 1.6206
    bone.tail = 0.0166, 0.0550, 1.5676
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_mug_lip_dn_3_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_mug_mouth_rowA_4_JNT')
    bone.head = 0.0216, 0.0520, 1.6192
    bone.tail = 0.0216, 0.0520, 1.5662
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_mug_mouth_rowA_4_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_mug_mouth_rowA_5_JNT')
    bone.head = 0.0155, 0.0538, 1.6134
    bone.tail = 0.0155, 0.0538, 1.5604
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_mug_mouth_rowA_5_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_mug_mouth_rowA_6_JNT')
    bone.head = 0.0058, 0.0570, 1.6122
    bone.tail = 0.0058, 0.0570, 1.5592
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_mug_mouth_rowA_6_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_mug_mouth_rowB_4_JNT')
    bone.head = 0.0283, 0.0454, 1.6192
    bone.tail = 0.0283, 0.0454, 1.5662
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_mug_mouth_rowB_4_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_mug_mouth_rowB_5_JNT')
    bone.head = 0.0219, 0.0469, 1.6088
    bone.tail = 0.0219, 0.0469, 1.5558
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_mug_mouth_rowB_5_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_eye_JNT')
    bone.head = -0.0284, 0.0407, 1.6901
    bone.tail = -0.0284, 0.0543, 1.6901
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_eye_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_eye_pupil_JNT')
    bone.head = -0.0294, 0.0542, 1.6896
    bone.tail = -0.0294, 0.0678, 1.6896
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_eye_pupil_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_eye_JNT')
    bone.head = 0.0284, 0.0407, 1.6901
    bone.tail = 0.0284, 0.0543, 1.6901
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_eye_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_eye_pupil_JNT')
    bone.head = 0.0293, 0.0543, 1.6896
    bone.tail = 0.0293, 0.0678, 1.6896
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_eye_pupil_JNT'] = bone.name
    bone = arm.edit_bones.new('HeadTip')
    bone.head = -0.0000, -0.0403, 1.8166
    bone.tail = -0.0000, -0.0403, 1.8266
    bone.roll = 0.0000
    bone.use_connect = False
    bones['HeadTip'] = bone.name
    bone = arm.edit_bones.new('gravity_root_upPoint_GRP')
    bone.head = -0.0000, -0.0403, 1.8166
    bone.tail = -0.0000, -0.0403, 1.8266
    bone.roll = 0.0000
    bone.use_connect = False
    bones['gravity_root_upPoint_GRP'] = bone.name
    bone = arm.edit_bones.new('head_upDn_topDetectZero_GRP')
    bone.head = -0.0000, -0.0403, 1.6397
    bone.tail = -0.0100, -0.0403, 1.6397
    bone.roll = 0.0000
    bone.use_connect = False
    bones['head_upDn_topDetectZero_GRP'] = bone.name
    bone = arm.edit_bones.new('head_tilt_start_GRP')
    bone.head = -0.0600, -0.0403, 1.6397
    bone.tail = -0.0600, -0.0403, 1.6497
    bone.roll = 0.0000
    bone.use_connect = False
    bones['head_tilt_start_GRP'] = bone.name
    bone = arm.edit_bones.new('gravity_front_GRP')
    bone.head = -0.0000, -0.0303, 1.6397
    bone.tail = -0.0000, -0.0303, 1.6497
    bone.roll = 0.0000
    bone.use_connect = False
    bones['gravity_front_GRP'] = bone.name
    bone = arm.edit_bones.new('gravity_side_GRP')
    bone.head = -0.0100, -0.0403, 1.6397
    bone.tail = -0.0100, -0.0403, 1.6497
    bone.roll = 0.0000
    bone.use_connect = False
    bones['gravity_side_GRP'] = bone.name
    bone = arm.edit_bones.new('l_sternocleidomastoid_top_mscl_Offset_GRP')
    bone.head = -0.0551, -0.0403, 1.6397
    bone.tail = -0.0551, -0.0487, 1.5981
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_sternocleidomastoid_top_mscl_Offset_GRP'] = bone.name
    bone = arm.edit_bones.new('l_sternocleidomastoid_top_mscl_JNT')
    bone.head = -0.0431, -0.0341, 1.5995
    bone.tail = -0.0468, -0.0360, 1.6119
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_sternocleidomastoid_top_mscl_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_jaw_rowC_0_JNT')
    bone.head = -0.0487, -0.0278, 1.6095
    bone.tail = -0.0524, -0.0298, 1.6219
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_jaw_rowC_0_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_neck_rowA_0_JNT')
    bone.head = -0.0468, -0.0474, 1.6095
    bone.tail = -0.0505, -0.0494, 1.6219
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_neck_rowA_0_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_jaw_rowC_1_JNT')
    bone.head = -0.0389, -0.0203, 1.5894
    bone.tail = -0.0427, -0.0222, 1.6018
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_jaw_rowC_1_JNT'] = bone.name
    bone = arm.edit_bones.new('r_sternocleidomastoid_top_mscl_Offset_GRP')
    bone.head = 0.0551, -0.0403, 1.6397
    bone.tail = 0.0551, -0.0487, 1.5981
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_sternocleidomastoid_top_mscl_Offset_GRP'] = bone.name
    bone = arm.edit_bones.new('r_sternocleidomastoid_top_mscl_JNT')
    bone.head = 0.0431, -0.0341, 1.5995
    bone.tail = 0.0468, -0.0360, 1.6119
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_sternocleidomastoid_top_mscl_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_jaw_rowC_1_JNT')
    bone.head = 0.0389, -0.0203, 1.5894
    bone.tail = 0.0427, -0.0222, 1.6018
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_jaw_rowC_1_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_jaw_rowC_0_JNT')
    bone.head = 0.0487, -0.0278, 1.6095
    bone.tail = 0.0524, -0.0298, 1.6219
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_jaw_rowC_0_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_neck_rowA_0_JNT')
    bone.head = 0.0468, -0.0474, 1.6095
    bone.tail = 0.0505, -0.0494, 1.6219
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_neck_rowA_0_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_jaw_throat_rowB_0_JNT')
    bone.head = -0.0192, -0.0086, 1.5761
    bone.tail = -0.0192, 0.0008, 1.6226
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_jaw_throat_rowB_0_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_neck_rowA_1_JNT')
    bone.head = -0.0433, -0.0362, 1.5734
    bone.tail = -0.0433, -0.0269, 1.6199
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_neck_rowA_1_JNT'] = bone.name
    bone = arm.edit_bones.new('mid_J_jaw_throat_rowB_0_JNT')
    bone.head = -0.0000, -0.0009, 1.5717
    bone.tail = -0.0000, 0.0085, 1.6182
    bone.roll = 0.0000
    bone.use_connect = False
    bones['mid_J_jaw_throat_rowB_0_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_jaw_throat_rowB_0_JNT')
    bone.head = 0.0192, -0.0086, 1.5761
    bone.tail = 0.0192, 0.0008, 1.6226
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_jaw_throat_rowB_0_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_neck_rowA_1_JNT')
    bone.head = 0.0433, -0.0362, 1.5734
    bone.tail = 0.0433, -0.0269, 1.6199
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_neck_rowA_1_JNT'] = bone.name
    bone = arm.edit_bones.new('l_sternocleidomastoid_top_mscl_endBounce_GRP')
    bone.head = -0.0352, -0.0218, 1.5534
    bone.tail = -0.0352, -0.0125, 1.5998
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_sternocleidomastoid_top_mscl_endBounce_GRP'] = bone.name
    bone = arm.edit_bones.new('r_sternocleidomastoid_top_mscl_endBounce_GRP')
    bone.head = 0.0352, -0.0218, 1.5534
    bone.tail = 0.0352, -0.0125, 1.5998
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_sternocleidomastoid_top_mscl_endBounce_GRP'] = bone.name
    bone = arm.edit_bones.new('sternocleidomastoid_top_start_GRP')
    bone.head = -0.0000, -0.0548, 1.5682
    bone.tail = -0.0000, -0.0149, 1.5550
    bone.roll = 0.0000
    bone.use_connect = False
    bones['sternocleidomastoid_top_start_GRP'] = bone.name
    bone = arm.edit_bones.new('l_sternocleidomastoid_top_start_Offset_GRP')
    bone.head = -0.0310, -0.0279, 1.5593
    bone.tail = -0.0100, 0.0067, 1.5479
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_sternocleidomastoid_top_start_Offset_GRP'] = bone.name
    bone = arm.edit_bones.new('l_sternocleidomastoid_top_start_Offset_B_GRP')
    bone.head = -0.0310, -0.0279, 1.5593
    bone.tail = -0.0100, 0.0067, 1.5479
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_sternocleidomastoid_top_start_Offset_B_GRP'] = bone.name
    bone = arm.edit_bones.new('l_sternocleidomastoid_top_start_GRP')
    bone.head = -0.0310, -0.0279, 1.5593
    bone.tail = -0.0310, -0.0411, 1.5194
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_sternocleidomastoid_top_start_GRP'] = bone.name
    bone = arm.edit_bones.new('r_sternocleidomastoid_top_start_Offset_GRP')
    bone.head = 0.0310, -0.0279, 1.5593
    bone.tail = 0.0520, -0.0624, 1.5707
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_sternocleidomastoid_top_start_Offset_GRP'] = bone.name
    bone = arm.edit_bones.new('r_sternocleidomastoid_top_start_Offset_B_GRP')
    bone.head = 0.0310, -0.0279, 1.5593
    bone.tail = 0.0520, -0.0624, 1.5708
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_sternocleidomastoid_top_start_Offset_B_GRP'] = bone.name
    bone = arm.edit_bones.new('r_sternocleidomastoid_top_start_GRP')
    bone.head = 0.0310, -0.0279, 1.5593
    bone.tail = 0.0310, -0.0411, 1.5194
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_sternocleidomastoid_top_start_GRP'] = bone.name
    bone = arm.edit_bones.new('head_upDn_botDetectZero_GRP')
    bone.head = -0.0000, -0.0548, 1.5682
    bone.tail = -0.0474, -0.0548, 1.5682
    bone.roll = 0.0000
    bone.use_connect = False
    bones['head_upDn_botDetectZero_GRP'] = bone.name
    bone = arm.edit_bones.new('neck_upDn_topDetectZero_GRP')
    bone.head = -0.0000, -0.0548, 1.5682
    bone.tail = -0.0474, -0.0548, 1.5682
    bone.roll = 0.0000
    bone.use_connect = False
    bones['neck_upDn_topDetectZero_GRP'] = bone.name
    bone = arm.edit_bones.new('head_tilt_end_GRP')
    bone.head = -0.0600, -0.0403, 1.6397
    bone.tail = -0.0600, -0.0403, 1.6871
    bone.roll = 0.0000
    bone.use_connect = False
    bones['head_tilt_end_GRP'] = bone.name
    bone = arm.edit_bones.new('neck_tilt_start_GRP')
    bone.head = -0.0600, -0.0548, 1.5682
    bone.tail = -0.0600, -0.0454, 1.6146
    bone.roll = 0.0000
    bone.use_connect = False
    bones['neck_tilt_start_GRP'] = bone.name
    bone = arm.edit_bones.new('l_sternocleidomastoid_bot_mscl_JNT')
    bone.head = -0.0190, -0.0216, 1.5191
    bone.tail = -0.0257, -0.0251, 1.5416
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_sternocleidomastoid_bot_mscl_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_neck_rowA_2_JNT')
    bone.head = -0.0369, -0.0291, 1.5430
    bone.tail = -0.0437, -0.0326, 1.5655
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_neck_rowA_2_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_neck_throat_rowA_0_JNT')
    bone.head = -0.0211, -0.0178, 1.5424
    bone.tail = -0.0278, -0.0213, 1.5649
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_neck_throat_rowA_0_JNT'] = bone.name
    bone = arm.edit_bones.new('r_sternocleidomastoid_bot_mscl_JNT')
    bone.head = 0.0190, -0.0216, 1.5191
    bone.tail = 0.0257, -0.0251, 1.5416
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_sternocleidomastoid_bot_mscl_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_neck_rowA_2_JNT')
    bone.head = 0.0369, -0.0291, 1.5430
    bone.tail = 0.0437, -0.0326, 1.5655
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_neck_rowA_2_JNT'] = bone.name
    bone = arm.edit_bones.new('r_J_neck_throat_rowA_0_JNT')
    bone.head = 0.0211, -0.0178, 1.5424
    bone.tail = 0.0278, -0.0213, 1.5649
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_neck_throat_rowA_0_JNT'] = bone.name
    bone = arm.edit_bones.new('mid_J_neck_throat_rowA_0_JNT')
    bone.head = -0.0000, -0.0124, 1.5467
    bone.tail = -0.0000, 0.0078, 1.6021
    bone.roll = 0.0000
    bone.use_connect = False
    bones['mid_J_neck_throat_rowA_0_JNT'] = bone.name
    bone = arm.edit_bones.new('l_sternocleidomastoid_top_mscl_startBounce_GRP')
    bone.head = -0.0352, -0.0165, 1.5681
    bone.tail = 0.0065, 0.0227, 1.5538
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_sternocleidomastoid_top_mscl_startBounce_GRP'] = bone.name
    bone = arm.edit_bones.new('r_sternocleidomastoid_top_mscl_startBounce_GRP')
    bone.head = 0.0352, -0.0165, 1.5681
    bone.tail = -0.0065, 0.0227, 1.5538
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_sternocleidomastoid_top_mscl_startBounce_GRP'] = bone.name
    bone = arm.edit_bones.new('r_J_neck_rowB_0_JNT')
    bone.head = 0.0412, -0.0738, 1.5773
    bone.tail = 0.0412, -0.0536, 1.6327
    bone.roll = 0.0000
    bone.use_connect = False
    bones['r_J_neck_rowB_0_JNT'] = bone.name
    bone = arm.edit_bones.new('l_J_neck_rowB_0_JNT')
    bone.head = -0.0413, -0.0738, 1.5773
    bone.tail = -0.0413, -0.0536, 1.6327
    bone.roll = 0.0000
    bone.use_connect = False
    bones['l_J_neck_rowB_0_JNT'] = bone.name
    bone = arm.edit_bones.new('neck_upDn_botDetectZero_GRP')
    bone.head = -0.0000, -0.0765, 1.5087
    bone.tail = -0.0590, -0.0765, 1.5087
    bone.roll = 0.0000
    bone.use_connect = False
    bones['neck_upDn_botDetectZero_GRP'] = bone.name
    bone = arm.edit_bones.new('neck_tilt_end_GRP')
    bone.head = -0.0600, -0.0548, 1.5682
    bone.tail = -0.0600, -0.0431, 1.6260
    bone.roll = 0.0000
    bone.use_connect = False
    bones['neck_tilt_end_GRP'] = bone.name
    bone = arm.edit_bones.new('skeleton:torso_bone')
    bone.head = -0.0000, -0.0475, 1.0476
    bone.tail = -0.0000, -0.0394, 1.1598
    bone.roll = 0.0000
    bone.use_connect = False
    bones['skeleton:torso_bone'] = bone.name
    bone = arm.edit_bones.new('skeleton:TransformationTarget')
    bone.head = 0.0000, 0.0000, 0.0000
    bone.tail = 0.5000, 0.0000, 0.0000
    bone.roll = 0.0000
    bone.use_connect = False
    bones['skeleton:TransformationTarget'] = bone.name
    bone = arm.edit_bones.new('new_torso')
    bone.head = -0.0000, -0.0467, 1.1211
    bone.tail = -0.0000, -0.0475, 1.0476
    bone.roll = 0.0000
    bone.use_connect = False
    bones['new_torso'] = bone.name
    bone = arm.edit_bones.new('Trajectory')
    bone.head = -0.0000, -0.0000, 0.0000
    bone.tail = 0.0000, 0.0000, 1.0137
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['Root']]
    bones['Trajectory'] = bone.name
    bone = arm.edit_bones.new('reference_joint')
    bone.head = -0.0000, -0.0000, 0.0000
    bone.tail = -0.0000, 0.0000, 1.0137
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['Root']]
    bones['reference_joint'] = bone.name
    bone = arm.edit_bones.new('gravity_setup_GRP')
    bone.head = -0.0000, -0.0000, 0.0000
    bone.tail = -0.0000, 0.0000, 1.6402
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['Root']]
    bones['gravity_setup_GRP'] = bone.name
    bone = arm.edit_bones.new('Spine')
    bone.head = -0.0000, -0.0540, 1.0823
    bone.tail = -0.0000, -0.0394, 1.1598
    bone.roll = 0.0000
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['Hips']]
    bones['Spine'] = bone.name
    bone = arm.edit_bones.new('LeftUpLeg')
    bone.head = -0.0767, -0.0410, 1.0128
    bone.tail = -0.1149, -0.0569, 0.5836
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['Hips']]
    bones['LeftUpLeg'] = bone.name
    bone = arm.edit_bones.new('RightUpLeg')
    bone.head = 0.0767, -0.0410, 1.0128
    bone.tail = 0.1149, -0.0569, 0.5836
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['Hips']]
    bones['RightUpLeg'] = bone.name
    bone = arm.edit_bones.new('l_leg_buttock_mscl_JNT')
    bone.head = -0.0701, -0.0981, 1.0275
    bone.tail = -0.0846, -0.1129, 0.9598
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['Hips']]
    bones['l_leg_buttock_mscl_JNT'] = bone.name
    bone = arm.edit_bones.new('r_leg_buttock_mscl_JNT')
    bone.head = 0.0701, -0.0981, 1.0275
    bone.tail = 0.0846, -0.1129, 0.9598
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['Hips']]
    bones['r_leg_buttock_mscl_JNT'] = bone.name
    bone = arm.edit_bones.new('gravity_GRP')
    bone.head = -0.0000, -0.0403, 1.6397
    bone.tail = -0.0000, -0.0303, 1.6397
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['gravity_setup_GRP']]
    bones['gravity_GRP'] = bone.name
    bone = arm.edit_bones.new('gravity_root_GRP')
    bone.head = -0.0000, -0.0403, 1.6397
    bone.tail = 1.6402, -0.0403, 1.6397
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['gravity_setup_GRP']]
    bones['gravity_root_GRP'] = bone.name
    bone = arm.edit_bones.new('Spine1')
    bone.head = -0.0000, -0.0394, 1.1598
    bone.tail = -0.0000, -0.0413, 1.2466
    bone.roll = 0.0000
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['Spine']]
    bones['Spine1'] = bone.name
    bone = arm.edit_bones.new('LeftLeg')
    bone.head = -0.1149, -0.0569, 0.5836
    bone.tail = -0.1567, -0.0860, 0.1176
    bone.roll = 0.0000
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['LeftUpLeg']]
    bones['LeftLeg'] = bone.name
    bone = arm.edit_bones.new('l_thigh_0_JNT')
    bone.head = -0.0894, -0.0450, 0.8698
    bone.tail = -0.0929, -0.0461, 0.8310
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['LeftUpLeg']]
    bones['l_thigh_0_JNT'] = bone.name
    bone = arm.edit_bones.new('l_thigh_1_JNT')
    bone.head = -0.1022, -0.0491, 0.7267
    bone.tail = -0.1043, -0.0498, 0.7023
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['LeftUpLeg']]
    bones['l_thigh_1_JNT'] = bone.name
    bone = arm.edit_bones.new('l_leg_groin_mscl_JNT')
    bone.head = -0.0725, -0.0024, 1.0098
    bone.tail = -0.0685, -0.0093, 1.0479
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['LeftUpLeg']]
    bones['l_leg_groin_mscl_JNT'] = bone.name
    bone = arm.edit_bones.new('RightLeg')
    bone.head = 0.1149, -0.0569, 0.5836
    bone.tail = 0.1567, -0.0860, 0.1176
    bone.roll = 0.0000
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['RightUpLeg']]
    bones['RightLeg'] = bone.name
    bone = arm.edit_bones.new('r_thigh_0_JNT')
    bone.head = 0.0894, -0.0450, 0.8698
    bone.tail = 0.0929, -0.0461, 0.8310
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['RightUpLeg']]
    bones['r_thigh_0_JNT'] = bone.name
    bone = arm.edit_bones.new('r_thigh_1_JNT')
    bone.head = 0.1022, -0.0491, 0.7267
    bone.tail = 0.1043, -0.0498, 0.7023
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['RightUpLeg']]
    bones['r_thigh_1_JNT'] = bone.name
    bone = arm.edit_bones.new('r_leg_groin_mscl_JNT')
    bone.head = 0.0725, -0.0024, 1.0098
    bone.tail = 0.0764, 0.0045, 0.9717
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['RightUpLeg']]
    bones['r_leg_groin_mscl_JNT'] = bone.name
    bone = arm.edit_bones.new('gravity_front_orig_GRP')
    bone.head = -0.0000, -0.0303, 1.6397
    bone.tail = -0.0000, -0.0203, 1.6397
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['gravity_GRP']]
    bones['gravity_front_orig_GRP'] = bone.name
    bone = arm.edit_bones.new('gravity_side_orig_GRP')
    bone.head = -0.0100, -0.0403, 1.6397
    bone.tail = -0.0100, -0.0303, 1.6397
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['gravity_GRP']]
    bones['gravity_side_orig_GRP'] = bone.name
    bone = arm.edit_bones.new('Spine2')
    bone.head = -0.0000, -0.0413, 1.2466
    bone.tail = -0.0000, -0.0724, 1.3636
    bone.roll = 0.0000
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['Spine1']]
    bones['Spine2'] = bone.name
    bone = arm.edit_bones.new('LeftFoot')
    bone.head = -0.1567, -0.0860, 0.1176
    bone.tail = -0.1601, 0.0223, 0.0175
    bone.roll = 0.0000
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['LeftLeg']]
    bones['LeftFoot'] = bone.name
    bone = arm.edit_bones.new('l_calf_0_JNT')
    bone.head = -0.1463, -0.0778, 0.2341
    bone.tail = -0.1526, -0.0827, 0.1642
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['LeftLeg']]
    bones['l_calf_0_JNT'] = bone.name
    bone = arm.edit_bones.new('l_lowLeg_back_B_mscl_JNT')
    bone.head = -0.1106, -0.1081, 0.3758
    bone.tail = -0.1120, -0.0901, 0.4438
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['LeftLeg']]
    bones['l_lowLeg_back_B_mscl_JNT'] = bone.name
    bone = arm.edit_bones.new('l_lowLeg_back_A_mscl_JNT')
    bone.head = -0.1630, -0.1173, 0.3795
    bone.tail = -0.1476, -0.0968, 0.4450
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['LeftLeg']]
    bones['l_lowLeg_back_A_mscl_JNT'] = bone.name
    bone = arm.edit_bones.new('l_knee_mscl_JNT')
    bone.head = -0.1139, 0.0171, 0.5800
    bone.tail = -0.1201, 0.0136, 0.5100
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['LeftLeg']]
    bones['l_knee_mscl_JNT'] = bone.name
    bone = arm.edit_bones.new('l_leg_back_B_mscl_JNT')
    bone.head = -0.0838, -0.0522, 0.7107
    bone.tail = -0.0632, -0.0645, 0.7058
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['l_thigh_1_JNT']]
    bones['l_leg_back_B_mscl_JNT'] = bone.name
    bone = arm.edit_bones.new('l_leg_back_A_mscl_JNT')
    bone.head = -0.1393, -0.0630, 0.7064
    bone.tail = -0.1602, -0.0747, 0.7013
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['l_thigh_1_JNT']]
    bones['l_leg_back_A_mscl_JNT'] = bone.name
    bone = arm.edit_bones.new('RightFoot')
    bone.head = 0.1567, -0.0860, 0.1176
    bone.tail = 0.1601, 0.0223, 0.0175
    bone.roll = 0.0000
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['RightLeg']]
    bones['RightFoot'] = bone.name
    bone = arm.edit_bones.new('r_calf_0_JNT')
    bone.head = 0.1463, -0.0778, 0.2341
    bone.tail = 0.1526, -0.0827, 0.1642
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['RightLeg']]
    bones['r_calf_0_JNT'] = bone.name
    bone = arm.edit_bones.new('r_lowLeg_back_A_mscl_JNT')
    bone.head = 0.1630, -0.1173, 0.3795
    bone.tail = 0.1784, -0.1379, 0.3140
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['RightLeg']]
    bones['r_lowLeg_back_A_mscl_JNT'] = bone.name
    bone = arm.edit_bones.new('r_lowLeg_back_B_mscl_JNT')
    bone.head = 0.1106, -0.1081, 0.3758
    bone.tail = 0.1092, -0.1261, 0.3078
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['RightLeg']]
    bones['r_lowLeg_back_B_mscl_JNT'] = bone.name
    bone = arm.edit_bones.new('r_knee_mscl_JNT')
    bone.head = 0.1139, 0.0171, 0.5800
    bone.tail = 0.1201, 0.0136, 0.5100
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['RightLeg']]
    bones['r_knee_mscl_JNT'] = bone.name
    bone = arm.edit_bones.new('r_leg_back_B_mscl_JNT')
    bone.head = 0.0838, -0.0522, 0.7107
    bone.tail = 0.1045, -0.0400, 0.7157
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['r_thigh_1_JNT']]
    bones['r_leg_back_B_mscl_JNT'] = bone.name
    bone = arm.edit_bones.new('r_leg_back_A_mscl_JNT')
    bone.head = 0.1393, -0.0630, 0.7064
    bone.tail = 0.1183, -0.0513, 0.7114
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['r_thigh_1_JNT']]
    bones['r_leg_back_A_mscl_JNT'] = bone.name
    bone = arm.edit_bones.new('Spine3')
    bone.head = -0.0000, -0.0724, 1.3636
    bone.tail = -0.0000, -0.0765, 1.5087
    bone.roll = 0.0000
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['Spine2']]
    bones['Spine3'] = bone.name
    bone = arm.edit_bones.new('LeftHeel')
    bone.head = -0.1536, -0.1362, 0.0831
    bone.tail = -0.1601, 0.0223, 0.0175
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['LeftFoot']]
    bones['LeftHeel'] = bone.name
    bone = arm.edit_bones.new('LeftToeBase')
    bone.head = -0.1601, 0.0223, 0.0175
    bone.tail = -0.1682, 0.1929, 0.0010
    bone.roll = 0.0000
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['LeftFoot']]
    bones['LeftToeBase'] = bone.name
    bone = arm.edit_bones.new('heel_l')
    bone.head = -0.1262, -0.0860, 0.0588
    bone.tail = -0.1873, -0.0860, 0.0588
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['LeftFoot']]
    bones['heel_l'] = bone.name
    bone = arm.edit_bones.new('RightHeel')
    bone.head = 0.1536, -0.1362, 0.0831
    bone.tail = 0.1601, 0.0223, 0.0175
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['RightFoot']]
    bones['RightHeel'] = bone.name
    bone = arm.edit_bones.new('RightToeBase')
    bone.head = 0.1601, 0.0223, 0.0175
    bone.tail = 0.1682, 0.1929, 0.0010
    bone.roll = 0.0000
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['RightFoot']]
    bones['RightToeBase'] = bone.name
    bone = arm.edit_bones.new('heel_r')
    bone.head = 0.1262, -0.0860, 0.0588
    bone.tail = 0.1873, -0.0860, 0.0588
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['RightFoot']]
    bones['heel_r'] = bone.name
    bone = arm.edit_bones.new('LeftShoulder')
    bone.head = -0.0178, -0.0085, 1.4922
    bone.tail = -0.1422, -0.0620, 1.4769
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['Spine3']]
    bones['LeftShoulder'] = bone.name
    bone = arm.edit_bones.new('RightShoulder')
    bone.head = 0.0180, -0.0086, 1.4923
    bone.tail = 0.1422, -0.0620, 1.4769
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['Spine3']]
    bones['RightShoulder'] = bone.name
    bone = arm.edit_bones.new('Neck')
    bone.head = -0.0000, -0.0765, 1.5087
    bone.tail = -0.0000, -0.0403, 1.6397
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['Spine3']]
    bones['Neck'] = bone.name
    bone = arm.edit_bones.new('r_latissimusDorsi_mscl_JNT')
    bone.head = 0.1266, -0.1066, 1.4094
    bone.tail = 0.1266, -0.1087, 1.4868
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['Spine3']]
    bones['r_latissimusDorsi_mscl_JNT'] = bone.name
    bone = arm.edit_bones.new('l_latissimusDorsi_mscl_JNT')
    bone.head = -0.1266, -0.1066, 1.4094
    bone.tail = -0.1266, -0.1087, 1.4868
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['Spine3']]
    bones['l_latissimusDorsi_mscl_JNT'] = bone.name
    bone = arm.edit_bones.new('l_trapezius_top_mscl_JNT')
    bone.head = -0.0496, -0.0615, 1.5428
    bone.tail = -0.1170, -0.0711, 1.5058
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['Spine3']]
    bones['l_trapezius_top_mscl_JNT'] = bone.name
    bone = arm.edit_bones.new('r_trapezius_top_mscl_JNT')
    bone.head = 0.0500, -0.0614, 1.5424
    bone.tail = 0.1173, -0.0708, 1.5052
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['Spine3']]
    bones['r_trapezius_top_mscl_JNT'] = bone.name
    bone = arm.edit_bones.new('l_chest_front_A_bot_out_JNT')
    bone.head = -0.0704, -0.0288, 1.4916
    bone.tail = -0.1412, -0.0565, 1.5062
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['Spine3']]
    bones['l_chest_front_A_bot_out_JNT'] = bone.name
    bone = arm.edit_bones.new('l_chest_front_B_top_out_JNT')
    bone.head = -0.0241, 0.0189, 1.4449
    bone.tail = -0.0894, -0.0136, 1.4708
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['Spine3']]
    bones['l_chest_front_B_top_out_JNT'] = bone.name
    bone = arm.edit_bones.new('l_chest_front_B_bot_out_JNT')
    bone.head = -0.1081, -0.0181, 1.4694
    bone.tail = -0.1812, -0.0426, 1.4769
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['Spine3']]
    bones['l_chest_front_B_bot_out_JNT'] = bone.name
    bone = arm.edit_bones.new('l_chest_front_C_top_out_JNT')
    bone.head = -0.0467, 0.0439, 1.3695
    bone.tail = -0.1084, 0.0441, 1.3227
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['Spine3']]
    bones['l_chest_front_C_top_out_JNT'] = bone.name
    bone = arm.edit_bones.new('l_chest_front_C_bot_out_JNT')
    bone.head = -0.1241, 0.0046, 1.4080
    bone.tail = -0.1760, -0.0301, 1.4539
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['Spine3']]
    bones['l_chest_front_C_bot_out_JNT'] = bone.name
    bone = arm.edit_bones.new('l_scapula_A_top_out_JNT')
    bone.head = -0.0565, -0.1200, 1.3868
    bone.tail = -0.1287, -0.1138, 1.4143
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['Spine3']]
    bones['l_scapula_A_top_out_JNT'] = bone.name
    bone = arm.edit_bones.new('l_scapula_A_bot_out_JNT')
    bone.head = -0.1405, -0.1110, 1.4297
    bone.tail = -0.2043, -0.1026, 1.4728
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['Spine3']]
    bones['l_scapula_A_bot_out_JNT'] = bone.name
    bone = arm.edit_bones.new('r_chest_front_A_bot_out_JNT')
    bone.head = 0.0708, -0.0288, 1.4916
    bone.tail = 0.1414, -0.0569, 1.5064
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['Spine3']]
    bones['r_chest_front_A_bot_out_JNT'] = bone.name
    bone = arm.edit_bones.new('r_chest_front_B_top_out_JNT')
    bone.head = 0.0245, 0.0189, 1.4449
    bone.tail = 0.0898, -0.0137, 1.4709
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['Spine3']]
    bones['r_chest_front_B_top_out_JNT'] = bone.name
    bone = arm.edit_bones.new('r_chest_front_B_bot_out_JNT')
    bone.head = 0.1081, -0.0181, 1.4695
    bone.tail = 0.1812, -0.0427, 1.4769
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['Spine3']]
    bones['r_chest_front_B_bot_out_JNT'] = bone.name
    bone = arm.edit_bones.new('r_chest_front_C_top_out_JNT')
    bone.head = 0.0519, 0.0439, 1.3695
    bone.tail = 0.1137, 0.0441, 1.3229
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['Spine3']]
    bones['r_chest_front_C_top_out_JNT'] = bone.name
    bone = arm.edit_bones.new('r_chest_front_C_bot_out_JNT')
    bone.head = 0.1247, 0.0046, 1.4080
    bone.tail = 0.1751, -0.0309, 1.4549
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['Spine3']]
    bones['r_chest_front_C_bot_out_JNT'] = bone.name
    bone = arm.edit_bones.new('r_scapula_A_top_out_JNT')
    bone.head = 0.0565, -0.1200, 1.3868
    bone.tail = 0.1287, -0.1138, 1.4143
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['Spine3']]
    bones['r_scapula_A_top_out_JNT'] = bone.name
    bone = arm.edit_bones.new('r_scapula_A_bot_out_JNT')
    bone.head = 0.1405, -0.1110, 1.4297
    bone.tail = 0.2043, -0.1026, 1.4728
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['Spine3']]
    bones['r_scapula_A_bot_out_JNT'] = bone.name
    bone = arm.edit_bones.new('l_sternocleidomastoid_bot_mscl_Offset_GRP')
    bone.head = -0.0069, -0.0154, 1.4790
    bone.tail = -0.0069, -0.0176, 1.5564
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['Spine3']]
    bones['l_sternocleidomastoid_bot_mscl_Offset_GRP'] = bone.name
    bone = arm.edit_bones.new('r_sternocleidomastoid_bot_mscl_Offset_GRP')
    bone.head = 0.0069, -0.0154, 1.4790
    bone.tail = 0.0069, -0.0176, 1.5564
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['Spine3']]
    bones['r_sternocleidomastoid_bot_mscl_Offset_GRP'] = bone.name
    bone = arm.edit_bones.new('headLookAt_GRP')
    bone.head = -0.0000, -0.0403, 1.6397
    bone.tail = -0.0000, -0.0403, 1.7172
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['Spine3']]
    bones['headLookAt_GRP'] = bone.name
    bone = arm.edit_bones.new('neck_lookAt_setup_Offset_GRP')
    bone.head = -0.0000, -0.0765, 1.5087
    bone.tail = -0.0000, -0.0784, 1.5861
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['Spine3']]
    bones['neck_lookAt_setup_Offset_GRP'] = bone.name
    bone = arm.edit_bones.new('neck1_lookAt_setup_Offset_GRP')
    bone.head = -0.0000, -0.0548, 1.5682
    bone.tail = -0.0000, -0.0557, 1.6456
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['Spine3']]
    bones['neck1_lookAt_setup_Offset_GRP'] = bone.name
    bone = arm.edit_bones.new('LeftArm')
    bone.head = -0.1422, -0.0620, 1.4769
    bone.tail = -0.3298, -0.0193, 1.2856
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['LeftShoulder']]
    bones['LeftArm'] = bone.name
    bone = arm.edit_bones.new('l_butterfly_top_CRV_bot_out_JNT')
    bone.head = -0.1017, -0.0638, 1.5241
    bone.tail = -0.1979, -0.1052, 1.5122
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['LeftShoulder']]
    bones['l_butterfly_top_CRV_bot_out_JNT'] = bone.name
    bone = arm.edit_bones.new('RightArm')
    bone.head = 0.1422, -0.0620, 1.4769
    bone.tail = 0.3298, -0.0193, 1.2856
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['RightShoulder']]
    bones['RightArm'] = bone.name
    bone = arm.edit_bones.new('r_butterfly_top_CRV_top_out_JNT')
    bone.head = 0.1018, -0.0639, 1.5242
    bone.tail = 0.1979, -0.1052, 1.5122
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['RightShoulder']]
    bones['r_butterfly_top_CRV_top_out_JNT'] = bone.name
    bone = arm.edit_bones.new('Head')
    bone.head = -0.0000, -0.0403, 1.6397
    bone.tail = -0.0000, -0.0403, 1.6497
    bone.roll = 0.0000
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['Neck']]
    bones['Head'] = bone.name
    bone = arm.edit_bones.new('neck_lookAt_setup_GRP')
    bone.head = -0.0000, -0.0765, 1.5087
    bone.tail = -0.0000, -0.0499, 1.5814
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['neck_lookAt_setup_Offset_GRP']]
    bones['neck_lookAt_setup_GRP'] = bone.name
    bone = arm.edit_bones.new('neck1_lookAt_setup_GRP')
    bone.head = -0.0000, -0.0548, 1.5682
    bone.tail = -0.0000, -0.0395, 1.6441
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['neck1_lookAt_setup_Offset_GRP']]
    bones['neck1_lookAt_setup_GRP'] = bone.name
    bone = arm.edit_bones.new('LeftForeArm')
    bone.head = -0.3298, -0.0193, 1.2856
    bone.tail = -0.4303, 0.1653, 1.1427
    bone.roll = 0.0000
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['LeftArm']]
    bones['LeftForeArm'] = bone.name
    bone = arm.edit_bones.new('l_SHL_0_JNT')
    bone.head = -0.2048, -0.0490, 1.4131
    bone.tail = -0.1701, -0.0562, 1.4485
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['LeftArm']]
    bones['l_SHL_0_JNT'] = bone.name
    bone = arm.edit_bones.new('l_SHL_1_JNT')
    bone.head = -0.2673, -0.0360, 1.3494
    bone.tail = -0.2603, -0.0374, 1.3565
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['LeftArm']]
    bones['l_SHL_1_JNT'] = bone.name
    bone = arm.edit_bones.new('RightForeArm')
    bone.head = 0.3298, -0.0193, 1.2856
    bone.tail = 0.4303, 0.1653, 1.1427
    bone.roll = 0.0000
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['RightArm']]
    bones['RightForeArm'] = bone.name
    bone = arm.edit_bones.new('r_SHL_0_JNT')
    bone.head = 0.2048, -0.0490, 1.4131
    bone.tail = 0.1701, -0.0562, 1.4485
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['RightArm']]
    bones['r_SHL_0_JNT'] = bone.name
    bone = arm.edit_bones.new('r_SHL_1_JNT')
    bone.head = 0.2673, -0.0360, 1.3494
    bone.tail = 0.2603, -0.0374, 1.3565
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['RightArm']]
    bones['r_SHL_1_JNT'] = bone.name
    bone = arm.edit_bones.new('LeftHand')
    bone.head = -0.4303, 0.1653, 1.1427
    bone.tail = -0.4565, 0.2192, 1.0910
    bone.roll = 0.0000
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['LeftForeArm']]
    bones['LeftHand'] = bone.name
    bone = arm.edit_bones.new('l_Wrist_0_JNT')
    bone.head = -0.3633, 0.0397, 1.2381
    bone.tail = -0.3753, 0.0623, 1.2209
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['LeftForeArm']]
    bones['l_Wrist_0_JNT'] = bone.name
    bone = arm.edit_bones.new('l_Wrist_1_JNT')
    bone.head = -0.3968, 0.1025, 1.1904
    bone.tail = -0.4088, 0.1251, 1.1732
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['LeftForeArm']]
    bones['l_Wrist_1_JNT'] = bone.name
    bone = arm.edit_bones.new('l_Wrist_2_JNT')
    bone.head = -0.4283, 0.1615, 1.1456
    bone.tail = -0.4422, 0.1650, 1.1600
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['LeftForeArm']]
    bones['l_Wrist_2_JNT'] = bone.name
    bone = arm.edit_bones.new('l_elbow_bend_A_mscl_JNT')
    bone.head = -0.3229, 0.0052, 1.3008
    bone.tail = -0.3402, 0.0204, 1.2804
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['LeftForeArm']]
    bones['l_elbow_bend_A_mscl_JNT'] = bone.name
    bone = arm.edit_bones.new('l_elbow_bend_B_mscl_JNT')
    bone.head = -0.3081, 0.0015, 1.2855
    bone.tail = -0.3254, 0.0167, 1.2651
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['LeftForeArm']]
    bones['l_elbow_bend_B_mscl_JNT'] = bone.name
    bone = arm.edit_bones.new('l_elbow_back_mscl_JNT')
    bone.head = -0.3442, -0.0492, 1.2781
    bone.tail = -0.3614, -0.0339, 1.2577
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['LeftForeArm']]
    bones['l_elbow_back_mscl_JNT'] = bone.name
    bone = arm.edit_bones.new('l_deltoid_top_top_out_JNT')
    bone.head = -0.1361, -0.0591, 1.5073
    bone.tail = -0.0962, -0.0639, 1.5371
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['l_SHL_0_JNT']]
    bones['l_deltoid_top_top_out_JNT'] = bone.name
    bone = arm.edit_bones.new('l_deltoid_top_bot_out_JNT')
    bone.head = -0.1823, -0.0536, 1.4709
    bone.tail = -0.1517, -0.0580, 1.5102
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['l_SHL_0_JNT']]
    bones['l_deltoid_top_bot_out_JNT'] = bone.name
    bone = arm.edit_bones.new('l_deltoid_front_top_out_JNT')
    bone.head = -0.1279, -0.0362, 1.4860
    bone.tail = -0.0963, -0.0527, 1.5211
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['l_SHL_0_JNT']]
    bones['l_deltoid_front_top_out_JNT'] = bone.name
    bone = arm.edit_bones.new('l_deltoid_front_bot_out_JNT')
    bone.head = -0.1732, -0.0182, 1.4368
    bone.tail = -0.1401, -0.0299, 1.4724
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['l_SHL_0_JNT']]
    bones['l_deltoid_front_bot_out_JNT'] = bone.name
    bone = arm.edit_bones.new('l_deltoid_back_top_out_JNT')
    bone.head = -0.1355, -0.1058, 1.4942
    bone.tail = -0.1001, -0.1082, 1.5295
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['l_SHL_0_JNT']]
    bones['l_deltoid_back_top_out_JNT'] = bone.name
    bone = arm.edit_bones.new('l_deltoid_back_bot_out_JNT')
    bone.head = -0.1679, -0.1052, 1.4620
    bone.tail = -0.1327, -0.1101, 1.4971
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['l_SHL_0_JNT']]
    bones['l_deltoid_back_bot_out_JNT'] = bone.name
    bone = arm.edit_bones.new('l_triceps_mscl_JNT')
    bone.head = -0.2666, -0.0455, 1.3523
    bone.tail = -0.2732, -0.0428, 1.3453
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['l_SHL_1_JNT']]
    bones['l_triceps_mscl_JNT'] = bone.name
    bone = arm.edit_bones.new('l_biceps_A_mscl_JNT')
    bone.head = -0.2627, -0.0236, 1.3509
    bone.tail = -0.2555, -0.0237, 1.3579
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['l_SHL_1_JNT']]
    bones['l_biceps_A_mscl_JNT'] = bone.name
    bone = arm.edit_bones.new('RightHand')
    bone.head = 0.4303, 0.1653, 1.1427
    bone.tail = 0.4565, 0.2192, 1.0910
    bone.roll = 0.0000
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['RightForeArm']]
    bones['RightHand'] = bone.name
    bone = arm.edit_bones.new('r_Wrist_0_JNT')
    bone.head = 0.3633, 0.0397, 1.2381
    bone.tail = 0.3753, 0.0623, 1.2209
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['RightForeArm']]
    bones['r_Wrist_0_JNT'] = bone.name
    bone = arm.edit_bones.new('r_Wrist_1_JNT')
    bone.head = 0.3968, 0.1025, 1.1904
    bone.tail = 0.4088, 0.1251, 1.1732
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['RightForeArm']]
    bones['r_Wrist_1_JNT'] = bone.name
    bone = arm.edit_bones.new('r_Wrist_2_JNT')
    bone.head = 0.4283, 0.1615, 1.1456
    bone.tail = 0.4422, 0.1650, 1.1600
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['RightForeArm']]
    bones['r_Wrist_2_JNT'] = bone.name
    bone = arm.edit_bones.new('r_elbow_bend_A_mscl_JNT')
    bone.head = 0.3229, 0.0052, 1.3008
    bone.tail = 0.3402, 0.0204, 1.2804
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['RightForeArm']]
    bones['r_elbow_bend_A_mscl_JNT'] = bone.name
    bone = arm.edit_bones.new('r_elbow_bend_B_mscl_JNT')
    bone.head = 0.3081, 0.0015, 1.2855
    bone.tail = 0.3254, 0.0167, 1.2651
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['RightForeArm']]
    bones['r_elbow_bend_B_mscl_JNT'] = bone.name
    bone = arm.edit_bones.new('r_elbow_back_mscl_JNT')
    bone.head = 0.3442, -0.0491, 1.2781
    bone.tail = 0.3614, -0.0339, 1.2577
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['RightForeArm']]
    bones['r_elbow_back_mscl_JNT'] = bone.name
    bone = arm.edit_bones.new('r_deltoid_top_top_out_JNT')
    bone.head = 0.1362, -0.0592, 1.5074
    bone.tail = 0.1761, -0.0544, 1.4776
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['r_SHL_0_JNT']]
    bones['r_deltoid_top_top_out_JNT'] = bone.name
    bone = arm.edit_bones.new('r_deltoid_top_bot_out_JNT')
    bone.head = 0.1823, -0.0536, 1.4709
    bone.tail = 0.2128, -0.0492, 1.4315
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['r_SHL_0_JNT']]
    bones['r_deltoid_top_bot_out_JNT'] = bone.name
    bone = arm.edit_bones.new('r_deltoid_front_top_out_JNT')
    bone.head = 0.1279, -0.0362, 1.4860
    bone.tail = 0.1594, -0.0196, 1.4509
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['r_SHL_0_JNT']]
    bones['r_deltoid_front_top_out_JNT'] = bone.name
    bone = arm.edit_bones.new('r_deltoid_front_bot_out_JNT')
    bone.head = 0.1732, -0.0182, 1.4368
    bone.tail = 0.2063, -0.0065, 1.4012
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['r_SHL_0_JNT']]
    bones['r_deltoid_front_bot_out_JNT'] = bone.name
    bone = arm.edit_bones.new('r_deltoid_back_top_out_JNT')
    bone.head = 0.1355, -0.1058, 1.4942
    bone.tail = 0.1709, -0.1034, 1.4589
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['r_SHL_0_JNT']]
    bones['r_deltoid_back_top_out_JNT'] = bone.name
    bone = arm.edit_bones.new('r_deltoid_back_bot_out_JNT')
    bone.head = 0.1679, -0.1052, 1.4620
    bone.tail = 0.2031, -0.1003, 1.4268
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['r_SHL_0_JNT']]
    bones['r_deltoid_back_bot_out_JNT'] = bone.name
    bone = arm.edit_bones.new('r_triceps_mscl_JNT')
    bone.head = 0.2666, -0.0455, 1.3523
    bone.tail = 0.2600, -0.0483, 1.3594
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['r_SHL_1_JNT']]
    bones['r_triceps_mscl_JNT'] = bone.name
    bone = arm.edit_bones.new('r_biceps_A_mscl_JNT')
    bone.head = 0.2627, -0.0236, 1.3509
    bone.tail = 0.2699, -0.0235, 1.3439
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['r_SHL_1_JNT']]
    bones['r_biceps_A_mscl_JNT'] = bone.name
    bone = arm.edit_bones.new('LeftInHandThumb')
    bone.head = -0.4179, 0.1885, 1.1284
    bone.tail = -0.4038, 0.2245, 1.1148
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['LeftHand']]
    bones['LeftInHandThumb'] = bone.name
    bone = arm.edit_bones.new('LeftInHandIndex')
    bone.head = -0.4287, 0.1895, 1.1393
    bone.tail = -0.4521, 0.2386, 1.1036
    bone.roll = 2.2308
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['LeftHand']]
    bones['LeftInHandIndex'] = bone.name
    bone = arm.edit_bones.new('LeftInHandMiddle')
    bone.head = -0.4370, 0.1839, 1.1364
    bone.tail = -0.4668, 0.2222, 1.0973
    bone.roll = 2.3351
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['LeftHand']]
    bones['LeftInHandMiddle'] = bone.name
    bone = arm.edit_bones.new('LeftInHandRing')
    bone.head = -0.4446, 0.1754, 1.1305
    bone.tail = -0.4735, 0.2029, 1.0906
    bone.roll = 2.3723
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['LeftHand']]
    bones['LeftInHandRing'] = bone.name
    bone = arm.edit_bones.new('LeftInHandPinky')
    bone.head = -0.4432, 0.1678, 1.1252
    bone.tail = -0.4781, 0.1844, 1.0819
    bone.roll = 2.5010
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['LeftHand']]
    bones['LeftInHandPinky'] = bone.name
    bone = arm.edit_bones.new('WeaponLeft')
    bone.head = -0.4277, 0.2520, 1.0947
    bone.tail = -0.4119, 0.2481, 1.0817
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['LeftHand']]
    bones['WeaponLeft'] = bone.name
    bone = arm.edit_bones.new('l_wrist_A_mscl_JNT')
    bone.head = -0.4351, 0.1825, 1.1647
    bone.tail = -0.4433, 0.1962, 1.1521
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['l_Wrist_2_JNT']]
    bones['l_wrist_A_mscl_JNT'] = bone.name
    bone = arm.edit_bones.new('l_wrist_B_mscl_JNT')
    bone.head = -0.4557, 0.1535, 1.1463
    bone.tail = -0.4639, 0.1672, 1.1338
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['l_Wrist_2_JNT']]
    bones['l_wrist_B_mscl_JNT'] = bone.name
    bone = arm.edit_bones.new('l_wrist_C_mscl_JNT')
    bone.head = -0.4163, 0.1613, 1.1291
    bone.tail = -0.4318, 0.1541, 1.1180
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['l_Wrist_2_JNT']]
    bones['l_wrist_C_mscl_JNT'] = bone.name
    bone = arm.edit_bones.new('RightInHandThumb')
    bone.head = 0.4179, 0.1885, 1.1284
    bone.tail = 0.4038, 0.2245, 1.1148
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['RightHand']]
    bones['RightInHandThumb'] = bone.name
    bone = arm.edit_bones.new('RightInHandIndex')
    bone.head = 0.4287, 0.1895, 1.1393
    bone.tail = 0.4521, 0.2386, 1.1036
    bone.roll = -2.2308
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['RightHand']]
    bones['RightInHandIndex'] = bone.name
    bone = arm.edit_bones.new('RightInHandMiddle')
    bone.head = 0.4370, 0.1839, 1.1364
    bone.tail = 0.4668, 0.2222, 1.0973
    bone.roll = -2.3351
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['RightHand']]
    bones['RightInHandMiddle'] = bone.name
    bone = arm.edit_bones.new('RightInHandRing')
    bone.head = 0.4446, 0.1754, 1.1305
    bone.tail = 0.4735, 0.2029, 1.0906
    bone.roll = -2.3723
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['RightHand']]
    bones['RightInHandRing'] = bone.name
    bone = arm.edit_bones.new('RightInHandPinky')
    bone.head = 0.4432, 0.1679, 1.1252
    bone.tail = 0.4781, 0.1844, 1.0819
    bone.roll = -2.5011
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['RightHand']]
    bones['RightInHandPinky'] = bone.name
    bone = arm.edit_bones.new('WeaponRight')
    bone.head = 0.4277, 0.2520, 1.0947
    bone.tail = 0.4119, 0.2481, 1.0817
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['RightHand']]
    bones['WeaponRight'] = bone.name
    bone = arm.edit_bones.new('r_wrist_A_mscl_JNT')
    bone.head = 0.4351, 0.1825, 1.1647
    bone.tail = 0.4433, 0.1962, 1.1521
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['r_Wrist_2_JNT']]
    bones['r_wrist_A_mscl_JNT'] = bone.name
    bone = arm.edit_bones.new('r_wrist_B_mscl_JNT')
    bone.head = 0.4557, 0.1535, 1.1463
    bone.tail = 0.4639, 0.1672, 1.1338
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['r_Wrist_2_JNT']]
    bones['r_wrist_B_mscl_JNT'] = bone.name
    bone = arm.edit_bones.new('r_wrist_C_mscl_JNT')
    bone.head = 0.4163, 0.1613, 1.1291
    bone.tail = 0.4008, 0.1685, 1.1402
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['r_Wrist_2_JNT']]
    bones['r_wrist_C_mscl_JNT'] = bone.name
    bone = arm.edit_bones.new('LeftHandThumb1')
    bone.head = -0.4038, 0.2245, 1.1148
    bone.tail = -0.4005, 0.2461, 1.0872
    bone.roll = 0.0000
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['LeftInHandThumb']]
    bones['LeftHandThumb1'] = bone.name
    bone = arm.edit_bones.new('l_thumb_side_mscl_JNT')
    bone.head = -0.4102, 0.2044, 1.1355
    bone.tail = -0.4038, 0.2199, 1.1266
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['LeftInHandThumb']]
    bones['l_thumb_side_mscl_JNT'] = bone.name
    bone = arm.edit_bones.new('LeftHandIndex1')
    bone.head = -0.4521, 0.2386, 1.1036
    bone.tail = -0.4570, 0.2646, 1.0734
    bone.roll = 2.1426
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['LeftInHandIndex']]
    bones['LeftHandIndex1'] = bone.name
    bone = arm.edit_bones.new('l_thumb_thumb_A_bot_mscl_JNT')
    bone.head = -0.4461, 0.2362, 1.1043
    bone.tail = -0.4291, 0.2819, 1.0676
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['LeftInHandIndex']]
    bones['l_thumb_thumb_A_bot_mscl_JNT'] = bone.name
    bone = arm.edit_bones.new('l_thumb_thumb_A_top_mscl_JNT')
    bone.head = -0.4460, 0.2375, 1.1058
    bone.tail = -0.4291, 0.2832, 1.0692
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['LeftInHandIndex']]
    bones['l_thumb_thumb_A_top_mscl_JNT'] = bone.name
    bone = arm.edit_bones.new('LeftHandMiddle1')
    bone.head = -0.4668, 0.2222, 1.0973
    bone.tail = -0.4771, 0.2480, 1.0613
    bone.roll = 2.1806
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['LeftInHandMiddle']]
    bones['LeftHandMiddle1'] = bone.name
    bone = arm.edit_bones.new('LeftHandRing1')
    bone.head = -0.4735, 0.2029, 1.0906
    bone.tail = -0.4824, 0.2211, 1.0564
    bone.roll = 2.1580
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['LeftInHandRing']]
    bones['LeftHandRing1'] = bone.name
    bone = arm.edit_bones.new('LeftHandPinky1')
    bone.head = -0.4781, 0.1844, 1.0819
    bone.tail = -0.4846, 0.1940, 1.0559
    bone.roll = 2.1377
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['LeftInHandPinky']]
    bones['LeftHandPinky1'] = bone.name
    bone = arm.edit_bones.new('l_pinkyBase_A_bot_mscl_JNT')
    bone.head = -0.4365, 0.1616, 1.1192
    bone.tail = -0.4414, 0.1651, 1.1100
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['LeftInHandPinky']]
    bones['l_pinkyBase_A_bot_mscl_JNT'] = bone.name
    bone = arm.edit_bones.new('RightHandThumb1')
    bone.head = 0.4038, 0.2245, 1.1148
    bone.tail = 0.4005, 0.2461, 1.0872
    bone.roll = 0.0000
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['RightInHandThumb']]
    bones['RightHandThumb1'] = bone.name
    bone = arm.edit_bones.new('r_thumb_side_mscl_JNT')
    bone.head = 0.4102, 0.2044, 1.1355
    bone.tail = 0.4167, 0.1889, 1.1445
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['RightInHandThumb']]
    bones['r_thumb_side_mscl_JNT'] = bone.name
    bone = arm.edit_bones.new('RightHandIndex1')
    bone.head = 0.4521, 0.2386, 1.1036
    bone.tail = 0.4570, 0.2646, 1.0734
    bone.roll = -2.1427
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['RightInHandIndex']]
    bones['RightHandIndex1'] = bone.name
    bone = arm.edit_bones.new('r_thumb_thumb_A_bot_mscl_JNT')
    bone.head = 0.4461, 0.2362, 1.1043
    bone.tail = 0.4630, 0.1905, 1.1409
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['RightInHandIndex']]
    bones['r_thumb_thumb_A_bot_mscl_JNT'] = bone.name
    bone = arm.edit_bones.new('r_thumb_thumb_A_top_mscl_JNT')
    bone.head = 0.4460, 0.2375, 1.1058
    bone.tail = 0.4630, 0.1918, 1.1425
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['RightInHandIndex']]
    bones['r_thumb_thumb_A_top_mscl_JNT'] = bone.name
    bone = arm.edit_bones.new('RightHandMiddle1')
    bone.head = 0.4668, 0.2222, 1.0973
    bone.tail = 0.4771, 0.2480, 1.0613
    bone.roll = -2.1806
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['RightInHandMiddle']]
    bones['RightHandMiddle1'] = bone.name
    bone = arm.edit_bones.new('RightHandRing1')
    bone.head = 0.4735, 0.2029, 1.0906
    bone.tail = 0.4824, 0.2211, 1.0564
    bone.roll = -2.1580
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['RightInHandRing']]
    bones['RightHandRing1'] = bone.name
    bone = arm.edit_bones.new('RightHandPinky1')
    bone.head = 0.4781, 0.1844, 1.0819
    bone.tail = 0.4846, 0.1940, 1.0559
    bone.roll = -2.1377
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['RightInHandPinky']]
    bones['RightHandPinky1'] = bone.name
    bone = arm.edit_bones.new('r_pinkyBase_A_bot_mscl_JNT')
    bone.head = 0.4365, 0.1616, 1.1192
    bone.tail = 0.4414, 0.1651, 1.1100
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['RightInHandPinky']]
    bones['r_pinkyBase_A_bot_mscl_JNT'] = bone.name
    bone = arm.edit_bones.new('LeftHandThumb2')
    bone.head = -0.4005, 0.2461, 1.0872
    bone.tail = -0.4045, 0.2564, 1.0538
    bone.roll = 0.0000
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['LeftHandThumb1']]
    bones['LeftHandThumb2'] = bone.name
    bone = arm.edit_bones.new('LeftHandIndex2')
    bone.head = -0.4570, 0.2646, 1.0734
    bone.tail = -0.4491, 0.2707, 1.0523
    bone.roll = 1.8774
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['LeftHandIndex1']]
    bones['LeftHandIndex2'] = bone.name
    bone = arm.edit_bones.new('l_ind_knuckle_top_mscl_JNT')
    bone.head = -0.4628, 0.2429, 1.1138
    bone.tail = -0.4551, 0.2309, 1.1195
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['LeftHandIndex1']]
    bones['l_ind_knuckle_top_mscl_JNT'] = bone.name
    bone = arm.edit_bones.new('l_ind_knuckle_bot_mscl_JNT')
    bone.head = -0.4411, 0.2336, 1.0942
    bone.tail = -0.4449, 0.2445, 1.0840
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['LeftHandIndex1']]
    bones['l_ind_knuckle_bot_mscl_JNT'] = bone.name
    bone = arm.edit_bones.new('LeftHandMiddle2')
    bone.head = -0.4771, 0.2480, 1.0613
    bone.tail = -0.4651, 0.2548, 1.0368
    bone.roll = 1.7648
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['LeftHandMiddle1']]
    bones['LeftHandMiddle2'] = bone.name
    bone = arm.edit_bones.new('l_mid_knuckle_top_mscl_JNT')
    bone.head = -0.4796, 0.2242, 1.1067
    bone.tail = -0.4692, 0.2144, 1.1139
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['LeftHandMiddle1']]
    bones['l_mid_knuckle_top_mscl_JNT'] = bone.name
    bone = arm.edit_bones.new('l_mid_knuckle_bot_mscl_JNT')
    bone.head = -0.4536, 0.2197, 1.0887
    bone.tail = -0.4593, 0.2292, 1.0772
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['LeftHandMiddle1']]
    bones['l_mid_knuckle_bot_mscl_JNT'] = bone.name
    bone = arm.edit_bones.new('LeftHandRing2')
    bone.head = -0.4824, 0.2211, 1.0564
    bone.tail = -0.4726, 0.2281, 1.0328
    bone.roll = 1.7541
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['LeftHandRing1']]
    bones['LeftHandRing2'] = bone.name
    bone = arm.edit_bones.new('l_ring_knuckle_top_mscl_JNT')
    bone.head = -0.4864, 0.2039, 1.0985
    bone.tail = -0.4758, 0.1967, 1.1066
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['LeftHandRing1']]
    bones['l_ring_knuckle_top_mscl_JNT'] = bone.name
    bone = arm.edit_bones.new('l_ring_knuckle_bot_mscl_JNT')
    bone.head = -0.4602, 0.2015, 1.0835
    bone.tail = -0.4658, 0.2087, 1.0714
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['LeftHandRing1']]
    bones['l_ring_knuckle_bot_mscl_JNT'] = bone.name
    bone = arm.edit_bones.new('LeftHandPinky2')
    bone.head = -0.4846, 0.1940, 1.0559
    bone.tail = -0.4787, 0.1998, 1.0396
    bone.roll = 1.7474
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['LeftHandPinky1']]
    bones['LeftHandPinky2'] = bone.name
    bone = arm.edit_bones.new('l_pinky_knuckle_top_mscl_JNT')
    bone.head = -0.4908, 0.1821, 1.0888
    bone.tail = -0.4795, 0.1787, 1.0975
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['LeftHandPinky1']]
    bones['l_pinky_knuckle_top_mscl_JNT'] = bone.name
    bone = arm.edit_bones.new('l_pinky_knuckle_bot_mscl_JNT')
    bone.head = -0.4648, 0.1862, 1.0760
    bone.tail = -0.4710, 0.1909, 1.0636
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['LeftHandPinky1']]
    bones['l_pinky_knuckle_bot_mscl_JNT'] = bone.name
    bone = arm.edit_bones.new('RightHandThumb2')
    bone.head = 0.4005, 0.2461, 1.0872
    bone.tail = 0.4045, 0.2564, 1.0538
    bone.roll = 0.0000
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['RightHandThumb1']]
    bones['RightHandThumb2'] = bone.name
    bone = arm.edit_bones.new('RightHandIndex2')
    bone.head = 0.4570, 0.2646, 1.0734
    bone.tail = 0.4491, 0.2707, 1.0523
    bone.roll = -1.8774
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['RightHandIndex1']]
    bones['RightHandIndex2'] = bone.name
    bone = arm.edit_bones.new('r_ind_knuckle_top_mscl_JNT')
    bone.head = 0.4628, 0.2429, 1.1138
    bone.tail = 0.4704, 0.2549, 1.1080
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['RightHandIndex1']]
    bones['r_ind_knuckle_top_mscl_JNT'] = bone.name
    bone = arm.edit_bones.new('r_ind_knuckle_bot_mscl_JNT')
    bone.head = 0.4411, 0.2336, 1.0942
    bone.tail = 0.4449, 0.2445, 1.0840
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['RightHandIndex1']]
    bones['r_ind_knuckle_bot_mscl_JNT'] = bone.name
    bone = arm.edit_bones.new('RightHandMiddle2')
    bone.head = 0.4771, 0.2480, 1.0613
    bone.tail = 0.4651, 0.2548, 1.0368
    bone.roll = -1.7648
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['RightHandMiddle1']]
    bones['RightHandMiddle2'] = bone.name
    bone = arm.edit_bones.new('r_mid_knuckle_top_mscl_JNT')
    bone.head = 0.4796, 0.2242, 1.1067
    bone.tail = 0.4899, 0.2339, 1.0994
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['RightHandMiddle1']]
    bones['r_mid_knuckle_top_mscl_JNT'] = bone.name
    bone = arm.edit_bones.new('r_mid_knuckle_bot_mscl_JNT')
    bone.head = 0.4536, 0.2197, 1.0887
    bone.tail = 0.4593, 0.2292, 1.0772
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['RightHandMiddle1']]
    bones['r_mid_knuckle_bot_mscl_JNT'] = bone.name
    bone = arm.edit_bones.new('RightHandRing2')
    bone.head = 0.4824, 0.2211, 1.0564
    bone.tail = 0.4726, 0.2281, 1.0329
    bone.roll = -1.7541
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['RightHandRing1']]
    bones['RightHandRing2'] = bone.name
    bone = arm.edit_bones.new('r_ring_knuckle_top_mscl_JNT')
    bone.head = 0.4864, 0.2039, 1.0985
    bone.tail = 0.4969, 0.2111, 1.0904
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['RightHandRing1']]
    bones['r_ring_knuckle_top_mscl_JNT'] = bone.name
    bone = arm.edit_bones.new('r_ring_knuckle_bot_mscl_JNT')
    bone.head = 0.4602, 0.2015, 1.0835
    bone.tail = 0.4658, 0.2087, 1.0714
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['RightHandRing1']]
    bones['r_ring_knuckle_bot_mscl_JNT'] = bone.name
    bone = arm.edit_bones.new('RightHandPinky2')
    bone.head = 0.4846, 0.1940, 1.0559
    bone.tail = 0.4787, 0.1998, 1.0396
    bone.roll = -1.7474
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['RightHandPinky1']]
    bones['RightHandPinky2'] = bone.name
    bone = arm.edit_bones.new('r_pinky_knuckle_top_mscl_JNT')
    bone.head = 0.4908, 0.1821, 1.0888
    bone.tail = 0.5021, 0.1855, 1.0802
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['RightHandPinky1']]
    bones['r_pinky_knuckle_top_mscl_JNT'] = bone.name
    bone = arm.edit_bones.new('r_pinky_knuckle_bot_mscl_JNT')
    bone.head = 0.4648, 0.1862, 1.0760
    bone.tail = 0.4710, 0.1909, 1.0636
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['RightHandPinky1']]
    bones['r_pinky_knuckle_bot_mscl_JNT'] = bone.name
    bone = arm.edit_bones.new('LeftHandIndex3')
    bone.head = -0.4491, 0.2707, 1.0523
    bone.tail = -0.4437, 0.2687, 1.0470
    bone.roll = 1.3237
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['LeftHandIndex2']]
    bones['LeftHandIndex3'] = bone.name
    bone = arm.edit_bones.new('l_ind_knuckle_B_top_mscl_JNT')
    bone.head = -0.4629, 0.2695, 1.0753
    bone.tail = -0.4620, 0.2732, 1.0685
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['LeftHandIndex2']]
    bones['l_ind_knuckle_B_top_mscl_JNT'] = bone.name
    bone = arm.edit_bones.new('LeftHandMiddle3')
    bone.head = -0.4651, 0.2548, 1.0368
    bone.tail = -0.4599, 0.2542, 1.0328
    bone.roll = 1.3587
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['LeftHandMiddle2']]
    bones['LeftHandMiddle3'] = bone.name
    bone = arm.edit_bones.new('l_mid_knuckle_B_top_mscl_JNT')
    bone.head = -0.4830, 0.2509, 1.0620
    bone.tail = -0.4823, 0.2538, 1.0560
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['LeftHandMiddle2']]
    bones['l_mid_knuckle_B_top_mscl_JNT'] = bone.name
    bone = arm.edit_bones.new('LeftHandRing3')
    bone.head = -0.4726, 0.2281, 1.0328
    bone.tail = -0.4683, 0.2281, 1.0296
    bone.roll = 1.3653
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['LeftHandRing2']]
    bones['LeftHandRing3'] = bone.name
    bone = arm.edit_bones.new('l_ring_knuckle_B_top_mscl_JNT')
    bone.head = -0.4875, 0.2228, 1.0566
    bone.tail = -0.4871, 0.2248, 1.0516
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['LeftHandRing2']]
    bones['l_ring_knuckle_B_top_mscl_JNT'] = bone.name
    bone = arm.edit_bones.new('LeftHandPinky3')
    bone.head = -0.4787, 0.1998, 1.0396
    bone.tail = -0.4752, 0.2008, 1.0366
    bone.roll = 1.4961
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['LeftHandPinky2']]
    bones['LeftHandPinky3'] = bone.name
    bone = arm.edit_bones.new('l_pinky_knuckle_B_top_mscl_JNT')
    bone.head = -0.4893, 0.1941, 1.0557
    bone.tail = -0.4891, 0.1957, 1.0513
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['LeftHandPinky2']]
    bones['l_pinky_knuckle_B_top_mscl_JNT'] = bone.name
    bone = arm.edit_bones.new('RightHandIndex3')
    bone.head = 0.4491, 0.2707, 1.0523
    bone.tail = 0.4437, 0.2687, 1.0470
    bone.roll = -1.3237
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['RightHandIndex2']]
    bones['RightHandIndex3'] = bone.name
    bone = arm.edit_bones.new('r_ind_knuckle_B_top_mscl_JNT')
    bone.head = 0.4629, 0.2695, 1.0753
    bone.tail = 0.4649, 0.2751, 1.0702
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['RightHandIndex2']]
    bones['r_ind_knuckle_B_top_mscl_JNT'] = bone.name
    bone = arm.edit_bones.new('RightHandMiddle3')
    bone.head = 0.4651, 0.2548, 1.0368
    bone.tail = 0.4599, 0.2542, 1.0328
    bone.roll = -1.3587
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['RightHandMiddle2']]
    bones['RightHandMiddle3'] = bone.name
    bone = arm.edit_bones.new('r_mid_knuckle_B_top_mscl_JNT')
    bone.head = 0.4830, 0.2509, 1.0620
    bone.tail = 0.4853, 0.2548, 1.0571
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['RightHandMiddle2']]
    bones['r_mid_knuckle_B_top_mscl_JNT'] = bone.name
    bone = arm.edit_bones.new('RightHandRing3')
    bone.head = 0.4726, 0.2281, 1.0329
    bone.tail = 0.4683, 0.2281, 1.0296
    bone.roll = -1.3653
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['RightHandRing2']]
    bones['RightHandRing3'] = bone.name
    bone = arm.edit_bones.new('r_ring_knuckle_B_top_mscl_JNT')
    bone.head = 0.4875, 0.2228, 1.0566
    bone.tail = 0.4893, 0.2253, 1.0522
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['RightHandRing2']]
    bones['r_ring_knuckle_B_top_mscl_JNT'] = bone.name
    bone = arm.edit_bones.new('RightHandPinky3')
    bone.head = 0.4787, 0.1998, 1.0396
    bone.tail = 0.4752, 0.2008, 1.0366
    bone.roll = -1.4961
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['RightHandPinky2']]
    bones['RightHandPinky3'] = bone.name
    bone = arm.edit_bones.new('r_pinky_knuckle_B_top_mscl_JNT')
    bone.head = 0.4893, 0.1941, 1.0557
    bone.tail = 0.4911, 0.1957, 1.0516
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['RightHandPinky2']]
    bones['r_pinky_knuckle_B_top_mscl_JNT'] = bone.name

    bpy.ops.object.mode_set(mode='OBJECT')
    pbone = obj.pose.bones[bones['Root']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['Hips']]
    pbone.rigify_type = 'spines.basic_spine'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Torso')
    assign_bone_collection_refs(pbone.rigify_parameters, 'fk', 'Torso (Tweak)')
    assign_bone_collection_refs(pbone.rigify_parameters, 'tweak', 'Torso (Tweak)')
    pbone = obj.pose.bones[bones['Neck1']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['LeftEye']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['RightEye']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['face_root_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_eye_brows_rowA_1_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_eye_lid_up_root_1_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_eye_lid_up_rowA_1_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_eye_lid_lashes_up_rowA_1_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_jaw_nosabial_rowC_1_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_mug_lip_up_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_mug_lip_up_inside_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_mug_mouth_rowB_3_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_eye_brows_rowA_1_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_eye_lid_up_root_1_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_eye_lid_up_rowA_1_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_eye_lid_lashes_up_rowA_1_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_jaw_nosabial_rowC_1_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_mug_mouth_rowB_3_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_eye_brows_rowA_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_eye_brows_rowA_0_twk_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_eye_brows_rowA_2_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_eye_brows_rowA_3_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_eye_brows_rowB_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_eye_brows_rowB_1_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_eye_brows_rowB_2_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_eye_brows_rowB_3_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_eye_brows_rowC_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_eye_brows_rowC_1_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_eye_brows_rowC_2_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_eye_check_rowA_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_eye_check_rowA_1_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_eye_check_rowB_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_eye_check_rowC_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_eye_check_rowC_1_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_eye_check_rowD_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_eye_check_rowD_1_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_eye_check_rowE_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_eye_lid_corner_inside_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_eye_lid_up_rowD_4_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_eye_lid_dn_root_1_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_eye_lid_dn_rowA_1_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_eye_lid_lashes_dn_rowA_1_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_eye_lid_dn_root_2_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_eye_lid_dn_rowA_2_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_eye_lid_lashes_dn_rowA_2_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_eye_lid_dn_rowB_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_eye_lid_dn_rowB_1_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_eye_lid_dn_rowB_2_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_eye_lid_up_root_2_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_eye_lid_up_rowA_2_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_eye_lid_lashes_up_rowA_2_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_eye_lid_up_rowA_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_eye_lid_lashes_up_rowA_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_eye_lid_up_rowA_3_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_eye_lid_lashes_up_rowA_3_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_eye_lid_up_rowB_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_eye_lid_up_rowB_1_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_eye_lid_up_rowB_2_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_eye_lid_up_rowC_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_eye_lid_up_rowC_1_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_eye_lid_up_rowC_2_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_eye_lid_up_rowC_3_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_eye_lid_up_rowD_1_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_eye_lid_up_rowD_2_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_eye_lid_up_rowD_3_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_eye_nose_rowA_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_eye_nose_rowA_1_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_eye_nose_rowA_2_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_eye_nose_rowA_3_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_eye_wetness_root_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_eye_wetness_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_jaw_ear_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_jaw_ear_1_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_jaw_ear_2_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_jaw_nosabial_rowA_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_jaw_nosabial_rowA_1_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_jaw_nosabial_rowB_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_jaw_nosabial_rowB_1_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_jaw_nosabial_rowC_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_mug_lip_up_1_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_mug_lip_up_inside_1_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_mug_lip_up_2_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_mug_lip_up_inside_2_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_mug_lip_up_3_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_mug_mouth_rowA_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_mug_mouth_rowA_1_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_mug_mouth_rowA_2_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_mug_mouth_rowA_3_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_mug_mouth_rowB_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_mug_mouth_rowB_1_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_mug_mouth_rowB_2_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_nose_nosabial_rowA_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_nose_nosabial_rowB_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_nose_nosabial_rowB_1_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_nose_nosabial_rowC_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_nose_nosabial_rowC_1_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['mid_J_eye_brows_rowB_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['mid_J_eye_brows_rowC_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['mid_J_eye_brows_rowD_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['mid_J_eye_nose_rowA_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['mid_J_mug_nose_tip_rowA_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['mid_J_mug_nose_tip_rowB_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_mug_nose_nostril_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_mug_nose_nostril_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['mid_J_nose_nosabial_rowB_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_eye_brows_rowA_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_eye_brows_rowA_0_twk_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_eye_brows_rowA_2_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_eye_brows_rowA_3_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_eye_brows_rowB_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_eye_brows_rowB_1_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_eye_brows_rowB_2_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_eye_brows_rowB_3_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_eye_brows_rowC_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_eye_brows_rowC_1_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_eye_brows_rowC_2_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_eye_check_rowA_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_eye_check_rowA_1_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_eye_check_rowB_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_eye_check_rowC_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_eye_check_rowC_1_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_eye_check_rowD_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_eye_check_rowD_1_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_eye_check_rowE_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_eye_lid_corner_inside_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_eye_lid_up_rowD_4_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_eye_lid_dn_root_1_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_eye_lid_dn_rowA_1_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_eye_lid_lashes_dn_rowA_1_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_eye_lid_dn_root_2_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_eye_lid_dn_rowA_2_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_eye_lid_lashes_dn_rowA_2_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_eye_lid_dn_rowB_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_eye_lid_dn_rowB_1_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_eye_lid_dn_rowB_2_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_eye_lid_up_root_2_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_eye_lid_up_rowA_2_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_eye_lid_lashes_up_rowA_2_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_eye_lid_up_rowA_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_eye_lid_lashes_up_rowA_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_eye_lid_up_rowA_3_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_eye_lid_lashes_up_rowA_3_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_eye_lid_up_rowB_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_eye_lid_up_rowB_1_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_eye_lid_up_rowB_2_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_eye_lid_up_rowC_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_eye_lid_up_rowC_1_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_eye_lid_up_rowC_2_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_eye_lid_up_rowC_3_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_eye_lid_up_rowD_1_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_eye_lid_up_rowD_2_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_eye_lid_up_rowD_3_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_eye_nose_rowA_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_eye_nose_rowA_1_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_eye_nose_rowA_2_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_eye_nose_rowA_3_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_eye_wetness_root_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_eye_wetness_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_jaw_ear_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_jaw_ear_1_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_jaw_ear_2_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_jaw_nosabial_rowA_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_jaw_nosabial_rowA_1_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_jaw_nosabial_rowB_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_jaw_nosabial_rowB_1_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_jaw_nosabial_rowC_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_mug_mouth_rowB_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_mug_mouth_rowB_1_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_mug_mouth_rowB_2_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_nose_nosabial_rowA_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_nose_nosabial_rowB_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_nose_nosabial_rowB_1_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_nose_nosabial_rowC_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_nose_nosabial_rowC_1_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_mug_mouth_rowA_3_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_mug_mouth_rowA_2_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_mug_mouth_rowA_1_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_mug_mouth_rowA_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_mug_lip_up_3_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_mug_lip_up_2_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_mug_lip_up_inside_2_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_mug_lip_up_1_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_mug_lip_up_inside_1_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_mug_lip_up_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_mug_lip_up_inside_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_eye_lid_dn_rowA_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_eye_lid_lashes_dn_rowA_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_eye_lid_dn_rowA_3_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_eye_lid_lashes_dn_rowA_3_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_eye_lid_dn_rowA_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_eye_lid_lashes_dn_rowA_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_eye_lid_dn_rowA_3_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_eye_lid_lashes_dn_rowA_3_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['jaw_root_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['mid_J_jaw_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_mug_lip_dn_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_mug_lip_dn_inside_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_jaw_nosabial_rowA_2_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_jaw_nosabial_rowA_3_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_jaw_nosabial_rowB_2_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_jaw_nosabial_rowB_3_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_jaw_nosabial_rowB_4_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_jaw_nosabial_rowC_2_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_jaw_nosabial_rowC_3_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_jaw_nosabial_rowD_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_jaw_rowA_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_jaw_rowB_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_jaw_rowB_1_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_jaw_rowB_2_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_jaw_throat_rowA_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_mug_chin_rowA_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_mug_chin_rowA_1_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_mug_chin_rowA_2_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_mug_lip_corner_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_mug_lip_corner_inside_dn_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_mug_lip_corner_inside_up_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_mug_lip_dn_1_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_mug_lip_dn_inside_1_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_mug_lip_dn_2_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_mug_lip_dn_inside_2_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_mug_lip_dn_3_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_mug_mouth_rowA_4_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_mug_mouth_rowA_5_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_mug_mouth_rowA_6_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_mug_mouth_rowB_4_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_mug_mouth_rowB_5_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['mid_J_jaw_nosabial_rowB_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['mid_J_jaw_throat_rowA_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['mid_J_mug_chin_rowA_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['mid_J_mug_chin_rowA_1_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['mid_J_tongue_rowA_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['mid_J_tongue_rowB_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_tongue_rowB_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_tongue_rowB_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['mid_J_tongue_rowC_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_tongue_rowC_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_tongue_rowC_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['mid_J_tongue_rowD_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_tongue_rowD_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_tongue_rowD_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_jaw_nosabial_rowA_2_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_jaw_nosabial_rowA_3_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_jaw_nosabial_rowB_2_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_jaw_nosabial_rowB_3_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_jaw_nosabial_rowB_4_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_jaw_nosabial_rowC_2_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_jaw_nosabial_rowC_3_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_jaw_nosabial_rowD_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_jaw_rowA_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_jaw_rowB_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_jaw_rowB_1_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_jaw_rowB_2_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_jaw_throat_rowA_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_mug_chin_rowA_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_mug_chin_rowA_1_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_mug_chin_rowA_2_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_mug_lip_corner_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_mug_lip_corner_inside_dn_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_mug_lip_corner_inside_up_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_mug_lip_dn_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_mug_lip_dn_inside_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_mug_lip_dn_1_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_mug_lip_dn_inside_1_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_mug_lip_dn_2_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_mug_lip_dn_inside_2_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_mug_lip_dn_3_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_mug_mouth_rowA_4_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_mug_mouth_rowA_5_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_mug_mouth_rowA_6_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_mug_mouth_rowB_4_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_mug_mouth_rowB_5_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_eye_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_eye_pupil_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_eye_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_eye_pupil_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['HeadTip']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['gravity_root_upPoint_GRP']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['head_upDn_topDetectZero_GRP']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['head_tilt_start_GRP']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['gravity_front_GRP']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['gravity_side_GRP']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_sternocleidomastoid_top_mscl_Offset_GRP']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_sternocleidomastoid_top_mscl_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_jaw_rowC_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_neck_rowA_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_jaw_rowC_1_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_sternocleidomastoid_top_mscl_Offset_GRP']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_sternocleidomastoid_top_mscl_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_jaw_rowC_1_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_jaw_rowC_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_neck_rowA_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_jaw_throat_rowB_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_neck_rowA_1_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['mid_J_jaw_throat_rowB_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_jaw_throat_rowB_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_neck_rowA_1_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_sternocleidomastoid_top_mscl_endBounce_GRP']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_sternocleidomastoid_top_mscl_endBounce_GRP']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['sternocleidomastoid_top_start_GRP']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_sternocleidomastoid_top_start_Offset_GRP']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_sternocleidomastoid_top_start_Offset_B_GRP']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_sternocleidomastoid_top_start_GRP']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_sternocleidomastoid_top_start_Offset_GRP']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_sternocleidomastoid_top_start_Offset_B_GRP']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_sternocleidomastoid_top_start_GRP']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['head_upDn_botDetectZero_GRP']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['neck_upDn_topDetectZero_GRP']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['head_tilt_end_GRP']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['neck_tilt_start_GRP']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_sternocleidomastoid_bot_mscl_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_neck_rowA_2_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_neck_throat_rowA_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_sternocleidomastoid_bot_mscl_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_neck_rowA_2_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_neck_throat_rowA_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['mid_J_neck_throat_rowA_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_sternocleidomastoid_top_mscl_startBounce_GRP']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_sternocleidomastoid_top_mscl_startBounce_GRP']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_J_neck_rowB_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['l_J_neck_rowB_0_JNT']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['neck_upDn_botDetectZero_GRP']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['neck_tilt_end_GRP']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['skeleton:torso_bone']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Torso')
    pbone = obj.pose.bones[bones['skeleton:TransformationTarget']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face', 'Torso', 'Fingers', 'Arm.L (IK)', 'Arm.R (IK)', 'Leg.L (IK)', 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['new_torso']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Torso')
    pbone = obj.pose.bones[bones['Trajectory']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['reference_joint']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['gravity_setup_GRP']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['Spine']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Torso')
    pbone = obj.pose.bones[bones['LeftUpLeg']]
    pbone.rigify_type = 'limbs.leg'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Leg.L (IK)')
    try:
        pbone.rigify_parameters.extra_ik_toe = True
    except AttributeError:
        pass
    assign_bone_collection_refs(pbone.rigify_parameters, 'fk', 'Leg.L (FK)')
    assign_bone_collection_refs(pbone.rigify_parameters, 'tweak', 'Leg.L (Tweak)')
    pbone = obj.pose.bones[bones['RightUpLeg']]
    pbone.rigify_type = 'limbs.leg'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Leg.R (IK)')
    try:
        pbone.rigify_parameters.extra_ik_toe = True
    except AttributeError:
        pass
    assign_bone_collection_refs(pbone.rigify_parameters, 'fk', 'Leg.R (FK)')
    assign_bone_collection_refs(pbone.rigify_parameters, 'tweak', 'Leg.R (Tweak)')
    pbone = obj.pose.bones[bones['l_leg_buttock_mscl_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['r_leg_buttock_mscl_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['gravity_GRP']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['gravity_root_GRP']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['Spine1']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Torso')
    pbone = obj.pose.bones[bones['LeftLeg']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Leg.L (IK)')
    pbone = obj.pose.bones[bones['l_thigh_0_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['l_thigh_1_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['l_leg_groin_mscl_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['RightLeg']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_thigh_0_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['r_thigh_1_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['r_leg_groin_mscl_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['gravity_front_orig_GRP']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['gravity_side_orig_GRP']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['Spine2']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Torso')
    pbone = obj.pose.bones[bones['LeftFoot']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Leg.L (IK)')
    pbone = obj.pose.bones[bones['l_calf_0_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['l_lowLeg_back_B_mscl_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['l_lowLeg_back_A_mscl_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['l_knee_mscl_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['l_leg_back_B_mscl_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['l_leg_back_A_mscl_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['RightFoot']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['r_calf_0_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['r_lowLeg_back_A_mscl_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['r_lowLeg_back_B_mscl_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['r_knee_mscl_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['r_leg_back_B_mscl_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['r_leg_back_A_mscl_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['Spine3']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Torso')
    pbone = obj.pose.bones[bones['LeftHeel']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['LeftToeBase']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Leg.L (IK)')
    pbone = obj.pose.bones[bones['heel_l']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Leg.L (IK)')
    pbone = obj.pose.bones[bones['RightHeel']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['RightToeBase']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['heel_r']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Leg.R (IK)')
    pbone = obj.pose.bones[bones['LeftShoulder']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Torso')
    try:
        pbone.rigify_parameters.super_copy_widget_type = 'shoulder'
    except AttributeError:
        pass
    pbone = obj.pose.bones[bones['RightShoulder']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Torso')
    try:
        pbone.rigify_parameters.super_copy_widget_type = 'shoulder'
    except AttributeError:
        pass
    pbone = obj.pose.bones[bones['Neck']]
    pbone.rigify_type = 'spines.super_head'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Torso')
    try:
        pbone.rigify_parameters.connect_chain = True
    except AttributeError:
        pass
    assign_bone_collection_refs(pbone.rigify_parameters, 'tweak', 'Face (Primary)')
    pbone = obj.pose.bones[bones['r_latissimusDorsi_mscl_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['l_latissimusDorsi_mscl_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['l_trapezius_top_mscl_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['r_trapezius_top_mscl_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['l_chest_front_A_bot_out_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['l_chest_front_B_top_out_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['l_chest_front_B_bot_out_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['l_chest_front_C_top_out_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['l_chest_front_C_bot_out_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['l_scapula_A_top_out_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['l_scapula_A_bot_out_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['r_chest_front_A_bot_out_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['r_chest_front_B_top_out_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['r_chest_front_B_bot_out_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['r_chest_front_C_top_out_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['r_chest_front_C_bot_out_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['r_scapula_A_top_out_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['r_scapula_A_bot_out_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['l_sternocleidomastoid_bot_mscl_Offset_GRP']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['r_sternocleidomastoid_bot_mscl_Offset_GRP']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['headLookAt_GRP']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['neck_lookAt_setup_Offset_GRP']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['neck1_lookAt_setup_Offset_GRP']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['LeftArm']]
    pbone.rigify_type = 'limbs.super_limb'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Arm.L (IK)')
    assign_bone_collection_refs(pbone.rigify_parameters, 'fk', 'Arm.L (FK)')
    assign_bone_collection_refs(pbone.rigify_parameters, 'tweak', 'Arm.L (Tweak)')
    pbone = obj.pose.bones[bones['l_butterfly_top_CRV_bot_out_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['RightArm']]
    pbone.rigify_type = 'limbs.super_limb'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Arm.R (IK)')
    assign_bone_collection_refs(pbone.rigify_parameters, 'fk', 'Arm.R (FK)')
    assign_bone_collection_refs(pbone.rigify_parameters, 'tweak', 'Arm.R (Tweak)')
    pbone = obj.pose.bones[bones['r_butterfly_top_CRV_top_out_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['Head']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Face')
    pbone = obj.pose.bones[bones['neck_lookAt_setup_GRP']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['neck1_lookAt_setup_GRP']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['LeftForeArm']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Arm.L (IK)')
    pbone = obj.pose.bones[bones['l_SHL_0_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['l_SHL_1_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['RightForeArm']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Arm.R (IK)')
    pbone = obj.pose.bones[bones['r_SHL_0_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['r_SHL_1_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['LeftHand']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Arm.L (IK)')
    pbone = obj.pose.bones[bones['l_Wrist_0_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['l_Wrist_1_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['l_Wrist_2_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['l_elbow_bend_A_mscl_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['l_elbow_bend_B_mscl_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['l_elbow_back_mscl_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['l_deltoid_top_top_out_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['l_deltoid_top_bot_out_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['l_deltoid_front_top_out_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['l_deltoid_front_bot_out_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['l_deltoid_back_top_out_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['l_deltoid_back_bot_out_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['l_triceps_mscl_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['l_biceps_A_mscl_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['RightHand']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Arm.R (IK)')
    pbone = obj.pose.bones[bones['r_Wrist_0_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['r_Wrist_1_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['r_Wrist_2_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['r_elbow_bend_A_mscl_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['r_elbow_bend_B_mscl_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['r_elbow_back_mscl_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['r_deltoid_top_top_out_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['r_deltoid_top_bot_out_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['r_deltoid_front_top_out_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['r_deltoid_front_bot_out_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['r_deltoid_back_top_out_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['r_deltoid_back_bot_out_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['r_triceps_mscl_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['r_biceps_A_mscl_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['LeftInHandThumb']]
    pbone.rigify_type = 'limbs.super_finger'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Fingers')
    assign_bone_collection_refs(pbone.rigify_parameters, 'tweak', 'Fingers (Detail)')
    pbone = obj.pose.bones[bones['LeftInHandIndex']]
    pbone.rigify_type = 'limbs.super_palm'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Fingers')
    try:
        pbone.rigify_parameters.primary_rotation_axis = 'X'
    except AttributeError:
        pass
    assign_bone_collection_refs(pbone.rigify_parameters, 'tweak', 'Fingers (Detail)')
    pbone = obj.pose.bones[bones['LeftInHandMiddle']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Fingers')
    try:
        pbone.rigify_parameters.primary_rotation_axis = 'X'
    except AttributeError:
        pass
    assign_bone_collection_refs(pbone.rigify_parameters, 'tweak', 'Fingers (Detail)')
    pbone = obj.pose.bones[bones['LeftInHandRing']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Fingers')
    try:
        pbone.rigify_parameters.primary_rotation_axis = 'X'
    except AttributeError:
        pass
    assign_bone_collection_refs(pbone.rigify_parameters, 'tweak', 'Fingers (Detail)')
    pbone = obj.pose.bones[bones['LeftInHandPinky']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Fingers')
    try:
        pbone.rigify_parameters.primary_rotation_axis = 'X'
    except AttributeError:
        pass
    assign_bone_collection_refs(pbone.rigify_parameters, 'tweak', 'Fingers (Detail)')
    pbone = obj.pose.bones[bones['WeaponLeft']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['l_wrist_A_mscl_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['l_wrist_B_mscl_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['l_wrist_C_mscl_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['RightInHandThumb']]
    pbone.rigify_type = 'limbs.super_finger'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Fingers')
    assign_bone_collection_refs(pbone.rigify_parameters, 'tweak', 'Fingers (Detail)')
    pbone = obj.pose.bones[bones['RightInHandIndex']]
    pbone.rigify_type = 'limbs.super_palm'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Fingers')
    try:
        pbone.rigify_parameters.primary_rotation_axis = 'X'
    except AttributeError:
        pass
    assign_bone_collection_refs(pbone.rigify_parameters, 'tweak', 'Fingers (Detail)')
    pbone = obj.pose.bones[bones['RightInHandMiddle']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Fingers')
    try:
        pbone.rigify_parameters.primary_rotation_axis = 'X'
    except AttributeError:
        pass
    assign_bone_collection_refs(pbone.rigify_parameters, 'tweak', 'Fingers (Detail)')
    pbone = obj.pose.bones[bones['RightInHandRing']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Fingers')
    try:
        pbone.rigify_parameters.primary_rotation_axis = 'X'
    except AttributeError:
        pass
    assign_bone_collection_refs(pbone.rigify_parameters, 'tweak', 'Fingers (Detail)')
    pbone = obj.pose.bones[bones['RightInHandPinky']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Fingers')
    try:
        pbone.rigify_parameters.primary_rotation_axis = 'X'
    except AttributeError:
        pass
    assign_bone_collection_refs(pbone.rigify_parameters, 'tweak', 'Fingers (Detail)')
    pbone = obj.pose.bones[bones['WeaponRight']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['r_wrist_A_mscl_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['r_wrist_B_mscl_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['r_wrist_C_mscl_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['LeftHandThumb1']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Fingers')
    assign_bone_collection_refs(pbone.rigify_parameters, 'tweak', 'Fingers (Detail)')
    pbone = obj.pose.bones[bones['l_thumb_side_mscl_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['LeftHandIndex1']]
    pbone.rigify_type = 'limbs.super_finger'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Fingers')
    try:
        pbone.rigify_parameters.primary_rotation_axis = 'X'
    except AttributeError:
        pass
    assign_bone_collection_refs(pbone.rigify_parameters, 'tweak', 'Fingers (Detail)')
    pbone = obj.pose.bones[bones['l_thumb_thumb_A_bot_mscl_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['l_thumb_thumb_A_top_mscl_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['LeftHandMiddle1']]
    pbone.rigify_type = 'limbs.super_finger'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Fingers')
    try:
        pbone.rigify_parameters.primary_rotation_axis = 'X'
    except AttributeError:
        pass
    assign_bone_collection_refs(pbone.rigify_parameters, 'tweak', 'Fingers (Detail)')
    pbone = obj.pose.bones[bones['LeftHandRing1']]
    pbone.rigify_type = 'limbs.super_finger'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Fingers')
    try:
        pbone.rigify_parameters.primary_rotation_axis = 'X'
    except AttributeError:
        pass
    assign_bone_collection_refs(pbone.rigify_parameters, 'tweak', 'Fingers (Detail)')
    pbone = obj.pose.bones[bones['LeftHandPinky1']]
    pbone.rigify_type = 'limbs.super_finger'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Fingers')
    try:
        pbone.rigify_parameters.primary_rotation_axis = 'X'
    except AttributeError:
        pass
    assign_bone_collection_refs(pbone.rigify_parameters, 'tweak', 'Fingers (Detail)')
    pbone = obj.pose.bones[bones['l_pinkyBase_A_bot_mscl_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['RightHandThumb1']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Fingers')
    assign_bone_collection_refs(pbone.rigify_parameters, 'tweak', 'Fingers (Detail)')
    pbone = obj.pose.bones[bones['r_thumb_side_mscl_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['RightHandIndex1']]
    pbone.rigify_type = 'limbs.super_finger'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Fingers')
    try:
        pbone.rigify_parameters.primary_rotation_axis = 'X'
    except AttributeError:
        pass
    assign_bone_collection_refs(pbone.rigify_parameters, 'tweak', 'Fingers (Detail)')
    pbone = obj.pose.bones[bones['r_thumb_thumb_A_bot_mscl_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['r_thumb_thumb_A_top_mscl_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['RightHandMiddle1']]
    pbone.rigify_type = 'limbs.super_finger'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Fingers')
    try:
        pbone.rigify_parameters.primary_rotation_axis = 'X'
    except AttributeError:
        pass
    assign_bone_collection_refs(pbone.rigify_parameters, 'tweak', 'Fingers (Detail)')
    pbone = obj.pose.bones[bones['RightHandRing1']]
    pbone.rigify_type = 'limbs.super_finger'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Fingers')
    try:
        pbone.rigify_parameters.primary_rotation_axis = 'X'
    except AttributeError:
        pass
    assign_bone_collection_refs(pbone.rigify_parameters, 'tweak', 'Fingers (Detail)')
    pbone = obj.pose.bones[bones['RightHandPinky1']]
    pbone.rigify_type = 'limbs.super_finger'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Fingers')
    try:
        pbone.rigify_parameters.primary_rotation_axis = 'X'
    except AttributeError:
        pass
    assign_bone_collection_refs(pbone.rigify_parameters, 'tweak', 'Fingers (Detail)')
    pbone = obj.pose.bones[bones['r_pinkyBase_A_bot_mscl_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['LeftHandThumb2']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Fingers')
    assign_bone_collection_refs(pbone.rigify_parameters, 'tweak', 'Fingers (Detail)')
    pbone = obj.pose.bones[bones['LeftHandIndex2']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Fingers')
    try:
        pbone.rigify_parameters.primary_rotation_axis = 'X'
    except AttributeError:
        pass
    assign_bone_collection_refs(pbone.rigify_parameters, 'tweak', 'Fingers (Detail)')
    pbone = obj.pose.bones[bones['l_ind_knuckle_top_mscl_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['l_ind_knuckle_bot_mscl_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['LeftHandMiddle2']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Fingers')
    try:
        pbone.rigify_parameters.primary_rotation_axis = 'X'
    except AttributeError:
        pass
    assign_bone_collection_refs(pbone.rigify_parameters, 'tweak', 'Fingers (Detail)')
    pbone = obj.pose.bones[bones['l_mid_knuckle_top_mscl_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['l_mid_knuckle_bot_mscl_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['LeftHandRing2']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Fingers')
    try:
        pbone.rigify_parameters.primary_rotation_axis = 'X'
    except AttributeError:
        pass
    assign_bone_collection_refs(pbone.rigify_parameters, 'tweak', 'Fingers (Detail)')
    pbone = obj.pose.bones[bones['l_ring_knuckle_top_mscl_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['l_ring_knuckle_bot_mscl_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['LeftHandPinky2']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Fingers')
    try:
        pbone.rigify_parameters.primary_rotation_axis = 'X'
    except AttributeError:
        pass
    assign_bone_collection_refs(pbone.rigify_parameters, 'tweak', 'Fingers (Detail)')
    pbone = obj.pose.bones[bones['l_pinky_knuckle_top_mscl_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['l_pinky_knuckle_bot_mscl_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['RightHandThumb2']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Fingers')
    assign_bone_collection_refs(pbone.rigify_parameters, 'tweak', 'Fingers (Detail)')
    pbone = obj.pose.bones[bones['RightHandIndex2']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Fingers')
    try:
        pbone.rigify_parameters.primary_rotation_axis = 'X'
    except AttributeError:
        pass
    assign_bone_collection_refs(pbone.rigify_parameters, 'tweak', 'Fingers (Detail)')
    pbone = obj.pose.bones[bones['r_ind_knuckle_top_mscl_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['r_ind_knuckle_bot_mscl_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['RightHandMiddle2']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Fingers')
    try:
        pbone.rigify_parameters.primary_rotation_axis = 'X'
    except AttributeError:
        pass
    assign_bone_collection_refs(pbone.rigify_parameters, 'tweak', 'Fingers (Detail)')
    pbone = obj.pose.bones[bones['r_mid_knuckle_top_mscl_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['r_mid_knuckle_bot_mscl_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['RightHandRing2']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Fingers')
    try:
        pbone.rigify_parameters.primary_rotation_axis = 'X'
    except AttributeError:
        pass
    assign_bone_collection_refs(pbone.rigify_parameters, 'tweak', 'Fingers (Detail)')
    pbone = obj.pose.bones[bones['r_ring_knuckle_top_mscl_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['r_ring_knuckle_bot_mscl_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['RightHandPinky2']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Fingers')
    try:
        pbone.rigify_parameters.primary_rotation_axis = 'X'
    except AttributeError:
        pass
    assign_bone_collection_refs(pbone.rigify_parameters, 'tweak', 'Fingers (Detail)')
    pbone = obj.pose.bones[bones['r_pinky_knuckle_top_mscl_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['r_pinky_knuckle_bot_mscl_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['LeftHandIndex3']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Fingers')
    try:
        pbone.rigify_parameters.primary_rotation_axis = 'X'
    except AttributeError:
        pass
    assign_bone_collection_refs(pbone.rigify_parameters, 'tweak', 'Fingers (Detail)')
    pbone = obj.pose.bones[bones['l_ind_knuckle_B_top_mscl_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['LeftHandMiddle3']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Fingers')
    try:
        pbone.rigify_parameters.primary_rotation_axis = 'X'
    except AttributeError:
        pass
    assign_bone_collection_refs(pbone.rigify_parameters, 'tweak', 'Fingers (Detail)')
    pbone = obj.pose.bones[bones['l_mid_knuckle_B_top_mscl_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['LeftHandRing3']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Fingers')
    try:
        pbone.rigify_parameters.primary_rotation_axis = 'X'
    except AttributeError:
        pass
    assign_bone_collection_refs(pbone.rigify_parameters, 'tweak', 'Fingers (Detail)')
    pbone = obj.pose.bones[bones['l_ring_knuckle_B_top_mscl_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['LeftHandPinky3']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Fingers')
    try:
        pbone.rigify_parameters.primary_rotation_axis = 'X'
    except AttributeError:
        pass
    assign_bone_collection_refs(pbone.rigify_parameters, 'tweak', 'Fingers (Detail)')
    pbone = obj.pose.bones[bones['l_pinky_knuckle_B_top_mscl_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['RightHandIndex3']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Fingers')
    try:
        pbone.rigify_parameters.primary_rotation_axis = 'X'
    except AttributeError:
        pass
    assign_bone_collection_refs(pbone.rigify_parameters, 'tweak', 'Fingers (Detail)')
    pbone = obj.pose.bones[bones['r_ind_knuckle_B_top_mscl_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['RightHandMiddle3']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Fingers')
    try:
        pbone.rigify_parameters.primary_rotation_axis = 'X'
    except AttributeError:
        pass
    assign_bone_collection_refs(pbone.rigify_parameters, 'tweak', 'Fingers (Detail)')
    pbone = obj.pose.bones[bones['r_mid_knuckle_B_top_mscl_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['RightHandRing3']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Fingers')
    try:
        pbone.rigify_parameters.primary_rotation_axis = 'X'
    except AttributeError:
        pass
    assign_bone_collection_refs(pbone.rigify_parameters, 'tweak', 'Fingers (Detail)')
    pbone = obj.pose.bones[bones['r_ring_knuckle_B_top_mscl_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')
    pbone = obj.pose.bones[bones['RightHandPinky3']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Fingers')
    try:
        pbone.rigify_parameters.primary_rotation_axis = 'X'
    except AttributeError:
        pass
    assign_bone_collection_refs(pbone.rigify_parameters, 'tweak', 'Fingers (Detail)')
    pbone = obj.pose.bones[bones['r_pinky_knuckle_B_top_mscl_JNT']]
    pbone.rigify_type = 'basic.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    assign_bone_collections(pbone, 'Additional')

    bpy.ops.object.mode_set(mode='EDIT')
    for bone in arm.edit_bones:
        bone.select = False
        bone.select_head = False
        bone.select_tail = False
    for b in bones:
        bone = arm.edit_bones[bones[b]]
        bone.select = True
        bone.select_head = True
        bone.select_tail = True
        bone.bbone_x = bone.bbone_z = bone.length * 0.05
        arm.edit_bones.active = bone

    arm.collections.active_index = 0

    return bones
    
def create_rigify_rig(self, context):
    org = context.object
  #  meta = create_meta(org)
    rigify_rig = create_rigify(org)
    #create_constraints(rigify_rig, meta)
    #meta.hide_set(True)
if __name__ == "__main__":
    org = bpy.context.object
    meta = create_meta(org)
    rigify_rig = create_rigify(meta)
    create_constraints(rigify_rig, meta)
    
    
    