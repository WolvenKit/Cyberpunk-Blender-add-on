import bpy
from bpy.app.handlers import persistent

from ....blender.armature_bones import (
    bone_names_equivalent,
    resolve_bone_name,
    resolve_pose_bone,
)
from ....blender.context import tag_view3d_redraw, with_context
from ....blender.identity import rna_identity
from ....core.log import get_logger

_LOG = get_logger(__name__)

SYNC_LOCK = False
_LAST_ACTIVE = (None, None)
_POLL_INTERVAL = 0.15


def _find_particle_for_bone(rig, state, bone_name):
    for ni, dnode in enumerate(state.dangle_nodes):
        for ci, chain in enumerate(dnode.chains):
            for pi, particle in enumerate(chain.particles):
                if bone_names_equivalent(rig, particle.bone_name, bone_name):
                    return ni, ci, pi
    return None


def _select_single_pose_bone(rig, bone_name):
    pose = rig.pose
    for pb in pose.bones:
        if pb.select:
            pb.select = False
    target_pb = resolve_pose_bone(rig, bone_name)
    if target_pb is None:
        return
    target_pb.select = True
    target_bone = target_pb.bone if target_pb is not None else None
    if target_bone is not None:
        rig.data.bones.active = target_bone
    tag_view3d_redraw()


def _posed_dangle_rig(obj):
    return (
        obj is not None
        and obj.type == "ARMATURE"
        and obj.mode == "POSE"
        and obj.dangle_state.is_dangle_rig
    )


def ensure_polling(context):
    if _posed_dangle_rig(getattr(context, "active_object", None)):
        if not bpy.app.timers.is_registered(SELECTION_POLL):
            bpy.app.timers.register(SELECTION_POLL, first_interval=_POLL_INTERVAL)


def stop_polling():
    if bpy.app.timers.is_registered(SELECTION_POLL):
        bpy.app.timers.unregister(SELECTION_POLL)


def poll_selection(context):
    global SYNC_LOCK, _LAST_ACTIVE
    if SYNC_LOCK:
        return _POLL_INTERVAL

    obj = getattr(context, "active_object", None)
    if not _posed_dangle_rig(obj):
        _LAST_ACTIVE = (None, None)
        return None

    active_pb = getattr(context, "active_pose_bone", None)
    if active_pb is None or active_pb.id_data is not obj:
        _LAST_ACTIVE = (rna_identity(obj), None)
        return _POLL_INTERVAL

    key = (rna_identity(obj), active_pb.name)
    if key == _LAST_ACTIVE:
        return _POLL_INTERVAL
    _LAST_ACTIVE = key

    hit = _find_particle_for_bone(obj, obj.dangle_state, active_pb.name)
    if hit is None:
        return _POLL_INTERVAL
    ni, ci, pi = hit

    st = obj.dangle_state
    SYNC_LOCK = True
    try:
        if st.active_dangle_node != ni:
            st.active_dangle_node = ni
        dnode = st.dangle_nodes[ni]
        if dnode.active_chain != ci:
            dnode.active_chain = ci
        chain = dnode.chains[ci]
        if chain.active_particle_index != pi:
            chain.active_particle_index = pi
    finally:
        SYNC_LOCK = False
    return _POLL_INTERVAL


SELECTION_POLL = with_context(poll_selection)


def on_active_chain_update(self, context):
    if SYNC_LOCK:
        return
    if not (0 <= self.active_chain < len(self.chains)):
        return
    chain = self.chains[self.active_chain]
    if len(chain.particles) == 0:
        return
    if chain.active_particle_index == 0:
        on_active_particle_update(chain, context)
    else:
        chain.active_particle_index = 0


def on_active_particle_update(self, context):
    global SYNC_LOCK, _LAST_ACTIVE
    if SYNC_LOCK:
        return
    rig = context.active_object
    if rig is None or rig.type != "ARMATURE" or rig.mode != "POSE":
        return
    if not (0 <= self.active_particle_index < len(self.particles)):
        return
    particle = self.particles[self.active_particle_index]
    if not particle.bone_name:
        return
    target_name = resolve_bone_name(rig, particle.bone_name)
    if not target_name:
        return
    SYNC_LOCK = True
    try:
        _select_single_pose_bone(rig, target_name)
        _LAST_ACTIVE = (rna_identity(rig), target_name)
    finally:
        SYNC_LOCK = False


@persistent
def reset_selection_state(_unused=None):
    global SYNC_LOCK, _LAST_ACTIVE
    SYNC_LOCK = False
    _LAST_ACTIVE = (None, None)
