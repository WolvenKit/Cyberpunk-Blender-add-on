from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

import bpy
from bpy.props import StringProperty
from bpy.types import Operator

def _import_loader():
    """Return the facial_setup_loader module, importing it if needed."""
    mod_name = "facial_setup_loader"
    pkg = __name__.rpartition(".")[0]
    if pkg:
        full_name = f"{pkg}.{mod_name}"
        if full_name in sys.modules:
            return sys.modules[full_name]
        try:
            import importlib
            return importlib.import_module(f".{mod_name}", pkg)
        except ImportError:
            pass
    # Fallback: bare import (standalone / dev scenario)
    if mod_name in sys.modules:
        return sys.modules[mod_name]
    import importlib
    return importlib.import_module(mod_name)


# Constants

# bpy.app.driver_namespace key
DRIVER_NS_KEY = "cp77_facial"

# Armature custom-property markers
PROP_BOUND       = "_cp77_bound"         # bool flag
PROP_SETUP_PATH  = "_cp77_setup_path"    # str
PROP_RIG_PATH    = "_cp77_rig_path"      # str
PROP_USED_BONES  = "_cp77_used_bones"    # JSON list of bone names (persistence)
PROP_NUM_TRACKS  = "_cp77_num_tracks"    # int

# Tracks whose valid range is [0, 2] instead of [0, 1]
_TRACKS_RANGE_2: frozenset[int] = frozenset({1, 2, 7, 8})

# Tracks that are solver *outputs* — registered read-only (no keyframing expected)
# These indices are computed from the tracksMapping at bind time.
# Stored as (start_inclusive, end_exclusive).
_OUTPUT_TRACK_GROUPS = ("lipsync_output", "wrinkles")


# Track segment container

@dataclass(frozen=True)
class TrackSegments:
    """Byte-precise track index ranges for each group in the rig track array."""
    num_tracks:          int   # total tracks in rig

    envelope_start:      int   # always 0
    envelope_end:        int   # = num_envelopes (13)

    main_start:          int   # = num_envelopes
    main_end:            int   # = num_envelopes + num_main_poses

    lipsync_ovr_start:   int
    lipsync_ovr_end:     int

    lipsync_out_start:   int
    lipsync_out_end:     int

    wrinkle_start:       int
    wrinkle_end:         int

    @classmethod
    def from_tracks_mapping(cls, tm: dict, num_tracks: int) -> "TrackSegments":
        ne  = tm["numEnvelopes"]        # 13
        nm  = tm["numMainPoses"]        # 141
        nlo = tm["numLipsyncOverrides"] # 86
        nw  = tm["numWrinkles"]         # 33

        env_s   = 0;          env_e  = ne
        main_s  = env_e;      main_e = main_s + nm
        lovr_s  = main_e;     lovr_e = lovr_s + nlo
        lout_s  = lovr_e;     lout_e = lout_s + nm   # output mirrors main count
        wrnk_s  = lout_e;     wrnk_e = wrnk_s + nw

        return cls(
            num_tracks       = num_tracks,
            envelope_start   = env_s,  envelope_end   = env_e,
            main_start       = main_s, main_end       = main_e,
            lipsync_ovr_start= lovr_s, lipsync_ovr_end= lovr_e,
            lipsync_out_start= lout_s, lipsync_out_end= lout_e,
            wrinkle_start    = wrnk_s, wrinkle_end    = wrnk_e,
        )

    def is_input(self, track_idx: int) -> bool:
        """Return True if this track is a keyframeable input (not solver output)."""
        return (
            self.envelope_start    <= track_idx < self.envelope_end    or
            self.main_start        <= track_idx < self.main_end        or
            self.lipsync_ovr_start <= track_idx < self.lipsync_ovr_end
        )

    def is_output(self, track_idx: int) -> bool:
        return (
            self.lipsync_out_start <= track_idx < self.lipsync_out_end or
            self.wrinkle_start     <= track_idx < self.wrinkle_end
        )


# Runtime cache

@dataclass
class BindingCache:
    """Per-armature runtime data held in driver_namespace."""
    setup:            object         # FacialSetupData (numpy)
    rig:              object         # RigData (numpy)
    used_bone_names:  List[str]      # rig bone names for each used_bone_index
    track_segments:   TrackSegments
    setup_path:       str
    rig_path:         str
    bind_time:        float          # time.time() at bind


def _get_ns() -> dict:
    """Return (creating if needed) the cp77_facial dict in driver_namespace."""
    ns = bpy.app.driver_namespace
    if DRIVER_NS_KEY not in ns:
        ns[DRIVER_NS_KEY] = {}
    return ns[DRIVER_NS_KEY]


def get_cache(armature_name: str) -> Optional[BindingCache]:
    """Return cached BindingCache for the named armature, or None."""
    return _get_ns().get(armature_name)


def _set_cache(armature_name: str, cache: BindingCache) -> None:
    _get_ns()[armature_name] = cache


def _del_cache(armature_name: str) -> None:
    ns = _get_ns()
    ns.pop(armature_name, None)


def is_bound(obj: bpy.types.Object) -> bool:
    """Return True if this armature object is currently bound."""
    return bool(obj.get(PROP_BOUND, False))


# Custom property helpers

_ENVELOPE_DESCS: Dict[int, str] = {
    0:  "Face envelope — master facial weight",
    1:  "Upper face envelope (0–2; multiplied against all upper-face poses)",
    2:  "Lower face envelope (0–2; multiplied against all lower-face poses)",
    3:  "Anti-stretch envelope",
    4:  "Lipsync envelope — master lipsync blend weight",
    5:  "Lipsync left-side envelope",
    6:  "Lipsync right-side envelope",
    7:  "JALI jaw slider (0–2; 1.0 = neutral, 2.0 = full open)",
    8:  "JALI lips slider (0–2; 1.0 = neutral, 2.0 = full pucker)",
    9:  "Muzzle lips (suppresses lips poses when > 0)",
    10: "Muzzle eyes (suppresses eye poses when > 0)",
    11: "Muzzle brows (suppresses brow poses when > 0)",
    12: "Muzzle eye directions (suppresses eye-direction poses when > 0)",
}


def _track_prop_range(track_idx: int, seg: TrackSegments):
    """Return (min, max, soft_min, soft_max) for a given track index."""
    if track_idx in _TRACKS_RANGE_2:
        return 0.0, 2.0, 0.0, 2.0
    return 0.0, 1.0, 0.0, 1.0


def _track_description(track_idx: int, track_name: str, seg: TrackSegments) -> str:
    if track_idx in _ENVELOPE_DESCS:
        return _ENVELOPE_DESCS[track_idx]
    if seg.main_start <= track_idx < seg.main_end:
        return f"Main pose weight — {track_name}"
    if seg.lipsync_ovr_start <= track_idx < seg.lipsync_ovr_end:
        return f"Lipsync override weight — {track_name}"
    if seg.lipsync_out_start <= track_idx < seg.lipsync_out_end:
        return f"[OUTPUT] Lipsync pose output — {track_name}"
    if seg.wrinkle_start <= track_idx < seg.wrinkle_end:
        return f"[OUTPUT] Wrinkle weight — {track_name}"
    return track_name


def register_track_properties(obj: bpy.types.Object, rig, seg: TrackSegments) -> None:
    def register_track_properties(obj: bpy.types.Object, rig, seg: TrackSegments) -> None:
        """
        Create a float custom property on `obj` for every track in the rig.

        Input tracks (envelopes, main poses, lipsync overrides) get full
        keyframeable float properties with correct min/max ranges.

        Output tracks (lipsync outputs, wrinkles) are registered read-only
        with a [0,1] range — the solver writes them each frame.
        """
        track_names = rig.track_names  # numpy object array of str

        for i, name in enumerate(track_names):
            name = str(name)
            current = obj.get(name)

            if current is None:
                obj[name] = 0.0
            elif not isinstance(current, float):
                obj[name] = float(current)

            mn, mx, smn, smx = _track_prop_range(i, seg)
            desc = _track_description(i, name, seg)

            ui = obj.id_properties_ui(name)

            try:
                ui.update(
                        min=float(mn),
                        max=float(mx),
                        soft_min=float(smn),
                        soft_max=float(smx),
                        description=desc,
                        )
            except TypeError as e:
                print(f"[CP77 Facial] ui.update skipped for '{name}': {e}")


def unregister_track_properties(obj: bpy.types.Object, rig) -> None:
    """Remove all facial track custom properties from the armature object."""
    track_names = rig.track_names
    for name in track_names:
        name = str(name)
        if name in obj:
            del obj[name]

    # Remove internal marker props
    for key in (PROP_BOUND, PROP_SETUP_PATH, PROP_RIG_PATH,
                PROP_USED_BONES, PROP_NUM_TRACKS):
        if key in obj:
            del obj[key]


# Bone validation and mapping

def build_used_bone_names(setup, rig) -> List[str]:
    """
    Resolve the bone name string for every index in setup.used_bone_indices.

    Returns a list parallel to setup.used_bone_indices where
    used_bone_names[i] = rig.bone_names[setup.used_bone_indices[i]].
    """
    bone_names = rig.bone_names   # numpy object array
    return [str(bone_names[idx]) for idx in setup.used_bone_indices]


def validate_bones(obj: bpy.types.Object, used_bone_names: List[str]) -> List[str]:
    """
    Check every name in used_bone_names exists as a pose bone.

    Returns a list of missing bone names (empty → all OK).
    """
    pose_bones = obj.pose.bones
    return [n for n in used_bone_names if n not in pose_bones]


# Persistence helpers (survive file save/load without cache)

def _persist_to_object(obj: bpy.types.Object, cache: BindingCache) -> None:
    """Write minimal binding info as custom properties so it survives a file reload."""
    obj[PROP_BOUND]      = True
    obj[PROP_SETUP_PATH] = cache.setup_path
    obj[PROP_RIG_PATH]   = cache.rig_path
    obj[PROP_USED_BONES] = json.dumps(cache.used_bone_names)
    obj[PROP_NUM_TRACKS] = cache.track_segments.num_tracks


def _paths_from_object(obj: bpy.types.Object):
    """Return (setup_path, rig_path) stored on the object, or (None, None)."""
    return (
        obj.get(PROP_SETUP_PATH),
        obj.get(PROP_RIG_PATH),
    )


def restore_cache_from_object(obj: bpy.types.Object) -> Optional[BindingCache]:
    """
    Attempt to rebuild the runtime cache from paths persisted on the armature.
    Called on file-load by the load_post handler in __init__.py.
    Returns the new BindingCache on success, None if files are missing or
    there is a parse error (caller should warn the user).
    """
    if not obj.get(PROP_BOUND):
        return None

    setup_path, rig_path = _paths_from_object(obj)
    if not setup_path or not rig_path:
        return None
    if not os.path.isfile(setup_path) or not os.path.isfile(rig_path):
        return None

    try:
        loader = _import_loader()
        rig    = loader.load_rig(rig_path)
        setup  = loader.load_facial_setup(setup_path, rig)
        seg    = TrackSegments.from_tracks_mapping(
            {"numEnvelopes": setup.num_envelope_tracks,
             "numMainPoses": setup.num_main_poses,
             "numLipsyncOverrides": setup.num_lipsync_overrides,
             "numWrinkles": setup.num_wrinkle_tracks},
            rig.num_tracks,
        )
        used_bone_names = build_used_bone_names(setup, rig)
        cache = BindingCache(
            setup           = setup,
            rig             = rig,
            used_bone_names = used_bone_names,
            track_segments  = seg,
            setup_path      = setup_path,
            rig_path        = rig_path,
            bind_time       = time.time(),
        )
        _set_cache(obj.name, cache)
        return cache
    except Exception as e:
        print(f"[CP77 Facial] Cache restore failed for '{obj.name}': {e}")
        return None


# Operators

class FACIAL_OT_Bind(Operator):
    """Load CP77 .facialsetup + animRig JSONs and bind them to the active armature"""
    bl_idname  = "cp77_facial.bind"
    bl_label   = "Bind Facial Setup"
    bl_options = {"REGISTER", "UNDO"}

    setup_path: StringProperty(
        name        = "Facial Setup JSON",
        description = "Path to the WolvenKit-exported .facialsetup JSON file",
        subtype     = "FILE_PATH",
        default     = "",
    )  # type: ignore

    rig_path: StringProperty(
        name        = "Rig JSON",
        description = "Path to the WolvenKit-exported animRig JSON file",
        subtype     = "FILE_PATH",
        default     = "",
    )  # type: ignore

    # Poll: only run on a selected armature object
    @classmethod
    def poll(cls, context):
        return (
            context.object is not None and
            context.object.type == "ARMATURE"
        )

    # Invoke: open a properties dialog so the user can enter paths
    def invoke(self, context, event):
        # Pre-populate from scene properties if available (set by the panel)
        scene_props = getattr(context.scene, "cp77_facial", None)
        if scene_props and not self.setup_path:
            self.setup_path = getattr(scene_props, "bound_facial_path", "")
        if scene_props and not self.rig_path:
            self.rig_path = getattr(scene_props, "bound_rig_path", "")

        # Fall back to paths already stored on the object
        if not self.setup_path or not self.rig_path:
            sp, rp = _paths_from_object(context.object)
            if sp and not self.setup_path:
                self.setup_path = sp
            if rp and not self.rig_path:
                self.rig_path = rp

        return context.window_manager.invoke_props_dialog(self, width=600)

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.prop(self, "setup_path", icon="FILE_BLEND")
        layout.prop(self, "rig_path",   icon="ARMATURE_DATA")

    # Execute: parse → validate → register props → cache
    def execute(self, context):
        obj = context.object

        #  Path validation 
        sp = bpy.path.abspath(self.setup_path)
        rp = bpy.path.abspath(self.rig_path)

        if not sp:
            self.report({"ERROR"}, "No facial setup path specified")
            return {"CANCELLED"}
        if not os.path.isfile(sp):
            self.report({"ERROR"}, f"Facial setup file not found:\n{sp}")
            return {"CANCELLED"}
        if not rp:
            self.report({"ERROR"}, "No rig path specified")
            return {"CANCELLED"}
        if not os.path.isfile(rp):
            self.report({"ERROR"}, f"Rig file not found:\n{rp}")
            return {"CANCELLED"}

        #  Parse 
        t0 = time.time()
        try:
            loader = _import_loader()
        except ImportError as e:
            self.report({"ERROR"}, f"facial_setup_loader not found: {e}")
            return {"CANCELLED"}

        try:
            rig   = loader.load_rig(rp)
        except Exception as e:
            self.report({"ERROR"}, f"Failed to parse rig JSON: {e}")
            return {"CANCELLED"}

        try:
            setup = loader.load_facial_setup(sp, rig)
        except Exception as e:
            self.report({"ERROR"}, f"Failed to parse facial setup JSON: {e}")
            return {"CANCELLED"}

        parse_ms = (time.time() - t0) * 1000

        #  Build track segments 
        seg = TrackSegments.from_tracks_mapping(
            {
                "numEnvelopes":        setup.num_envelope_tracks,
                "numMainPoses":        setup.num_main_poses,
                "numLipsyncOverrides": setup.num_lipsync_overrides,
                "numWrinkles":         setup.num_wrinkle_tracks,
            },
            rig.num_tracks,
        )

        #  Bone validation 
        used_bone_names = build_used_bone_names(setup, rig)
        missing = validate_bones(obj, used_bone_names)
        if missing:
            sample = ", ".join(missing[:5])
            extra  = f" (and {len(missing) - 5} more)" if len(missing) > 5 else ""
            self.report(
                {"WARNING"},
                f"{len(missing)} bones not found in armature: {sample}{extra}. "
                "Solve will skip missing bones."
            )

        #  Register custom properties 
        t1 = time.time()
        register_track_properties(obj, rig, seg)
        prop_ms = (time.time() - t1) * 1000

        #  Build and store cache 
        cache = BindingCache(
            setup           = setup,
            rig             = rig,
            used_bone_names = used_bone_names,
            track_segments  = seg,
            setup_path      = sp,
            rig_path        = rp,
            bind_time       = time.time(),
        )
        _set_cache(obj.name, cache)

        #  Persist paths + markers on the object 
        _persist_to_object(obj, cache)

        #  Update scene properties if they exist 
        scene_props = getattr(context.scene, "cp77_facial", None)
        if scene_props:
            scene_props.bound_facial_path = sp
            scene_props.bound_rig_path    = rp

        total_ms = (time.time() - t0) * 1000
        self.report(
            {"INFO"},
            f"Bound '{obj.name}': "
            f"{rig.num_bones} bones, {rig.num_tracks} tracks, "
            f"{len(setup.used_bone_indices)} used bones "
            f"({len(missing)} missing). "
            f"Parse {parse_ms:.0f}ms · Props {prop_ms:.0f}ms · Total {total_ms:.0f}ms"
        )
        return {"FINISHED"}



class FACIAL_OT_Unbind(Operator):
    """Remove facial setup binding and all track properties from the active armature"""
    bl_idname  = "cp77_facial.unbind"
    bl_label   = "Unbind Facial Setup"
    bl_options = {"REGISTER", "UNDO"}

    keep_properties: bpy.props.BoolProperty(
        name        = "Keep Track Properties",
        description = "Keep the float custom properties on the object (preserves keyframes)",
        default     = False,
    )  # type: ignore

    @classmethod
    def poll(cls, context):
        return (
            context.object is not None and
            context.object.type == "ARMATURE" and
            is_bound(context.object)
        )

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=360)

    def draw(self, context):
        self.layout.prop(self, "keep_properties")

    def execute(self, context):
        obj = context.object
        cache = get_cache(obj.name)

        # Stop solver if running (solver module sets scene property)
        scene_props = getattr(context.scene, "cp77_facial", None)
        if scene_props and getattr(scene_props, "solver_active", False):
            scene_props.solver_active = False
            # The solver's update callback will handle handler removal.

        if not self.keep_properties and cache is not None:
            unregister_track_properties(obj, cache.rig)
        else:
            # Just remove the internal markers even if keeping float props
            for key in (PROP_BOUND, PROP_SETUP_PATH, PROP_RIG_PATH,
                        PROP_USED_BONES, PROP_NUM_TRACKS):
                if key in obj:
                    del obj[key]

        _del_cache(obj.name)
        self.report({"INFO"}, f"Unbound facial setup from '{obj.name}'")
        return {"FINISHED"}



class FACIAL_OT_RebuildCache(Operator):
    """Reload the facial setup JSON files and rebuild the runtime cache (no UI change)"""
    bl_idname  = "cp77_facial.rebuild_cache"
    bl_label   = "Rebuild Cache"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        return (
            context.object is not None and
            context.object.type == "ARMATURE" and
            is_bound(context.object)
        )

    def execute(self, context):
        obj    = context.object
        result = restore_cache_from_object(obj)
        if result is None:
            self.report({"ERROR"}, "Cache rebuild failed — check file paths")
            return {"CANCELLED"}
        self.report({"INFO"}, f"Cache rebuilt for '{obj.name}'")
        return {"FINISHED"}


# Read-back helpers (used by solver and preview modules)

def read_tracks(obj: bpy.types.Object, cache: BindingCache):
    """
    Read all track custom properties from the armature object into a
    numpy float32 array of length rig.num_tracks.

    Missing properties (e.g. not yet created) default to 0.0.
    """
    import numpy as np
    track_names = cache.rig.track_names   # numpy object array
    arr = np.zeros(cache.track_segments.num_tracks, dtype=np.float32)
    for i, name in enumerate(track_names):
        v = obj.get(str(name), 0.0)
        arr[i] = float(v)
    return arr


def write_output_tracks(obj: bpy.types.Object, cache: BindingCache, out_tracks) -> None:
    """
    Write solver output tracks (lipsync outputs + wrinkles) back to the
    armature object's custom properties.

    `out_tracks` is a numpy float32 array of length num_tracks.
    Only writes the output segments — input tracks are left unchanged.
    """
    seg        = cache.track_segments
    track_names = cache.rig.track_names

    for i in range(seg.lipsync_out_start, seg.lipsync_out_end):
        obj[str(track_names[i])] = float(out_tracks[i])

    for i in range(seg.wrinkle_start, seg.wrinkle_end):
        obj[str(track_names[i])] = float(out_tracks[i])


# Registration

_CLASSES = (
    FACIAL_OT_Bind,
    FACIAL_OT_Unbind,
    FACIAL_OT_RebuildCache,
)


def register():
    for cls in _CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(_CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass
