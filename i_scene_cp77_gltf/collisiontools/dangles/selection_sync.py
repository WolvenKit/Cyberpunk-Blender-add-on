import bpy

SYNC_LOCK = False
_LAST_ACTIVE = (None, None)
_POLL_INTERVAL = 0.15


def _find_particle_for_bone(state, bone_name):
    for ni, dnode in enumerate(state.dangle_nodes):
        for ci, chain in enumerate(dnode.chains):
            for pi, particle in enumerate(chain.particles):
                if particle.bone_name == bone_name:
                    return ni, ci, pi
    return None


def _tag_view3d_redraw():
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()


def _select_single_pose_bone(rig, bone_name):
    pose = rig.pose
    for pb in pose.bones:
        if pb.bone.select:
            pb.bone.select = False
    target_pb = pose.bones.get(bone_name)
    if target_pb is None:
        return
    target_pb.bone.select = True
    target_bone = rig.data.bones.get(bone_name)
    if target_bone is not None:
        rig.data.bones.active = target_bone
    _tag_view3d_redraw()


def _poll_selection():
    global SYNC_LOCK, _LAST_ACTIVE
    if SYNC_LOCK:
        return _POLL_INTERVAL

    ctx = bpy.context
    obj = getattr(ctx, "active_object", None)
    if obj is None or obj.type != 'ARMATURE' or obj.mode != 'POSE':
        _LAST_ACTIVE = (None, None)
        return _POLL_INTERVAL
    if not obj.dangle_state.is_dangle_rig:
        return _POLL_INTERVAL

    active_pb = getattr(ctx, "active_pose_bone", None)
    if active_pb is None or active_pb.id_data is not obj:
        _LAST_ACTIVE = (obj.name, None)
        return _POLL_INTERVAL

    key = (obj.name, active_pb.name)
    if key == _LAST_ACTIVE:
        return _POLL_INTERVAL
    _LAST_ACTIVE = key

    hit = _find_particle_for_bone(obj.dangle_state, active_pb.name)
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
    if rig is None or rig.type != 'ARMATURE' or rig.mode != 'POSE':
        return
    if not (0 <= self.active_particle_index < len(self.particles)):
        return
    particle = self.particles[self.active_particle_index]
    if not particle.bone_name:
        return
    SYNC_LOCK = True
    try:
        _select_single_pose_bone(rig, particle.bone_name)
        _LAST_ACTIVE = (rig.name, particle.bone_name)
    finally:
        SYNC_LOCK = False


def register():
    if not bpy.app.timers.is_registered(_poll_selection):
        bpy.app.timers.register(
            _poll_selection, first_interval=_POLL_INTERVAL, persistent=True
        )


def unregister():
    if bpy.app.timers.is_registered(_poll_selection):
        bpy.app.timers.unregister(_poll_selection)