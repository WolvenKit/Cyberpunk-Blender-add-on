def draw(layout, context, obj):
    header, panel = layout.panel("root_motion", default_closed=True)
    header.label(text="Root Motion", icon="ANIM")
    if panel is None:
        return
    data = context.scene.rm_data
    col = panel.column(align=True)
    col.label(text="Bone Configuration:", icon="BONE_DATA")
    col.prop_search(data, "root", obj.pose, "bones", text="Root")
    col.prop_search(data, "hip", obj.pose, "bones", text="Hip")
    col.separator()
    col.label(text="Transfer Options:", icon="MODIFIER")
    col.prop(data, "step")
    col.prop(data, "no_rot")
    col.prop(data, "do_vert")
    col.separator()
    col.label(text="Operations:")
    col.operator("cp77.hip_to_root_motion", text="Hip to Root Motion", icon="EXPORT")
    col.operator("cp77.root_to_hip_motion", text="Root to Hip Motion", icon="IMPORT")
    col.operator("cp77.remove_root_motion", text="Remove Root Motion", icon="X")
