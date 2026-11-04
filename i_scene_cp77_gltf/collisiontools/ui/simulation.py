def draw_simulation(layout, px_s):
    row = layout.row()
    if px_s.sim_running:
        row.operator("physx.stop_sim", icon="PAUSE", text="Stop")
    else:
        row.operator("physx.sim_step", icon="PLAY", text="Start")
    layout.prop(px_s, "sim_steps", text="Step Count")
    row = layout.row()
    row.operator("physx.build_scene", text="Rebuild Scene", icon="FILE_REFRESH")
    row.operator("physx.run_steps", icon="NEXT_KEYFRAME", text="Step N")
