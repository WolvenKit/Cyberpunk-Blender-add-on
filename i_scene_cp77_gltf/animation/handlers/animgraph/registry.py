from __future__ import annotations

from .additional_transform import AdditionalTransformHandler
from .aim_constraint import AimConstraintHandler
from .blends import (
    BlendAdditiveHandler,
    BlendMaskDynamicHandler,
    BlendMultipleHandler,
    BlendOverrideHandler,
    BlendTwoHandler,
)
from .cone_limit import ConeLimitHandler
from .direct_conn import FloatTrackDirectConnConstraintHandler
from .exploration import NpcExplorationHandler
from .facial_mixer import FacialMixerHandler
from .facial_pose import (
    EyesTracksLookAtHandler,
    SermoHandler,
    SetBonePositionHandler,
    SetTrackRangeHandler,
)
from .foot_step_scaling import FootStepScalingHandler
from .ik import (
    AddIkRequestHandler,
    Ik2ConstraintHandler,
    Ik2Handler,
    ReadIkRequestHandler,
)
from .inertialization import InertializationHandler
from .look_at import LookAtControllerHandler, LookAtHandler
from .math_expression import MathExpressionPoseHandler
from .orient_constraint import OrientConstraintHandler
from .parent_constraint import MultipleParentConstraintHandler, ParentConstraintHandler
from .passthrough import (
    IdentityHandler,
    InputHandler,
    NullLinkHandler,
    ReferenceHandler,
    SlotPassthroughHandler,
)
from .point_constraint import PointConstraintHandler
from .pose_space import PoseLsToMsHandler, PoseMsToLsHandler
from .rotate_bone_by_quaternion import RotateBoneByQuaternionHandler
from .rotation_limit import RotationLimitHandler
from .set_bone_orientation import SetBoneOrientationHandler
from .set_bone_transform import SetBoneTransformHandler
from .shared_meta_pose import FacialSharedMetaPoseHandler, SharedMetaPoseHandler
from .simple_bounce import SimpleBounceHandler
from .simple_spline import SimpleSplineHandler
from .sk_anim import SkAnimHandler
from .stack import StackHandler
from .state_machine import StateMachineHandler
from .suspension_limit import SuspensionLimitHandler
from .switch import SwitchHandler
from .tracks import (
    AdditionalFloatTrackHandler,
    FloatTrackModifierHandler,
    TrackSetterHandler,
    TransformToTrackHandler,
)
from .trajectory_meta_pose import TrajectoryFromMetaPoseHandler
from .translation_limit import TranslationLimitHandler
from .twist_constraint import TwistConstraintHandler
from .value_dynamics import (
    CriticalSpringDampHandler,
    DampFloatHandler,
    DampVectorHandler,
    FloatCumulativeHandler,
    FloatLatchHandler,
    FloatRandomHandler,
    FloatTimeDependentSinusHandler,
    IntLatchHandler,
    SignalHandler,
    SpringDampHandler,
    TimerHandler,
    ValueBySpeedHandler,
)
from .value_math import (
    CoordinateFromVectorHandler,
    CurveFloatValueHandler,
    DirectionToEulerHandler,
    FloatClampHandler,
    FloatComparatorHandler,
    FloatInterpolationHandler,
    FloatMathOpHandler,
    MathExpressionFloatHandler,
    MathExpressionQuaternionHandler,
    MathExpressionVectorHandler,
    QuaternionInterpolationHandler,
    VectorInterpolationHandler,
    VectorWsToMsHandler,
)
from .value_sources import (
    AnimSetTagValueHandler,
    BoolConstantHandler,
    BoolInputHandler,
    BoolJoinHandler,
    BoolToFloatConverterHandler,
    BoolVariableHandler,
    EventHandler,
    EventValueHandler,
    FloatConstantHandler,
    FloatInputHandler,
    FloatJoinHandler,
    FloatToBoolConverterHandler,
    FloatToIntConverterHandler,
    FloatVariableHandler,
    FPPCameraSharedVarHandler,
    IntConstantHandler,
    IntInputHandler,
    IntJoinHandler,
    IntToFloatConverterHandler,
    IntVariableHandler,
    MultiBoolToFloatValueHandler,
    NameHashConstantHandler,
    QuaternionConstantHandler,
    QuaternionInputHandler,
    QuaternionJoinHandler,
    TagValueHandler,
    VectorConstantHandler,
    VectorInputHandler,
    VectorJoinHandler,
    WrapperValueHandler,
)
from .vehicle import RotateBoneHandler, TranslateBoneHandler
from .workspot import WorkspotHubHandler


def _table(handlers):
    table = {}
    for handler in handlers:
        for node_type in handler.node_types:
            if node_type in table:
                raise RuntimeError(f"{node_type} has two pose operation handlers")
            table[node_type] = handler
    return table


POSE_OP_HANDLERS = _table(
    (
        SermoHandler(),
        EyesTracksLookAtHandler(),
        SetTrackRangeHandler(),
        TrackSetterHandler(),
        MathExpressionPoseHandler(),
        SetBonePositionHandler(),
        SetBoneTransformHandler(),
        OrientConstraintHandler(),
        ParentConstraintHandler(),
        MultipleParentConstraintHandler(),
        SetBoneOrientationHandler(),
        ConeLimitHandler(),
        AddIkRequestHandler(),
        FootStepScalingHandler(),
        ReadIkRequestHandler(),
        Ik2ConstraintHandler(),
        Ik2Handler(),
        LookAtHandler(),
        AdditionalTransformHandler(),
        RotateBoneByQuaternionHandler(),
        SuspensionLimitHandler(),
        TranslationLimitHandler(),
        RotationLimitHandler(),
        SimpleBounceHandler(),
        PointConstraintHandler(),
        SimpleSplineHandler(),
        TwistConstraintHandler(),
        AimConstraintHandler(),
        AdditionalFloatTrackHandler(),
        FloatTrackModifierHandler(),
        TransformToTrackHandler(),
        RotateBoneHandler(),
        TranslateBoneHandler(),
        FloatTrackDirectConnConstraintHandler(),
    )
)


GRAPH_NODE_HANDLERS = (
    InputHandler(),
    ReferenceHandler(),
    IdentityHandler(),
    NullLinkHandler(),
    SlotPassthroughHandler(),
    LookAtControllerHandler(),
    FacialMixerHandler(),
    TrajectoryFromMetaPoseHandler(),
    SwitchHandler(),
    BlendMaskDynamicHandler(),
    BlendMultipleHandler(),
    BlendTwoHandler(),
    FacialSharedMetaPoseHandler(),
    StateMachineHandler(),
    SkAnimHandler(),
    WorkspotHubHandler(),
    NpcExplorationHandler(),
    BlendOverrideHandler(),
    BlendAdditiveHandler(),
    SharedMetaPoseHandler(),
    PoseLsToMsHandler(),
    PoseMsToLsHandler(),
    InertializationHandler(),
    StackHandler(),
)
_GRAPH_NODE_BY_KIND = {
    kind: handler for handler in GRAPH_NODE_HANDLERS for kind in handler.kinds
}
_GRAPH_NODE_BY_PREFIX = tuple(
    (prefix, handler)
    for handler in GRAPH_NODE_HANDLERS
    for prefix in handler.kind_prefixes
)


def graph_node_handler(kind: str):
    """The handler of a program-node kind, matched exactly first and then by prefix, or None"""
    handler = _GRAPH_NODE_BY_KIND.get(kind)
    if handler is not None:
        return handler
    return next(
        (
            handler
            for prefix, handler in _GRAPH_NODE_BY_PREFIX
            if kind.startswith(prefix)
        ),
        None,
    )


VALUE_NODE_HANDLERS = _table(
    (
        IntInputHandler(),
        IntVariableHandler(),
        IntConstantHandler(),
        IntJoinHandler(),
        FloatToIntConverterHandler(),
        NameHashConstantHandler(),
        BoolInputHandler(),
        BoolVariableHandler(),
        BoolConstantHandler(),
        BoolJoinHandler(),
        FloatToBoolConverterHandler(),
        FloatInputHandler(),
        FloatVariableHandler(),
        IntToFloatConverterHandler(),
        BoolToFloatConverterHandler(),
        FloatConstantHandler(),
        FloatJoinHandler(),
        WrapperValueHandler(),
        EventHandler(),
        TagValueHandler(),
        AnimSetTagValueHandler(),
        EventValueHandler(),
        MultiBoolToFloatValueHandler(),
        VectorConstantHandler(),
        VectorInputHandler(),
        VectorJoinHandler(),
        QuaternionConstantHandler(),
        QuaternionInputHandler(),
        QuaternionJoinHandler(),
        IntLatchHandler(),
        FloatRandomHandler(),
        TimerHandler(),
        FloatLatchHandler(),
        DampFloatHandler(),
        CriticalSpringDampHandler(),
        SignalHandler(),
        FloatTimeDependentSinusHandler(),
        SpringDampHandler(),
        FloatCumulativeHandler(),
        MathExpressionFloatHandler(),
        MathExpressionVectorHandler(),
        MathExpressionQuaternionHandler(),
        FloatClampHandler(),
        CurveFloatValueHandler(),
        FloatMathOpHandler(),
        FloatComparatorHandler(),
        DirectionToEulerHandler(),
        FPPCameraSharedVarHandler(),
        CoordinateFromVectorHandler(),
        FloatInterpolationHandler(),
        VectorInterpolationHandler(),
        QuaternionInterpolationHandler(),
        VectorWsToMsHandler(),
        ValueBySpeedHandler(),
        DampVectorHandler(),
    )
)
