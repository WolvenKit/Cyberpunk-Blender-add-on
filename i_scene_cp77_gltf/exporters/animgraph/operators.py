from __future__ import annotations

from typing import Any

import bpy

from ...animation.animgraph_constants import ANIMGRAPH_TREE_ID

from ...assetio import animgraph_json as json_io
from .variables import encode_root_variables
from .tree_document import encode_active_tree
from .root import encode_rootchunk_summary, encode_wolvenkit_json
from .nodes import _runtime_node, encode_selected_node

TEXT_SELECTED_NODE = "REDengine Encoded Selected Node"
TEXT_ROOT_VARIABLES = "REDengine Encoded Root Variables"
TEXT_ACTIVE_TREE = "REDengine Encoded Active Tree"
TEXT_ROOTCHUNK_JSON = "REDengine Encoded RootChunk JSON"
TEXT_EXPORT_REVERSAL_AUDIT = "REDengine Export Reversal Audit"

def _write_text_block(name: str, value: Any, *, copy_to_clipboard: bool = True) -> bpy.types.Text:
    text = bpy.data.texts.get(name)
    if text is None:
        text = bpy.data.texts.new(name)
    else:
        text.clear()
    rendered = json_io.dumps(value)
    text.write(rendered)
    if copy_to_clipboard:
        try:
            bpy.context.window_manager.clipboard = rendered
        except Exception:
            pass
    return text

class REDENGINE_OT_encode_rootchunk_json(bpy.types.Operator):
    bl_idname = 'redengine.encode_rootchunk_json'
    bl_label = 'Encode RootChunk JSON'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        space = context.space_data
        return (
            space is not None
            and space.type == 'NODE_EDITOR'
            and space.node_tree is not None
            and getattr(space.node_tree, 'bl_idname', '') == ANIMGRAPH_TREE_ID
        )

    def execute(self, context):
        try:
            tree = context.space_data.node_tree
            payload = encode_wolvenkit_json(tree)
            text = _write_text_block(TEXT_ROOTCHUNK_JSON, payload, copy_to_clipboard=False)
            summary = encode_rootchunk_summary(payload)
            self.report(
                {'INFO'},
                f"Encoded RootChunk JSON to Text: {text.name} "
                f"root={summary.get('rootHandle', '') or '<none>'} "
                f"nodes={summary.get('rootNodes', 0)} "
                f"full={summary.get('rootNodeFullEntries', 0)} "
                f"refs={summary.get('rootNodeRefEntries', 0)} "
                f"root-output={summary.get('rootOutputRef', '') or 'null'} "
                f"variables={summary.get('variables', 0)} "
                f"nodesToInit={summary.get('nodesToInit', 0)} "
                f"initRefs={summary.get('nodesToInitRefs', 0)}"
            )
            return {'FINISHED'}
        except Exception as exc:
            self.report({'ERROR'}, f"Failed to encode RootChunk JSON: {exc}")
            return {'CANCELLED'}

class REDENGINE_OT_encode_selected_node(bpy.types.Operator):
    bl_idname = 'redengine.encode_selected_node'
    bl_label = 'Encode Selected Node JSON'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        space = context.space_data
        node = getattr(context, 'active_node', None)
        return (
            space is not None
            and space.type == 'NODE_EDITOR'
            and space.node_tree is not None
            and getattr(space.node_tree, 'bl_idname', '') == ANIMGRAPH_TREE_ID
            and node is not None
            and _runtime_node(node)
        )

    def execute(self, context):
        try:
            entry = encode_selected_node(context)
            text = _write_text_block(TEXT_SELECTED_NODE, entry)
            self.report({'INFO'}, f"Encoded selected node to Text: {text.name} (also copied to clipboard)")
            return {'FINISHED'}
        except Exception as exc:
            self.report({'ERROR'}, f"Failed to encode selected node: {exc}")
            return {'CANCELLED'}

class REDENGINE_OT_encode_root_variables(bpy.types.Operator):
    bl_idname = 'redengine.encode_root_variables'
    bl_label = 'Encode Root Variables JSON'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        space = context.space_data
        return (
            space is not None
            and space.type == 'NODE_EDITOR'
            and space.node_tree is not None
            and getattr(space.node_tree, 'bl_idname', '') == ANIMGRAPH_TREE_ID
        )

    def execute(self, context):
        try:
            wrapper = encode_root_variables(context.space_data.node_tree)
            text = _write_text_block(TEXT_ROOT_VARIABLES, wrapper)
            self.report({'INFO'}, f"Encoded root variables to Text: {text.name} (also copied to clipboard)")
            return {'FINISHED'}
        except Exception as exc:
            self.report({'ERROR'}, f"Failed to encode root variables: {exc}")
            return {'CANCELLED'}

class REDENGINE_OT_encode_active_tree(bpy.types.Operator):
    bl_idname = 'redengine.encode_active_tree'
    bl_label = 'Encode Active Tree JSON'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        space = context.space_data
        return (
            space is not None
            and space.type == 'NODE_EDITOR'
            and space.node_tree is not None
            and getattr(space.node_tree, 'bl_idname', '') == ANIMGRAPH_TREE_ID
        )

    def execute(self, context):
        try:
            payload = encode_active_tree(context.space_data.node_tree)


            text = _write_text_block(TEXT_ACTIVE_TREE, payload, copy_to_clipboard=False)
            summary = payload.get('summary', {}) if isinstance(payload, dict) else {}
            self.report(
                {'INFO'},
                f"Encoded active tree to Text: {text.name} "
                f"nodes={summary.get('encodedNodes', 0)}/{summary.get('runtimeNodes', 0)} "
                f"editor-skipped={summary.get('editorSkipped', 0)} "
                f"blockers={summary.get('blockers', 0)} warnings={summary.get('warnings', 0)}"
            )
            return {'FINISHED'}
        except Exception as exc:
            self.report({'ERROR'}, f"Failed to encode active tree: {exc}")
            return {'CANCELLED'}


ANIMGRAPH_EXPORT_OPERATOR_CLASSES = (
    REDENGINE_OT_encode_selected_node,
    REDENGINE_OT_encode_root_variables,
    REDENGINE_OT_encode_active_tree,
    REDENGINE_OT_encode_rootchunk_json,
)
