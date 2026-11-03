import json
import logging
import time

import bpy

from ....animation.model.animgraph.constants import ANIMGRAPH_TREE_ID
from ....blender.animgraph.preview_settings import adopt_dangle_settings
from ....blender.animgraph.results_overlay import redraw_editors
from ....blender.animgraph.rig_binding import binding_tree, bound_armature
from ....blender.animgraph.source import load_graph_payload
from ....blender.context import tag_view3d_redraw
from ....blender.operator_results import OperationResult
from ....core.log import debug_exception, get_logger, log_once
from ...blender.dangle_context import get_active_rig
from .graph_state import GraphPreviewState
from .overlay import _DRAW_CACHES, update_draw_cache
from .simulation import core, solvers, spaces

SUPPORTED_PREVIEW_SOLVERS = {"DYNG", "PBD", "SPRING", "PENDULUM"}
_ACTIVE_PREVIEW_SESSIONS = {}
# Session key -> name of the graph tree a whole-graph preview plays, so a preview stops when its graph goes.
_SESSION_GRAPHS = {}
# Session key -> the simulator a whole-graph preview steps, for the graph editor's results and viewed node.
_SESSION_SIMULATORS = {}


_LOG = get_logger(__name__)


def _graph_preview_snapshot(rig, source_payload=None, *, errors=()):
    state = getattr(rig, "dangle_state", None)
    graph_names = frozenset()
    available = frozenset()
    action_sources = {}
    static_switches = []
    graph_slot_conditions = []
    rig_tags = frozenset()
    metarig_part_bindings = ()
    root_type = ""
    root_handle = ""
    if isinstance(source_payload, dict):
        try:
            from ....animation.domain.animgraph.animation_scope import (
                available_animation_names,
                graph_animation_names,
            )
            from ....animation.domain.animgraph.topology import (
                handle_index,
                resolve,
                static_condition_result,
                static_switch_branch,
            )
            from ....gltf.provenance import SOURCE_PATH_KEY

            actions = getattr(getattr(bpy, "data", None), "actions", None)
            graph_names = graph_animation_names(source_payload)
            available = available_animation_names(
                source_payload,
                actions,
                source_path_property=SOURCE_PATH_KEY,
            )
            for name in sorted(graph_names):
                action = (
                    actions.get(name)
                    if actions is not None and hasattr(actions, "get")
                    else None
                )
                if action is None:
                    action_sources[name] = None
                    continue
                source = (
                    action.get(SOURCE_PATH_KEY, "") if hasattr(action, "get") else ""
                )
                action_sources[name] = str(source or "")

            index = handle_index(source_payload)
            visual_tags = frozenset(
                item.strip()
                for item in str(getattr(state, "preview_visual_tags", "") or "").split(
                    ","
                )
                if item.strip()
            )
            component_tags = frozenset(
                item.strip()
                for item in str(
                    getattr(state, "preview_component_tags", "") or ""
                ).split(",")
                if item.strip()
            )
            arm_data = getattr(rig, "data", None)
            rig_tags = frozenset(
                str(tag)
                for tag in (
                    arm_data.get("cp77_rig_tags", ())
                    if hasattr(arm_data, "get")
                    else ()
                )
                if str(tag or "") and str(tag) != "None"
            )
            from ....blender.rig_metadata import source_rig_part_bindings

            metarig_part_bindings = source_rig_part_bindings(rig)
            for handle, node in sorted(index.items(), key=lambda item: item[0]):
                if (
                    not isinstance(node, dict)
                    or node.get("$type") != "animAnimNode_StaticSwitch"
                ):
                    continue
                condition = (
                    resolve(node.get("condition"), index)
                    if node.get("condition") is not None
                    else None
                )
                condition_type = (
                    str((condition or {}).get("$type", "") or "")
                    if isinstance(condition, dict)
                    else ""
                )
                condition_value = ""
                if isinstance(condition, dict):
                    if condition_type == "animHasAnimationCondition":
                        value = condition.get("animationName", "")
                        condition_value = str(
                            value.get("$value", value.get("value", ""))
                            if isinstance(value, dict)
                            else value or ""
                        )
                    elif condition_type == "animVisualTagCondition":
                        value = condition.get("visualTag", "")
                        condition_value = str(
                            value.get("$value", value.get("value", ""))
                            if isinstance(value, dict)
                            else value or ""
                        )
                try:
                    branch = static_switch_branch(
                        node,
                        index,
                        visual_tags=visual_tags,
                        available_animations=available,
                        rig_tags=rig_tags,
                        parent_tags=component_tags,
                    )
                    switch_error = ""
                except Exception as error:
                    debug_exception(
                        _LOG, "Could not resolve branch %s of a static switch", index
                    )
                    branch = ""
                    switch_error = f"{type(error).__name__}: {error}"
                static_switches.append(
                    {
                        "handle": str(handle),
                        "condition_type": condition_type or "<none>",
                        "condition_value": condition_value,
                        "selected_branch": branch,
                        "error": switch_error,
                    }
                )

            for handle, node in sorted(index.items(), key=lambda item: item[0]):
                if (
                    not isinstance(node, dict)
                    or node.get("$type") != "animAnimNode_GraphSlotConditions"
                ):
                    continue
                entries = []
                selected = None
                for condition_index, entry in enumerate(node.get("conditions") or ()):
                    if not isinstance(entry, dict):
                        continue
                    graph_value = entry.get("graph")
                    depot = ""
                    if isinstance(graph_value, dict):
                        depot_value = graph_value.get("DepotPath")
                        if isinstance(depot_value, dict):
                            depot = str(
                                depot_value.get("$value", depot_value.get("value", ""))
                                or ""
                            )
                        elif depot_value is not None:
                            depot = str(depot_value or "")
                    condition_ref = entry.get("condition")
                    condition = (
                        resolve(condition_ref, index)
                        if condition_ref is not None
                        else None
                    )
                    condition_type = (
                        str((condition or {}).get("$type", "") or "")
                        if isinstance(condition, dict)
                        else "<null>"
                    )
                    condition_value = ""
                    if isinstance(condition, dict):
                        value = condition.get(
                            "tag",
                            condition.get(
                                "visualTag",
                                condition.get(
                                    "animationName", condition.get("animTag", "")
                                ),
                            ),
                        )
                        if isinstance(value, dict):
                            value = value.get("$value", value.get("value", ""))
                        condition_value = str(value or "")
                    if condition_ref is None:
                        matched = False
                        condition_error = ""
                    else:
                        try:
                            matched = static_condition_result(
                                condition_ref,
                                index,
                                visual_tags=visual_tags,
                                available_animations=available,
                                rig_tags=rig_tags,
                                parent_tags=component_tags,
                            )
                            condition_error = ""
                        except Exception as error:
                            debug_exception(
                                _LOG,
                                "Could not evaluate condition %s of a static switch",
                                index,
                            )
                            matched = False
                            condition_error = f"{type(error).__name__}: {error}"
                    item = {
                        "index": condition_index,
                        "condition_type": condition_type,
                        "condition_value": condition_value,
                        "graph": depot,
                        "matched": bool(matched),
                        "error": condition_error,
                    }
                    entries.append(item)
                    if matched and selected is None:
                        selected = item
                        break
                graph_slot_conditions.append(
                    {
                        "handle": str(handle),
                        "slot_name": str(
                            (
                                (node.get("name") or {}).get("$value", "")
                                if isinstance(node.get("name"), dict)
                                else node.get("name", "")
                            )
                            or ""
                        ),
                        "selected": selected,
                        "conditions": entries,
                        "injected_graph_evaluated": False,
                    }
                )
        except Exception as error:
            debug_exception(
                _LOG, "Could not list the animation sources for the preview snapshot"
            )
            action_sources["<diagnostic-error>"] = f"{type(error).__name__}: {error}"

        root = source_payload.get("Data", {}).get("RootChunk", {})
        root_ref = root.get("rootNode") if isinstance(root, dict) else None
        if isinstance(root_ref, dict):
            root_handle = str(
                root_ref.get("HandleId", root_ref.get("HandleRefId", "")) or ""
            )
            root_data = resolve(root_ref, index)
            if isinstance(root_data, dict):
                root_type = str(root_data.get("$type", "") or "")

    vector_inputs = []
    evaluation_order = []
    if state is not None:
        for item in getattr(state, "preview_vector_inputs", ()):
            vector_inputs.append(
                {
                    "key": str(getattr(item, "key", "") or ""),
                    "value": tuple(
                        float(value) for value in getattr(item, "value", ())
                    ),
                }
            )
        for operation in getattr(state, "evaluation_order", ()):
            evaluation_order.append(
                {
                    "type": str(getattr(operation, "node_type", "") or ""),
                    "index": int(getattr(operation, "node_index", -1)),
                    "handle": str(getattr(operation, "source_handle", "") or ""),
                    "path": str(getattr(operation, "graph_path", "") or ""),
                }
            )

    return {
        "rig": getattr(rig, "name", "<none>"),
        "rig_mode": str(getattr(rig, "mode", "<unknown>") or "<unknown>"),
        "preview_mode": str(getattr(state, "preview_mode", "<unknown>") or "<unknown>"),
        "graph_source_path": str(getattr(state, "animgraph_source_path", "") or ""),
        "graph_source_text": str(getattr(state, "animgraph_source_text", "") or ""),
        "graph_tree": str(getattr(state, "animgraph_tree_name", "") or ""),
        "root_type": root_type or "<unknown>",
        "root_handle": root_handle or "<inline>",
        "skeletal_lod": int(getattr(state, "preview_skeletal_lod", 0) or 0),
        "performance_mode": bool(getattr(state, "preview_performance_mode", False)),
        "rig_tags": tuple(sorted(rig_tags)),
        "metarig_part_bindings": metarig_part_bindings,
        "visual_tags": tuple(
            sorted(
                item.strip()
                for item in str(getattr(state, "preview_visual_tags", "") or "").split(
                    ","
                )
                if item.strip()
            )
        ),
        "graph_animations": tuple(sorted(graph_names)),
        "available_animations": tuple(sorted(available)),
        "missing_graph_animations": tuple(sorted(set(graph_names) - set(available))),
        "action_sources": action_sources,
        "static_switches": static_switches,
        "graph_slot_conditions": graph_slot_conditions,
        "external_events": tuple(
            item.strip()
            for item in str(getattr(state, "preview_external_events", "") or "").split(
                ","
            )
            if item.strip()
        ),
        "anim_features_json": str(
            getattr(state, "preview_anim_features_json", "") or ""
        ),
        "vector_inputs": vector_inputs,
        "graph_compiled": bool(getattr(state, "graph_compiled", False)),
        "evaluation_boundary": str(getattr(state, "evaluation_boundary", "") or ""),
        "preview_input_error": str(getattr(state, "preview_input_error", "") or ""),
        "dangle_nodes": len(getattr(state, "dangle_nodes", ()) or ()),
        "drag_nodes": len(getattr(state, "drag_nodes", ()) or ()),
        "evaluation_order": evaluation_order,
        "errors": tuple(str(error) for error in errors if str(error)),
    }


def _log_graph_preview_context(level, stage, rig, source_payload=None, *, errors=()):
    try:
        snapshot = _graph_preview_snapshot(rig, source_payload, errors=errors)
        _LOG.log(
            level,
            "AnimGraph preview diagnostics: stage=%s snapshot=%s",
            stage,
            json.dumps(snapshot, sort_keys=True, separators=(",", ":"), default=str),
        )
    except Exception:
        _LOG.exception("AnimGraph preview diagnostic capture failed: stage=%s", stage)


def _session_key(rig):
    try:
        return int(rig.as_pointer())
    except (ReferenceError, AttributeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_session_key", type(error).__name__),
            "session key: fell back after %s",
            error,
            exc_info=True,
        )
        return None


def register_preview_session(rig, stop_callback, graph_tree=None, simulator=None):
    key = _session_key(rig)
    if key is not None:
        _ACTIVE_PREVIEW_SESSIONS[key] = stop_callback
        if graph_tree is not None:
            _SESSION_GRAPHS[key] = binding_tree(graph_tree).name
            _SESSION_SIMULATORS[key] = simulator
    return key


def _end_graph_session(tree_name, simulator) -> None:
    """A stopped graph preview shows the final pose again, and its results leave the graph editor"""
    runtime = getattr(simulator, "animgraph_runtime", None)
    if runtime is not None:
        runtime.view_handle = None
    tree = bpy.data.node_groups.get(tree_name) if tree_name else None
    if getattr(tree, "bl_idname", "") == ANIMGRAPH_TREE_ID:
        tree.red_preview.view_handle = ""
        redraw_editors(bpy.context.window_manager, tree_name)


def unregister_preview_session(key):
    if key is not None:
        _ACTIVE_PREVIEW_SESSIONS.pop(key, None)
        _end_graph_session(
            _SESSION_GRAPHS.pop(key, None), _SESSION_SIMULATORS.pop(key, None)
        )


def stop_orphaned_previews():
    """Stop every whole-graph preview whose graph tree no longer exists"""
    for key, tree_name in tuple(_SESSION_GRAPHS.items()):
        if tree_name not in bpy.data.node_groups:
            stop_callback = _ACTIVE_PREVIEW_SESSIONS.get(key)
            if stop_callback is not None:
                stop_callback(None, False)
            unregister_preview_session(key)


def graph_runtime(graph_tree):
    """The AnimGraph runtime of the whole-graph preview playing graph_tree, else None"""
    name = binding_tree(graph_tree).name
    for key, tree_name in _SESSION_GRAPHS.items():
        if tree_name == name:
            return getattr(_SESSION_SIMULATORS.get(key), "animgraph_runtime", None)
    return None


def session_results(graph_tree):
    runtime = graph_runtime(graph_tree)
    return runtime.results() if runtime is not None else None


def set_view_handle(graph_tree, handle) -> None:
    """Show the pose node handle produces on the rig, or the final pose again for an empty handle"""
    runtime = graph_runtime(graph_tree)
    if runtime is not None:
        runtime.view_handle = handle or None
    binding_tree(graph_tree).red_preview.view_handle = handle or ""


def preview_running(rig) -> bool:
    key = _session_key(rig)
    return key is not None and key in _ACTIVE_PREVIEW_SESSIONS


def stop_active_previews():
    failures = []
    for stop_callback in tuple(_ACTIVE_PREVIEW_SESSIONS.values()):
        try:
            stop_callback()
        except Exception as error:
            debug_exception(_LOG, "Could not stop an active Dangle preview")
            failures.append(error)
    _ACTIVE_PREVIEW_SESSIONS.clear()
    if failures:
        raise RuntimeError("; ".join(str(error) for error in failures))


def stop_preview(context, rig, restore_pose=True):
    key = _session_key(rig)
    stop_callback = _ACTIVE_PREVIEW_SESSIONS.get(key) if key is not None else None
    if stop_callback is not None:
        stop_callback(context, restore_pose)
        return True
    try:
        if rig is not None:
            rig.dangle_state.is_playing = False
    except ReferenceError:
        pass
    return False


def runtime_target_errors(rig, state=None):
    """Why rig cannot run a preview, and why state cannot play"""
    errors = list(spaces.armature_space_errors(rig))
    if state is not None:
        errors.extend(spaces.state_configuration_errors(state))
    return errors


def unsupported_solver_names(state):
    active_dangles, _active_drags = spaces.executable_node_indices(state)
    return sorted(
        {
            chain.solver
            for index, node in enumerate(state.dangle_nodes)
            if index in active_dangles
            for chain in node.chains
            if chain.solver not in SUPPORTED_PREVIEW_SOLVERS
        }
    )


def enable_rig(context):
    rig = context.active_object
    if rig is None or rig.type != "ARMATURE":
        return OperationResult.cancelled("Select an armature to enable Dangle physics")
    errors = runtime_target_errors(rig)
    if errors:
        return OperationResult.cancelled(errors[0])
    rig.dangle_state.is_dangle_rig = True
    for index, obj in enumerate(context.scene.objects):
        if obj == rig:
            context.scene.dangle_active_rig_index = index
            break
    return OperationResult.finished()


def disable_rig(context):
    rig = get_active_rig(context)
    if rig is None:
        return OperationResult.cancelled("No active Dangle rig selected.", "WARNING")
    stop_preview(context, rig, restore_pose=True)
    _DRAW_CACHES.pop(f"{rig.as_pointer()}", None)
    _DRAW_CACHES.pop(rig.name, None)
    state = rig.dangle_state
    state.dangle_nodes.clear()
    state.collision_shapes.clear()
    state.drag_nodes.clear()
    state.evaluation_order.clear()
    state.is_dangle_rig = False
    tag_view3d_redraw(context)
    return OperationResult.finished(f"Removed dangle data from {rig.name}.")


def refresh_graph_state(state, payload):
    """Read the graph's conditions, named inputs and dangle operations into state, keeping solver edits"""
    from .editor_state import refresh_graph_operations

    rig = getattr(state, "id_data", None)
    try:
        refresh_graph_operations(payload, state)
    except Exception as error:
        _log_graph_preview_context(
            logging.WARNING,
            "refresh-error",
            rig,
            payload,
            errors=(f"{type(error).__name__}: {error}",),
        )
        raise
    _log_graph_preview_context(logging.DEBUG, "refresh-complete", rig, payload)
    return payload


def _refresh_graph_inputs(rig):
    from ...blender.dangle_source import load_source_payload

    return refresh_graph_state(rig.dangle_state, load_source_payload(rig))


def refresh_graph_inputs(graph_tree):
    """Read the graph's conditions and named inputs into its preview settings, keeping their values"""
    root = binding_tree(graph_tree)
    rig = bound_armature(root)
    if rig is None:
        return OperationResult.cancelled("Bind the graph to an armature first.")
    if graph_tree_previewing(root):
        return OperationResult.cancelled(
            "Stop the preview before refreshing the graph's inputs."
        )
    adopt_dangle_settings(root)
    try:
        refresh_graph_state(
            GraphPreviewState(rig.dangle_state, root), load_graph_payload(root)
        )
    except (ValueError, KeyError, TypeError) as error:
        return OperationResult.cancelled(str(error), error=error)
    return OperationResult.finished()


def toggle_graph_tag(graph_tree, tag):
    """Add or remove a visual tag the graph's StaticSwitches test, for the next preview start"""
    if graph_tree_previewing(graph_tree):
        return OperationResult.cancelled(
            "Stop the preview before changing the graph's conditions."
        )
    settings = binding_tree(graph_tree).red_preview
    if not tag or not any(item.tag == tag for item in settings.visual_tag_requirements):
        return OperationResult.cancelled("The graph no longer tests this visual tag.")
    tags = list(
        dict.fromkeys(
            value.strip() for value in settings.visual_tags.split(",") if value.strip()
        )
    )
    if tag in tags:
        tags.remove(tag)
    else:
        tags.append(tag)
    settings.visual_tags = ", ".join(tags)
    return OperationResult.finished()


def graph_tree_previewing(graph_tree) -> bool:
    name = binding_tree(graph_tree).name
    return name in _SESSION_GRAPHS.values()


def refresh_preview_inputs(context):
    rig = get_active_rig(context)
    if rig is None:
        return OperationResult.cancelled("No active Dangle rig selected.")
    if rig.dangle_state.is_playing:
        return OperationResult.cancelled(
            "Stop simulation before refreshing graph conditions."
        )
    if not rig.dangle_state.animgraph_source_text:
        return OperationResult.cancelled(
            "Import an AnimGraph before refreshing its inputs."
        )
    try:
        payload = _refresh_graph_inputs(rig)
    except (ValueError, KeyError, TypeError) as error:
        return OperationResult.cancelled(str(error), error=error)
    _log_graph_preview_context(logging.DEBUG, "manual-refresh", rig, payload)
    return OperationResult.finished(
        "Graph conditions and inputs refreshed; solver edits retained."
    )


def toggle_preview_tag(context, tag):
    rig = get_active_rig(context)
    if rig is None:
        return OperationResult.cancelled("No active Dangle rig selected.")
    state = rig.dangle_state
    if state.is_playing:
        return OperationResult.cancelled(
            "Stop simulation before changing graph conditions."
        )
    if not tag or not any(
        item.tag == tag for item in state.preview_visual_tag_requirements
    ):
        return OperationResult.cancelled(
            "The selected visual tag is no longer required by this graph."
        )
    tags = list(
        dict.fromkeys(
            value.strip()
            for value in state.preview_visual_tags.split(",")
            if value.strip()
        )
    )
    if tag in tags:
        tags.remove(tag)
    else:
        tags.append(tag)
    state.preview_visual_tags = ", ".join(tags)
    return OperationResult.finished()


def _timeline_playback_active() -> bool:
    context = getattr(bpy, "context", None)
    screen = getattr(context, "screen", None)
    if screen is not None and bool(getattr(screen, "is_animation_playing", False)):
        return True
    window_manager = getattr(context, "window_manager", None)
    for window in getattr(window_manager, "windows", ()) or ():
        candidate = getattr(window, "screen", None)
        if candidate is not None and bool(
            getattr(candidate, "is_animation_playing", False)
        ):
            return True
    return False


def _register_frame_change_capture(simulator):
    existing = getattr(simulator, "_frame_change_capture_handlers", None)
    if existing is not None:
        return

    def _prepare_before_animation(_scene, _depsgraph=None):
        try:
            if getattr(getattr(simulator, "state", None), "is_playing", False):
                simulator._timeline_playing = _timeline_playback_active()
                simulator.prepare_frame_change_upstream()
        except ReferenceError:
            return
        except Exception:
            _LOG.exception("Dangle frame-change upstream prepare failed")

    def _capture_after_animation(_scene, _depsgraph=None):
        try:
            if getattr(getattr(simulator, "state", None), "is_playing", False):
                simulator.capture_frame_change_upstream(_depsgraph)
        except ReferenceError:
            return
        except Exception:
            _LOG.exception("Dangle frame-change upstream capture failed")

    simulator._frame_change_capture_handlers = (
        _prepare_before_animation,
        _capture_after_animation,
    )
    bpy.app.handlers.frame_change_pre.append(_prepare_before_animation)
    bpy.app.handlers.frame_change_post.append(_capture_after_animation)


def _unregister_frame_change_capture(simulator):
    if simulator is None:
        return
    handlers = getattr(simulator, "_frame_change_capture_handlers", None)
    if handlers is None:
        return
    pre_handler, post_handler = handlers
    try:
        bpy.app.handlers.frame_change_pre.remove(pre_handler)
    except ValueError:
        pass
    try:
        bpy.app.handlers.frame_change_post.remove(post_handler)
    except ValueError:
        pass
    simulator._frame_change_capture_handlers = None


def _enter_pose_mode(context, rig) -> bool:
    if rig.mode == "POSE":
        return True
    try:
        context.view_layer.objects.active = rig
        rig.select_set(True)
        bpy.ops.object.mode_set(mode="POSE")
    except (RuntimeError, ReferenceError):
        return False
    return rig.mode == "POSE"


def _preview_target(context, graph_tree):
    """The rig and the state a preview runs on"""
    if graph_tree is None:
        rig = get_active_rig(context)
        if rig is None:
            return None, None, "No active Dangle rig selected."
        rig.dangle_state.preview_mode = "SELECTED"
        return rig, rig.dangle_state, ""
    root = binding_tree(graph_tree)
    rig = bound_armature(root)
    if rig is None:
        return None, None, "Bind the graph to an armature before playing it."
    adopt_dangle_settings(root)
    return rig, GraphPreviewState(rig.dangle_state, root), ""


def prepare_preview(context, graph_tree=None):
    """Start the selected-dangle simulation, or with graph_tree the whole graph on its bound armature"""
    rig, state, rejection = _preview_target(context, graph_tree)
    if rig is None:
        return OperationResult.cancelled(rejection)
    source_payload = None
    if graph_tree is not None:
        try:
            source_payload = load_graph_payload(graph_tree)
            refresh_graph_state(state, source_payload)
        except (ValueError, KeyError, TypeError) as error:
            _log_graph_preview_context(
                logging.WARNING,
                "preflight-refresh-rejected",
                rig,
                source_payload,
                errors=(f"{type(error).__name__}: {error}",),
            )
            return OperationResult.cancelled(str(error), error=error)
    errors = runtime_target_errors(rig, state)
    if errors:
        _log_graph_preview_context(
            logging.WARNING,
            "preflight-validation-rejected",
            rig,
            source_payload,
            errors=errors,
        )
        return OperationResult.cancelled(errors[0])
    active_dangles, active_drags = spaces.executable_node_indices(state)
    graph_pose_only = bool(state.preview_mode == "GRAPH" and source_payload is not None)
    if not active_dangles and not active_drags and not graph_pose_only:
        _log_graph_preview_context(
            logging.WARNING,
            "preflight-empty-graph",
            rig,
            source_payload,
            errors=("No Dangle or Drag operations are reachable for preview.",),
        )
        return OperationResult.cancelled(
            "No Dangle or Drag operations are reachable for preview.", "WARNING"
        )
    if not state.dangle_nodes and not state.drag_nodes and not graph_pose_only:
        _log_graph_preview_context(
            logging.WARNING,
            "preflight-no-imported-physics",
            rig,
            source_payload,
            errors=("No Dangle or Drag nodes imported.",),
        )
        return OperationResult.cancelled("No Dangle or Drag nodes imported.", "WARNING")
    unsupported = unsupported_solver_names(state)
    if unsupported:
        _log_graph_preview_context(
            logging.WARNING,
            "preflight-unsupported-solver",
            rig,
            source_payload,
            errors=(f"Preview does not support: {', '.join(unsupported)}",),
        )
        return OperationResult.cancelled(
            f"Preview does not support: {', '.join(unsupported)}"
        )
    linked_runtime = None
    if state.preview_mode == "GRAPH":
        linked = [
            state.dangle_nodes[index].source_handle
            for index in active_dangles
            if state.dangle_nodes[index].external_force_linked
        ]
        if linked:
            if source_payload is None:
                return OperationResult.cancelled(
                    "Linked external force requires the imported AnimGraph source."
                )
            from ....animation.domain.animgraph.math_expression import (
                MathExpressionError,
            )
            from ....animation.runtime.animgraph.linked_forces import LinkedForcePreview

            try:
                linked_runtime = LinkedForcePreview(source_payload, linked)
            except MathExpressionError as error:
                _log_graph_preview_context(
                    logging.WARNING,
                    "preflight-linked-force-rejected",
                    rig,
                    source_payload,
                    errors=(f"{type(error).__name__}: {error}",),
                )
                return OperationResult.cancelled(
                    f"Preview unavailable: {error}", error=error
                )
    if not _enter_pose_mode(context, rig):
        _log_graph_preview_context(
            logging.WARNING,
            "preflight-pose-mode-required",
            rig,
            source_payload,
            errors=("Enter Pose Mode before starting the preview.",),
        )
        return OperationResult.cancelled(
            "Enter Pose Mode before starting the preview.", "WARNING"
        )
    # One preview plays at a time.
    stop_preview(context, rig, restore_pose=True)
    stop_active_previews()
    try:
        simulator = core.DyngSimulator(
            rig,
            linked_force_runtime=linked_runtime,
            source_payload=source_payload,
            view_layer_update=getattr(
                getattr(context, "view_layer", None), "update", None
            ),
            graph_tree=binding_tree(graph_tree) if graph_tree is not None else None,
        )
    except Exception as error:
        _log_graph_preview_context(
            logging.ERROR,
            "simulator-construction-error",
            rig,
            source_payload,
            errors=(f"{type(error).__name__}: {error}",),
        )
        return OperationResult.cancelled(str(error), error=error)
    state.is_playing = True
    _register_frame_change_capture(simulator)
    _LOG.info(
        "AnimGraph preview started: rig=%s mode=%s dangles=%d drags=%d linked_forces=%d",
        getattr(rig, "name", "<unnamed>"),
        str(state.preview_mode or "<unknown>"),
        len(active_dangles),
        len(active_drags),
        linked_runtime.dangle_count if linked_runtime is not None else 0,
    )
    _log_graph_preview_context(logging.DEBUG, "preview-started", rig, source_payload)
    return OperationResult.finished(
        payload=(rig, simulator, f"{rig.as_pointer()}", time.time())
    )


def step_preview(context, simulator, cache_key, dt):
    simulator._timeline_playing = _timeline_playback_active()
    solvers.update_simulation(simulator, min(dt, 0.1), time_dilation=1.0)
    draw_started = time.perf_counter()
    update_draw_cache(cache_key, simulator)
    tag_view3d_redraw(context)
    runtime = getattr(simulator, "animgraph_runtime", None)
    if runtime is not None and runtime.structured:
        runtime.record_draw_time(time.perf_counter() - draw_started)


def finalize_preview(context, rig, simulator, cache_key, restore_pose=True):
    _unregister_frame_change_capture(simulator)
    runtime = (
        getattr(simulator, "animgraph_runtime", None) if simulator is not None else None
    )
    if runtime is not None and runtime.structured:
        summary = runtime.performance_summary()
        if summary:
            _LOG.debug("AnimGraph preview performance: %s", summary)
        hotspots = (
            runtime.performance_hotspots()
            if hasattr(runtime, "performance_hotspots")
            else None
        )
        if hotspots:
            _LOG.debug("AnimGraph pose hotspots: %s", hotspots)
    _LOG.info(
        "Stopping Dangle preview: rig=%s restore_pose=%s",
        getattr(rig, "name", "<released>"),
        bool(restore_pose),
    )
    if restore_pose and simulator is not None:
        try:
            simulator.restore_upstream_pose()
        except ReferenceError:
            pass
    try:
        if simulator is not None:
            simulator.state.is_playing = False
        elif rig is not None:
            rig.dangle_state.is_playing = False
    except ReferenceError:
        pass
    if cache_key is not None:
        _DRAW_CACHES.pop(cache_key, None)
    tag_view3d_redraw(context)
