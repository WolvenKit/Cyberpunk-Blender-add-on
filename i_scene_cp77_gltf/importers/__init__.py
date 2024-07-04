import bpy
import sys

from bpy_extras.io_utils import ImportHelper
from bpy.props import (StringProperty, EnumProperty, BoolProperty, CollectionProperty)
from bpy.types import (Operator, Panel, OperatorFileListElement, TOPBAR_MT_file_import )
from .import_with_materials import *
from .entity_import import *
from .sector_import import *
from .phys_import import *
from ..main.bartmoss_functions import *
from ..main.common import get_classes
from ..cyber_props import *
from ..cyber_prefs import *
from ..icons.cp77_icons import *


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
        default="*.json",
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
        row.prop(props, "use_cycles")
        if props.use_cycles:
            row = layout.row(align=True)
            row.prop(props, "update_gi")
        row = layout.row(align=True)
        row.prop(props, "with_materials")
        if cp77_addon_prefs.experimental_features:
            row = layout.row(align=True)
            row.prop(props,"remap_depot")
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
        importEnt( bob, apps, excluded, props.with_materials, self.include_collisions, self.include_phys, self.include_entCollider, inColl, props.remap_depot)

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


    def draw(self, context):
        cp77_addon_prefs = bpy.context.preferences.addons['i_scene_cp77_gltf'].preferences
        props = context.scene.cp77_panel_props
        layout = self.layout
        box = layout.box()
        row = box.row(align=True) 
        row.prop(self, "want_collisions",)
        row = layout.row(align=True)
        row.prop(self, "am_modding")
        row = layout.row(align=True)
        row.prop(props, "with_materials")
        if cp77_addon_prefs.experimental_features:
            row = layout.row(align=True)
            row.prop(props,"remap_depot")

    def execute(self, context):
        bob=self.filepath
        props = context.scene.cp77_panel_props
        print('Importing Sectors from project - ',bob)
        importSectors( bob, self.want_collisions, self.am_modding, props.with_materials , props.remap_depot)
        return {'FINISHED'}


class CP77Import(Operator, ImportHelper):
    bl_idname = "io_scene_gltf.cp77"
    bl_label = "Import glTF"
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
                                default="ALL"
                                )

    #kwekmaster: refactor UI layout from the operator.
    def draw(self, context):
        pass

    def execute(self, context):
        props = context.scene.cp77_panel_props
        SetCyclesRenderer(props.use_cycles, props.update_gi)
        CP77GLBimport(self, self.exclude_unused_mats, self.image_format, props.with_materials, self.filepath, self.hide_armatures, self.import_garmentsupport, self.files, self.directory, self.appearances, props.remap_depot)

        return {'FINISHED'}
 

# Material Sub-panel
class CP77_PT_ImportWithMaterial(Panel):
    bl_space_type = 'FILE_BROWSER'
    bl_region_type = 'TOOL_PROPS'
    bl_label = "With Materials"  
    
    @classmethod
    def poll(cls, context):
        operator = context.space_data.active_operator
        return operator.bl_idname == "IO_SCENE_GLTF_OT_cp77"

    def draw_header(self, context):
        props = context.scene.cp77_panel_props
        self.layout.prop(props, "with_materials", text="")
    
    def draw(self, context):
        cp77_addon_prefs = bpy.context.preferences.addons['i_scene_cp77_gltf'].preferences
        props = context.scene.cp77_panel_props
        operator = context.space_data.active_operator
        layout = self.layout
        row = layout.row(align=True)
        layout.enabled = props.with_materials
        row.prop(operator, 'exclude_unused_mats')
        row = layout.row(align=True)
        row.prop(operator, 'image_format')
        row = layout.row(align=True)
        row.prop(operator, 'hide_armatures')
        row = layout.row(align=True)
        row.prop(props, 'use_cycles')
        if cp77_addon_prefs.experimental_features:
            row = layout.row(align=True)
            row.prop(props,"remap_depot")
        if props.use_cycles:
            row = layout.row(align=True)
            row.prop(props, 'update_gi')
        row = layout.row(align=True)
        row.prop(operator, 'import_garmentsupport')


def menu_func_import(self, context):
    self.layout.operator(CP77Import.bl_idname, text="Cyberpunk GLTF (.gltf/.glb)", icon_value=get_icon('WKIT'))
    self.layout.operator(CP77EntityImport.bl_idname, text="Cyberpunk Entity (.json)", icon_value=get_icon('WKIT'))
    self.layout.operator(CP77StreamingSectorImport.bl_idname, text="Cyberpunk StreamingSector", icon_value=get_icon('WKIT'))


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