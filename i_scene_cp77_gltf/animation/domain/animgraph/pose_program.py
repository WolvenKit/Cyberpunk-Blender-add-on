from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ....assetio.values import cname_text, coerce_int
from ...model.animgraph.program import PoseProgramNode, PoseProgramPlan
from ...model.animgraph.schema import registry, rtti
from .additional_transform import additional_transform_data
from .aim_constraint import aim_constraint_data
from .blends import (
    blend_additive_data,
    blend_mask_dynamic_data,
    blend_multiple_data,
    blend_override_data,
    blend_two_data,
)
from .cone_limit import cone_limit_data
from .facial_mixer import normalize_facial_mixer
from .facial_pose import (
    eyes_tracks_look_at_data,
    sermo_data,
    set_bone_position_data,
    set_track_range_data,
)
from .foot_step_scaling import foot_step_scaling_data
from .ik import add_ik_request_data, ik2_constraint_data, ik2_data, read_ik_request_data
from .inertialization import inertialization_data
from .look_at import normalize_look_at_controller
from .look_at_node import look_at_node_data
from .math_expression import math_expression_pose_data
from .orient_constraint import orient_constraint_data
from .parent_constraint import multiple_parent_constraint_data, parent_constraint_data
from .point_constraint import point_constraint_data
from .rotate_bone_by_quaternion import rotate_bone_by_quaternion_data
from .rotation_limit import rotation_limit_data
from .set_bone_orientation import set_bone_orientation_data
from .set_bone_transform import set_bone_transform_data
from .shared_meta_pose import shared_meta_pose_additive_data, shared_meta_pose_data
from .simple_bounce import simple_bounce_data
from .simple_spline import simple_spline_data
from .sk_anim import sk_anim_data
from .slots import graph_slot_conditions_data, slot_data
from .stack import (
    normalize_track_extender,
    normalize_track_shrinker,
    normalize_transform_extender,
    normalize_transform_shrinker,
)
from .state_machine import state_machine_data
from .suspension_limit import suspension_limit_data
from .switch import selector_switch_data, switch_data
from .topology import (
    GraphTopologyError,
    PreviewBoundary,
    compilation_children,
    link_targets,
    linked_node,
    reference_handle,
    resolve,
    static_switch_branch,
)
from .tracks import (
    additional_float_track_data,
    float_track_modifier_data,
    track_setter_data,
    transform_track_data,
)
from .trajectory_meta_pose import trajectory_from_meta_pose_data
from .translation_limit import translation_limit_data
from .twist_constraint import twist_constraint_data
from .vehicle import rotate_bone_data, translate_bone_data
from .workspot import workspot_hub_data

# The program data of every pose operation the runtime evaluates from document data.
POSE_OP_DATA = {
    "animAnimNode_Sermo": sermo_data,
    "animAnimNode_EyesTracksLookAt": eyes_tracks_look_at_data,
    "animAnimNode_SetTrackRange": set_track_range_data,
    "animAnimNode_TrackSetter": track_setter_data,
    "animAnimNode_MathExpressionPose": math_expression_pose_data,
    "animAnimNode_SetBonePosition": set_bone_position_data,
    "animAnimNode_SetBoneTransform": set_bone_transform_data,
    "animAnimNode_OrientConstraint": orient_constraint_data,
    "animAnimNode_TranslationLimit": translation_limit_data,
    "animAnimNode_RotationLimit": rotation_limit_data,
    "animAnimNode_SuspensionLimit": suspension_limit_data,
    "animAnimNode_SimpleBounce": simple_bounce_data,
    "animAnimNode_FloatTrackDirectConnConstraint": transform_track_data,
    "animAnimNode_PointConstraint": point_constraint_data,
    "animAnimNode_SimpleSpline": simple_spline_data,
    "animAnimNode_TwistConstraint": twist_constraint_data,
    "animAnimNode_AimConstraint": aim_constraint_data,
    "animAnimNode_AimConstraint_ObjectUp": aim_constraint_data,
    "animAnimNode_AimConstraint_ObjectRotationUp": aim_constraint_data,
    "animAnimNode_AdditionalFloatTrack": additional_float_track_data,
    "animAnimNode_FloatTrackModifier": float_track_modifier_data,
    "animAnimNode_FloatTrackModifierMarkUnstable": float_track_modifier_data,
    "animAnimNode_TransformToTrack": transform_track_data,
    "animAnimNode_RotateBone": rotate_bone_data,
    "animAnimNode_TranslateBone": translate_bone_data,
    "animAnimNode_ParentConstraint": parent_constraint_data,
    "animAnimNode_MultipleParentConstraint": multiple_parent_constraint_data,
    "animAnimNode_SetBoneOrientation": set_bone_orientation_data,
    "animAnimNode_ConeLimit": cone_limit_data,
    "animAnimNode_AdditionalTransform": additional_transform_data,
    "animAnimNode_RotateBoneByQuaternion": rotate_bone_by_quaternion_data,
    "animAnimNode_AddIkRequest": add_ik_request_data,
    "animAnimNode_ReadIkRequest": read_ik_request_data,
    "animAnimNode_Ik2Constraint": ik2_constraint_data,
    "animAnimNode_Ik2": ik2_data,
    "animAnimNode_LookAt": look_at_node_data,
    "animAnimNode_FootStepScaling": foot_step_scaling_data,
}
PURE_POSE_OP_TYPES = frozenset(POSE_OP_DATA)
# DirectConnConstraint has no document data of its own; the runtime evaluates it through the node editor's chain.
POSE_OP_TYPES = PURE_POSE_OP_TYPES | {"animAnimNode_DirectConnConstraint"}

# Pose operations are defined on REDengine joint frames (bone-local axes, engine
# model-space rotations, engine local transforms). Track-only operations need no
# conversion, and Sermo only runs on the engine-space bridge.
ENGINE_SPACE_POSE_OPS = PURE_POSE_OP_TYPES - frozenset(
    {
        "animAnimNode_Sermo",
        "animAnimNode_SetTrackRange",
        "animAnimNode_TrackSetter",
        "animAnimNode_AdditionalFloatTrack",
        "animAnimNode_FloatTrackModifier",
        "animAnimNode_FloatTrackModifierMarkUnstable",
    }
)

TRANSPARENT_TYPES = frozenset(
    {
        "animAnimNode_Output",
        "animAnimNode_Join",
        "animAnimNode_SelectiveJoin",
        # Console-only skips are inactive on PC and a preview is a foreground instance.
        "animAnimNode_SkipConsoleBegin",
        "animAnimNode_SkipConsoleEnd",
        "animAnimNode_ForegroundSegmentBegin",
        "animAnimNode_ForegroundSegmentEnd",
        "animAnimNode_DisableLunaticMode",
        # No active ragdoll: RagdollControl outputs its inputPoseNode unchanged.
        "animAnimNode_RagdollControl",
        # Writes IK anim features only; the pose passes through.
        "animAnimNode_GenerateIkAnimFeatureData",
        # Copies transforms from a parent object's pose, which a preview does not have.
        "animAnimNode_ParentTransform",
        # Foot IK is disabled outside the game world (no ground collision), so the pose passes through.
        "animAnimNode_AddSnapToTerrainIkRequest",
        # Corrections arrive only as gameplay animPoseCorrectionParams events; without one the pose passes through.
        "animAnimNode_PoseCorrection",
        # A stage's entry passes on the stage input it is linked to.
        # Vehicle look-at restrictions arrive only from gameplay; without them the pose passes through.
        "animAnimNode_LookAtApplyVehicleRestrictions",
        # The first-person camera turns the camera bones by the player's camera input; with none, as in a preview,
        # it turns them by nothing and the pose passes through.
        "animAnimNode_FPPCamera",
        # A curve-path slot passes its input on.
        "animAnimNode_CurvePathSlot",
        "animAnimNode_StagePoseEntry",
    }
)
SLOT_TYPES = frozenset(
    {
        "animAnimNode_GraphSlot",
        # A test slot attaches a graph from another file, which a preview does not attach.
        "animAnimNode_GraphSlot_Test",
        "animAnimNode_MixerSlot",
    }
)
# Stack node type -> (program kind, data normaliser).
STACK_RULES = {
    "animAnimNode_StackTransformsExtender": (
        "STACK_TRANSFORMS_EXTEND",
        normalize_transform_extender,
    ),
    "animAnimNode_StackTransformsShrinker": (
        "STACK_TRANSFORMS_SHRINK",
        normalize_transform_shrinker,
    ),
    "animAnimNode_StackTracksExtender": (
        "STACK_TRACKS_EXTEND",
        normalize_track_extender,
    ),
    "animAnimNode_StackTracksShrinker": (
        "STACK_TRACKS_SHRINK",
        normalize_track_shrinker,
    ),
}
RUNTIME_BRANCH_TYPES = frozenset(
    {
        "animAnimNode_RuntimeSwitch",
        "animAnimNode_TriggerBranch",
    }
)
# Program kinds that become program nodes of their own.
_NODE_KINDS = frozenset(
    {
        "DANGLE",
        "DRAG",
        "POSE_OP",
        "LOOK_AT_CONTROLLER",
        "FACIAL_MIXER",
        "TRAJECTORY_FROM_META_POSE",
        "SHARED_META_POSE",
        "FACIAL_SHARED_META_POSE",
        "SHARED_META_POSE_ADDITIVE",
        "POSE_LS_TO_MS",
        "POSE_MS_TO_LS",
        "INERTIALIZATION",
        "STACK_TRANSFORMS_EXTEND",
        "STACK_TRANSFORMS_SHRINK",
        "STACK_TRACKS_EXTEND",
        "STACK_TRACKS_SHRINK",
        "SK_ANIM",
        "STATE_MACHINE",
        "SLOT_PASSTHROUGH",
        "SWITCH",
        "BLEND_TWO",
        "BLEND_MULTIPLE",
        "BLEND_MASK_DYNAMIC",
        "WORKSPOT_HUB",
        "NPC_EXPLORATION",
    }
)

_SEGMENT_BEGIN_TO_END = {
    "animAnimNode_ConditionalSegmentBegin": "animAnimNode_ConditionalSegmentEnd",
    "animAnimNode_LODBegin": "animAnimNode_LODEnd",
    "animAnimNode_SkipPerformanceModeBegin": "animAnimNode_SkipPerformanceModeEnd",
}
_SEGMENT_END_TO_BEGIN = {value: key for key, value in _SEGMENT_BEGIN_TO_END.items()}


def pure_pose_op_data(node_type: str, node: Mapping[str, Any]) -> Mapping[str, Any]:
    """A pose operation's program data from its document or encoded editor properties"""
    builder = POSE_OP_DATA.get(node_type)
    return builder(node_type, node) if builder is not None else {}


def _pose_children(node, index):
    return list(link_targets(node, index, pose_only=True))


def _single_pose_child(node, index):
    children = _pose_children(node, index)
    if len(children) > 1:
        raise GraphTopologyError(
            f"{node.get('$type', '') or '<unknown>'!s} has multiple pose inputs"
        )
    return children[0][1] if children else None


def _paired_segment_begin(end_node, index):
    end_type = str(end_node.get("$type", "") or "")
    begin_type = _SEGMENT_END_TO_BEGIN.get(end_type)
    if not begin_type:
        raise GraphTopologyError(
            f"{end_type or '<unknown>'} is not a supported segment end"
        )
    depth = 0
    reference = _single_pose_child(end_node, index)
    visited = set()
    while reference is not None:
        node = resolve(reference, index)
        if not isinstance(node, Mapping):
            raise GraphTopologyError(
                f"{end_type} segment contains an unresolved pose link"
            )
        handle = reference_handle(reference) or f"inline:{id(node)}"
        if handle in visited:
            raise GraphTopologyError(
                f"{end_type} segment pairing encountered a pose cycle"
            )
        visited.add(handle)
        node_type = str(node.get("$type", "") or "")
        if node_type == end_type:
            depth += 1
        elif node_type == begin_type:
            if depth == 0:
                return node
            depth -= 1
        reference = _single_pose_child(node, index)
    raise GraphTopologyError(f"{end_type} has no matching {begin_type}")


def _segment_pairs(root_reference, index, *, end_type: str, begin_type: str):
    pairs = {}
    open_ends = []
    visited = set()
    stack = [root_reference]
    while stack:
        reference = stack.pop()
        if reference is None:
            continue
        node = resolve(reference, index)
        if not isinstance(node, Mapping):
            continue
        handle = reference_handle(reference) or f"inline:{id(node)}"
        if handle in visited:
            continue
        visited.add(handle)
        node_type = str(node.get("$type", "") or "")
        if node_type == end_type:
            open_ends.append(handle)
        elif node_type == begin_type and open_ends:
            pairs[open_ends.pop()] = node
        children = compilation_children(node, index)
        stack.extend(reversed(children))
    return pairs


def _conditional_segment_active(
    begin_node, skeletal_lod: int, anim_features: Mapping[tuple[str, str], bool] | None
):
    condition = (
        begin_node.get("condition")
        if isinstance(begin_node.get("condition"), Mapping)
        else {}
    )
    lod = coerce_int(condition.get("lod", -1), -1, unwrap=False)
    if lod > -1:
        return int(skeletal_lod) <= lod, f"LOD {int(skeletal_lod)} <= {lod}"
    group = cname_text(condition.get("group"))
    name = cname_text(condition.get("name"))
    key = (group, name)
    if group in {"", "None"} and name in {"", "None"}:
        # An unnamed feature never binds an instance value, and an unbound condition is not satisfied.
        return False, "unnamed anim feature"
    if anim_features is None or key not in anim_features:
        raise GraphTopologyError(
            f"ConditionalSegment anim feature {group or '<none>'}/{name or '<none>'} has no preview value"
        )
    expected = bool(condition.get("animFeatureValue", False))
    actual = bool(anim_features[key])
    return actual == expected, f"feature {group}/{name}={actual} expected {expected}"


class _NullPoseLink:
    """A serialized pose link with no node, evaluating to the reference pose"""

    __slots__ = ("path",)

    def __init__(self, path: str):
        self.path = path


# Multi-input kinds a synchronisation passes through to the clips below.
_SYNC_THROUGH = frozenset({"SWITCH", "BLEND_MULTIPLE", "BLEND_TWO", "BLEND_ADDITIVE"})
_SYNC_LABELS = {
    "SWITCH": "Switch",
    "BLEND_MULTIPLE": "BlendMultiple",
    "BLEND_TWO": "Blend2",
}


def _switch_sync_unsupported(children) -> str:
    """The first program kind under a synchronised switch that the preview cannot synchronise, or ''"""
    pending = list(children)
    seen: set[int] = set()
    while pending:
        node = pending.pop()
        if node is None or id(node) in seen:
            continue
        seen.add(id(node))
        if node.kind == "SK_ANIM":
            continue
        if node.kind in _SYNC_THROUGH or len(node.children) <= 1:
            pending.extend(node.children)
            continue
        return node.kind
    return ""


def _is_sk_anim_type(node_type: str) -> bool:
    return (
        node_type == "animAnimNode_SkAnim"
        or "animAnimNode_SkAnim" in registry.parent_chain(node_type)
    )


def compile_pose_program(
    root_reference,
    index,
    *,
    visual_tags=None,
    skeletal_lod: int = 0,
    performance_mode: bool = False,
    anim_features: Mapping[tuple[str, str], bool] | None = None,
    available_animations: frozenset[str] | set[str] | None = None,
    rig_tags: frozenset[str] | set[str] | None = None,
    parent_tags: frozenset[str] | set[str] | None = None,
) -> PoseProgramPlan:
    """Compile the active pose graph without recursing through deep REDengine chains"""
    boundaries: list[str] = []
    operations: list[tuple[str, str, str]] = []
    blends: list[str] = []
    operation_seen: set[tuple[str, str]] = set()
    blend_seen: set[str] = set()
    results: dict[str, PoseProgramNode | None] = {}
    visiting: set[str] = set()
    frames: dict[str, dict[str, Any]] = {}
    # Segments pair in compile order: each End is pushed depth first and the next Begin pops it,
    # whatever lies in between.
    segment_pairs = {
        end_type: _segment_pairs(
            root_reference, index, end_type=end_type, begin_type=begin_type
        )
        for begin_type, end_type in _SEGMENT_BEGIN_TO_END.items()
    }
    lod_pairs = segment_pairs["animAnimNode_LODEnd"]

    def boundary(path, text):
        message = f"{path}: {text}"
        if message not in boundaries:
            boundaries.append(message)

    def resolved(reference):
        if reference is None:
            return None, ""
        node = resolve(reference, index)
        if not isinstance(node, Mapping):
            return None, ""
        handle = reference_handle(reference) or f"inline:{id(node)}"
        return node, handle

    def token(reference, path):
        if isinstance(reference, _NullPoseLink):
            return f"null:{reference.path}"
        if reference is None:
            return f"input:{path}"
        node, handle = resolved(reference)
        return handle if node is not None else f"invalid:{path}"

    def null_link(child_path):
        link = _NullPoseLink(child_path)
        results[token(link, child_path)] = PoseProgramNode(
            "NULL_LINK", "", "NullPoseLink", child_path, {}
        )
        return link

    def link_child(node, field, path):
        """Child spec for a pose link field"""
        target = linked_node(node, field)
        child_path = f"{path}.{field}"
        return (
            (target, child_path)
            if target is not None
            else (null_link(child_path), child_path)
        )

    def input_children(inputs, path):
        return [
            link_child(
                {"inputNode": item if isinstance(item, Mapping) else {}},
                "inputNode",
                f"{path}.inputNodes[{i}]",
            )
            for i, item in enumerate(inputs)
        ]

    def single_input(node, node_type, path, default_field="input"):
        children = _pose_children(node, index)
        if len(children) > 1:
            raise PreviewBoundary(f"{node_type} has multiple pose inputs")
        return (
            [(children[0][1], f"{path}.{children[0][0]}")]
            if children
            else [(None, f"{path}.{default_field}")]
        )

    def compile_node(node, node_type, handle, path):
        """(kind, child specs, data) of one graph node, or a finished leaf program node"""
        ancestors = registry.parent_chain(node_type)
        if node_type == "animAnimNode_StaticSwitch":
            try:
                branch = static_switch_branch(
                    node,
                    index,
                    visual_tags=visual_tags,
                    available_animations=available_animations,
                    rig_tags=rig_tags,
                    parent_tags=parent_tags,
                )
            except GraphTopologyError as error:
                raise PreviewBoundary(str(error)) from error
            return "PASS", [(linked_node(node, branch), f"{path}.{branch}")], {}
        if node_type in _SEGMENT_END_TO_BEGIN:
            try:
                if node_type == "animAnimNode_LODEnd":
                    if int(skeletal_lod) <= 0:
                        begin_node = None
                        active = True
                    else:
                        begin_node = lod_pairs.get(handle)
                        if not isinstance(begin_node, Mapping):
                            raise GraphTopologyError(
                                "animAnimNode_LODEnd has no matching animAnimNode_LODBegin"
                            )
                        try:
                            level_of_detail = int(
                                begin_node.get("levelOfDetail", 0) or 0
                            )
                        except (TypeError, ValueError) as exc:
                            raise GraphTopologyError(
                                "LODBegin levelOfDetail is not an integer"
                            ) from exc
                        active = int(skeletal_lod) <= level_of_detail
                else:
                    begin_node = segment_pairs[node_type].get(handle)
                    if not isinstance(begin_node, Mapping):
                        begin_node = _paired_segment_begin(node, index)
                    if node_type == "animAnimNode_ConditionalSegmentEnd":
                        active, _reason = _conditional_segment_active(
                            begin_node, skeletal_lod, anim_features
                        )
                    else:
                        active = not bool(performance_mode)
                selected = _single_pose_child(node if active else begin_node, index)
            except GraphTopologyError as error:
                raise PreviewBoundary(str(error)) from error
            data = {
                "active": bool(active),
                "skeletalLOD": int(skeletal_lod),
                "performanceMode": bool(performance_mode),
            }
            return (
                "PASS",
                [(selected, f"{path}.{'inputLink' if active else 'skipLink'}")],
                data,
            )
        if node_type in _SEGMENT_BEGIN_TO_END:
            try:
                selected = _single_pose_child(node, index)
            except GraphTopologyError as error:
                raise PreviewBoundary(str(error)) from error
            return "PASS", [(selected, f"{path}.inputLink")], {}
        if node_type in {"animAnimNode_PoseLsToMs", "animAnimNode_PoseMsToLs"}:
            kind = (
                "POSE_LS_TO_MS"
                if node_type == "animAnimNode_PoseLsToMs"
                else "POSE_MS_TO_LS"
            )
            return kind, single_input(node, node_type, path), {}
        if node_type in STACK_RULES:
            kind, normalize = STACK_RULES[node_type]
            return kind, single_input(node, node_type, path), normalize(node)
        if _is_sk_anim_type(node_type):
            children = _pose_children(node, index)
            one_shot = node_type == "animAnimNode_SkOneShotAnim"
            if children and not (one_shot and len(children) == 1):
                raise PreviewBoundary(
                    f"{node_type} source-animation preview does not yet support pose-input decorators"
                )
            # A one-shot clip plays once over its input pose, then passes the input through.
            child_specs = (
                (
                    [(children[0][1], f"{path}.{children[0][0]}")]
                    if children
                    else [(None, f"{path}.Input")]
                )
                if one_shot
                else []
            )
            return "SK_ANIM", child_specs, sk_anim_data(node, one_shot=one_shot)
        if node_type == "animAnimNode_StateMachine":
            data, state_refs = state_machine_data(node, index)
            return (
                "STATE_MACHINE",
                [(ref, f"{path}.states[{i}]") for i, ref in enumerate(state_refs)],
                data,
            )
        if node_type == "animAnimNode_Switch":
            data, active_inputs = switch_data(node, index)
            child_specs = []
            for i, item in enumerate(active_inputs):
                input_path = f"{path}.inputNodes[{i}]"
                target = item.get("node")
                child_specs.append(
                    (null_link(input_path) if target is None else target, input_path)
                )
            return "SWITCH", child_specs, data
        if node_type == "animAnimNode_BlendByMaskDynamic":
            data = blend_mask_dynamic_data(node)
            return (
                "BLEND_MASK_DYNAMIC",
                [link_child(node, "base", path), link_child(node, "blend", path)],
                data,
            )
        if node_type in {"animAnimNode_EnumSwitch", "animAnimNode_InputSwitch"}:
            data, inputs = selector_switch_data(node_type, node, index)
            return "SWITCH", input_children(inputs, path), data
        if node_type == "animAnimNode_BlendMultiple":
            data, inputs = blend_multiple_data(node, index)
            return "BLEND_MULTIPLE", input_children(inputs, path), data
        if (
            node_type in RUNTIME_BRANCH_TYPES
            or "animAnimNode_StateMachine" in ancestors
        ):
            raise PreviewBoundary(f"{node_type} requires runtime branch evaluation")
        if node_type in {
            "animAnimNode_SharedMetaPose",
            "animAnimNode_FacialSharedMetaPose",
        }:
            kind = (
                "FACIAL_SHARED_META_POSE"
                if node_type == "animAnimNode_FacialSharedMetaPose"
                else "SHARED_META_POSE"
            )
            return (
                kind,
                single_input(node, node_type, path),
                shared_meta_pose_data(node),
            )
        if node_type == "animAnimNode_SharedMetaPoseAdditive":
            child_specs = single_input(node, node_type, path)
            return (
                "SHARED_META_POSE_ADDITIVE",
                child_specs,
                shared_meta_pose_additive_data(node),
            )
        if node_type == "animAnimNode_Blend2":
            data, first, second = blend_two_data(node, index)
            inputs = []
            for target, field in (
                (first, "firstInputNode"),
                (second, "secondInputNode"),
            ):
                input_path = f"{path}.{field}"
                inputs.append(
                    (null_link(input_path) if target is None else target, input_path)
                )
            return "BLEND_TWO", inputs, data
        if node_type == "animAnimNode_BlendAdditive":
            data = blend_additive_data(node)
            return (
                "BLEND_ADDITIVE",
                [
                    link_child(node, "inputNode", path),
                    link_child(node, "addedInputNode", path),
                ],
                data,
            )
        if node_type == "animAnimNode_BlendOverride":
            data = blend_override_data(node, index)
            return (
                "BLEND_OVERRIDE",
                [
                    link_child(node, "inputNode", path),
                    link_child(node, "overrideInputNode", path),
                ],
                data,
            )
        if node_type in {"animAnimNode_Dangle", "animAnimNode_Drag"}:
            return (
                "DANGLE" if node_type.endswith("_Dangle") else "DRAG",
                single_input(node, node_type, path),
                {},
            )
        if node_type in {
            "animAnimNode_LookAtController",
            "animAnimNode_FacialMixerSlot",
        }:
            child_specs = single_input(node, node_type, path)
            normalize = (
                normalize_look_at_controller
                if node_type == "animAnimNode_LookAtController"
                else normalize_facial_mixer
            )
            try:
                data = normalize(node)
            except (TypeError, ValueError) as error:
                raise PreviewBoundary(str(error)) from error
            return (
                "LOOK_AT_CONTROLLER"
                if node_type == "animAnimNode_LookAtController"
                else "FACIAL_MIXER",
                child_specs,
                data,
            )
        if node_type == "animAnimNode_Inertialization":
            return (
                "INERTIALIZATION",
                single_input(node, node_type, path),
                inertialization_data(node),
            )
        if node_type == "animAnimNode_TrajectoryFromMetaPose":
            return (
                "TRAJECTORY_FROM_META_POSE",
                single_input(node, node_type, path),
                trajectory_from_meta_pose_data(node),
            )
        if node_type in POSE_OP_TYPES:
            child_specs = single_input(node, node_type, path)
            if node_type == "animAnimNode_Ik2Constraint" and isinstance(
                node.get("inputTargetOrientation"), Mapping
            ):
                raise PreviewBoundary(
                    "Ik2Constraint target orientation is not implemented by Graph preview"
                )
            return "POSE_OP", child_specs, pure_pose_op_data(node_type, node)
        if node_type == "animAnimNode_ReferencePoseTerminator":
            return PoseProgramNode("REFERENCE", handle, node_type, path, {})
        if node_type == "animAnimNode_IdentityPoseTerminator":
            return PoseProgramNode("IDENTITY", handle, node_type, path, {})
        if node_type in TRANSPARENT_TYPES:
            return "PASS", single_input(node, node_type, path), {}
        if node_type == "animAnimNode_GraphSlotConditions":
            child_specs = single_input(node, node_type, path)
            data = graph_slot_conditions_data(
                node_type,
                node,
                index,
                visual_tags=visual_tags,
                available_animations=available_animations,
                rig_tags=rig_tags,
                parent_tags=parent_tags,
            )
            return "SLOT_PASSTHROUGH", child_specs, data
        if node_type in SLOT_TYPES:
            return (
                "SLOT_PASSTHROUGH",
                single_input(node, node_type, path),
                slot_data(node_type, node),
            )
        if node_type == "animAnimNode_WorkspotHub":
            return "WORKSPOT_HUB", [], workspot_hub_data(node)
        if node_type == "animAnimNode_NPCExploration":
            return "NPC_EXPLORATION", [], {}
        if "animAnimNode_Container" in ancestors or node_type in {
            "animAnimNode_Root",
            "animAnimNode_Container",
        }:
            children = compilation_children(node, index)
            if len(children) != 1:
                raise PreviewBoundary(
                    f"{node_type} requires exactly one output pose for preview"
                )
            return "PASS", [(children[0], f"{path}.nodes[0]")], {}
        pose_fields = [
            field
            for field in rtti.input_socket_definitions(
                node_type, seed_array_inputs=False
            )
            if field.link_type == "animPoseLink"
        ]
        if pose_fields:
            raise PreviewBoundary(
                f"{node_type} is not implemented by the pose preview evaluator"
            )
        raise PreviewBoundary(f"{node_type} does not provide a supported pose output")

    stack: list[tuple[str, Any, str]] = [("ENTER", root_reference, "root")]
    root_token = token(root_reference, "root")
    while stack:
        phase, reference, path = stack.pop()
        current_token = token(reference, path)
        if phase == "EXIT":
            frame = frames.pop(current_token, None)
            if frame is None:
                continue
            visiting.discard(current_token)
            child_nodes = tuple(
                results.get(child_token) for child_token in frame["child_tokens"]
            )
            if any(child is None for child in child_nodes):
                results[current_token] = None
                continue
            rule = frame["rule"]
            handle = frame["handle"]
            node_type = frame["node_type"]
            if rule == "PASS":
                result = child_nodes[0]
            elif rule in {"BLEND_OVERRIDE", "BLEND_ADDITIVE"}:
                result = PoseProgramNode(
                    rule, handle, node_type, path, frame["data"], child_nodes
                )
                if handle not in blend_seen:
                    blend_seen.add(handle)
                    blends.append(handle)
            elif (
                rule in _SYNC_LABELS
                and frame["data"].get("syncMethod")
                and (unsupported_kind := _switch_sync_unsupported(child_nodes))
            ):
                label = _SYNC_LABELS[rule]
                results[current_token] = boundary(
                    path,
                    f"{label} synchronization through {unsupported_kind} is not implemented by Graph preview",
                )
                continue
            elif rule in _NODE_KINDS:
                result = PoseProgramNode(
                    rule, handle, node_type, path, frame["data"], child_nodes
                )
                if rule in {"DANGLE", "DRAG"}:
                    key = (rule, handle)
                    if key not in operation_seen:
                        operation_seen.add(key)
                        operations.append((rule, handle, path))
            else:
                raise RuntimeError(f"Unknown pose-program compile rule {rule!r}")
            results[current_token] = result
            continue

        if current_token in results:
            continue
        if reference is None:
            results[current_token] = PoseProgramNode("INPUT", "", "InputPose", path, {})
            continue
        node, handle = resolved(reference)
        if node is None:
            results[current_token] = boundary(
                path, "pose link does not resolve to a node"
            )
            continue
        node_type = str(node.get("$type", "") or "")
        if current_token in visiting:
            results[current_token] = boundary(
                path, f"pose graph contains a cycle at {node_type or '<unknown>'}"
            )
            continue
        try:
            compiled = compile_node(node, node_type, handle, path)
        except PreviewBoundary as error:
            results[current_token] = boundary(path, str(error))
            continue
        if isinstance(compiled, PoseProgramNode):
            results[current_token] = compiled
            continue
        rule, child_specs, frame_data = compiled

        visiting.add(current_token)
        child_tokens = tuple(
            token(child, child_path) for child, child_path in child_specs
        )
        frames[current_token] = {
            "handle": handle,
            "node_type": node_type,
            "rule": rule,
            "data": frame_data,
            "child_tokens": child_tokens,
        }
        stack.append(("EXIT", reference, path))
        for child, child_path in reversed(child_specs):
            child_token = token(child, child_path)
            if child_token in visiting:
                child_node, _child_handle = resolved(child)
                child_type = str((child_node or {}).get("$type", "") or "")
                results[child_token] = boundary(
                    child_path,
                    f"pose graph contains a cycle at {child_type or '<unknown>'}",
                )
                continue
            if child_token not in results:
                stack.append(("ENTER", child, child_path))

    root = results.get(root_token)
    if boundaries:
        root = None
    return PoseProgramPlan(root, tuple(operations), tuple(blends), tuple(boundaries))


def program_handles(
    node: PoseProgramNode | None, *, kind: str | None = None
) -> frozenset[str]:
    if node is None:
        return frozenset()
    result = set()
    stack = [node]
    seen = set()
    while stack:
        current = stack.pop()
        identity = id(current)
        if identity in seen:
            continue
        seen.add(identity)
        if current.handle and (kind is None or current.kind == kind):
            result.add(current.handle)
        stack.extend(current.children)
    return frozenset(result)
