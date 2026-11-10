import os
from contextlib import contextmanager

import bpy

from ...assetio.paths import is_plain_file_name
from ...blender.context import BlenderContextSnapshot, get_safe_mode, safe_mode_switch
from ...blender.gltf_exclusions import collect_excluded_objects
from ...blender.mesh_repair import cleanup_validation_temporaries
from ...blender.mesh_validation import MeshValidationError, MeshValidationOptions
from ...blender.operator_results import OperationResult
from ...blender.selection import select_objects, set_active_collection
from ...core.log import get_logger
from ..animation.writer import export_animation
from ..common.errors import ExportError
from .scope import MeshExportScope, resolve_mesh_export_scope
from .validation import format_fix_summary, prepare_meshes_for_export
from .writer import export_mesh_glb_direct, mesh_glb_payload

_LOG = get_logger(__name__)

DIRECT_ANIMATION_EXPORT_MARKER = "CP77_DIRECT_ANIMATION_GLB_V1"
DIRECT_MESH_EXPORT_MARKER = "CP77_DIRECT_MESH_GLB_V1"


def _is_cyberpunk_mesh(obj):
    """A mesh following WolvenKit's submesh naming, or one the add-on imported under any name"""
    return obj.name.startswith("submesh") or bool(obj.get("cp77_imported_mesh"))


def export_cyberpunk_collections_glb(
    context,
    filepath,
    export_poses=False,
    is_skinned=True,
    try_fix=False,
    apply_transform=True,
    export_tracks=False,
    apply_modifiers=True,
    only_visible=False,
    mesh_validation_options=None,
    root_motion="CLIP",
):
    """Export each collection holding Cyberpunk meshes to its own .glb in the folder filepath"""
    snapshot = BlenderContextSnapshot().store()
    exported = []
    try:
        if get_safe_mode() != "OBJECT":
            safe_mode_switch("OBJECT")

        excluded_objects = collect_excluded_objects()
        # Collections whose names differ only in case write the same file on Windows and default macOS volumes.
        file_owners = {}
        for collection in tuple(bpy.data.collections):
            if (only_visible and collection.hide_viewport) or collection.name.endswith(
                "not_exported"
            ):
                continue

            old_visible = collection.hide_viewport
            old_render = collection.hide_render
            object_visibility = {
                obj.name: (
                    obj.hide_viewport,
                    obj.hide_select,
                    obj.hide_get(),
                )
                for obj in collection.objects
            }
            try:
                collection.hide_viewport = False
                collection.hide_render = False

                armatures = tuple(
                    obj
                    for obj in collection.objects
                    if obj.type == "ARMATURE" and obj not in excluded_objects
                )
                # Every mesh of an exported collection is exported, whatever its name; only the glTF exclusions
                # leave one out.
                meshes = tuple(
                    obj
                    for obj in collection.objects
                    if obj.type == "MESH" and obj not in excluded_objects
                )
                if export_poses and not armatures:
                    exported.append((collection.name, "No armature", ()))
                    continue
                if not export_poses and not any(
                    _is_cyberpunk_mesh(obj) for obj in meshes
                ):
                    exported.append(
                        (
                            collection.name,
                            "No Cyberpunk meshes (named 'submesh…' or imported by the add-on)",
                            (),
                        )
                    )
                    continue
                # The collection names its file in the chosen folder, so it cannot name a folder or drive.
                if not is_plain_file_name(collection.name):
                    exported.append(
                        (
                            collection.name,
                            "The collection name is not a plain file name",
                            (),
                        )
                    )
                    continue
                owner = file_owners.setdefault(
                    collection.name.casefold(), collection.name
                )
                if owner != collection.name:
                    exported.append(
                        (
                            collection.name,
                            f"Its file would replace {owner}.glb on file systems that ignore case",
                            (),
                        )
                    )
                    continue
                visible_objects = (*armatures, *meshes)

                if not set_active_collection(collection, context):
                    exported.append(
                        (
                            collection.name,
                            "Failed to set collection as active",
                            (),
                        )
                    )
                    continue

                select_objects(
                    visible_objects,
                    reveal=True,
                    clear=True,
                    context=context,
                )
                if not context.selected_objects:
                    exported.append(
                        (
                            collection.name,
                            "Failed to set child object selection",
                            (),
                        )
                    )
                    continue

                collection_path = os.path.join(
                    filepath,
                    f"{collection.name}.glb",
                )
                try:
                    result = export_cyberpunk_glb(
                        context,
                        collection_path,
                        export_poses=export_poses,
                        export_visible=False,
                        limit_selected=True,
                        is_skinned=is_skinned,
                        try_fix=try_fix,
                        apply_transform=apply_transform,
                        export_tracks=export_tracks,
                        root_motion=root_motion,
                        apply_modifiers=apply_modifiers,
                        called_from_loop=True,
                        mesh_validation_options=mesh_validation_options,
                        mesh_scope=MeshExportScope(meshes, "collection"),
                        excluded_objects=excluded_objects,
                    )
                    if result.ok:
                        exported.append((collection.name, None, result.warnings))
                    else:
                        exported.append((collection.name, result.message, ()))
                except Exception as error:
                    _LOG.error(
                        "Collection %s was not exported: %s",
                        collection.name,
                        error,
                        exc_info=True,
                    )
                    exported.append((collection.name, str(error), ()))
            finally:
                collection.hide_viewport = old_visible
                collection.hide_render = old_render
                for obj_name, visibility in object_visibility.items():
                    obj = bpy.data.objects.get(obj_name)
                    if obj is None:
                        continue
                    obj.hide_viewport, obj.hide_select = visibility[:2]
                    obj.hide_set(visibility[2])
    finally:
        snapshot.restore()
    return exported


def export_cyberpunk_glb(
    context,
    filepath,
    export_poses=False,
    export_visible=False,
    limit_selected=True,
    is_skinned=True,
    try_fix=False,
    apply_transform=True,
    export_tracks=False,
    apply_modifiers=True,
    called_from_loop=False,
    selected_action_names=None,
    mesh_validation_options=None,
    mesh_scope=None,
    excluded_objects=None,
    root_motion="CLIP",
    source_rig_path="",
):
    """Write the selected meshes, or the selected MetaRig's animations, as one Cyberpunk GLB"""
    snapshot = None if called_from_loop else BlenderContextSnapshot().store()
    selected_objects = tuple(context.selected_objects)
    try:
        if get_safe_mode() != "OBJECT":
            safe_mode_switch("OBJECT")

        if export_poses:
            armatures = [obj for obj in selected_objects if obj.type == "ARMATURE"]
            if not armatures:
                return OperationResult.cancelled(
                    "Select the armature whose animations to export."
                )
            return export_anims(
                filepath,
                armatures,
                export_tracks=bool(export_tracks),
                root_motion=root_motion,
                selected_action_names=selected_action_names,
                source_rig_path=source_rig_path,
            )
        else:
            if excluded_objects is None:
                excluded_objects = collect_excluded_objects()
            scope = mesh_scope or resolve_mesh_export_scope(
                context,
                limit_selected=limit_selected,
                export_visible=export_visible,
                excluded_objects=excluded_objects,
            )
            meshes = list(scope.meshes)
            if not meshes:
                return OperationResult.cancelled("Select at least one mesh to export.")
            return export_meshes(
                filepath,
                is_skinned,
                try_fix,
                False,
                apply_transform,
                apply_modifiers,
                meshes,
                mesh_validation_options=mesh_validation_options,
            )
    except (ExportError, MeshValidationError) as error:
        # The scene cannot satisfy the export contract; the message says why, no traceback is needed.
        return OperationResult.cancelled(str(error), error=error)
    finally:
        if snapshot is not None:
            snapshot.restore()


def export_anims(
    filepath,
    armatures,
    *,
    export_tracks=True,
    active_action_only=False,
    selected_action_names=None,
    root_motion="CLIP",
    source_rig_path="",
):
    """Export CP77 animations directly without invoking Blender's glTF exporter"""
    _LOG.debug("Animation export writer selected: %s", DIRECT_ANIMATION_EXPORT_MARKER)
    summary = export_animation(
        filepath,
        armatures,
        export_tracks=bool(export_tracks),
        active_action_only=active_action_only,
        selected_action_names=selected_action_names,
        root_motion=root_motion,
        source_rig_path=source_rig_path,
    )
    _LOG.info(
        "Exported %s animations, %s joints, and %s accessors to %s.",
        summary["animation_count"],
        summary["joint_count"],
        summary["accessor_count"],
        summary["filepath"],
    )
    validation = summary.get("file_validation", {})
    if validation.get("valid"):
        _LOG.debug(
            "GLB validation passed: skin extras, animation extras, "
            "samplers, accessors and embedded BIN payload validated successfully."
        )
    warnings = ()
    if not summary.get("source_rest_snapshot"):
        warnings = (
            "Source animation rest metadata unavailable; the selected MetaRig rest was used as the GLB source "
            "skeleton. Re-import an animation with the synchronized direct importer for exact source-rest retention.",
        )
    tracks = (
        "with synchronized float tracks"
        if export_tracks
        else "keeping the imported float-track payloads"
    )
    return OperationResult.finished(
        f"Exported {summary['animation_count']} animations to {os.path.basename(summary['filepath'])}, {tracks}.",
        warnings=warnings,
    )


def export_meshes(
    filepath,
    is_skinned,
    try_fix,
    red_garment_col,
    apply_transform,
    apply_modifiers,
    meshes,
    mesh_validation_options=None,
):
    """Prepare meshes and write the CP77 GLB with the direct mesh writer"""
    _LOG.debug("Mesh export writer selected: %s", DIRECT_MESH_EXPORT_MARKER)
    validation_options = mesh_validation_options or MeshValidationOptions(
        try_fix=try_fix
    )
    with _prepared_meshes(meshes, is_skinned, validation_options) as validation_result:
        summary = export_mesh_glb_direct(
            filepath,
            validation_result.export_objects,
            is_skinned=is_skinned,
            apply_modifiers=apply_modifiers,
            bake_transforms=apply_transform,
            ensure_garment_attributes=bool(red_garment_col),
        )
        _LOG.info(
            "Exported %s submeshes, %s vertices, %s triangles, %s joints and %s morph targets to %s.",
            summary["submesh_count"],
            summary["vertex_count"],
            summary["triangle_count"],
            summary["joint_count"],
            summary["morph_count"],
            summary["filepath"],
        )
        if summary.get("file_validation", {}).get("valid"):
            _LOG.debug(
                "GLB validation passed: skin extras, per-vertex "
                "attributes, morph targets and embedded BIN payload validated successfully."
            )

        fix_summary = format_fix_summary(validation_result)
        return OperationResult.finished(
            f"Exported {summary['submesh_count']} submeshes ({summary['vertex_count']} vertices) to "
            f"{os.path.basename(summary['filepath'])}.",
            warnings=(fix_summary,) if fix_summary else (),
        )


@contextmanager
def _prepared_meshes(meshes, is_skinned, validation_options):
    """The meshes validated and prepared for export"""
    validation_result = prepare_meshes_for_export(
        meshes, is_skinned=is_skinned, options=validation_options
    )
    try:
        yield validation_result
    finally:
        cleanup_validation_temporaries(
            validation_result.temp_objects, validation_result.temp_armatures
        )


def build_mesh_glb_payload(
    meshes, *, is_skinned, garment, apply_transform=True, apply_modifiers=True
):
    """The GLB bytes export_meshes writes for meshes with default validation, and its summary"""
    with _prepared_meshes(
        meshes, is_skinned, MeshValidationOptions(try_fix=False)
    ) as validation_result:
        return mesh_glb_payload(
            validation_result.export_objects,
            is_skinned=is_skinned,
            apply_modifiers=apply_modifiers,
            bake_transforms=apply_transform,
            ensure_garment_attributes=bool(garment),
        )
