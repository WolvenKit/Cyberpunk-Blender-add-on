import os
import re
import sys

import bpy.utils.previews
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    EnumProperty,
    IntProperty,
    StringProperty,
)
from bpy.types import Operator, PropertyGroup, TOPBAR_MT_file_export, UIList
from bpy_extras.io_utils import ExportHelper

from ..animation.domain.clip.root_motion import ROOT_MOTION_EXPORT_ITEMS
from ..blender.gltf_exclusions import collect_excluded_objects
from ..blender.mesh_validation import MeshValidationOptions
from ..blender.operator_results import execute_operation
from ..core.log import get_logger, log_once
from ..core.notifications import report
from ..core.registration import RegistrationLedger, get_classes
from ..icons.cp77_icons import get_icon
from .animation.document import compatible_actions_for_export
from .animation.rig_source import animation_rig_export_entries
from .animation.writer import animation_glb_path
from .animgraph.operators import ANIMGRAPH_EXPORT_OPERATOR_CLASSES
from .materials.hair_profile import cp77_hp_export
from .materials.instance import cp77_materialinstance_export
from .materials.multilayer_mask import cp77_mlmask_export
from .materials.multilayer_setup import cp77_mlsetup_export
from .materials.project_paths import default_project_output, replace_depot_suffix
from .mesh.orchestration import export_cyberpunk_collections_glb, export_cyberpunk_glb
from .mesh.scope import resolve_mesh_export_scope
from .mesh.writer import mesh_glb_path
from .rig.writer import export_active_rig
from .sector.execution import export_project_sectors

_LOG = get_logger(__name__)


def _selected_export_armatures(context):
    view_layer = getattr(context, "view_layer", None)
    objects = getattr(view_layer, "objects", ()) if view_layer is not None else ()
    selected = [
        obj
        for obj in objects
        if getattr(obj, "type", None) == "ARMATURE" and obj.select_get()
    ]
    if selected:
        return selected
    return [
        obj
        for obj in getattr(bpy.context, "selected_objects", ())
        if getattr(obj, "type", None) == "ARMATURE"
    ]


def _active_material(operator, context):
    """The active object's active material, or None after telling the user why there is none"""
    active_object = context.active_object
    if not active_object:
        report(operator, "ERROR_INVALID_CONTEXT", "No active object", logger=_LOG)
        return None
    active_material = active_object.active_material
    if not active_material:
        report(
            operator,
            "ERROR_INVALID_CONTEXT",
            "Active object has no material.",
            logger=_LOG,
        )
        return None
    return active_material


def _mesh_validation_options(operator):
    return MeshValidationOptions(
        advanced_validation=operator.advanced_validation,
        check_missing_uv=operator.check_missing_uv,
        check_degenerate_faces=operator.check_degenerate_faces,
        check_degenerate_uvs=operator.check_degenerate_uvs,
        check_unweighted_vertices=operator.check_unweighted_vertices,
        check_unused_bones=operator.check_unused_bones,
        try_fix=operator.try_fix,
        fix_remove_unmatched_vertex_groups=operator.fix_remove_unmatched_vertex_groups,
        fix_apply_autofitter_shape_keys=operator.fix_apply_autofitter_shape_keys,
        fix_add_missing_uv=operator.fix_add_missing_uv,
        fix_dissolve_degenerate_faces=operator.fix_dissolve_degenerate_faces,
        fix_dissolve_degenerate_uvs=operator.fix_dissolve_degenerate_uvs,
        fix_assign_unweighted_vertices=operator.fix_assign_unweighted_vertices,
        fix_remove_unused_bones=operator.fix_remove_unused_bones,
        fix_limit_influences=operator.fix_limit_influences,
    )


def _draw_mesh_validation_options(layout, operator):
    validation_box = layout.box()
    validation_box.label(text="Mesh Validation")
    validation_box.prop(operator, "advanced_validation")
    if operator.advanced_validation:
        checks = validation_box.column(align=True)
        checks.prop(operator, "check_missing_uv")
        checks.prop(operator, "check_degenerate_faces")
        checks.prop(operator, "check_degenerate_uvs")
        if operator.is_skinned:
            checks.prop(operator, "check_unweighted_vertices")
            checks.prop(operator, "check_unused_bones")

    validation_box.prop(operator, "try_fix")
    if not operator.try_fix:
        return

    fixes = validation_box.box()
    fixes.label(text="Apply Fixes", icon="MODIFIER")
    fixes.prop(operator, "fix_remove_unmatched_vertex_groups")
    fixes.prop(operator, "fix_apply_autofitter_shape_keys")
    if operator.advanced_validation:
        if operator.check_missing_uv:
            fixes.prop(operator, "fix_add_missing_uv")
        if operator.check_degenerate_faces:
            fixes.prop(operator, "fix_dissolve_degenerate_faces")
        if operator.check_degenerate_uvs:
            fixes.prop(operator, "fix_dissolve_degenerate_uvs")
        if operator.is_skinned and operator.check_unweighted_vertices:
            fixes.prop(operator, "fix_assign_unweighted_vertices")
        if operator.is_skinned and operator.check_unused_bones:
            fixes.prop(operator, "fix_remove_unused_bones")
    if operator.is_skinned:
        fixes.prop(operator, "fix_limit_influences")


class CP77RigJSONExport(Operator, ExportHelper):
    bl_idname = "export_scene.cp77_rig_export"
    bl_label = "Export Rig Updates to JSON for Cyberpunk"
    # The export leaves edit or pose mode for the write, which commits pending edit-mode bone changes.
    bl_options = {"REGISTER", "UNDO"}
    bl_description = "Export changes to Rigs exported from JSON back to JSON"
    filename_ext = ".rig.json"
    filter_glob: StringProperty(default="*.rig.json", options={"HIDDEN"})

    def execute(self, context):
        return execute_operation(
            self, "Rig export", export_active_rig, context, self.filepath
        )

    def check(self, context):
        # Ensure the file path ends with the correct extension
        if not self.filepath.endswith(self.filename_ext):
            self.filepath += self.filename_ext
        return True


class CP77StreamingSectorExport(Operator, ExportHelper):
    bl_idname = "export_scene.cp77_sector"
    bl_label = "Export Sector Updates for Cyberpunk"
    bl_options = {"REGISTER"}
    bl_description = "Export changes to Sectors back to project"
    filename_ext = ".cpmodproj"
    filter_glob: StringProperty(default="*.cpmodproj", options={"HIDDEN"})

    def draw(self, context):
        props = context.scene.cp77_panel_props
        layout = self.layout
        layout.prop(props, "axl_yaml")
        layout.prop(props, "include_heightfields")

    def execute(self, context):
        props = context.scene.cp77_panel_props
        return execute_operation(
            self,
            "Sector export",
            export_project_sectors,
            self.filepath,
            props.axl_yaml,
            include_heightfields=props.include_heightfields,
        )


class CP77CollectionExport(Operator, ExportHelper):
    bl_idname = "export_scene.cp77_collection_glb"
    bl_label = "Export for Cyberpunk"
    bl_options = {"REGISTER"}
    bl_description = "Export to GLB with optimized settings for use with Wolvenkit for Cyberpunk 2077"
    filename_ext = ".glb"

    directory: StringProperty(  # pyright: ignore[reportInvalidTypeForm]
        name="Export Folder",
        description="Folder where GLB files will be saved",
        subtype="DIR_PATH",
        default="",
    )

    only_visible: BoolProperty(  # pyright: ignore[reportInvalidTypeForm]
        name="Only Visible",
        default=False,
        description="Check this to export only collections that are currently visible in view port",
    )

    is_skinned: BoolProperty(  # pyright: ignore[reportInvalidTypeForm]
        name="Skinned Mesh",
        default=True,
        description="Ensure armatures and vert groups are exported.",
    )
    try_fix: BoolProperty(  # pyright: ignore[reportInvalidTypeForm]
        name="Try Fix",
        default=False,
        description="Enable selected repairs on temporary export copies",
    )

    advanced_validation: BoolProperty(
        name="Additional Validation",
        default=False,
        description="Enable optional UV, degeneracy, weight and unused-bone checks",
    )
    check_missing_uv: BoolProperty(name="Require Active UV Layer", default=True)
    check_degenerate_faces: BoolProperty(name="Check Degenerate Faces", default=True)
    check_degenerate_uvs: BoolProperty(name="Check Degenerate UVs", default=False)
    check_unweighted_vertices: BoolProperty(
        name="Check Unweighted Vertices", default=True
    )
    check_unused_bones: BoolProperty(
        name="Check Bones Without Vertex Groups",
        default=False,
        description="Check the armature against the union of vertex groups on exported submeshes",
    )
    fix_remove_unmatched_vertex_groups: BoolProperty(
        name="Remove Vertex Groups Without Bones",
        default=True,
    )
    fix_apply_autofitter_shape_keys: BoolProperty(
        name="Bake Autofitter Shape Keys",
        default=False,
        description="Bake Autofitter keys at their current values into temporary export copies",
    )
    fix_add_missing_uv: BoolProperty(name="Add Missing UV Layer", default=True)
    fix_dissolve_degenerate_faces: BoolProperty(
        name="Dissolve Degenerate Faces/Vertices",
        default=True,
    )
    fix_dissolve_degenerate_uvs: BoolProperty(
        name="Dissolve UV-Degenerate Faces/Vertices",
        default=False,
    )
    fix_assign_unweighted_vertices: BoolProperty(
        name="Assign Unweighted Vertices to Root",
        default=False,
    )
    fix_remove_unused_bones: BoolProperty(
        name="Remove Bones Without Vertex Groups",
        default=False,
        description="Create a temporary armature, remove unmatched bones and reparent retained descendants",
    )
    fix_limit_influences: BoolProperty(
        name="Limit Bone Influences",
        default=False,
        description="Keep each vertex's 8 strongest bone influences on the temporary export copy and normalize "
        "them. This changes how those vertices deform",
    )

    export_poses: BoolProperty(  # pyright: ignore[reportInvalidTypeForm]
        name="Animations",
        default=False,
        description="Use this option if you are exporting anims to be imported into wkit as .anim",
    )

    apply_transform: BoolProperty(  # pyright: ignore[reportInvalidTypeForm]
        name="Apply Transform",
        default=True,
        description="Applies the transform of the objects. Disable this if you don't care about the location/rotation/scale of the objects",
    )

    apply_modifiers: BoolProperty(  # pyright: ignore[reportInvalidTypeForm]
        name="Apply Modifiers",
        default=True,
        description="Applies the modifiers of the objects. Disable this if you have shapekeys.",
    )
    root_motion: EnumProperty(
        name="Root Motion",
        items=ROOT_MOTION_EXPORT_ITEMS,
        default="CLIP",
    )
    export_tracks: BoolProperty(  # pyright: ignore[reportInvalidTypeForm]
        name="Synchronize Float Tracks",
        default=True,
        description="Update imported trackKeys from live Float F-Curves; disable to preserve the source payload unchanged",
    )

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        box.label(text="Export Options")
        row = box.row(align=True)
        row.prop(self, "only_visible")
        row = box.row(align=True)
        row.prop(self, "export_poses")
        if self.export_poses:
            row = box.row(align=True)
            row.prop(self, "export_tracks")
            box.prop(self, "root_motion")
            return

        row = box.row(align=True)
        row.prop(self, "is_skinned")
        _draw_mesh_validation_options(layout, self)
        row = layout.row(align=True)
        row.prop(self, "apply_transform")
        row.prop(self, "apply_modifiers")

    def format_export_results_detailed(self, export_status, directory):
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
                "  "
                + "\n  ".join([f"✗ {name}: {error}" for name, error in export_skipped])
            )
        if notes:
            parts.append("notes:")
            parts.append("  " + "\n  ".join(notes))

        return "\n".join(parts)

    def execute(self, context):
        # A script may set only filepath; the files then go beside it rather than into Blender's working directory.
        directory = self.directory or os.path.dirname(self.filepath)
        if not directory:
            report(
                self,
                "ERROR",
                "Choose the folder to export the collections to.",
                logger=_LOG,
            )
            return {"CANCELLED"}
        export_status = export_cyberpunk_collections_glb(
            context=context,
            filepath=directory,
            export_poses=self.export_poses,
            is_skinned=self.is_skinned,
            try_fix=self.try_fix,
            apply_transform=self.apply_transform,
            apply_modifiers=self.apply_modifiers,
            export_tracks=bool(self.export_tracks),
            root_motion=self.root_motion,
            only_visible=self.only_visible,
            mesh_validation_options=_mesh_validation_options(self),
        )

        report(
            self,
            "INFO",
            self.format_export_results_detailed(export_status, directory),
            logger=_LOG,
        )
        if not any(error is None for _, error, _warnings in export_status):
            report(
                self, "ERROR", "No collections were exported successfully.", logger=_LOG
            )
            return {"CANCELLED"}
        return {"FINISHED"}


def _animation_export_rig_index_updated(operator, context):
    populate = getattr(operator, "_populate_action_items", None)
    if populate is not None:
        populate(context)


class CP77RigExportItem(PropertyGroup):
    rig_path: StringProperty(name="Source Rig Path")
    display_name: StringProperty(name="Rig")


class CP77_UL_rig_export(UIList):
    bl_idname = "CP77_UL_rig_export"

    def draw_item(
        self,
        context,
        layout,
        data,
        item,
        icon,
        active_data,
        active_property,
        index,
        flt_flag=0,
    ):
        layout.label(text=item.display_name, icon="ARMATURE_DATA")


class CP77ActionExportItem(PropertyGroup):
    action_name: StringProperty(name="Action")
    export: BoolProperty(name="Export", default=True)


class CP77_UL_action_export(UIList):
    bl_idname = "CP77_UL_action_export"

    def draw_item(
        self,
        context,
        layout,
        data,
        item,
        icon,
        active_data,
        active_property,
        index,
        flt_flag=0,
    ):
        row = layout.row(align=True)
        row.prop(item, "export", text="")
        row.label(text=item.action_name, icon="ACTION")


class CP77_OT_set_action_export_selection(Operator):
    bl_idname = "cp77.set_action_export_selection"
    bl_label = "Set Action Export Selection"
    bl_options = {"INTERNAL"}

    selected: BoolProperty(default=True, options={"SKIP_SAVE"})

    def execute(self, context):
        space = getattr(context, "space_data", None)
        export_operator = getattr(space, "active_operator", None)
        if export_operator is None or getattr(export_operator, "bl_idname", "") not in {
            "EXPORT_SCENE_OT_cp77_glb",
            "export_scene.cp77_glb",
        }:
            return {"CANCELLED"}
        for item in export_operator.action_items:
            item.export = self.selected
        return {"FINISHED"}


class CP77GLBExport(Operator, ExportHelper):
    bl_idname = "export_scene.cp77_glb"
    bl_label = "Export for Cyberpunk"
    bl_options = {"REGISTER"}
    bl_description = "Export to GLB with optimized settings for use with Wolvenkit for Cyberpunk 2077"
    filename_ext = ".glb"

    filter_glob: StringProperty(default="*.glb", options={"HIDDEN"})

    filepath: StringProperty(subtype="FILE_PATH")

    limit_selected: BoolProperty(
        name="Limit to Selected Meshes",
        default=True,
        description="Only Export the Selected Meshes. This is probably the setting you want to use",
    )

    is_skinned: BoolProperty(
        name="Skinned Mesh",
        default=True,
        description="Ensure armatures and vert groups are exported.",
    )
    try_fix: BoolProperty(
        name="Try Fix",
        default=False,
        description="Enable selected repairs on temporary export copies",
    )

    advanced_validation: BoolProperty(
        name="Additional Validation",
        default=False,
        description="Enable optional UV, degeneracy, weight and unused-bone checks",
    )
    check_missing_uv: BoolProperty(name="Require Active UV Layer", default=True)
    check_degenerate_faces: BoolProperty(name="Check Degenerate Faces", default=True)
    check_degenerate_uvs: BoolProperty(name="Check Degenerate UVs", default=False)
    check_unweighted_vertices: BoolProperty(
        name="Check Unweighted Vertices", default=True
    )
    check_unused_bones: BoolProperty(
        name="Check Bones Without Vertex Groups",
        default=False,
        description="Check the armature against the union of vertex groups on exported submeshes",
    )
    fix_remove_unmatched_vertex_groups: BoolProperty(
        name="Remove Vertex Groups Without Bones",
        default=True,
    )
    fix_apply_autofitter_shape_keys: BoolProperty(
        name="Bake Autofitter Shape Keys",
        default=False,
        description="Bake Autofitter keys at their current values into temporary export copies",
    )
    fix_add_missing_uv: BoolProperty(name="Add Missing UV Layer", default=True)
    fix_dissolve_degenerate_faces: BoolProperty(
        name="Dissolve Degenerate Faces/Vertices",
        default=True,
    )
    fix_dissolve_degenerate_uvs: BoolProperty(
        name="Dissolve UV-Degenerate Faces/Vertices",
        default=False,
    )
    fix_assign_unweighted_vertices: BoolProperty(
        name="Assign Unweighted Vertices to Root",
        default=False,
    )
    fix_remove_unused_bones: BoolProperty(
        name="Remove Bones Without Vertex Groups",
        default=False,
        description="Create a temporary armature, remove unmatched bones and reparent retained descendants",
    )
    fix_limit_influences: BoolProperty(
        name="Limit Bone Influences",
        default=False,
        description="Keep each vertex's 8 strongest bone influences on the temporary export copy and normalize "
        "them. This changes how those vertices deform",
    )

    export_poses: BoolProperty(
        name="Animations",
        default=False,
        description="Use this option if you are exporting anims to be imported into wkit as .anim",
    )

    export_visible: BoolProperty(
        name="Export Visible Meshes",
        default=False,
        description="Use this option to export all visible objects. Only use this if you know why you're using this",
    )

    apply_transform: BoolProperty(
        name="Apply Transform",
        default=True,
        description="Applies the transform of the objects. Disable this if you don't care about the location/rotation/scale of the objects",
    )

    apply_modifiers: BoolProperty(
        name="Apply Modifiers",
        default=True,
        description="Applies the modifiers of the objects. Disable this if you have shapekeys.",
    )
    root_motion: EnumProperty(
        name="Root Motion",
        items=ROOT_MOTION_EXPORT_ITEMS,
        default="CLIP",
    )
    export_tracks: BoolProperty(
        name="Synchronize Float Tracks",
        default=True,
        description="Update imported trackKeys from live Float F-Curves; disable to preserve the source payload unchanged",
    )
    rig_items: CollectionProperty(type=CP77RigExportItem)
    rig_index: IntProperty(
        default=0,
        options={"SKIP_SAVE"},
        update=_animation_export_rig_index_updated,
    )
    rig_list_error: StringProperty(default="", options={"HIDDEN", "SKIP_SAVE"})
    action_items: CollectionProperty(type=CP77ActionExportItem)
    action_index: IntProperty(default=0, options={"SKIP_SAVE"})
    action_list_error: StringProperty(default="", options={"HIDDEN", "SKIP_SAVE"})
    action_list_rig_path: StringProperty(default="", options={"HIDDEN", "SKIP_SAVE"})

    def _requires_source_rig_selection(self):
        return len(self.rig_items) > 1

    def _selected_rig_path(self):
        if not self._requires_source_rig_selection():
            return ""
        if self.rig_index < 0 or self.rig_index >= len(self.rig_items):
            return ""
        return str(self.rig_items[self.rig_index].rig_path or "")

    def _populate_rig_items(self, context):
        self.rig_items.clear()
        self.rig_list_error = ""
        armatures = _selected_export_armatures(context)
        if len(armatures) != 1:
            self.rig_list_error = "Select exactly one MetaRig to list its source rigs."
            return
        entries = animation_rig_export_entries(armatures[0])
        for path, display_name in entries:
            item = self.rig_items.add()
            item.rig_path = path
            item.display_name = display_name
        self.rig_index = (
            min(max(int(self.rig_index), 0), len(self.rig_items) - 1)
            if self.rig_items
            else 0
        )

    def _populate_action_items(self, context):
        self.action_items.clear()
        self.action_list_error = ""
        self.action_list_rig_path = ""
        armatures = _selected_export_armatures(context)
        if len(armatures) != 1:
            self.action_list_error = (
                "Select exactly one MetaRig to list compatible actions."
            )
            return
        source_rig_path = self._selected_rig_path()
        if self.rig_list_error:
            self.action_list_error = self.rig_list_error
            return
        if self._requires_source_rig_selection() and not source_rig_path:
            self.action_list_error = "Select one source rig for animation export."
            return
        self.action_list_rig_path = source_rig_path
        try:
            actions = compatible_actions_for_export(
                armatures[0], source_rig_path=source_rig_path
            )
        except Exception as error:
            log_once(
                _LOG,
                "WARNING",
                ("actions", type(error).__name__),
                "Compatible actions could not be listed: %s",
                error,
                exc_info=True,
            )
            self.action_list_error = str(error)
            return
        for action in actions:
            item = self.action_items.add()
            item.action_name = action.name
            item.export = True
        self.action_index = 0

    def invoke(self, context, event):
        self._populate_rig_items(context)
        self._populate_action_items(context)
        self.check(context)
        return ExportHelper.invoke(self, context, event)

    def check(self, context):
        """Keep the file selector synchronized with the selected export format"""
        meshes = (
            resolve_mesh_export_scope(
                context,
                limit_selected=getattr(self, "limit_selected", True),
                export_visible=getattr(self, "export_visible", False),
                excluded_objects=collect_excluded_objects(),
            ).meshes
            if not self.export_poses
            else ()
        )
        morph_export = mesh_glb_path("export.glb", meshes).endswith(".morphtarget.glb")
        extension = (
            ".anims.glb"
            if self.export_poses
            else ".morphtarget.glb"
            if morph_export
            else ".glb"
        )
        pattern = "*" + extension
        was_animation = self.filter_glob == "*.anims.glb"
        was_morph = self.filter_glob == "*.morphtarget.glb"
        changed = self.filter_glob != pattern
        self.filename_ext = extension
        self.filter_glob = pattern
        if self.export_poses:
            if self.filepath:
                if was_morph and self.filepath.casefold().endswith(".morphtarget.glb"):
                    self.filepath = self.filepath[: -len(".morphtarget.glb")] + ".glb"
                filepath = animation_glb_path(self.filepath)
                changed = changed or filepath != self.filepath
                self.filepath = filepath
            return changed
        if was_animation and self.filepath.lower().endswith(".anims.glb"):
            self.filepath = self.filepath[:-10] + ".glb"
            changed = True
        if (
            was_morph
            and not morph_export
            and self.filepath.casefold().endswith(".morphtarget.glb")
        ):
            self.filepath = self.filepath[: -len(".morphtarget.glb")] + ".glb"
            changed = True
        if morph_export and self.filepath:
            filepath = mesh_glb_path(self.filepath, meshes)
            changed = changed or filepath != self.filepath
            self.filepath = filepath
        if morph_export:
            return changed
        return ExportHelper.check(self, context) or changed

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        box.label(text="Export Options")
        row = box.row(align=True)
        row.prop(self, "export_poses")
        if not self.export_poses:
            row = box.row(align=True)
            row.prop(self, "is_skinned")
            _draw_mesh_validation_options(layout, self)
            row = box.row(align=True)
            row.prop(self, "limit_selected")
            if not self.limit_selected:
                row = box.row(align=True)
                row.prop(self, "export_visible")
            row = layout.row(align=True)
            row.prop(self, "apply_transform")
            row.prop(self, "apply_modifiers")
        else:
            direct = box.box()
            direct.prop(self, "export_tracks")
            direct.prop(self, "root_motion")
            if self._requires_source_rig_selection():
                direct.label(text="Source Rig", icon="ARMATURE_DATA")
                rig_box = direct.box()
                if self.rig_list_error:
                    rig_box.label(text=self.rig_list_error, icon="ERROR")
                else:
                    rig_box.template_list(
                        CP77_UL_rig_export.bl_idname,
                        "",
                        self,
                        "rig_items",
                        self,
                        "rig_index",
                        rows=min(8, max(2, len(self.rig_items))),
                    )
            direct.label(text="Actions to Export", icon="EXPORT")
            action_box = direct.box()
            header = action_box.row(align=True)
            select_all = header.operator(
                CP77_OT_set_action_export_selection.bl_idname, text="All"
            )
            select_all.selected = True
            select_none = header.operator(
                CP77_OT_set_action_export_selection.bl_idname, text="None"
            )
            select_none.selected = False
            if self.action_list_error:
                action_box.label(text=self.action_list_error, icon="ERROR")
            elif self.action_items:
                action_box.template_list(
                    CP77_UL_action_export.bl_idname,
                    "",
                    self,
                    "action_items",
                    self,
                    "action_index",
                    rows=min(10, max(4, len(self.action_items))),
                )
            else:
                action_box.label(text="No compatible CP77 actions found.", icon="INFO")

    def execute(self, context):
        selected_action_names = None
        if self.export_poses:
            selected_rig_path = self._selected_rig_path()
            if self.action_list_rig_path != selected_rig_path or not self.action_items and not self.action_list_error:
                self._populate_action_items(context)
            if self.action_list_error:
                report(self, "ERROR", self.action_list_error, logger=_LOG)
                return {"CANCELLED"}
            selected_action_names = [
                item.action_name for item in self.action_items if item.export
            ]
            if not selected_action_names:
                report(
                    self, "ERROR", "Select at least one action to export.", logger=_LOG
                )
                return {"CANCELLED"}

        # Mesh and animation export share the service the collection export uses, with the same checks.
        return execute_operation(
            self,
            "Export",
            export_cyberpunk_glb,
            context=context,
            filepath=self.filepath,
            export_poses=self.export_poses,
            export_visible=self.export_visible,
            limit_selected=self.limit_selected,
            is_skinned=self.is_skinned,
            try_fix=self.try_fix,
            apply_transform=self.apply_transform,
            apply_modifiers=self.apply_modifiers,
            export_tracks=bool(self.export_tracks),
            root_motion=self.root_motion,
            selected_action_names=selected_action_names,
            source_rig_path=self._selected_rig_path() if self.export_poses else "",
            mesh_validation_options=_mesh_validation_options(self),
        )


class CP77HairProfileExport(Operator, ExportHelper):
    bl_idname = "export_scene.hp"
    bl_label = "Export Hair Profile"
    bl_description = "Generates a new .hp.json in your mod project folder which can be imported in WolvenKit"
    bl_parent_id = "CP77_PT_MaterialTools"

    filepath: StringProperty(subtype="FILE_PATH")
    filename_ext = ".hp.json"
    filter_glob: StringProperty(
        default="*.hp.json",
        options={"HIDDEN"},
    )

    def execute(self, context):
        if _active_material(self, context) is None:
            return {"CANCELLED"}
        return execute_operation(
            self, "Hair profile export", cp77_hp_export, context, self.filepath
        )


class CP77MaterialInstanceExport(Operator, ExportHelper):
    """Export the active material properties to a WolvenKit JSON file"""

    bl_idname = "export_scene.mi"
    bl_label = "Export Material"
    bl_description = "Export selected material as a Material Instance (.mi) json file which can be converted in WolvenKit"

    filepath: StringProperty(name="File Path", subtype="FILE_PATH")

    filename_ext = ".json"

    @classmethod
    def poll(cls, context):
        active_object = getattr(context, "active_object", None)
        return (
            active_object is not None
            and getattr(active_object, "active_material", None) is not None
        )

    def invoke(self, context, event):
        active_material = _active_material(self, context)
        if active_material is None:
            return {"CANCELLED"}
        if str(active_material.get("MultilayerMask", "None")) == "None":
            report(
                self,
                "ERROR",
                "Only Multilayered-based materials are currently supported.",
                logger=_LOG,
            )
            return {"CANCELLED"}

        default_name = active_material.name
        invalid_chars = r'[<>:"/\\|?*\n\t\r\x00-\x1F]'
        safe_string = re.sub(invalid_chars, "_", default_name)
        safe_string = safe_string.replace(" ", "_")
        safe_string = safe_string.lower()

        projpath = str(active_material.get("cp77_project_path", ""))
        if projpath == "":
            self.filepath = f"{safe_string}.mi.json"
            context.window_manager.fileselect_add(self)
            return {"RUNNING_MODAL"}

        basepath = projpath + "\\"

        self.filepath = basepath + f"{safe_string}.mi.json"
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        return execute_operation(
            self,
            "Material export",
            cp77_materialinstance_export,
            context,
            self.filepath,
        )


class CP77MlSetupExport(Operator):
    bl_idname = "export_scene.mlsetup"
    bl_label = "Export MLSetup"
    # A successful export points the material at the written setup.
    bl_options = {"REGISTER", "UNDO"}
    bl_parent_id = "CP77_PT_MaterialTools"
    bl_description = "Export selected material to a mlsetup json file which can be converted in WolvenKit"

    filepath: StringProperty(subtype="FILE_PATH")

    filename_ext = ".json"

    def draw(self, context):
        props = context.scene.cp77_panel_props
        layout = self.layout
        layout.prop(props, "write_mltemplate")

    def invoke(self, context, event):
        active_material = _active_material(self, context)
        if active_material is None:
            return {"CANCELLED"}
        mlsetup_path = active_material.get("MLSetup")
        if mlsetup_path is None:
            report(
                self,
                "ERROR",
                "Active material does not contain MLSetup path",
                logger=_LOG,
            )
            return {"CANCELLED"}

        # The material's paths come from imported data: the default stays inside the project, and folders are only
        # created once the export runs. A created material has no setup yet, so it starts from its own name.
        self.filepath = default_project_output(
            active_material.get("cp77_project_path", ""),
            str(mlsetup_path) or f"{active_material.name}.mlsetup",
            ".json",
        )
        _LOG.debug("MLSetup default path: %s", self.filepath)
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        write_mltemplate = context.scene.cp77_panel_props.write_mltemplate
        return execute_operation(
            self,
            "MLSetup export",
            cp77_mlsetup_export,
            context,
            self.filepath,
            write_mltemplate,
        )


class CP77MlMaskExport(Operator, ExportHelper):
    bl_idname = "export_scene.mlmask"
    bl_label = "Export MLMask"
    # A successful export points the material at the written mask set.
    bl_options = {"REGISTER", "UNDO"}
    bl_description = "Export mask images from selected material and create a masklist file which can be imported in WolvenKit"

    filepath: StringProperty(subtype="FILE_PATH")

    filename_ext = ".masklist"

    export_format: EnumProperty(
        name="File Format",
        description="Choose the format for exported images",
        items=[
            ("PNG", "PNG", "Save as Portable Network Graphics"),
            ("JPEG", "JPEG", "Save as Joint Photographic Experts Group"),
            ("TARGA", "Targa", "Save as Targa graphic"),
            ("TIFF", "TIFF", "Save as Tagged Image File Format"),
        ],
        default="PNG",
    )

    def invoke(self, context, event):
        active_material = _active_material(self, context)
        if active_material is None:
            return {"CANCELLED"}

        mlmask_path = str(active_material.get("MultilayerMask", "") or "")
        if not mlmask_path:
            report(
                self,
                "ERROR",
                "Active material does not contain MLMask path",
                logger=_LOG,
            )
            return {"CANCELLED"}

        masklist_path = replace_depot_suffix(mlmask_path, ".mlmask", ".masklist")
        self.filepath = default_project_output(
            active_material.get("cp77_project_path", ""), masklist_path, ""
        )
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        return execute_operation(
            self,
            "MLMask export",
            cp77_mlmask_export,
            context,
            self.filepath,
            self.export_format,
        )


def menu_func_export(self, context):
    layout = self.layout
    icon = get_icon("WKIT")
    layout.operator(CP77GLBExport.bl_idname, text="Cyberpunk GLB", icon_value=icon)
    layout.operator(
        CP77CollectionExport.bl_idname, text="Cyberpunk Collections", icon_value=icon
    )
    layout.operator(
        CP77StreamingSectorExport.bl_idname,
        text="Cyberpunk StreamingSector",
        icon_value=icon,
    )
    layout.operator(
        CP77RigJSONExport.bl_idname, text="Cyberpunk Rig to JSON", icon_value=icon
    )


registration_classes = (
    get_classes(sys.modules[__name__]) + ANIMGRAPH_EXPORT_OPERATOR_CLASSES
)

_LEDGER = RegistrationLedger("exporters")


def _remove_export_menu():
    try:
        TOPBAR_MT_file_export.remove(menu_func_export)
    except Exception:
        _LOG.debug(
            "File export menu entry was not present during cleanup", exc_info=True
        )


def register_exporters():
    if _LEDGER.active:
        return
    try:
        _LEDGER.register_classes(registration_classes)
        _remove_export_menu()
        TOPBAR_MT_file_export.append(menu_func_export)
        _LEDGER.add_cleanup("export menu", _remove_export_menu)
    except Exception:
        _LEDGER.cleanup()
        raise


def unregister_exporters():
    _LEDGER.cleanup_or_raise()
