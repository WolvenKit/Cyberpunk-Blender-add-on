import time

import bpy

from ...animation.model.animgraph.constants import ANIMGRAPH_TREE_ID
from ...blender.animgraph.results_overlay import redraw_editors
from ...blender.animgraph.rig_binding import binding_tree, bound_armature
from ...blender.operator_results import OperationResult, finish_operator
from ...core.log import get_logger
from ...core.notifications import report
from ..blender.dangle_context import get_active_rig
from ..runtime.dangle.preview import (
    disable_rig,
    enable_rig,
    finalize_preview,
    prepare_preview,
    refresh_graph_inputs,
    refresh_preview_inputs,
    register_preview_session,
    step_preview,
    stop_orphaned_previews,
    stop_preview,
    toggle_graph_tag,
    toggle_preview_tag,
    unregister_preview_session,
)

_LOG = get_logger(__name__)
# Seconds between redraws of the graph editor's results while a graph plays.
_OVERLAY_INTERVAL = 0.1


class DANGLE_OT_enable_rig(bpy.types.Operator):
    bl_idname = "dangle.enable_rig"
    bl_label = "Enable Dangle Physics on Armature"

    def execute(self, context):
        return finish_operator(self, enable_rig(context))


class DANGLE_OT_disable_rig(bpy.types.Operator):
    bl_idname = "dangle.disable_rig"
    bl_label = "Remove Dangle from Armature"
    bl_options = {"UNDO"}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        return finish_operator(self, disable_rig(context))


class DANGLE_OT_refresh_preview_inputs(bpy.types.Operator):
    bl_idname = "dangle.refresh_preview_inputs"
    bl_label = "Refresh Graph Inputs"
    bl_description = "Read conditions and named inputs from the stored graph while retaining solver edits"
    bl_options = {"UNDO"}

    def execute(self, context):
        return finish_operator(self, refresh_preview_inputs(context))


class DANGLE_OT_toggle_preview_tag(bpy.types.Operator):
    bl_idname = "dangle.toggle_preview_tag"
    bl_label = "Visual Tag Is Present"
    bl_description = "Toggle this visual tag in the preview context; conditions are applied when Play starts"
    bl_options = {"UNDO"}

    tag: bpy.props.StringProperty(options={"HIDDEN"})

    def execute(self, context):
        return finish_operator(self, toggle_preview_tag(context, self.tag))


class _PreviewPlayOperator:
    """The modal loop both previews share"""

    _timer = None
    _simulator = None
    _rig = None
    _cache_key = None
    _last_time = 0.0
    _closed = False
    _session_key = None
    _window_manager = None
    _graph_name = ""
    _overlay_time = 0.0

    def _start(self, context):
        """The preview's start result and the graph it plays (None for the selected-dangle simulation)"""
        return prepare_preview(context), None

    def execute(self, context):
        result, graph = self._start(context)
        if not result.ok:
            return finish_operator(self, result)
        self._rig, self._simulator, self._cache_key, self._last_time = result.details[
            "payload"
        ]
        self._closed = False
        self._window_manager = context.window_manager
        try:
            self._timer = context.window_manager.event_timer_add(
                1.0 / 60.0, window=context.window
            )
            self._session_key = register_preview_session(
                self._rig, self._finish, graph, self._simulator
            )
            self._graph_name = binding_tree(graph).name if graph is not None else ""
            context.window_manager.modal_handler_add(self)
        except Exception as error:
            self._finish(context, restore_pose=True)
            report(
                self,
                "ERROR",
                f"Dangle preview could not start: {error}",
                logger=_LOG,
                error=error,
            )
            return {"CANCELLED"}
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        if self._closed:
            return {"CANCELLED"}
        stop_orphaned_previews()
        if self._closed:
            return {"CANCELLED"}
        try:
            valid_rig = self._rig is not None and self._rig.name in bpy.data.objects
        except ReferenceError:
            valid_rig = False
        if not valid_rig or event.type == "ESC" or not self._simulator.state.is_playing:
            self._finish(context, restore_pose=valid_rig)
            return {"CANCELLED"}
        if event.type == "TIMER":
            current_time = time.time()
            try:
                step_preview(
                    context,
                    self._simulator,
                    self._cache_key,
                    current_time - self._last_time,
                )
            except Exception as error:
                self._finish(context, restore_pose=True)
                report(
                    self,
                    "ERROR",
                    f"Dangle preview stopped: {error}",
                    logger=_LOG,
                    error=error,
                )
                return {"CANCELLED"}
            self._last_time = current_time
            if (
                self._graph_name
                and current_time - self._overlay_time >= _OVERLAY_INTERVAL
            ):
                redraw_editors(context.window_manager, self._graph_name)
                self._overlay_time = current_time
        return {"PASS_THROUGH"}

    def _finish(self, context=None, restore_pose=True):
        if self._closed:
            return
        self._closed = True
        active_context = context or bpy.context
        try:
            finalize_preview(
                active_context,
                self._rig,
                self._simulator,
                self._cache_key,
                restore_pose,
            )
        except Exception as error:
            report(
                self,
                "ERROR",
                f"Dangle preview restoration failed: {error}",
                logger=_LOG,
                error=error,
            )
        finally:
            try:
                if self._simulator is not None:
                    self._simulator.state.is_playing = False
                elif self._rig is not None:
                    self._rig.dangle_state.is_playing = False
            except ReferenceError:
                pass
            if self._timer is not None and self._window_manager is not None:
                try:
                    self._window_manager.event_timer_remove(self._timer)
                except (ReferenceError, ValueError):
                    pass
                self._timer = None
            unregister_preview_session(self._session_key)
            self._session_key = None
            self._simulator = None
            self._rig = None
            self._cache_key = None
            self._window_manager = None

    def cancel(self, context):
        self._finish(context, restore_pose=True)


class DANGLE_OT_preview_play(_PreviewPlayOperator, bpy.types.Operator):
    bl_idname = "dangle.preview_play"
    bl_label = "Play Dangle Simulation"


def _graph_tree(context, tree_name):
    tree = bpy.data.node_groups.get(tree_name) if tree_name else None
    if tree is None:
        tree = getattr(getattr(context, "space_data", None), "node_tree", None)
    return tree if getattr(tree, "bl_idname", "") == ANIMGRAPH_TREE_ID else None


class REDENGINE_OT_graph_preview_play(_PreviewPlayOperator, bpy.types.Operator):
    bl_idname = "redengine.graph_preview_play"
    bl_label = "Play Graph"
    bl_description = "Play the whole graph on its bound armature, dangles included"

    tree_name: bpy.props.StringProperty(options={"HIDDEN"})

    def _start(self, context):
        tree = _graph_tree(context, self.tree_name)
        if tree is None:
            return OperationResult.cancelled("Open a graph to play it."), None
        return prepare_preview(context, graph_tree=tree), tree


class REDENGINE_OT_graph_preview_stop(bpy.types.Operator):
    bl_idname = "redengine.graph_preview_stop"
    bl_label = "Stop Graph"

    tree_name: bpy.props.StringProperty(options={"HIDDEN"})

    def execute(self, context):
        tree = _graph_tree(context, self.tree_name)
        rig = bound_armature(tree) if tree is not None else None
        if rig is not None:
            stop_preview(context, rig, restore_pose=True)
        return {"FINISHED"}


class REDENGINE_OT_graph_preview_refresh_inputs(bpy.types.Operator):
    bl_idname = "redengine.graph_preview_refresh_inputs"
    bl_label = "Refresh Graph Inputs"
    bl_description = (
        "Read the graph's conditions and named inputs, keeping their values"
    )
    bl_options = {"UNDO"}

    tree_name: bpy.props.StringProperty(options={"HIDDEN"})

    def execute(self, context):
        tree = _graph_tree(context, self.tree_name)
        if tree is None:
            return finish_operator(
                self, OperationResult.cancelled("Open a graph first.")
            )
        return finish_operator(self, refresh_graph_inputs(tree))


class REDENGINE_OT_graph_preview_toggle_tag(bpy.types.Operator):
    bl_idname = "redengine.graph_preview_toggle_tag"
    bl_label = "Visual Tag Is Present"
    bl_description = "Toggle this visual tag for the next preview start"
    bl_options = {"UNDO"}

    tree_name: bpy.props.StringProperty(options={"HIDDEN"})
    tag: bpy.props.StringProperty(options={"HIDDEN"})

    def execute(self, context):
        tree = _graph_tree(context, self.tree_name)
        if tree is None:
            return finish_operator(
                self, OperationResult.cancelled("Open a graph first.")
            )
        return finish_operator(self, toggle_graph_tag(tree, self.tag))


class DANGLE_OT_preview_stop(bpy.types.Operator):
    bl_idname = "dangle.preview_stop"
    bl_label = "Stop Simulation"

    def execute(self, context):
        rig = get_active_rig(context)
        if rig is not None:
            stop_preview(context, rig, restore_pose=True)
        return {"FINISHED"}
