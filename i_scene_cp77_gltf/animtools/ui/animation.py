import bpy

from ...blender.animation_context import local_actions
from ...icons.cp77_icons import get_icon
from ..blender.rigify.pairing import find_pair
from ..runtime import additive_preview
from ..services.actions import action_counts
from .playback import draw_mix_face


def draw(context, layout, obj):
    if obj is None or obj.type != "ARMATURE":
        box = layout.box()
        box.label(text="Select an armature")
        return

    has_actions = bool(local_actions())
    active_action = obj.animation_data.action if obj.animation_data else None
    props = context.scene.cp77_additive_preview
    additive_preview_active = additive_preview.is_active(obj)

    box = layout.box()
    col = box.column(align=True)

    if active_action or additive_preview_active or has_actions:
        playback_row = col.row()
        playback_row.alignment = "CENTER"
        row = playback_row.row(align=True)
        row.operator("screen.frame_jump", text="", icon="REW").end = False
        row.operator("screen.keyframe_jump", text="", icon="PREV_KEYFRAME").next = False
        row.operator(
            "screen.animation_play", text="", icon="PLAY_REVERSE"
        ).reverse = True
        if context.screen is not None and context.screen.is_animation_playing:
            row.operator(
                "screen.animation_cancel", text="", icon="PAUSE"
            ).restore_frame = False
        else:
            row.operator("screen.animation_play", text="", icon="PLAY")
        row.operator("screen.keyframe_jump", text="", icon="NEXT_KEYFRAME").next = True
        row.operator("screen.frame_jump", text="", icon="FF").end = True

        mode_row = col.row()
        mode_row.alignment = "CENTER"
        draw_mix_face(mode_row, context)

    draw_playback_settings(col, context, active_action)
    col.separator()

    header, panel = layout.panel("animsets", default_closed=False)
    header.label(text="Animations", icon_value=get_icon("WKIT"))
    if panel:
        draw_clip_list(panel, props)

    box = layout.box()
    box.label(text="Animation Tools", icon="KEYFRAME")
    col = box.column(align=True)
    draw_rigify_bakes(col, obj)
    draw_clip_tools(col)
    col.operator("cp77.open_animation_workspace", icon="WORKSPACE")


def draw_playback_settings(layout, context, action):
    """The active clip's playback range and the scene frame rate"""
    if action is not None:
        row = layout.row(align=True)
        row.prop(action, "use_frame_range", text="Set Playback Range", toggle=1)
        if action.use_frame_range:
            row = layout.row(align=True)
            row.prop(context.scene, "frame_start", text="Start")
            row.prop(context.scene, "frame_end", text="End")
    layout.menu("RENDER_MT_framerate_presets")
    row = layout.row(align=True)
    row.prop(context.scene.render, "fps", text="FPS")
    row.prop(context.scene.render, "fps_base", text="Base")


def draw_clip_list(layout, props):
    """Every clip in one list, with the button that adds a clip"""
    count = sum(action_counts())
    row = layout.row(align=True)
    row.label(text="Clips")
    op = row.operator("cp77.new_action", icon="ADD", text="")
    op.additive = False
    if count:
        layout.template_list(
            "CP77_UL_ClipList",
            "",
            bpy.data,
            "actions",
            props,
            "clip_index",
            rows=min(5, count),
        )
    else:
        layout.label(text="No animations loaded", icon="INFO")


def draw_rigify_bakes(layout, obj):
    source, rig = find_pair(obj)
    if source is not None and rig is not None:
        layout.operator("cp77.bake_source_to_rigify", text="Bake Cyberpunk to Rigify")
        layout.operator("cp77.bake_rigify_to_source", text="Bake Rigify to Cyberpunk")


def draw_clip_tools(layout):
    layout.operator("insert_keyframe.cp77", text="Insert Keyframe")
    layout.operator("cp77.anim_namer", text="Fix Anim Names")
