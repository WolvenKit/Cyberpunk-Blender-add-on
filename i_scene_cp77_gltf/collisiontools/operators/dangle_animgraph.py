import bpy
from bpy.props import StringProperty
from bpy_extras.io_utils import ExportHelper, ImportHelper

from ...animation.model.animgraph.constants import ANIMGRAPH_FILE_FILTER
from ...assetio.paths import animgraph_json_path
from ...blender.animgraph.preview_settings import adopt_dangle_settings
from ...blender.workspace import is_animation_workspace, show_graph
from ...core.log import get_logger
from ...core.notifications import import_operation, report
from ..blender.dangle_context import get_active_rig, rig_for_context
from ..services.dangles.sync import (
    export_from_specialist_editor,
    import_into_both_editors,
    sync_editor_to_graph,
    sync_graph_to_editor,
    validate_imported_document,
)
from ..services.dangles.view import (
    can_return_to_editor,
    rig_graph_tree,
    switch_to_editor_view,
    switch_to_graph_view,
)

_LOG = get_logger(__name__)


class DANGLE_OT_import_json(bpy.types.Operator, ImportHelper):
    bl_idname = "dangle.import_json"
    bl_label = "Import WolvenKit AnimGraph JSON"
    filename_ext = ".animgraph.json"
    filter_glob: StringProperty(default=ANIMGRAPH_FILE_FILTER, options={"HIDDEN"})

    @import_operation
    def execute(self, context):
        rig = get_active_rig(context)
        _LOG.info(
            "Importing AnimGraph: path=%s rig=%s",
            self.filepath,
            getattr(rig, "name", "<none>"),
        )
        if not rig:
            report(self, "ERROR", "No active Dangle Rig selected.", logger=_LOG)
            return {"CANCELLED"}
        if rig.dangle_state.is_playing:
            report(self, "ERROR", "Stop Dangle preview before importing.", logger=_LOG)
            return {"CANCELLED"}
        try:
            count, tree, editor_error = import_into_both_editors(
                self.filepath, rig, context
            )
            if tree is None:
                report(
                    self,
                    "WARNING",
                    f"Imported {count} dangle node(s), but the Graph View "
                    f"could not be built: {editor_error}",
                    logger=_LOG,
                )
            else:
                report(
                    self,
                    "INFO",
                    f"Imported {count} dangle node(s) and created AnimGraph tree {tree.name}.",
                    logger=_LOG,
                )
        except Exception as e:
            report(
                self,
                "ERROR",
                f"Failed to import {self.filepath}: {e}",
                logger=_LOG,
                error=e,
            )
            return {"CANCELLED"}
        _LOG.info(
            "AnimGraph import complete: path=%s dangles=%d graph=%s",
            self.filepath,
            count,
            getattr(tree, "name", "<unavailable>"),
        )
        return {"FINISHED"}


class DANGLE_OT_export_animgraph(bpy.types.Operator, ExportHelper):
    bl_idname = "dangle.export_animgraph"
    bl_label = "Export WolvenKit AnimGraph JSON"
    bl_options = {"REGISTER"}

    filename_ext = ".animgraph.json"
    filter_glob: StringProperty(default=ANIMGRAPH_FILE_FILTER, options={"HIDDEN"})

    def invoke(self, context, event):
        rig = get_active_rig(context)
        if rig is None:
            report(self, "ERROR", "No active Dangle Rig selected.", logger=_LOG)
            return {"CANCELLED"}
        previous = str(rig.dangle_state.animgraph_last_export_path or "")
        source = str(rig.dangle_state.animgraph_source_path or "")
        self.filepath = animgraph_json_path(previous or source or f"{rig.name}_dangle")
        return ExportHelper.invoke(self, context, event)

    def check(self, context):
        normalized = animgraph_json_path(self.filepath)
        if normalized != self.filepath:
            self.filepath = normalized
            return True
        return False

    def execute(self, context):
        rig = get_active_rig(context)
        _LOG.info(
            "Exporting AnimGraph: path=%s rig=%s",
            self.filepath,
            getattr(rig, "name", "<none>"),
        )
        if rig is None:
            report(self, "ERROR", "No active Dangle Rig selected.", logger=_LOG)
            return {"CANCELLED"}
        if rig.dangle_state.is_playing:
            report(self, "ERROR", "Stop Dangle preview before exporting.", logger=_LOG)
            return {"CANCELLED"}
        try:
            summary = export_from_specialist_editor(
                animgraph_json_path(self.filepath), rig, context
            )
        except Exception as exc:
            report(
                self,
                "ERROR",
                f"Failed to export AnimGraph to {self.filepath}: {exc}",
                logger=_LOG,
                error=exc,
            )
            return {"CANCELLED"}
        self.filepath = animgraph_json_path(self.filepath)
        refresh_error = summary.get("editorRefreshError")
        warnings = summary.get("warnings", ()) or ()
        if warnings:
            unreachable = len(summary.get("unreachableNodes", ()))
            _LOG.warning(
                "AnimGraph export validation warnings: total=%d unreachable_nodes=%d other=%d first=%s",
                len(warnings),
                unreachable,
                len(warnings) - unreachable,
                str(warnings[0]),
            )
        if refresh_error:
            report(
                self,
                "WARNING",
                f"AnimGraph exported, but the Graph View refresh failed: {refresh_error}",
                logger=_LOG,
            )
        elif warnings:
            report(
                self,
                "WARNING",
                f"Exported WolvenKit AnimGraph with {len(warnings)} runtime warning(s): "
                f"{warnings[0]}",
                logger=_LOG,
            )
        else:
            report(
                self,
                "INFO",
                f"Exported WolvenKit AnimGraph: {summary.get('dangleNodes', 0)} Dangle, "
                f"{summary.get('dragNodes', 0)} Drag, {summary.get('handles', 0)} handles.",
                logger=_LOG,
            )
        _LOG.info(
            "AnimGraph export complete: path=%s dangles=%d drags=%d handles=%d warnings=%d",
            self.filepath,
            summary.get("dangleNodes", 0),
            summary.get("dragNodes", 0),
            summary.get("handles", 0),
            len(warnings),
        )
        return {"FINISHED"}


class DANGLE_OT_validate_animgraph(bpy.types.Operator):
    bl_idname = "dangle.validate_animgraph"
    bl_label = "Validate AnimGraph"

    def execute(self, context):
        rig = get_active_rig(context)
        if rig is None:
            return {"CANCELLED"}
        try:
            summary = validate_imported_document(rig)
        except Exception as exc:
            report(self, "ERROR", str(exc), logger=_LOG, error=exc)
            return {"CANCELLED"}
        if not summary.get("ready"):
            errors = summary.get("errors", ())
            report(
                self,
                "ERROR",
                errors[0] if errors else "AnimGraph validation failed",
                logger=_LOG,
            )
            return {"FINISHED"}
        warnings = summary.get("warnings", ()) or ()
        level = {"WARNING"} if warnings else {"INFO"}
        suffix = f", {len(warnings)} warning(s)" if warnings else ""
        report(
            self,
            level,
            f"AnimGraph document valid: {summary.get('dangleNodes', 0)} Dangle, "
            f"{summary.get('dragNodes', 0)} Drag, {summary.get('handles', 0)} handles{suffix}.",
            logger=_LOG,
        )
        return {"FINISHED"}


class DANGLE_OT_switch_to_graph(bpy.types.Operator):
    bl_idname = "dangle.switch_to_graph"
    bl_label = "Switch to Graph View"

    def execute(self, context):
        rig = get_active_rig(context)
        if rig is None:
            return {"CANCELLED"}
        try:
            if is_animation_workspace(context):
                # The workspace already shows a graph editor beside the viewport.
                tree = rig_graph_tree(context, rig)
                show_graph(context, tree)
            else:
                tree = switch_to_graph_view(context, rig)
        except Exception as exc:
            report(self, "ERROR", str(exc), logger=_LOG, error=exc)
            return {"CANCELLED"}
        report(self, "INFO", f"Opened Graph View for {tree.name}.", logger=_LOG)
        return {"FINISHED"}


class DANGLE_OT_preview_whole_graph(bpy.types.Operator):
    bl_idname = "dangle.preview_whole_graph"
    bl_label = "Preview Whole Graph"
    bl_description = "Open the rig's graph in the Animation workspace, where the whole graph plays with its dangles"

    def execute(self, context):
        rig = get_active_rig(context)
        if rig is None:
            report(self, "ERROR", "No active Dangle Rig selected.", logger=_LOG)
            return {"CANCELLED"}
        try:
            tree = rig_graph_tree(context, rig)
        except Exception as exc:
            report(self, "ERROR", str(exc), logger=_LOG, error=exc)
            return {"CANCELLED"}
        adopt_dangle_settings(tree)
        show_graph(context, tree)
        return {"FINISHED"}


class DANGLE_OT_switch_to_editor(bpy.types.Operator):
    bl_idname = "dangle.switch_to_editor"
    bl_label = "Switch to Dangle Editor View"

    @classmethod
    def poll(cls, context):
        return can_return_to_editor(context)

    def execute(self, context):
        try:
            rig = switch_to_editor_view(context)
        except Exception as exc:
            report(self, "ERROR", str(exc), logger=_LOG, error=exc)
            return {"CANCELLED"}
        report(
            self, "INFO", f"Returned to the Dangle editor for {rig.name}.", logger=_LOG
        )
        return {"FINISHED"}


def _editor_to_graph(operator, context):
    rig = get_active_rig(context) or rig_for_context(context)
    if rig is None:
        return {"CANCELLED"}
    if rig.dangle_state.is_playing:
        report(
            operator, "ERROR", "Stop Dangle preview before synchronizing.", logger=_LOG
        )
        return {"CANCELLED"}
    try:
        tree = sync_editor_to_graph(rig, context)
    except Exception as exc:
        report(operator, "ERROR", str(exc), logger=_LOG, error=exc)
        return {"CANCELLED"}
    report(
        operator,
        "INFO",
        f"Synchronized Dangle editor changes to graph {tree.name}.",
        logger=_LOG,
    )
    return {"FINISHED"}


def _graph_to_editor(operator, context):
    rig = rig_for_context(context) or get_active_rig(context)
    if rig is None:
        return {"CANCELLED"}
    if rig.dangle_state.is_playing:
        report(
            operator, "ERROR", "Stop Dangle preview before synchronizing.", logger=_LOG
        )
        return {"CANCELLED"}
    try:
        count, summary = sync_graph_to_editor(rig)
    except Exception as exc:
        report(operator, "ERROR", str(exc), logger=_LOG, error=exc)
        return {"CANCELLED"}
    report(
        operator,
        "INFO",
        f"Synchronized graph changes to the Dangle editor: {count} Dangle node(s), "
        f"{summary.get('dragNodes', 0)} Drag node(s).",
        logger=_LOG,
    )
    return {"FINISHED"}


class DANGLE_OT_push_to_graph(bpy.types.Operator):
    bl_idname = "dangle.push_to_graph"
    bl_label = "Push Dangle Editor Changes to Graph"

    def execute(self, context):
        return _editor_to_graph(self, context)


class DANGLE_OT_pull_from_graph(bpy.types.Operator):
    bl_idname = "dangle.pull_from_graph"
    bl_label = "Pull Graph Changes into Dangle Editor"

    def execute(self, context):
        return _graph_to_editor(self, context)


class DANGLE_OT_push_to_editor(bpy.types.Operator):
    bl_idname = "dangle.push_to_editor"
    bl_label = "Push Graph Changes to Dangle Editor"

    def execute(self, context):
        return _graph_to_editor(self, context)


class DANGLE_OT_pull_from_editor(bpy.types.Operator):
    bl_idname = "dangle.pull_from_editor"
    bl_label = "Pull Dangle Editor Changes into Graph"

    def execute(self, context):
        return _editor_to_graph(self, context)
