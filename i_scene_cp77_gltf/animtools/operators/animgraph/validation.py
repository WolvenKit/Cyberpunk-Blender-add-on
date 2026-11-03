import bpy

<<<<<<< Updated upstream
from ....animation.animgraph_constants import ANIMGRAPH_TREE_ID
from ...services import animgraph_validation


class REDENGINE_OT_validate_graph(bpy.types.Operator):
    """Validate the active AnimGraph without mutating export state."""
    bl_idname = 'redengine.validate_graph'
    bl_label = 'Validate Graph'
    bl_options = {'REGISTER', 'UNDO'}
=======
from ....animation.model.animgraph.constants import ANIMGRAPH_TREE_ID
from ....core.log import get_logger
from ....core.notifications import report
from ...services.animgraph import validation

_LOG = get_logger(__name__)


class REDENGINE_OT_validate_graph(bpy.types.Operator):
    """Validate the active AnimGraph without mutating export state"""

    bl_idname = "redengine.validate_graph"
    bl_label = "Validate Graph"
    bl_options = {"REGISTER", "UNDO"}
>>>>>>> Stashed changes

    @classmethod
    def poll(cls, context):
        space = context.space_data
<<<<<<< Updated upstream
        if space is None or space.type != 'NODE_EDITOR':
            return False
        tree = space.node_tree
        return tree is not None and getattr(tree, 'bl_idname', '') == ANIMGRAPH_TREE_ID

    def execute(self, context):
        tree = context.space_data.node_tree
        report = animgraph_validation.run_and_store(tree)
        counters = report.get('counters', {})
        summary = report.get('artist_summary', '') or report.get('summary', '')
        if report.get('ready'):
            self.report({'INFO'}, f'Graph validation passed. {summary}')
        else:
            self.report({'WARNING'}, f"Graph validation failed: blockers={counters.get('blocking_issues', 0)} warnings={counters.get('warnings', 0)}")
        return {'FINISHED'}
=======
        if space is None or space.type != "NODE_EDITOR":
            return False
        tree = space.node_tree
        return tree is not None and getattr(tree, "bl_idname", "") == ANIMGRAPH_TREE_ID

    def execute(self, context):
        document_report = validation.run_and_store(context.space_data.node_tree)
        counters = document_report.get("counters", {})
        summary = document_report.get("artist_summary", "") or document_report.get(
            "summary", ""
        )
        if document_report.get("ready"):
            report(self, "INFO", f"Graph validation passed. {summary}", logger=_LOG)
        else:
            report(
                self,
                "WARNING",
                f"Graph validation failed: blockers={counters.get('blocking_issues', 0)} "
                f"warnings={counters.get('warnings', 0)}",
                logger=_LOG,
            )
        return {"FINISHED"}
>>>>>>> Stashed changes
