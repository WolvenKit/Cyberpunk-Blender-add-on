import time

import bpy
import mathutils

class RootMotionData(bpy.types.PropertyGroup):
    hip = bpy.props.StringProperty(name="Hip Bone")
    root = bpy.props.StringProperty(name="Root Bone")
    copy = bpy.props.StringProperty(name="Debug Character")
    step = bpy.props.IntProperty(name="Step Size", default=3, min=1)
    no_rot = bpy.props.BoolProperty(name="Ignore Rotation")
    do_vert = bpy.props.BoolProperty(name="Extract Vertical Motion")


class CP77HipMotionToRoot(bpy.types.Operator):
    """Transfer hip bone motion to root bone"""
    bl_idname = "hip_to_root_motion.cp77"
    bl_label = "Create Root Motion"
    bl_description = "Transfer Hip Motion to Root Bone"
    bl_options = {'REGISTER', 'UNDO'}

    skel = None

    @classmethod
    def poll(cls, context):
        return valid_armature(context) is not None

    def modal(self, context, event):
        ref = debug_character(context, self.skel)
        data = context.scene.rm_data
        frames = self.skel.animation_data.action.frame_range

        expr = "\"%s\"" % data.hip
        curves = self.skel.animation_data.action.fcurves
        for c in curves:
            if expr in c.data_path:
                curves.remove(c)

        root = self.skel.pose.bones[data.root]
        ref_hip = ref.pose.bones[data.hip]
        ref_hip_vec = (ref_hip.head - ref_hip.tail)
        ref_hip_vec.z = 0
        ref_mtx = world_mtx(ref, ref_hip)
        for f in steps(context, frames):
            context.scene.frame_set(f)

            mtx = world_mtx(ref, ref_hip)
            mtx_trans = mathutils.Matrix.Translation(mtx.translation - ref_mtx.translation)
            if not data.do_vert:
                mtx_trans.translation.z = 0
            root.matrix = pose_mtx(self.skel, root, mtx_trans)

            if not data.no_rot:
                hip_vec = (ref_hip.head - ref_hip.tail)
                hip_vec.z = 0
                root.rotation_quaternion = ref_hip_vec.rotation_difference(hip_vec)

            root.scale = (1, 1, 1)
            root.keyframe_insert(data_path="location")
            root.keyframe_insert(data_path="rotation_quaternion")

        hip = self.skel.pose.bones[data.hip]
        for f in range(round(frames.x), round(frames.y) + 1):
            context.scene.frame_set(f)
            hip.matrix = pose_mtx(self.skel, hip, world_mtx(ref, ref_hip))
            hip.keyframe_insert(data_path="rotation_quaternion")
            hip.keyframe_insert(data_path="location")
            hip.keyframe_insert(data_path="scale")

        return {'FINISHED'}

    def invoke(self, context, event):
        self.skel = valid_armature(context)
        context.scene.frame_set(self.skel.animation_data.action.frame_range.x)

        data = context.scene.rm_data
        if data.root == "":
            data.root = self.skel.pose.bones[0].name
        if data.hip == "":
            data.hip = self.skel.pose.bones[1].name

        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}


class CP77RootToHipMotion(bpy.types.Operator):
    """Transfer root bone motion to hip bone"""
    bl_idname = "root_to_hip_motion.cp77"
    bl_label = "Transfer Root To Hip Motion"
    bl_description = "Integrate root motion to hip bone"
    bl_options = {'REGISTER', 'UNDO'}

    skel = None

    @classmethod
    def poll(cls, context):
        return valid_armature(context) is not None

    def modal(self, context, event):
        ref = debug_character(context, self.skel)
        data = context.scene.rm_data

        root_expr = "\"%s\"" % data.root
        hip_expr = "\"%s\"" % data.hip
        curves = self.skel.animation_data.action.fcurves
        for c in curves:
            if root_expr in c.data_path or hip_expr in c.data_path:
                curves.remove(c)

        root = self.skel.pose.bones[data.root]
        root.keyframe_insert(data_path="rotation_quaternion")
        root.keyframe_insert(data_path="location")
        root.keyframe_insert(data_path="scale")

        hip = self.skel.pose.bones[data.hip]
        ref_hip = ref.pose.bones[data.hip]
        for f in steps(context, self.skel.animation_data.action.frame_range):
            context.scene.frame_set(f)
            ref_mtx = world_mtx(ref, ref_hip)

            hip.matrix = pose_mtx(self.skel, hip, ref_mtx)
            hip.keyframe_insert(data_path="rotation_quaternion")
            hip.keyframe_insert(data_path="location")
            hip.keyframe_insert(data_path="scale")

        root.keyframe_insert(data_path="rotation_quaternion")
        root.keyframe_insert(data_path="location")
        root.keyframe_insert(data_path="scale")

        return {'FINISHED'}

    def invoke(self, context, event):
        self.skel = valid_armature(context)
        context.scene.frame_set(self.skel.animation_data.action.frame_range.x)

        data = context.scene.rm_data
        if data.root == "":
            data.root = self.skel.pose.bones[0].name
        if data.hip == "":
            data.hip = self.skel.pose.bones[1].name

        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}


class CP77RemoveRootMotion(bpy.types.Operator):
    """Remove root motion from action, causing it to animate in-place"""
    bl_idname = "remove_root_motion.cp77"
    bl_label = "Remove Root Motion"
    bl_description = "Remove root motion from action, causing it to animate in-place"
    bl_options = {'REGISTER', 'UNDO'}

    skel = None

    @classmethod
    def poll(cls, context):
        return valid_armature(context) is not None

    def modal(self, context, event):
        data = context.scene.rm_data
        expr = "\"%s\"" % data.root
        curves = self.skel.animation_data.action.fcurves
        for c in curves:
            if expr in c.data_path:
                curves.remove(c)

        root = self.skel.pose.bones[data.root]
        frames = self.skel.animation_data.action.frame_range
        for f in [round(frames.x), round(frames.y)]:
            context.scene.frame_set(f)
            root.keyframe_insert(data_path="rotation_quaternion")
            root.keyframe_insert(data_path="location")
            root.keyframe_insert(data_path="scale")

        return {'FINISHED'}

    def invoke(self, context, event):
        self.skel = valid_armature(context)
        context.scene.frame_set(self.skel.animation_data.action.frame_range.x)

        data = context.scene.rm_data
        if data.root == "":
            data.root = self.skel.pose.bones[0].name

        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}


class CP77Remove_ref_character(bpy.types.Operator):
    """Remove reference character and its properties"""
    bl_idname = "rm_remove_ref_char.cp77"
    bl_label = "Finalize Root Motion Operation"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.scene.rm_data.copy != ""

    def execute(self, context):
        char = bpy.data.objects.get(context.scene.rm_data.copy)
        context.scene.rm_data.copy = ""
        if char is None:
            return {'CANCELLED'}

        anim = char.animation_data.action
        if anim != None:
            bpy.data.actions.remove(anim, True)

        context.scene.objects.unlink(char)
        bpy.data.objects.remove(char, True)

        return {'FINISHED'}


class PANEL_PT_main_panel(bpy.types.Panel):
    bl_idname = "PANEL_PT_root_motionist_main"
    bl_label = "Root Motion"
    bl_category = "CP77 Modding"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_parent = "CP77_PT_animspanel"

    @classmethod
    def poll(cls, context):
        return valid_armature(context) is not None

    def draw(self, context):
        layout = self.layout
        obj = context.active_object

        col = layout.column(align=True)
        col.prop_search(context.scene.rm_data, "root", obj.pose, "bones", text="Root")
        col.prop_search(context.scene.rm_data, "hip", obj.pose, "bones", text="Hip")
        #col.prop(obj.animation_data, "action", text="Anim")

        col = layout.column(align=True)
        col.prop(context.scene.rm_data, "step")
        col.prop(context.scene.rm_data, "no_rot")
        col.prop(context.scene.rm_data, "do_vert")
        #layout.separator()

        col = layout.column(align=True)
        row = col.row(align=True)
        row.operator("hip_to_root_motion.cp77", text="Transfer Hip To Root Motion")
        col.operator("root_to_hip_motion.cp77", text="Transfer Root To Hip Motion")
        col.operator("remove_root_motion.cp77", text="Animate In-Place")

        layout.operator("rm_remove_ref_char.cp77", text="Delete Ref Character")


def valid_armature(context):
    skel = context.active_object
    if skel is not None and skel.type == 'ARMATURE':
        if len(skel.pose.bones) >= 2:
            if skel.animation_data.action is not None:
                return skel
    return None


def world_mtx(armature, bone):
    return armature.convert_space(bone, bone.matrix, from_space='POSE', to_space='WORLD')


def pose_mtx(armature, bone, mat):
    return armature.convert_space(bone, mat, from_space='WORLD', to_space='POSE')


def debug_character(context, original):
    char = bpy.data.objects.get(context.scene.rm_data.copy)
    if char is not None:
        return char
    char = original.copy()
    char.data = original.data.copy()
    char.animation_data.action = original.animation_data.action.copy()
    char.name = "skel" + str(int(time.time()))
    context.scene.rm_data.copy = char.name
    context.scene.objects.link(char)
    return char


def steps(context, frames):
    last = round(frames.y)
    frms = list(range(round(frames.x), last + 1, context.scene.rm_data.step))
    if frms[-1] != last:
        frms.append(last)
    return frms


def register_rm():
    bpy.utils.register_class(RootMotionData)
    bpy.utils.register_class(CP77HipMotionToRoot)
    bpy.utils.register_class(CP77RootToHipMotion)
    bpy.utils.register_class(CP77RemoveRootMotion)
    bpy.utils.register_class(CP77Remove_ref_character)
    bpy.utils.register_class(PANEL_PT_main_panel)

    bpy.types.Scene.rm_data = bpy.props.PointerProperty(type=RootMotionData)


def unregister_rm():
    del bpy.types.Scene.rm_data

    bpy.utils.unregister_class(RootMotionData)
    bpy.utils.unregister_class(CP77HipMotionToRoot)
    bpy.utils.unregister_class(CP77RootToHipMotion)
    bpy.utils.unregister_class(CP77RemoveRootMotion)
    bpy.utils.unregister_class(CP77Remove_ref_character)
    bpy.utils.unregister_class(PANEL_PT_main_panel)
