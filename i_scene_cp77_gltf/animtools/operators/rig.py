import os

import bpy
from bpy.props import BoolProperty, CollectionProperty, EnumProperty, StringProperty
from bpy.types import Operator, OperatorFileListElement

from ...blender.operator_results import execute_operation, finish_operator
from ...core.log import get_logger
from ...core.notifications import import_operation, report
from ..services import pose, rig_assembly, rig_loader

_LOG = get_logger(__name__)


def _selected_armature(operator, context):
    armature = context.object
    if not armature or armature.type != "ARMATURE":
        report(operator, "ERROR", "Select an armature object.", logger=_LOG)
        return None
    return armature


class LoadAPose(Operator):
    bl_idname = "cp77.load_apose"
    bl_label = "Load A-Pose"
    bl_options = {"REGISTER", "UNDO"}

    @import_operation
    def execute(self, context):
        armature = _selected_armature(self, context)
        if armature is None:
            return {"CANCELLED"}
        return execute_operation(
            self, "A-Pose load", pose.load_bind_pose, armature, use_tpose=False
        )


class LoadTPose(Operator):
    bl_idname = "cp77.load_tpose"
    bl_label = "Load T-Pose"
    bl_options = {"REGISTER", "UNDO"}

    @import_operation
    def execute(self, context):
        armature = _selected_armature(self, context)
        if armature is None:
            return {"CANCELLED"}
        return execute_operation(
            self, "T-Pose load", pose.load_bind_pose, armature, use_tpose=True
        )


class CP77BoneHider(Operator):
    bl_idname = "bone_hider.cp77"
    bl_options = {"REGISTER", "UNDO"}
    bl_label = "Hide Non-Animation Bones"

    def execute(self, context):
        return execute_operation(
            self, "Bone visibility", pose.set_extra_bones_hidden, context, True
        )


class CP77BoneUnhider(Operator):
    bl_idname = "bone_unhider.cp77"
    bl_options = {"REGISTER", "UNDO"}
    bl_label = "Unhide Bones"

    def execute(self, context):
        return execute_operation(
            self, "Bone visibility", pose.set_extra_bones_hidden, context, False
        )


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

    @import_operation
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
        return finish_operator(self, result)

    def draw(self, context):
        props = context.scene.cp77_panel_props
        box = self.layout.box()
        row = box.row(align=True)
        row.label(text="Select rig to load: ")
        row.prop(props, "body_list", text="")
        col = box.column()
        col.prop(self, "rigify_it", text="Generate Rigify Control Rig")
        col.prop(props, "fbx_rot", text="Load Rig in FBX Orientation")


class CP77_OT_RefreshMetaRigParts(Operator):
    bl_idname = "cp77.refresh_metarig_parts"
    bl_label = "Refresh MetaRig Parts"

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == "ARMATURE"

    def execute(self, context):
        rig_assembly.sync_state(context, context.active_object, force=True)
        return {"FINISHED"}


class CP77_OT_EditMetaRigPart(Operator):
    bl_idname = "cp77.edit_metarig_part"
    bl_label = "Edit MetaRig Part"
    bl_options = {"REGISTER", "UNDO"}

    operation: EnumProperty(
        items=(
            ("REPLACE", "Replace", "Replace the selected imported MetaRig part"),
            ("ADD", "Add", "Append another rig part to the MetaRig"),
        ),
        default="REPLACE",
        options={"HIDDEN"},
    )
    filepath: StringProperty(name="Rig Part", subtype="FILE_PATH")
    filter_glob: StringProperty(default="*.rig.json", options={"HIDDEN"})

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return context.mode == "OBJECT" and obj is not None and obj.type == "ARMATURE"

    def invoke(self, context, event):
        self._target = context.active_object
        self._signature = str(self._target.get("cp77_metarig_part_ledger", ""))
        state = rig_assembly.sync_state(context)
        if self.operation == "REPLACE":
            if not state.parts:
                report(
                    self,
                    "ERROR",
                    "The selected armature has no imported MetaRig part ledger.",
                    logger=_LOG,
                )
                return {"CANCELLED"}
            index = max(0, min(state.active_index, len(state.parts) - 1))
            self.filepath = state.parts[index].path
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        target = context.active_object
        if target is None or target.type != "ARMATURE":
            report(self, "ERROR", "Select the imported MetaRig armature.", logger=_LOG)
            return {"CANCELLED"}
        if getattr(self, "_target", target) != target or (
            hasattr(self, "_signature")
            and self._signature != str(target.get("cp77_metarig_part_ledger", ""))
        ):
            report(
                self,
                "ERROR",
                "The active rig or its composition changed while selecting a file.",
                logger=_LOG,
            )
            return {"CANCELLED"}
        path = os.path.normpath(bpy.path.abspath(str(self.filepath or "")))
        if not path.casefold().endswith(".rig.json") or not os.path.isfile(path):
            report(self, "ERROR", "Select an exported .rig.json file.", logger=_LOG)
            return {"CANCELLED"}
        return execute_operation(
            self,
            "MetaRig part edit",
            rig_assembly.edit_part,
            context,
            target,
            self.operation,
            path,
        )


class CP77_OT_RemoveMetaRigPart(Operator):
    bl_idname = "cp77.remove_metarig_part"
    bl_label = "Remove MetaRig Part"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return context.mode == "OBJECT" and obj is not None and obj.type == "ARMATURE"

    def execute(self, context):
        return execute_operation(
            self,
            "MetaRig part removal",
            rig_assembly.remove_selected_part,
            context,
            context.active_object,
        )


RIG_OPERATOR_CLASSES = (
    CP77_OT_RefreshMetaRigParts,
    LoadAPose,
    LoadTPose,
    CP77BoneHider,
    CP77BoneUnhider,
    CP77RigLoader,
    CP77_OT_EditMetaRigPart,
    CP77_OT_RemoveMetaRigPart,
)
