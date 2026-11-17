def draw_glb_mesh_validation(context, layout):
    props = context.scene.cp77_mesh_validation
    meshes = tuple(
        obj for obj in context.selected_objects if getattr(obj, "type", None) == "MESH"
    )
    if (
        not meshes
        and getattr(getattr(context, "active_object", None), "type", None) == "MESH"
    ):
        meshes = (context.active_object,)

    box = layout.box()
    box.label(text="GLB Export Validation")
    column = box.column(align=True)
    if not meshes:
        column.label(text="Select one or more meshes", icon="INFO")
    column.prop(props, "is_skinned")

    # One list: what a check finds, Fix repairs, along with what export always needs.
    checks = column.box().column(align=True)
    if props.is_skinned:
        checks.prop(props, "check_unweighted_vertices")
        checks.prop(props, "check_unused_bones")
    checks.prop(props, "check_unused_vertex_groups")
    checks.prop(props, "check_missing_uv")
    checks.prop(props, "check_degenerate_faces")
    checks.prop(props, "check_degenerate_uvs")

    row = column.row(align=True)
    row.operator("cp77.validate_glb_meshes", text="Validate", icon="VIEWZOOM")
    row.operator("cp77.fix_glb_meshes", text="Fix", icon="MODIFIER")

    if props.last_status and props.last_status != "PASS":
        result = box.box()
        result.label(
            text=f"Last result: {props.last_status}",
            icon="ERROR" if props.last_status == "ERROR" else "INFO",
        )
        lines = tuple(line for line in props.last_report.splitlines() if line.strip())
        for line in lines[:12]:
            result.label(text=line[:180])
        if len(lines) > 12:
            result.label(text=f"… {len(lines) - 12} more report lines", icon="INFO")
