from __future__ import annotations

import weakref

from ...animation.domain.facial.graph import FacialGraphBinding
from ...bartmoss.qs_transform import QsTransform
from . import session as facial_session


def bind_graph(armature):
    session = facial_session.ensure_session(armature)
    if session is None:
        raise ValueError(
            "Sermo requires a facial setup bound to the preview armature in Animation Tools"
        )
    rig = session.rig
    binding = FacialGraphBinding(
        facial_session.get_compiled_runtime(session),
        tuple(
            str(bone.name) if bone is not None else "" for bone in session.pose_bones
        ),
        tuple(
            QsTransform.from_components(t, q, s)
            for t, q, s in zip(rig.ls_t, rig.ls_q, rig.ls_s)
        ),
        tuple(session.track_names),
        tuple(float(value) for value in session.track_defaults),
        tuple(int(index) for index in session.used_bone_indices),
    )
    return session, binding


def claim_session(session, owner) -> None:
    """Let owner drive the session"""
    session.graph_preview_runtime = weakref.ref(owner)


def graph_preview_owns_session(session) -> bool:
    reference = session.graph_preview_runtime
    owner = reference() if reference is not None else None
    return bool(owner is not None and owner.drives_facial_session(session))
