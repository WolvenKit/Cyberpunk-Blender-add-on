from __future__ import annotations

TRANSFORM_VECTOR_TYPE = "animAnimNodeSourceChannel_TransformVector"
REFERENCE_TRANSFORM_VECTOR_TYPE = "animAnimNodeSourceChannel_ReferenceTransformVector"
ORIENTATION_VECTOR_TYPE = "animAnimNodeSourceChannel_OrientationVector"
STATIC_VECTOR_TYPE = "animAnimNodeSourceChannel_StaticVector"
SOCKET_VECTOR_TYPE = "animAnimNodeSourceChannel_SocketVector"
ANIM_FEATURE_VECTOR_TYPE = "animAnimNodeSourceChannel_AnimFeatureVector"

VECTOR_TYPES = frozenset(
    (
        TRANSFORM_VECTOR_TYPE,
        REFERENCE_TRANSFORM_VECTOR_TYPE,
        ORIENTATION_VECTOR_TYPE,
        STATIC_VECTOR_TYPE,
        SOCKET_VECTOR_TYPE,
        ANIM_FEATURE_VECTOR_TYPE,
    )
)
