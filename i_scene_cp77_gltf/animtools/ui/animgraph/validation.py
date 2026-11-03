import bpy

from ....animation.model.animgraph.constants import ANIMGRAPH_TREE_ID
from ...runtime import read_models


class REDENGINE_PT_graph_validator(bpy.types.Panel):
    bl_idname = "REDENGINE_PT_graph_validator"
    bl_space_type = "NODE_EDITOR"
    bl_region_type = "UI"
    bl_category = "Graph"
    bl_label = "Graph Validator"

    @classmethod
    def poll(cls, context):
        space = context.space_data
        if space is None or space.type != "NODE_EDITOR":
            return False
        tree = space.node_tree
        return tree is not None and tree.bl_idname == ANIMGRAPH_TREE_ID

    def draw(self, context):
        layout = self.layout
        tree = context.space_data.node_tree
        report = read_models.validation_report(tree)

        if not report:
            return

        ready = bool(report.get("ready", False))
        blocking = report.get("blocking", []) if isinstance(report, dict) else []
        warnings = report.get("warnings", []) if isinstance(report, dict) else []
        summary = report.get("artist_summary", "") or report.get("summary", "")

        if not ready:
            status = layout.box()
            status.label(text="Graph needs fixes", icon="ERROR")
            if summary:
                status.label(text=str(summary))

        if blocking:
            err = layout.box()
            err.label(text="Fix before export", icon="ERROR")
            for item in blocking[:10]:
                err.label(text=str(item))
            if len(blocking) > 10:
                err.label(text=f"... {len(blocking) - 10} more")

        if warnings:
            warn = layout.box()
            warn.label(text="Warnings", icon="INFO")
            for item in warnings[:8]:
                warn.label(text=str(item))
            if len(warnings) > 8:
                warn.label(text=f"... {len(warnings) - 8} more")
