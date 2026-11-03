import os
<<<<<<< Updated upstream

import bpy

from ..animation import export_anims_glb_direct
from .document import export_mesh_glb_direct
from .scope import resolve_mesh_export_scope
from .validation import format_fix_summary, prepare_meshes_for_export
from ...blender.mesh_repair import cleanup_validation_temporaries
from ...blender.mesh_validation import MeshValidationOptions
from ...blender.context import BlenderContextSnapshot, get_safe_mode, safe_mode_switch
from ...blender.selection import select_objects, set_active_collection
from ...gltf.exclusions import collect_excluded_objects
from ...notifications import show_message

RED_COLOR = (1, 0, 0, 1)  # RGBA
GARMENT_CAP_NAME = "_GarmentSupportCap"
GARMENT_WEIGHT_NAME = "_GarmentSupportWeight"
DIRECT_ANIMATION_EXPORT_MARKER = "CP77_DIRECT_ANIMATION_GLB_V1"
DIRECT_MESH_EXPORT_MARKER = "CP77_DIRECT_MESH_GLB_V1"

EXPORT_DEFAULTS = {
    'system': 'METRIC',
    'length_unit': 'METERS',
    'scale_length': 1.0,
    'system_rotation': 'DEGREES',
    'mass_unit': 'KILOGRAMS',
    'temperature_unit': 'KELVIN',
    'time_unit': 'SECONDS',
    'use_separate': False,
    }



def default_cp77_options():
    """Build default glTF export options"""
    major, minor = bpy.app.version[:2]
    options = {
        'export_format': 'GLB',
        'check_existing': True,
        'export_skins': True,
        'export_yup': True,
        'export_cameras': False,
        'export_materials': 'NONE',
        'export_all_influences': True,
        'export_lights': False,
        'export_apply': False,
        'export_extras': True,
        }
    if major >= 4:
        options.update(
                {
                    'export_image_format': 'NONE',
                    'export_try_sparse_sk': False,
                    }
                )
        if minor >= 1:
            options.update(
                    {
                        'export_shared_accessors': True,
                        'export_try_omit_sparse_sk': False,
                        }
                    )
    return options


def cp77_mesh_options():
    """Mesh-specific export options."""
    major, minor = bpy.app.version[:2]
    options = {
        'export_animations': False,
        'export_tangents': True,
        'export_normals': True,
        'export_morph_tangent': True,
        'export_morph_normal': True,
        'export_morph': True,
        'export_attributes': True,
        }
    if major < 4:
        options.update({'export_colors': True})
        if minor >= 2:
            options.update(
                    {
                        "export_all_vertex_colors ": True,
                        "export_active_vertex_color_when_no_material": True,
                        }
                    )
    return options


def add_garment_cap(mesh):
    """Add garment support color attributes to mesh."""
    cap_layer = mesh.data.color_attributes.get(GARMENT_CAP_NAME)
    weight_layer = mesh.data.color_attributes.get(GARMENT_WEIGHT_NAME)

    if cap_layer is None:
        cap_layer = mesh.data.color_attributes.new(
                name=GARMENT_CAP_NAME, domain='CORNER', type='BYTE_COLOR'
                )

    if weight_layer is None:
        weight_layer = mesh.data.color_attributes.new(
                name=GARMENT_WEIGHT_NAME, domain='CORNER', type='BYTE_COLOR'
                )

    # Paint cap layer red
    if cap_layer is not None:
        n = len(cap_layer.data)
        if n:
            cap_layer.data.foreach_set("color", RED_COLOR * n)


def save_user_settings_and_reset_to_default():
    """Back up user's workbench configuration and reset to factory defaults."""
    us = bpy.context.scene.unit_settings
    user_settings = {
        'system': us.system,
        'length_unit': us.length_unit,
        'scale_length': us.scale_length,
        'system_rotation': us.system_rotation,
        'mass_unit': us.mass_unit,
        'temperature_unit': us.temperature_unit,
        'time_unit': us.time_unit,
        'use_separate': us.use_separate,
        }
    try:
        for key, value in EXPORT_DEFAULTS.items():
            setattr(us, key, value)
    except Exception:
        for key, value in user_settings.items():
            setattr(us, key, value)
        raise
    return user_settings


def restore_user_settings(user_settings):
    """Restore user's previous settings."""
    us = bpy.context.scene.unit_settings
    for key, value in user_settings.items():
        setattr(us, key, value)



def set_visible(collection, new_visibility_state):
    for obj in collection.objects:
        if obj.type == 'MESH':
            obj.hide_set(new_visibility_state and not obj.name.startswith('submesh_'))
        if obj.type == 'ARMATURE':
            obj.hide_set(not new_visibility_state)

    return [f for f in collection.objects if f.visible_get()]


def export_cyberpunk_collections_glb(
        context, filepath, export_poses=False, is_skinned=True, try_fix=False,
        red_garment_col=False, apply_transform=True,
        action_filter=False, export_tracks=False, apply_modifiers=True,
        only_visible=False, mesh_validation_options=None,
    ):
    snapshot = BlenderContextSnapshot().store()
    user_settings = None
    exported = []
    try:
        user_settings = save_user_settings_and_reset_to_default()
        if get_safe_mode() != 'OBJECT':
            safe_mode_switch('OBJECT')

        excluded_objects = collect_excluded_objects()
        for collection in tuple(bpy.data.collections):
            if (
                (only_visible and collection.hide_viewport)
                or collection.name.endswith("not_exported")
=======
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
    red_garment_col=False,
    apply_transform=True,
    action_filter=False,
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
>>>>>>> Stashed changes
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

<<<<<<< Updated upstream
                visible_objects = [
                    obj
                    for obj in collection.objects
                    if obj not in excluded_objects
                    and (
                        obj.type == 'ARMATURE'
                        or (
                            obj.type == 'MESH'
                            and obj.name.startswith('submesh')
                        )
                    )
                ]
                if not visible_objects:
                    exported.append((
                        collection.name,
                        "No armatures or meshes starting with 'submesh'",
                    ))
                    continue

                if not set_active_collection(collection, context):
                    exported.append((
                        collection.name,
                        "Failed to set collection as active",
                    ))
=======
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
>>>>>>> Stashed changes
                    continue

                select_objects(
                    visible_objects,
                    reveal=True,
                    clear=True,
                    context=context,
                )
                if not context.selected_objects:
<<<<<<< Updated upstream
                    exported.append((
                        collection.name,
                        "Failed to set child object selection",
                    ))
=======
                    exported.append(
                        (
                            collection.name,
                            "Failed to set child object selection",
                            (),
                        )
                    )
>>>>>>> Stashed changes
                    continue

                collection_path = os.path.join(
                    filepath,
                    f"{collection.name}.glb",
                )
                try:
<<<<<<< Updated upstream
                    export_cyberpunk_glb(
=======
                    result = export_cyberpunk_glb(
>>>>>>> Stashed changes
                        context,
                        collection_path,
                        export_poses=export_poses,
                        export_visible=False,
                        limit_selected=True,
                        is_skinned=is_skinned,
                        try_fix=try_fix,
                        red_garment_col=red_garment_col,
                        apply_transform=apply_transform,
                        action_filter=action_filter,
                        export_tracks=export_tracks,
<<<<<<< Updated upstream
                        apply_modifiers=apply_modifiers,
                        called_from_loop=True,
                        mesh_validation_options=mesh_validation_options,
                        excluded_objects=excluded_objects,
                    )
                    exported.append((collection.name, None))
                except Exception as error:
                    exported.append((collection.name, str(error)))
=======
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
>>>>>>> Stashed changes
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
<<<<<<< Updated upstream
        if user_settings is not None:
            restore_user_settings(user_settings)
=======
>>>>>>> Stashed changes
        snapshot.restore()
    return exported


def export_cyberpunk_glb(
<<<<<<< Updated upstream
        context, filepath, export_poses=False, export_visible=False,
        limit_selected=True, is_skinned=True, try_fix=False,
        red_garment_col=False, apply_transform=True,
        action_filter=False, export_tracks=False, apply_modifiers=True, called_from_loop=False,
        selected_action_names=None, mesh_validation_options=None,
        mesh_scope=None, excluded_objects=None,
        ):
    """Main export function for CP77 glTF files."""
    snapshot = None if called_from_loop else BlenderContextSnapshot().store()
    user_settings = None
    selected_objects = tuple(context.selected_objects)
    try:
        if not called_from_loop:
            user_settings = save_user_settings_and_reset_to_default()
        if get_safe_mode() != 'OBJECT':
            safe_mode_switch('OBJECT')

        if export_poses:
            armatures = [obj for obj in selected_objects if obj.type == 'ARMATURE']
            if not armatures:
                raise ValueError(
                    "No armature objects selected. Please select an armature."
                )
            export_anims(
                context,
                filepath,
                default_cp77_options(),
                armatures,
                True,
                active_action_only=bool(action_filter),
                selected_action_names=selected_action_names,
=======
    context,
    filepath,
    export_poses=False,
    export_visible=False,
    limit_selected=True,
    is_skinned=True,
    try_fix=False,
    red_garment_col=False,
    apply_transform=True,
    action_filter=False,
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
                active_action_only=bool(action_filter),
                selected_action_names=selected_action_names,
                source_rig_path=source_rig_path,
>>>>>>> Stashed changes
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
<<<<<<< Updated upstream
                raise ValueError(
                    "No meshes selected. Please select at least one mesh."
                )
            export_meshes(
                context,
=======
                return OperationResult.cancelled("Select at least one mesh to export.")
            return export_meshes(
>>>>>>> Stashed changes
                filepath,
                is_skinned,
                try_fix,
                red_garment_col,
                apply_transform,
                apply_modifiers,
                meshes,
                mesh_validation_options=mesh_validation_options,
            )
<<<<<<< Updated upstream
        return {'FINISHED'}
    finally:
        if user_settings is not None:
            restore_user_settings(user_settings)
=======
    except (ExportError, MeshValidationError) as error:
        # The scene cannot satisfy the export contract; the message says why, no traceback is needed.
        return OperationResult.cancelled(str(error), error=error)
    finally:
>>>>>>> Stashed changes
        if snapshot is not None:
            snapshot.restore()


def export_anims(
<<<<<<< Updated upstream
        context, filepath, options, armatures, export_tracks=True,
        active_action_only=False, selected_action_names=None,
        ):
    """Export CP77 animations directly without invoking Blender's glTF exporter."""
    print(f"[CP77 Direct Export] {DIRECT_ANIMATION_EXPORT_MARKER}: direct writer selected")
    if len(armatures) != 1:
        raise ValueError(
            "Direct CP77 animation export requires exactly one selected armature."
            )

    summary = export_anims_glb_direct(
        filepath,
        armatures[0],
        export_tracks=bool(export_tracks),
        active_action_only=active_action_only,
        selected_action_names=selected_action_names,
        )
    print(
        f"[CP77 Direct Export] Exported {summary['animation_count']} animations, "
        f"{summary['joint_count']} joints, and {summary['accessor_count']} accessors "
        f"to {summary['filepath']}."
        )
    validation = summary.get("file_validation", {})
    if validation.get("valid"):
        print(
            "[CP77 Direct Export] GLB 2.0 container, skin extras, animation extras, "
            "samplers, accessors and embedded BIN payload validated successfully."
        )
    if not summary.get('source_rest_snapshot'):
        print(
            "[CP77 Direct Export] Source animation rest metadata was unavailable; "
            "the selected MetaRig rest was used as the GLB source skeleton. "
            "Re-import an animation with the synchronized direct importer for exact source-rest retention."
            )
    return {'FINISHED'}


def export_meshes(
        context, filepath, is_skinned, try_fix, red_garment_col,
        apply_transform, apply_modifiers, meshes, mesh_validation_options=None,
        ):
    """Prepare meshes and write the CP77 GLB with the direct mesh writer.

    The direct writer resolves object transforms, the armature binding and the
    split-vertex expansion itself, so no selection state, transform_apply pass or
    armature visibility juggling is required around it.
    """
    print(f"[CP77 Direct Export] {DIRECT_MESH_EXPORT_MARKER}: direct writer selected")
    validation_options = mesh_validation_options or MeshValidationOptions(try_fix=try_fix)
    validation_result = prepare_meshes_for_export(
        meshes,
        is_skinned=is_skinned,
        options=validation_options,
    )
    export_objects = validation_result.export_objects
    temp_objects = validation_result.temp_objects
    temp_armatures = validation_result.temp_armatures

    try:
        for mesh in export_objects:
            if red_garment_col:
                add_garment_cap(mesh)
            if mesh.data.name != mesh.name:
                mesh.data.name = mesh.name

        summary = export_mesh_glb_direct(
            filepath,
            export_objects,
            is_skinned=is_skinned,
            apply_modifiers=apply_modifiers,
            bake_transforms=apply_transform,
        )
        print(
            f"[CP77 Direct Export] Exported {summary['submesh_count']} submeshes, "
            f"{summary['vertex_count']} vertices, {summary['triangle_count']} triangles, "
            f"{summary['joint_count']} joints and {summary['morph_count']} morph targets "
            f"to {summary['filepath']}."
        )
        if summary.get("file_validation", {}).get("valid"):
            print(
                "[CP77 Direct Export] GLB 2.0 container, skin extras, per-vertex "
=======
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
>>>>>>> Stashed changes
                "attributes, morph targets and embedded BIN payload validated successfully."
            )

        fix_summary = format_fix_summary(validation_result)
<<<<<<< Updated upstream
        if fix_summary:
            try:
                show_message(fix_summary)
            except Exception as error:
                print(f"[CP77 Direct Export] Fix summary UI unavailable: {error}")
        return {'FINISHED'}
    finally:
        cleanup_validation_temporaries(temp_objects, temp_armatures)


def ExportAll(self, context):
    """Export all meshes with sourcePath or projPath."""
    to_exp = [
        obj for obj in context.scene.objects
        if obj.type == 'MESH' and ('sourcePath' in obj or 'projPath' in obj)
        ]

    if len(to_exp) > 0:
        excluded_objects = collect_excluded_objects()
        for obj in to_exp:
            filepath = obj.get('projPath', '')
            if filepath:
                export_cyberpunk_glb(
                    context,
                    filepath=filepath,
                    export_poses=False,
                    excluded_objects=excluded_objects,
                )
=======
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
>>>>>>> Stashed changes
