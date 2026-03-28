from __future__ import annotations
import sys
import time
import numpy as np
import bpy
from bpy.types import Operator
from bpy.props import BoolProperty, IntProperty, FloatProperty
from pathlib import Path
from typing import Tuple

from ..main.common import get_classes
from .compat import get_action_fcurves
from . import rig_binding
from . import pose_preview
from . import solver as _solver
from .facial_setup_loader import load_rig, load_facial_setup

# Optional JALI dependencies
try:
    from .jali import JALI_DEPS_INSTALLED as PARSELMOUTH_AVAILABLE
    from .jali import AcousticPhonemeDetector, TranscriptAligner
    from .jali_integration import JALIToCp77Bridge, JALIAnimationPipeline
except ImportError:
    PARSELMOUTH_AVAILABLE = False
    AcousticPhonemeDetector = None
    TranscriptAligner = None
    JALIToCp77Bridge = None
    JALIAnimationPipeline = None

_CACHE: dict = {
    "rig":   None,   # RigData
    "setup": None,   # FacialSetupData
}


def _sync_cache_from_binding(obj_name: str) -> bool:
    """Copy rig_binding cache entries into _CACHE dict for UI compat."""
    cache = rig_binding.get_cache(obj_name)
    if cache is not None:
        _CACHE["rig"]   = cache.rig
        _CACHE["setup"] = cache.setup
        return True
    return False


# Alias for the preview snapshot store — __init__.py imports this
_PREVIEW_SNAPSHOT = pose_preview._snapshots


# Shared facial helpers — used by the panel in __init__.py

def _get_pose_count(setup, part: str = "face") -> int:
    """Number of main poses for *part* (face/eyes/tongue)."""
    part_data = getattr(setup, part, None)
    if part_data is not None:
        return part_data.num_main_poses
    return 0


def _get_pose_track_name(setup, rig, part: str, pose_index: int) -> str:
    """Human-readable track name for a main pose, or empty string."""
    part_data = getattr(setup, part, None)
    if part_data is None or pose_index < 0 or pose_index >= part_data.num_main_poses:
        return ""
    track_idx = int(part_data.main_tracks[pose_index])
    if track_idx < rig.num_tracks:
        return str(rig.track_names[track_idx])
    return ""


def _cache_ensure_loaded(context) -> bool:
    """Return True if cache is populated; try to load from active armature."""
    obj = context.active_object
    if obj is None or obj.type != 'ARMATURE':
        return _CACHE.get("rig") is not None

    # Check if rig_binding already has it cached
    if _sync_cache_from_binding(obj.name):
        return True

    # Try to restore from persisted paths on the armature
    if rig_binding.is_bound(obj):
        result = rig_binding.restore_cache_from_object(obj)
        if result is not None:
            _sync_cache_from_binding(obj.name)
            return True

    # Try to load from scene properties
    props = getattr(context.scene, 'cp77_facial', None)
    if props is None:
        return False
    rig_path   = getattr(props, "rig_json", "")
    setup_path = getattr(props, "facial_json", "")
    if rig_path and setup_path:
        try:
            rig   = load_rig(bpy.path.abspath(rig_path))
            setup = load_facial_setup(bpy.path.abspath(setup_path), rig)
            _bind_to_object(context, obj, rig, setup,
                            bpy.path.abspath(setup_path),
                            bpy.path.abspath(rig_path))
            return True
        except Exception:
            pass
    return False


def _bind_to_object(context, obj, rig, setup, setup_path, rig_path):
    """Full bind: register props, build cache, update _CACHE dict."""
    seg = rig_binding.TrackSegments.from_tracks_mapping(
        {
            "numEnvelopes":        setup.num_envelope_tracks,
            "numMainPoses":        setup.num_main_poses,
            "numLipsyncOverrides": setup.num_lipsync_overrides,
            "numWrinkles":         setup.num_wrinkle_tracks,
        },
        rig.num_tracks,
    )
    used_bone_names = rig_binding.build_used_bone_names(setup, rig)
    rig_binding.register_track_properties(obj, rig, seg)

    cache = rig_binding.BindingCache(
        setup           = setup,
        rig             = rig,
        used_bone_names = used_bone_names,
        track_segments  = seg,
        setup_path      = setup_path,
        rig_path        = rig_path,
        bind_time       = time.time(),
    )
    rig_binding._set_cache(obj.name, cache)
    rig_binding._persist_to_object(obj, cache)

    _CACHE["rig"]   = rig
    _CACHE["setup"] = setup


# Operators

class CP77_OT_LoadFacial(Operator):
    bl_idname = "cp77.load_facial"
    bl_label = "Load Rig + FacialSetup"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.cp77_facial
        if not props.rig_json:
            self.report({'ERROR'}, "Please select a rig JSON file")
            return {'CANCELLED'}
        if not props.facial_json:
            self.report({'ERROR'}, "Please select a facial setup JSON file")
            return {'CANCELLED'}

        obj = context.active_object
        if obj is None or obj.type != 'ARMATURE':
            self.report({'ERROR'}, "Select an armature first")
            return {'CANCELLED'}

        sp = bpy.path.abspath(props.facial_json)
        rp = bpy.path.abspath(props.rig_json)

        try:
            t0 = time.time()
            rig   = load_rig(rp)
            setup = load_facial_setup(sp, rig)

            _bind_to_object(context, obj, rig, setup, sp, rp)

            elapsed = (time.time() - t0) * 1000
            nb = rig.num_bones
            mp = setup.face.num_main_poses
            cp = setup.face.num_correctives

            missing = rig_binding.validate_bones(
                obj, rig_binding.build_used_bone_names(setup, rig))
            warn = f" ({len(missing)} bones missing)" if missing else ""

            self.report(
                {'INFO'},
                f"Loaded: {nb} bones, {mp} main poses, "
                f"{cp} correctives{warn} [{elapsed:.0f}ms]"
            )
            return {'FINISHED'}

        except FileNotFoundError as e:
            self.report({'ERROR'}, f"File not found: {e}")
            return {'CANCELLED'}
        except Exception as e:
            self.report({'ERROR'}, f"Load failed: {e}")
            import traceback; traceback.print_exc()
            return {'CANCELLED'}


class CP77_OT_ApplyMainPose(Operator):
    """Apply the selected pose at full weight via pose_preview backend."""
    bl_idname  = "cp77.apply_main_pose"
    bl_label   = "Apply Pose"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (context.active_object is not None and
                context.active_object.type == 'ARMATURE')

    def execute(self, context):
        if not _cache_ensure_loaded(context):
            self.report({'ERROR'}, "Load rig + facialsetup first.")
            return {'CANCELLED'}

        obj   = context.active_object
        cache = rig_binding.get_cache(obj.name)
        if cache is None:
            self.report({'ERROR'}, "No binding cache for this armature.")
            return {'CANCELLED'}

        props = context.scene.cp77_facial
        part       = getattr(props, 'preview_part', 'face')
        pose_index = int(getattr(props, 'preview_pose_index',
                                 getattr(props, 'main_pose', 0)))

        ok, msg = pose_preview.preview_apply_pose(obj, cache, part, pose_index)
        self.report({'INFO'} if ok else {'ERROR'}, msg)
        return {'FINISHED'} if ok else {'CANCELLED'}


class CP77_OT_BrowsePose(Operator):
    """Step forward or backward through main poses."""
    bl_idname  = "cp77.browse_pose"
    bl_label   = "Browse Poses"
    bl_options = {'REGISTER', 'UNDO'}

    direction: IntProperty(name="Direction", default=1, min=-1, max=1)

    @classmethod
    def poll(cls, context):
        return (context.active_object is not None and
                context.active_object.type == 'ARMATURE' and
                _CACHE.get("setup") is not None)

    def execute(self, context):
        if not _cache_ensure_loaded(context):
            self.report({'ERROR'}, "Load rig + facialsetup first.")
            return {'CANCELLED'}

        obj   = context.active_object
        cache = rig_binding.get_cache(obj.name)
        if cache is None:
            return {'CANCELLED'}

        props     = context.scene.cp77_facial
        part      = getattr(props, 'preview_part', 'face')
        part_data = getattr(cache.setup, part, None)
        if part_data is None:
            return {'CANCELLED'}

        n_poses = part_data.num_main_poses
        if n_poses == 0:
            return {'CANCELLED'}

        current  = int(getattr(props, 'preview_pose_index',
                                getattr(props, 'main_pose', 0)))
        new_idx  = (current + self.direction) % n_poses

        if hasattr(props, 'preview_pose_index'):
            props.preview_pose_index = new_idx
        if hasattr(props, 'main_pose'):
            props.main_pose = new_idx

        ok, msg = pose_preview.preview_apply_pose(obj, cache, part, new_idx)
        self.report({'INFO'} if ok else {'ERROR'}, msg)
        return {'FINISHED'} if ok else {'CANCELLED'}


class CP77_OT_ClearPosePreview(Operator):
    """Restore the pose that existed before the last preview."""
    bl_idname  = "cp77.clear_pose_preview"
    bl_label   = "Clear Preview"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        if obj is None or obj.type != 'ARMATURE':
            return False
        if getattr(context.scene.cp77_facial, 'preview_active', False):
            return True
        return obj.name in pose_preview._snapshots

    def execute(self, context):
        obj   = context.active_object
        cache = rig_binding.get_cache(obj.name)
        if cache is None:
            # Fallback: reset all bones to identity
            if context.object.mode != 'POSE':
                bpy.ops.object.mode_set(mode='POSE')
            for pb in obj.pose.bones:
                pb.matrix_basis.identity()
            props = getattr(context.scene, 'cp77_facial', None)
            if props and hasattr(props, 'preview_active'):
                props.preview_active = False
            self.report({'INFO'}, "Preview cleared — bones reset (no cache)")
            return {'FINISHED'}

        ok, msg = pose_preview.preview_clear(obj, cache)
        self.report({'INFO'}, msg)
        return {'FINISHED'}


class CP77_OT_ResetNeutral(Operator):
    bl_idname = "cp77.reset_neutral"
    bl_label = "Reset to Rest"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object
        if obj is None or obj.type != 'ARMATURE':
            self.report({'ERROR'}, 'Select an Armature object.')
            return {'CANCELLED'}
        if context.object.mode != 'POSE':
            bpy.ops.object.mode_set(mode='POSE')
        for pb in obj.pose.bones:
            pb.matrix_basis.identity()
        obj.update_tag(refresh={'DATA'})
        context.view_layer.update()
        return {'FINISHED'}


class CP77_OT_ResetTracksToDefaults(Operator):
    """Reset all facial track custom properties to zero."""
    bl_idname = "cp77.reset_tracks_defaults"
    bl_label = "Reset Tracks to Defaults"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (context.active_object and
                context.active_object.type == 'ARMATURE')

    def execute(self, context):
        obj = context.active_object
        cache = rig_binding.get_cache(obj.name)
        if cache is None:
            self.report({'ERROR'}, "No rig loaded. Bind facial setup first.")
            return {'CANCELLED'}

        count = 0
        for name in cache.rig.track_names:
            name = str(name)
            if name in obj:
                obj[name] = 0.0
                count += 1

        self.report({'INFO'}, f"Reset {count} tracks to zero")
        return {'FINISHED'}


class CP77_OT_BakeFacialAnimation(Operator):
    """Bake facial animation over frame range using facial_solve_numpy."""
    bl_idname = "cp77.bake_facial_animation"
    bl_label = "Bake Facial Animation"
    bl_options = {'REGISTER', 'UNDO'}

    frame_start:   bpy.props.IntProperty(name="Start Frame", default=1, min=0)
    frame_end:     bpy.props.IntProperty(name="End Frame",   default=250, min=0)
    keyframe_step: bpy.props.IntProperty(name="Step", default=1, min=1, max=10)

    @classmethod
    def poll(cls, context):
        return (context.active_object and
                context.active_object.type == 'ARMATURE')

    def execute(self, context):
        obj = context.active_object
        if not _cache_ensure_loaded(context):
            self.report({'ERROR'}, 'Load rig + facialsetup first.')
            return {'CANCELLED'}

        cache = rig_binding.get_cache(obj.name)
        if cache is None:
            self.report({'ERROR'}, 'No binding cache.')
            return {'CANCELLED'}

        if context.object.mode != 'POSE':
            bpy.ops.object.mode_set(mode='POSE')

        if not obj.animation_data:
            obj.animation_data_create()
        if not obj.animation_data.action:
            obj.animation_data.action = bpy.data.actions.new(
                name="FacialAnimation")

        if self.frame_end < self.frame_start:
            self.report({'ERROR'}, 'End frame must be >= start frame.')
            return {'CANCELLED'}

        frame_count = 0
        for frame in range(self.frame_start, self.frame_end + 1,
                           self.keyframe_step):
            context.scene.frame_set(frame)

            in_tracks = rig_binding.read_tracks(obj, cache)
            bone_quats, bone_trans, out_tracks = _solver.facial_solve_numpy(
                cache.setup, cache.rig, cache.track_segments,
                in_tracks, lod=0,
            )

            _solver.write_bones(obj, cache, bone_quats, bone_trans)
            rig_binding.write_output_tracks(obj, cache, out_tracks)

            for bone in obj.pose.bones:
                bone.keyframe_insert(data_path="location", frame=frame)
                bone.keyframe_insert(
                    data_path="rotation_quaternion", frame=frame)
                bone.keyframe_insert(data_path="scale", frame=frame)

            frame_count += 1

        obj.update_tag(refresh={'DATA'})
        context.view_layer.update()
        self.report(
            {'INFO'},
            f'Baked {frame_count} frames '
            f'({self.frame_start}-{self.frame_end}).')
        return {'FINISHED'}

    def invoke(self, context, event):
        self.frame_start = context.scene.frame_start
        self.frame_end   = context.scene.frame_end
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "frame_start")
        layout.prop(self, "frame_end")
        layout.prop(self, "keyframe_step")


class CP77_OT_ClearFacialAnimation(Operator):
    """Clear all facial animation keyframes."""
    bl_idname = "cp77.clear_facial_animation"
    bl_label = "Clear Facial Animation"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (context.active_object and
                context.active_object.type == 'ARMATURE' and
                context.active_object.animation_data and
                context.active_object.animation_data.action)

    def execute(self, context):
        obj    = context.active_object
        action = obj.animation_data.action
        fcurves = get_action_fcurves(action)
        if fcurves is None:
            self.report({'INFO'}, 'No F-curves found.')
            return {'CANCELLED'}
        to_remove = list(fcurves)
        for fc in to_remove:
            fcurves.remove(fc)
        self.report({'INFO'}, f'Cleared {len(to_remove)} F-curves.')
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)


# JALI operators — optional, require praat-parselmouth

class CP77_OT_PreviewFacialPose(Operator):
    """Preview facial poses in real-time for testing and verification"""
    bl_idname = "cp77.preview_facial_pose"
    bl_label = "Preview Facial Pose"
    bl_description = "Apply a test facial pose to verify rig setup"
    bl_options = {'REGISTER', 'UNDO'}

    pose_type: bpy.props.EnumProperty(
            name="Pose Type",
            items=[
                ('NEUTRAL', "Neutral", "Relaxed neutral face"),
                ('AA', "AA - 'father'", "Open jaw, neutral lips"),
                ('IY', "IY - 'beet'", "Slight jaw, wide lips"),
                ('UW', "UW - 'boot'", "Slight jaw, puckered lips"),
                ('M', "M - 'mom'", "Closed jaw, lip closure"),
                ('F', "F - 'fun'", "Slight jaw, lip-teeth"),
                ('S', "S - 'sun'", "Narrow jaw, stretched"),
                ('TH', "TH - 'think'", "Slight jaw, tongue forward"),
                ('SMILE', "Smile", "Wide lips, raised corners"),
                ('POUT', "Pout", "Puckered lips"),
                ('JAW_OPEN', "Jaw Open", "Max jaw opening"),
                ('CUSTOM', "Custom JALI", "Manual JA/LI control"),
                ],
            default='NEUTRAL'
            )

    custom_jaw: bpy.props.FloatProperty(
            name="Jaw (JA)",
            default=0.5,
            min=0.0,
            max=1.0,
            description="Jaw opening (0 = closed, 1 = max open)"
            )

    custom_lip: bpy.props.FloatProperty(
            name="Lip (LI)",
            default=0.0,
            min=-1.0,
            max=1.0,
            description="Lip shaping (-1 = pucker, 0 = neutral, 1 = wide)"
            )

    intensity: bpy.props.FloatProperty(
            name="Intensity",
            default=1.0,
            min=0.0,
            max=2.0,
            description="Pose intensity multiplier"
            )

    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.type == 'ARMATURE'

    def execute(self, context):
        obj = context.active_object

        if JALIToCp77Bridge is None:
            self.report({'ERROR'}, "JALI not available — install praat-parselmouth")
            return {'CANCELLED'}

        if not _cache_ensure_loaded(context):
            self.report({'ERROR'}, 'Load rig + facialsetup first.')
            return {'CANCELLED'}

        rig   = _CACHE.get("rig")
        setup = _CACHE.get("setup")
        cache = rig_binding.get_cache(obj.name)

        if not rig or not setup or cache is None:
            self.report({'ERROR'}, 'Load rig + facialsetup first.')
            return {'CANCELLED'}

        ja, li = self._get_jali_params()
        ja *= self.intensity
        li *= self.intensity

        bridge = JALIToCp77Bridge()

        track_names = [str(n) for n in rig.track_names]

        ja_curve = np.array([ja], dtype=np.float32)
        li_curve = np.array([li], dtype=np.float32)

        tracks = bridge.jali_to_tracks(ja_curve, li_curve, track_names)

        for i, name in enumerate(track_names):
            if not name:
                continue
            value = float(tracks[0, i])
            if name not in obj:
                obj[name] = value
                if hasattr(obj, 'id_properties_ui'):
                    ui = obj.id_properties_ui(name)
                    ui.update(min=0.0, max=1.0, soft_min=0.0, soft_max=1.0)
            else:
                obj[name] = value

        if context.object.mode != 'POSE':
            bpy.ops.object.mode_set(mode='POSE')

        result = self._apply_solved_pose(context, cache, obj, tracks[0, :])

        if result:
            self.report({'INFO'}, f'Applied {self.pose_type} pose (JA={ja:.2f}, LI={li:.2f})')

        return {'FINISHED'}

    def _get_jali_params(self) -> Tuple[float, float]:
        try:
            from .jali import PHONEME_JALI_MAP as ARPABET_JALI_MAP
        except ImportError:
            ARPABET_JALI_MAP = {}

        if self.pose_type == 'CUSTOM':
            return self.custom_jaw, self.custom_lip

        pose_map = {
            'NEUTRAL': (0.3, 0.0),
            'AA': (1.0, 0.0),
            'IY': (0.15, 0.9),
            'UW': (0.2, -0.95),
            'M': (0.0, 0.0),
            'F': (0.1, 0.1),
            'S': (0.05, 0.4),
            'TH': (0.15, 0.0),
            'SMILE': (0.3, 0.8),
            'POUT': (0.2, -0.9),
            'JAW_OPEN': (1.0, 0.0),
            }

        if self.pose_type in ARPABET_JALI_MAP:
            jali = ARPABET_JALI_MAP[self.pose_type]
            return jali.jaw, jali.lip

        return pose_map.get(self.pose_type, (0.3, 0.0))

    def _apply_solved_pose(self, context, cache, obj,
                           tracks_in: np.ndarray) -> bool:
        """Run facial solver and write bone transforms."""
        try:
            bone_quats, bone_trans, out_tracks = _solver.facial_solve_numpy(
                cache.setup, cache.rig, cache.track_segments,
                tracks_in, lod=0,
            )
        except Exception as e:
            self.report({'ERROR'}, f'Solver error: {e}')
            return False
        _solver.write_bones(obj, cache, bone_quats, bone_trans)
        rig_binding.write_output_tracks(obj, cache, out_tracks)
        context.view_layer.update()
        return True

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=350)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "pose_type", text="")

        if self.pose_type == 'CUSTOM':
            box = layout.box()
            box.label(text="JALI Parameters:", icon='SETTINGS')
            box.prop(self, "custom_jaw", slider=True)
            box.prop(self, "custom_lip", slider=True)

        layout.separator()
        layout.prop(self, "intensity", slider=True)


class CP77_OT_GenerateJALILipSync(Operator):
    """Generate JALI-based lipsync animation for CP77 facial system"""
    bl_idname = "cp77.generate_jali_lipsync"
    bl_label = "Generate JALI Lipsync"
    bl_description = "Analyze audio and generate procedural facial animation using JALI"
    bl_options = {'REGISTER', 'UNDO'}

    audio_path: bpy.props.StringProperty(
            name="Audio File",
            subtype='FILE_PATH',
            description="Audio file to analyze (.wav, .mp3, .ogg)"
            )

    transcript: bpy.props.StringProperty(
            name="Transcript (Optional)",
            description="Text transcript for better accuracy"
            )

    use_transcript: bpy.props.BoolProperty(
            name="Use Transcript",
            default=False,
            description="Use transcript for forced alignment (more accurate)"
            )

    jaw_multiplier: bpy.props.FloatProperty(
            name="Jaw Multiplier",
            default=1.0,
            min=0.0,
            max=2.0,
            description="Scale jaw opening (1.0 = normal, 2.0 = exaggerated)"
            )

    lip_multiplier: bpy.props.FloatProperty(
            name="Lip Multiplier",
            default=1.0,
            min=0.0,
            max=2.0,
            description="Scale lip shaping (1.0 = normal, 2.0 = exaggerated)"
            )

    @classmethod
    def poll(cls, context):
        return (context.active_object and
                context.active_object.type == 'ARMATURE')

    def execute(self, context):
        if not PARSELMOUTH_AVAILABLE:
            self.report({'ERROR'}, "Install parselmouth: pip install praat-parselmouth")
            return {'CANCELLED'}

        audio_path = bpy.path.abspath(self.audio_path)
        if not audio_path or not Path(audio_path).exists():
            self.report({'ERROR'}, f"Audio file not found: {audio_path}")
            return {'CANCELLED'}

        if not _cache_ensure_loaded(context):
            self.report({'ERROR'}, "Load facial rig + setup first")
            return {'CANCELLED'}

        rig   = _CACHE.get("rig")
        setup = _CACHE.get("setup")

        if not rig or not setup:
            self.report({'ERROR'}, "Load facial rig + setup first")
            return {'CANCELLED'}

        try:
            self.report({'INFO'}, "Detecting phonemes from audio...")

            if self.use_transcript and self.transcript.strip():
                aligner = TranscriptAligner(audio_path, self.transcript)
                phoneme_events = aligner.align_phonemes()
                self.report({'INFO'}, f"Aligned {len(phoneme_events)} phonemes with transcript")
            else:
                detector = AcousticPhonemeDetector()
                phoneme_events = detector.detect_phonemes(audio_path)
                self.report({'INFO'}, f"Detected {len(phoneme_events)} phonemes (acoustic-only)")

            if not phoneme_events:
                self.report({'WARNING'}, "No phonemes detected")
                return {'CANCELLED'}

            self.report({'INFO'}, "Generating JALI animation...")

            pipeline = JALIAnimationPipeline(
                    rig=rig,
                    setup=setup,
                    fps=context.scene.render.fps
                    )

            tracks, inbetweens, correctives = pipeline.generate_animation(
                    phoneme_events,
                    audio_path=audio_path
                    )

            if self.jaw_multiplier != 1.0 or self.lip_multiplier != 1.0:
                self.report(
                        {'INFO'},
                        f"Applying multipliers (Jaw: {self.jaw_multiplier:.2f}, Lip: {self.lip_multiplier:.2f})"
                        )

                track_names = [str(n) for n in rig.track_names]

                for i, name in enumerate(track_names):
                    if 'jaw' in name.lower():
                        tracks[:, i] *= self.jaw_multiplier
                    elif 'lips' in name.lower() or 'mouth' in name.lower():
                        tracks[:, i] *= self.lip_multiplier

            self.report({'INFO'}, "Applying animation to armature...")
            pipeline.apply_to_armature(
                    context.active_object,
                    tracks,
                    start_frame=context.scene.frame_start
                    )

            duration = phoneme_events[-1].end + 0.5
            context.scene.frame_end = int(duration * context.scene.render.fps) + 10

            self.report({'INFO'}, f"Lipsync complete ({duration:.2f}s, {len(phoneme_events)} phonemes)")
            return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, f"Failed: {e}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw(self, context):
        layout = self.layout

        layout.label(text="Audio Input:", icon='SPEAKER')
        layout.prop(self, "audio_path", text="")

        layout.separator()
        layout.prop(self, "use_transcript")

        if self.use_transcript:
            box = layout.box()
            box.label(text="Transcript:", icon='TEXT')
            box.prop(self, "transcript", text="")

        layout.separator()
        layout.label(text="JALI Parameters:", icon='SETTINGS')

        col = layout.column(align=True)
        col.prop(self, "jaw_multiplier", slider=True)
        col.prop(self, "lip_multiplier", slider=True)


#  Collect for get_classes (used by __init__.py registration) 
operators, other_classes = get_classes(sys.modules[__name__])
