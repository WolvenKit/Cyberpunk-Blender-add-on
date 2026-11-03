import bpy

from ....blender.animgraph.rig_binding import binding_tree
from ....importers.animgraph.graph_import import rig_part_items
from .context import animgraph_editor_poll

_PART_ITEMS = []  # Blender reads dynamic enum strings after the items callback returns.


def _part_items(_self, context):
    root = binding_tree(getattr(context.space_data, "node_tree", None))
    armature = getattr(root, "red_bound_armature", None)
    _PART_ITEMS[:] = rig_part_items(armature) if armature is not None else []
    return _PART_ITEMS


class REDENGINE_OT_bind_rig_part(bpy.types.Operator):
    bl_idname = "redengine.bind_rig_part"
    bl_label = "Rig Part"
    bl_description = "The bound armature's MetaRig part the graph animates"
    bl_options = {"REGISTER", "UNDO"}

    part: bpy.props.EnumProperty(name="Rig Part", items=_part_items)

    @classmethod
    def poll(cls, context):
        return (
            animgraph_editor_poll(context)
            and binding_tree(context.space_data.node_tree).red_bound_armature
        )

    def execute(self, context):
        binding_tree(context.space_data.node_tree).red_rig_part = self.part
        return {"FINISHED"}
