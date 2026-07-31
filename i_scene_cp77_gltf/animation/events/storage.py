import copy
import json

from .codec import event_array

_EVENT_TYPES = {
    "Sound", "SoundFromEmitter", "Effect", "EffectDuration", "Simple", "Phase",
    "KeyPose", "ForceRagdoll", "ItemEffect", "ItemEffectDuration", "FootIK",
    "FootPlant", "FootPhase", "FoleyAction", "GameplayVo", "Slide", "SafeCut",
    "SimpleDuration", "TrajectoryAdjustment", "WorkspotFastExitCutoff", "Valued",
    "SceneItem", "WorkspotItem", "WorkspotPlayFacialAnim",
}
_WORKSPOT_ACTION_TYPES = {
    "EquipItemToSlot", "EquipPropToSlot", "EquipInventoryWeapon",
    "UnequipFromSlot", "UnequipProp", "UnequipItem",
}
_ATTACH_METHODS = {"BonePosition", "RelativePosition", "Custom"}


def _get(value, key, default=None):
    try:
        return value[key]
    except (KeyError, TypeError, IndexError):
        try:
            return value.get(key, default)
        except AttributeError:
            return default


def _plain(value):
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, dict) or hasattr(value, "keys"):
        return {str(key): _plain(value[key]) for key in value.keys()}
    try:
        return [_plain(item) for item in value]
    except TypeError:
        return value


def _source_dict(item):
    payload = getattr(item, "source_json", "")
    if not payload:
        return {}
    try:
        value = json.loads(payload)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _store_source(item, value):
    if hasattr(item, "source_json"):
        item.source_json = json.dumps(_plain(value), ensure_ascii=False, separators=(",", ":"))


def _set_optional(entry, key, value):
    if value:
        entry[key] = value
    else:
        entry.pop(key, None)


def sync_markers_from_events(action):
    if action is None:
        return
    while len(action.pose_markers) > 0:
        action.pose_markers.remove(action.pose_markers[0])
    for event in getattr(action, "cp77_anim_events", ()):
        marker = action.pose_markers.new(event.event_name or event.event_type)
        marker.frame = event.start_frame


def load_events_to_collection(action):
    raw = _get(action, "animEvents")
    if raw is None:
        return False
    try:
        raw_events = event_array(raw, getattr(action, "name", ""))
    except ValueError:
        return False
    events = getattr(action, "cp77_anim_events", None)
    if events is None:
        return False
    events.clear()
    for raw_event in raw_events:
        event = events.add()
        source_type = str(_get(raw_event, "type", "Simple") or "Simple")
        event.source_event_type = source_type
        event.event_type = source_type if source_type in _EVENT_TYPES else "Simple"
        event.event_name = str(_get(raw_event, "eventName", "") or "")
        event.start_frame = int(_get(raw_event, "startFrame", 0) or 0)
        event.duration_in_frames = int(_get(raw_event, "durationInFrames", 0) or 0)
        _store_source(event, raw_event)

        raw_switches = _get(raw_event, "switches")
        if raw_switches:
            if hasattr(raw_switches, "keys"):
                for name, value in raw_switches.items():
                    switch = event.switches.add()
                    switch.name = str(name)
                    switch.value = str(value)
            elif hasattr(raw_switches, "__iter__"):
                for raw_switch in raw_switches:
                    switch = event.switches.add()
                    switch.name = str(_get(raw_switch, "name", ""))
                    switch.value = str(_get(raw_switch, "value", ""))
                    _store_source(switch, raw_switch)

        raw_param_curves = _get(raw_event, "paramCurves")
        if raw_param_curves and hasattr(raw_param_curves, "__iter__"):
            for raw_param in raw_param_curves:
                param = event.params.add()
                param.name = str(_get(raw_param, "name", ""))
                param.value = float(_get(raw_param, "value", 0.0) or 0.0)
                param.enter_curve_type = str(_get(raw_param, "enterCurveType", "Linear"))
                param.enter_curve_time = float(_get(raw_param, "enterCurveTime", 1.0) or 0.0)
                param.exit_curve_type = str(_get(raw_param, "exitCurveType", "Linear"))
                param.exit_curve_time = float(_get(raw_param, "exitCurveTime", 1.0) or 0.0)
                _store_source(param, raw_param)
        else:
            raw_params = _get(raw_event, "params")
            if raw_params:
                if hasattr(raw_params, "keys"):
                    iterable = (
                        {"name": name, "value": value}
                        for name, value in raw_params.items()
                    )
                else:
                    iterable = raw_params
                for raw_param in iterable:
                    param = event.params.add()
                    param.name = str(_get(raw_param, "name", ""))
                    param.value = float(_get(raw_param, "value", 0.0) or 0.0)
                    _store_source(param, raw_param)

        raw_dynamic = _get(raw_event, "dynamicParams")
        if raw_dynamic and hasattr(raw_dynamic, "__iter__"):
            event.dynamic_params = ",".join(str(value) for value in raw_dynamic)
        event.metadata_context = str(_get(raw_event, "metadataContext", "") or "")
        event.only_play_on = str(_get(raw_event, "onlyPlayOn", "") or "")
        event.dont_play_on = str(_get(raw_event, "dontPlayOn", "") or "")
        gender = str(_get(raw_event, "playerGenderAlt", "None") or "None")
        event.player_gender_alt = gender if gender in {"None", "Female", "Male"} else "None"
        event.emitter_name = str(_get(raw_event, "emitterName", "") or "")
        event.effect_name = str(_get(raw_event, "effectName", "") or "")
        event.sequence_shift = int(_get(raw_event, "sequenceShift", 0) or 0)
        event.break_all_loops_on_stop = bool(_get(raw_event, "breakAllLoopsOnStop", False))
        event.event_value = float(
            _get(raw_event, "eventValue", _get(raw_event, "value", 0.0)) or 0.0
        )
        event.action_name = str(_get(raw_event, "actionName", "") or "")
        event.bone_name = str(_get(raw_event, "boneName", "") or "")
        event.facial_anim_name = str(_get(raw_event, "facialAnimName", "") or "")
        leg = str(_get(raw_event, "leg", "Left") or "Left")
        event.leg = leg if leg in {"Left", "Right"} else "Left"
        phase = str(
            _get(raw_event, "footPhase", _get(raw_event, "phase", "RightUp"))
            or "RightUp"
        )
        valid_phases = {"RightUp", "RightForward", "LeftUp", "LeftForward", "NotConsidered"}
        event.foot_phase = phase if phase in valid_phases else "RightUp"
        event.vo_context = str(_get(raw_event, "voContext", "") or "")
        event.is_quest = bool(_get(raw_event, "isQuest", False))
        side = str(_get(raw_event, "side", "Left") or "Left")
        event.side = side if side in {"Left", "Right"} else "Left"
        event.custom_event = str(_get(raw_event, "customEvent", "") or "")

        raw_actions = _get(raw_event, "workspotActions")
        if raw_actions and hasattr(raw_actions, "__iter__"):
            for raw_action in raw_actions:
                action_item = event.workspot_actions.add()
                action_type = str(_get(raw_action, "$type", "EquipItemToSlot") or "EquipItemToSlot")
                action_item.source_action_type = action_type
                action_item.action_type = (
                    action_type
                    if action_type in _WORKSPOT_ACTION_TYPES
                    else "EquipItemToSlot"
                )
                action_item.item = str(_get(raw_action, "item", "") or "")
                action_item.item_slot = str(_get(raw_action, "itemSlot", "") or "")
                action_item.item_id = str(_get(raw_action, "itemId", "") or "")
                attach = str(_get(raw_action, "attachMethod", "BonePosition") or "BonePosition")
                action_item.attach_method = attach if attach in _ATTACH_METHODS else "BonePosition"
                action_item.offset_pos_x = float(_get(raw_action, "offsetPosX", 0.0) or 0.0)
                action_item.offset_pos_y = float(_get(raw_action, "offsetPosY", 0.0) or 0.0)
                action_item.offset_pos_z = float(_get(raw_action, "offsetPosZ", 0.0) or 0.0)
                action_item.offset_rot_i = float(_get(raw_action, "offsetRotI", 0.0) or 0.0)
                action_item.offset_rot_j = float(_get(raw_action, "offsetRotJ", 0.0) or 0.0)
                action_item.offset_rot_k = float(_get(raw_action, "offsetRotK", 0.0) or 0.0)
                action_item.offset_rot_r = float(_get(raw_action, "offsetRotR", 1.0) or 1.0)
                action_item.weapon_type = str(_get(raw_action, "weaponType", "Any") or "Any")
                action_item.keep_equipped_after_exit = bool(
                    _get(raw_action, "keepEquippedAfterExit", False)
                )
                action_item.fallback_item = str(_get(raw_action, "fallbackItem", "") or "")
                action_item.fallback_slot = str(_get(raw_action, "fallbackSlot", "") or "")
                _store_source(action_item, raw_action)

    action.cp77_anim_events_index = 0 if len(events) else -1
    action["_cp77_events_loaded"] = True
    sync_markers_from_events(action)
    return True


def _event_base(event):
    source = _source_dict(event)
    source_type = getattr(event, "source_event_type", "")
    event_type = event.event_type
    if source_type and source_type not in _EVENT_TYPES and event_type == "Simple":
        output_type = source_type
    else:
        output_type = event_type
        if source_type and source_type != output_type:
            source = {}
    entry = copy.deepcopy(source)
    entry["type"] = output_type
    entry["eventName"] = event.event_name
    entry["startFrame"] = event.start_frame
    entry["durationInFrames"] = event.duration_in_frames
    return entry


def _workspot_action_payload(item):
    source = _source_dict(item)
    source_type = getattr(item, "source_action_type", "")
    action_type = item.action_type
    if (
        source_type
        and source_type not in _WORKSPOT_ACTION_TYPES
        and action_type == "EquipItemToSlot"
    ):
        output_type = source_type
    else:
        output_type = action_type
        if source_type and source_type != output_type:
            source = {}
    result = copy.deepcopy(source)
    result["$type"] = output_type
    if output_type not in _WORKSPOT_ACTION_TYPES:
        return result
    if action_type == "EquipItemToSlot":
        result["item"] = item.item
        result["itemSlot"] = item.item_slot
    elif action_type == "EquipPropToSlot":
        result.update({
            "itemId": item.item_id,
            "itemSlot": item.item_slot,
            "attachMethod": item.attach_method,
            "offsetPosX": item.offset_pos_x,
            "offsetPosY": item.offset_pos_y,
            "offsetPosZ": item.offset_pos_z,
            "offsetRotI": item.offset_rot_i,
            "offsetRotJ": item.offset_rot_j,
            "offsetRotK": item.offset_rot_k,
            "offsetRotR": item.offset_rot_r,
        })
    elif action_type == "EquipInventoryWeapon":
        result.update({
            "weaponType": item.weapon_type,
            "keepEquippedAfterExit": item.keep_equipped_after_exit,
            "fallbackItem": item.fallback_item,
            "fallbackSlot": item.fallback_slot,
        })
    elif action_type == "UnequipFromSlot":
        result["itemSlot"] = item.item_slot
    elif action_type == "UnequipProp":
        result["itemId"] = item.item_id
    elif action_type == "UnequipItem":
        result["item"] = item.item
    return result


def save_events_to_idproperty(action):
    events = getattr(action, "cp77_anim_events", None)
    if events is None or len(events) == 0:
        if not _get(action, "_cp77_events_loaded", False):
            return False
        existing = _get(action, "animEvents")
        if existing is not None and hasattr(existing, "__len__") and len(existing) > 0:
            return False
        if "animEvents" in action:
            del action["animEvents"]
        return True

    result = []
    for event in events:
        entry = _event_base(event)
        event_type = event.event_type
        if event_type == "Sound":
            if len(event.switches):
                entry["switches"] = {item.name: item.value for item in event.switches}
            else:
                entry.pop("switches", None)
            if len(event.params):
                entry["params"] = {item.name: item.value for item in event.params}
                curves = []
                for item in event.params:
                    curve = _source_dict(item)
                    curve.update({
                        "name": item.name,
                        "value": item.value,
                        "enterCurveType": item.enter_curve_type,
                        "enterCurveTime": item.enter_curve_time,
                        "exitCurveType": item.exit_curve_type,
                        "exitCurveTime": item.exit_curve_time,
                    })
                    curves.append(curve)
                entry["paramCurves"] = curves
            else:
                entry.pop("params", None)
                entry.pop("paramCurves", None)
            dynamic = [value.strip() for value in event.dynamic_params.split(",") if value.strip()]
            if dynamic:
                entry["dynamicParams"] = dynamic
            else:
                entry.pop("dynamicParams", None)
            _set_optional(entry, "metadataContext", event.metadata_context)
            _set_optional(entry, "onlyPlayOn", event.only_play_on)
            _set_optional(entry, "dontPlayOn", event.dont_play_on)
            if event.player_gender_alt != "None":
                entry["playerGenderAlt"] = event.player_gender_alt
            else:
                entry.pop("playerGenderAlt", None)
        elif event_type == "SoundFromEmitter":
            _set_optional(entry, "emitterName", event.emitter_name)
        elif event_type in {"Effect", "ItemEffect"}:
            _set_optional(entry, "effectName", event.effect_name)
        elif event_type in {"EffectDuration", "ItemEffectDuration"}:
            _set_optional(entry, "effectName", event.effect_name)
            entry["sequenceShift"] = event.sequence_shift
            entry["breakAllLoopsOnStop"] = event.break_all_loops_on_stop
        elif event_type == "Valued":
            key = "value" if "value" in entry and "eventValue" not in entry else "eventValue"
            entry[key] = event.event_value
        elif event_type == "FoleyAction":
            _set_optional(entry, "actionName", event.action_name)
        elif event_type == "SceneItem":
            _set_optional(entry, "boneName", event.bone_name)
        elif event_type == "WorkspotPlayFacialAnim":
            _set_optional(entry, "facialAnimName", event.facial_anim_name)
        elif event_type == "FootIK":
            entry["leg"] = event.leg
        elif event_type == "FootPhase":
            key = "phase" if "phase" in entry and "footPhase" not in entry else "footPhase"
            entry[key] = event.foot_phase
        elif event_type == "GameplayVo":
            _set_optional(entry, "voContext", event.vo_context)
            entry["isQuest"] = event.is_quest
        elif event_type == "FootPlant":
            entry["side"] = event.side
            _set_optional(entry, "customEvent", event.custom_event)
        elif event_type == "WorkspotItem":
            if len(event.workspot_actions):
                entry["workspotActions"] = [
                    _workspot_action_payload(item) for item in event.workspot_actions
                ]
            else:
                entry.pop("workspotActions", None)
        result.append(entry)
    action["animEvents"] = result
    return True
