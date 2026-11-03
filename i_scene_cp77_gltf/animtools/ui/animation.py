import bpy

from ..services.actions import iter_local_actions
from ..services.rigify.pairing import find_pair
from .root_motion import draw as draw_root_motion
from ...icons.cp77_icons import get_icon


def draw(context, layout, obj):
    if obj is None or obj.type != 'ARMATURE':
        box = layout.box()
        box.label(text="Select an armature to use animation tools")
        return

    available_anims = list(iter_local_actions())
    active_action = obj.animation_data.action if obj.animation_data else None
    props = context.scene.cp77_panel_props

    box = layout.box()
    col = box.column(align=True)

    if active_action:
        row = col.row(align=True)
        row.alignment = 'CENTER'
        row.operator("screen.frame_jump", text="", icon='REW').end = False
        row.operator("screen.keyframe_jump", text="", icon='PREV_KEYFRAME').next = False
        row.operator("screen.animation_play", text="", icon='PLAY_REVERSE').reverse = True
        row.operator("screen.animation_play", text="", icon='PLAY')
        row.operator("screen.keyframe_jump", text="", icon='NEXT_KEYFRAME').next = True
        row.operator("screen.frame_jump", text="", icon='FF').end = True

        row = col.row(align=True)
        row.prop(active_action, 'use_frame_range', text="Set Playback Range", toggle=1)

        if active_action.use_frame_range:
            row = col.row(align=True)
            row.prop(context.scene, 'frame_start', text="Start")
            row.prop(context.scene, 'frame_end', text="End")

    col.menu('RENDER_MT_framerate_presets')
    row = col.row(align=True)
    row.prop(context.scene.render, "fps", text="FPS")
    row.prop(context.scene.render, "fps_base", text="Base")
    col.separator()
    header, panel = layout.panel("animsets", default_closed=False)
    header.label(text='Animsets', icon_value=get_icon('WKIT'))
    header.operator('cp77.new_action', icon='ADD', text="")

    if panel:
        if available_anims and obj.animation_data:
            row = panel.row()
            rows = 5 if len(bpy.data.actions) > 5 else len(bpy.data.actions)
            row.template_list(
                    "CP77_UL_AnimList",
                    "",
                    bpy.data,
                    "actions",
                    props,
                    "active_action_index",
                    rows=rows
                    )

    draw_root_motion(layout, context, obj)

    box = layout.box()
    box.label(text="Animation Tools", icon='KEYFRAME')
    col = box.column(align=True)
    source, rig = find_pair(obj)
    if source is not None and rig is not None:
        col.operator('cp77.bake_rigify_to_source', text='Bake Rigify to Cyberpunk', )
    col.operator('insert_keyframe.cp77', text="Insert Keyframe")
    col.operator('cp77.anim_namer', text="Fix Anim Names")
