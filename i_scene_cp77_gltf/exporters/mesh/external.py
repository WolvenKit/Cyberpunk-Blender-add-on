from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass

import bpy

from ..common.atomic import atomic_replace_staged
from .validation import format_fix_summary, prepare_meshes_for_export
from ...blender.mesh_repair import cleanup_validation_temporaries
from ...blender.mesh_validation import MeshValidationOptions
from ...notifications import show_message
from ...gltf.provenance import (
    GLBContentKind,
    GLBSource,
    SelectionOrigin,
    inspect_glb,
    selection_origin,
)


class ExternalGLBExportError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ExternalExportSummary:
    filepath: str
    mesh_count: int
    armature_count: int
    fixes_applied: bool


def _operator_kwargs(operator, values):
    try:
        supported = {prop.identifier for prop in operator.get_rna_type().properties}
    except (AttributeError, RuntimeError):
        return dict(values)
    return {key: value for key, value in values.items() if key in supported}


def _selection_snapshot(context):
    return (
        tuple(context.selected_objects),
        context.view_layer.objects.active,
        context.mode,
    )


def _restore_selection(context, snapshot):
    selected, active, mode = snapshot
    if context.mode != "OBJECT":
        try:
            bpy.ops.object.mode_set(mode="OBJECT")
        except RuntimeError:
            pass
    for obj in tuple(context.selected_objects):
        obj.select_set(False)
    for obj in selected:
        if obj.name in bpy.data.objects:
            obj.select_set(True)
    if active is not None and active.name in bpy.data.objects:
        context.view_layer.objects.active = active
    if mode != "OBJECT":
        target_mode = "EDIT" if str(mode).startswith("EDIT") else mode
        try:
            bpy.ops.object.mode_set(mode=target_mode)
        except RuntimeError:
            pass


def _object_identity(value):
    try:
        return int(value.as_pointer())
    except (AttributeError, ReferenceError):
        return id(value)


def _armatures_for_meshes(meshes):
    result = []
    seen = set()

    def add(armature):
        if armature is None or getattr(armature, "type", None) != "ARMATURE":
            return
        identity = _object_identity(armature)
        if identity in seen:
            return
        seen.add(identity)
        result.append(armature)

    for mesh in meshes:
        add(getattr(mesh, "parent", None))
        for modifier in mesh.modifiers:
            if modifier.type == "ARMATURE":
                add(modifier.object)
    return tuple(result)


def mesh_export_origin(meshes, *, is_skinned: bool) -> SelectionOrigin:
    meshes = tuple(meshes)
    objects = meshes
    if is_skinned:
        objects = (*meshes, *_armatures_for_meshes(meshes))
    return selection_origin(objects)


def _external_export_copies(context, meshes, *, is_skinned, apply_transform):
    copies = []
    source_to_copy = {}
    try:
        for index, source in enumerate(meshes):
            obj = source.copy()
            obj.data = source.data.copy()
            obj.name = f"submesh_{index:02d}_LOD_1"
            obj.data.name = obj.name
            context.scene.collection.objects.link(obj)
            copies.append(obj)
            source_to_copy[_object_identity(source)] = obj

        for source, obj in zip(meshes, copies):
            world = obj.matrix_world.copy()
            source_parent = getattr(source, "parent", None)
            copied_parent = source_to_copy.get(
                _object_identity(source_parent) if source_parent is not None else None
            )
            if copied_parent is not None:
                obj.parent = copied_parent
                obj.matrix_world = world
            elif source_parent is not None and source_parent.type == "ARMATURE" and is_skinned:
                obj.parent = source_parent
                obj.matrix_world = world
            elif obj.parent is not None:
                obj.parent = None
                obj.matrix_world = world

            if apply_transform and not is_skinned:
                matrix = obj.matrix_world.copy()
                obj.data.transform(matrix)
                obj.parent = None
                obj.matrix_world.identity()
                obj.data.update()
        return tuple(copies)
    except Exception:
        cleanup_validation_temporaries(copies, ())
        raise


def export_external_glb(
    context,
    filepath: str,
    meshes,
    *,
    is_skinned: bool,
    apply_transform: bool,
    apply_modifiers: bool,
    mesh_validation_options: MeshValidationOptions | None = None,
) -> ExternalExportSummary:
    path = os.path.abspath(os.fspath(filepath))
    meshes = tuple(meshes)
    if not meshes:
        raise ExternalGLBExportError("Select at least one external mesh to export.")
    if any(getattr(obj, "type", None) != "MESH" for obj in meshes):
        raise ExternalGLBExportError("The external export path accepts mesh objects only.")
    if mesh_export_origin(meshes, is_skinned=is_skinned) is not SelectionOrigin.EXTERNAL:
        raise ExternalGLBExportError(
            "The external export path accepts only meshes without CP77 plugin provenance."
        )
    directory = os.path.dirname(path) or os.getcwd()
    if not os.path.isdir(directory):
        raise ExternalGLBExportError(f"Export directory does not exist: {directory}")

    validation = prepare_meshes_for_export(
        meshes,
        is_skinned=is_skinned,
        options=mesh_validation_options or MeshValidationOptions(),
    )
    validated_meshes = tuple(validation.export_objects)
    temp_objects = validation.temp_objects
    temp_armatures = validation.temp_armatures
    selection = _selection_snapshot(context)
    export_meshes = ()
    visibility = ()
    temporary_path = ""
    try:
        export_meshes = _external_export_copies(
            context,
            validated_meshes,
            is_skinned=is_skinned,
            apply_transform=apply_transform,
        )
        temp_objects.extend(export_meshes)
        armatures = _armatures_for_meshes(export_meshes) if is_skinned else ()
        visibility = tuple((obj, obj.hide_get()) for obj in armatures)

        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        for obj in tuple(context.selected_objects):
            obj.select_set(False)
        for obj in (*export_meshes, *armatures):
            obj.hide_set(False)
            obj.select_set(True)
        context.view_layer.objects.active = export_meshes[0]

        handle, temporary_path = tempfile.mkstemp(
            prefix=f".{os.path.basename(path)}.",
            suffix=".glb",
            dir=directory,
        )
        os.close(handle)
        os.unlink(temporary_path)
        options = _operator_kwargs(
            bpy.ops.export_scene.gltf,
            {
                "filepath": temporary_path,
                "export_format": "GLB",
                "check_existing": False,
                "use_selection": True,
                "export_selected": True,
                "export_animations": False,
                "export_skins": bool(is_skinned),
                "export_yup": True,
                "export_cameras": False,
                "export_lights": False,
                "export_materials": "NONE",
                "export_all_influences": True,
                "export_extras": False,
                "export_apply": bool(apply_modifiers),
                "export_normals": True,
                "export_tangents": True,
                "export_morph": True,
                "export_morph_normal": True,
                "export_morph_tangent": True,
                "export_attributes": True,
                "export_image_format": "NONE",
            },
        )
        if not ({"use_selection", "export_selected"} & set(options)):
            raise ExternalGLBExportError(
                "The installed Blender glTF exporter exposes no selected-object option."
            )
        if not bpy.ops.export_scene.gltf.poll():
            raise ExternalGLBExportError(
                "Blender's glTF exporter is unavailable in the current context."
            )
        result = bpy.ops.export_scene.gltf(**options)
        if "FINISHED" not in result:
            raise ExternalGLBExportError("Blender's glTF exporter did not finish successfully.")
        if not os.path.isfile(temporary_path) or os.path.getsize(temporary_path) < 20:
            raise ExternalGLBExportError("Blender's glTF exporter did not create a valid GLB file.")
        inspection = inspect_glb(temporary_path)
        if inspection.source is not GLBSource.EXTERNAL:
            raise ExternalGLBExportError(
                "Blender's glTF exporter emitted an unexpected CP77 generator marker."
            )
        if inspection.content_kind is not GLBContentKind.MESH:
            raise ExternalGLBExportError(
                "Blender's glTF exporter created a GLB without a mesh-only payload."
            )
        fix_summary = format_fix_summary(validation)
        if fix_summary:
            show_message(fix_summary)
        atomic_replace_staged({path: temporary_path})
        temporary_path = ""
        return ExternalExportSummary(
            filepath=path,
            mesh_count=len(export_meshes),
            armature_count=len(armatures),
            fixes_applied=bool(validation.fixes_applied),
        )
    except Exception as error:
        if isinstance(error, ExternalGLBExportError):
            raise
        raise ExternalGLBExportError(f"External GLB export failed: {error}") from error
    finally:
        if temporary_path:
            try:
                os.unlink(temporary_path)
            except FileNotFoundError:
                pass
        for obj, hidden in visibility:
            if obj.name in bpy.data.objects:
                obj.hide_set(hidden)
        _restore_selection(context, selection)
        cleanup_validation_temporaries(temp_objects, temp_armatures)

