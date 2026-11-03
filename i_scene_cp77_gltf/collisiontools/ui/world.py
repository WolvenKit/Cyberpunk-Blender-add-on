def draw_world(layout, px_s):
    gbox = layout.box()
    gbox.label(text="Environment", icon="WORLD_DATA")
    gbox.prop(px_s, "gravity")
    gbox.operator("physx.update_gravity", icon="FORCE_FORCE", text="Update Gravity")

    fbox = layout.box()
    fbox.label(text="Interaction")
    if not px_s.use_grab_mode:
        fbox.prop(px_s, "force_mode")
        fbox.prop(px_s, "use_force_pos", icon="CURSOR")
        row = fbox.row()
        row.prop(px_s, "force_value")
        row.operator("physx.apply_force", icon="FORCE_LENNARDJONES", text="Apply Force")

    io_box = layout.box()
    io_box.label(text="Physics Resources")
    row = io_box.row(align=True)
    row.operator("physx.export_phys", icon="EXPORT", text="Export Actor .phys")
    row.operator("physx.import_phys", icon="IMPORT", text="Import .phys Actors")
    io_box.operator(
        "physx.import_phys_to_actor", icon="CON_CHILDOF", text="Attach .phys to Object"
    )
    io_box.operator(
        "physx.export_heightfields",
        icon="MESH_GRID",
        text="Export Selected Heightfields",
    )
