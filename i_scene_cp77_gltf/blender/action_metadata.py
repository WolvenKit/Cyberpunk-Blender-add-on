from __future__ import annotations

import copy
import math

import bpy
import numpy as np

from ..animation.domain.clip.additive import is_additive_animation_type
from ..animation.model.clip.binding import (
    ActionBinding,
    TrackBinding,
    create_track_binding,
)
from ..animation.model.clip.metadata import (
    ACTION_DEFAULTS,
    ANIMATION_EXTRAS_SNAPSHOT_KEY,
    ANIMATION_SCHEMA,
    FPS,
    IMPORTED_NAME_KEY,
    OPTIMIZATION_HINT_DEFAULTS,
    SKIN_EXTRAS_SNAPSHOT_KEY,
    SOURCE_CHANNELS_SNAPSHOT_KEY,
    SOURCE_NAME_KEY,
    SOURCE_REST_SNAPSHOT_KEY,
    decode_json_snapshot,
    indexed_strings,
    normalize_animation_extras,
)
from ..assetio.values import json_text, plain_value
from ..core.log import get_logger, log_once
from .event_storage import load_events_to_collection
from .transactions import track_created_datablock

_LOG = get_logger(__name__)


def action_playback_frame_domain(action) -> tuple[float, float]:
    try:
        start = float(action.frame_range[0])
        end = float(action.frame_range[1])
    except (AttributeError, TypeError, ValueError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("action_playback_frame_domain 1", type(error).__name__),
            "action playback frame domain: fell back after %s",
            error,
            exc_info=True,
        )
        start = 0.0
        end = 0.0

    try:
        duration_seconds = float(action.get("cp77_direct_anim_duration_seconds"))
    except (AttributeError, TypeError, ValueError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("action_playback_frame_domain 2", type(error).__name__),
            "action playback frame domain: fell back after %s",
            error,
            exc_info=True,
        )
        duration_seconds = -1.0
    if math.isfinite(duration_seconds) and duration_seconds >= 0.0:
        duration_frames = duration_seconds * FPS
        nearest = round(duration_frames)
        if abs(duration_frames - nearest) <= 1e-5:
            duration_frames = float(nearest)
        end = max(end, start + duration_frames)

    try:
        frame_count = float(action.get("cp77_direct_anim_frame_count"))
    except (AttributeError, TypeError, ValueError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("action_playback_frame_domain 3", type(error).__name__),
            "action playback frame domain: fell back after %s",
            error,
            exc_info=True,
        )
        frame_count = -1.0
    if math.isfinite(frame_count) and frame_count >= 1.0:
        end = max(end, start + frame_count - 1.0)

    if end <= start:
        end = start + 1.0
    return start, end


def action_playback_frame_bounds(action) -> tuple[int, int]:
    start, end = action_playback_frame_domain(action)
    return math.floor(start), math.ceil(end)


def action_is_additive(action) -> bool:
    """Whether the action's animationType is one of the additive types"""
    return is_additive_animation_type(action.get("animationType", "Normal"))


def store_json_snapshot(owner, key: str, value) -> None:
    owner[key] = json_text(value)


def load_json_snapshot(owner, key: str) -> dict:
    return decode_json_snapshot(owner.get(key) if owner is not None else None)


def ensure_action_defaults(action) -> None:
    for key, default in ACTION_DEFAULTS.items():
        if key not in action:
            action[key] = copy.deepcopy(default)

    action["schema"] = copy.deepcopy(ANIMATION_SCHEMA)

    hints = plain_value(action.get("optimizationHints"))
    if not isinstance(hints, dict):
        action["optimizationHints"] = copy.deepcopy(OPTIMIZATION_HINT_DEFAULTS)
    else:
        for key, default in OPTIMIZATION_HINT_DEFAULTS.items():
            if key not in hints:
                hints[key] = copy.deepcopy(default)
        action["optimizationHints"] = hints


def apply_action_extras(action, extras, *, load_events=True) -> bool:
    """Store normalized animation extras on action"""
    normalized = normalize_animation_extras(
        extras,
        label=f"Animation {getattr(action, 'name', '<unnamed>')!r} extras",
    )
    store_json_snapshot(action, ANIMATION_EXTRAS_SNAPSHOT_KEY, normalized)
    # An ID property assignment copies the value into Blender, so the defaults stay untouched without a deep copy.
    for key, default in ACTION_DEFAULTS.items():
        action[key] = normalized.get(key, default)

    events = normalized["animEvents"]
    if events is None:
        if "animEvents" in action:
            del action["animEvents"]
    else:
        action["animEvents"] = events

    if not load_events:
        return False
    try:
        return load_events_to_collection(action)
    except (AttributeError, RuntimeError, TypeError, ValueError) as error:
        _LOG.warning(
            "Could not load animation events for %r: %s",
            action.name,
            error,
            exc_info=True,
        )
        return False


def apply_skin_extras(armature, extras) -> None:
    if armature is None or getattr(armature, "type", None) != "ARMATURE":
        return
    if not isinstance(extras, dict):
        return
    store_json_snapshot(armature, SKIN_EXTRAS_SNAPSHOT_KEY, extras)
    rig_path = extras.get("rigPath")
    if rig_path is not None:
        armature["rigPath"] = plain_value(rig_path)
    bone_names = extras.get("boneNames")
    if bone_names:
        armature["boneNames"] = [str(value) for value in bone_names]
    parent_indices = extras.get("boneParentIndexes")
    if parent_indices:
        armature["boneParentIndexes"] = [int(value) for value in parent_indices]
    track_names = extras.get("trackNames")
    if track_names is not None:
        armature["trackNames"] = {
            str(index): str(name) for index, name in enumerate(track_names)
        }


def clip_action_name(clip_name: str, armature) -> str:
    """The clip's own name, or the name qualified by the armature when another Action already has it"""
    if bpy.data.actions.get(clip_name) is None:
        return clip_name
    return f"{clip_name} [{armature.name}]"


def new_clip_action(clip_name: str, armature):
    """A new Action for the clip on armature, tracked by the running import and kept by a fake user"""
    action = track_created_datablock(
        "actions", bpy.data.actions.new(clip_action_name(clip_name, armature))
    )
    action.use_fake_user = True
    return action


def store_action_source(
    action, *, source_name: str, skin=None, source_rest=None, source_channels=None
) -> None:
    """Record source identity separately from Blender's unique datablock names"""
    action[SOURCE_NAME_KEY] = str(source_name)
    action[IMPORTED_NAME_KEY] = str(action.name)
    if isinstance(skin, dict):
        store_json_snapshot(action, SKIN_EXTRAS_SNAPSHOT_KEY, skin)
    if isinstance(source_rest, dict):
        store_json_snapshot(action, SOURCE_REST_SNAPSHOT_KEY, source_rest)
    if isinstance(source_channels, dict):
        store_json_snapshot(action, SOURCE_CHANNELS_SNAPSHOT_KEY, source_channels)


def action_export_name(action) -> str:
    """Preserve imported clip identity until the user explicitly renames its Action"""
    current_name = str(action.name)
    source_name = action.get(SOURCE_NAME_KEY)
    imported_name = action.get(IMPORTED_NAME_KEY)
    if isinstance(source_name, str) and source_name and current_name == imported_name:
        return source_name
    return current_name


def armature_track_names(armature) -> list[str]:
    if armature is None or getattr(armature, "type", None) != "ARMATURE":
        return []
    for owner in (armature, getattr(armature, "data", None)):
        if owner is None:
            continue
        names = indexed_strings(owner.get("trackNames"))
        if names:
            return names
    return []


def armature_skin_extras(armature) -> dict:
    if armature is None or getattr(armature, "type", None) != "ARMATURE":
        return {}
    skin = load_json_snapshot(armature, SKIN_EXTRAS_SNAPSHOT_KEY)
    skin.setdefault("rigPath", str(armature.get("rigPath", "")))
    bone_names = indexed_strings(armature.get("boneNames"))
    if bone_names:
        skin.setdefault("boneNames", bone_names)
    parents = armature.get("boneParentIndexes")
    if parents is not None:
        skin.setdefault("boneParentIndexes", [int(value) for value in parents])
    track_names = armature_track_names(armature)
    if track_names:
        skin.setdefault("trackNames", track_names)
    return skin


def action_skin_extras(action, armature=None) -> dict:
    snapshot = load_json_snapshot(action, SKIN_EXTRAS_SNAPSHOT_KEY)
    return snapshot if snapshot else armature_skin_extras(armature)


def action_source_rest(action, armature=None) -> dict:
    snapshot = load_json_snapshot(action, SOURCE_REST_SNAPSHOT_KEY)
    return (
        snapshot if snapshot else load_json_snapshot(armature, SOURCE_REST_SNAPSHOT_KEY)
    )


def action_track_names(action, armature=None, skin=None) -> list[str]:
    source = skin if isinstance(skin, dict) else action_skin_extras(action, armature)
    if isinstance(source, dict) and "trackNames" in source:
        return indexed_strings(source.get("trackNames"))
    return armature_track_names(armature)


def resolve_track_binding(action=None, armature=None, skin=None) -> TrackBinding:
    return create_track_binding(action_track_names(action, armature, skin))


def resolve_action_binding(action, armature=None) -> ActionBinding:
    skin = action_skin_extras(action, armature)
    return ActionBinding(
        extras=load_json_snapshot(action, ANIMATION_EXTRAS_SNAPSHOT_KEY),
        skin=skin,
        source_rest=action_source_rest(action, armature),
        tracks=resolve_track_binding(action, armature, skin),
    )


def action_frame_range(action) -> tuple[float, float]:
    start, end = (float(value) for value in action.frame_range)
    duration = action.get("cp77_direct_anim_duration_seconds")
    if duration is not None:
        duration = float(duration)
        if not np.isfinite(duration) or duration < 0.0:
            raise ValueError("The action has an invalid source duration.")
        end = max(end, start + duration * FPS)
    if not np.isfinite(start) or not np.isfinite(end) or end < start:
        raise ValueError("The action has an invalid frame range.")
    return start, end
