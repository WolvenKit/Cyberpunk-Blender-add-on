import re
import string
from pathlib import Path

import bpy.utils.previews
from bpy.props import (BoolProperty, CollectionProperty, IntProperty, StringProperty)
from bpy.types import (Operator, Panel, PropertyGroup, TOPBAR_MT_file_export, UIList)
from bpy_extras.io_utils import ExportHelper

from .collision_export import *
from .direct_anim_export import compatible_actions_for_export, export_anims_glb_direct
from .glb_export import export_cyberpunk_collections_glb, export_cyberpunk_glb
from .hp_export import *
from .mesh_validation import MeshValidationOptions
from .mi_export import *
from .mlmask_export import *
from .mlsetup_export import *
from .phys_export import *
from .sectors_export import *
from .write_rig import export_armature_to_rig_json
from ..cyber_props import *
from ..icons.cp77_icons import *


def _selected_export_armatures(context):
    view_layer = getattr(context, "view_layer", None)
    objects = getattr(view_layer, "objects", ()) if view_layer is not None else ()
    selected = [
        obj for obj in objects
        if getattr(obj, "type", None) == 'ARMATURE' and obj.select_get()
    ]
    if selected:
        return selected
    return [
        obj for obj in getattr(bpy.context, "selected_objects", ())
        if getattr(obj, "type", None) == 'ARMATURE'
    ]


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
    )


def _draw_mesh_validation_options(layout, operator):
    validation_box = layout.box()
    validation_box.label(text="Mesh Validation", icon='CHECKMARK')
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
    fixes.label(text="Apply Fixes", icon='MODIFIER')
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


class CP77RigJSONExport(Operator, ExportHelper):
    bl_idname = "export_scene.cp77_rig_export"
    bl_label = "Export Rig Updates to JSON for Cyberpunk"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Export changes to Rigs exported from JSON back to JSON"
    filename_ext = ".rig.json"
    filter_glob: StringProperty(default="*.rig.json", options={'HIDDEN'})

    def draw(self, context):
        props = context.scene.cp77_panel_props
        layout = self.layout

    def execute(self, context):
        armature_object = context.view_layer.objects.active
        if armature_object is None or armature_object.type != 'ARMATURE':
            self.report({'ERROR'}, "No active armature object found in the scene.")
            return {'CANCELLED'}

        try:
            summary = export_armature_to_rig_json(
                    armature_object,
                    self.filepath,
                    pose_target='IMPORTED',
                    )
        except Exception as error:
            self.report({'ERROR'}, f"Rig export failed: {error}")
            return {'CANCELLED'}

        message = f"Exported {summary['bone_count']} bones to {Path(summary['filepath']).name}."
        if summary.get('topology_changed'):
            message += " Topology changed; retained non-pose metadata may require review."
        if summary.get('nonuniform_scaled_edit_count'):
            message += " Edited bones under nonuniform source scale were reconstructed approximately."
        self.report({'INFO'}, message)
        return {'FINISHED'}

    def check(self, context):
        # Ensure the file path ends with the correct extension
        if not self.filepath.endswith(self.filename_ext):
            self.filepath += self.filename_ext
        return True


class CP77StreamingSectorExport(Operator, ExportHelper):
    bl_idname = "export_scene.cp77_sector"
    bl_label = "Export Sector Updates for Cyberpunk"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Export changes to Sectors back to project"
    filename_ext = ".cpmodproj"
    filter_glob: StringProperty(default="*.cpmodproj", options={'HIDDEN'})

    def draw(self, context):
        props = context.scene.cp77_panel_props
        layout = self.layout
        layout.prop(props, "axl_yaml")

    def execute(self, context):
        use_yaml = context.scene.cp77_panel_props.axl_yaml
        exportSectors(self.filepath, use_yaml)
        return {'FINISHED'}


class CP77CollectionExport(Operator, ExportHelper):
    bl_idname = "export_scene.cp77_collection_glb"
    bl_label = "Export for Cyberpunk"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Export to GLB with optimized settings for use with Wolvenkit for Cyberpunk 2077"
    filename_ext = ".glb"

    # For folder export
    directory: StringProperty(  # pyright: ignore[reportInvalidTypeForm]
            name="Export Folder",
            description="Folder where GLB files will be saved",
            subtype='DIR_PATH',
            default="",
            )

    only_visible: BoolProperty(  # pyright: ignore[reportInvalidTypeForm]
            name="Only Visible",
            default=False,
            description="Check this to export only collections that are currently visible in view port"
            )

    is_skinned: BoolProperty(  # pyright: ignore[reportInvalidTypeForm]
            name="Skinned Mesh",
            default=True,
            description="Ensure armatures and vert groups are exported."
            )
    try_fix: BoolProperty(  # pyright: ignore[reportInvalidTypeForm]
            name="Try Fix",
            default=False,
            description="Enable selected repairs on temporary export copies"
            )

    advanced_validation: BoolProperty(
            name="Additional Validation",
            default=False,
            description="Enable optional UV, degeneracy, weight and unused-bone checks",
            )
    check_missing_uv: BoolProperty(name="Require Active UV Layer", default=True)
    check_degenerate_faces: BoolProperty(name="Check Degenerate Faces", default=True)
    check_degenerate_uvs: BoolProperty(name="Check Degenerate UVs", default=False)
    check_unweighted_vertices: BoolProperty(name="Check Unweighted Vertices", default=True)
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

    export_poses: BoolProperty(  # pyright: ignore[reportInvalidTypeForm]
            name="Animations",
            default=False,
            description="Use this option if you are exporting anims to be imported into wkit as .anim"
            )

    apply_transform: BoolProperty(  # pyright: ignore[reportInvalidTypeForm]
            name="Apply Transform",
            default=True,
            description="Applies the transform of the objects. Disable this if you don't care about the location/rotation/scale of the objects"
            )

    apply_modifiers: BoolProperty(  # pyright: ignore[reportInvalidTypeForm]
            name="Apply Modifiers",
            default=True,
            description="Applies the modifiers of the objects. Disable this if you have shapekeys."
            )
    export_tracks: BoolProperty(  # pyright: ignore[reportInvalidTypeForm]
            name="Export Float Tracks",
            default=True,
            description="Transfer Float F-Curves Back to Custom Props for Wolvenkit Import"
            )

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        box.label(text='Export Options')
        row = box.row(align=True)
        row.prop(self, "only_visible")
        row = box.row(align=True)
        row.prop(self, "export_poses")
        if self.export_poses:
            row.label(text="Float tracks are included for every exported action.", icon='FCURVE')
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

        for name, error in export_status:
            if error:
                export_skipped.append((name, error))
            else:
                exported.append(name)

        # Build parts
        parts = []

        # Success section
        parts.append(f"exported to {directory}:")
        if exported:
            parts.append("  " + "\n  ".join([f"✓ {name}" for name in exported]))
        else:
            parts.append("  (no successful exports)")

        # Failed/skipped section (only if needed)
        if export_skipped:
            parts.append("export skipped or failed:")
            parts.append("  " + "\n  ".join([f"✗ {name}: {error}" for name, error in export_skipped]))

        return "\n".join(parts)

    def execute(self, context):
        export_status = export_cyberpunk_collections_glb(
                context=context,
                filepath=self.directory,
                export_poses=self.export_poses,
                is_skinned=self.is_skinned,
                try_fix=self.try_fix,
                apply_transform=self.apply_transform,
                apply_modifiers=self.apply_modifiers,
                export_tracks=True,
                only_visible=self.only_visible,
                mesh_validation_options=_mesh_validation_options(self),
                )

        self.report({'INFO'}, self.format_export_results_detailed(export_status, self.filepath))
        return {'FINISHED'}


class CP77ActionExportItem(PropertyGroup):
    action_name: StringProperty(name="Action")
    export: BoolProperty(name="Export", default=True)


class CP77_UL_action_export(UIList):
    bl_idname = "CP77_UL_action_export"

    def draw_item(
            self, context, layout, data, item, icon, active_data, active_property, index,
            flt_flag=0,
            ):
        row = layout.row(align=True)
        row.prop(item, "export", text="")
        row.label(text=item.action_name, icon='ACTION')


class CP77_OT_set_action_export_selection(Operator):
    bl_idname = "cp77.set_action_export_selection"
    bl_label = "Set Action Export Selection"
    bl_options = {'INTERNAL'}

    selected: BoolProperty(default=True, options={'SKIP_SAVE'})

    def execute(self, context):
        space = getattr(context, "space_data", None)
        export_operator = getattr(space, "active_operator", None)
        if (
                export_operator is None
                or getattr(export_operator, "bl_idname", "") not in {
                    "EXPORT_SCENE_OT_cp77_glb",
                    "export_scene.cp77_glb",
                    }
        ):
            return {'CANCELLED'}
        for item in export_operator.action_items:
            item.export = self.selected
        return {'FINISHED'}


class CP77GLBExport(Operator, ExportHelper):
    bl_idname = "export_scene.cp77_glb"
    bl_label = "Export for Cyberpunk"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Export to GLB with optimized settings for use with Wolvenkit for Cyberpunk 2077"
    filename_ext = ".glb"

    filter_glob: StringProperty(default="*.glb", options={'HIDDEN'})

    filepath: StringProperty(subtype="FILE_PATH")

    limit_selected: BoolProperty(
            name="Limit to Selected Meshes",
            default=True,
            description="Only Export the Selected Meshes. This is probably the setting you want to use"
            )

    is_skinned: BoolProperty(
            name="Skinned Mesh",
            default=True,
            description="Ensure armatures and vert groups are exported."
            )
    try_fix: BoolProperty(
            name="Try Fix",
            default=False,
            description="Enable selected repairs on temporary export copies"
            )

    advanced_validation: BoolProperty(
            name="Additional Validation",
            default=False,
            description="Enable optional UV, degeneracy, weight and unused-bone checks",
            )
    check_missing_uv: BoolProperty(name="Require Active UV Layer", default=True)
    check_degenerate_faces: BoolProperty(name="Check Degenerate Faces", default=True)
    check_degenerate_uvs: BoolProperty(name="Check Degenerate UVs", default=False)
    check_unweighted_vertices: BoolProperty(name="Check Unweighted Vertices", default=True)
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

    export_poses: BoolProperty(
            name="Animations",
            default=False,
            description="Use this option if you are exporting anims to be imported into wkit as .anim"
            )

    export_visible: BoolProperty(
            name="Export Visible Meshes",
            default=False,
            description="Use this option to export all visible objects. Only use this if you know why you're using this"
            )

    apply_transform: BoolProperty(
            name="Apply Transform",
            default=True,
            description="Applies the transform of the objects. Disable this if you don't care about the location/rotation/scale of the objects"
            )

    apply_modifiers: BoolProperty(
            name="Apply Modifiers",
            default=True,
            description="Applies the modifiers of the objects. Disable this if you have shapekeys."
            )
    export_tracks: BoolProperty(
            name="Export Float Tracks",
            default=True,
            description="Transfer Float F-Curves Back to Custom Props for Wolvenkit Import"
            )
    action_items: CollectionProperty(type=CP77ActionExportItem)
    action_index: IntProperty(default=0, options={'SKIP_SAVE'})
    action_list_error: StringProperty(default="", options={'HIDDEN', 'SKIP_SAVE'})

    def _populate_action_items(self, context):
        self.action_items.clear()
        self.action_list_error = ""
        armatures = _selected_export_armatures(context)
        if len(armatures) != 1:
            self.action_list_error = "Select exactly one MetaRig to list compatible actions."
            return
        try:
            actions = compatible_actions_for_export(armatures[0])
        except Exception as error:
            self.action_list_error = str(error)
            return
        for action in actions:
            item = self.action_items.add()
            item.action_name = action.name
            item.export = True
        self.action_index = 0

    def invoke(self, context, event):
        self._populate_action_items(context)
        return ExportHelper.invoke(self, context, event)

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        box.label(text='Export Options')
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
            direct.label(text="Actions to Export", icon='EXPORT')
            action_box = direct.box()
            selected_count = sum(1 for item in self.action_items if item.export)
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
                action_box.label(text=self.action_list_error, icon='ERROR')
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
                action_box.label(text="No compatible CP77 actions found.", icon='INFO')

    def execute(self, context):
        selected_action_names = None
        if self.export_poses:
            if not self.action_items and not self.action_list_error:
                self._populate_action_items(context)
            if self.action_list_error:
                self.report({'ERROR'}, self.action_list_error)
                return {'CANCELLED'}
            selected_action_names = [
                item.action_name for item in self.action_items if item.export
                ]
            if not selected_action_names:
                self.report({'ERROR'}, "Select at least one action to export.")
                return {'CANCELLED'}

        try:
            if self.export_poses:
                armatures = _selected_export_armatures(context)
                if len(armatures) != 1:
                    raise ValueError("Direct animation export requires exactly one selected MetaRig.")
                summary = export_anims_glb_direct(
                    self.filepath,
                    armatures[0],
                    export_tracks=True,
                    selected_action_names=selected_action_names,
                )
                self.report(
                    {'INFO'},
                    f"Directly exported {summary['animation_count']} CP77 actions with float tracks.",
                )
                return {'FINISHED'}

            export_cyberpunk_glb(
                context=context,
                filepath=self.filepath,
                export_poses=False,
                export_visible=self.export_visible,
                limit_selected=self.limit_selected,
                is_skinned=self.is_skinned,
                try_fix=self.try_fix,
                apply_transform=self.apply_transform,
                apply_modifiers=self.apply_modifiers,
                mesh_validation_options=_mesh_validation_options(self),
            )
        except Exception as error:
            self.report({'ERROR'}, f"Export failed: {error}")
            return {'CANCELLED'}
        return {'FINISHED'}


class CP77HairProfileExport(Operator):
    bl_idname = "export_scene.hp"
    bl_label = "Export Hair Profile"
    bl_description = "Generates a new .hp.json in your mod project folder which can be imported in WolvenKit"
    bl_parent_id = "CP77_PT_MaterialTools"

    filepath: StringProperty(subtype="FILE_PATH")

    def execute(self, context):
        active_object = context.active_object
        if not active_object:
            self.report({'ERROR'}, "No active object")
            return {'CANCELLED'}
        active_material = active_object.active_material
        if not active_material:
            self.report({'ERROR'}, "Active object has no material.")
            return {'CANCELLED'}

        cp77_hp_export(self.filepath)
        return {"FINISHED"}


class CP77MaterialInstanceExport(Operator, ExportHelper):
    """Export the active material properties to a WolvenKit JSON file"""
    bl_idname = "export_scene.mi"
    bl_label = "Export Material"
    bl_description = "Export selected material as a Material Instance (.mi) json file which can be converted in WolvenKit"

    filepath: StringProperty(name="File Path", subtype='FILE_PATH')

    filename_ext = ".json"

    # filter_glob: StringProperty(default="*.json",options={'HIDDEN'})

    def draw(self, context):
        layout = self.layout
        active_object = context.active_object
        active_material = active_object.active_material

        box = layout.box()
        box.label(text="Material Data", icon='NODE_MATERIAL')

        # Create a column and disable it to make everything inside read-only
        col = box.column()
        col.enabled = False

        # Helper to display custom props if they exist
        def draw_mat_prop(prop_name, label):
            if prop_name in active_material:
                col.prop(active_material, f'["{prop_name}"]', text=label)
            else:
                col.label(text=f"{label}: (Not Set)")

        draw_mat_prop('MLSetup', "MLSetup")
        draw_mat_prop('MultilayerMask', "MLMask")
        draw_mat_prop('GlobalNormal', "Normal Map")

    def invoke(self, context, event):
        active_object = context.active_object
        if not active_object:
            self.report({'ERROR'}, "No active object")
            return {'CANCELLED'}
        active_material = active_object.active_material
        if not active_material:
            self.report({'ERROR'}, "Active object has no material.")
            return {'CANCELLED'}
        if str(active_material['MultilayerMask']) == "None":
            self.report({'ERROR'}, "Only Multilayered-based materials are currently supported.")
            return {'CANCELLED'}

        default_name = active_material.name if active_material else "default"
        # JATO: probably should do some safety-checks on the name cause bpy material names are wild-west
        # this is just something I pulled from web search results. maybe better not to import re/string idk
        invalid_chars = re.escape(string.punctuation + string.whitespace)
        invalid_chars = r'[<>:"/\\|?*\n\t\r\x00-\x1F]'
        safe_string = re.sub(invalid_chars, '_', default_name)
        safe_string = safe_string.replace(' ', '_')
        safe_string = safe_string.lower()

        projpath = active_material['ProjPath']
        if projpath == "":
            self.filepath = f"{safe_string}.mi.json"
            context.window_manager.fileselect_add(self)
            return {'RUNNING_MODAL'}

        basepath = str(active_material['ProjPath']) + "\\"

        self.filepath = basepath + f"{safe_string}.mi.json"
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        cp77_materialinstance_export(self, context, self.filepath)
        return {'FINISHED'}


class CP77MlSetupExport(Operator):
    bl_idname = "export_scene.mlsetup"
    bl_label = "Export MLSetup"
    bl_parent_id = "CP77_PT_MaterialTools"
    bl_description = "Export selected material to a mlsetup json file which can be converted in WolvenKit"

    filepath: StringProperty(subtype="FILE_PATH")

    filename_ext = ".json"

    def draw(self, context):
        props = context.scene.cp77_panel_props
        layout = self.layout
        layout.prop(props, "write_mltemplate")

    def invoke(self, context, event):
        active_object = context.active_object
        if not active_object:
            self.report({'ERROR'}, "No active object")
            return {'CANCELLED'}
        active_material = active_object.active_material
        if not active_material:
            self.report({'ERROR'}, "Active object has no material.")
            return {'CANCELLED'}
        mlsetup_path = str(active_material['MLSetup'])
        if mlsetup_path == "":
            self.report({'ERROR'}, "Active material does not contain MLSetup path")
            return {'CANCELLED'}

        projpath = active_material['ProjPath']
        if projpath == "":
            self.filepath = f"{Path(mlsetup_path).name}.json"
            context.window_manager.fileselect_add(self)
            print("mlsetup filepath: ", self.filepath)
            return {'RUNNING_MODAL'}

        self.filepath = f"{projpath}\\{mlsetup_path}.json"
        if not os.path.exists(Path(self.filepath).parent):
            os.makedirs(Path(self.filepath).parent)

        print("mlsetup filepath: ", self.filepath)

        context.window_manager.fileselect_add(self)

        return {'RUNNING_MODAL'}

    def execute(self, context):
        write_mltemplate = context.scene.cp77_panel_props.write_mltemplate
        cp77_mlsetup_export(self, context, self.filepath, write_mltemplate)

        before, mid, after = self.filepath.partition('source\\raw\\'.replace('\\', os.sep))
        if after != '':
            active_material = bpy.context.active_object.active_material
            active_material['MLSetup'] = after[:-5]  # this trims .json from name
        else:
            print("WolvenKit project path not detected. MLSetup path was not updated")

        return {"FINISHED"}


class CP77MlMaskExport(Operator, ExportHelper):
    bl_idname = "export_scene.mlmask"
    bl_label = "Export MLMask"
    bl_description = "Export mask images from selected material and create a masklist file which can be imported in WolvenKit"

    filepath: StringProperty(subtype="FILE_PATH")

    filename_ext = ".masklist"

    # filter_glob: StringProperty(default="*.masklist",options={'HIDDEN'})

    export_format: EnumProperty(
            name="File Format",
            description="Choose the format for exported images",
            items=[
                ('PNG', "PNG", "Save as Portable Network Graphics"),
                ('JPEG', "JPEG", "Save as Joint Photographic Experts Group"),
                ('TARGA', "Targa", "Save as Targa graphic"),
                ('TIFF', "TIFF", "Save as Tagged Image File Format"),
                ],
            default='PNG'
            )

    def invoke(self, context, event):
        active_object = context.active_object
        if not active_object:
            self.report({'ERROR'}, "No active object")
            return {'CANCELLED'}
        active_material = active_object.active_material
        if not active_material:
            self.report({'ERROR'}, "Active object has no material.")
            return {'CANCELLED'}

        mlmask_path = str(active_material['MultilayerMask'])
        if mlmask_path == "":
            self.report({'ERROR'}, "Active material does not contain MLMask path")
            return {'CANCELLED'}

        # JATO: need to convert from .mlmask to .masklist
        masklist_path = (mlmask_path.split(".")[0]) + ".masklist"

        projpath = str(active_material['ProjPath'])
        if projpath != "":
            self.filepath = projpath + "\\" + masklist_path
            if not os.path.exists(Path(self.filepath).parent):
                os.makedirs(Path(self.filepath).parent)
        else:
            self.filepath = Path(masklist_path).name

        context.window_manager.fileselect_add(self)

        return {'RUNNING_MODAL'}

    def execute(self, context):
        cp77_mlmask_export(self, context, self.filepath, self.export_format)

        before, mid, after = self.filepath.partition('source\\raw\\'.replace('\\', os.sep))
        if after != '':
            active_material = bpy.context.active_object.active_material
            active_material['MultilayerMask'] = after[:-8] + "mlmask"
        else:
            print("WolvenKit project path not detected. MLSetup path was not updated")

        return {'FINISHED'}


class CP77CollisionExport(Operator):
    bl_idname = "export_scene.collisions"
    bl_label = "Export Collisions to .JSON"
    bl_parent_id = "CP77_PT_collisions"
    bl_description = "Export project collisions to .phys.json"

    filepath: StringProperty(subtype="FILE_PATH")

    def draw(self, context):
        props = context.scene.cp77_panel_props
        layout = self.layout
        layout.prop(props, "collision_type")

    def execute(self, context):
        collision_type = context.scene.cp77_panel_props.collision_type
        cp77_collision_export(self.filepath, collision_type)
        return {"FINISHED"}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}


def menu_func_export(self, context):
    self.layout.operator(CP77GLBExport.bl_idname, text="Cyberpunk GLB", icon_value=get_icon("WKIT"))
    self.layout.operator(CP77CollectionExport.bl_idname, text="Cyberpunk Collections", icon_value=get_icon("WKIT"))
    self.layout.operator(
        CP77StreamingSectorExport.bl_idname, text="Cyberpunk StreamingSector", icon_value=get_icon("WKIT")
        )
    self.layout.operator(CP77RigJSONExport.bl_idname, text="Cyberpunk Rig to JSON", icon_value=get_icon("WKIT"))


operators, other_classes = get_classes(sys.modules[__name__])

_dependency_classes = [CP77ActionExportItem, CP77_UL_action_export]
_action_ui_operators = [CP77_OT_set_action_export_selection]
_remaining_operators = [
    cls for cls in operators if cls not in _action_ui_operators
]
_remaining_other_classes = [
    cls for cls in other_classes if cls not in _dependency_classes
]
_registration_classes = [
    *_dependency_classes,
    *_action_ui_operators,
    *_remaining_operators,
    *_remaining_other_classes,
]


def register_exporters():
    for cls in _registration_classes:
        if not hasattr(bpy.types, cls.__name__):
            bpy.utils.register_class(cls)
    TOPBAR_MT_file_export.append(menu_func_export)


def unregister_exporters():
    TOPBAR_MT_file_export.remove(menu_func_export)
    for cls in reversed(_registration_classes):
        if hasattr(bpy.types, cls.__name__):
            bpy.utils.unregister_class(cls)
