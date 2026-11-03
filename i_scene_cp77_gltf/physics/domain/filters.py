from __future__ import annotations

from ...assetio.values import cname_text, coerce_int, handle_data
from ..model.collision_layers import COLLISION_LAYERS, COLLISION_PRESETS, get_layer_bit
from ..model.filters import PhysicsFilterState

COLLISION_LAYER_COUNT = len(COLLISION_LAYERS)
_UI_FILTER_WIDTH = 20


def decode_filter_data(value) -> PhysicsFilterState:
    wrapper = handle_data(value)
    simulation = handle_data(wrapper.get("simulationFilter"))
    query = handle_data(wrapper.get("queryFilter"))
    return PhysicsFilterState(
        preset=cname_text(handle_data(wrapper.get("preset")), "None"),
        simulation_group=coerce_int(simulation.get("mask1"), 0, unwrap=False),
        simulation_target=coerce_int(simulation.get("mask2"), 0, unwrap=False),
        query_mask=coerce_int(query.get("mask2"), 0, unwrap=False),
    )


def preset_filter_state(preset_name: str) -> PhysicsFilterState | None:
    data = COLLISION_PRESETS.get(str(preset_name or ""))
    if data is None:
        return None
    group = 0
    target = 0
    query = 0
    for name in data[0]:
        bit = get_layer_bit(name)
        if bit >= 0:
            group |= 1 << bit
    for name in data[1]:
        bit = get_layer_bit(name)
        if bit >= 0:
            target |= 1 << bit
    for name in data[2]:
        bit = get_layer_bit(name)
        if bit >= 0:
            query |= 1 << bit
            continue
        bit = get_layer_bit(name, is_query=True)
        if bit >= 0:
            query |= 1 << (COLLISION_LAYER_COUNT + bit)
    return PhysicsFilterState(str(preset_name), group, target, query)


def simulation_filter_state(state: PhysicsFilterState) -> PhysicsFilterState:
    """The filter a shape simulates with"""
    if state.simulation_group or state.simulation_target:
        return state
    preset = preset_filter_state(state.preset)
    if preset is None:
        return state
    return PhysicsFilterState(
        state.preset,
        preset.simulation_group,
        preset.simulation_target,
        state.query_mask or preset.query_mask,
    )


def bool_vector_mask(values) -> int:
    mask = 0
    for index, enabled in enumerate(values or ()):
        if enabled:
            mask |= 1 << index
    return mask


def mask_bool_vector(mask: int, *, width: int = _UI_FILTER_WIDTH) -> tuple[bool, ...]:
    value = coerce_int(mask, 0, unwrap=False)
    return tuple(bool(value & (1 << index)) for index in range(width))


def query_ui_mask(query_mask: int) -> int:
    return coerce_int(query_mask, 0, unwrap=False) >> COLLISION_LAYER_COUNT


def encode_query_ui_mask(ui_mask: int) -> int:
    return coerce_int(ui_mask, 0, unwrap=False) << COLLISION_LAYER_COUNT


def filter_ui_signature(preset: str, group_values, target_values, query_values) -> str:
    return "|".join(
        (
            str(preset or "None"),
            str(bool_vector_mask(group_values)),
            str(bool_vector_mask(target_values)),
            str(bool_vector_mask(query_values)),
        )
    )


def state_for_export(shape) -> PhysicsFilterState:
    visible_preset = str(getattr(shape, "collision_preset", "") or "None")
    current_signature = filter_ui_signature(
        visible_preset,
        getattr(shape, "filter_group", ()),
        getattr(shape, "filter_mask", ()),
        getattr(shape, "filter_query", ()),
    )
    source_signature = str(getattr(shape, "filter_source_signature", "") or "")
    source_preset = str(getattr(shape, "filter_source_preset", "") or "")
    if source_signature and source_signature == current_signature:
        try:
            return PhysicsFilterState(
                source_preset or visible_preset,
                int(getattr(shape, "filter_source_sim_group", "0") or 0),
                int(getattr(shape, "filter_source_sim_target", "0") or 0),
                int(getattr(shape, "filter_source_query_mask", "0") or 0),
            )
        except (TypeError, ValueError, OverflowError):
            pass

    preset_state = preset_filter_state(visible_preset)
    if preset_state is not None and visible_preset not in {"None", "No Collision"}:
        return preset_state

    return PhysicsFilterState(
        source_preset or visible_preset,
        bool_vector_mask(getattr(shape, "filter_group", ())),
        bool_vector_mask(getattr(shape, "filter_mask", ())),
        encode_query_ui_mask(bool_vector_mask(getattr(shape, "filter_query", ()))),
    )
