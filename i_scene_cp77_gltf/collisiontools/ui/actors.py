def draw_actors(layout, px_s):
    row = layout.row()
    row.template_list(
        "PHYSX_UL_actor_list", "", px_s, "actors", px_s, "actor_list_index"
    )
    col = row.column(align=True)
    col.operator("physx.list_action", icon="ADD", text="").action = "ADD"
    col.operator("physx.list_action", icon="REMOVE", text="").action = "REMOVE"

    if len(px_s.actors) == 0 or px_s.actor_list_index >= len(px_s.actors):
        return
    item = px_s.actors[px_s.actor_list_index]
    obj = item.obj_ref
    if not obj:
        return
    px = obj.physx

    header_set, panel_set = layout.panel("physx_actor_settings", default_closed=True)
    header_set.label(text="Actor Settings")
    if panel_set:
        panel_set.label(text=obj.name, icon="EDITMODE_HLT")
        panel_set.prop(
            item, "visualization_enabled", text="Collider Visualization", toggle=True
        )

        header_dyn, panel_dyn = panel_set.panel(
            "physx_actor_dynamics", default_closed=True
        )
        header_dyn.label(text="Dynamics")
        if panel_dyn:
            row = panel_dyn.row()
            row.prop(px, "calc_mass", toggle=True)
            row.prop(px, "calc_offset", toggle=True)
            row.prop(px, "calc_inertia", toggle=True)
            panel_dyn.operator("physx.calc_dynamics", icon="PREFERENCES")

            col = panel_dyn.column()
            col.active = not px.calc_mass
            col.prop(px, "mass")
            col = panel_dyn.column()
            col.active = not px.calc_offset
            col.prop(px, "com_offset")
            col = panel_dyn.column()
            col.active = not px.calc_inertia
            col.prop(px, "inertia")

    header_col, panel_col = layout.panel("physx_colliders", default_closed=True)
    header_col.label(text="Colliders")
    if panel_col is None:
        return

    header_shp, panel_shp = panel_col.panel("physx_shapes_list", default_closed=True)
    header_shp.label(text="Shapes")
    header_shp.operator("physx.shape_action", icon="ADD", text="").action = "ADD"
    header_shp.operator("physx.shape_action", icon="REMOVE", text="").action = "REMOVE"
    if panel_shp:
        row = panel_shp.row()
        row.template_list("PHYSX_UL_shape_list", "", px, "shapes", px, "shape_index")

    if len(px.shapes) == 0 or px.shape_index >= len(px.shapes):
        return
    shape = px.shapes[px.shape_index]

    shape_box = panel_col.box()
    shape_box.label(text="Shape Properties")
    row = shape_box.row(align=True)
    row.prop(shape, "name", text="Name: ")
    row = shape_box.row(align=True)
    row.prop(shape, "physics_material", text="Material: ")
    row = shape_box.row(align=True)
    row.prop(shape, "collision_preset", text="Filter: ")

    shape_box = panel_col.box()
    row = shape_box.row(align=True)
    row.label(text="Dimensions: ")
    if shape.shape_type != "HEIGHTFIELD":
        row = shape_box.row(align=True)
        row.operator(
            "physx.fit_bounds_shape", icon="FULLSCREEN_ENTER", text="Fit to Bounds"
        )
    row = shape_box.row(align=True)
    if shape.shape_type == "BOX":
        row.prop(shape, "dim_x", text="X")
        row.prop(shape, "dim_y", text="Y")
        row.prop(shape, "dim_z", text="Z")
    elif shape.shape_type in ("SPHERE", "CAPSULE"):
        row.prop(shape, "dim_x", text="R")
    if shape.shape_type == "CAPSULE":
        row.prop(shape, "dim_y", text="H-H")
    if shape.shape_type == "HEIGHTFIELD":
        scale_box = shape_box.box()
        scale_box.label(text="Heightfield Scale")
        row = scale_box.row(align=True)
        row.prop(shape, "heightfield_height_scale", text="Height")
        row.prop(shape, "heightfield_row_scale", text="Row")
        row.prop(shape, "heightfield_column_scale", text="Column")

    if shape.shape_type in ("CONVEX", "TRIANGLE", "HEIGHTFIELD"):
        cook_box = panel_col.box()
        cook_box.label(text="Native Geometry")
        if shape.shape_type in ("CONVEX", "TRIANGLE"):
            if shape.shape_type == "CONVEX":
                cook_box.prop(shape, "vertex_limit")
            cook_box.operator("physx.cook_mesh", icon="SCULPTMODE_HLT")
        elif shape.shape_type == "HEIGHTFIELD":
            row = cook_box.row(align=True)
            row.prop(shape, "heightfield_rows")
            row.prop(shape, "heightfield_columns")
            cook_box.operator(
                "physx.cook_mesh", icon="MESH_GRID", text="Cook From Active Mesh"
            )
        if not shape.is_cooked:
            cook_box.label(text="Mesh not cooked", icon="ERROR")
        row = cook_box.row(align=True)
        row.operator("physx.save_cooked", icon="FILE_TICK", text="Save")
        row.operator("physx.load_cooked", icon="FILE_FOLDER", text="Load")

    header_trn, panel_trn = panel_col.panel("physx_transforms", default_closed=True)
    header_trn.label(text="Local Transform")
    if panel_trn is None:
        return
    if item.poll_armature_availability():
        box = panel_trn.box()
        box.label(text="Transform Target (Bone)", icon="BONE_DATA")
        box.prop(item, "use_bone_parent", text="Use Bone Parent", toggle=True)
        if item.use_bone_parent:
            col = box.column()
            col.prop(item, "parent_armature", text="Armature")
            if item.parent_armature and item.parent_armature != "NONE":
                col.prop(item, "target_bone", text="Bone")
            else:
                col.label(text="Select an armature first", icon="ERROR")

    box = panel_trn.box()
    box.label(text="Local Transform")
    box.prop(shape, "local_pos")
    box.prop(shape, "local_rot")
