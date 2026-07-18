from bpy.props import (BoolProperty, CollectionProperty, EnumProperty, IntProperty, StringProperty)
from bpy.types import (Operator, OperatorFileListElement, TOPBAR_MT_file_import)
from bpy_extras.io_utils import ImportHelper

from .entity_import import *
from .import_with_materials import *
from .npz_import import (
    CP77CharacterShapeProps, CP77_OT_LoadBaseCharacter, CP77_OT_NpzImportMesh, CP77_OT_NpzImportShapeKeys,
    )
from .phys_import import *
from .read_rig import create_armature_from_data
from .sector_import import *
from ..cyber_props import *
from ..icons.cp77_icons import *

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
        cp77_phys_import(self.filepath)
        return {"FINISHED"}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}


def get_appearance_items(self, context):
    if not self.filepath or not os.path.isfile(self.filepath):
        return []

    try:
        with open(self.filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"[CP77] Error reading appearances: {e}")
        return []

    root = data.get('Data', {}).get('RootChunk', {})
    names = []

    for app in root.get('appearances') or []:
        if isinstance(app, dict):
            name = app.get('appearanceName', {}).get('$value')
            if name:
                names.append(name)

    return names


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

        if not self.filepath or not os.path.isfile(self.filepath):
            return None

        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)

            root = data.get('Data', {}).get('RootChunk', {})
            default_value = root.get('defaultAppearance', {})

            if isinstance(default_value, dict):
                default_name = default_value.get('$value', '').strip()
            else:
                default_name = str(default_value).strip()

            if not default_name or default_name.lower() in ('none', 'null', 'random', ''):
                return None

            appearances = root.get('appearances', [])
            for app in appearances:
                name_field = app.get('name', {})
                if isinstance(name_field, dict):
                    name_value = name_field.get('$value', '')
                else:
                    name_value = str(name_field)

                if name_value == default_name:
                    app_name = app.get('appearanceName', {})
                    if isinstance(app_name, dict):
                        return app_name.get('$value', default_name)
                    return str(app_name)

            return default_name

        except Exception as e:
            print(f"[CP77] Error resolving defaultAppearance: {e}")
            return None

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
        cp77_addon_prefs = bpy.context.preferences.addons['i_scene_cp77_gltf'].preferences
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

        row = layout.row(align=True)
        if not self.include_collisions:
            self.include_phys = False
            self.include_entCollider = False
            self._collisions_initialized = False
        else:
            if not hasattr(self, "_collisions_initialized") or not self._collisions_initialized:
                self.include_phys = True
                self.include_entCollider = True
                self._collisions_initialized = True

        row.prop(self, "include_collisions")

        if self.include_collisions:
            row = layout.row(align=True)
            row.prop(self, "include_phys")
            row = layout.row(align=True)
            row.prop(self, "include_entCollider")

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
        excluded = ""
        bob = self.filepath
        inColl = self.inColl
        # print('Bob - ',bob)
        importEnt(
            props.with_materials, bob, apps, excluded, self.include_collisions, self.include_phys,
            self.include_entCollider, inColl, props.remap_depot,
            meshes=None, mesh_jsons=None, escaped_path=None, app_path=None, anim_files=None, rigjsons=None
            )

        return {'FINISHED'}


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
        name="Import Lights", default=True, description="Import and setup Lights based on worldLightNodes"
        )

    def draw(self, context):
        cp77_addon_prefs = bpy.context.preferences.addons['i_scene_cp77_gltf'].preferences
        props = context.scene.cp77_panel_props
        layout = self.layout
        box = layout.box()
        box.label(text="Sector Import", icon='OUTLINER_OB_GROUP_INSTANCE')
        col = box.column()
        col.prop(self, "want_collisions", )
        col.prop(self, "with_lights")
        col.prop(self, "am_modding")
        col.prop(props, "with_materials")
        if cp77_addon_prefs.experimental_features:
            box = layout.box()
            col = box.column()
            col.prop(props, "remap_depot")

    def execute(self, context):
        bob = self.filepath
        props = context.scene.cp77_panel_props
        print('Importing Sectors from project - ', bob)
        importSectors(
            bob, props.with_materials, props.remap_depot, self.want_collisions, self.am_modding, self.with_lights
            )
        return {'FINISHED'}


def get_gltf_appearance_items(self, context):
    if not self.filepath:
        return []

    names = []

    base = os.path.splitext(self.filepath)[0]
    material_json = base + ".Material.json"

    if os.path.isfile(material_json):
        try:
            with open(material_json, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if 'Appearances' in data:
                for app_name in data['Appearances'].keys():
                    if app_name:
                        names.append(app_name)
        except Exception as e:
            print(f"[CP77] Error reading material.json: {e}")

    return names


def clean_appearance_name(name, index):
    suffix = str(index)
    if name.endswith(suffix):
        return name[:-len(suffix)]
    return name


class CP77Import(Operator, ImportHelper):
    bl_idname = "io_scene_gltf.cp77"
    bl_label = "Import glTF"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Load glTF 2.0 files with Cyberpunk 2077 materials"

    filter_glob: StringProperty(default="*.gltf;*.glb", options={'HIDDEN'})
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
        cp77_addon_prefs = bpy.context.preferences.addons['i_scene_cp77_gltf'].preferences
        props = context.scene.cp77_panel_props
        layout = self.layout

        box = layout.box()
        box.label(text="Mesh Appearance", icon='OUTLINER_OB_GROUP_INSTANCE')

        if not self.filepath:
            row = box.row(align=True)
            row.label(text="Please select a .glb/.gltf file")
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
                sub.label(text=f"Importing .gltf/.glb without materials")
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

        impinitiated_cache = False
        if not JSONTool._use_cache:
            JSONTool.start_caching()
            impinitiated_cache = True

        try:
            CP77GLBimport(
                    props.with_materials,
                    props.remap_depot,
                    False,
                    self.image_format,
                    self.filepath,
                    self.hide_armatures,
                    self.import_garmentsupport,
                    self.files,
                    self.directory,
                    appearances,
                    self.scripting,
                    self.import_tracks,
                    False,
                    animation_target='AUTO',
                    )
        except Exception as error:
            if self.filepath.lower().endswith('.anims.glb'):
                self.report({'ERROR'}, str(error))
                return {'CANCELLED'}
            raise
        finally:
            if impinitiated_cache:
                JSONTool.stop_caching()

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
        if active_material['MeshPath'] == "":
            self.report(
                    {'ERROR'},
                    "Material was not reloaded: Use Locate Mesh to find a valid source file within a WolvenKit project"
                    )
            return {'CANCELLED'}

        old_mat = active_material
        old_mat_idx = active_object.active_material_index

        new_mat = reload_mats(self, context)

        # JATO: maybe dumb but if reload_mats dont return the same type something is f'd
        if type(new_mat) is not type(old_mat):
            self.report({'ERROR'}, 'Material failed to reload')
            return {'CANCELLED'}

        old_mat.user_remap(new_mat)

        bpy.context.object.active_material = new_mat
        bpy.context.active_object.active_material_index = old_mat_idx

        bpy.ops.refresh_layer.mlsetup()

        # JATO: cannot figure out how to delete the old mat without causing a crash...
        # bpy.data.materials.remove(old_mat)

        return {"FINISHED"}


def menu_func_import(self, context):
    self.layout.operator(CP77Import.bl_idname, text="Cyberpunk GLTF (.gltf/.glb)", icon_value=get_icon('WKIT'))
    self.layout.operator(CP77EntityImport.bl_idname, text="Cyberpunk Entity (.json)", icon_value=get_icon('WKIT'))
    self.layout.operator(
        CP77StreamingSectorImport.bl_idname, text="Cyberpunk StreamingSector", icon_value=get_icon('WKIT')
        )
    self.layout.operator(CP77ImportRig.bl_idname, text="Cyberpunk Rig import (.rig.json)", icon_value=get_icon('WKIT'))


operators, other_classes = get_classes(sys.modules[__name__])
_npz_classes = (
    CP77CharacterShapeProps,
    CP77_OT_NpzImportMesh,
    CP77_OT_NpzImportShapeKeys,
    CP77_OT_LoadBaseCharacter,
    )


def register_importers():
    try:
        bpy.utils.register_class(AppearanceItem)
    except Exception:
        pass

    for cls in operators:
        if not hasattr(bpy.types, cls.__name__):
            bpy.utils.register_class(cls)

    for cls in other_classes:
        if cls.__name__ == "AppearanceItem":
            continue
        if not hasattr(bpy.types, cls.__name__):
            bpy.utils.register_class(cls)

    for cls in _npz_classes:
        if not hasattr(bpy.types, cls.__name__):
            bpy.utils.register_class(cls)

    bpy.types.Scene.cp77_character_shape = bpy.props.PointerProperty(type=CP77CharacterShapeProps)
    TOPBAR_MT_file_import.append(menu_func_import)


def unregister_importers():
    if hasattr(bpy.types.Scene, "cp77_character_shape"):
        del bpy.types.Scene.cp77_character_shape

    for cls in reversed(_npz_classes):
        if hasattr(bpy.types, cls.__name__):
            bpy.utils.unregister_class(cls)
    for cls in reversed(other_classes):
        bpy.utils.unregister_class(cls)
    for cls in reversed(operators):
        bpy.utils.unregister_class(cls)

    TOPBAR_MT_file_import.remove(menu_func_import)
