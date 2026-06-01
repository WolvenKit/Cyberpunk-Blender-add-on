import bpy
import sys
import os
import json 
import re
from bpy_extras.io_utils import ImportHelper
from bpy.props import (StringProperty, EnumProperty, BoolProperty, CollectionProperty)
from bpy.types import (Operator, OperatorFileListElement, TOPBAR_MT_file_import )
from .import_with_materials import *
from .entity_import import *
from .sector_import import *
from .phys_import import *
from ..main.bartmoss_functions import *
from ..main.common import get_classes
from ..cyber_props import *
from ..cyber_prefs import *
from ..icons.cp77_icons import *
from .read_rig import create_armature_from_data
from .npz_import import (CP77CharacterShapeProps, CP77_OT_NpzImportMesh, CP77_OT_NpzImportShapeKeys, CP77_OT_LoadBaseCharacter)

_appearance_enum_cache = [("default", "default", "Use default appearance")]
_last_selected_appearance = {}

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
    
    create_debug: BoolProperty(name="Create Debug Empties",default=False,description="Create Empties at the Joints - Useful for Validating and Debugging Transforms")
    
    bind_pose: EnumProperty(
        name="Rig Bind Pose",
        items=(("A-Pose", "A-Pose", "Will Fallback to T Pose if Unavailable"),
                ("T-Pose", "T-Pose", "")),
        description="Bind Pose to Load",
        default="T-Pose")
        

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
        row.prop(self, "bind_pose",text="")
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


# ====================== APPEARANCE DROP MENU ======================

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


def get_appearance_enum_items(self, context):
    global _appearance_enum_cache

    if not self.filepath:
        _appearance_enum_cache = [("SELECT_FILE", "Select file", "Please select an .ent.json file")]
        return _appearance_enum_cache

    names = get_appearance_items(self, context)

    if not names:
        _appearance_enum_cache = [("default", "default", "Use default appearance")]
        return _appearance_enum_cache

    result = [
        ("default", "default", "Use default appearance"),
        ("all", "all", "Import ALL appearances"),
        None,
    ]

    for name in sorted(names, key=str.lower):
        if name.lower() != "default":
            result.append((name, name, f"Import appearance: {name}"))

    _appearance_enum_cache = result
    return _appearance_enum_cache


def update_filepath(self, context):
    try:
        items = get_appearance_enum_items(self, context)
        self.property_unset("selected_appearance")

        if self.filepath in _last_selected_appearance:
            last = _last_selected_appearance[self.filepath]
            if any(item[0] == last for item in items):
                self["selected_appearance"] = last
                return

        self["selected_appearance"] = "default"

    except Exception as e:
        print(f"[CP77] update_filepath error: {e}")
        self["selected_appearance"] = "default"

    for area in context.screen.areas:
        area.tag_redraw()

# ==================================================================

class CP77EntityImport(Operator,ImportHelper):

    bl_idname = "io_scene_gltf.cp77entity"
    bl_label = "Import Ent from JSON"
    bl_description = "Import Characters and Vehicles from Cyberpunk 2077 Entity Files"

    filter_glob: StringProperty(
        default="*.ent.json",
        options={'HIDDEN'},
        )

    filepath: StringProperty(name= "Filepath",
                             subtype = 'FILE_PATH',
                             update=update_filepath)

    appearances: StringProperty(name= "Appearances",
                                description="Entity Appearances to extract. Needs appearanceName from ent. Comma seperate multiples",
                                default="default",
                                )

    generate_overrides: BoolProperty(name="Generate Overrides for Multilayer materials (may be slow)",default=False,description="Imports overrides and palettes for multilayered materials")

    exclude_meshes: StringProperty(name= "Meshes_to_Exclude",
                                description="Meshes to skip during import",
                                default="",
                                options={'HIDDEN'})

    include_collisions: BoolProperty(name="Include Collisions",default=False,description="Use this option to import collision bodies with this entity")
    include_phys: BoolProperty(name="Include .phys Collisions",default=False,description="Use this option if you want to import the .phys collision bodies. Useful for vehicle modding")
    include_entCollider: BoolProperty(name="Include Collision Components",default=False,description="Use this option to import entColliderComponent and entSimpleColliderComponent")
    inColl: StringProperty(name= "Collector to put the imported entity in",
                                description="Collector to put the imported entity in",
                                default='',
                                options={'HIDDEN'})
  
    # ====================== APPEARANCE BLOCK ==========================
    
    show_appearance_selection: BoolProperty(
        name="Appearance Selection",
        description="Enable / Disable selection of entity appearance from dropdown list / old appearance text field",
        default=True
    )
    
    selected_appearance: bpy.props.EnumProperty(
        name="Appearance",
        items=get_appearance_enum_items,
    )
    
    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}
    
    #===================================================================
    
    def draw(self, context):
        cp77_addon_prefs = bpy.context.preferences.addons['i_scene_cp77_gltf'].preferences
        props = context.scene.cp77_panel_props
        layout = self.layout
        box = layout.box()
        box.label(text="Entity Appearance", icon='OUTLINER_OB_GROUP_INSTANCE')
        row = box.row(align=True)
        row.prop(self, "show_appearance_selection", text="Appearance Selection", toggle=True)
        row = box.row(align=True)

        if self.show_appearance_selection:
            #### Appearance selection ####
            items = get_appearance_enum_items(self, context)

            row = box.row(align=True)
            # row.operator("wm.redraw_timer", text="Refresh Appearances", icon='FILE_REFRESH').type = 'DRAW'

            row = box.row(align=True)
            if items and items[0][0] == "default" and len(items) == 1:
                row.label(text="No appearances found")
            else:
                row.label(text=f"Select appearance (Total: {len([i for i in items if i and i[0] not in ('default', 'all')])})")

            row = box.row(align=True)
            row.prop(self, "selected_appearance", text="")
        
        else:
            #### Old text field ####
            row = box.row(align=True)
            split = row.split(factor=0.45, align=True)
            split.label(text="Appearance:")
            split.prop(self, "appearances", text="")


        box = layout.box()
        col = box.column()
        col.prop(props, "with_materials")        
        col.prop(self, 'generate_overrides')
        box = layout.box()
        col = box.column()
        col.prop(props, "use_vulkan")
        col.prop(props, "use_cycles")
        if props.use_cycles:
            col.prop(props, "update_gi")
        if cp77_addon_prefs.experimental_features:
            col.prop(props,"remap_depot")
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

        if self.filepath and self.selected_appearance:
            _last_selected_appearance[self.filepath] = self.selected_appearance
        
        if self.show_appearance_selection and self.selected_appearance:
            if self.selected_appearance in ("NO_APPEARANCES", "SELECT_FILE"):
                apps = ["default"]
            elif self.selected_appearance == "all":
                apps = ["ALL"]
            else:
                apps = [self.selected_appearance]
        else:
            apps = [a.strip() for a in self.appearances.split(",") if a.strip()]
        
        print('apps - ',apps)
        excluded=""
        bob=self.filepath
        inColl=self.inColl
        #print('Bob - ',bob)
        importEnt(props.with_materials, bob, apps, excluded, self.include_collisions, self.include_phys, self.include_entCollider, inColl, props.remap_depot, 
                    meshes=None, mesh_jsons=None, escaped_path=None, app_path=None, anim_files=None, rigjsons=None, generate_overrides=self.generate_overrides)

        return {'FINISHED'}


class CP77StreamingSectorImport(Operator,ImportHelper):

    bl_idname = "io_scene_gltf.cp77sector"
    bl_label = "Import All StreamingSectors from project"
    bl_description = "Load Cyberpunk 2077 Streaming Sectors"

    filter_glob: StringProperty(
        default="*.cpmodproj",
        options={'HIDDEN'},
        )

    filepath: StringProperty(name= "Filepath",
                             subtype = 'FILE_PATH')

    want_collisions: BoolProperty(name="Import Collisions",default=False,description="Import Box and Capsule Collision objects (mesh not yet supported)")
    am_modding: BoolProperty(name="Generate New Collectors",default=False,description="Generate _new collectors for sectors to allow modifications to be saved back to game")
    with_lights: BoolProperty(name="Import Lights",default=True,description="Import and setup Lights based on worldLightNodes")

    def draw(self, context):
        cp77_addon_prefs = bpy.context.preferences.addons['i_scene_cp77_gltf'].preferences
        props = context.scene.cp77_panel_props
        layout = self.layout
        box = layout.box()
        col = box.column()
        col.prop(self, "want_collisions",)
        col.prop(self, "with_lights")
        col.prop(self, "am_modding")
        col.prop(props, "with_materials")
        if cp77_addon_prefs.experimental_features:
            box = layout.box()
            col = box.column()
            col.prop(props,"remap_depot")

    def execute(self, context):
        bob=self.filepath
        props = context.scene.cp77_panel_props
        print('Importing Sectors from project - ',bob)
        importSectors( bob, props.with_materials, props.remap_depot, self.want_collisions, self.am_modding, self.with_lights)
        return {'FINISHED'}


def get_gltf_appearance_items(self, context):
    if not self.filepath:
        return []

    names = []

    base = os.path.splitext(self.filepath)[0]
    material_json = base + ".material.json"

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

    if not names:
        names = ["default"]

    return names
    
def clean_appearance_name(name):
    """Removes digits from app names at the end"""
    return re.sub(r'\d+$', '', name).strip()

def get_gltf_appearance_enum_items(self, context):
    global _appearance_enum_cache

    if not self.filepath:
        _appearance_enum_cache = [("SELECT_FILE", "Select file", "Please select a .glb/.gltf file")]
        return _appearance_enum_cache

    if self.filepath in _appearance_enum_cache:
        return _appearance_enum_cache[self.filepath]

    names = get_gltf_appearance_items(self, context)

    if not names:
        result = [("all", "all", "Import ALL appearances")]
    else:
        if len(names) == 1:
            clean_name = clean_appearance_name(names[0])
            result = [(names[0], clean_name, f"Import appearance: {names[0]}")]
        else:
            result = [
                ("all", "all", "Import ALL appearances"),
                None,
            ]

        sorted_names = sorted(names, key=str.lower)
        for name in sorted_names:
            clean_name = clean_appearance_name(name)
            result.append((name, clean_name, f"Import appearance: {clean_name}"))

    _appearance_enum_cache = result
    return _appearance_enum_cache
    
def update_filepath(self, context):
    try:
        items = get_gltf_appearance_enum_items(self, context)
        self.property_unset("selected_appearance")

        # Всегда выбираем default при смене файла
        self["selected_appearance"] = "default"

    except Exception as e:
        print(f"[CP77] update_filepath error: {e}")
        self["selected_appearance"] = "default"

    for area in context.screen.areas:
        area.tag_redraw()

def update_appearances_logic(self, context):
    if self.all_appearances_toggle:
        self.appearances_buffer = self.appearances
        self.appearances = ""
    else:
        self.appearances = self.appearances_buffer

class CP77Import(Operator, ImportHelper):
    bl_idname = "io_scene_gltf.cp77"
    bl_label = "Import glTF"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Load glTF 2.0 files with Cyberpunk 2077 materials" #Kwek: tooltips towards a more polished UI.
    filter_glob: StringProperty(
        default="*.gltf;*.glb",
        options={'HIDDEN'},
        )
    
    show_appearance_selection: BoolProperty(
        name="Appearance Selection",
        default=True
    )

    selected_appearance: bpy.props.EnumProperty(
        name="Appearances",
        items=get_gltf_appearance_enum_items,
    )

    appearances: StringProperty(
        name="Appearances",
        description="Appearances to extract (comma separated)",
        default="default"
    )

    all_appearances_toggle: bpy.props.BoolProperty(
        name="All Appearances",
        default=False,
        update=update_appearances_logic
    )
    appearances_buffer: bpy.props.StringProperty()
    
    image_format: EnumProperty(
        name="Textures",
        items=(("png", "Use PNG textures", ""),
                ("dds", "Use DDS textures", ""),
                ("jpg", "Use JPG textures", ""),
                ("tga", "Use TGA textures", ""),
                ("bmp", "Use BMP textures", ""),
                ("jpeg", "Use JPEG textures", "")),
        description="Texture Format",
        default="png")
    exclude_unused_mats: BoolProperty(name="Exclude Unused Materials",default=True,description="Enabling this options skips all the materials that aren't being used by any mesh")

    #Kwekmaster: QoL option to match WolvenKit GUI options - Name change to With Materials
    hide_armatures: BoolProperty(name="Hide Armatures",default=True,description="Hide the armatures on imported meshes")

    import_garmentsupport: BoolProperty(name="Import Garment Support (Experimental)",default=True,description="Imports Garment Support mesh data as color attributes")
    generate_overrides: BoolProperty(name="Generate Overrides for Multilayer materials (may be slow)",default=False,description="Imports overrides and palettes for multilayered materials")

    filepath: StringProperty(subtype = 'FILE_PATH', update=update_filepath)

    files: CollectionProperty(type=OperatorFileListElement)
    directory: StringProperty()

    all_appearances_toggle: bpy.props.BoolProperty(name="All Appearances",default=False,update=update_appearances_logic)
    appearances_buffer: bpy.props.StringProperty()
    appearances: StringProperty(name= "Appearances",description="Appearances to extract with models",default="Default")

    scripting: BoolProperty(name="Scripting",default=False ,description="Tell it its being called by a script so it can ignore the gui file lists",options={'HIDDEN'})
    import_tracks: BoolProperty(name="Import Tracks",default=True,description="Import Animation Float Tracks to F-Curves")


    # switch back to operator draw function to align with other UI features
    def draw(self, context):
        cp77_addon_prefs = bpy.context.preferences.addons['i_scene_cp77_gltf'].preferences
        props = context.scene.cp77_panel_props
        layout = self.layout
        
        box = layout.box()
        box.label(text="Mesh Appearance", icon='OUTLINER_OB_GROUP_INSTANCE')

        row = box.row(align=True)
        row.prop(self, "show_appearance_selection", text="Appearance Selection", toggle=True)

        if self.show_appearance_selection:
            # === NEW DROPDOWN LIST ===
            items = get_gltf_appearance_enum_items(self, context)

            row = box.row(align=True)
            # row.operator("wm.redraw_timer", text="Refresh Appearances", icon='FILE_REFRESH').type = 'DRAW'

            row = box.row(align=True)
            if items and items[0][0] == "default" and len(items) == 1:
                row.label(text="No appearances found", icon='INFO')
            else:
                row.label(text=f"Select appearance (Total: {len([i for i in items if i and i[0] not in ('default', 'all')])})")

            row = box.row(align=True)
            row.prop(self, "selected_appearance", text="")

        else:
            # === OLD APPEARANCE TEXT FIELD ===
            box = layout.box()
            box.label(text="Appearances to Import:")

            row = box.row(align=True)
            row.prop(self, "all_appearances_toggle", text="All Appearances")

            if not self.all_appearances_toggle:
                row = box.row(align=True)
                row.prop(self, "appearances", text="")
        
        if not props.with_materials:
            box = layout.box()
            col = box.column()
            col.prop(props, 'with_materials')
            col.prop(self, 'hide_armatures')
            col.prop(self, 'import_garmentsupport')
            if cp77_addon_prefs.experimental_features:
                col.prop(props,"remap_depot")
        if props.with_materials:
            box = layout.box()
            col = box.column()
            col.prop(props, 'with_materials')
            col.prop(self, 'generate_overrides')
            if not self.show_appearance_selection:
                col.prop(self, 'exclude_unused_mats')
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
            if cp77_addon_prefs.experimental_features:
                col.prop(props,"remap_depot")
        box = layout.box()
        col = box.column()
        col.prop(self, 'import_tracks')

    def execute(self, context):
        props = context.scene.cp77_panel_props
        SetVulkanBackend(props.use_vulkan)
        SetCyclesRenderer(props.use_cycles, props.update_gi)
        
        if self.show_appearance_selection and self.selected_appearance:
            if self.selected_appearance in ("NO_APPEARANCES", "SELECT_FILE"):
                appearances = ["default"]
            elif self.selected_appearance == "all":
                appearances = ["ALL"]
            else:
                # Передаём очищенное имя (без цифр), как в старом способе
                clean_name = clean_appearance_name(self.selected_appearance)
                appearances = [clean_name]
        else:
            appearances = [a.strip() for a in self.appearances.split(",") if a.strip()]
        
        print('apps - ', appearances)
        # turns out that multimesh import of an entire car uses a gazillion duplicates as well...
        impinitiated_cache = False
        if not JSONTool._use_cache:
            JSONTool.start_caching()
            impinitiated_cache = True
        CP77GLBimport( props.with_materials, props.remap_depot, self.exclude_unused_mats, self.image_format, self.filepath, self.hide_armatures, self.import_garmentsupport, self.files, self.directory, appearances, self.scripting, self.import_tracks, self.generate_overrides)
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
            self.report({'ERROR'}, "Material was not reloaded: Use Locate Mesh to find a valid source file within a WolvenKit project")
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
        #bpy.data.materials.remove(old_mat)

        return {"FINISHED"}

def menu_func_import(self, context):
    self.layout.operator(CP77Import.bl_idname, text="Cyberpunk GLTF (.gltf/.glb)", icon_value=get_icon('WKIT'))
    self.layout.operator(CP77EntityImport.bl_idname, text="Cyberpunk Entity (.json)", icon_value=get_icon('WKIT'))
    self.layout.operator(CP77StreamingSectorImport.bl_idname, text="Cyberpunk StreamingSector", icon_value=get_icon('WKIT'))
    self.layout.operator(CP77ImportRig.bl_idname, text="Cyberpunk Rig import (.rig.json)", icon_value=get_icon('WKIT'))


operators, other_classes = get_classes(sys.modules[__name__])
_npz_classes = (
    CP77CharacterShapeProps,
    CP77_OT_NpzImportMesh,
    CP77_OT_NpzImportShapeKeys,
    CP77_OT_LoadBaseCharacter,
)


def register_importers():
    for cls in operators:
        if not hasattr(bpy.types, cls.__name__):
            bpy.utils.register_class(cls)
    for cls in other_classes:
        if not hasattr(bpy.types, cls.__name__):
            bpy.utils.register_class(cls)
    for cls in _npz_classes:
        if not hasattr(bpy.types, cls.__name__):
            bpy.utils.register_class(cls)

    bpy.types.Scene.cp77_character_shape = bpy.props.PointerProperty(type=CP77CharacterShapeProps)

    TOPBAR_MT_file_import.append(menu_func_import)


def unregister_importers():
    # Clean up the scene property
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
