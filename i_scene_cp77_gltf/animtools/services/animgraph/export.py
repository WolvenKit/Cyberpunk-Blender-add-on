from ....blender.animgraph.rig_binding import binding_tree
from ....blender.animgraph.source import store_graph_source
from ....collisiontools.blender.dangle_context import rig_for_graph_tree
from ....collisiontools.services.dangles.sync import export_from_specialist_editor
from ....exporters.animgraph.root import write_graph_document


def export_graph(path: str, tree, context=None) -> dict:
    """Write the graph tree belongs to at path"""
    root = binding_tree(tree)
    rig = rig_for_graph_tree(root)
    if rig is not None and rig.dangle_state.is_dangle_rig:
        return export_from_specialist_editor(path, rig, context)
    store_graph_source(root, write_graph_document(path, root), path)
    return {"path": path}
