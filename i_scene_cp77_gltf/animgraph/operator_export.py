from __future__ import annotations

import json
import os
import re

import bpy
from bpy_extras.io_utils import ExportHelper

from .constants import ANIMGRAPH_TREE_ID
from .json_encoder import encode_wolvenkit_json, encode_rootchunk_summary
from .json_io import dump_file
try:
    from . import variable_bindings
except Exception:
    variable_bindings = None


FILENAME_EXT = ".animgraph.json"
_ANIMGRAPH_TOKEN = ".animgraph"
_JSON_TOKEN = ".json"
_BLENDER_DUPLICATE_SUFFIX_RE = re.compile(r"\.\d{3,}$")


def _strip_repeated_animgraph_json_suffix(name: str) -> str:
    """Return a stable base name for .animgraph.json export paths."""
    stem = str(name or '').strip() or 'animgraph'
    while True:
        lower = stem.lower()
        if lower.endswith(_JSON_TOKEN):
            stem = stem[:-len(_JSON_TOKEN)]
            continue
        if lower.endswith(_ANIMGRAPH_TOKEN):
            stem = stem[:-len(_ANIMGRAPH_TOKEN)]
            continue
        duplicate_match = _BLENDER_DUPLICATE_SUFFIX_RE.search(stem)
        if duplicate_match is not None and duplicate_match.end() == len(stem):
            stem = stem[:duplicate_match.start()]
            continue
        break
    return stem or 'animgraph'


def _animgraph_json_name(name: str) -> str:
    return f"{_strip_repeated_animgraph_json_suffix(name)}{FILENAME_EXT}"


def _root_tree(tree):
    if variable_bindings is not None:
        try:
            return variable_bindings.root_tree_for(tree) or tree
        except Exception:
            pass
    return tree


def _default_export_name(tree) -> str:
    root = _root_tree(tree)
    name = str(getattr(root, 'name', '') or 'animgraph')
    return _animgraph_json_name(name)


def _ensure_animgraph_json_path(filepath: str) -> str:
    path = str(filepath or '')
    if not path:
        return path
    directory, basename = os.path.split(path)
    normalized = _animgraph_json_name(basename or 'animgraph')
    return os.path.join(directory, normalized) if directory else normalized


def menu_func_export(self, _context):
    self.layout.operator(EXPORT_OT_redengine_animgraph.bl_idname,
                         text="REDengine AnimGraph (.animgraph.json)")


class EXPORT_OT_redengine_animgraph(bpy.types.Operator, ExportHelper):
    bl_idname = "export_anim.redengine_animgraph"
    bl_label = "Export REDengine AnimGraph"
    bl_options = {'REGISTER'}

    filename_ext = FILENAME_EXT
    filter_glob: bpy.props.StringProperty(default="*.animgraph.json", options={'HIDDEN'})

    @classmethod
    def poll(cls, context):
        space = context.space_data
        return (
            space is not None
            and space.type == 'NODE_EDITOR'
            and space.node_tree is not None
            and getattr(space.node_tree, 'bl_idname', '') == ANIMGRAPH_TREE_ID
        )

    def invoke(self, context, event):
        tree = context.space_data.node_tree
        current_path = str(getattr(self, 'filepath', '') or '').strip()
        if current_path:


            self.filepath = _ensure_animgraph_json_path(current_path)
        else:
            self.filepath = _default_export_name(tree)
        return ExportHelper.invoke(self, context, event)

    def check(self, context):


        filepath = str(getattr(self, 'filepath', '') or '')
        normalized = _ensure_animgraph_json_path(filepath) if filepath else filepath
        if normalized and normalized != filepath:
            self.filepath = normalized
            return True
        return False

    def execute(self, context):
        tree = context.space_data.node_tree
        filepath = _ensure_animgraph_json_path(self.filepath)
        if not filepath:
            self.report({'ERROR'}, "No export path selected")
            return {'CANCELLED'}

        try:
            payload = encode_wolvenkit_json(tree)

            basename = os.path.basename(filepath)
            archive = basename[:-len('.json')] if basename.lower().endswith('.json') else basename
            if archive:
                payload.setdefault('Header', {})['ArchiveFileName'] = archive

            dump_file(filepath, payload, indent=2)

            summary = encode_rootchunk_summary(payload)
            self.filepath = filepath
            self.report(
                {'INFO'},
                f"Exported AnimGraph JSON: {filepath} "
                f"nodesToInit={summary.get('nodesToInit', 0)} "
                f"rootNodes={summary.get('rootNodes', 0)} "
                f"variables={summary.get('variables', 0)}"
            )
            return {'FINISHED'}
        except Exception as exc:
            self.report({'ERROR'}, f"Failed to export AnimGraph JSON: {exc}")
            return {'CANCELLED'}
