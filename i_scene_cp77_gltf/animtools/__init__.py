import sys
import bpy
from bpy.utils import register_class, unregister_class
from bpy.types import Panel
from bpy.props import StringProperty
from ..cyber_props import CP77_FacialProps
from ..icons.cp77_icons import get_icon
from ..main.common import get_classes
from . import root_motion
from . import anim_events
from . import anim_ops
from . import facial_ops
from . import rig_binding
from . import pose_preview
from . import solver as _solver_mod
from .anim_ops import BHLS_OT_Start, BHLS_OT_Stop
from .facial_ops import (
    _CACHE,
    _PREVIEW_SNAPSHOT,
    _get_pose_count,
    _get_pose_track_name,
)
from .animtools import CP77AnimsList
class CP77_PT_AnimsPanel(Panel):
    bl_idname = "CP77_PT_animspanel"
    bl_label = "Animation Tools"
    bl_category = "CP77 Modding"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_options = {'DEFAULT_CLOSED'}

    name: StringProperty(options={'HIDDEN'})

    @classmethod
    def poll(cls, context):
        cp77_addon_prefs = bpy.context.preferences.addons['i_scene_cp77_gltf'].preferences
        if cp77_addon_prefs.context_only:
            return context.active_object and context.active_object.type == 'ARMATURE'
        else:
            return context

    def draw(self, context):
        layout = self.layout
        cp77_addon_prefs = bpy.context.preferences.addons['i_scene_cp77_gltf'].preferences

        if not cp77_addon_prefs.show_animtools:
            return

        props = context.scene.cp77_panel_props
        obj = context.active_object

        # Tab selector at the top
        row = layout.row(align=True)
        row.prop(props, "animtab", expand=True)

        layout.separator()

        # RIG SETUP TAB
        if props.animtab == 'RIGSETUP':
            self.draw_rigsetup_tab(context, layout, obj)

        # ANIMATION TAB
        elif props.animtab == 'ANIMATION':
            self.draw_animation_tab(context, layout, obj)

        # FACIAL ANIMATION TAB
        elif props.animtab == 'FACIAL':
            self.draw_facial_tab(context, layout, obj)

    def draw_rigsetup_tab(self, context, layout, obj):
        """Rig loading, configuration, and preparation"""
        box = layout.box()
        box.label(text='Rig Loading', icon_value=get_icon("WKIT"))
        col = box.column()
        col.operator('cp77.rig_loader', text="Load Bundled Rig")

        if obj is None or obj.type != 'ARMATURE':
            col.label(text="Select an armature to access additional rig tools", icon='INFO')
            return

        col.operator('rigify_generator.cp77', text='Generate Rigify Rig')

        # Bone visibility
        box = layout.box()
        box.label(text="Bone Visibility", icon='BONE_DATA')
        col = box.column()
        if 'deformBonesHidden' in obj:
            col.operator('bone_unhider.cp77', text='Unhide Deform Bones')
        else:
            col.operator('bone_hider.cp77', text='Hide Deform Bones')

        if anim_ops._running:
            col.operator(BHLS_OT_Stop.bl_idname, text="Stop Drawing Bone Lines", icon='PAUSE')
        else:
            col.operator(BHLS_OT_Start.bl_idname, text="Draw Bone Lines", icon='PLAY')

        # Posing
        box = layout.box()
        box.label(text="Pose Management", icon='ARMATURE_DATA')
        col = box.column()
        col.operator('reset_armature.cp77', text="Reset Armature")

        if 'T-Pose' in obj.data:
            if obj.data['T-Pose'] is True:
                col.operator('cp77.load_apose', text="Switch to A-Pose")
            else:
                col.operator('cp77.load_tpose', text="Switch to T-Pose")



    def draw_animation_tab(self, context, layout, obj):
        """Animation playback, management, and keyframing"""
        if obj is None or obj.type != 'ARMATURE':
            box = layout.box()
            box.label(text="Select an armature to use animation tools", icon='INFO')
            return

        available_anims = list(CP77AnimsList(self, context))
        active_action = obj.animation_data.action if obj.animation_data else None
        props = context.scene.cp77_panel_props

        # Playback controls with timeline settings
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
                row.prop(bpy.context.scene, 'frame_start', text="Start")
                row.prop(bpy.context.scene, 'frame_end', text="End")

        col.menu('RENDER_MT_framerate_presets')
        row = col.row(align=True)
        row.prop(context.scene.render, "fps", text="FPS")
        row.prop(context.scene.render, "fps_base", text="Base")
        col.separator()
        # Animation list
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

        # Root Motion tools
        rm_open, panel = layout.panel("root_motion", default_closed=True)
        rm_open.label(text="Root Motion", icon='ANIM')

        if panel:
            data = context.scene.rm_data
            col = panel.column(align=True)
            col.label(text="Bone Configuration:", icon='BONE_DATA')
            col.prop_search(data, "root", obj.pose, "bones", text="Root")
            col.prop_search(data, "hip", obj.pose, "bones", text="Hip")

            col.separator()
            col.label(text="Transfer Options:", icon='MODIFIER')
            col.prop(data, "step")
            col.prop(data, "no_rot")
            col.prop(data, "do_vert")

            col.separator()
            col.label(text="Operations:")
            col.operator("cp77.hip_to_root_motion", text="Hip to Root Motion", icon='EXPORT')
            col.operator("cp77.root_to_hip_motion", text="Root to Hip Motion", icon='IMPORT')
            col.operator("cp77.remove_root_motion", text="Remove Root Motion", icon='X')

        # Keyframe and animation tools
        box = layout.box()
        box.label(text="Animation Tools", icon='KEYFRAME')
        col = box.column(align=True)
        col.operator('insert_keyframe.cp77', text="Insert Keyframe")
        col.operator('cp77.anim_namer', text="Fix Anim Names")

    def draw_facial_tab(self, context, layout, obj):
        """Facial animation: setup files, weighted pose preview, baking."""
        props  = context.scene.cp77_facial
        loaded = _CACHE.get("rig") is not None

        # ── File Loading ─────────────────────────────────────────────────
        box    = layout.box()
        header = box.row()
        header.label(text="Facial Setup Files", icon='FILE_FOLDER')
        if loaded:
            header.label(text="", icon='CHECKMARK')

        col = box.column(align=True)
        col.prop(props, "rig_json",    text="Rig JSON")
        col.prop(props, "facial_json", text="Facial JSON")
        box.operator("cp77.load_facial", text="Load Facial Setup", icon='FILE_FOLDER')

        # ── Loaded Status ────────────────────────────────────────────────
        if loaded:
            rig   = _CACHE["rig"]
            setup = _CACHE["setup"]
            n_main = _get_pose_count(setup, "face")
            n_corr = setup.face.num_correctives
            info   = layout.box()
            col    = info.column(align=True)
            col.scale_y = 0.85
            col.label(text=f"Bones: {rig.num_bones}  ·  Tracks: {len(rig.track_names)}", icon='ARMATURE_DATA')
            col.label(text=f"Main poses: {n_main}  ·  Correctives: {n_corr}",            icon='ANIM_DATA')

        layout.separator(factor=0.5)

        # ── Pose Preview ─────────────────────────────────────────────────
        box        = layout.box()
        preview_on = getattr(props, 'preview_active', False)

        hdr = box.row()
        hdr.label(text="Pose Preview", icon='HIDE_OFF' if preview_on else 'HIDE_ON')

        if not loaded:
            box.label(text="Load a facial setup to enable preview.", icon='INFO')
        else:
            rig   = _CACHE["rig"]
            setup = _CACHE["setup"]

            # Part selector
            row = box.row(align=True)
            part_row = row.split(factor=0.15, align=True)
            part_row.label(text="Part:")
            if hasattr(props, 'preview_part'):
                sub = part_row.row(align=True)
                sub.prop(props, "preview_part", expand=True)
            part = getattr(props, 'preview_part', 'face')

            # Pose index + count
            n_poses    = _get_pose_count(setup, part)
            pose_index = int(getattr(props, 'preview_pose_index',
                                     getattr(props, 'main_pose', 0)))
            pose_index = max(0, min(pose_index, max(0, n_poses - 1)))

            idx_row = box.row(align=True)
            if hasattr(props, 'preview_pose_index'):
                idx_row.prop(props, "preview_pose_index", text="Pose")
            else:
                idx_row.prop(props, "main_pose", text="Pose")
            idx_row.label(text=f"/ {max(0, n_poses - 1)}")

            # Live track name
            track_name = _get_pose_track_name(setup, rig, part, pose_index)
            if track_name:
                nr = box.row()
                nr.scale_y = 0.8
                nr.label(text=f"Track:  {track_name}", icon='ACTION')

            # Weight slider
            box.prop(props, "preview_weight", text="Weight", slider=True)

            box.separator(factor=0.3)

            # ◀ Prev  Apply  Next ▶
            nav = box.row(align=True)
            nav.scale_y = 1.15
            op_p = nav.operator("cp77.browse_pose", text="", icon='TRIA_LEFT')
            op_p.direction = -1
            nav.operator("cp77.apply_main_pose", text="Apply Pose", icon='PLAY')
            op_n = nav.operator("cp77.browse_pose", text="", icon='TRIA_RIGHT')
            op_n.direction = 1

            # Clear / restore
            clear = box.row()
            clear.enabled = preview_on or (obj is not None and obj.name in _PREVIEW_SNAPSHOT)
            clear.operator("cp77.clear_pose_preview", text="Clear Preview", icon='LOOP_BACK')

            box.separator(factor=0.3)

            # Reset row
            reset_row = box.row(align=True)
            reset_row.operator("cp77.reset_neutral",         text="Rest Pose",       icon='ARMATURE_DATA')
            reset_row.operator("cp77.reset_tracks_defaults", text="Reset Defaults",  icon='FILE_REFRESH')

        layout.separator(factor=0.5)

        # ── Animation Baking ─────────────────────────────────────────────
        box = layout.box()
        box.label(text="Animation Baking", icon='REC')
        col = box.column(align=True)
        row = col.row(align=True)
        row.operator("cp77.bake_facial_animation",  text="Bake",  icon='REC')
        row.operator("cp77.clear_facial_animation", text="Clear", icon='X')

        # ── Real-Time Solver ─────────────────────────────────────────────
        if loaded:
            from . import solver as _solver

            box = layout.box()
            active = _solver.is_solver_active()
            hdr = box.row()
            hdr.label(text="Real-Time Solver",
                       icon='REC' if active else 'PLAY')

            row = box.row(align=True)
            row.scale_y = 1.15
            row.operator(
                "cp77_facial.toggle_solver",
                text="Stop Solver" if active else "Start Solver",
                icon='PAUSE' if active else 'PLAY',
                depress=active,
            )

            # Timing readout
            timing = bpy.app.driver_namespace.get("cp77_facial_last_ms", {})
            if timing:
                tcol = box.column(align=True)
                tcol.scale_y = 0.85
                for name, ms in timing.items():
                    tcol.label(text=f"{name}: {ms:.1f} ms", icon='TIME')

            row = box.row()
            row.operator("cp77_facial.solve_now", text="Solve Now",
                          icon='RENDER_STILL')


class CP77_UL_AnimList(bpy.types.UIList):
    """UI List for displaying animations with filtering support"""

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            obj = context.active_object
            if not obj or not obj.animation_data:
                return

            active_action = obj.animation_data.action
            selected = item == active_action

            # Determine SIMD status for this action
            _hints = item.get("optimizationHints", None)
            _is_simd = False
            if _hints is not None:
                try:
                    _is_simd = bool(_hints.get("preferSIMD", False)) if hasattr(_hints, 'get') else bool(_hints["preferSIMD"])
                except (KeyError, TypeError):
                    pass
            _simd_icon = 'FORCE_MAGNETIC' if _is_simd else 'FORCE_CHARGE'

            row = layout.row(align=True)

            # Play/pause control
            if selected and context.screen.is_animation_playing:
                op = row.operator('screen.animation_cancel', icon='PAUSE', text="", emboss=False)
                op.restore_frame = False
            else:
                icon = 'PLAY' if selected else 'TRIA_RIGHT'
                op = row.operator('cp77.set_animset', icon=icon, text="", emboss=False)
                op.name = item.name
                op.play = True

            # Animation name
            op = row.operator('cp77.set_animset', text=item.name, emboss=False)
            op.name = item.name
            op.play = False

            # Cyclic toggle for active animation with frame range
            if selected and active_action and active_action.use_frame_range:
                row.prop(active_action, 'use_cyclic', icon='CON_FOLLOWPATH', text="", emboss=False)

            # SIMD encoding toggle
            row.operator('cp77.toggle_simd', icon=_simd_icon, text="", emboss=False).name = item.name

            # Delete action
            row.operator('cp77.delete_anims', icon='X', text="", emboss=False).name = item.name

        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label(text="", icon='ACTION')

    def filter_items(self, context, data, propname):
        """Filter and sort items in the list"""
        actions = getattr(data, propname)
        helper_funcs = bpy.types.UI_UL_list

        # Default return values
        flt_flags = []
        flt_neworder = []

        # Filter by name
        if self.filter_name:
            flt_flags = helper_funcs.filter_items_by_name(
                    self.filter_name,
                    self.bitflag_filter_item,
                    actions,
                    "name",
                    reverse=False
                    )

        if not flt_flags:
            flt_flags = [self.bitflag_filter_item] * len(actions)

        # Sort alphabetically if requested
        if self.use_filter_sort_alpha:
            flt_neworder = helper_funcs.sort_items_by_name(actions, "name")

        return flt_flags, flt_neworder

def register_animtools():
    """Register all animation tool classes."""
    # Register new backend modules first (operators used by facial_ops and UI)
    rig_binding.register()
    pose_preview.register()
    _solver_mod.register()

    # Collect operators and panel classes from submodules
    for mod in (anim_ops, facial_ops):
        ops, others = get_classes(mod)
        for cls in ops + others:
            if not hasattr(bpy.types, cls.__name__):
                try:
                    register_class(cls)
                except ValueError:
                    pass

    # Panel and UIList live here
    for cls in (CP77_PT_AnimsPanel, CP77_UL_AnimList):
        if not hasattr(bpy.types, cls.__name__):
            try:
                register_class(cls)
            except ValueError:
                pass

    bpy.types.Scene.cp77_facial = bpy.props.PointerProperty(type=CP77_FacialProps)
    root_motion.register_rm()
    anim_events.register_anim_events()


def unregister_animtools():
    """Unregister all animation tool classes."""
    # Stop bone-line drawing if active.  _handle lives in anim_ops and is
    # mutated there by BHLS_OT_Start/Stop, so reference it directly.
    if anim_ops._handle is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(anim_ops._handle, 'WINDOW')
        except Exception:
            pass
        anim_ops._handle = None

    root_motion.unregister_rm()
    anim_events.unregister_anim_events()

    if hasattr(bpy.types.Scene, 'cp77_facial'):
        del bpy.types.Scene.cp77_facial

    for mod in (facial_ops, anim_ops):
        ops, others = get_classes(mod)
        for cls in reversed(ops + others):
            try:
                unregister_class(cls)
            except RuntimeError:
                pass

    for cls in reversed((CP77_PT_AnimsPanel, CP77_UL_AnimList)):
        try:
            unregister_class(cls)
        except RuntimeError:
            pass

    # Unregister new backend modules (reverse order of register)
    _solver_mod.unregister()
    pose_preview.unregister()
    rig_binding.unregister()