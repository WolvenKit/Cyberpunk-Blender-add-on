import bpy

from ...animation.model.animgraph.constants import ANIMGRAPH_TREE_ID
from ...core.log import debug_exception, get_logger
from ..identity import rna_identity
from .results_overlay import redraw_editors
from .rig_binding import binding_tree

_LOG = get_logger(__name__)


_ACTIVE_PREVIEW_SESSIONS = {}


# Session key -> name of the graph tree a whole-graph preview plays, so a preview stops when its graph goes.
_SESSION_GRAPHS = {}


# Session key -> the simulator a whole-graph preview steps, for the graph editor's results and viewed node.
_SESSION_SIMULATORS = {}
_SESSION_TREES = {}


def register_preview_session(rig, stop_callback, graph_tree=None, simulator=None):
    key = rna_identity(rig)
    _ACTIVE_PREVIEW_SESSIONS[key] = stop_callback
    if graph_tree is not None:
        name = binding_tree(graph_tree).name
        _drop_session_graph(key)
        _SESSION_GRAPHS[key] = name
        _SESSION_SIMULATORS[key] = simulator
        _SESSION_TREES.setdefault(name, {})[key] = None
    return key


def _drop_session_graph(key):
    name = _SESSION_GRAPHS.pop(key, None)
    sessions = _SESSION_TREES.get(name)
    if sessions is not None:
        sessions.pop(key, None)
        if not sessions:
            del _SESSION_TREES[name]
    return name


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
        _end_graph_session(_drop_session_graph(key), _SESSION_SIMULATORS.pop(key, None))


def _stop_graph_sessions(matches):
    for key, tree_name in tuple(_SESSION_GRAPHS.items()):
        if matches(tree_name):
            stop_callback = _ACTIVE_PREVIEW_SESSIONS.get(key)
            if stop_callback is not None:
                stop_callback(None, False)
            unregister_preview_session(key)


def stop_orphaned_previews():
    """Stop every whole-graph preview whose graph tree no longer exists"""
    _stop_graph_sessions(lambda tree_name: tree_name not in bpy.data.node_groups)


def stop_graph_preview(graph_tree):
    name = binding_tree(graph_tree).name
    _stop_graph_sessions(lambda tree_name: tree_name == name)


def graph_runtime(graph_tree):
    """The AnimGraph runtime of the whole-graph preview playing graph_tree, else None"""
    sessions = _SESSION_TREES.get(binding_tree(graph_tree).name)
    if not sessions:
        return None
    return getattr(
        _SESSION_SIMULATORS.get(next(iter(sessions))), "animgraph_runtime", None
    )


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
    return rna_identity(rig) in _ACTIVE_PREVIEW_SESSIONS


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


def preview_stop_callback(rig):
    return _ACTIVE_PREVIEW_SESSIONS.get(rna_identity(rig))


def graph_tree_previewing(graph_tree) -> bool:
    return binding_tree(graph_tree).name in _SESSION_TREES
