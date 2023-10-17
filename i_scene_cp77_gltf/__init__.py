import bpy
import bpy.utils.previews
import os
import textwrap

from bpy.props import (
    StringProperty,
    EnumProperty,
    BoolProperty,
    CollectionProperty)
from bpy_extras.io_utils import ImportHelper
from .importers.entity_import import *
from .importers.sector_import import *
from .importers.import_with_materials import *
from bpy_extras.io_utils import ExportHelper
from .exporters.glb_export import *
from .exporters.hp_export import *
from .exporters.collision_export import *
from .exporters.mlsetup_export import *
from .main.collisions import *
from .main.animtools import *
from .main.meshtools import *
from .main.bartmoss_functions import *


bl_info = {
    "name": "Cyberpunk 2077 IO Suite",
    "author": "HitmanHimself, Turk, Jato, dragonzkiller, kwekmaster, glitchered, Simarilius, Doctor Presto, shotlastc",
    "version": (1, 4, 1),
    "blender": (3, 1, 0),
    "location": "File > Import-Export",
    "description": "Import and Export WolvenKit Cyberpunk2077 gLTF models with materials, Import .streamingsector and .ent from .json",
    "warning": "",
    "category": "Import-Export",
}


icons_dir = os.path.join(os.path.dirname(__file__), "icons")
custom_icon_col = {}


class CP77IOSuitePreferences(bpy.types.AddonPreferences):
    bl_idname = __name__
    
    experimental_features: bpy.props.BoolProperty(
    name= "Enable Experimental Features",
    description="Experimental Features for Mod Developers, may encounter bugs",
    default=False,
    )
    

 ## toggle the mod tools tab and its sub panels - default True
    show_modtools: bpy.props.BoolProperty(
    name= "Show the Mod Tools Panel",
    description="Show the Mod tools Tab in the 3d viewport",
    default=True,
    )

    show_meshtools: bpy.props.BoolProperty(
    name= "Show the Mesh Tools Panel",
    description="Show the mesh tools panel",
    default=True,
    )

    show_collisiontools: bpy.props.BoolProperty(
    name= "Show the Collision Tools Panel",
    description="Show the Collision tools panel",
    default=True,
    )

    show_animtools: bpy.props.BoolProperty(
    name= "Show the Animation Tools Panel",
    description="Show the anim tools panel",
    default=True,
    )

    def draw(self, context):           
        layout = self.layout                    
        box = layout.box()
        row = box.row()
        row.prop(self, "experimental_features")
        row.prop(self, "show_modtools")                    
        
        if self.show_modtools:
            box = layout.box()
            row = box.row(align=True)
            row.prop(self, "show_meshtools")
            row.prop(self, "show_collisiontools")
            row.prop(self, "show_animtools")


def SetCyclesRenderer(set_gi_params=False):
    # set the render engine for all scenes to Cycles
    for scene in bpy.data.scenes:
        scene.render.engine = 'CYCLES'

    if set_gi_params:
        cycles = bpy.context.scene.cycles
        cycles.max_bounces = 32
        cycles.caustics_reflective = True
        cycles.caustics_refractive = True
        cycles.diffuse_bounces = 32
        cycles.glossy_bounces = 32
        cycles.transmission_bounces = 32
        cycles.volume_bounces = 32
        cycles.transparent_max_bounces = 32
        cycles.use_fast_gi = False
        cycles.ao_bounces = 1
        cycles.ao_bounces_render = 1


class CP77_PT_PanelProps(bpy.types.PropertyGroup):
   
# collision panel props:
    collider_type: bpy.props.EnumProperty(
        name="Collision Type",
        items=[
        ('VEHICLE', "Vehicle Collision", "Generate .phys formatted collisions for a vehicle mod"),
        ('ENTITY', "Entity Collision", "Generate entCollisionComponents"),
        ],
        default='VEHICLE'
    ) 

    collision_shape: bpy.props.EnumProperty(
        name="Collision Shape",
        items=[
        ('CONVEX', "Convex Collider", "Generate a Convex Collider"),
        ('BOX', "Box Collider", "Generate a Box Collider"),
        ('CAPSULE', "Capsule Collider", "Generate a Capsule Collider")
        ],
        default='CONVEX'
    )

    matchSize: bpy.props.BoolProperty(        
        name="Match the Shape of Existing Mesh",
        description="Match the size of the selected Mesh",
        default=True,

    )

    radius: bpy.props.FloatProperty(
        name="Radius",
        description="Enter the Radius value of the capsule",
        default=0,
        min=0,
        max=100,
        step=1,
    )

    height: bpy.props.FloatProperty(
        name="height",
        description="Enter the height of the capsule",
        default=0,
        min=0,
        max=1000,
        step=1,
    )

    sampleverts: bpy.props.IntProperty(
        name="Vertices to Sample",
        description="This is the number of vertices in your new collider",
        default=0,
        min=0,
        max=100,
    )

# anims props"
    frameall: BoolProperty(
        name="All Frames",
        default=False,
        description="Insert a keyframe on every frame of the active action"
    )
    
    body_list: bpy.props.EnumProperty(
        items=[(name, name, '') for name in cp77riglist(None)[1]],
        name="Rig GLB"
    )
    
# mesh props
    fbx_rot: BoolProperty(
        name="",
        default=False,
        description="Rotate for an fbx orientated mesh"
    )

    refit_json: bpy.props.EnumProperty(
        items=[(target_body_names, target_body_names, '') for target_body_names in CP77RefitList(None)[1]],
        name="Body Shape"
    )

    selected_armature: bpy.props.EnumProperty(
        items=CP77ArmatureList
    )

    mesh_source: bpy.props.EnumProperty(
        items=CP77MeshList
    ) 

    mesh_target: bpy.props.EnumProperty(
        items=CP77MeshList
    )   

class CP77CollisionGenerator(bpy.types.Operator):
    bl_idname = "generate_cp77.collisions"
    bl_label = "Generate Collider"
    bl_options = {'REGISTER', "UNDO"}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        props = context.scene.cp77_panel_props
        CP77CollisionGen(self, context,props.matchSize, props.collision_shape, props.sampleverts, props.radius, props.height)
        return {"FINISHED"}
    
    def draw(self, context):
        props = context.scene.cp77_panel_props
        layout = self.layout
        row = layout.row(align=True)
        split = row.split(factor=0.5,align=True)
        split.label(text="Collision Shape:")
        split.prop(props, 'collision_shape', text="")
        row = layout.row(align=True)
        
        if props.collision_shape == 'CONVEX':
            row.label(text="Vertices to Sample:")
            row.prop(props,"sampleverts", text="")

        if props.collision_shape == 'CAPSULE':
            row.prop(props, "matchSize", text="Match the size of the selected mesh")
            if not props.matchSize:
                row = layout.row(align=True)
                row.label(text="Radius:")
                row.prop(props, "radius", text="")
                row.label(text="Height:")
                row.prop(props, "height", text="")
            

class CP77CollisionExport(bpy.types.Operator):
    bl_idname = "export_scene.collisions"
    bl_label = "Export Collisions to .JSON"
    bl_parent_id = "CP77_PT_collisions"
    bl_description = "Export these collisions to .phys.json"

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
  
    def execute(self, context):
        cp77_collision_export(self.filepath)
        return {"FINISHED"}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}


class CP77_PT_CollisionTools(bpy.types.Panel):
    bl_label = "Collision Tools"
    bl_idname = "CP77_PT_collisions"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "CP77 Modding"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.type == 'MESH'

    def draw(self, context):
        layout = self.layout
        cp77_addon_prefs = context.preferences.addons[__name__].preferences

        if cp77_addon_prefs.show_modtools:
            if cp77_addon_prefs.show_collisiontools:
                box = layout.box()
                if context.mode == 'EDIT_MESH':
                    box.operator("generate_cp77.collisions")
                box.operator("export_scene.collisions")


def CP77AnimsList(self, context):
    for action in bpy.data.actions:
        if action.library:
            continue
        yield action


### allow deleting animations from the animset panel, regardless of editor context
class CP77AnimsDelete(bpy.types.Operator):
    bl_idname = 'cp77.delete_anims'
    bl_label = "Delete action"
    bl_options = {'INTERNAL', 'UNDO'}
    bl_description = "Delete this action"

    name: bpy.props.StringProperty()

    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.animation_data

    def execute(self, context):
        delete_anim(self, context)
        return{'FINISHED'}


# this class is where most of the function is so far - play/pause 
# Todo: fix renaming actions from here
class CP77Animset(bpy.types.Operator):
    bl_idname = 'cp77.set_animset'
    bl_label = "Available Animsets"
    bl_options = {'INTERNAL', 'UNDO'}

    name: bpy.props.StringProperty(options={'HIDDEN'})
    new_name: bpy.props.StringProperty(name="New name", default="")
    play: bpy.props.BoolProperty(options={'HIDDEN'}, default=False)

    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.animation_data

    def execute(self, context):
        obj = context.active_object
        if not self.name:
            obj.animation_data.action = None
            return {'FINISHED'}

        action = bpy.data.actions.get(self.name, None)
        if not action:
            return {'CANCELLED'}

        # Always save it, just in case
        action.use_fake_user = True

        if self.new_name:
            # Rename
            action.name = self.new_name
        elif not self.play and obj.animation_data.action == action:
            # Action was already active, stop editing
            obj.animation_data.action = None
        else:
            reset_armature(self,context)
            obj.animation_data.action = action

            if self.play:
                context.scene.frame_current = int(action.curve_frame_range[0])
                bpy.ops.screen.animation_cancel(restore_frame=False)
                play_anim(self,context,action.name)

        return {'FINISHED'}

    def invoke(self, context, event):
        if event.ctrl:
            self.new_name = self.name
            return context.window_manager.invoke_props_dialog(self)
        else:
            self.new_name = ""
            return self.execute(context)

# inserts a keyframe on the current frame
class CP77Keyframe(bpy.types.Operator):
    bl_idname = "insert_keyframe.cp77"
    bl_parent_id = "CP77_PT_animspanel"
    bl_label = "Keyframe Pose"
    bl_description = "Insert a Keyframe"

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        props = context.scene.cp77_panel_props
        cp77_keyframe(props, context, props.frameall)
        return {"FINISHED"}
    
    def draw(self, context):
        layout = self.layout
        props = context.scene.cp77_panel_props
        row = layout.row(align=True)
        row.label(text="Insert a keyframe for every bone at every from of the animation")
        row = layout.row(align=True)
        row.prop(props, "frameall", text="")

    
class CP77ResetArmature(bpy.types.Operator):
    bl_idname = "reset_armature.cp77"
    bl_parent_id = "CP77_PT_animspanel"
    bl_label = "Reset Pose"
    bl_description = "Clear all transforms on current selected armature"

    def execute(self, context):
        reset_armature(self, context)
        return {"FINISHED"}


class CP77NewAction(bpy.types.Operator):

    bl_idname = 'cp77.new_action'
    bl_label = "Add Action"
    bl_options = {'INTERNAL', 'UNDO'}

    name: bpy.props.StringProperty(default="New action")

    @classmethod
    def poll(cls, context):
        return context.active_object is not None

    def execute(self, context):
        obj = context.active_object


    def invoke(self, context, event):
        obj = context.active_object
        if not obj.animation_data:
            obj.animation_data_create()
        new_action = bpy.data.actions.new(self.name)
        new_action.use_fake_user = True
        reset_armature(obj, context)
        obj.animation_data.action = new_action
        return {'FINISHED'}
    

class CP77RigLoader(bpy.types.Operator):
    bl_idname = "cp77.rig_loader"
    bl_label = "Load rigs from .glb"

    def execute(self, context):
        props = context.scene.cp77_panel_props
        selected_rig_name = props.body_list
        rig_files, rig_names = cp77riglist(context)

        if selected_rig_name in rig_names:
            # Find the corresponding .glb file and load it
            selected_rig = rig_files[rig_names.index(selected_rig_name)]
            bpy.ops.import_scene.gltf(filepath=selected_rig)
            if props.fbx_rot:
                rotate_quat_180(self,context)
        return {'FINISHED'}


### Draw a panel to store anims functions
class CP77_PT_AnimsPanel(bpy.types.Panel):
    bl_idname = "CP77_PT_animspanel"
    bl_label = "Animation Tools"
    bl_category = "CP77 Modding"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_options = {'DEFAULT_CLOSED'}

    name: bpy.props.StringProperty(options={'HIDDEN'})

## make sure the context is unrestricted as possible, ensure there's an armature selected 
    def draw(self, context):
        layout = self.layout 

        cp77_addon_prefs = context.preferences.addons[__name__].preferences

        if cp77_addon_prefs.show_animtools:
            props = context.scene.cp77_panel_props
            if bpy.context.mode in {'OBJECT', 'POSE', 'EDIT'}:
                box = layout.box()
                box.label(text='Rigs', icon_value=custom_icon_col["import"]['WKIT'].icon_id)
                row = box.row(align=True)
                row.label(text='Rig:')
                row.prop(props, 'body_list', text="",)
                row = box.row(align=True)
                row.operator('cp77.rig_loader',icon='ADD', text="load selected rig")
                row.prop(props, 'fbx_rot', text="", icon='LOOP_BACK', toggle=1)
                row = box.row(align=True)
                row = box.row(align=True)
                row.operator('insert_keyframe.cp77')
                row.operator('reset_armature.cp77')

                obj = context.active_object
                if obj and obj.type == 'ARMATURE':
                    available_anims = list(CP77AnimsList(context,obj))
                    active_action = obj.animation_data.action if obj.animation_data else None
                    box = layout.box()
                    row = box.row(align=True)
                    row.label(text='Animsets', icon_value=custom_icon_col["import"]['WKIT'].icon_id)
                    row.operator('cp77.new_action',icon='ADD', text="")
                    if available_anims:
                        col = box.column(align=True)
                        for action in available_anims:
                            action.use_fake_user:True
                            selected = action == active_action
                            row = col.row(align=True)
                            sub = row.column(align=True)
                            sub.ui_units_x = 1.0
                            if selected and context.screen.is_animation_playing:
                                op = sub.operator('screen.animation_cancel', icon='PAUSE', text=action.name, emboss=True)
                                op.restore_frame = False
                            else:
                                icon = 'PLAY' if selected else 'TRIA_RIGHT'
                                op = sub.operator('cp77.set_animset', icon=icon, text="", emboss=True)
                                op.name = action.name
                                op.play = True

                                op = row.operator('cp77.set_animset', text=action.name)
                                op.name = action.name
                                op.play = False
                                row.operator('cp77.delete_anims', icon='X', text="").name = action.name


class CollectionAppearancePanel(bpy.types.Panel):
    bl_label = "Ent Appearances"
    bl_idname = "PANEL_PT_appearance_variants"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "collection"

    #only draw the if the collector has an appearanceName property
    @classmethod
    def poll(cls, context):
        collection = context.collection
        return hasattr(collection, "appearanceName")

    def draw(self, context):
        layout = self.layout
        collection = context.collection
        layout.prop(collection, "appearanceName")

    
class CP77Autofitter(bpy.types.Operator):
    bl_idname = "cp77.auto_fitter"
    bl_label = "Auto Fit"

    def execute(self, context):
        props = context.scene.cp77_panel_props
        target_body_name = props.refit_json
        target_body_paths, target_body_names = CP77RefitList(context)
        refitter = CP77RefitChecker(self, context)  

        if target_body_name in target_body_names:          
            target_body_path = target_body_paths[target_body_names.index(target_body_name)]
            CP77Refit(context, refitter, target_body_path, target_body_name, props.fbx_rot)

            return {'FINISHED'}


class CP77WeightTransfer(bpy.types.Operator):
    bl_idname = 'cp77.trans_weights'
    bl_label = "Transfer weights from one mesh to another"
    bl_description = "Transfer weights from source mesh to target mesh"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # Call the trans_weights function with the provided arguments
        result = trans_weights(self, context)
        return {"FINISHED"}


class CP77UVTool(bpy.types.Operator):
    bl_idname = 'cp77.uv_checker'
    bl_label = "UV Checker"
    bl_description = "Apply a texture to assist with UV coordinate mapping"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        CP77UvChecker(self, context)
        return {"FINISHED"}
        
        
class CP77HairProfileExport(bpy.types.Operator):
    bl_idname = "export_scene.hp"
    bl_label = "Export Hair Profile"
    bl_description ="Generates a new .hp.json in your mod project folder which can be imported in Wolvenkit"
    bl_parent_id = "CP77_PT_MeshTools"

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")

    def execute(self, context):
        cp77_hp_export(self.filepath)
        return {"FINISHED"}


class CP77MlSetupExport(bpy.types.Operator):
    bl_idname = "export_scene.mlsetup"
    bl_label = "Export MLSetup"
    bl_parent_id = "CP77_PT_MeshTools"

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
  
    def execute(self, context):
        cp77_mlsetup_export(self, context)
        return {"FINISHED"}


class CP77SetArmature(bpy.types.Operator):
    bl_idname = "cp77.set_armature"
    bl_label = "Change Armature Target"
    bl_parent_id = "CP77_PT_MeshTools"
    
    def execute(self, context):
        CP77ArmatureSet(self,context)
        return {'FINISHED'}


class CP77GroupVerts(bpy.types.Operator):
    bl_idname = "cp77.group_verts"
    bl_parent_id = "CP77_PT_MeshTools"
    bl_label = "Assign to Nearest Group"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        CP77GroupUngroupedVerts(self, context)
        return {'FINISHED'}


class CP77_PT_MeshTools(bpy.types.Panel):
    bl_label = "Mesh Tools"
    bl_idname = "CP77_PT_MeshTools"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "CP77 Modding"
    bl_options = {'DEFAULT_CLOSED'}
   
    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.type == 'MESH'

    def draw(self, context):
        layout = self.layout
        props = context.scene.cp77_panel_props
        cp77_addon_prefs = context.preferences.addons[__name__].preferences
        if cp77_addon_prefs.show_modtools:
            if cp77_addon_prefs.show_meshtools:
                box = layout.box()
                box.label(text="Mesh Cleanup", icon_value=custom_icon_col["trauma"]["TRAUMA"].icon_id)
                row = box.row(align=True)
                row.operator("cp77.group_verts", text="Group Ungrouped Verts")
                row = box.row(align=True)
                row.operator("cp77.uv_checker", text="UV Checker")
                box = layout.box()
                box.label(icon_value=custom_icon_col["sculpt"]["SCULPT"].icon_id, text="Modelling:")
                row = box.row(align=True)
                split = row.split(factor=0.5,align=True)
                split.label(text="Source Mesh:")
                split.prop(props, "mesh_source", text="")
                row = box.row(align=True)
                split = row.split(factor=0.5,align=True)
                split.label(text="Target Mesh:")
                split.prop(props, "mesh_target", text="")
                row = box.row(align=True)
                box.operator("cp77.trans_weights", text="Transfer Vertex Weights")
                box = layout.box()
                box.label(icon_value=custom_icon_col["refit"]["REFIT"].icon_id, text="Autofitter:")
                row = box.row(align=True)
                split = row.split(factor=0.29,align=True)
                split.label(text="Shape:")
                split.prop(props, 'refit_json', text="")
                row = box.row(align=True)
                row.operator("cp77.auto_fitter", text="Refit Selected Mesh")
                row.prop(props, 'fbx_rot', text="", icon='LOOP_BACK', toggle=1)
                box = layout.box()
                box.label(icon_value=custom_icon_col["tech"]["TECH"].icon_id, text="Modifiers:")
                row = box.row(align=True)
                split = row.split(factor=0.35,align=True)
                split.label(text="Target:")
                split.prop(props, "selected_armature", text="")
                row = box.row(align=True)
                row.operator("cp77.set_armature", text="Change Armature Target")
                box = layout.box()
                box.label(text="Material Export", icon="MATERIAL")
                box.operator("export_scene.hp")
                if context.preferences.addons[__name__].preferences.experimental_features:
                    box.operator("export_scene.mlsetup")
        

## adds a message box for the exporters to use for error notifications, will also be used later for redmod integration    
class ShowMessageBox(bpy.types.Operator):
    bl_idname = "cp77.message_box"
    bl_label = "Message"

    message: bpy.props.StringProperty(default="")

    def execute(self, context):
        self.report({'INFO'}, self.message)
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=300)

    def draw(self, context):
        wrapp = textwrap.TextWrapper(width=50) #50 = maximum length       
        wList = wrapp.wrap(text=self.message) 
        for text in wList: 
            row = self.layout.row(align = True)
            row.alignment = 'EXPAND'
            row.label(text=text)     
        
class CP77GLBExport(bpy.types.Operator,ExportHelper):
  ### cleaned this up and moved most code to exporters.py
    bl_idname = "export_scene.cp77_glb"
    bl_label = "Export for Cyberpunk"
    bl_options = {'REGISTER','UNDO'}
    filename_ext = ".glb"
   ### adds a checkbox for anim export settings
    filter_glob: StringProperty(default="*.glb", options={'HIDDEN'})
    export_poses: BoolProperty(
        name="As Photomode Pose",
        default=False,
        description="Use this option if you are exporting anims to be imported into wkit as .anim"
    )
    def draw(self, context):
        layout = self.layout
        layout.prop(self, "export_poses")
        
    def execute(self, context):
        export_cyberpunk_glb(context, self.filepath, self.export_poses)
        return {'FINISHED'}


class CP77EntityImport(bpy.types.Operator,ImportHelper):

    bl_idname = "io_scene_gltf.cp77entity"
    bl_label = "Import Ent from JSON"
    
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
      
    update_gi: BoolProperty(name="Update Global Illumination",default=True,description="Update Cycles global illumination options for transparency fixes and higher quality renders")
    with_materials: BoolProperty(name="With Materials",default=True,description="Import Wolvenkit-exported materials")   
    include_collisions: BoolProperty(name="Include Vehicle Collisions",default=False,description="Use this option if you want to include the .phys collision info for vehicle modding")
     
    def execute(self, context):
        SetCyclesRenderer(self.update_gi)

        apps=self.appearances.split(",")
        print('apps - ',apps)
        excluded=""
        bob=self.filepath
        #print('Bob - ',bob)
        importEnt( bob, apps, excluded,self.with_materials, self.include_collisions)

        return {'FINISHED'}

class CP77StreamingSectorImport(bpy.types.Operator,ImportHelper):

    bl_idname = "io_scene_gltf.cp77sector"
    bl_label = "Import All StreamingSectors from project"
    
    filter_glob: StringProperty(
        default="*.cpmodproj",
        options={'HIDDEN'},
        )
    
    filepath: StringProperty(name= "Filepath",
                             subtype = 'FILE_PATH')

    want_collisions: BoolProperty(name="Import Collisions",default=False,description="Import Box and Capsule Collision objects (mesh not yet supported)")
    am_modding: BoolProperty(name="Generate New Collectors",default=False,description="Generate _new collectors for sectors to allow modifications to be saved back to game")
    with_materials: BoolProperty(name="With Materials",default=False,description="Import Wolvenkit-exported materials")

    def execute(self, context):
        bob=self.filepath
        print('Importing Sectors from project - ',bob)
        importSectors( bob, self.want_collisions, self.am_modding, self.with_materials)
        return {'FINISHED'}

# Material Sub-panel
class CP77_PT_ImportWithMaterial(bpy.types.Panel):
    bl_space_type = 'FILE_BROWSER'
    bl_region_type = 'TOOL_PROPS'
    bl_label = "With Materials"

    @classmethod
    def poll(cls, context):
        operator = context.space_data.active_operator
        return operator.bl_idname == "IO_SCENE_GLTF_OT_cp77"

    def draw_header(self, context):
        operator = context.space_data.active_operator
        self.layout.prop(operator, "with_materials", text="")

    def draw(self, context):
        operator = context.space_data.active_operator
        layout = self.layout
        layout.enabled = operator.with_materials
        layout.use_property_split = True
        layout.prop(operator, 'exclude_unused_mats')
        layout.prop(operator, 'image_format')
        layout.prop(operator, 'hide_armatures')
        layout.prop(operator, 'update_gi')
        layout.prop(operator, 'import_garmentsupport')


# Material Sub-panel
class CP77_PT_ImportWithMaterial(bpy.types.Panel):
    bl_space_type = 'FILE_BROWSER'
    bl_region_type = 'TOOL_PROPS'
    bl_label = "With Materials"

    @classmethod
    def poll(cls, context):
        operator = context.space_data.active_operator
        return operator.bl_idname == "IO_SCENE_GLTF_OT_cp77"

    def draw_header(self, context):
        operator = context.space_data.active_operator
        self.layout.prop(operator, "with_materials", text="")

    def draw(self, context):
        operator = context.space_data.active_operator
        layout = self.layout
        layout.enabled = operator.with_materials
        layout.use_property_split = True
        layout.prop(operator, 'exclude_unused_mats')
        layout.prop(operator, 'image_format')
        layout.prop(operator, 'hide_armatures')
        layout.prop(operator, 'update_gi')
        layout.prop(operator, 'import_garmentsupport')


class CP77Import(bpy.types.Operator,ImportHelper):
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
    with_materials: BoolProperty(name="With Materials",default=True,description="Import mesh with Wolvenkit-exported materials")

    hide_armatures: BoolProperty(name="Hide Armatures",default=True,description="Hide the armatures on imported meshes")

    update_gi: BoolProperty(name="Update Global Illumination",default=True,description="Update Cycles global illumination options for transparency fixes and higher quality renders")

    import_garmentsupport: BoolProperty(name="Import Garment Support (Experimental)",default=True,description="Imports Garment Support mesh data as color attributes")
    
    filepath: StringProperty(subtype = 'FILE_PATH')

    files: CollectionProperty(type=bpy.types.OperatorFileListElement)
    directory: StringProperty()
    
    appearances: StringProperty(name= "Appearances",
                                description="Appearances to extract with models",
                                default="ALL",
                                options={'HIDDEN'}
                                )

    #kwekmaster: refactor UI layout from the operator.
    def draw(self, context):
        pass

    def execute(self, context):
        SetCyclesRenderer(self.update_gi)
        CP77GLBimport(self, self.exclude_unused_mats, self.image_format, self.with_materials, self.filepath, self.hide_armatures, self.import_garmentsupport, self.files, self.directory, self.appearances)

        return {'FINISHED'}

def menu_func_import(self, context):
    self.layout.operator(CP77Import.bl_idname, text="Cyberpunk GLTF (.gltf/.glb)", icon_value=custom_icon_col["import"]['WKIT'].icon_id)
    self.layout.operator(CP77EntityImport.bl_idname, text="Cyberpunk Entity (.json)", icon_value=custom_icon_col["import"]['WKIT'].icon_id)
    self.layout.operator(CP77StreamingSectorImport.bl_idname, text="Cyberpunk StreamingSector", icon_value=custom_icon_col["import"]['WKIT'].icon_id)

def menu_func_export(self, context):
    self.layout.operator(CP77GLBExport.bl_idname, text="Export Selection to GLB for Cyberpunk", icon_value=custom_icon_col["import"]['WKIT'].icon_id)
    
#kwekmaster - Minor Refactoring 
classes = (
    CP77Import,
    CP77EntityImport,
    CP77_PT_ImportWithMaterial,
    CP77StreamingSectorImport,
    CP77GLBExport,
    ShowMessageBox,
    CP77_PT_AnimsPanel,
    CP77Keyframe,
    CP77_PT_CollisionTools,
    CP77CollisionExport,
    CP77CollisionGenerator,
    CP77Animset,
    CP77AnimsDelete,
    CP77IOSuitePreferences,
    CollectionAppearancePanel,
    CP77HairProfileExport,
    CP77_PT_MeshTools,
    CP77Autofitter,
    CP77NewAction,
    CP77RigLoader,
    CP77SetArmature,
    CP77_PT_PanelProps,
    CP77GroupVerts,
    CP77UVTool,
    CP77MlSetupExport,
    CP77WeightTransfer,
    CP77ResetArmature,
)

def register():
    custom_icon = bpy.utils.previews.new()
    custom_icon.load("WKIT", os.path.join(icons_dir, "wkit.png"), 'IMAGE')

    sculpt_icon = bpy.utils.previews.new()
    sculpt_icon.load("SCULPT", os.path.join(icons_dir, "sculpt.png"), 'IMAGE')

    cleanup_icon = bpy.utils.previews.new()
    cleanup_icon.load("TRAUMA", os.path.join(icons_dir, "trauma.png"), 'IMAGE')

    tech_icon = bpy.utils.previews.new()
    tech_icon.load("TECH", os.path.join(icons_dir, "tech.png"), 'IMAGE')

    refit_icon = bpy.utils.previews.new()
    refit_icon.load("REFIT", os.path.join(icons_dir, "refit.png"), 'IMAGE')


    custom_icon_col["import"] = custom_icon
    custom_icon_col["trauma"] = cleanup_icon
    custom_icon_col["tech"] = tech_icon
    custom_icon_col["sculpt"] = sculpt_icon
    custom_icon_col["refit"] = refit_icon

    #kwekmaster - Minor Refactoring 
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.cp77_panel_props = bpy.props.PointerProperty(type=CP77_PT_PanelProps) 
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export) 
    
def unregister():
    del bpy.types.Scene.cp77_panel_props
    for icon_key in custom_icon_col.keys():
        bpy.utils.previews.remove(custom_icon_col[icon_key])


    #kwekmaster - Minor Refactoring 
    for cls in classes:
        bpy.utils.unregister_class(cls)

    
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
    custom_icon_col.clear()
                
if __name__ == "__main__":
    register()

