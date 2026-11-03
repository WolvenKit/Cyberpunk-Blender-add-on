<<<<<<< Updated upstream
import bpy

from ..services.facial import preview as facial_preview
from ..services.facial import runtime as facial_runtime
from ..services.facial import session as facial_session
=======
from ...blender.facial import session as facial_session
from ..services.facial import pose_preview_label
>>>>>>> Stashed changes
from . import jali as jali_ui


def draw(context, layout, obj):
    props = context.scene.cp77_facial
<<<<<<< Updated upstream
    session = facial_session.get_session(obj) if obj is not None and obj.type == "ARMATURE" else None
    loaded = session is not None

    header, panel = layout.panel("facial_setup_files", default_closed=False)
    header.label(text="Facial Setup Files", icon='FILE_FOLDER')
    if loaded:
        header.label(text="", icon='CHECKMARK')

    if panel:
        col = panel.column(align=True)
        col.prop(props, "rig_json", text="Rig JSON")
        col.prop(props, "facial_json", text="Facial JSON")
        col.operator("cp77.load_facial", text="Load Facial Setup", icon='FILE_FOLDER')

        if loaded:
            n_main = facial_session.pose_count(session, "face")
            n_corr = session.setup.face.num_correctives
            info = panel.column(align=True)
            info.scale_y = 0.85
            info.separator(factor=0.5)
            info.label(text=f"Bones: {session.rig.num_bones}  ·  Tracks: {len(session.track_names)}", icon='ARMATURE_DATA')
            info.label(text=f"Main poses: {n_main}  ·  Correctives: {n_corr}", icon='ANIM_DATA')

    preview_on = facial_preview.has_preview(session)
    header, panel = layout.panel("facial_pose_preview", default_closed=False)
    header.label(text="Pose Preview", icon='HIDE_OFF' if preview_on else 'HIDE_ON')

    if panel:
        if not loaded:
            panel.label(text="Load a facial setup to enable preview.", icon='INFO')
=======
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
>>>>>>> Stashed changes
        else:
            row = panel.row(align=True)
            part_row = row.split(factor=0.15, align=True)
            part_row.label(text="Part:")
<<<<<<< Updated upstream
            if hasattr(props, 'preview_part'):
                sub = part_row.row(align=True)
                sub.prop(props, "preview_part", expand=True)
            part = getattr(props, 'preview_part', 'face')

            n_poses = facial_session.pose_count(session, part)
            pose_index = int(
                getattr(
                    props, 'preview_pose_index',
                    getattr(props, 'main_pose', 0)
                    )
                )
            pose_index = max(0, min(pose_index, max(0, n_poses - 1)))

            idx_row = panel.row(align=True)
            if hasattr(props, 'preview_pose_index'):
                idx_row.prop(props, "preview_pose_index", text="Pose")
            else:
                idx_row.prop(props, "main_pose", text="Pose")
            idx_row.label(text=f"/ {max(0, n_poses - 1)}")

            track_name = facial_session.pose_track_name(session, part, pose_index)
            if track_name:
                nr = panel.row()
                nr.scale_y = 0.8
                nr.label(text=f"Track:  {track_name}", icon='ACTION')
=======
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
>>>>>>> Stashed changes

            panel.prop(props, "preview_weight", text="Weight", slider=True)

            panel.separator(factor=0.3)

            nav = panel.row(align=True)
            nav.scale_y = 1.15
<<<<<<< Updated upstream
            op_p = nav.operator("cp77.browse_pose", text="", icon='TRIA_LEFT')
            op_p.direction = -1
            nav.operator("cp77.apply_main_pose", text="Apply Pose", icon='PLAY')
            op_n = nav.operator("cp77.browse_pose", text="", icon='TRIA_RIGHT')
=======
            op_p = nav.operator("cp77.browse_pose", text="", icon="TRIA_LEFT")
            op_p.direction = -1
            nav.operator("cp77.apply_main_pose", text="Apply Pose", icon="PLAY")
            op_n = nav.operator("cp77.browse_pose", text="", icon="TRIA_RIGHT")
>>>>>>> Stashed changes
            op_n.direction = 1

            clear = panel.row()
            clear.enabled = preview_on
<<<<<<< Updated upstream
            clear.operator("cp77.clear_pose_preview", text="Clear Preview", icon='LOOP_BACK')
=======
            clear.operator(
                "cp77.clear_pose_preview", text="Clear Preview", icon="LOOP_BACK"
            )
>>>>>>> Stashed changes

            panel.separator(factor=0.3)

            reset_row = panel.row(align=True)
<<<<<<< Updated upstream
            reset_row.operator("cp77.reset_neutral", text="Rest Pose", icon='ARMATURE_DATA')
            reset_row.operator("cp77.reset_tracks_defaults", text="Reset Defaults", icon='FILE_REFRESH')

    header, panel = layout.panel("facial_baking", default_closed=False)
    header.label(text="Animation Baking", icon='REC')
=======
            reset_row.operator(
                "cp77.reset_neutral", text="Rest Pose", icon="ARMATURE_DATA"
            )
            reset_row.operator(
                "cp77.reset_tracks_defaults", text="Reset Defaults", icon="FILE_REFRESH"
            )

    header, panel = layout.panel("facial_baking", default_closed=False)
    header.label(text="Animation Baking", icon="REC")
>>>>>>> Stashed changes

    if panel:
        col = panel.column(align=True)
        row = col.row(align=True)
<<<<<<< Updated upstream
        row.operator("cp77.bake_facial_animation", text="Bake", icon='REC')
        row.operator("cp77.clear_facial_animation", text="Clear", icon='X')

    jali_ui.draw_panel(layout, loaded)

    if loaded:
        active = facial_runtime.is_solver_active()
        header, panel = layout.panel("facial_solver", default_closed=True)
        header.label(
            text="Real-Time Solver",
            icon='REC' if active else 'PLAY'
            )

        if panel:
            row = panel.row(align=True)
            row.scale_y = 1.15
            row.operator(
                    "cp77_facial.toggle_solver",
                    text="Stop Solver" if active else "Start Solver",
                    icon='PAUSE' if active else 'PLAY',
                    depress=active,
                    )

            timing = bpy.app.driver_namespace.get("cp77_facial_last_ms", {})
            if timing:
                tcol = panel.column(align=True)
                tcol.scale_y = 0.85
                for name, ms in timing.items():
                    tcol.label(text=f"{name}: {ms:.1f} ms", icon='TIME')

            row = panel.row()
            row.operator(
                "cp77_facial.solve_now", text="Solve Now",
                icon='RENDER_STILL'
                )
=======
        row.operator("cp77.bake_facial_animation", text="Bake", icon="REC")
        row.operator("cp77.clear_facial_animation", text="Clear", icon="X")

    jali_ui.draw_panel(layout, loaded)
>>>>>>> Stashed changes
