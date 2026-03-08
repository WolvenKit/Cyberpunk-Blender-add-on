import bpy
import math
from math import ceil, floor
from collections import Counter, defaultdict
from .compat import get_action_fcurves

_DEF_FPS = 30.0
_VERBOSE = False


def _set_verbose(val: bool):
    global _VERBOSE
    _VERBOSE = bool(val)


def _vprint(msg: str):
    if _VERBOSE:
        print(msg)


def _iget(d, key, default=None):
    """Getter for IDPropertyGroup/dict/attrs."""
    try:
        return d.get(key, default)
    except AttributeError:
        try:
            return d[key]
        except Exception:
            return getattr(d, key, default)


#  Track-name resolution from armature skin extras

def _get_track_name_map(armature=None):
    candidates = [armature] if armature else [
        obj for obj in bpy.data.objects
        if obj.type == 'ARMATURE' and (
            obj.get("trackNames") is not None or obj.get("numTrackNames", 0) > 0
        )
    ]
    for arm in candidates:
        if arm is None:
            continue

        # Current format: single dict {"0": name, "1": name, …}
        tn = arm.get("trackNames")
        if tn is not None and hasattr(tn, 'keys'):
            return {int(k): str(v) for k, v in tn.items()}

        # Legacy format: numTrackNames + trackName_{i}
        num = arm.get("numTrackNames", 0)
        if num > 0:
            return {
                i: arm.get(f"trackName_{i}", f"T{i:02d}")
                for i in range(num)
            }
    return {}


def _track_prop_name(index, name_map):
    """Return the custom-property name for a track index.

    Uses the real track name from *name_map* when available, falling back
    to the legacy ``T00`` / ``T01`` format.
    """
    if name_map and index in name_map:
        return name_map[index]
    return f"T{index:02d}"


def _track_data_path(prop_name):
    """Return the FCurve data-path string for a track property name."""
    return f'["{prop_name}"]'


#  Bulk keyframe helpers  (foreach_set is ~10-50× faster than per-kf .co =)

def _bulk_set_keyframes(fc, frames, values, interpolation=None):
    """Insert keyframes into *fc* using the fast ``foreach_set`` path.

    *frames*        – sequence of frame numbers (same length as *values*).
    *values*        – sequence of values.
    *interpolation* – optional Blender interpolation string to apply to
                      every keyframe (e.g. ``'CONSTANT'``).  When *None*
                      the default (``'BEZIER'``) is kept.
    """
    n = len(frames)
    if n == 0:
        return
    fc.keyframe_points.add(n)
    coords = [0.0] * (n * 2)
    for i in range(n):
        coords[i * 2] = frames[i]
        coords[i * 2 + 1] = values[i]
    fc.keyframe_points.foreach_set('co', coords)
    if interpolation is not None:
        for kp in fc.keyframe_points:
            kp.interpolation = interpolation
    fc.update()


#  Export – Transfer (& Remove) Track FCurves to Action Extras

def export_anim_tracks(action, armature=None):
    """Transfer track FCurves from *action* back into IDProperty key lists.

    Track names are resolved from the *armature* (the rig-level source of
    truth).  When *armature* is ``None`` the function auto-discovers it the
    same way :func:`import_anim_tracks` does.  Falls back to a legacy
    ``["T…`` prefix scan when no rig-level mapping exists.
    """
    obj = {"trackKeys": [], "constTrackKeys": []}
    num_exported = 0
    fcurves = get_action_fcurves(action)
    if fcurves is None:
        _vprint('export_anim_tracks: no fcurves available')
        return

    # Resolve track-index → property-name from the armature
    name_map = _get_track_name_map(armature)

    track_fc_info = []  # [(track_index, data_path, fc), ...]

    if name_map:
        # Named tracks from rig – look up each known track by its data-path
        for idx, prop_name in name_map.items():
            dp = _track_data_path(prop_name)
            fc = fcurves.find(data_path=dp)
            if fc is not None:
                track_fc_info.append((idx, dp, fc))
    else:
        # Legacy fallback: scan for data-paths starting with '["T'
        for fc in fcurves:
            dp = fc.data_path
            if dp.startswith('["T') and dp.endswith('"]'):
                prop_name = dp[2:-2]  # strip ["..."]
                try:
                    idx = int(prop_name[1:])
                except ValueError:
                    continue
                track_fc_info.append((idx, dp, fc))

    for track_index, t_datapath, fc in track_fc_info:
        if fc and len(fc.keyframe_points) > 0:
            n_kf = len(fc.keyframe_points)
            # Bulk-read values via foreach_get
            cos = [0.0] * (n_kf * 2)
            fc.keyframe_points.foreach_get('co', cos)
            kf_vals = [cos[i * 2 + 1] for i in range(n_kf)]
            tmin = min(kf_vals)
            tmax = max(kf_vals)
            tavg = sum(kf_vals) / n_kf
            if tavg == 0 or tmin == tmax:
                obj["constTrackKeys"].append({
                    'trackIndex': track_index, 'value': tavg, 'time': 0.0
                })
                num_exported += 1
            else:
                num_exported += n_kf
                for i in range(n_kf):
                    obj["trackKeys"].append({
                        'trackIndex': track_index,
                        'value': cos[i * 2 + 1],
                        'time': cos[i * 2] / 30.0,
                    })
            fc.keyframe_points.clear()
            fc.update()
        if fc:
            fcurves.remove(fc)

    action['trackKeys'] = obj["trackKeys"]
    action['constTrackKeys'] = obj["constTrackKeys"]
    # Preserve optimizationHints from import; only set defaults if missing
    if "optimizationHints" not in action:
        action["optimizationHints"] = {"preferSIMD": False, "maxRotationCompression": 0}
    remove_track_action_group(action)
    _vprint(f'{num_exported} Tracks Exported')


#  Custom properties on armatures for track channels

def add_track_properties(track_properties=[]):
    """Create custom float properties for tracks on all armatures."""
    armature_list = [obj for obj in bpy.data.objects if obj.type == 'ARMATURE']
    for armature in armature_list:
        for prop_name in track_properties:
            try:
                if prop_name not in armature:
                    armature[prop_name] = 0.0
                rna = armature.id_properties_ui(prop_name)
                rna.update(
                    description="",
                    default=0.0,
                    min=-3.40282e+38,
                    max=3.40282e+38,
                    soft_min=-3.40282e+38,
                    soft_max=3.40282e+38,
                    subtype='NONE',
                )
                try:
                    armature.property_overridable_library_set(f'["{prop_name}"]', True)
                except Exception:
                    pass
            except Exception as e:
                print(f"Error creating custom track property ({prop_name}) "
                      f"on Armature [{armature.name}]: {e}")


#  Track action group helpers

def _get_action_groups(action):
    """Return the groups collection for *action*.

    Blender 4.x: ``action.groups``
    Blender 5.x: groups live on the channelbag, not the action itself.
    """
    if hasattr(action, 'groups'):
        return action.groups
    # 5.x layered actions – groups are on the channelbag
    try:
        for layer in action.layers:
            for strip in layer.strips:
                for cb in strip.channelbags:
                    if hasattr(cb, 'groups'):
                        return cb.groups
    except Exception:
        pass
    return None


def get_track_action_group_name():
    return "Track Keys"


def remove_track_action_group(action):
    groups = _get_action_groups(action)
    if groups is None:
        return
    try:
        group_name = get_track_action_group_name()
        group_id = groups.find(group_name)
        if group_id >= 0:
            groups.remove(groups[group_id])
    except Exception as e:
        print(f"Error removing custom track action group: {e}")


def add_track_action_group(action):
    groups = _get_action_groups(action)
    if groups is None:
        return None
    try:
        group_name = get_track_action_group_name()
        group_id = groups.find(group_name)
        if group_id < 0:
            return groups.new(group_name)
        else:
            return groups[group_id]
    except Exception as e:
        print(f"Error adding custom track action group: {e}")
        return None


#  Import – Create FCurves for anim tracks (with frame-alignment fix)

def import_anim_tracks(action):
    track_keys = action.get("trackKeys", [])
    const_track_keys = action.get("constTrackKeys", [])

    if not track_keys and not const_track_keys:
        return

    #  Pre-group all key data by track index  (O(n) vs old O(n×m))
    t_by_idx = defaultdict(list)       # {track_index: [[time, value], ...]}
    ct_by_idx = defaultdict(list)      # {track_index: [value, ...]}

    for trk in track_keys:
        idx = _iget(trk, 'trackIndex')
        if idx is None:
            continue
        t_by_idx[idx].append([_iget(trk, 'time', 0.0), _iget(trk, 'value', 0.0)])

    for ct in const_track_keys:
        idx = _iget(ct, 'trackIndex')
        if idx is None:
            continue
        ct_by_idx[idx].append(_iget(ct, 'value', 0.0))

    all_indices = sorted(set(t_by_idx.keys()) | set(ct_by_idx.keys()))
    if not all_indices:
        return

    #  Resolve human-readable track names from armature skin extras
    name_map = _get_track_name_map()

    # Build property names & data-paths, store mapping on action for export
    track_prop_names = {}       # index → property name
    track_data_paths = {}       # index → data-path string
    for idx in all_indices:
        pname = _track_prop_name(idx, name_map)
        track_prop_names[idx] = pname
        track_data_paths[idx] = _track_data_path(pname)

    prop_name_list = list(track_prop_names.values())
    add_track_properties(prop_name_list)

    #  Create / reset FCurves
    #  NOTE: get_action_fcurves must be called BEFORE add_track_action_group
    #  because on Blender 5.x it creates the channelbag where groups live.
    fcurves = get_action_fcurves(action)
    if fcurves is None:
        _vprint('import_anim_tracks: no fcurves collection available')
        return

    action_group = add_track_action_group(action)

    fc_cache = {}  # index → FCurve
    for idx in all_indices:
        dp = track_data_paths[idx]
        fc = fcurves.find(data_path=dp)
        if fc is not None:
            fc.keyframe_points.clear()
            fcurves.remove(fc)
        fc = fcurves.new(data_path=dp)
        if action_group is not None:
            fc.group = action_group
        fc_cache[idx] = fc

    #  Resolve final keyframe data (const + animated)
    num_imported = 0
    final_frames = {}  # index → [frame, ...]
    final_values = {}  # index → [value, ...]

    # Constant tracks
    for idx, vals in ct_by_idx.items():
        vmin, vmax = min(vals), max(vals)
        const_val = vmin if vmin == vmax else vals[-1]
        final_frames[idx] = [0.0]
        final_values[idx] = [const_val]
        num_imported += 1

    # Animated tracks – align fractional frames to integer boundaries
    for idx, raw_keys in t_by_idx.items():
        raw_keys.sort(key=lambda p: p[0])  # sort by time
        n_kf = len(raw_keys)

        frames_unaligned = [t * 30.0 for t, _ in raw_keys]
        frames_aligned = []
        for f in frames_unaligned:
            if (ceil(f) - f) < (f - floor(f)):
                frames_aligned.append(float(ceil(f)))
            else:
                frames_aligned.append(float(floor(f)))

        # Insert unaligned keyframes into a temporary FCurve for evaluation
        fc = fc_cache[idx]
        raw_values = [v for _, v in raw_keys]
        _bulk_set_keyframes(fc, frames_unaligned, raw_values)

        # Re-evaluate at aligned integer frames
        aligned_vals = [fc.evaluate(frm) for frm in frames_aligned]

        # Clear temp data
        fc.keyframe_points.clear()
        fc.update()

        final_frames[idx] = frames_aligned
        final_values[idx] = aligned_vals
        num_imported += n_kf

    #  Bulk-insert final keyframes
    for idx in all_indices:
        frms = final_frames.get(idx)
        vals = final_values.get(idx)
        if frms:
            _bulk_set_keyframes(fc_cache[idx], frms, vals)

    _vprint(f'{num_imported} Tracks Imported')


#  POSE BONES – Correct timing misalignment (sub-frame quantisation)

def fix_anim_frame_alignment(action):
    fcurves = get_action_fcurves(action)
    if fcurves is None:
        return

    # Count array components per data-path (location=3, quat=4, etc.)
    fc_keys = dict(Counter(
        fc.data_path for fc in fcurves if fc.data_path.startswith('pose.bones[')
    ))

    for dp, array_len in fc_keys.items():
        num_fixed = 0
        for i in range(array_len):
            fc = fcurves.find(data_path=dp, index=i)
            if fc is None or len(fc.keyframe_points) == 0:
                continue

            n_kf = len(fc.keyframe_points)

            # Bulk-read current keyframe data
            cos = [0.0] * (n_kf * 2)
            fc.keyframe_points.foreach_get('co', cos)

            frames_unaligned = [cos[j * 2] for j in range(n_kf)]
            frame_values = [cos[j * 2 + 1] for j in range(n_kf)]

            # Snap to nearest integer frame
            frames_aligned = []
            for f in frames_unaligned:
                if (ceil(f) - f) < (f - floor(f)):
                    fn = float(ceil(f))
                else:
                    fn = float(floor(f))
                if fn != f:
                    num_fixed += 1
                frames_aligned.append(fn)

            # Deduplicate (multiple sub-frame keys can snap to same integer)
            frames_aligned_unique = sorted(set(frames_aligned))
            num_keys = len(frames_aligned_unique)

            # Re-evaluate FCurve at aligned frames
            frame_values_aligned = [fc.evaluate(frm) for frm in frames_aligned_unique]

            # Diagnostic logging for constant-channel drift
            omin, omax = min(frame_values), max(frame_values)
            vmin, vmax = min(frame_values_aligned), max(frame_values_aligned)
            if omin == omax and vmin != vmax:
                _vprint(f'org {omin} == {omax} but {vmin} != {vmax} Re-Aligned')
            if vmin == vmax and omin != omax:
                _vprint(f'org {omin} != {omax} but {vmin} == {vmax} Re-Aligned')

            if num_keys == 1:
                continue

            # Preserve original interpolation mode (CP77 uses CONSTANT/STEP)
            orig_interp = fc.keyframe_points[0].interpolation

            fc.keyframe_points.clear()
            fc.update()
            _bulk_set_keyframes(
                fc,
                frames_aligned_unique,
                frame_values_aligned,
                interpolation=orig_interp,
            )

        if num_fixed > 0:
            _vprint(f'{dp} Re-Aligned Timing for {num_fixed} Frames')