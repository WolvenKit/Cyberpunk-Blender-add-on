import bpy

<<<<<<< Updated upstream
from ...animation.animgraph_constants import ANIMGRAPH_TREE_ID
from . import presenters
from .properties import REDengine_AnimNodeProperty
=======
from ...animation.model.animgraph.constants import ANIMGRAPH_TREE_ID
from ...core.log import get_logger
from . import node_lod, presenters
from .properties import (
    AIM_UP_CHANNEL_ITEMS,
    REDengine_AnimNodeProperty,
    REDengine_PointConstraintWeightedTransform,
    REDengine_SimpleBounceTrackOutput,
    REDengine_SimpleBounceTransformOutput,
)
from .sm_properties import (
    INTERPOLATION_TYPE_ITEMS,
    REDengine_SMStateRef,
    REDengine_SMTransition,
)

_LOG = get_logger(__name__)


def _on_copied(node, original) -> None:
    """Node.copy for AnimGraph nodes"""
    try:
        from . import sm_edit

        sm_edit.on_node_copied(node, original)
    except Exception:
        _LOG.exception(
            "AnimGraph node copy hook failed for %r", getattr(node, "name", node)
        )
>>>>>>> Stashed changes


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
<<<<<<< Updated upstream
    red_editor_subgraph_a_label: bpy.props.StringProperty(name="Editor Subgraph A Label")
    red_editor_subgraph_b_name: bpy.props.StringProperty(name="Editor Subgraph B")
    red_editor_subgraph_b_label: bpy.props.StringProperty(name="Editor Subgraph B Label")
    red_properties: bpy.props.CollectionProperty(type=REDengine_AnimNodeProperty)
    red_properties_index: bpy.props.IntProperty(name="Property")
=======
    red_editor_subgraph_a_label: bpy.props.StringProperty(
        name="Editor Subgraph A Label"
    )
    red_editor_subgraph_b_name: bpy.props.StringProperty(name="Editor Subgraph B")
    red_editor_subgraph_b_label: bpy.props.StringProperty(
        name="Editor Subgraph B Label"
    )
    red_properties: bpy.props.CollectionProperty(type=REDengine_AnimNodeProperty)
    red_properties_index: bpy.props.IntProperty(name="Property")
    red_simple_bounce_transform_outputs: bpy.props.CollectionProperty(
        type=REDengine_SimpleBounceTransformOutput
    )
    red_simple_bounce_transform_outputs_index: bpy.props.IntProperty(
        name="Transform Output", default=0
    )
    red_simple_bounce_track_outputs: bpy.props.CollectionProperty(
        type=REDengine_SimpleBounceTrackOutput
    )
    red_simple_bounce_track_outputs_index: bpy.props.IntProperty(
        name="Track Output", default=0
    )
    red_point_constraint_inputs: bpy.props.CollectionProperty(
        type=REDengine_PointConstraintWeightedTransform
    )
    red_point_constraint_inputs_index: bpy.props.IntProperty(
        name="Weighted Input", default=0
    )
    red_aim_up_transform: bpy.props.StringProperty(name="Up Transform")
    red_aim_up_anchor_transform: bpy.props.StringProperty(name="Up Anchor Transform")
    red_aim_up_vector: bpy.props.FloatVectorProperty(
        name="Up Vector", size=3, default=(0.0, 1.0, 0.0)
    )
    red_aim_up_channel_type: bpy.props.EnumProperty(
        name="Up Source",
        items=AIM_UP_CHANNEL_ITEMS,
        default="animAnimNodeSourceChannel_TransformVector",
    )
    red_transitions: bpy.props.CollectionProperty(type=REDengine_SMTransition)
    red_transitions_index: bpy.props.IntProperty(name="Transition", default=0)
    red_sm_any_interpolation: bpy.props.EnumProperty(
        name="Any State Interpolation", items=INTERPOLATION_TYPE_ITEMS, default="Linear"
    )
    red_sm_any_interpolator_json: bpy.props.StringProperty(
        name="Any State Interpolator"
    )
>>>>>>> Stashed changes

    @classmethod
    def poll(cls, ntree):
        return ntree.bl_idname == ANIMGRAPH_TREE_ID

    def init(self, context):
        pass

<<<<<<< Updated upstream
    def draw_buttons(self, context, layout):
=======
    def copy(self, node):
        _on_copied(self, node)

    def draw_buttons(self, context, layout):
        if node_lod.draw_placeholder(self, context, layout):
            return
>>>>>>> Stashed changes
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
<<<<<<< Updated upstream
    red_editor_subgraph_a_label: bpy.props.StringProperty(name="Editor Subgraph A Label")
    red_editor_subgraph_b_name: bpy.props.StringProperty(name="Editor Subgraph B")
    red_editor_subgraph_b_label: bpy.props.StringProperty(name="Editor Subgraph B Label")
    red_properties: bpy.props.CollectionProperty(type=REDengine_AnimNodeProperty)
    red_properties_index: bpy.props.IntProperty(name="Property")
=======
    red_editor_subgraph_a_label: bpy.props.StringProperty(
        name="Editor Subgraph A Label"
    )
    red_editor_subgraph_b_name: bpy.props.StringProperty(name="Editor Subgraph B")
    red_editor_subgraph_b_label: bpy.props.StringProperty(
        name="Editor Subgraph B Label"
    )
    red_properties: bpy.props.CollectionProperty(type=REDengine_AnimNodeProperty)
    red_properties_index: bpy.props.IntProperty(name="Property")
    red_transitions: bpy.props.CollectionProperty(type=REDengine_SMTransition)
    red_transitions_index: bpy.props.IntProperty(name="Transition", default=0)
    red_sm_states: bpy.props.CollectionProperty(type=REDengine_SMStateRef)
    red_sm_states_index: bpy.props.IntProperty(name="State", default=0)
    red_sm_records: bpy.props.BoolProperty(name="Transition Records", default=False)
    red_sm_import_notes: bpy.props.StringProperty(
        name="Import Notes",
        description="Import findings about this state machine's transitions, one per line (until dismissed)",
    )
>>>>>>> Stashed changes

    @classmethod
    def poll(cls, ntree):
        return ntree.bl_idname == ANIMGRAPH_TREE_ID

<<<<<<< Updated upstream
    def draw_buttons(self, context, layout):
        enter = layout.operator("redengine.enter_group", text="Enter Subgraph", icon="NODETREE")
=======
    def copy(self, node):
        _on_copied(self, node)

    def draw_buttons(self, context, layout):
        if node_lod.draw_placeholder(self, context, layout):
            return
        enter = layout.operator(
            "redengine.enter_group", text="Enter Subgraph", icon="NODETREE"
        )
>>>>>>> Stashed changes
        enter.node_name = self.name
        presenters.draw_node(self, context, layout)
