import bpy

from ...animation.model.animgraph.schema import enums
from .properties import REDengine_AnimArrayField

INTERPOLATION_TYPE_ENUM = "animAnimStateInterpolationType"
INTERPOLATION_TYPE_ITEMS = tuple(enums.enum_items(INTERPOLATION_TYPE_ENUM))
BLEND_INTERPOLATOR_TYPE = "animAnimStateTransitionInterpolator_Blend"


def _get_target_name(self):
    from . import sm_edit

    return sm_edit.target_name(self)


def _set_target_name(self, value):
    from . import sm_edit

    sm_edit.set_target_name(self, value)


def _get_state_label(self):
    from . import sm_edit

    return sm_edit.state_ref_label(self)


class REDengine_SMCondition(bpy.types.PropertyGroup):
    """One entry of a transition's flattened condition tree (see sm_conditions.FlatCondition)"""

    short: bpy.props.StringProperty(name="Condition")
    depth: bpy.props.IntProperty(name="Depth", default=0, min=0)
    handle_id: bpy.props.StringProperty(name="Handle ID")
    original_json: bpy.props.StringProperty(name="Original JSON")
    fields: bpy.props.CollectionProperty(type=REDengine_AnimArrayField)


class REDengine_SMTransition(bpy.types.PropertyGroup):
    """One transition (or conditional entry) stored on the node that owns it"""

    list_name: bpy.props.StringProperty(name="List", default="transitions")
    original_index: bpy.props.IntProperty(name="Original Index", default=-1)
    original_json: bpy.props.StringProperty(name="Original JSON")
    handle_id: bpy.props.StringProperty(name="Handle ID")
    target_handle: bpy.props.StringProperty(name="Target")
    target_name: bpy.props.StringProperty(
        name="Target",
        description="State this transition leads to",
        get=_get_target_name,
        set=_set_target_name,
    )

    enabled: bpy.props.BoolProperty(name="Enabled", default=True)
    forced_true: bpy.props.BoolProperty(name="Forced True")
    priority: bpy.props.IntProperty(name="Priority")
    duration: bpy.props.FloatProperty(name="Duration")
    can_request_inertialization: bpy.props.BoolProperty(
        name="Can Request Inertialization"
    )
    support_blend_from_pose: bpy.props.BoolProperty(name="Support Blend From Pose")
    is_out_transition_from_action: bpy.props.BoolProperty(
        name="Out Transition From Action"
    )

    interpolator_type: bpy.props.StringProperty(
        name="Interpolator", default=BLEND_INTERPOLATOR_TYPE
    )
    interpolator_handle: bpy.props.StringProperty(name="Interpolator Handle ID")
    interpolation_type: bpy.props.EnumProperty(
        name="Interpolation", items=INTERPOLATION_TYPE_ITEMS, default="Linear"
    )

    anim_feature_name: bpy.props.StringProperty(name="Anim Feature", default="None")
    action_db_path: bpy.props.StringProperty(name="Action Anim Database")
    sync_method_json: bpy.props.StringProperty(name="Sync Method")

    conditions: bpy.props.CollectionProperty(type=REDengine_SMCondition)
    condition_opaque_json: bpy.props.StringProperty(
        name="Shared Condition",
        description="Original condition kept verbatim because it holds references that could not be resolved",
    )
    conditions_index: bpy.props.IntProperty(name="Condition")


class REDengine_SMStateRef(bpy.types.PropertyGroup):
    """Handle of one State node, in the order of the state machine's states list"""

    handle: bpy.props.StringProperty(name="State Handle")
    label: bpy.props.StringProperty(name="State", get=_get_state_label)
