import os
import sys

import bpy
from .materials.multilayer_setup import CP77ImportMLSetup
from bpy.props import BoolProperty, CollectionProperty, EnumProperty, IntProperty, StringProperty
from bpy.types import Operator, OperatorFileListElement, PropertyGroup, TOPBAR_MT_file_import
from bpy_extras.io_utils import ImportHelper

from ..addon_identity import get_addon_preferences
from .mesh import import_cyberpunk_glb, import_external_glb, reload_materials
from .character import (
    CP77CharacterShapeProps, CP77_OT_LoadBaseCharacter, CP77_OT_NpzImportMesh, CP77_OT_NpzImportShapeKeys,
    )
from ..assetio.documents import DocumentSession
from ..cyber_props import SetCyclesRenderer, SetVulkanBackend
from ..icons.cp77_icons import get_icon
from ..gltf.provenance import GLBProvenanceError, inspect_glb
from ..registration import get_classes, RegistrationLedger
from .entity.repository import EntityRepository

_last_selected_entity_appearance = {}
_last_selected_gltf_appearance = {}
_gltf_appearance_cache = {}
_entity_appearance_cache = {}


class AppearanceItem(PropertyGroup):
    name: StringProperty()
    selected: BoolProperty(default=False)


class CP77_UL_AppearanceList(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        self.use_filter_show = len(data.appearance_list) > 15

        row = layout.row(align=True)
        all_selected = any(i.name == "all" and i.selected for i in data.appearance_list)

        if item.name.startswith("-") or item.name.startswith("─"):
            sep_row = layout.row()
            sep_row.separator(factor=0.5)
            sep_row.enabled = False
            return

        if item.name == "all":
            row.prop(item, "selected", text=item.name, text_ctxt=f"All appearances")
            return

        if item.name == "default":
            resolved = getattr(data, "_resolved_default", None)
            label = f"default → {resolved}" if resolved else "default"

            if all_selected:
                if item.selected:
                    item.selected = False
                row.enabled = False
            row.prop(item, "selected", text=label)
            return

        if all_selected:
            if item.selected:
                item.selected = False
            row.enabled = False

        elif getattr(data, "_default_selected", False):
            resolved = getattr(data, "_resolved_default", None)
            if resolved and item.name.lower() == resolved.lower():
                if item.selected:
                    item.selected = False
                row.enabled = False

        row.prop(item, "selected", text=item.name)


class CP77ImportRig(Operator):
    bl_idname = "import_scene.rig"
    bl_label = "Import Rig from JSON"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Import a rig from a rig.JSON file and create an armature in Blender"

    filter_glob: StringProperty(
            default="*.rig.json",
            options={'HIDDEN'},
            )
    filepath: bpy.props.StringProperty(subtype="FILE_PATH")

    create_debug: BoolProperty(
        name="Create Debug Empties", default=False,
        description="Create Empties at the Joints - Useful for Validating and Debugging Transforms"
        )

    bind_pose: EnumProperty(
            name="Rig Bind Pose",
            items=(("A-Pose", "A-Pose", "Will Fallback to T Pose if Unavailable"),
                   ("T-Pose", "T-Pose", "")),
            description="Bind Pose to Load",
            default="T-Pose"
            )

    def execute(self, context):
        from .rig import create_armature_from_data

        create_armature_from_data(self.filepath, self.bind_pose, self.create_debug)

        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        box.label(text="Rig Import Options")
        row = box.row()
        row.label(text="Bind Pose:")
        row.prop(self, "bind_pose", text="")
        row = box.row()
        row.prop(self, "create_debug")


class CP7PhysImport(Operator):
    bl_idname = "import_scene.phys"
    bl_label = "Import .phys Collisions"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Import collisions from an exported .phys.json"

    filepath: StringProperty(subtype="FILE_PATH")

    def execute(self, context):
        from .collision import import_phys

        import_phys(self.filepath)
        return {"FINISHED"}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}


def _load_entity_for_ui(filepath):
    if not filepath or not os.path.isfile(filepath):
        return None
    with DocumentSession() as documents:
        return EntityRepository(documents).load(filepath, required=True)


def get_appearance_items(self, context):
    try:
        entity = _load_entity_for_ui(self.filepath)
    except Exception as error:
        print(f"[CP77] Error reading appearances: {error}")
        return []
    return list(entity.appearance_names) if entity is not None else []


class CP77EntityImport(Operator, ImportHelper):
    bl_idname = "io_scene_gltf.cp77entity"
    bl_label = "Import Ent from JSON"
    bl_description = "Import Characters and Vehicles from Cyberpunk 2077 Entity Files"

    filter_glob: StringProperty(
            default="*.ent.json",
            options={'HIDDEN'},
            )

    filepath: StringProperty(
        name="Filepath",
        subtype='FILE_PATH'
        )

    # generate_overrides: BoolProperty(name="Generate Overrides for Multilayer materials (may be slow)",default=False,description="Imports overrides and palettes for multilayered materials")

    appearance_list: CollectionProperty(type=AppearanceItem)
    active_appearance_index: IntProperty(default=0)

    exclude_meshes: StringProperty(
        name="Meshes_to_Exclude",
        description="Meshes to skip during import",
        default="",
        options={'HIDDEN'}
        )

    include_collisions: BoolProperty(
        name="Include Collisions", default=False,
        description="Use this option to import collision bodies with this entity"
        )
    include_phys: BoolProperty(
        name="Include .phys Collisions", default=False,
        description="Use this option if you want to import the .phys collision bodies. Useful for vehicle modding"
        )
    include_entCollider: BoolProperty(
        name="Include Collision Components", default=False,
        description="Use this option to import entColliderComponent and entSimpleColliderComponent"
        )
    import_occluders: BoolProperty(
        name="Include Static Occluders", default=False,
        description="Import entStaticOccluderMeshComponent geometry"
        )
    import_proxies: BoolProperty(
        name="Include Appearance Proxies", default=False,
        description="Import entAppearanceProxyMeshComponent geometry"
        )
    include_lights: BoolProperty(
        name="Import Lights",
        default=False,
        description=(
            "Import entity light components and light-channel components"
        ),
        )
    inColl: StringProperty(
        name="Collector to put the imported entity in",
        description="Collector to put the imported entity in",
        default='',
        options={'HIDDEN'}
        )

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def get_default_appearance_name(self):
        try:
            entity = _load_entity_for_ui(self.filepath)
        except Exception as error:
            print(f"[CP77] Error resolving defaultAppearance: {error}")
            return None
        if entity is None or entity.default_appearance.casefold() in {"", "none", "null", "random"}:
            return None
        return entity.default_appearance

    def ent_update_appearance_list(self):
        self.appearance_list.clear()
        names = get_appearance_items(self, bpy.context)

        self._resolved_default = self.get_default_appearance_name()

        last_selected = _last_selected_entity_appearance.get(self.filepath, [])

        if not names:
            item = self.appearance_list.add()
            item.name = "default"
            item.selected = True
            return

        if len(names) == 1:
            item = self.appearance_list.add()
            item.name = "default"
            item.selected = True
            return

        def_item = self.appearance_list.add()
        def_item.name = "default"
        def_item.selected = "default" in last_selected or not last_selected

        all_item = self.appearance_list.add()
        all_item.name = "all"
        all_item.selected = "all" in last_selected

        sep = self.appearance_list.add()
        sep.name = "----"
        sep.selected = False

        for name in sorted([n for n in names if n.lower() != "default"], key=str.lower):
            item = self.appearance_list.add()
            item.name = name
            item.selected = name in last_selected

    def draw(self, context):
        cp77_addon_prefs = get_addon_preferences(context)
        props = context.scene.cp77_panel_props
        layout = self.layout

        box = layout.box()
        box.label(text="Entity Appearance", icon='OUTLINER_OB_GROUP_INSTANCE')

        if not self.filepath:
            if len(self.appearance_list) > 0:
                self.appearance_list.clear()
                self._last_filepath = ""

            row = box.row(align=True)
            row.label(text="Please select a .ent.json file")
            return

        last = getattr(self, '_last_filepath', '')
        if last != self.filepath:
            self.ent_update_appearance_list()
            self._last_filepath = self.filepath

        if len(self.appearance_list) == 0:
            box = layout.box()
            row = box.row(align=True)
            row.label(text="No appearances found", icon='INFO')
            sub = box.row()
            sub.alignment = 'CENTER'
            sub.enabled = False
            sub.label(text=f"Will import base components only")

        row = box.row()
        row.template_list(
                "CP77_UL_AppearanceList",
                "",
                self,
                "appearance_list",
                self,
                "active_appearance_index",
                rows=min(10, len(self.appearance_list))
                )

        selected_names = [item.name for item in self.appearance_list if item.selected]

        if "default" in selected_names:
            resolved = getattr(self, '_resolved_default', None)
            if resolved and resolved.lower() != "default":
                for item in self.appearance_list:
                    if item.name.lower() == resolved.lower() and item.selected:
                        box = layout.box()
                        row = box.row(align=True)
                        row.label(text="Skipping duplicate entity import:", icon="INFO")
                        sub = box.row()
                        sub.alignment = 'CENTER'
                        sub.enabled = False
                        sub.label(text=f"↳ '{resolved}' matches 'default'")
                        break

        box = layout.box()
        box.label(text="Entity Import")
        col = box.column()
        col.prop(props, "with_materials")
        if cp77_addon_prefs.experimental_features:
            col.prop(props, "remap_depot")
        # col.prop(self, 'generate_overrides')
        box = layout.box()
        col = box.column()
        col.prop(props, 'use_vulkan')
        col.prop(props, 'use_cycles')
        if props.use_cycles:
            col.prop(props, 'update_gi')

        if not self.include_collisions:
            self.include_phys = False
            self.include_entCollider = False
            self._collisions_initialized = False
        else:
            if not hasattr(self, "_collisions_initialized") or not self._collisions_initialized:
                self.include_phys = True
                self.include_entCollider = True
                self._collisions_initialized = True

        header, panel = layout.panel(
            "cp77_entity_optional_imports",
            default_closed=True,
            )
        header.label(text="Optional Imports")
        if panel:
            col = panel.column()
            col.prop(self, "import_occluders")
            col.prop(self, "import_proxies")
            col.prop(self, "include_lights")
            col.prop(self, "include_collisions")
            if self.include_collisions:
                nested = col.column(align=True)
                nested.prop(self, "include_phys")
                nested.prop(self, "include_entCollider")

    def execute(self, context):
        props = context.scene.cp77_panel_props

        SetVulkanBackend(props.use_vulkan)
        SetCyclesRenderer(props.use_cycles, props.update_gi)

        selected = [item.name for item in self.appearance_list if item.selected]

        if selected:
            _last_selected_entity_appearance[self.filepath] = selected

        if "all" in selected:
            apps = ["ALL"]

        elif "default" in selected:
            resolved = getattr(self, '_resolved_default', None)
            filtered = []

            for name in selected:
                if name == "default":
                    filtered.append("default")
                elif resolved and name.lower() == resolved.lower():
                    print(f"[CP77] Warning: '{name}' is the same as resolved defaultAppearance.")
                    print(f"[CP77] It was already included via 'default'. Skipping duplicate.")
                else:
                    filtered.append(name)

            apps = filtered if filtered else ["default"]

        else:
            apps = selected

        print('apps - ', apps)
        bob = self.filepath
        inColl = self.inColl
        # print('Bob - ',bob)
        from .entity import EntityImportRequest, import_entity

        try:
            result = import_entity(
                EntityImportRequest(
                    with_materials=props.with_materials,
                    filepath=bob,
                    appearances=tuple(apps),
                    excluded_meshes=(),
                    include_collisions=self.include_collisions,
                    include_phys=self.include_phys,
                    include_entity_colliders=self.include_entCollider,
                    include_occluders=self.import_occluders,
                    include_proxies=self.import_proxies,
                    include_lights=self.include_lights,
                    parent_collection_name=inColl,
                )
            )
        except Exception as error:
            self.report({'ERROR'}, f"Entity import failed: {error}")
            return {'CANCELLED'}
        if result.warnings:
            self.report(
                {'WARNING'},
                f"Entity import completed with warnings: {result.warnings[0]}",
            )
        if result.failures:
            self.report(
                {'ERROR'},
                f"Entity import failed and was rolled back: {result.failures[0]}",
            )
        return result.blender_status


class CP77StreamingSectorImport(Operator, ImportHelper):
    bl_idname = "io_scene_gltf.cp77sector"
    bl_label = "Import All StreamingSectors from project"
    bl_description = "Load Cyberpunk 2077 Streaming Sectors"

    filter_glob: StringProperty(
            default="*.cpmodproj",
            options={'HIDDEN'},
            )

    filepath: StringProperty(
        name="Filepath",
        subtype='FILE_PATH'
        )

    want_collisions: BoolProperty(
        name="Import Collisions", default=False,
        description="Import Box and Capsule Collision objects (mesh not yet supported)"
        )
    am_modding: BoolProperty(
        name="Generate New Collectors", default=False,
        description="Generate _new collectors for sectors to allow modifications to be saved back to game"
        )
    with_lights: BoolProperty(
        name="Import Lights", default=False,
        description=(
            "Import sector lights and light-related components in nested entities"
        )
        )
    import_foliage: BoolProperty(
        name="Import Foliage",
        default=False,
        description=(
            "Import foliage populations; foliage-destruction metadata also "
            "requires Import Collisions"
        ),
        )
    import_effects: BoolProperty(
        name="Import Effects",
        default=False,
        description="Import particle and effect nodes",
        )
    import_proxies: BoolProperty(
        name="Import Proxy Meshes", default=False,
        description=(
            "Import all proxy mesh nodes, including global water-patch proxies"
        )
        )
    import_acoustics: BoolProperty(
        name="Import Acoustic Data", default=False,
        description="Import acoustic sector markers and resolve acoustic data resources"
        )
    import_occluders: BoolProperty(
        name="Import Occluders", default=False,
        description="Import static and instanced occluder geometry"
        )
    import_minimap: BoolProperty(
        name="Import Minimap Data", default=False,
        description="Import minimap data nodes and resolve minimap resources"
        )
    import_environment_probes: BoolProperty(
        name="Import Environment Probes", default=False,
        description="Import reflection probe volumes and resolve environment probe resources"
        )
    import_world_metadata: BoolProperty(
        name="Import World Metadata", default=False,
        description=(
            "Import ambient and interior areas, light-channel volumes and shapes, "
            "interior maps, static fog volumes, static sound emitters, and world boundaries"
            )
        )
    import_gi: BoolProperty(
        name="Import GI Data", default=False,
        description="Import global illumination nodes, spaces, and GI resources"
        )

    def draw(self, context):
        cp77_addon_prefs = get_addon_preferences(context)
        props = context.scene.cp77_panel_props
        layout = self.layout

        box = layout.box()
        box.label(text="Sector Import", icon='OUTLINER_OB_GROUP_INSTANCE')
        col = box.column()
        col.prop(self, "am_modding")
        col.prop(props, "with_materials")

        header, panel = layout.panel(
            "cp77_sector_optional_imports",
            default_closed=True,
            )
        header.label(text="Optional Imports")
        if panel:
            col = panel.column()
            col.prop(self, "want_collisions")
            col.prop(self, "with_lights")
            col.prop(self, "import_foliage")
            col.prop(self, "import_effects")
            col.prop(self, "import_proxies")
            col.prop(self, "import_acoustics")
            col.prop(self, "import_minimap")
            col.prop(self, "import_occluders")
            col.prop(self, "import_environment_probes")
            col.prop(self, "import_world_metadata")
            col.prop(self, "import_gi")

        if cp77_addon_prefs.experimental_features:
            box = layout.box()
            col = box.column()
            col.prop(props, "remap_depot")

    def execute(self, context):
        bob = self.filepath
        props = context.scene.cp77_panel_props
        print('Importing Sectors from project - ', bob)
        from .sector.execution import import_sectors

        try:
            result = import_sectors(
                filepath=bob,
                with_mats=props.with_materials,
                remap_depot=props.remap_depot,
                want_collisions=self.want_collisions,
                am_modding=self.am_modding,
                with_lights=self.with_lights,
                import_foliage=self.import_foliage,
                import_effects=self.import_effects,
                import_proxies=self.import_proxies,
                import_acoustics=self.import_acoustics,
                import_occluders=self.import_occluders,
                import_minimap=self.import_minimap,
                import_environment_probes=self.import_environment_probes,
                import_world_metadata=self.import_world_metadata,
                import_gi=self.import_gi,
                )
        except Exception as error:
            self.report({'ERROR'}, f"Sector import failed: {error}")
            return {'CANCELLED'}
        if result.warnings:
            self.report(
                {'WARNING'},
                f"Sector import completed with warnings: {result.warnings[0]}",
            )
        if result.failures:
            self.report(
                {'ERROR'},
                f"Sector import failed and was rolled back: {result.failures[0]}",
            )
        return result.blender_status



def get_gltf_appearance_items(self, context):
    if not self.filepath:
        return []

    names = []

    base = os.path.splitext(self.filepath)[0]
    material_json = base + ".Material.json"

    if os.path.isfile(material_json):
        try:
            from ..materials.resources import load_material_bundle

            bundle = load_material_bundle(material_json)
            appearances = bundle.appearances
            values = appearances.keys() if isinstance(appearances, dict) else appearances
            names.extend(str(name) for name in values if name)
        except Exception as error:
            print(f"[CP77] Error reading material.json: {error}")

    return names


def clean_appearance_name(name, index):
    suffix = str(index)
    if name.endswith(suffix):
        return name[:-len(suffix)]
    return name


class CP77Import(Operator, ImportHelper):
    bl_idname = "io_scene_gltf.cp77"
    bl_label = "Import Cyberpunk GLB"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Import a WolvenKit/direct GLB, or normalize an external GLB through Blender"

    filter_glob: StringProperty(default="*.glb", options={'HIDDEN'})
    filepath: StringProperty(name="Filepath", subtype='FILE_PATH')
    files: CollectionProperty(type=OperatorFileListElement)
    directory: StringProperty(subtype='FILE_PATH')

    appearance_list: CollectionProperty(type=AppearanceItem)
    active_appearance_index: IntProperty(default=0)

    image_format: EnumProperty(
            name="Textures",
            items=(("png", "Use PNG textures", ""),
                   ("dds", "Use DDS textures", ""),
                   ("jpg", "Use JPG textures", ""),
                   ("tga", "Use TGA textures", ""),
                   ("bmp", "Use BMP textures", ""),
                   ("jpeg", "Use JPEG textures", "")),
            default="png"
            )

    # exclude_unused_mats: BoolProperty(name="Exclude Unused Materials",default=True,description="Enabling this options skips all the materials that aren't being used by any mesh")

    # Kwekmaster: QoL option to match WolvenKit GUI options - Name change to With Materials
    hide_armatures: BoolProperty(
        name="Hide Armatures", default=True, description="Hide the armatures on imported meshes"
        )

    import_garmentsupport: BoolProperty(
        name="Import Garment Support (Experimental)", default=True,
        description="Imports Garment Support mesh data as color attributes"
        )
    # generate_overrides: BoolProperty(name="Generate Overrides for Multilayer materials (may be slow)",default=False,description="Imports overrides and palettes for multilayered materials")

    scripting: BoolProperty(
        name="Scripting", default=False,
        description="Tell it its being called by a script so it can ignore the gui file lists", options={'HIDDEN'}
        )
    import_tracks: BoolProperty(
        name="Import Tracks", default=True, description="Import Animation Float Tracks to F-Curves"
        )

    def gltf_update_appearance_list(self):
        self.appearance_list.clear()
        names = get_gltf_appearance_items(self, bpy.context)

        last_selected = _last_selected_gltf_appearance.get(self.filepath, [])

        if not names:
            return

        cleaned_names = []
        for i, name in enumerate(names):
            clean_name = clean_appearance_name(name, i)
            cleaned_names.append(clean_name)

        if len(cleaned_names) == 1:
            item = self.appearance_list.add()
            item.name = clean_name
            item.selected = True
            return

        all_item = self.appearance_list.add()
        all_item.name = "all"
        all_item.selected = "all" in last_selected or not last_selected

        for name in cleaned_names:
            item = self.appearance_list.add()
            item.name = name
            item.selected = name in last_selected

    def draw(self, context):
        cp77_addon_prefs = get_addon_preferences(context)
        props = context.scene.cp77_panel_props
        layout = self.layout

        box = layout.box()
        box.label(text="Mesh Appearance", icon='OUTLINER_OB_GROUP_INSTANCE')

        if not self.filepath:
            row = box.row(align=True)
            row.label(text="Please select a .glb file")
            return

        if self.filepath:
            last = getattr(self, '_last_filepath', '')
            if last != self.filepath:
                self.gltf_update_appearance_list()
                self._last_filepath = self.filepath

            if len(self.appearance_list) == 0:
                box = layout.box()
                row = box.row(align=True)
                row.label(text="No appearances found", icon='INFO')
                sub = box.row()
                sub.alignment = 'CENTER'
                sub.enabled = False
                sub.label(text="Importing GLB without CP77 material sidecar")
                return

            row = box.row()

            row.template_list(
                    "CP77_UL_AppearanceList",
                    "",
                    self,
                    "appearance_list",
                    self,
                    "active_appearance_index",
                    rows=min(10, len(self.appearance_list)),
                    )

        if not props.with_materials:
            box = layout.box()
            col = box.column()
            col.prop(props, 'with_materials')
            if cp77_addon_prefs.experimental_features:
                col.prop(props, "remap_depot")
            box = layout.box()
            col = box.column()
            col.prop(self, 'hide_armatures')
            col.prop(self, 'import_garmentsupport')
            if cp77_addon_prefs.experimental_features:
                col.prop(props, "remap_depot")
        if props.with_materials:
            box = layout.box()
            col = box.column()
            col.prop(props, 'with_materials')
            if cp77_addon_prefs.experimental_features:
                col.prop(props, "remap_depot")
            # col.prop(self, 'generate_overrides')
            # if not self.show_appearance_selection:
            #   col.prop(self, 'exclude_unused_mats')
            box = layout.box()
            col = box.column()
            col.prop(props, 'use_vulkan')
            col.prop(props, 'use_cycles')
            if props.use_cycles:
                col.prop(props, 'update_gi')
            box = layout.box()
            box.label(text='Texture Format:')
            box.prop(self, 'image_format', text='')
            box = layout.box()
            col = box.column()
            col.prop(self, 'hide_armatures')
            col.prop(self, 'import_garmentsupport')
        box = layout.box()
        col = box.column()
        col.prop(self, 'import_tracks')

        # if not self.show_appearance_selection:
        #    col.prop(self, 'exclude_unused_mats')

    def execute(self, context):
        props = context.scene.cp77_panel_props
        inspection = None
        import_path = self.filepath

        if not self.scripting:
            selected_names = [
                str(getattr(item, "name", "") or "")
                for item in self.files
                if str(getattr(item, "name", "") or "")
            ]
            if selected_names:
                base_directory = self.directory or os.path.dirname(self.filepath)
                selected_paths = [
                    os.path.join(base_directory, name)
                    for name in selected_names
                ]
            else:
                selected_paths = [self.filepath] if self.filepath else []
            if len(selected_paths) != 1:
                self.report(
                    {'ERROR'},
                    "The UI importer accepts exactly one GLB at a time.",
                )
                return {'CANCELLED'}
            import_path = os.path.abspath(selected_paths[0])
            try:
                inspection = inspect_glb(import_path)
            except GLBProvenanceError as error:
                self.report({'ERROR'}, str(error))
                return {'CANCELLED'}

            if not inspection.claims_cp77_origin:
                try:
                    summary = import_external_glb(import_path, inspection)
                except Exception as error:
                    self.report({'ERROR'}, str(error))
                    return {'CANCELLED'}
                generator = inspection.generator or "unspecified generator"
                self.report(
                    {'INFO'},
                    f"Imported {summary.mesh_count} external meshes and "
                    f"{summary.armature_count} armatures and "
                    f"{summary.action_count} actions from {generator}"
                    + (
                        "; objects were normalized for CP77 export."
                        if summary.object_count
                        else "."
                    ),
                )
                return {'FINISHED'}

            if not inspection.direct_import_supported:
                self.report(
                    {'ERROR'},
                    f"{inspection.generator or 'The GLB generator'} identifies a CP77 source, "
                    f"but the document content is {inspection.content_kind.value!r} and cannot "
                    "be imported by the direct CP77 path.",
                )
                return {'CANCELLED'}

        SetVulkanBackend(props.use_vulkan)
        SetCyclesRenderer(props.use_cycles, props.update_gi)

        selected = [item.name for item in self.appearance_list if item.selected]
        if selected:
            _last_selected_gltf_appearance[self.filepath] = selected

        if "all" in selected:
            appearances = ["ALL"]
        elif len(selected) == 0:
            appearances = ["default"]
        else:
            appearances = selected

        print('apps - ', appearances)

        try:
            result = import_cyberpunk_glb(
                    props.with_materials,
                    props.remap_depot,
                    False,
                    self.image_format,
                    import_path,
                    self.hide_armatures,
                    self.import_garmentsupport,
                    () if inspection is not None else self.files,
                    os.path.dirname(import_path) if inspection is not None else self.directory,
                    appearances,
                    self.scripting,
                    self.import_tracks,
                    False,
                    animation_target='AUTO',
                    content_kind=(
                        inspection.content_kind.value
                        if inspection is not None
                        else None
                    ),
                    )
        except Exception as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}

        if result.failures:
            self.report(
                {'ERROR'},
                f"GLB import was incomplete: {result.failures[0]}",
            )
            return {'CANCELLED'}
        if result.warnings:
            self.report(
                {'WARNING'},
                f"GLB import completed with warnings: {result.warnings[0]}",
            )
        if inspection is not None:
            self.report(
                {'INFO'},
                f"Imported {inspection.content_kind.value} GLB from "
                f"{inspection.generator or inspection.source.value}.",
            )
        return {'FINISHED'}


class CP77MaterialReload(Operator):
    bl_idname = "reload_material.cp77"
    bl_label = "Reload Material"
    bl_options = {'REGISTER', 'UNDO'}
    bl_parent_id = "CP77_PT_MaterialTools"
    bl_description = "Reload the active material from json."

    def execute(self, context):
        active_object = context.active_object
        if not active_object:
            self.report({'ERROR'}, "No active object")
            return {'CANCELLED'}
        active_material = active_object.active_material
        if not active_material:
            self.report({'ERROR'}, "Active object has no material")
            return {'CANCELLED'}
        # JATO: TODO make a popup asking to use the locate mesh operator
        if not active_material.get("MeshPath"):
            self.report(
                    {'ERROR'},
                    "Material was not reloaded: Use Locate Mesh to find a valid source file within a WolvenKit project"
                    )
            return {'CANCELLED'}

        old_mat = active_material
        old_mat_idx = active_object.active_material_index

        new_mat = reload_materials(self, context)

        # The reload service must return the same Blender material type.
        if type(new_mat) is not type(old_mat):
            self.report({'ERROR'}, 'Material failed to reload')
            return {'CANCELLED'}

        context.active_object.active_material = new_mat
        context.active_object.active_material_index = old_mat_idx

        from ..materialtools.editor import synchronize_panel
        synchronize_panel(context)

        try:
            if old_mat.users == 0:
                bpy.data.materials.remove(
                    old_mat,
                    do_unlink=True,
                    do_id_user=True,
                    do_ui_user=True,
                )
        except (ReferenceError, RuntimeError, TypeError):
            pass

        return {"FINISHED"}


def menu_func_import(self, context):
    self.layout.operator(CP77Import.bl_idname, text="Cyberpunk GLB (.glb)", icon_value=get_icon('WKIT'))
    self.layout.operator(CP77EntityImport.bl_idname, text="Cyberpunk Entity (.json)", icon_value=get_icon('WKIT'))
    self.layout.operator(
        CP77StreamingSectorImport.bl_idname, text="Cyberpunk StreamingSector", icon_value=get_icon('WKIT')
        )
    self.layout.operator(CP77ImportRig.bl_idname, text="Cyberpunk Rig import (.rig.json)", icon_value=get_icon('WKIT'))


_npz_classes = (
    CP77ImportMLSetup,
    CP77CharacterShapeProps,
    CP77_OT_NpzImportMesh,
    CP77_OT_NpzImportShapeKeys,
    CP77_OT_LoadBaseCharacter,
)
registration_classes = get_classes(
    sys.modules[__name__],
    extra_classes=_npz_classes,
)


_LEDGER = RegistrationLedger("importers")


def _remove_import_menu():
    try:
        TOPBAR_MT_file_import.remove(menu_func_import)
    except Exception:
        pass


def register_importers():
    if _LEDGER.active:
        return
    try:
        _LEDGER.register_classes(registration_classes)
        _LEDGER.add_property(
            bpy.types.Scene,
            "cp77_character_shape",
            bpy.props.PointerProperty(type=CP77CharacterShapeProps),
        )
        _remove_import_menu()
        TOPBAR_MT_file_import.append(menu_func_import)
        _LEDGER.add_cleanup("import menu", _remove_import_menu)
        from .entity.rigs import register_rig_cache_handlers, unregister_rig_cache_handlers
        register_rig_cache_handlers()
        _LEDGER.add_cleanup("rig cache handlers", unregister_rig_cache_handlers)
    except Exception:
        _LEDGER.cleanup()
        raise


def unregister_importers():
    failures = _LEDGER.cleanup()
    if failures:
        raise RuntimeError("; ".join(f"{label}: {error}" for label, error in failures))
