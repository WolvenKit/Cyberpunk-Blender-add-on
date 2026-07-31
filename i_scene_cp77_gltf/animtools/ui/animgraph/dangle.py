import bpy

from ....animation.animgraph_constants import ANIMGRAPH_TREE_ID

def _root_animgraph_tree(tree):
    current = tree
    visited = set()
    while current is not None:
        try:
            pointer = int(current.as_pointer())
        except Exception:
            pointer = id(current)
        if pointer in visited:
            break
        visited.add(pointer)
        parent_name = str(current.get("red_parent_graph", "") or "")
        if not parent_name:
            break
        parent = bpy.data.node_groups.get(parent_name)
        if parent is None:
            break
        current = parent
    return current

class REDENGINE_PT_dangle_bridge(bpy.types.Panel):
    bl_idname = "REDENGINE_PT_dangle_bridge"
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "AnimGraph"
    bl_label = "Dangle Editor"

    @classmethod
    def poll(cls, context):
        space = context.space_data
        if space is None or space.type != 'NODE_EDITOR':
            return False
        tree = _root_animgraph_tree(space.node_tree)
        return bool(
            tree is not None
            and tree.bl_idname == ANIMGRAPH_TREE_ID
            and str(tree.get("cp77_dangle_rig", "") or "")
        )

    def draw(self, context):
        layout = self.layout
        root = _root_animgraph_tree(context.space_data.node_tree)
        rig_name = str(root.get("cp77_dangle_rig", "") or "") if root else ""
        if rig_name:
            layout.label(text=f"Rig: {rig_name}", icon='ARMATURE_DATA')

        row = layout.row(align=True)
        row.operator("dangle.switch_to_editor", icon='VIEW3D', text="Editor View")

        sync_row = layout.row(align=True)
        sync_row.operator("dangle.push_to_editor", icon='EXPORT', text="Push to Editor")
        sync_row.operator("dangle.pull_from_editor", icon='IMPORT', text="Pull from Editor")
