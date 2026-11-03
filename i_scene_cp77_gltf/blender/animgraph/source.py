import bpy

from ...assetio import animgraph_json as json_io
from ..transactions import track_created_datablock
from .rig_binding import binding_tree


def graph_source_text(tree) -> bpy.types.Text | None:
    name = str(binding_tree(tree).red_source_text or "")
    return bpy.data.texts.get(name) if name else None


def store_graph_source(tree, raw_text: str, filepath: str) -> bpy.types.Text:
    """Keep raw_text as the graph's source document, reusing the text the graph already names"""
    root = binding_tree(tree)
    text = graph_source_text(root)
    if text is None:
        # A leading dot keeps the text out of Blender's text lists, like the dangle editor's source texts.
        text = track_created_datablock(
            "texts", bpy.data.texts.new(f".CP77_AnimGraph_Source_{root.name}")
        )
    text.clear()
    text.write(str(raw_text or ""))
    root.red_source_text = text.name
    root.red_source_path = str(filepath or "")
    return text


def load_graph_payload(tree) -> dict:
    text = graph_source_text(tree)
    if text is None:
        raise ValueError("This graph has no imported source document.")
    try:
        payload = json_io.loads(text.as_string())
    except Exception as exc:
        raise ValueError(
            f"The graph's stored source document is invalid: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise ValueError("The graph's stored source document is not a JSON object.")
    return payload
