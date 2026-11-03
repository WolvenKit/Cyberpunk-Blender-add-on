from ...blender.facial import session as facial_session
from ..services.facial import pose_preview_label
from . import jali as jali_ui


def draw(context, layout, obj):
    props = context.scene.cp77_facial
    session = (
        facial_session.peek_session(obj)
        if obj is not None and obj.type == "ARMATURE"
        else None
    )
    loaded = session is not None

    header, panel = layout.panel("facial_setup_files", default_closed=False)
    header.label(text="Facial Setup Files", icon="FILE_FOLDER")

    if panel:
        col = panel.column(align=True)
        col.prop(props, "facial_json", text="Facial JSON")
        col.operator("cp77.load_facial", text="Load Facial Setup", icon="FILE_FOLDER")
        if not loaded and facial_session.is_bound(obj):
            col.operator(
                "cp77_facial.rebuild_cache",
                text="Restore Facial Session",
                icon="FILE_REFRESH",
            )

    preview_on = session is not None and session.has_preview
    header, panel = layout.panel("facial_pose_preview", default_closed=False)
    header.label(text="Pose Preview", icon="HIDE_OFF")

    if panel:
        if not loaded:
            panel.label(text="Load a facial setup first.", icon="INFO")
        else:
            row = panel.row(align=True)
            part_row = row.split(factor=0.15, align=True)
            part_row.label(text="Part:")
            sub = part_row.row(align=True)
            sub.prop(props, "preview_part", expand=True)

            n_poses, track_name = pose_preview_label(
                session, props.preview_part, props.preview_pose_index
            )

            idx_row = panel.row(align=True)
            idx_row.prop(props, "preview_pose_index", text="Pose")
            idx_row.label(text=f"/ {max(0, n_poses - 1)}")

            if track_name:
                nr = panel.row()
                nr.scale_y = 0.8
                nr.label(text=f"Track:  {track_name}", icon="ACTION")

            panel.prop(props, "preview_weight", text="Weight", slider=True)

            panel.separator(factor=0.3)

            nav = panel.row(align=True)
            nav.scale_y = 1.15
            op_p = nav.operator("cp77.browse_pose", text="", icon="TRIA_LEFT")
            op_p.direction = -1
            nav.operator("cp77.apply_main_pose", text="Apply Pose", icon="PLAY")
            op_n = nav.operator("cp77.browse_pose", text="", icon="TRIA_RIGHT")
            op_n.direction = 1

            clear = panel.row()
            clear.enabled = preview_on
            clear.operator(
                "cp77.clear_pose_preview", text="Clear Preview", icon="LOOP_BACK"
            )

            panel.separator(factor=0.3)

            reset_row = panel.row(align=True)
            reset_row.operator(
                "cp77.reset_neutral", text="Rest Pose", icon="ARMATURE_DATA"
            )
            reset_row.operator(
                "cp77.reset_tracks_defaults", text="Reset Defaults", icon="FILE_REFRESH"
            )

    header, panel = layout.panel("facial_baking", default_closed=False)
    header.label(text="Animation Baking", icon="REC")

    if panel:
        col = panel.column(align=True)
        row = col.row(align=True)
        row.operator("cp77.bake_facial_animation", text="Bake", icon="REC")
        row.operator("cp77.clear_facial_animation", text="Clear", icon="X")

    jali_ui.draw_panel(layout, loaded)
