NODE_CATEGORY_COLORS = {
    'container': (0.18, 0.22, 0.30),
    'clip': (0.20, 0.40, 0.20),
    'constraint': (0.18, 0.30, 0.45),
    'physics': (0.45, 0.25, 0.15),
    'blend': (0.35, 0.22, 0.42),
    'posespace': (0.15, 0.38, 0.40),
    'bone': (0.40, 0.32, 0.18),
    'float': (0.28, 0.28, 0.28),
    'vector': (0.24, 0.24, 0.42),
    'stack': (0.15, 0.33, 0.33),
    'terminator': (0.12, 0.12, 0.12),
    'lod': (0.42, 0.40, 0.16),
    'meta': (0.42, 0.22, 0.34),
    'transition': (0.26, 0.26, 0.34),
    'default': (0.25, 0.25, 0.25),
}

CONTAINER_TYPES = frozenset({
    'Root', 'State', 'StateFrozen', 'StateMachine', 'LocoState',
    'LocomotionMachine', 'Stage',
})

PHYSICS_TYPES = frozenset({'SimpleSpline', 'Dangle', 'Drag', 'SimpleBounce', 'RagdollControl'})

BLEND_TYPES = frozenset({
    'Blend2', 'BlendAdditive', 'BlendOverride', 'BlendFromPose',
    'BlendByMaskDynamic', 'BlendMultiple', 'BlendSpace', 'GraphSlot', 'Join',
    'SelectiveJoin', 'MixerSlot', 'FacialMixerSlot', 'StaticSwitch', 'RuntimeSwitch',
    'Switch', 'InputSwitch', 'EnumSwitch', 'TagSwitch', 'TriggerBranch',
})

POSESPACE_TYPES = frozenset({'PoseMsToLs', 'PoseLsToMs'})

BONE_TYPES = frozenset({
    'RotateBone', 'RotateBoneByQuaternion', 'TransformToTrack', 'SetBoneTransform',
    'SetBonePosition', 'SetBoneOrientation', 'TranslateBone', 'TransformRotator',
    'TrackSetter', 'SetTrackRange', 'RotationLimit', 'AdditionalTransform',
    'AdditionalFloatTrack', 'FloatTrackModifier',
})

CLIP_TYPES = frozenset({
    'SkAnim', 'SkPhaseAnim', 'SkFrameAnim', 'SkFrameAnimByTrack',
    'SkPhaseWithDurationAnim', 'SkPhaseWithSpeedAnim', 'SkDurationAnim',
    'SkSpeedAnim', 'SkOneShotAnim', 'SkAnimDecorator', 'SkAnimContinue',
    'SkSyncedMasterAnim', 'SkSyncedMasterAnimByTime', 'SkSyncedSlaveAnim',
    'SkAnimSlot', 'SkPhaseSlotWithDurationAnim', 'AnimDatabase',
})

TERMINATOR_TYPES = frozenset({'ReferencePoseTerminator', 'IdentityPoseTerminator', 'Output'})

CONSTRAINT_OR_IK_TYPES = frozenset({
    'PointConstraint', 'OrientConstraint', 'ParentConstraint', 'AimConstraint',
    'TwistConstraint', 'TranslationLimit', 'DirectConnConstraint',
    'FloatTrackDirectConnConstraint', 'Ik2', 'Ik2Constraint', 'AddIkRequest',
    'AddSnapToTerrainIkRequest', 'ReadIkRequest', 'LookAt', 'LookAtController',
    'LookAtApplyVehicleRestrictions', 'EyesLookAt', 'EyesTracksLookAt',
    'FootstepAdjuster', 'FootStepScaling', 'FloorIk',
})


def node_category(short: str) -> str:
    if short in CONTAINER_TYPES:
        return "container"
    if short in ('Entry', 'AnyState', 'StateMachineOutput', 'RootOutput'):
        return "transition"
    if short in CONSTRAINT_OR_IK_TYPES or short.endswith('Constraint'):
        return "constraint"
    if short.startswith('Stack'):
        return "stack"
    if short.startswith('LOD') or short.startswith('SkipPerformance') or short.startswith('SkipConsole'):
        return "lod"
    if short in PHYSICS_TYPES:
        return "physics"
    if short in BLEND_TYPES:
        return "blend"
    if short in POSESPACE_TYPES:
        return "posespace"
    if short in BONE_TYPES:
        return "bone"
    if short in CLIP_TYPES:
        return "clip"
    if short in TERMINATOR_TYPES:
        return "terminator"
    if 'Vector' in short or 'Quaternion' in short or 'Transform' in short:
        return "vector"
    if 'Meta' in short or 'Shared' in short:
        return "meta"
    if 'Float' in short or short in {'Timer', 'DampFloat', 'Event', 'EventValue', 'TagValue', 'WrapperValue', 'Signal'}:
        return "float"
    return "default"
