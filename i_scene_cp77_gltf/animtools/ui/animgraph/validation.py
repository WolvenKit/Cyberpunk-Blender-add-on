import bpy

from ....animation.animgraph_constants import ANIMGRAPH_TREE_ID
from ...services import animgraph_validation as graph_validator
from ....blender.animgraph.validation import reporting

class REDENGINE_PT_graph_validator(bpy.types.Panel):
    bl_idname = "REDENGINE_PT_graph_validator"
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "AnimGraph"
    bl_label = "Graph Validator"

    @classmethod
    def poll(cls, context):
        space = context.space_data
        if space is None or space.type != 'NODE_EDITOR':
            return False
        tree = space.node_tree
        return tree is not None and tree.bl_idname == ANIMGRAPH_TREE_ID

    @staticmethod
    def _metric(layout, label: str, value: str, *, icon: str = 'NONE'):
        row = layout.row(align=True)
        row.label(text=label, icon=icon)
        row.label(text=str(value))

    def draw(self, context):
        layout = self.layout
        tree = context.space_data.node_tree
        report = reporting.load_report(tree, report_key=graph_validator.REPORT_KEY)

        layout.operator('redengine.validate_graph', text='Validate Graph', icon='CHECKMARK')

        if not report:
            layout.label(text='No validation report yet.', icon='INFO')
            return

        ready = bool(report.get('ready', False))
        counters = report.get('counters', {}) if isinstance(report, dict) else {}
        blocking = report.get('blocking', []) if isinstance(report, dict) else []
        warnings = report.get('warnings', []) if isinstance(report, dict) else []
        summary = report.get('artist_summary', '') or report.get('summary', '')

        status = layout.box()
        status.label(text=('Graph ready for export' if ready else 'Graph needs fixes'), icon=('CHECKMARK' if ready else 'ERROR'))
        if summary:
            status.label(text=str(summary))

        metrics = layout.box()
        metrics.label(text='Validation coverage', icon='RNA')
        self._metric(metrics, 'Runtime nodes', f"{counters.get('runtime_nodes_valid', 0)} / {counters.get('runtime_nodes_total', 0)}")
        self._metric(metrics, 'Properties', f"{counters.get('properties_valid', 0)} / {counters.get('properties_total', 0)}")
        self._metric(metrics, 'Input sockets', f"{counters.get('input_sockets_valid', 0)} / {counters.get('input_sockets_total', 0)}")
        self._metric(metrics, 'Dataflow links', f"{counters.get('links_valid', 0)} / {counters.get('links_total', 0)}")
        self._metric(metrics, 'Variables', f"{counters.get('variables_valid', 0)} / {counters.get('variables_total', 0)}")
        self._metric(metrics, 'Handle refs', f"missing {counters.get('missing_handle_refs', 0)}, duplicates {counters.get('duplicate_handle_ids', 0)}")
        self._metric(metrics, 'Issues', f"{counters.get('blocking_issues', 0)} blocking, {counters.get('warnings', 0)} warnings")

        if blocking:
            err = layout.box()
            err.label(text='Fix before export', icon='ERROR')
            for item in blocking[:10]:
                err.label(text=str(item))
            if len(blocking) > 10:
                err.label(text=f"... {len(blocking) - 10} more")

        if warnings:
            warn = layout.box()
            warn.label(text='Warnings', icon='INFO')
            for item in warnings[:8]:
                warn.label(text=str(item))
            if len(warnings) > 8:
                warn.label(text=f"... {len(warnings) - 8} more")

        active = context.active_node
        if active is not None:
            details = layout.box()
            details.label(text='Active node', icon='NODE')
            details.label(text=f"HandleId: {getattr(active, 'red_handle_id', '') or '<none>'}")
            details.label(text=f"Type: {getattr(active, 'red_type', '') or '<none>'}")
            details.label(text=f"Exportable: {bool(getattr(active, 'red_exportable', False))}")
