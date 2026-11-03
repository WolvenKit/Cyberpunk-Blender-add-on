from bpy.types import UIList

from ...icons.cp77_icons import get_icon
from ..operators.overlay import BHLS_OT_Start, BHLS_OT_Stop
from ..runtime.overlay import is_running
from ..services.rig_assembly import state_is_current
from . import rigify as rigify_ui


class CP77_UL_RigParts(UIList):
    def draw_item(
        self, context, layout, data, item, icon, active_data, active_propname, index
    ):
        row = layout.row(align=True)
        row.label(text=item.role, icon="ARMATURE_DATA")
        row.label(text=item.label)


def draw(context, layout, obj):
    box = layout.box()
    box.label(text="Rig Loading", icon_value=get_icon("WKIT"))
    col = box.column()
    col.operator("cp77.rig_loader", text="Load Bundled Rig")

    if obj is None or obj.type != "ARMATURE":
        col.label(text="Select an armature")
        return

    col.operator("rigify_generator.cp77", text="Generate Rigify Rig")

    rig_parts = layout.box()
    header = rig_parts.row(align=True)
    header.label(text="Imported MetaRig Parts", icon="ARMATURE_DATA")
    header.operator("cp77.refresh_metarig_parts", text="", icon="FILE_REFRESH")
    state = context.scene.cp77_rig_assembly
    if not state_is_current(context, obj):
        rig_parts.label(text="Refresh to list the parts", icon="INFO")
    elif state.parts:
        rig_parts.template_list(
            "CP77_UL_RigParts",
            "",
            state,
            "parts",
            state,
            "active_index",
            rows=min(6, max(3, len(state.parts))),
        )
        row = rig_parts.row(align=True)
        replace = row.operator(
            "cp77.edit_metarig_part",
            text="Replace Selected",
            icon="FILE_REFRESH",
        )
        replace.operation = "REPLACE"
        add = row.operator(
            "cp77.edit_metarig_part",
            text="Add Part",
            icon="ADD",
        )
        add.operation = "ADD"
        remove = rig_parts.row()
        remove.enabled = state.active_index > 0
        remove.operator(
            "cp77.remove_metarig_part", text="Remove Selected Part", icon="REMOVE"
        )
    else:
        rig_parts.label(text="No imported parts", icon="INFO")

    box = layout.box()
    box.label(text="Bone Visibility", icon="BONE_DATA")
    col = box.column()
    if "cp77_deform_bones_hidden" in obj:
        col.operator("bone_unhider.cp77", text="Unhide Deform Bones")
    else:
        col.operator("bone_hider.cp77", text="Hide Deform Bones")

    if is_running():
        col.operator(
            BHLS_OT_Stop.bl_idname, text="Stop Drawing Bone Lines", icon="PAUSE"
        )
    else:
        col.operator(BHLS_OT_Start.bl_idname, text="Draw Bone Lines", icon="PLAY")

    box = layout.box()
    box.label(text="Pose Management", icon="ARMATURE_DATA")
    col = box.column()
    col.operator("reset_armature.cp77", text="Reset Armature")

    if "cp77_t_pose" in obj.data:
        if obj.data["cp77_t_pose"] is True:
            col.operator("cp77.load_apose", text="Switch to A-Pose")
        else:
            col.operator("cp77.load_tpose", text="Switch to T-Pose")

    rigify_ui.draw_rigify_controls(layout, context)
