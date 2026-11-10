from ...blender.gltf_exclusions import collect_excluded_objects
from ..mesh.scope import resolve_mesh_export_scope


def export_scope(context, *, limit_selected, export_visible, previous=(None, ())):
    key = (
        tuple(sorted(obj.name for obj in getattr(context, "selected_objects", ()))),
        len(context.view_layer.objects),
        getattr(getattr(context, "collection", None), "name", ""),
        limit_selected,
        export_visible,
    )
    if key == previous[0]:
        return previous
    meshes = resolve_mesh_export_scope(
        context,
        limit_selected=limit_selected,
        export_visible=export_visible,
        excluded_objects=collect_excluded_objects(),
    ).meshes
    return key, meshes


def export_results_message(export_status, directory):
    exported = []
    export_skipped = []
    notes = []

    for name, error, warnings in export_status:
        if error:
            export_skipped.append((name, error))
        else:
            exported.append(name)
            notes.extend(f"{name}: {warning}" for warning in warnings)

    parts = [f"exported to {directory}:"]
    if exported:
        parts.append("  " + "\n  ".join([f"✓ {name}" for name in exported]))
    else:
        parts.append("  (no successful exports)")

    if export_skipped:
        parts.append("export skipped or failed:")
        parts.append(
            "  " + "\n  ".join([f"✗ {name}: {error}" for name, error in export_skipped])
        )
    if notes:
        parts.append("notes:")
        parts.append("  " + "\n  ".join(notes))

    return "\n".join(parts)
