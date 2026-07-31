import bpy

from ...animation.animgraph_constants import ANIMGRAPH_TREE_ID
from . import presenters
from .properties import REDengine_AnimNodeProperty


class REDengine_AnimGraphNode_Generic(bpy.types.Node):
    bl_idname = "REDengine_AnimGraphNode_Generic"
    bl_label = "AnimGraph Node"

    red_type: bpy.props.StringProperty(name="Node Type")
    red_handle_id: bpy.props.StringProperty(name="Handle ID")
    red_exportable: bpy.props.BoolProperty(name="Exportable", default=True)
    red_pseudo: bpy.props.BoolProperty(name="Editor Node", default=False)
    red_parent_class: bpy.props.StringProperty(name="Parent Class")
    red_output_kind: bpy.props.StringProperty(name="Output Kind")
    red_presenter: bpy.props.StringProperty(name="Presenter", default="generic")
    red_metadata_known: bpy.props.BoolProperty(name="Metadata Known", default=False)
    red_roundtrip_ready: bpy.props.BoolProperty(name="Roundtrip Ready", default=False)
    red_roundtrip_notes: bpy.props.StringProperty(name="Roundtrip Notes")
    red_layout_auto: bpy.props.BoolProperty(name="Auto Layout", default=True)
    red_layout_locked: bpy.props.BoolProperty(name="Layout Locked", default=False)
    red_editor_subgraph_a_name: bpy.props.StringProperty(name="Editor Subgraph A")
    red_editor_subgraph_a_label: bpy.props.StringProperty(name="Editor Subgraph A Label")
    red_editor_subgraph_b_name: bpy.props.StringProperty(name="Editor Subgraph B")
    red_editor_subgraph_b_label: bpy.props.StringProperty(name="Editor Subgraph B Label")
    red_properties: bpy.props.CollectionProperty(type=REDengine_AnimNodeProperty)
    red_properties_index: bpy.props.IntProperty(name="Property")

    @classmethod
    def poll(cls, ntree):
        return ntree.bl_idname == ANIMGRAPH_TREE_ID

    def init(self, context):
        pass

    def draw_buttons(self, context, layout):
        presenters.draw_node(self, context, layout)


class REDengine_AnimGraphContainer(bpy.types.NodeCustomGroup):
    bl_idname = "REDengine_AnimGraphContainer"
    bl_label = "AnimGraph Container"

    red_type: bpy.props.StringProperty(name="Node Type")
    red_handle_id: bpy.props.StringProperty(name="Handle ID")
    red_exportable: bpy.props.BoolProperty(name="Exportable", default=True)
    red_pseudo: bpy.props.BoolProperty(name="Editor Node", default=False)
    red_parent_class: bpy.props.StringProperty(name="Parent Class")
    red_output_kind: bpy.props.StringProperty(name="Output Kind")
    red_presenter: bpy.props.StringProperty(name="Presenter", default="generic")
    red_metadata_known: bpy.props.BoolProperty(name="Metadata Known", default=False)
    red_roundtrip_ready: bpy.props.BoolProperty(name="Roundtrip Ready", default=False)
    red_roundtrip_notes: bpy.props.StringProperty(name="Roundtrip Notes")
    red_layout_auto: bpy.props.BoolProperty(name="Auto Layout", default=True)
    red_layout_locked: bpy.props.BoolProperty(name="Layout Locked", default=False)
    red_editor_subgraph_a_name: bpy.props.StringProperty(name="Editor Subgraph A")
    red_editor_subgraph_a_label: bpy.props.StringProperty(name="Editor Subgraph A Label")
    red_editor_subgraph_b_name: bpy.props.StringProperty(name="Editor Subgraph B")
    red_editor_subgraph_b_label: bpy.props.StringProperty(name="Editor Subgraph B Label")
    red_properties: bpy.props.CollectionProperty(type=REDengine_AnimNodeProperty)
    red_properties_index: bpy.props.IntProperty(name="Property")

    @classmethod
    def poll(cls, ntree):
        return ntree.bl_idname == ANIMGRAPH_TREE_ID

    def draw_buttons(self, context, layout):
        enter = layout.operator("redengine.enter_group", text="Enter Subgraph", icon="NODETREE")
        enter.node_name = self.name
        presenters.draw_node(self, context, layout)
