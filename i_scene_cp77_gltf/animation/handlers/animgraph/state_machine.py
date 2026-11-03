from __future__ import annotations

from collections.abc import Mapping

from ...domain.animgraph.branch_frames import interpolate_frames
from ...domain.animgraph.state_machine import choose_transition, prefer_transition
from ...model.animgraph.handles import normalized_source_handle
from .base import GraphNodeHandler


class StateMachineHandler(GraphNodeHandler):
    kinds = ("STATE_MACHINE",)

    def execute(self, context, step):
        step.handle = normalized_source_handle(step.program_node.handle)
        data = step.program_node.data
        states = tuple(data.get("states", ()) or ())
        if not states or not step.program_node.children:
            result = step.input_frame
            step.frame_cache[step.cache_key] = result
            return result
        default_state = max(
            0, min(int(data.get("defaultStateIndex", 0) or 0), len(states) - 1)
        )
        first_activation = step.handle not in context._state_machine_states
        resumed_transition = step.handle in context._state_machine_pending
        active_state = int(
            context._state_machine_pending.pop(
                step.handle,
                context._state_machine_states.get(step.handle, default_state),
            )
        )
        if not 0 <= active_state < len(step.program_node.children):
            active_state = default_state
        context._state_machine_states[step.handle] = active_state
        self._push_state_tags(context, step.handle, states)
        try:
            return self._execute_state_machine(
                context,
                step.program_node,
                step.handle,
                data,
                states,
                default_state,
                first_activation,
                resumed_transition,
                active_state,
                step.raw_dt,
                step.time_dilation,
                step.skip_physics,
                step.operation_callback,
                step.frame_cache,
                step.input_frame,
                step.additive_branch,
                step.cache_key,
            )
        finally:
            self._push_state_tags(context, step.handle, states)

    def _push_state_tags(self, context, handle, states) -> None:
        """Publish the current state's tags"""
        blend = context._state_machine_blends.get(handle)
        if blend is not None:
            progress = min(
                1.0,
                float(blend.get("elapsed", 0.0)) / max(1e-8, float(blend["duration"])),
            )
            weighted = (
                (int(blend["source"]), 1.0 - progress),
                (int(blend["target"]), progress),
            )
        else:
            weighted = ((int(context._state_machine_states.get(handle, 0)), 1.0),)
        for index, value in weighted:
            if 0 <= index < len(states):
                for tag in states[index].get("tags", ()) or ():
                    context._data_flow[tag] = value

    def _execute_state_machine(
        self,
        context,
        program_node,
        handle,
        data,
        states,
        default_state,
        first_activation,
        resumed_transition,
        active_state,
        raw_dt,
        time_dilation,
        skip_physics,
        operation_callback,
        frame_cache,
        input_frame,
        additive_branch,
        cache_key,
    ):
        features = context.feature_values()
        external_events = context.external_events()
        transitions = tuple(data.get("transitions", ()) or ())
        global_transitions = tuple(data.get("globalTransitions", ()) or ())
        history = context._state_condition_history
        blends = context._state_machine_blends
        frame_id = int(context._perf_frames)

        blend = blends.get(handle)
        if blend is not None:
            source_state = int(blend["source"])
            target_state = int(blend["target"])
            source_frame = context._execute_program(
                program_node.children[source_state],
                raw_dt,
                time_dilation,
                skip_physics,
                operation_callback,
                frame_cache,
                input_frame,
                additive_branch,
            )
            target_frame = context._execute_program(
                program_node.children[target_state],
                raw_dt,
                time_dilation,
                skip_physics,
                operation_callback,
                frame_cache,
                input_frame,
                additive_branch,
            )
            duration = max(1e-8, float(blend["duration"]))
            elapsed = float(blend.get("elapsed", 0.0)) + float(raw_dt)
            progress = min(1.0, elapsed / duration)
            blend["elapsed"] = elapsed
            progress_fn = globals().get("interpolation_progress")
            eased = (
                progress_fn(
                    progress, str(blend.get("interpolationType", "Linear") or "Linear")
                )
                if callable(progress_fn)
                else progress
            )
            result = interpolate_frames(source_frame, target_frame, eased)
            if progress >= 1.0:
                context._state_machine_states[handle] = target_state
                blends.pop(handle, None)
                if bool(
                    states[target_state].get(
                        "preventTransitionsInActivationFrame", False
                    )
                ):
                    context._state_machine_transition_delay.add(handle)
            frame_cache[cache_key] = result
            return result

        if first_activation:
            conditional_entries = tuple(data.get("conditionalEntries", ()) or ())
            entry = choose_transition(
                conditional_entries,
                range(len(conditional_entries)),
                features=features,
                external_events=external_events,
                anim_end_events=frozenset(context._anim_end_events),
                history=history,
                frame_id=frame_id,
                dt=raw_dt,
                key_prefix=(handle, "entry"),
                wrapper_variables=context.wrapper_variables(),
                inputs=context,
            )
            if entry is not None:
                target = int(entry.target_state)
                if not 0 <= target < len(program_node.children):
                    raise ValueError(
                        f"StateMachine {handle or program_node.path} conditional entry targets invalid state {target}"
                    )
                active_state = target
                context._state_machine_states[handle] = active_state
                context._reset_branch_activation(program_node.children[active_state])
                resetter = globals().get("reset_condition")
                if callable(resetter):
                    resetter(
                        conditional_entries[entry.index].get("condition"),
                        history,
                        (handle, "entry", entry.index),
                    )

        transition_delay = handle in context._state_machine_transition_delay
        if transition_delay:
            context._state_machine_transition_delay.discard(handle)

        if not resumed_transition:
            result = context._execute_program(
                program_node.children[active_state],
                raw_dt,
                time_dilation,
                skip_physics,
                operation_callback,
                frame_cache,
                input_frame,
                additive_branch,
            )
            if (first_activation or transition_delay) and bool(
                states[active_state].get("preventTransitionsInActivationFrame", False)
            ):
                frame_cache[cache_key] = result
                return result
        elif transition_delay:
            result = context._execute_program(
                program_node.children[active_state],
                raw_dt,
                time_dilation,
                skip_physics,
                operation_callback,
                frame_cache,
                input_frame,
                additive_branch,
            )
            frame_cache[cache_key] = result
            return result

        local = None
        if not resumed_transition:
            local = choose_transition(
                transitions,
                states[active_state].get("outTransitionIndices", ()) or (),
                features=features,
                external_events=external_events,
                anim_end_events=frozenset(context._anim_end_events),
                history=history,
                frame_id=frame_id,
                dt=raw_dt,
                key_prefix=(handle, "local"),
                wrapper_variables=context.wrapper_variables(),
                inputs=context,
            )
        global_choice = choose_transition(
            global_transitions,
            range(len(global_transitions)),
            features=features,
            external_events=external_events,
            anim_end_events=frozenset(context._anim_end_events),
            history=history,
            frame_id=frame_id,
            dt=raw_dt,
            key_prefix=(handle, "global"),
            wrapper_variables=context.wrapper_variables(),
            inputs=context,
        )
        choice = prefer_transition(local, global_choice)
        if choice is not None:
            target = int(choice.target_state)
            if not 0 <= target < len(program_node.children):
                raise ValueError(
                    f"StateMachine {handle or program_node.path} transition targets invalid state {target}"
                )
            is_global = global_choice is choice
            source_transitions = global_transitions if is_global else transitions
            transition = source_transitions[choice.index]
            resetter = globals().get("reset_condition")
            if callable(resetter):
                resetter(
                    transition.get("condition"),
                    history,
                    (handle, "global" if is_global else "local", choice.index),
                )
            context._reset_branch_activation(program_node.children[target])
            inertial = (
                bool(transition.get("canRequestInertialization", False))
                if isinstance(transition, Mapping)
                else False
            )
            if inertial:
                context._request_inertialization(float(choice.duration))
            if choice.duration > 1e-8 and not inertial:
                interpolator = (
                    transition.get("interpolator")
                    if isinstance(transition, Mapping)
                    else None
                )
                if not isinstance(interpolator, Mapping):
                    interpolator = (
                        data.get("anyStateInterpolator")
                        if isinstance(data.get("anyStateInterpolator"), Mapping)
                        else {}
                    )
                blends[handle] = {
                    "source": active_state,
                    "target": target,
                    "elapsed": 0.0,
                    "duration": float(choice.duration),
                    "interpolationType": str(
                        interpolator.get("interpolationType", "Linear") or "Linear"
                    ),
                }
            else:
                context._state_machine_pending[handle] = target
                if bool(
                    states[target].get("preventTransitionsInActivationFrame", False)
                ):
                    context._state_machine_transition_delay.add(handle)
                result = context._execute_program(
                    program_node.children[target],
                    raw_dt,
                    time_dilation,
                    skip_physics,
                    operation_callback,
                    frame_cache,
                    input_frame,
                    additive_branch,
                )
        elif resumed_transition:
            result = context._execute_program(
                program_node.children[active_state],
                raw_dt,
                time_dilation,
                skip_physics,
                operation_callback,
                frame_cache,
                input_frame,
                additive_branch,
            )
        frame_cache[cache_key] = result
        return result
