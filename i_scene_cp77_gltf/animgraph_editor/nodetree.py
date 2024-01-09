import bpy
from bpy.types import NodeTree, Node, NodeSocket, NodeTreeInterfaceSocket
import nodeitems_utils
from nodeitems_utils import NodeCategory, NodeItem

from bpy.utils import register_class, unregister_class

class CP77AnimGraphTree(NodeTree):
    bl_idname = 'cp77_animGraphEditor'
    bl_label = "Cyberpunk 2077 AnimGraph Editor"
    bl_icon = 'NODETREE'


def register():
    
    for cls in classes:
        register_class(cls)

    nodeitems_utils.register_node_categories('CUSTOM_NODES', node_categories)


def unregister():
    nodeitems_utils.unregister_node_categories('CUSTOM_NODES')

    
    for cls in reversed(classes):
        unregister_class(cls)


if __name__ == "__main__":
    register()
