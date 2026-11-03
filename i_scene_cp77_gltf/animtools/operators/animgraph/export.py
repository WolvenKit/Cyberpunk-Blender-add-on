import bpy
from bpy.props import StringProperty
from bpy_extras.io_utils import ExportHelper

from ....animation.model.animgraph.constants import ANIMGRAPH_FILE_FILTER
from ....assetio.paths import animgraph_json_path
from ....blender.animgraph.rig_binding import binding_tree
from ....core.log import get_logger
from ....core.notifications import report
from ...services.animgraph.export import export_graph
from .context import animgraph_editor_poll

_LOG = get_logger(__name__)


class REDENGINE_OT_export_animgraph(bpy.types.Operator, ExportHelper):
    bl_idname = "redengine.export_animgraph"
    bl_label = "Export AnimGraph"
    bl_description = "Write the graph as a WolvenKit AnimGraph document"

    filename_ext = ".animgraph.json"
    filter_glob: StringProperty(default=ANIMGRAPH_FILE_FILTER, options={"HIDDEN"})

    @classmethod
    def poll(cls, context):
        return animgraph_editor_poll(context)

    def invoke(self, context, event):
        root = binding_tree(context.space_data.node_tree)
        self.filepath = animgraph_json_path(root.red_source_path or root.name)
        return ExportHelper.invoke(self, context, event)

    def check(self, context):
        normalized = animgraph_json_path(self.filepath)
        if normalized != self.filepath:
            self.filepath = normalized
            return True
        return False

    def execute(self, context):
        path = animgraph_json_path(self.filepath)
        try:
            export_graph(path, context.space_data.node_tree, context)
        except Exception as error:
            report(
                self,
                "ERROR",
                f"Couldn't export the AnimGraph: {error}",
                logger=_LOG,
                error=error,
            )
            return {"CANCELLED"}
        report(self, "INFO", f"Exported {path}.", logger=_LOG)
        return {"FINISHED"}
