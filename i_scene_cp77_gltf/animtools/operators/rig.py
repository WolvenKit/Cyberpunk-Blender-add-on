from bpy.props import BoolProperty, CollectionProperty, StringProperty
from bpy.types import Operator, OperatorFileListElement

from ..services import pose, rig_loader


def _finish(operator, result):
    if result.message:
        operator.report({result.level}, result.message)
    return result.blender_status


class LoadAPose(Operator):
    bl_idname = "cp77.load_apose"
    bl_label = "Load A-Pose"

    def execute(self, context):
        armature = context.object
        if not armature or armature.type != "ARMATURE":
            self.report({"ERROR"}, "Select an armature object.")
            return {"CANCELLED"}
        return _finish(self, pose.load_bind_pose(armature, use_tpose=False))


class LoadTPose(Operator):
    bl_idname = "cp77.load_tpose"
    bl_label = "Load T-Pose"

    def execute(self, context):
        armature = context.object
        if not armature or armature.type != "ARMATURE":
            self.report({"ERROR"}, "Select an armature object.")
            return {"CANCELLED"}
        return _finish(self, pose.load_bind_pose(armature, use_tpose=True))


class CP77BoneHider(Operator):
    bl_idname = "bone_hider.cp77"
    bl_parent_id = "CP77_PT_animspanel"
    bl_options = {"REGISTER", "UNDO"}
    bl_label = "Hide Non-Animation Bones"

    def execute(self, context):
        return _finish(self, pose.set_extra_bones_hidden(context, True))


class CP77BoneUnhider(Operator):
    bl_idname = "bone_unhider.cp77"
    bl_parent_id = "CP77_PT_animspanel"
    bl_options = {"REGISTER", "UNDO"}
    bl_label = "Unhide Bones"

    def execute(self, context):
        return _finish(self, pose.set_extra_bones_hidden(context, False))


class CP77RigLoader(Operator):
    bl_idname = "cp77.rig_loader"
    bl_label = "Load Deform Rig from Resources"

    files: CollectionProperty(type=OperatorFileListElement)
    appearances: StringProperty(name="Appearances", default="")
    directory: StringProperty(name="Directory", default="")
    filepath: StringProperty(name="Filepath", default="")
    rigify_it: BoolProperty(name="Apply Rigify Rig", default=False)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        props = context.scene.cp77_panel_props
        result = rig_loader.load_selected_rig(
            context,
            selected_name=props.body_list,
            fbx_rotation=bool(props.fbx_rot),
            generate_rigify=bool(self.rigify_it),
        )
        if result.ok:
            self.filepath = str(result.details.get("filepath", ""))
        return _finish(self, result)

    def draw(self, context):
        props = context.scene.cp77_panel_props
        box = self.layout.box()
        row = box.row(align=True)
        row.label(text="Select rig to load: ")
        row.prop(props, "body_list", text="")
        col = box.column()
        col.prop(self, "rigify_it", text="Generate Rigify Control Rig")
        col.prop(props, "fbx_rot", text="Load Rig in FBX Orientation")
