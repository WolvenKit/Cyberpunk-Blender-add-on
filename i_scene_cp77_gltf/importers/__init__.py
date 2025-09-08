import bpy
import sys

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


class CP77EntityImport(Operator,ImportHelper):

    bl_idname = "io_scene_gltf.cp77entity"
    bl_label = "Import Ent from JSON"
    bl_description = "Import Characters and Vehicles from Cyberpunk 2077 Entity Files"

    filter_glob: StringProperty(
        default="*.ent.json",
        options={'HIDDEN'},
        )

    filepath: StringProperty(name= "Filepath",
                             subtype = 'FILE_PATH')

    appearances: StringProperty(name= "Appearances",
                                description="Entity Appearances to extract. Needs appearanceName from ent. Comma seperate multiples",
                                default="default",
                                )
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
  
    def draw(self, context):
        cp77_addon_prefs = bpy.context.preferences.addons['i_scene_cp77_gltf'].preferences
        props = context.scene.cp77_panel_props
        layout = self.layout
        row = layout.row(align=True)
        split = row.split(factor=0.45,align=True)
        split.label(text="Ent Appearance:")
        split.prop(self, "appearances", text="")
        row = layout.row(align=True)
        box = layout.box()
        col = box.column()
        col.prop(props, "with_materials")
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
        SetCyclesRenderer(props.use_cycles, props.update_gi)

        apps=self.appearances.split(",")
        print('apps - ',apps)
        excluded=""
        bob=self.filepath
        inColl=self.inColl
        #print('Bob - ',bob)
        importEnt(props.with_materials, bob, apps, excluded, self.include_collisions, self.include_phys, self.include_entCollider, inColl, props.remap_depot, meshes=None, mesh_jsons=None, escaped_path=None, app_path=None, anim_files=None, rigjsons=None)

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


class CP77Import(Operator, ImportHelper):
    bl_idname = "io_scene_gltf.cp77"
    bl_label = "Import glTF"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Load glTF 2.0 files with Cyberpunk 2077 materials" #Kwek: tooltips towards a more polished UI.
    filter_glob: StringProperty(
        default="*.gltf;*.glb",
        options={'HIDDEN'},
        )
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

    filepath: StringProperty(subtype = 'FILE_PATH')

    files: CollectionProperty(type=OperatorFileListElement)
    directory: StringProperty()

    appearances: StringProperty(name= "Appearances",
                                description="Appearances to extract with models",
                                default="Default"
                                )
    scripting: BoolProperty(name="Scripting",default=False ,description="Tell it its being called by a script so it can ignore the gui file lists",options={'HIDDEN'})
    import_tracks: BoolProperty(name="Import Tracks",default=True,description="Import Animation Float Tracks to F-Curves")


    # switch back to operator draw function to align with other UI features
    def draw(self, context):
        cp77_addon_prefs = bpy.context.preferences.addons['i_scene_cp77_gltf'].preferences
        props = context.scene.cp77_panel_props
        layout = self.layout
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
            box.label(text='Appearances to Import:')
            box.prop(self, 'appearances', text='')
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
        appearances=self.appearances.split(",")
        # turns out that multimesh import of an entire car uses a gazillion duplicates as well...
        JSONTool.start_caching()
        CP77GLBimport( props.with_materials, props.remap_depot, self.exclude_unused_mats, self.image_format, self.filepath, self.hide_armatures, self.import_garmentsupport, self.files, self.directory, appearances, self.scripting, self.import_tracks)
        JSONTool.stop_caching()

        return {'FINISHED'}

class CP77MaterialReload(Operator):
    bl_idname = "reload_material.cp77"
    bl_label = "Reload Material"
    bl_options = {'REGISTER', 'UNDO'}
    bl_parent_id = "CP77_PT_MaterialTools"
    bl_description = """Reload the active material from json.
WARNING! All data within the active material will be deleted"""

    def execute(self, context):
        try:
            reload_mats(self, context)

        except Exception as e:
            print("Exception when trying to import mats: " + str(e))
            raise e

        return {"FINISHED"}

def menu_func_import(self, context):
    self.layout.operator(CP77Import.bl_idname, text="Cyberpunk GLTF (.gltf/.glb)", icon_value=get_icon('WKIT'))
    self.layout.operator(CP77EntityImport.bl_idname, text="Cyberpunk Entity (.json)", icon_value=get_icon('WKIT'))
    self.layout.operator(CP77StreamingSectorImport.bl_idname, text="Cyberpunk StreamingSector", icon_value=get_icon('WKIT'))
    self.layout.operator(CP77ImportRig.bl_idname, text="Cyberpunk Rig import (.rig.json)", icon_value=get_icon('WKIT'))


operators, other_classes = get_classes(sys.modules[__name__])

def register_importers():
    for cls in operators:
        if not hasattr(bpy.types, cls.__name__):
            bpy.utils.register_class(cls)
    for cls in other_classes:
        if not hasattr(bpy.types, cls.__name__):
            bpy.utils.register_class(cls)
    TOPBAR_MT_file_import.append(menu_func_import)

def unregister_importers():
    for cls in reversed(other_classes):
        if hasattr(bpy.types, cls.__name__):
            bpy.utils.unregister_class(cls)
    for cls in reversed(operators):
        if hasattr(bpy.types, cls.__name__):
            bpy.utils.unregister_class(cls)
    TOPBAR_MT_file_import.remove(menu_func_import)