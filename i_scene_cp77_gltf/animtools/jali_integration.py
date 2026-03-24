import bpy
import numpy as np
from typing import List, Dict, Tuple, Any

from .jali import PhonemeEvent, CoarticulationEngine, JALIAudioAnalyzer
from .tracks import get_action_fcurves, _bulk_set_keyframes
from .bartmoss_math import smoothstep

VISEME_TO_OVERRIDE_TRACKS = {
    'AHH': {'lipsync_jaw_override': 1.0, 'lipsync_mouth_open_override': 0.8},
    'EEE': {'lipsync_jaw_override': 0.5, 'lipsync_mouth_wide_override': 1.0, 'lipsync_lip_spread_override': 0.8},
    'OOO': {'lipsync_jaw_override': 0.4, 'lipsync_mouth_narrow_override': 1.0, 'lipsync_lip_funnel_override': 0.9},
    'R': {'lipsync_jaw_override': 0.3, 'lipsync_mouth_narrow_override': 0.6},
    'L': {'lipsync_jaw_override': 0.3, 'lipsync_tongue_override': 0.7},
    'W': {'lipsync_jaw_override': 0.2, 'lipsync_mouth_narrow_override': 1.0, 'lipsync_lip_pucker_override': 1.0},
    'MMM': {'lipsync_jaw_override': 0.0, 'lipsync_lip_closure_override': 1.0, 'lipsync_lip_press_override': 1.0},
    'FFF': {'lipsync_jaw_override': 0.1, 'lipsync_lip_bite_override': 1.0},
    'TTH': {'lipsync_jaw_override': 0.15, 'lipsync_tongue_override': 0.8},
    'SSS': {'lipsync_jaw_override': 0.05, 'lipsync_mouth_narrow_override': 0.4},
    'SHH': {'lipsync_jaw_override': 0.05, 'lipsync_mouth_narrow_override': 0.7, 'lipsync_lip_pucker_override': 0.6},
    }

VISEME_TO_LIPSYNC_POSES = {
    'AHH': {'lipsync_pose_mouth_open': 0.8, 'lipsync_pose_jaw_drop': 0.7},
    'EEE': {'lipsync_pose_smile': 0.7, 'lipsync_pose_lip_spread': 0.8},
    'OOO': {'lipsync_pose_pucker': 0.9, 'lipsync_pose_lip_round': 0.85},
    'W': {'lipsync_pose_pucker': 1.0},
    'MMM': {'lipsync_pose_lip_close': 1.0},
    'FFF': {'lipsync_pose_lip_bite': 1.0},
    'SSS': {'lipsync_pose_teeth_close': 0.8},
    'SHH': {'lipsync_pose_sh_shape': 0.9},
    }


class JALIToCp77Bridge:
    def __init__(self, rig, setup):
        self.rig = rig
        self.setup = setup
        self.track_map = {str(n): i for i, n in enumerate(rig.track_names)}

        # Resolve dynamic mappings from setup if provided, else defaults
        self.override_map = getattr(
            setup, 'overrideToMainPoseMap', {
                    'lipsync_jaw_override': 'jaw_open',
                    'lipsync_mouth_open_override': 'mouth_open',
                    'lipsync_mouth_wide_override': 'mouth_wide',
                    'lipsync_mouth_narrow_override': 'mouth_narrow',
                    'lipsync_lip_spread_override': 'lip_corner_wide',
                    'lipsync_lip_funnel_override': 'lip_funnel',
                    'lipsync_lip_pucker_override': 'lip_pucker',
                    'lipsync_lip_closure_override': 'lip_close',
                    'lipsync_lip_press_override': 'lip_press',
                    'lipsync_lip_bite_override': 'lip_bite',
                    'lipsync_tongue_override': 'tongue_out',
                    }
            )

    def get_track_index(self, logical_name: str, is_override: bool = False) -> int:
        """Resolve a JALI logical track name to the actual Rig JSON track index."""
        cp_name = self.override_map.get(logical_name, logical_name)
        return self.track_map.get(cp_name, -1)


class JALIAnimationPipeline:
    """Orchestrates JALI curve generation and bakes directly to Blender FCurves."""

    def __init__(self, rig, setup, fps: float):
        self.rig = rig
        self.setup = setup
        self.fps = fps
        self.bridge = JALIToCp77Bridge(rig, setup)

    def generate_animation(self, phonemes: List[PhonemeEvent], audio_path: str = "") -> Tuple[np.ndarray, None, None]:
        if audio_path:
            analyzer = JALIAudioAnalyzer()
            analyzer.compute_jali_values(audio_path, phonemes)

        coart = CoarticulationEngine(self.fps)
        phonemes = coart.apply_coarticulation(phonemes)

        duration = phonemes[-1].end + 0.5 if phonemes else 1.0
        n_frames = int(duration * self.fps) + 10
        times = np.linspace(0, duration, n_frames)

        # [num_frames, num_tracks] NumPy array
        tracks = np.zeros((n_frames, self.rig.num_tracks), dtype=np.float32)

        # Base override tracks start at 1.0 (no suppression). Positional tracks start at 0.0.
        for logical_name in self.bridge.override_map.keys():
            idx = self.bridge.get_track_index(logical_name, is_override=True)
            if idx >= 0:
                tracks[:, idx] = 1.0

        for phoneme in phonemes:
            t_attack = phoneme.start - phoneme.onset
            t_apex = phoneme.start
            t_sustain = phoneme.start + (0.75 * phoneme.duration)
            t_decay = phoneme.end + phoneme.offset

            viseme = phoneme.label
            override_weights = VISEME_TO_OVERRIDE_TRACKS.get(viseme, {})
            pose_weights = VISEME_TO_LIPSYNC_POSES.get(viseme, {})

            for frame in range(n_frames):
                t = times[frame]
                envelope_value = 0.0

                if t_attack <= t < t_apex:
                    envelope_value = smoothstep(0.0, 1.0, (t - t_attack) / phoneme.onset) * phoneme.power
                elif t_apex <= t < t_sustain:
                    envelope_value = phoneme.power
                elif t_sustain <= t < t_decay:
                    envelope_value = smoothstep(0.0, 1.0, 1.0 - ((t - t_sustain) / (t_decay - t_sustain))) * phoneme.power

                if envelope_value <= 0.0:
                    continue

                # 1. Apply Overrides (Modulation)
                for override_track, weight in override_weights.items():
                    idx = self.bridge.get_track_index(override_track, is_override=True)
                    if idx < 0: continue

                    modulated = weight * (
                        phoneme.ja_value if 'jaw' in override_track else phoneme.li_value) * envelope_value
                    override_value = 1.0 + (modulated - 1.0) * envelope_value
                    tracks[frame, idx] = min(tracks[frame, idx], override_value)

                # 2. Apply Lipsync Poses (Additive)
                for pose_track, weight in pose_weights.items():
                    idx = self.bridge.get_track_index(pose_track, is_override=False)
                    if idx < 0: continue

                    modulated = weight * (
                        phoneme.ja_value if 'jaw' in pose_track else phoneme.li_value) * envelope_value
                    tracks[frame, idx] = max(tracks[frame, idx], modulated)

                # 3. Apply Base JALI Limits (Jaw 1-2, Lips 0-2)
                jaw_idx = self.bridge.get_track_index('jaliJaw')
                lip_idx = self.bridge.get_track_index('jaliLips')
                env_idx = self.bridge.get_track_index('lipSyncEnvelope')

                if jaw_idx >= 0:
                    tracks[frame, jaw_idx] = max(tracks[frame, jaw_idx], 1.0 + (phoneme.ja_value * envelope_value))
                if lip_idx >= 0:
                    tracks[frame, lip_idx] = max(tracks[frame, lip_idx], 1.0 + (phoneme.li_value * envelope_value))
                if env_idx >= 0:
                    tracks[frame, env_idx] = 1.0  # Activate lipsync mode

        return tracks, None, None

    def apply_to_armature(self, obj: bpy.types.Object, tracks: np.ndarray, start_frame: int = 1) -> None:
        if not obj.animation_data:
            obj.animation_data_create()
        if not obj.animation_data.action:
            obj.animation_data.action = bpy.data.actions.new(name="JALI_Lipsync")

        action = obj.animation_data.action
        fcurves = get_action_fcurves(action)
        if fcurves is None:
            return

        num_frames, num_tracks = tracks.shape
        frames = list(range(start_frame, start_frame + num_frames))

        # Find which tracks actually have animation data to insert
        for i in range(num_tracks):
            col_data = tracks[:, i]
            # Skip if track is completely neutral (0.0 for poses, 1.0 for overrides/jaw limits)
            if np.all(col_data == 0.0) or np.all(col_data == 1.0):
                continue

            name_str = str(self.rig.track_names[i])
            if name_str not in obj:
                obj[name_str] = float(col_data[0])

            dp = f'["{name_str}"]'
            fc = fcurves.find(data_path=dp)
            if fc is not None:
                fc.keyframe_points.clear()
                fcurves.remove(fc)

            fc = fcurves.new(data_path=dp)
            _bulk_set_keyframes(fc, frames, col_data.tolist())

        obj.update_tag(refresh={'DATA'})