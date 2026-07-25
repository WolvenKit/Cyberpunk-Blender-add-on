import json

import bpy
from bpy.props import BoolProperty, StringProperty
from bpy_extras.io_utils import ImportHelper

from .parser import AnimGraphParser
from .json_io import load_file


class IMPORT_OT_redengine_animgraph(bpy.types.Operator, ImportHelper):
    bl_idname = "import_anim.redengine_animgraph"
    bl_label = "Import REDengine AnimGraph"
    bl_options = {'REGISTER', 'UNDO'}


    filename_ext = ".json"
    filter_glob: StringProperty(
        default="*animgraph.json",
        options={'HIDDEN', 'SKIP_SAVE'},
        maxlen=255,
    )
    use_filter: BoolProperty(default=True, options={'HIDDEN', 'SKIP_SAVE'})

    def _force_animgraph_filter(self):
        changed = False
        if getattr(self, 'filter_glob', None) != "*animgraph.json":
            self.filter_glob = "*animgraph.json"
            changed = True
        if not getattr(self, 'use_filter', True):
            self.use_filter = True
            changed = True
        return changed

    def invoke(self, context, event):
        self._force_animgraph_filter()
        return ImportHelper.invoke(self, context, event)

    def check(self, context):
        return self._force_animgraph_filter()

    def execute(self, context):
        try:
            if not self.filepath.lower().endswith(".animgraph.json"):
                self.report({'ERROR'}, "Expected a .animgraph.json file")
                return {'CANCELLED'}

            json_data = load_file(self.filepath)

            graph_name = bpy.path.display_name_from_filepath(self.filepath)
            tree = bpy.data.node_groups.new(name=graph_name, type='REDengine_AnimGraphTree')

            parser = AnimGraphParser(tree)
            parser.execute(json_data, context)

            msg = (
                f"Imported {graph_name}: {len(parser.definitions)} nodes, "
                f"{len(parser.containers)} subgraphs, {len(tree.variables)} variables"
            )
            if parser.skipped_cross_tree_links:
                msg += f", {parser.skipped_cross_tree_links} cross-tree links skipped"
            self.report({'INFO'}, msg)
            return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, f"Failed to import AnimGraph: {e}")
            return {'CANCELLED'}
