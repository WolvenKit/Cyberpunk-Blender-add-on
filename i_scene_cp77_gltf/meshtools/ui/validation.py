def draw_glb_mesh_validation(context, layout):
    props = context.scene.cp77_mesh_validation
    meshes = tuple(
        obj for obj in context.selected_objects if getattr(obj, "type", None) == "MESH"
    )
    if not meshes and getattr(getattr(context, "active_object", None), "type", None) == "MESH":
        meshes = (context.active_object,)

    box = layout.box()
    box.label(text="GLB Export Validation", icon="CHECKMARK")
    column = box.column(align=True)
    column.label(
        text=(
            f"{len(meshes)} selected mesh{'es' if len(meshes) != 1 else ''}"
            if meshes
            else "Select one or more meshes"
        ),
        icon="MESH_DATA" if meshes else "INFO",
    )
    column.prop(props, "is_skinned")
    column.prop(props, "advanced_validation")

    if props.advanced_validation:
        checks = column.box().column(align=True)
        checks.label(text="Additional Checks")
        checks.prop(props, "check_missing_uv")
        checks.prop(props, "check_degenerate_faces")
        checks.prop(props, "check_degenerate_uvs")
        if props.is_skinned:
            checks.prop(props, "check_unweighted_vertices")
            checks.prop(props, "check_unused_bones")

    row = column.row(align=True)
    row.operator("cp77.validate_glb_meshes", text="Validate", icon="VIEWZOOM")
    row.operator("cp77.fix_glb_meshes", text="Apply Fixes", icon="MODIFIER")

    repair_box = column.box()
    header = repair_box.row(align=True)
    header.prop(
        props,
        "show_fixes",
        text="Repair Options",
        icon="TRIA_DOWN" if props.show_fixes else "TRIA_RIGHT",
        emboss=False,
    )
    if props.show_fixes:
        fixes = repair_box.column(align=True)
        fixes.prop(props, "fix_remove_unmatched_vertex_groups")
        fixes.prop(props, "fix_apply_autofitter_shape_keys")
        if props.advanced_validation:
            if props.check_missing_uv:
                fixes.prop(props, "fix_add_missing_uv")
            if props.check_degenerate_faces:
                fixes.prop(props, "fix_dissolve_degenerate_faces")
            if props.check_degenerate_uvs:
                fixes.prop(props, "fix_dissolve_degenerate_uvs")
            if props.is_skinned and props.check_unweighted_vertices:
                fixes.prop(props, "fix_assign_unweighted_vertices")
            if props.is_skinned and props.check_unused_bones:
                fixes.prop(props, "fix_remove_unused_bones")
        warning = fixes.box()
        warning.label(text="Apply Fixes edits selected source meshes.", icon="ERROR")
        warning.label(text="The operation is undoable; export-time fixes still use copies.")

    if props.last_status:
        result = box.box()
        icon = "CHECKMARK" if props.last_status == "PASS" else (
            "ERROR" if props.last_status == "ERROR" else "INFO"
        )
        result.label(text=f"Last result: {props.last_status}", icon=icon)
        counts = result.row(align=True)
        counts.label(text=f"Meshes: {props.last_mesh_count}")
        counts.label(text=f"Issues: {props.last_issue_count}")
        counts.label(text=f"Fixes: {props.last_fix_count}")
        counts.label(text=f"Remaining: {props.last_remaining_count}")
        lines = tuple(line for line in props.last_report.splitlines() if line.strip())
        for line in lines[:12]:
            result.label(text=line[:180])
        if len(lines) > 12:
            result.label(text=f"… {len(lines) - 12} more report lines", icon="INFO")
