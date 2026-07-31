from ..services.overlay import is_running as draw_is_running
from ..operators.overlay import BHLS_OT_Start, BHLS_OT_Stop
from . import rigify as rigify_ui
from ...icons.cp77_icons import get_icon


def draw(context, layout, obj):
    box = layout.box()
    box.label(text='Rig Loading', icon_value=get_icon("WKIT"))
    col = box.column()
    col.operator('cp77.rig_loader', text="Load Bundled Rig")

    if obj is None or obj.type != 'ARMATURE':
        col.label(text="Select an armature to access rig tools")
        return

    col.operator('rigify_generator.cp77', text='Generate Rigify Rig')

    box = layout.box()
    box.label(text="Bone Visibility", icon='BONE_DATA')
    col = box.column()
    if 'deformBonesHidden' in obj:
        col.operator('bone_unhider.cp77', text='Unhide Deform Bones')
    else:
        col.operator('bone_hider.cp77', text='Hide Deform Bones')

    if draw_is_running():
        col.operator(BHLS_OT_Stop.bl_idname, text="Stop Drawing Bone Lines", icon='PAUSE')
    else:
        col.operator(BHLS_OT_Start.bl_idname, text="Draw Bone Lines", icon='PLAY')

    box = layout.box()
    box.label(text="Pose Management", icon='ARMATURE_DATA')
    col = box.column()
    col.operator('reset_armature.cp77', text="Reset Armature")

    if 'T-Pose' in obj.data:
        if obj.data['T-Pose'] is True:
            col.operator('cp77.load_apose', text="Switch to A-Pose")
        else:
            col.operator('cp77.load_tpose', text="Switch to T-Pose")

    rigify_ui.draw_rigify_controls(layout, context)
