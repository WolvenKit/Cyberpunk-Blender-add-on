ANIMGRAPH_TREE_ID = 'REDengine_AnimGraphTree'
ANIM_NODE_PREFIX = 'animAnimNode_'

LINK_TYPES = frozenset({
    'animPoseLink',
    'animFloatLink',
    'animVectorLink',
    'animIntLink',
    'animBoolLink',
    'animQuaternionLink',
    'animTransformLink',
})

LINK_SOCKET = {
    'animPoseLink': ('REDengine_AnimGraphSocket_Pose', 'Pose'),
    'animFloatLink': ('REDengine_AnimGraphSocket_Float', 'Float'),
    'animVectorLink': ('REDengine_AnimGraphSocket_Vector', 'Vector'),
    'animIntLink': ('REDengine_AnimGraphSocket_Int', 'Int'),
    'animBoolLink': ('REDengine_AnimGraphSocket_Bool', 'Bool'),
    'animQuaternionLink': ('REDengine_AnimGraphSocket_Quaternion', 'Quaternion'),
    'animTransformLink': ('REDengine_AnimGraphSocket_Transform', 'Transform'),
}

COMPARE_OPS = {
    'Equal': '==',
    'NotEqual': '!=',
    'Less': '<',
    'LessEqual': '<=',
    'Greater': '>',
    'GreaterEqual': '>=',
}

CONTAINER_FIELDS = frozenset({'frozenState', 'states', 'nodes'})
CONTAINER_OUTPUT_NAME = 'Out Pose'
OUTPUT_NODE_TYPE = 'animAnimNode_Output'

HIDDEN_FIELDS = frozenset({
    '$type', 'id', 'nodes', 'states', 'frozenState', 'transitions',
    'globalTransitions', 'conditionalEntries', 'anyStateInterpolator',
    'outTransitionIndices', 'profileTimers', 'poseInfoLogger', 'solo',
    'debugValueProvider',
})
HIDDEN_FIELD_PREFIXES = ('vis',)

VAR_ARRAYS = (
    ('boolVariables', 'Bool'),
    ('intVariables', 'Int'),
    ('floatVariables', 'Float'),
    ('vectorVariables', 'Vector'),
    ('quaternionVariables', 'Quaternion'),
    ('transformVariables', 'Transform'),
)
