from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

ENUMS = {'animAimState': {'options': {'Aimed': 1, 'Unaimed': 0}, 'size': 4},
 'animAnimEventGenderAlt': {'options': {'Female': 1, 'Male': 2, 'None': 0}, 'size': 4},
 'animAnimNode_SetDrivenKey_InternalsEChannelType': {'options': {'FloatTrack': 0,
                                                                 'RotEulX_Roll': 5,
                                                                 'RotEulY_Yaw': 6,
                                                                 'RotEulZ_Pitch': 4,
                                                                 'RotQuatW': 13,
                                                                 'RotQuatX': 10,
                                                                 'RotQuatY': 11,
                                                                 'RotQuatZ': 12,
                                                                 'ScaleX': 7,
                                                                 'ScaleY': 8,
                                                                 'ScaleZ': 9,
                                                                 'TransX': 1,
                                                                 'TransY': 2,
                                                                 'TransZ': 3},
                                                     'size': 4},
 'animAnimStateInterpolationType': {'options': {'EaseIn': 1, 'EaseInOut': 3, 'EaseOut': 2, 'Linear': 0}, 'size': 1},
 'animAnimationType': {'options': {'Additive': 3,
                                   'AdditiveFromFirstFrame': 2,
                                   'AdditiveFromRefPose': 1,
                                   'AdditiveWithoutFirstFrame': 4,
                                   'Normal': 0},
                       'size': 1},
 'animAxis': {'options': {'NegativeX': 3, 'NegativeY': 4, 'NegativeZ': 5, 'X': 0, 'Y': 1, 'Z': 2}, 'size': 4},
 'animClampType': {'options': {'Clamp': 1, 'None': 0, 'WrappedClamp': 2}, 'size': 4},
 'animCompareFunc': {'options': {'Equal': 0, 'Greater': 4, 'GreaterEqual': 5, 'Less': 2, 'LessEqual': 3, 'NotEqual': 1},
                     'size': 4},
 'animConstraintWeightMode': {'options': {'FloatTrack': 1, 'Static': 0}, 'size': 4},
 'animCoverAction': {'options': {'BlindfireLeft': 11,
                                 'BlindfireOver': 13,
                                 'BlindfireRight': 12,
                                 'EnterCover': 7,
                                 'LeanLeft': 1,
                                 'LeanOver': 5,
                                 'LeanRight': 2,
                                 'LeaveCover': 10,
                                 'NoAction': 0,
                                 'OverheadStepOutLeft': 14,
                                 'OverheadStepOutRight': 15,
                                 'OverheadStepUp': 16,
                                 'SlideTo': 8,
                                 'StepOutLeft': 3,
                                 'StepOutRight': 4,
                                 'StepUp': 6,
                                 'Vault': 9},
                     'size': 4},
 'animCoverBehavior': {'options': {'DoAction': 2, 'Idle': 0, 'PostAction': 3, 'PreAction': 1}, 'size': 4},
 'animCoverStance': {'options': {'HighLeft': 2, 'HighRight': 4, 'LowLeft': 1, 'LowRight': 3, 'None': 0}, 'size': 4},
 'animCoverState': {'options': {'HighCover': 2, 'LowCover': 1}, 'size': 4},
 'animDyngConstraintLinkType': {'options': {'Closer': 3,
                                            'Greater': 2,
                                            'KeepFixedDistance': 0,
                                            'KeepVariableDistance': 1},
                                'size': 4},
 'animDyngParticleProjectionType': {'options': {'Directed': 2, 'Disabled': 0, 'ShortestPath': 1}, 'size': 4},
 'animEAnimGraphAdditiveType': {'options': {'AGAT_Local': 0, 'AGAT_Ref': 1}, 'size': 4},
 'animEAnimGraphCompareFunc': {'options': {'AGCF_Equal': 0,
                                           'AGCF_Greater': 4,
                                           'AGCF_GreaterEqual': 5,
                                           'AGCF_Less': 2,
                                           'AGCF_LessEqual': 3,
                                           'AGCF_NotEqual': 1},
                               'size': 4},
 'animEAnimGraphLogicOp': {'options': {'AGLO_And': 1, 'AGLO_Or': 0}, 'size': 4},
 'animEAnimGraphMathInterpolation': {'options': {'AGMI_BEZIER': 2, 'AGMI_LINEAR': 0, 'AGMI_SIN': 1}, 'size': 4},
 'animEAnimGraphMathOp': {'options': {'AGMO_ATan': 5,
                                      'AGMO_Abs': 8,
                                      'AGMO_Add': 0,
                                      'AGMO_AngleDiff': 6,
                                      'AGMO_Divide': 3,
                                      'AGMO_Length': 7,
                                      'AGMO_Multiply': 2,
                                      'AGMO_SafeDivide': 4,
                                      'AGMO_Subtract': 1},
                          'size': 4},
 'animEBlendFromPoseMode': {'options': {'BFPM_AlwaysOnActivation': 0, 'BFPM_RequestedByTag': 1}, 'size': 4},
 'animEBlendTracksMode': {'options': {'AGBT_Add': 2, 'AGBT_BasePose': 0, 'AGBT_Interpolate': 1}, 'size': 4},
 'animEBlendTypeLBC': {'options': {'CustomCurve': 2, 'Linear': 0, 'Smoothstep': 1}, 'size': 4},
 'animEDirectionToEuler': {'options': {'Pitch': 0, 'Roll': 2, 'Yaw': 1}, 'size': 4},
 'animEFootPhase': {'options': {'LeftForward': 3, 'LeftUp': 2, 'NotConsidered': 4, 'RightForward': 1, 'RightUp': 0},
                    'size': 1},
 'animEInterpolationType': {'options': {'Lerp': 0, 'Slerp': 1}, 'size': 4},
 'animEMotionExtractionCompressionType': {'options': {'EMECT_LINEAR': 6,
                                                      'EMECT_SPLINE_HIGH': 5,
                                                      'EMECT_SPLINE_LOW': 4,
                                                      'EMECT_SPLINE_MID': 2,
                                                      'EMECT_UNCOMPRESSED': 0,
                                                      'EMECT_UNCOMPRESSED_2D': 7,
                                                      'EMECT_UNCOMPRESSED_3D_FALLBACKING': 8,
                                                      'EMECT_UNCOMPRESSED_ALL_ANGLES': 3,
                                                      'EMECT_UNCOMPRESSED_ALL_ANGLES_FALLBACKING': 9},
                                          'size': 4},
 'animEResetTypeNode': {'options': {'RT_Indentity': 1, 'RT_Reference': 0}, 'size': 4},
 'animESpace': {'options': {'Local': 0, 'Model': 1, 'World': 2}, 'size': 4},
 'animESpaceMW': {'options': {'Model': 0, 'World': 1}, 'size': 4},
 'animETransformAxis': {'options': {'X_Axis': 1, 'Y_Axis': 2, 'Z_Axis': 4}, 'size': 4},
 'animEVectorWsToMsType': {'options': {'Direction': 1, 'Position': 0}, 'size': 4},
 'animEventFilterType': {'options': {'AlwaysCollect': 1, 'Default': 0, 'Mute': 3, 'Solo': 2}, 'size': 4},
 'animEventSide': {'options': {'Left': 0, 'Right': 1}, 'size': 4},
 'animFacialEmotionTransitionType': {'options': {'Blend': 2, 'Custom': 4, 'Fast': 1, 'Instant': 3, 'Natural': 0},
                                     'size': 4},
 'animFloatTrackOperationType': {'options': {'Add': 2,
                                             'Multiply': 1,
                                             'Override': 0,
                                             'Subtract': 3,
                                             'SubtractSwapped': 4,
                                             'WeightComplement': 5},
                                 'size': 4},
 'animHitReactionType': {'options': {'Block': 8,
                                     'Bump': 11,
                                     'Death': 7,
                                     'GuardBreak': 9,
                                     'Impact': 2,
                                     'Knockdown': 5,
                                     'None': 0,
                                     'Pain': 4,
                                     'Parry': 10,
                                     'Ragdoll': 6,
                                     'Stagger': 3,
                                     'Twitch': 1},
                         'size': 4},
 'animLeg': {'options': {'Left': 0, 'Right': 1}, 'size': 4},
 'animLocoStateType': {'options': {'LS_Loop': 1, 'LS_Pre': 0}, 'size': 4},
 'animLocomotionDecision': {'options': {'LD_Move': 3, 'LD_MoveTo': 2, 'LD_None': 0, 'LD_Stop': 1}, 'size': 4},
 'animLocomotion_AnimType': {'options': {'None': 0,
                                         'idle_stand': 1,
                                         'idle_step_single_0': 99,
                                         'idle_step_single_090': 100,
                                         'idle_step_single_180': 101,
                                         'idle_step_single_270': 102,
                                         'idle_to_idle_0': 2,
                                         'idle_to_idle_090': 3,
                                         'idle_to_idle_180_l': 5,
                                         'idle_to_idle_180_r': 6,
                                         'idle_to_idle_270': 4,
                                         'idle_to_jog_0': 17,
                                         'idle_to_jog_180': 53,
                                         'idle_to_sprint_0': 18,
                                         'idle_to_walk_0': 16,
                                         'idle_to_walk_090': 63,
                                         'idle_to_walk_180': 52,
                                         'idle_to_walk_270': 64,
                                         'idle_turn_to_jog_090': 38,
                                         'idle_turn_to_jog_180_l': 39,
                                         'idle_turn_to_jog_180_r': 40,
                                         'idle_turn_to_jog_270': 41,
                                         'idle_turn_to_sprint_090': 42,
                                         'idle_turn_to_sprint_180_l': 43,
                                         'idle_turn_to_sprint_180_r': 44,
                                         'idle_turn_to_sprint_270': 45,
                                         'idle_turn_to_walk_090': 34,
                                         'idle_turn_to_walk_180_l': 35,
                                         'idle_turn_to_walk_180_r': 36,
                                         'idle_turn_to_walk_270': 37,
                                         'jog_0': 10,
                                         'jog_0_down_slope': 87,
                                         'jog_0_down_stairs': 85,
                                         'jog_0_to_jog_180_l': 56,
                                         'jog_0_to_jog_180_r': 57,
                                         'jog_0_up_slope': 88,
                                         'jog_0_up_stairs': 86,
                                         'jog_180': 47,
                                         'jog_180_to_jog_0_l': 58,
                                         'jog_180_to_jog_0_r': 59,
                                         'jog_left': 11,
                                         'jog_right': 12,
                                         'jog_to_idle_0': 20,
                                         'jog_to_idle_0_l_hard': 24,
                                         'jog_to_idle_0_r_hard': 25,
                                         'jog_to_idle_180': 55,
                                         'jog_to_sprint_0': 31,
                                         'jog_to_sprint_180': 60,
                                         'jog_to_walk_0': 30,
                                         'jog_to_walk_180': 62,
                                         'sprint_0': 13,
                                         'sprint_0_down_slope': 91,
                                         'sprint_0_down_stairs': 89,
                                         'sprint_0_up_slope': 92,
                                         'sprint_0_up_stairs': 90,
                                         'sprint_left': 14,
                                         'sprint_right': 15,
                                         'sprint_to_idle_0': 21,
                                         'sprint_to_idle_0_l_hard': 26,
                                         'sprint_to_idle_0_r_hard': 27,
                                         'sprint_to_jog_0': 33,
                                         'sprint_to_walk_0': 32,
                                         'walk_0': 7,
                                         'walk_090': 65,
                                         'walk_090_down_stairs': 94,
                                         'walk_090_to_walk_0': 73,
                                         'walk_090_to_walk_180': 75,
                                         'walk_090_to_walk_270_l': 77,
                                         'walk_090_to_walk_270_r': 78,
                                         'walk_090_up_stairs': 93,
                                         'walk_0_down_slope': 83,
                                         'walk_0_down_stairs': 81,
                                         'walk_0_to_walk_090': 69,
                                         'walk_0_to_walk_180_l': 48,
                                         'walk_0_to_walk_180_r': 49,
                                         'walk_0_to_walk_270': 70,
                                         'walk_0_up_slope': 84,
                                         'walk_0_up_stairs': 82,
                                         'walk_180': 46,
                                         'walk_180_down_stairs': 98,
                                         'walk_180_to_walk_090': 71,
                                         'walk_180_to_walk_0_l': 50,
                                         'walk_180_to_walk_0_r': 51,
                                         'walk_180_to_walk_270': 72,
                                         'walk_180_up_stairs': 97,
                                         'walk_270': 66,
                                         'walk_270_down_stairs': 96,
                                         'walk_270_to_walk_0': 74,
                                         'walk_270_to_walk_090_l': 79,
                                         'walk_270_to_walk_090_r': 80,
                                         'walk_270_to_walk_180': 76,
                                         'walk_270_up_stairs': 95,
                                         'walk_left': 8,
                                         'walk_right': 9,
                                         'walk_to_idle_0': 19,
                                         'walk_to_idle_090': 67,
                                         'walk_to_idle_0_l_hard': 22,
                                         'walk_to_idle_0_r_hard': 23,
                                         'walk_to_idle_180': 54,
                                         'walk_to_idle_270': 68,
                                         'walk_to_jog_0': 28,
                                         'walk_to_jog_180': 61,
                                         'walk_to_sprint_0': 29},
                             'size': 4},
 'animLocomotion_Style': {'options': {'LS_Any': 5,
                                      'LS_Idle': 0,
                                      'LS_Jog': 3,
                                      'LS_Rotation': 1,
                                      'LS_Sprint': 4,
                                      'LS_Walk': 2},
                          'size': 4},
 'animLookAtChestMode': {'options': {'Default': 0, 'ENUM_SIZE': 4, 'Horizontal': 2, 'HorizontalNoHips': 3, 'NoHips': 1},
                         'size': 4},
 'animLookAtEyesMode': {'options': {'Default': 0, 'ENUM_SIZE': 2, 'Horizontal': 1}, 'size': 4},
 'animLookAtHeadMode': {'options': {'Default': 0, 'ENUM_SIZE': 2, 'Horizontal': 1}, 'size': 4},
 'animLookAtLeftHandedMode': {'options': {'Default': 0, 'ENUM_SIZE': 2, 'Horizontal': 1}, 'size': 4},
 'animLookAtLimitDegreesType': {'options': {'Narrow': 0, 'None': 3, 'Normal': 1, 'Wide': 2}, 'size': 4},
 'animLookAtLimitDistanceType': {'options': {'Long': 2, 'None': 3, 'Normal': 1, 'Short': 0}, 'size': 4},
 'animLookAtRightHandedMode': {'options': {'Default': 0, 'ENUM_SIZE': 2, 'Horizontal': 1}, 'size': 4},
 'animLookAtStatus': {'options': {'Active': 2, 'LimitReached': 4, 'TransitionInProgress': 8}, 'size': 4},
 'animLookAtStyle': {'options': {'Fast': 3, 'Normal': 2, 'Slow': 1, 'VeryFast': 4, 'VerySlow': 0}, 'size': 4},
 'animLookAtTwoHandedMode': {'options': {'Default': 0, 'ENUM_SIZE': 2, 'Horizontal': 1}, 'size': 4},
 'animMotionTableAction': {'options': {'MTA_BackwardMove': 6,
                                       'MTA_BackwardStart': 18,
                                       'MTA_BackwardStop': 19,
                                       'MTA_BackwardToStrafeLeft': 14,
                                       'MTA_BackwardToStrafeRight': 15,
                                       'MTA_CrowdDirectionalStartFast': 47,
                                       'MTA_CrowdFleeStartIdle': 45,
                                       'MTA_CrowdFleeStartMotion': 46,
                                       'MTA_CrowdFleeStopBack': 43,
                                       'MTA_CrowdFleeStopFront': 42,
                                       'MTA_CrowdHardStop': 40,
                                       'MTA_CrowdMove': 34,
                                       'MTA_CrowdMoveSlopes': 35,
                                       'MTA_CrowdMoveStairs': 36,
                                       'MTA_CrowdRelaxedStart': 44,
                                       'MTA_CrowdRelaxedStop': 39,
                                       'MTA_CrowdSprintStop': 41,
                                       'MTA_Custom': 33,
                                       'MTA_ForwardToJog': 25,
                                       'MTA_ForwardToSprint': 26,
                                       'MTA_ForwardToStrafeLeft': 10,
                                       'MTA_ForwardToStrafeRight': 11,
                                       'MTA_ForwardToWalk': 24,
                                       'MTA_HardStopLeftLeg': 27,
                                       'MTA_HardStopRightLeg': 28,
                                       'MTA_Move': 3,
                                       'MTA_None': 0,
                                       'MTA_RepositionBackward': 32,
                                       'MTA_RepositionForward': 29,
                                       'MTA_RepositionLeft': 30,
                                       'MTA_RepositionRight': 31,
                                       'MTA_Start': 1,
                                       'MTA_Stop': 2,
                                       'MTA_StrafeLeft': 8,
                                       'MTA_StrafeLeftStart': 20,
                                       'MTA_StrafeLeftStop': 21,
                                       'MTA_StrafeLeftToBackward': 16,
                                       'MTA_StrafeLeftToForward': 12,
                                       'MTA_StrafeLeftToStrafeRight': 37,
                                       'MTA_StrafeRight': 9,
                                       'MTA_StrafeRightStart': 22,
                                       'MTA_StrafeRightStop': 23,
                                       'MTA_StrafeRightToBackward': 17,
                                       'MTA_StrafeRightToForward': 13,
                                       'MTA_StrafeRightToStrafeLeft': 38,
                                       'MTA_TransitionFromBackward': 7,
                                       'MTA_TransitionToBackward': 5,
                                       'MTA_TurnInPlace': 4},
                           'size': 4},
 'animMotionTableType': {'options': {'MTT_Custom': 4, 'MTT_Jog': 2, 'MTT_None': 0, 'MTT_Sprint': 3, 'MTT_Walk': 1},
                         'size': 4},
 'animMotionTag': {'options': {'Jog': 2, 'MT_Invalid': 0, 'Sprint': 3, 'Walk': 1}, 'size': 4},
 'animNodeProfileTimerMode': {'options': {'Begin': 0, 'End': 1}, 'size': 4},
 'animParentStaticSwitchBranch': {'options': {'FalseBranch': 2, 'None': 0, 'TrueBranch': 1}, 'size': 4},
 'animPendulumConstraintType': {'options': {'Cone': 0, 'HalfCone': 2, 'HingePlane': 1}, 'size': 4},
 'animPendulumProjectionType': {'options': {'DirectedRotational': 2, 'Disabled': 0, 'ShortestPathRotational': 1},
                                'size': 4},
 'animPositionProjectionType': {'options': {'Directional': 2, 'Disabled': 0, 'ShortestPath': 1}, 'size': 4},
 'animQuaternionInterpolationType': {'options': {'Linear': 0, 'Spherical': 1}, 'size': 4},
 'animSetBoneTransformEntry_SetMethod': {'options': {'NoSnapping': 0,
                                                     'RotationOnly': 3,
                                                     'TranslationOnly': 2,
                                                     'WholeTransform': 1},
                                         'size': 4},
 'animSpringProjectionType': {'options': {'Disabled': 0, 'ShortestPath': 1}, 'size': 4},
 'animStackTransformsExtender_SnapToBoneMethod': {'options': {'NoSnapping': 0,
                                                              'RotationOnly': 3,
                                                              'TranslationOnly': 2,
                                                              'WholeTransform': 1},
                                                  'size': 4},
 'animStanceState': {'options': {'Cover': 3, 'Crawl': 5, 'Crouch': 1, 'Kneel': 2, 'Stand': 0, 'Swim': 4}, 'size': 4},
 'animStateTag': {'options': {'Cover': 2, 'Idle': 1, 'ST_Invalid': 0}, 'size': 4},
 'animTransformChannel': {'options': {'PosX': 0,
                                      'PosY': 1,
                                      'PosZ': 2,
                                      'RotX': 3,
                                      'RotY': 4,
                                      'RotZ': 5,
                                      'ScaleX': 6,
                                      'ScaleY': 7,
                                      'ScaleZ': 8},
                          'size': 4},
 'animVectorCoordinateType': {'options': {'W': 3, 'X': 0, 'Y': 1, 'Z': 2}, 'size': 4},
 'animcompressionBufferTypePreset': {'options': {'SIMD': 1, 'Spline': 0, 'TestRaw': 2}, 'size': 1},
 'animcompressionFrameratePreset': {'options': {'USE_10_HZ': 2, 'USE_15_HZ': 1, 'USE_30_HZ': 0}, 'size': 1},
 'animcompressionQualityPreset': {'options': {'CINEMATIC_HIGH': 3, 'HIGH': 0, 'LOW': 2, 'MID': 1}, 'size': 1}}

FLAG_ENUMS = {'animETransformAxis', 'animLookAtStatus'}


FIELD_HINTS = {'animDyngConstraintCone.constraintType': 'animPendulumConstraintType',
 'animDyngConstraintCone.projectionType': 'animPendulumProjectionType',
 'animDyngConstraintLink.linkType': 'animDyngConstraintLinkType',
 'animDyngParticle.projectionType': 'animDyngParticleProjectionType',
 'animSetBoneTransformEntry.setMethod': 'animSetBoneTransformEntry_SetMethod',
 'animStackTransformsExtender_Entry.snapMethod': 'animStackTransformsExtender_SnapToBoneMethod',
 'animStackTransformsExtender_Entry.snapToBoneMethod': 'animStackTransformsExtender_SnapToBoneMethod',
 'editorDangleConeConstraint.constraintType': 'animPendulumConstraintType',
 'editorDangleConeConstraint.projectionType': 'animPendulumProjectionType',
 'editorDangleParticle.projectionType': 'animDyngParticleProjectionType'}


FIELD_NAME_HINTS = {'additiveType': ['animEAnimGraphAdditiveType'],
 'axis': ['animAxis', 'animETransformAxis'],
 'blendMode': ['animEBlendTracksMode'],
 'blendType': ['animEBlendTypeLBC'],
 'channel': ['animTransformChannel'],
 'compareFunc': ['animCompareFunc', 'animEAnimGraphCompareFunc'],
 'constraintType': ['animPendulumConstraintType'],
 'coordinate': ['animVectorCoordinateType'],
 'interpolation': ['animEAnimGraphMathInterpolation', 'animEInterpolationType', 'animQuaternionInterpolationType'],
 'interpolationType': ['animEAnimGraphMathInterpolation',
                       'animEInterpolationType',
                       'animQuaternionInterpolationType',
                       'animAnimStateInterpolationType'],
 'linkType': ['animDyngConstraintLinkType'],
 'logicOp': ['animEAnimGraphLogicOp'],
 'mathOp': ['animEAnimGraphMathOp'],
 'operationType': ['animFloatTrackOperationType'],
 'projectionType': ['animDyngParticleProjectionType',
                    'animPendulumProjectionType',
                    'animPositionProjectionType',
                    'animSpringProjectionType'],
 'setMethod': ['animSetBoneTransformEntry_SetMethod'],
 'snapMethod': ['animStackTransformsExtender_SnapToBoneMethod'],
 'snapToBoneMethod': ['animStackTransformsExtender_SnapToBoneMethod'],
 'space': ['animESpace', 'animESpaceMW']}


JSON_PATH_HINTS = {'dyngConstraint.Data.innerConstraints[].Data.constraintType': 'animPendulumConstraintType',
 'dyngConstraint.Data.innerConstraints[].Data.linkType': 'animDyngConstraintLinkType',
 'dyngConstraint.Data.innerConstraints[].Data.projectionType': 'animPendulumProjectionType',
 'particlesContainer.particles[].projectionType': 'animDyngParticleProjectionType'}

SENTINEL_NAMES = {'ENUM_SIZE'}
RAW_IDENTIFIER = '__RAW__'


def has_enum(name: str) -> bool:
    return str(name or '') in ENUMS


def enum_record(name: str) -> Dict[str, Any]:
    return ENUMS.get(str(name or ''), {})


def enum_size(name: str) -> int:
    try:
        return int(enum_record(name).get('size', 4))
    except Exception:
        return 4


def is_flags(name: str) -> bool:
    return str(name or '') in FLAG_ENUMS


def options(name: str, *, include_sentinel: bool = True) -> Dict[str, int]:
    opts = dict(enum_record(name).get('options', {}) or {})
    if not include_sentinel:
        opts = {k: v for k, v in opts.items() if k not in SENTINEL_NAMES}
    return opts


def value_for_name(name: str, option_name: str) -> Optional[int]:
    opts = options(name, include_sentinel=True)
    if option_name in opts:
        return int(opts[option_name])
    return None


def name_for_value(name: str, value: Any) -> Optional[str]:
    try:
        iv = int(value)
    except Exception:
        return None
    for opt_name, opt_value in options(name, include_sentinel=True).items():
        try:
            if int(opt_value) == iv:
                return opt_name
        except Exception:
            continue
    return None


def value_is_known(name: str, value: Any) -> bool:
    if isinstance(value, str):
        return value in options(name, include_sentinel=True)
    return name_for_value(name, value) is not None


def _option_label(option_name: str, option_value: int) -> str:
    return f"{option_name} ({option_value})"


def enum_items(name: str, *, include_sentinel: bool = False) -> List[Tuple[str, str, str]]:
    if not has_enum(name):
        return [(RAW_IDENTIFIER, 'Raw / unknown', 'No enum definition is available')]
    items: List[Tuple[str, str, str]] = [(RAW_IDENTIFIER, 'Raw / unknown', 'Preserve an unknown or custom enum value')]
    for opt_name, opt_value in sorted(options(name, include_sentinel=include_sentinel).items(), key=lambda kv: (int(kv[1]), kv[0])):
        items.append((opt_name, _option_label(opt_name, int(opt_value)), f"{name}.{opt_name} = {int(opt_value)}"))
    return items


def normalize_choice(name: str, value: Any) -> str:
    """Return the enum option name for known values, otherwise RAW_IDENTIFIER."""
    if isinstance(value, str) and value in options(name, include_sentinel=True):
        return value
    by_value = name_for_value(name, value)
    if by_value:
        return by_value
    return RAW_IDENTIFIER


def decoded_value_text(name: str, value: Any) -> str:
    if isinstance(value, str) and value in options(name, include_sentinel=True):
        return value
    by_value = name_for_value(name, value)
    if by_value:
        return by_value
    return '' if value is None else str(value)


def encode_value(name: str, value_text: Any, *, storage: str = 'name', raw_value: Any = '') -> Any:
    """Encode a UI enum value while preserving its serialized style."""
    text = '' if value_text is None else str(value_text)
    if storage == 'value':
        if text in options(name, include_sentinel=True):
            val = value_for_name(name, text)
            if val is not None:
                return val
        for candidate in (raw_value, text):
            try:
                return int(str(candidate), 0)
            except Exception:
                pass
        return 0
    return text


def _json_path_pattern(path: str) -> str:
    text = str(path or '')
    return re.sub(r'\[\d+\]', '[]', text)


def _value_matches(enum_name: str, value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value in options(enum_name, include_sentinel=True)
    try:
        int(value)
    except Exception:
        return False
    return name_for_value(enum_name, value) is not None


def _choose_candidate(candidates: Iterable[str], value: Any) -> str:
    matches = [name for name in candidates if has_enum(name) and _value_matches(name, value)]
    return matches[0] if len(matches) == 1 else ''


def resolve_enum_type(
    type_hint: str = '',
    *,
    field_name: str = '',
    parent_type: str = '',
    json_path: str = '',
    value: Any = None,
) -> str:
    """Resolve the enum type for a serialized property."""
    hint = str(type_hint or '')
    if has_enum(hint):
        return hint
    parent = str(parent_type or '')
    field = str(field_name or '')
    if parent and field:
        exact = FIELD_HINTS.get(f'{parent}.{field}')
        if exact and has_enum(exact):
            return exact
    p = _json_path_pattern(json_path)
    exact_path = JSON_PATH_HINTS.get(p)
    if exact_path and has_enum(exact_path):
        return exact_path
    candidates = FIELD_NAME_HINTS.get(field, [])
    return _choose_candidate(candidates, value)


def flags_summary(name: str, value_text: Any, raw_value: Any = '') -> str:
    """Return decoded names for bitmask-style enum values."""
    if not has_enum(name):
        return ''
    value: Optional[int] = None
    text = '' if value_text is None else str(value_text)
    if text in options(name, include_sentinel=True):
        value = value_for_name(name, text)
    if value is None:
        for candidate in (raw_value, text):
            try:
                value = int(str(candidate), 0)
                break
            except Exception:
                pass
    if value is None:
        return text
    names = []
    for opt_name, opt_value in sorted(options(name, include_sentinel=False).items(), key=lambda kv: int(kv[1])):
        try:
            bit = int(opt_value)
        except Exception:
            continue
        if bit != 0 and (value & bit) == bit:
            names.append(opt_name)
    return ' | '.join(names) if names else str(value)


def summary() -> Dict[str, int]:
    return {
        'enums': len(ENUMS),
        'flag_enums': len(FLAG_ENUMS),
        'field_hints': len(FIELD_HINTS),
        'field_name_hints': len(FIELD_NAME_HINTS),
        'path_hints': len(JSON_PATH_HINTS),
    }
