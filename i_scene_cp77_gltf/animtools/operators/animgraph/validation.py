import bpy

from ....animation.animgraph_constants import ANIMGRAPH_TREE_ID
from ...services import animgraph_validation


class REDENGINE_OT_validate_graph(bpy.types.Operator):
    """Validate the active AnimGraph without mutating export state."""
    bl_idname = 'redengine.validate_graph'
    bl_label = 'Validate Graph'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        space = context.space_data
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
